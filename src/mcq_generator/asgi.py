"""
ASGI entrypoint for the MCQ Generator API.

This module exposes the FastAPI `app` so servers like uvicorn can import
`mcq_generator.asgi:app` as the ASGI application.
"""

from .api.main import app

__all__ = ["app"]
