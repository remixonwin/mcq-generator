#!/usr/bin/env python3
"""
One-off DB repair script: for each job in the jobs table, ensure mcq_results
rows are present by restoring from .mcq_exports and syncing generated_count.

Usage: python scripts/db_repair_all_jobs.py
"""

from pathlib import Path
from src.mcq_generator.state_manager import StateManager


def main(db_path: str = "mcq_state.duckdb"):
    s = StateManager(db_path=db_path)
    try:
        jobs = s.list_jobs()
        for job in jobs:
            job_id = job["job_id"]
            print(f"Repairing job: {job_id}")
            restored = s.restore_missing_mcqs(job_id)
            if restored:
                print(f"  Restored {restored} rows for {job_id}")
            else:
                print(f"  No rows restored for {job_id}")
            synced = s.sync_generated_count(job_id)
            print(f"  Synced generated_count = {synced}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
