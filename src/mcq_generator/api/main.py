"""
Main FastAPI application factory.

This module creates and configures the FastAPI application instance,
following the application factory pattern for flexibility in testing
and different deployment scenarios.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .routers import (
    audit_logs,
    datasets,
    exports,
    health,
    jobs,
    metrics,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application factory - creates and configures the FastAPI app.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="MCQ Generator API",
        description="""
        High-Performance MCQ Generator API.

        This API provides endpoints for:
        - Dataset search on HuggingFace Hub
        - Job creation and management
        - MCQ generation with pause/resume support
        - Export in multiple formats (JSON, CSV, Markdown, PDF)
        - Real-time metrics and monitoring
        """,
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "MCQ Generator Team",
            "url": "https://github.com/example/mcq-generator",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # Add middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Configure CORS - allow from environment or default to common dev ports
    cors_env = os.getenv("CORS_ORIGINS", "")
    if cors_env:
        cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    else:
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health, tags=["Health"])
    app.include_router(metrics, tags=["Metrics"])
    app.include_router(datasets, prefix="/api/v1", tags=["Datasets"])
    app.include_router(jobs, prefix="/api/v1", tags=["Jobs"])
    app.include_router(exports, prefix="/api/v1", tags=["Exports"])
    app.include_router(audit_logs, prefix="/api/v1", tags=["Audit Logs"])

    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Bad Request", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.exception(f"Unhandled exception during {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if app.debug else "An unexpected error occurred",
                "path": request.url.path,
            },
        )

    return app


# Global app instance for ASGI servers
app = create_app()
