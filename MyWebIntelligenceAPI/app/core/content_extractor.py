"""
Extracteur de contenu et de métadonnées à partir de HTML brut.
Adapté de readable_pipeline.py et des fonctions de core.py.
"""
from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import trafilatura

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
