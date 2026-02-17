"""
CLI interface using Rich and Typer.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

from pathlib import Path
import asyncio
import json
import csv
import signal
import sys
from datetime import datetime

from .generator import MCQGenerator
from .state_manager import StateManager
from .dataset_search import search_datasets
from .exporters.json_exporter import JSONExporter
from .exporters.csv_exporter import CSVExporter
from .exporters.markdown_exporter import MarkdownExporter

app = typer.Typer(name="mcq", help="High-Performance MCQ Generator", add_completion=False)

console = Console()


class SearchState:
    """Maintains search state across paginated results."""

    def __init__(self):
        self.query: str = ""
        self.results: list = []
        self.offset: int = 0
        self.limit: int = 10

    def search(self, query: str, offset: int = 0) -> list:
        """Search with pagination."""
        self.query = query
        self.offset = offset
        self.results = search_datasets(query=query, limit=self.limit, offset=offset)
        return self.results

    def has_more(self) -> bool:
        """Check if more results available."""
        return len(self.results) == self.limit


search_state = SearchState()
generation_running = True


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global generation_running
    generation_running = False
    console.print("\n[yellow]Stopping generation... (saving progress)[/yellow]")


signal.signal(signal.SIGINT, signal_handler)


def display_results(results: list, start_num: int = 1):
    """Display search results in a table."""
    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Dataset", style="cyan")
    table.add_column("Downloads", justify="right", style="green")
    table.add_column("Likes", justify="right", style="magenta")

    for i, ds in enumerate(results, start_num):
        table.add_row(str(i), ds["id"], f"{ds['downloads']:,}", f"{ds['likes']:,}")

    console.print(table)
    return table


@app.command()
def search(
    query: str = typer.Argument(None, help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
    sort: str = typer.Option("downloads", "--sort", help="Sort by (downloads, likes)"),
):
    """Search for datasets on HuggingFace Hub."""
    if not query:
        console.print("[yellow]Please provide a search query[/yellow]")
        raise typer.Exit(1)

    console.print(f"[cyan]Searching for:[/cyan] {query}")

    results = search_datasets(query=query, limit=limit, sort=sort)

    if not results:
        console.print("[yellow]No datasets found[/yellow]")
        return

    display_results(results)


@app.command()
def interactive():
    """Interactive dataset search and generation workflow."""
    _run_interactive_generation()


def _run_interactive_generation():
    """Interactive dataset search and generation workflow."""
    global generation_running

    console.print(
        Panel.fit(
            "[bold cyan]Interactive MCQ Generator[/bold cyan]\nSearch, select, and generate",
            box=box.DOUBLE,
        )
    )

    query = Prompt.ask(
        "[cyan]Enter search query[/cyan] (e.g., 'sentiment', 'qa', 'text classification')"
    )

    console.print(f"\n[cyan]Searching for:[/cyan] {query}")

    offset = 0
    all_results = []

    while True:
        results = search_state.search(query, offset)
        all_results.extend(results)

        console.print(f"\n[green]Results {offset + 1}-{offset + len(results)}:[/green]\n")
        display_results(results, start_num=offset + 1)

        if not search_state.has_more():
            console.print("[dim]No more results available[/dim]")
            break

        console.print("\n[dim]Options:[/dim]")
        console.print("  [cyan]n[/cyan] - Next page")
        console.print("  [cyan]q[/cyan] - Done selecting")
        console.print("  [cyan]c[/cyan] - Cancel")

        action = Prompt.ask(
            "\n[cyan]Action[/cyan]",
            choices=["n", "q", "c"],
            default="q",
        )

        if action == "c":
            console.print("[yellow]Cancelled.[/yellow]")
            return
        elif action == "q":
            break
        elif action == "n":
            offset += search_state.limit

    if not all_results:
        console.print("[yellow]No datasets found.[/yellow]")
        return

    console.print(f"\n[green]Total datasets available: {len(all_results)}[/green]\n")

    choices = [str(i) for i in range(1, len(all_results) + 1)]
    choice = Prompt.ask(
        "\n[cyan]Select dataset number[/cyan]",
        choices=choices,
    )

    selected = all_results[int(choice) - 1]
    dataset_name = selected["id"]

    console.print(f"\n[green]Selected:[/green] {dataset_name}")
    console.print(f"   Downloads: {selected['downloads']:,} | Likes: {selected['likes']:,}")

    if not Confirm.ask("\n[cyan]Proceed with this dataset?[/cyan]"):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    console.print("\n[cyan]Generation Mode:[/cyan]")
    console.print("  [cyan]1[/cyan] - Limited (specify number of questions)")
    console.print("  [cyan]2[/cyan] - Continuous (generate until cancelled/paused)")

    mode = Prompt.ask("[cyan]Choose mode[/cyan]", choices=["1", "2"], default="2")

    output = Prompt.ask(
        "[cyan]Output file[/cyan]", default=f"mcqs_{dataset_name.split('/')[-1]}.json"
    )

    if mode == "1":
        questions = Prompt.ask("[cyan]Number of questions to generate[/cyan]", default="50")
        target_questions = int(questions)
        continuous = False
    else:
        console.print(
            "\n[yellow]Continuous mode: Generating until cancelled, paused, or exhausted.[/yellow]"
        )
        console.print("[yellow]Results will be saved after each MCQ generation.[/yellow]")
        target_questions = 999999999
        continuous = True

    console.print(f"\n[bold cyan]Starting generation...[/bold cyan]")
    console.print(f"Dataset: {dataset_name}")
    console.print(f"Mode: {'Continuous' if continuous else 'Limited'}")
    console.print(f"Output: {output}\n")

    output_path = Path(output)
    asyncio.run(
        _run_generation_loop(
            dataset_name=dataset_name,
            target_questions=target_questions,
            output_path=output_path,
        )
    )


def _save_incremental(output_path: Path, mcqs: list, dataset_name: str):
    """Save MCQs incrementally to file in multiple formats."""
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "dataset": dataset_name,
        "total_questions": len(mcqs),
        "mcqs": mcqs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_path.with_suffix(".json")
    # Ensure all MCQs are plain dicts (in case old code stored dataclasses)
    serializable_mcqs = []
    for m in mcqs:
        if hasattr(m, "to_dict") and callable(m.to_dict):
            serializable_mcqs.append(m.to_dict())
        else:
            serializable_mcqs.append(m)

    output_data["mcqs"] = serializable_mcqs

    # Atomic write: write to temp file then replace to avoid partial writes
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = json_path.with_suffix(json_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    tmp_path.replace(json_path)
    console.print(f"[green]Saved {len(serializable_mcqs)} MCQs to {json_path}[/green]")

    # Mirror to default root file `mcqs.json` for backwards compatibility so
    # users who expect the top-level file to update will see progress.
    try:
        root_path = Path("mcqs.json")
        tmp_root = root_path.with_suffix(root_path.suffix + ".tmp")
        tmp_root.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_root.replace(root_path)
    except Exception:
        # Non-fatal: continue without blocking generation
        console.print("[yellow]Warning: failed to update top-level mcqs.json[/yellow]")

    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Question",
                "Option A",
                "Option B",
                "Option C",
                "Correct",
                "Explanation",
                "Difficulty",
                "Topic",
            ]
        )
        for mcq in mcqs:
            writer.writerow(
                [
                    mcq["question"],
                    mcq["options"][0],
                    mcq["options"][1],
                    mcq["options"][2],
                    chr(65 + mcq["correct_answer"]),
                    mcq["explanation"],
                    mcq["metadata"]["difficulty"],
                    mcq["metadata"]["topic_category"],
                ]
            )

    gift_path = output_path.with_suffix(".txt")
    with open(gift_path, "w") as f:
        f.write("# MCQ Export - GIFT Format\n\n")
        for mcq in mcqs:
            f.write(f"::{mcq['metadata']['topic_category']}::{mcq['question']}{{\n")
            for i, option in enumerate(mcq["options"]):
                marker = "=" if i == mcq["correct_answer"] else "~"
                f.write(f"    {marker}{option}\n")
            f.write(f"    # {mcq['explanation']}\n}}\n\n")

    txt_path = output_path.with_suffix(".txt").with_name(output_path.stem + "_readable.txt")
    with open(txt_path, "w") as f:
        f.write(f"# MCQs Generated from {dataset_name}\n")
        f.write(f"# Total: {len(mcqs)} questions\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
        for i, mcq in enumerate(mcqs, 1):
            f.write(f"## Question {i}\n")
            f.write(f"{mcq['question']}\n\n")
            f.write(f"A) {mcq['options'][0]}\n")
            f.write(f"B) {mcq['options'][1]}\n")
            f.write(f"C) {mcq['options'][2]}\n")
            f.write(f"\nCorrect Answer: {chr(65 + mcq['correct_answer'])}\n")
            f.write(f"\nExplanation: {mcq['explanation']}\n")
            f.write(
                f"\nDifficulty: {mcq['metadata']['difficulty']} | Topic: {mcq['metadata']['topic_category']}\n"
            )
            f.write("-" * 50 + "\n\n")

    return json_path, csv_path, gift_path, txt_path


def _show_post_generation_menu(output_path: Path, mcqs_count: int, dataset_name: str):
    """Show post-generation menu with options."""
    console.print("\n" + "=" * 50)
    console.print(f"[bold green]Generation Complete![/bold green] {mcqs_count} MCQs generated")
    console.print("=" * 50)

    console.print(f"\n[cyan]Output files saved to:[/cyan] {output_path.parent.absolute()}")

    table = Table(title="Generated Files", box=box.ROUNDED)
    table.add_column("Format", style="cyan")
    table.add_column("File", style="white")
    table.add_column("Description", style="dim")

    table.add_row("JSON", output_path.with_suffix(".json").name, "Full data with metadata")
    table.add_row("CSV", output_path.with_suffix(".csv").name, "Spreadsheet format")
    table.add_row(
        "GIFT", output_path.with_name(output_path.stem + ".txt").name, "Moodle quiz format"
    )
    table.add_row(
        "TXT", output_path.with_name(output_path.stem + "_readable.txt").name, "Human readable"
    )

    console.print(table)

    console.print("\n[cyan]Options:[/cyan]")
    console.print("  [green]1[/green] - Generate more (continue current dataset)")
    console.print("  [green]2[/green] - Generate from different dataset")
    console.print("  [green]3[/green] - Search for new dataset")
    console.print("  [green]4[/green] - View files in folder")
    console.print("  [green]5[/green] - Exit")

    choice = Prompt.ask(
        "\n[cyan]What would you like to do?[/cyan]",
        choices=["1", "2", "3", "4", "5"],
        default="5",
    )

    return choice


async def _run_generation_loop(
    dataset_name: str,
    target_questions: int,
    output_path: Path,
    resume_job_id: Optional[str] = None,
    checkpoint_interval: int = 10,
    provider_url: Optional[str] = None,
    cache_dir: str = ".mcq_cache",
):
    """Core generation loop used by all commands."""
    global generation_running
    generation_running = True

    generator = MCQGenerator(
        provider_url=provider_url,
        cache_dir=cache_dir,
        checkpoint_interval=checkpoint_interval,
    )

    mcqs = []
    # If resuming a job, preload existing MCQs from state DB (preferred) or the
    # output JSON file (fallback) so we append new MCQs instead of overwriting.
    if resume_job_id:
        try:
            state = StateManager()
            try:
                existing = state.get_mcqs(resume_job_id)
                if existing:
                    mcqs.extend(existing)
                    console.print(
                        f"[green]Loaded {len(existing)} existing MCQs from job state[/green]"
                    )
            finally:
                state.close()
        except Exception:
            try:
                json_path = output_path.with_suffix(".json")
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        file_mcqs = data.get("mcqs", [])
                        if file_mcqs:
                            mcqs.extend(file_mcqs)
                            console.print(
                                f"[green]Loaded {len(file_mcqs)} existing MCQs from {json_path}[/green]"
                            )
            except Exception:
                console.print(
                    "[yellow]Could not preload existing MCQs for resume; starting fresh.[/yellow]"
                )
    signal.signal(signal.SIGINT, signal_handler)

    continuous = target_questions >= 999999999

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        if continuous:
            task = progress.add_task(f"[cyan]Generating MCQs from {dataset_name}...", total=None)
        else:
            task = progress.add_task(
                f"[cyan]Generating MCQs from {dataset_name}...", total=target_questions
            )

        try:
            async for mcq in generator.generate_from_dataset(
                dataset_name=dataset_name,
                target_questions=target_questions,
                resume_job_id=resume_job_id,
            ):
                if not generation_running:
                    console.print("\n[yellow]Generation stopped.[/yellow]")
                    break

                mcq_dict = mcq.to_dict()
                mcqs.append(mcq_dict)

                _save_incremental(output_path, mcqs, dataset_name)

                # If this is a resumed job and we're writing into the autosave
                # directory, also mirror the file to the repository root
                # `mcqs.json` so users checking the default location see updates.
                try:
                    if resume_job_id and output_path.parent.name == ".mcq_exports":
                        src = output_path.with_suffix(".json")
                        dst = Path("mcqs.json")
                        if src.exists():
                            # atomic copy via read/write
                            data = src.read_text(encoding="utf-8")
                            tmp = dst.with_suffix(dst.suffix + ".tmp")
                            tmp.write_text(data, encoding="utf-8")
                            tmp.replace(dst)
                except Exception:
                    console.print(
                        "[yellow]Warning: failed to mirror autosave to mcqs.json[/yellow]"
                    )

                if continuous:
                    progress.update(
                        task,
                        description=f"[cyan]Generated {len(mcqs)} MCQs from {dataset_name}...",
                    )
                else:
                    progress.update(task, advance=1)

                if len(mcqs) % 10 == 0:
                    _display_stats(generator, len(mcqs))

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")

        finally:
            await generator.close()

    if mcqs:
        console.print(f"\n[green]Final: {len(mcqs)} MCQs saved to {output_path}[/green]")
        _display_final_stats(generator, len(mcqs))


def _open_output_folder(path: Path):
    """Open output folder in file manager."""
    import os
    import subprocess

    folder = path.parent.absolute()
    console.print(f"[cyan]Opening folder:[/cyan] {folder}")

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        elif sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.run(["xdg-open", str(folder)])
    except Exception as e:
        console.print(f"[yellow]Could not open folder: {e}[/yellow]")


@app.command()
def generate(
    dataset: str = typer.Argument(..., help="HuggingFace dataset name"),
    questions: int = typer.Option(
        0, "--questions", "-n", help="Number of questions (0 for continuous)"
    ),
    output: str = typer.Option("mcqs.json", "--output", "-o", help="Output file path"),
    checkpoint: int = typer.Option(10, "--checkpoint", help="Checkpoint interval"),
    cache_dir: str = typer.Option(".mcq_cache", "--cache-dir", help="Cache directory"),
    provider_url: str = typer.Option("http://localhost:7543", "--provider", help="Provider URL"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Job ID to resume"),
):
    """Generate MCQs from a HuggingFace dataset."""
    continuous = questions == 0

    console.print(
        Panel.fit(
            "[bold cyan]MCQ Generator[/bold cyan]\n"
            + ("Continuous mode" if continuous else f"{questions} questions"),
            box=box.DOUBLE,
        )
    )

    target = questions if questions > 0 else 999999999
    asyncio.run(
        _run_generation_loop(
            dataset_name=dataset,
            target_questions=target,
            output_path=Path(output),
            resume_job_id=resume,
            checkpoint_interval=checkpoint,
            provider_url=provider_url,
            cache_dir=cache_dir,
        )
    )


@app.command()
def resume(
    job_id: str = typer.Argument(..., help="Job ID to resume"),
    output: str = typer.Option("mcqs.json", "--output", "-o", help="Output file"),
):
    """Resume an interrupted job."""
    console.print(f"[cyan]Resuming job {job_id}...[/cyan]")

    # Load job progress and close the StateManager before starting the
    # generation loop. Keeping the connection open across the async run
    # can cause concurrent write transactions and DuckDB "write-write
    # conflict" errors when the generator also writes state. Close early
    # so the generator may open its own connection safely.
    state = StateManager()
    progress_info = state.get_job_progress(job_id)

    console.print(
        Panel(
            f"[bold]Job: {job_id}[/bold]\n"
            f"Dataset: {progress_info['dataset_name']}\n"
            f"Progress: {progress_info['generated_count']}/{progress_info['target_questions']} "
            f"({progress_info['progress_pct']:.1f}%)\n"
            f"Status: {progress_info['status']}"
        )
    )

    dataset_name = progress_info["dataset_name"]
    target = progress_info["target_questions"]

    # Close the StateManager before starting generation to avoid holding a
    # write lock across the async generator run.
    state.close()

    # If the user didn't specify an explicit output file, prefer the
    # autosave location produced by StateManager to avoid confusing
    # interactions with older files: .mcq_exports/<job_id>.json
    if output == "mcqs.json":
        export_dir = Path(".mcq_exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / f"{job_id}.json"
    else:
        output_path = Path(output)

    asyncio.run(
        _run_generation_loop(
            dataset_name=dataset_name,
            target_questions=target,
            output_path=output_path,
            resume_job_id=job_id,
        )
    )


@app.command()
def list_jobs(status: Optional[str] = typer.Option(None, "--status", help="Filter by status")):
    """List all jobs."""
    state = StateManager()
    try:
        jobs = state.list_jobs(status=status)

        if not jobs:
            console.print("[yellow]No jobs found[/yellow]")
            return

        table = Table(title="MCQ Generation Jobs", box=box.ROUNDED)
        table.add_column("Job ID", style="cyan", no_wrap=True)
        table.add_column("Dataset", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Progress", justify="right")
        table.add_column("Created", style="blue")

        for job in jobs:
            progress_pct = (
                (job["generated_count"] / job["target_questions"] * 100)
                if job["target_questions"] > 0
                else 0
            )
            progress_str = (
                f"{job['generated_count']}/{job['target_questions']} ({progress_pct:.0f}%)"
            )

            table.add_row(
                job["job_id"],
                job["dataset_name"],
                job["status"],
                progress_str,
                str(job["created_at"]),
            )

        console.print(table)

    finally:
        state.close()


@app.command()
def status(job_id: str = typer.Argument(..., help="Job ID to check")):
    """Check job status."""
    state = StateManager()
    try:
        progress = state.get_job_progress(job_id)

        layout = Layout()

        layout.split_column(Layout(name="header"), Layout(name="body"))

        layout["header"].update(Panel(f"[bold cyan]Job: {job_id}[/bold cyan]", box=box.DOUBLE))

        info_table = Table(box=box.SIMPLE)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Dataset", progress["dataset_name"])
        info_table.add_row("Status", progress["status"])
        info_table.add_row("Target", str(progress["target_questions"]))
        info_table.add_row("Generated", str(progress["generated_count"]))
        info_table.add_row("Progress", f"{progress['progress_pct']:.1f}%")
        info_table.add_row("Created", str(progress["created_at"]))
        info_table.add_row("Updated", str(progress["updated_at"]))

        layout["body"].update(Panel(info_table))

        console.print(layout)

    finally:
        state.close()


@app.command()
def stats():
    """Show overall statistics."""
    state = StateManager()
    try:
        statistics = state.get_statistics()

        table = Table(title="System Statistics", box=box.DOUBLE_EDGE)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Total Jobs", str(statistics["total_jobs"]))
        table.add_row("Completed", str(statistics["completed_jobs"]))
        table.add_row("Running", str(statistics["running_jobs"]))
        table.add_row("Paused", str(statistics["paused_jobs"]))
        table.add_row("Total MCQs", str(statistics["total_mcqs"]))

        console.print(table)

    finally:
        state.close()


@app.command()
def export(
    job_id: str = typer.Argument(..., help="Job ID to export"),
    format: str = typer.Option("json", "--format", "-f", help="Export format (json/csv/markdown)"),
    output: str = typer.Option("export", "--output", "-o", help="Output file path"),
    min_quality: Optional[float] = typer.Option(
        None, "--min-quality", help="Minimum quality score (0-100)"
    ),
    max_quality: Optional[float] = typer.Option(
        None, "--max-quality", help="Maximum quality score (0-100)"
    ),
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", help="Filter by difficulty: Easy/Medium/Hard"
    ),
    topic: Optional[str] = typer.Option(None, "--topic", help="Filter by topic category substring"),
    no_source: bool = typer.Option(False, "--no-source", help="Exclude source text"),
    no_explanation: bool = typer.Option(False, "--no-explanation", help="Exclude explanation"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="Exclude metadata fields"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress status messages"),
):
    """Export MCQs from a job to various formats."""
    state = StateManager()
    try:
        # Validate job_id exists
        jobs = state.list_jobs()
        if not any(job["job_id"] == job_id for job in jobs):
            console.print(
                f"[red]Error: Job '{job_id}' not found. Use 'mcq list-jobs' to see available jobs.[/red]"
            )
            raise typer.Exit(1)

        # Get MCQs for job_id
        mcqs = state.get_mcqs(job_id)
        if not mcqs:
            console.print(
                f"[yellow]Warning: Job '{job_id}' has 0 MCQs. No export generated.[/yellow]"
            )
            return

        # Apply filters
        filters = {
            "min_quality": min_quality,
            "max_quality": max_quality,
            "difficulty": difficulty,
            "topic": topic,
        }

        # Create exporter instance based on format
        if format == "json":
            exporter = JSONExporter(
                include_source=not no_source,
                include_explanation=not no_explanation,
                include_metadata=not no_metadata,
                min_quality=min_quality,
                max_quality=max_quality,
                difficulty=difficulty,
                topic=topic,
            )
        elif format == "csv":
            exporter = CSVExporter(
                include_source=not no_source,
                include_explanation=not no_explanation,
                include_metadata=not no_metadata,
                min_quality=min_quality,
                max_quality=max_quality,
                difficulty=difficulty,
                topic=topic,
            )
        elif format == "markdown":
            exporter = MarkdownExporter(
                include_source=not no_source,
                include_explanation=not no_explanation,
                include_metadata=not no_metadata,
                min_quality=min_quality,
                max_quality=max_quality,
                difficulty=difficulty,
                topic=topic,
                job_id=job_id,
            )
        else:
            console.print(f"[red]Error: Invalid format '{format}'. Use: json, csv, markdown.[/red]")
            raise typer.Exit(1)

        # Export MCQs
        if output == "export":
            # Output to stdout
            result = exporter.export(mcqs)
            console.print(result)
        else:
            # Output to file
            exporter.export(mcqs, output)
            if not quiet:
                console.print(f"[green]Exported {len(mcqs)} MCQs to {output}[/green]")

    finally:
        state.close()


def _display_stats(generator, current: int):
    """Display current generation statistics."""
    cache_stats = generator.cache.get_stats()
    provider_stats = generator.provider.get_stats()

    stats_panel = Panel(
        f"[cyan]Generated:[/cyan] {current}\n"
        f"[cyan]Cache Hit Rate:[/cyan] {cache_stats['mcq_cache']['hit_rate']:.1f}%\n"
        f"[cyan]Provider Success:[/cyan] {provider_stats['success_rate']:.1f}%",
        title="[bold]Statistics[/bold]",
        box=box.ROUNDED,
    )

    console.print(stats_panel)


def _display_final_stats(generator, total_generated: int):
    """Display final statistics."""
    cache_stats = generator.cache.get_stats()
    provider_stats = generator.provider.get_stats()
    filter_stats = generator.filter.get_stats()

    table = Table(title="Generation Summary", box=box.DOUBLE_EDGE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Generated", str(total_generated))
    table.add_row("Cache Hit Rate", f"{cache_stats['mcq_cache']['hit_rate']:.1f}%")
    table.add_row("Filter Pass Rate", f"{filter_stats['pass_rate']:.1f}%")

    console.print(table)


if __name__ == "__main__":
    app()
