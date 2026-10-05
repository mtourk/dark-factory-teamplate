"""
Context Broker: Assembles and isolates context packages by role.

Per master plan §6:
"Every agent call is identified by: project_id + run_id + role + session_id
A new role means a new API conversation, system prompt, context package, private directory, and session ID."

Context classes (§6.1):
1. Immutable governance: protected paths, merge/deploy policy
2. Certified project knowledge: approved requirements, ADRs, contracts, glossary
3. Run-shared approved artifacts: compiled intent, assurance, plan, criteria, evidence
4. Role-private data: conversations, notes, exploration
5. Restricted assurance: sealed tests, mutations, rubrics, policies, secrets
6. Ephemeral: temporary reasoning

Storage (§6.6):
C:\Factory\
  worktrees\RUN-...\
    shared\                 (run-shared, role-accessible)
    analyst-private\        (analyst session only)
    builder-private\        (builder session only)
    reviewer-private\       (reviewer session only)
  control\
    sealed\                 (hidden from builder)
    mutations\              (hidden from builder)
    rubrics\                (hidden from builder)
    policies\
    secrets\                (never logged)
"""

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from pydantic import BaseModel, ValidationError

from factory.models import ContextManifest, FactoryRole, SourceArtifact, ContextExclusion, PolicyDecision, ContextIsolationLevel


FACTORY_ROOT = Path("C:/Factory")
CONTROL_DIR = FACTORY_ROOT / "control"
SEALED_DIR = CONTROL_DIR / "sealed"
MUTATIONS_DIR = CONTROL_DIR / "mutations"
RUBRICS_DIR = CONTROL_DIR / "rubrics"
POLICIES_DIR = CONTROL_DIR / "policies"
SECRETS_DIR = CONTROL_DIR / "secrets"


class ContextPolicyViolation(Exception):
    """Raised when context access violates policy (fail-closed, §6.1)."""
    pass


@dataclass
class ContextPackage:
    """Assembled context for one role in one run."""
    package_id: str
    project_id: str
    run_id: str
    role: FactoryRole
    session_id: str

    # Included artifacts
    governance: Dict[str, Any]  # protected paths, merge policy
    certified_knowledge: Dict[str, Any]  # ADRs, contracts, glossary
    shared_artifacts: Dict[str, Any]  # compiled intent, plan, evidence
    role_private: Dict[str, Any]  # (empty on first pass, filled during role execution)

    # Metadata
    created_at: datetime
    manifest: ContextManifest

    def to_manifest(self) -> ContextManifest:
        """Convert to ContextManifest for serialization."""
        return self.manifest

    def validate_isolation(self) -> None:
        """Verify no unauthorized data in this package (§6.8)."""
        # Builder must not see sealed tests
        if self.role == FactoryRole.BUILDER:
            if "sealed_tests" in self.shared_artifacts:
                raise ContextPolicyViolation("Builder received sealed tests (§9 violation)")
            if "mutation_definitions" in self.shared_artifacts:
                raise ContextPolicyViolation("Builder received mutation definitions (§9 violation)")
            if "reviewer_rubric" in self.shared_artifacts:
                raise ContextPolicyViolation("Builder received reviewer rubric (§11 violation)")

        # Reviewer must not see builder conversation
        if self.role == FactoryRole.REVIEWER:
            if "builder_chat" in self.shared_artifacts:
                raise ContextPolicyViolation("Reviewer received builder conversation (§11 violation)")
            if "repair_logs" in self.shared_artifacts:
                raise ContextPolicyViolation("Reviewer received repair logs (§11 violation)")
            if "sealed_tests" in self.shared_artifacts:
                raise ContextPolicyViolation("Reviewer received sealed tests (§11 violation)")


class ContextBroker:
    """Context package assembler with isolation enforcement."""

    def __init__(self, project_id: str, run_id: str):
        """
        Initialize broker for project run.

        Args:
            project_id: e.g., "investisor"
            run_id: e.g., "RUN-20261003"
        """
        self.project_id = project_id
        self.run_id = run_id
        self.worktree_path = FACTORY_ROOT / "worktrees" / run_id

        # Create run directories
        self.shared_dir = self.worktree_path / "shared"
        self.shared_dir.mkdir(parents=True, exist_ok=True)

    def get_role_private_dir(self, role: FactoryRole) -> Path:
        """Get private directory for role (§6.6)."""
        role_name = role.value  # e.g., "builder"
        private_dir = self.worktree_path / f"{role_name}-private"
        private_dir.mkdir(parents=True, exist_ok=True)
        return private_dir

    def assemble_governance_context(self) -> Dict[str, Any]:
        """
        Assemble immutable governance context (same for all roles).

        Includes:
        - Protected paths (cannot auto-merge)
        - Merge and deployment policy
        - Authority rules
        """
        return {
            "protected_paths": [
                "DARK_FACTORY_MASTER_PLAN.md",
                "DARK_FACTORY_BUILD_PROMPT.md",
                "IMPLEMENTATION_CHECKLIST.md",
                "THIRD_PARTY_NOTICES.md",
                ".factory-control/",
                ".factory/",
                ".github/workflows/",
                "docs/decisions/",
            ],
            "merge_policy": {
                "require_all_checks": True,
                "no_admin_bypass": True,
                "no_direct_push_to_main": True,
                "auto_merge_only_reviewed_sha": True,
            },
            "deployment_policy": {
                "cloudflare_secrets_github_only": True,
                "never_deploy_to_main_directly": True,
                "verify_production_after_deploy": True,
            },
        }

    def assemble_certified_knowledge(self) -> Dict[str, Any]:
        """
        Assemble certified project knowledge (same for all roles).

        Includes:
        - Approved ADRs
        - Contracts and glossary
        - Domain rules
        """
        # In a real implementation, load from certified_knowledge/ directory
        # For now, return skeleton
        return {
            "adrs": {},  # ADR-001, ADR-002, etc.
            "contracts": {},  # API schemas, data contracts
            "glossary": {},  # domain terms
            "domain_rules": {},  # business rules
        }

    def assemble_shared_artifacts(
        self,
        compiled_intent: Optional[Dict[str, Any]] = None,
        approved_plan: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assemble run-shared approved artifacts.

        All roles get these (but builder/reviewer see different subsets).
        """
        return {
            "compiled_intent": compiled_intent or {},
            "approved_plan": approved_plan or {},
            "evidence": evidence or {},
        }

    def assemble_role_context(self, role: FactoryRole) -> ContextPackage:
        """
        Assemble complete context package for role (fail-closed if incomplete).

        Args:
            role: factory role

        Returns:
            ContextPackage with all non-private artifacts

        Raises:
            ContextPolicyViolation: if manifest is missing or incomplete
        """
        package_id = f"pkg-{self.run_id}-{role.value}"
        session_id = f"sess-{role.value}-{datetime.utcnow().isoformat()}"

        # manifest_id must match ContextManifest's pattern
        # ^manifest-[a-z0-9-]{16}$ (factory/models.py), so derive a 16-char
        # lowercase-alphanumeric suffix from a hash of (run_id, role) rather
        # than reusing package_id (which contains uppercase/underscore chars
        # and is not length-constrained).
        manifest_suffix = hashlib.sha256(
            f"{self.run_id}:{role.value}".encode()
        ).hexdigest()[:16]
        manifest_id = f"manifest-{manifest_suffix}"

        # Assemble sources
        governance = self.assemble_governance_context()
        knowledge = self.assemble_certified_knowledge()
        shared = self.assemble_shared_artifacts()

        # Create manifest (manifest_hash computed below, before the first
        # and only ContextManifest validation -- see _compute_manifest_hash).
        manifest_dict = {
            "manifest_id": manifest_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "role": role,
            "session_id": session_id,
            "source_artifacts": self._compute_source_artifacts(governance, knowledge, shared),
            "exclusions": self._compute_exclusions(role),
            "policy_decision": {
                "isolation_level": self._get_isolation_level(role),
                "approved_by": "orchestrator",
                "approval_timestamp": datetime.utcnow().isoformat(),
            },
            "timestamp": datetime.utcnow().isoformat(),
            "manifest_hash": "",  # Placeholder; replaced below before validation
        }

        # Compute manifest hash over the manifest contents (excluding the
        # hash field itself, per _compute_manifest_hash) BEFORE constructing/
        # validating the ContextManifest -- manifest_hash requires a 64-char
        # hex pattern, so validating with "" first would always raise.
        manifest_dict["manifest_hash"] = self._compute_manifest_hash(manifest_dict)

        # Validate manifest structure exactly once, with the real hash.
        try:
            manifest = ContextManifest(**manifest_dict)
        except ValidationError as e:
            raise ContextPolicyViolation(f"Context manifest validation failed: {e}")

        # Assemble package
        package = ContextPackage(
            package_id=package_id,
            project_id=self.project_id,
            run_id=self.run_id,
            role=role,
            session_id=session_id,
            governance=governance,
            certified_knowledge=knowledge,
            shared_artifacts=shared,
            role_private={},
            created_at=datetime.utcnow(),
            manifest=manifest,
        )

        # Validate isolation boundaries
        package.validate_isolation()

        return package

    def _compute_source_artifacts(
        self,
        governance: Dict[str, Any],
        knowledge: Dict[str, Any],
        shared: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Compute source artifact hashes."""
        artifacts = []
        for name, data in [
            ("governance", governance),
            ("certified_knowledge", knowledge),
            ("shared_artifacts", shared),
        ]:
            artifact_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()
            artifacts.append({
                "artifact_id": name,
                "artifact_type": name,
                # SourceArtifact.source_phase requires >=1 (factory/models.py).
                # No caller currently threads a real phase number through to
                # the broker (governance/certified_knowledge/shared_artifacts
                # are all phase-agnostic, run-level context), so phase 1 is
                # used as a placeholder pending real phase-tracking.
                "source_phase": 1,
                "hash_sha256": artifact_hash,
                "description": f"{name} context",
            })
        return artifacts

    def _compute_exclusions(self, role: FactoryRole) -> List[Dict[str, str]]:
        """Compute exclusions for role."""
        exclusions = []

        if role == FactoryRole.BUILDER:
            exclusions.extend([
                {"excluded_type": "sealed_tests", "reason": "Builder must not see hidden acceptance criteria (§9)"},
                {"excluded_type": "mutation_definitions", "reason": "Builder must not overfit (§9)"},
                {"excluded_type": "reviewer_rubric", "reason": "Builder independence (§11)"},
                {"excluded_type": "credentials", "reason": "Secrets never exposed (§6)"},
            ])

        if role == FactoryRole.REVIEWER:
            exclusions.extend([
                {"excluded_type": "builder_chat", "reason": "Reviewer independence (§11)"},
                {"excluded_type": "repair_logs", "reason": "Reviewer independence (§11)"},
                {"excluded_type": "sealed_tests", "reason": "Tests never exposed to model (§9)"},
                {"excluded_type": "credentials", "reason": "Secrets never exposed (§6)"},
            ])

        return exclusions

    def _get_isolation_level(self, role: FactoryRole) -> str:
        """Get context isolation level for role."""
        if role in [FactoryRole.BUILDER, FactoryRole.REVIEWER]:
            return ContextIsolationLevel.ROLE_PRIVATE.value
        return ContextIsolationLevel.SHARED.value

    def _compute_manifest_hash(self, manifest_dict: Dict[str, Any]) -> str:
        """Compute SHA-256 of manifest."""
        # Exclude the hash field itself
        manifest_copy = {k: v for k, v in manifest_dict.items() if k != "manifest_hash"}
        manifest_json = json.dumps(manifest_copy, sort_keys=True)
        return hashlib.sha256(manifest_json.encode()).hexdigest()

    def store_package(self, package: ContextPackage) -> Path:
        """
        Store context package to disk (role-private directory).

        Returns:
            Path to stored manifest file
        """
        private_dir = self.get_role_private_dir(package.role)
        manifest_path = private_dir / f"context-manifest-{package.package_id}.json"

        manifest_json = package.manifest.model_dump_json(indent=2)
        manifest_path.write_text(manifest_json)

        return manifest_path

    def load_package(self, role: FactoryRole, package_id: str) -> ContextPackage:
        """
        Load context package from disk (verify manifest integrity).

        Args:
            role: role loading the package
            package_id: package identifier

        Returns:
            ContextPackage

        Raises:
            ContextPolicyViolation: if manifest missing or integrity check fails
        """
        private_dir = self.get_role_private_dir(role)
        manifest_path = private_dir / f"context-manifest-{package_id}.json"

        if not manifest_path.exists():
            raise ContextPolicyViolation(f"Context package not found: {manifest_path}")

        manifest_json = manifest_path.read_text()
        manifest_dict = json.loads(manifest_json)

        # Verify manifest hash (integrity check)
        stored_hash = manifest_dict.get("manifest_hash", "")
        manifest_dict["manifest_hash"] = ""  # Clear for recomputation
        computed_hash = self._compute_manifest_hash(manifest_dict)

        if stored_hash != computed_hash:
            raise ContextPolicyViolation(f"Context manifest integrity check failed (tampering detected?)")

        manifest_dict["manifest_hash"] = stored_hash
        manifest = ContextManifest(**manifest_dict)

        # Reconstruct package (simplified)
        package = ContextPackage(
            package_id=package_id,
            project_id=manifest.project_id,
            run_id=manifest.run_id,
            role=manifest.role,
            session_id=manifest.session_id,
            governance={},
            certified_knowledge={},
            shared_artifacts={},
            role_private={},
            created_at=datetime.utcnow(),
            manifest=manifest,
        )

        # Validate isolation
        package.validate_isolation()

        return package


if __name__ == "__main__":
    # Quick test
    broker = ContextBroker("investisor", "RUN-test001")
    package = broker.assemble_role_context(FactoryRole.BUILDER)
    print(f"Context package: {package.package_id}")
    print(f"Role: {package.role.value}")
    print(f"Manifest hash: {package.manifest.manifest_hash[:16]}...")
    broker.store_package(package)
    print("Package stored successfully")
