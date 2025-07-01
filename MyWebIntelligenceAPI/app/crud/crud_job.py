"""
Fonctions CRUD pour les Jobs
"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json

from app.db import models
from app.schemas.job import CrawlJobCreate as JobCreate, CrawlJobUpdate as JobUpdate
from app.db.models import CrawlStatus as JobStatus

async def get_job(db: AsyncSession, job_id: int) -> Optional[models.CrawlJob]:
    """Récupère un job par son ID."""
    result = await db.execute(select(models.CrawlJob).filter(models.CrawlJob.id == job_id))
    return result.scalar_one_or_none()

async def create(db: AsyncSession, *, obj_in: JobCreate) -> models.CrawlJob:
    """Crée un nouveau job."""
    db_obj = models.CrawlJob(
        land_id=obj_in.land_id,
        job_type=obj_in.job_type,
        task_id=obj_in.task_id,
        status=JobStatus.PENDING
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def update_job_status(db: AsyncSession, job_id: int, status: JobStatus, result: Optional[Dict[str, Any]] = None):
    """Met à jour le statut et le résultat d'un job."""
    job = await get_job(db, job_id)
    if job:
        job.status = status
        if result:
            job.result = json.dumps(result)
        await db.commit()
