# MyWebIntelligenceAPI Architecture

This document outlines the architecture of the MyWebIntelligenceAPI application.

## 1. Detailed Application Structure

The application is structured into the following main directories:

- **`main.py`**: The main entry point of the FastAPI application. It initializes the FastAPI app, includes the API routers, and configures the middleware.

- **`config.py`**: Contains the application settings, loaded from environment variables.

- **`api/`**: Contains the API endpoints, versioning, and routing logic.
    - **`router.py`**: The main API router, which includes the versioned routers.
    - **`versioning.py`**: The middleware for handling API versioning.
    - **`dependencies.py`**: FastAPI dependencies, such as getting the current user.
    - **`v1/`** and **`v2/`**: Each version has its own subdirectory with `router.py` and an `endpoints` directory.
        - **`endpoints/`**: Contains the actual API endpoint files, organized by resource (e.g., `lands.py`, `jobs.py`).

- **`core/`**: Contains the core components of the application.
    - **`celery_app.py`**: The Celery application instance and configuration.
    - **`crawler_engine.py`**: The main crawling logic.
    - **`content_extractor.py`**: Extracts the main content from HTML.
    - **`media_processor.py`**: Processes and analyzes media files.
    - **`text_processing.py`**: Handles text normalization, keyword extraction, and relevance scoring.
    - **`security.py`**: Authentication and authorization logic.
    - **`settings.py`**: Pydantic settings models.
    - **`embedding_providers/`**: A registry for different embedding providers (e.g., OpenAI, Mistral).

- **`crud/`**: Contains the CRUD (Create, Read, Update, Delete) operations for the database models. Each file corresponds to a database model (e.g., `crud_land.py`, `crud_expression.py`).
    - **`base.py`**: A base class for CRUD operations.

- **`db/`**: Contains the database models and session management.
    - **`models.py`**: The SQLAlchemy database models.
    - **`session.py`**: The database session and engine setup.
    - **`base.py`**: The declarative base for the SQLAlchemy models.

- **`schemas/`**: Contains the Pydantic schemas for data validation and serialization. Each file corresponds to a resource (e.g., `land.py`, `expression.py`).

- **`services/`**: Contains the business logic and services that expose the core functionalities.
    - **`crawling_service.py`**: The service for managing crawl jobs.
    - **`embedding_service.py`**: The service for managing embedding generation.
    - **`export_service.py`**: The service for exporting data.
    - **`text_processor_service.py`**: The service for text processing tasks.

- **`tasks/`**: Contains the asynchronous tasks that are handled by Celery.
    - **`crawling_task.py`**: The Celery task for crawling a land.
    - **`readable_working_task.py`**: The Celery task for readable content extraction.
    - **`embedding_tasks.py`**: Celery tasks for generating embeddings.
    - **`export_task.py`**: The Celery task for exporting data.

- **`utils/`**: Contains utility functions.
    - **`text_utils.py`**: Utility functions for text manipulation.

## 2. API Versioning

The API uses a versioning middleware to handle different versions of the API. The version is specified in the `Accept` header of the request.

- **`v1/`**: The first version of the API. It is stable and contains the main functionalities of the application.
- **`v2/`**: The second version of the API. It is currently in beta and introduces breaking changes and new features.

## 3. Core Components

### 3.1. Crawler Engine (`core/crawler_engine.py`)

The crawler engine is responsible for crawling web pages. It uses `httpx` for making HTTP requests and `BeautifulSoup` for parsing HTML content.

The main steps of the crawling process are:

1.  **Fetch content**: Fetches the HTML content of a given URL.
2.  **Extract content and metadata**: Extracts the readable content, title, description, keywords, and language of the page.
3.  **Calculate relevance**: Calculates the relevance of the page based on a dictionary of keywords.
4.  **Extract links and media**: Extracts the links and media from the page.
5.  **Save to DB**: Saves the extracted data to the database.

### 3.2. Media Processor (`core/media_processor.py`)

The media processor is responsible for analyzing media files (images, videos, audios). It uses `Pillow` for image analysis and `playwright` for dynamic media extraction.

The main steps of the media analysis process are:

1.  **Analyze image properties**: Extracts the width, height, format, color mode, and aspect ratio of an image.
2.  **Extract colors**: Extracts the dominant colors of an image using K-means clustering.
3.  **Extract EXIF**: Extracts the EXIF metadata of an image.

### 3.3. Text Processing (`core/text_processing.py`)

The text processing module provides functions for text normalization, keyword extraction, and relevance calculation. It uses `nltk` for natural language processing.

## 4. Services

### 4.1. Crawling Service (`services/crawling_service.py`)

The crawling service exposes the crawling functionality. It provides a method to start a crawl for a given land and to get the pipeline statistics.

### 4.2. Embedding Service (`services/embedding_service.py`)

The embedding service is responsible for generating embeddings for text content. It uses a registry of embedding providers (e.g., OpenAI, Mistral) to generate the embeddings.

### 4.3. Export Service (`services/export_service.py`)

The export service provides methods to export data in different formats, such as CSV, GEXF, and corpus.

## 5. Celery Tasks

The application uses Celery for handling asynchronous tasks. The main tasks are:

- **`crawling_task.py`**: Contains the tasks for crawling web pages.
- **`readable_working_task.py`**: Contains the tasks for readable content extraction using Trafilatura with Archive.org fallbacks.
- **`embedding_tasks.py`**: Contains the tasks for generating embeddings.
- **`export_task.py`**: Contains the tasks for exporting data.

## 6. Main Pipelines

### 6.1. Crawling Pipeline

The crawling pipeline is the main pipeline of the application. It is responsible for crawling web pages, extracting content, and saving it to the database.

The pipeline is triggered by a request to the `/lands/{land_id}/crawl` endpoint. This creates a crawl job that is dispatched to a Celery worker.

The main steps of the pipeline are:

1.  **Prepare crawl**: Fetches the expressions to crawl for a given land.
2.  **Crawl expressions**: Crawls the expressions in batches.
3.  **Update job status**: Updates the status of the crawl job with the results of the crawl.

### 6.2. Readable Pipeline

The readable pipeline is responsible for extracting clean, readable content from crawled web pages using Mercury-like functionality.

The pipeline is triggered by a request to the `/lands/{land_id}/readable` endpoint. This creates a readable job that is dispatched to a Celery worker.

The main steps of the pipeline are:

1.  **Content extraction**: Uses Trafilatura to extract clean content from HTML.
2.  **Archive.org fallback**: If primary extraction fails, attempts to fetch content from Internet Archive.
3.  **Content processing**: Extracts title, description, language, and readable text.
4.  **Database update**: Updates expressions with the extracted readable content.

### 6.3. Embedding Pipeline

The embedding pipeline is responsible for generating embeddings for the text content of the expressions.

The pipeline is triggered by a request to the `/lands/{land_id}/embeddings/generate` endpoint. This creates an embedding job that is dispatched to a Celery worker.

The main steps of the pipeline are:

1.  **Extract paragraphs**: Extracts the paragraphs from the readable content of the expressions.
2.  **Generate embeddings**: Generates the embeddings for the paragraphs in batches using the selected embedding provider.
3.  **Save embeddings**: Saves the embeddings to the database.