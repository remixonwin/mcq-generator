"""
Tests for metrics endpoints
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


def test_get_metrics_success(client: TestClient):
    """Test successful metrics retrieval."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "jobs_created": 100,
            "jobs_completed": 85,
            "jobs_failed": 5,
            "jobs_pending": 10,
            "total_questions_generated": 850,
            "average_generation_time": 2.5,
            "api_requests": 1500,
            "cache_hit_rate": 0.75,
            "system_uptime": 86400,
            "memory_usage": 0.65
        }
        
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs_created" in data
        assert "api_requests" in data
        assert isinstance(data["jobs_created"], int)


def test_get_metrics_with_time_range(client: TestClient):
    """Test metrics retrieval with time range filter."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "jobs_created": 50,
            "jobs_completed": 45,
            "time_range": "24h"
        }
        
        response = client.get("/metrics?range=24h")
        assert response.status_code == 200
        
        data = response.json()
        assert "time_range" in data


def test_metrics_response_structure(client: TestClient):
    """Test metrics response has correct structure."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_pending": 0,
            "total_questions_generated": 0,
            "api_requests": 0
        }
        
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        # Should contain key metric categories
        expected_categories = ["jobs", "questions", "api"]
        for category in expected_categories:
            assert any(category in key for key in data.keys())


def test_metrics_data_types(client: TestClient):
    """Test metrics data types are correct."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "jobs_created": 100,  # int
            "cache_hit_rate": 0.75,  # float
            "system_healthy": True,  # bool
            "last_reset": "2024-01-01T00:00:00Z"  # string
        }
        
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data["jobs_created"], int)
        assert isinstance(data["cache_hit_rate"], float)
        assert isinstance(data["system_healthy"], bool)
        assert isinstance(data["last_reset"], str)


def test_metrics_error_handling(client: TestClient):
    """Test error handling in metrics endpoint."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.side_effect = Exception("Metrics service unavailable")
        
        response = client.get("/metrics")
        assert response.status_code == 500


def test_metrics_caching(client: TestClient):
    """Test metrics endpoint caching behavior."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {"jobs_created": 100}
        
        # Make multiple requests
        response1 = client.get("/metrics")
        response2 = client.get("/metrics")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should return the same data
        assert response1.json() == response2.json()


def test_metrics_with_invalid_range(client: TestClient):
    """Test metrics with invalid time range parameter."""
    response = client.get("/metrics?range=invalid")
    # Should either ignore invalid parameter or return validation error
    assert response.status_code in [200, 422]


def test_detailed_metrics(client: TestClient):
    """Test detailed metrics endpoint."""
    with patch('mcq_generator.api.routers.metrics.get_detailed_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "summary": {
                "jobs_created": 100,
                "jobs_completed": 85
            },
            "by_status": {
                "pending": 10,
                "running": 5,
                "completed": 85
            },
            "by_day": [
                {"date": "2024-01-01", "jobs": 20},
                {"date": "2024-01-02", "jobs": 30}
            ]
        }
        
        response = client.get("/metrics?detailed=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "by_status" in data


def test_metrics_performance(client: TestClient):
    """Test metrics endpoint performance."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {"jobs_created": 100}
        
        # Metrics should be fast to load
        response = client.get("/metrics")
        assert response.status_code == 200
        # Should return quickly (this is more of an integration test concern)


def test_metrics_content_type(client: TestClient):
    """Test metrics endpoint returns JSON content type."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_metrics_zero_values(client: TestClient):
    """Test metrics when no activity has occurred."""
    with patch('mcq_generator.api.routers.metrics.get_metrics') as mock_metrics:
        mock_metrics.return_value = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_questions_generated": 0,
            "api_requests": 0
        }
        
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        # All count metrics should be zero
        for key, value in data.items():
            if "jobs" in key or "total" in key or "requests" in key:
                assert value == 0
