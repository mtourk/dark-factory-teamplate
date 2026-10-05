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
- resume: resume runs interrupted mid-flight
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
- profile: manage per-project profiles (create/list/show) — see factory/profiles.py

This factory is a reusable template/engine (master plan §17): every command
that acts on a managed project operates against a *profile*, selected via
the global --profile option, the FACTORY_PROFILE environment variable, or
implicitly when exactly one profile exists. See profiles/README.md.
"""

import sys
import time
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from factory.state import (
    init_db, get_db_session, ensure_project,
    list_resumable_runs, latest_checkpoint, get_run, list_stages,
)
from factory.config import load_config
from factory.profiles import (
    NoActiveProfileError,
    Profile,
    ProfileNotFoundError,
    create_profile,
    list_profiles,
    load_profile,
    resolve_active_profile,
)
from factory.backlog.github_adapter import GitHubAdapter
from factory.implementation.builder import BuilderCoordinator
from factory.implementation.orchestrator import ImplementationOrchestrator, ImplementationPhase
from factory.implementation.workspace import WorkspaceError, ensure_workspace
from factory.intake.local_sync import LocalProfileSync
from factory.sealed_qa.runner import stage_commands_from_profile_config

app = typer.Typer(
    name="factory",
    help="Dark Factory FactoryFlow Orchestrator - Windows-native autonomous delivery",
    no_args_is_help=True,
)
profile_app = typer.Typer(name="profile", help="Manage per-project profiles (factory/profiles.py).")
app.add_typer(profile_app, name="profile")

# This is a Windows-native CLI whose output uses ✓/✗/⚠ glyphs. Under a legacy
# console codepage (e.g. cp1252) writing those raises UnicodeEncodeError, so
# force UTF-8 on the standard streams at startup. Guarded for environments where
# the streams are already wrapped/replaced (e.g. pytest capture, pipes).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile to run against (see 'factory profile list')."
    ),
) -> None:
    """Dark Factory: select the active profile for this invocation."""
    ctx.obj = {"profile_name": profile}


def _resolve_profile_or_exit(ctx: typer.Context) -> Profile:
    """Resolve the active profile for the current command, or exit with a clear error."""
    explicit = (ctx.obj or {}).get("profile_name")
    try:
        return resolve_active_profile(explicit)
    except NoActiveProfileError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)


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
        ("Active profile", _check_profiles),
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
def feature(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="Feature goal (e.g., 'Add ROI calculator')"),
) -> None:
    """
    Create a new feature request and submit to backlog.

    Syntax: factory [--profile <name>] feature "<goal>"

    Creates GitHub issue with factory:ready label and starts workflow,
    against the active profile's target repository.
    """
    active_profile = _resolve_profile_or_exit(ctx)
    console.print(f"[bold blue]Create Feature[/bold blue]: {goal}")
    console.print(f"[cyan]Profile:[/cyan] {active_profile.name} ({active_profile.target_repo.repo_string})")
    console.print("[yellow]Feature submission not yet implemented (Phase 4 backlog scheduler)[/yellow]")


@app.command()
def express(
    ctx: typer.Context,
    change: str = typer.Argument(..., help="Quick change description"),
) -> None:
    """
    Submit a small/quick change (abbreviated cycle, fewer verification steps).

    Syntax: factory [--profile <name>] express "<description>"

    Faster than full feature but still verified and tested.
    """
    active_profile = _resolve_profile_or_exit(ctx)
    console.print(f"[bold blue]Express Change[/bold blue]: {change}")
    console.print(f"[cyan]Profile:[/cyan] {active_profile.name} ({active_profile.target_repo.repo_string})")
    console.print("[yellow]Express mode not yet implemented (Phase 4 backlog scheduler)[/yellow]")


FACTORY_READY_LABEL = "factory:ready"


def _sync_pending_profiles() -> None:
    """
    Pull in any repos the user chose to have created fresh via the intake
    worker's web UI at issue-submission time (factory/intake/local_sync.py),
    turning each into a local profile *before* profile resolution runs — so
    `run` can pick a just-created project the same way it picks a
    pre-existing one, with no separate manual step. Best-effort: a worker
    that's unreachable is a warning, not a reason to abort a run against an
    already-known profile.
    """
    try:
        synced = LocalProfileSync().sync_all()
        if synced:
            console.print(f"[green]✓[/green] Synced {synced} new profile(s) from intake worker")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Pending-profile sync skipped: {e}")


def _print_run_result(run_result) -> None:
    """Print an ImplementationRun's outcome (shared by `run` for each issue processed)."""
    if run_result.phase == ImplementationPhase.COMPLETE:
        console.print(
            f"  [green]✓ COMPLETE[/green] (attempt {run_result.attempt_number}, "
            f"{len(run_result.repair_outputs)} repair cycle(s))"
        )
    else:
        reason = run_result.stop_condition.value if run_result.stop_condition else "unknown"
        console.print(f"  [red]✗ STOPPED[/red]: {reason} (attempt {run_result.attempt_number})")


@app.command()
def run(
    ctx: typer.Context,
    once: bool = typer.Option(False, "--Once", help="Process one item and exit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without modifying state"),
    sync_profiles: bool = typer.Option(
        True,
        "--sync-profiles/--no-sync-profiles",
        help="Pull in repos created via the intake web UI before resolving the active profile",
    ),
) -> None:
    """
    Execute factory workflow: claim → implement → verify → repair → close.

    Nothing here is hardcoded to one project (master plan §17): which repo
    `run` acts on is decided entirely by the active profile, resolved the
    same way as every other command (--profile flag > FACTORY_PROFILE env
    var > the one profile on disk). That covers both cases from the
    intake flow — the user picking an existing repo, or choosing "create a
    new repo" while filing the issue — because the latter only differs in
    that its profile did not exist on disk until `_sync_pending_profiles()`
    (just above) pulled it in from the intake worker a moment ago.

    Options:
    - run: process every eligible issue in the active profile's repo
    - run --Once: process one item and exit
    - run --dry-run: show what would happen, no changes
    - run --no-sync-profiles: skip the intake-worker pending-profile sync
    """
    if sync_profiles:
        _sync_pending_profiles()

    active_profile = _resolve_profile_or_exit(ctx)
    console.print("[bold blue]Factory Run[/bold blue]")
    console.print(f"[cyan]Profile:[/cyan] {active_profile.name} ({active_profile.target_repo.repo_string})")
    if once:
        console.print("[cyan]Mode: once (process one item, exit)[/cyan]")
    if dry_run:
        console.print("[cyan]Mode: dry-run (simulation only)[/cyan]")

    github = GitHubAdapter(
        owner=active_profile.target_repo.owner,
        repo=active_profile.target_repo.name,
    )
    try:
        eligible = github.list_issues(state="open", labels=[FACTORY_READY_LABEL])
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list issues for {active_profile.target_repo.repo_string}: {e}")
        raise typer.Exit(code=1)

    if not eligible:
        console.print(f"[yellow]No '{FACTORY_READY_LABEL}' issues found.[/yellow]")
        return

    if dry_run:
        console.print(f"Would process {len(eligible)} issue(s):")
        for issue in eligible[:1] if once else eligible:
            console.print(f"  #{issue.number}: {issue.title}")
        return

    try:
        workspace_path = ensure_workspace(active_profile)
    except WorkspaceError as e:
        console.print(f"[red]✗[/red] Workspace preparation failed: {e}")
        raise typer.Exit(code=1)
    console.print(f"[cyan]Workspace:[/cyan] {workspace_path}")

    try:
        stage_commands = stage_commands_from_profile_config(active_profile.verification_commands)
    except ValueError as e:
        console.print(f"[red]✗[/red] Invalid verification_commands in profile '{active_profile.name}': {e}")
        raise typer.Exit(code=1)
    if not stage_commands:
        console.print(
            "[yellow]⚠[/yellow] No verification_commands configured on this profile — "
            "the gate will pass with zero stages run. See 'factory profile show'."
        )

    # Durable run state (FF-P21-01): persist Run/Stage rows so runs survive a
    # process restart and are later resumable. Best-effort — if DB setup fails
    # we degrade to an in-memory run rather than aborting the whole command.
    state_session = None
    try:
        state_session = init_db()  # create schema if needed + return a session
        ensure_project(
            state_session,
            project_id=active_profile.name,
            github_repo=active_profile.target_repo.repo_string,
        )
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] State persistence disabled (DB unavailable): {e}")
        state_session = None

    orchestrator = ImplementationOrchestrator(
        BuilderCoordinator(), state_session=state_session
    )
    to_process = eligible[:1] if once else eligible

    try:
        for issue in to_process:
            run_id = f"RUN-{active_profile.name}-{issue.number}-{int(time.time())}"
            console.print(f"[bold]→ Issue #{issue.number}[/bold]: {issue.title} ({run_id})")
            try:
                result = orchestrator.run_full_cycle(
                    run_id=run_id,
                    github_adapter=github,
                    issue_number=issue.number,
                    project_id=active_profile.name,
                    repo_root=workspace_path,
                    stage_commands=stage_commands,
                )
            except Exception as e:
                console.print(f"  [red]✗ ERROR[/red]: {e}")
                continue
            _print_run_result(result)
    finally:
        if state_session is not None:
            state_session.close()


@app.command()
def pause() -> None:
    """
    Pause factory processing: stop claiming new items after current run completes.

    New items remain eligible but will not be claimed until resumed.
    """
    console.print("[bold blue]Factory Pause[/bold blue]")
    console.print("[yellow]Pause command not yet implemented (Phase 4 state management)[/yellow]")


@app.command(name="resume")
def resume_queue(ctx: typer.Context) -> None:
    """
    Resume runs interrupted mid-flight (FF-P21-02).

    Finds persisted runs for the active profile whose status is non-terminal
    (implementing/verifying/repairing/...) — e.g. because the process was
    killed or a provider failed — and re-dispatches each through the normal
    build→verify→repair loop. Durable Run/Stage/Checkpoint state means a resume
    continues the task rather than losing it; full state-aware single-step
    resume (continue from the exact failed step) lands with agent handoff
    (FF-P27-01).
    """
    active_profile = _resolve_profile_or_exit(ctx)
    console.print("[bold blue]Factory Resume[/bold blue]")
    console.print(f"[cyan]Profile:[/cyan] {active_profile.name} ({active_profile.target_repo.repo_string})")

    try:
        session = init_db()
    except Exception as e:
        console.print(f"[red]✗[/red] State database unavailable: {e}")
        raise typer.Exit(code=1)

    try:
        resumable = list_resumable_runs(session, project_id=active_profile.name)
        if not resumable:
            console.print("[green]✓[/green] No interrupted runs to resume.")
            return

        console.print(f"Found {len(resumable)} interrupted run(s):")
        for r in resumable:
            cp = latest_checkpoint(session, r.id)
            where = f" @ {cp.current_operation}" if cp and cp.current_operation else ""
            console.print(f"  {r.id} (issue #{r.issue_number}, status={r.status}{where})")

        try:
            github = GitHubAdapter(
                owner=active_profile.target_repo.owner,
                repo=active_profile.target_repo.name,
            )
            workspace_path = ensure_workspace(active_profile)
            stage_commands = stage_commands_from_profile_config(active_profile.verification_commands)
        except (WorkspaceError, ValueError) as e:
            console.print(f"[red]✗[/red] Could not prepare resume context: {e}")
            raise typer.Exit(code=1)

        orchestrator = ImplementationOrchestrator(
            BuilderCoordinator(), state_session=session
        )
        for r in resumable:
            console.print(f"[bold]→ Resuming issue #{r.issue_number}[/bold] ({r.id})")
            try:
                result = orchestrator.run_full_cycle(
                    run_id=r.id,
                    github_adapter=github,
                    issue_number=r.issue_number,
                    project_id=active_profile.name,
                    repo_root=workspace_path,
                    stage_commands=stage_commands,
                )
            except Exception as e:
                console.print(f"  [red]✗ ERROR[/red]: {e}")
                continue
            _print_run_result(result)
    finally:
        session.close()


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
def queue(ctx: typer.Context) -> None:
    """
    List eligible items waiting for factory to claim, for the active profile.

    Shows issue number, title, priority, claim status.
    """
    active_profile = _resolve_profile_or_exit(ctx)
    console.print("[bold blue]Factory Queue[/bold blue]")
    console.print(f"[cyan]Profile:[/cyan] {active_profile.name} ({active_profile.target_repo.repo_string})")
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
    try:
        session = init_db()
    except Exception as e:
        console.print(f"[red]✗[/red] State database unavailable: {e}")
        raise typer.Exit(code=1)

    try:
        if run_id:
            run = get_run(session, run_id)
            if run is None:
                console.print(f"[yellow]No run found with id {run_id}.[/yellow]")
                return
            console.print(
                f"[cyan]Run {run.id}[/cyan] (issue #{run.issue_number}, project {run.project_id})"
            )
            console.print(f"  status={run.status}  stage={run.stage}  attempts={run.attempts}")
            if run.completed_at:
                console.print(f"  completed_at={run.completed_at}")
            stages = list_stages(session, run_id)
            if stages:
                console.print("  stages:")
                for s in stages:
                    err = f" — {s.error_message}" if s.error_message else ""
                    console.print(f"    [{s.status}] {s.stage_name} (attempt {s.attempt}){err}")
            cp = latest_checkpoint(session, run_id)
            if cp:
                console.print(
                    f"  last checkpoint: step={cp.step_id} status={cp.step_status} "
                    f"op={cp.current_operation} files={cp.modified_files}"
                )
            return

        # No run id: summarise interrupted runs across all projects.
        resumable = list_resumable_runs(session)
        if not resumable:
            console.print("[green]✓[/green] No interrupted runs. Use 'factory status --RunId <id>' for details.")
            return
        console.print(f"[yellow]{len(resumable)} interrupted run(s)[/yellow] (resume with 'factory resume'):")
        for r in resumable:
            console.print(f"  {r.id} — issue #{r.issue_number} ({r.project_id}): {r.status}")
    finally:
        session.close()


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


def _check_profiles() -> tuple[bool, str]:
    """Check that at least one profile exists (non-blocking: doctor can pass without one)."""
    names = list_profiles()
    if not names:
        return True, "No profiles yet (run 'factory profile create <name> --repo <url>')"
    try:
        active = resolve_active_profile()
        return True, f"{len(names)} profile(s), active: {active.name} ({active.target_repo.repo_string})"
    except NoActiveProfileError:
        return True, f"{len(names)} profile(s): {', '.join(names)} (specify --profile to select one)"


# ============================================================================
# Profile management commands (factory/profiles.py)
# ============================================================================

@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name, e.g. 'my-project'"),
    repo: str = typer.Option(..., "--repo", help="Target repo URL, e.g. https://github.com/acme/my-project"),
    cloudflare_project: Optional[str] = typer.Option(
        None, "--cloudflare-project", help="Cloudflare/Wrangler project name, if deploying there"
    ),
    target_branch: str = typer.Option("main", "--target-branch", help="Branch 'factory run' checks out and verifies"),
    verify: List[str] = typer.Option(
        [],
        "--verify",
        help="Verification stage command, as 'stage=cmd arg1 arg2' (repeatable). "
        "stage is a VerificationStage name, e.g. 'unit=pytest' or 'lint=npm run lint'.",
    ),
) -> None:
    """Create a new profile and persist it to profiles/<name>.yml."""
    import shlex

    verification_commands = {}
    for entry in verify:
        if "=" not in entry:
            console.print(f"[red]✗[/red] --verify must be 'stage=cmd', got: {entry}")
            raise typer.Exit(code=1)
        stage_key, _, cmd_str = entry.partition("=")
        verification_commands[stage_key.strip()] = shlex.split(cmd_str)

    try:
        stage_commands_from_profile_config(verification_commands)  # validate stage names up front
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    try:
        new_profile = create_profile(
            name=name,
            target_repo_url=repo,
            cloudflare_project_name=cloudflare_project,
            target_branch=target_branch,
            verification_commands=verification_commands,
        )
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]✓[/green] Profile '{new_profile.name}' created: {new_profile.target_repo.repo_string}")
    console.print(f"[cyan]Saved to:[/cyan] profiles/{new_profile.name}.yml")


@profile_app.command("list")
def profile_list() -> None:
    """List all profiles."""
    names = list_profiles()
    if not names:
        console.print("[yellow]No profiles exist yet.[/yellow]")
        return

    table = Table(title="Factory Profiles")
    table.add_column("Name")
    table.add_column("Target Repo")
    for name in names:
        try:
            p = load_profile(name)
            table.add_row(p.name, p.target_repo.repo_string)
        except ProfileNotFoundError as e:
            table.add_row(name, f"[red]error: {e}[/red]")
    console.print(table)


@profile_app.command("show")
def profile_show(name: str = typer.Argument(..., help="Profile name")) -> None:
    """Show details for a single profile."""
    try:
        p = load_profile(name)
    except ProfileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Profile[/bold blue]: {p.name}")
    console.print(f"  Target repo: {p.target_repo.repo_string} ({p.target_repo.url})")
    console.print(f"  Target branch: {p.target_branch}")
    console.print(f"  Cloudflare project: {p.cloudflare.project_name or '(none)'}")
    console.print(f"  Business requirements source: {p.business_requirements_source or '(none)'}")
    console.print(f"  Protected paths: {p.protected_paths or '(defaults only)'}")
    console.print(f"  Verification commands: {p.verification_commands or '(none configured — gate runs 0 stages)'}")
    if p.notes:
        console.print(f"  Notes: {p.notes}")


if __name__ == "__main__":
    app()
