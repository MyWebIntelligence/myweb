"""
Schémas Pydantic pour les Domains
"""

from pydantic import BaseModel
from typing import Optional
from .base import TimeStampedSchema

# Schéma de base pour un Domain
class DomainBase(BaseModel):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None

# Schéma pour la création d'un Domain
class DomainCreate(DomainBase):
    land_id: int

# Schéma pour la mise à jour d'un Domain
class DomainUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None

# Schéma pour l'affichage d'un Domain
class Domain(TimeStampedSchema):
    id: int
    land_id: int
    name: str
    title: Optional[str] = None
    total_expressions: int
