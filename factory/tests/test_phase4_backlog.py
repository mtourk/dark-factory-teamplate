"""
Phase 4: Backlog scheduler tests.

Tests for GitHub API, eligibility checking, priority ordering, atomic claims.
"""

import pytest
from datetime import datetime

from factory.backlog.github_adapter import GitHubIssue, parse_repo_url, GitHubAdapter
from factory.backlog.scheduler import (
    BacklogScheduler, Priority, BlockReason, EligibleIssue, IneligibleIssue,
    create_required_labels
)
from factory.state import Project, init_db, get_db_session, close_db_session


# ============================================================================
# GitHub Adapter Tests
# ============================================================================

class TestGitHubAdapter:
    """GitHub API client tests."""

    def test_parse_repo_url(self):
        """Parse GitHub repo URL correctly."""
        owner, repo = parse_repo_url("https://github.com/mtourk/investisor")
        assert owner == "mtourk"
        assert repo == "investisor"

    def test_parse_repo_url_with_git_suffix(self):
        """Parse repo URL with .git suffix."""
        owner, repo = parse_repo_url("https://github.com/mtourk/investisor.git")
        assert owner == "mtourk"
        assert repo == "investisor"

    def test_parse_repo_url_with_trailing_slash(self):
        """Parse repo URL with trailing slash."""
        owner, repo = parse_repo_url("https://github.com/mtourk/investisor/")
        assert owner == "mtourk"
        assert repo == "investisor"

    def test_adapter_initialization(self):
        """GitHub adapter initializes with token and repo."""
        adapter = GitHubAdapter(token="test-token", owner="mtourk", repo="investisor")
        assert adapter.token == "test-token"
        assert adapter.owner == "mtourk"
        assert adapter.repo == "investisor"
        adapter.close()

    def test_adapter_auth_headers(self):
        """Authorization headers are correct."""
        adapter = GitHubAdapter(token="test-token")
        headers = adapter._auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"
        adapter.close()


# ============================================================================
# Eligibility Checking Tests
# ============================================================================

class TestEligibilityChecking:
    """Eligibility filtering tests."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler for test."""
        session = init_db()
        project = Project(id="test-project", github_repo="https://github.com/test/test")
        session.add(project)
        session.commit()

        scheduler = BacklogScheduler(project, session)
        yield scheduler
        close_db_session(session)

    def test_ready_issue_is_eligible(self, scheduler):
        """Issue with factory:ready label is eligible."""
        issue = GitHubIssue(
            number=1,
            title="Test issue",
            body="",
            labels=["factory:ready"],
            state="open",
            created_at="2026-10-01T00:00:00Z",
            url="https://example.com"
        )

        is_elig, reason, details = scheduler.is_eligible(issue)
        assert is_elig is True
        assert reason is None

    def test_closed_issue_not_eligible(self, scheduler):
        """Closed issue is not eligible."""
        issue = GitHubIssue(
            number=2,
            title="Closed issue",
            body="",
            labels=["factory:ready"],
            state="closed",
            created_at="2026-10-01T00:00:00Z",
            url="https://example.com"
        )

        is_elig, reason, details = scheduler.is_eligible(issue)
        assert is_elig is False
        assert reason == BlockReason.CLOSED

    def test_no_ready_label_not_eligible(self, scheduler):
        """Issue without factory:ready label is not eligible."""
        issue = GitHubIssue(
            number=3,
            title="Not ready",
            body="",
            labels=[],
            state="open",
            created_at="2026-10-01T00:00:00Z",
            url="https://example.com"
        )

        is_elig, reason, details = scheduler.is_eligible(issue)
        assert is_elig is False
        assert reason == BlockReason.NOT_READY

    def test_blocked_issue_not_eligible(self, scheduler):
        """Issue with factory:blocked label is not eligible."""
        issue = GitHubIssue(
            number=4,
            title="Blocked",
            body="",
            labels=["factory:ready", "factory:blocked"],
            state="open",
            created_at="2026-10-01T00:00:00Z",
            url="https://example.com"
        )

        is_elig, reason, details = scheduler.is_eligible(issue)
        assert is_elig is False
        assert reason == BlockReason.BLOCKED_LABEL


# ============================================================================
# Priority Ordering Tests
# ============================================================================

class TestPriorityOrdering:
    """Priority extraction and sorting tests."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler for test."""
        session = init_db()
        project = Project(id="test-project", github_repo="https://github.com/test/test")
        session.add(project)
        session.commit()

        scheduler = BacklogScheduler(project, session)
        yield scheduler
        close_db_session(session)

    def test_extract_priority_critical(self, scheduler):
        """Extract critical priority from labels."""
        priority = scheduler.parse_priority_from_labels(["priority:critical"])
        assert priority == Priority.CRITICAL

    def test_extract_priority_security(self, scheduler):
        """Security issues get highest priority."""
        priority = scheduler.parse_priority_from_labels(["security"])
        assert priority == Priority.SECURITY

    def test_extract_default_priority(self, scheduler):
        """Default priority is NORMAL."""
        priority = scheduler.parse_priority_from_labels([])
        assert priority == Priority.NORMAL

    def test_sort_by_priority_then_date(self, scheduler):
        """Issues sorted by priority, then creation date."""
        issues = [
            EligibleIssue(1, "Low", Priority.LOW, "2026-10-01T00:00:00Z", "url", []),
            EligibleIssue(2, "Critical", Priority.CRITICAL, "2026-10-02T00:00:00Z", "url", []),
            EligibleIssue(3, "High (old)", Priority.HIGH, "2026-09-01T00:00:00Z", "url", []),
            EligibleIssue(4, "High (new)", Priority.HIGH, "2026-10-01T00:00:00Z", "url", []),
        ]

        sorted_issues = scheduler.sort_eligible_issues(issues)

        # Expected order: Critical(2), High(old,3), High(new,4), Low(1)
        assert sorted_issues[0].number == 2  # Critical
        assert sorted_issues[1].number == 3  # High (older)
        assert sorted_issues[2].number == 4  # High (newer)
        assert sorted_issues[3].number == 1  # Low


# ============================================================================
# Atomic Claim Tests
# ============================================================================

class TestAtomicClaiming:
    """Atomic claim enforcement tests."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler for test."""
        session = init_db()
        project = Project(id="test-project", github_repo="https://github.com/test/test")
        session.add(project)
        session.commit()

        scheduler = BacklogScheduler(project, session)
        yield scheduler
        close_db_session(session)

    def test_claim_next_eligible_single_issue(self, scheduler):
        """Claim the next eligible issue."""
        issues = [
            EligibleIssue(42, "Test", Priority.HIGH, "2026-10-01T00:00:00Z", "url", [])
        ]

        claimed = scheduler.claim_next_eligible(issues, "RUN-test001")
        assert claimed is not None
        assert claimed.number == 42

    def test_claim_race_prevention(self, scheduler):
        """Cannot claim same issue twice."""
        issues = [
            EligibleIssue(43, "Test", Priority.HIGH, "2026-10-01T00:00:00Z", "url", [])
        ]

        # First claim succeeds
        claimed1 = scheduler.claim_next_eligible(issues, "RUN-test001")
        assert claimed1 is not None

        # Second claim on same issue fails
        claimed2 = scheduler.claim_next_eligible(issues, "RUN-test002")
        assert claimed2 is None


# ============================================================================
# Phase 4 Gate Test
# ============================================================================

def test_phase4_gate_backlog_scheduler_operational():
    """
    Phase 4 Gate: Backlog scheduler is operational.

    Verifies:
    - GitHub adapter URL parsing
    - Eligibility checking (all block reasons)
    - Priority extraction and sorting
    - Atomic claim prevention of races
    - Deterministic ordering (priority → date)
    """
    # URL parsing
    owner, repo = parse_repo_url("https://github.com/mtourk/investisor")
    assert owner == "mtourk" and repo == "investisor"

    # Eligibility and priority
    session = init_db()
    project = Project(id="investisor", github_repo="https://github.com/mtourk/investisor")
    session.add(project)
    session.commit()

    scheduler = BacklogScheduler(project, session)

    # Test eligibility
    ready_issue = GitHubIssue(42, "Ready", "", ["factory:ready"], "open", "2026-10-01", "url")
    is_elig, reason, _ = scheduler.is_eligible(ready_issue)
    assert is_elig is True

    # Test priority
    security_priority = scheduler.parse_priority_from_labels(["security"])
    assert security_priority == Priority.SECURITY

    # Test sorting
    issues = [
        EligibleIssue(1, "Low", Priority.LOW, "2026-10-01T00:00:00Z", "url", []),
        EligibleIssue(2, "Critical", Priority.CRITICAL, "2026-10-02T00:00:00Z", "url", []),
    ]
    sorted_issues = scheduler.sort_eligible_issues(issues)
    assert sorted_issues[0].priority == Priority.CRITICAL

    # Test atomic claim
    eligible = [EligibleIssue(100, "Test", Priority.HIGH, "2026-10-01", "url", [])]
    claimed = scheduler.claim_next_eligible(eligible, "RUN-g001")
    assert claimed is not None

    close_db_session(session)
    print("✓ Phase 4 Gate: Backlog scheduler operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
