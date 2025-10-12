import logging
import asyncio
from datetime import datetime, timezone
from collections import defaultdict
from celery import group
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.crud import crud_job, crud_expression
from app.db.models import CrawlStatus
from app.config import settings
from app.core.crawler_engine import CrawlerEngine
from app.core.websocket import WebSocketManager

logger = logging.getLogger(__name__)

async def _async_crawl_land_task(job_id: int, ws_channel: str = None):
    """
    Async implementation of crawl land task.

    Args:
        job_id: ID of the crawl job
        ws_channel: Optional WebSocket channel for progress updates
    """
    job = None
    land_id_for_logging = None
    engine = None
    start_time = datetime.now(timezone.utc)

    logger.info(f"=" * 80)
    logger.info(f"CRAWL STARTED - Job ID: {job_id}")
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info(f"=" * 80)

    # Use async context manager for database session
    async with AsyncSessionLocal() as db:
        try:
            engine = CrawlerEngine(db)

            job = await crud_job.job.get(db, job_id=job_id)
            if not job:
                logger.error(f"Crawl job with id {job_id} not found.")
                return

            # Récupération de l'ID du land avec accès sécurisé à l'attribut SQLAlchemy
            land_id_for_logging = getattr(job, 'land_id', 0)
            await crud_job.job.update_status(db, job_id=job_id, status=CrawlStatus.RUNNING)

            # Accès correct aux paramètres du job
            params = job.parameters if job.parameters is not None else {}
            limit = params.get("limit", 0) if isinstance(params, dict) else 0
            depth = params.get("depth") if isinstance(params, dict) else None
            http_status = params.get("http_status") if isinstance(params, dict) else None
            analyze_media = bool(params.get("analyze_media")) if isinstance(params, dict) else False

            logger.info(f"Land ID: {land_id_for_logging}")
            logger.info(
                "Crawl Parameters: limit=%s, depth=%s, http_status=%s, analyze_media=%s",
                limit,
                depth,
                http_status,
                analyze_media,
            )

            land, expressions = await engine.prepare_crawl(
                land_id_for_logging,
                limit=limit,
                depth=depth,
                http_status=http_status,
            )

            expression_ids = [expr.id for expr in expressions]

            processed = 0
            errors = 0
            http_stats = defaultdict(int)
            total_expressions = len(expression_ids)
            
            # Initialize WebSocket manager for progress updates
            websocket_manager = WebSocketManager()

            batch_size = max(1, getattr(settings, "CRAWL_BATCH_SIZE", 10))

            if not expression_ids:
                if ws_channel:
                    await websocket_manager.send_crawl_progress(
                        ws_channel, 0, 0, "Aucune expression à crawler"
                    )
                await engine.http_client.aclose()
                engine = None
            elif len(expression_ids) <= batch_size:
                if ws_channel:
                    await websocket_manager.send_crawl_progress(
                        ws_channel, 0, total_expressions, "Début du crawling..."
                    )
                
                processed, errors, stats = await engine.crawl_expressions(
                    expressions, analyze_media=analyze_media
                )
                for code, count in stats.items():
                    http_stats[code] += count
                
                if ws_channel:
                    await websocket_manager.send_crawl_progress(
                        ws_channel, processed, total_expressions, f"Crawl terminé: {processed} traités, {errors} erreurs"
                    )
                    
                await engine.http_client.aclose()
                engine = None
            else:
                await engine.http_client.aclose()
                engine = None
                batches = [
                    expression_ids[i : i + batch_size]
                    for i in range(0, len(expression_ids), batch_size)
                ]

                batch_tasks = [
                    celery_app.signature(
                        "tasks.crawl_expression_batch_task",
                        args=[job_id, batch, analyze_media],
                    )
                    for batch in batches
                ]

                group_result = group(batch_tasks).apply_async()
                batch_results = await asyncio.to_thread(
                    group_result.get, disable_sync_subtasks=False
                )

                for result in batch_results:
                    if not isinstance(result, dict):
                        continue
                    processed += int(result.get("processed", 0))
                    errors += int(result.get("errors", 0))
                    for code, count in result.get("http_status", {}).items():
                        http_stats[code] += count

            # Calculate metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            speed = processed / duration if duration > 0 else 0

            # Log summary
            http_stats_dict = dict(http_stats)

            logger.info(f"=" * 80)
            logger.info(f"CRAWL COMPLETED - Job ID: {job_id}, Land ID: {land_id_for_logging}")
            logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"URLs Processed: {processed}")
            logger.info(f"Errors: {errors}")
            logger.info(f"Speed: {speed:.2f} URLs/second")
            logger.info("HTTP Status Codes:")
            for status_code, count in sorted(http_stats_dict.items()):
                logger.info(f"  {status_code}: {count}")
            logger.info(f"=" * 80)

            # Update job with detailed results
            result = {
                "processed": processed,
                "errors": errors,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "speed_urls_per_second": speed,
                "http_status_codes": http_stats_dict
            }
            await crud_job.job.update_status(
                db,
                job_id=job_id,
                status=CrawlStatus.COMPLETED,
                result=result
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            logger.error(f"=" * 80)
            logger.error(f"CRAWL FAILED - Job ID: {job_id}, Land ID: {land_id_for_logging or 'unknown'}")
            logger.error(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error(f"Error: {str(e)}")
            logger.error(f"=" * 80)
            logger.exception("Full traceback:")

            if job:
                await crud_job.job.update_status(
                    db,
                    job_id=job_id,
                    status=CrawlStatus.FAILED,
                    result={
                        "error": str(e),
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "duration_seconds": duration
                    }
                )
            else:
                logger.error(f"Could not update status for job {job_id} because it could not be fetched.")
        finally:
            if engine and hasattr(engine, 'http_client'):
                await engine.http_client.aclose()

@celery_app.task(name="tasks.crawl_land_task", bind=True)
def crawl_land_task(self, job_id: int, ws_channel: str = None):
    """
    Celery task to crawl a land (synchronous wrapper).

    Args:
        job_id: ID of the crawl job
        ws_channel: Optional WebSocket channel for progress updates
    """
    # Get or create event loop for this thread
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the async task
    try:
        loop.run_until_complete(_async_crawl_land_task(job_id, ws_channel))
    finally:
        # Don't close the loop as it might be reused by Celery
        pass


async def _async_crawl_expression_batch_task(job_id: int, expression_ids: list[int], analyze_media: bool) -> dict:
    start_time = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        engine = CrawlerEngine(db)
        try:
            expressions = await crud_expression.expression.get_by_ids(db, expression_ids)
            processed, errors, http_stats = await engine.crawl_expressions(
                expressions, analyze_media=analyze_media
            )
            end_time = datetime.now(timezone.utc)
            return {
                "processed": processed,
                "errors": errors,
                "http_status": http_stats,
                "duration_seconds": (end_time - start_time).total_seconds(),
            }
        except Exception as exc:
            logger.exception("Batch crawl failed for expressions %s: %s", expression_ids, exc)
            await db.rollback()
            return {
                "processed": 0,
                "errors": len(expression_ids),
                "http_status": {"error": len(expression_ids)},
                "duration_seconds": 0,
            }
        finally:
            try:
                await db.rollback()
            except Exception:
                pass
            await engine.http_client.aclose()


@celery_app.task(name="tasks.crawl_expression_batch_task", bind=True)
def crawl_expression_batch_task(self, job_id: int, expression_ids: list[int], analyze_media: bool = False):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        _async_crawl_expression_batch_task(job_id, expression_ids, analyze_media)
    )
