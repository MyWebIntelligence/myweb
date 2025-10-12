"""
Module des tâches asynchrones Celery
"""

from .embedding_tasks import (
    generate_embeddings_for_land_task,
    generate_embeddings_for_expressions_task,
    extract_paragraphs_for_land_task
)
from .crawling_task import crawl_land_task
from .media_analysis_task import (
    analyze_land_media_task,
    analyze_media_batch_task,
)
from .text_processing_tasks import (
    analyze_text_content_task,
    extract_paragraphs_for_expression_task,
)
from .readable_task import process_readable_task
from .readable_test_task import test_readable_simple
from .readable_working_task import readable_working_task

__all__ = [
    "generate_embeddings_for_land_task",
    "generate_embeddings_for_expressions_task", 
    "extract_paragraphs_for_land_task",
    "extract_paragraphs_for_expression_task",
    "analyze_text_content_task",
    "crawl_land_task",
    "analyze_land_media_task",
    "analyze_media_batch_task",
    "process_readable_task",
    "test_readable_simple",
    "readable_working_task",
]
