import json
from src.mcq_generator.state_manager import StateManager


def test_save_mcq_and_integrity(tmp_path):
    # Create a temporary DB location
    db_path = tmp_path / "mcq_state.duckdb"
    s = StateManager(db_path=str(db_path))
    job_id = "test_job"
    s.create_job(job_id=job_id, dataset_name="ds", target_questions=10)

    # Save an MCQ and verify mcq_results row and jobs.generated_count updated
    mcq = {
        "question": "Q",
        "options": ["A", "B", "C"],
        "correct_answer": 0,
        "explanation": "E",
        "metadata": {},
    }

    s.save_mcq(job_id=job_id, document_index=1, document_hash="h", mcq_data=mcq, quality_score=50.0)
    rows = s.count_mcq_rows(job_id)
    assert rows == 1
    progress = s.get_job_progress(job_id)
    assert progress["generated_count"] == 1

    # Calling save_mcq again for same document should not double count
    s.save_mcq(job_id=job_id, document_index=1, document_hash="h", mcq_data=mcq, quality_score=60.0)
    rows2 = s.count_mcq_rows(job_id)
    assert rows2 == 1
    progress2 = s.get_job_progress(job_id)
    assert progress2["generated_count"] == 1

    s.close()
