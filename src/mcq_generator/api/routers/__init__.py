"""
Router exports.
"""

from .datasets import router as datasets_router
from .exports import router as exports_router
from .health import router as health_router
from .jobs import router as jobs_router
from .metrics import router as metrics_router

# Alias for backwards compatibility
jobs = jobs_router
datasets = datasets_router
exports = exports_router
health = health_router
metrics = metrics_router

__all__ = ["jobs", "datasets", "exports", "health", "metrics"]
