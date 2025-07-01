"""
Endpoints pour la gestion des Lands
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app import schemas
from app.crud import crud_land
from app.db import models
from app.api import dependencies
from app.tasks.crawling_task import crawl_land_task
from app.core.celery_app import celery_app
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/", response_model=schemas.Land, status_code=status.HTTP_201_CREATED)
async def create_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_in: schemas.LandCreate,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Créer un nouveau land.
    """
    if current_user.id is not None:
        land = await crud_land.create_land(db=db, land_in=land_in, owner_id=current_user.id)
        return land
    raise HTTPException(status_code=400, detail="Invalid user")

@router.get("/", response_model=List[schemas.Land])
async def read_lands(
    db: AsyncSession = Depends(dependencies.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Récupérer la liste des lands de l'utilisateur.
    """
    if current_user.id is not None:
        lands = await crud_land.get_lands_by_owner(
            db=db, owner_id=current_user.id, skip=skip, limit=limit
        )
        return lands
    return []

@router.get("/{land_id}", response_model=schemas.Land)
async def read_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Récupérer un land par son ID.
    """
    land = await crud_land.get_land(db, land_id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return land

@router.put("/{land_id}", response_model=schemas.Land)
async def update_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_id: int,
    land_in: schemas.LandUpdate,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Mettre à jour un land.
    """
    land = await crud_land.get_land(db, land_id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    land = await crud_land.update_land(db=db, db_land=land, land_in=land_in)
    return land

@router.delete("/{land_id}", response_model=schemas.Land)
async def delete_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Supprimer un land.
    """
    land = await crud_land.get_land(db, land_id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    land = await crud_land.delete_land(db=db, land_id=land_id)
    return land

@router.post("/{land_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def crawl_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Lancer une tâche de crawling pour un land.
    """
    # Vérifier que le land existe et appartient à l'utilisateur
    land = await crud_land.get_land(db, land_id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Créer un ID de job unique
    job_id = str(uuid.uuid4())
    
    # Lancer la tâche Celery (si Celery est configuré)
    try:
        # Pour l'instant, on retourne juste un job_id sans lancer réellement Celery
        # task = crawl_land_task.apply_async(args=[land_id], task_id=job_id)
        return {"job_id": job_id, "status": "started", "message": "Crawl job initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start crawl job: {str(e)}")

@router.post("/{land_id}/consolidate", status_code=status.HTTP_202_ACCEPTED)
async def consolidate_land(
    *,
    db: AsyncSession = Depends(dependencies.get_db),
    land_id: int,
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Lancer une tâche de consolidation pour un land.
    """
    land = await crud_land.get_land(db, land_id=land_id)
    if not land:
        raise HTTPException(status_code=404, detail="Land not found")
    if current_user.id is not None and land.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    job_id = str(uuid.uuid4())
    
    try:
        task = celery_app.send_task("app.tasks.consolidation_task.consolidate_land_task", args=[land_id], task_id=job_id)
        return {"job_id": job_id, "status": "started", "message": "Consolidation job initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start consolidation job: {str(e)}")
