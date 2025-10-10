import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)

lemmatizer = WordNetLemmatizer()

def get_lemma(term: str, lang: str = "en") -> str:
    """
    Get the lemma (base form) of a term using NLTK's lemmatizer.
    Supports English by default, returns the original term for other languages.
    """
    if lang != "en":
        # For non-English languages, return the term as-is
        return term.lower().strip()
    
    # Tokenize and lemmatize each word in the term
    tokens = word_tokenize(term)
    lemmatized_tokens = [lemmatizer.lemmatize(token) for token in tokens]
    return " ".join(lemmatized_tokens).lower().strip()

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

async def expression_relevance(dictionary: Dict[str, float], expr, lang: str = "fr") -> int:
    """
    Calculate the relevance score of an expression based on the land's dictionary.
    """
    if not dictionary:
        return 0
    
    score = 0
    
    # Process title (weight 10)
    if expr.title:
        title_tokens = word_tokenize(expr.title.lower())
        for token in title_tokens:
            lemma = get_lemma(token, lang)
            if lemma in dictionary:
                score += int(dictionary[lemma] * 10)
    
    # Process readable content (weight 1)
    if expr.readable:
        content_tokens = word_tokenize(expr.readable.lower())
        for token in content_tokens:
            lemma = get_lemma(token, lang)
            if lemma in dictionary:
                score += int(dictionary[lemma])
    
    return score
