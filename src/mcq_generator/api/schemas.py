"""
Pydantic schemas for API request/response validation.

Following industry best practices, all schemas are centralized here
for consistency and reusability across the API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Common Schemas
# ============================================================================


class StatusEnum(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class PaginationParams(BaseModel):
    """Pagination parameters."""

    offset: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(10, ge=1, le=100, description="Maximum items to return")


class PaginatedResponse(BaseModel):
    """Base paginated response."""

    total: int = Field(..., description="Total number of items")
    offset: int = Field(..., description="Current offset")
    limit: int = Field(..., description="Current limit")
    items: list[Any] = Field(..., description="Response items")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    db: str | None = Field(None, description="Database status")
    broker: str | None = Field(None, description="Message broker status")
    version: str = Field(..., description="API version")


# ============================================================================
# Dataset Schemas
# ============================================================================


class DatasetSearchParams(BaseModel):
    """Dataset search parameters."""

    q: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Number of results")
    sort: str = Field("downloads", pattern="^(downloads|likes|trending)$")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class DatasetItem(BaseModel):
    """Dataset search result item."""

    id: str = Field(..., description="Dataset ID")
    downloads: int = Field(..., description="Download count")
    likes: int = Field(..., description="Like count")


class DatasetSearchResponse(BaseModel):
    """Dataset search response."""

    results: list[DatasetItem] = Field(..., description="Search results")
    total: int = Field(..., description="Total available results")


# ============================================================================
# Job Schemas
# ============================================================================


class CreateJobRequest(BaseModel):
    """Request to create a new generation job."""

    dataset: str = Field(..., min_length=1, description="HuggingFace dataset name")
    questions: int = Field(0, ge=0, description="Number of questions (0 = unlimited)")
    checkpoint: int = Field(10, ge=1, description="Checkpoint interval")
    cache_dir: str = Field(".mcq_cache", description="Cache directory path")
    provider_url: str | None = Field(None, description="Custom provider URL")
    output: str | None = Field(
        None, description="Output file path (auto-generated if not provided)"
    )
    dataset_split: str = Field("train", description="Dataset split to use")
    text_column: str = Field("text", description="Text column name")


class CreateJobResponse(BaseModel):
    """Response after creating a job."""

    job_id: str = Field(..., description="Unique job identifier")
    message: str = Field(..., description="Status message")
    status: str = Field(..., description="Initial job status")


class JobProgress(BaseModel):
    """Job progress information."""

    job_id: str = Field(..., description="Job identifier")
    dataset_name: str = Field(..., description="Source dataset")
    status: StatusEnum = Field(..., description="Current status")
    target_questions: int = Field(..., description="Target MCQ count")
    generated_count: int = Field(..., description="Generated MCQ count")
    processed_count: int = Field(0, description="Processed document count")
    total_documents: int | None = Field(None, description="Total documents in dataset")
    progress_pct: float = Field(0.0, description="Progress percentage")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(), description="Last update timestamp"
    )
    completed_at: datetime | None = Field(None, description="Completion timestamp")


class JobListResponse(PaginatedResponse):
    """List of jobs response."""

    items: list[JobProgress] = Field(..., description="List of jobs")


class ResumeJobRequest(BaseModel):
    """Request to resume a job."""

    provider_url: str | None = Field(None, description="Custom provider URL")


class ResumeJobResponse(BaseModel):
    """Response after resuming a job."""

    job_id: str = Field(..., description="Job identifier")
    message: str = Field(..., description="Status message")
    status: str = Field(..., description="Current status")


class UpdateJobStatusRequest(BaseModel):
    """Request to update job status."""

    status: StatusEnum = Field(..., description="New status")
    reason: str | None = Field(None, description="Status change reason")


class JobStatistics(BaseModel):
    """Job statistics."""

    total_jobs: int = Field(..., description="Total number of jobs")
    completed_jobs: int = Field(..., description="Completed jobs")
    running_jobs: int = Field(..., description="Running jobs")
    paused_jobs: int = Field(..., description="Paused jobs")
    failed_jobs: int = Field(..., description="Failed jobs")
    pending_jobs: int = Field(..., description="Pending jobs")
    total_mcqs: int = Field(..., description="Total MCQs generated")


# ============================================================================
# Export Schemas
# ============================================================================


class ExportFormat(str, Enum):
    """Export format enumeration."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    PDF = "pdf"


class ExportRequest(BaseModel):
    """Export request parameters."""

    format: ExportFormat = Field(ExportFormat.JSON, description="Export format")
    output: str | None = Field(None, description="Output file path")
    include_metadata: bool = Field(True, description="Include metadata in export")


class ExportResponse(BaseModel):
    """Export response."""

    job_id: str = Field(..., description="Job identifier")
    format: ExportFormat = Field(..., description="Export format")
    file_path: str | None = Field(None, description="Output file path")
    content: dict[str, Any] | None = Field(None, description="Exported content (for JSON)")
    message: str = Field(..., description="Status message")


class MCQMetadata(BaseModel):
    """MCQ metadata model."""

    source_document: str = Field(..., description="Source document identifier")
    source_id: str = Field(..., description="Source ID")
    source_url: str = Field(default="", description="Source URL")
    document_hash: str = Field(..., description="Document hash")
    specific_names: list[str] = Field(default_factory=list)
    specific_places: list[str] = Field(default_factory=list)
    specific_dates: list[str] = Field(default_factory=list)
    specific_events: list[str] = Field(default_factory=list)
    timestamp: datetime | None = Field(None, description="Generation timestamp")
    difficulty: str = Field(default="Medium", description="Difficulty level")
    topic_category: str = Field(default="General", description="Topic category")
    quality_score: float = Field(default=0.0, description="Quality score")


class MCQOption(BaseModel):
    """MCQ option model."""

    id: str = Field(..., description="Option identifier (A, B, C, etc.)")
    text: str = Field(..., description="Option text")
    is_correct: bool = Field(..., description="Whether this is the correct answer")
    explanation: str | None = Field(None, description="Explanation for this option")
    distractor_type: str | None = Field(None, description="Type of distractor if not correct")


class MCQItem(BaseModel):
    """MCQ item model."""

    question_hash: str = Field(..., description="Unique hash for the question")
    question: str = Field(..., description="Question text")
    options: list[MCQOption] = Field(..., min_length=3, description="Answer options")
    context: str | None = Field(None, description="Question context")
    difficulty: str = Field(..., description="Difficulty level")
    question_type: str = Field(..., description="Type of question")
    learning_objective: str | None = Field(None, description="Target learning objective")
    quality_score: float | None = Field(None, description="Quality score (0.0 - 1.0)")
    generated_at: datetime = Field(..., description="Generation timestamp")
    model_name: str = Field(..., description="Model used for generation")
    source_metadata: dict[str, Any] | None = Field(None, description="Source metadata")
    explanation: str = Field(..., description="General explanation")
    source_text: str = Field(default="", description="Source text excerpt")
    created_at: datetime | None = Field(None, description="System creation timestamp")


class MCQListResponse(BaseModel):
    """List of MCQs response."""

    job_id: str = Field(..., description="Job identifier")
    total: int = Field(..., description="Total MCQs")
    mcqs: list[MCQItem] = Field(..., description="List of MCQs")
