"""
Module des tâches asynchrones Celery (V2 - Sync only)
"""

from .crawling_task import crawl_land_task
from .consolidation_task import consolidate_land_task
from .domain_crawl_task import domain_crawl_task, domain_recrawl_task, domain_crawl_batch_task

# Export tasks temporarily disabled (needs refactoring)
# from .export_tasks import create_export_task

__all__ = [
    "crawl_land_task",
    "consolidate_land_task",
    "domain_crawl_task",
    "domain_recrawl_task",
    "domain_crawl_batch_task",
]
