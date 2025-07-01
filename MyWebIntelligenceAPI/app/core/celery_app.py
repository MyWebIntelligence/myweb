"""
Configuration de l'application Celery
"""

from celery import Celery
from ..config import settings

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.crawling_task"],
)

celery_app.conf.update(
    task_track_started=True,
)
