"""
Health check router.

Provides endpoints for monitoring and health checks.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ...storage import StateManager
from ..dependencies import get_api_key, get_state_manager
from ..schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API and its dependencies are healthy.",
    include_in_schema=True,
)
def health_check(
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key),
) -> HealthResponse:
    """Health check endpoint."""
    try:
        # Try a simple DB query
        _ = sm.get_statistics()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check broker if configured
    broker = os.getenv("CELERY_BROKER_URL")
    broker_status = broker if broker else None

    overall_status = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        db=db_status,
        broker=broker_status,
        version="2.0.0",
    )


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Simple health check",
    description="Lightweight health check endpoint (Kubernetes compatible).",
    include_in_schema=True,
)
def healthz(
    sm: StateManager = Depends(get_state_manager),
) -> HealthResponse:
    """Kubernetes-compatible health check."""
    try:
        _ = sm.get_statistics()
        return HealthResponse(
            status="ok",
            db="connected",
            version="2.0.0",
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "db": str(e),
                "version": "2.0.0",
            },
        )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Check if the service is ready to accept traffic.",
    include_in_schema=True,
)
def readiness_probe(
    sm: StateManager = Depends(get_state_manager),
) -> dict:
    """Readiness probe for Kubernetes."""
    try:
        _ = sm.get_statistics()
        return {"ready": True}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"ready": False},
        )
