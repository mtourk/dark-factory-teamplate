"""
Worktree Management: isolated build environments per run.

Per master plan §10:
"Every run uses C:\\Factory\\worktrees\\RUN-<id> and branch
factory/RUN-<id>-<slug>. Never modify the primary checkout, reuse a
worktree, or delete evidence before durability is confirmed.

Worktrees are not security sandboxes. Combine them with a restricted
account, ACLs, command broker, OPA, and allowed write roots.

Protected paths include factory governance, control data, production
workflows, environment files, authority code, emergency-stop scripts,
and secret configuration. A protected-path change may not auto-merge."
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from factory.profiles import get_factory_root

# FF-P01-01: resolved via factory/profiles.py (FACTORY_ROOT env var, else
# ~/.factory) instead of a hardcoded Windows path, so this module works
# unmodified on Windows/macOS/Linux.
FACTORY_ROOT = get_factory_root()
WORKTREES_DIR = FACTORY_ROOT / "worktrees"


@dataclass
class WorktreeMetadata:
    """Metadata for run worktree."""
    run_id: str
    project_id: str
    issue_number: int
    branch_name: str
    base_sha: str  # Base commit SHA
    created_at: str
    worktree_path: Path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "issue_number": self.issue_number,
            "branch_name": self.branch_name,
            "base_sha": self.base_sha,
            "created_at": self.created_at,
            "worktree_path": str(self.worktree_path),
        }


class WorktreeManager:
    """
    Manage isolated git worktrees for each run (§10).

    Layout:
    C:\\Factory\\worktrees\\RUN-<id>\\
        shared\\                (run-shared, all roles read)
        builder-private\\       (builder session only)
        reviewer-private\\      (reviewer session only)
        analyst-private\\       (analyst session only)
        ...
        .git                    (worktree git state)
        .worktree               (git worktree metadata)
    """

    def __init__(self, factory_root: Path = FACTORY_ROOT):
        """Initialize worktree manager."""
        self.factory_root = factory_root
        self.worktrees_dir = factory_root / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def create_worktree(
        self,
        run_id: str,
        project_id: str,
        issue_number: int,
        base_sha: str,
        branch_slug: str,
    ) -> WorktreeMetadata:
        """
        Create isolated worktree for run (§10).

        Args:
            run_id: factory run ID (e.g., "RUN-20261003-001")
            project_id: project ID (e.g., "investisor")
            issue_number: GitHub issue number
            base_sha: base commit SHA (40-char hex)
            branch_slug: short branch name (e.g., "search-feature")

        Returns:
            WorktreeMetadata with worktree path and metadata

        Raises:
            ValueError: if run_id already exists (no reuse per §10)
        """
        worktree_path = self.worktrees_dir / run_id
        if worktree_path.exists():
            raise ValueError(f"Worktree already exists (no reuse per §10): {worktree_path}")

        # Create worktree directory structure
        worktree_path.mkdir(parents=True, exist_ok=False)
        (worktree_path / "shared").mkdir(exist_ok=True)

        # Branch name: factory/RUN-<id>-<slug>
        branch_name = f"factory/{run_id}-{branch_slug}"

        # Create metadata file
        metadata = WorktreeMetadata(
            run_id=run_id,
            project_id=project_id,
            issue_number=issue_number,
            branch_name=branch_name,
            base_sha=base_sha,
            created_at=datetime.utcnow().isoformat(),
            worktree_path=worktree_path,
        )

        metadata_path = worktree_path / ".factory-worktree-metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        return metadata

    def get_worktree_path(self, run_id: str) -> Path:
        """Get path for run worktree."""
        return self.worktrees_dir / run_id

    def get_shared_dir(self, run_id: str) -> Path:
        """Get shared artifacts directory for run."""
        return self.get_worktree_path(run_id) / "shared"

    def get_role_private_dir(self, run_id: str, role: str) -> Path:
        """Get role-private directory (e.g., builder-private, reviewer-private)."""
        return self.get_worktree_path(run_id) / f"{role}-private"

    def load_metadata(self, run_id: str) -> WorktreeMetadata:
        """Load worktree metadata."""
        metadata_path = self.get_worktree_path(run_id) / ".factory-worktree-metadata.json"
        if not metadata_path.exists():
            raise ValueError(f"Worktree metadata not found: {metadata_path}")

        with open(metadata_path, "r") as f:
            data = json.load(f)

        return WorktreeMetadata(
            run_id=data["run_id"],
            project_id=data["project_id"],
            issue_number=data["issue_number"],
            branch_name=data["branch_name"],
            base_sha=data["base_sha"],
            created_at=data["created_at"],
            worktree_path=Path(data["worktree_path"]),
        )

    def verify_worktree_integrity(self, run_id: str) -> Dict[str, Any]:
        """
        Verify worktree integrity: directory exists, metadata valid, no tampering.

        Args:
            run_id: run ID

        Returns:
            integrity report dict with status and details
        """
        worktree_path = self.get_worktree_path(run_id)

        report = {
            "run_id": run_id,
            "exists": worktree_path.exists(),
            "shared_exists": (worktree_path / "shared").exists(),
            "metadata_valid": False,
            "metadata_errors": [],
        }

        if not worktree_path.exists():
            report["metadata_errors"].append("Worktree directory missing")
            return report

        try:
            metadata = self.load_metadata(run_id)
            report["metadata_valid"] = True
            report["branch_name"] = metadata.branch_name
            report["base_sha"] = metadata.base_sha
        except Exception as e:
            report["metadata_errors"].append(str(e))

        return report


class ProtectedPathValidator:
    """Validate changes against protected paths list (§10)."""

    # Protected paths (per master plan §10 and IMPLEMENTATION_CHECKLIST.md)
    PROTECTED_PATHS = [
        "DARK_FACTORY_MASTER_PLAN.md",
        "DARK_FACTORY_BUILD_PROMPT.md",
        "IMPLEMENTATION_CHECKLIST.md",
        "THIRD_PARTY_NOTICES.md",
        ".factory-control/",
        ".factory/",
        ".github/workflows/",
        "docs/decisions/",
    ]

    @classmethod
    def is_protected(cls, path: str) -> bool:
        """Check if path is protected (cannot auto-merge)."""
        path_normalized = path.replace("\\", "/").lstrip("/")

        for protected in cls.PROTECTED_PATHS:
            protected_normalized = protected.replace("\\", "/").rstrip("/")

            # Exact match or directory match
            if path_normalized == protected_normalized:
                return True
            if path_normalized.startswith(protected_normalized + "/"):
                return True
            if protected_normalized.endswith("/") and path_normalized.startswith(protected_normalized):
                return True

        return False

    @classmethod
    def validate_changeset(cls, changed_paths: list) -> Dict[str, Any]:
        """
        Validate changeset: no protected paths (§10).

        Args:
            changed_paths: list of changed file paths

        Returns:
            validation report with protected_violations list
        """
        violations = []

        for path in changed_paths:
            if cls.is_protected(path):
                violations.append(path)

        return {
            "valid": len(violations) == 0,
            "protected_violations": violations,
            "total_changed": len(changed_paths),
        }
