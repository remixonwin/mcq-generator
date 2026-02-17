"""
Tests for JSON exporter.
"""

import pytest
import json
from pathlib import Path
from mcq_generator.exporters.json_exporter import JSONExporter


class TestJSONExporter:
    """Test suite for JSONExporter."""

    def test_initialization(self):
        """Test JSONExporter initialization."""
        exporter = JSONExporter()

        assert exporter.format_name == "json"
        assert exporter.file_extension == ".json"

    def test_export_returns_string(self, sample_mcqs):
        """Test exporting to string."""
        exporter = JSONExporter()

        result = exporter.export(sample_mcqs)

        assert isinstance(result, str)
        data = json.loads(result)
        assert "meta" in data
        assert "data" in data

    def test_export_includes_metadata(self, sample_mcqs):
        """Test export includes metadata."""
        exporter = JSONExporter()

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        assert data["meta"]["count"] == 2
        assert data["meta"]["format"] == "mcq-generator-v1"

    def test_export_with_quality_filter(self, sample_mcqs):
        """Test export with quality filter."""
        exporter = JSONExporter(min_quality=80.0)

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        assert data["meta"]["count"] == 2

    def test_export_with_difficulty_filter(self, sample_mcqs):
        """Test export with difficulty filter."""
        exporter = JSONExporter(difficulty="Easy")

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        assert data["meta"]["count"] == 2

    def test_export_with_topic_filter(self, sample_mcqs):
        """Test export with topic filter."""
        exporter = JSONExporter(topic="Geography")

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        assert data["meta"]["count"] == 1

    def test_export_to_file(self, sample_mcqs, temp_dir):
        """Test exporting to file."""
        exporter = JSONExporter()
        output_path = temp_dir / "output.json"

        exporter.export(sample_mcqs, output_file=str(output_path))

        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert data["meta"]["count"] == 2

    def test_export_creates_parent_dirs(self, sample_mcqs, temp_dir):
        """Test that export creates parent directories."""
        exporter = JSONExporter()
        output_path = temp_dir / "nested" / "dir" / "output.json"

        exporter.export(sample_mcqs, output_file=str(output_path))

        assert output_path.exists()

    def test_export_filters_in_metadata(self, sample_mcqs):
        """Test that applied filters are included in metadata."""
        exporter = JSONExporter(min_quality=80.0, difficulty="Easy")

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        filters = data["meta"]["filters"]
        assert "min_quality" in filters
        assert "difficulty" in filters

    def test_export_empty_list(self):
        """Test exporting empty list."""
        exporter = JSONExporter()

        result = exporter.export([])
        data = json.loads(result)

        assert data["meta"]["count"] == 0
        assert data["data"] == []

    def test_export_filters_applied_in_order(self, sample_mcqs):
        """Test that multiple filters are applied in order."""
        exporter = JSONExporter(difficulty="Easy", topic="Geography")

        result = exporter.export(sample_mcqs)
        data = json.loads(result)

        assert data["meta"]["count"] == 1
        assert "Geography" in data["data"][0]["metadata"]["topic_category"]

    def test_context_manager_support(self, temp_dir):
        """Test JSONExporter does not need context manager (not a resource)."""
        exporter = JSONExporter()
        assert exporter is not None
