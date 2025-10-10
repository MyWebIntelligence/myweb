from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_active_user
from app.schemas.land import Land, LandCreate, LandUpdate
from app.crud.crud_land import land as crud_land
from app.schemas.job import CrawlRequest, CrawlJobResponse
from app.services.crawling_service import start_crawl_for_land
from app.core.websocket import websocket_manager
from app.schemas.user import User

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
    
    return await start_crawl_for_land(db, land_id, crawl_request)
