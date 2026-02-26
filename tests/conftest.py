"""
Pytest configuration and fixtures for MCQ Generator tests
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from mcq_generator.api.main import create_app
from mcq_generator.config import config


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = create_app()
    app.dependency_overrides.clear()
    return app


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create an async test client for the FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    mock_cfg = Mock(spec=config)
    mock_cfg.HF_TOKEN = "test_hf_token"
    mock_cfg.GROQ_API_KEY = "test_groq_key"
    mock_cfg.OPENROUTER_API_KEY = "test_openrouter_key"
    mock_cfg.GEMINI_API_KEY = "test_gemini_key"
    mock_cfg.LLM_MODEL = "gpt-4"
    mock_cfg.PROVIDER_URL = "http://localhost:7330"
    mock_cfg.CONSECUTIVE_FAILURE_LIMIT = 10
    mock_cfg.BACKOFF_INITIAL_SECONDS = 1
    mock_cfg.BACKOFF_MULTIPLIER = 2
    mock_cfg.BACKOFF_MAX_SECONDS = 60
    mock_cfg.BACKOFF_TRIGGER = 5
    mock_cfg.COUNT_CONTENT_FAILURES = False
    mock_cfg.TEXT_COLUMN_WHITELIST = ["text", "content", "title"]
    mock_cfg.MAX_SYNTH_COLUMNS = 3
    mock_cfg.CONTENT_FAILURE_LIMIT = 50
    mock_cfg.DUMP_RETENTION = 50
    return mock_cfg


@pytest.fixture
def sample_dataset_response():
    """Sample dataset search response."""
    return {
        "datasets": [
            {
                "id": "test_dataset_1",
                "author": "test_author",
                "downloads": 1000,
                "likes": 50,
                "last_modified": "2024-01-01T00:00:00.000Z",
                "tags": ["test", "dataset"],
                "title": "Test Dataset 1",
                "description": "A test dataset for testing purposes"
            },
            {
                "id": "test_dataset_2",
                "author": "another_author",
                "downloads": 500,
                "likes": 25,
                "last_modified": "2024-01-02T00:00:00.000Z",
                "tags": ["test", "another"],
                "title": "Test Dataset 2",
                "description": "Another test dataset"
            }
        ],
        "total": 2,
        "page": 1,
        "per_page": 10
    }


@pytest.fixture
def sample_job_request():
    """Sample job creation request."""
    return {
        "dataset_id": "test_dataset_1",
        "config": {
            "num_questions": 10,
            "difficulty": "medium",
            "topics": ["science", "mathematics"]
        }
    }


@pytest.fixture
def sample_job_response():
    """Sample job response."""
    return {
        "id": "test_job_123",
        "dataset_id": "test_dataset_1",
        "status": "pending",
        "config": {
            "num_questions": 10,
            "difficulty": "medium",
            "topics": ["science", "mathematics"]
        },
        "created_at": "2024-01-01T00:00:00.000Z",
        "updated_at": "2024-01-01T00:00:00.000Z",
        "progress": 0,
        "total_questions": 10,
        "generated_questions": []
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = Mock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.ping = AsyncMock(return_value=True)
    return mock_redis


@pytest.fixture
def mock_celery():
    """Mock Celery app for testing."""
    mock_celery = Mock()
    mock_task = Mock()
    mock_task.delay = Mock(return_value=Mock(id="test_task_id"))
    mock_celery.send_task = Mock(return_value=Mock(id="test_task_id"))
    return mock_celery, mock_task
