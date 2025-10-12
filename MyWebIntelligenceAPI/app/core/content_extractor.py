"""
Extracteur de contenu et de métadonnées à partir de HTML brut.
Adapté de readable_pipeline.py et des fonctions de core.py.
"""
from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import trafilatura
import httpx
import asyncio
import json

def get_readable_content(html: str) -> Tuple[str, BeautifulSoup]:
    """
    Extrait le contenu lisible d'un HTML avec stratégie de fallback en cascade:
    1. Trafilatura (primary)
    2. Smart extraction (content heuristics)
    3. BeautifulSoup (fallback)
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Méthode 1: Trafilatura (preferred)
    readable_text = trafilatura.extract(
        html, 
        include_comments=False, 
        include_tables=True,
        include_formatting=True,
        favor_precision=True
    )
    
    if readable_text and len(readable_text) > 200:
        print("Readable content extracted with Trafilatura.")
        return readable_text, soup
    
    # Méthode 2: Smart extraction avec heuristiques
    smart_content = _smart_content_extraction(soup)
    if smart_content and len(smart_content) > 200:
        print("Readable content extracted with smart heuristics.")
        return smart_content, soup

    # Méthode 3: BeautifulSoup fallback
    print("Advanced methods failed, falling back to BeautifulSoup.")
    clean_html(soup)
    text = soup.get_text(separator='\n', strip=True)
    return text, soup

def _smart_content_extraction(soup: BeautifulSoup) -> Optional[str]:
    """
    Extraction intelligente basée sur les heuristiques de contenu principal.
    Inspiré de la logique Mercury Parser du système ancien.
    """
    # Priorité aux sélecteurs de contenu communs
    content_selectors = [
        'article', '[role="main"]', 'main', '.content', '.post-content',
        '.entry-content', '.article-content', '.post-body', '.story-body',
        '#content', '#main-content', '.main-content', '.article-body'
    ]
    
    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            # Prendre le plus grand élément trouvé
            largest_element = max(elements, key=lambda x: len(x.get_text(strip=True)))
            text_content = largest_element.get_text(separator='\n', strip=True)
            if len(text_content) > 200:
                return text_content
    
    # Fallback: chercher les paragraphes les plus substantiels
    paragraphs = soup.find_all('p')
    if paragraphs:
        content_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
        if content_paragraphs:
            return '\n\n'.join(content_paragraphs)
    
    return None

def get_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extrait les métadonnées (titre, description, etc.) d'un objet BeautifulSoup.
    """
    title = get_title(soup) or url
    description = get_description(soup)
    keywords = get_keywords(soup)
    lang = soup.html.get('lang', '') if soup.html else ''

    return {
        'title': title,
        'description': description,
        'keywords': keywords,
        'lang': lang
    }

def get_title(soup: BeautifulSoup) -> Optional[str]:
    """Extrait le titre avec une chaîne de fallbacks."""
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content'].strip()

    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    if twitter_title and twitter_title.get('content'):
        return twitter_title['content'].strip()

    title_tag = soup.find('title')
    if title_tag and title_tag.string:
        return title_tag.string.strip()
        
    return None

def get_description(soup: BeautifulSoup) -> Optional[str]:
    """Extrait la description avec une chaîne de fallbacks."""
    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc['content'].strip()

    twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
    if twitter_desc and twitter_desc.get('content'):
        return twitter_desc['content'].strip()

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content'].strip()

    return None

def get_keywords(soup: BeautifulSoup) -> Optional[str]:
    """Extrait les mots-clés."""
    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_tag and keywords_tag.get('content'):
        return keywords_tag['content'].strip()
    return None

def clean_html(soup: BeautifulSoup):
    """Supprime les balises inutiles du HTML."""
    for selector in ['script', 'style', 'nav', 'footer', 'aside']:
        for tag in soup.select(selector):
            tag.decompose()

async def get_readable_content_with_fallbacks(url: str, html: Optional[str] = None) -> Tuple[Optional[str], Optional[BeautifulSoup], str]:
    """
    Extrait le contenu lisible avec fallbacks avancés:
    1. HTML fourni + Trafilatura
    2. Smart extraction sur HTML fourni
    3. Archive.org + Trafilatura
    4. BeautifulSoup fallback
    
    Returns:
        Tuple[content, soup, status] where status indicates which method succeeded
    """
    soup = None
    
    # Method 1 & 2: Use provided HTML
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try Trafilatura first
        readable_text = trafilatura.extract(
            html, 
            include_comments=False, 
            include_tables=True,
            include_formatting=True,
            favor_precision=True
        )
        
        if readable_text and len(readable_text) > 200:
            return readable_text, soup, "trafilatura_direct"
        
        # Try smart extraction
        smart_content = _smart_content_extraction(soup)
        if smart_content and len(smart_content) > 200:
            return smart_content, soup, "smart_extraction"
    
    # Method 3: Archive.org fallback
    try:
        archived_content = await _extract_from_archive_org(url)
        if archived_content:
            content, archive_soup = archived_content
            if content and len(content) > 200:
                return content, archive_soup, "archive_org"
    except Exception as e:
        print(f"Archive.org fallback failed for {url}: {e}")
    
    # Method 4: BeautifulSoup fallback on original HTML
    if soup:
        clean_html(soup)
        text = soup.get_text(separator='\n', strip=True)
        return text, soup, "beautifulsoup_fallback"
    
    return None, None, "all_failed"

async def _extract_from_archive_org(url: str) -> Optional[Tuple[str, BeautifulSoup]]:
    """Extract content from Archive.org archived version of the URL."""
    try:
        # Get archived snapshot info
        archive_api_url = f"http://archive.org/wayback/available?url={url}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(archive_api_url)
            response.raise_for_status()
            archive_data = response.json()
            
            archived_url = archive_data.get('archived_snapshots', {}).get('closest', {}).get('url')
            if not archived_url:
                return None
            
            # Fetch archived content
            archived_response = await client.get(archived_url)
            archived_response.raise_for_status()
            
            if 'html' not in archived_response.headers.get('content-type', ''):
                return None
                
            archived_html = archived_response.text
            
            # Extract with Trafilatura
            extracted_content = trafilatura.extract(
                archived_html, 
                include_comments=False, 
                include_tables=True,
                include_formatting=True,
                favor_precision=True
            )
            
            if extracted_content and len(extracted_content) > 100:
                soup = BeautifulSoup(archived_html, 'html.parser')
                return extracted_content, soup
                
    except Exception as e:
        print(f"Error in Archive.org extraction for {url}: {e}")
        
    return None


class ContentExtractor:
    """
    Content extractor class that wraps the extraction functions.
    """
    
    def __init__(self):
        pass
    
    def get_readable_content(self, html: str) -> Tuple[str, BeautifulSoup]:
        """Extract readable content from HTML."""
        return get_readable_content(html)
    
    def get_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract metadata from BeautifulSoup object."""
        return get_metadata(soup, url)
    
    async def get_readable_content_with_fallbacks(self, url: str, html: Optional[str] = None) -> Dict[str, Any]:
        """Extract readable content with fallbacks and return structured result."""
        content, soup, source = await get_readable_content_with_fallbacks(url, html)
        
        if not content:
            return {}
        
        # Extract metadata if we have soup
        metadata = {}
        if soup:
            metadata = get_metadata(soup, url)
        
        return {
            'readable': content,
            'content': html or '',
            'title': metadata.get('title'),
            'description': metadata.get('description'),
            'language': metadata.get('lang'),
            'source': source
        }
