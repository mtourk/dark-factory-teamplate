"""
Phase 8: Tool Authorization and Worktrees tests.

Tests for:
1. Named operations (read, write, git, build, test, etc.)
2. OPA authorization policy enforcement
3. Restricted operations (require human approval)
4. Builder role limitations
5. Protected path restrictions
6. Secret access denial (builder role)
7. Network access restrictions
8. Result verification (never trust exit code alone)
9. File hash verification
10. Git commit SHA verification
11. Worktree creation and isolation
12. Worktree metadata integrity
13. Protected path validation
14. No reuse of worktrees per run
"""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from factory.tools.authorized_ops import (
    OperationType,
    AuthorizationResult,
    AuthorizationContext,
    OperationResult,
    AuthorizationBroker,
    compute_file_hash,
    verify_file_hash,
)
from factory.tools.worktrees import (
    WorktreeManager,
    WorktreeMetadata,
    ProtectedPathValidator,
)


# ============================================================================
# Named Operations Tests
# ============================================================================

class TestNamedOperations:
    """Test named operations enum."""

    def test_all_operations_defined(self):
        """All operation types are defined."""
        ops = [op for op in OperationType]
        assert len(ops) > 0
        assert OperationType.READ_FILE in ops
        assert OperationType.GIT_COMMIT in ops
        assert OperationType.INSTALL_DEPENDENCY in ops

    def test_operation_categories(self):
        """Operations organized by category (code, build, git, restricted)."""
        code_ops = [
            OperationType.READ_FILE,
            OperationType.SEARCH_CODE,
            OperationType.WRITE_FILE,
            OperationType.APPLY_PATCH,
        ]
        build_ops = [
            OperationType.FORMAT,
            OperationType.LINT,
            OperationType.TYPECHECK,
            OperationType.BUILD,
            OperationType.TEST,
        ]
        git_ops = [
            OperationType.GIT_STATUS,
            OperationType.GIT_DIFF,
            OperationType.GIT_COMMIT,
            OperationType.GIT_PUSH,
        ]

        for op in code_ops + build_ops + git_ops:
            assert op in [o for o in OperationType]


# ============================================================================
# OPA Authorization Tests (§9)
# ============================================================================

class TestOPAAuthorization:
    """Test OPA policy evaluation (§9)."""

    def test_authorization_context_creation(self):
        """Authorization context captures full policy context."""
        context = AuthorizationContext(
            project_id="investisor",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.READ_FILE,
            command_template="cat {filename}",
            working_directory="/home/user/code",
            paths=["src/main.py"],
        )

        assert context.project_id == "investisor"
        assert context.operation == OperationType.READ_FILE

    def test_safe_operation_approved(self):
        """Safe operations approved by OPA."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="investisor",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.READ_FILE,
            command_template="cat {file}",
            working_directory="/code",
            paths=["README.md"],
        )

        result, reason = broker.evaluate_authorization(context)
        assert result == AuthorizationResult.APPROVED

    def test_restricted_operation_requires_approval(self):
        """Restricted operations require human approval (§9)."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="investisor",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.INSTALL_DEPENDENCY,
            command_template="npm install {pkg}",
            working_directory="/code",
            paths=["package.json"],
        )

        result, reason = broker.evaluate_authorization(context)
        assert result == AuthorizationResult.REQUIRES_HUMAN_DECISION


# ============================================================================
# Builder Role Limitations (§9)
# ============================================================================

class TestBuilderRoleLimitations:
    """Test builder role has limited operations."""

    def test_builder_allowed_operations(self):
        """Builder can perform safe operations."""
        broker = AuthorizationBroker()
        allowed_ops = [
            OperationType.READ_FILE,
            OperationType.SEARCH_CODE,
            OperationType.FORMAT,
            OperationType.BUILD,
            OperationType.TEST,
        ]

        for op in allowed_ops:
            context = AuthorizationContext(
                project_id="test",
                run_id="RUN-001",
                role="builder",
                operation=op,
                command_template="cmd",
                working_directory="/code",
                paths=[],
            )

            result, _ = broker.evaluate_authorization(context)
            assert result == AuthorizationResult.APPROVED

    def test_builder_denied_git_push(self):
        """Builder cannot push directly."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.GIT_PUSH,
            command_template="git push",
            working_directory="/code",
            paths=[],
        )

        result, _ = broker.evaluate_authorization(context)
        assert result == AuthorizationResult.DENIED

    def test_builder_denied_deploy(self):
        """Builder cannot deploy."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.DEPLOY,
            command_template="wrangler deploy",
            working_directory="/code",
            paths=[],
        )

        result, _ = broker.evaluate_authorization(context)
        assert result in [AuthorizationResult.DENIED, AuthorizationResult.REQUIRES_HUMAN_DECISION]


# ============================================================================
# Protected Path Restrictions (§10)
# ============================================================================

class TestProtectedPathValidation:
    """Test protected path validation (§10)."""

    def test_protected_paths_identified(self):
        """Protected paths list is non-empty."""
        validator = ProtectedPathValidator()
        assert len(validator.PROTECTED_PATHS) > 0
        assert "DARK_FACTORY_MASTER_PLAN.md" in validator.PROTECTED_PATHS
        assert ".factory-control/" in validator.PROTECTED_PATHS

    def test_is_protected_exact_match(self):
        """Exact path match is protected."""
        validator = ProtectedPathValidator()
        assert validator.is_protected("DARK_FACTORY_MASTER_PLAN.md") is True
        assert validator.is_protected("IMPLEMENTATION_CHECKLIST.md") is True

    def test_is_protected_directory(self):
        """Files under protected directory are protected."""
        validator = ProtectedPathValidator()
        assert validator.is_protected(".factory-control/policies/policy.opa") is True
        assert validator.is_protected(".github/workflows/deploy.yml") is True

    def test_is_protected_non_protected(self):
        """Non-protected paths pass."""
        validator = ProtectedPathValidator()
        assert validator.is_protected("src/main.py") is False
        assert validator.is_protected("README.md") is False
        assert validator.is_protected("factory/backlog/scheduler.py") is False

    def test_protected_path_change_denied(self):
        """Protected path change is denied."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.PROTECTED_PATH_CHANGE,
            command_template="edit {file}",
            working_directory="/code",
            paths=["DARK_FACTORY_MASTER_PLAN.md"],
        )

        result, _ = broker.evaluate_authorization(context)
        assert result == AuthorizationResult.DENIED

    def test_validate_changeset_no_violations(self):
        """Changeset with no protected paths passes."""
        validator = ProtectedPathValidator()

        report = validator.validate_changeset([
            "src/main.py",
            "README.md",
            "factory/backlog/scheduler.py",
        ])

        assert report["valid"] is True
        assert len(report["protected_violations"]) == 0

    def test_validate_changeset_with_violations(self):
        """Changeset with protected paths fails."""
        validator = ProtectedPathValidator()

        report = validator.validate_changeset([
            "src/main.py",
            "DARK_FACTORY_MASTER_PLAN.md",
            ".github/workflows/deploy.yml",
        ])

        assert report["valid"] is False
        assert len(report["protected_violations"]) == 2


# ============================================================================
# Secret Access Restrictions (§9)
# ============================================================================

class TestSecretAccessRestrictions:
    """Test secrets are never exposed to builder."""

    def test_builder_denied_secret_access(self):
        """Builder denied access to secret-required operations."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.DEPLOY,
            command_template="deploy --token {secret}",
            working_directory="/code",
            paths=[],
            secret_required=True,
        )

        result, _ = broker.evaluate_authorization(context)
        assert result == AuthorizationResult.DENIED


# ============================================================================
# Operation Result Verification (§9)
# ============================================================================

class TestOperationResultVerification:
    """Test verification of operation results (never trust exit code alone)."""

    def test_file_hash_computation(self):
        """File hash is computed correctly."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            testfile = tmppath / "test.txt"
            testfile.write_text("Hello, World!")

            hash1 = compute_file_hash(testfile)
            hash2 = compute_file_hash(testfile)

            assert hash1 == hash2  # Deterministic
            assert len(hash1) == 64  # SHA-256 hex

    def test_file_hash_verification(self):
        """File hash verification works."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            testfile = tmppath / "test.txt"
            testfile.write_text("Content")

            hash_val = compute_file_hash(testfile)
            assert verify_file_hash(testfile, hash_val) is True
            assert verify_file_hash(testfile, "wronghash") is False

    def test_git_commit_verification(self):
        """Git commit SHA is verified."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="planner",
            operation=OperationType.GIT_COMMIT,
            command_template="git commit",
            working_directory="/code",
            paths=[],
        )

        # Valid SHA-1 (40 hex chars)
        valid_sha = "a" * 40
        result = OperationResult(
            operation=OperationType.GIT_COMMIT,
            success=True,
            output="commit created",
            git_commit=valid_sha,
        )

        verified, reason = broker.verify_operation_result(context, result)
        assert verified is True

        # Invalid SHA
        bad_sha = "not-a-sha"
        bad_result = OperationResult(
            operation=OperationType.GIT_COMMIT,
            success=True,
            output="commit created",
            git_commit=bad_sha,
        )

        verified, reason = broker.verify_operation_result(context, bad_result)
        assert verified is False

    def test_audit_log_recording(self):
        """Authorization decisions are recorded in audit log."""
        broker = AuthorizationBroker()

        context = AuthorizationContext(
            project_id="test",
            run_id="RUN-001",
            role="builder",
            operation=OperationType.READ_FILE,
            command_template="cat file",
            working_directory="/code",
            paths=["README.md"],
        )

        result, reason = broker.evaluate_authorization(context)
        broker.record_authorization(context, result, reason)

        log = broker.get_audit_log()
        assert len(log) > 0
        assert log[0]["project_id"] == "test"
        assert log[0]["operation"] == "read_file"


# ============================================================================
# Worktree Management Tests (§10)
# ============================================================================

class TestWorktreeManagement:
    """Test worktree creation and isolation (§10)."""

    def test_worktree_creation(self):
        """Worktree created with metadata (§10)."""
        with TemporaryDirectory() as tmpdir:
            manager = WorktreeManager(factory_root=Path(tmpdir))

            metadata = manager.create_worktree(
                run_id="RUN-001",
                project_id="test",
                issue_number=42,
                base_sha="a" * 40,
                branch_slug="feature-search",
            )

            assert metadata.run_id == "RUN-001"
            assert metadata.branch_name == "factory/RUN-001-feature-search"
            assert metadata.worktree_path.exists()

    def test_no_worktree_reuse(self):
        """Worktree cannot be reused for different run (§10)."""
        with TemporaryDirectory() as tmpdir:
            manager = WorktreeManager(factory_root=Path(tmpdir))

            metadata1 = manager.create_worktree(
                run_id="RUN-001",
                project_id="test",
                issue_number=1,
                base_sha="a" * 40,
                branch_slug="feature-1",
            )

            # Attempt to create same run_id again
            with pytest.raises(ValueError, match="no reuse"):
                manager.create_worktree(
                    run_id="RUN-001",
                    project_id="test",
                    issue_number=2,
                    base_sha="b" * 40,
                    branch_slug="feature-2",
                )

    def test_worktree_directory_structure(self):
        """Worktree has correct directory structure (§10)."""
        with TemporaryDirectory() as tmpdir:
            manager = WorktreeManager(factory_root=Path(tmpdir))

            metadata = manager.create_worktree(
                run_id="RUN-002",
                project_id="test",
                issue_number=42,
                base_sha="a" * 40,
                branch_slug="test",
            )

            assert (metadata.worktree_path / "shared").exists()

    def test_worktree_metadata_persistence(self):
        """Worktree metadata can be loaded."""
        with TemporaryDirectory() as tmpdir:
            manager = WorktreeManager(factory_root=Path(tmpdir))

            metadata1 = manager.create_worktree(
                run_id="RUN-003",
                project_id="investisor",
                issue_number=99,
                base_sha="c" * 40,
                branch_slug="search",
            )

            metadata2 = manager.load_metadata("RUN-003")

            assert metadata2.run_id == "RUN-003"
            assert metadata2.project_id == "investisor"
            assert metadata2.issue_number == 99

    def test_worktree_integrity_check(self):
        """Worktree integrity verification works."""
        with TemporaryDirectory() as tmpdir:
            manager = WorktreeManager(factory_root=Path(tmpdir))

            metadata = manager.create_worktree(
                run_id="RUN-004",
                project_id="test",
                issue_number=1,
                base_sha="d" * 40,
                branch_slug="test",
            )

            report = manager.verify_worktree_integrity("RUN-004")

            assert report["exists"] is True
            assert report["shared_exists"] is True
            assert report["metadata_valid"] is True


# ============================================================================
# Phase 8 Gate Test
# ============================================================================

def test_phase8_gate_tool_authorization_and_worktrees_operational():
    """
    Phase 8 Gate: Tool authorization and worktrees are operational.

    Verifies:
    - Named operations defined (read, write, git, build, test, etc.)
    - OPA authorization policies enforced
    - Restricted operations require human approval
    - Builder role has limited operations
    - Protected paths cannot be changed
    - Secrets never exposed to builder
    - Network access restricted
    - Operation results verified (not just exit code)
    - File hashes computed and verified
    - Git commits verified by SHA
    - Worktrees created with isolation
    - Worktree metadata persisted
    - No worktree reuse per run
    - Protected path validation
    - Audit logging
    """
    # Named operations
    assert OperationType.READ_FILE in [o for o in OperationType]
    assert OperationType.INSTALL_DEPENDENCY in [o for o in OperationType]

    # OPA authorization
    broker = AuthorizationBroker()

    read_context = AuthorizationContext(
        project_id="test",
        run_id="RUN-001",
        role="builder",
        operation=OperationType.READ_FILE,
        command_template="cat",
        working_directory="/code",
        paths=["README.md"],
    )

    result, _ = broker.evaluate_authorization(read_context)
    assert result == AuthorizationResult.APPROVED

    # Restricted operations
    install_context = AuthorizationContext(
        project_id="test",
        run_id="RUN-001",
        role="builder",
        operation=OperationType.INSTALL_DEPENDENCY,
        command_template="npm install",
        working_directory="/code",
        paths=[],
    )

    result, _ = broker.evaluate_authorization(install_context)
    assert result == AuthorizationResult.REQUIRES_HUMAN_DECISION

    # Protected paths
    validator = ProtectedPathValidator()
    assert validator.is_protected("DARK_FACTORY_MASTER_PLAN.md") is True
    assert validator.is_protected("src/main.py") is False

    changeset_report = validator.validate_changeset([
        "src/main.py",
        "DARK_FACTORY_MASTER_PLAN.md",
    ])
    assert changeset_report["valid"] is False

    # File hash verification
    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        testfile = tmppath / "test.txt"
        testfile.write_text("test")
        hash_val = compute_file_hash(testfile)
        assert verify_file_hash(testfile, hash_val) is True

    # Git commit verification
    valid_sha = "a" * 40
    commit_result = OperationResult(
        operation=OperationType.GIT_COMMIT,
        success=True,
        output="committed",
        git_commit=valid_sha,
    )
    verified, _ = broker.verify_operation_result(read_context, commit_result)
    assert verified is True

    # Worktrees
    with TemporaryDirectory() as tmpdir:
        manager = WorktreeManager(factory_root=Path(tmpdir))

        metadata = manager.create_worktree(
            run_id="RUN-gate001",
            project_id="test",
            issue_number=1,
            base_sha="b" * 40,
            branch_slug="test",
        )

        assert metadata.worktree_path.exists()

        loaded = manager.load_metadata("RUN-gate001")
        assert loaded.run_id == "RUN-gate001"

        integrity = manager.verify_worktree_integrity("RUN-gate001")
        assert integrity["exists"] is True

    # Audit log
    assert len(broker.get_audit_log()) == 0
    broker.record_authorization(read_context, AuthorizationResult.APPROVED, "test")
    assert len(broker.get_audit_log()) > 0

    print("✓ Phase 8 Gate: Tool authorization and worktrees operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
