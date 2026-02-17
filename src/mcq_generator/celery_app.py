"""
Celery app factory for MCQ Generator (optional).

This module creates a Celery app when `CELERY_BROKER_URL` is configured.
Tasks should live in `mcq_generator.tasks` and be discoverable by workers.
"""

from __future__ import annotations

import os

from celery import Celery

BROKER = os.getenv("CELERY_BROKER_URL")
BACKEND = os.getenv("CELERY_RESULT_BACKEND")

if not BROKER:
    raise RuntimeError("CELERY_BROKER_URL not configured")

celery_app = Celery("mcq_generator", broker=BROKER, backend=BACKEND)
celery_app.conf.task_routes = {"mcq_generator.tasks.generate_task": {"queue": "mcq_jobs"}}
