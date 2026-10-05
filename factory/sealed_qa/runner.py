"""
Verification Runner: executes real commands for pipeline stages (§11).

`verification.py` is a pure data model (`VerificationPipeline`/`VerificationGate`)
— something still has to actually run format/lint/build/test and feed results
into it. This module is that "something" for local, subprocess-driven stages.

Honesty note: not all 17 stages in `VerificationStage` have a generic,
project-agnostic command (mutation testing, visual regression, accessibility,
performance need project-specific tooling we don't have yet). Stages with no
configured command are recorded as SKIPPED, not silently assumed to pass —
`VerificationGate.passes()` only requires no FAILED/deterministic-failure
stage, so skipped stages don't block the gate, but they also don't vouch for
anything. Callers that need a stricter gate should check
`pipeline.get_summary()["total_stages"]` against how many they expected to run.
"""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from factory.sealed_qa.verification import (
    VerificationPipeline,
    VerificationResult,
    VerificationStage,
)


@dataclass
class StageCommand:
    """A shell command that implements one verification stage."""
    stage: VerificationStage
    command: List[str]  # e.g. ["npm", "run", "lint"]
    cwd: Optional[Path] = None  # defaults to runner's repo_root
    timeout_seconds: float = 300.0


# Short, YAML-friendly keys (profile config) -> VerificationStage. Lets a
# profile write "unit: [pytest]" instead of the canonical "5_unit" enum value.
STAGE_KEY_MAP: Dict[str, VerificationStage] = {
    stage.name.lower(): stage for stage in VerificationStage
}


def stage_commands_from_profile_config(
    config: Optional[Dict[str, List[str]]],
) -> List[StageCommand]:
    """
    Turn a profile's `verification_commands` dict into `StageCommand`s.

    Args:
        config: short stage name (e.g. "unit", "lint", "build" — see
            `STAGE_KEY_MAP` / `VerificationStage`) -> command argv. Project
            profiles own this because the right command is project-specific
            (npm vs pytest vs cargo, etc.) — this function has no defaults
            and configures nothing on its own.

    Returns:
        One StageCommand per configured key, in no particular order (the
        runner re-sorts into canonical §11 order before executing).

    Raises:
        ValueError: a key doesn't match any VerificationStage name.
    """
    commands: List[StageCommand] = []
    for key, command in (config or {}).items():
        stage = STAGE_KEY_MAP.get(key.lower())
        if stage is None:
            valid = ", ".join(sorted(STAGE_KEY_MAP))
            raise ValueError(f"Unknown verification stage '{key}'. Valid stages: {valid}")
        commands.append(StageCommand(stage=stage, command=list(command)))
    return commands


@dataclass
class VerificationRunner:
    """
    Run a configured set of `StageCommand`s in §11 order and build a
    `VerificationPipeline` from the real results.

    Project-specific command sets live outside this module (e.g. a project
    profile) and get passed in as `stage_commands` — this runner has no
    opinion about whether a project uses npm, pytest, cargo, etc.
    """
    repo_root: Path
    stage_commands: List[StageCommand] = field(default_factory=list)

    def run(self) -> VerificationPipeline:
        """
        Execute each configured stage command in §11 order; stop at the
        first FAILED deterministic stage (per §11, a deterministic failure
        is terminal — running later stages on a broken build wastes time
        and can't change the gate outcome).

        Returns:
            VerificationPipeline populated with one StageResult per
            configured stage (plus SKIPPED entries are *not* added for
            unconfigured stages — only configured stages are recorded).
        """
        pipeline = VerificationPipeline()

        # Run in canonical §11 order regardless of the order passed in.
        ordered = sorted(self.stage_commands, key=lambda sc: sc.stage.value)

        for stage_cmd in ordered:
            result, duration, output, error = self._run_one(stage_cmd)
            pipeline.add_stage_result(
                stage_cmd.stage, result, duration, output, error=error
            )

            is_deterministic = stage_cmd.stage in VerificationPipeline.DETERMINISTIC_STAGES
            if result in (VerificationResult.FAILED, VerificationResult.DETERMINISTIC_FAILURE) and is_deterministic:
                # §11: deterministic failures are terminal; don't run the rest.
                break

        return pipeline

    def _run_one(self, stage_cmd: StageCommand):
        """Run a single stage command; never raises — failures become FAILED results."""
        cwd = stage_cmd.cwd or self.repo_root
        started = time.monotonic()
        try:
            proc = subprocess.run(
                stage_cmd.command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=stage_cmd.timeout_seconds,
            )
            duration = time.monotonic() - started
            output = (proc.stdout or "") + (proc.stderr or "")

            if proc.returncode == 0:
                return VerificationResult.PASSED, duration, output, None

            is_deterministic = stage_cmd.stage in VerificationPipeline.DETERMINISTIC_STAGES
            result = (
                VerificationResult.DETERMINISTIC_FAILURE
                if is_deterministic
                else VerificationResult.FAILED
            )
            return result, duration, output, f"Exit code {proc.returncode}"

        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - started
            output = (e.stdout or "") + (e.stderr or "") if (e.stdout or e.stderr) else ""
            return VerificationResult.FAILED, duration, output, f"Timed out after {stage_cmd.timeout_seconds}s"
        except OSError as e:
            duration = time.monotonic() - started
            return VerificationResult.FAILED, duration, "", f"Could not run command: {e}"
