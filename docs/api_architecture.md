# MCQ Generator API Architecture

## Overview

This document describes the unified API architecture for the MCQ Generator project, following industry best practices and RESTful design principles.

## Architecture Principles

1. **Separation of Concerns**: Clear separation between HTTP layer, business logic, and data access
2. **DRY (Don't Repeat Yourself)**: Shared schemas, services, and utilities
3. **Dependency Injection**: FastAPI's dependency injection for testability and modularity
4. **Layered Architecture**: Routers → Services → Repositories (StateManager)
5. **Backward Compatibility**: Old endpoints preserved via compatibility layer

## Directory Structure

```
src/mcq_generator/api/
├── __init__.py           # Package exports
├── main.py               # FastAPI app factory
├── dependencies.py       # Shared dependencies (auth, DB connections)
├── schemas.py            # Pydantic models (request/response)
├── client.py             # HTTP client for CLI integration
├── tasks.py              # Background task runner
├── routers/              # HTTP route handlers
│   ├── __init__.py
│   ├── jobs.py           # Job CRUD operations
│   ├── datasets.py       # Dataset search
│   ├── exports.py        # Export operations
│   ├── health.py         # Health checks
│   └── metrics.py        # Prometheus metrics
└── services/             # Business logic layer
    ├── __init__.py
    ├── job_service.py    # Job operations
    ├── dataset_service.py # Dataset operations
    └── export_service.py # Export operations
```

## API Endpoints

### Jobs (`/api/v1/jobs`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List all jobs with pagination |
| POST | `/jobs` | Create a new generation job |
| GET | `/jobs/{job_id}` | Get job details |
| POST | `/jobs/{job_id}/resume` | Resume a paused job |
| PATCH | `/jobs/{job_id}/status` | Update job status |
| DELETE | `/jobs/{job_id}` | Delete a job |
| GET | `/jobs/{job_id}/mcqs` | Get MCQs for a job |

### Datasets (`/api/v1/datasets`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/datasets/search` | Search HuggingFace datasets |

### Exports (`/api/v1/exports`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/exports/{job_id}` | Export MCQs in specified format |
| GET | `/exports/{job_id}/download` | Download exported file |

### Health & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Detailed health check |
| GET | `/healthz` | Kubernetes-compatible health check |
| GET | `/ready` | Readiness probe |
| GET | `/metrics` | Prometheus metrics |

## Key Features

### 1. Proper Validation
- All requests validated with Pydantic models
- Type hints throughout
- Automatic OpenAPI documentation at `/docs`

### 2. Error Handling
- Consistent error responses
- Proper HTTP status codes
- Exception handlers for common errors

### 3. Security
- API key authentication (optional)
- Dependencies for access control
- CORS configuration

### 4. Documentation
- OpenAPI/Swagger docs auto-generated
- Inline docstrings
- Type annotations

### 5. Testing Support
- Dependency injection for easy mocking
- Service layer for unit testing
- Client library for integration testing

## Usage Examples

### Start the API Server

```bash
# Using uvicorn directly
uvicorn mcq_generator.asgi:app --reload

# Or with custom settings
uvicorn mcq_generator.asgi:app --host 0.0.0.0 --port 8000
```

### Create a Job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "microsoft/orca-agentinstruct-1M-v1",
    "questions": 100,
    "checkpoint": 10
  }'
```

### List Jobs

```bash
curl http://localhost:8000/api/v1/jobs?status=running&limit=10
```

### Search Datasets

```bash
curl "http://localhost:8000/api/v1/datasets/search?q=sentiment&limit=10"
```

### Export MCQs

```bash
curl -X POST http://localhost:8000/api/v1/exports/job_123 \
  -H "Content-Type: application/json" \
  -d '{"format": "json"}'
```

## CLI Integration

The CLI can use the API client instead of direct database access:

```python
from mcq_generator.api.client import MCQApiClient

with MCQApiClient() as client:
    # List jobs
    jobs = client.list_jobs(status="running")
    
    # Create job
    job = client.create_job(
        dataset="microsoft/orca-agentinstruct-1M-v1",
        questions=100
    )
    
    # Get MCQs
    mcqs = client.get_job_mcqs(job["job_id"])
```

## Environment Variables

- `MCQ_API_URL` - API base URL (default: http://localhost:8000)
- `MCQ_DB_PATH` - DuckDB database path
- `API_KEY` - Optional API key for authentication
- `CELERY_BROKER_URL` - Optional Celery broker for distributed tasks

## Migration from Old API

The old `api.py` file is deprecated but preserved for backward compatibility. New development should use the structured API package.

### Compatibility Notes

- Old endpoints still work but may be removed in future versions
- New endpoints use `/api/v1/` prefix
- Service layer can be used independently of HTTP layer
- Direct StateManager access still supported but discouraged

## Future Improvements

1. **Authentication**: JWT/OAuth2 integration
2. **Rate Limiting**: Request throttling
3. **WebSockets**: Real-time job progress updates
4. **Caching**: Redis for response caching
5. **API Versioning**: Support for multiple API versions
