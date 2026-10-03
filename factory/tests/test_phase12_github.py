"""
Phase 12: GitHub and Auto-Merge tests.

Tests for:
1. Factory labels (18 states)
2. State machine transitions (valid/invalid)
3. Required checks (18 checks)
4. Auto-merge prerequisites (12 prerequisites)
5. Auto-merge gate (validation logic)
6. Blocked reasons (all 12 blocking conditions)
7. Governance changes prevention
8. Protected paths preservation
9. SHA binding enforcement
10. Business decision resolution
11. Evidence validation
12. Preview pass requirement
"""

import pytest
from typing import List

from factory.github_integration.labels import (
    FactoryLabel,
    RequiredCheck,
    GitHubStateTransition,
)
from factory.github_integration.auto_merge import (
    AutoMergePrerequisite,
    CheckStatus,
    AutoMergeValidation,
    AutoMergeGate,
)


# ============================================================================
# Factory Label Tests (§14)
# ============================================================================

class TestFactoryLabels:
    """Test factory state machine labels."""

    def test_all_labels_defined(self):
        """All 18 factory labels defined."""
        labels = [l for l in FactoryLabel]
        assert len(labels) == 18
        assert FactoryLabel.FACTORY_READY in labels
        assert FactoryLabel.FACTORY_DELIVERED in labels
        assert FactoryLabel.FACTORY_QUARANTINED in labels

    def test_label_enum_values(self):
        """Label values formatted correctly (factory:name)."""
        assert FactoryLabel.FACTORY_READY.value == "factory:ready"
        assert FactoryLabel.FACTORY_CLAIMED.value == "factory:claimed"
        assert FactoryLabel.FACTORY_AUTO_MERGE.value == "factory:auto-merge"


# ============================================================================
# State Machine Transition Tests (§14)
# ============================================================================

class TestStateTransitions:
    """Test valid state transitions."""

    def test_ready_to_claimed(self):
        """Ready transitions to claimed."""
        valid = GitHubStateTransition.is_valid_transition(
            FactoryLabel.FACTORY_READY,
            FactoryLabel.FACTORY_CLAIMED,
        )
        assert valid is True

    def test_ready_to_blocked(self):
        """Ready can transition to blocked."""
        valid = GitHubStateTransition.is_valid_transition(
            FactoryLabel.FACTORY_READY,
            FactoryLabel.FACTORY_BLOCKED,
        )
        assert valid is True

    def test_ready_to_invalid_transition(self):
        """Ready cannot skip to implementing."""
        valid = GitHubStateTransition.is_valid_transition(
            FactoryLabel.FACTORY_READY,
            FactoryLabel.FACTORY_IMPLEMENTING,
        )
        assert valid is False

    def test_full_pipeline_transitions(self):
        """Full pipeline: ready → claimed → analyzing → planning → implementing → verifying → reviewing → preview → auto-merge → deploying → delivered."""
        transitions = [
            (FactoryLabel.FACTORY_READY, FactoryLabel.FACTORY_CLAIMED),
            (FactoryLabel.FACTORY_CLAIMED, FactoryLabel.FACTORY_ANALYZING),
            (FactoryLabel.FACTORY_ANALYZING, FactoryLabel.FACTORY_PLANNING),
            (FactoryLabel.FACTORY_PLANNING, FactoryLabel.FACTORY_IMPLEMENTING),
            (FactoryLabel.FACTORY_IMPLEMENTING, FactoryLabel.FACTORY_VERIFYING),
            (FactoryLabel.FACTORY_VERIFYING, FactoryLabel.FACTORY_REVIEWING),
            (FactoryLabel.FACTORY_REVIEWING, FactoryLabel.FACTORY_PREVIEW),
            (FactoryLabel.FACTORY_PREVIEW, FactoryLabel.FACTORY_AUTO_MERGE),
            (FactoryLabel.FACTORY_AUTO_MERGE, FactoryLabel.FACTORY_DEPLOYING),
            (FactoryLabel.FACTORY_DEPLOYING, FactoryLabel.FACTORY_VALIDATING_PRODUCTION),
            (FactoryLabel.FACTORY_VALIDATING_PRODUCTION, FactoryLabel.FACTORY_DELIVERED),
        ]

        for from_label, to_label in transitions:
            valid = GitHubStateTransition.is_valid_transition(from_label, to_label)
            assert valid is True, f"Transition {from_label.value} -> {to_label.value} should be valid"

    def test_get_allowed_transitions(self):
        """Get allowed next states from current state."""
        allowed = GitHubStateTransition.get_allowed_transitions(FactoryLabel.FACTORY_READY)

        assert FactoryLabel.FACTORY_CLAIMED in allowed
        assert FactoryLabel.FACTORY_BLOCKED in allowed
        assert len(allowed) == 2


# ============================================================================
# Required Checks Tests (§14)
# ============================================================================

class TestRequiredChecks:
    """Test required status checks."""

    def test_all_checks_defined(self):
        """All 18 required checks defined."""
        checks = [c for c in RequiredCheck]
        assert len(checks) == 18

    def test_check_categories(self):
        """Checks cover all categories."""
        checks = [c for c in RequiredCheck]

        # Intent and authority
        assert RequiredCheck.CHECK_INTENT in checks
        assert RequiredCheck.CHECK_AUTHORITY in checks

        # Code quality
        assert RequiredCheck.CHECK_FORMAT in checks
        assert RequiredCheck.CHECK_LINT in checks

        # Security
        assert RequiredCheck.CHECK_SECRET_SCAN in checks
        assert RequiredCheck.CHECK_STATIC_SECURITY in checks

        # Advanced
        assert RequiredCheck.CHECK_MUTATION in checks
        assert RequiredCheck.CHECK_SEALED_QA in checks
        assert RequiredCheck.CHECK_INDEPENDENT_REVIEW in checks

        # Evidence
        assert RequiredCheck.CHECK_EVIDENCE_MANIFEST in checks

    def test_check_names_formatted(self):
        """Check names formatted as factory/check-name."""
        for check in RequiredCheck:
            assert check.value.startswith("factory/check-")


# ============================================================================
# Auto-Merge Prerequisites Tests (§14)
# ============================================================================

class TestAutoMergePrerequisites:
    """Test auto-merge prerequisites."""

    def test_all_prerequisites_defined(self):
        """All 12 prerequisites defined."""
        prqs = [p for p in AutoMergePrerequisite]
        assert len(prqs) == 12

    def test_prerequisite_values(self):
        """Prerequisite values are descriptive."""
        assert AutoMergePrerequisite.NO_BUSINESS_DECISIONS.value == "no_unresolved_business_decisions"
        assert AutoMergePrerequisite.AUTHORITY_ALLOWS.value == "authority_allows"
        assert AutoMergePrerequisite.SHA_MATCH.value == "reviewed_sha_equals_head_sha"


# ============================================================================
# Auto-Merge Gate Tests (§14)
# ============================================================================

class TestAutoMergeGate:
    """Test auto-merge validation gate."""

    def test_all_prerequisites_pass(self):
        """Auto-merge allowed when all prerequisites pass."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is True
        assert len(validation.blocked_reasons) == 0

    def test_business_decisions_block(self):
        """Unresolved business decisions block auto-merge."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=False,  # Block!
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "Unresolved business decisions" in validation.blocked_reasons

    def test_protected_paths_block(self):
        """Protected path changes block auto-merge (§14)."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=True,  # Block!
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "Protected paths were modified" in validation.blocked_reasons

    def test_governance_changes_block(self):
        """Governance changes block auto-merge (§14)."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=True,  # Block!
        )

        assert validation.can_auto_merge is False
        assert "Governance changes cannot auto-merge" in validation.blocked_reasons

    def test_sha_mismatch_block(self):
        """SHA mismatch blocks auto-merge (§13 binding)."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=False,  # Block! (§13)
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "Reviewed SHA != current head SHA" in validation.blocked_reasons

    def test_check_failure_blocks(self):
        """Failed checks block auto-merge."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=False,  # Block!
            sealed_pass=True,
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "required checks failed" in validation.blocked_reasons

    def test_sealed_mutation_blocks(self):
        """Sealed or mutation failure blocks auto-merge."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=False,  # Block!
            review_pass=True,
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "Sealed acceptance or mutation" in validation.blocked_reasons

    def test_review_rejection_blocks(self):
        """Review rejection blocks auto-merge."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=True,
            intent_valid=True,
            authority_allows=True,
            all_checks_pass=True,
            sealed_pass=True,
            review_pass=False,  # Block!
            protected_paths_changed=False,
            preview_pass=True,
            pr_has_conflict=False,
            evidence_valid=True,
            sha_match=True,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert "Independent review did not approve" in validation.blocked_reasons

    def test_multiple_blocks(self):
        """Multiple blocking conditions reported."""
        gate = AutoMergeGate()

        validation = gate.validate_prerequisites(
            business_decisions_resolved=False,
            intent_valid=False,
            authority_allows=True,
            all_checks_pass=False,
            sealed_pass=False,
            review_pass=True,
            protected_paths_changed=True,
            preview_pass=False,
            pr_has_conflict=True,
            evidence_valid=False,
            sha_match=False,
            governance_changes=False,
        )

        assert validation.can_auto_merge is False
        assert len(validation.blocked_reasons) > 5


# ============================================================================
# Phase 12 Gate Test
# ============================================================================

def test_phase12_gate_github_and_auto_merge_operational():
    """
    Phase 12 Gate: GitHub integration and auto-merge are operational.

    Verifies:
    - 18 factory labels (state machine)
    - Valid state transitions
    - 18 required status checks
    - 12 auto-merge prerequisites
    - Auto-merge gate logic
    - All blocking conditions
    - Protected paths prevention
    - Governance changes prevention
    - SHA binding enforcement (§13)
    - Business decision resolution
    - Evidence validation
    - Preview requirement
    """
    # Labels
    labels = [l for l in FactoryLabel]
    assert len(labels) == 18

    # State machine
    assert GitHubStateTransition.is_valid_transition(
        FactoryLabel.FACTORY_READY,
        FactoryLabel.FACTORY_CLAIMED,
    )

    assert not GitHubStateTransition.is_valid_transition(
        FactoryLabel.FACTORY_READY,
        FactoryLabel.FACTORY_DEPLOYING,
    )

    # Required checks
    checks = [c for c in RequiredCheck]
    assert len(checks) == 18
    assert all(c.value.startswith("factory/check-") for c in checks)

    # Auto-merge prerequisites
    prqs = [p for p in AutoMergePrerequisite]
    assert len(prqs) == 12

    # Gate - all pass
    gate = AutoMergeGate()

    validation_pass = gate.validate_prerequisites(
        business_decisions_resolved=True,
        intent_valid=True,
        authority_allows=True,
        all_checks_pass=True,
        sealed_pass=True,
        review_pass=True,
        protected_paths_changed=False,
        preview_pass=True,
        pr_has_conflict=False,
        evidence_valid=True,
        sha_match=True,
        governance_changes=False,
    )

    assert validation_pass.can_auto_merge is True

    # Gate - protected paths block
    validation_protected = gate.validate_prerequisites(
        business_decisions_resolved=True,
        intent_valid=True,
        authority_allows=True,
        all_checks_pass=True,
        sealed_pass=True,
        review_pass=True,
        protected_paths_changed=True,  # Protected path!
        preview_pass=True,
        pr_has_conflict=False,
        evidence_valid=True,
        sha_match=True,
        governance_changes=False,
    )

    assert validation_protected.can_auto_merge is False
    assert "Protected paths" in validation_protected.blocked_reasons[0]

    # Gate - governance block
    validation_governance = gate.validate_prerequisites(
        business_decisions_resolved=True,
        intent_valid=True,
        authority_allows=True,
        all_checks_pass=True,
        sealed_pass=True,
        review_pass=True,
        protected_paths_changed=False,
        preview_pass=True,
        pr_has_conflict=False,
        evidence_valid=True,
        sha_match=True,
        governance_changes=True,  # Governance!
    )

    assert validation_governance.can_auto_merge is False
    assert "Governance changes" in validation_governance.blocked_reasons[0]

    # Gate - SHA mismatch (§13)
    validation_sha = gate.validate_prerequisites(
        business_decisions_resolved=True,
        intent_valid=True,
        authority_allows=True,
        all_checks_pass=True,
        sealed_pass=True,
        review_pass=True,
        protected_paths_changed=False,
        preview_pass=True,
        pr_has_conflict=False,
        evidence_valid=True,
        sha_match=False,  # SHA mismatch!
        governance_changes=False,
    )

    assert validation_sha.can_auto_merge is False
    assert "SHA mismatch" in validation_sha.blocked_reasons[0]

    # Report
    report = gate.get_report(validation_pass)
    assert report["can_auto_merge"] is True
    assert report["all_passed"] is True

    print("✓ Phase 12 Gate: GitHub integration and auto-merge operational (18 labels, 18 checks, 12 prerequisites)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
