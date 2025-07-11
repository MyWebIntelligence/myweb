from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json

from app.db import models
from app.schemas.job import CrawlJobCreate
from app.db.models import CrawlStatus as JobStatus

class CRUDJob:
    async def get(self, db: AsyncSession, job_id: int) -> Optional[models.CrawlJob]:
        """Récupère un job par son ID."""
        result = await db.execute(select(models.CrawlJob).filter(models.CrawlJob.id == job_id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, *, obj_in: CrawlJobCreate) -> models.CrawlJob:
        """Crée un nouveau job."""
        db_obj = models.CrawlJob(
            land_id=obj_in.land_id,
            job_type=obj_in.job_type,
            celery_task_id=obj_in.task_id,
            status=JobStatus.PENDING,
            parameters=obj_in.parameters
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_status(self, db: AsyncSession, job_id: int, status: JobStatus, result: Optional[Dict[str, Any]] = None):
        """Met à jour le statut et le résultat d'un job."""
        job_obj = await self.get(db, job_id)
        if job_obj:
            job_obj.status = status
            if result:
                job_obj.result_data = result
            await db.commit()
            await db.refresh(job_obj)
        return job_obj

job = CRUDJob()
