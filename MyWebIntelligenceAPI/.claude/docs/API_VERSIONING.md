# API Versioning Guide - MyWebIntelligence

## Overview

MyWebIntelligence API uses semantic versioning to manage breaking changes and maintain backward compatibility. This document provides comprehensive information about our versioning strategy, migration paths, and best practices.

## Version Strategy

### Supported Versions

- **v1 (1.0.0)** - Stable ✅
  - Release Date: June 1, 2025
  - Status: Stable and supported
  - End of Support: January 4, 2026
  
- **v2 (2.0.0)** - Beta 🚧
  - Release Date: July 4, 2025
  - Status: Beta (recommended for new projects)
  - Stable Release: September 1, 2025

### Version Detection

The API automatically detects the requested version using multiple methods:

1. **Header-based** (Recommended)
   ```http
   API-Version: v2
   Accept-Version: v2
   X-API-Version: v2
   ```

2. **URL Path-based**
   ```
   GET /api/v1/lands  # v1
   GET /api/v2/lands  # v2
   ```

3. **Query Parameter**
   ```
   GET /api/lands?version=v2
   ```

## Breaking Changes in v2

### 1. Export Endpoints → Async Job Pattern

**v1 Behavior:**
```http
POST /api/v1/export/csv
→ Direct CSV file response
```

**v2 Behavior:**
```http
POST /api/v2/export/csv
→ {"job_id": "uuid", "tracking_url": "/api/v2/export/jobs/uuid"}

GET /api/v2/export/jobs/{job_id}
→ Job status and progress

GET /api/v2/export/download/{job_id}
→ Download completed file
```

**Migration Steps:**
1. Update export calls to handle job_id response
2. Implement job polling for completion
3. Download files using the job_id endpoint

### 2. Mandatory Pagination

**v1 Behavior:**
```http
GET /api/v1/lands
→ All lands (no pagination)
```

**v2 Behavior:**
```http
GET /api/v2/lands?page=1&page_size=20
→ Paginated response with metadata
```

**Response Format:**
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8,
  "has_next": true,
  "has_previous": false
}
```

### 3. Standardized Error Responses

**v1 Error Format:**
```json
{
  "detail": "Land not found"
}
```

**v2 Error Format:**
```json
{
  "error_code": "LAND_NOT_FOUND",
  "message": "Land with ID 123 not found",
  "details": {"land_id": 123},
  "suggestion": "Check the land ID and ensure you have access"
}
```

## New Features in v2

### Enhanced Export Formats

- **JSON-LD**: Semantic web compatibility
- **Parquet**: Optimized for big data analytics
- **Enhanced CSV**: With metadata and analytics
- **Community GEXF**: Network analysis with community detection

### Advanced Filtering

```http
GET /api/v2/lands?name_filter=research&status_filter=active&page=1&page_size=20
```

### Bulk Operations

```http
POST /api/v2/lands/batch
POST /api/v2/export/batch
```

### Enhanced Job Tracking

- Real-time progress updates
- Detailed error reporting
- Estimated completion times
- Resource usage metrics

## Migration Guide

### Client Code Migration

#### 1. Update Export Handling

**Before (v1):**
```javascript
// Direct export
const response = await fetch('/api/v1/export/csv', {
  method: 'POST',
  body: JSON.stringify({land_id: 123, export_type: 'pagecsv'})
});
const blob = await response.blob();
// Use blob directly
```

**After (v2):**
```javascript
// Async export with job tracking
const jobResponse = await fetch('/api/v2/export/csv', {
  method: 'POST',
  headers: {'API-Version': 'v2'},
  body: JSON.stringify({land_id: 123, export_type: 'pagecsv'})
});
const {job_id} = await jobResponse.json();

// Poll for completion
const pollJob = async () => {
  const statusResponse = await fetch(`/api/v2/export/jobs/${job_id}`, {
    headers: {'API-Version': 'v2'}
  });
  const status = await statusResponse.json();
  
  if (status.status === 'completed') {
    window.location.href = `/api/v2/export/download/${job_id}`;
  } else if (status.status === 'failed') {
    console.error('Export failed:', status.error);
  } else {
    setTimeout(pollJob, 2000); // Poll every 2 seconds
  }
};
pollJob();
```

#### 2. Add Pagination to Listing Calls

**Before (v1):**
```javascript
const lands = await fetch('/api/v1/lands').then(r => r.json());
```

**After (v2):**
```javascript
const getLands = async (page = 1, pageSize = 20) => {
  const response = await fetch(
    `/api/v2/lands?page=${page}&page_size=${pageSize}`,
    {headers: {'API-Version': 'v2'}}
  );
  return response.json();
};

const {items: lands, total, has_next} = await getLands();
```

#### 3. Update Error Handling

**Before (v1):**
```javascript
try {
  const response = await fetch('/api/v1/lands/123');
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
} catch (error) {
  console.error(error.message);
}
```

**After (v2):**
```javascript
try {
  const response = await fetch('/api/v2/lands/123', {
    headers: {'API-Version': 'v2'}
  });
  if (!response.ok) {
    const error = await response.json();
    console.error(`${error.error_code}: ${error.message}`);
    if (error.suggestion) {
      console.info('Suggestion:', error.suggestion);
    }
  }
} catch (error) {
  console.error('Network error:', error);
}
```

### Server-Side Migration

#### Python/Requests Example

```python
# v2 Client with automatic version handling
import requests

class MyWebIntelligenceClient:
    def __init__(self, base_url, api_version='v2'):
        self.base_url = base_url
        self.headers = {'API-Version': api_version}
    
    def list_lands(self, page=1, page_size=20):
        response = requests.get(
            f"{self.base_url}/api/v2/lands",
            headers=self.headers,
            params={'page': page, 'page_size': page_size}
        )
        return response.json()
    
    def export_csv_async(self, land_id, export_type):
        # Start export job
        response = requests.post(
            f"{self.base_url}/api/v2/export/csv",
            headers=self.headers,
            json={'land_id': land_id, 'export_type': export_type}
        )
        job = response.json()
        
        # Poll for completion
        while True:
            status_response = requests.get(
                f"{self.base_url}/api/v2/export/jobs/{job['job_id']}",
                headers=self.headers
            )
            status = status_response.json()
            
            if status['status'] == 'completed':
                return status['result']['file_url']
            elif status['status'] == 'failed':
                raise Exception(f"Export failed: {status['error']}")
            
            time.sleep(2)  # Wait 2 seconds before next poll
```

## Compatibility & Deprecation

### Deprecation Timeline

1. **July 4, 2025**: v2 Beta release
2. **September 1, 2025**: v2 Stable release
3. **December 1, 2025**: v1 deprecated (warnings added)
4. **January 4, 2026**: v1 sunset (no longer supported)

### Compatibility Mode

During the transition period, the API provides compatibility warnings:

```http
GET /api/v1/lands
Response Headers:
API-Deprecation-Warning: API version v1 is deprecated and will be discontinued in 90 days. Migration guide: /docs/migration/v1-to-v2
API-Version: v1
API-Supported-Versions: v1,v2
```

## Testing Your Migration

### 1. Gradual Migration

Test v2 endpoints gradually:

```javascript
// Feature flag for v2 testing
const useV2 = process.env.USE_API_V2 === 'true';
const apiVersion = useV2 ? 'v2' : 'v1';
const headers = {'API-Version': apiVersion};
```

### 2. A/B Testing

Run parallel requests to validate responses:

```javascript
const testV2Migration = async () => {
  const [v1Response, v2Response] = await Promise.all([
    fetch('/api/v1/lands', {headers: {'API-Version': 'v1'}}),
    fetch('/api/v2/lands?page=1&page_size=1000', {headers: {'API-Version': 'v2'}})
  ]);
  
  const v1Data = await v1Response.json();
  const v2Data = await v2Response.json();
  
  console.log('v1 count:', v1Data.length);
  console.log('v2 count:', v2Data.total);
  // Compare for consistency
};
```

### 3. Migration Validation Endpoint

Use the dedicated endpoint to check migration status:

```http
GET /api/v2/migration-status
→ Current migration progress and recommendations
```

## Best Practices

### 1. Always Specify Version

**✅ Good:**
```http
GET /api/v2/lands
Headers: API-Version: v2
```

**❌ Avoid:**
```http
GET /api/lands  # Uses default version
```

### 2. Handle Version Errors Gracefully

```javascript
const makeApiCall = async (endpoint, options = {}) => {
  try {
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        'API-Version': 'v2',
        ...options.headers
      }
    });
    
    if (response.status === 400) {
      const error = await response.json();
      if (error.error === 'unsupported_api_version') {
        // Fallback to v1 or show upgrade message
        console.warn('v2 not supported, falling back to v1');
        return makeApiCall(endpoint.replace('/v2/', '/v1/'), {
          ...options,
          headers: {...options.headers, 'API-Version': 'v1'}
        });
      }
    }
    
    return response;
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
};
```

### 3. Monitor API Version Usage

Track which versions your application uses:

```javascript
// Add version tracking to your analytics
const trackApiCall = (endpoint, version, status) => {
  analytics.track('api_call', {
    endpoint,
    api_version: version,
    status_code: status
  });
};
```

## Support and Resources

### Documentation
- [v1 API Reference](/docs/api/v1)
- [v2 API Reference](/docs/api/v2)
- [Migration Examples](/docs/examples/migration)

### Tools
- [Migration Testing Script](/tools/test-migration.js)
- [Version Compatibility Checker](/tools/check-compatibility.py)
- [Automated Migration Tool](/tools/migrate-client.py)

### Support Channels
- Email: support@mywebintelligence.com
- Documentation: [API Docs](https://docs.mywebintelligence.com)
- GitHub Issues: [Report Migration Issues](https://github.com/mywebintelligence/api/issues)

### Migration Assistance

The MyWebIntelligence team provides free migration assistance:

1. **Code Review**: We'll review your client code and suggest improvements
2. **Testing Support**: Help with testing your migration in our staging environment
3. **Custom Scripts**: We can provide custom migration scripts for complex use cases

Contact us at migration-support@mywebintelligence.com to schedule assistance.

---

## Changelog

- **v2.0.0 (2025-07-04)**: Beta release with breaking changes
- **v1.0.0 (2025-06-01)**: Initial stable release