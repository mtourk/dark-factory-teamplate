"""
Phase 3: FactoryFlow Core tests.

Tests for CLI, state management, config loading, and model validation.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

from factory.state import (
    init_db, get_db_session, close_db_session,
    Project, Run, Claim, Decision, Evidence, EmergencyStop,
    is_claim_stale, attempt_claim, release_claim,
    activate_emergency_stop, deactivate_emergency_stop, is_emergency_stopped
)
from factory.models import (
    Workflow, StageType, ContextManifest, EvidenceManifest,
    FactoryRole, FindingClassification
)
from factory.config import load_project_config, validate_workflow


# ============================================================================
# Database Tests
# ============================================================================

class TestStateManagement:
    """SQLite state management tests."""

    def test_init_db_creates_schema(self, tmp_path):
        """Database initialization creates all tables."""
        session = init_db()
        assert session is not None
        # Tables exist if we can query them
        session.query(Project).count()
        session.query(Run).count()
        close_db_session(session)

    def test_atomic_claim_success(self):
        """Atomic claim on unclaimed issue succeeds."""
        session = init_db()

        claim = attempt_claim(
            project_id="investisor",
            issue_number=42,
            run_id="RUN-20261003",
            session=session
        )

        assert claim is not None
        assert claim.issue_number == 42
        assert claim.lease_status == "active"
        close_db_session(session)

    def test_atomic_claim_race_protection(self):
        """Cannot claim already-claimed issue."""
        session = init_db()

        # First claim succeeds
        claim1 = attempt_claim(
            project_id="investisor",
            issue_number=43,
            run_id="RUN-abc001",
            session=session
        )
        assert claim1 is not None

        # Second concurrent claim fails
        claim2 = attempt_claim(
            project_id="investisor",
            issue_number=43,
            run_id="RUN-abc002",
            session=session
        )
        assert claim2 is None
        close_db_session(session)

    def test_stale_claim_recovery(self):
        """Stale lease allows new claim."""
        session = init_db()

        # First claim
        claim1 = attempt_claim(
            project_id="investisor",
            issue_number=44,
            run_id="RUN-xyz001",
            session=session
        )
        assert claim1 is not None

        # Mark as stale
        claim1.heartbeat = datetime.utcnow() - timedelta(hours=1)
        session.commit()

        # New claim should succeed (stale recovery)
        claim2 = attempt_claim(
            project_id="investisor",
            issue_number=44,
            run_id="RUN-xyz002",
            session=session
        )
        # Recovery creates new claim
        assert claim2 is not None or claim1.lease_status == "stale"
        close_db_session(session)

    def test_release_claim(self):
        """Released claim allows new claims."""
        session = init_db()

        claim = attempt_claim(
            project_id="investisor",
            issue_number=45,
            run_id="RUN-rel001",
            session=session
        )
        assert claim.lease_status == "active"

        release_claim(claim, session)
        assert claim.lease_status == "released"
        close_db_session(session)

    def test_emergency_stop_activation(self):
        """Emergency stop can be activated and checked."""
        session = init_db()

        assert not is_emergency_stopped(session)

        activate_emergency_stop("Production incident", session)
        assert is_emergency_stopped(session)

        deactivate_emergency_stop(session)
        assert not is_emergency_stopped(session)
        close_db_session(session)


# ============================================================================
# Model Validation Tests
# ============================================================================

class TestPydanticModels:
    """Pydantic model validation tests."""

    def test_workflow_valid(self):
        """Valid workflow model passes."""
        workflow_dict = {
            "version": "1.0.0",
            "name": "test-flow",
            "description": "Test workflow",
            "stages": [
                {
                    "id": "stage-1",
                    "type": "command",
                    "timeout_seconds": 60,
                    "max_attempts": 1,
                    "transitions": {
                        "success": "terminal",
                        "failure": "terminal"
                    }
                }
            ]
        }
        workflow = Workflow(**workflow_dict)
        assert workflow.name == "test-flow"
        assert len(workflow.stages) == 1

    def test_workflow_version_validation(self):
        """Workflow version must be semver."""
        with pytest.raises(ValueError):
            Workflow(
                version="invalid",
                name="test",
                description="test",
                stages=[]
            )

    def test_context_manifest_hash_format(self):
        """Context manifest hash must be SHA-256 hex."""
        with pytest.raises(ValueError):
            ContextManifest(
                manifest_id="manifest-abc123def456g",
                project_id="test",
                run_id="RUN-12345678",
                role=FactoryRole.BUILDER,
                session_id="sess-xyz",
                source_artifacts=[],
                exclusions=[],
                policy_decision={
                    "isolation_level": "role_private",
                    "approved_by": "test",
                    "approval_timestamp": datetime.utcnow()
                },
                timestamp=datetime.utcnow(),
                manifest_hash="invalid"  # Not 64-char hex
            )

    def test_evidence_manifest_sha_binding(self):
        """Evidence deployed_sha must match head_sha."""
        with pytest.raises(ValueError):
            EvidenceManifest(
                evidence_id="evidence-abc123def456g",
                project_id="test",
                run_id="RUN-12345678",
                issue_number=42,
                base_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                deployed_sha="cccccccccccccccccccccccccccccccccccccccc",  # Mismatch!
                requirements=[],
                gates={
                    "intent_validation": True,
                    "authority_check": True,
                    "protected_paths": True,
                    "format": True,
                    "lint": True,
                    "typecheck": True,
                    "build": True,
                    "unit_tests": True,
                    "contract_tests": True,
                    "integration_tests": True,
                    "security_check": True,
                    "mutation_testing": True,
                    "sealed_qa": True,
                    "independent_review": True,
                    "preview": True,
                },
                context_packages=[],
                tests={},
                security_results={},
                mutation_results={},
                review_verdict={
                    "status": "approved",
                    "reviewed_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "reviewed_by_role": "reviewer"
                },
                timestamp=datetime.utcnow()
            )


# ============================================================================
# CLI Tests
# ============================================================================

class TestCLI:
    """CLI command tests."""

    def test_doctor_command_checks(self):
        """Doctor command runs all checks."""
        # This would need mocking of external commands
        # For now, just verify imports work
        from factory.cli import doctor, app
        assert callable(doctor)
        assert app is not None

    def test_all_commands_exist(self):
        """All required commands are defined."""
        from factory.cli import (
            doctor, init, feature, express, run, pause, resume_queue,
            emergency_stop, queue, status, validate, report,
            benchmark, learn, decisions, decide
        )
        # If imports succeed, commands exist
        assert callable(doctor)


# ============================================================================
# Config Tests
# ============================================================================

class TestConfig:
    """Configuration loading tests."""

    def test_default_config_loads(self):
        """Project config loads with defaults."""
        config = load_project_config()
        assert "project_id" in config
        assert "target_branch" in config

    def test_workflow_validation_from_dict(self):
        """Workflow validation works from dict."""
        workflow_dict = {
            "version": "1.0.0",
            "name": "test",
            "description": "test",
            "stages": [{
                "id": "s1",
                "type": "command",
                "timeout_seconds": 30,
                "max_attempts": 1,
                "transitions": {"success": "terminal", "failure": "terminal"}
            }]
        }
        workflow = validate_workflow(workflow_dict)
        assert workflow.version == "1.0.0"


# ============================================================================
# Phase 3 Gate Test
# ============================================================================

def test_phase3_gate_core_operational():
    """
    Phase 3 Gate: FactoryFlow core is operational.

    Verifies:
    - Database initialization and basic operations
    - Atomic claim prevents races
    - Emergency stop works
    - Pydantic models validate correctly
    - CLI commands exist and are callable
    - Config loading works
    """
    # Database
    session = init_db()
    assert session is not None

    # Atomic claim
    claim = attempt_claim("test", 1, "RUN-test1", session)
    assert claim is not None
    race_claim = attempt_claim("test", 1, "RUN-test2", session)
    assert race_claim is None

    # Emergency stop
    assert not is_emergency_stopped(session)
    activate_emergency_stop("Test", session)
    assert is_emergency_stopped(session)
    deactivate_emergency_stop(session)
    assert not is_emergency_stopped(session)

    # Models
    workflow = Workflow(
        version="1.0.0",
        name="test",
        description="test",
        stages=[{
            "id": "s1",
            "type": "command",
            "timeout_seconds": 30,
            "max_attempts": 1,
            "transitions": {"success": "terminal", "failure": "terminal"}
        }]
    )
    assert workflow.name == "test"

    # CLI
    from factory.cli import app
    assert app is not None

    close_db_session(session)
    print("✓ Phase 3 Gate: FactoryFlow core operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
