import nltk
from nltk.stem import WordNetLemmatizer, SnowballStemmer
from nltk.tokenize import word_tokenize
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict
import re
import logging

logger = logging.getLogger(__name__)

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('stopwords', quiet=True)

# Initialize stemmers for different languages
english_lemmatizer = WordNetLemmatizer()
french_stemmer = SnowballStemmer('french')
english_stemmer = SnowballStemmer('english')

def get_lemma(term: str, lang: str = "en") -> str:
    """
    Get the lemma/stem (base form) of a term using appropriate language processors.
    Supports French stemming, English lemmatization, and basic cleaning for other languages.
    """
    if not term or not term.strip():
        return ""
    
    # Clean and normalize the term
    cleaned_term = normalize_text(term)
    
    if lang == "fr":
        # French: Use Snowball stemmer
        tokens = word_tokenize(cleaned_term, language='french')
        stemmed_tokens = [french_stemmer.stem(token) for token in tokens if token.isalnum()]
        return " ".join(stemmed_tokens).lower().strip()
    
    elif lang == "en":
        # English: Use WordNet lemmatizer + Snowball stemmer for better coverage
        tokens = word_tokenize(cleaned_term)
        processed_tokens = []
        for token in tokens:
            if token.isalnum():
                # Try lemmatization first, then stemming as fallback
                lemmatized = english_lemmatizer.lemmatize(token.lower())
                if lemmatized == token.lower():
                    # Lemmatization didn't change the word, try stemming
                    stemmed = english_stemmer.stem(token.lower())
                    processed_tokens.append(stemmed)
                else:
                    processed_tokens.append(lemmatized)
        return " ".join(processed_tokens).strip()
    
    else:
        # Other languages: Basic cleaning and normalization
        tokens = word_tokenize(cleaned_term)
        cleaned_tokens = [token.lower() for token in tokens if token.isalnum()]
        return " ".join(cleaned_tokens).strip()


def normalize_text(text: str) -> str:
    """
    Normalize text by removing special characters, extra spaces, and accents.
    Preserves French accents for better stemming.
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Normalize quotes and dashes
    text = re.sub(r'[""''«»]', '"', text)
    text = re.sub(r'[–—]', '-', text)
    
    # Remove non-alphabetic characters except spaces, accents, and hyphens
    text = re.sub(r'[^\w\s\-àâäçéèêëïîôöùûüÿ]', ' ', text, flags=re.IGNORECASE)
    
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_keywords(text: str, lang: str = "fr", max_keywords: int = 10) -> list[str]:
    """
    Extract meaningful keywords from text using language-specific processing.
    """
    if not text:
        return []
    
    try:
        from nltk.corpus import stopwords
        
        # Get stopwords for the language
        if lang == "fr":
            stop_words = set(stopwords.words('french'))
            # Add common French words not in NLTK
            stop_words.update(['cela', 'celui', 'celle', 'ceux', 'celles', 'ça', 'où'])
        elif lang == "en":
            stop_words = set(stopwords.words('english'))
        else:
            stop_words = set()
        
        # Normalize and tokenize
        normalized = normalize_text(text)
        tokens = word_tokenize(normalized.lower())
        
        # Filter tokens: remove stopwords, short words, and get stems/lemmas
        keywords = []
        for token in tokens:
            if (len(token) >= 3 and 
                token.isalnum() and 
                token not in stop_words):
                
                # Get the stem/lemma
                lemma = get_lemma(token, lang)
                if lemma and lemma not in keywords:
                    keywords.append(lemma)
        
        # Limit number of keywords
        return keywords[:max_keywords]
        
    except Exception as e:
        logger.warning(f"Error extracting keywords: {e}")
        # Fallback: simple word splitting
        words = text.split()
        return [word.lower().strip('.,!?;:') for word in words[:max_keywords] if len(word) >= 3]

async def get_land_dictionary(db: AsyncSession, land_id: int) -> Dict[str, float]:
    """
    Retrieve the dictionary for a land from the database.
    Returns a dictionary mapping lemmas to their weights.
    """
    from app.db.models import Word, LandDictionary
    
    result = await db.execute(
        select(Word.lemma, LandDictionary.weight)
        .join(LandDictionary, Word.id == LandDictionary.word_id)
        .where(LandDictionary.land_id == land_id)
    )
    
    dictionary = {}
    rows = result.fetchall()
    # Handle async mock case
    if hasattr(rows, '__await__'):
        rows = await rows
    
    for lemma, weight in rows:
        dictionary[lemma] = weight
    
    return dictionary


def get_land_dictionary_sync(db, land_id: int) -> Dict[str, float]:
    """
    Synchronous alternative used by Celery workers relying on Session.
    """
    from sqlalchemy.orm import Session
    from app.db.models import Word, LandDictionary

    if not isinstance(db, Session):
        raise TypeError("get_land_dictionary_sync expects a synchronous Session")

    result = (
        db.query(Word.lemma, LandDictionary.weight)
        .join(LandDictionary, Word.id == LandDictionary.word_id)
        .filter(LandDictionary.land_id == land_id)
        .all()
    )

    dictionary: Dict[str, float] = {}
    for lemma, weight in result:
        dictionary[lemma] = weight
    return dictionary

async def expression_relevance(dictionary: Dict[str, float], expr, lang: str = "fr") -> float:
    """
    Calculate the relevance score of an expression based on the land's dictionary.
    Improved with better text processing and language support.
    
    Returns a float score where:
    - 0: No relevance
    - 1-5: Low relevance  
    - 5-15: Medium relevance
    - 15+: High relevance
    """
    if not dictionary:
        logger.debug("No dictionary provided for relevance calculation")
        return 0.0
    
    score = 0.0
    matched_terms = set()  # Avoid counting the same lemma multiple times
    
    # Process title (weight 10) - titles are more important
    if hasattr(expr, 'title') and expr.title:
        title_keywords = extract_keywords(expr.title, lang, max_keywords=20)
        for keyword in title_keywords:
            if keyword in dictionary and keyword not in matched_terms:
                weight = dictionary[keyword]
                score += weight * 10
                matched_terms.add(keyword)
                logger.debug(f"Title match: '{keyword}' -> +{weight * 10}")
    
    # Process readable content (weight 1)
    if hasattr(expr, 'readable') and expr.readable:
        content_keywords = extract_keywords(expr.readable, lang, max_keywords=50)
        for keyword in content_keywords:
            if keyword in dictionary and keyword not in matched_terms:
                weight = dictionary[keyword]
                score += weight * 1
                matched_terms.add(keyword)
                logger.debug(f"Content match: '{keyword}' -> +{weight}")
    
    # Bonus for multiple matching terms (indicates topic relevance)
    if len(matched_terms) > 1:
        bonus = len(matched_terms) * 0.5
        score += bonus
        logger.debug(f"Multi-term bonus: {len(matched_terms)} terms -> +{bonus}")
    
    # Apply language-specific relevance boost
    if lang == "fr" and len(matched_terms) > 0:
        # French texts often have more inflections, give small boost
        score *= 1.1
    
    final_score = round(score, 2)
    logger.debug(f"Final relevance score: {final_score} (matched {len(matched_terms)} terms)")
    
    return final_score


def calculate_text_similarity(text1: str, text2: str, lang: str = "fr") -> float:
    """
    Calculate similarity between two texts using stemmed/lemmatized keywords.
    Returns a value between 0 (no similarity) and 1 (identical).
    """
    if not text1 or not text2:
        return 0.0
    
    # Extract keywords from both texts
    keywords1 = set(extract_keywords(text1, lang, max_keywords=50))
    keywords2 = set(extract_keywords(text2, lang, max_keywords=50))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    
    return intersection / union if union > 0 else 0.0
