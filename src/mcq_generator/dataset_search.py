"""
HuggingFace Dataset Search Module
"""

import logging
from typing import Optional
from huggingface_hub import list_datasets

from .config import config

logger = logging.getLogger(__name__)


def search_datasets(
    query: Optional[str] = None,
    limit: int = 10,
    sort: str = "downloads",
    direction: Optional[int] = -1,
    offset: int = 0,
) -> list[dict]:
    """
    Search for datasets on HuggingFace Hub.

    Args:
        query: Search query string
        limit: Number of results to return
        sort: Sort by field (downloads, likes, trending)
        direction: Sort direction (-1 for desc, 1 for asc)
        offset: Number of results to skip

    Returns:
        List of dataset info dictionaries
    """
    try:
        datasets = list_datasets(
            search=query,
            limit=limit,
            sort=sort,
            direction=None,
            token=config.HF_TOKEN,
        )

        results = []
        for i, ds in enumerate(datasets):
            if i < offset:
                continue
            results.append(
                {
                    "id": ds.id,
                    "downloads": getattr(ds, "downloads", 0) or 0,
                    "likes": getattr(ds, "likes", 0) or 0,
                    "tags": getattr(ds, "tags", []) or [],
                    "private": getattr(ds, "private", False),
                    "author": getattr(ds, "author", ""),
                    "sha": getattr(ds, "sha", ""),
                }
            )

        return results

    except Exception as e:
        logger.error(f"Error searching datasets: {e}")
        return []


def get_dataset_info(dataset_id: str) -> Optional[dict]:
    """
    Get detailed info for a specific dataset.

    Args:
        dataset_id: Dataset ID (e.g., "glue" or "stanfordnlp/imdb")

    Returns:
        Dataset info dictionary or None if not found
    """
    try:
        datasets = list_datasets(search=dataset_id, limit=1, token=config.HF_TOKEN)

        for ds in datasets:
            if ds.id.lower() == dataset_id.lower():
                return {
                    "id": ds.id,
                    "downloads": getattr(ds, "downloads", 0) or 0,
                    "likes": getattr(ds, "likes", 0) or 0,
                    "tags": getattr(ds, "tags", []) or [],
                    "private": getattr(ds, "private", False),
                    "author": getattr(ds, "author", ""),
                    "sha": getattr(ds, "sha", ""),
                }

        return None

    except Exception as e:
        logger.error(f"Error getting dataset info: {e}")
        return None
