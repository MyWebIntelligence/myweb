"""
Lands endpoints v2
Breaking changes: Mandatory pagination, enhanced response format
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_active_user
from app.schemas.land import Land, LandCreate, LandUpdate
from app.crud.crud_land import land as crud_land
from app.schemas.job import CrawlRequest, CrawlJobResponse
from app.services.crawling_service import start_crawl_for_land
from app.schemas.user import User
from app.api.versioning import get_api_version_from_request
from pydantic import BaseModel

router = APIRouter()


class PaginatedResponse(BaseModel):
    """Réponse paginée standardisée pour v2"""
    items: List[Land]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class V2ErrorResponse(BaseModel):
    """Format d'erreur standardisé pour v2"""
    error_code: str
    message: str
    details: Optional[dict] = None
    suggestion: Optional[str] = None


@router.get("/", response_model=PaginatedResponse)
async def list_lands_v2(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    name_filter: Optional[str] = Query(None, description="Filter by land name"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> PaginatedResponse:
    """
    List user's lands with mandatory pagination
    
    Breaking changes from v1:
    - Pagination is now mandatory (page and page_size required)
    - Enhanced response format with pagination metadata
    - Additional filtering options
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count for pagination
    total = await crud_land.count_user_lands(db, user_id=current_user.id)
    
    # Get paginated lands
    lands = await crud_land.get_user_lands_paginated(
        db, 
        user_id=current_user.id,
        offset=offset,
        limit=page_size,
        name_filter=name_filter,
        status_filter=status_filter
    )
    
    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    return PaginatedResponse(
        items=lands,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous
    )


@router.get("/{land_id}", response_model=Land)
async def get_land_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Get a specific land by ID
    
    Enhanced error handling with v2 format
    """
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure you have access to this land"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to access this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or use lands you own"
            }
        )
    
    return land


@router.post("/", response_model=Land)
async def create_land_v2(
    land_data: LandCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Create a new land
    
    Enhanced validation and error handling
    """
    try:
        # Check if land name already exists for this user
        existing_land = await crud_land.get_by_name_and_user(
            db, name=land_data.name, user_id=current_user.id
        )
        
        if existing_land:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "LAND_NAME_EXISTS",
                    "message": f"Land with name '{land_data.name}' already exists",
                    "details": {"name": land_data.name},
                    "suggestion": "Choose a different name for your land"
                }
            )
        
        # Create land with owner_id
        land_data_dict = land_data.dict()
        land_data_dict["owner_id"] = current_user.id
        
        land = await crud_land.create(db, obj_in=land_data_dict)
        return land
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_CREATION_FAILED",
                "message": "Failed to create land",
                "details": {"error": str(e)},
                "suggestion": "Check your input data and try again"
            }
        )


@router.put("/{land_id}", response_model=Land)
async def update_land_v2(
    land_id: int,
    land_update: LandUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Land:
    """
    Update a land
    
    Enhanced error handling with v2 format
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to update this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or update lands you own"
            }
        )
    
    try:
        updated_land = await crud_land.update(db, db_obj=land, obj_in=land_update)
        return updated_land
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_UPDATE_FAILED",
                "message": "Failed to update land",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check your input data and try again"
            }
        )


@router.delete("/{land_id}")
async def delete_land_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Delete a land
    
    Enhanced response format for v2
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to delete this land",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or delete lands you own"
            }
        )
    
    try:
        await crud_land.remove(db, id=land_id)
        
        return {
            "success": True,
            "message": f"Land {land_id} deleted successfully",
            "details": {
                "land_id": land_id,
                "name": land.name,
                "deleted_at": "2025-07-04T00:00:00Z"  # In real implementation, use actual timestamp
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "LAND_DELETION_FAILED",
                "message": "Failed to delete land",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Try again or contact support if the problem persists"
            }
        )


@router.post("/{land_id}/crawl", response_model=CrawlJobResponse)
async def crawl_land_v2(
    land_id: int,
    crawl_request: CrawlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> CrawlJobResponse:
    """
    Start a crawl job for a specific land
    
    Enhanced error handling with v2 format
    """
    # Check if user has permission to crawl this land
    land_obj = await crud_land.get(db, id=land_id)
    
    if not land_obj:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure it exists"
            }
        )
    
    if land_obj.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to crawl this land",
                "details": {"land_id": land_id, "owner_id": land_obj.owner_id},
                "suggestion": "Contact the land owner or crawl lands you own"
            }
        )
    
    try:
        return await start_crawl_for_land(db, land_id, crawl_request)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "CRAWL_START_FAILED",
                "message": "Failed to start crawl job",
                "details": {"land_id": land_id, "error": str(e)},
                "suggestion": "Check crawl parameters and try again"
            }
        )


@router.get("/{land_id}/stats")
async def get_land_stats_v2(
    land_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Get enhanced statistics for a land
    
    New endpoint in v2 with detailed analytics
    """
    # Check if land exists and user has access
    land = await crud_land.get(db, id=land_id)
    
    if not land:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "LAND_NOT_FOUND",
                "message": f"Land with ID {land_id} not found",
                "details": {"land_id": land_id},
                "suggestion": "Check the land ID and ensure you have access to this land"
            }
        )
    
    if land.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ACCESS_DENIED",
                "message": "You don't have permission to access this land's statistics",
                "details": {"land_id": land_id, "owner_id": land.owner_id},
                "suggestion": "Contact the land owner or access lands you own"
            }
        )
    
    # Get enhanced statistics (mock data for now)
    return {
        "land_id": land_id,
        "name": land.name,
        "crawl_stats": {
            "total_crawls": 5,
            "successful_crawls": 4,
            "failed_crawls": 1,
            "last_crawl_date": "2025-07-03T14:30:00Z",
            "avg_crawl_duration": "00:15:30"
        },
        "content_stats": {
            "total_pages": 1250,
            "total_expressions": 3400,
            "total_media": 850,
            "content_types": {
                "html": 1200,
                "pdf": 35,
                "images": 850,
                "other": 15
            }
        },
        "export_stats": {
            "total_exports": 12,
            "recent_exports": [
                {"format": "csv", "date": "2025-07-02T10:15:00Z", "records": 1250},
                {"format": "gexf", "date": "2025-07-01T16:45:00Z", "records": 3400}
            ]
        },
        "performance_metrics": {
            "avg_response_time": "200ms",
            "success_rate": "94.2%",
            "data_quality_score": "87%"
        }
    }