"""
Tests for FF-P01-01: hardcoded Windows (`C:\\Factory`-style) path elimination.

Covers:
1. factory/profiles.py's new get_factory_root()/get_workspace_root() helpers
   (env-var precedence, cross-platform default via pathlib.Path.home()).
2. factory/context/broker.py, factory/state.py, factory/implementation/
   workspace.py, factory/sealed_qa/acceptance.py, factory/tools/worktrees.py
   are actually wired to those helpers (not just that the helpers exist in
   isolation) — reload each module under a monkeypatched FACTORY_ROOT and
   confirm its module-level path constant moves with it.
3. A static source-level guarantee that none of the five target files build
   a Path(...) from a hardcoded 'C:\\...'/'C:/...' literal (the regression
   this item exists to prevent), simulating what a non-Windows contributor
   would hit immediately: a drive-letter literal has no meaning off Windows.

These tests use only pathlib.Path throughout (no manual string/backslash
path assembly), so they're meaningful evidence on Windows, macOS, and Linux
alike — per docs/operations/CROSS_MACHINE_DEV_WORKFLOW.md.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import factory.profiles as profiles


REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_FILES = [
    "factory/context/broker.py",
    "factory/state.py",
    "factory/implementation/workspace.py",
    "factory/sealed_qa/acceptance.py",
    "factory/tools/worktrees.py",
]

# Matches constructing a Path (or f-string/str default) directly from a
# hardcoded drive-letter-rooted literal, e.g. Path("C:/Factory") or
# Path("C:\\Factory\\workspaces"). Deliberately narrow (anchored to `Path(`)
# so it does not flag the module docstrings/comments that illustrate the
# on-disk layout for humans (explicitly allowed by this item's acceptance
# criteria: "...outside of test fixtures and documentation").
_HARDCODED_WINDOWS_PATH_LITERAL = re.compile(r"""Path\(\s*["']C:[\\/]""")


class TestNoHardcodedWindowsPathLiterals:
    """Static guarantee: no Path(...) in the 5 target files is seeded from
    a hardcoded 'C:\\...' literal. This is the exact regression FF-P01-01
    fixes, and the acceptance criterion the backlog item names verbatim."""

    @pytest.mark.parametrize("relative_path", TARGET_FILES)
    def test_file_has_no_hardcoded_drive_letter_path_construction(self, relative_path):
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        match = _HARDCODED_WINDOWS_PATH_LITERAL.search(source)
        assert match is None, (
            f"{relative_path} still constructs a Path(...) from a hardcoded "
            f"Windows drive-letter literal: {match.group(0) if match else ''!r}"
        )


class TestGetFactoryRoot:
    """factory/profiles.py:get_factory_root() — precedence and portability."""

    def test_returns_a_path_instance(self, monkeypatch):
        monkeypatch.delenv("FACTORY_ROOT", raising=False)
        assert isinstance(profiles.get_factory_root(), Path)

    def test_default_is_home_dot_factory_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("FACTORY_ROOT", raising=False)
        assert profiles.get_factory_root() == Path.home() / ".factory"

    def test_env_var_takes_precedence_over_default(self, monkeypatch, tmp_path):
        custom_root = tmp_path / "custom-factory-root"
        monkeypatch.setenv("FACTORY_ROOT", str(custom_root))
        assert profiles.get_factory_root() == custom_root

    def test_env_var_with_unix_style_separators_is_honored_verbatim(self, monkeypatch):
        """
        A dev machine (macOS/Linux) will set FACTORY_ROOT using forward
        slashes and no drive letter. get_factory_root() must not assume or
        inject any Windows-specific separator or drive letter — it only
        wraps whatever the environment provides in pathlib.Path, which
        itself is responsible for OS-appropriate interpretation.
        """
        monkeypatch.setenv("FACTORY_ROOT", "/home/dev/.factory")
        result = profiles.get_factory_root()
        assert result == Path("/home/dev/.factory")
        # No manual backslash concatenation anywhere in the result's construction:
        # joining a child path must go through Path's own `/` operator and
        # must not silently drop/duplicate separators.
        assert (result / "control" / "sealed") == Path("/home/dev/.factory/control/sealed")


class TestGetWorkspaceRoot:
    """factory/profiles.py:get_workspace_root() — precedence and derivation."""

    def test_returns_a_path_instance(self, monkeypatch):
        monkeypatch.delenv("FACTORY_WORKSPACES_ROOT", raising=False)
        assert isinstance(profiles.get_workspace_root(), Path)

    def test_env_var_takes_precedence(self, monkeypatch, tmp_path):
        custom_workspaces = tmp_path / "custom-workspaces"
        monkeypatch.setenv("FACTORY_WORKSPACES_ROOT", str(custom_workspaces))
        assert profiles.get_workspace_root() == custom_workspaces

    def test_default_derives_from_factory_root(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FACTORY_WORKSPACES_ROOT", raising=False)
        custom_root = tmp_path / "custom-factory-root"
        monkeypatch.setenv("FACTORY_ROOT", str(custom_root))
        assert profiles.get_workspace_root() == custom_root / "workspaces"


def _run_in_subprocess(code: str, env_overrides: dict) -> list:
    """
    Run `code` in a fresh Python subprocess with `env_overrides` applied on
    top of the current environment, and return its stdout split into lines.

    A fresh subprocess (rather than importlib.reload() of the already-
    imported production module in-process) is deliberate: these target
    modules compute their path constants once, at import time, and other
    test files (test_context_broker.py, test_phase5_leakage.py,
    test_phase8_tools_worktrees.py, test_phase9_sealed_qa.py,
    test_workspace.py) import classes from them directly. Reloading a
    module in-process rebinds its classes to new identities, which breaks
    `isinstance(...)` checks in any test file that cached the pre-reload
    class object — a correctness hazard for the rest of the suite, not just
    a style preference. A subprocess gets a clean import with the env var
    already set, with zero risk of leaking into this test session.
    """
    env = os.environ.copy()
    env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"subprocess failed (code 0 expected): stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return result.stdout.strip().splitlines()


class TestModulesWireIntoFactoryProfilesRoot:
    """
    Each of the 5 target modules must actually resolve its storage path via
    factory/profiles.py's get_factory_root()/get_workspace_root() — not
    merely have a Path(...) somewhere that happens to not be 'C:\\...'
    (e.g. it must not have been replaced with a *different* hardcoded
    literal). Verified by moving FACTORY_ROOT (in a subprocess, so the
    module-level constants are recomputed from a fresh import) and
    confirming each module's constant moves with it.
    """

    def test_broker_factory_root_moves_with_env_var(self, tmp_path):
        custom_root = tmp_path / "broker-root"
        lines = _run_in_subprocess(
            "import factory.context.broker as b; "
            "print(b.FACTORY_ROOT); print(b.CONTROL_DIR); print(b.SEALED_DIR)",
            {"FACTORY_ROOT": str(custom_root)},
        )
        assert Path(lines[0]) == custom_root
        assert Path(lines[1]) == custom_root / "control"
        assert Path(lines[2]) == custom_root / "control" / "sealed"

    def test_state_db_path_moves_with_env_var(self, tmp_path):
        custom_root = tmp_path / "state-root"
        lines = _run_in_subprocess(
            "import factory.state as s; print(s.DB_PATH); print(s.DB_PATH.parent.exists())",
            {"FACTORY_ROOT": str(custom_root)},
        )
        assert Path(lines[0]) == custom_root / "state.db"
        assert lines[1] == "True"  # module-level mkdir ran

    def test_workspace_default_root_moves_with_env_var(self, tmp_path):
        custom_root = tmp_path / "workspace-root"
        lines = _run_in_subprocess(
            "import factory.implementation.workspace as w; print(w.DEFAULT_WORKSPACES_ROOT)",
            {"FACTORY_ROOT": str(custom_root), "FACTORY_WORKSPACES_ROOT": ""},
        )
        assert Path(lines[0]) == custom_root / "workspaces"

    def test_workspace_respects_explicit_workspaces_root_env_var(self, tmp_path):
        custom_workspaces = tmp_path / "explicit-workspaces"
        lines = _run_in_subprocess(
            "import factory.implementation.workspace as w; print(w.DEFAULT_WORKSPACES_ROOT)",
            {"FACTORY_WORKSPACES_ROOT": str(custom_workspaces)},
        )
        assert Path(lines[0]) == custom_workspaces

    def test_worktrees_factory_root_moves_with_env_var(self, tmp_path):
        custom_root = tmp_path / "worktrees-root"
        lines = _run_in_subprocess(
            "import factory.tools.worktrees as wt; "
            "print(wt.FACTORY_ROOT); print(wt.WORKTREES_DIR); "
            "print(wt.WorktreeManager().factory_root)",
            {"FACTORY_ROOT": str(custom_root)},
        )
        assert Path(lines[0]) == custom_root
        assert Path(lines[1]) == custom_root / "worktrees"
        # WorktreeManager's default `factory_root` param is bound at import
        # time too; confirm it was bound from the env-var-driven value.
        assert Path(lines[2]) == custom_root

    def test_sealed_qa_acceptance_default_dir_moves_with_env_var(self, monkeypatch, tmp_path):
        """
        Unlike the other four, SealedQABroker resolves its default
        sealed_dir lazily inside __init__ (not at module import time), so
        no reload is needed here — just confirming the env var is honored
        at call time.
        """
        from factory.sealed_qa.acceptance import SealedQABroker

        custom_root = tmp_path / "sealed-root"
        monkeypatch.setenv("FACTORY_ROOT", str(custom_root))
        broker = SealedQABroker()
        assert broker.sealed_dir == custom_root / "control" / "sealed"
        assert broker.sealed_dir.exists()


class TestCrossPlatformPathAssembly:
    """
    Direct regression coverage for the "don't introduce new Windows-specific
    path assumptions" constraint: build each module's root from a
    Unix-style (forward-slash, no drive letter) FACTORY_ROOT value and
    confirm the resulting sub-paths are still assembled correctly via
    pathlib's `/` operator, with no doubled/missing separators and no
    dependence on a drive letter being present.
    """

    @pytest.mark.parametrize(
        "unix_style_root",
        ["/home/dev/.factory", "/Users/dev/.factory", "/tmp/factory-test-root"],
    )
    def test_get_factory_root_subpaths_assemble_cleanly(self, monkeypatch, unix_style_root):
        monkeypatch.setenv("FACTORY_ROOT", unix_style_root)
        root = profiles.get_factory_root()
        worktree = root / "worktrees" / "RUN-abc12345"
        assert worktree == Path(unix_style_root) / "worktrees" / "RUN-abc12345"
        assert str(worktree).count("//") == 0
