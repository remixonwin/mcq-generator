#!/usr/bin/env python3
"""
Reconcile NDJSON -> DB and regenerate aggregated JSON for a job.

Usage: python scripts/reconcile_ndjson_to_db_and_json.py <job_id>

Actions:
 - Inserts any NDJSON entries missing in the DB, assigning document_index when needed.
 - Rebuilds .mcq_exports/<job_id>.json by deduplicating NDJSON by mcq_id (last wins).
 - Merges the rebuilt job JSON into root mcqs.json to keep the root aggregate up to date.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from src.mcq_generator.state_manager import StateManager
from src.mcq_generator.utils import merge_mcqs


def main(job_id: str, db_path: str = "mcq_state.duckdb"):
    export_dir = Path(".mcq_exports")
    ndpath = export_dir / f"{job_id}.ndjson"
    jsonpath = export_dir / f"{job_id}.json"

    if not ndpath.exists():
        print(f"NDJSON not found: {ndpath}")
        return

    s = StateManager(db_path=db_path)
    try:
        # Determine current max document_index for this job
        row = s.conn.execute(
            "SELECT COALESCE(MAX(document_index), -1) FROM mcq_results WHERE job_id = ?",
            [job_id],
        ).fetchone()
        max_idx = int(row[0]) if row and row[0] is not None else -1
        assign_next = max_idx + 1

        inserted = 0
        mapping = {}  # mcq_id -> entry (last wins)

        # Iterate NDJSON and insert missing rows
        with ndpath.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                md = entry.get("metadata", {}) or {}
                doc_idx = None
                if isinstance(md, dict) and md.get("document_index") is not None:
                    try:
                        doc_idx = int(md.get("document_index"))
                    except Exception:
                        doc_idx = None

                if doc_idx is None:
                    # Assign a sequential index to preserve uniqueness
                    doc_idx = assign_next
                    assign_next += 1

                mcq_id = f"{job_id}_mcq_{doc_idx}"

                # Dedup mapping (last occurrence wins)
                mapping[mcq_id] = entry

                row = s.conn.execute(
                    "SELECT COUNT(1) FROM mcq_results WHERE mcq_id = ?", [mcq_id]
                ).fetchone()
                exists = int(row[0]) if row else 0
                if exists:
                    continue

                # Insert row
                try:
                    s.conn.execute(
                        "INSERT INTO mcq_results (mcq_id, job_id, document_index, document_hash, mcq_json, quality_score) VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            mcq_id,
                            job_id,
                            doc_idx,
                            md.get("document_hash", ""),
                            json.dumps(entry, default=str),
                            float(entry.get("quality_score", 0.0)),
                        ],
                    )
                    inserted += 1
                except Exception as e:
                    print(f"Failed insert for {mcq_id}: {e}")

        # Sync generated_count
        s.sync_generated_count(job_id)

        # Rebuild aggregated JSON from mapping (last wins), preserving order of insertion by document_index when available
        # Sort by document_index extracted from keys where possible
        def sort_key(item):
            mcq_id, entry = item
            parts = mcq_id.rsplit("_", 1)
            try:
                return int(parts[-1])
            except Exception:
                return 10**12

        items = sorted(mapping.items(), key=sort_key)
        mcqs = [v for k, v in items]

        aggregated = {
            "generated_at": datetime.now().isoformat(),
            "dataset": None,
            "total_questions": len(mcqs),
            "mcqs": mcqs,
        }

        jsonpath.parent.mkdir(parents=True, exist_ok=True)
        tmp = jsonpath.with_suffix(jsonpath.suffix + ".tmp")
        tmp.write_text(json.dumps(aggregated, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(jsonpath)

        # Merge into root mcqs.json
        root = Path("mcqs.json")
        root_existing = None
        if root.exists():
            try:
                root_existing = json.loads(root.read_text(encoding="utf-8"))
            except Exception:
                root_existing = None

        merged = merge_mcqs(root_existing or {}, aggregated)
        tmp_root = root.with_suffix(root.suffix + ".tmp")
        tmp_root.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_root.replace(root)

        print(f"Done. Inserted {inserted} rows; aggregated json has {len(mcqs)} entries.")

    finally:
        s.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: reconcile_ndjson_to_db_and_json.py <job_id>")
        sys.exit(1)
    main(sys.argv[1])
