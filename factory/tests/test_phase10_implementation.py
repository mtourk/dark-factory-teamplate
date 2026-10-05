"""
Phase 10: Implementation, Verification, and Repair tests.

Tests for:
1. Builder input validation and constraints
2. Builder output validation (no prohibited paths, sealed tests)
3. Builder cannot weaken/mock tests
4. Build history and patch digest tracking
5. Verification pipeline integration
6. Verification gate decision (pass/fail)
7. Repair cycle tracking (max 3)
8. Stall detection (same failure twice)
9. Stop conditions (max cycles, stall, business meaning, protected paths, etc.)
10. Stall diagnosis session (hypothesis generation, ranking, experiments)
11. Implementation orchestrator (build → verify → repair → complete)
12. Lifecycle phases (building, verifying, repairing, stall_diagnosis, complete, stopped)
"""

import sys
from unittest.mock import MagicMock

import pytest
from datetime import datetime
from pathlib import Path

from factory.implementation.builder import (
    BuilderInput,
    BuilderOutput,
    BuilderCoordinator,
)
from factory.implementation.repair import (
    RepairInput,
    RepairOutput,
    RepairCycleTracker,
    StopCondition,
    StallDiagnosisSession,
)
from factory.implementation.orchestrator import (
    ImplementationPhase,
    ImplementationRun,
    ImplementationOrchestrator,
)
from factory.sealed_qa.runner import StageCommand
from factory.sealed_qa.verification import (
    VerificationStage,
    VerificationResult,
    VerificationPipeline,
    VerificationGate,
)


# ============================================================================
# Builder Input/Output Tests
# ============================================================================

class TestBuilderInput:
    """Test builder input structure and constraints."""

    def test_builder_input_creation(self):
        """Builder input created with requirement and scope."""
        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=42,
            requirement_summary="User can search companies",
            allowed_fix_scope="src/search/ module",
            attempt_number=1,
        )

        assert builder_input.run_id == "RUN-001"
        assert builder_input.attempt_number == 1
        assert len(builder_input.prohibited_paths) > 0

    def test_builder_output_creation(self):
        """Builder output created with code changes."""
        builder_output = BuilderOutput(
            run_id="RUN-001",
            issue_number=42,
            attempt_number=1,
            changes={"src/search.py": "def search(): pass"},
            changed_files=["src/search.py"],
        )

        assert builder_output.issue_number == 42
        assert len(builder_output.changed_files) == 1

    def test_builder_output_patch_digest(self):
        """Patch digest computed deterministically."""
        output1 = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={"a.py": "code1"},
            changed_files=["a.py"],
        )

        output2 = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={"a.py": "code1"},
            changed_files=["a.py"],
        )

        digest1 = output1.compute_patch_digest()
        digest2 = output2.compute_patch_digest()

        assert digest1 == digest2  # Deterministic


# ============================================================================
# Builder Coordinator Tests
# ============================================================================

class TestBuilderCoordinator:
    """Test builder output validation and constraints."""

    def test_builder_coordinator_initialization(self):
        """Builder coordinator initializes."""
        coordinator = BuilderCoordinator()
        assert coordinator.build_history == []

    def test_validate_builder_input_valid(self):
        """Valid builder input passes validation."""
        coordinator = BuilderCoordinator()

        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=1,
            requirement_summary="Test",
            allowed_fix_scope="src/",
            attempt_number=1,
        )

        result = coordinator.validate_builder_input(builder_input)
        assert result["valid"] is True

    def test_validate_builder_input_bad_attempt(self):
        """Invalid attempt number rejected."""
        coordinator = BuilderCoordinator()

        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=1,
            requirement_summary="Test",
            allowed_fix_scope="src/",
            attempt_number=5,  # Out of range
        )

        result = coordinator.validate_builder_input(builder_input)
        assert result["valid"] is False

    def test_validate_builder_output_no_violations(self):
        """Valid builder output passes."""
        coordinator = BuilderCoordinator()

        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=1,
            requirement_summary="Test",
            allowed_fix_scope="src/",
            attempt_number=1,
        )

        builder_output = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={"src/main.py": "code"},
            changed_files=["src/main.py"],
        )

        result = coordinator.validate_builder_output(builder_output, builder_input)
        assert result["valid"] is True

    def test_validate_builder_output_protected_path(self):
        """Builder cannot change protected paths."""
        coordinator = BuilderCoordinator()

        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=1,
            requirement_summary="Test",
            allowed_fix_scope="src/",
            attempt_number=1,
        )

        builder_output = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={
                "src/main.py": "code",
                "DARK_FACTORY_MASTER_PLAN.md": "modified",  # Violation!
            },
            changed_files=["src/main.py", "DARK_FACTORY_MASTER_PLAN.md"],
        )

        result = coordinator.validate_builder_output(builder_output, builder_input)
        assert result["valid"] is False
        assert len(result["violations"]) > 0

    def test_validate_builder_output_sealed_tests(self):
        """Builder cannot modify sealed tests."""
        coordinator = BuilderCoordinator()

        builder_input = BuilderInput(
            run_id="RUN-001",
            issue_number=1,
            requirement_summary="Test",
            allowed_fix_scope="src/",
            attempt_number=1,
        )

        builder_output = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={
                "src/main.py": "code",
                "factory/sealed_qa/acceptance.py": "modified",  # Violation!
            },
            changed_files=["src/main.py", "factory/sealed_qa/acceptance.py"],
        )

        result = coordinator.validate_builder_output(builder_output, builder_input)
        assert result["valid"] is False


# ============================================================================
# Repair Cycle Tests
# ============================================================================

class TestRepairCycleTracker:
    """Test repair cycles and stall detection."""

    def test_repair_input_creation(self):
        """Repair input created with failure context."""
        repair_input = RepairInput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            failure_category="unit_test",
            failure_logs="Test failed: expected 5, got 3",
            expected_behavior="Return search count",
            actual_behavior="Return wrong count",
            allowed_fix_scope="src/search.py",
            prohibited_paths=["factory/", "tests/sealed_"],
        )

        assert repair_input.failure_category == "unit_test"

    def test_repair_output_creation(self):
        """Repair output created with diagnosis and fix."""
        repair_output = RepairOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            diagnosis="Off-by-one error in count loop",
            fix_explanation="Changed range(n) to range(n+1)",
            hypothesis="Loop boundary incorrect",
            changes={"src/search.py": "updated code"},
            changed_files=["src/search.py"],
        )

        assert repair_output.diagnosis is not None

    def test_repair_cycle_tracker_initialization(self):
        """Repair tracker initializes with max cycles."""
        tracker = RepairCycleTracker()
        assert tracker.MAX_REPAIR_CYCLES == 3
        assert len(tracker.cycles) == 0

    def test_repair_cycle_tracking(self):
        """Repair cycles are tracked."""
        tracker = RepairCycleTracker()

        output1 = RepairOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            diagnosis="First attempt",
            fix_explanation="Try fix 1",
            hypothesis="Root cause 1",
            changes={"a.py": "fix1"},
            changed_files=["a.py"],
        )

        tracker.add_cycle(output1)
        assert len(tracker.cycles) == 1

    def test_stall_detection_same_failure_twice(self):
        """Stall detected when same failure repeats."""
        tracker = RepairCycleTracker()

        # Add two identical failures
        tracker.add_failure("unit_test")
        tracker.add_failure("unit_test")

        # Add identical patches
        output1 = RepairOutput(
            run_id="RUN",
            issue_number=1,
            attempt_number=1,
            diagnosis="d1",
            fix_explanation="f1",
            hypothesis="h1",
            changes={"a.py": "code"},
            changed_files=["a.py"],
        )
        output1.compute_patch_digest()

        output2 = RepairOutput(
            run_id="RUN",
            issue_number=1,
            attempt_number=2,
            diagnosis="d2",
            fix_explanation="f2",
            hypothesis="h2",
            changes={"a.py": "code"},  # Same code
            changed_files=["a.py"],
        )
        output2.compute_patch_digest()

        tracker.add_cycle(output1)
        tracker.add_cycle(output2)

        assert tracker.is_stall_detected() is True

    def test_stall_not_detected_different_fixes(self):
        """Stall not detected if fixes differ."""
        tracker = RepairCycleTracker()

        tracker.add_failure("unit_test")
        tracker.add_failure("unit_test")

        output1 = RepairOutput(
            run_id="RUN",
            issue_number=1,
            attempt_number=1,
            diagnosis="d1",
            fix_explanation="f1",
            hypothesis="h1",
            changes={"a.py": "code1"},
            changed_files=["a.py"],
        )
        output1.compute_patch_digest()

        output2 = RepairOutput(
            run_id="RUN",
            issue_number=1,
            attempt_number=2,
            diagnosis="d2",
            fix_explanation="f2",
            hypothesis="h2",
            changes={"a.py": "code2"},  # Different
            changed_files=["a.py"],
        )
        output2.compute_patch_digest()

        tracker.add_cycle(output1)
        tracker.add_cycle(output2)

        assert tracker.is_stall_detected() is False

    def test_stop_condition_max_attempts(self):
        """Stop condition triggered at max cycles."""
        tracker = RepairCycleTracker()

        for i in range(3):
            output = RepairOutput(
                run_id="RUN",
                issue_number=1,
                attempt_number=i + 1,
                diagnosis="d",
                fix_explanation="f",
                hypothesis="h",
                changes={f"a{i}.py": "code"},
                changed_files=[f"a{i}.py"],
            )
            tracker.add_cycle(output)

        # Should trigger MAX_ATTEMPTS_EXHAUSTED
        stop_cond = tracker.check_stop_conditions(None)
        assert stop_cond == StopCondition.MAX_ATTEMPTS_EXHAUSTED


# ============================================================================
# Stall Diagnosis Tests
# ============================================================================

class TestStallDiagnosis:
    """Test stall diagnosis session."""

    def test_stall_diagnosis_initialization(self):
        """Stall diagnosis session initializes."""
        session = StallDiagnosisSession()
        assert len(session.hypotheses) == 0

    def test_generate_hypotheses(self):
        """Hypotheses generated for stalled failure."""
        session = StallDiagnosisSession()

        hypotheses = session.generate_hypotheses(
            failure_category="unit_test",
            logs="Test failed",
            prior_fixes=["fix1", "fix2"],
        )

        assert len(hypotheses) >= 3
        assert all("root_cause" in h for h in hypotheses)

    def test_rank_hypotheses(self):
        """Hypotheses ranked by confidence."""
        session = StallDiagnosisSession()

        hypotheses = [
            {"id": "H1", "root_cause": "Cause 1"},
            {"id": "H2", "root_cause": "Cause 2"},
        ]

        ranked = session.rank_hypotheses(hypotheses)

        assert len(ranked) == 2
        assert all("rank" in h for h in ranked)
        assert all("confidence" in h for h in ranked)
        assert ranked[0]["confidence"] > ranked[1]["confidence"]

    def test_execute_smallest_experiment(self):
        """Smallest experiment executed for hypothesis testing."""
        session = StallDiagnosisSession()

        hypothesis = {"id": "H1", "root_cause": "Test issue"}

        experiment = session.execute_smallest_experiment(hypothesis)

        assert "hypothesis_id" in experiment
        assert experiment["reversible"] is True


# ============================================================================
# Orchestrator Tests
# ============================================================================

class TestImplementationOrchestrator:
    """Test implementation orchestration."""

    def test_implementation_run_lifecycle(self):
        """Implementation run goes through phases."""
        coordinator = BuilderCoordinator()
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.start_implementation(
            run_id="RUN-001",
            issue_number=42,
            project_id="test",
            requirement_summary="Test req",
            allowed_fix_scope="src/",
        )

        assert run.phase == ImplementationPhase.BUILDING
        assert run.attempt_number == 1

    def test_orchestrator_build_to_verify(self):
        """Orchestrator transitions from build to verify phase."""
        coordinator = BuilderCoordinator()
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.start_implementation(
            run_id="RUN-001",
            issue_number=1,
            project_id="test",
            requirement_summary="Test",
            allowed_fix_scope="src/",
        )

        builder_output = BuilderOutput(
            run_id="RUN-001",
            issue_number=1,
            attempt_number=1,
            changes={"src/main.py": "code"},
            changed_files=["src/main.py"],
        )

        validation = orchestrator.complete_build_phase(run, builder_output)

        assert validation["valid"] is True
        assert run.phase == ImplementationPhase.VERIFYING

    def test_orchestrator_verify_pass_completes(self):
        """Orchestrator completes when verification passes."""
        coordinator = BuilderCoordinator()
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.start_implementation(
            run_id="RUN-001",
            issue_number=1,
            project_id="test",
            requirement_summary="Test",
            allowed_fix_scope="src/",
        )
        run.phase = ImplementationPhase.VERIFYING

        # Create passing pipeline
        pipeline = VerificationPipeline()
        for stage in [VerificationStage.FORMAT, VerificationStage.BUILD]:
            pipeline.add_stage_result(
                stage,
                VerificationResult.PASSED,
                1.0,
                "OK",
            )

        report = orchestrator.complete_verification_phase(run, pipeline)

        assert run.phase == ImplementationPhase.COMPLETE
        assert report["gate_passes"] is True

    def test_orchestrator_verify_fail_repairs(self):
        """Orchestrator moves to repair on verification failure."""
        coordinator = BuilderCoordinator()
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.start_implementation(
            run_id="RUN-001",
            issue_number=1,
            project_id="test",
            requirement_summary="Test",
            allowed_fix_scope="src/",
        )
        run.phase = ImplementationPhase.VERIFYING

        # Create failing pipeline
        pipeline = VerificationPipeline()
        pipeline.add_stage_result(
            VerificationStage.FORMAT,
            VerificationResult.FAILED,
            1.0,
            "Failed",
            error="Format error",
        )

        orchestrator.complete_verification_phase(run, pipeline)

        assert run.phase == ImplementationPhase.REPAIRING


# ============================================================================
# Full Loop Tests (run_full_cycle: build → apply → verify → repair → done)
# ============================================================================

def _marker_check_command(marker_path: str) -> list:
    """A real subprocess "stage" that passes iff `marker_path` contains PASS."""
    return [
        sys.executable,
        "-c",
        f"import sys, pathlib; sys.exit(0 if pathlib.Path({marker_path!r}).read_text() == 'PASS' else 1)",
    ]


class TestRunFullCycle:
    """Test ImplementationOrchestrator.run_full_cycle (the end-to-end loop)."""

    def test_completes_on_first_pass(self, tmp_path):
        coordinator = BuilderCoordinator()
        coordinator.build_from_issue = MagicMock(
            return_value=BuilderOutput(
                run_id="RUN-FULL-1",
                issue_number=1,
                attempt_number=1,
                changes={"marker.txt": "PASS"},
                changed_files=["marker.txt"],
                explanation="Writes marker.txt",
            )
        )
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.run_full_cycle(
            run_id="RUN-FULL-1",
            github_adapter=MagicMock(),
            issue_number=1,
            project_id="test",
            repo_root=tmp_path,
            allowed_fix_scope="marker.txt",
            stage_commands=[
                StageCommand(VerificationStage.FORMAT, _marker_check_command("marker.txt")),
            ],
        )

        assert run.phase == ImplementationPhase.COMPLETE
        assert (tmp_path / "marker.txt").read_text() == "PASS"
        coordinator.build_from_issue.assert_called_once()

    def test_stops_on_protected_path(self, tmp_path):
        coordinator = BuilderCoordinator()
        coordinator.build_from_issue = MagicMock(
            return_value=BuilderOutput(
                run_id="RUN-FULL-2",
                issue_number=1,
                attempt_number=1,
                changes={"DARK_FACTORY_MASTER_PLAN.md": "modified"},
                changed_files=["DARK_FACTORY_MASTER_PLAN.md"],
            )
        )
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.run_full_cycle(
            run_id="RUN-FULL-2",
            github_adapter=MagicMock(),
            issue_number=1,
            project_id="test",
            repo_root=tmp_path,
            stage_commands=[],
        )

        assert run.phase == ImplementationPhase.STOPPED
        assert run.stop_condition == StopCondition.PROTECTED_PATH_TOUCHED
        # Builder output was never written to disk.
        assert not (tmp_path / "DARK_FACTORY_MASTER_PLAN.md").exists()

    def test_repairs_then_completes(self, tmp_path):
        """First attempt fails verification; failure_context flows into the
        second build_from_issue call, which fixes it."""
        coordinator = BuilderCoordinator()

        def fake_build(**kwargs):
            attempt = kwargs["attempt_number"]
            content = "FAIL" if attempt == 1 else "PASS"
            if attempt > 1:
                assert kwargs["failure_context"] is not None
            return BuilderOutput(
                run_id="RUN-FULL-3",
                issue_number=1,
                attempt_number=attempt,
                changes={"marker.txt": content},
                changed_files=["marker.txt"],
            )

        coordinator.build_from_issue = MagicMock(side_effect=fake_build)
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.run_full_cycle(
            run_id="RUN-FULL-3",
            github_adapter=MagicMock(),
            issue_number=1,
            project_id="test",
            repo_root=tmp_path,
            allowed_fix_scope="marker.txt",
            stage_commands=[
                StageCommand(VerificationStage.UNIT, _marker_check_command("marker.txt")),
            ],
        )

        assert run.phase == ImplementationPhase.COMPLETE
        assert run.attempt_number == 2
        assert len(run.repair_outputs) == 1
        assert coordinator.build_from_issue.call_count == 2

    def test_stops_on_max_attempts_exhausted(self, tmp_path):
        """Always-failing verification exhausts the 3-attempt budget (§12)."""
        coordinator = BuilderCoordinator()

        def fake_build(**kwargs):
            attempt = kwargs["attempt_number"]
            # Different content each attempt so stall detection (identical
            # patch digest twice) doesn't fire before MAX_ATTEMPTS_EXHAUSTED.
            return BuilderOutput(
                run_id="RUN-FULL-4",
                issue_number=1,
                attempt_number=attempt,
                changes={"marker.txt": f"FAIL-{attempt}"},
                changed_files=["marker.txt"],
            )

        coordinator.build_from_issue = MagicMock(side_effect=fake_build)
        orchestrator = ImplementationOrchestrator(coordinator)

        run = orchestrator.run_full_cycle(
            run_id="RUN-FULL-4",
            github_adapter=MagicMock(),
            issue_number=1,
            project_id="test",
            repo_root=tmp_path,
            allowed_fix_scope="marker.txt",
            stage_commands=[
                StageCommand(VerificationStage.UNIT, _marker_check_command("marker.txt")),
            ],
        )

        assert run.phase == ImplementationPhase.STOPPED
        assert run.stop_condition == StopCondition.MAX_ATTEMPTS_EXHAUSTED
        assert coordinator.build_from_issue.call_count == 3


# ============================================================================
# Phase 10 Gate Test
# ============================================================================

def test_phase10_gate_implementation_verification_repair_operational():
    """
    Phase 10 Gate: Implementation, verification, and repair are operational.

    Verifies:
    - Builder input validation and constraints
    - Builder output validation (no prohibited/sealed paths)
    - Build history and patch digest tracking
    - Verification pipeline integration
    - Repair cycle tracking (max 3)
    - Stall detection (same failure twice)
    - Stop conditions
    - Stall diagnosis (hypotheses, ranking, experiments)
    - Orchestrator lifecycle (build → verify → repair → complete)
    - Phase transitions
    """
    # Builder
    coordinator = BuilderCoordinator()

    builder_input = BuilderInput(
        run_id="RUN-gate001",
        issue_number=42,
        requirement_summary="Search feature",
        allowed_fix_scope="src/",
        attempt_number=1,
    )

    validation = coordinator.validate_builder_input(builder_input)
    assert validation["valid"] is True

    builder_output = BuilderOutput(
        run_id="RUN-gate001",
        issue_number=42,
        attempt_number=1,
        changes={"src/search.py": "def search(): pass"},
        changed_files=["src/search.py"],
    )

    validation = coordinator.validate_builder_output(builder_output, builder_input)
    assert validation["valid"] is True

    digest = builder_output.compute_patch_digest()
    assert len(digest) == 64

    # Verification
    pipeline = VerificationPipeline()
    pipeline.add_stage_result(VerificationStage.FORMAT, VerificationResult.PASSED, 1.0, "OK")
    pipeline.add_stage_result(VerificationStage.BUILD, VerificationResult.PASSED, 2.0, "OK")

    gate = VerificationGate(pipeline)
    assert gate.passes() is True

    # Repair tracking
    tracker = RepairCycleTracker()
    assert tracker.MAX_REPAIR_CYCLES == 3

    tracker.add_failure("test_failure")
    tracker.add_failure("test_failure")

    output1 = RepairOutput(
        run_id="RUN-gate001",
        issue_number=42,
        attempt_number=1,
        diagnosis="First fix",
        fix_explanation="Fixed issue",
        hypothesis="Root cause A",
        changes={"src/search.py": "v2"},
        changed_files=["src/search.py"],
    )

    output1.compute_patch_digest()
    tracker.add_cycle(output1)

    output2 = RepairOutput(
        run_id="RUN-gate001",
        issue_number=42,
        attempt_number=2,
        diagnosis="Second fix",
        fix_explanation="Another fix",
        hypothesis="Root cause B",
        changes={"src/search.py": "v3"},  # Different
        changed_files=["src/search.py"],
    )

    output2.compute_patch_digest()
    tracker.add_cycle(output2)

    assert tracker.is_stall_detected() is False

    # Stall diagnosis
    session = StallDiagnosisSession()
    hypotheses = session.generate_hypotheses("test_failure", "logs", [])
    assert len(hypotheses) > 0

    ranked = session.rank_hypotheses(hypotheses)
    assert all("confidence" in h for h in ranked)

    # Orchestrator
    orchestrator = ImplementationOrchestrator(coordinator)

    run = orchestrator.start_implementation(
        run_id="RUN-gate001",
        issue_number=42,
        project_id="investisor",
        requirement_summary="Search",
        allowed_fix_scope="src/",
    )

    assert run.phase == ImplementationPhase.BUILDING

    validation = orchestrator.complete_build_phase(run, builder_output)
    assert validation["valid"] is True
    assert run.phase == ImplementationPhase.VERIFYING

    report = orchestrator.complete_verification_phase(run, pipeline)
    assert run.phase == ImplementationPhase.COMPLETE

    print("✓ Phase 10 Gate: Implementation, verification, repair operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
