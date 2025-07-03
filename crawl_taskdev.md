# Crawl Pipeline Documentation

## Complete Crawl Workflow

```mermaid
graph TD
    A[POST /api/v1/lands/{land_id}/crawl] --> B[lands.py]
    B --> C[crawling_service.py]
    C --> D[Create CrawlJob record]
    C --> E[Dispatch Celery task]
    E --> F[crawling_task.py]
    F --> G[crawler_engine.py]
    G --> H[Process URLs]
    H --> I[Extract content]
    I --> J[Save expressions]
    J --> K[Process media]
    K --> L[Extract links]
    L --> M[Update crawl progress]
    M --> N[WebSocket updates]
```

## Key Components

### 1. Endpoint (lands.py)
- **Path**: `/api/v1/lands/{land_id}/crawl`
- **Method**: POST
- **Parameters**:
  - `land_id`: ID of land to crawl
  - `limit`: Max URLs to process
  - `depth`: Crawl depth
- **Authentication**: JWT required
- **Flow**:
  1. Verify land exists and user has permission
  2. Call `start_crawl_for_land()` service

### 2. Crawling Service (crawling_service.py)
- **Function**: `start_crawl_for_land()`
- **Responsibilities**:
  - Validate crawl parameters
  - Create CrawlJob record
  - Dispatch Celery task
  - Handle WebSocket channel setup
- **Key Variables**:
  - `db_job`: Created job object
  - `ws_channel`: "crawl_progress_{job_id}"
  - `task`: Celery task reference

### 3. Celery Task (crawling_task.py)
- **Task**: `crawl_land_task`
- **Parameters**:
  - `job_id`: ID of crawl job
  - `ws_channel`: WebSocket channel for progress
- **Flow**:
  1. Update job status to "STARTED"
  2. Call `crawl_land()` from crawler_engine
  3. Handle success/error states
  4. Send WebSocket updates

### 4. Crawler Engine (crawler_engine.py)
- **Main Function**: `crawl_land()`
- **Key Functions**:
  - `get_expressions_to_crawl()`: Get seed URLs
  - `process_url()`: Fetch and process single URL
  - `extract_metadata()`: Get title/description
  - `save_expression()`: Store in database
  - `process_media()`: Handle images/files
  - `extract_links()`: Find new URLs to crawl
- **Key Variables**:
  - `visited_urls`: Set of processed URLs
  - `queue`: URLs to process (BFS)
  - `current_depth`: Current crawl depth

### 5. WebSocket Manager (websocket.py)
- **Class**: `WebSocketManager`
- **Methods**:
  - `connect()`: Add client to channel
  - `disconnect()`: Remove client from channel
  - `broadcast()`: Send message to all clients in channel
- **Channel Format**: "crawl_progress_{job_id}"

## Critical Attention Points

### 1. Concurrency Issues
- **Risk**: Race conditions when multiple workers access same URL
- **Test**: Run concurrent crawl jobs on same land
- **Solution**: Implement distributed locking (Redis)

### 2. Memory Management
- **Risk**: Memory bloat with large crawls
- **Test**: Crawl with 10,000+ URLs
- **Solution**: Implement batch processing

### 3. Error Handling
- **Critical Points**:
  - Network timeouts
  - Malformed HTML
  - Database connection loss
- **Test**: Simulate network failures during crawl

### 4. WebSocket Reliability
- **Risk**: Client disconnections during long crawls
- **Test**: Disconnect/reconnect during crawl
- **Solution**: Implement reconnect logic

### 5. Performance Bottlenecks
- **Potential Issues**:
  - Database write contention
  - CPU-intensive processing
  - Network latency
- **Monitoring**: Track:
  - URLs processed/second
  - DB write latency
  - Memory usage

## Testing Strategy

### Unit Tests
1. Service layer parameter validation
2. WebSocket connection management
3. URL processing edge cases

### Integration Tests
1. Full crawl workflow with mock HTTP server
2. Database transaction rollback tests
3. Celery task error handling

### Load Testing
1. 100 concurrent crawl jobs
2. Crawl with 50,000 URLs
3. High-depth crawls (depth=10)

### Security Tests
1. SQL injection in crawl parameters
2. XSS in extracted content
3. Authentication bypass attempts
