"""
Backlog scheduler: eligibility check, priority ordering, atomic claim.

Per master plan §5:
"An item is eligible when it is open, labeled factory:ready, not claimed/blocked/quarantined/decision-required,
has resolved dependencies, does not conflict with active scope, and emergency stop is inactive.

Deterministic order:
1. Approved production security and defect work according to policy.
2. priority:critical
3. priority:high
4. priority:normal
5. priority:low
6. Creation order as tie-breaker.
"
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy.orm import Session

from factory.backlog.github_adapter import GitHubIssue, parse_repo_url
from factory.state import (
    Project, Run, Claim, Quarantine, EmergencyStop, Decision,
    attempt_claim, is_emergency_stopped
)


class Priority(int, Enum):
    """Issue priority levels (lower number = higher priority)."""
    SECURITY = 0
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class BlockReason(str, Enum):
    """Why an issue is not eligible."""
    NOT_READY = "not_factory_ready"
    ALREADY_CLAIMED = "already_claimed"
    BLOCKED_LABEL = "blocked"
    QUARANTINED = "quarantined"
    DECISION_REQUIRED = "decision_required"
    CLOSED = "closed"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class EligibleIssue:
    """Issue eligible for factory claim."""
    number: int
    title: str
    priority: Priority
    created_at: str
    url: str
    labels: List[str]


@dataclass
class IneligibleIssue:
    """Issue not eligible for factory claim."""
    number: int
    title: str
    reason: BlockReason
    details: str


class BacklogScheduler:
    """Backlog scheduling with deterministic priority and eligibility."""

    def __init__(self, project: Project, session: Session):
        """
        Initialize scheduler for project.

        Args:
            project: Project record
            session: Database session
        """
        self.project = project
        self.session = session

    def parse_priority_from_labels(self, labels: List[str]) -> Priority:
        """
        Extract priority from issue labels.

        Looks for: priority:critical, priority:high, priority:normal, priority:low.
        Default: Priority.NORMAL
        """
        priority_map = {
            "priority:critical": Priority.CRITICAL,
            "priority:high": Priority.HIGH,
            "priority:normal": Priority.NORMAL,
            "priority:low": Priority.LOW,
            "security": Priority.SECURITY,  # alias
        }

        for label, priority in priority_map.items():
            if label in labels:
                return priority

        return Priority.NORMAL

    def is_eligible(self, issue: GitHubIssue) -> tuple[bool, Optional[BlockReason], Optional[str]]:
        """
        Check if issue is eligible for factory claim (§5).

        Args:
            issue: GitHub issue

        Returns:
            (is_eligible, block_reason, details)
        """
        # 1. Must be open
        if issue.state != "open":
            return False, BlockReason.CLOSED, "Issue is closed"

        # 2. Must have factory:ready label
        if "factory:ready" not in issue.labels:
            return False, BlockReason.NOT_READY, "Missing factory:ready label"

        # 3. Check if already claimed
        existing_claim = self.session.query(Claim).filter(
            Claim.project_id == self.project.id,
            Claim.issue_number == issue.number,
        ).first()

        if existing_claim:
            from factory.state import is_claim_stale
            if not is_claim_stale(existing_claim):
                return False, BlockReason.ALREADY_CLAIMED, f"Claimed by {existing_claim.lease_owner}"

        # 4. Check if blocked
        if "factory:blocked" in issue.labels:
            return False, BlockReason.BLOCKED_LABEL, "Marked as blocked"

        # 5. Check if decision-required
        if "factory:decision-required" in issue.labels:
            return False, BlockReason.DECISION_REQUIRED, "Waiting for human decision"

        # 6. Check if quarantined
        quarantine = self.session.query(Quarantine).join(
            Run, Quarantine.run_id == Run.id
        ).filter(
            Run.project_id == self.project.id,
            Run.issue_number == issue.number,
        ).first()

        if quarantine and quarantine.recovery_status != "resolved":
            return False, BlockReason.QUARANTINED, f"Quarantined: {quarantine.incident_type}"

        # 7. Check emergency stop
        if is_emergency_stopped(self.session):
            return False, BlockReason.EMERGENCY_STOP, "Factory emergency stop active"

        return True, None, None

    def sort_eligible_issues(self, issues: List[EligibleIssue]) -> List[EligibleIssue]:
        """
        Sort eligible issues by deterministic priority (§5).

        Order:
        1. Priority (security < critical < high < normal < low)
        2. Creation date (oldest first, tie-breaker)
        """
        return sorted(
            issues,
            key=lambda i: (i.priority.value, i.created_at)
        )

    def get_eligible_issues(self, all_issues: List[GitHubIssue]) -> tuple[List[EligibleIssue], List[IneligibleIssue]]:
        """
        Filter and sort issues into eligible and ineligible.

        Args:
            all_issues: all open issues from GitHub

        Returns:
            (eligible_sorted, ineligible_with_reasons)
        """
        eligible = []
        ineligible = []

        for issue in all_issues:
            is_elig, reason, details = self.is_eligible(issue)

            if is_elig:
                eligible.append(EligibleIssue(
                    number=issue.number,
                    title=issue.title,
                    priority=self.parse_priority_from_labels(issue.labels),
                    created_at=issue.created_at,
                    url=issue.url,
                    labels=issue.labels,
                ))
            else:
                ineligible.append(IneligibleIssue(
                    number=issue.number,
                    title=issue.title,
                    reason=reason,
                    details=details or "",
                ))

        # Sort eligible by priority
        eligible = self.sort_eligible_issues(eligible)

        return eligible, ineligible

    def claim_next_eligible(self, issues: List[EligibleIssue], run_id: str) -> Optional[EligibleIssue]:
        """
        Claim the next eligible issue atomically (§5).

        Args:
            issues: sorted eligible issues
            run_id: factory run ID

        Returns:
            Claimed issue, or None if all fail or none available
        """
        for issue in issues:
            claim = attempt_claim(
                project_id=self.project.id,
                issue_number=issue.number,
                run_id=run_id,
                session=self.session
            )

            if claim:
                # Claimed successfully
                return issue

        # No issue could be claimed
        return None


def create_required_labels(github_client) -> None:
    """
    Create factory labels on GitHub repo (idempotent).

    Labels per §5, §14:
    - factory:ready, factory:claimed, factory:analyzing, factory:planning
    - factory:implementing, factory:verifying, factory:repairing, factory:reviewing
    - factory:preview, factory:auto-merge, factory:deploying, factory:validating-production
    - factory:delivered, factory:blocked, factory:failed, factory:quarantined
    - factory:decision-required
    - priority:critical, priority:high, priority:normal, priority:low
    - security
    """
    labels = [
        ("factory:ready", "00FF00", "Ready for factory to claim"),
        ("factory:claimed", "0075FF", "Factory is working on this"),
        ("factory:analyzing", "0075FF", "BMAD analysis in progress"),
        ("factory:planning", "0075FF", "Architecture planning"),
        ("factory:implementing", "0075FF", "Implementation in progress"),
        ("factory:verifying", "0075FF", "Verification running"),
        ("factory:repairing", "FF6600", "Repair cycle active"),
        ("factory:reviewing", "0075FF", "Independent review"),
        ("factory:preview", "00CCFF", "Cloudflare preview deployed"),
        ("factory:auto-merge", "0075FF", "Ready for auto-merge"),
        ("factory:deploying", "0075FF", "Production deployment"),
        ("factory:validating-production", "0075FF", "Production validation"),
        ("factory:delivered", "00AA00", "Successfully delivered"),
        ("factory:blocked", "FF0000", "Blocked (cannot claim)"),
        ("factory:failed", "FF0000", "Factory failed on this"),
        ("factory:quarantined", "FF0000", "Bad deployment, quarantined"),
        ("factory:decision-required", "FFAA00", "Needs human decision"),
        ("priority:critical", "FF0000", "Critical priority"),
        ("priority:high", "FF6600", "High priority"),
        ("priority:normal", "FFAA00", "Normal priority"),
        ("priority:low", "CCCCCC", "Low priority"),
        ("security", "FF0000", "Security issue"),
    ]

    for label_name, color, description in labels:
        try:
            # Try to create (will fail if exists, but that's fine)
            github_client.client.post(
                f"/repos/{github_client.owner}/{github_client.repo}/labels",
                json={"name": label_name, "color": color, "description": description}
            )
        except Exception:
            # Label probably exists, skip
            pass


if __name__ == "__main__":
    # Example usage
    from factory.backlog.github_adapter import GitHubIssue

    issue1 = GitHubIssue(
        number=42,
        title="Add ROI calculator",
        body="",
        labels=["factory:ready", "priority:high"],
        state="open",
        created_at="2026-10-01T10:00:00Z",
        url="https://github.com/test/test/issues/42",
    )

    issue2 = GitHubIssue(
        number=43,
        title="Fix auth bug",
        body="",
        labels=["factory:ready", "security"],
        state="open",
        created_at="2026-10-02T10:00:00Z",
        url="https://github.com/test/test/issues/43",
    )

    print(f"Issue {issue1.number}: priority {Priority.HIGH.name}")
    print(f"Issue {issue2.number}: priority {Priority.SECURITY.name}")
    print("Security issues come first in deterministic order")
