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

# Unified Shared Infrastructure
try:
    from shared.config import settings as unified_settings

    _UNIFIED_MODE = True
except ImportError:
    # Fallback to local config if unified is not available
    try:
        from ..config import settings as unified_settings

        _UNIFIED_MODE = True
    except ImportError:
        unified_settings = None  # type: ignore[assignment]
        _UNIFIED_MODE = False

# Security utilities
try:
    from shared.security import (
        sanitize_html,
        sanitize_user_input,
        validate_email,
        validate_input_length,
        validate_path_traversal,
        validate_url,
    )

    _SECURITY_AVAILABLE = True
except ImportError:
    _SECURITY_AVAILABLE = False

    # Fallback no-op functions
    def sanitize_html(text: str, strip: bool = False) -> str:
        return text

    def sanitize_user_input(text: str | None) -> str | None:
        return text

    def validate_path_traversal(file_path: str, allowed_dir: str | None = None) -> bool:
        return True

    def validate_input_length(
        text: str | None, max_length: int = 10240, min_length: int = 0
    ) -> bool:
        return True

    def validate_email(email: str) -> bool:
        return True

    def validate_url(url: str, allowed_schemes: tuple = ("http", "https")) -> bool:
        return True


# API Key configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: str | None = Depends(api_key_header)) -> str | None:
    # Use unified settings if available
    if _UNIFIED_MODE and unified_settings:
        expected_key = unified_settings.mcq_api_key
        require_api_key = unified_settings.mcq_require_api_key
    else:
        # Legacy fallback
        expected_key = os.getenv("MCQ_API_KEY") or os.getenv("API_KEY")
        require_api_key = os.getenv(
            "MCQ_REQUIRE_API_KEY", os.getenv("REQUIRE_API_KEY", "false")
        ).lower() not in ("0", "false", "no")

    # If REQUIRE_API_KEY is enabled, API key is mandatory
    if require_api_key:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if not expected_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error: MCQ_API_KEY not set but MCQ_REQUIRE_API_KEY is enabled",
            )
        if api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )
        return api_key

    # Dev mode: no key configured, accept all requests
    if not expected_key:
        return api_key

    # Key configured but not required — validate when provided
    if not api_key:
        # We enforce key if configured, even if not strictly 'required' by boolean,
        # otherwise why configure it? (Fixes bypass)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

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
    if not db_path:
        if _UNIFIED_MODE and unified_settings:
            db_path = unified_settings.mcq_db_path
        else:
            db_path = os.getenv("MCQ_DB_PATH", "mcq_state.duckdb")

    sm = StateManager(db_path=db_path)
    try:
        yield sm
    finally:
        sm.close()


def get_state_manager() -> Generator[StateManager, None, None]:
    if _UNIFIED_MODE and unified_settings:
        db_path = unified_settings.mcq_db_path
    else:
        db_path = os.getenv("MCQ_DB_PATH", "mcq_state.duckdb")

    sm = StateManager(db_path=db_path)
    try:
        yield sm
    finally:
        sm.close()
