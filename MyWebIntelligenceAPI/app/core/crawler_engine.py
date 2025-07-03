"""
Moteur de crawling principal, adapté de core.py.
Contient la logique de récupération, d'analyse et de traitement du contenu web.
"""
import asyncio
import re
from urllib.parse import urlparse, urljoin
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup
import trafilatura
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from datetime import datetime
from app.db import models
from app.crud import crud_expression, crud_domain, crud_link, crud_media
from app.config import settings
from app.core.text_processing import expression_relevance, get_land_dictionary, stem_word
from app.core.content_extractor import get_readable_content, get_metadata, get_title, get_description, get_keywords, clean_html
from app.core.media_processor import MediaProcessor

class CrawlerEngine:
    """
    Classe encapsulant la logique de crawling.
    """
    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient):
        self.db = db
        self.http_client = http_client
        self.media_processor = MediaProcessor(db, http_client)

    async def crawl_land(self, land: models.Land, limit: int = 0, http_status: Optional[str] = None, depth: Optional[int] = None) -> tuple[int, int]:
        """
        Lance le crawl d'un land.
        """
        print(f"Crawling land {land.id}")
        dictionary = await get_land_dictionary(self.db, land_id=land.id)

        total_processed = 0
        total_errors = 0

        if depth is not None:
            depths_to_process = [depth]
        else:
            depths_to_process = await crud_expression.get_distinct_depths(self.db, land_id=land.id, http_status=http_status)

        for current_depth in depths_to_process:
            print(f"Processing depth {current_depth}")

            expressions_to_crawl = await crud_expression.get_expressions_to_crawl(
                self.db, land_id=land.id, limit=limit, http_status=http_status, depth=current_depth
            )

            if not expressions_to_crawl:
                continue

            tasks = [self.crawl_expression_with_media_analysis(expr, dictionary) for expr in expressions_to_crawl]
            results = await asyncio.gather(*tasks)
            
            processed_in_batch = sum(1 for r in results if r is True)
            total_processed += processed_in_batch
            total_errors += (len(expressions_to_crawl) - processed_in_batch)

            if limit > 0 and total_processed >= limit:
                return total_processed, total_errors

        return total_processed, total_errors

    async def crawl_expression_with_media_analysis(self, expression: models.Expression, dictionary) -> bool:
        """
        Crawl and process an expression with media analysis
        """
        print(f"Crawling expression #{expression.id} with media analysis: {expression.url}")
        content = None
        raw_html = None
        links = []
        status_code_str = "000"  # Default to client error
        expression.fetched_at = datetime.now()

        try:
            response = await self.http_client.get(expression.url, headers={"User-Agent": "MyWebIntelligence-Crawler/1.0"}, timeout=15)
            status_code_str = str(response.status_code)
            if response.status_code == 200 and 'html' in response.headers.get('content-type', ''):
                raw_html = response.text
            else:
                print(f"Direct request for {expression.url} returned status {status_code_str}")
        except httpx.RequestError as e:
            print(f"RequestError for {expression.url}: {e}. Status: 000.")
            status_code_str = "000"
        except Exception as e:
            print(f"Generic exception during initial fetch for {expression.url}: {e}")
            status_code_str = "ERR"

        try:
            expression.http_status = int(status_code_str)
        except (ValueError, TypeError):
            expression.http_status = 0

        if raw_html:
            try:
                extracted_content = trafilatura.extract(raw_html, include_links=True, include_comments=False, include_images=True, output_format='markdown')
                readable_html = trafilatura.extract(raw_html, include_links=True, include_comments=False, include_images=True, output_format='html')
                if extracted_content and len(extracted_content) > 100:
                    media_lines = []
                    if readable_html:
                        soup_readable = BeautifulSoup(readable_html, 'html.parser')
                        for tag, label in [('img', 'IMAGE'), ('video', 'VIDEO'), ('audio', 'AUDIO')]:
                            for element in soup_readable.find_all(tag):
                                src = element.get('src')
                                if src:
                                    if tag == 'img':
                                        media_lines.append(f"![{label}]({src})")
                                    else:
                                        media_lines.append(f"[{label}: {src}]")
                    content = extracted_content
                    if media_lines:
                        content += "\n\n" + "\n".join(media_lines)
                    if readable_html:
                        soup_readable = BeautifulSoup(readable_html, 'html.parser')
                        await self._extract_and_save_media(soup_readable, expression)
                    img_md_links = re.findall(r'!\[.*?\]\((.*?)\)', content)
                    for img_url in img_md_links:
                        resolved_img_url = urljoin(str(expression.url), img_url)
                        if not await crud_media.media_exists(self.db, expression_id=expression.id, url=resolved_img_url):
                            await crud_media.create_media(self.db, expression_id=expression.id, media_data={'url': resolved_img_url, 'media_type': 'IMAGE'})
                    links = self.extract_md_links(content)
                    expression.readable = content
                    print(f"Trafilatura succeeded on fetched HTML for {expression.url}")
            except Exception as e:
                print(f"Trafilatura failed on raw HTML for {expression.url}: {e}")

            if not content:
                try:
                    soup = BeautifulSoup(raw_html, 'html.parser')
                    clean_html(soup)
                    text_content, _ = get_readable_content(raw_html) # Utilise la fonction corrigée
                    if text_content and len(text_content) > 100:
                        content = text_content
                        urls = [a.get('href') for a in soup.find_all('a') if self._is_crawlable(a.get('href'))]
                        links = urls
                        expression.readable = content
                        print(f"BeautifulSoup fallback succeeded for {expression.url}")
                except Exception as e:
                    print(f"BeautifulSoup fallback failed for {expression.url}: {e}")

        if not content:
            try:
                print(f"Trying URL-based fallback: archive.org for {expression.url}")
                api_url = f"http://archive.org/wayback/available?url={expression.url}"
                response = await self.http_client.get(api_url, timeout=10)
                response.raise_for_status()
                archive_data = response.json()
                archived_url = archive_data.get('archived_snapshots', {}).get('closest', {}).get('url')
                if archived_url:
                    downloaded = trafilatura.fetch_url(archived_url)
                    if downloaded:
                        raw_html = downloaded
                        extracted_content = trafilatura.extract(downloaded, include_links=True, include_images=True, output_format='markdown')
                        readable_html = trafilatura.extract(downloaded, include_links=True, include_images=True, output_format='html')
                        if extracted_content and len(extracted_content) > 100:
                            media_lines = []
                            if readable_html:
                                soup_readable = BeautifulSoup(readable_html, 'html.parser')
                                for tag, label in [('img', 'IMAGE'), ('video', 'VIDEO'), ('audio', 'AUDIO')]:
                                    for element in soup_readable.find_all(tag):
                                        src = element.get('src')
                                        if src:
                                            if tag == 'img':
                                                media_lines.append(f"![{label}]({src})")
                                            else:
                                                media_lines.append(f"[{label}: {src}]")
                            content = extracted_content
                            if media_lines:
                                content += "\n\n" + "\n".join(media_lines)
                            if readable_html:
                                soup_readable = BeautifulSoup(readable_html, 'html.parser')
                                await self._extract_and_save_media(soup_readable, expression)
                            img_md_links = re.findall(r'!\[.*?\]\((.*?)\)', content)
                            for img_url in img_md_links:
                                resolved_img_url = urljoin(str(expression.url), img_url)
                                if not await crud_media.media_exists(self.db, expression_id=expression.id, url=resolved_img_url):
                                    await crud_media.create_media(self.db, expression_id=expression.id, media_data={'url': resolved_img_url, 'media_type': 'IMAGE'})
                            links = self.extract_md_links(content)
                            expression.readable = content
                            print(f"Archive.org + Trafilatura succeeded for {expression.url}")
            except Exception as e:
                print(f"Archive.org fallback failed for {expression.url}: {e}")

        if content:
            soup = BeautifulSoup(raw_html if raw_html else content, 'html.parser')
            expression.title = str(get_title(soup) or expression.url)
            expression.description = str(get_description(soup)) if get_description(soup) else None
            expression.keywords = str(get_keywords(soup)) if get_keywords(soup) else None
            expression.lang = str(soup.html.get('lang', '')) if soup.html else ''
            expression.relevance = await expression_relevance(dictionary, expression)
            expression.readable_at = datetime.now()
            if expression.relevance is not None and expression.relevance > 0:
                expression.approved_at = datetime.now()
            
            if expression.id is not None:
                await crud_link.delete_links_for_expression(self.db, source_id=expression.id)

            if expression.relevance is not None and expression.relevance > 0 and settings.ANALYZE_MEDIA and expression.id is not None:
                try:
                    print(f"Attempting dynamic media extraction for #{expression.id}")
                    await self.media_processor.extract_dynamic_medias(str(expression.url), expression)
                except Exception as e:
                    print(f"Dynamic media extraction failed for #{expression.id}: {e}")

            if expression.relevance is not None and expression.relevance > 0 and expression.depth is not None and expression.depth < 3 and links:
                print(f"Linking {len(links)} expressions to #{expression.id}")
                for link in links:
                    await self.link_expression(expression.land, expression, link)
            
            await self.db.commit()
            return True
        else:
            print(f"All extraction methods failed for {expression.url}. Final status: {expression.http_status}")
            await self.db.commit()
            return False

    async def link_expression(self, land: models.Land, source_expression: models.Expression, url: str) -> bool:
        if source_expression.depth is None or source_expression.id is None:
            return False
        target_expression = await self.add_expression(land, url, source_expression.depth + 1)
        if target_expression and target_expression.id is not None:
            try:
                await crud_link.create_link(self.db, source_id=source_expression.id, target_id=target_expression.id)
                return True
            except IntegrityError:
                await self.db.rollback()
        return False

    async def add_expression(self, land: models.Land, url: str, depth=0) -> Optional[models.Expression]:
        url = self.remove_anchor(url)
        if self._is_crawlable(url) and land.id is not None:
            domain_name = self.get_domain_name(url)
            domain = await crud_domain.get_or_create(self.db, name=domain_name)
            if domain.id is None: return None # Should not happen
            
            expression = await crud_expression.get_by_url_and_land(self.db, url=url, land_id=land.id)
            if expression is None:
                expression = await crud_expression.create_expression(self.db, land_id=land.id, domain_id=domain.id, url=url, depth=depth)
            return expression
        return None

    def get_domain_name(self, url: str) -> str:
        parsed = urlparse(url)
        domain_name = parsed.netloc
        # for key, value in settings.HEURISTICS.items():
        #     if domain_name.endswith(key):
        #         matches = re.findall(value, url)
        #         domain_name = matches[0] if matches else domain_name
        return domain_name

    def remove_anchor(self, url: str) -> str:
        anchor_pos = url.find('#')
        return url[:anchor_pos] if anchor_pos > 0 else url

    def _is_crawlable(self, url: str):
        try:
            parsed = urlparse(url)
            exclude_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.pdf',
                           '.txt', '.csv', '.xls', '.xlsx', '.doc', '.docx')

            return \
                (url is not None) \
                and url.startswith(('http://', 'https://')) \
                and (not url.lower().endswith(exclude_ext))
        except:
            return False
            
    def extract_md_links(self, md_content: str):
        matches = re.findall(r'\(((https?|ftp)://[^\s/$.?#].[^\s]*)\)', md_content)
        urls = []
        for match in matches:
            url = match[0]
            if url.endswith(")") and url.count("(") <= url.count(")"):
                url = url[:-1]
            urls.append(url)
        return urls

    async def _extract_and_save_media(self, soup: BeautifulSoup, expression: models.Expression):
        """Extrait, analyse et sauvegarde les médias."""
        if expression.id is None: return
        media_urls = self.media_processor.extract_media_urls(soup, str(expression.url))
        
        await crud_media.delete_media_for_expression(self.db, expression_id=expression.id)

        for url in media_urls:
            analysis_result = await self.media_processor.analyze_image(url)
            await crud_media.create_media(self.db, expression_id=expression.id, media_data=analysis_result)

    async def _extract_and_save_links(self, soup: BeautifulSoup, expression: models.Expression):
        """Extrait et sauvegarde les liens sortants."""
        if expression.depth is not None and expression.depth >= settings.MAX_CRAWL_DEPTH:
            return

        if expression.id is not None:
            await crud_link.delete_links_for_expression(self.db, source_id=expression.id)

        urls = {urljoin(str(expression.url), a.get('href')) for a in soup.find_all('a', href=True)}
        
        for url in urls:
            if self._is_crawlable(url) and expression.land_id is not None and expression.depth is not None and expression.id is not None:
                target_expr = await self.add_expression(
                    expression.land, url, expression.depth + 1
                )
                if target_expr and target_expr.id is not None:
                    await crud_link.create_link(self.db, source_id=expression.id, target_id=target_expr.id)

    async def consolidate_land(self, land: models.Land, limit: int = 0, depth: Optional[int] = None) -> tuple[int, int]:
        """
        Consolide un land : recalcule la pertinence, les liens, les médias, etc.
        """
        print(f"Consolidating land {land.id}")
        dictionary = await get_land_dictionary(self.db, land_id=land.id)
        
        expressions_to_consolidate = await crud_expression.get_expressions_to_consolidate(
            self.db, land_id=land.id, limit=limit, depth=depth
        )

        if not expressions_to_consolidate:
            print("No expressions to consolidate for this land.")
            return 0, 0

        processed_count = 0
        error_count = 0

        for expr in expressions_to_consolidate:
            try:
                # 1. Recalculer la pertinence
                relevance = await expression_relevance(dictionary, expr)
                if relevance is not None:
                    expr.relevance = relevance

                # 2. Extraire et recréer les liens et médias à partir du contenu 'readable'
                if expr.readable:
                    soup = BeautifulSoup(expr.readable, 'html.parser')
                    await self._extract_and_save_links(soup, expr)
                    await self._extract_and_save_media(soup, expr)

                await self.db.commit()
                processed_count += 1
                print(f"Consolidated expression #{expr.id}")
            except Exception as e:
                error_count += 1
                print(f"Error consolidating expression #{expr.id}: {e}")
                await self.db.rollback()

        return processed_count, error_count
