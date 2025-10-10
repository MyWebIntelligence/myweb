import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.crud import crud_job
from app.db.models import CrawlStatus
import httpx
from app.core.crawler_engine import CrawlerEngine

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.crawl_land_task", bind=True)
async def crawl_land_task(self, job_id: int):
    """
    Celery task to crawl a land.
    """
    db: AsyncSession = AsyncSessionLocal()
    job = None
    land_id_for_logging = None
    engine = None
    try:
        engine = CrawlerEngine(db)
        
        job = await crud_job.job.get(db, job_id=job_id)
        if not job:
            logger.error(f"Crawl job with id {job_id} not found.")
            return

        # Récupération de l'ID du land avec accès sécurisé à l'attribut SQLAlchemy
        land_id_for_logging = getattr(job, 'land_id', 0)
        await crud_job.job.update_status(db, job_id=job_id, status=CrawlStatus.RUNNING)
        
        # Accès correct aux paramètres du job
        params = job.parameters if job.parameters is not None else {}
        limit = params.get("limit", 0) if isinstance(params, dict) else 0
        depth = params.get("depth") if isinstance(params, dict) else None
        http_status = params.get("http_status") if isinstance(params, dict) else None

        processed, errors = await engine.crawl_land(land_id=land_id_for_logging, limit=limit, depth=depth, http_status=http_status)
        
        await crud_job.job.update_status(db, job_id=job_id, status=CrawlStatus.COMPLETED, result={"processed": processed, "errors": errors})
        logger.info(f"Crawl for land {land_id_for_logging} completed. Processed: {processed}, Errors: {errors}")
    except Exception as e:
        logger.exception(f"Crawl for land {land_id_for_logging or 'unknown'} failed.")
        if job:
            await crud_job.job.update_status(db, job_id=job_id, status=CrawlStatus.FAILED, result={"error": str(e)})
        else:
            logger.error(f"Could not update status for job {job_id} because it could not be fetched.")
    finally:
        await db.close()
        if engine and hasattr(engine, 'http_client'):
            await engine.http_client.aclose()
