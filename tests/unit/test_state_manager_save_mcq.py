import json
import tempfile
from pathlib import Path

from mcq_generator.state_manager import StateManager


def test_save_mcq_inserts_and_reads_synth_columns(tmp_path: Path):
    db_path = tmp_path / "test_state.duckdb"
    sm = StateManager(db_path=str(db_path))
    try:
        job_id = "job_test"
        sm.create_job(job_id=job_id, dataset_name="ds", target_questions=1, config={})

        mcq = {"question": "Q", "options": ["A", "B", "C"], "metadata": {}}
        sm.save_mcq(
            job_id=job_id,
            document_index=0,
            document_hash="h",
            mcq_data=mcq,
            quality_score=50.0,
            synth_columns=["col1", "col2"],
        )

        mcqs = sm.get_mcqs(job_id)
        assert len(mcqs) == 1
        row = mcqs[0]
        assert row.get("synth_columns") == ["col1", "col2"]
    finally:
        sm.close()
