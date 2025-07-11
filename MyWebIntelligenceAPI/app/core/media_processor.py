"""
Processeur de médias, adapté de media_analyzer.py.
Analyse les images pour en extraire les métadonnées, les couleurs dominantes, etc.
"""
import io
import hashlib
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError
from sklearn.cluster import KMeans
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import models
from app.crud import crud_media

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not available. Dynamic media extraction will be skipped.")

def generer_palette_web_safe():
    """Génère les 216 couleurs RGB de la palette Web Safe."""
    niveaux = [0, 51, 102, 153, 204, 255]
    return [(r, g, b) for r in niveaux for g in niveaux for b in niveaux]

def distance_rgb(c1, c2):
    """Calcule la distance euclidienne au carré entre deux couleurs RGB."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2))

def convertir_vers_web_safe(rgb):
    """Convertit une couleur RGB en sa correspondante la plus proche dans la palette Web Safe."""
    palette = generer_palette_web_safe()
    return min(palette, key=lambda c: distance_rgb(rgb, c))

class MediaProcessor:
    """Analyseur de médias avec traitement asynchrone."""
    
    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient):
        self.db = db
        self.http_client = http_client
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    async def analyze_image(self, url: str) -> Dict[str, Any]:
        """Analyse complète d'une image."""
        result: Dict[str, Any] = {
            'url': url,
            'error': None, 'width': None, 'height': None, 'format': None,
            'file_size': None, 'color_mode': None, 'has_transparency': False,
            'aspect_ratio': None, 'exif_data': None, 'image_hash': None,
            'dominant_colors': [], 'websafe_colors': {}
        }

        try:
            response = await self.http_client.get(url, timeout=30)
            response.raise_for_status()
            
            content = await response.aread()
            if len(content) > self.max_size:
                raise ValueError(f"File size exceeds limit ({len(content)} bytes)")

            result['file_size'] = len(content)
            result['image_hash'] = hashlib.sha256(content).hexdigest()
            
            with Image.open(io.BytesIO(content)) as img:
                self._analyze_image_properties(img, result)
                if settings.ANALYZE_MEDIA:
                    self._extract_colors(img, result)
                    self._extract_exif(img, result)

        except Exception as e:
            result['error'] = str(e)
        
        return result

    def _analyze_image_properties(self, img: Image.Image, result: Dict):
        """Extrait les propriétés basiques de l'image."""
        result.update({
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'color_mode': img.mode,
            'has_transparency': 'A' in img.getbands(),
            'aspect_ratio': round(img.width / img.height, 2) if img.height else 0
        })

    def _extract_colors(self, img: Image.Image, result: Dict[str, Any]):
        """Extrait les couleurs dominantes avec K-means."""
        n_colors = settings.N_DOMINANT_COLORS
        try:
            img_resized = img.resize((100, 100)).convert('RGB')
            pixels = np.array(img_resized).reshape(-1, 3)
            
            kmeans = KMeans(n_clusters=n_colors, n_init='auto', random_state=42)
            kmeans.fit(pixels)
            
            counts = np.bincount(kmeans.labels_)
            total = sum(counts)
            
            sorted_colors = sorted(zip(kmeans.cluster_centers_, counts), key=lambda x: x[1], reverse=True)
            
            dominant_colors = [{'rgb': tuple(map(int, color)), 'percentage': round(count / total * 100, 2)} for color, count in sorted_colors]
            result['dominant_colors'] = dominant_colors
            
            websafe_palette = {}
            for item in dominant_colors:
                websafe_color = convertir_vers_web_safe(item['rgb'])
                websafe_hex = '#%02x%02x%02x' % websafe_color
                websafe_palette.setdefault(websafe_hex, 0)
                websafe_palette[websafe_hex] += item['percentage']
            result['websafe_colors'] = websafe_palette

        except Exception as e:
            if not result.get('error'):
                result['error'] = f"Color analysis error: {str(e)}"

    def _extract_exif(self, img: Image.Image, result: Dict[str, Any]):
        """Extrait les métadonnées EXIF."""
        try:
            exif_data = img.getexif()
            if exif_data:
                exif = {
                    "ImageWidth": exif_data.get(256), "ImageLength": exif_data.get(257),
                    "Make": exif_data.get(271), "Model": exif_data.get(272),
                    "DateTime": exif_data.get(306),
                }
                result['exif_data'] = {k: v for k, v in exif.items() if v is not None}
        except Exception as e:
            if not result.get('error'):
                result['error'] = f"EXIF error: {str(e)}"

    def extract_media_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extrait les URLs des médias d'un objet BeautifulSoup."""
        urls = set()
        media_tags = soup.find_all(['img', 'video', 'audio'])
        for tag in media_tags:
            src = tag.get('src')
            if src:
                urls.add(urljoin(base_url, src))
        return list(urls)

    async def extract_dynamic_medias(self, url: str, expression: models.Expression):
        """
        Extract media URLs from a webpage using a headless browser.
        """
        if not PLAYWRIGHT_AVAILABLE:
            print(f"Playwright not available, skipping dynamic media extraction for {url}")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "MyWebIntelligence-Crawler/1.0"})
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)

                media_selectors = {
                    'IMAGE': 'img[src]',
                    'VIDEO': 'video[src], video source[src]',
                    'AUDIO': 'audio[src], audio source[src]'
                }
                
                for media_type, selector in media_selectors.items():
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        src = await element.get_attribute('src')
                        if src:
                            resolved_url = urljoin(url, src)
                            if not await crud_media.media_exists(self.db, expression_id=expression.id, url=resolved_url):
                                await crud_media.create_media(self.db, expression_id=expression.id, media_data={'url': resolved_url, 'media_type': media_type})

                lazy_img_selectors = [
                    'img[data-src]', 'img[data-lazy-src]', 
                    'img[data-original]', 'img[data-url]'
                ]
                
                for selector in lazy_img_selectors:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        for attr in ['data-src', 'data-lazy-src', 'data-original', 'data-url']:
                            src = await element.get_attribute(attr)
                            if src:
                                resolved_url = urljoin(url, src)
                                if not await crud_media.media_exists(self.db, expression_id=expression.id, url=resolved_url):
                                    await crud_media.create_media(self.db, expression_id=expression.id, media_data={'url': resolved_url, 'media_type': 'IMAGE'})
                                break
            except Exception as e:
                print(f"Error during dynamic media extraction for {url}: {e}")
            finally:
                await browser.close()
