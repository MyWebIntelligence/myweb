from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_active_user
from app.schemas.land import Land, LandCreate, LandUpdate
from app.crud.crud_land import land as crud_land
from app.schemas.job import CrawlRequest, CrawlJobResponse
from app.services import crawling_service
from app.core.websocket import websocket_manager
from app.schemas.user import User
from app.tasks.consolidation_task import consolidate_land_task
from app.tasks.media_analysis_task import analyze_land_media_task
from app.tasks.readable_task import process_readable_task
from app.schemas.readable import ReadableRequest
from typing import Dict, Any, Optional

router = APIRouter()

@router.post("/{land_id}/crawl", response_model=CrawlJobResponse)
async def crawl_land(
    land_id: int,
    crawl_request: CrawlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Start a crawl job for a specific land.
    """
    # Check if user has permission to crawl this land
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    return await crawling_service.start_crawl_for_land(db, land_id, crawl_request)

@router.post("/{land_id}/consolidate")
async def consolidate_land(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Consolidate data for a specific land.
    """
    # Check if user has permission
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    # Start consolidation task
    task_result = consolidate_land_task.delay(land_id)
    return {
        "message": f"Consolidation started for land {land_id}",
        "task_id": task_result.id
    }

@router.post("/{land_id}/readable")
async def generate_readable(
    land_id: int,
    request: ReadableRequest = ReadableRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate readable content for expressions in a land.
    Supports merge strategies and LLM validation.
    """
    # Check if user has permission
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    # Create job record
    from app.crud import crud_job
    from app.schemas.job import CrawlJobCreate
    
    # Create job for tracking
    job_data = CrawlJobCreate(
        land_id=land_id,
        job_type="readable_processing",
        task_id="",  # Will be set after task creation
        parameters={
            "limit": request.limit,
            "depth": request.depth,
            "merge_strategy": request.merge_strategy.value,
            "enable_llm": request.enable_llm
        }
    )
    
    job = await crud_job.job.create(db, obj_in=job_data)
    
    # Start readable processing task
    task_result = process_readable_task.delay(
        land_id=land_id,
        job_id=job.id,
        limit=request.limit,
        depth=request.depth,
        merge_strategy=request.merge_strategy.value,
        enable_llm=request.enable_llm
    )
    
    # Update job with task ID
    await crud_job.job.update(db, db_obj=job, obj_in={"task_id": task_result.id})
    
    return {
        "message": f"Readable processing started for land {land_id}",
        "job_id": job.id,
        "task_id": task_result.id,
        "parameters": {
            "limit": request.limit,
            "depth": request.depth,
            "merge_strategy": request.merge_strategy.value,
            "enable_llm": request.enable_llm
        }
    }

@router.post("/{land_id}/medianalyse")
async def analyze_media(
    land_id: int,
    depth: int = 999,
    minrel: float = 0.0,
    batch_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Analyze media content for expressions in a land using Celery async task.
    
    Args:
        land_id: ID of the land
        depth: Maximum depth of expressions to analyze (default: 999)
        minrel: Minimum relevance score (default: 0.0)
        batch_size: Number of media per processing batch (default: 50)
    """
    # Check if user has permission
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    # Create job record
    from app.crud import crud_job
    from app.schemas.job import CrawlJobCreate
    
    # Create job for tracking
    job_data = CrawlJobCreate(
        land_id=land_id,
        job_type="media_analysis",
        task_id="",  # Will be set after task creation
        parameters={
            "depth": depth,
            "minrel": minrel,
            "batch_size": batch_size
        }
    )
    
    job = await crud_job.job.create(db, obj_in=job_data)
    
    # Start media analysis task
    task_result = analyze_land_media_task.delay(
        job_id=job.id,
        land_id=land_id,
        depth=depth,
        minrel=minrel,
        batch_size=batch_size
    )
    
    # Update job with task ID
    await crud_job.job.update(db, db_obj=job, obj_in={"task_id": task_result.id})
    
    return {
        "message": f"Media analysis started for land {land_id}",
        "job_id": job.id,
        "task_id": task_result.id,
        "parameters": {
            "depth": depth,
            "minrel": minrel,
            "batch_size": batch_size
        }
    }

@router.post("/{land_id}/seorank")
async def analyze_seo_rank(
    land_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Analyze SEO ranking for expressions in a land.
    """
    # Check if user has permission
    land_obj = await crud_land.get(db, id=land_id)
    if not land_obj or land_obj.owner_id != getattr(current_user, 'id', None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found or you don't have permission"
        )
    
    # TODO: Implement SEO ranking task
    return {
        "message": f"SEO ranking not yet implemented for land {land_id}",
        "status": "placeholder"
    }

