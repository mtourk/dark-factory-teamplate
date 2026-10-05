"""
Tests for factory/sealed_qa/runner.py: the real subprocess-driven
verification stage runner, and the profile-config -> StageCommand adapter
that lets `factory run` be driven entirely by profile data (§11, §17).
"""

import sys

import pytest

from factory.sealed_qa.runner import (
    STAGE_KEY_MAP,
    StageCommand,
    VerificationRunner,
    stage_commands_from_profile_config,
)
from factory.sealed_qa.verification import VerificationResult, VerificationStage

PY = sys.executable


# ============================================================================
# stage_commands_from_profile_config / STAGE_KEY_MAP
# ============================================================================

class TestStageCommandsFromProfileConfig:
    def test_empty_config_returns_no_commands(self):
        assert stage_commands_from_profile_config({}) == []
        assert stage_commands_from_profile_config(None) == []

    def test_maps_known_stage_keys(self):
        commands = stage_commands_from_profile_config(
            {"unit": ["pytest", "-q"], "lint": ["npm", "run", "lint"]}
        )
        by_stage = {c.stage: c.command for c in commands}
        assert by_stage[VerificationStage.UNIT] == ["pytest", "-q"]
        assert by_stage[VerificationStage.LINT] == ["npm", "run", "lint"]

    def test_stage_key_lookup_is_case_insensitive(self):
        commands = stage_commands_from_profile_config({"UNIT": ["pytest"]})
        assert commands[0].stage == VerificationStage.UNIT

    def test_unknown_stage_key_raises_with_valid_list(self):
        with pytest.raises(ValueError, match="Unknown verification stage 'bogus'"):
            stage_commands_from_profile_config({"bogus": ["echo", "hi"]})

    def test_stage_key_map_covers_every_verification_stage(self):
        assert set(STAGE_KEY_MAP.values()) == set(VerificationStage)


# ============================================================================
# VerificationRunner: real subprocess execution
# ============================================================================

class TestVerificationRunner:
    def test_passing_command_yields_passed_result(self, tmp_path):
        runner = VerificationRunner(
            repo_root=tmp_path,
            stage_commands=[StageCommand(stage=VerificationStage.UNIT, command=[PY, "-c", "pass"])],
        )
        pipeline = runner.run()
        results = pipeline.get_summary()
        assert results["total_stages"] == 1
        assert pipeline.stages[0].result == VerificationResult.PASSED

    def test_deterministic_failure_halts_later_stages(self, tmp_path):
        """§11: a deterministic stage failure is terminal."""
        runner = VerificationRunner(
            repo_root=tmp_path,
            stage_commands=[
                StageCommand(stage=VerificationStage.LINT, command=[PY, "-c", "import sys; sys.exit(1)"]),
                StageCommand(stage=VerificationStage.UNIT, command=[PY, "-c", "pass"]),
            ],
        )
        pipeline = runner.run()
        # Only LINT ran: UNIT must have been skipped because LINT failed deterministically.
        ran_stages = [sr.stage for sr in pipeline.stages]
        assert ran_stages == [VerificationStage.LINT]
        assert pipeline.stages[0].result == VerificationResult.DETERMINISTIC_FAILURE

    def test_non_deterministic_failure_does_not_halt_later_stages(self, tmp_path):
        runner = VerificationRunner(
            repo_root=tmp_path,
            stage_commands=[
                StageCommand(stage=VerificationStage.UNIT, command=[PY, "-c", "import sys; sys.exit(1)"]),
                StageCommand(stage=VerificationStage.COMPONENT, command=[PY, "-c", "pass"]),
            ],
        )
        pipeline = runner.run()
        ran_stages = [sr.stage for sr in pipeline.stages]
        assert ran_stages == [VerificationStage.UNIT, VerificationStage.COMPONENT]
        assert pipeline.stages[0].result == VerificationResult.FAILED
        assert pipeline.stages[1].result == VerificationResult.PASSED

    def test_runs_in_canonical_order_regardless_of_input_order(self, tmp_path):
        runner = VerificationRunner(
            repo_root=tmp_path,
            stage_commands=[
                StageCommand(stage=VerificationStage.UNIT, command=[PY, "-c", "pass"]),
                StageCommand(stage=VerificationStage.FORMAT, command=[PY, "-c", "pass"]),
            ],
        )
        pipeline = runner.run()
        ran_stages = [sr.stage for sr in pipeline.stages]
        assert ran_stages == [VerificationStage.FORMAT, VerificationStage.UNIT]

    def test_missing_executable_is_recorded_as_failed_not_raised(self, tmp_path):
        runner = VerificationRunner(
            repo_root=tmp_path,
            stage_commands=[StageCommand(stage=VerificationStage.UNIT, command=["this-binary-does-not-exist"])],
        )
        pipeline = runner.run()
        assert pipeline.stages[0].result == VerificationResult.FAILED
