"""
Schémas Pydantic pour les Médias
"""

from pydantic import BaseModel
from typing import Optional, Any
from .base import TimeStampedSchema
from ..db.models import MediaType

# Schéma de base pour un Média
class MediaBase(BaseModel):
    url: str
    type: MediaType
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    alt_text: Optional[str] = None

# Schéma pour la création d'un Média
class MediaCreate(MediaBase):
    expression_id: int

# Schéma pour la mise à jour d'un Média
class MediaUpdate(BaseModel):
    alt_text: Optional[str] = None

# Schéma pour l'affichage d'un Média
class Media(TimeStampedSchema):
    id: int
    expression_id: int
    url: str
    type: MediaType
