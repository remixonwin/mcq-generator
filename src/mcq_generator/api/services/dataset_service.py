"""
Service layer for dataset operations.

Encapsulates dataset search logic, separating business logic from HTTP layer.
"""

from __future__ import annotations

import logging
from typing import Any

from ...dataset_search import search_datasets
from ..schemas import DatasetItem

logger = logging.getLogger(__name__)


class DatasetService:
    """Service for dataset-related operations."""

    def search(
        self,
        query: str,
        limit: int = 10,
        sort: str = "downloads",
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Search for datasets on HuggingFace Hub.

        Args:
            query: Search query string
            limit: Maximum number of results
            sort: Sort field (downloads, likes, trending)
            offset: Offset for pagination

        Returns:
            Dict with results list and total count
        """
        logger.info(
            f"Searching datasets: query='{query}', limit={limit}, sort={sort}, offset={offset}"
        )

        results = search_datasets(
            query=query,
            limit=limit,
            sort=sort,
            offset=offset,
        )

        # Convert to schema models
        items = [
            DatasetItem(
                id=r["id"],
                downloads=r.get("downloads", 0),
                likes=r.get("likes", 0),
            )
            for r in results
        ]

        return {
            "results": items,
            "total": len(items),  # Note: HuggingFace doesn't provide total count easily
        }
