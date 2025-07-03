# Crawl Endpoint Implementation Task

## Objective
Implement a crawl endpoint that mirrors the functionality of the old crawler in `.crawlerOLD_APP/core.py` while integrating with the new FastAPI architecture.

## Key Requirements
1. **Endpoint Specification**:
   - Path: `/api/v1/lands/{land_id}/crawl`
   - Method: POST
   - Parameters:
     - `limit`: Optional[int] - Max number of URLs to process
     - `depth`: Optional[int] - Crawl depth
     - `http_status`: Optional[str] - Filter by HTTP status

2. **Core Functionality**:
   - Must replicate the exact crawling behavior from `crawl_land()` in old core.py
   - Should use Celery for async task execution
   - Must track job progress via WebSocket

3. **Implementation Components**:
   - New endpoint in `lands.py`
   - Celery task in `crawling_task.py`
   - Service layer in `crawling_service.py`
   - WebSocket handler for progress updates

## Technical Considerations
- Maintain compatibility with existing database models
- Implement proper error handling
- Include comprehensive logging
- Add unit and integration tests

## Dependencies
- Requires completed models and schemas
- Needs Celery worker setup
- Depends on WebSocket infrastructure

## Testing Plan
1. Unit tests for individual components
2. Integration test for full crawl workflow
3. Performance testing for large crawls
4. Error scenario testing

## Estimated Time
- Development: 3 days
- Testing: 1 day
- Documentation: 0.5 day

## Risk Analysis
- Potential race conditions in job tracking
- Memory usage with large crawls
- Timeout handling for slow responses

## Acceptance Criteria
- Passes all test cases
- Matches old crawler output exactly
- Handles all error cases gracefully
- Documentation complete

## Tasks to finalize
- [ ] Fix Pylance errors in `MyWebIntelligenceAPI/app/services/crawling_service.py`.
- [ ] Fix Pylance errors in `MyWebIntelligenceAPI/app/tasks/crawling_task.py`.
- [ ] Fix Pylance errors in `MyWebIntelligenceAPI/app/core/crawler_engine.py`.
- [ ] Fix Pylance errors in `MyWebIntelligenceAPI/app/crud/__init__.py`.
- [ ] Fix Pylance errors in `MyWebIntelligenceAPI/app/crud/crud_job.py`.
