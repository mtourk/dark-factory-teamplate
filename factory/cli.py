"""
FactoryFlow CLI: Primary interface for dark factory orchestration.

Commands per DARK_FACTORY_MASTER_PLAN.md §4.2:
- doctor: system diagnostics
- init: initialize factory project
- feature: start new feature (full BMAD → implementation → deploy cycle)
- express: quick change (abbreviated cycle)
- run: execute factory workflow (claim → implement → deploy → close)
- run -Once: single run, exit
- pause: pause factory processing
- resume-queue: resume paused queue
- emergency-stop: block new merges, record incident
- queue: list eligible issues
- status: show factory status
- status -RunId: show specific run status
- validate -RunId: run verification on specific run
- report -RunId: generate delivery report
- benchmark: measure model performance
- learn -RunId: extract and promote lessons
- decisions: list all ADRs
- decide: human decision on escalated item
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from factory.state import init_db, get_db_session
from factory.config import load_config
from factory.models import Project, Run

app = typer.Typer(
    name="factory",
    help="Dark Factory FactoryFlow Orchestrator - Windows-native autonomous delivery",
    no_args_is_help=True,
)

console = Console()


@app.command()
def doctor() -> None:
    """
    System diagnostics: verify environment, tooling, Ollama, GitHub, database.

    Exit code: 0 if healthy, 1 if blockers found.
    """
    console.print("[bold blue]Factory Doctor[/bold blue]")
    console.print()

    checks = [
        ("Python version", _check_python),
        ("Working directory", _check_workdir),
        ("Database connection", _check_db),
        ("Ollama endpoint", _check_ollama),
        ("GitHub CLI auth", _check_gh_auth),
        ("Git repository", _check_git),
    ]

    results = []
    for check_name, check_fn in checks:
        try:
            status, message = check_fn()
            results.append((check_name, status, message))
            icon = "✓" if status else "✗"
            color = "green" if status else "red"
            console.print(f"[{color}]{icon}[/{color}] {check_name}: {message}")
        except Exception as e:
            results.append((check_name, False, str(e)))
            console.print(f"[red]✗[/red] {check_name}: ERROR - {e}")

    console.print()
    passed = sum(1 for _, status, _ in results if status)
    total = len(results)
    console.print(f"[bold]{passed}/{total} checks passed[/bold]")

    if passed < total:
        sys.exit(1)


@app.command()
def init(project_path: Optional[str] = typer.Option(None, help="Path to target project")) -> None:
    """
    Initialize factory: create schema, config dirs, templates.

    Required before first run. Idempotent (safe to re-run).
    """
    console.print("[bold blue]Factory Init[/bold blue]")

    try:
        db_session = init_db()
        console.print("[green]✓[/green] Database initialized")

        config_dir = Path(".factory/config")
        config_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Config directory: {config_dir}")

        console.print("[green]✓[/green] Factory initialized and ready")
    except Exception as e:
        console.print(f"[red]✗[/red] Initialization failed: {e}")
        sys.exit(1)


@app.command()
def feature(goal: str = typer.Argument(..., help="Feature goal (e.g., 'Add ROI calculator')")) -> None:
    """
    Create a new feature request and submit to backlog.

    Syntax: factory feature "<goal>"

    Creates GitHub issue with factory:ready label and starts workflow.
    """
    console.print(f"[bold blue]Create Feature[/bold blue]: {goal}")
    console.print("[yellow]Feature submission not yet implemented (Phase 4 backlog scheduler)[/yellow]")


@app.command()
def express(change: str = typer.Argument(..., help="Quick change description")) -> None:
    """
    Submit a small/quick change (abbreviated cycle, fewer verification steps).

    Syntax: factory express "<description>"

    Faster than full feature but still verified and tested.
    """
    console.print(f"[bold blue]Express Change[/bold blue]: {change}")
    console.print("[yellow]Express mode not yet implemented (Phase 4 backlog scheduler)[/yellow]")


@app.command()
def run(
    once: bool = typer.Option(False, "--Once", help="Process one item and exit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without modifying state"),
) -> None:
    """
    Execute factory workflow: claim → implement → deploy → close.

    Runs continuously selecting eligible items from backlog.

    Options:
    - run: continuous loop until queue empty or stop requested
    - run --Once: process one item and exit
    - run --dry-run: show what would happen, no changes
    """
    console.print("[bold blue]Factory Run[/bold blue]")
    if once:
        console.print("[cyan]Mode: once (process one item, exit)[/cyan]")
    if dry_run:
        console.print("[cyan]Mode: dry-run (simulation only)[/cyan]")
    console.print("[yellow]Factory run not yet implemented (Phase 4+ backlog, scheduler)[/yellow]")


@app.command()
def pause() -> None:
    """
    Pause factory processing: stop claiming new items after current run completes.

    New items remain eligible but will not be claimed until resumed.
    """
    console.print("[bold blue]Factory Pause[/bold blue]")
    console.print("[yellow]Pause command not yet implemented (Phase 4 state management)[/yellow]")


@app.command()
def resume_queue() -> None:
    """Resume factory queue after pause."""
    console.print("[bold blue]Factory Resume[/bold blue]")
    console.print("[yellow]Resume command not yet implemented (Phase 4 state management)[/yellow]")


@app.command()
def emergency_stop(reason: Optional[str] = typer.Option(None, help="Reason for emergency stop")) -> None:
    """
    Emergency stop: block all new claims and disable pending auto-merges.

    Used during production incidents. Requires explicit resume to clear.

    Options:
    - factory emergency-stop: immediate stop
    - factory emergency-stop --reason "Production health unknown": stop with reason
    """
    console.print("[bold blue]Emergency Stop[/bold blue]")
    if reason:
        console.print(f"[yellow]Reason:[/yellow] {reason}")
    console.print("[yellow]Emergency stop not yet implemented (Phase 14 recovery)[/yellow]")


@app.command()
def queue() -> None:
    """
    List eligible items waiting for factory to claim.

    Shows issue number, title, priority, claim status.
    """
    console.print("[bold blue]Factory Queue[/bold blue]")
    console.print("[yellow]Queue listing not yet implemented (Phase 4 backlog scheduler)[/yellow]")


@app.command()
def status(run_id: Optional[str] = typer.Option(None, help="Specific run ID")) -> None:
    """
    Show factory status: queue, running, completed, failures.

    Options:
    - factory status: overall factory status
    - factory status --RunId RUN-abc12345: detailed status of one run
    """
    console.print("[bold blue]Factory Status[/bold blue]")
    if run_id:
        console.print(f"[cyan]Run: {run_id}[/cyan]")
    console.print("[yellow]Status command not yet implemented (Phase 3 state query)[/yellow]")


@app.command()
def validate(run_id: str = typer.Option(..., help="Run ID to validate")) -> None:
    """
    Manually trigger verification on a specific run.

    Syntax: factory validate --RunId RUN-abc12345
    """
    console.print(f"[bold blue]Validate Run[/bold blue]: {run_id}")
    console.print("[yellow]Manual validation not yet implemented (Phase 10 verification)[/yellow]")


@app.command()
def report(run_id: str = typer.Option(..., help="Run ID to report")) -> None:
    """
    Generate delivery report for a completed run.

    Syntax: factory report --RunId RUN-abc12345

    Output: evidence manifest, retrospective, lessons learned.
    """
    console.print(f"[bold blue]Delivery Report[/bold blue]: {run_id}")
    console.print("[yellow]Report generation not yet implemented (Phase 15 evidence)[/yellow]")


@app.command()
def benchmark() -> None:
    """
    Run model benchmarking: measure latency, throughput, memory, capability.

    Outputs: baseline.md with performance metrics for all roles.
    """
    console.print("[bold blue]Model Benchmark[/bold blue]")
    console.print("[yellow]Benchmarking not yet implemented (Phase 6 gateway)[/yellow]")


@app.command()
def learn(run_id: str = typer.Option(..., help="Run ID to extract lessons from")) -> None:
    """
    Extract candidate lessons from a completed run.

    Syntax: factory learn --RunId RUN-abc12345

    Lessons require evidence validation and policy approval before promotion to certified knowledge.
    """
    console.print(f"[bold blue]Learn from Run[/bold blue]: {run_id}")
    console.print("[yellow]Learning system not yet implemented (Phase 15 certified memory)[/yellow]")


@app.command()
def decisions() -> None:
    """
    List all architecture decision records (ADRs).

    Shows: ADR ID, title, status, date, phase.
    """
    console.print("[bold blue]Architecture Decisions[/bold blue]")
    console.print("[yellow]ADR listing not yet implemented (Phase 1+ decisions)[/yellow]")


@app.command()
def decide(
    decision_id: str = typer.Option(..., help="Decision ID (e.g., 'issue-42-roi-formula')"),
    option: str = typer.Option(..., help="Chosen option (e.g., 'linear', 'exponential')"),
) -> None:
    """
    Record a human decision on an escalated item.

    Syntax: factory decide --DecisionId issue-42-roi-formula --Option linear

    Used when factory encounters strategic ambiguity that needs business input.
    Records decision and resumes processing with that item.
    """
    console.print(f"[bold blue]Decide[/bold blue]: {decision_id}")
    console.print(f"[cyan]Option: {option}[/cyan]")
    console.print("[yellow]Decision recording not yet implemented (Phase 7 strategic ambiguity)[/yellow]")


def _check_python() -> tuple[bool, str]:
    """Check Python version."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 12):
        return True, f"Python {version}"
    return False, f"Python {version} (requires 3.12+)"


def _check_workdir() -> tuple[bool, str]:
    """Check working directory is factory repo."""
    if Path(".factory").exists() or Path("DARK_FACTORY_MASTER_PLAN.md").exists():
        return True, str(Path.cwd())
    return False, "Not in factory repository"


def _check_db() -> tuple[bool, str]:
    """Check SQLite database connection."""
    try:
        session = get_db_session()
        session.close()
        return True, "SQLite operational"
    except Exception as e:
        return False, f"Database error: {e}"


def _check_ollama() -> tuple[bool, str]:
    """Check Ollama endpoint is responding."""
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            return True, "Ollama 11434 responding"
        return False, f"Ollama responded with {response.status_code}"
    except Exception as e:
        return False, f"Ollama unreachable: {e}"


def _check_gh_auth() -> tuple[bool, str]:
    """Check GitHub CLI authentication."""
    try:
        import subprocess
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Extract username from output
            return True, "GitHub authenticated"
        return False, "GitHub not authenticated (run: gh auth login)"
    except Exception as e:
        return False, f"GitHub CLI error: {e}"


def _check_git() -> tuple[bool, str]:
    """Check Git repository state."""
    try:
        import subprocess
        result = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "Git repository ready"
        return False, "Not a Git repository"
    except Exception as e:
        return False, f"Git error: {e}"


if __name__ == "__main__":
    app()
