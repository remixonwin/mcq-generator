"""
Main FastAPI application factory.

This module creates and configures the FastAPI application instance,
following the application factory pattern for flexibility in testing
and different deployment scenarios.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .routers import (
    audit_logs_router,
    datasets_router,
    exports_router,
    health_router,
    jobs_router,
    metrics_router,
)
from .. import tasks
from ..dataset_search import search_datasets
from ..state_manager import StateManager
from ..metrics import jobs_created, jobs_enqueued, api_requests
from fastapi import Body
from datetime import datetime, timezone
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application factory - creates and configures the FastAPI app.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="MCQ Generator API",
        description="""
        High-Performance MCQ Generator API.
        
        This API provides endpoints for:
        - Dataset search on HuggingFace Hub
        - Job creation and management
        - MCQ generation with pause/resume support
        - Export in multiple formats (JSON, CSV, Markdown, PDF)
        - Real-time metrics and monitoring
        """,
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "MCQ Generator Team",
            "url": "https://github.com/example/mcq-generator",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # Add middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Configure CORS
    cors_origins = [
        "http://localhost:43211",  # Frontend Dev
        "http://127.0.0.1:43211",
        "http://localhost:37241",  # Current Flutter Web Dev Port
        "http://localhost:8000",   # Backend itself
        "http://localhost:43229",  # Flutter Web Dev Port (New)
        "http://127.0.0.1:43229",
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(metrics_router, tags=["Metrics"])
    app.include_router(datasets_router, prefix="/api/v1", tags=["Datasets"])
    app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])
    app.include_router(exports_router, prefix="/api/v1", tags=["Exports"])
    app.include_router(audit_logs_router, prefix="/api/v1", tags=["Audit Logs"])

    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Bad Request", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.exception(f"Unhandled exception during {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error", 
                "message": str(exc) if app.debug else "An unexpected error occurred",
                "path": request.url.path
            },
        )

    return app


# Global app instance for ASGI servers
app = create_app()


# Compatibility: expose legacy top-level endpoints for older clients/tests
@app.get("/search")
def legacy_search(q: str, limit: int = 10, sort: str = "downloads", offset: int = 0):
    api_requests.labels(path="/search").inc()
    results = search_datasets(query=q, limit=limit, sort=sort, offset=offset)
    return {"results": results}


@app.post("/generate", status_code=202)
def legacy_generate(body: dict = Body(...)):
    # Minimal compatibility wrapper to schedule a job. Accepts limited fields.
    dataset = body.get("dataset") or body.get("name")
    questions = int(body.get("questions", 0))

    job_id = f"api_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    try:
        sm = StateManager()
        try:
            sm.create_job(job_id=job_id, dataset_name=dataset, target_questions=questions)
            sm.update_job_status(job_id, "running")
        finally:
            sm.close()
    except Exception:
        # best-effort in-memory fallback: create a minimal in-memory job record
        try:
            import mcq_generator.inmem as inmem_mod

            inmem_mod._inmem_jobs[job_id] = {
                "job_id": job_id,
                "dataset_name": dataset,
                "status": "running",
                "target_questions": questions or 0,
                "generated_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

    jobs_created.inc()
    jobs_enqueued.inc()
    tasks.enqueue_generate(
        job_id=job_id,
        dataset=dataset,
        target=questions or 999999999,
        output=f".mcq_exports/{job_id}.json",
        checkpoint_interval=int(body.get("checkpoint", 10)),
        cache_dir=body.get("cache_dir", ".mcq_cache"),
        provider_url=body.get("provider_url"),
        text_column=body.get("text_column", "text"),
    )

    return {"job_id": job_id, "message": "Job created and scheduled"}


@app.get("/jobs")
def legacy_list_jobs():
    api_requests.labels(path="/jobs").inc()
    try:
        sm = StateManager()
        try:
            jobs = sm.list_jobs()
        finally:
            sm.close()
    except Exception:
        jobs = []

    # Merge in-memory jobs (avoid duplicates)
    try:
        import mcq_generator.inmem as inmem_mod

        for jid, j in inmem_mod._inmem_jobs.items():
            if not any(existing["job_id"] == jid for existing in jobs):
                jobs.insert(0, j)
    except Exception:
        # ignore if import fails
        pass
    return {"jobs": jobs}


@app.get("/jobs/{job_id}")
def legacy_job_status(job_id: str):
    api_requests.labels(path="/jobs/{job_id}").inc()
    try:
        sm = StateManager()
        try:
            progress = sm.get_job_progress(job_id)
            return progress
        finally:
            sm.close()
    except Exception:
        # Fall back to in-memory job record when DB is unavailable
        try:
            import mcq_generator.inmem as inmem_mod

            if job_id in inmem_mod._inmem_jobs:
                return inmem_mod._inmem_jobs[job_id]
        except Exception:
            pass
        raise


@app.get("/stats")
def legacy_stats():
    api_requests.labels(path="/stats").inc()
    try:
        sm = StateManager()
        try:
            return sm.get_statistics()
        finally:
            sm.close()
    except Exception:
        return {
            "total_jobs": 0,
            "completed_jobs": 0,
            "running_jobs": 0,
            "paused_jobs": 0,
            "total_mcqs": 0,
        }
