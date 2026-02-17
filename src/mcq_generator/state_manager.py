"""
State Manager using DuckDB for high-performance pause/resume functionality.
"""

import duckdb
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import logging
import time

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages job state, checkpoints, and progress tracking using DuckDB.
    """

    def __init__(self, db_path: str = "mcq_state.duckdb"):
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id VARCHAR PRIMARY KEY,
                dataset_name VARCHAR NOT NULL,
                dataset_split VARCHAR DEFAULT 'train',
                total_documents INTEGER,
                target_questions INTEGER,
                processed_count INTEGER DEFAULT 0,
                generated_count INTEGER DEFAULT 0,
                status VARCHAR DEFAULT 'pending',
                config JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                last_processed_index INTEGER NOT NULL,
                document_indices INTEGER[],
                cache_stats JSON,
                metrics JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mcq_results (
                mcq_id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                document_index INTEGER NOT NULL,
                document_hash VARCHAR NOT NULL,
                mcq_json JSON NOT NULL,
                quality_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_job ON checkpoints(job_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_mcq_job ON mcq_results(job_id)")

    def create_job(
        self,
        job_id: str,
        dataset_name: str,
        target_questions: int,
        config: Optional[dict] = None,
        dataset_split: str = "train",
    ) -> str:
        """Create a new job."""
        self.conn.execute(
            """
            INSERT INTO jobs (job_id, dataset_name, dataset_split, target_questions, config)
            VALUES (?, ?, ?, ?, ?)
            """,
            [job_id, dataset_name, dataset_split, target_questions, json.dumps(config or {})],
        )
        logger.info(f"Created job {job_id} for dataset {dataset_name}")
        return job_id

    def save_checkpoint(
        self,
        job_id: str,
        last_processed_index: int,
        document_indices: list,
        cache_stats: dict,
        metrics: dict,
    ) -> None:
        """Save a checkpoint for pause/resume."""
        checkpoint_id = f"{job_id}_cp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # Wrap DB writes in a small retry loop to handle transient write-write
        # conflicts in DuckDB when multiple processes may access the DB.
        max_attempts = 5
        delay = 0.05
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn.execute(
                    """
                    INSERT INTO checkpoints (checkpoint_id, job_id, last_processed_index, document_indices, cache_stats, metrics)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        checkpoint_id,
                        job_id,
                        last_processed_index,
                        document_indices,
                        json.dumps(cache_stats, default=str),
                        json.dumps(metrics, default=str),
                    ],
                )

                self.conn.execute(
                    "UPDATE jobs SET processed_count = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    [last_processed_index, job_id],
                )

                logger.info(f"Saved checkpoint {checkpoint_id} at index {last_processed_index}")
                break
            except duckdb.IOException as e:
                logger.debug(
                    "Transient DuckDB error saving checkpoint (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    e,
                )
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 2.0)

    def get_latest_checkpoint(self, job_id: str) -> Optional[dict]:
        """Get the most recent checkpoint for resuming."""
        result = self.conn.execute(
            """
            SELECT checkpoint_id, last_processed_index, document_indices, cache_stats, metrics, created_at
            FROM checkpoints
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [job_id],
        ).fetchone()

        if not result:
            return None

        # result[3] and result[4] may be NULL in the DB; guard before json.loads
        raw_cache = result[3]
        raw_metrics = result[4]

        cache_stats = json.loads(raw_cache) if raw_cache else {}
        metrics = json.loads(raw_metrics) if raw_metrics else {}

        created_at = result[5]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "checkpoint_id": result[0],
            "last_processed_index": result[1],
            "document_indices": result[2],
            "cache_stats": cache_stats,
            "metrics": metrics,
            "created_at": created_at,
        }

    def save_mcq(
        self,
        job_id: str,
        document_index: int,
        document_hash: str,
        mcq_data: dict,
        quality_score: float,
    ) -> None:
        """Save a generated MCQ."""
        mcq_id = f"{job_id}_mcq_{document_index}"

        # Upsert: update if exists, otherwise insert. Only increment generated_count
        # on new insert to avoid double-counting when resuming.
        # Wrap DB operations in a retry loop to avoid transient conflicts.
        max_attempts = 5
        delay = 0.05
        inserted = False
        for attempt in range(1, max_attempts + 1):
            try:
                row = self.conn.execute(
                    "SELECT COUNT(1) FROM mcq_results WHERE mcq_id = ?",
                    [mcq_id],
                ).fetchone()
                exists = row[0] if row else 0

                if exists and exists > 0:
                    # Update existing record
                    self.conn.execute(
                        """
                        UPDATE mcq_results
                        SET mcq_json = ?, quality_score = ?, created_at = CURRENT_TIMESTAMP
                        WHERE mcq_id = ?
                        """,
                        [json.dumps(mcq_data, default=str), quality_score, mcq_id],
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO mcq_results (mcq_id, job_id, document_index, document_hash, mcq_json, quality_score)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        [
                            mcq_id,
                            job_id,
                            document_index,
                            document_hash,
                            json.dumps(mcq_data, default=str),
                            quality_score,
                        ],
                    )
                    self.conn.execute(
                        "UPDATE jobs SET generated_count = generated_count + 1, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                        [job_id],
                    )
                    inserted = True

                break
            except duckdb.IOException as e:
                logger.debug(
                    "Transient DuckDB error saving mcq (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    e,
                )
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 2.0)

        # Best-effort exports: NDJSON + aggregated JSON in .mcq_exports
        try:
            export_dir = Path(".mcq_exports")
            export_dir.mkdir(parents=True, exist_ok=True)
            nd_path = export_dir / f"{job_id}.ndjson"
            if inserted:
                with nd_path.open("a", encoding="utf-8") as f:
                    f.write(
                        json.dumps({**mcq_data, "quality_score": quality_score}, default=str) + "\n"
                    )

            # Update aggregated JSON (replace or append appropriately)
            json_path = export_dir / f"{job_id}.json"
            try:
                existing = {
                    "generated_at": datetime.now().isoformat(),
                    "dataset": None,
                    "total_questions": 0,
                    "mcqs": [],
                }
                if json_path.exists():
                    try:
                        existing = json.loads(json_path.read_text(encoding="utf-8"))
                    except Exception:
                        existing = {
                            "generated_at": datetime.now().isoformat(),
                            "dataset": None,
                            "total_questions": 0,
                            "mcqs": [],
                        }

                entry = {**mcq_data, "quality_score": quality_score}
                existing_mcqs = existing.get("mcqs", [])
                if inserted:
                    existing_mcqs.append(entry)
                else:
                    # Replace or append
                    replaced = False
                    for i, e in enumerate(existing_mcqs):
                        if e.get("metadata", {}).get("source_document") == mcq_data.get(
                            "metadata", {}
                        ).get("source_document"):
                            existing_mcqs[i] = entry
                            replaced = True
                            break
                    if not replaced:
                        existing_mcqs.append(entry)

                existing["mcqs"] = existing_mcqs
                existing["total_questions"] = len(existing_mcqs)
                existing["generated_at"] = datetime.now().isoformat()

                tmp_json = json_path.with_suffix(json_path.suffix + ".tmp")
                tmp_json.write_text(
                    json.dumps(existing, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                tmp_json.replace(json_path)
            except Exception:
                logger.debug("Failed to update aggregated json export for job")
        except Exception:
            logger.debug("Failed to write autosave ndjson file for mcq")

    def get_job_progress(self, job_id: str) -> dict:
        """Get current progress for a job."""
        result = self.conn.execute(
            """
            SELECT job_id, dataset_name, total_documents, target_questions,
                   processed_count, generated_count, status,
                   created_at, updated_at, completed_at
            FROM jobs WHERE job_id = ?
            """,
            [job_id],
        ).fetchone()

        if not result:
            raise ValueError(f"Job {job_id} not found")

        created_at = result[7]
        updated_at = result[8]
        completed_at = result[9]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        if isinstance(completed_at, datetime):
            completed_at = completed_at.isoformat()

        return {
            "job_id": result[0],
            "dataset_name": result[1],
            "total_documents": result[2],
            "target_questions": result[3],
            "processed_count": result[4],
            "generated_count": result[5],
            "status": result[6],
            "created_at": created_at,
            "updated_at": updated_at,
            "completed_at": completed_at,
            "progress_pct": (result[5] / result[3] * 100) if result[3] > 0 else 0,
        }

    def list_jobs(self, status: Optional[str] = None) -> list[dict]:
        """List all jobs, optionally filtered by status."""
        query = "SELECT job_id, dataset_name, status, target_questions, generated_count, created_at FROM jobs"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        results = self.conn.execute(query, params).fetchall()

        out = []
        for row in results:
            created_at = row[5]
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            out.append(
                {
                    "job_id": row[0],
                    "dataset_name": row[1],
                    "status": row[2],
                    "target_questions": row[3],
                    "generated_count": row[4],
                    "created_at": created_at,
                }
            )
        return out

    def update_job_status(self, job_id: str, status: str) -> None:
        """Update job status (pending, running, paused, completed, failed)."""
        # Some environments may hit transient DuckDB write-write conflicts
        # when multiple processes/threads try to update the DB at once. Add a
        # small retry/backoff to make status updates more resilient.
        max_attempts = 5
        delay = 0.1
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    [status, job_id],
                )

                if status == "completed":
                    self.conn.execute(
                        "UPDATE jobs SET completed_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                        [job_id],
                    )

                # Success
                break
            except duckdb.IOException as e:
                logger.warning(
                    "DuckDB write conflict updating job status (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    e,
                )
                if attempt == max_attempts:
                    # Re-raise the last exception to let callers handle persistent failures
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 2.0)
            except Exception:
                # For any other DB error, re-raise immediately
                raise

    def update_total_documents(self, job_id: str, total_documents: int) -> None:
        """Update total_documents for the job (set after loading dataset)."""
        self.conn.execute(
            "UPDATE jobs SET total_documents = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            [total_documents, job_id],
        )

    def get_mcqs(self, job_id: str) -> list[dict]:
        """Get all MCQs for a job."""
        results = self.conn.execute(
            "SELECT mcq_json, quality_score, created_at FROM mcq_results WHERE job_id = ? ORDER BY document_index",
            [job_id],
        ).fetchall()

        out = []
        for row in results:
            created_at = row[2]
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            mcq = {**json.loads(row[0]), "quality_score": row[1], "created_at": created_at}
            out.append(mcq)
        return out

    def get_statistics(self) -> dict:
        """Get overall statistics."""
        stats = self.conn.execute("""
            SELECT 
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_jobs,
                SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) as paused_jobs,
                SUM(generated_count) as total_mcqs
            FROM jobs
        """).fetchone()

        if stats is None:
            return {
                "total_jobs": 0,
                "completed_jobs": 0,
                "running_jobs": 0,
                "paused_jobs": 0,
                "total_mcqs": 0,
            }

        return {
            "total_jobs": stats[0] or 0,
            "completed_jobs": stats[1] or 0,
            "running_jobs": stats[2] or 0,
            "paused_jobs": stats[3] or 0,
            "total_mcqs": stats[4] or 0,
        }

    def cleanup_old_checkpoints(self, job_id: str, keep_last_n: int = 5) -> None:
        """Remove old checkpoints to save space."""
        self.conn.execute(
            """
            DELETE FROM checkpoints
            WHERE checkpoint_id IN (
                SELECT checkpoint_id FROM checkpoints
                WHERE job_id = ?
                ORDER BY created_at DESC
                OFFSET ?
            )
            """,
            [job_id, keep_last_n],
        )

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
