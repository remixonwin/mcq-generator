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


@pytest.mark.asyncio
async def test_generate_from_numeric_only_dataset_synthesizes_text(temp_dir):
    """Ensure numeric-only datasets do not raise and synth_columns are chosen."""
    from mcq_generator import generator as genmod
    import hashlib

    class FakeDataset:
        def __init__(self, rows, column_names):
            self._rows = rows
            self.column_names = column_names

        def __len__(self):
            return len(self._rows)

        def __getitem__(self, idx):
            return self._rows[idx]

    rows = [
        {"feat1": 1.23, "feat2": 4.56, "id": 1},
        {"feat1": 7.89, "feat2": 0.12, "id": 2},
    ]

    fake_ds = FakeDataset(rows, ["feat1", "feat2", "id"])

    with patch("mcq_generator.generator.load_dataset") as mock_load_dataset:
        with patch("mcq_generator.generator.ProviderClient") as MockProvider:
            with patch("mcq_generator.generator.CacheManager") as MockCache:
                with patch("mcq_generator.generator.StateManager") as MockState:
                    mock_load_dataset.return_value = fake_ds

                    # Provider returns a valid MCQ response regardless of input
                    provider_inst = MagicMock()
                    provider_inst.generate = AsyncMock(
                        return_value={
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            "QUESTION: What is 1+1?\nA) 1\nB) 2\nC) 3\nCORRECT: B\n"
                                            "EXPLANATION: 1+1=2.\nNAMES: \nPLACES: \nDATES: \nEVENTS: \nDIFFICULTY: Easy\nTOPIC: Math"
                                        )
                                    }
                                }
                            ]
                        }
                    )

                    MockProvider.return_value = provider_inst

                    cache_inst = MagicMock()
                    cache_inst.get_best_examples.return_value = []
                    cache_inst.get_mcq.return_value = None
                    MockCache.return_value = cache_inst

                    state_inst = MagicMock()
                    state_inst.get_latest_checkpoint.return_value = None
                    state_inst.update_total_documents.return_value = None
                    state_inst.get_job_progress.return_value = {"status": "running"}
                    # track save_mcq calls
                    state_inst.save_mcq = MagicMock()
                    MockState.return_value = state_inst

                    gen = genmod.MCQGenerator(
                        cache_dir=str(temp_dir / "cache"), db_path=str(temp_dir / "test.db")
                    )

                    # Make filter permissive so synthesized short texts are processed
                    gen.filter = MagicMock()
                    gen.filter.should_process.return_value = True
                    gen.duplicate_detector = MagicMock()
                    gen.duplicate_detector.is_duplicate.return_value = False

                    # Run generator and get first produced MCQ (should not raise)
                    agen = gen.generate_from_dataset(
                        dataset_name="fake_dataset",
                        target_questions=1,
                        dataset_split="train",
                        text_column="text",
                    )

                    produced = None
                    async for item in agen:
                        produced = item
                        break

                    assert produced is not None
                    # synth_columns should have been selected and stored on the generator
                    assert hasattr(gen, "_synth_columns")
                    assert len(gen._synth_columns) > 0

                    # Ensure save_mcq was called with mcq data and document_hash
                    assert state_inst.save_mcq.call_count > 0
                    called = state_inst.save_mcq.call_args_list[0]
                    assert "document_hash" in called.kwargs
                    assert "mcq_data" in called.kwargs
                    # mcq_data should contain metadata.document_hash equal to saved document_hash
                    dh = called.kwargs.get("document_hash")
                    md_hash = (
                        called.kwargs.get("mcq_data", {}).get("metadata", {}).get("document_hash")
                    )
                    assert dh == md_hash


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
