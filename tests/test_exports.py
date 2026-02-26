"""
Tests for export endpoints
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


def test_export_json_success(client: TestClient):
    """Test successful JSON export."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = {
            "job_id": "test_job",
            "format": "json",
            "data": {
                "questions": [
                    {
                        "id": 1,
                        "question": "What is 2+2?",
                        "options": ["3", "4", "5", "6"],
                        "correct_answer": "4"
                    }
                ]
            }
        }
        
        response = client.get("/api/v1/exports/test_job?format=json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


def test_export_csv_success(client: TestClient):
    """Test successful CSV export."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = "question,option_a,option_b,option_c,option_d,correct_answer\nWhat is 2+2?,3,4,5,6,4\n"
        
        response = client.get("/api/v1/exports/test_job?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]


def test_export_markdown_success(client: TestClient):
    """Test successful Markdown export."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = "# MCQ Questions\n\n## Question 1\nWhat is 2+2?\n\n- A) 3\n- B) 4\n- C) 5\n- D) 6\n\n**Correct Answer:** B\n"
        
        response = client.get("/api/v1/exports/test_job?format=markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]


def test_export_pdf_success(client: TestClient):
    """Test successful PDF export."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = b"fake_pdf_content"
        
        response = client.get("/api/v1/exports/test_job?format=pdf")
        assert response.status_code == 200
        assert "application/pdf" in response.headers["content-type"]


def test_export_invalid_format(client: TestClient):
    """Test export with invalid format."""
    response = client.get("/api/v1/exports/test_job?format=invalid")
    assert response.status_code == 422  # Validation error


def test_export_missing_format(client: TestClient):
    """Test export without format parameter."""
    response = client.get("/api/v1/exports/test_job")
    # Should either default to JSON or return validation error
    assert response.status_code in [200, 422]


def test_export_job_not_found(client: TestClient):
    """Test export for non-existent job."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.side_effect = ValueError("Job not found")
        
        response = client.get("/api/v1/exports/nonexistent_job?format=json")
        assert response.status_code == 404


def test_export_job_incomplete(client: TestClient):
    """Test export for incomplete job."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.side_effect = ValueError("Job not completed")
        
        response = client.get("/api/v1/exports/incomplete_job?format=json")
        assert response.status_code == 400


def test_export_with_custom_filename(client: TestClient):
    """Test export with custom filename parameter."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = {"data": "test"}
        
        response = client.get("/api/v1/exports/test_job?format=json&filename=my_questions")
        assert response.status_code == 200
        
        # Check if filename is set in headers
        content_disposition = response.headers.get("content-disposition", "")
        assert "my_questions" in content_disposition or "attachment" in content_disposition


def test_export_list_formats(client: TestClient):
    """Test listing available export formats."""
    response = client.get("/api/v1/exports/formats")
    assert response.status_code == 200
    
    data = response.json()
    assert "formats" in data
    assert isinstance(data["formats"], list)
    # Should include common formats
    expected_formats = ["json", "csv", "markdown", "pdf"]
    for fmt in expected_formats:
        assert fmt in data["formats"]


def test_export_error_handling(client: TestClient):
    """Test error handling in export endpoints."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.side_effect = Exception("Export service unavailable")
        
        response = client.get("/api/v1/exports/test_job?format=json")
        assert response.status_code == 500


def test_export_large_dataset(client: TestClient):
    """Test export handling for large datasets."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        # Simulate large export
        large_data = {
            "questions": [{"id": i, "question": f"Question {i}"} for i in range(1000)]
        }
        mock_export.return_value = large_data
        
        response = client.get("/api/v1/exports/large_job?format=json")
        assert response.status_code == 200


def test_export_with_filters(client: TestClient):
    """Test export with filtering options."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = {"questions": []}
        
        response = client.get("/api/v1/exports/test_job?format=json&difficulty=medium&topics=science")
        assert response.status_code == 200


def test_export_content_encoding(client: TestClient):
    """Test export content encoding headers."""
    with patch('mcq_generator.api.routers.exports.export_job') as mock_export:
        mock_export.return_value = {"data": "test"}
        
        response = client.get("/api/v1/exports/test_job?format=json")
        assert response.status_code == 200
        # Should have proper encoding headers
        assert "charset" in response.headers.get("content-type", "").lower()
