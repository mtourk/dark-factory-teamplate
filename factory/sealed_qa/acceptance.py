"""
Hidden Acceptance Specifications (Sealed QA).

Per master plan §11:
"Create hidden acceptance specifications before implementation. Keep them
out of builder-readable storage. Builder receives only an observable
failure envelope, allowed fix scope, and attempt number.

The builder may not delete/weaken/skip/exclude failing tests, modify
sealed tests, or replace final integration behavior with mocks merely
to pass."
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum


class AcceptanceCritiaType(str, Enum):
    """Type of acceptance criterion."""
    OBSERVABLE = "observable"  # User-visible behavior
    PERFORMANCE = "performance"  # Latency, throughput
    SECURITY = "security"  # Access control, data protection
    RELIABILITY = "reliability"  # Error handling, recovery
    INTEGRATION = "integration"  # Cross-component interaction


@dataclass
class AcceptanceCriterion:
    """Single sealed acceptance criterion."""
    id: str
    criterion_type: AcceptanceCriaType
    description: str  # What must be true
    verification_method: str  # How to test
    observable_only: bool = False  # Can builder see this?
    critical: bool = True  # Failure blocks merge


@dataclass
class SealedSpecification:
    """Hidden acceptance specification (not builder-readable, §11)."""
    issue_number: int
    project_id: str
    run_id: str
    criteria: List[AcceptanceCriterion]
    failure_envelope_allowed: bool = True  # Builder sees only failures, not criteria
    digest: str = ""  # SHA-256 of sealed spec (for integrity/non-tampering)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def compute_digest(self) -> str:
        """Compute SHA-256 digest of spec (immutable reference)."""
        spec_json = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(spec_json.encode()).hexdigest()

    def to_dict_redacted_for_builder(self) -> Dict[str, Any]:
        """Return sealed spec with builder-sensitive info redacted (§11)."""
        # Builder only sees observable criteria counts, not actual criteria
        observable_count = sum(
            1 for c in self.criteria if c.observable_only
        )
        sealed_count = sum(
            1 for c in self.criteria if not c.observable_only
        )

        return {
            "issue_number": self.issue_number,
            "observable_criteria_count": observable_count,
            "sealed_criteria_count": sealed_count,
            "total_criteria": len(self.criteria),
            "message": "Hidden acceptance spec. Builder cannot see criteria.",
        }


class SealedQABroker:
    """
    Manage sealed acceptance specifications and builder access restrictions (§11).

    Sealed specs live in protected storage outside builder's context.
    Builder receives only failure envelope: which test failed, allowed
    fix scope, attempt number.
    """

    def __init__(self, sealed_dir: Path = None):
        """
        Initialize sealed QA broker.

        Args:
            sealed_dir: directory for sealed spec storage (default: C:/Factory/control/sealed)
        """
        if sealed_dir is None:
            sealed_dir = Path("C:/Factory/control/sealed")
        self.sealed_dir = sealed_dir
        self.sealed_dir.mkdir(parents=True, exist_ok=True)

    def store_sealed_spec(self, spec: SealedSpecification) -> Path:
        """
        Store sealed specification in protected location (§11).

        Args:
            spec: sealed specification

        Returns:
            path to stored spec file
        """
        spec.digest = spec.compute_digest()

        spec_path = (
            self.sealed_dir
            / f"sealed-spec-{spec.issue_number}-{spec.digest[:8]}.json"
        )

        spec_json = json.dumps(asdict(spec), indent=2, default=str)
        spec_path.write_text(spec_json)

        return spec_path

    def load_sealed_spec(self, issue_number: int, digest_prefix: str) -> SealedSpecification:
        """
        Load sealed spec from protected storage.

        Args:
            issue_number: GitHub issue number
            digest_prefix: first 8 chars of digest

        Returns:
            sealed specification

        Raises:
            ValueError: if spec not found
        """
        spec_path = (
            self.sealed_dir / f"sealed-spec-{issue_number}-{digest_prefix}.json"
        )

        if not spec_path.exists():
            raise ValueError(f"Sealed spec not found: {spec_path}")

        data = json.loads(spec_path.read_text())

        return SealedSpecification(
            issue_number=data["issue_number"],
            project_id=data["project_id"],
            run_id=data["run_id"],
            criteria=[
                AcceptanceCriterion(
                    id=c["id"],
                    criterion_type=AcceptanceCriaType(c["criterion_type"]),
                    description=c["description"],
                    verification_method=c["verification_method"],
                    observable_only=c.get("observable_only", False),
                    critical=c.get("critical", True),
                )
                for c in data["criteria"]
            ],
            digest=data.get("digest", ""),
            created_at=data.get("created_at", ""),
        )

    def get_builder_failure_envelope(
        self,
        spec: SealedSpecification,
        failed_criterion_id: str,
    ) -> Dict[str, Any]:
        """
        Generate failure envelope for builder (limited visibility, §11).

        Builder sees:
        - Which criterion failed
        - Allowed fix scope (if marked)
        - Attempt number (tracked elsewhere)
        - Error output (logs only, not criteria)

        Builder cannot see:
        - Sealed criterion details
        - Full spec
        - Other criteria

        Args:
            spec: sealed specification
            failed_criterion_id: which criterion failed

        Returns:
            failure envelope (builder-visible only)
        """
        criterion = next(
            (c for c in spec.criteria if c.id == failed_criterion_id),
            None,
        )

        if not criterion:
            return {
                "error": "Unknown criterion",
                "allowed_scope": "Review error logs and fix implementation",
            }

        return {
            "criterion_id": criterion.id,
            "criterion_type": criterion.criterion_type.value,
            "observable": criterion.observable_only,
            "critical": criterion.critical,
            "allowed_scope": (
                "Fix observable behavior"
                if criterion.observable_only
                else "Review error logs; cannot modify sealed tests"
            ),
            "message": "Test failed. See logs for details.",
        }

    def validate_builder_cannot_modify(
        self,
        spec: SealedSpecification,
        changed_files: List[str],
    ) -> Dict[str, Any]:
        """
        Validate builder cannot modify sealed tests (§11).

        Checks:
        - No test files modified
        - No sealed spec files touched
        - No verification framework modified

        Args:
            spec: sealed specification
            changed_files: list of files builder changed

        Returns:
            validation report
        """
        violations = []

        sealed_paths = [
            "factory/sealed_qa/",
            ".factory-control/sealed/",
            "tests/sealed_",
            "tests/acceptance_",
        ]

        for file_path in changed_files:
            for sealed_path in sealed_paths:
                if sealed_path in file_path:
                    violations.append(file_path)

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "message": (
                "Builder may not modify sealed tests or verification framework (§11)"
            ),
        }
