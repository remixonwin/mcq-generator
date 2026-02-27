"""
Task queue abstraction.

This module provides a simple abstraction `enqueue_generate` that runs
generation in a background thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)

# Thread pool for background jobs
_job_futures: dict[str, Future] = {}

# Use a persistent thread pool for background jobs
_executor = ThreadPoolExecutor(max_workers=4)


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
    # Submit to persistent executor
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

    def _run() -> dict[str, Any]:
        start = perf_counter()
        result = None
        try:
            # Import inside to avoid issues
            import sys

            # Get the project root path relative to this file
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            src_path = os.path.join(project_root, "src")
            sys.path.insert(0, src_path)
            from mcq_generator.api.tasks import run_generation_job_simple

            # Run with a fresh event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    run_generation_job_simple(
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
            finally:
                loop.close()

            result = {"success": True}

            # Record metrics
            try:
                from mcq_generator.metrics import inc_job_completed, observe_job_duration

                duration = perf_counter() - start
                inc_job_completed(dataset)
                observe_job_duration(dataset, duration)
            except Exception:
                pass

        except Exception as e:
            logger.exception(f"Background task failed: {e}")

            # Record failure metrics
            try:
                from mcq_generator.metrics import inc_job_failed

                inc_job_failed(dataset)
            except Exception:
                pass

            raise

        return result

    # Submit to persistent executor
    future = _executor.submit(_run)
    return future
