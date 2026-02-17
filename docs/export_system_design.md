# MCQ Export System - Architecture & Design Document

## 1. Overview

This document outlines the design for an export system that allows users to export MCQ (Multiple Choice Question) data from the DuckDB storage via a new CLI command.

## 2. CLI Command Structure

### Command Signature

```bash
mcq export <JOB_ID> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `job_id` | string | Yes | The job ID to export MCQs from |

### Options

| Option | Flag | Type | Default | Description |
|--------|------|------|---------|-------------|
| Format | `--format`, `-f` | choice | `json` | Output format: `json`, `csv`, `markdown` |
| Output | `--output`, `-o` | string | stdout | Output file path (omit for stdout) |
| Quality Min | `--min-quality` | float | None | Minimum quality score (0-100) |
| Quality Max | `--max-quality` | float | None | Maximum quality score (0-100) |
| Difficulty | `--difficulty` | choice | All | Filter by difficulty: `Easy`, `Medium`, `Hard` |
| Topic | `--topic` | string | All | Filter by topic category |
| Exclude Source | `--no-source` | flag | false | Exclude source text from output |
| Exclude Explanation | `--no-explanation` | flag | false | Exclude explanation from output |
| Exclude Metadata | `--no-metadata` | flag | false | Exclude metadata from output |
| Quiet | `--quiet`, `-q` | flag | false | Suppress non-error output |

### Examples

```bash
# Export all MCQs from a job to JSON
mcq export job_20240215_abc123

# Export to CSV file
mcq export job_20240215_abc123 -f csv -o questions.csv

# Export only high-quality questions to Markdown
mcq export job_20240215_abc123 -f markdown --min-quality 80

# Filter by difficulty and export to file
mcq export job_20240215_abc123 --difficulty Medium -o medium_questions.json

# Export without source text (for privacy)
mcq export job_20240215_abc123 --no-source -o clean_export.json
```

## 3. Export Format Specifications

### 3.1 JSON Format

**Structure:**
```json
{
  "export_info": {
    "job_id": "job_20240215_abc123",
    "exported_at": "2024-02-15T10:30:00Z",
    "total_questions": 50,
    "filters_applied": {
      "min_quality": 70,
      "difficulty": null
    }
  },
  "questions": [
    {
      "question": "What is the capital of France?",
      "options": ["London", "Paris", "Berlin"],
      "correct_answer": 1,
      "correct_letter": "B",
      "explanation": "Paris has been the capital of France since the 10th century.",
      "source_text": "France is a country in Western Europe...",
      "metadata": {
        "difficulty": "Easy",
        "topic_category": "Geography",
        "quality_score": 85.5,
        "source_document": "dataset_0",
        "timestamp": "2024-02-15T10:00:00Z"
      }
    }
  ]
}
```

**Note:** The `correct_letter` field is derived from `correct_answer` (0=A, 1=B, 2=C).

### 3.2 CSV Format (Flattened - One Row Per Question)

**Columns:**
```
question,option_a,option_b,option_c,correct_answer,correct_letter,explanation,difficulty,topic,quality_score,source_document,timestamp
```

**Example:**
```csv
question,option_a,option_b,option_c,correct_answer,correct_letter,explanation,difficulty,topic,quality_score,source_document,timestamp
"What is the capital of France?","London","Paris","Berlin","1","B","Paris has been the capital since the 10th century.","Easy","Geography","85.5","dataset_0","2024-02-15T10:00:00Z"
```

**Notes:**
- When `--no-explanation` is used, the explanation column is omitted
- When `--no-metadata` is used, difficulty, topic, quality_score, source_document, timestamp are omitted
- Source text is NOT included in CSV (too long for cell format)

### 3.3 Markdown Format (Quiz/Study Format)

**Structure:**
```markdown
# MCQ Export - Job: job_20240215_abc123

**Exported:** 2024-02-15 10:30:00 UTC  
**Total Questions:** 50  
**Filters:** min_quality=70, difficulty=Medium

---

## Question 1 (Easy - Geography)

What is the capital of France?

A) London  
B) Paris  
C) Berlin  

**Answer: B**

**Explanation:** Paris has been the capital of France since the 10th century.

---

## Question 2 (Medium - History)

[...]

---

*End of Export*
```

**Notes:**
- Source text is NOT included in Markdown format by default
- Each question is separated by `---`
- Question number, difficulty, and topic are in the header

## 4. Filtering Logic

### 4.1 Filter Types

| Filter | Type | Description |
|--------|------|-------------|
| `min_quality` | float | Minimum quality_score (inclusive) |
| `max_quality` | float | Maximum quality_score (inclusive) |
| `difficulty` | string | Exact match: "Easy", "Medium", "Hard" |
| `topic` | string | Substring match on topic_category |

### 4.2 Combining Filters

All filters use AND logic:
- `min_quality=70 AND max_quality=90 AND difficulty=Medium AND topic contains "History"`

### 4.3 Filter Application Order

1. Fetch all MCQs for job_id from StateManager
2. Apply quality filters
3. Apply difficulty filter
4. Apply topic filter
5. Return filtered results

## 5. Validation Rules

### 5.1 Job ID Validation

Before export:
1. Check if job_id exists in `jobs` table
2. If not found, display error and exit with code 1
3. If found but has 0 MCQs, display warning but continue

### 5.2 Option Validation

- Format must be one of: `json`, `csv`, `markdown` (case-insensitive)
- Quality scores must be 0-100
- Output file must be writable (or stdout)

### 5.3 Error Messages

| Error | Message |
|-------|---------|
| Job not found | `Error: Job '{job_id}' not found. Use 'mcq list-jobs' to see available jobs.` |
| No MCQs | `Warning: Job '{job_id}' has 0 MCQs. No export generated.` |
| Invalid quality | `Error: Quality must be between 0 and 100.` |
| Invalid format | `Error: Invalid format '{format}'. Use: json, csv, markdown.` |
| Write error | `Error: Cannot write to '{path}': {error}` |

## 6. File Changes

### 6.1 New Files

| File | Purpose |
|------|---------|
| `src/mcq_generator/exporters/base.py` | Abstract base class for exporters |
| `src/mcq_generator/exporters/json_exporter.py` | JSON export implementation |
| `src/mcq_generator/exporters/csv_exporter.py` | CSV export implementation |
| `src/mcq_generator/exporters/markdown_exporter.py` | Markdown export implementation |
| `src/mcq_generator/exporters/__init__.py` | Exporters package init |

### 6.2 Modified Files

| File | Changes |
|------|---------|
| `src/mcq_generator/cli.py` | Add `export` command and helper functions |

### 6.3 New Directory Structure

```
src/mcq_generator/
├── exporters/
│   ├── __init__.py
│   ├── base.py
│   ├── json_exporter.py
│   ├── csv_exporter.py
│   └── markdown_exporter.py
```

## 7. Code Structure Recommendations

### 7.1 Exporter Base Class

```python
# exporters/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, TextIO

class BaseExporter(ABC):
    """Abstract base class for all exporters."""
    
    @abstractmethod
    def export(self, mcqs: List[Dict[str, Any]], output: TextIO, options: Dict[str, Any]) -> None:
        """Export MCQs to the provided output stream."""
        pass
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the expected file extension for this format."""
        pass
```

### 7.2 Export Options Dictionary

```python
export_options = {
    "include_source": bool,      # default: True
    "include_explanation": bool, # default: True
    "include_metadata": bool,    # default: True
    "quality_min": Optional[float],
    "quality_max": Optional[float],
    "difficulty": Optional[str], # "Easy", "Medium", "Hard"
    "topic": Optional[str],
}
```

### 7.3 CLI Command Structure

```python
# In cli.py
@app.command()
def export(
    job_id: str = typer.Argument(..., help="Job ID to export"),
    format: str = typer.Option("json", "--format", "-f", help="Export format"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
    min_quality: Optional[float] = typer.Option(None, "--min-quality"),
    max_quality: Optional[float] = typer.Option(None, "--max-quality"),
    difficulty: Optional[str] = typer.Option(None, "--difficulty"),
    topic: Optional[str] = typer.Option(None, "--topic"),
    no_source: bool = typer.Option(False, "--no-source"),
    no_explanation: bool = typer.Option(False, "--no-explanation"),
    no_metadata: bool = typer.Option(False, "--no-metadata"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
):
    """Export MCQs from a job to various formats."""
    # Implementation...
```

## 8. Implementation Priority

### Phase 1 (MVP)
- JSON exporter
- Basic filtering (job_id validation, quality filter)
- File output
- stdout output

### Phase 2
- CSV exporter
- Markdown exporter
- Difficulty filter
- Topic filter

### Phase 3 (Future)
- PDF exporter
- Batch export multiple jobs
- Export templates
- Custom field selection

## 9. Testing Strategy

### Unit Tests
- Test each exporter with sample MCQ data
- Test filtering logic
- Test edge cases (empty results, invalid inputs)

### Integration Tests
- Test CLI command end-to-end
- Test file output
- Test stdout output

### Test Data
```python
sample_mcq = {
    "question": "What is 2+2?",
    "options": ["3", "4", "5"],
    "correct_answer": 1,
    "explanation": "2+2 equals 4",
    "source_text": "Basic math: 2+2=4",
    "metadata": {
        "difficulty": "Easy",
        "topic_category": "Math",
        "quality_score": 90.0,
        "source_document": "test_001",
        "timestamp": "2024-01-01T00:00:00"
    }
}
```

## 10. Summary

This design provides:
- ✅ Simple CLI interface with intuitive options
- ✅ Multiple export formats (JSON, CSV, Markdown)
- ✅ Flexible filtering with AND logic
- ✅ Clear validation and error messages
- ✅ Modular exporter architecture for easy extension
- ✅ Backward compatibility with existing storage
