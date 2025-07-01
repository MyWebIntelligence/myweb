"""
Schémas Pydantic pour les Lands (projets de crawling)
"""

from pydantic import BaseModel
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
    pass

# Schéma pour la mise à jour d'un Land
class LandUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_urls: Optional[List[str]] = None
    crawl_depth: Optional[int] = None
    crawl_limit: Optional[int] = None
    settings: Optional[dict] = None

# Schéma pour l'affichage d'un Land
class Land(TimeStampedSchema):
    id: int
    owner_id: int
    name: str
    description: Optional[str] = None
    crawl_status: CrawlStatus
    total_expressions: int
    total_domains: int
    last_crawl: Optional[datetime] = None
