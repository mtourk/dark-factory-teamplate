"""
Tests for `factory run` (factory/cli.py): the dynamic, profile-driven
claim -> implement -> verify -> repair -> close entrypoint (master plan §17).

These confirm `run` is never hardcoded to one project — every dependency it
builds (GitHubAdapter, workspace, verification stages, run_full_cycle's
kwargs) is derived purely from whichever profile `--profile`/env/implicit
resolution hands it, covering both an existing repo and one freshly synced
in from the intake worker's "create new project" flow.

The deep claim/build/apply/verify/repair logic inside `run_full_cycle()`
itself is covered by factory/tests/test_phase10_implementation.py; here we
stub `ImplementationOrchestrator` so these tests exercise only the CLI's own
wiring (profile resolution -> GitHubAdapter -> workspace -> stage commands
-> run_full_cycle call -> result printing).
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import factory.cli as cli
from factory.backlog.github_adapter import GitHubIssue
from factory.implementation.orchestrator import ImplementationPhase, ImplementationRun
from factory.implementation.repair import StopCondition
from factory.profiles import create_profile

runner = CliRunner()


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    """Isolate profile storage to a temp directory, same convention as test_profiles.py."""
    import factory.profiles as profiles_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(profiles_module, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.delenv("FACTORY_PROFILE", raising=False)
    return tmp_path / "profiles"


class _StubGitHubAdapter:
    """Captures the owner/repo it was constructed with; returns canned issues."""

    instances = []

    def __init__(self, owner="", repo="", token=None):
        self.owner = owner
        self.repo = repo
        self.list_issues_calls = []
        _StubGitHubAdapter.instances.append(self)

    def list_issues(self, state="open", labels=None):
        self.list_issues_calls.append({"state": state, "labels": labels})
        return self.issues_to_return


class _StubLocalProfileSync:
    """Returns a configurable number of 'synced' profiles; never touches the network."""

    synced_count = 0

    def __init__(self):
        pass

    def sync_all(self):
        return _StubLocalProfileSync.synced_count


class _StubOrchestrator:
    """Captures run_full_cycle's kwargs and returns a prebuilt ImplementationRun."""

    calls = []
    result_to_return = None
    raise_error = None

    def __init__(self, builder_coordinator):
        self.builder_coordinator = builder_coordinator

    def run_full_cycle(self, **kwargs):
        _StubOrchestrator.calls.append(kwargs)
        if _StubOrchestrator.raise_error is not None:
            raise _StubOrchestrator.raise_error
        return _StubOrchestrator.result_to_return


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch, tmp_path):
    """Wire every external dependency `run` touches to a stub, and reset captured state."""
    _StubGitHubAdapter.instances = []
    _StubGitHubAdapter.issues_to_return = [
        GitHubIssue(
            number=42,
            title="Add ROI calculator",
            body="...",
            labels=["factory:ready"],
            state="open",
            created_at="2024-01-01T00:00:00Z",
            url="https://github.com/acme/widgets/issues/42",
        )
    ]
    _StubLocalProfileSync.synced_count = 0
    _StubOrchestrator.calls = []
    _StubOrchestrator.raise_error = None
    _StubOrchestrator.result_to_return = ImplementationRun(
        run_id="RUN-test",
        issue_number=42,
        project_id="acme-widgets",
        phase=ImplementationPhase.COMPLETE,
    )

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    monkeypatch.setattr(cli, "GitHubAdapter", _StubGitHubAdapter)
    monkeypatch.setattr(cli, "LocalProfileSync", _StubLocalProfileSync)
    monkeypatch.setattr(cli, "ImplementationOrchestrator", _StubOrchestrator)
    monkeypatch.setattr(cli, "ensure_workspace", lambda profile: workspace_path)
    return workspace_path


def _make_profile(profiles_dir, **overrides):
    kwargs = dict(
        name="acme-widgets",
        target_repo_url="https://github.com/acme/widgets",
        verification_commands={"unit": ["python", "-c", "pass"]},
    )
    kwargs.update(overrides)
    return create_profile(**kwargs)


class TestRunProfileDrivenDispatch:
    """`run` must derive everything from the resolved profile, never a hardcoded repo."""

    def test_github_adapter_built_from_active_profile(self, profiles_dir):
        _make_profile(profiles_dir)
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 0, result.output
        assert len(_StubGitHubAdapter.instances) == 1
        adapter = _StubGitHubAdapter.instances[0]
        assert adapter.owner == "acme"
        assert adapter.repo == "widgets"

    def test_run_full_cycle_called_with_profile_derived_kwargs(self, profiles_dir, _reset_stubs):
        _make_profile(profiles_dir)
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 0, result.output
        assert len(_StubOrchestrator.calls) == 1
        call = _StubOrchestrator.calls[0]
        assert call["issue_number"] == 42
        assert call["project_id"] == "acme-widgets"
        assert call["repo_root"] == _reset_stubs
        assert [c.command for c in call["stage_commands"]] == [["python", "-c", "pass"]]

    def test_different_profile_drives_different_repo(self, profiles_dir):
        """A second, differently-named/repo'd profile is handled identically, just with its own data."""
        _make_profile(
            profiles_dir,
            name="other-project",
            target_repo_url="https://github.com/other-org/other-repo",
        )
        result = runner.invoke(cli.app, ["--profile", "other-project", "run"])
        assert result.exit_code == 0, result.output
        adapter = _StubGitHubAdapter.instances[0]
        assert adapter.owner == "other-org"
        assert adapter.repo == "other-repo"
        assert _StubOrchestrator.calls[0]["project_id"] == "other-project"

    def test_two_profiles_requires_explicit_selection(self, profiles_dir):
        _make_profile(profiles_dir, name="alpha", target_repo_url="https://github.com/acme/alpha")
        _make_profile(profiles_dir, name="beta", target_repo_url="https://github.com/acme/beta")
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 1


class TestRunSyncProfiles:
    def test_sync_pending_profiles_runs_by_default(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubLocalProfileSync.synced_count = 1
        result = runner.invoke(cli.app, ["run"])
        assert "Synced 1 new profile" in result.output

    def test_no_sync_profiles_flag_skips_sync(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubLocalProfileSync.synced_count = 1
        result = runner.invoke(cli.app, ["run", "--no-sync-profiles"])
        assert "Synced" not in result.output


class TestRunOnceAndDryRun:
    def test_once_processes_a_single_issue(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubGitHubAdapter.issues_to_return = [
            GitHubIssue(number=1, title="first", body="", labels=[], state="open", created_at="", url=""),
            GitHubIssue(number=2, title="second", body="", labels=[], state="open", created_at="", url=""),
        ]
        result = runner.invoke(cli.app, ["run", "--Once"])
        assert result.exit_code == 0, result.output
        assert len(_StubOrchestrator.calls) == 1
        assert _StubOrchestrator.calls[0]["issue_number"] == 1

    def test_dry_run_makes_no_run_full_cycle_calls(self, profiles_dir):
        _make_profile(profiles_dir)
        result = runner.invoke(cli.app, ["run", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert _StubOrchestrator.calls == []
        assert "#42" in result.output

    def test_no_eligible_issues_exits_cleanly(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubGitHubAdapter.issues_to_return = []
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 0, result.output
        assert "No 'factory:ready' issues found" in result.output
        assert _StubOrchestrator.calls == []


class TestRunVerificationCommands:
    def test_warns_when_no_verification_commands_configured(self, profiles_dir):
        _make_profile(profiles_dir, verification_commands={})
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 0, result.output
        assert "No verification_commands configured" in result.output

    def test_invalid_verification_stage_key_exits_with_error(self, profiles_dir):
        _make_profile(profiles_dir, verification_commands={"not_a_real_stage": ["echo", "hi"]})
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 1
        # Rich may word-wrap this across lines at narrow widths; compare with
        # newlines collapsed instead of asserting on an exact wrapped line.
        collapsed = " ".join(result.output.split())
        assert "Unknown verification stage 'not_a_real_stage'" in collapsed


class TestRunResultPrinting:
    def test_complete_run_prints_success(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubOrchestrator.result_to_return = ImplementationRun(
            run_id="RUN-test",
            issue_number=42,
            project_id="acme-widgets",
            phase=ImplementationPhase.COMPLETE,
            attempt_number=2,
        )
        result = runner.invoke(cli.app, ["run"])
        assert "COMPLETE" in result.output

    def test_stopped_run_prints_stop_condition(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubOrchestrator.result_to_return = ImplementationRun(
            run_id="RUN-test",
            issue_number=42,
            project_id="acme-widgets",
            phase=ImplementationPhase.STOPPED,
            stop_condition=StopCondition.MAX_ATTEMPTS_EXHAUSTED,
        )
        result = runner.invoke(cli.app, ["run"])
        assert "STOPPED" in result.output
        assert "max_attempts_exhausted" in result.output

    def test_run_full_cycle_exception_is_reported_and_does_not_abort_remaining_issues(self, profiles_dir):
        _make_profile(profiles_dir)
        _StubGitHubAdapter.issues_to_return = [
            GitHubIssue(number=1, title="first", body="", labels=[], state="open", created_at="", url=""),
            GitHubIssue(number=2, title="second", body="", labels=[], state="open", created_at="", url=""),
        ]
        _StubOrchestrator.raise_error = RuntimeError("boom")
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 0, result.output
        assert result.output.count("ERROR") == 2
        assert len(_StubOrchestrator.calls) == 2


class TestRunWorkspaceFailure:
    def test_workspace_error_exits_with_code_1(self, profiles_dir, monkeypatch):
        from factory.implementation.workspace import WorkspaceError

        _make_profile(profiles_dir)

        def _boom(profile):
            raise WorkspaceError("clone failed")

        monkeypatch.setattr(cli, "ensure_workspace", _boom)
        result = runner.invoke(cli.app, ["run"])
        assert result.exit_code == 1
        assert "Workspace preparation failed" in result.output
