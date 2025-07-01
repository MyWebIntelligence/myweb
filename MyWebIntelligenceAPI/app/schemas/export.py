"""
Schémas Pydantic pour les Exports
"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from .base import TimeStampedSchema

# Schéma de base pour un Export
class ExportBase(BaseModel):
    land_id: int
    export_type: str
    parameters: Optional[dict] = None

# Schéma pour la création d'un Export
class ExportCreate(ExportBase):
    minimum_relevance: float = 0.5

# Schéma pour la mise à jour d'un Export
class ExportUpdate(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None

# Schéma pour l'affichage d'un Export
class Export(TimeStampedSchema):
    id: int
    land_id: int
    export_type: str
    filename: str
    file_size: Optional[int] = None
    status: str
