"""
Tests for base exporter.
"""

import pytest
from mcq_generator.exporters.base import BaseExporter


class ConcreteExporter(BaseExporter):
    """Concrete implementation of BaseExporter for testing."""

    @property
    def format_name(self) -> str:
        return "test"

    @property
    def file_extension(self) -> str:
        return ".test"

    def export(self, mcqs, output_file=None):
        return "test export"


class TestBaseExporter:
    """Test suite for BaseExporter."""

    def test_initialization_default(self):
        """Test BaseExporter initialization with defaults."""
        exporter = ConcreteExporter()

        assert exporter.include_source is True
        assert exporter.include_explanation is True
        assert exporter.include_metadata is True
        assert exporter.min_quality is None
        assert exporter.max_quality is None
        assert exporter.difficulty is None
        assert exporter.topic is None

    def test_initialization_custom(self):
        """Test BaseExporter initialization with custom parameters."""
        exporter = ConcreteExporter(
            include_source=False,
            min_quality=50.0,
            max_quality=90.0,
            difficulty="Easy",
            topic="Science",
        )

        assert exporter.include_source is False
        assert exporter.min_quality == 50.0
        assert exporter.max_quality == 90.0
        assert exporter.difficulty == "Easy"
        assert exporter.topic == "Science"

    def test_filter_by_quality_min(self):
        """Test filtering by minimum quality."""
        exporter = ConcreteExporter(min_quality=70.0)

        mcqs = [
            {"question": "Q1", "quality_score": 80.0},
            {"question": "Q2", "quality_score": 60.0},
            {"question": "Q3", "quality_score": 90.0},
        ]

        filtered = exporter.filter_by_quality(mcqs)

        assert len(filtered) == 2
        assert all(m["quality_score"] >= 70.0 for m in filtered)

    def test_filter_by_quality_max(self):
        """Test filtering by maximum quality."""
        exporter = ConcreteExporter(max_quality=80.0)

        mcqs = [
            {"question": "Q1", "quality_score": 80.0},
            {"question": "Q2", "quality_score": 90.0},
            {"question": "Q3", "quality_score": 70.0},
        ]

        filtered = exporter.filter_by_quality(mcqs)

        assert len(filtered) == 2
        assert all(m["quality_score"] <= 80.0 for m in filtered)

    def test_filter_by_quality_range(self):
        """Test filtering by quality range."""
        exporter = ConcreteExporter(min_quality=60.0, max_quality=90.0)

        mcqs = [
            {"question": "Q1", "quality_score": 50.0},
            {"question": "Q2", "quality_score": 70.0},
            {"question": "Q3", "quality_score": 95.0},
        ]

        filtered = exporter.filter_by_quality(mcqs)

        assert len(filtered) == 1
        assert filtered[0]["quality_score"] == 70.0

    def test_filter_by_difficulty(self):
        """Test filtering by difficulty."""
        exporter = ConcreteExporter(difficulty="Easy")

        mcqs = [
            {"question": "Q1", "metadata": {"difficulty": "Easy"}},
            {"question": "Q2", "metadata": {"difficulty": "Medium"}},
            {"question": "Q3", "metadata": {"difficulty": "Easy"}},
        ]

        filtered = exporter.filter_by_difficulty(mcqs)

        assert len(filtered) == 2

    def test_filter_by_difficulty_no_filter(self):
        """Test no difficulty filter applied."""
        exporter = ConcreteExporter()

        mcqs = [
            {"question": "Q1", "metadata": {"difficulty": "Easy"}},
            {"question": "Q2", "metadata": {"difficulty": "Medium"}},
        ]

        filtered = exporter.filter_by_difficulty(mcqs)

        assert len(filtered) == 2

    def test_filter_by_topic(self):
        """Test filtering by topic."""
        exporter = ConcreteExporter(topic="Science")

        mcqs = [
            {"question": "Q1", "metadata": {"topic_category": "Science"}},
            {"question": "Q2", "metadata": {"topic_category": "History"}},
            {"question": "Q3", "metadata": {"topic_category": "Computer Science"}},
        ]

        filtered = exporter.filter_by_topic(mcqs)

        assert len(filtered) == 2

    def test_filter_by_topic_case_insensitive(self):
        """Test topic filtering is case insensitive."""
        exporter = ConcreteExporter(topic="science")

        mcqs = [
            {"question": "Q1", "metadata": {"topic_category": "Science"}},
            {"question": "Q2", "metadata": {"topic_category": "SCIENCE"}},
            {"question": "Q3", "metadata": {"topic_category": "History"}},
        ]

        filtered = exporter.filter_by_topic(mcqs)

        assert len(filtered) == 2

    def test_apply_filters(self):
        """Test applying all filters."""
        exporter = ConcreteExporter(min_quality=75.0, difficulty="Medium", topic="Science")

        mcqs = [
            {
                "question": "Q1",
                "quality_score": 80.0,
                "metadata": {"difficulty": "Medium", "topic_category": "Science"},
            },
            {
                "question": "Q2",
                "quality_score": 70.0,
                "metadata": {"difficulty": "Medium", "topic_category": "Science"},
            },
            {
                "question": "Q3",
                "quality_score": 85.0,
                "metadata": {"difficulty": "Easy", "topic_category": "History"},
            },
        ]

        filtered = exporter.apply_filters(mcqs)

        assert len(filtered) == 1

    def test_get_filters_used(self):
        """Test getting filters that were applied."""
        exporter = ConcreteExporter(min_quality=50.0, difficulty="Easy", topic="Math")

        filters = exporter.get_filters_used()

        assert filters["min_quality"] == 50.0
        assert filters["difficulty"] == "Easy"
        assert filters["topic"] == "Math"

    def test_get_filters_used_empty(self):
        """Test getting filters when none applied."""
        exporter = ConcreteExporter()

        filters = exporter.get_filters_used()

        assert filters == {}

    def test_format_name_property(self):
        """Test format_name property raises NotImplementedError in base class."""
        base = BaseExporter()

        with pytest.raises(NotImplementedError):
            _ = base.format_name

    def test_file_extension_property(self):
        """Test file_extension property raises NotImplementedError in base class."""
        base = BaseExporter()

        with pytest.raises(NotImplementedError):
            _ = base.file_extension

    def test_export_method(self):
        """Test export method raises NotImplementedError in base class."""
        base = BaseExporter()

        with pytest.raises(NotImplementedError):
            base.export([])
