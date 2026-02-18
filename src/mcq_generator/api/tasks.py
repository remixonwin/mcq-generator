"""
Background task runner for the API.

Handles actual MCQ generation execution, separate from the HTTP layer.
This module provides the bridge between API job creation and actual processing.
"""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from ..config import config
from ..generator import MCQGenerator
from ..metrics import inc_job_completed, inc_job_failed, observe_job_duration
from ..state_manager import StateManager

logger = logging.getLogger(__name__)


async def run_generation_job(
    job_id: str,
    dataset: str,
    target: int,
    output: str,
    checkpoint_interval: int,
    cache_dir: str,
    provider_url: str | None,
    text_column: str | None = "text",
) -> None:
    """
    Run a generation job in the background.

    This is the actual worker function that generates MCQs.
    It should be called from background task handlers (Celery, threads, etc.)

    Args:
        job_id: Unique job identifier
        dataset: HuggingFace dataset name
        target: Target number of questions (use large number for continuous)
        output: Output file path
        checkpoint_interval: How often to save checkpoints
        cache_dir: Cache directory path
        provider_url: Optional custom provider URL
    """
    start_time = perf_counter()

    gen = MCQGenerator(
        provider_url=provider_url or config.PROVIDER_URL,
        cache_dir=cache_dir,
        checkpoint_interval=checkpoint_interval,
    )

    try:
        logger.info(f"Starting generation job {job_id} for dataset {dataset}")

        # Update job status
        try:
            sm = StateManager()
            sm.update_job_status(job_id, "running")
            sm.close()
        except Exception as e:
            logger.warning(f"Could not update job status: {e}")

        # Run generation
        async for mcq in gen.generate_from_dataset(
            dataset_name=dataset,
            target_questions=target,
            resume_job_id=job_id,
            text_column=text_column,
        ):
            # Yield control to allow other tasks
            await asyncio.sleep(0)

        # Success
        duration = perf_counter() - start_time
        observe_job_duration(dataset, duration)
        inc_job_completed(dataset)

        logger.info(f"Job {job_id} completed successfully in {duration:.2f}s")

    except asyncio.CancelledError:
        logger.info(f"Job {job_id} was cancelled")
        try:
            sm = StateManager()
            sm.update_job_status(job_id, "paused")
            sm.close()
        except Exception:
            pass
        raise

    except Exception as e:
        # Failure
        logger.exception(f"Job {job_id} failed: {e}")
        inc_job_failed(dataset)

        try:
            sm = StateManager()
            sm.update_job_status(job_id, "failed")
            sm.close()
        except Exception:
            pass
        raise

    finally:
        try:
            await gen.close()
        except Exception:
            pass
