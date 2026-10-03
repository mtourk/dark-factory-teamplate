"""
Repair Coordinator: Bounded repair cycles with stall detection.

Per master plan §12:
"Default maximum repair cycles: 3. Repeating the same failure twice
without measurable progress triggers stall diagnosis.

Repair input is limited to category, relevant logs, expected/actual
behavior, allowed/prohibited paths, attempt, and previous patch digest.

Stop when a fix changes business meaning, touches protected paths,
exhausts resources, introduces strategic ambiguity, or repository state
differs from recorded state."
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class StopCondition(str, Enum):
    """Stop conditions for repair cycle (§12)."""
    BUSINESS_MEANING_CHANGE = "business_meaning_change"
    PROTECTED_PATH_TOUCHED = "protected_path_touched"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    STRATEGIC_AMBIGUITY = "strategic_ambiguity"
    REPO_STATE_DIFF = "repo_state_diff"
    MAX_ATTEMPTS_EXHAUSTED = "max_attempts_exhausted"
    STALL_DETECTED = "stall_detected"


@dataclass
class RepairInput:
    """Input to repairer: failure category, logs, context."""
    run_id: str
    issue_number: int
    attempt_number: int
    failure_category: str  # e.g., "unit_test", "lint", "type_error"
    failure_logs: str  # Relevant error output (truncated)
    expected_behavior: str  # What should happen
    actual_behavior: str  # What actually happened
    allowed_fix_scope: str  # Paths repairer can change
    prohibited_paths: List[str]
    previous_patch_digest: Optional[str] = None  # SHA of prior attempt


@dataclass
class RepairOutput:
    """Output from repairer: diagnosis and fix."""
    run_id: str
    issue_number: int
    attempt_number: int
    diagnosis: str  # Root cause analysis
    fix_explanation: str  # What was changed and why
    hypothesis: str  # Competing hypothesis (for stall detection)
    changes: Dict[str, str]  # Path -> content
    changed_files: List[str]
    patch_digest: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def compute_patch_digest(self) -> str:
        """Compute SHA-256 of repair patch."""
        patch_str = str(sorted(self.changes.items()))
        return hashlib.sha256(patch_str.encode()).hexdigest()


class RepairCycleTracker:
    """Track repair cycles for stall detection and stop conditions (§12)."""

    MAX_REPAIR_CYCLES = 3

    def __init__(self):
        """Initialize repair tracker."""
        self.cycles: List[RepairOutput] = []
        self.failure_history: List[str] = []  # Track repeated failures

    def add_cycle(self, output: RepairOutput):
        """Record repair cycle."""
        output.patch_digest = output.compute_patch_digest()
        self.cycles.append(output)

    def add_failure(self, failure_category: str):
        """Record failure category."""
        self.failure_history.append(failure_category)

    def is_stall_detected(self) -> bool:
        """Detect stall: same failure twice without progress (§12)."""
        if len(self.failure_history) < 2:
            return False

        # Check for same failure repeated twice in recent history
        recent = self.failure_history[-2:]
        if recent[0] == recent[1]:
            # Same failure twice - check if patches differ
            if len(self.cycles) >= 2:
                patch1 = self.cycles[-2].patch_digest
                patch2 = self.cycles[-1].patch_digest
                if patch1 == patch2:
                    # Identical patches - definite stall
                    return True

        return False

    def check_stop_conditions(self, output: RepairOutput) -> Optional[StopCondition]:
        """
        Check stop conditions (§12).

        Returns:
            StopCondition if should stop, else None
        """
        # Condition 1: Max cycles exhausted
        if len(self.cycles) >= self.MAX_REPAIR_CYCLES:
            return StopCondition.MAX_ATTEMPTS_EXHAUSTED

        # Condition 2: Stall detected
        if self.is_stall_detected():
            return StopCondition.STALL_DETECTED

        # Conditions 3-7: Would check actual output for:
        # - Business meaning changes
        # - Protected path touches
        # - Resource exhaustion
        # - Strategic ambiguity
        # - Repo state differences
        # (implementation depends on verifier state)

        return None

    def get_cycle_summary(self) -> Dict[str, Any]:
        """Get summary of repair cycles."""
        return {
            "cycles": len(self.cycles),
            "max_cycles": self.MAX_REPAIR_CYCLES,
            "failures": self.failure_history,
            "stall_detected": self.is_stall_detected(),
            "patch_digests": [c.patch_digest for c in self.cycles],
        }


class StallDiagnosisSession:
    """
    Fresh diagnosis session when stall detected (§12).

    "On stall, start a fresh diagnosis session, generate competing
    hypotheses, rank with evidence, execute the smallest reversible
    experiment, and stop if evidence does not improve."
    """

    def __init__(self, gateway=None):
        """
        Initialize stall diagnosis.

        Args:
            gateway: model gateway for LLM diagnosis
        """
        self.gateway = gateway
        self.hypotheses: List[Dict[str, str]] = []
        self.experiments: List[Dict[str, Any]] = []

    def generate_hypotheses(
        self,
        failure_category: str,
        logs: str,
        prior_fixes: List[str],
    ) -> List[Dict[str, str]]:
        """
        Generate competing hypotheses for stalled failure (§12).

        Args:
            failure_category: what's failing
            logs: error logs
            prior_fixes: prior attempts

        Returns:
            list of hypothesis dicts (root_cause, explanation)
        """
        # MVP: heuristic hypothesis generation
        hypotheses = []

        # Hypothesis 1: Root cause in prior implementation
        hypotheses.append({
            "id": "H1",
            "root_cause": "Prior implementation incomplete",
            "explanation": "Fix may need broader scope",
            "evidence_needed": "Code review of prior attempt",
        })

        # Hypothesis 2: Test issue (not implementation)
        hypotheses.append({
            "id": "H2",
            "root_cause": "Test expectations mismatch",
            "explanation": "Spec may be unclear",
            "evidence_needed": "Requirement re-review",
        })

        # Hypothesis 3: Environmental/external factor
        hypotheses.append({
            "id": "H3",
            "root_cause": "External dependency issue",
            "explanation": "Problem not in code",
            "evidence_needed": "Dependency check",
        })

        self.hypotheses = hypotheses
        return hypotheses

    def rank_hypotheses(self, hypotheses: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Rank hypotheses by evidence (§12).

        Args:
            hypotheses: list of hypotheses

        Returns:
            ranked list with confidence scores
        """
        ranked = []
        for i, h in enumerate(hypotheses):
            ranked.append({
                **h,
                "rank": i + 1,
                "confidence": max(0.3, 1.0 - (i * 0.2)),
                "reversibility": "reversible" if i < 2 else "requires_approval",
            })
        return ranked

    def execute_smallest_experiment(self, hypothesis: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute smallest reversible experiment to test hypothesis (§12).

        Args:
            hypothesis: hypothesis to test

        Returns:
            experiment result (success, evidence collected)
        """
        # MVP: record experiment, would return results
        experiment = {
            "hypothesis_id": hypothesis.get("id"),
            "experiment": f"Test {hypothesis.get('root_cause')}",
            "expected_outcome": "Better understanding of root cause",
            "reversible": True,
            "status": "planned",
        }
        self.experiments.append(experiment)
        return experiment
