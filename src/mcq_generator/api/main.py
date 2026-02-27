"""
Main FastAPI application factory.

This module creates and configures the FastAPI application instance,
following the application factory pattern for flexibility in testing
and different deployment scenarios.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Rate limiting imports
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Security imports
try:
    from shared.logging import (
        CorrelationIdMiddleware,
        RequestResponseLoggingMiddleware,
        configure_logging,
    )
    from shared.security import (
        RequestSizeLimitMiddleware,
        SecurityHeadersMiddleware,
    )

    _SECURITY_AVAILABLE = True
except ImportError:
    _SECURITY_AVAILABLE = False

    # Fallback no-op middleware
    class SecurityHeadersMiddleware:
        pass

    class RequestSizeLimitMiddleware:
        pass

    # Fallback logging middleware
    class CorrelationIdMiddleware:
        pass

    class RequestResponseLoggingMiddleware:
        pass

    def configure_logging(*args, **kwargs):
        pass


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

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.getenv("MCQ_RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
RATE_LIMIT_READ_REQUESTS = int(os.getenv("MCQ_RATE_LIMIT_READ_REQUESTS", "100"))
RATE_LIMIT_READ_WINDOW = os.getenv("MCQ_RATE_LIMIT_READ_WINDOW", "1 minute")
RATE_LIMIT_WRITE_REQUESTS = int(os.getenv("MCQ_RATE_LIMIT_WRITE_REQUESTS", "10"))
RATE_LIMIT_WRITE_WINDOW = os.getenv("MCQ_RATE_LIMIT_WRITE_WINDOW", "1 minute")
RATE_LIMIT_REDIS_URL = os.getenv("MCQ_RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


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

    # Add security middleware if available
    if _SECURITY_AVAILABLE:
        try:
            app.add_middleware(SecurityHeadersMiddleware)
            app.add_middleware(RequestSizeLimitMiddleware, max_body_size=10 * 1024 * 1024)  # 10MB
        except Exception as e:
            logger.warning(f"Could not add security middleware: {e}")

    # Configure rate limiter with Redis storage if enabled
    if RATE_LIMIT_ENABLED:
        try:
            import redis.asyncio as redis

            redis_client = redis.from_url(RATE_LIMIT_REDIS_URL)
            # Skip ping in synchronous factory, connection will be checked on first request or startup event
            # await redis_client.ping()

            # Use Redis storage for distributed rate limiting
            from slowapi._store import RedisRateLimit

            limiter.storage = RedisRateLimit(redis_client)
            logger.info("Rate limiting enabled with Redis backend")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis for rate limiting: {e}. Using in-memory storage."
            )

    # Add rate limiter to app state
    app.state.limiter = limiter

    # Add rate limit exception handler
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": str(exc.detail),
                "retry_after": exc.detail,
            },
            headers={"Retry-After": str(exc.detail)},
        )

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
        allow_headers=["*", "X-Correlation-ID"],
    )

    # Add correlation ID and request/response logging middleware
    try:
        app.add_middleware(CorrelationIdMiddleware)
        app.add_middleware(RequestResponseLoggingMiddleware, service_name="mcq-generator")
    except Exception as e:
        logger.warning(f"Could not add logging middleware: {e}")

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
