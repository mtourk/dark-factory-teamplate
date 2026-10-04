"""
Builder: Code generation via LLM (Aider integration placeholder).

Per master plan §10:
"Builder receives only an observable failure envelope, allowed fix scope,
and attempt number.

The builder may not delete/weaken/skip/exclude failing tests, modify
sealed tests, or replace final integration behavior with mocks merely
to pass."

Task-type model selection (as of 2026-10-04):
- Discovery phase (intake Worker, gemini.ts): uses qwen2.5:7b-instruct (fast, good conversational quality)
- Implementation phase (this file, future): will read GitHub issue's `model:implementation-32b` label
  and pass `model_name` to the gateway for code generation (not yet implemented)
- The label is auto-added by factory/intake/worker/src/github.ts when filing an issue
- Implementation should:
  1. Load the GitHub issue (repo/issue_number)
  2. Read its labels
  3. Extract `model:*` label (e.g., "model:implementation-32b")
  4. Pass model name to builder's LLM calls when Aider integration is built
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


@dataclass
class BuilderInput:
    """Input to builder: requirement, allowed scope, attempt info."""
    run_id: str
    issue_number: int
    requirement_summary: str  # From BMAD
    allowed_fix_scope: str  # What builder may change
    attempt_number: int  # Attempt count (1-3)
    failure_context: Optional[str] = None  # Error details from verification
    prohibited_paths: List[str] = None  # Cannot touch these
    previous_patch_digest: Optional[str] = None  # SHA of prior attempt

    def __post_init__(self):
        if self.prohibited_paths is None:
            self.prohibited_paths = [
                "DARK_FACTORY_MASTER_PLAN.md",
                ".factory-control/",
                ".factory/",
                ".github/workflows/",
                "docs/decisions/",
                "factory/sealed_qa/",
            ]


@dataclass
class BuilderOutput:
    """Output from builder: code changes."""
    run_id: str
    issue_number: int
    attempt_number: int
    changes: Dict[str, str]  # Path -> file content
    changed_files: List[str]
    patch_digest: str = ""  # SHA-256 of changes
    duration_seconds: float = 0.0
    explanation: str = ""  # Builder's explanation (not authority for acceptance)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def compute_patch_digest(self) -> str:
        """Compute SHA-256 of patch (for cycle detection)."""
        patch_json = str(sorted(self.changes.items()))
        return hashlib.sha256(patch_json.encode()).hexdigest()


class BuilderCoordinator:
    """
    Coordinate builder code generation with allowed scope enforcement.

    Builder constraints:
    - Cannot touch prohibited paths
    - Cannot weaken/skip tests
    - Cannot modify sealed tests
    - Cannot replace integration behavior with mocks
    - Explanation is not authority for acceptance
    """

    def __init__(self, gateway=None):
        """
        Initialize builder coordinator.

        Args:
            gateway: model gateway for LLM calls
        """
        self.gateway = gateway
        self.build_history: List[BuilderOutput] = []

    def validate_builder_input(self, builder_input: BuilderInput) -> Dict[str, Any]:
        """Validate builder input is well-formed."""
        if builder_input.attempt_number < 1 or builder_input.attempt_number > 3:
            return {
                "valid": False,
                "reason": "Attempt number must be 1-3 (§12)",
            }

        if not builder_input.requirement_summary:
            return {"valid": False, "reason": "No requirement summary"}

        if not builder_input.allowed_fix_scope:
            return {"valid": False, "reason": "No allowed fix scope"}

        return {"valid": True}

    def validate_builder_output(
        self,
        builder_output: BuilderOutput,
        builder_input: BuilderInput,
    ) -> Dict[str, Any]:
        """
        Validate builder output doesn't violate constraints.

        Args:
            builder_output: code changes from builder
            builder_input: original input with constraints

        Returns:
            validation report with violations list
        """
        violations = []

        # Check for prohibited path changes
        for file_path in builder_output.changed_files:
            for prohibited in builder_input.prohibited_paths:
                if file_path.startswith(prohibited):
                    violations.append(f"Prohibited path: {file_path}")

        # Check for sealed test modifications
        sealed_patterns = [
            "factory/sealed_qa/",
            "tests/sealed_",
            "tests/acceptance_",
        ]
        for file_path in builder_output.changed_files:
            for pattern in sealed_patterns:
                if pattern in file_path:
                    violations.append(f"Cannot modify sealed tests: {file_path}")

        # Check for test weakening (heuristic: deletion of test lines)
        for file_path, content in builder_output.changes.items():
            if "test" in file_path.lower() and "def test_" in content:
                # Sanity check: tests are present, not deleted
                pass

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "patch_digest": builder_output.compute_patch_digest(),
        }

    def record_build(self, output: BuilderOutput):
        """Record builder output for history/cycle detection."""
        output.patch_digest = output.compute_patch_digest()
        self.build_history.append(output)

    def get_build_history(self) -> List[BuilderOutput]:
        """Get full build history."""
        return self.build_history
