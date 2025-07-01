"""
Schémas Pydantic pour les Expressions
"""

from pydantic import BaseModel
from typing import Optional
from .base import TimeStampedSchema

# Schéma de base pour une Expression
class ExpressionBase(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    relevance: Optional[float] = None
    depth: Optional[int] = None

# Schéma pour la création d'une Expression
class ExpressionCreate(ExpressionBase):
    land_id: int
    domain_id: int

# Schéma pour la mise à jour d'une Expression
class ExpressionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    readable: Optional[str] = None
    relevance: Optional[float] = None

# Schéma pour l'affichage d'une Expression
class Expression(TimeStampedSchema):
    id: int
    land_id: int
    domain_id: int
    url: str
    title: Optional[str] = None
    http_status: Optional[int] = None
    relevance: Optional[float] = None
    depth: Optional[int] = None
