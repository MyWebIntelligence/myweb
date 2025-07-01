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

from datetime import datetime
from app.db import models
from app.crud import crud_expression, crud_domain, crud_link, crud_media
from app.core.config import settings
from app.core.text_processing import expression_relevance, get_land_dictionary
from app.core.content_extractor import get_readable_content, get_metadata
from app.core.media_processor import MediaProcessor

class CrawlerEngine:
    """
    Classe encapsulant la logique de crawling.
    """
    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient):
        self.db = db
        self.http_client = http_client
        self.media_processor = MediaProcessor(http_client)

    async def crawl_land(self, land: models.Land, limit: int = 0, http_status: Optional[str] = None, depth: Optional[int] = None) -> tuple[int, int]:
        """
        Lance le crawl d'un land.
        """
        print(f"Crawling land {land.id}")
        dictionary = await get_land_dictionary(self.db, land_id=land.id)
        
        expressions_to_crawl = await crud_expression.get_expressions_to_crawl(
            self.db, land_id=land.id, limit=limit, http_status=http_status, depth=depth
        )

        if not expressions_to_crawl:
            print("No expressions to crawl for this land.")
            return 0, 0

        tasks = [self.crawl_expression(expr, dictionary) for expr in expressions_to_crawl]
        results = await asyncio.gather(*tasks)
        
        processed_count = sum(1 for r in results if r is True)
        error_count = len(results) - processed_count
        
        return processed_count, error_count

    async def crawl_expression(self, expression: models.Expression, dictionary: List[str]) -> bool:
        """
        Crawle et traite une seule expression en utilisant un pipeline robuste.
        """
        print(f"Crawling expression #{expression.id}: {expression.url}")
        raw_html, status_code, final_url = await self._fetch_direct(expression.url)

        # Si l'extraction directe échoue, essayer les fallbacks
        if not raw_html:
            # Fallback 1: Archive.org
            print(f"Direct fetch failed for {expression.url}. Trying Archive.org...")
            raw_html, status_code, final_url = await self._fetch_archive_org(expression.url)

        expression.http_status = str(status_code)
        expression.fetched_at = datetime.now()

        if not raw_html:
            print(f"All fetch methods failed for {expression.url}")
            await self.db.commit()
            return False

        # Extraction du contenu et des métadonnées
        content, soup = get_readable_content(raw_html)
        metadata = get_metadata(soup, final_url)

        # Mise à jour de l'expression
        expression.title = metadata['title']
        expression.description = metadata['description']
        expression.keywords = metadata['keywords']
        expression.lang = metadata['lang']
        expression.readable = content
        expression.readable_at = datetime.now()
        
        # Calcul de la pertinence
        relevance = await expression_relevance(dictionary, expression)
        if relevance is not None:
            expression.relevance = relevance
        
        if expression.relevance and expression.relevance > 0:
            expression.approved_at = datetime.now()
            
            # Extraction des médias et des liens
            await self._extract_and_save_media(soup, expression)
            await self._extract_and_save_links(soup, expression)

        await self.db.commit()
        print(f"Successfully processed expression #{expression.id}")
        return True

    async def _fetch_direct(self, url: str) -> tuple[Optional[str], int, str]:
        """Récupération directe via HTTPX."""
        try:
            response = await self.http_client.get(url, follow_redirects=True, timeout=15)
            response.raise_for_status()
            if 'text/html' in response.headers.get('content-type', ''):
                return response.text, response.status_code, str(response.url)
            return None, response.status_code, str(response.url)
        except httpx.HTTPStatusError as e:
            return None, e.response.status_code, str(e.request.url)
        except Exception:
            return None, 0, url

    async def _fetch_archive_org(self, url: str) -> tuple[Optional[str], int, str]:
        """Fallback via Archive.org."""
        try:
            api_url = f"http://archive.org/wayback/available?url={url}"
            response = await self.http_client.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            snapshot = data.get('archived_snapshots', {}).get('closest')
            if snapshot and snapshot.get('available'):
                snapshot_url = snapshot['url']
                print(f"Found archive snapshot: {snapshot_url}")
                content_response = await self.http_client.get(snapshot_url, timeout=20)
                if 'text/html' in content_response.headers.get('content-type', ''):
                    return content_response.text, int(snapshot.get('status', 200)), snapshot_url
        except Exception as e:
            print(f"Archive.org fallback failed: {e}")
        return None, 0, url

    async def _extract_and_save_media(self, soup: BeautifulSoup, expression: models.Expression):
        """Extrait, analyse et sauvegarde les médias."""
        media_urls = self.media_processor.extract_media_urls(soup, str(expression.url))
        
        # Supprimer les anciens médias pour éviter les doublons lors de la reconsolidation
        await crud_media.delete_media_for_expression(self.db, expression_id=expression.id)

        for url in media_urls:
            analysis_result = await self.media_processor.analyze_image(url)
            await crud_media.create_media(self.db, expression_id=expression.id, media_data=analysis_result)

    async def _extract_and_save_links(self, soup: BeautifulSoup, expression: models.Expression):
        """Extrait et sauvegarde les liens sortants."""
        if expression.depth is not None and expression.depth >= settings.CRAWL_MAX_DEPTH:
            return

        # Supprimer les anciens liens
        if expression.id is not None:
            await crud_link.delete_links_for_expression(self.db, source_id=expression.id)

        urls = {urljoin(str(expression.url), a.get('href')) for a in soup.find_all('a', href=True)}
        
        for url in urls:
            if self._is_crawlable(url) and expression.land_id is not None and expression.depth is not None and expression.id is not None:
                target_expr = await crud_expression.get_or_create_expression(
                    self.db, land_id=expression.land_id, url=url, depth=expression.depth + 1
                )
                if target_expr and target_expr.id is not None:
                    await crud_link.create_link(self.db, source_id=expression.id, target_id=target_expr.id)

    def _is_crawlable(self, url: str) -> bool:
        """Vérifie si une URL est valide pour le crawling."""
        exclude_ext = ('.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip', '.css')
        return url.startswith(('http://', 'https://')) and not url.lower().endswith(exclude_ext)

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
