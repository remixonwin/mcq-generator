# MCQ Generator

High-Performance MCQ Generator with intelligent filtering, caching, and state management.

## Installation

```bash
uv sync
```

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# Interactive mode - search, select, and generate
mcq interactive

# Search for datasets
mcq search "sentiment"

# Generate with continuous mode (until cancelled)
mcq generate <dataset>

# Generate with limited questions
mcq generate <dataset> --questions 100

# List all jobs
mcq list-jobs

# Check job status
mcq status <job_id>

# Show statistics
mcq stats

# Export MCQs
mcq export <job_id> --format json --output export
```

## Commands

| Command | Description |
|---------|-------------|
| `interactive` | Interactive search, select, and generate workflow |
| `search` | Search for datasets on HuggingFace Hub |
| `generate` | Generate MCQs from a HuggingFace dataset |
| `resume` | Resume an interrupted job |
| `list-jobs` | List all jobs |
| `status` | Check job status |
| `stats` | Show overall statistics |
| `export` | Export MCQs in different formats |

## Interactive Mode

Run `mcq interactive` for a guided workflow:

1. Enter search query (e.g., "sentiment", "qa")
2. Browse results with pagination (n = next, q = done, c = cancel)
3. Select a dataset by number
4. Choose generation mode:
   - **Limited**: Specify number of questions
   - **Continuous**: Generate until cancelled/exhausted
5. Enter output filename
6. Start generation

## Continuous Mode

- Generates MCQs until:
  - User presses Ctrl+C (interrupted)
  - Dataset is exhausted
  - Error occurs
- **Auto-saves after each MCQ** - no data loss on interruption
- Press Ctrl+C to stop gracefully (saves progress)

## Options

### generate
- `--questions, -n` - Number of questions (0 = continuous mode, default: 0)
- `--output, -o` - Output file path (default: mcqs.json)
- `--checkpoint` - Checkpoint interval (default: 10)
- `--cache-dir` - Cache directory (default: .mcq_cache)
- `--provider` - Provider URL (default: http://localhost:7543)
- `--resume` - Job ID to resume

### search
- `--limit, -n` - Number of results (default: 10)
- `--sort` - Sort by (downloads, likes)
