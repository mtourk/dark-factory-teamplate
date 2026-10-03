"""
Pytest configuration and shared fixtures for factory tests.
"""

import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Use temporary database for tests."""
    # Tests will use in-memory SQLite or temp file
    os.environ["FACTORY_DB"] = ":memory:"
    yield


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
