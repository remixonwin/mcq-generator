"""
Task queue abstraction.

This module provides a simple abstraction `enqueue_generate` that will
use Celery if configured (CELERY_BROKER_URL env var present) or fall back
to running the task in-process for development.
"""

from __future__ import annotations

import asyncio
import os
import threading

BROKER = os.getenv("CELERY_BROKER_URL")


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
):
    """Enqueue generation job.

    If Celery is configured this will send a task to the Celery worker.
    Otherwise it will start generation in a background thread (development).
    """
    if BROKER:
        # Lazy import Celery to avoid adding dependency when unused
        try:
            from .celery_app import celery_app

            celery_app.send_task(
                "mcq_generator.tasks.generate_task",
                args=[
                    job_id,
                    dataset,
                    target,
                    output,
                    checkpoint_interval,
                    cache_dir,
                    provider_url,
                    text_column,
                ],
            )
            return
        except Exception as e:
            # Fallthrough to local execution on error
            import logging

            logging.getLogger(__name__).warning(f"Celery enqueue failed: {e}")

    # Development fallback: run task in a background thread
    def _run():
        try:
            # Import here to avoid circular imports
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
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Background task failed: {e}")

    t = threading.Thread(target=_run, name=f"mcq-job-{job_id}", daemon=True)
    t.start()


def generate_task(
    job_id: str,
    dataset: str,
    target: int,
    output: str,
    checkpoint_interval: int,
    cache_dir: str,
    provider_url: str | None,
    text_column: str | None = "text",
):
    """Task entrypoint used by Celery workers."""
    from time import perf_counter

    from .api.tasks import run_generation_job
    from .metrics import inc_job_completed, inc_job_failed, observe_job_duration

    start = perf_counter()
    try:
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
        duration = perf_counter() - start
        try:
            inc_job_completed(dataset)
            observe_job_duration(dataset, duration)
            try:
                from .metrics import push_job_metrics

                push_job_metrics(job_id, dataset, duration, True)
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        try:
            inc_job_failed(dataset)
            try:
                from .metrics import push_job_metrics

                push_job_metrics(job_id, dataset, 0.0, False)
            except Exception:
                pass
        except Exception:
            pass
        raise
