"""
CSV Exporter implementation.
"""

import csv
import io
from pathlib import Path
from typing import Any

from .base import BaseExporter


class CSVExporter(BaseExporter):
    """Exports MCQs to CSV format."""

    @property
    def format_name(self) -> str:
        return "csv"

    @property
    def file_extension(self) -> str:
        return ".csv"

    def export(
        self,
        mcqs: list[dict[str, Any]],
        output_file: str | None = None,
        include_metadata: bool = True,
    ) -> str:
        """
        Export MCQs to CSV.

        Args:
            mcqs: List of MCQ dictionaries
            output_file: Optional output file path
            include_metadata: Whether to include metadata in export

        Returns:
            CSV string if output_file is None, else empty string
        """
        filtered = self.apply_filters(mcqs)

        fieldnames = [
            "question",
            "option_a",
            "option_b",
            "option_c",
            "correct_answer",
            "explanation",
            "difficulty",
            "topic",
            "source_id",
            "quality_score",
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for mcq in filtered:
            options = mcq.get("options", [])
            metadata = mcq.get("metadata", {})

            row = {
                "question": mcq.get("question", ""),
                "option_a": options[0] if len(options) > 0 else "",
                "option_b": options[1] if len(options) > 1 else "",
                "option_c": options[2] if len(options) > 2 else "",
                "correct_answer": ["A", "B", "C"][mcq.get("correct_answer", 0)],
                "explanation": mcq.get("explanation", ""),
                "difficulty": metadata.get("difficulty", ""),
                "topic": metadata.get("topic_category", ""),
                "source_id": metadata.get("source_id", ""),
                "quality_score": metadata.get("quality_score", 0),
            }
            writer.writerow(row)

        csv_str = output.getvalue()
        output.close()

        if output_file:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(csv_str, encoding="utf-8")
            return ""

        return csv_str
