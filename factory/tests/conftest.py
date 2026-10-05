"""
Pytest configuration and shared fixtures for factory tests.
"""

import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Give every test an isolated in-memory state database.

    FB-12: previously this set FACTORY_DB=":memory:" once at session scope, but
    factory/state.py bound a single on-disk engine at import and ignored the
    env var entirely — so tests silently shared the real ~/.factory/state.db,
    which made full-suite runs flaky (rows from one test leaked into the next,
    causing PK/unique collisions). Now state.py honors FACTORY_DB and builds the
    engine lazily, so resetting it per test yields a clean, isolated DB.
    """
    from factory import state

    monkeypatch.setenv("FACTORY_DB", ":memory:")
    state.configure_engine(":memory:")  # fresh, empty in-memory DB for this test
    yield
    state.configure_engine(":memory:")  # dispose this test's DB afterward


@pytest.fixture
def temp_project_dir():
    """Temporary project directory for test isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_github_repo():
    """Mock GitHub repository configuration."""
    return {
        "project_id": "test-repo",
        "github_repo": "https://github.com/test/test-repo",
        "target_branch": "main",
        "model_alias": "qwen2.5-coder:32b",
    }
