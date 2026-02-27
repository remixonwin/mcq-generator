"""
Health check router.

Provides endpoints for monitoring and health checks.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from mcq_generator.api.dependencies import get_api_key_optional, get_state_manager
from mcq_generator.api.schemas import HealthResponse
from mcq_generator.storage import StateManager

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API and its dependencies are healthy. Kubernetes compatible.",
    include_in_schema=True,
)
def health_check(
    sm: StateManager = Depends(get_state_manager),
    api_key: str | None = Depends(get_api_key_optional),
) -> HealthResponse:
    """Health check endpoint with dependency status."""

    # Try a simple DB query
    db_status = "connected"
    try:
        _ = sm.get_statistics()
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check broker if configured
    broker = os.getenv("CELERY_BROKER_URL")
    broker_status = broker if broker else None

    # Check Redis connectivity
    redis_status = "unknown"
    try:
        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        # Use await for async redis
        import asyncio

        asyncio.get_event_loop().run_until_complete(r.ping())
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    overall_status = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        db=db_status,
        broker=broker_status,
        redis=redis_status,
        version="2.0.0",
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
