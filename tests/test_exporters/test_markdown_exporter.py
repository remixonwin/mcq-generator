"""
Tests for Markdown exporter.
"""

import pytest
from mcq_generator.exporters.markdown_exporter import MarkdownExporter, _get_correct_letter


class TestMarkdownExporter:
    """Test suite for MarkdownExporter."""

    def test_initialization(self):
        """Test MarkdownExporter initialization."""
        exporter = MarkdownExporter()

        assert exporter.format_name == "markdown"
        assert exporter.file_extension == ".md"
        assert exporter.job_id == "unknown"

    def test_initialization_with_job_id(self):
        """Test MarkdownExporter with custom job_id."""
        exporter = MarkdownExporter(job_id="test_job_123")

        assert exporter.job_id == "test_job_123"

    def test_export_returns_string(self, sample_mcqs):
        """Test exporting to string."""
        exporter = MarkdownExporter()

        result = exporter.export(sample_mcqs)

        assert isinstance(result, str)
        assert "# MCQ Export" in result

    def test_export_includes_header(self, sample_mcqs):
        """Test export includes header information."""
        exporter = MarkdownExporter(job_id="test_job")

        result = exporter.export(sample_mcqs)

        assert "MCQ Export" in result
        assert "Total Questions" in result
        assert "2" in result
        assert "Exported:" in result

    def test_export_includes_questions(self, sample_mcqs):
        """Test export includes questions."""
        exporter = MarkdownExporter()

        result = exporter.export(sample_mcqs)

        assert "Question 1" in result
        assert "Question 2" in result
        assert "capital of France" in result

    def test_export_includes_options(self, sample_mcqs):
        """Test export includes options."""
        exporter = MarkdownExporter()

        result = exporter.export(sample_mcqs)

        assert "A)" in result
        assert "B)" in result
        assert "C)" in result

    def test_export_includes_answers(self, sample_mcqs):
        """Test export includes answers."""
        exporter = MarkdownExporter()

        result = exporter.export(sample_mcqs)

        assert "Answer:" in result

    def test_export_includes_explanation(self, sample_mcqs):
        """Test export includes explanations."""
        exporter = MarkdownExporter(include_explanation=True)

        result = exporter.export(sample_mcqs)

        assert "Explanation:" in result

    def test_export_excludes_explanation(self, sample_mcqs):
        """Test export can exclude explanations."""
        exporter = MarkdownExporter(include_explanation=False)

        result = exporter.export(sample_mcqs)

        assert "Explanation:" not in result

    def test_export_with_quality_filter(self, sample_mcqs):
        """Test export with quality filter."""
        exporter = MarkdownExporter(min_quality=85.0)

        result = exporter.export(sample_mcqs)

        assert "Total Questions" in result

    def test_export_with_difficulty_filter(self, sample_mcqs):
        """Test export with difficulty filter."""
        exporter = MarkdownExporter(difficulty="Easy")

        result = exporter.export(sample_mcqs)

        assert "Total Questions" in result
        assert "2" in result

    def test_export_to_file(self, sample_mcqs, temp_dir):
        """Test exporting to file."""
        exporter = MarkdownExporter()
        output_path = temp_dir / "output.md"

        exporter.export(sample_mcqs, output_file=str(output_path))

        assert output_path.exists()

        content = output_path.read_text()
        assert "# MCQ Export" in content

    def test_export_includes_filters_info(self, sample_mcqs):
        """Test export includes filter information."""
        exporter = MarkdownExporter(min_quality=80.0)

        result = exporter.export(sample_mcqs)

        assert "Filters:" in result
        assert "min_quality=80.0" in result

    def test_export_includes_metadata(self, sample_mcqs):
        """Test export includes metadata like difficulty and topic."""
        exporter = MarkdownExporter()

        result = exporter.export(sample_mcqs)

        assert "Easy" in result
        assert "Geography" in result


class TestGetCorrectLetter:
    """Test suite for _get_correct_letter helper."""

    def test_valid_indices(self):
        """Test converting valid indices to letters."""
        assert _get_correct_letter(0) == "A"
        assert _get_correct_letter(1) == "B"
        assert _get_correct_letter(2) == "C"

    def test_invalid_index(self):
        """Test handling of invalid index."""
        assert _get_correct_letter(5) == "A"
        assert _get_correct_letter(-1) == "A"

    def test_edge_cases(self):
        """Test edge cases."""
        assert _get_correct_letter(0) == "A"
        assert _get_correct_letter(2) == "C"
