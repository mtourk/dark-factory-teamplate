"""
Tests for factory/implementation/workspace.py: the factory's own disposable
local checkout per profile (master plan §17 — never hardcoded to one repo).

These exercise the real git clone/fetch/reset-hard mechanics against a local
git repository standing in for "origin" — no network access, no GitHub.
"""

import subprocess
from pathlib import Path

import pytest

from factory.implementation.workspace import WorkspaceError, ensure_workspace
from factory.profiles import Profile, TargetRepository


def _run_git(args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


def _local_profile(name: str, remote_path: Path, branch: str = "main") -> Profile:
    """
    Build a Profile pointing at a local git repo instead of a real GitHub URL.

    TargetRepository.__post_init__ rejects anything that isn't an
    https://github.com/... URL (by design, for production code paths), so we
    bypass __init__ here with object.__new__ — these tests only need
    `ensure_workspace()`'s git mechanics to see a valid, clonable `url`.
    """
    repo = object.__new__(TargetRepository)
    repo.owner = "local"
    repo.name = name
    repo.url = str(remote_path)
    return Profile(name=name, target_repo=repo, target_branch=branch)


@pytest.fixture
def remote_repo(tmp_path):
    """A local git repo acting as the profile's 'origin', with one commit."""
    remote = tmp_path / "origin"
    remote.mkdir()
    _run_git(["init", "-b", "main"], cwd=remote)
    _run_git(["config", "user.email", "test@example.com"], cwd=remote)
    _run_git(["config", "user.name", "Test"], cwd=remote)
    (remote / "app.py").write_text("print('v1')\n")
    _run_git(["add", "."], cwd=remote)
    _run_git(["commit", "-m", "initial"], cwd=remote)
    return remote


class TestEnsureWorkspaceClone:
    def test_first_call_clones(self, remote_repo, tmp_path):
        workspace_root = tmp_path / "workspaces"
        profile = _local_profile("proj", remote_repo)

        repo_path = ensure_workspace(profile, workspace_root=workspace_root)

        assert repo_path == (workspace_root / "proj").resolve()
        assert (repo_path / ".git").exists()
        assert (repo_path / "app.py").read_text() == "print('v1')\n"

    def test_clone_failure_raises_workspace_error(self, tmp_path):
        workspace_root = tmp_path / "workspaces"
        profile = _local_profile("proj", tmp_path / "does-not-exist")

        with pytest.raises(WorkspaceError):
            ensure_workspace(profile, workspace_root=workspace_root)


class TestEnsureWorkspaceReset:
    def test_second_call_resets_local_mutations(self, remote_repo, tmp_path):
        """
        A prior (possibly failed/stopped) run may have left behind edits and
        stray files; the next `ensure_workspace()` call for the same profile
        must discard all of it and land back on origin's current tree.
        """
        workspace_root = tmp_path / "workspaces"
        profile = _local_profile("proj", remote_repo)

        repo_path = ensure_workspace(profile, workspace_root=workspace_root)

        # Simulate a dirty workspace left over from a previous attempt.
        (repo_path / "app.py").write_text("print('mutated by a failed run')\n")
        (repo_path / "junk.txt").write_text("stray file\n")

        repo_path_2 = ensure_workspace(profile, workspace_root=workspace_root)

        assert repo_path_2 == repo_path
        assert (repo_path / "app.py").read_text() == "print('v1')\n"
        assert not (repo_path / "junk.txt").exists()

    def test_second_call_picks_up_new_origin_commits(self, remote_repo, tmp_path):
        """A run should always start from the current tip of the target branch."""
        workspace_root = tmp_path / "workspaces"
        profile = _local_profile("proj", remote_repo)

        ensure_workspace(profile, workspace_root=workspace_root)

        (remote_repo / "app.py").write_text("print('v2')\n")
        _run_git(["add", "."], cwd=remote_repo)
        _run_git(["commit", "-m", "v2"], cwd=remote_repo)

        repo_path = ensure_workspace(profile, workspace_root=workspace_root)

        assert (repo_path / "app.py").read_text() == "print('v2')\n"

    def test_fetch_failure_raises_workspace_error(self, remote_repo, tmp_path):
        workspace_root = tmp_path / "workspaces"
        profile = _local_profile("proj", remote_repo)
        ensure_workspace(profile, workspace_root=workspace_root)

        # Pull the rug out: origin stops existing for the second call.
        broken_profile = _local_profile("proj", tmp_path / "gone")
        with pytest.raises(WorkspaceError):
            ensure_workspace(broken_profile, workspace_root=workspace_root)
