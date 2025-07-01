"""
Service de crawling qui orchestre le moteur de crawling et les tâches asynchrones.
"""
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.db import models
from app.crud import crud_land
from app.core.crawler_engine import CrawlerEngine
from app.core.celery_app import celery_app

class CrawlingService:
    """
    Service pour gérer les opérations de crawling.
    """
    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient):
        self.db = db
        self.http_client = http_client
        self.engine = CrawlerEngine(db, http_client)

    async def start_land_crawl(self, land_id: int):
        """
        Lance une tâche de crawling asynchrone pour un land.
        """
        land = await crud_land.get_land(self.db, land_id=land_id)
        if not land:
            raise ValueError("Land not found")

        # Lancement de la tâche Celery
        task = celery_app.send_task("app.tasks.crawling_task.crawl_land_task", args=[land_id])
        
        return {"job_id": task.id, "message": "Crawl task initiated"}

    async def crawl_land_directly(self, land_id: int):
        """
        Lance un crawling direct (synchrone dans ce contexte) pour un land.
        Utilisé par la tâche Celery.
        """
        land = await crud_land.get_land(self.db, land_id=land_id)
        if not land:
            raise ValueError("Land not found")
        
        processed, errors = await self.engine.crawl_land(land)
        return {"processed": processed, "errors": errors}

    async def start_land_consolidation(self, land_id: int):
        """
        Lance une tâche de consolidation asynchrone pour un land.
        """
        land = await crud_land.get_land(self.db, land_id=land_id)
        if not land:
            raise ValueError("Land not found")

        task = celery_app.send_task("app.tasks.consolidation_task.consolidate_land_task", args=[land_id])
        
        return {"job_id": task.id, "message": "Consolidation task initiated"}

    async def consolidate_land_directly(self, land_id: int):
        """
        Lance une consolidation directe (synchrone) pour un land.
        """
        land = await crud_land.get_land(self.db, land_id=land_id)
        if not land:
            raise ValueError("Land not found")
        
        processed, errors = await self.engine.consolidate_land(land)
        return {"processed": processed, "errors": errors}
