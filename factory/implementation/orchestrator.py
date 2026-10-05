"""
Implementation Orchestrator: Builder → Verify → Repair cycle.

Orchestrates the full implementation loop:
1. Builder generates code
2. Verification runs (17 stages)
3. If failure: Repairer attempts fix (max 3 cycles)
4. Stall detection and diagnosis
5. Record evidence

`run_full_cycle()` is the end-to-end entrypoint: given a `factory:ready`
issue number, it drives claim-free build → apply → verify → (repair)*
→ complete/stop, calling back into `BuilderCoordinator.build_from_issue()`
for each attempt (including repair attempts, which are just another build
call with `failure_context` set) and `VerificationRunner` for real stage
execution. The lower-level `start_implementation`/`complete_build_phase`/
`complete_verification_phase` methods below remain usable standalone (the
existing test suite drives them manually), and `run_full_cycle` is built
on top of them rather than duplicating their logic.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

from factory.implementation.builder import BuilderCoordinator, BuilderOutput, BuilderInput
from factory.implementation.patch_apply import apply_changes
from factory.implementation.repair import (
    RepairCycleTracker,
    RepairOutput,
    StallDiagnosisSession,
    StopCondition,
)
from factory.sealed_qa.runner import StageCommand, VerificationRunner
from factory.sealed_qa.verification import VerificationPipeline, VerificationGate


class ImplementationPhase(str, Enum):
    """Phases of implementation lifecycle."""
    BUILDING = "building"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    STALL_DIAGNOSIS = "stall_diagnosis"
    COMPLETE = "complete"
    STOPPED = "stopped"


@dataclass
class ImplementationRun:
    """Complete implementation run (build + verify + repair cycles)."""
    run_id: str
    issue_number: int
    project_id: str
    phase: ImplementationPhase
    attempt_number: int = 1
    builder_output: Optional[BuilderOutput] = None
    verification_pipeline: Optional[VerificationPipeline] = None
    verification_gate: Optional[VerificationGate] = None
    repair_outputs: List[Any] = None
    stop_condition: Optional[StopCondition] = None
    stall_diagnosis: Optional[Dict[str, Any]] = None
    started_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()
        if self.repair_outputs is None:
            self.repair_outputs = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "run_id": self.run_id,
            "issue_number": self.issue_number,
            "project_id": self.project_id,
            "phase": self.phase.value,
            "attempt_number": self.attempt_number,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stop_condition": self.stop_condition.value if self.stop_condition else None,
        }


class ImplementationOrchestrator:
    """
    Orchestrate implementation lifecycle: build → verify → repair → complete.

    Coordinates:
    - Builder code generation
    - Verification pipeline (17 stages)
    - Bounded repair (max 3 cycles)
    - Stall detection and diagnosis
    - Stop conditions
    """

    def __init__(self, builder_coordinator, gateway=None):
        """
        Initialize orchestrator.

        Args:
            builder_coordinator: BuilderCoordinator instance
            gateway: model gateway for LLM calls
        """
        self.builder_coordinator = builder_coordinator
        self.gateway = gateway
        self.runs: Dict[str, ImplementationRun] = {}

    def start_implementation(
        self,
        run_id: str,
        issue_number: int,
        project_id: str,
        requirement_summary: str,
        allowed_fix_scope: str,
    ) -> ImplementationRun:
        """
        Start new implementation run.

        Args:
            run_id: factory run ID
            issue_number: GitHub issue
            project_id: project ID
            requirement_summary: BMAD output
            allowed_fix_scope: what builder may change

        Returns:
            ImplementationRun (in BUILDING phase)
        """
        run = ImplementationRun(
            run_id=run_id,
            issue_number=issue_number,
            project_id=project_id,
            phase=ImplementationPhase.BUILDING,
            attempt_number=1,
        )

        self.runs[run_id] = run
        return run

    def complete_build_phase(
        self,
        run: ImplementationRun,
        builder_output: BuilderOutput,
    ) -> Dict[str, Any]:
        """
        Complete build phase, transition to verification.

        Args:
            run: implementation run
            builder_output: code from builder

        Returns:
            validation report
        """
        # Validate builder output
        builder_input = BuilderInput(
            run_id=run.run_id,
            issue_number=run.issue_number,
            requirement_summary="",
            allowed_fix_scope="",
            attempt_number=run.attempt_number,
        )

        validation = self.builder_coordinator.validate_builder_output(
            builder_output, builder_input
        )

        if validation["valid"]:
            run.builder_output = builder_output
            run.phase = ImplementationPhase.VERIFYING
            self.builder_coordinator.record_build(builder_output)

        return validation

    def complete_verification_phase(
        self,
        run: ImplementationRun,
        pipeline: VerificationPipeline,
    ) -> Dict[str, Any]:
        """
        Complete verification phase, determine next step.

        Args:
            run: implementation run
            pipeline: verification pipeline with results

        Returns:
            gate report (passed/failed, reason)
        """
        gate = VerificationGate(pipeline)
        run.verification_pipeline = pipeline
        run.verification_gate = gate

        if gate.passes():
            # Verification passed - implementation complete
            run.phase = ImplementationPhase.COMPLETE
            run.completed_at = datetime.utcnow().isoformat()
        else:
            # Verification failed - move to repair
            run.phase = ImplementationPhase.REPAIRING

        return gate.report()

    def start_repair_cycle(self, run: ImplementationRun) -> RepairCycleTracker:
        """
        Start repair cycle (max 3).

        Args:
            run: implementation run (in REPAIRING phase)

        Returns:
            RepairCycleTracker for this cycle
        """
        tracker = RepairCycleTracker()
        return tracker

    def check_stop_conditions(
        self,
        run: ImplementationRun,
        tracker: RepairCycleTracker,
    ) -> Optional[StopCondition]:
        """
        Check stop conditions (§12).

        Args:
            run: implementation run
            tracker: repair cycle tracker

        Returns:
            StopCondition if should stop, else None
        """
        if len(tracker.cycles) >= RepairCycleTracker.MAX_REPAIR_CYCLES:
            return StopCondition.MAX_ATTEMPTS_EXHAUSTED

        if tracker.is_stall_detected():
            return StopCondition.STALL_DETECTED

        return None

    def start_stall_diagnosis(self, run: ImplementationRun) -> StallDiagnosisSession:
        """
        Start stall diagnosis session (§12).

        Args:
            run: implementation run (stalled)

        Returns:
            StallDiagnosisSession for hypothesis generation/testing
        """
        run.phase = ImplementationPhase.STALL_DIAGNOSIS
        session = StallDiagnosisSession(gateway=self.gateway)
        return session

    def run_full_cycle(
        self,
        run_id: str,
        github_adapter,  # factory.backlog.github_adapter.GitHubAdapter
        issue_number: int,
        project_id: str,
        repo_root: Path,
        allowed_fix_scope: str = "",
        stage_commands: Optional[List[StageCommand]] = None,
    ) -> ImplementationRun:
        """
        Drive the full claim → build → apply → verify → repair → complete/stop
        loop for one issue, end to end.

        Each attempt (including repair attempts) calls
        `BuilderCoordinator.build_from_issue()` with the growing
        `failure_context`, so the model doing the repair is the same model
        that did the original build, now told what failed last time — there
        is no separate "repairer" LLM call in this codebase yet.

        Args:
            run_id: factory run ID
            github_adapter: configured GitHubAdapter (owner/repo already set)
            issue_number: the `factory:ready` issue to implement
            project_id: project ID (for the run record)
            repo_root: working tree to write changes into and run
                verification commands against
            allowed_fix_scope: what the builder may change
            stage_commands: verification stages to actually run (see
                `factory.sealed_qa.runner.VerificationRunner`); stages with
                no configured command are not run at all, not assumed to pass

        Returns:
            The finished ImplementationRun, in COMPLETE or STOPPED phase.
        """
        run = self.start_implementation(
            run_id=run_id,
            issue_number=issue_number,
            project_id=project_id,
            requirement_summary="",  # the issue itself is the source of truth
            allowed_fix_scope=allowed_fix_scope,
        )

        tracker = RepairCycleTracker()
        failure_context: Optional[str] = None

        while True:
            builder_output = self.builder_coordinator.build_from_issue(
                run_id=run_id,
                github_adapter=github_adapter,
                issue_number=issue_number,
                attempt_number=run.attempt_number,
                allowed_fix_scope=allowed_fix_scope,
                failure_context=failure_context,
            )

            build_validation = self.complete_build_phase(run, builder_output)
            if not build_validation["valid"]:
                # §10: a prohibited/sealed-path violation isn't something a
                # retry can fix — stop now rather than spend more attempts.
                self.finalize_run(run, ImplementationPhase.STOPPED, StopCondition.PROTECTED_PATH_TOUCHED)
                return run

            apply_result = apply_changes(
                repo_root, builder_output.changes, builder_output.changed_files
            )
            if not apply_result.ok:
                self.finalize_run(run, ImplementationPhase.STOPPED, StopCondition.RESOURCE_EXHAUSTED)
                return run

            runner = VerificationRunner(repo_root=repo_root, stage_commands=stage_commands or [])
            pipeline = runner.run()
            gate_report = self.complete_verification_phase(run, pipeline)

            if gate_report["gate_passes"]:
                return run  # complete_verification_phase already set phase=COMPLETE

            # Verification failed: record this attempt as a repair cycle,
            # check §12 stop conditions, and either retry or stop.
            failure_category = gate_report["summary"]["first_failure"] or "unknown"
            tracker.add_failure(failure_category)

            repair_output = RepairOutput(
                run_id=run_id,
                issue_number=issue_number,
                attempt_number=run.attempt_number,
                diagnosis=gate_report["reason"],
                fix_explanation=builder_output.explanation,
                hypothesis="",
                changes=builder_output.changes,
                changed_files=builder_output.changed_files,
            )
            tracker.add_cycle(repair_output)
            run.repair_outputs.append(repair_output)

            stop_condition = tracker.check_stop_conditions(repair_output)
            if stop_condition is not None:
                if stop_condition == StopCondition.STALL_DETECTED:
                    session = self.start_stall_diagnosis(run)
                    hypotheses = session.generate_hypotheses(
                        failure_category=failure_category,
                        logs=gate_report["reason"],
                        prior_fixes=[r.fix_explanation for r in run.repair_outputs],
                    )
                    run.stall_diagnosis = {
                        "hypotheses": session.rank_hypotheses(hypotheses),
                    }
                self.finalize_run(run, ImplementationPhase.STOPPED, stop_condition)
                return run

            failure_context = self._summarize_failure_for_builder(gate_report)
            run.attempt_number += 1
            run.phase = ImplementationPhase.BUILDING

    @staticmethod
    def _summarize_failure_for_builder(gate_report: Dict[str, Any]) -> str:
        """Build the short failure_context string fed to the next build_from_issue call."""
        summary = gate_report["summary"]
        failing_stage = summary.get("first_failure") or "unknown stage"
        failed = [
            s for s in gate_report["stages"]
            if s["stage"] == failing_stage
        ]
        detail = failed[0] if failed else {}
        error = detail.get("error") or detail.get("output") or ""
        return f"Stage '{failing_stage}' failed: {gate_report['reason']}. Details: {error[:500]}"

    def finalize_run(
        self,
        run: ImplementationRun,
        final_phase: ImplementationPhase,
        stop_condition: Optional[StopCondition] = None,
    ):
        """
        Finalize implementation run.

        Args:
            run: implementation run
            final_phase: COMPLETE or STOPPED
            stop_condition: reason for stopping (if STOPPED)
        """
        run.phase = final_phase
        run.stop_condition = stop_condition
        run.completed_at = datetime.utcnow().isoformat()

    def get_run(self, run_id: str) -> Optional[ImplementationRun]:
        """Get implementation run by ID."""
        return self.runs.get(run_id)

    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """Get summary of implementation run."""
        run = self.get_run(run_id)
        if not run:
            return {"error": "Run not found"}

        return {
            "run_id": run.run_id,
            "issue_number": run.issue_number,
            "phase": run.phase.value,
            "attempt_number": run.attempt_number,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "stop_condition": run.stop_condition.value if run.stop_condition else None,
        }
