"""
Export router.

Handles export-related endpoints for MCQs in various formats.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...metrics import api_requests
from ...state_manager import StateManager
from ..dependencies import get_api_key, get_state_manager
from ..schemas import (
    ErrorResponse,
    ExportFormat,
    ExportRequest,
    ExportResponse,
)
from ..services import ExportService

router = APIRouter(prefix="/exports")


@router.post(
    "/{job_id}",
    response_model=ExportResponse,
    summary="Export job MCQs",
    description="Export MCQs for a job in the specified format.",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Invalid format"},
    },
)
def export_job(
    job_id: str,
    request: ExportRequest,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> ExportResponse:
    """Export MCQs for a job."""
    api_requests.labels(path="/api/v1/exports/{job_id}").inc()

    service = ExportService(sm)

    try:
        result = service.export_job(
            job_id=job_id,
            format=request.format,
            output=request.output,
            include_metadata=request.include_metadata,
        )
        return ExportResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


@router.get(
    "/{job_id}/download",
    summary="Download export",
    description="Download exported MCQs as a file.",
    responses={
        404: {"model": ErrorResponse, "description": "Job or export not found"},
    },
)
def download_export(
    job_id: str,
    format: ExportFormat = ExportFormat.JSON,
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
):
    """Download exported MCQs file."""
    import os

    from fastapi.responses import FileResponse

    api_requests.labels(path="/api/v1/exports/{job_id}/download").inc()

    # Verify job exists
    jobs = sm.list_jobs()
    if not any(job["job_id"] == job_id for job in jobs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Validate job_id to prevent path traversal
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format",
        )
    
    # Determine file path
    file_path = f".mcq_exports/{job_id}.{format.value}"

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export file not found: {file_path}",
        )

    media_types = {
        ExportFormat.JSON: "application/json",
        ExportFormat.CSV: "text/csv",
        ExportFormat.MARKDOWN: "text/markdown",
        ExportFormat.PDF: "application/pdf",
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(format, "application/octet-stream"),
        filename=f"{job_id}.{format.value}",
    )
