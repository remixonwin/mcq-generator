"""
Markdown Exporter for MCQs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseExporter


def _get_correct_letter(correct_answer: int) -> str:
    """Convert correct_answer index to letter (0=A, 1=B, 2=C)."""
    letters = ["A", "B", "C"]
    return letters[correct_answer] if 0 <= correct_answer < len(letters) else "A"


class MarkdownExporter(BaseExporter):
    """Exporter for Markdown format (quiz/study format)."""

    def __init__(
        self,
        include_source: bool = True,
        include_explanation: bool = True,
        include_metadata: bool = True,
        min_quality: Optional[float] = None,
        max_quality: Optional[float] = None,
        difficulty: Optional[str] = None,
        topic: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        super().__init__(
            include_source=include_source,
            include_explanation=include_explanation,
            include_metadata=include_metadata,
            min_quality=min_quality,
            max_quality=max_quality,
            difficulty=difficulty,
            topic=topic,
        )
        self.job_id = job_id or "unknown"

    @property
    def format_name(self) -> str:
        return "markdown"

    @property
    def file_extension(self) -> str:
        return ".md"

    def export(self, mcqs: List[Dict[str, Any]], output_file: Optional[str] = None) -> str:
        """Export MCQs to Markdown format."""
        # Apply filters
        filtered_mcqs = self.apply_filters(mcqs)

        lines = []

        # Header
        lines.append("# MCQ Export - Job: " + self.job_id)
        lines.append("")
        lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append(f"**Total Questions:** {len(filtered_mcqs)}")

        filters_used = self.get_filters_used()
        if filters_used:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters_used.items())
            lines.append(f"**Filters:** {filter_str}")
        else:
            lines.append("**Filters:** None")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Questions
        for i, mcq in enumerate(filtered_mcqs, 1):
            self._add_question(lines, mcq, i)

        # Footer
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*End of Export*")

        markdown_content = "\n".join(lines)

        # Write to file or return
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            return ""
        else:
            return markdown_content

    def _add_question(self, lines: List[str], mcq: Dict[str, Any], question_num: int) -> None:
        """Add a question to the markdown output."""
        metadata = mcq.get("metadata", {})
        
        difficulty = metadata.get("difficulty", "Unknown")
        topic = metadata.get("topic_category", "Unknown")
        
        # Question header
        lines.append(f"## Question {question_num} ({difficulty} - {topic})")
        lines.append("")
        
        # Question text
        lines.append(mcq.get("question", ""))
        lines.append("")
        
        # Options
        options = mcq.get("options", [])
        option_letters = ["A", "B", "C"]
        
        for i, option in enumerate(options):
            letter = option_letters[i] if i < len(option_letters) else "?"
            lines.append(f"{letter}) {option}")
        
        lines.append("")
        
        # Answer
        correct_answer = mcq.get("correct_answer", 0)
        correct_letter = _get_correct_letter(correct_answer)
        lines.append(f"**Answer: {correct_letter}**")
        
        # Explanation (if requested)
        if self.include_explanation:
            explanation = mcq.get("explanation", "")
            if explanation:
                lines.append("")
                lines.append(f"**Explanation:** {explanation}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
