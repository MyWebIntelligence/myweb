"""
Fonctions de traitement du langage naturel (NLP) pour le calcul de la pertinence.
Adapté des fonctions de core.py.
"""
import re
from typing import List
import nltk
from nltk.stem.snowball import FrenchStemmer
from nltk.tokenize import word_tokenize
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import models

# Téléchargement des ressources NLTK si nécessaire
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Initialisation du stemmer
stemmer = FrenchStemmer()

def stem_word(word: str) -> str:
    """Racine (stem) un mot en utilisant le FrenchStemmer de NLTK."""
    return stemmer.stem(word.lower())

async def get_land_dictionary(db: AsyncSession, land_id: int) -> List[str]:
    """Récupère le dictionnaire de lemmes pour un land donné."""
    query = (
        select(models.Word.lemma)
        .join(models.LandDictionary)
        .where(models.LandDictionary.land_id == land_id)
    )
    result = await db.execute(query)
    return [row[0] for row in result.all()]

async def expression_relevance(dictionary: List[str], expression: models.Expression) -> int:
    """
    Calcule la pertinence d'une expression en fonction du dictionnaire du land.
    """
    if not dictionary:
        return 0

    title_relevance = 0
    content_relevance = 0

    def get_relevance(text: str, weight: int) -> int:
        if not isinstance(text, str):
            return 0
        
        try:
            stems = [stem_word(w) for w in word_tokenize(text, language='french')]
            stemmed_text = " ".join(stems)
            
            # Compte les occurrences de chaque lemme du dictionnaire
            relevance_score = sum(
                weight * len(re.findall(r'\\b%s\\b' % re.escape(lemma), stemmed_text, re.IGNORECASE))
                for lemma in dictionary
            )
            return relevance_score
        except Exception:
            return 0

    if expression.title:
        title_relevance = get_relevance(expression.title, 10)
    
    if expression.readable:
        content_relevance = get_relevance(expression.readable, 1)

    return title_relevance + content_relevance
