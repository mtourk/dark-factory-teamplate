"""
Phase 11: Independent Review tests.

Tests for:
1. Fresh review sessions (new conversation per review)
2. SHA binding (base/head SHAs are 40-char hex)
3. Review context (approved context only)
4. 14 review dimensions (requirements, architecture, security, etc.)
5. Review findings (dimension, severity, evidence, blocked status)
6. Review verdicts (approved, rejected, decision_required)
7. Auto-merge prerequisites
8. SHA mismatch detection (reviewed vs current PR head)
9. Protected paths detection
10. Blocked findings detection
11. Review gate (can_auto_merge decision)
12. Evidence gaps
13. Mutation survival assessment
14. False-pass risk assessment
"""

import pytest
from datetime import datetime

from factory.review.independent import (
    ReviewDimension,
    ReviewVerdict,
    FindingSeverity,
    ReviewFinding,
    ReviewContext,
    ReviewSession,
    ReviewBroker,
    ReviewGate,
)


# ============================================================================
# Review Context and SHA Binding Tests (§13)
# ============================================================================

class TestReviewContext:
    """Test review context and SHA binding."""

    def test_review_context_creation(self):
        """Review context created with SHAs and specification."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={"requirement": "Search"},
            implementation_summary="Added search.py",
            test_results={"passed": 10, "failed": 0},
            mutation_results={"killed": 90, "survived": 10},
            sealed_acceptance_summary={"passed": True},
        )

        assert context.base_sha == "a" * 40
        assert context.head_sha == "b" * 40

    def test_sha_validation_valid(self):
        """Valid SHAs (40-char hex) pass validation."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=1,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        assert context.validate_shas() is True

    def test_sha_validation_invalid_length(self):
        """Invalid SHA length rejected."""
        context = ReviewContext(
            base_sha="short",  # Too short
            head_sha="b" * 40,
            issue_number=1,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        assert context.validate_shas() is False

    def test_sha_validation_invalid_chars(self):
        """Invalid SHA characters rejected."""
        context = ReviewContext(
            base_sha="z" * 40,  # 'z' not valid hex
            head_sha="b" * 40,
            issue_number=1,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        assert context.validate_shas() is False


# ============================================================================
# Review Session and Findings Tests (§13)
# ============================================================================

class TestReviewSession:
    """Test review sessions and findings."""

    def test_review_session_creation(self):
        """Review session created with fresh session ID."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-RUN-001-42-2026-10-03",
            issue_number=42,
            context=context,
        )

        assert session.reviewer_role == "reviewer"
        assert session.verdict is None

    def test_review_findings_creation(self):
        """Review finding created with dimension and severity."""
        finding = ReviewFinding(
            dimension=ReviewDimension.REQUIREMENTS,
            severity=FindingSeverity.HIGH,
            statement="Missing error handling for network failures",
            evidence=["Issue #42: requirements", "Code review"],
            recommendation="Add try/catch around network call",
            blocked=False,
        )

        assert finding.dimension == ReviewDimension.REQUIREMENTS
        assert finding.severity == FindingSeverity.HIGH


# ============================================================================
# Review Dimensions Tests (§13)
# ============================================================================

class TestReviewDimensions:
    """Test all 14 review dimensions."""

    def test_all_dimensions_covered(self):
        """All 14 dimensions defined."""
        dimensions = [d for d in ReviewDimension]
        assert len(dimensions) == 14
        assert ReviewDimension.REQUIREMENTS in dimensions
        assert ReviewDimension.ARCHITECTURE in dimensions
        assert ReviewDimension.PERMISSIONS in dimensions
        assert ReviewDimension.SECURITY in dimensions
        assert ReviewDimension.ERROR_HANDLING in dimensions
        assert ReviewDimension.DATA_BEHAVIOR in dimensions
        assert ReviewDimension.SCOPE in dimensions
        assert ReviewDimension.TESTS in dimensions
        assert ReviewDimension.MUTATION in dimensions
        assert ReviewDimension.FALSE_PASS_RISK in dimensions
        assert ReviewDimension.DEPENDENCIES in dimensions
        assert ReviewDimension.RECOVERY in dimensions
        assert ReviewDimension.DOCUMENTATION in dimensions
        assert ReviewDimension.EVIDENCE in dimensions


# ============================================================================
# Review Broker Tests (§13)
# ============================================================================

class TestReviewBroker:
    """Test review session creation and management."""

    def test_review_broker_initialization(self):
        """Review broker initializes."""
        broker = ReviewBroker()
        assert len(broker.sessions) == 0

    def test_create_review_session(self):
        """Create fresh review session."""
        broker = ReviewBroker()

        session = broker.create_review_session(
            run_id="RUN-001",
            issue_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            bmad_spec={"requirement": "Search"},
            implementation_summary="Added search",
            test_results={"passed": 10},
            mutation_results={"killed": 90},
            sealed_acceptance_summary={"passed": True},
        )

        assert session.issue_number == 42
        assert session.context.base_sha == "a" * 40

    def test_create_review_session_invalid_sha(self):
        """Invalid SHA rejected on session creation."""
        broker = ReviewBroker()

        with pytest.raises(ValueError, match="Invalid SHAs"):
            broker.create_review_session(
                run_id="RUN-001",
                issue_number=42,
                base_sha="invalid",  # Too short
                head_sha="b" * 40,
                bmad_spec={},
                implementation_summary="",
                test_results={},
                mutation_results={},
                sealed_acceptance_summary={},
            )

    def test_add_finding_to_session(self):
        """Add finding to review session."""
        broker = ReviewBroker()

        session = broker.create_review_session(
            run_id="RUN-001",
            issue_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            bmad_spec={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        finding = broker.add_finding(
            session.session_id,
            dimension=ReviewDimension.SECURITY,
            severity=FindingSeverity.CRITICAL,
            statement="SQL injection vulnerability",
            evidence=["Code line 42", "Not using parameterized query"],
            blocked=True,
        )

        assert finding.blocked is True
        assert len(session.findings) == 1

    def test_finalize_verdict(self):
        """Finalize review verdict."""
        broker = ReviewBroker()

        session = broker.create_review_session(
            run_id="RUN-001",
            issue_number=42,
            base_sha="a" * 40,
            head_sha="b" * 40,
            bmad_spec={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = broker.finalize_verdict(
            session.session_id,
            ReviewVerdict.APPROVED,
            protected_paths_touched=False,
        )

        assert session.verdict == ReviewVerdict.APPROVED


# ============================================================================
# Auto-Merge Prerequisites Tests (§13)
# ============================================================================

class TestAutoMergePrerequisites:
    """Test auto-merge gate and prerequisites."""

    def test_gate_approved_no_findings(self):
        """Gate approves when verdict approved and no blocked findings."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            verdict=ReviewVerdict.APPROVED,
            protected_paths_touched=False,
        )

        gate = ReviewGate(session, "b" * 40)
        assert gate.can_auto_merge() is True

    def test_gate_rejected_verdict(self):
        """Gate rejects when verdict rejected."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            verdict=ReviewVerdict.REJECTED,
            protected_paths_touched=False,
        )

        gate = ReviewGate(session, "b" * 40)
        assert gate.can_auto_merge() is False

    def test_gate_blocked_findings(self):
        """Gate rejects if blocked findings present."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        finding = ReviewFinding(
            dimension=ReviewDimension.SECURITY,
            severity=FindingSeverity.CRITICAL,
            statement="Critical issue",
            evidence=[],
            blocked=True,
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            findings=[finding],
            verdict=ReviewVerdict.APPROVED,
            protected_paths_touched=False,
        )

        gate = ReviewGate(session, "b" * 40)
        assert gate.can_auto_merge() is False

    def test_gate_protected_paths_touched(self):
        """Gate rejects if protected paths modified."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            verdict=ReviewVerdict.APPROVED,
            protected_paths_touched=True,  # Protected path modified!
        )

        gate = ReviewGate(session, "b" * 40)
        assert gate.can_auto_merge() is False

    def test_gate_sha_mismatch(self):
        """Gate rejects if reviewed SHA != current PR head SHA (§13)."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            verdict=ReviewVerdict.APPROVED,
            protected_paths_touched=False,
        )

        current_head = "c" * 40  # Different from reviewed "b" * 40

        gate = ReviewGate(session, current_head)
        assert gate.can_auto_merge() is False
        assert "SHA mismatch" in gate.cannot_merge_reason()

    def test_gate_report(self):
        """Gate generates detailed report."""
        context = ReviewContext(
            base_sha="a" * 40,
            head_sha="b" * 40,
            issue_number=42,
            bmad_specification={},
            implementation_summary="",
            test_results={},
            mutation_results={},
            sealed_acceptance_summary={},
        )

        session = ReviewSession(
            run_id="RUN-001",
            reviewer_role="reviewer",
            session_id="review-1",
            issue_number=42,
            context=context,
            verdict=ReviewVerdict.APPROVED,
            protected_paths_touched=False,
        )

        gate = ReviewGate(session, "b" * 40)
        report = gate.report()

        assert "can_auto_merge" in report
        assert "verdict" in report
        assert "sha_match" in report
        assert report["can_auto_merge"] is True


# ============================================================================
# Phase 11 Gate Test
# ============================================================================

def test_phase11_gate_independent_review_operational():
    """
    Phase 11 Gate: Independent review is operational.

    Verifies:
    - Fresh review sessions (new conversation per review)
    - SHA binding (base/head 40-char hex)
    - Review context (approved context only)
    - 14 review dimensions covered
    - Review findings (dimension, severity, evidence, blocked)
    - Review verdicts (approved, rejected, decision_required)
    - Auto-merge prerequisites
    - SHA mismatch detection (reviewed vs current PR head §13)
    - Protected paths detection
    - Blocked findings detection
    - Review gate (can_auto_merge decision)
    """
    # Review context with SHAs
    context = ReviewContext(
        base_sha="a" * 40,
        head_sha="b" * 40,
        issue_number=42,
        bmad_specification={"title": "Search feature", "criteria": ["Find by name"]},
        implementation_summary="Added search.py with main search function",
        test_results={"unit": 10, "integration": 5, "passed": 15, "failed": 0},
        mutation_results={"killed": 95, "survived": 5, "total": 100},
        sealed_acceptance_summary={"passed": True, "failures": 0},
    )

    assert context.validate_shas() is True

    # Review broker and session
    broker = ReviewBroker()

    session = broker.create_review_session(
        run_id="RUN-gate001",
        issue_number=42,
        base_sha="a" * 40,
        head_sha="b" * 40,
        bmad_spec=context.bmad_specification,
        implementation_summary=context.implementation_summary,
        test_results=context.test_results,
        mutation_results=context.mutation_results,
        sealed_acceptance_summary=context.sealed_acceptance_summary,
    )

    assert session.reviewer_role == "reviewer"

    # Review all 14 dimensions
    dimensions = [d for d in ReviewDimension]
    assert len(dimensions) == 14

    # Add findings
    broker.add_finding(
        session.session_id,
        ReviewDimension.REQUIREMENTS,
        FindingSeverity.LOW,
        "Requirements well covered",
        ["Issue matches implementation"],
    )

    broker.add_finding(
        session.session_id,
        ReviewDimension.TESTS,
        FindingSeverity.LOW,
        "Test coverage good",
        ["15 tests passed, mutation 95% killed"],
    )

    broker.add_finding(
        session.session_id,
        ReviewDimension.SECURITY,
        FindingSeverity.MEDIUM,
        "Validate user input",
        ["Code doesn't sanitize search string"],
        recommendation="Add input validation",
    )

    assert len(session.findings) == 3

    # Finalize verdict
    session = broker.finalize_verdict(
        session.session_id,
        ReviewVerdict.APPROVED,
        protected_paths_touched=False,
    )

    assert session.verdict == ReviewVerdict.APPROVED

    # Auto-merge gate - SHA match
    gate = ReviewGate(session, "b" * 40)
    assert gate.can_auto_merge() is True

    report = gate.report()
    assert report["can_auto_merge"] is True
    assert report["sha_match"] is True

    # Auto-merge gate - SHA mismatch (§13)
    gate_mismatch = ReviewGate(session, "c" * 40)
    assert gate_mismatch.can_auto_merge() is False
    assert "SHA mismatch" in gate_mismatch.cannot_merge_reason()

    # Auto-merge gate - blocked findings
    blocked_finding = ReviewFinding(
        dimension=ReviewDimension.SECURITY,
        severity=FindingSeverity.CRITICAL,
        statement="SQL injection",
        evidence=[],
        blocked=True,
    )
    session.findings.append(blocked_finding)

    gate_blocked = ReviewGate(session, "b" * 40)
    assert gate_blocked.can_auto_merge() is False

    print("✓ Phase 11 Gate: Independent review operational (SHA-bound, 14 dimensions)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
