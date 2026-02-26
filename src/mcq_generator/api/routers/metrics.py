"""
Metrics router.

Provides Prometheus-compatible metrics endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ...metrics import generate_metrics, metrics_available
from ..dependencies import get_api_key_optional

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Prometheus-compatible metrics endpoint for monitoring.",
    include_in_schema=True,
)
def metrics_endpoint(
    api_key: str | None = Depends(get_api_key_optional),
) -> Response:
    """Get Prometheus metrics."""
    body, content_type = generate_metrics()
    return Response(content=body, media_type=content_type)


@router.get(
    "/metrics/status",
    summary="Metrics status",
    description="Check if Prometheus metrics are available.",
    include_in_schema=True,
)
def metrics_status(
    api_key: str | None = Depends(get_api_key_optional),
) -> dict:
    """Check if metrics are available."""
    return {
        "available": metrics_available(),
        "provider": "prometheus_client" if metrics_available() else "none",
    }
