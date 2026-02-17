"""
Shared fixtures for mcq_generator tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from mcq_generator.generator import MCQ, MCQMetadata, MCQGenerator
from mcq_generator.cache_manager import CacheManager, DuplicateDetector
from mcq_generator.state_manager import StateManager
from mcq_generator.filters import DocumentFilter, QualityScorer
from mcq_generator.provider_client import ProviderClient


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_mcq_metadata():
    """Create sample MCQ metadata."""
    return MCQMetadata(
        source_document="test_doc_1",
        source_id="test_1",
        source_url="https://example.com/test",
        document_hash="abc123",
        specific_names=["John Doe", "Jane Smith"],
        specific_places=["New York", "Paris"],
        specific_dates=["2024-01-15"],
        specific_events=["World Cup"],
        timestamp=datetime.now().isoformat(),
        difficulty="Medium",
        topic_category="General Knowledge",
        quality_score=85.0,
    )


@pytest.fixture
def sample_mcq(sample_mcq_metadata):
    """Create a sample MCQ object."""
    return MCQ(
        question="What is the capital of France?",
        options=["London", "Paris", "Berlin"],
        correct_answer=1,
        explanation="Paris is the capital and most populous city of France.",
        metadata=sample_mcq_metadata,
        source_text="France is a country in Western Europe. Its capital is Paris.",
    )


@pytest.fixture
def sample_mcq_dict(sample_mcq):
    """Convert sample MCQ to dictionary."""
    return sample_mcq.to_dict()


@pytest.fixture
def mock_provider_client():
    """Create a mocked ProviderClient."""
    mock = MagicMock(spec=ProviderClient)
    mock.generate = AsyncMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "content": """QUESTION: What is 2+2?
A) 3
B) 4
C) 5
CORRECT: B
EXPLANATION: 2+2 equals 4.
NAMES: 
PLACES: 
DATES: 
EVENTS: 
DIFFICULTY: Easy
TOPIC: Mathematics"""
                    }
                }
            ]
        }
    )
    mock.health_check = AsyncMock(return_value=True)
    mock.get_stats = MagicMock(
        return_value={
            "total_requests": 10,
            "successful_requests": 9,
            "failed_requests": 1,
            "success_rate": 90.0,
        }
    )
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def cache_manager(temp_dir):
    """Create a CacheManager with temporary directory."""
    return CacheManager(cache_dir=str(temp_dir / "cache"))


@pytest.fixture
def state_manager(temp_dir):
    """Create a StateManager with temporary database."""
    return StateManager(db_path=str(temp_dir / "test_state.duckdb"))


@pytest.fixture
def document_filter():
    """Create a DocumentFilter with default settings."""
    return DocumentFilter()


@pytest.fixture
def quality_scorer():
    """Create a QualityScorer."""
    return QualityScorer()


@pytest.fixture
def duplicate_detector(cache_manager):
    """Create a DuplicateDetector."""
    return DuplicateDetector(cache_manager)


@pytest.fixture
def sample_texts():
    """Provide sample texts for testing filters."""
    return {
        "valid": """John Doe visited Paris in January 2024. He met with Jane Smith at the Eiffel Tower.
The city was beautiful and they enjoyed the French cuisine. Paris is the capital of France
and one of the most popular tourist destinations in the world. The weather was pleasant.""",
        "too_short": "Short text.",
        "no_entities": """This is a generic text without any specific names or places.
It is just a bunch of random words put together to make a sentence.""",
        "with_dates": "The event happened on January 15, 2024, and again on 2024-02-20.",
    }


@pytest.fixture
def sample_mcqs():
    """Create multiple sample MCQs for exporter testing."""
    return [
        {
            "question": "What is the capital of France?",
            "options": ["London", "Paris", "Berlin"],
            "correct_answer": 1,
            "explanation": "Paris is the capital city of France.",
            "quality_score": 85.0,
            "metadata": {
                "source_document": "doc_1",
                "source_id": "1",
                "source_url": "",
                "document_hash": "hash1",
                "specific_names": ["France"],
                "specific_places": ["Paris"],
                "specific_dates": [],
                "specific_events": [],
                "timestamp": "2024-01-01T00:00:00",
                "difficulty": "Easy",
                "topic_category": "Geography",
                "quality_score": 85.0,
            },
            "source_text": "France is a country in Western Europe.",
        },
        {
            "question": "Who wrote Romeo and Juliet?",
            "options": ["Charles Dickens", "William Shakespeare", "Jane Austen"],
            "correct_answer": 1,
            "explanation": "William Shakespeare wrote Romeo and Juliet.",
            "quality_score": 90.0,
            "metadata": {
                "source_document": "doc_2",
                "source_id": "2",
                "source_url": "",
                "document_hash": "hash2",
                "specific_names": ["William Shakespeare"],
                "specific_places": [],
                "specific_dates": [],
                "specific_events": [],
                "timestamp": "2024-01-01T00:00:00",
                "difficulty": "Easy",
                "topic_category": "Literature",
                "quality_score": 90.0,
            },
            "source_text": "Romeo and Juliet is a famous play.",
        },
    ]


@pytest.fixture
def mock_dataset():
    """Create a mock dataset for testing."""
    mock = MagicMock()
    mock.__len__ = MagicMock(return_value=10)
    mock.__getitem__ = MagicMock(
        side_effect=lambda i: {
            "text": f"This is document number {i}. It contains some text about John Smith and Jane Doe."
        }
    )
    return mock
