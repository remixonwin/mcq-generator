"""
CLI interface using Rich and Typer.
"""

import asyncio
import csv
import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .dataset_search import search_datasets
from .exporters.csv_exporter import CSVExporter
from .exporters.json_exporter import JSONExporter
from .exporters.markdown_exporter import MarkdownExporter
from .generator import MCQGenerator
from .state_manager import StateManager

app = typer.Typer(name="mcq", help="High-Performance MCQ Generator", add_completion=False)


def main():
    """Main entry point - runs interactive menu by default."""
    _run_main_menu()


@app.callback(invoke_without_command=True)
def mcq(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Open interactive menu"
    ),
):
    """MCQ Generator - High-Performance MCQ Generator."""
    if ctx.invoked_subcommand is None and interactive:
        _run_main_menu()
    elif ctx.invoked_subcommand is None and not interactive:
        console.print("[yellow]No command specified. Use --interactive or see --help[/yellow]")


def _run_main_menu():
    """Run the main interactive menu."""
    while True:
        console.print(
            Panel.fit(
                "[bold cyan]MCQ Generator[/bold cyan]\nYour AI-powered quiz generation tool",
                box=box.DOUBLE,
            )
        )

        state = StateManager()
        try:
            stale_jobs = state.get_stale_jobs(stale_minutes=5)
            if stale_jobs:
                console.print(
                    f"[yellow]Found {len(stale_jobs)} stale job(s) - auto-fixing...[/yellow]"
                )
                fixed = state.fix_stale_jobs(stale_minutes=5, mark_as="paused")
                console.print(f"[green]Fixed {fixed} stale job(s)[/green]\n")

            running_jobs = state.list_jobs(status="running")
            paused_jobs = state.list_jobs(status="paused")
            completed_jobs = state.list_jobs(status="completed")
        finally:
            state.close()

        console.print(f"[green]Running Jobs:[/green] {len(running_jobs)}")
        console.print(f"[yellow]Paused Jobs:[/yellow] {len(paused_jobs)}")
        console.print(f"[blue]Completed Jobs:[/blue] {len(completed_jobs)}")

        console.print("\n[bold cyan]Main Menu:[/bold cyan]")
        console.print("  [cyan]1[/cyan] - Search & Generate MCQs")
        console.print("  [cyan]2[/cyan] - Manage Jobs (list, start, stop, view)")
        console.print("  [cyan]3[/cyan] - Resume a paused/running job")
        console.print("  [cyan]4[/cyan] - View Statistics")
        console.print("  [cyan]5[/cyan] - Export MCQs")
        console.print("  [cyan]q[/cyan] - Quit")
        console.print("  [dim]Ctrl+C - Cancel[/dim]")

        try:
            choice = Prompt.ask(
                "\n[cyan]Select option[/cyan]",
                choices=["1", "2", "3", "4", "5", "q"],
                default="q",
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled by user.[/yellow]")
            console.print("[blue]Goodbye![/blue]")
            break

        if choice == "q":
            console.print("[blue]Goodbye![/blue]")
            break
        elif choice == "1":
            _run_interactive_generation()
        elif choice == "2":
            _run_jobs_menu()
        elif choice == "3":
            _run_resume_menu()
        elif choice == "4":
            _show_stats_menu()
        elif choice == "5":
            _run_export_menu()

        console.clear()


def _run_jobs_menu():
    """Run the jobs management menu."""
    state = StateManager()
    try:
        jobs = state.list_jobs()

        if not jobs:
            console.print("[yellow]No jobs found[/yellow]")
            return

        _run_interactive_job_menu(jobs, state)
    finally:
        state.close()


def _run_resume_menu():
    """Run the resume job menu."""
    state = StateManager()
    try:
        paused_jobs = state.list_jobs(status="paused")
        running_jobs = state.list_jobs(status="running")
        jobs = paused_jobs + running_jobs

        if not jobs:
            console.print("[yellow]No resumable jobs found (paused or running).[/yellow]")
            return

        table = Table(title="Resumable Jobs", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Job ID", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Dataset", style="magenta")
        table.add_column("Progress", justify="right")

        for i, job in enumerate(jobs, 1):
            progress_pct = (
                (job["generated_count"] / job["target_questions"] * 100)
                if job["target_questions"] > 0
                else 0
            )
            progress_str = (
                f"{job['generated_count']}/{job['target_questions']} ({progress_pct:.0f}%)"
            )
            table.add_row(str(i), job["job_id"], job["status"], job["dataset_name"], progress_str)

        console.print(table)

        choices = [str(i) for i in range(1, len(jobs) + 1)] + ["c"]
        choice = Prompt.ask(
            "\n[cyan]Select job number to resume (or c to cancel)[/cyan]",
            choices=choices,
            default="c",
        )

        if choice == "c":
            return

        job_id = jobs[int(choice) - 1]["job_id"]
        console.print(f"\n[green]Resuming job:[/green] {job_id}")
    finally:
        state.close()


def _show_stats_menu():
    """Show statistics."""
    state = StateManager()
    try:
        stats = state.get_statistics()
    finally:
        state.close()

    console.print(Panel.fit("[bold cyan]Statistics[/bold cyan]", box=box.DOUBLE))
    console.print(f"Total Jobs: {stats['total_jobs']}")
    console.print(f"Completed: {stats['completed_jobs']}")
    console.print(f"Running: {stats['running_jobs']}")
    console.print(f"Paused: {stats['paused_jobs']}")
    console.print(f"Total MCQs Generated: {stats['total_mcqs']}")


def _run_export_menu():
    """Run the export menu."""
    state = StateManager()
    try:
        jobs = state.list_jobs(status="completed")

        if not jobs:
            console.print("[yellow]No completed jobs to export[/yellow]")
            return

        table = Table(title="Completed Jobs", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Job ID", style="cyan")
        table.add_column("Dataset", style="magenta")
        table.add_column("Generated", justify="right")

        for i, job in enumerate(jobs, 1):
            table.add_row(str(i), job["job_id"], job["dataset_name"], str(job["generated_count"]))

        console.print(table)

        choices = [str(i) for i in range(1, len(jobs) + 1)]
        choice = Prompt.ask(
            "\n[cyan]Select job number to export[/cyan]", choices=choices + ["c"], default="c"
        )

        if choice == "c":
            return

        job_id = jobs[int(choice) - 1]["job_id"]
        _export_job_results(job_id, state)
    finally:
        state.close()


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

    try:
        loop = asyncio.get_running_loop()
        loop.call_soon(_cancel_current_task)
    except RuntimeError:
        pass


def _cancel_current_task():
    """Cancel the currently running async task."""
    try:
        task = asyncio.current_task()
        if task and not task.done():
            task.cancel()
    except RuntimeError:
        pass


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

    try:
        query = Prompt.ask(
            "[cyan]Enter search query[/cyan] (e.g., 'sentiment', 'qa', 'text classification')"
        )
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return

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
        console.print("  [dim]Ctrl+C - Cancel[/dim]")

        try:
            action = Prompt.ask(
                "\n[cyan]Action[/cyan]",
                choices=["n", "q", "c"],
                default="q",
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled by user.[/yellow]")
            return

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

    choices = [str(i) for i in range(1, len(all_results) + 1)] + ["c", "q"]
    try:
        choice = Prompt.ask(
            "\n[cyan]Select dataset number (or c to cancel, q to quit)[/cyan]",
            choices=choices,
            default="c",
        )
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return

    if choice in ["c", "q"]:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    selected = all_results[int(choice) - 1]
    dataset_name = selected["id"]

    console.print(f"\n[green]Selected:[/green] {dataset_name}")
    console.print(f"   Downloads: {selected['downloads']:,} | Likes: {selected['likes']:,}")

    try:
        if not Confirm.ask("\n[cyan]Proceed with this dataset?[/cyan]"):
            console.print("[yellow]Cancelled.[/yellow]")
            return
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return

    console.print("\n[cyan]Generation Mode:[/cyan]")
    console.print("  [cyan]1[/cyan] - Limited (specify number of questions)")
    console.print("  [cyan]2[/cyan] - Continuous (generate until cancelled/paused)")

    try:
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
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return

    console.print("\n[bold cyan]Starting generation...[/bold cyan]")
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
        # Merge with existing root mcqs.json instead of overwriting to avoid
        # losing MCQs from other jobs. We key entries by
        # metadata.source_document when available.
        if root_path.exists():
            try:
                existing = json.loads(root_path.read_text(encoding="utf-8"))
                existing_mcqs = existing.get("mcqs", [])
            except Exception:
                existing = {
                    "generated_at": datetime.now().isoformat(),
                    "dataset": None,
                    "total_questions": 0,
                    "mcqs": [],
                }
                existing_mcqs = []

            # Build map by source_document
            merged_map = {}
            others = []
            for m in existing_mcqs:
                key = m.get("metadata", {}).get("source_document")
                if key:
                    merged_map[key] = m
                else:
                    others.append(m)

            for m in serializable_mcqs:
                key = m.get("metadata", {}).get("source_document")
                if key:
                    merged_map[key] = m
                else:
                    others.append(m)

            merged_mcqs = list(merged_map.values()) + others
            existing["mcqs"] = merged_mcqs
            existing["total_questions"] = len(merged_mcqs)
            existing["generated_at"] = datetime.now().isoformat()

            tmp_root.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            tmp_root.replace(root_path)
        else:
            tmp_root.write_text(
                json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
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
    resume_job_id: str | None = None,
    checkpoint_interval: int = 10,
    provider_url: str | None = None,
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
                    with open(json_path, encoding="utf-8") as f:
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
                    # If this was a resumed job, persist a final checkpoint and
                    # mark the job as paused so the CLI reflects the true state.
                    if resume_job_id:
                        try:
                            # Best-effort: infer last processed index from the
                            # last MCQ's metadata if available.
                            if mcqs:
                                try:
                                    last_md = mcqs[-1].get("metadata", {})
                                    # metadata.source_document is like '<dataset>_<index>'
                                    sd = last_md.get("source_document", "")
                                    last_index = int(sd.split("_")[-1])
                                except Exception:
                                    last_index = max(0, 0)
                            else:
                                last_index = max(0, 0)

                            # Save checkpoint (processed_indices optional here)
                            await generator._save_checkpoint(
                                job_id=resume_job_id,
                                last_index=last_index,
                                processed_indices=[],
                                generated_count=len(mcqs),
                            )
                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: failed to save checkpoint: {e}[/yellow]"
                            )

                        try:
                            generator.state.update_job_status(resume_job_id, "paused")
                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: failed to set job status to paused: {e}[/yellow]"
                            )

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
                            # Merge current job autosave into root `mcqs.json` to avoid
                            # overwriting MCQs from other jobs. We match on
                            # `metadata.source_document` (format: <dataset>_<index>)
                            try:
                                new_data = json.loads(src.read_text(encoding="utf-8"))
                                new_mcqs = new_data.get("mcqs", [])

                                if dst.exists():
                                    try:
                                        existing = json.loads(dst.read_text(encoding="utf-8"))
                                        existing_mcqs = existing.get("mcqs", [])
                                    except Exception:
                                        existing = {
                                            "generated_at": datetime.now().isoformat(),
                                            "dataset": None,
                                            "total_questions": 0,
                                            "mcqs": [],
                                        }
                                        existing_mcqs = []
                                else:
                                    existing = {
                                        "generated_at": datetime.now().isoformat(),
                                        "dataset": None,
                                        "total_questions": 0,
                                        "mcqs": [],
                                    }
                                    existing_mcqs = []

                                # Build a map keyed by source_document to preserve and
                                # update existing entries without losing other jobs'
                                merged_map = {}
                                others = []
                                for m in existing_mcqs:
                                    key = m.get("metadata", {}).get("source_document")
                                    if key:
                                        merged_map[key] = m
                                    else:
                                        others.append(m)

                                for m in new_mcqs:
                                    key = m.get("metadata", {}).get("source_document")
                                    if key:
                                        merged_map[key] = m
                                    else:
                                        others.append(m)

                                merged_mcqs = list(merged_map.values()) + others
                                existing["mcqs"] = merged_mcqs
                                existing["total_questions"] = len(merged_mcqs)
                                existing["generated_at"] = datetime.now().isoformat()

                                tmp = dst.with_suffix(dst.suffix + ".tmp")
                                tmp.write_text(
                                    json.dumps(existing, indent=2, ensure_ascii=False),
                                    encoding="utf-8",
                                )
                                tmp.replace(dst)
                            except Exception:
                                # If merging fails for any reason, fall back to
                                # copying the autosave file instead of crashing.
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
    resume: str | None = typer.Option(None, "--resume", help="Job ID to resume"),
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
    job_id: str = typer.Argument(None, help="Job ID to resume"),
    output: str = typer.Option("mcqs.json", "--output", "-o", help="Output file"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Select job interactively"),
):
    """Resume an interrupted job."""

    # Interactive mode: show paused jobs and let user select one
    if interactive:
        state = StateManager()
        try:
            # Get paused and running jobs (jobs that can be resumed)
            paused_jobs = state.list_jobs(status="paused")
            running_jobs = state.list_jobs(status="running")

            # Combine paused and running jobs
            jobs = paused_jobs + running_jobs

            if not jobs:
                console.print("[yellow]No resumable jobs found (paused or running).[/yellow]")
                return

            # Display jobs in a table
            table = Table(title="Resumable Jobs (Paused/Running)", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Dataset", style="magenta")
            table.add_column("Progress", justify="right")
            table.add_column("Created", style="blue")

            for i, job in enumerate(jobs, 1):
                progress_pct = (
                    (job["generated_count"] / job["target_questions"] * 100)
                    if job["target_questions"] > 0
                    else 0
                )
                progress_str = (
                    f"{job['generated_count']}/{job['target_questions']} ({progress_pct:.0f}%)"
                )
                table.add_row(
                    str(i),
                    job["job_id"],
                    job["status"],
                    job["dataset_name"],
                    progress_str,
                    str(job["created_at"]),
                )

            console.print(table)

            # Let user select a job
            choices = [str(i) for i in range(1, len(jobs) + 1)]
            choice = Prompt.ask(
                "\n[cyan]Select job number to resume[/cyan]",
                choices=choices,
            )

            job_id = jobs[int(choice) - 1]["job_id"]
            console.print(f"\n[green]Selected:[/green] {job_id}")

        finally:
            state.close()

    if not job_id:
        console.print("[red]Error: Please provide a job ID or use --interactive/-i flag.[/red]")
        raise typer.Exit(1)

    # Load job progress and close the StateManager before starting the
    # generation loop. Keeping the connection open across the async run
    # can cause concurrent write transactions and DuckDB "write-write
    # conflict" errors when the generator also writes state. Close early
    # so the generator may open its own connection safely.
    state = StateManager()
    progress_info = state.get_job_progress(job_id)

    # Ensure DB counts match exports before resuming. If mcq_results rows
    # are missing (due to prior partial failures), attempt a best-effort
    # restore from the job exports and sync the generated_count so the CLI
    # and generator see consistent state.
    try:
        db_count = state.count_mcq_rows(job_id)
        if db_count != progress_info.get("generated_count", 0):
            console.print(
                f"[yellow]Inconsistent DB counts detected (jobs.generated_count={progress_info.get('generated_count')} vs mcq_results={db_count}). Attempting repair from exports...[/yellow]"
            )
            restored = state.restore_missing_mcqs(job_id)
            if restored:
                console.print(f"[green]Restored {restored} MCQs from exports into DB.[/green]")
            # Re-read progress info after repair
            progress_info = state.get_job_progress(job_id)
    except Exception as e:
        console.print(f"[yellow]Warning: failed to verify/repair DB before resume: {e}[/yellow]")

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
def list_jobs(
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive menu to manage jobs"
    ),
    fix_stale: bool = typer.Option(
        False, "--fix-stale", "-f", help="Auto-fix stale jobs (mark as paused)"
    ),
):
    """List all jobs."""
    state = StateManager()
    try:
        stale_jobs = state.get_stale_jobs(stale_minutes=5)
        if stale_jobs:
            console.print(
                f"[yellow]Warning: Found {len(stale_jobs)} stale job(s) that may have crashed:[/yellow]"
            )
            for j in stale_jobs:
                console.print(f"  - {j['job_id']}: last updated {j.get('updated_at', 'unknown')}")

            if fix_stale:
                fixed = state.fix_stale_jobs(stale_minutes=5, mark_as="paused")
                console.print(f"[green]Fixed {fixed} stale job(s) by marking as paused[/green]")
            else:
                console.print("[dim]Run with --fix-stale to auto-mark these as paused[/dim]")
            console.print()

        jobs = state.list_jobs(status=status)

        if not jobs:
            console.print("[yellow]No jobs found[/yellow]")
            return

        if interactive:
            _run_interactive_job_menu(jobs, state)
            return

        _display_jobs_table(jobs)

    finally:
        state.close()


def _display_jobs_table(jobs: list[dict]) -> None:
    """Display jobs in a table."""
    table = Table(title="MCQ Generation Jobs", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Job ID", style="cyan", no_wrap=True)
    table.add_column("Dataset", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Progress", justify="right")
    table.add_column("Created", style="blue")

    for i, job in enumerate(jobs, 1):
        progress_pct = (
            (job["generated_count"] / job["target_questions"] * 100)
            if job["target_questions"] > 0
            else 0
        )
        progress_str = f"{job['generated_count']}/{job['target_questions']} ({progress_pct:.0f}%)"

        table.add_row(
            str(i),
            job["job_id"],
            job["dataset_name"],
            job["status"],
            progress_str,
            str(job["created_at"]),
        )

    console.print(table)


def _run_interactive_job_menu(jobs: list[dict], state: StateManager) -> None:
    """Run interactive job management menu."""
    while True:
        table = Table(title="MCQ Generation Jobs", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Job ID", style="cyan", no_wrap=True)
        table.add_column("Dataset", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Progress", justify="right")
        table.add_column("Created", style="blue")

        for i, job in enumerate(jobs, 1):
            progress_pct = (
                (job["generated_count"] / job["target_questions"] * 100)
                if job["target_questions"] > 0
                else 0
            )
            progress_str = (
                f"{job['generated_count']}/{job['target_questions']} ({progress_pct:.0f}%)"
            )

            table.add_row(
                str(i),
                job["job_id"],
                job["dataset_name"],
                job["status"],
                progress_str,
                str(job["created_at"]),
            )

        console.print(table)

        console.print("\n[dim]Options:[/dim]")
        console.print("  [cyan]1-[/cyan]<n> - Select job number")
        console.print("  [cyan]r[/cyan] - Refresh list")
        console.print("  [cyan]q[/cyan] - Quit")
        console.print("  [dim]Ctrl+C - Cancel[/dim]")

        choices = [str(i) for i in range(1, len(jobs) + 1)] + ["r", "q"]
        try:
            choice = Prompt.ask(
                "\n[cyan]Select option[/cyan]",
                choices=choices,
                default="q",
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled by user.[/yellow]")
            break

        if choice == "q":
            break

        if choice == "r":
            jobs = state.list_jobs()
            console.clear()
            continue

        job_index = int(choice) - 1
        if 0 <= job_index < len(jobs):
            selected_job = jobs[job_index]
            state_closed = _manage_single_job(selected_job, state)
            if state_closed:
                # State was closed to spawn subprocess, recreate it
                state = StateManager()
            jobs = state.list_jobs()
            console.clear()


def _manage_single_job(job: dict, state: StateManager) -> bool:
    """Manage a single job (start/stop/view/delete). Returns True if state was closed."""
    job_id = job["job_id"]
    current_status = job["status"]
    state_closed = False

    while True:
        console.print(f"\n[bold cyan]Job:[/bold cyan] {job_id}")
        console.print(f"[bold cyan]Dataset:[/bold cyan] {job['dataset_name']}")
        console.print(f"[bold cyan]Status:[/bold cyan] {current_status}")
        console.print(
            f"[bold cyan]Progress:[/bold cyan] {job.get('generated_count', 0)}/{job.get('target_questions', '?')}"
        )

        options = []
        if current_status == "paused":
            options.append("s - Start/Resume job")
            options.append("p - (already paused)")
        elif current_status == "running":
            options.append("p - Pause/Stop job")
            job_info = state.get_job(job_id)
            stale = state.get_stale_jobs(stale_minutes=1)
            is_stale = any(j["job_id"] == job_id for j in stale)
            if is_stale:
                options.append("s - Restart stalled job")
            else:
                options.append("s - (already running)")
        elif current_status == "completed":
            options.append("e - Export results")
        elif current_status == "failed":
            options.append("r - Retry/Reset job")
        else:
            options.append("s - Start job")

        options.append("v - View details")
        options.append("l - View logs")
        options.append("d - Delete job")
        options.append("b - Back to list")

        console.print("\n[dim]Options:[/dim]")
        for opt in options:
            console.print(f"  [cyan]{opt}[/cyan]")
        console.print("  [dim]Ctrl+C - Cancel[/dim]")

        try:
            choice = Prompt.ask(
                "\n[cyan]Select action[/cyan]",
                choices=["s", "p", "v", "b", "e", "r", "d", "l"],
                default="b",
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled by user.[/yellow]")
            return state_closed

        if choice == "b":
            return state_closed

        if choice == "d":
            confirm = Confirm.ask(
                f"\n[red]Are you sure you want to delete job '{job_id}'?[/red]\nThis will delete all MCQs and checkpoints for this job."
            )
            if confirm:
                success = state.delete_job(job_id)
                if success:
                    console.print(f"[green]Job {job_id} deleted successfully[/green]")
                    return state_closed
                else:
                    console.print(f"[red]Failed to delete job {job_id}[/red]")
            continue

        if choice == "v":
            _display_job_details(job_id, state)
            current_status = state.get_job_progress(job_id)["status"]
            continue

        if choice == "l":
            log_file = Path(f"mcq_{job_id}.log")
            if log_file.exists():
                console.print(f"\n[bold cyan]Last 20 lines of {log_file}:[/bold cyan]\n")
                with open(log_file) as f:
                    lines = f.readlines()
                    for line in lines[-20:]:
                        console.print(line.rstrip())
                console.print()
            else:
                console.print(f"[yellow]No log file found at {log_file}[/yellow]")
            continue

        if choice == "s" and current_status == "paused":
            console.print(f"[cyan]Starting job {job_id}...[/cyan]")
            log_file = Path(f"mcq_{job_id}.log")
            console.print(f"[yellow]Job will run in background. Log: {log_file}[/yellow]")
            try:
                # Close DB connection before spawning subprocess to avoid lock conflicts
                state.close()
                state_closed = True
                # Give DuckDB time to release the lock
                import time

                time.sleep(0.5)
                with open(log_file, "w") as log:
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "src.mcq_generator.cli", "resume", job_id],
                        cwd=Path.cwd(),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    # Wait briefly to see if process starts successfully
                    import time

                    time.sleep(2)
                    if proc.poll() is not None:
                        # Process exited immediately
                        console.print(f"[red]Job failed to start. Check log: {log_file}[/red]")
                        return state_closed
                    else:
                        console.print(
                            f"[green]Job {job_id} started in background (PID: {proc.pid})[/green]"
                        )
            except Exception as e:
                console.print(f"[red]Failed to start job: {e}[/red]")
            return state_closed

        if choice == "s" and current_status == "running":
            stale = state.get_stale_jobs(stale_minutes=1)
            is_stale = any(j["job_id"] == job_id for j in stale)
            if is_stale:
                console.print(f"[yellow]Restarting stalled job {job_id}...[/yellow]")
                log_file = Path(f"mcq_{job_id}.log")
                try:
                    # Close DB connection before spawning subprocess to avoid lock conflicts
                    state.close()
                    state_closed = True
                    # Give DuckDB time to release the lock
                    import time

                    time.sleep(0.5)
                    with open(log_file, "a") as log:
                        proc = subprocess.Popen(
                            [sys.executable, "-m", "src.mcq_generator.cli", "resume", job_id],
                            cwd=Path.cwd(),
                            stdout=log,
                            stderr=subprocess.STDOUT,
                        )
                        # Wait briefly to see if process starts successfully
                        import time

                        time.sleep(2)
                        if proc.poll() is not None:
                            console.print(
                                f"[red]Job failed to restart. Check log: {log_file}[/red]"
                            )
                        else:
                            console.print(
                                f"[green]Job {job_id} restarted in background (PID: {proc.pid})[/green]"
                            )
                except Exception as e:
                    console.print(f"[red]Failed to restart job: {e}[/red]")
                return state_closed

        if choice == "p" and current_status == "running":
            state.update_job_status(job_id, "paused")
            console.print(f"[yellow]Job {job_id} paused/stopped[/yellow]")
            current_status = "paused"

        if choice == "e" and current_status == "completed":
            _export_job_results(job_id, state)

        if choice == "r" and current_status == "failed":
            state.update_job_status(job_id, "paused")
            console.print(f"[green]Job {job_id} reset to paused state[/green]")
            current_status = "paused"

    return state_closed


def _display_job_details(job_id: str, state: StateManager) -> None:
    """Display detailed job information with live logs."""
    progress = state.get_job_progress(job_id)

    layout = Layout()
    layout.split_column(Layout(name="header"), Layout(name="info"), Layout(name="logs"))

    layout["header"].update(Panel(f"[bold cyan]Job: {job_id}[/bold cyan]", box=box.DOUBLE))

    info_table = Table(box=box.SIMPLE)
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value", style="white")

    info_table.add_row("Dataset", progress["dataset_name"])
    info_table.add_row(
        "Status",
        f"[{'green' if progress['status'] == 'running' else 'yellow' if progress['status'] == 'paused' else 'blue'}]{progress['status']}[/]",
    )
    info_table.add_row("Target", str(progress["target_questions"]))
    info_table.add_row("Generated", str(progress["generated_count"]))
    info_table.add_row("Progress", f"{progress['progress_pct']:.1f}%")
    info_table.add_row("Created", str(progress["created_at"]))
    info_table.add_row("Updated", str(progress["updated_at"]))

    layout["info"].update(Panel(info_table, title="[bold]Job Info[/bold]"))

    recent_mcqs = state.conn.execute(
        """
        SELECT mcq_json, quality_score, created_at 
        FROM mcq_results 
        WHERE job_id = ?
        ORDER BY created_at DESC 
        LIMIT 5
        """,
        [job_id],
    ).fetchall()

    if recent_mcqs:
        logs_text = ""
        for mcq_json, quality, created in recent_mcqs:
            mcq = json.loads(mcq_json)
            question = mcq.get("question", "N/A")[:60]
            logs_text += f"[dim]{created}[/dim] | [green]Q:{quality:.0f}[/green] | {question}...\n"

        layout["logs"].update(
            Panel(
                logs_text,
                title="[bold]Recent MCQ Outputs (Live Feed)[/bold]",
                box=box.ROUNDED,
            )
        )
    else:
        layout["logs"].update(
            Panel(
                "[dim]No MCQs generated yet...[/dim]",
                title="[bold]Recent MCQ Outputs (Live Feed)[/bold]",
                box=box.ROUNDED,
            )
        )

    console.print(layout)


def _export_job_results(job_id: str, state: StateManager) -> None:
    """Export job results to a file."""
    output_file = Prompt.ask(
        "[cyan]Output file[/cyan]",
        default=f"mcqs_{job_id}.json",
    )
    mcqs = state.get_mcqs(job_id)
    with open(output_file, "w") as f:
        json.dump(mcqs, f, indent=2)
    console.print(f"[green]Exported {len(mcqs)} MCQs to {output_file}[/green]")


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
    min_quality: float | None = typer.Option(
        None, "--min-quality", help="Minimum quality score (0-100)"
    ),
    max_quality: float | None = typer.Option(
        None, "--max-quality", help="Maximum quality score (0-100)"
    ),
    difficulty: str | None = typer.Option(
        None, "--difficulty", help="Filter by difficulty: Easy/Medium/Hard"
    ),
    topic: str | None = typer.Option(None, "--topic", help="Filter by topic category substring"),
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


@app.command()
def delete(
    job_id: str = typer.Argument(..., help="Job ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Delete a job and all its related data (MCQs, checkpoints)."""
    state = StateManager()
    try:
        job = state.get_job(job_id)
        if not job:
            console.print(f"[red]Error: Job '{job_id}' not found.[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]Job:[/bold] {job_id}")
        console.print(f"[bold]Dataset:[/bold] {job['dataset_name']}")
        console.print(f"[bold]Status:[/bold] {job['status']}")
        console.print(f"[bold]Generated:[/bold] {job['generated_count']}/{job['target_questions']}")

        if not force:
            confirm = Confirm.ask(
                "\n[red]Are you sure you want to delete this job?[/red]\nThis will permanently delete all MCQs and checkpoints for this job."
            )
            if not confirm:
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return

        success = state.delete_job(job_id)
        if success:
            console.print(f"[green]Job {job_id} deleted successfully[/green]")
        else:
            console.print(f"[red]Failed to delete job {job_id}[/red]")
            raise typer.Exit(1)

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
