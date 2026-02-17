"""
Service layer for job-related operations.

This layer contains the business logic for job management,
separating it from the HTTP layer (routers) and data layer (StateManager).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ...api.schemas import (
    CreateJobRequest,
    JobProgress,
    JobStatistics,
    StatusEnum,
)
from ...state_manager import StateManager

logger = logging.getLogger(__name__)


class JobService:
    """Service for job-related operations."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager

    def create_job(self, request: CreateJobRequest) -> dict[str, Any]:
        """
        Create a new generation job.

        Returns the created job details.
        """
        import uuid

        job_id = f"api_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        self.state.create_job(
            job_id=job_id,
            dataset_name=request.dataset,
            target_questions=request.questions,
            dataset_split=request.dataset_split,
            config={
                "checkpoint_interval": request.checkpoint,
                "cache_dir": request.cache_dir,
                "provider_url": request.provider_url,
                "output": request.output,
                "text_column": request.text_column,
            },
        )

        logger.info(f"Created job {job_id} for dataset {request.dataset}")

        return {
            "job_id": job_id,
            "status": "pending",
            "dataset": request.dataset,
            "target_questions": request.questions,
        }

    def get_job(self, job_id: str) -> JobProgress:
        """Get job progress by ID."""
        progress = self.state.get_job_progress(job_id)
        return JobProgress(**progress)

    def list_jobs(
        self,
        status: StatusEnum | None = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        List jobs with optional filtering and pagination.

        Returns a paginated list of jobs.
        """
        status_filter = status.value if status else None
        jobs = self.state.list_jobs(status=status_filter)

        total = len(jobs)
        paginated_jobs = jobs[offset : offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [JobProgress(**job) for job in paginated_jobs],
        }

    def update_job_status(
        self,
        job_id: str,
        status: StatusEnum,
        reason: str | None = None,
    ) -> JobProgress:
        """Update job status."""
        # Verify job exists
        job = self.state.get_job_progress(job_id)

        # Update status
        self.state.update_job_status(job_id, status.value)

        if reason:
            logger.info(f"Job {job_id} status changed to {status.value}: {reason}")
        else:
            logger.info(f"Job {job_id} status changed to {status.value}")

        # Return updated job
        return self.get_job(job_id)

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all its data."""
        return self.state.delete_job(job_id)

    def get_statistics(self) -> JobStatistics:
        """Get overall job statistics."""
        stats = self.state.get_statistics()

        # Calculate failed and pending from total
        completed = stats.get("completed_jobs", 0)
        running = stats.get("running_jobs", 0)
        paused = stats.get("paused_jobs", 0)
        total = stats.get("total_jobs", 0)
        total_mcqs = stats.get("total_mcqs", 0)

        # Failed and pending are derived
        known_status = completed + running + paused
        failed = max(0, total - known_status)  # Approximate
        pending = 0  # We don't track pending separately in current schema

        return JobStatistics(
            total_jobs=total,
            completed_jobs=completed,
            running_jobs=running,
            paused_jobs=paused,
            failed_jobs=failed,
            pending_jobs=pending,
            total_mcqs=total_mcqs,
        )

    def get_stale_jobs(self, stale_minutes: int = 5) -> list[JobProgress]:
        """Get stale jobs (running but not updated recently)."""
        stale = self.state.get_stale_jobs(stale_minutes=stale_minutes)
        return [JobProgress(**job) for job in stale]

    def fix_stale_jobs(self, stale_minutes: int = 5, mark_as: str = "paused") -> int:
        """Mark stale jobs as paused or failed."""
        return self.state.fix_stale_jobs(stale_minutes=stale_minutes, mark_as=mark_as)

    def get_job_mcqs(self, job_id: str) -> list[dict[str, Any]]:
        """Get all MCQs for a job."""
        return self.state.get_mcqs(job_id)
