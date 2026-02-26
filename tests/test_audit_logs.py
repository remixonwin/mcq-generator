"""
Tests for audit logs endpoints
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


def test_get_audit_logs_success(client: TestClient):
    """Test successful audit logs retrieval."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [
                {
                    "id": "log_1",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "action": "job_created",
                    "user_id": "user_123",
                    "resource_id": "job_456",
                    "details": {"dataset_id": "test_dataset"}
                },
                {
                    "id": "log_2",
                    "timestamp": "2024-01-01T01:00:00Z",
                    "action": "job_completed",
                    "user_id": "user_123",
                    "resource_id": "job_456",
                    "details": {"questions_generated": 10}
                }
            ],
            "total": 2,
            "page": 1,
            "per_page": 10
        }
        
        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert len(data["logs"]) == 2


def test_get_audit_logs_with_filters(client: TestClient):
    """Test audit logs with filtering parameters."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [],
            "total": 0,
            "page": 1,
            "per_page": 10
        }
        
        response = client.get("/api/v1/audit-logs?action=job_created&user_id=user_123&limit=5")
        assert response.status_code == 200


def test_get_audit_logs_with_date_range(client: TestClient):
    """Test audit logs with date range filtering."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [],
            "total": 0,
            "page": 1,
            "per_page": 10
        }
        
        response = client.get("/api/v1/audit-logs?start_date=2024-01-01&end_date=2024-01-31")
        assert response.status_code == 200


def test_get_audit_logs_pagination(client: TestClient):
    """Test audit logs pagination."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [],
            "total": 100,
            "page": 2,
            "per_page": 20
        }
        
        response = client.get("/api/v1/audit-logs?page=2&per_page=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 20


def test_get_audit_log_by_id(client: TestClient):
    """Test getting a specific audit log by ID."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_log') as mock_log:
        mock_log.return_value = {
            "id": "log_1",
            "timestamp": "2024-01-01T00:00:00Z",
            "action": "job_created",
            "user_id": "user_123",
            "resource_id": "job_456",
            "details": {"dataset_id": "test_dataset"},
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0..."
        }
        
        response = client.get("/api/v1/audit-logs/log_1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "log_1"
        assert "timestamp" in data
        assert "action" in data


def test_get_audit_log_not_found(client: TestClient):
    """Test getting non-existent audit log."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_log') as mock_log:
        mock_log.side_effect = ValueError("Audit log not found")
        
        response = client.get("/api/v1/audit-logs/nonexistent_log")
        assert response.status_code == 404


def test_audit_logs_response_structure(client: TestClient):
    """Test audit logs response has correct structure."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [
                {
                    "id": "log_1",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "action": "job_created",
                    "user_id": "user_123",
                    "resource_id": "job_456",
                    "details": {}
                }
            ],
            "total": 1,
            "page": 1,
            "per_page": 10
        }
        
        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        
        data = response.json()
        log_entry = data["logs"][0]
        required_fields = ["id", "timestamp", "action", "user_id"]
        for field in required_fields:
            assert field in log_entry


def test_audit_logs_invalid_parameters(client: TestClient):
    """Test audit logs with invalid parameters."""
    response = client.get("/api/v1/audit-logs?page=-1")
    assert response.status_code == 422  # Validation error
    
    response = client.get("/api/v1/audit-logs?per_page=0")
    assert response.status_code == 422  # Validation error


def test_audit_logs_invalid_date_format(client: TestClient):
    """Test audit logs with invalid date format."""
    response = client.get("/api/v1/audit-logs?start_date=invalid-date")
    assert response.status_code == 422  # Validation error


def test_audit_logs_error_handling(client: TestClient):
    """Test error handling in audit logs endpoints."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.side_effect = Exception("Database connection failed")
        
        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 500


def test_audit_logs_empty_result(client: TestClient):
    """Test audit logs when no logs exist."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [],
            "total": 0,
            "page": 1,
            "per_page": 10
        }
        
        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["logs"]) == 0
        assert data["total"] == 0


def test_audit_logs_content_type(client: TestClient):
    """Test audit logs endpoint returns JSON content type."""
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_audit_logs_action_filter(client: TestClient):
    """Test filtering audit logs by action type."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [
                {
                    "id": "log_1",
                    "action": "job_created",
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            ],
            "total": 1
        }
        
        response = client.get("/api/v1/audit-logs?action=job_created")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["action"] == "job_created"


def test_audit_logs_user_filter(client: TestClient):
    """Test filtering audit logs by user ID."""
    with patch('mcq_generator.api.routers.audit_logs.get_audit_logs') as mock_logs:
        mock_logs.return_value = {
            "logs": [
                {
                    "id": "log_1",
                    "user_id": "user_123",
                    "action": "job_created",
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            ],
            "total": 1
        }
        
        response = client.get("/api/v1/audit-logs?user_id=user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["user_id"] == "user_123"
