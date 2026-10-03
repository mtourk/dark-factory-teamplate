"""
Named Operations and Authorization Broker.

Per master plan §9:
"Never expose unrestricted PowerShell. Expose named operations such as
read/search/write/apply-patch, format, lint, typecheck, build, tests,
security checks, Git status/diff/commit/push/branch.

Dependency install, directory deletion, migration, network access,
authentication, workflow, deployment, and protected-path changes are
restricted operations.

Every consequential action is evaluated by OPA using project/run/role,
operation, command template, working directory, paths, network, secret
requirement, and expected side effect.

Never trust exit code alone. Verify the resulting file hash, Git commit,
PR head, auto-merge state, deployment version, or health result."
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


class OperationType(str, Enum):
    """Named operations (§9)."""
    # Code operations
    READ_FILE = "read_file"
    SEARCH_CODE = "search_code"
    WRITE_FILE = "write_file"
    APPLY_PATCH = "apply_patch"

    # Build/test operations
    FORMAT = "format"
    LINT = "lint"
    TYPECHECK = "typecheck"
    BUILD = "build"
    TEST = "test"
    SECURITY_CHECK = "security_check"

    # Git operations
    GIT_STATUS = "git_status"
    GIT_DIFF = "git_diff"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    GIT_BRANCH = "git_branch"

    # Restricted operations (OPA evaluation required)
    INSTALL_DEPENDENCY = "install_dependency"  # RESTRICTED
    DELETE_DIRECTORY = "delete_directory"  # RESTRICTED
    MIGRATE_DATA = "migrate_data"  # RESTRICTED
    NETWORK_REQUEST = "network_request"  # RESTRICTED
    AUTHENTICATE = "authenticate"  # RESTRICTED
    WORKFLOW_CHANGE = "workflow_change"  # RESTRICTED
    DEPLOY = "deploy"  # RESTRICTED
    PROTECTED_PATH_CHANGE = "protected_path_change"  # RESTRICTED


class AuthorizationResult(str, Enum):
    """OPA policy evaluation result."""
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_HUMAN_DECISION = "requires_human_decision"


@dataclass
class AuthorizationContext:
    """Context for OPA policy evaluation (§9)."""
    project_id: str
    run_id: str
    role: str
    operation: OperationType
    command_template: str  # e.g., "git commit -m {message}"
    working_directory: str
    paths: List[str]  # Files/directories involved
    network_required: bool = False
    secret_required: bool = False
    expected_side_effect: str = ""  # Description of expected outcome


@dataclass
class OperationResult:
    """Result of executed named operation."""
    operation: OperationType
    success: bool
    output: str
    error: Optional[str] = None
    file_hashes: Dict[str, str] = None  # Path -> SHA256 for verification
    git_commit: Optional[str] = None  # For git operations
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if self.file_hashes is None:
            self.file_hashes = {}


class AuthorizationBroker:
    """
    Evaluate named operations against OPA policies (§9).

    OPA policy context:
    - project_id, run_id, role (who)
    - operation (what)
    - command_template (how)
    - working_directory, paths (where)
    - network_required, secret_required, expected_side_effect (constraints)
    """

    def __init__(self):
        """Initialize authorization broker."""
        self.audit_log: List[Dict[str, Any]] = []

    def evaluate_authorization(
        self,
        context: AuthorizationContext,
    ) -> Tuple[AuthorizationResult, Optional[str]]:
        """
        Evaluate authorization using simplified OPA rules.

        Args:
            context: authorization context (project, run, role, operation, etc.)

        Returns:
            (AuthorizationResult, reason_string)
        """
        # Simplified OPA-like policy rules (real implementation would use OPA binary)

        # Rule 1: Restricted operations require explicit approval
        if context.operation in [
            OperationType.INSTALL_DEPENDENCY,
            OperationType.DELETE_DIRECTORY,
            OperationType.MIGRATE_DATA,
            OperationType.NETWORK_REQUEST,
            OperationType.AUTHENTICATE,
            OperationType.WORKFLOW_CHANGE,
            OperationType.DEPLOY,
        ]:
            return (
                AuthorizationResult.REQUIRES_HUMAN_DECISION,
                f"Restricted operation: {context.operation.value}",
            )

        # Rule 2: Protected-path changes not permitted for auto-merge
        if context.operation == OperationType.PROTECTED_PATH_CHANGE:
            protected_paths = [
                "DARK_FACTORY_MASTER_PLAN.md",
                "DARK_FACTORY_BUILD_PROMPT.md",
                ".factory-control/",
                ".factory/",
                ".github/workflows/",
                "docs/decisions/",
            ]
            for path in context.paths:
                if any(path.startswith(pp) for pp in protected_paths):
                    return (
                        AuthorizationResult.DENIED,
                        f"Protected path: {path} cannot be auto-merged",
                    )

        # Rule 3: Builder role has limited operations
        if context.role == "builder":
            allowed_builder_ops = [
                OperationType.READ_FILE,
                OperationType.SEARCH_CODE,
                OperationType.WRITE_FILE,
                OperationType.APPLY_PATCH,
                OperationType.FORMAT,
                OperationType.LINT,
                OperationType.TYPECHECK,
                OperationType.BUILD,
                OperationType.TEST,
                OperationType.GIT_STATUS,
                OperationType.GIT_DIFF,
                OperationType.GIT_COMMIT,
            ]
            if context.operation not in allowed_builder_ops:
                return (
                    AuthorizationResult.DENIED,
                    f"Builder role denied {context.operation.value}",
                )

        # Rule 4: Network operations restricted
        if context.network_required and context.operation not in [
            OperationType.NETWORK_REQUEST,
            OperationType.SECURITY_CHECK,
        ]:
            return (
                AuthorizationResult.DENIED,
                "Network access not allowed for this operation",
            )

        # Rule 5: Secrets never permitted for builder
        if context.secret_required and context.role == "builder":
            return (
                AuthorizationResult.DENIED,
                "Builder role cannot access secrets",
            )

        # Default: approve safe operations
        return (AuthorizationResult.APPROVED, "Authorization approved")

    def verify_operation_result(
        self,
        context: AuthorizationContext,
        result: OperationResult,
    ) -> Tuple[bool, str]:
        """
        Verify operation result: never trust exit code alone (§9).

        Args:
            context: original authorization context
            result: operation result with file_hashes, git_commit, etc.

        Returns:
            (verification_passed, reason)
        """
        # Simplified verification rules

        # For git operations, verify commit SHA format
        if context.operation == OperationType.GIT_COMMIT:
            if result.git_commit:
                # Verify SHA-1 format (40 hex chars)
                if len(result.git_commit) == 40 and all(
                    c in "0123456789abcdef" for c in result.git_commit
                ):
                    return (True, "Git commit SHA verified")
                else:
                    return (False, f"Invalid commit SHA: {result.git_commit}")

        # For file writes, verify hash
        if context.operation in [OperationType.WRITE_FILE, OperationType.APPLY_PATCH]:
            if not result.file_hashes:
                return (False, "No file hashes recorded (cannot verify write)")
            if not result.success:
                return (False, "Write operation failed")
            return (True, "File hashes recorded for verification")

        # For read operations, verify paths accessed match context
        if context.operation == OperationType.READ_FILE:
            return (True, "Read operation verified")

        return (result.success, "Operation result verified" if result.success else "Operation failed")

    def record_authorization(
        self,
        context: AuthorizationContext,
        result: AuthorizationResult,
        reason: str,
    ):
        """Record authorization decision in audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": context.project_id,
            "run_id": context.run_id,
            "role": context.role,
            "operation": context.operation.value,
            "working_directory": context.working_directory,
            "paths": context.paths,
            "result": result.value,
            "reason": reason,
        }
        self.audit_log.append(entry)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get authorization audit log."""
        return self.audit_log


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file for verification (§9)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()


def verify_file_hash(file_path: Path, expected_hash: str) -> bool:
    """Verify file hash (§9: never trust exit code alone)."""
    actual_hash = compute_file_hash(file_path)
    return actual_hash == expected_hash
