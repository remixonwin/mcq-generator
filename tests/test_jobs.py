"""
Tests for job management endpoints
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_job_success(client: TestClient, sample_job_request, sample_job_response):
    """Test successful job creation."""
    with patch('mcq_generator.api.routers.jobs.create_job') as mock_create:
        mock_create.return_value = sample_job_response

        response = client.post("/api/v1/jobs", json=sample_job_request)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["dataset_id"] == sample_job_request["dataset_id"]
        assert data["status"] == "pending"


def test_create_job_invalid_request(client: TestClient):
    """Test job creation with invalid request data."""
    invalid_request = {
        "dataset_id": "",  # Empty dataset_id
        "config": {
            "num_questions": -1  # Invalid negative number
        }
    }

    response = client.post("/api/v1/jobs", json=invalid_request)
    assert response.status_code == 422  # Validation error


def test_create_job_missing_fields(client: TestClient):
    """Test job creation with missing required fields."""
    incomplete_request = {
        "dataset_id": "test_dataset"
        # Missing config field
    }

    response = client.post("/api/v1/jobs", json=incomplete_request)
    assert response.status_code == 422


def test_get_job_success(client: TestClient, sample_job_response):
    """Test getting job details successfully."""
    with patch('mcq_generator.api.routers.jobs.get_job') as mock_get:
        mock_get.return_value = sample_job_response

        response = client.get(f"/api/v1/jobs/{sample_job_response['id']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == sample_job_response["id"]
        assert "status" in data
        assert "progress" in data


def test_get_job_not_found(client: TestClient):
    """Test getting details for non-existent job."""
    with patch('mcq_generator.api.routers.jobs.get_job') as mock_get:
        mock_get.side_effect = ValueError("Job not found")

        response = client.get("/api/v1/jobs/nonexistent_job")
        assert response.status_code == 404


def test_list_jobs_success(client: TestClient):
    """Test listing jobs successfully."""
    with patch('mcq_generator.api.routers.jobs.list_jobs') as mock_list:
        mock_list.return_value = {
            "jobs": [
                {
                    "id": "job1",
                    "status": "completed",
                    "created_at": "2024-01-01T00:00:00.000Z"
                },
                {
                    "id": "job2",
                    "status": "pending",
                    "created_at": "2024-01-02T00:00:00.000Z"
                }
            ],
            "total": 2,
            "page": 1,
            "per_page": 10
        }

        response = client.get("/api/v1/jobs")
        assert response.status_code == 200

        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert len(data["jobs"]) == 2


def test_list_jobs_with_filters(client: TestClient):
    """Test listing jobs with status and date filters."""
    with patch('mcq_generator.api.routers.jobs.list_jobs') as mock_list:
        mock_list.return_value = {"jobs": [], "total": 0, "page": 1, "per_page": 10}

        response = client.get("/api/v1/jobs?status=completed&limit=5")
        assert response.status_code == 200


def test_update_job_status_success(client: TestClient):
    """Test updating job status successfully."""
    with patch('mcq_generator.api.routers.jobs.update_job_status') as mock_update:
        mock_update.return_value = {
            "id": "test_job",
            "status": "paused",
            "updated_at": "2024-01-01T00:00:00.000Z"
        }

        response = client.put("/api/v1/jobs/test_job/status", json={"status": "paused"})
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "paused"


def test_update_job_status_invalid(client: TestClient):
    """Test updating job status with invalid status."""
    response = client.put("/api/v1/jobs/test_job/status", json={"status": "invalid_status"})
    assert response.status_code == 422


def test_delete_job_success(client: TestClient):
    """Test deleting a job successfully."""
    with patch('mcq_generator.api.routers.jobs.delete_job') as mock_delete:
        mock_delete.return_value = {"message": "Job deleted successfully"}

        response = client.delete("/api/v1/jobs/test_job")
        assert response.status_code == 200


def test_delete_job_not_found(client: TestClient):
    """Test deleting a non-existent job."""
    with patch('mcq_generator.api.routers.jobs.delete_job') as mock_delete:
        mock_delete.side_effect = ValueError("Job not found")

        response = client.delete("/api/v1/jobs/nonexistent_job")
        assert response.status_code == 404


def test_job_progress_update(client: TestClient):
    """Test job progress updates."""
    with patch('mcq_generator.api.routers.jobs.get_job_progress') as mock_progress:
        mock_progress.return_value = {
            "job_id": "test_job",
            "progress": 50,
            "total_questions": 100,
            "generated_questions": 50,
            "current_stage": "generating"
        }

        response = client.get("/api/v1/jobs/test_job/progress")
        assert response.status_code == 200

        data = response.json()
        assert "progress" in data
        assert "current_stage" in data


def test_job_error_handling(client: TestClient):
    """Test error handling in job endpoints."""
    with patch('mcq_generator.api.routers.jobs.create_job') as mock_create:
        mock_create.side_effect = Exception("Service unavailable")

        response = client.post("/api/v1/jobs", json={
            "dataset_id": "test",
            "config": {"num_questions": 10}
        })
        assert response.status_code == 500


def test_job_pagination(client: TestClient):
    """Test job listing pagination."""
    with patch('mcq_generator.api.routers.jobs.list_jobs') as mock_list:
        mock_list.return_value = {
            "jobs": [],
            "total": 100,
            "page": 2,
            "per_page": 10
        }

        response = client.get("/api/v1/jobs?page=2&per_page=10")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 10
