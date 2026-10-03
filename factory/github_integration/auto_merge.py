"""
Auto-Merge Prerequisites Validator.

Per master plan §14:
"Auto-merge prerequisites: no unresolved business decisions, valid intent,
authority allows, all checks pass, sealed and mutation pass, independent
review pass, protected paths unchanged, preview pass, no conflict, valid
evidence, and reviewed SHA equals head SHA.

Never push directly to main, never use admin bypass, never modify branch
protection, and never auto-merge governance changes."
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class AutoMergePrerequisite(str, Enum):
    """Auto-merge prerequisites (§14)."""
    NO_BUSINESS_DECISIONS = "no_unresolved_business_decisions"
    VALID_INTENT = "valid_intent"
    AUTHORITY_ALLOWS = "authority_allows"
    ALL_CHECKS_PASS = "all_checks_pass"
    SEALED_PASS = "sealed_and_mutation_pass"
    INDEPENDENT_REVIEW_PASS = "independent_review_pass"
    PROTECTED_PATHS_UNCHANGED = "protected_paths_unchanged"
    PREVIEW_PASS = "preview_pass"
    NO_CONFLICT = "no_conflict"
    VALID_EVIDENCE = "valid_evidence"
    SHA_MATCH = "reviewed_sha_equals_head_sha"
    NO_GOVERNANCE_CHANGES = "no_governance_changes"


@dataclass
class CheckStatus:
    """Status of a required check."""
    name: str
    passed: bool
    url: Optional[str] = None
    description: Optional[str] = None
    timestamp: str = ""


@dataclass
class AutoMergeValidation:
    """Auto-merge prerequisites validation result."""
    can_auto_merge: bool
    prerequisites_met: Dict[str, bool]  # prerequisite -> met
    check_results: List[CheckStatus]
    blocked_reasons: List[str]  # Why auto-merge is blocked
    warnings: List[str]  # Non-blocking issues


class AutoMergeGate:
    """
    Validate auto-merge prerequisites (§14).

    Checks:
    1. No unresolved business decisions
    2. Valid intent (BMAD specification complete)
    3. Authority allows (no governance/protected path changes)
    4. All required checks pass
    5. Sealed acceptance + mutation pass
    6. Independent review passes
    7. Protected paths unchanged
    8. Preview passes
    9. No PR conflicts
    10. Valid evidence manifest
    11. Reviewed SHA == head SHA
    12. No governance changes auto-merge
    """

    def __init__(self):
        """Initialize auto-merge gate."""
        pass

    def validate_prerequisites(
        self,
        business_decisions_resolved: bool,
        intent_valid: bool,
        authority_allows: bool,
        all_checks_pass: bool,
        sealed_pass: bool,
        review_pass: bool,
        protected_paths_changed: bool,
        preview_pass: bool,
        pr_has_conflict: bool,
        evidence_valid: bool,
        sha_match: bool,
        governance_changes: bool,
    ) -> AutoMergeValidation:
        """
        Validate all auto-merge prerequisites (§14).

        Args:
            business_decisions_resolved: strategic ambiguities resolved
            intent_valid: BMAD spec complete
            authority_allows: no governance/protected paths
            all_checks_pass: all required checks pass
            sealed_pass: sealed acceptance + mutation pass
            review_pass: independent review approved
            protected_paths_changed: any protected paths modified
            preview_pass: preview deployment passed
            pr_has_conflict: PR conflicts with main
            evidence_valid: evidence manifest valid
            sha_match: reviewed head SHA == current PR head SHA
            governance_changes: any governance file changes

        Returns:
            AutoMergeValidation with detailed results
        """
        prerequisites = {
            AutoMergePrerequisite.NO_BUSINESS_DECISIONS.value: business_decisions_resolved,
            AutoMergePrerequisite.VALID_INTENT.value: intent_valid,
            AutoMergePrerequisite.AUTHORITY_ALLOWS.value: authority_allows,
            AutoMergePrerequisite.ALL_CHECKS_PASS.value: all_checks_pass,
            AutoMergePrerequisite.SEALED_PASS.value: sealed_pass,
            AutoMergePrerequisite.INDEPENDENT_REVIEW_PASS.value: review_pass,
            AutoMergePrerequisite.PROTECTED_PATHS_UNCHANGED.value: not protected_paths_changed,
            AutoMergePrerequisite.PREVIEW_PASS.value: preview_pass,
            AutoMergePrerequisite.NO_CONFLICT.value: not pr_has_conflict,
            AutoMergePrerequisite.VALID_EVIDENCE.value: evidence_valid,
            AutoMergePrerequisite.SHA_MATCH.value: sha_match,
            AutoMergePrerequisite.NO_GOVERNANCE_CHANGES.value: not governance_changes,
        }

        can_merge = all(prerequisites.values())

        blocked_reasons = []
        if not business_decisions_resolved:
            blocked_reasons.append("Unresolved business decisions")
        if not intent_valid:
            blocked_reasons.append("Intent (BMAD specification) incomplete")
        if not authority_allows:
            blocked_reasons.append("Authority does not allow (may be protected path change)")
        if not all_checks_pass:
            blocked_reasons.append("Some required checks failed")
        if not sealed_pass:
            blocked_reasons.append("Sealed acceptance or mutation tests failed")
        if not review_pass:
            blocked_reasons.append("Independent review did not approve")
        if protected_paths_changed:
            blocked_reasons.append("Protected paths were modified (§14)")
        if not preview_pass:
            blocked_reasons.append("Preview deployment failed")
        if pr_has_conflict:
            blocked_reasons.append("PR has conflicts with main")
        if not evidence_valid:
            blocked_reasons.append("Evidence manifest invalid")
        if not sha_match:
            blocked_reasons.append("Reviewed SHA != current head SHA (§13 binding)")
        if governance_changes:
            blocked_reasons.append("Governance changes cannot auto-merge (§14)")

        warnings = []
        if not intent_valid:
            warnings.append("Consider re-running BMAD analysis")

        return AutoMergeValidation(
            can_auto_merge=can_merge,
            prerequisites_met=prerequisites,
            check_results=[],
            blocked_reasons=blocked_reasons,
            warnings=warnings,
        )

    def get_report(self, validation: AutoMergeValidation) -> Dict[str, Any]:
        """Generate auto-merge report."""
        return {
            "can_auto_merge": validation.can_auto_merge,
            "prerequisites_met": validation.prerequisites_met,
            "blocked_count": len(validation.blocked_reasons),
            "blocked_reasons": validation.blocked_reasons,
            "warnings": validation.warnings,
            "all_passed": all(validation.prerequisites_met.values()),
        }
