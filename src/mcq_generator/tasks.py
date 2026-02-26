"""
Task queue abstraction.

This module provides a simple abstraction `enqueue_generate` that runs
generation in a background thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)

# Thread pool for background jobs
_job_futures: dict[str, Future] = {}


def enqueue_generate(
    *,
    job_id: str,
    dataset: str,
    target: int,
    output: str,
    checkpoint_interval: int,
    cache_dir: str,
    provider_url: str | None,
    text_column: str | None = "text",
) -> str:
    """Enqueue generation job.

    Runs generation in a background thread.
    Returns the job_id.
    """
    # Always use local thread execution (Celery worker has registration issues)
    future = _run_in_thread(
        job_id=job_id,
        dataset=dataset,
        target=target,
        output=output,
        checkpoint_interval=checkpoint_interval,
        cache_dir=cache_dir,
        provider_url=provider_url,
        text_column=text_column,
    )
    _job_futures[job_id] = future
    return job_id


def get_job_status(job_id: str) -> dict[str, Any]:
    """Get the status of a background job.
    
    Returns a dict with 'status' ('pending', 'running', 'completed', 'failed'),
    'error' (if failed), and 'result' (if completed).
    """
    if job_id not in _job_futures:
        return {"status": "not_found"}
    
    future = _job_futures[job_id]
    if future.running():
        return {"status": "running"}
    elif future.done():
        if future.exception() is None:
            return {"status": "completed", "result": future.result()}
        else:
            return {"status": "failed", "error": str(future.exception())}
    else:
        return {"status": "pending"}


def _run_in_thread(
    *,
    job_id: str,
    dataset: str,
    target: int,
    output: str,
    checkpoint_interval: int,
    cache_dir: str,
    provider_url: str | None,
    text_column: str | None = "text",
) -> Future:
    """Run generation in a background thread."""
    from concurrent.futures import ThreadPoolExecutor
    
    def _run() -> dict[str, Any]:
        start = perf_counter()
        result = None
        error = None
        try:
            from .api.tasks import run_generation_job

            asyncio.run(
                run_generation_job(
                    job_id=job_id,
                    dataset=dataset,
                    target=target,
                    output=output,
                    checkpoint_interval=checkpoint_interval,
                    cache_dir=cache_dir,
                    provider_url=provider_url,
                    text_column=text_column,
                )
            )
            result = {"success": True}
            
            # Record metrics
            try:
                from .metrics import inc_job_completed, observe_job_duration
                duration = perf_counter() - start
                inc_job_completed(dataset)
                observe_job_duration(dataset, duration)
                try:
                    from .metrics import push_job_metrics
                    push_job_metrics(job_id, dataset, duration, True)
                except Exception:
                    pass
            except Exception:
                pass
                
        except Exception as e:
            error = e
            logger.exception(f"Background task failed: {e}")
            
            # Record failure metrics
            try:
                from .metrics import inc_job_failed
                inc_job_failed(dataset)
                try:
                    from .metrics import push_job_metrics
                    push_job_metrics(job_id, dataset, 0.0, False)
                except Exception:
                    pass
            except Exception:
                pass
            
            raise
        
        return result

    # Use ThreadPoolExecutor to get a proper Future
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run)
    executor.shutdown(wait=False)  # Don't wait, let the thread run independently
    return future
