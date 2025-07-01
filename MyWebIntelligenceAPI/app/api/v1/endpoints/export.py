"""
Endpoints pour la gestion des exports.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app import schemas
from app.crud import crud_land
from app.db import models
from app.api import dependencies
from app.core.celery_app import celery_app

router = APIRouter()

@router.post("/", response_model=schemas.Job, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    export_in: schemas.ExportCreate,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Créer un nouvel export.
    """
    land = await crud_land.get_land(db, land_id=export_in.land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    job_id = str(uuid.uuid4())

    try:
        task = celery_app.send_task(
            "app.tasks.export_task.export_land_task", 
            args=[export_in.land_id, export_in.export_type, export_in.minimum_relevance],
            task_id=job_id
        )
        # Vous voudrez probablement enregistrer ce job dans la base de données
        return {"job_id": job_id, "status": "started", "message": "Export job initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start export job: {str(e)}")
