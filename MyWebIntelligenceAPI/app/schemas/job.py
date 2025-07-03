from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import enum

class CrawlStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class CrawlRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Max number of URLs to process")
    depth: Optional[int] = Field(None, description="Crawl depth")
    http_status: Optional[str] = Field(None, description="Filter by HTTP status for re-crawling")

# Schéma de base pour un Job
class CrawlJobBase(BaseModel):
    land_id: int
    job_type: str
    parameters: Optional[Dict[str, Any]] = None

# Schéma pour la création d'un Job
class CrawlJobCreate(CrawlJobBase):
    task_id: str

class CrawlJobResponse(BaseModel):
    job_id: int
    celery_task_id: str
    land_id: int
    status: CrawlStatus
    created_at: datetime
    parameters: Dict[str, Any]

    class Config:
        orm_mode = True
