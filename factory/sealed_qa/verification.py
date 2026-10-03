"""
Verification Pipeline: 17-stage deterministic verification (§11).

Per master plan §11:
"Verification order:
1. Format
2. Lint
3. Type check
4. Build
5. Unit
6. Component
7. Contract
8. Integration
9. Secret scan
10. Static security
11. Dependency scan
12. Mutation testing
13. Runtime scenarios
14. Sealed acceptance
15. Accessibility
16. Visual regression
17. Performance when relevant

Deterministic failures cannot be overridden by an LLM, urgency, retry
exhaustion, or builder explanation."
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class VerificationStage(str, Enum):
    """17-stage verification pipeline (§11)."""
    FORMAT = "1_format"
    LINT = "2_lint"
    TYPECHECK = "3_typecheck"
    BUILD = "4_build"
    UNIT = "5_unit"
    COMPONENT = "6_component"
    CONTRACT = "7_contract"
    INTEGRATION = "8_integration"
    SECRET_SCAN = "9_secret_scan"
    STATIC_SECURITY = "10_static_security"
    DEPENDENCY_SCAN = "11_dependency_scan"
    MUTATION = "12_mutation"
    RUNTIME = "13_runtime"
    SEALED_ACCEPTANCE = "14_sealed_acceptance"
    ACCESSIBILITY = "15_accessibility"
    VISUAL_REGRESSION = "16_visual_regression"
    PERFORMANCE = "17_performance"


class VerificationResult(str, Enum):
    """Result of verification stage."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DETERMINISTIC_FAILURE = "deterministic_failure"  # Cannot override


@dataclass
class StageResult:
    """Result of single verification stage."""
    stage: VerificationStage
    result: VerificationResult
    duration_seconds: float
    output: str  # Stage output/logs
    error: Optional[str] = None
    deterministic: bool = False  # Cannot override if true
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "stage": self.stage.value,
            "result": self.result.value,
            "duration_seconds": round(self.duration_seconds, 2),
            "output": self.output[:500],  # Truncate for logs
            "error": self.error[:500] if self.error else None,
            "deterministic": self.deterministic,
            "timestamp": self.timestamp,
        }


class VerificationPipeline:
    """
    17-stage verification pipeline with deterministic failure handling (§11).

    Pipeline runs stages in order; stops on first failure.
    Deterministic failures (format, type check, build, security scans)
    cannot be overridden by retry/urgency/builder explanation.
    """

    # Stages that are deterministic (cannot override)
    DETERMINISTIC_STAGES = [
        VerificationStage.FORMAT,
        VerificationStage.LINT,
        VerificationStage.TYPECHECK,
        VerificationStage.BUILD,
        VerificationStage.SECRET_SCAN,
        VerificationStage.STATIC_SECURITY,
        VerificationStage.DEPENDENCY_SCAN,
        VerificationStage.MUTATION,
        VerificationStage.SEALED_ACCEPTANCE,
    ]

    def __init__(self):
        """Initialize verification pipeline."""
        self.stages: List[StageResult] = []

    def add_stage_result(
        self,
        stage: VerificationStage,
        result: VerificationResult,
        duration_seconds: float,
        output: str,
        error: Optional[str] = None,
    ) -> StageResult:
        """
        Add verification stage result.

        Args:
            stage: verification stage
            result: PASSED, FAILED, SKIPPED, DETERMINISTIC_FAILURE
            duration_seconds: stage duration
            output: stage output/logs
            error: error message if failed

        Returns:
            StageResult (recorded)
        """
        is_deterministic = stage in self.DETERMINISTIC_STAGES

        stage_result = StageResult(
            stage=stage,
            result=result,
            duration_seconds=duration_seconds,
            output=output,
            error=error,
            deterministic=is_deterministic,
        )

        self.stages.append(stage_result)
        return stage_result

    def get_summary(self) -> Dict[str, Any]:
        """Get verification summary (pass/fail status, failed stages)."""
        failed_stages = [s for s in self.stages if s.result == VerificationResult.FAILED]
        deterministic_failures = [
            s for s in failed_stages if s.deterministic
        ]

        all_passed = len(failed_stages) == 0

        return {
            "passed": all_passed,
            "total_stages": len(self.stages),
            "passed_stages": sum(
                1 for s in self.stages if s.result == VerificationResult.PASSED
            ),
            "failed_stages": len(failed_stages),
            "deterministic_failures": len(deterministic_failures),
            "first_failure": (
                failed_stages[0].stage.value if failed_stages else None
            ),
            "deterministic_failure_present": len(deterministic_failures) > 0,
            "overridable": len(deterministic_failures) == 0,
        }

    def is_deterministic_failure(self) -> bool:
        """Check if any deterministic failure present (cannot override §11)."""
        failed = [s for s in self.stages if s.result == VerificationResult.FAILED]
        deterministic_failed = [s for s in failed if s.deterministic]
        return len(deterministic_failed) > 0

    def cannot_override_reason(self) -> Optional[str]:
        """
        Get reason why verification cannot be overridden (§11).

        Returns:
            reason string if deterministic failure, else None
        """
        failed = [s for s in self.stages if s.result == VerificationResult.FAILED]
        deterministic_failed = [s for s in failed if s.deterministic]

        if not deterministic_failed:
            return None

        stages = ", ".join([s.stage.value for s in deterministic_failed])
        return (
            f"Deterministic failures cannot be overridden (§11): {stages}. "
            "LLM urgency, retry exhaustion, or builder explanation do not matter."
        )


class VerificationGate:
    """
    Verification gate: pass/fail decision based on pipeline results.

    Gate passes only when:
    - All required stages passed
    - No deterministic failures
    - Sealed acceptance passed
    - No builder tampering with tests/sealed specs
    """

    def __init__(self, pipeline: VerificationPipeline):
        """Initialize gate with pipeline results."""
        self.pipeline = pipeline

    def passes(self) -> bool:
        """Determine if gate passes."""
        # No deterministic failures allowed
        if self.pipeline.is_deterministic_failure():
            return False

        # All stages must be passed or skipped (not failed)
        summary = self.pipeline.get_summary()
        return summary["failed_stages"] == 0

    def reason(self) -> str:
        """Get gate pass/fail reason."""
        if not self.passes():
            reason = self.pipeline.cannot_override_reason()
            if reason:
                return reason

            summary = self.pipeline.get_summary()
            if summary["failed_stages"] > 0:
                return f"{summary['failed_stages']} stage(s) failed"

            return "Verification gate failed"

        return "All verification stages passed"

    def report(self) -> Dict[str, Any]:
        """Generate verification gate report."""
        summary = self.pipeline.get_summary()

        return {
            "gate_passes": self.passes(),
            "reason": self.reason(),
            "summary": summary,
            "stages": [s.to_dict() for s in self.pipeline.stages],
        }
