"""
State Manager using DuckDB for high-performance pause/resume functionality.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class StateManager:
    """
    Manages job state, checkpoints, and progress tracking using DuckDB.
    """

    def __init__(self, db_path: str = "mcq_state.duckdb"):
        # Allow overriding DB path via environment variable for tests and deployments
        env_path = os.getenv("MCQ_DB_PATH")
        if env_path and (db_path is None or db_path == "mcq_state.duckdb"):
            db_path = env_path

        self.db_path = Path(db_path)

        # Attempt to connect to DuckDB with a small retry/backoff to handle
        # transient file lock conflicts (common when a background worker has
        # an open write handle). If we cannot acquire a writable connection
        # after a few attempts, fall back to a read-only connection so that
        # callers can still inspect state (listing jobs, viewing progress)
        # without failing the whole CLI.
        self.read_only = False
        max_attempts = 5
        delay = 0.1
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn = duckdb.connect(str(self.db_path))
                break
            except duckdb.IOException as e:
                if attempt == max_attempts:
                    if self._try_recover_from_stale_lock():
                        logger.info("Recovered from stale lock")
                        continue
                    logger.warning(
                        "Unable to acquire writable DuckDB connection after %d attempts; trying read-only fallback",
                        max_attempts,
                    )
                    try:
                        self.conn = duckdb.connect(str(self.db_path), read_only=True)
                        self.read_only = True
                        logger.info("Connected to DuckDB in read-only mode: %s", self.db_path)
                        break
                    except Exception as e2:
                        logger.error(
                            "Failed to open DuckDB - a job may be running. Use 'mcq logs <job_id>' to view progress"
                        )
                        raise RuntimeError("Database locked by another process") from e2
                time.sleep(delay)
                delay = min(delay * 2, 1.0)

        if not getattr(self, "conn", None):
            # If for some reason connection isn't set, raise to fail fast
            raise RuntimeError(f"Failed to connect to DuckDB at {self.db_path}")

        if not self.read_only:
            self._initialize_schema()
        else:
            logger.debug("Skipping schema initialization in read-only mode")

    def _try_recover_from_stale_lock(self) -> bool:
        """Check if lock-holding process is dead and recover."""
        lock_file = self.db_path.with_suffix(".lock")
        if not lock_file.exists():
            return False
        try:
            import psutil

            content = lock_file.read_text().strip()
            if content.isdigit():
                pid = int(content)
                if not psutil.pid_exists(pid):
                    logger.info("Removing stale lock file from dead process %d", pid)
                    lock_file.unlink()
                    return True
        except Exception:
            pass
        return False

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
                synth_columns JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure older DBs get the new synth_columns column without breaking
        # existing installs. Try to add the column if it doesn't exist; ignore
        # errors if it already exists or the DB doesn't allow ALTER.
        try:
            self.conn.execute("ALTER TABLE checkpoints ADD COLUMN IF NOT EXISTS synth_columns JSON")
        except Exception:
            # Non-fatal: some DuckDB versions or states may not support IF NOT EXISTS
            # or may raise if column already present. Ignore to be backward compatible.
            pass

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mcq_results (
                mcq_id VARCHAR PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                document_index INTEGER NOT NULL,
                document_hash VARCHAR NOT NULL,
                mcq_json JSON NOT NULL,
                quality_score FLOAT,
                synth_columns JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_job ON checkpoints(job_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_mcq_job ON mcq_results(job_id)")
        # Ensure older DBs get the new synth_columns column on mcq_results (best-effort)
        try:
            # Some DuckDB versions support ALTER TABLE ... ADD COLUMN IF NOT EXISTS
            self.conn.execute("ALTER TABLE mcq_results ADD COLUMN IF NOT EXISTS synth_columns JSON")
        except Exception:
            try:
                # Older syntax without IF NOT EXISTS may raise; try a safer no-op
                self.conn.execute("ALTER TABLE mcq_results ADD COLUMN synth_columns JSON")
            except Exception:
                # Ignore failures - schema upgrade not critical at runtime
                pass

    def create_job(
        self,
        job_id: str,
        dataset_name: str,
        target_questions: int,
        config: dict | None = None,
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

    def update_job_config(self, job_id: str, new_config: dict, merge: bool = True) -> None:
        """Update or set the JSON config blob for a job.

        If merge is True, the existing config will be merged with new_config
        (shallow dict update). Otherwise the config will be replaced.
        """
        # Fetch existing config
        try:
            row = self.conn.execute("SELECT config FROM jobs WHERE job_id = ?", [job_id]).fetchone()
            raw = row[0] if row and row[0] is not None else None
            if merge:
                try:
                    existing = json.loads(raw) if raw else {}
                except Exception:
                    existing = {}
                merged = {**existing, **(new_config or {})}
            else:
                merged = new_config or {}

            self.conn.execute(
                "UPDATE jobs SET config = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                [json.dumps(merged, default=str), job_id],
            )
        except Exception as e:
            logger.warning(f"Failed to update job config for {job_id}: {e}")

    def save_checkpoint(
        self,
        job_id: str,
        last_processed_index: int,
        document_indices: list,
        cache_stats: dict,
        metrics: dict,
        synth_columns: list | None = None,
    ) -> None:
        """Save a checkpoint for pause/resume."""
        checkpoint_id = f"{job_id}_cp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        # Wrap DB writes in a small retry loop to handle transient write-write
        # conflicts in DuckDB when multiple processes may access the DB.
        max_attempts = 5
        delay = 0.05
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn.execute(
                    """
                    INSERT INTO checkpoints (checkpoint_id, job_id, last_processed_index, document_indices, cache_stats, metrics, synth_columns)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        checkpoint_id,
                        job_id,
                        last_processed_index,
                        document_indices,
                        json.dumps(cache_stats, default=str),
                        json.dumps(metrics, default=str),
                        json.dumps(synth_columns, default=str)
                        if synth_columns is not None
                        else None,
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

    def get_latest_checkpoint(self, job_id: str) -> dict | None:
        """Get the most recent checkpoint for resuming."""
        result = self.conn.execute(
            """
            SELECT checkpoint_id, last_processed_index, document_indices, cache_stats, metrics, synth_columns, created_at
            FROM checkpoints
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [job_id],
        ).fetchone()

        if not result:
            return None

        # result[3].. may be NULL in the DB; guard before json.loads
        raw_cache = result[3]
        raw_metrics = result[4]
        raw_synth = result[5] if len(result) > 5 else None

        cache_stats = json.loads(raw_cache) if raw_cache else {}
        metrics = json.loads(raw_metrics) if raw_metrics else {}
        try:
            synth_columns = json.loads(raw_synth) if raw_synth else None
        except Exception:
            synth_columns = None

        created_at = result[6] if len(result) > 6 else None
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "checkpoint_id": result[0],
            "last_processed_index": result[1],
            "document_indices": result[2],
            "cache_stats": cache_stats,
            "metrics": metrics,
            "synth_columns": synth_columns,
            "created_at": created_at,
        }

    def save_mcq(
        self,
        job_id: str,
        document_index: int,
        document_hash: str,
        mcq_data: dict,
        quality_score: float,
        synth_columns: list | None = None,
    ) -> None:
        """Save a generated MCQ."""
        mcq_id = f"{job_id}_mcq_{document_index}"

        # Upsert: update if exists, otherwise insert. Only increment generated_count
        # on new insert to avoid double-counting when resuming.
        # Wrap DB operations in a retry loop to avoid transient conflicts.
        # Ensure mcq_data metadata explicitly contains job_id and document_index
        try:
            if isinstance(mcq_data, dict):
                md = mcq_data.get("metadata", {})
                if isinstance(md, dict):
                    md.setdefault("job_id", job_id)
                    md.setdefault("document_index", document_index)
                    mcq_data["metadata"] = md
        except Exception:
            pass

        max_attempts = 5
        delay = 0.05
        inserted = False
        for attempt in range(1, max_attempts + 1):
            try:
                row = self.conn.execute(
                    "SELECT COUNT(1) FROM mcq_results WHERE mcq_id = ?",
                    [mcq_id],
                ).fetchone()
                exists = int(row[0]) if row and len(row) > 0 else 0

                if exists and exists > 0:
                    # Update existing record
                    self.conn.execute(
                        """
                        UPDATE mcq_results
                        SET mcq_json = ?, quality_score = ?, synth_columns = ?, created_at = CURRENT_TIMESTAMP
                        WHERE mcq_id = ?
                        """,
                        [
                            json.dumps(mcq_data, default=str),
                            quality_score,
                            json.dumps(synth_columns, default=str)
                            if synth_columns is not None
                            else None,
                            mcq_id,
                        ],
                    )
                else:
                    self.conn.execute(
                        """
                        INSERT INTO mcq_results (mcq_id, job_id, document_index, document_hash, mcq_json, quality_score, synth_columns)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            mcq_id,
                            job_id,
                            document_index,
                            document_hash,
                            json.dumps(mcq_data, default=str),
                            quality_score,
                            json.dumps(synth_columns, default=str)
                            if synth_columns is not None
                            else None,
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

        # Ensure mcq_data metadata explicitly contains job_id and document_index
        try:
            if isinstance(mcq_data, dict):
                md = mcq_data.get("metadata", {})
                if isinstance(md, dict):
                    md.setdefault("job_id", job_id)
                    md.setdefault("document_index", document_index)
                    mcq_data["metadata"] = md
        except Exception:
            pass

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

        # Verification: ensure mcq row exists after upsert. If we expected an
        # insert (inserted=True) but the row isn't present, attempt a direct
        # insert to repair the inconsistency. This protects against cases where
        # the generated_count was incremented but the insert didn't persist.
        try:
            row = self.conn.execute(
                "SELECT COUNT(1) FROM mcq_results WHERE mcq_id = ?",
                [mcq_id],
            ).fetchone()
            exists_now = int(row[0]) if row else 0
            if inserted and exists_now == 0:
                logger.warning(
                    "mcq_results inconsistency detected for %s: expected inserted but row missing, repairing",
                    mcq_id,
                )
                # Try to insert directly (idempotent check first)
                try:
                    self.conn.execute(
                        "INSERT INTO mcq_results (mcq_id, job_id, document_index, document_hash, mcq_json, quality_score, synth_columns) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [
                            mcq_id,
                            job_id,
                            document_index,
                            document_hash,
                            json.dumps(mcq_data, default=str),
                            quality_score,
                            json.dumps(synth_columns, default=str)
                            if synth_columns is not None
                            else None,
                        ],
                    )
                    # Ensure generated_count reflects reality
                    self.conn.execute(
                        "UPDATE jobs SET generated_count = (SELECT COUNT(1) FROM mcq_results WHERE job_id = ?), updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                        [job_id, job_id],
                    )
                    logger.info("Repaired mcq_results and synced generated_count for %s", job_id)
                except Exception as e:
                    logger.error("Failed to repair missing mcq row %s: %s", mcq_id, e)
        except Exception:
            # Non-fatal: continue
            pass

    def get_job_progress(self, job_id: str) -> dict:
        """Get current progress for a job."""
        result = self.conn.execute(
            """
            SELECT job_id, dataset_name, total_documents, target_questions,
                    processed_count, generated_count, status,
                    created_at, updated_at, completed_at, config
            FROM jobs WHERE job_id = ?
            """,
            [job_id],
        ).fetchone()

        if not result:
            raise ValueError(f"Job {job_id} not found")

        # Always get the real count from mcq_results to ensure accuracy
        actual_count = self.count_mcq_rows(job_id)

        created_at = result[7]
        updated_at = result[8]
        completed_at = result[9]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        if isinstance(completed_at, datetime):
            completed_at = completed_at.isoformat()

        # config is stored as JSON text in the jobs table; parse if present
        raw_config = result[10]
        try:
            cfg = json.loads(raw_config) if raw_config else {}
        except Exception:
            cfg = {}

        # Expose text_column and synth_columns at top-level for convenience.
        text_column = cfg.get("text_column")
        synth_columns = cfg.get("synth_columns")
        # If synth_columns not present in job config, look at latest checkpoint
        if synth_columns is None:
            try:
                cp = self.get_latest_checkpoint(job_id)
                if cp:
                    synth_columns = cp.get("synth_columns")
            except Exception:
                synth_columns = None

        return {
            "job_id": result[0],
            "dataset_name": result[1],
            "total_documents": result[2],
            "target_questions": result[3],
            "processed_count": result[4],
            "generated_count": actual_count,
            "status": result[6],
            "created_at": created_at,
            "updated_at": updated_at,
            "completed_at": completed_at,
            "progress_pct": (actual_count / result[3] * 100) if result[3] > 0 else 0,
            "config": cfg,
            "text_column": text_column,
            "synth_columns": synth_columns,
        }

    def count_mcq_rows(self, job_id: str) -> int:
        """Return the number of mcq_results rows for a job."""
        row = self.conn.execute(
            "SELECT COUNT(1) FROM mcq_results WHERE job_id = ?",
            [job_id],
        ).fetchone()
        return int(row[0]) if row else 0

    def sync_generated_count(self, job_id: str) -> int:
        """Ensure jobs.generated_count matches the number of mcq_results rows.

        Returns the synchronized count.
        """
        actual = self.count_mcq_rows(job_id)
        # Small retry loop like update_job_status
        max_attempts = 3
        delay = 0.05
        for attempt in range(1, max_attempts + 1):
            try:
                self.conn.execute(
                    "UPDATE jobs SET generated_count = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    [actual, job_id],
                )
                break
            except duckdb.IOException as e:
                logger.debug(
                    "Transient DuckDB error syncing generated_count (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    e,
                )
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 1.0)

        return actual

    def restore_missing_mcqs(self, job_id: str, export_dir: str = ".mcq_exports") -> int:
        """Best-effort restore of MCQs from .mcq_exports/<job_id>.ndjson or .json into the DB.

        Returns the number of MCQs restored/inserted.
        """
        from pathlib import Path

        restored = 0
        export_path_nd = Path(export_dir) / f"{job_id}.ndjson"
        export_path_json = Path(export_dir) / f"{job_id}.json"

        def _iter_entries():
            if export_path_nd.exists():
                with export_path_nd.open("r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            yield json.loads(line)
                        except Exception:
                            continue
            elif export_path_json.exists():
                try:
                    data = json.loads(export_path_json.read_text(encoding="utf-8"))
                    for entry in data.get("mcqs", []):
                        yield entry
                except Exception:
                    return

        # Insert missing rows directly for robustness (avoid relying on save_mcq
        # which has more complex upsert logic). We perform a simple existence
        # check per mcq_id and insert when absent.
        for entry in _iter_entries():
            try:
                md = entry.get("metadata", {})
                src = md.get("source_document", "")
                doc_index = None
                if isinstance(src, str) and "_" in src:
                    try:
                        doc_index = int(src.split("_")[-1])
                    except Exception:
                        doc_index = None

                # If document index couldn't be parsed, assign a new sequential
                # index based on current max for this job so we can insert a
                # non-null document_index (schema requires it).
                if doc_index is None:
                    row = self.conn.execute(
                        "SELECT COALESCE(MAX(document_index), -1) FROM mcq_results WHERE job_id = ?",
                        [job_id],
                    ).fetchone()
                    max_idx = int(row[0]) if row and row[0] is not None else -1
                    doc_index = max_idx + 1

                mcq_id = f"{job_id}_mcq_{doc_index}"
                row = self.conn.execute(
                    "SELECT COUNT(1) FROM mcq_results WHERE mcq_id = ?",
                    [mcq_id],
                ).fetchone()
                exists = int(row[0]) if row else 0
                if exists:
                    continue

                # Insert directly
                self.conn.execute(
                    "INSERT INTO mcq_results (mcq_id, job_id, document_index, document_hash, mcq_json, quality_score, synth_columns) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        mcq_id,
                        job_id,
                        doc_index,
                        md.get("document_hash", ""),
                        json.dumps(entry, default=str),
                        float(entry.get("quality_score", 0.0)),
                        None,
                    ],
                )
                restored += 1
            except Exception:
                # skip problematic entries
                continue

        # After attempting restore, resync generated_count
        self.sync_generated_count(job_id)
        return restored

    def list_jobs(self, status: str | None = None) -> list[dict]:
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
                    # Sync generated_count to match actual mcq_results count
                    self.sync_generated_count(job_id)

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

        # Also write lightweight status file for concurrent read access
        try:
            progress = self.get_job_progress(job_id) if not self.read_only else {}
            self.write_job_status_lightweight(job_id, status, progress)
        except Exception:
            logger.debug("Failed to write lightweight status file")

    def update_total_documents(self, job_id: str, total_documents: int) -> None:
        """Update total_documents for the job (set after loading dataset)."""
        self.conn.execute(
            "UPDATE jobs SET total_documents = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            [total_documents, job_id],
        )

    def get_mcqs(self, job_id: str) -> list[dict]:
        """Get all MCQs for a job."""
        results = self.conn.execute(
            "SELECT mcq_json, quality_score, synth_columns, created_at FROM mcq_results WHERE TRIM(job_id) = ? ORDER BY document_index",
            [job_id],
        ).fetchall()

        out = []
        for row in results:
            created_at_val = row[3]
            if isinstance(created_at_val, datetime):
                created_at_val = created_at_val.isoformat()

            try:
                parsed = json.loads(row[0])
            except Exception:
                parsed = {}

            synth_raw = row[2]
            try:
                synth_cols = json.loads(synth_raw) if synth_raw else None
            except Exception:
                synth_cols = None

            mcq = {**parsed, "quality_score": row[1], "created_at": created_at_val}
            if synth_cols is not None:
                mcq["synth_columns"] = synth_cols
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

    def get_stale_jobs(self, stale_minutes: int = 5) -> list[dict]:
        """Get jobs marked as running but not updated in X minutes (likely crashed/stuck)."""
        results = self.conn.execute(
            f"""
            SELECT job_id, dataset_name, status, target_questions, generated_count, created_at, updated_at
            FROM jobs
            WHERE status = 'running'
            AND updated_at < CURRENT_TIMESTAMP - INTERVAL '{stale_minutes}' minute
            ORDER BY created_at DESC
            """
        ).fetchall()

        out = []
        for row in results:
            created_at = row[5]
            updated_at = row[6]
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            if isinstance(updated_at, datetime):
                updated_at = updated_at.isoformat()
            out.append(
                {
                    "job_id": row[0],
                    "dataset_name": row[1],
                    "status": row[2],
                    "target_questions": row[3],
                    "generated_count": row[4],
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
        return out

    def fix_stale_jobs(self, stale_minutes: int = 5, mark_as: str = "paused") -> int:
        """Mark stale running jobs as paused/failed. Returns count of fixed jobs."""
        stale = self.get_stale_jobs(stale_minutes)
        if not stale:
            return 0

        self.conn.execute(
            f"""
            UPDATE jobs
            SET status = '{mark_as}', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'running'
            AND updated_at < CURRENT_TIMESTAMP - INTERVAL '{stale_minutes}' minute
            """
        )
        return len(stale)

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

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all its related data (mcq_results, checkpoints). Returns True if successful."""
        try:
            self.conn.execute("DELETE FROM mcq_results WHERE job_id = ?", [job_id])
            self.conn.execute("DELETE FROM checkpoints WHERE job_id = ?", [job_id])
            self.conn.execute("DELETE FROM jobs WHERE job_id = ?", [job_id])
            return True
        except Exception:
            return False

    def get_job(self, job_id: str) -> dict | None:
        """Get a single job by ID."""
        result = self.conn.execute(
            "SELECT job_id, dataset_name, status, target_questions, generated_count, created_at, updated_at FROM jobs WHERE job_id = ?",
            [job_id],
        ).fetchone()

        if result is None:
            return None

        return {
            "job_id": result[0],
            "dataset_name": result[1],
            "status": result[2],
            "target_questions": result[3],
            "generated_count": result[4],
            "created_at": result[5].isoformat()
            if isinstance(result[5], datetime)
            else str(result[5]),
            "updated_at": result[6].isoformat()
            if isinstance(result[6], datetime)
            else str(result[6]),
        }

    def _get_status_file(self, job_id: str) -> Path:
        """Get path to lightweight status JSON file for a job."""
        return self.db_path.parent / ".job_status" / f"{job_id}.json"

    def write_job_status_lightweight(
        self, job_id: str, status: str, progress: dict[str, Any]
    ) -> None:
        """Write lightweight status to JSON file for concurrent read access."""
        status_file = self._get_status_file(job_id)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        status_file.write_text(json.dumps(data))

    def read_job_status_lightweight(self, job_id: str) -> dict[str, Any] | None:
        """Read lightweight status from JSON file. Returns None if not found."""
        status_file = self._get_status_file(job_id)
        if not status_file.exists():
            return None
        try:
            return json.loads(status_file.read_text())
        except Exception:
            return None

    def list_jobs_lightweight(self) -> list[dict[str, Any]]:
        """List all jobs from lightweight status files (fallback when DB locked)."""
        status_dir = self.db_path.parent / ".job_status"
        if not status_dir.exists():
            return []
        jobs = []
        for status_file in status_dir.glob("*.json"):
            try:
                data = json.loads(status_file.read_text())
                jobs.append(data)
            except Exception:
                continue
        return sorted(jobs, key=lambda x: x.get("updated_at", ""), reverse=True)

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
