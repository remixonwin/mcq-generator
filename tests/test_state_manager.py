"""
Tests for state_manager module.
"""

import pytest
import os
from mcq_generator.state_manager import StateManager


class TestStateManager:
    """Test suite for StateManager."""

    def test_initialization(self, temp_dir):
        """Test StateManager initialization creates database."""
        db_path = str(temp_dir / "test.duckdb")
        manager = StateManager(db_path=db_path)

        assert os.path.exists(db_path)
        manager.close()

    def test_create_job(self, state_manager):
        """Test creating a new job."""
        job_id = "test_job_001"

        result = state_manager.create_job(
            job_id=job_id,
            dataset_name="test/dataset",
            target_questions=10,
        )

        assert result == job_id

        job = state_manager.get_job_progress(job_id)
        assert job["job_id"] == job_id
        assert job["status"] == "pending"

    def test_update_job_status(self, state_manager):
        """Test updating job status."""
        job_id = "test_job_002"
        state_manager.create_job(job_id, "test/dataset", 10)

        state_manager.update_job_status(job_id, "running")

        job = state_manager.get_job_progress(job_id)
        assert job["status"] == "running"

    def test_save_checkpoint(self, state_manager):
        """Test saving a checkpoint."""
        job_id = "test_job_003"
        state_manager.create_job(job_id, "test/dataset", 10)

        state_manager.save_checkpoint(
            job_id=job_id,
            last_processed_index=5,
            document_indices=[0, 1, 2, 3, 4],
            cache_stats={"hits": 10},
            metrics={"generated_count": 3},
        )

        checkpoint = state_manager.get_latest_checkpoint(job_id)
        assert checkpoint is not None
        assert checkpoint["last_processed_index"] == 5

    def test_get_latest_checkpoint_no_checkpoint(self, state_manager):
        """Test getting latest checkpoint when none exists."""
        job_id = "test_job_004"
        state_manager.create_job(job_id, "test/dataset", 10)

        checkpoint = state_manager.get_latest_checkpoint(job_id)
        assert checkpoint is None

    def test_save_mcq(self, state_manager, sample_mcq_dict):
        """Test saving an MCQ."""
        job_id = "test_job_005"
        state_manager.create_job(job_id, "test/dataset", 10)

        state_manager.save_mcq(
            job_id=job_id,
            document_index=0,
            document_hash="abc123",
            mcq_data=sample_mcq_dict,
            quality_score=85.0,
        )

        mcqs = state_manager.get_mcqs(job_id)
        assert len(mcqs) == 1
        assert mcqs[0]["question"] == sample_mcq_dict["question"]

    def test_get_job_progress(self, state_manager):
        """Test retrieving job progress."""
        job_id = "test_job_006"
        state_manager.create_job(job_id, "test/dataset", 10)

        state_manager.save_mcq(
            job_id=job_id,
            document_index=0,
            document_hash="hash1",
            mcq_data={
                "question": "Q1",
                "options": [],
                "correct_answer": 0,
                "metadata": {},
                "explanation": "",
            },
            quality_score=80.0,
        )

        progress = state_manager.get_job_progress(job_id)

        assert progress["generated_count"] == 1
        assert progress["target_questions"] == 10

    def test_list_jobs(self, state_manager):
        """Test listing jobs."""
        state_manager.create_job("job_1", "dataset1", 10)
        state_manager.create_job("job_2", "dataset2", 20)

        jobs = state_manager.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_by_status(self, state_manager):
        """Test listing jobs filtered by status."""
        state_manager.create_job("job_1", "dataset1", 10)
        state_manager.create_job("job_2", "dataset2", 20)

        state_manager.update_job_status("job_1", "running")

        running = state_manager.list_jobs(status="running")
        assert len(running) == 1
        assert running[0]["job_id"] == "job_1"

    def test_get_statistics(self, state_manager):
        """Test getting overall statistics."""
        state_manager.create_job("job_1", "dataset1", 10)
        state_manager.update_job_status("job_1", "completed")
        state_manager.create_job("job_2", "dataset2", 20)
        state_manager.update_job_status("job_2", "running")

        stats = state_manager.get_statistics()

        assert stats["total_jobs"] == 2
        assert stats["completed_jobs"] == 1
        assert stats["running_jobs"] == 1

    def test_cleanup_old_checkpoints(self, state_manager):
        """Test cleaning up old checkpoints."""
        import time
        import uuid

        job_id = "test_job_cleanup_" + str(uuid.uuid4())[:8]
        state_manager.create_job(job_id, "test/dataset", 10)

        for i in range(3):
            checkpoint_id = f"{job_id}_cp_{i}"
            state_manager.conn.execute(
                """
                INSERT INTO checkpoints (checkpoint_id, job_id, last_processed_index, document_indices, cache_stats, metrics)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    checkpoint_id,
                    job_id,
                    i,
                    list(range(i)),
                    "{}",
                    "{}",
                ],
            )

        state_manager.cleanup_old_checkpoints(job_id, keep_last_n=2)

        checkpoint = state_manager.get_latest_checkpoint(job_id)
        assert checkpoint is not None

    def test_get_mcqs_for_nonexistent_job(self, state_manager):
        """Test getting MCQs for nonexistent job returns empty list."""
        mcqs = state_manager.get_mcqs("nonexistent_job")
        assert mcqs == []

    def test_get_job_progress_nonexistent_job(self, state_manager):
        """Test getting progress for nonexistent job raises error."""
        with pytest.raises(ValueError, match="not found"):
            state_manager.get_job_progress("nonexistent_job")

    def test_context_manager(self, temp_dir):
        """Test StateManager as context manager."""
        db_path = str(temp_dir / "ctx.duckdb")
        with StateManager(db_path=db_path) as manager:
            assert manager is not None
            manager.create_job("ctx_job", "dataset", 5)

        assert os.path.exists(db_path)

    def test_job_completion_timestamp(self, state_manager):
        """Test that completed jobs have completion timestamp."""
        job_id = "test_job_008"
        state_manager.create_job(job_id, "test/dataset", 10)

        state_manager.update_job_status(job_id, "completed")

        job = state_manager.get_job_progress(job_id)
        assert job["completed_at"] is not None
