"""
HTTP client for CLI to communicate with the API.

This client allows the CLI to use the REST API instead of
accessing the database directly, ensuring a single source of truth.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class MCQApiClient:
    """
    HTTP client for MCQ Generator API.

    Usage:
        client = MCQApiClient(base_url="http://localhost:8000")
        jobs = client.list_jobs()
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or os.getenv("MCQ_API_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("API_KEY")
        self.timeout = timeout

        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an HTTP request."""
        url = f"/api/v1{path}" if not path.startswith("/") else path

        response = self.client.request(method, url, **kwargs)
        response.raise_for_status()

        if response.status_code == 204:
            return {}

        return response.json()

    # =========================================================================
    # Dataset Operations
    # =========================================================================

    def search_datasets(
        self,
        query: str,
        limit: int = 10,
        sort: str = "downloads",
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for datasets."""
        return self._request(
            "GET",
            "/datasets/search",
            params={"q": query, "limit": limit, "sort": sort, "offset": offset},
        )

    # =========================================================================
    # Job Operations
    # =========================================================================

    def list_jobs(
        self,
        status: str | None = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """List all jobs."""
        params = {"offset": offset, "limit": limit}
        if status:
            params["status"] = status

        return self._request("GET", "/jobs", params=params)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Get job details."""
        return self._request("GET", f"/jobs/{job_id}")

    def create_job(
        self,
        dataset: str,
        questions: int = 0,
        checkpoint: int = 10,
        cache_dir: str = ".mcq_cache",
        provider_url: str | None = None,
        output: str | None = None,
        dataset_split: str = "train",
        text_column: str = "text",
    ) -> dict[str, Any]:
        """Create a new generation job."""
        data = {
            "dataset": dataset,
            "questions": questions,
            "checkpoint": checkpoint,
            "cache_dir": cache_dir,
            "provider_url": provider_url,
            "output": output,
            "dataset_split": dataset_split,
            "text_column": text_column,
        }
        return self._request("POST", "/jobs", json=data)

    def resume_job(self, job_id: str) -> dict[str, Any]:
        """Resume a job."""
        return self._request("POST", f"/jobs/{job_id}/resume")

    def update_job_status(
        self,
        job_id: str,
        status: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Update job status."""
        data = {"status": status}
        if reason:
            data["reason"] = reason

        return self._request("PATCH", f"/jobs/{job_id}/status", json=data)

    def delete_job(self, job_id: str) -> None:
        """Delete a job."""
        self._request("DELETE", f"/jobs/{job_id}")

    def get_job_mcqs(self, job_id: str) -> dict[str, Any]:
        """Get MCQs for a job."""
        return self._request("GET", f"/jobs/{job_id}/mcqs")

    # =========================================================================
    # Export Operations
    # =========================================================================

    def export_job(
        self,
        job_id: str,
        format: str = "json",
        output: str | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Export job MCQs."""
        data = {
            "format": format,
            "include_metadata": include_metadata,
        }
        if output:
            data["output"] = output

        return self._request("POST", f"/exports/{job_id}", json=data)

    # =========================================================================
    # Health & Metrics
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Check API health."""
        return self._request("GET", "/health")

    def get_metrics(self) -> str:
        """Get Prometheus metrics."""
        response = self.client.get("/metrics")
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
