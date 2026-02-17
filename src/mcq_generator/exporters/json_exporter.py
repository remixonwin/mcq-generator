"""
JSON Exporter implementation.
"""

import json
from pathlib import Path
from typing import Any

from .base import BaseExporter


class JSONExporter(BaseExporter):
    """Exports MCQs to JSON format."""

    @property
    def format_name(self) -> str:
        return "json"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(
        self,
        mcqs: list[dict[str, Any]],
        output_file: str | None = None,
        include_metadata: bool = True,
    ) -> str:
        """
        Export MCQs to JSON.

        Args:
            mcqs: List of MCQ dictionaries
            output_file: Optional output file path
            include_metadata: Whether to include metadata in export

        Returns:
            JSON string if output_file is None, else empty string
        """
        filtered = self.apply_filters(mcqs)

        output_data = {
            "meta": {
                "count": len(filtered),
                "filters": self.get_filters_used(),
                "format": "mcq-generator-v1",
            },
            "data": filtered,
        }

        json_str = json.dumps(output_data, indent=2, ensure_ascii=False)

        if output_file:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
            return ""

        return json_str
