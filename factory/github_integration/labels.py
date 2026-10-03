"""
GitHub Labels and State Machine.

Per master plan §14:
"Use labels for ready, claimed, analyzing, decision-required, planning,
implementing, verifying, repairing, reviewing, preview, auto-merge,
deploying, validating-production, delivered, blocked, failed, and
quarantined."
"""

from enum import Enum
from typing import Dict, Any, List


class FactoryLabel(str, Enum):
    """Factory state machine labels (§14)."""
    # Initial state
    FACTORY_READY = "factory:ready"

    # Claiming and claiming
    FACTORY_CLAIMED = "factory:claimed"

    # Analysis phase
    FACTORY_ANALYZING = "factory:analyzing"
    FACTORY_DECISION_REQUIRED = "factory:decision-required"

    # Planning and implementation
    FACTORY_PLANNING = "factory:planning"
    FACTORY_IMPLEMENTING = "factory:implementing"

    # Verification and repair
    FACTORY_VERIFYING = "factory:verifying"
    FACTORY_REPAIRING = "factory:repairing"

    # Review and deployment
    FACTORY_REVIEWING = "factory:reviewing"
    FACTORY_PREVIEW = "factory:preview"
    FACTORY_AUTO_MERGE = "factory:auto-merge"
    FACTORY_DEPLOYING = "factory:deploying"
    FACTORY_VALIDATING_PRODUCTION = "factory:validating-production"

    # End states
    FACTORY_DELIVERED = "factory:delivered"
    FACTORY_BLOCKED = "factory:blocked"
    FACTORY_FAILED = "factory:failed"
    FACTORY_QUARANTINED = "factory:quarantined"


class RequiredCheck(str, Enum):
    """Required status checks for auto-merge (§14)."""
    # Intent and authority
    CHECK_INTENT = "factory/check-intent"
    CHECK_AUTHORITY = "factory/check-authority"
    CHECK_PROTECTED_PATHS = "factory/check-protected-paths"

    # Code quality
    CHECK_FORMAT = "factory/check-format"
    CHECK_LINT = "factory/check-lint"
    CHECK_TYPECHECK = "factory/check-typecheck"

    # Build and unit tests
    CHECK_BUILD = "factory/check-build"
    CHECK_UNIT = "factory/check-unit"

    # Integration and contract
    CHECK_CONTRACT = "factory/check-contract"
    CHECK_INTEGRATION = "factory/check-integration"

    # Security
    CHECK_SECRET_SCAN = "factory/check-secret-scan"
    CHECK_STATIC_SECURITY = "factory/check-static-security"
    CHECK_DEPENDENCY_SCAN = "factory/check-dependency-scan"

    # Advanced verification
    CHECK_MUTATION = "factory/check-mutation"
    CHECK_SEALED_QA = "factory/check-sealed-qa"

    # Review and preview
    CHECK_INDEPENDENT_REVIEW = "factory/check-independent-review"
    CHECK_PREVIEW = "factory/check-preview"
    CHECK_PREVIEW_SMOKE = "factory/check-preview-smoke"

    # Evidence
    CHECK_EVIDENCE_MANIFEST = "factory/check-evidence-manifest"


class GitHubStateTransition:
    """Valid state transitions for factory labels (§14)."""

    # State machine: which labels can transition to which
    VALID_TRANSITIONS = {
        FactoryLabel.FACTORY_READY: [
            FactoryLabel.FACTORY_CLAIMED,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_CLAIMED: [
            FactoryLabel.FACTORY_ANALYZING,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_ANALYZING: [
            FactoryLabel.FACTORY_DECISION_REQUIRED,
            FactoryLabel.FACTORY_PLANNING,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_DECISION_REQUIRED: [
            FactoryLabel.FACTORY_PLANNING,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_PLANNING: [
            FactoryLabel.FACTORY_IMPLEMENTING,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_IMPLEMENTING: [
            FactoryLabel.FACTORY_VERIFYING,
            FactoryLabel.FACTORY_REPAIRING,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_VERIFYING: [
            FactoryLabel.FACTORY_REPAIRING,
            FactoryLabel.FACTORY_REVIEWING,
            FactoryLabel.FACTORY_FAILED,
        ],
        FactoryLabel.FACTORY_REPAIRING: [
            FactoryLabel.FACTORY_VERIFYING,
            FactoryLabel.FACTORY_FAILED,
        ],
        FactoryLabel.FACTORY_REVIEWING: [
            FactoryLabel.FACTORY_PREVIEW,
            FactoryLabel.FACTORY_FAILED,
            FactoryLabel.FACTORY_BLOCKED,
        ],
        FactoryLabel.FACTORY_PREVIEW: [
            FactoryLabel.FACTORY_AUTO_MERGE,
            FactoryLabel.FACTORY_FAILED,
        ],
        FactoryLabel.FACTORY_AUTO_MERGE: [
            FactoryLabel.FACTORY_DEPLOYING,
            FactoryLabel.FACTORY_FAILED,
        ],
        FactoryLabel.FACTORY_DEPLOYING: [
            FactoryLabel.FACTORY_VALIDATING_PRODUCTION,
            FactoryLabel.FACTORY_FAILED,
        ],
        FactoryLabel.FACTORY_VALIDATING_PRODUCTION: [
            FactoryLabel.FACTORY_DELIVERED,
            FactoryLabel.FACTORY_QUARANTINED,
        ],
    }

    @classmethod
    def is_valid_transition(
        cls,
        from_label: FactoryLabel,
        to_label: FactoryLabel,
    ) -> bool:
        """Check if state transition is valid."""
        if from_label not in cls.VALID_TRANSITIONS:
            return False

        allowed = cls.VALID_TRANSITIONS[from_label]
        return to_label in allowed

    @classmethod
    def get_allowed_transitions(cls, current_label: FactoryLabel) -> List[FactoryLabel]:
        """Get allowed next states from current label."""
        return cls.VALID_TRANSITIONS.get(current_label, [])
