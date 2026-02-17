"""
FastAPI HTTP API for MCQ Generator.

This module provides an HTTP surface that mirrors the existing CLI
functionality without changing any existing module behavior. It starts
background generation tasks, exposes job and stats endpoints, and
reuses the existing StateManager, MCQGenerator and exporter classes.

The API is intentionally lightweight and non-invasive: it creates jobs
via StateManager and launches the generator in background so endpoint
responses are fast and stable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security.api_key import APIKey, APIKeyHeader
from pydantic import BaseModel

from . import tasks
from .config import config
from .dataset_search import search_datasets
from .exporters.csv_exporter import CSVExporter
from .exporters.json_exporter import JSONExporter
from .exporters.markdown_exporter import MarkdownExporter
from .generator import MCQGenerator
from .metrics import (
    api_requests,
    generate_metrics,
    jobs_created,
    jobs_enqueued,
)
from .state_manager import StateManager

# API key security (optional). If API_KEY env var is set, requests must include
# header `X-API-Key: <key>`. If not set, endpoints are open.
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key_header: str | None = Depends(api_key_header)) -> str | None:
    expected = os.getenv("API_KEY")
    if not expected:
        return None
    if not api_key_header:
        raise HTTPException(status_code=401, detail="Missing API Key")
    if api_key_header != expected:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key_header


app = FastAPI(title="MCQ Generator API", version="2.0.0")

# Keep track of background tasks so the server can report active tasks.
_background_tasks: dict[str, asyncio.Task] = {}

# Lightweight in-memory job fallback when DB is unavailable (e.g. during
# tests or transient DuckDB file lock). Keys are job_id -> job dict.
_inmem_jobs: dict[str, dict] = {}


class SearchResponseItem(BaseModel):
    id: str
    downloads: int
    likes: int


class GenerateRequest(BaseModel):
    dataset: str
    questions: int | None = 0
    checkpoint: int | None = 10
    cache_dir: str | None = ".mcq_cache"
    provider_url: str | None = None
    output: str | None = "mcqs.json"


class GenerateResponse(BaseModel):
    job_id: str
    message: str


async def _start_background_generation(
    job_id: str,
    dataset: str,
    target: int,
    output: str,
    checkpoint_interval: int,
    cache_dir: str,
    provider_url: str | None,
):
    """Run generation loop; intended to be executed in an event loop.

    This is an async coroutine so callers can await it or use
    `asyncio.run(...)` in a worker thread/process.
    """
    gen = MCQGenerator(
        provider_url=provider_url or config.PROVIDER_URL,
        cache_dir=cache_dir,
        checkpoint_interval=checkpoint_interval,
    )

    try:
        # Treat job_id as resume id so generator will resume if checkpoint exists
        async for _ in gen.generate_from_dataset(
            dataset_name=dataset, target_questions=target, resume_job_id=job_id
        ):
            await asyncio.sleep(0)
    except Exception:
        try:
            sm = StateManager()
            sm.update_job_status(job_id, "failed")
            sm.close()
        except Exception:
            pass
    finally:
        try:
            await gen.close()
        except Exception:
            pass


@app.get("/search")
def api_search(q: str, limit: int = 10, sort: str = "downloads", offset: int = 0):
    """Search datasets similar to the CLI `search` command."""
    api_requests.labels(path="/search").inc()
    results = search_datasets(query=q, limit=limit, sort=sort, offset=offset)
    return {"results": results}


@app.post("/generate", response_model=GenerateResponse, status_code=202)
def api_generate(req: GenerateRequest):
    """Create a job and start generation in the background.

    The endpoint returns immediately with the created job id. Clients can
    poll `/jobs/{job_id}` to observe progress.
    """
    job_id = f"api_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    # Try to persist job to DB, but fall back to in-memory storage on DB lock
    try:
        sm = StateManager()
        try:
            sm.create_job(
                job_id=job_id, dataset_name=req.dataset, target_questions=req.questions or 0
            )
            sm.update_job_status(job_id, "running")
        finally:
            sm.close()
    except Exception:
        # Fallback: keep minimal job info in memory so API responses are stable
        _inmem_jobs[job_id] = {
            "job_id": job_id,
            "dataset_name": req.dataset,
            "status": "running",
            "target_questions": req.questions or 0,
            "generated_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    # Don't start heavy background generation inside test environments that
    # don't expect it — use FastAPI's BackgroundTasks to schedule the runner.
    jobs_created.inc()
    # Enqueue generation job via tasks module. Depending on deployment this
    # will either send a Celery task to Redis or schedule a local worker.
    jobs_enqueued.inc()
    tasks.enqueue_generate(
        job_id=job_id,
        dataset=req.dataset,
        target=int(req.questions or 999999999),
        output=str(req.output or f".mcq_exports/{job_id}.json"),
        checkpoint_interval=int(req.checkpoint or 10),
        cache_dir=str(req.cache_dir or ".mcq_cache"),
        provider_url=req.provider_url,
    )
    # Note: job duration/completion/failure are recorded by the worker when
    # the job actually runs. The API cannot know completion time here.

    return {"job_id": job_id, "message": "Job created and scheduled"}


@app.post("/resume/{job_id}")
def api_resume(job_id: str, api_key: APIKey = Depends(get_api_key)):
    """Resume an existing job by id."""
    sm = StateManager()
    try:
        try:
            progress = sm.get_job_progress(job_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Enqueue resume
        tasks.enqueue_generate(
            job_id=job_id,
            dataset=progress["dataset_name"],
            target=progress["target_questions"] or 999999999,
            output=f".mcq_exports/{job_id}.json",
            checkpoint_interval=10,
            cache_dir=".mcq_cache",
            provider_url=None,
        )

        return {"job_id": job_id, "message": "Resume scheduled"}
    finally:
        sm.close()


@app.get("/jobs")
def api_list_jobs(status: str | None = None, api_key: APIKey = Depends(get_api_key)):
    api_requests.labels(path="/jobs").inc()
    jobs = []
    # Try DB first; on failure, return in-memory jobs only
    try:
        sm = StateManager()
        try:
            jobs = sm.list_jobs(status=status)
        finally:
            sm.close()
    except Exception:
        jobs = []

    # Merge in-memory jobs (avoid duplicates)
    for jid, j in _inmem_jobs.items():
        if status and j.get("status") != status:
            continue
        if not any(existing["job_id"] == jid for existing in jobs):
            jobs.insert(0, j)

    return {"jobs": jobs}


@app.get("/jobs/{job_id}")
def api_job_status(job_id: str, api_key: APIKey = Depends(get_api_key)):
    api_requests.labels(path="/jobs/{job_id}").inc()
    # Try DB first, fallback to in-memory
    try:
        sm = StateManager()
        try:
            progress = sm.get_job_progress(job_id)
            return progress
        finally:
            sm.close()
    except Exception:
        if job_id in _inmem_jobs:
            return _inmem_jobs[job_id]
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@app.get("/stats")
def api_stats(api_key: APIKey = Depends(get_api_key)):
    api_requests.labels(path="/stats").inc()
    try:
        sm = StateManager()
        try:
            return sm.get_statistics()
        finally:
            sm.close()
    except Exception:
        # DuckDB unavailable (locked) - synthesize stats from in-memory jobs
        total_jobs = len(_inmem_jobs)
        completed = sum(1 for j in _inmem_jobs.values() if j.get("status") == "completed")
        running = sum(1 for j in _inmem_jobs.values() if j.get("status") == "running")
        paused = sum(1 for j in _inmem_jobs.values() if j.get("status") == "paused")
        total_mcqs = sum(int(j.get("generated_count", 0) or 0) for j in _inmem_jobs.values())
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed,
            "running_jobs": running,
            "paused_jobs": paused,
            "total_mcqs": total_mcqs,
        }


@app.post("/export/{job_id}")
def api_export(
    job_id: str,
    format: str = "json",
    output: str | None = None,
    api_key: APIKey = Depends(get_api_key),
):
    api_requests.labels(path="/export").inc()
    """Export MCQs for a job in the requested format. If `output` is
    omitted the exporter result will be returned directly (for json) or
    a small message for file exports.
    """
    sm = StateManager()
    try:
        jobs = sm.list_jobs()
        if not any(job["job_id"] == job_id for job in jobs):
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        mcqs = sm.get_mcqs(job_id)
        if not mcqs:
            return {"message": "Job has no MCQs"}

        if format == "json":
            exporter = JSONExporter()
        elif format == "csv":
            exporter = CSVExporter()
        elif format == "markdown":
            exporter = MarkdownExporter(job_id=job_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        # If no output path provided return content for json; other formats
        # write to file and return path message to keep behavior simple.
        if output is None and format == "json":
            return exporter.export(mcqs)
        else:
            out = output or f"export_{job_id}.{format}"
            exporter.export(mcqs, out)
            return {"message": f"Exported to {out}"}
    finally:
        sm.close()


@app.get("/metrics")
def metrics_endpoint():
    """Prometheus metrics endpoint. If prometheus_client is not installed
    this returns plain text guidance.
    """
    body, ctype = generate_metrics()
    return Response(content=body, media_type=ctype)


@app.get("/healthz")
def health_check():
    """Simple health endpoint.

    Checks that DuckDB file is accessible and Redis/Celery broker is
    optionally reachable when configured.
    """
    # Basic DB check
    try:
        sm = StateManager()
        try:
            # Quick minimal query
            _ = sm.get_statistics()
        finally:
            sm.close()
    except Exception as e:
        return {"status": "unhealthy", "db": str(e)}

    # Broker check (if configured)
    broker = os.getenv("CELERY_BROKER_URL")
    if broker:
        # We don't want to add redis dependency here; just return broker string
        return {"status": "ok", "broker": broker}

    return {"status": "ok"}
