import os
import json
from fastapi.testclient import TestClient

from mcq_generator.api import app


client = TestClient(app)


def test_search_endpoint():
    resp = client.get("/search", params={"q": "test", "limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


def test_jobs_and_stats_flow():
    # Create a simple generate job (dev fallback runs inline)
    resp = client.post("/generate", json={"dataset": "test_dataset", "questions": 0})
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # Check job listing and detail
    resp2 = client.get("/jobs")
    assert resp2.status_code == 200
    jobs = resp2.json().get("jobs", [])
    assert any(j["job_id"] == job_id for j in jobs)

    resp3 = client.get(f"/jobs/{job_id}")
    assert resp3.status_code == 200

    # Stats endpoint
    resp4 = client.get("/stats")
    assert resp4.status_code == 200
