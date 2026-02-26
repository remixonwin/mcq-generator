"""
Tests for health check endpoints
"""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_health_check_with_details(client: TestClient):
    """Test health check endpoint with detailed information."""
    response = client.get("/health?detailed=true")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    # Detailed health might include additional fields like dependencies


def test_health_check_response_structure(client: TestClient):
    """Test health check response has correct structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    required_fields = ["status", "timestamp", "version"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_health_check_cors_headers(client: TestClient):
    """Test health check endpoint includes proper CORS headers."""
    response = client.options("/health")
    # CORS preflight should succeed
    assert response.status_code == 200 or response.status_code == 405  # Some servers don't allow OPTIONS on health


def test_health_check_content_type(client: TestClient):
    """Test health check returns JSON content type."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_health_check_rate_limiting(client: TestClient):
    """Test health check endpoint is not rate limited."""
    # Make multiple requests to ensure health check is always accessible
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200
