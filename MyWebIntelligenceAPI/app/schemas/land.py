"""
Schémas Pydantic pour les Lands (projets de crawling)
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime
from .base import TimeStampedSchema
from ..db.models import CrawlStatus

# Schéma de base pour un Land
class LandBase(BaseModel):
    name: str
    description: Optional[str] = None
    start_urls: Optional[List[str]] = None
    crawl_depth: int = 3
    crawl_limit: int = 1000
    settings: Optional[dict] = None

# Schéma pour la création d'un Land
class LandCreate(LandBase):
    lang: List[str] = ["fr"]

# Schéma pour la mise à jour d'un Land
class LandUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_urls: Optional[List[str]] = None
    crawl_depth: Optional[int] = None
    crawl_limit: Optional[int] = None
    settings: Optional[dict] = None
    lang: Optional[List[str]] = None

# Schémas pour la réponse détaillée d'un Land, incluant son dictionnaire

class WordInDict(BaseModel):
    """Représente un mot dans le dictionnaire."""
    word: str
    lemma: Optional[str] = None

    class Config:
        from_attributes = True

class DictionaryItem(BaseModel):
    """Représente une entrée dans la table d'association LandDictionary."""
    word: WordInDict
    weight: float

    class Config:
        from_attributes = True

# Schéma pour l'affichage d'un Land (enrichi avec le dictionnaire)
class Land(TimeStampedSchema):
    id: int
    owner_id: int
    name: str
    description: Optional[str] = None
    lang: List[str]
    crawl_status: CrawlStatus
    total_expressions: int
    total_domains: int
    last_crawl: Optional[datetime] = None
    words: List[DictionaryItem] = []

    class Config:
        from_attributes = True

    @field_validator("lang", mode="before")
    @classmethod
    def split_lang_string(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(',') if lang.strip()]
        if v is None:
            return []
        return v

# Schéma pour ajouter des termes à un Land
class LandAddTerms(BaseModel):
    terms: List[str]
