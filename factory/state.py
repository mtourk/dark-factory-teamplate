"""
SQLite state management for FactoryFlow orchestrator.

Tracks: projects, runs, stages, attempts, worktrees, branches, PRs,
deployments, decisions, evidence, leases, claims, and quarantines.

Per §4.4: "A resumed run must verify real Git/GitHub/deployment state
and must not repeat a consequential action without an idempotency check."
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    ForeignKey, Index, UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from factory.profiles import get_factory_root

# SQLite database location (§6.6 storage). FF-P01-01: resolved via
# factory/profiles.py (FACTORY_ROOT env var, else ~/.factory) instead of a
# hardcoded Windows path, so this module works unmodified on Windows/macOS/Linux.
DB_PATH = get_factory_root() / "state.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

Base = declarative_base()

# FB-12: the SQLAlchemy engine/session are created lazily (on first use) and
# honor the FACTORY_DB env var, rather than binding a process-wide on-disk
# engine at import time. This lets tests inject an isolated/in-memory database
# (conftest.py sets FACTORY_DB=":memory:") instead of silently sharing the real
# <factory_root>/state.db file across the whole test session.
_engine = None
_session_local = None


def _resolve_db_url() -> str:
    """Resolve the SQLite URL used for the engine.

    FACTORY_DB overrides the default on-disk path:
      - ":memory:"      → a shared in-memory DB (isolated to this process)
      - "/path/to.db"   → that file
      - unset           → DB_PATH (<factory_root>/state.db)
    """
    override = os.environ.get("FACTORY_DB")
    if override == ":memory:":
        return "sqlite:///:memory:"
    if override:
        return f"sqlite:///{override}"
    return f"sqlite:///{DB_PATH}"


def get_engine():
    """Return the process engine, creating it lazily on first use."""
    global _engine
    if _engine is None:
        url = _resolve_db_url()
        if url == "sqlite:///:memory:":
            # Keep a single shared connection so the in-memory schema and data
            # survive across sessions within the same process.
            _engine = create_engine(
                url,
                echo=False,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            _engine = create_engine(url, echo=False)
    return _engine


def _get_session_local():
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(bind=get_engine())
    return _session_local


def configure_engine(db_url: Optional[str] = None):
    """(Re)configure the engine. Intended for tests.

    Disposes any existing engine and clears the cached sessionmaker so the next
    DB call rebuilds from FACTORY_DB/DB_PATH (or the explicit `db_url`).
    """
    global _engine, _session_local
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_local = None
    if db_url is not None:
        value = db_url[len("sqlite:///"):] if db_url.startswith("sqlite:///") else db_url
        os.environ["FACTORY_DB"] = value
    return get_engine()


# ============================================================================
# Models (SQLAlchemy ORM)
# ============================================================================

class Project(Base):
    """Factory project configuration."""
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)  # e.g., "investisor"
    github_repo = Column(String(512), unique=True, nullable=False)  # e.g., "https://github.com/mtourk/investisor"
    target_branch = Column(String(128), default="main")
    created_at = Column(DateTime, default=datetime.utcnow)



class Run(Base):
    """One factory run (issue → PR → merge → deploy → close)."""
    __tablename__ = "runs"

    id = Column(String(64), primary_key=True)  # e.g., "RUN-20261003"
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    issue_number = Column(Integer, nullable=False)
    status = Column(String(32), default="claimed")  # claimed, analyzing, planning, implementing, verifying, repairing, reviewing, merging, deploying, validating, closed, failed, quarantined

    # Git/GitHub state
    branch_name = Column(String(256))  # factory/RUN-...-slug
    worktree_path = Column(String(512))  # <factory_root>/worktrees/RUN-... (factory/profiles.py:get_factory_root)
    base_sha = Column(String(40))  # main at claim time
    head_sha = Column(String(40))  # final commit
    pr_number = Column(Integer)

    # Execution tracking
    stage = Column(String(32))  # current stage (claim, analyze, plan, build, verify, repair, review, merge, deploy)
    attempts = Column(Integer, default=0)
    max_repairs = Column(Integer, default=3)
    repair_count = Column(Integer, default=0)

    # Models and sessions
    current_role = Column(String(32))  # analyst, builder, reviewer, etc.
    session_id = Column(String(128))  # API session for role

    # Evidence and decisions
    compiled_intent_id = Column(String(128))
    evidence_id = Column(String(128))
    context_manifest_id = Column(String(128))
    decision_required = Column(Boolean, default=False)
    decision_required_reason = Column(Text)

    # Deployment
    preview_url = Column(String(512))
    preview_health = Column(Boolean)
    deployed_sha = Column(String(40))
    production_health = Column(String(32))  # healthy, degraded, failed, unknown

    # Timing
    claimed_at = Column(DateTime, default=datetime.utcnow)
    lease_heartbeat = Column(DateTime)
    completed_at = Column(DateTime)

    # Immutable record
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "issue_number", name="uq_project_issue"),
        Index("idx_status", "status"),
        Index("idx_project_id", "project_id"),
    )


class Stage(Base):
    """Execution of one stage within a run."""
    __tablename__ = "stages"

    id = Column(String(128), primary_key=True)  # e.g., "RUN-20261003-analyze-1"
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)
    stage_name = Column(String(32), nullable=False)  # analyze, plan, implement, etc.
    attempt = Column(Integer, default=1)

    # Input/output
    input_schema = Column(JSON)
    output_schema = Column(JSON)

    # Execution
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    status = Column(String(32))  # running, passed, failed, timeout
    error_message = Column(Text)

    # For repair
    previous_patch_digest = Column(String(64))  # SHA-256 of last patch tried

    created_at = Column(DateTime, default=datetime.utcnow)


class Claim(Base):
    """Atomic claim on an issue (prevents race conditions, §5)."""
    __tablename__ = "claims"

    id = Column(String(128), primary_key=True)  # e.g., "claim-issue-42-run-123"
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    issue_number = Column(Integer, nullable=False)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)

    # Lease tracking
    lease_owner = Column(String(128))  # hostname/process ID
    lease_status = Column(String(32))  # active, stale, released
    heartbeat = Column(DateTime)  # last update
    ttl_seconds = Column(Integer, default=1800)  # 30 minutes

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "issue_number", name="uq_claim_issue"),
    )


class Decision(Base):
    """Strategic ambiguity requiring human decision."""
    __tablename__ = "decisions"

    id = Column(String(128), primary_key=True)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)

    question = Column(Text, nullable=False)  # What needs deciding?
    context = Column(Text)  # Background
    options = Column(JSON)  # List of choices
    recommendation = Column(Text)  # What factory recommends

    # Decision record
    decided = Column(Boolean, default=False)
    decided_by = Column(String(128))  # who decided
    chosen_option = Column(String(256))
    decided_at = Column(DateTime)
    reasoning = Column(Text)  # why this option

    created_at = Column(DateTime, default=datetime.utcnow)


class Evidence(Base):
    """Evidence manifest for one run (Phase 15)."""
    __tablename__ = "evidence"

    id = Column(String(128), primary_key=True)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False, unique=True)

    # SHAs
    base_sha = Column(String(40))
    head_sha = Column(String(40))
    deployed_sha = Column(String(40))

    # Gates (all must pass for auto-merge, §14)
    intent_validation = Column(Boolean, default=False)
    authority_check = Column(Boolean, default=False)
    protected_paths = Column(Boolean, default=False)
    format_check = Column(Boolean, default=False)
    lint_check = Column(Boolean, default=False)
    typecheck_check = Column(Boolean, default=False)
    build_check = Column(Boolean, default=False)
    unit_tests = Column(Boolean, default=False)
    contract_tests = Column(Boolean, default=False)
    integration_tests = Column(Boolean, default=False)
    security_check = Column(Boolean, default=False)
    mutation_testing = Column(Boolean, default=False)
    sealed_qa = Column(Boolean, default=False)
    independent_review = Column(Boolean, default=False)
    preview_deploy = Column(Boolean, default=False)

    # Results
    test_results = Column(JSON)  # {unit: {passed, failed}, ...}
    security_results = Column(JSON)
    mutation_results = Column(JSON)  # {total, killed, survived, survival_rate}
    review_findings = Column(JSON)

    # Traceability
    requirements_demonstrated = Column(JSON)  # list of req IDs
    context_packages = Column(JSON)  # [{package_id, role, hash}, ...]

    # Manifest
    manifest_hash = Column(String(64))  # SHA-256 of entire manifest

    created_at = Column(DateTime, default=datetime.utcnow)


class Quarantine(Base):
    """Incident quarantine (bad deployment, unknown state, §15)."""
    __tablename__ = "quarantine"

    id = Column(String(128), primary_key=True)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)

    incident_type = Column(String(64))  # bad_deployment, unknown_state, health_check_failed
    bad_sha = Column(String(40))  # what went wrong
    reason = Column(Text)

    # Recovery
    recovery_procedure = Column(Text)  # ADR reference or approved steps
    last_known_good_sha = Column(String(40))
    recovery_attempted = Column(Boolean, default=False)
    recovery_status = Column(String(32))  # pending, in_progress, resolved

    created_at = Column(DateTime, default=datetime.utcnow)


class EmergencyStop(Base):
    """Emergency stop state (§15)."""
    __tablename__ = "emergency_stop"

    id = Column(String(128), primary_key=True)

    active = Column(Boolean, default=False)
    reason = Column(Text)
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class TaskCheckpoint(Base):
    """Durable, resumable snapshot of where a task/run is (FF-P21-02, plan §40).

    A checkpoint is written after each meaningful step/side-effect so that a
    different model/provider can continue from the exact point of failure
    rather than restarting. State is stored model-neutrally (structured JSON),
    not as natural-language conversation (plan §52).
    """
    __tablename__ = "task_checkpoints"

    id = Column(String(128), primary_key=True)  # e.g. "RUN-...-step-5"
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)
    task_id = Column(String(128))
    agent_id = Column(String(64))  # role/agent that produced this checkpoint

    step_id = Column(String(64))
    step_status = Column(String(32))  # pending, in_progress, completed, failed

    # Structured, model-neutral state
    input_state = Column(JSON)
    output_state = Column(JSON)
    completed_actions = Column(JSON)   # list of actions already done
    pending_actions = Column(JSON)     # list of actions still to do
    current_files = Column(JSON)       # files relevant to the current step
    modified_files = Column(JSON)      # files already changed this task

    # Repository continuity (plan §53)
    git_commit = Column(String(40))
    git_diff_hash = Column(String(64))

    # Context / memory / handoff (populated more fully in later phases)
    context_snapshot = Column(JSON)
    memory_snapshot = Column(JSON)
    handoff_summary = Column(Text)

    last_successful_operation = Column(Text)
    current_operation = Column(Text)
    resume_instructions = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_checkpoint_run", "run_id"),
    )


class AgentRun(Base):
    """One agent execution attempt against a task (FF-P21-02, plan §41).

    Kept separate from the task/Run status: an attempt can FAIL while the task
    remains resumable (plan §39). provider/credential/model are nullable until
    the gateway lands (FF-P22-01).
    """
    __tablename__ = "agent_runs"

    id = Column(String(128), primary_key=True)
    agent_id = Column(String(64))
    task_id = Column(String(128))
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False)

    model = Column(String(128))
    provider = Column(String(64))
    credential = Column(String(128))  # credential id/alias, never a secret value

    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)

    status = Column(String(32))  # pending, running, succeeded, failed, cancelled, rate_limited, quota_exhausted, timed_out
    attempt_number = Column(Integer, default=1)

    input_tokens = Column(Integer)
    output_tokens = Column(Integer)

    failure_reason = Column(Text)
    checkpoint_id = Column(String(128), ForeignKey("task_checkpoints.id"))

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_agentrun_run", "run_id"),
    )


class LLMRequest(Base):
    """One LLM request attempt, for observability + routing analytics (plan §42).

    Written by the gateway (FF-P22-01) / observability layer (FF-P23-01); the
    schema is created here as part of the state foundation so later phases only
    add writers, not migrations.
    """
    __tablename__ = "llm_requests"

    request_id = Column(String(128), primary_key=True)
    run_id = Column(String(64), ForeignKey("runs.id"))
    task_id = Column(String(128))
    agent_id = Column(String(64))
    attempt_id = Column(String(128))

    provider = Column(String(64))
    credential = Column(String(128))  # credential id/alias, never a secret value
    model = Column(String(128))

    task_type = Column(String(64))

    context_tokens = Column(Integer)
    input_tokens = Column(Integer)
    expected_output_tokens = Column(Integer)
    actual_output_tokens = Column(Integer)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    status = Column(String(32))
    fallback_reason = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_llmrequest_run", "run_id"),
        Index("idx_llmrequest_provider", "provider"),
    )


# ============================================================================
# Database Functions
# ============================================================================

def init_db() -> Session:
    """Initialize database schema and return session."""
    Base.metadata.create_all(get_engine())
    return _get_session_local()()


def get_db_session() -> Session:
    """Get a new database session."""
    return _get_session_local()()


def close_db_session(session: Session) -> None:
    """Close database session."""
    session.close()


def is_claim_stale(claim: Claim) -> bool:
    """Check if claim lease has expired (§5 stale recovery)."""
    if not claim.heartbeat:
        return True
    stale_time = claim.heartbeat + timedelta(seconds=claim.ttl_seconds)
    return datetime.utcnow() > stale_time


def update_lease_heartbeat(claim: Claim, session: Session) -> None:
    """Update claim lease heartbeat (keep-alive for long operations)."""
    claim.heartbeat = datetime.utcnow()
    session.commit()


def attempt_claim(
    project_id: str,
    issue_number: int,
    run_id: str,
    session: Session,
) -> Optional[Claim]:
    """
    Attempt atomic claim on issue (§5).

    Returns: Claim if successful, None if already claimed.
    Fails hard if race condition detected (concurrent claims).
    """
    existing = session.query(Claim).filter(
        Claim.project_id == project_id,
        Claim.issue_number == issue_number,
    ).first()

    if existing:
        if is_claim_stale(existing):
            # Stale claim: recover by reassigning the EXISTING row to the new
            # run. There is a unique constraint on (project_id, issue_number),
            # so inserting a second claim row for the same issue would violate
            # it — the stale lease must be taken over in place, which is also
            # the correct "one active claim per issue" semantics.
            existing.run_id = run_id
            existing.lease_owner = f"factory-{run_id}"
            existing.lease_status = "active"
            existing.heartbeat = datetime.utcnow()
            session.commit()
            return existing
        else:
            # Active claim: cannot claim
            return None

    # No existing claim: create new
    claim = Claim(
        id=f"claim-{project_id}-{issue_number}-{run_id}",
        project_id=project_id,
        issue_number=issue_number,
        run_id=run_id,
        lease_owner=f"factory-{run_id}",
        lease_status="active",
        heartbeat=datetime.utcnow(),
    )
    session.add(claim)
    session.commit()
    return claim


def release_claim(claim: Claim, session: Session) -> None:
    """Release a claim (issue is now eligible for other runs)."""
    claim.lease_status = "released"
    session.commit()


def is_emergency_stopped(session: Session) -> bool:
    """Check if emergency stop is active."""
    stop = session.query(EmergencyStop).filter(EmergencyStop.active == True).first()
    return stop is not None


def activate_emergency_stop(reason: str, session: Session) -> None:
    """Activate emergency stop (blocks new claims, disables pending auto-merges)."""
    stop = EmergencyStop(
        id=f"stop-{datetime.utcnow().isoformat()}",
        active=True,
        reason=reason,
        activated_at=datetime.utcnow(),
    )
    session.add(stop)
    session.commit()


def deactivate_emergency_stop(session: Session) -> None:
    """Deactivate emergency stop (explicit resume required per §15)."""
    stops = session.query(EmergencyStop).filter(EmergencyStop.active == True).all()
    for stop in stops:
        stop.active = False
        stop.deactivated_at = datetime.utcnow()
    session.commit()


# ============================================================================
# Run lifecycle persistence (FF-P21-01)
# ============================================================================

def ensure_project(
    session: Session,
    project_id: str,
    github_repo: str,
    target_branch: str = "main",
) -> Project:
    """Return the Project row for `project_id`, creating it if absent.

    `github_repo` is required/unique on first creation; on later calls the
    existing row is returned unchanged.
    """
    project = session.query(Project).filter(Project.id == project_id).first()
    if project is None:
        project = Project(
            id=project_id,
            github_repo=github_repo,
            target_branch=target_branch,
        )
        session.add(project)
        session.commit()
    return project


def create_or_reset_run(
    session: Session,
    run_id: str,
    project_id: str,
    issue_number: int,
    status: str = "implementing",
    stage: str = "build",
) -> Run:
    """Create a Run row, or reset the existing one for (project, issue).

    There is a unique constraint on (project_id, issue_number), so
    re-processing the same issue reuses the existing row (keeping its id)
    instead of failing. The row is reset to a fresh, resumable start state.
    """
    now = datetime.utcnow()
    existing = session.query(Run).filter(
        Run.project_id == project_id,
        Run.issue_number == issue_number,
    ).first()

    if existing is not None:
        existing.status = status
        existing.stage = stage
        existing.attempts = 0
        existing.repair_count = 0
        existing.completed_at = None
        existing.lease_heartbeat = now
        session.commit()
        return existing

    run = Run(
        id=run_id,
        project_id=project_id,
        issue_number=issue_number,
        status=status,
        stage=stage,
        attempts=0,
        repair_count=0,
        claimed_at=now,
        lease_heartbeat=now,
    )
    session.add(run)
    session.commit()
    return run


def update_run(session: Session, run_id: str, **fields) -> Optional[Run]:
    """Patch columns on a Run row and commit. Unknown keys are ignored."""
    run = session.query(Run).filter(Run.id == run_id).first()
    if run is None:
        return None
    for key, value in fields.items():
        if hasattr(run, key):
            setattr(run, key, value)
    run.lease_heartbeat = datetime.utcnow()
    session.commit()
    return run


def record_stage(
    session: Session,
    run_id: str,
    stage_name: str,
    attempt: int,
    status: str,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
    output_schema: Optional[dict] = None,
    previous_patch_digest: Optional[str] = None,
) -> Stage:
    """Upsert a Stage execution record for a run.

    Uses merge keyed on a deterministic id (`<run>-<stage>-<attempt>`) so that
    re-running the same stage/attempt (e.g. after a crash + resume) updates the
    row rather than violating the primary key — a small step toward the
    idempotent-resume requirement in §4.4.
    """
    stage = Stage(
        id=f"{run_id}-{stage_name}-{attempt}",
        run_id=run_id,
        stage_name=stage_name,
        attempt=attempt,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        error_message=error_message,
        output_schema=output_schema,
        previous_patch_digest=previous_patch_digest,
    )
    merged = session.merge(stage)
    session.commit()
    return merged


# ============================================================================
# Checkpoint & resume (FF-P21-02)
# ============================================================================

# Run statuses that mean a run was interrupted mid-flight and can be resumed.
RESUMABLE_STATUSES = ("implementing", "verifying", "repairing", "analyzing", "planning")
TERMINAL_STATUSES = ("closed", "failed", "quarantined")


def save_checkpoint(
    session: Session,
    run_id: str,
    step_id: str,
    step_status: str,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    modified_files: Optional[list] = None,
    current_files: Optional[list] = None,
    completed_actions: Optional[list] = None,
    pending_actions: Optional[list] = None,
    git_commit: Optional[str] = None,
    git_diff_hash: Optional[str] = None,
    output_state: Optional[dict] = None,
    last_successful_operation: Optional[str] = None,
    current_operation: Optional[str] = None,
    resume_instructions: Optional[str] = None,
) -> TaskCheckpoint:
    """Upsert a durable checkpoint for a run step.

    Keyed on `<run_id>-<step_id>` so re-checkpointing the same step updates the
    row (idempotent resume). Returns the persisted checkpoint.
    """
    checkpoint = TaskCheckpoint(
        id=f"{run_id}-{step_id}",
        run_id=run_id,
        task_id=task_id,
        agent_id=agent_id,
        step_id=step_id,
        step_status=step_status,
        modified_files=modified_files,
        current_files=current_files,
        completed_actions=completed_actions,
        pending_actions=pending_actions,
        git_commit=git_commit,
        git_diff_hash=git_diff_hash,
        output_state=output_state,
        last_successful_operation=last_successful_operation,
        current_operation=current_operation,
        resume_instructions=resume_instructions,
    )
    merged = session.merge(checkpoint)
    session.commit()
    return merged


def latest_checkpoint(session: Session, run_id: str) -> Optional[TaskCheckpoint]:
    """Return the most recently updated checkpoint for a run, if any."""
    return (
        session.query(TaskCheckpoint)
        .filter(TaskCheckpoint.run_id == run_id)
        .order_by(TaskCheckpoint.updated_at.desc())
        .first()
    )


def list_resumable_runs(session: Session, project_id: Optional[str] = None) -> list:
    """Return runs that were interrupted mid-flight (non-terminal status).

    These are candidates for `factory resume`. Optionally scoped to one project.
    """
    query = session.query(Run).filter(Run.status.in_(RESUMABLE_STATUSES))
    if project_id is not None:
        query = query.filter(Run.project_id == project_id)
    return query.order_by(Run.claimed_at.asc()).all()


def get_run(session: Session, run_id: str) -> Optional[Run]:
    """Fetch one Run row by id."""
    return session.query(Run).filter(Run.id == run_id).first()


def list_stages(session: Session, run_id: str) -> list:
    """Return all Stage rows for a run, oldest first."""
    return (
        session.query(Stage)
        .filter(Stage.run_id == run_id)
        .order_by(Stage.created_at.asc())
        .all()
    )


if __name__ == "__main__":
    # Initialize database if running this module directly
    init_db()
    print(f"Database initialized at {DB_PATH}")
