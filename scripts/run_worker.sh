#!/usr/bin/env bash
# Simple persistent worker runner to resume any paused jobs on startup.
# This is a thin supervisor that looks for paused jobs and schedules them
# using the same generator logic; suitable for development or small deploys.

set -euo pipefail

export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src"

python - <<'PY'
from mcq_generator.state_manager import StateManager
from mcq_generator.api import _start_background_generation
import time

sm = StateManager()
try:
    jobs = sm.list_jobs(status="paused")
    for job in jobs:
        job_id = job["job_id"]
        progress = sm.get_job_progress(job_id)
        print(f"Scheduling resume for paused job: {job_id}")
        # Start background task in event loop
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(_start_background_generation(job_id, progress["dataset_name"], progress["target_questions"] or 999999999, f".mcq_exports/{job_id}.json", 10, ".mcq_cache", None))
        except Exception:
            # If no running event loop, run synchronously in a new loop
            asyncio.run(_start_background_generation(job_id, progress["dataset_name"], progress["target_questions"] or 999999999, f".mcq_exports/{job_id}.json", 10, ".mcq_cache", None))

    # Keep process alive to let background tasks run
    while True:
        time.sleep(60)
finally:
    sm.close()

PY
