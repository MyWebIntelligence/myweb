"""
Module des tâches asynchrones Celery (V2 - Sync only)
"""

from .crawling_task import crawl_land_task
from .export_tasks import export_task
from .consolidation_task import consolidate_land_task

__all__ = [
    "crawl_land_task",
    "export_task",
    "consolidate_land_task",
]
