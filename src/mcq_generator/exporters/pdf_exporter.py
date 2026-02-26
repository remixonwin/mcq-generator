"""
PDF Exporter implementation using reportlab.
"""

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .base import BaseExporter


class PDFExporter(BaseExporter):
    """Exports MCQs to PDF format."""

    @property
    def format_name(self) -> str:
        return "pdf"

    @property
    def file_extension(self) -> str:
        return ".pdf"

    def export(self, mcqs: list[dict[str, Any]], output_file: str | None = None) -> str:
        """
        Export MCQs to PDF.

        Args:
            mcqs: List of MCQ dictionaries
            output_file: Optional output file path

        Returns:
            "PDF content generated" string if output_file is None (PDF content is binary),
            else empty string
        """
        if not output_file:
            # We don't support returning PDF binary content as string
            return "PDF content generated (binary data not returned as string)"

        filtered = self.apply_filters(mcqs)

        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_file,
            pagesize=LETTER,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Question", parent=styles["Heading2"], spaceAfter=12))
        styles.add(
            ParagraphStyle(name="Option", parent=styles["Normal"], leftIndent=20, spaceAfter=6)
        )

        story = []

        story.append(Paragraph("MCQ Export", styles["Title"]))
        story.append(Spacer(1, 12))

        if self.topic:
            story.append(Paragraph(f"Topic: {self.topic}", styles["Normal"]))
        if self.difficulty:
            story.append(Paragraph(f"Difficulty: {self.difficulty}", styles["Normal"]))

        story.append(Spacer(1, 24))

        for i, mcq in enumerate(filtered, 1):
            question_text = f"{i}. {mcq.get('question', '')}"
            story.append(Paragraph(question_text, styles["Question"]))

            options = mcq.get("options", [])
            for j, opt in enumerate(options):
                label = ["A", "B", "C"][j]
                story.append(Paragraph(f"{label}) {opt}", styles["Option"]))

            if self.include_explanation:
                explanation = f"<b>Explanation:</b> {mcq.get('explanation', '')}"
                story.append(Spacer(1, 6))
                story.append(Paragraph(explanation, styles["Normal"]))

            correct_idx = mcq.get("correct_answer", 0)
            correct_label = ["A", "B", "C"][correct_idx]
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>Correct Answer:</b> {correct_label}", styles["Normal"]))

            story.append(Spacer(1, 24))

        doc.build(story)
        return ""
