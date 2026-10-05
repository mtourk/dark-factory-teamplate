"""
Local workspace management: give `run_full_cycle()` a `repo_root` to write
into, for *whichever* profile's target repository the current `factory run`
invocation resolved to (master plan §17 — never hardcoded to one project).

This is the factory's own disposable clone, not the user's working copy:
each profile gets exactly one local checkout under `workspace_root`, which
`ensure_workspace()` creates on first use and hard-resets to the profile's
`target_branch` on every subsequent call. Nothing here cares whether the
target repo already existed or was just created via the intake worker's
"create new project" web UI flow (factory/intake/local_sync.py) — by the
time a profile exists on disk, both cases look identical: a GitHub URL plus
a branch name.
"""

import os
import subprocess
from pathlib import Path

from factory.profiles import Profile

DEFAULT_WORKSPACES_ROOT = Path(os.environ.get("FACTORY_WORKSPACES_ROOT", "C:/Factory/workspaces"))


class WorkspaceError(Exception):
    """Raised when the local checkout for a profile cannot be prepared."""


def _authenticated_url(url: str, token: str) -> str:
    """Inject a GH token into an https://github.com/... URL for clone/fetch auth."""
    if not token or not url.startswith("https://"):
        return url
    return url.replace("https://", f"https://x-access-token:{token}@", 1)


def _run_git(args, cwd: Path, timeout: float = 300.0):
    try:
        return subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise WorkspaceError(f"git {' '.join(args)} failed to run: {e}") from e


def ensure_workspace(
    profile: Profile,
    workspace_root: Path = DEFAULT_WORKSPACES_ROOT,
    token: str = "",
) -> Path:
    """
    Ensure a local, up-to-date checkout of `profile.target_repo` exists and
    return its path.

    - First call for a profile: `git clone` into `workspace_root/<profile.name>`.
    - Later calls: `git fetch` + hard reset to `origin/<profile.target_branch>`,
      so each run starts from a clean, current tree regardless of what a
      prior (possibly failed/stopped) attempt left behind.

    Args:
        profile: the resolved active profile (factory/profiles.py)
        workspace_root: parent directory for all profiles' checkouts
        token: GitHub token for cloning private repos (defaults to GH_TOKEN env)

    Returns:
        Absolute path to the profile's local checkout.

    Raises:
        WorkspaceError: git clone/fetch/reset failed.
    """
    token = token or os.getenv("GH_TOKEN", "")
    workspace_root.mkdir(parents=True, exist_ok=True)
    repo_path = (workspace_root / profile.name).resolve()
    branch = profile.target_branch or "main"

    if not (repo_path / ".git").exists():
        clone_url = _authenticated_url(profile.target_repo.url, token)
        result = _run_git(
            ["clone", "--branch", branch, clone_url, str(repo_path)],
            cwd=workspace_root,
        )
        if result.returncode != 0:
            raise WorkspaceError(f"git clone of {profile.target_repo.repo_string} failed: {result.stderr}")
        return repo_path

    fetch_url = _authenticated_url(profile.target_repo.url, token)
    result = _run_git(["fetch", fetch_url, branch], cwd=repo_path)
    if result.returncode != 0:
        raise WorkspaceError(f"git fetch for {profile.target_repo.repo_string} failed: {result.stderr}")

    result = _run_git(["checkout", branch], cwd=repo_path)
    if result.returncode != 0:
        raise WorkspaceError(f"git checkout {branch} failed: {result.stderr}")

    result = _run_git(["reset", "--hard", "FETCH_HEAD"], cwd=repo_path)
    if result.returncode != 0:
        raise WorkspaceError(f"git reset --hard failed: {result.stderr}")

    result = _run_git(["clean", "-fd"], cwd=repo_path)
    if result.returncode != 0:
        raise WorkspaceError(f"git clean failed: {result.stderr}")

    return repo_path
