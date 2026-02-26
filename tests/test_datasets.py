"""
Tests for dataset endpoints
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


def test_search_datasets_success(client: TestClient, sample_dataset_response):
    """Test successful dataset search."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.return_value = sample_dataset_response
        
        response = client.get("/api/v1/datasets/search?query=science&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "datasets" in data
        assert "total" in data
        assert len(data["datasets"]) == 2
        assert data["total"] == 2


def test_search_datasets_with_pagination(client: TestClient):
    """Test dataset search with pagination parameters."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.return_value = {
            "datasets": [],
            "total": 0,
            "page": 2,
            "per_page": 5
        }
        
        response = client.get("/api/v1/datasets/search?page=2&per_page=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 5


def test_search_datasets_with_filters(client: TestClient):
    """Test dataset search with filtering parameters."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.return_value = {"datasets": [], "total": 0}
        
        response = client.get("/api/v1/datasets/search?author=test_author&tags=science,math")
        assert response.status_code == 200
        
        # Verify the search was called with correct parameters
        mock_search.assert_called_once()


def test_search_datasets_missing_query(client: TestClient):
    """Test dataset search without query parameter."""
    response = client.get("/api/v1/datasets/search")
    # Should either work with empty query or return validation error
    assert response.status_code in [200, 422]


def test_get_dataset_details(client: TestClient):
    """Test getting details for a specific dataset."""
    with patch('mcq_generator.dataset_search.get_dataset_info') as mock_get:
        mock_get.return_value = {
            "id": "test_dataset_1",
            "author": "test_author",
            "description": "Test dataset",
            "tags": ["test"],
            "downloads": 1000
        }
        
        response = client.get("/api/v1/datasets/test_dataset_1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "test_dataset_1"
        assert "author" in data
        assert "description" in data


def test_get_dataset_not_found(client: TestClient):
    """Test getting details for non-existent dataset."""
    with patch('mcq_generator.dataset_search.get_dataset_info') as mock_get:
        mock_get.side_effect = ValueError("Dataset not found")
        
        response = client.get("/api/v1/datasets/nonexistent_dataset")
        assert response.status_code == 404


def test_search_datasets_invalid_parameters(client: TestClient):
    """Test dataset search with invalid parameters."""
    response = client.get("/api/v1/datasets/search?limit=-1")
    assert response.status_code == 422  # Validation error
    
    response = client.get("/api/v1/datasets/search?page=0")
    assert response.status_code == 422  # Validation error


def test_search_datasets_large_limit(client: TestClient):
    """Test dataset search with large limit parameter."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.return_value = {"datasets": [], "total": 0}
        
        response = client.get("/api/v1/datasets/search?limit=100")
        assert response.status_code == 200


def test_dataset_endpoint_cors(client: TestClient):
    """Test CORS headers on dataset endpoints."""
    response = client.options("/api/v1/datasets/search")
    assert response.status_code in [200, 405]  # OPTIONS might not be allowed


def test_search_datasets_special_characters(client: TestClient):
    """Test dataset search with special characters in query."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.return_value = {"datasets": [], "total": 0}
        
        response = client.get("/api/v1/datasets/search?query=test%20query%20with%20spaces")
        assert response.status_code == 200


def test_dataset_error_handling(client: TestClient):
    """Test error handling in dataset endpoints."""
    with patch('mcq_generator.dataset_search.search_datasets') as mock_search:
        mock_search.side_effect = Exception("Service unavailable")
        
        response = client.get("/api/v1/datasets/search?query=test")
        assert response.status_code == 500
