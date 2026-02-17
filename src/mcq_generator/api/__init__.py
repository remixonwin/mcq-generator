"""
Unified API System for MCQ Generator.

This module re-exports the main components for backward compatibility.
The API has been restructured into a proper architecture with routers,
services, and schemas for maintainability and scalability.
"""

from .dependencies import API_KEY_NAME, get_api_key, get_state_manager
from .main import app, create_app

__all__ = ["app", "create_app", "get_state_manager", "get_api_key", "API_KEY_NAME"]
