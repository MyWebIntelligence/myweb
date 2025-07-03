from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_land, crud_job
from app.schemas.job import CrawlRequest, CrawlJobCreate
from app.tasks.crawling_task import crawl_land_task
from fastapi import HTTPException, status
from app.core.websocket import WebSocketManager

websocket_manager = WebSocketManager()

async def start_crawl_for_land(db: AsyncSession, land_id: int, crawl_request: CrawlRequest):
    """
    Creates a crawl job and dispatches it to a Celery worker with WebSocket progress tracking.
    """
    # Validate land exists
    land = await crud_land.get(db, id=land_id)
    if not land:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")

    # Validate crawl parameters
    if crawl_request.depth is not None and crawl_request.depth < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Depth must be a positive integer"
        )
    
    if crawl_request.limit is not None and crawl_request.limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Limit must be a positive integer"
        )

    # Create job record
    job_create_schema = CrawlJobCreate(
        land_id=land_id,
        job_type="crawl",
        parameters=crawl_request.dict(),
        task_id=""
    )
    db_job = await crud_job.create(db, obj_in=job_create_schema)

    try:
        # Dispatch task with WebSocket channel
        task = crawl_land_task.delay(
            job_id=db_job.id,
            ws_channel=f"crawl_progress_{db_job.id}"
        )
        
        # Update job with Celery task ID
        db_job.celery_task_id = task.id
        await db.commit()
        await db.refresh(db_job)
        
        # Return job info including WebSocket channel
        return {
            **db_job.__dict__,
            "ws_channel": f"crawl_progress_{db_job.id}"
        }
    
    except Exception as e:
        # Handle task dispatch failure
        await crud_job.update(
            db, 
            db_obj=db_job, 
            obj_in={"status": "FAILED", "error_message": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl task dispatch failed: {str(e)}"
        )
