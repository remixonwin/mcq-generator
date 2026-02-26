"""
Shared dependencies for the API.

This module provides dependency injection functions for FastAPI,
following the dependency injection pattern for testability and
maintainability.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from ..storage import StateManager

# API Key configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: str | None = Depends(api_key_header)) -> str | None:
    """
    Validate API key if API_KEY environment variable is set.

    If no API_KEY is configured, all requests are allowed.
    If API_KEY is configured, requests must include the correct key.
    """
    expected_key = os.getenv("API_KEY")

    # If no API key is configured, allow all requests
    if not expected_key:
        return api_key

    # API key is required but not provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Invalid API key
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


def get_api_key_optional(api_key: str | None = Depends(api_key_header)) -> str | None:
    """
    Optional API key validation - allows requests with or without API key.
    """
    expected_key = os.getenv("API_KEY")

    # If no API key is configured, allow all requests
    if not expected_key:
        return api_key

    # If API key is provided, validate it
    if api_key and api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


@contextmanager
def state_manager_context(db_path: str | None = None) -> Generator[StateManager, None, None]:
    """
    Context manager for StateManager to ensure proper cleanup.

    Usage:
        with state_manager_context() as sm:
            # use sm
    """
    sm = StateManager(db_path=db_path or os.getenv("MCQ_DB_PATH", "mcq_state.duckdb"))
    try:
        yield sm
    finally:
        sm.close()


def get_state_manager() -> Generator[StateManager, None, None]:
    """
    FastAPI dependency that provides a StateManager instance.

    The connection is automatically closed after the request.

    Usage:
        @app.get("/jobs")
        def list_jobs(sm: StateManager = Depends(get_state_manager)):
            return sm.list_jobs()
    """
    db_path = os.getenv("MCQ_DB_PATH", "mcq_state.duckdb")
    sm = StateManager(db_path=db_path)
    try:
        yield sm
    finally:
        sm.close()
