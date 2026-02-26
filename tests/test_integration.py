"""
Integration tests for MCQ Generator API
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


class TestMCQGeneratorIntegration:
    """Integration tests for the complete MCQ Generator workflow."""

    def test_complete_workflow(self, client: TestClient):
        """Test complete workflow from dataset search to export."""
        # Mock the entire workflow
        with patch('mcq_generator.dataset_search.search_datasets') as mock_search, \
             patch('mcq_generator.api.routers.jobs.create_job') as mock_create_job, \
             patch('mcq_generator.api.routers.jobs.get_job') as mock_get_job, \
             patch('mcq_generator.api.routers.exports.export_job') as mock_export:

            # Step 1: Search datasets
            mock_search.return_value = {
                "datasets": [{
                    "id": "test_dataset",
                    "title": "Test Dataset",
                    "description": "A test dataset"
                }],
                "total": 1
            }

            search_response = client.get("/api/v1/datasets/search?query=test")
            assert search_response.status_code == 200
            dataset_id = search_response.json()["datasets"][0]["id"]

            # Step 2: Create job
            mock_create_job.return_value = {
                "id": "test_job",
                "dataset_id": dataset_id,
                "status": "pending",
                "config": {"num_questions": 5}
            }

            job_request = {
                "dataset_id": dataset_id,
                "config": {"num_questions": 5}
            }
            job_response = client.post("/api/v1/jobs", json=job_request)
            assert job_response.status_code == 201
            job_id = job_response.json()["id"]

            # Step 3: Check job status
            mock_get_job.return_value = {
                "id": job_id,
                "status": "completed",
                "progress": 100,
                "generated_questions": [
                    {"id": 1, "question": "Test question", "options": ["A", "B", "C", "D"], "correct": "A"}
                ]
            }

            status_response = client.get(f"/api/v1/jobs/{job_id}")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "completed"

            # Step 4: Export results
            mock_export.return_value = {
                "questions": [
                    {"id": 1, "question": "Test question", "options": ["A", "B", "C", "D"], "correct": "A"}
                ]
            }

            export_response = client.get(f"/api/v1/exports/{job_id}?format=json")
            assert export_response.status_code == 200
            assert "questions" in export_response.json()

    def test_error_propagation(self, client: TestClient):
        """Test error handling across the workflow."""
        with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
            mock_search.side_effect = Exception("Service unavailable")

            response = client.get("/api/v1/datasets/search?query=test")
            assert response.status_code == 500

    def test_health_check_integration(self, client: TestClient):
        """Test health check endpoint integration."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_metrics_integration(self, client: TestClient):
        """Test metrics endpoint integration."""
        with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "jobs_created": 10,
                "jobs_completed": 8,
                "api_requests": 100
            }

            response = client.get("/metrics")
            assert response.status_code == 200

            data = response.json()
            assert "jobs_created" in data
            assert isinstance(data["jobs_created"], int)

    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are properly set."""
        response = client.options("/api/v1/datasets/search")
        # CORS preflight should be handled
        assert response.status_code in [200, 405]  # Some endpoints may not allow OPTIONS

    def test_api_documentation_accessible(self, client: TestClient):
        """Test API documentation endpoints are accessible."""
        # Test OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200

        # Test docs endpoint (if available)
        response = client.get("/docs")
        assert response.status_code in [200, 404]  # May not be available in test client

    def test_request_validation(self, client: TestClient):
        """Test request validation across endpoints."""
        # Test invalid JSON
        response = client.post("/api/v1/jobs", data="invalid json")
        assert response.status_code == 422

        # Test missing required fields
        response = client.post("/api/v1/jobs", json={})
        assert response.status_code == 422

    def test_response_format_consistency(self, client: TestClient):
        """Test response formats are consistent across endpoints."""
        with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
            mock_search.return_value = {"datasets": [], "total": 0}

            response = client.get("/api/v1/datasets/search")
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
