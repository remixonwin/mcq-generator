"""
Service layer for dataset operations.

Encapsulates dataset search logic, separating business logic from HTTP layer.
"""

from __future__ import annotations

import logging
from typing import Any

from datasets import load_dataset

from ...config import config
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

    def probe_dataset(self, dataset_name: str, limit_samples: int = 3) -> dict:
        """Lightweight preflight probe for a HuggingFace dataset.

        Attempts to stream a few examples and detect a usable text column.
        Returns a dict: { usable: bool, text_column: str|None, sample: str|None, reason: str }
        """
        logger.info(f"Probing dataset {dataset_name} (limit={limit_samples})")
        try:
            # Use streaming load to avoid downloading entire dataset
            ds = load_dataset(dataset_name, split="train", streaming=True, token=config.HF_TOKEN)
        except Exception as e:
            logger.warning(f"Failed to load dataset {dataset_name}: {e}")
            return {
                "usable": False,
                "text_column": None,
                "sample": None,
                "reason": f"load_error: {e}",
            }

        samples = []
        try:
            it = iter(ds)
            for _ in range(limit_samples):
                try:
                    item = next(it)
                except StopIteration:
                    break
                samples.append(item)
        except Exception as e:
            logger.debug(f"Error iterating dataset stream for {dataset_name}: {e}")

        if not samples:
            return {"usable": False, "text_column": None, "sample": None, "reason": "no_examples"}

        # Prefer common text-like columns
        candidate_cols = [
            "text",
            "content",
            "context",
            "article",
            "document",
            "body",
            "passage",
            "question",
            "summary",
            "headline",
        ]

        keys = set()
        for s in samples:
            if isinstance(s, dict):
                keys.update(s.keys())

        chosen = None
        for c in candidate_cols:
            if c in keys:
                chosen = c
                break

        if not chosen:
            first = samples[0]
            if isinstance(first, dict):
                for k, v in first.items():
                    if isinstance(v, str) and len(v) > 50:
                        chosen = k
                        break

        sample_text = None
        if chosen:
            for s in samples:
                if isinstance(s, dict):
                    val = s.get(chosen)
                    if isinstance(val, list):
                        val = " ".join(str(x) for x in val if x)
                    if isinstance(val, str) and len(val.strip()) > 30:
                        sample_text = val.strip()
                        break

        if not chosen or not sample_text:
            # Synthesize from multiple fields as fallback
            for s in samples:
                if not isinstance(s, dict):
                    continue
                parts = []
                for k, v in s.items():
                    if v is None:
                        continue
                    if isinstance(v, list):
                        v_str = " ".join(str(x) for x in v if x)
                    else:
                        v_str = str(v)
                    v_str = v_str.strip()
                    if len(v_str) > 30:
                        parts.append(f"{k}: {v_str}")
                if parts:
                    sample_text = " . ".join(parts)[:2000]
                    chosen = None
                    break

        if not sample_text:
            return {
                "usable": False,
                "text_column": None,
                "sample": None,
                "reason": "no_text_samples",
            }

        reason = f"probe_ok (column={chosen or 'synthesized'})"
        return {"usable": True, "text_column": chosen, "sample": sample_text, "reason": reason}
