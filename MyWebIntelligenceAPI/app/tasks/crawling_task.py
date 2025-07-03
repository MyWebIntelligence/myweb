import logging
import asyncio
from app.core.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.crud import crud_job
from app.db.models import CrawlStatus
import httpx
from app.core.crawler_engine import CrawlerEngine

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.crawl_land_task", bind=True)
def crawl_land_task(self, job_id: int):
    """
    Celery task to crawl a land.
    """
    async def async_crawl():
        db = AsyncSessionLocal()
        job = None
        land_id_for_logging = None
        try:
            async with httpx.AsyncClient() as http_client:
                engine = CrawlerEngine(db, http_client)
                
                job = await crud_job.job.get(db, job_id=job_id)
                if not job:
                    logger.error(f"Crawl job with id {job_id} not found.")
                    return

                land_id_for_logging = job.land_id
                await crud_job.job.update_status(db, job_id=job.id, status=CrawlStatus.RUNNING)
                
                limit = job.parameters.get("limit") if job.parameters else None
                depth = job.parameters.get("depth") if job.parameters else None
                http_status = job.parameters.get("http_status") if job.parameters else None

                processed, errors = await engine.crawl_land(land_id=job.land_id, limit=limit, depth=depth, http_status=http_status)
                
                await crud_job.job.update_status(db, job_id=job.id, status=CrawlStatus.COMPLETED, result={"processed": processed, "errors": errors})
                logger.info(f"Crawl for land {job.land_id} completed. Processed: {processed}, Errors: {errors}")
        except Exception as e:
            logger.exception(f"Crawl for land {land_id_for_logging or 'unknown'} failed.")
            if job:
                await crud_job.job.update_status(db, job_id=job.id, status=CrawlStatus.FAILED, result={"error": str(e)})
            else:
                logger.error(f"Could not update status for job {job_id} because it could not be fetched.")
        finally:
            await db.close()

    asyncio.run(async_crawl())
