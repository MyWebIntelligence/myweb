"""
Schémas Pydantic pour les Jobs de crawling
"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from .base import TimeStampedSchema
from ..db.models import CrawlStatus as JobStatus

# Schéma de base pour un Job
class CrawlJobBase(BaseModel):
    land_id: int
    job_type: str
    parameters: Optional[dict] = None

# Schéma pour la création d'un Job
class CrawlJobCreate(CrawlJobBase):
    task_id: str

# Schéma pour la mise à jour d'un Job
class CrawlJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    progress: Optional[float] = None
    current_step: Optional[str] = None
    result_data: Optional[dict] = None
    error_message: Optional[str] = None

# Schéma pour l'affichage d'un Job
class CrawlJob(TimeStampedSchema):
    id: int
    land_id: int
    job_type: str
    status: JobStatus
    progress: float
