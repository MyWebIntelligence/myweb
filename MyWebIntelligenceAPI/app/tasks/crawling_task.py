"""
Tâche Celery pour le crawling
"""
import asyncio
from app.core.celery_app import celery_app
from app.services.crawling_service import CrawlingService
from app.db.base import AsyncSessionLocal
import httpx
from app.crud import crud_land, crud_job
from app.schemas.job import CrawlJobCreate
from app.db.models import CrawlStatus as JobStatus

@celery_app.task(bind=True)
def crawl_land_task(self, land_id: int):
    """
    Tâche Celery pour crawler un land.
    Elle utilise le CrawlingService pour effectuer le travail.
    """
    async def async_crawl():
        db = AsyncSessionLocal()
        async with httpx.AsyncClient() as http_client:
            service = CrawlingService(db, http_client)
            job = None
            try:
                # 1. Créer un job pour suivre la tâche
                job_in = CrawlJobCreate(land_id=land_id, job_type="crawling", task_id=self.request.id)
                job = await crud_job.create(db, obj_in=job_in)
                
                # 2. Mettre à jour le statut du land
                await crud_land.update_land_status(db, land_id=land_id, status=JobStatus.RUNNING)

                # 3. Lancer le crawling
                result = await service.crawl_land_directly(land_id)
                
                # 4. Mettre à jour le statut à la fin
                await crud_land.update_land_status(db, land_id=land_id, status=JobStatus.COMPLETED)
                await crud_job.update_job_status(db, job_id=job.id, status=JobStatus.COMPLETED, result=result)
                
                return result

            except Exception as e:
                error_message = str(e)
                print(f"Error during crawl task for land {land_id}: {error_message}")
                if job:
                    await crud_job.update_job_status(db, job_id=job.id, status=JobStatus.FAILED, result={"error": error_message})
                await crud_land.update_land_status(db, land_id=land_id, status=JobStatus.FAILED)
                # Re-raise l'exception pour que Celery la marque comme FAILED
                raise
            finally:
                await db.close()

    return asyncio.run(async_crawl())
