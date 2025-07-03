"""
Configuration de l'application Celery
"""

from celery import Celery
from ..config import settings

celery_app = Celery("tasks")

celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.update(
    task_track_started=True,
)
