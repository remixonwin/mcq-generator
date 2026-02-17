"""
Dataset router.

Handles dataset search endpoints, providing access to HuggingFace Hub datasets.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...metrics import api_requests
from ..dependencies import get_api_key
from ..schemas import DatasetSearchResponse, ErrorResponse
from ..services import DatasetService

router = APIRouter(prefix="/datasets")


@router.get(
    "/search",
    response_model=DatasetSearchResponse,
    summary="Search datasets",
    description="Search for datasets on HuggingFace Hub.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid search parameters"},
    },
)
def search_datasets_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    sort: str = Query("downloads", pattern="^(downloads|likes|trending)$"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    api_key: str | None = Depends(get_api_key),
) -> DatasetSearchResponse:
    """Search for datasets on HuggingFace Hub."""
    api_requests.labels(path="/api/v1/datasets/search").inc()

    service = DatasetService()
    result = service.search(query=q, limit=limit, sort=sort, offset=offset)

    return DatasetSearchResponse(**result)
