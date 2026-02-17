"""
Service layer for export operations.

Handles exporting MCQs in various formats, separating business logic from HTTP layer.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ...exporters.csv_exporter import CSVExporter
from ...exporters.json_exporter import JSONExporter
from ...exporters.markdown_exporter import MarkdownExporter
from ...exporters.pdf_exporter import PDFExporter
from ..schemas import ExportFormat, MCQItem, MCQMetadata, MCQOption

logger = logging.getLogger(__name__)


class ExportService:
    """Service for export-related operations."""

    def __init__(self, state_manager):
        self.state = state_manager

    def get_exporter(self, format: ExportFormat):
        """Get the appropriate exporter for the format."""
        exporters = {
            ExportFormat.JSON: JSONExporter,
            ExportFormat.CSV: CSVExporter,
            ExportFormat.MARKDOWN: MarkdownExporter,
            ExportFormat.PDF: PDFExporter,
        }

        exporter_class = exporters.get(format)
        if not exporter_class:
            raise ValueError(f"Unsupported export format: {format}")

        return exporter_class

    def export_job(
        self,
        job_id: str,
        format: ExportFormat,
        output: str | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """
        Export MCQs for a job in the requested format.

        Args:
            job_id: The job ID to export
            format: Export format (json, csv, markdown, pdf)
            output: Optional output file path
            include_metadata: Whether to include metadata in export

        Returns:
            Dict with export results
        """
        # Verify job exists
        jobs = self.state.list_jobs()
        job_exists = any(job["job_id"] == job_id for job in jobs)

        if not job_exists:
            raise ValueError(f"Job {job_id} not found")

        # Get MCQs for the job
        mcqs = self.state.get_mcqs(job_id)

        if not mcqs:
            return {
                "job_id": job_id,
                "format": format,
                "message": "Job has no MCQs",
                "file_path": None,
                "content": None,
            }

        # Get the exporter
        exporter_class = self.get_exporter(format)

        # Handle Markdown exporter which requires job_id
        if format == ExportFormat.MARKDOWN:
            exporter = exporter_class(job_id=job_id)
        else:
            exporter = exporter_class()

        # Determine output path
        if not output:
            output = f".mcq_exports/{job_id}.{format.value}"

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # For JSON, we can return the content directly
        if format == ExportFormat.JSON and not output:
            content = exporter.export(mcqs, include_metadata=include_metadata)
            return {
                "job_id": job_id,
                "format": format,
                "message": "MCQs exported successfully",
                "file_path": None,
                "content": content,
            }

        # Export to file
        result = exporter.export(mcqs, str(output_path), include_metadata=include_metadata)

        return {
            "job_id": job_id,
            "format": format,
            "message": f"Exported to {output_path}",
            "file_path": str(output_path),
            "content": None,
        }

    def get_job_mcqs(self, job_id: str) -> dict[str, Any]:
        """
        Get all MCQs for a job in a structured format.

        Returns:
            Dict with job_id, total count, and list of MCQItems
        """
        mcqs = self.state.get_mcqs(job_id)

        # Convert to MCQItem models
        mcq_items = []
        for mcq in mcqs:
            metadata_raw = mcq.get("metadata", {})
            
            # Map options to MCQOption objects
            options_raw = mcq.get("options", [])
            correct_idx = mcq.get("correct_answer", 0)
            formatted_options = []
            for i, opt_text in enumerate(options_raw):
                formatted_options.append(
                    MCQOption(
                        id=chr(65 + i),  # A, B, C
                        text=opt_text,
                        is_correct=(i == correct_idx),
                        explanation=None  # Individual explanations not available in current internal format
                    )
                )

            # Extract fields from nested metadata or top level
            # Internal format often has quality_score at top level or in metadata
            quality_score = mcq.get("quality_score")
            if quality_score is None:
                quality_score = metadata_raw.get("quality_score", 0.0)
            
            # Try to get generation timestamp
            ts_raw = metadata_raw.get("timestamp")
            generated_at = None
            if ts_raw:
                try:
                    from datetime import datetime
                    if isinstance(ts_raw, str):
                        # Handle potential fractional seconds or Z suffix
                        ts_raw = ts_raw.replace("Z", "+00:00")
                        generated_at = datetime.fromisoformat(ts_raw)
                    else:
                        generated_at = ts_raw
                except Exception:
                    pass
            
            if not generated_at:
                generated_at = datetime.now()

            # Ensure question_hash exists
            q_hash = mcq.get("question_hash")
            if not q_hash:
                q_hash = metadata_raw.get("question_hash") or metadata_raw.get("document_hash")
            if not q_hash:
                q_hash = hashlib.sha256(mcq.get("question", "").encode()).hexdigest()

            mcq_items.append(
                MCQItem(
                    question_hash=q_hash,
                    question=mcq.get("question", ""),
                    options=formatted_options,
                    context=mcq.get("context") or metadata_raw.get("context"),
                    difficulty=metadata_raw.get("difficulty", "Medium"),
                    question_type=metadata_raw.get("question_type", "factual"),
                    learning_objective=metadata_raw.get("learning_objective"),
                    quality_score=float(quality_score),
                    generated_at=generated_at,
                    model_name=metadata_raw.get("model_name", "gpt-4"),
                    source_metadata=metadata_raw,
                    explanation=mcq.get("explanation", ""),
                    source_text=mcq.get("source_text", ""),
                    created_at=None,
                )
            )

        return {
            "job_id": job_id,
            "total": len(mcq_items),
            "mcqs": mcq_items,
        }
