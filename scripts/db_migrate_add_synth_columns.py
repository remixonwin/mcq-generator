#!/usr/bin/env python3
"""Database migration helper: add `synth_columns` JSON column to tables.

This script is best-effort and safe to run repeatedly. It will make a
backup copy of the DuckDB file before attempting ALTER statements and will
ignore errors that indicate the column already exists. Use it when you want
to ensure older DB files get the new schema field for per-MCQ traceability.
"""

import shutil
import sys
from pathlib import Path

try:
    import duckdb
except Exception:
    print("duckdb is required to run this script. Install with `pip install duckdb`.")
    raise


def backup(db_path: Path) -> Path:
    bak = db_path.with_suffix(db_path.suffix + ".bak")
    try:
        shutil.copy2(db_path, bak)
        print(f"Backup created at {bak}")
    except Exception as e:
        print(f"Failed to create backup: {e}")
    return bak


def migrate(db_path: Path):
    if not db_path.exists():
        print(f"DB file {db_path} does not exist")
        return

    backup(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        print("Attempting to add synth_columns column to checkpoints...")
        try:
            conn.execute("ALTER TABLE checkpoints ADD COLUMN IF NOT EXISTS synth_columns JSON")
            print("checkpoints: ALTER attempted (IF NOT EXISTS)")
        except Exception:
            try:
                conn.execute("ALTER TABLE checkpoints ADD COLUMN synth_columns JSON")
                print("checkpoints: ALTER attempted")
            except Exception as e:
                print(f"checkpoints: ALTER failed or not supported: {e}")

        print("Attempting to add synth_columns column to mcq_results...")
        try:
            conn.execute("ALTER TABLE mcq_results ADD COLUMN IF NOT EXISTS synth_columns JSON")
            print("mcq_results: ALTER attempted (IF NOT EXISTS)")
        except Exception:
            try:
                conn.execute("ALTER TABLE mcq_results ADD COLUMN synth_columns JSON")
                print("mcq_results: ALTER attempted")
            except Exception as e:
                print(f"mcq_results: ALTER failed or not supported: {e}")

        print(
            "Migration complete. If errors were reported, inspect the DB and restore the .bak file if needed."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/mcq_state.duckdb")
    migrate(path)
