import threading
import time
import json

import pytest
from fastapi.testclient import TestClient

from mcq_generator import api as api_module


def start_mock_provider_thread():
    # Reuse the module's server but skip if port already in use (another test run)
    from scripts.mock_provider import run as run_mock

    try:
        t = threading.Thread(target=run_mock, kwargs={"port": 7543}, daemon=True)
        t.start()
        # Give server a moment to start
        time.sleep(0.5)
        return t
    except OSError:
        # Port in use: assume a provider already running and continue
        return None


class FakeDataset:
    def __init__(self, rows, column_names):
        self._rows = rows
        self.column_names = column_names

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, idx):
        return self._rows[idx]


def test_e2e_generation_with_mock_provider(monkeypatch, tmp_path):
    # Start mock provider
    start_mock_provider_thread()

    # Use a temporary DB for this test to avoid using the repo's DB file which
    # may be invalid in CI/dev environments. StateManager reads MCQ_DB_PATH.
    monkeypatch.setenv("MCQ_DB_PATH", str(tmp_path / "mcq_state.duckdb"))

    # Patch load_dataset to return a small fake dataset without a 'text' column
    import mcq_generator.generator as gen_mod

    rows = [
        {"col1": "Alice in Wonderland", "col2": "1865"},
        {"col1": "Through the Looking-Glass", "col2": "1871"},
    ]

    fake_ds = FakeDataset(rows, column_names=["col1", "col2"])

    monkeypatch.setattr(gen_mod, "load_dataset", lambda name, split, token=None: fake_ds)
    # Bypass heavy filtering in tests so small synthesized docs are processed
    monkeypatch.setattr(gen_mod.DocumentFilter, "should_process", lambda self, text: True)

    client = TestClient(api_module.app)

    # Create job: request generation with missing text_column to trigger synthesis
    payload = {
        "dataset": "fake_dataset",
        "questions": 1,
        "provider_url": "http://127.0.0.1:7543",
        "text_column": "missing",
    }

    r = client.post("/generate", json=payload)
    assert r.status_code == 202
    data = r.json()
    job_id = data["job_id"]

    # Poll for completion (with timeout)
    timeout = 20
    start = time.time()
    progress = None
    while time.time() - start < timeout:
        pr = client.get(f"/jobs/{job_id}")
        assert pr.status_code == 200
        progress = pr.json()
        if progress.get("status") == "completed":
            break
        time.sleep(0.5)

    assert progress is not None
    assert progress.get("status") == "completed"

    # Check that either synth_columns were persisted (synthesis mode) or
    # a text_column was selected and persisted (normal string-column mode).
    assert "synth_columns" in progress
    if progress.get("synth_columns") is None:
        # Fallback: ensure text_column was persisted and is one of the dataset cols
        assert progress.get("text_column") in ("col1", "col2")

    # Verify mcq rows exist in DB and include synth_columns
    from mcq_generator.state_manager import StateManager

    sm = StateManager()
    try:
        mcqs = sm.get_mcqs(job_id)
        assert len(mcqs) > 0
        for m in mcqs:
            # Each exported MCQ should include synth_columns when present
            assert "synth_columns" in m or progress.get("synth_columns") is None
    finally:
        sm.close()
