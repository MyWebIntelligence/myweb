"""
Endpoints pour la gestion des Jobs Celery
"""
from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult
from app.core.celery_app import celery_app
from app.schemas.job import JobStatus

router = APIRouter()

@router.get("/{job_id}", response_model=JobStatus, status_code=status.HTTP_200_OK)
async def get_job_status(job_id: str):
    """
    Récupérer le statut et le résultat d'une tâche Celery.
    """
    task_result = AsyncResult(job_id, app=celery_app)

    if not task_result:
        raise HTTPException(status_code=404, detail="Job not found")

    status = task_result.status
    result = task_result.result if task_result.ready() else None

    if status == 'FAILURE':
        response = {
            "job_id": job_id,
            "status": status,
            "progress": 0,
            "result": str(result),
            "error_message": str(task_result.traceback)
        }
    elif status == 'PENDING':
        response = {
            "job_id": job_id,
            "status": status,
            "progress": 0,
            "result": None,
            "error_message": None
        }
    elif status == 'SUCCESS':
         response = {
            "job_id": job_id,
            "status": status,
            "progress": 100,
            "result": result,
            "error_message": None
        }
    else: # RUNNING or other states
        progress = 0
        if result and isinstance(result, dict) and 'progress' in result:
            progress = result['progress']
        
        response = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "result": result,
            "error_message": None
        }

    return JobStatus(**response)
