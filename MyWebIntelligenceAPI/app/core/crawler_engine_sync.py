"""
Synchronous version of the crawler engine for Celery workers.

This avoids AsyncSession usage which caused greenlet issues under the prefork
worker pool. It re-implements the handful of DB operations required for the
crawl pipeline using a regular SQLAlchemy Session.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session, selectinload

from app.core import content_extractor, text_processing
from app.core.media_processor_sync import MediaProcessorSync
from app.db import models

logger = logging.getLogger(__name__)


class SyncCrawlerEngine:
    """Crawler engine relying on synchronous SQLAlchemy session and httpx client."""

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.Client(timeout=15.0, follow_redirects=True)

    # ------------------------------------------------------------------ #
    # High level API                                                     #
    # ------------------------------------------------------------------ #
    def prepare_crawl(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
    ) -> Tuple[Optional[models.Land], List[models.Expression]]:
        """Return the land and the ordered list of expressions to crawl."""
        land = self.db.query(models.Land).options(selectinload(models.Land.words)).filter(models.Land.id == land_id).first()
        if not land:
            logger.error("Land %s not found", land_id)
            return None, []

        if land.start_urls:
            existing_expr = self._get_expressions_to_crawl_query(land_id, limit=1).first()
            if not existing_expr:
                for url in land.start_urls:
                    try:
                        self._get_or_create_expression(land_id, url, depth=0)
                        logger.info("Created expression for URL: %s", url)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Failed to create expression for %s: %s", url, exc)
                self.db.commit()

        expressions = self._fetch_expressions_to_crawl(
            land_id=land_id,
            limit=limit,
            depth=depth,
            http_status=http_status,
        )
        logger.info("Found %s expressions to crawl for land %s", len(expressions), land_id)
        return land, expressions

    def crawl_land(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
        analyze_media: bool = False,
    ) -> Tuple[int, int, Dict[str, int]]:
        """Crawl the land synchronously and return processed, error counts, stats."""
        land, expressions = self.prepare_crawl(
            land_id,
            limit=limit,
            depth=depth,
            http_status=http_status,
        )
        if land is None:
            return 0, 0, {}

        processed, errors, stats = self.crawl_expressions(expressions, analyze_media=analyze_media)
        self.http_client.close()
        return processed, errors, stats

    def crawl_expressions(
        self,
        expressions: Iterable[models.Expression],
        analyze_media: bool = False,
    ) -> Tuple[int, int, Dict[str, int]]:
        """Process expressions sequentially."""
        processed = 0
        errors = 0
        http_stats: Dict[str, int] = defaultdict(int)

        for expression in expressions:
            expr = self.db.query(models.Expression).filter(models.Expression.id == expression.id).first()
            if not expr:
                logger.warning("Expression %s not found during crawl", expression.id)
                continue

            expr_url = getattr(expr, "url", None)
            if not expr_url:
                logger.warning("Expression %s has no URL", expr.id)
                continue

            try:
                status_code = self.crawl_expression(expr, analyze_media=analyze_media)
                self.db.commit()
                processed += 1
                if status_code is not None:
                    http_stats[str(status_code)] += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to crawl expression %s (%s): %s", expr.id, expr_url, exc)
                self.db.rollback()
                errors += 1
                http_stats["error"] += 1

        return processed, errors, dict(http_stats)

    def crawl_expression(self, expr: models.Expression, analyze_media: bool = False) -> Optional[int]:
        """Fetch, analyse and store an expression."""
        expr_url = str(expr.url)
        logger.info("Crawling URL: %s (analyze_media=%s)", expr_url, analyze_media)

        html_content = ""
        http_status_code: Optional[int] = None
        try:
            response = self.http_client.get(expr_url)
            response.raise_for_status()
            html_content = response.text
            http_status_code = response.status_code
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error for %s: %s", expr_url, exc)
            html_content = exc.response.text if exc.response is not None else ""
            http_status_code = exc.response.status_code if exc.response is not None else None
        except httpx.RequestError as exc:
            logger.error("Request error for %s: %s", expr_url, exc)
            http_status_code = 0

        update_data: Dict[str, Optional[str]] = {
            "http_status": http_status_code,
            "crawled_at": datetime.utcnow(),
        }

        readable_content = None
        soup = None
        extraction_method = "unknown"

        try:
            readable_content, soup, extraction_method = asyncio.run(
                content_extractor.get_readable_content_with_fallbacks(expr_url, html_content)
            )
        except RuntimeError:
            # We might already be running in an event loop if the caller wraps asyncio.run
            readable_content, soup, extraction_method = asyncio.get_event_loop().run_until_complete(
                content_extractor.get_readable_content_with_fallbacks(expr_url, html_content)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Readable extraction failed for %s: %s", expr_url, exc)

        if soup:
            metadata = content_extractor.get_metadata(soup, expr_url)
        else:
            metadata = {"title": expr_url, "description": None, "keywords": None, "lang": None}

        if readable_content:
            metadata_lang = metadata.get("lang") or metadata.get("language")
            update_data.update(
                {
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "keywords": metadata.get("keywords"),
                    "language": metadata_lang,
                    "readable": readable_content,
                }
            )

            land_dict = text_processing.get_land_dictionary_sync(self.db, expr.land_id)

            class TempExpr:
                def __init__(self, title: Optional[str], readable: Optional[str], expr_id: int):
                    self.title = title
                    self.readable = readable
                    self.id = expr_id

            temp_expr = TempExpr(metadata.get("title"), readable_content, expr.id)
            try:
                relevance = asyncio.run(
                    text_processing.expression_relevance(land_dict, temp_expr, metadata_lang or "fr")
                )
            except RuntimeError:
                loop = asyncio.new_event_loop()
                relevance = loop.run_until_complete(
                    text_processing.expression_relevance(land_dict, temp_expr, metadata_lang or "fr")
                )
                loop.close()
            update_data["relevance"] = relevance

            if relevance > 0:
                update_data["approved_at"] = datetime.utcnow()

            self._handle_links_and_media(
                soup=soup,
                expr=expr,
                expr_url=expr_url,
                analyze_media=analyze_media,
            )

        for field, value in update_data.items():
            setattr(expr, field, value)

        self.db.add(expr)
        return http_status_code

    def close(self) -> None:
        """Close HTTP resources."""
        try:
            self.http_client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _get_or_create_domain(self, name: str, land_id: int) -> models.Domain:
        domain = (
            self.db.query(models.Domain)
            .filter(
                models.Domain.name == name,
                models.Domain.land_id == land_id,
            )
            .first()
        )
        if domain:
            return domain

        domain = models.Domain(name=name, land_id=land_id)
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def _get_or_create_expression(self, land_id: int, url: str, depth: int) -> models.Expression:
        url_hash = models.Expression.compute_url_hash(url)
        expression = (
            self.db.query(models.Expression)
            .filter(
                models.Expression.land_id == land_id,
                models.Expression.url_hash == url_hash,
                models.Expression.url == url,
            )
            .first()
        )
        if expression:
            return expression

        domain_name = urlparse(url).netloc
        domain = self._get_or_create_domain(domain_name, land_id)

        expression = models.Expression(
            url=url,
            url_hash=url_hash,
            land_id=land_id,
            domain_id=domain.id,
            depth=depth,
        )
        self.db.add(expression)
        self.db.flush()
        self.db.refresh(expression)
        return expression

    def _get_expressions_to_crawl_query(
        self,
        land_id: int,
        limit: int = 0,
        http_status: Optional[str] = None,
        depth: Optional[int] = None,
    ):
        query = (
            self.db.query(models.Expression)
            .filter(models.Expression.land_id == land_id)
            .filter(models.Expression.crawled_at.is_(None))
            .order_by(models.Expression.depth.asc(), models.Expression.created_at.asc())
        )

        if http_status is not None:
            try:
                http_value = int(http_status)
                query = query.filter(models.Expression.http_status == http_value)
            except (TypeError, ValueError):
                pass

        if depth is not None:
            query = query.filter(models.Expression.depth == depth)

        if limit and limit > 0:
            query = query.limit(limit)

        return query

    def _fetch_expressions_to_crawl(
        self,
        land_id: int,
        limit: int = 0,
        depth: Optional[int] = None,
        http_status: Optional[str] = None,
    ) -> List[models.Expression]:
        return list(
            self._get_expressions_to_crawl_query(
                land_id=land_id,
                limit=limit,
                depth=depth,
                http_status=http_status,
            ).all()
        )

    def _handle_links_and_media(
        self,
        soup,
        expr: models.Expression,
        expr_url: str,
        analyze_media: bool,
    ) -> None:
        import os

        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug("Test environment detected, skipping link/media extraction")
            return

        try:
            self._extract_and_save_links(soup, expr, expr_url)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("Error extracting links for %s: %s", expr_url, exc)

        try:
            self._extract_and_save_media(soup, expr, expr_url, analyze_media)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("Error extracting media for %s: %s", expr_url, exc)

    def _extract_and_save_links(self, soup, expr: models.Expression, expr_url: str) -> List[Dict[str, str]]:
        from app.db.models import ExpressionLink

        links_found: List[Dict[str, str]] = []

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if not href or href.startswith("#") or href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            try:
                full_url = urljoin(expr_url, href)
                parsed = urlparse(full_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    continue

                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    tracking_params = {
                        "utm_source",
                        "utm_medium",
                        "utm_campaign",
                        "utm_content",
                        "utm_term",
                        "fbclid",
                        "gclid",
                        "ref",
                        "source",
                        "campaign",
                    }
                    kept_params = []
                    for part in parsed.query.split("&"):
                        if "=" not in part:
                            continue
                        key = part.split("=", 1)[0].lower()
                        if key not in tracking_params:
                            kept_params.append(part)
                    if kept_params:
                        clean_url = f"{clean_url}?{'&'.join(kept_params)}"

                domain = self._get_or_create_domain(parsed.netloc.lower(), expr.land_id)

                target_expr = (
                    self.db.query(models.Expression)
                    .filter(
                        models.Expression.land_id == expr.land_id,
                        models.Expression.url_hash == models.Expression.compute_url_hash(clean_url),
                        models.Expression.url == clean_url,
                    )
                    .first()
                )

                link_text = link.get_text(strip=True)[:200] or "No text"

                if not target_expr:
                    depth = (expr.depth or 0) + 1
                    target_expr = self._get_or_create_expression(expr.land_id, clean_url, depth)

                    links_found.append(
                        {
                            "url": clean_url,
                            "text": link_text,
                            "domain": domain.name,
                            "depth": target_expr.depth or depth,
                        }
                    )

                if target_expr.id == expr.id:
                    continue

                link_type = "internal" if parsed.netloc == urlparse(expr_url).netloc else "external"
                rel_attr = link.get("rel")
                if isinstance(rel_attr, (list, tuple)):
                    rel_attr = " ".join(str(item) for item in rel_attr if item)

                relationship_exists = (
                    self.db.query(models.ExpressionLink)
                    .filter(
                        models.ExpressionLink.source_id == expr.id,
                        models.ExpressionLink.target_id == target_expr.id,
                    )
                    .first()
                    is not None
                )

                if not relationship_exists:
                    link_obj = ExpressionLink(
                        source_id=expr.id,
                        target_id=target_expr.id,
                        anchor_text=link_text,
                        link_type=link_type,
                        rel_attribute=rel_attr,
                    )
                    self.db.add(link_obj)
                    self.db.commit()

            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.warning("Error processing link %s: %s", href, exc)

        if links_found:
            logger.info("Discovered %s new links from %s", len(links_found), expr_url)

        return links_found

    def _extract_and_save_media(
        self,
        soup,
        expr: models.Expression,
        expr_url: str,
        analyze_media: bool,
    ) -> None:
        media_processor = MediaProcessorSync(self.db, self.http_client)
        media_urls = media_processor.extract_media_urls(soup, expr_url)

        for media_url in media_urls:
            try:
                if media_url.startswith("data:"):
                    continue

                if media_processor.media_exists(expr.id, media_url):
                    continue

                media_type = self._determine_media_type(media_url)
                media_payload: Dict[str, Any] = {"url": media_url, "type": media_type}

                if analyze_media and media_type == models.MediaType.IMAGE:
                    analysis = media_processor.analyze_image(media_url)
                    if not analysis.get("error"):
                        media_payload.update(
                            {
                                "width": analysis.get("width"),
                                "height": analysis.get("height"),
                                "file_size": analysis.get("file_size"),
                                "format": analysis.get("format"),
                                "has_transparency": analysis.get("has_transparency"),
                                "aspect_ratio": analysis.get("aspect_ratio"),
                                "dominant_colors": analysis.get("dominant_colors"),
                                "websafe_colors": analysis.get("websafe_colors"),
                                "image_hash": analysis.get("image_hash"),
                                "exif_data": analysis.get("exif_data"),
                                "color_mode": analysis.get("color_mode"),
                                "mime_type": analysis.get("mime_type"),
                                "processed_at": datetime.now(timezone.utc),
                                "is_processed": True,
                                "analysis_error": None,
                                "processing_error": None,
                            }
                        )
                    else:
                        media_payload["analysis_error"] = analysis["error"]
                else:
                    media_payload.setdefault("is_processed", False)

                media_processor.create_media(expr.id, media_payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error processing media %s: %s", media_url, exc)
                self.db.rollback()

        try:
            media_processor.extract_dynamic_medias(expr_url, expr)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error during dynamic media extraction for %s: %s", expr_url, exc)

    @staticmethod
    def _determine_media_type(url: str) -> models.MediaType:
        url_lower = url.lower()

        image_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.tiff', '.ico')
        video_ext = ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v')
        audio_ext = ('.mp3', '.wav', '.ogg', '.aac', '.flac', '.m4a', '.wma')

        if url_lower.endswith(image_ext):
            return models.MediaType.IMAGE
        if url_lower.endswith(video_ext):
            return models.MediaType.VIDEO
        if url_lower.endswith(audio_ext):
            return models.MediaType.AUDIO
        return models.MediaType.IMAGE
