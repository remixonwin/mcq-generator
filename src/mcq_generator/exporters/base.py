"""
Abstract base class for exporters.
"""

from abc import ABC
from typing import Any


class BaseExporter(ABC):
    """Abstract base class for all exporters."""

    def __init__(
        self,
        include_source: bool = True,
        include_explanation: bool = True,
        include_metadata: bool = True,
        min_quality: float | None = None,
        max_quality: float | None = None,
        difficulty: str | None = None,
        topic: str | None = None,
    ):
        self.include_source = include_source
        self.include_explanation = include_explanation
        self.include_metadata = include_metadata
        self.min_quality = min_quality
        self.max_quality = max_quality
        self.difficulty = difficulty
        self.topic = topic

    @property
    def format_name(self) -> str:
        """Return the format name."""
        raise NotImplementedError("Subclasses must implement format_name")

    @property
    def file_extension(self) -> str:
        """Return the expected file extension for this format."""
        raise NotImplementedError("Subclasses must implement file_extension")

    def export(self, mcqs: list[dict[str, Any]], output_file: str | None = None) -> str:
        """
        Export MCQs to the specified output file or return as string.
        
        Args:
            mcqs: List of MCQ dictionaries
            output_file: Optional output file path. If None, returns string.
            
        Returns:
            The exported content as a string (if output_file is None) or empty string.
        """
        raise NotImplementedError("Subclasses must implement export")

    def filter_by_quality(self, mcqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter MCQs by quality score."""
        filtered = mcqs

        if self.min_quality is not None:
            filtered = [
                mcq for mcq in filtered
                if mcq.get("quality_score", 0) >= self.min_quality
            ]

        if self.max_quality is not None:
            filtered = [
                mcq for mcq in filtered
                if mcq.get("quality_score", 0) <= self.max_quality
            ]

        return filtered

    def filter_by_difficulty(self, mcqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter MCQs by difficulty level."""
        if not self.difficulty:
            return mcqs

        return [
            mcq for mcq in mcqs
            if mcq.get("metadata", {}).get("difficulty") == self.difficulty
        ]

    def filter_by_topic(self, mcqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter MCQs by topic category (substring match)."""
        if not self.topic:
            return mcqs

        topic_filter = self.topic
        return [
            mcq for mcq in mcqs
            if topic_filter.lower() in str(mcq.get("metadata", {}).get("topic_category") or "").lower()
        ]

    def apply_filters(self, mcqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply all filters to MCQs."""
        filtered = self.filter_by_quality(mcqs)
        filtered = self.filter_by_difficulty(filtered)
        filtered = self.filter_by_topic(filtered)
        return filtered

    def get_filters_used(self) -> dict[str, Any]:
        """Get dictionary of filters that were applied."""
        filters: dict[str, Any] = {}

        if self.min_quality is not None:
            filters["min_quality"] = self.min_quality
        if self.max_quality is not None:
            filters["max_quality"] = self.max_quality
        if self.difficulty is not None:
            filters["difficulty"] = self.difficulty
        if self.topic is not None:
            filters["topic"] = self.topic

        return filters
