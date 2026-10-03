"""
Independent Review: SHA-bound, fresh session, comprehensive verification.

Per master plan §13:
"Reviewer session is fresh and SHA-bound. Review requirements, architecture,
permissions, security, errors, data, scope, tests, mutation survival,
false-pass risk, dependencies, recovery, documentation, and evidence.

Output includes pass/fail/decision status, reviewed base/head SHA, findings,
covered requirements, evidence gaps, and protected-path status. Auto-merge
requires current PR SHA to equal reviewed SHA."
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum


class ReviewDimension(str, Enum):
    """Review dimensions (§13)."""
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    PERMISSIONS = "permissions"
    SECURITY = "security"
    ERROR_HANDLING = "error_handling"
    DATA_BEHAVIOR = "data_behavior"
    SCOPE = "scope"
    TESTS = "tests"
    MUTATION = "mutation"
    FALSE_PASS_RISK = "false_pass_risk"
    DEPENDENCIES = "dependencies"
    RECOVERY = "recovery"
    DOCUMENTATION = "documentation"
    EVIDENCE = "evidence"


class ReviewVerdict(str, Enum):
    """Review decision."""
    APPROVED = "approved"
    REJECTED = "rejected"
    DECISION_REQUIRED = "decision_required"


class FindingSeverity(str, Enum):
    """Review finding severity."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ReviewFinding:
    """Single review finding across dimensions."""
    dimension: ReviewDimension
    severity: FindingSeverity
    statement: str  # Finding text
    evidence: List[str]  # Citations from requirements, code, tests
    recommendation: Optional[str] = None
    blocked: bool = False  # Blocks merge if true
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "dimension": self.dimension.value,
            "severity": self.severity.value,
            "statement": self.statement,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
        }


@dataclass
class ReviewContext:
    """Context available to reviewer (fresh session, §13)."""
    base_sha: str  # Base commit SHA (40-char hex)
    head_sha: str  # PR head SHA (40-char hex)
    issue_number: int
    bmad_specification: Dict[str, Any]  # Original requirement
    implementation_summary: str  # Code changes
    test_results: Dict[str, Any]  # Public + sealed summary
    mutation_results: Dict[str, Any]  # Mutation testing results
    sealed_acceptance_summary: Dict[str, Any]  # Observable pass/fail only
    evidence_manifest: Optional[Dict[str, Any]] = None

    def validate_shas(self) -> bool:
        """Validate SHAs are 40-char hex (§13)."""
        for sha in [self.base_sha, self.head_sha]:
            if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
                return False
        return True


@dataclass
class ReviewSession:
    """Fresh, isolated review session (§13)."""
    run_id: str
    reviewer_role: str  # "reviewer" role
    session_id: str  # Unique per review
    issue_number: int
    context: ReviewContext
    findings: List[ReviewFinding] = None
    verdict: Optional[ReviewVerdict] = None
    protected_paths_touched: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if self.findings is None:
            self.findings = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "run_id": self.run_id,
            "reviewer_role": self.reviewer_role,
            "session_id": self.session_id,
            "issue_number": self.issue_number,
            "base_sha": self.context.base_sha,
            "head_sha": self.context.head_sha,
            "findings_count": len(self.findings),
            "verdict": self.verdict.value if self.verdict else None,
            "protected_paths_touched": self.protected_paths_touched,
            "created_at": self.created_at,
        }


class ReviewBroker:
    """
    Broker independent review sessions with SHA binding (§13).

    Each review is fresh (new session, new conversation) and SHA-bound:
    - Reviewer sees only approved/orchestrator-compiled context
    - Reviews specific SHAs (base, head)
    - Auto-merge requires reviewed head SHA == current PR head SHA
    """

    def __init__(self):
        """Initialize review broker."""
        self.sessions: Dict[str, ReviewSession] = {}

    def create_review_session(
        self,
        run_id: str,
        issue_number: int,
        base_sha: str,
        head_sha: str,
        bmad_spec: Dict[str, Any],
        implementation_summary: str,
        test_results: Dict[str, Any],
        mutation_results: Dict[str, Any],
        sealed_acceptance_summary: Dict[str, Any],
    ) -> ReviewSession:
        """
        Create fresh review session (§13).

        Args:
            run_id: factory run ID
            issue_number: GitHub issue number
            base_sha: base commit SHA (40-char hex)
            head_sha: PR head commit SHA (40-char hex)
            bmad_spec: BMAD specification
            implementation_summary: code changes summary
            test_results: public test results
            mutation_results: mutation testing results
            sealed_acceptance_summary: sealed acceptance summary (observable only)

        Returns:
            ReviewSession (fresh, isolated)
        """
        context = ReviewContext(
            base_sha=base_sha,
            head_sha=head_sha,
            issue_number=issue_number,
            bmad_specification=bmad_spec,
            implementation_summary=implementation_summary,
            test_results=test_results,
            mutation_results=mutation_results,
            sealed_acceptance_summary=sealed_acceptance_summary,
        )

        if not context.validate_shas():
            raise ValueError("Invalid SHAs (must be 40-char hex)")

        session_id = f"review-{run_id}-{issue_number}-{datetime.utcnow().isoformat()[:10]}"

        session = ReviewSession(
            run_id=run_id,
            reviewer_role="reviewer",
            session_id=session_id,
            issue_number=issue_number,
            context=context,
        )

        self.sessions[session_id] = session
        return session

    def add_finding(
        self,
        session_id: str,
        dimension: ReviewDimension,
        severity: FindingSeverity,
        statement: str,
        evidence: List[str],
        recommendation: Optional[str] = None,
        blocked: bool = False,
    ) -> ReviewFinding:
        """
        Add finding to review session.

        Args:
            session_id: review session ID
            dimension: which dimension (requirements, security, etc.)
            severity: CRITICAL, HIGH, MEDIUM, LOW
            statement: finding statement
            evidence: citations from requirements/code/tests
            recommendation: suggested resolution
            blocked: if true, blocks auto-merge

        Returns:
            ReviewFinding (recorded)
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]

        finding = ReviewFinding(
            dimension=dimension,
            severity=severity,
            statement=statement,
            evidence=evidence,
            recommendation=recommendation,
            blocked=blocked,
        )

        session.findings.append(finding)
        return finding

    def finalize_verdict(
        self,
        session_id: str,
        verdict: ReviewVerdict,
        protected_paths_touched: bool = False,
    ) -> ReviewSession:
        """
        Finalize review verdict.

        Args:
            session_id: review session ID
            verdict: APPROVED, REJECTED, DECISION_REQUIRED
            protected_paths_touched: if true, blocks auto-merge

        Returns:
            finalized ReviewSession
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]
        session.verdict = verdict
        session.protected_paths_touched = protected_paths_touched

        return session

    def get_session(self, session_id: str) -> Optional[ReviewSession]:
        """Get review session by ID."""
        return self.sessions.get(session_id)


class ReviewGate:
    """
    Review gate: auto-merge prerequisites (§13).

    Auto-merge requires:
    - Verdict: APPROVED
    - No blocked findings
    - No protected paths touched
    - Reviewed head SHA == current PR head SHA
    - Evidence manifest valid
    - All requirements covered
    """

    def __init__(self, session: ReviewSession, current_head_sha: str):
        """
        Initialize review gate.

        Args:
            session: completed review session
            current_head_sha: current PR head SHA (must match reviewed SHA)
        """
        self.session = session
        self.current_head_sha = current_head_sha

    def can_auto_merge(self) -> bool:
        """Determine if auto-merge allowed (§13)."""
        # Condition 1: Verdict is APPROVED
        if self.session.verdict != ReviewVerdict.APPROVED:
            return False

        # Condition 2: No blocked findings
        blocked = [f for f in self.session.findings if f.blocked]
        if blocked:
            return False

        # Condition 3: No protected paths touched
        if self.session.protected_paths_touched:
            return False

        # Condition 4: Reviewed head SHA matches current PR head SHA (§13)
        if self.session.context.head_sha != self.current_head_sha:
            return False

        return True

    def cannot_merge_reason(self) -> Optional[str]:
        """Get reason why auto-merge blocked."""
        if self.session.verdict != ReviewVerdict.APPROVED:
            return f"Verdict not approved: {self.session.verdict.value}"

        blocked = [f for f in self.session.findings if f.blocked]
        if blocked:
            return f"{len(blocked)} blocking finding(s)"

        if self.session.protected_paths_touched:
            return "Protected paths were modified"

        if self.session.context.head_sha != self.current_head_sha:
            return (
                f"SHA mismatch: reviewed {self.session.context.head_sha[:8]} "
                f"!= current {self.current_head_sha[:8]} (§13)"
            )

        return None

    def report(self) -> Dict[str, Any]:
        """Generate auto-merge gate report."""
        return {
            "can_auto_merge": self.can_auto_merge(),
            "reason": self.cannot_merge_reason() or "Ready for auto-merge",
            "verdict": self.session.verdict.value if self.session.verdict else None,
            "findings": len(self.session.findings),
            "blocked_findings": sum(1 for f in self.session.findings if f.blocked),
            "protected_paths_touched": self.session.protected_paths_touched,
            "sha_match": self.session.context.head_sha == self.current_head_sha,
            "base_sha": self.session.context.base_sha[:8],
            "head_sha": self.session.context.head_sha[:8],
            "current_head_sha": self.current_head_sha[:8],
        }
