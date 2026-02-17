"""
Tests for generator module.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime

from mcq_generator.generator import MCQGenerator, MCQ, MCQMetadata


class TestMCQGenerator:
    """Test suite for MCQGenerator."""

    @pytest.mark.asyncio
    async def test_initialization(self, temp_dir):
        """Test MCQGenerator initialization."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator(
                        cache_dir=str(temp_dir / "cache"),
                        db_path=str(temp_dir / "test.db"),
                    )

                    assert generator is not None

    def test_mcq_to_dict(self, sample_mcq):
        """Test MCQ to_dict method."""
        result = sample_mcq.to_dict()

        assert "question" in result
        assert "options" in result
        assert "correct_answer" in result
        assert "metadata" in result
        assert result["metadata"]["difficulty"] == "Medium"

    def test_build_prompt(self, temp_dir):
        """Test prompt building."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager") as mock_cache:
                with patch("mcq_generator.generator.StateManager"):
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get_best_examples.return_value = []
                    mock_cache.return_value = mock_cache_instance

                    generator = MCQGenerator(
                        cache_dir=str(temp_dir / "cache"),
                        db_path=str(temp_dir / "test.db"),
                    )

                    text = "This is a test document."
                    prompt = generator._build_prompt(text, [])

                    assert "This is a test document" in prompt

    def test_build_prompt_with_examples(self, temp_dir):
        """Test prompt building with examples."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager") as mock_cache:
                with patch("mcq_generator.generator.StateManager"):
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get_best_examples.return_value = []
                    mock_cache.return_value = mock_cache_instance

                    generator = MCQGenerator(
                        cache_dir=str(temp_dir / "cache"),
                        db_path=str(temp_dir / "test.db"),
                    )

                    text = "Test document"
                    examples = [
                        {"question": "Example Q", "options": ["A", "B", "C"], "correct_answer": 0}
                    ]
                    prompt = generator._build_prompt(text, examples)

                    assert "examples" in prompt.lower() or "EXAMPLE" in prompt

    def test_parse_response(self, temp_dir):
        """Test response parsing."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator()

                    response = """QUESTION: What is 2+2?
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
TOPIC: Math"""

                    mcq = generator._parse_response(response, "Source text", "doc_1")

                    assert mcq is not None
                    assert mcq.question == "What is 2+2?"
                    assert mcq.correct_answer == 1  # B

    def test_parse_response_invalid(self, temp_dir):
        """Test response parsing with invalid input."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator()

                    response = "Invalid response"

                    mcq = generator._parse_response(response, "Source text", "doc_1")

                    assert mcq is None

    def test_parse_response_missing_options(self, temp_dir):
        """Test response parsing with missing options."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator()

                    response = """QUESTION: What is 2+2?
CORRECT: B
EXPLANATION: 2+2=4."""

                    mcq = generator._parse_response(response, "Source text", "doc_1")

                    assert mcq is None

    def test_format_example(self, temp_dir):
        """Test example formatting."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator()

                    example = {
                        "question": "Test Q?",
                        "options": ["A", "B", "C"],
                        "correct_answer": 0,
                    }

                    formatted = generator._format_example(example)

                    assert "Test Q?" in formatted
                    assert "A)" in formatted or "A)" in formatted

    @pytest.mark.asyncio
    async def test_process_document_filtered(self, temp_dir):
        """Test processing filtered document."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager") as mock_cache:
                with patch("mcq_generator.generator.StateManager"):
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get_best_examples.return_value = []
                    mock_cache_instance.get_mcq.return_value = None
                    mock_cache.return_value = mock_cache_instance

                    generator = MCQGenerator(
                        cache_dir=str(temp_dir / "cache"),
                        db_path=str(temp_dir / "test.db"),
                    )

                    result = await generator._process_document(
                        text="short",  # Will be filtered
                        document_index=0,
                        dataset_name="test",
                        job_id="job_1",
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_process_document_cached(self, temp_dir, sample_mcq_dict):
        """Test processing cached document."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager") as mock_cache:
                with patch("mcq_generator.generator.StateManager"):
                    mock_cache_instance = MagicMock()
                    mock_cache_instance.get_best_examples.return_value = []
                    mock_cache_instance.get_mcq.return_value = {
                        "mcq": sample_mcq_dict,
                        "document_hash": "abc123",
                        "quality_score": 80.0,
                    }
                    mock_cache.return_value = mock_cache_instance

                    generator = MCQGenerator(
                        cache_dir=str(temp_dir / "cache"),
                        db_path=str(temp_dir / "test.db"),
                    )
                    generator.filter = MagicMock()
                    generator.filter.should_process.return_value = True

                    result = await generator._process_document(
                        text="test text", document_index=0, dataset_name="test", job_id="job_1"
                    )

                    assert result is not None

    def test_dict_to_mcq(self, temp_dir, sample_mcq_dict):
        """Test converting dict to MCQ."""
        with patch("mcq_generator.generator.ProviderClient"):
            with patch("mcq_generator.generator.CacheManager"):
                with patch("mcq_generator.generator.StateManager"):
                    generator = MCQGenerator()

                    mcq = generator._dict_to_mcq(sample_mcq_dict)

                    assert isinstance(mcq, MCQ)
                    assert mcq.question == sample_mcq_dict["question"]


class TestMCQMetadata:
    """Test suite for MCQMetadata dataclass."""

    def test_creation(self):
        """Test MCQMetadata creation."""
        metadata = MCQMetadata(
            source_document="doc1",
            source_id="1",
            source_url="http://example.com",
            document_hash="abc",
            specific_names=["John"],
            specific_places=["Paris"],
            specific_dates=["2024"],
            specific_events=["Event"],
            timestamp="2024-01-01",
            difficulty="Easy",
            topic_category="Test",
            quality_score=85.0,
        )

        assert metadata.source_document == "doc1"
        assert metadata.quality_score == 85.0


class TestMCQ:
    """Test suite for MCQ dataclass."""

    def test_creation(self, sample_mcq_metadata):
        """Test MCQ creation."""
        mcq = MCQ(
            question="Test question?",
            options=["A", "B", "C"],
            correct_answer=0,
            explanation="Explanation",
            metadata=sample_mcq_metadata,
            source_text="Source text",
        )

        assert mcq.question == "Test question?"
        assert len(mcq.options) == 3
        assert mcq.correct_answer == 0
