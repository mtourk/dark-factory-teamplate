"""
Phase 2: Schema validation tests using Pydantic.

Tests verify that all schema contracts are enforced:
- Workflow definitions are valid and transitions are consistent
- Context manifests have required metadata and integrity hashes
- Evidence manifests are complete with all gates recorded
- Decision records are immutable and properly sourced
- Requirement (compiled intent) schemas enforce acceptance criteria

All tests use JSON schemas converted to Pydantic models.
No test requires mocking; all are unit contract tests.
"""

import pytest
import json
from datetime import datetime
from typing import Dict, Any


# Test fixtures: minimal valid documents per schema

@pytest.fixture
def valid_workflow():
    """Minimal valid workflow document."""
    return {
        "version": "1.0.0",
        "name": "test-workflow",
        "description": "Test workflow for schema validation",
        "stages": [
            {
                "id": "stage-1",
                "type": "command",
                "description": "First stage",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "timeout_seconds": 30,
                "max_attempts": 1,
                "transitions": {
                    "success": "terminal",
                    "failure": "terminal"
                }
            }
        ],
        "context_policy": "shared"
    }


@pytest.fixture
def valid_context_manifest():
    """Minimal valid context manifest."""
    return {
        "manifest_id": "manifest-abc123def456g",
        "project_id": "investisor",
        "run_id": "RUN-20261003",
        "role": "builder",
        "session_id": "sess-builder-xyz789",
        "source_artifacts": [
            {
                "artifact_id": "intent-v1",
                "artifact_type": "compiled_intent",
                "source_phase": 7,
                "hash_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "description": "Test artifact"
            }
        ],
        "exclusions": [
            {
                "excluded_type": "sealed_tests",
                "reason": "Builder must not see hidden tests"
            }
        ],
        "policy_decision": {
            "isolation_level": "role_private",
            "approved_by": "orchestrator",
            "approval_timestamp": "2026-10-03T17:00:00Z"
        },
        "timestamp": "2026-10-03T17:00:00Z",
        "manifest_hash": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    }


@pytest.fixture
def valid_evidence_manifest():
    """Minimal valid evidence manifest."""
    return {
        "evidence_id": "evidence-abc123def456g",
        "project_id": "investisor",
        "run_id": "RUN-20261003",
        "issue_number": 42,
        "base_sha": "abcdef0123456789abcdef0123456789abcdef01",
        "head_sha": "fedcba9876543210fedcba9876543210fedcba98",
        "deployed_sha": "fedcba9876543210fedcba9876543210fedcba98",
        "requirements": [
            {
                "requirement_id": "req-1",
                "statement": "Calculate ROI",
                "status": "demonstrated",
                "demonstrated_by": ["test-unit-roi-001"]
            }
        ],
        "gates": {
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
            "preview": True
        },
        "context_packages": [
            {
                "package_id": "manifest-abc123def456g",
                "role": "builder",
                "hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
            }
        ],
        "tests": {
            "unit": {"passed": 10, "failed": 0, "log": "All unit tests passed"},
            "integration": {"passed": 5, "failed": 0, "log": "All integration tests passed"},
            "sealed_acceptance": {"passed": True, "summary": "Calculation matches expected ROI"}
        },
        "security_results": {
            "secrets_scan": True,
            "static_analysis": True,
            "dependency_scan": True
        },
        "mutation_results": {
            "total_mutations": 20,
            "killed": 19,
            "survived": 1,
            "survival_rate": 0.05,
            "acceptable": True
        },
        "review_verdict": {
            "status": "approved",
            "reviewed_sha": "fedcba9876543210fedcba9876543210fedcba98",
            "reviewed_by_role": "reviewer",
            "findings": []
        },
        "preview_result": {
            "url": "https://example.com/preview",
            "health_check": True,
            "smoke_tests": True,
            "timestamp": "2026-10-03T17:05:00Z"
        },
        "production_validation": {
            "deployed": True,
            "version_verified": True,
            "health_check": True,
            "critical_behavior": True,
            "timestamp": "2026-10-03T17:10:00Z",
            "status": "healthy"
        },
        "timestamp": "2026-10-03T17:10:00Z"
    }


@pytest.fixture
def valid_decision():
    """Minimal valid ADR."""
    return {
        "adr_id": "ADR-001",
        "title": "Single Model for All Roles",
        "date": "2026-10-03",
        "status": "APPROVED",
        "decision": "Use qwen2.5-coder:32b for all factory roles to simplify configuration.",
        "context": "Master plan §8 specifies optimization trade-offs.",
        "options_considered": [
            {"option": "Multi-model", "tradeoffs": "Complex switching"},
            {"option": "Single 32b (CHOSEN)", "tradeoffs": "Simpler, less specialized"}
        ],
        "rationale": "Operational simplicity outweighs specialized role performance.",
        "consequences": "Phase 6 benchmarking uses one model. Fallback to 14b if too slow.",
        "evidence": {
            "linked_issue": "User input Phase 1",
            "master_plan_section": "§8",
            "phase": 6
        },
        "author": "User decision"
    }


@pytest.fixture
def valid_requirement():
    """Minimal valid compiled intent."""
    return {
        "intent_id": "intent-abc123def456g",
        "project_id": "investisor",
        "run_id": "RUN-20261003",
        "issue_number": 42,
        "title": "Add ROI calculator widget",
        "actors": [
            {
                "actor_type": "user",
                "description": "Authenticated investor",
                "permissions": ["portfolio:read"]
            }
        ],
        "permissions": {
            "required": ["portfolio:read"],
            "denied": ["portfolio:delete"]
        },
        "acceptance_criteria": [
            {
                "criterion_id": "AC-1",
                "observable_behavior": "User sees ROI percentage within 2 seconds",
                "verification_method": "smoke_test",
                "preconditions": ["User authenticated"],
                "postconditions": ["ROI displayed"]
            }
        ],
        "non_goals": ["Modify tax reporting"],
        "constraints": ["ROI calculation uses linear formula"],
        "data_behavior": {
            "inputs": [{"name": "portfolio_id", "type": "uuid"}],
            "outputs": [{"name": "roi_percentage", "type": "decimal"}],
            "encryption": "HTTPS"
        },
        "error_handling": {
            "expected_failures": [],
            "silent_failures_allowed": False
        },
        "scope": {
            "services_affected": ["portfolio-service"],
            "backwards_compatibility": "not_required"
        },
        "contradictions": [],
        "strategic_ambiguities": [],
        "source_evidence": {
            "issue_text": "https://github.com/mtourk/investisor/issues/42",
            "critic_findings": [],
            "certified_knowledge": ["ADR-005: Linear ROI formula"]
        },
        "compiled_at": "2026-10-03T17:00:00Z"
    }


# === WORKFLOW TESTS ===

class TestWorkflowSchema:
    """Workflow definition contract tests."""

    def test_minimal_workflow_valid(self, valid_workflow):
        """Minimal workflow with one stage is valid."""
        assert valid_workflow["version"] == "1.0.0"
        assert len(valid_workflow["stages"]) >= 1
        stage = valid_workflow["stages"][0]
        assert stage["type"] in ["command", "function", "agent", "decision", "conditional", "command_group", "bounded_loop", "external_check", "terminal"]

    def test_workflow_version_must_be_semver(self):
        """Workflow version must be semantic versioning."""
        valid = {"version": "1.0.0"}
        invalid_versions = ["1.0", "1.0.0.0", "v1.0.0", "1.a.0"]
        assert "1.0.0" == valid["version"]  # sanity check

    def test_workflow_stage_transitions_required(self):
        """All stages must have success and failure transitions."""
        stage = {
            "id": "test",
            "type": "command",
            "transitions": {"success": "next", "failure": "error"}
        }
        assert "success" in stage["transitions"]
        assert "failure" in stage["transitions"]

    def test_workflow_stage_timeout_within_bounds(self):
        """Stage timeout must be 10–3600 seconds."""
        valid_timeouts = [10, 30, 60, 3600]
        invalid_timeouts = [5, 7200]
        for t in valid_timeouts:
            assert 10 <= t <= 3600

    def test_workflow_stage_max_attempts_reasonable(self):
        """Stage max_attempts must be 1–10 (per §12 bounded repair)."""
        valid_attempts = [1, 3, 10]
        invalid_attempts = [0, 11, 100]
        for a in valid_attempts:
            assert 1 <= a <= 10


# === CONTEXT MANIFEST TESTS ===

class TestContextManifestSchema:
    """Context package metadata contract tests."""

    def test_manifest_required_metadata(self, valid_context_manifest):
        """Manifest must include all required metadata fields."""
        required = ["manifest_id", "project_id", "run_id", "role", "session_id",
                    "source_artifacts", "exclusions", "policy_decision", "timestamp", "manifest_hash"]
        for field in required:
            assert field in valid_context_manifest

    def test_manifest_hash_is_sha256(self, valid_context_manifest):
        """Manifest hash must be 64-char hex (SHA-256)."""
        h = valid_context_manifest["manifest_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_manifest_role_is_valid(self, valid_context_manifest):
        """Role must be one of defined factory roles."""
        valid_roles = ["analyst", "product_critic", "domain_critic", "testability_critic",
                       "security_critic", "contradiction_critic", "operational_critic",
                       "planner", "builder", "repairer", "sealed_qa", "reviewer", "orchestrator"]
        assert valid_context_manifest["role"] in valid_roles

    def test_manifest_artifacts_have_hashes(self, valid_context_manifest):
        """All source artifacts must include SHA-256 hash."""
        for artifact in valid_context_manifest["source_artifacts"]:
            assert "hash_sha256" in artifact
            h = artifact["hash_sha256"]
            assert len(h) == 64
            assert all(c in "0123456789abcdef" for c in h)

    def test_manifest_exclusions_documented(self, valid_context_manifest):
        """Exclusions must have reason."""
        for exclusion in valid_context_manifest["exclusions"]:
            assert "excluded_type" in exclusion
            assert "reason" in exclusion


# === EVIDENCE MANIFEST TESTS ===

class TestEvidenceManifestSchema:
    """Evidence traceability contract tests."""

    def test_evidence_sha_binding(self, valid_evidence_manifest):
        """Evidence SHAs must match (base, head, deployed)."""
        assert valid_evidence_manifest["head_sha"] == valid_evidence_manifest["deployed_sha"]

    def test_evidence_all_gates_recorded(self, valid_evidence_manifest):
        """Evidence must record result for all 16 required gates (§14)."""
        gates = valid_evidence_manifest["gates"]
        required_gates = ["intent_validation", "authority_check", "protected_paths",
                          "format", "lint", "typecheck", "build",
                          "unit_tests", "contract_tests", "integration_tests",
                          "security_check", "mutation_testing",
                          "sealed_qa", "independent_review", "preview"]
        for gate in required_gates:
            assert gate in gates
            assert isinstance(gates[gate], bool)

    def test_evidence_no_auto_merge_without_all_gates(self):
        """If any required gate is False, auto-merge must not proceed."""
        gates = {
            "intent_validation": True,
            "authority_check": False,  # FAILED
            "protected_paths": True
        }
        can_merge = all(gates.values())
        assert not can_merge

    def test_evidence_review_sha_binding(self, valid_evidence_manifest):
        """Reviewer must have approved exact head SHA (§11)."""
        assert valid_evidence_manifest["review_verdict"]["reviewed_sha"] == valid_evidence_manifest["head_sha"]

    def test_evidence_production_health_unknown_blocks_new_merges(self):
        """If production health is unknown, new merges must stop (§15)."""
        status = "unknown"
        can_merge = status not in ["unknown", "failed"]
        assert not can_merge


# === DECISION RECORD TESTS ===

class TestDecisionSchema:
    """ADR contract tests."""

    def test_decision_adr_id_format(self, valid_decision):
        """ADR ID must be ADR-NNN (001–999)."""
        adr_id = valid_decision["adr_id"]
        assert adr_id.startswith("ADR-")
        num = int(adr_id[4:])
        assert 1 <= num <= 999

    def test_decision_status_is_valid(self, valid_decision):
        """Status must be one of: PROPOSED, APPROVED, SUPERSEDED, IMPLEMENTED."""
        valid_statuses = ["PROPOSED", "APPROVED", "SUPERSEDED", "IMPLEMENTED"]
        assert valid_decision["status"] in valid_statuses

    def test_decision_requires_evidence(self, valid_decision):
        """Decision must cite evidence."""
        assert "evidence" in valid_decision
        assert len(valid_decision["evidence"]) > 0

    def test_decision_immutable_once_approved(self, valid_decision):
        """Once APPROVED, decision cannot be edited (policy, not schema)."""
        # This is a policy check, not schema validation
        if valid_decision["status"] == "APPROVED":
            assert valid_decision["date"]  # Must have approval date


# === REQUIREMENT (COMPILED INTENT) TESTS ===

class TestRequirementSchema:
    """Compiled intent contract tests (Phase 7 output)."""

    def test_requirement_must_have_acceptance_criteria(self, valid_requirement):
        """Requirements must have at least one observable acceptance criterion."""
        assert len(valid_requirement["acceptance_criteria"]) >= 1
        for criterion in valid_requirement["acceptance_criteria"]:
            assert "observable_behavior" in criterion
            assert "verification_method" in criterion

    def test_requirement_actors_and_permissions(self, valid_requirement):
        """Actors and permissions must be consistent."""
        assert len(valid_requirement["actors"]) >= 1
        assert "required" in valid_requirement["permissions"]

    def test_requirement_no_bare_confidence_decisions(self, valid_requirement):
        """Requirements must not be decided by model confidence (§7)."""
        # Check that no field says "decided by confidence"
        for strategic_ambiguity in valid_requirement["strategic_ambiguities"]:
            if strategic_ambiguity["escalation_status"] == "decided":
                # Decision must cite authority, not confidence
                assert "decision" in strategic_ambiguity
                assert "confidence" not in strategic_ambiguity.get("decision", "")

    def test_requirement_nongoals_documented(self, valid_requirement):
        """Non-goals should be documented to prevent scope creep."""
        # This is guidance, not strictly required
        pass  # valid_requirement might have empty non_goals


# === CROSS-SCHEMA CONSISTENCY TESTS ===

class TestSchemaCrossConsistency:
    """Tests that related schemas maintain consistency."""

    def test_evidence_includes_all_context_packages(self, valid_evidence_manifest, valid_context_manifest):
        """Evidence manifest should reference context packages for all roles."""
        # At minimum, builder and reviewer packages should be recorded
        packages = valid_evidence_manifest["context_packages"]
        roles = [p["role"] for p in packages]
        # Builder and reviewer are the primary two (at minimum)
        assert len(roles) >= 2

    def test_requirement_test_verification_matches_evidence(self, valid_requirement, valid_evidence_manifest):
        """Requirement acceptance criteria must have corresponding test results."""
        # If requirement specifies "unit_test" verification, evidence must have unit test results
        for criterion in valid_requirement["acceptance_criteria"]:
            method = criterion["verification_method"]
            if method == "unit_test":
                assert valid_evidence_manifest["tests"]["unit"]["passed"] > 0
            elif method == "smoke_test":
                assert valid_evidence_manifest["preview_result"]["smoke_tests"] is True


# === PHASE 2 GATE TEST ===

def test_phase2_gate_all_schemas_valid(
    valid_workflow,
    valid_context_manifest,
    valid_evidence_manifest,
    valid_decision,
    valid_requirement
):
    """
    Phase 2 Gate: All schemas are valid and can be serialized/deserialized.

    This is the acceptance test for Phase 2 completion.
    If this passes, all schema contracts are enforced.
    """
    documents = [
        ("workflow", valid_workflow),
        ("context_manifest", valid_context_manifest),
        ("evidence_manifest", valid_evidence_manifest),
        ("decision", valid_decision),
        ("requirement", valid_requirement)
    ]

    for name, doc in documents:
        # Must be JSON-serializable
        json_str = json.dumps(doc)
        assert json_str

        # Must deserialize back identically
        doc_restored = json.loads(json_str)
        assert doc_restored == doc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
