"""
Pydantic models for FactoryFlow data validation.

Schemas for workflows, context, evidence, decisions, requirements.
Used for deserialization + validation of all orchestrator inputs/outputs.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class RunStatus(str, Enum):
    """Run lifecycle states."""
    CLAIMED = "claimed"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    REVIEWING = "reviewing"
    MERGING = "merging"
    DEPLOYING = "deploying"
    VALIDATING_PRODUCTION = "validating_production"
    CLOSED = "closed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class StageType(str, Enum):
    """Workflow stage types (§4.3)."""
    COMMAND = "command"
    FUNCTION = "function"
    AGENT = "agent"
    DECISION = "decision"
    CONDITIONAL = "conditional"
    COMMAND_GROUP = "command_group"
    BOUNDED_LOOP = "bounded_loop"
    EXTERNAL_CHECK = "external_check"
    TERMINAL = "terminal"


class ContextIsolationLevel(str, Enum):
    """Context isolation levels (§6)."""
    SHARED = "shared"
    ROLE_PRIVATE = "role_private"
    SEALED = "sealed"


class FactoryRole(str, Enum):
    """Factory roles (each needs fresh session, §6.2)."""
    ANALYST = "analyst"
    PRODUCT_CRITIC = "product_critic"
    DOMAIN_CRITIC = "domain_critic"
    TESTABILITY_CRITIC = "testability_critic"
    SECURITY_CRITIC = "security_critic"
    CONTRADICTION_CRITIC = "contradiction_critic"
    OPERATIONAL_CRITIC = "operational_critic"
    PLANNER = "planner"
    BUILDER = "builder"
    REPAIRER = "repairer"
    SEALED_QA = "sealed_qa"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"


class FindingClassification(str, Enum):
    """Critic finding classifications (§7)."""
    EVIDENCE_RESOLVABLE = "evidence_resolvable"
    DELEGATED_TECHNICAL = "delegated_technical"
    REVERSIBLE = "reversible"
    STRATEGIC_AMBIGUITY = "strategic_ambiguity"
    INVALID = "invalid"


# ============================================================================
# Workflow Models
# ============================================================================

class StageTransitions(BaseModel):
    """State transitions for a workflow stage."""
    success: str = Field(..., description="Next stage on success")
    failure: str = Field(..., description="Next stage on failure (repair, escalate)")
    decision_required: Optional[str] = Field(None, description="Next stage if decision needed")


class WorkflowStage(BaseModel):
    """One stage in a workflow."""
    id: str = Field(..., min_length=1, max_length=64)
    type: StageType
    description: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(..., ge=10, le=3600)
    max_attempts: int = Field(..., ge=1, le=10)
    context_policy: Optional[ContextIsolationLevel] = None
    transitions: StageTransitions
    tool_policy: Optional[str] = None


class Workflow(BaseModel):
    """Complete workflow definition."""
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: str
    stages: List[WorkflowStage] = Field(..., min_items=1)
    context_policy: Optional[ContextIsolationLevel] = ContextIsolationLevel.SHARED


# ============================================================================
# Context Manifest Models
# ============================================================================

class SourceArtifact(BaseModel):
    """Artifact included in context package."""
    artifact_id: str
    artifact_type: str
    source_phase: int = Field(..., ge=1, le=16)
    hash_sha256: str = Field(..., regex=r"^[a-f0-9]{64}$")
    description: Optional[str] = None


class ContextExclusion(BaseModel):
    """Category deliberately excluded from context."""
    excluded_type: str
    reason: str


class PolicyDecision(BaseModel):
    """Policy approval record for context."""
    isolation_level: ContextIsolationLevel
    approved_by: str
    approval_timestamp: datetime


class ContextManifest(BaseModel):
    """Metadata for context package (§6.3)."""
    manifest_id: str = Field(..., regex=r"^manifest-[a-z0-9-]{16}$")
    project_id: str
    run_id: str = Field(..., regex=r"^RUN-[a-z0-9]{8}$")
    role: FactoryRole
    session_id: str
    source_artifacts: List[SourceArtifact]
    exclusions: List[ContextExclusion]
    policy_decision: PolicyDecision
    timestamp: datetime
    manifest_hash: str = Field(..., regex=r"^[a-f0-9]{64}$")


# ============================================================================
# Critic Finding Models
# ============================================================================

class CriticFinding(BaseModel):
    """One finding from an isolated critic (§7)."""
    finding_id: str
    critic_role: FactoryRole
    category: str  # e.g., "missing_permission", "contradiction", "unsupported_assumption"
    statement: str
    evidence_sources: List[str]  # References to authoritative sources
    severity: str  # info, low, medium, high, critical
    resolution_class: FindingClassification
    recommended_action: Optional[str] = None


# ============================================================================
# Evidence Manifest Models
# ============================================================================

class TestResults(BaseModel):
    """Test execution results."""
    unit: Optional[Dict[str, Any]] = None
    integration: Optional[Dict[str, Any]] = None
    sealed_acceptance: Optional[Dict[str, Any]] = None


class GateStatus(BaseModel):
    """All required gates (§14)."""
    intent_validation: bool
    authority_check: bool
    protected_paths: bool
    format: bool
    lint: bool
    typecheck: bool
    build: bool
    unit_tests: bool
    contract_tests: bool
    integration_tests: bool
    security_check: bool
    mutation_testing: bool
    sealed_qa: bool
    independent_review: bool
    preview: bool


class ReviewVerdict(BaseModel):
    """Independent review result (§11)."""
    status: str  # approved, rejected, decision_required
    reviewed_sha: str = Field(..., regex=r"^[a-f0-9]{40}$")
    reviewed_by_role: str = "reviewer"
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class EvidenceManifest(BaseModel):
    """Complete traceability record (§16)."""
    evidence_id: str = Field(..., regex=r"^evidence-[a-z0-9-]{16}$")
    project_id: str
    run_id: str
    issue_number: int
    base_sha: str = Field(..., regex=r"^[a-f0-9]{40}$")
    head_sha: str = Field(..., regex=r"^[a-f0-9]{40}$")
    deployed_sha: str = Field(..., regex=r"^[a-f0-9]{40}$")
    requirements: List[Dict[str, Any]]
    gates: GateStatus
    context_packages: List[Dict[str, Any]]
    tests: TestResults
    security_results: Dict[str, Any]
    mutation_results: Dict[str, Any]
    review_verdict: ReviewVerdict
    preview_result: Optional[Dict[str, Any]] = None
    production_validation: Optional[Dict[str, Any]] = None
    timestamp: datetime

    @field_validator("deployed_sha")
    @classmethod
    def deployed_must_match_head(cls, v: str, info) -> str:
        """Production SHA must match reviewed/merged SHA (§11)."""
        if info.data.get("head_sha") and v != info.data["head_sha"]:
            raise ValueError("deployed_sha must equal head_sha (no post-merge rebases)")
        return v


# ============================================================================
# Decision Models
# ============================================================================

class DecisionRecord(BaseModel):
    """Architecture decision record (ADR)."""
    adr_id: str = Field(..., regex=r"^ADR-\d{3}$")
    title: str = Field(..., min_length=5, max_length=200)
    date: str  # ISO date
    status: str  # PROPOSED, APPROVED, SUPERSEDED, IMPLEMENTED
    decision: str = Field(..., min_length=20)
    context: str
    options_considered: List[Dict[str, str]] = Field(..., min_items=2)
    rationale: str
    consequences: str
    evidence: Dict[str, Any]
    author: str
    superseded_by: Optional[str] = None


# ============================================================================
# Project Models
# ============================================================================

class ProjectConfig(BaseModel):
    """Factory project configuration."""
    project_id: str
    github_repo: str
    target_branch: str = "main"
    model_alias: str = "qwen2.5-coder:32b"  # Which model for all roles
    max_context_tokens: int = 8192
    backlog_policy: Dict[str, Any]  # Priority order, eligible criteria


class RunConfig(BaseModel):
    """Configuration for one factory run."""
    run_id: str
    project_id: str
    issue_number: int
    initial_context_tokens: int = 8192
    max_repair_attempts: int = 3


if __name__ == "__main__":
    # Quick validation test
    workflow_dict = {
        "version": "1.0.0",
        "name": "test",
        "description": "Test workflow",
        "stages": [
            {
                "id": "s1",
                "type": "command",
                "timeout_seconds": 30,
                "max_attempts": 1,
                "transitions": {"success": "terminal", "failure": "terminal"},
            }
        ],
    }
    workflow = Workflow(**workflow_dict)
    print(f"Workflow validated: {workflow.name} v{workflow.version}")
