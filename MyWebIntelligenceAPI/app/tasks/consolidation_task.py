"""
Tâche Celery pour la consolidation
"""
import asyncio
from app.core.celery_app import celery_app
from app.services.crawling_service import CrawlingService
from app.db.base import AsyncSessionLocal
import httpx

@celery_app.task(bind=True)
def consolidate_land_task(self, land_id: int):
    """
    Tâche Celery pour consolider un land.
    """
    async def async_consolidate():
        db = AsyncSessionLocal()
        async with httpx.AsyncClient() as http_client:
            service = CrawlingService(db, http_client)
            try:
                result = await service.consolidate_land_directly(land_id)
                return result
            except Exception as e:
                print(f"Error during consolidation task for land {land_id}: {e}")
                raise
            finally:
                await db.close()

    return asyncio.run(async_consolidate())
