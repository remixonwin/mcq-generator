"""
Job management router.

Handles all job-related endpoints including creation, status updates,
resuming, and management operations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ... import tasks
from ...metrics import api_requests, jobs_created, jobs_enqueued
from ...state_manager import StateManager
from ..dependencies import get_api_key, get_state_manager
from ..schemas import (
    CreateJobRequest,
    CreateJobResponse,
    ErrorResponse,
    JobListResponse,
    JobProgress,
    ResumeJobResponse,
    StatusEnum,
    UpdateJobStatusRequest,
)
from ..services import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs")


@router.get(
    "",
    response_model=JobListResponse,
    summary="List all jobs",
    description="Get a paginated list of all MCQ generation jobs.",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
def list_jobs(
    status: StatusEnum | None = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(10, ge=1, le=100, description="Page size"),
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> JobListResponse:
    """List all jobs with optional filtering."""
    api_requests.labels(path="/api/v1/jobs").inc()

    service = JobService(sm)
    result = service.list_jobs(status=status, offset=offset, limit=limit)

    return JobListResponse(**result)


@router.post(
    "",
    response_model=CreateJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new job",
    description="Create a new MCQ generation job and start processing in the background.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
def create_job(
    request: CreateJobRequest,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> CreateJobResponse:
    """Create a new generation job."""
    api_requests.labels(path="/api/v1/jobs").inc()

    service = JobService(sm)

    # Create the job
    job = service.create_job(request)
    job_id = job["job_id"]

    # Update status to running
    sm.update_job_status(job_id, "running")

    # Enqueue the generation task
    target = request.questions if request.questions > 0 else 0
    output = request.output or f".mcq_exports/{job_id}.json"

    jobs_created.inc()
    jobs_enqueued.inc()

    tasks.enqueue_generate(
        job_id=job_id,
        dataset=request.dataset,
        target=target,
        output=output,
        checkpoint_interval=request.checkpoint,
        cache_dir=request.cache_dir,
        provider_url=request.provider_url,
    )

    logger.info(f"Created and enqueued job {job_id}")

    return CreateJobResponse(
        job_id=job_id,
        message="Job created and scheduled",
        status="running",
    )


@router.get(
    "/{job_id}",
    response_model=JobProgress,
    summary="Get job status",
    description="Get detailed progress information for a specific job.",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def get_job(
    job_id: str,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> JobProgress:
    """Get job progress by ID."""
    api_requests.labels(path="/api/v1/jobs/{job_id}").inc()

    service = JobService(sm)

    try:
        return service.get_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/{job_id}/resume",
    response_model=ResumeJobResponse,
    summary="Resume a job",
    description="Resume a paused or running job from its last checkpoint.",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def resume_job(
    job_id: str,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> ResumeJobResponse:
    """Resume an existing job."""
    api_requests.labels(path="/api/v1/jobs/{job_id}/resume").inc()

    # Get job details
    try:
        progress = sm.get_job_progress(job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    # Enqueue resume task
    jobs_enqueued.inc()
    tasks.enqueue_generate(
        job_id=job_id,
        dataset=progress["dataset_name"],
        target=progress["target_questions"] or 999999999,
        output=f".mcq_exports/{job_id}.json",
        checkpoint_interval=10,
        cache_dir=".mcq_cache",
        provider_url=None,
    )

    logger.info(f"Resumed job {job_id}")

    return ResumeJobResponse(
        job_id=job_id,
        message="Resume scheduled",
        status="running",
    )


@router.patch(
    "/{job_id}/status",
    response_model=JobProgress,
    summary="Update job status",
    description="Update the status of a job (pause, cancel, etc.).",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def update_job_status(
    job_id: str,
    request: UpdateJobStatusRequest,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> JobProgress:
    """Update job status."""
    service = JobService(sm)

    try:
        return service.get_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job",
    description="Delete a job and all its associated data (MCQs, checkpoints).",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def delete_job(
    job_id: str,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> None:
    """Delete a job."""
    service = JobService(sm)

    success = service.delete_job(job_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or could not be deleted",
        )

    logger.info(f"Deleted job {job_id}")


@router.get(
    "/{job_id}/mcqs",
    summary="Get job MCQs",
    description="Get all generated MCQs for a job.",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
def get_job_mcqs(
    job_id: str,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
):
    """Get all MCQs for a job."""
    from ..services import ExportService

    service = ExportService(sm)

    # Verify job exists
    jobs = sm.list_jobs()
    if not any(job["job_id"] == job_id for job in jobs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return service.get_job_mcqs(job_id)
