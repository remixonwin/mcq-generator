# MCQ Generator

High-Performance MCQ Generator with intelligent filtering, caching, and state management.

## Quick Start

```bash
# Open interactive menu (default)
mcq

# Or use specific commands
mcq --help
```

## Interactive Menu

Run `mcq` to open the main menu:

```
╔══════════════════════════════════════╗
║ MCQ Generator                        ║
║ Your AI-powered quiz generation tool ║
╚══════════════════════════════════════╝
Running Jobs: 0
Paused Jobs: 1
Completed Jobs: 5

Main Menu:
  1 - Search & Generate MCQs
  2 - Manage Jobs (list, start, stop, view)
  3 - Resume a paused/running job
  4 - View Statistics
  5 - Export MCQs
  q - Quit
```

## Commands

| Command | Description |
|---------|-------------|
| `mcq` | Open interactive menu (default) |
| `mcq list-jobs` | List all jobs |
| `mcq list-jobs -i` | Interactive job management |
| `mcq list-jobs --fix-stale` | Fix stalled jobs |
| `mcq delete <job_id>` | Delete a job |
| `mcq delete <job_id> --force` | Delete without confirmation |
| `mcq export <job_id>` | Export MCQs |

## Interactive Menu Options

### Main Menu
- **1** - Search & Generate MCQs
- **2** - Manage Jobs (start, stop, view, delete)
- **3** - Resume paused/running job
- **4** - View Statistics
- **5** - Export MCQs
- **q** - Quit

### Job Management
- **1-n** - Select job by number
- **s** - Start/Resume job
- **p** - Pause/Stop job
- **v** - View details
- **l** - View logs
- **d** - Delete job
- **r** - Refresh list
- **b** - Back to menu
- **Ctrl+C** - Cancel

### Search & Generate
- Enter search query (e.g., "sentiment", "qa")
- **n** - Next page
- **q** - Done selecting
- **c** - Cancel
- Select dataset number
- Choose mode (Limited/Continuous)

## Continuous Mode

- Generates MCQs until:
  - User presses Ctrl+C
  - Dataset is exhausted
  - Error occurs
- Auto-saves after each MCQ (no data loss)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Cancel current operation |
| `q` | Quit/Back |
| `c` | Cancel |
| `n` | Next page |
| `b` | Back to previous menu |

## Installation

```bash
uv sync
```

## API Server

```bash
# Run API server
./scripts/run_api.sh

# With custom host/port
./scripts/run_api.sh --host 0.0.0.0 --port 8000

# Or directly with uvicorn
PYTHONPATH=src uvicorn mcq_generator.asgi:app --host 0.0.0.0 --port 8000
```
