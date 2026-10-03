"""
SQLite state management for FactoryFlow orchestrator.

Tracks: projects, runs, stages, attempts, worktrees, branches, PRs,
deployments, decisions, evidence, leases, claims, and quarantines.

Per §4.4: "A resumed run must verify real Git/GitHub/deployment state
and must not repeat a consequential action without an idempotency check."
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    ForeignKey, Index, UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# SQLite database location (§6.6 storage)
DB_PATH = Path("C:/Factory/state.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


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
    worktree_path = Column(String(512))  # C:\Factory\worktrees\RUN-...
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


# ============================================================================
# Database Functions
# ============================================================================

def init_db() -> Session:
    """Initialize database schema and return session."""
    Base.metadata.create_all(engine)
    return SessionLocal()


def get_db_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


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
            # Stale claim: recover and reuse
            existing.lease_status = "stale"
            new_claim = Claim(
                id=f"claim-{project_id}-{issue_number}-{run_id}",
                project_id=project_id,
                issue_number=issue_number,
                run_id=run_id,
                lease_owner=f"factory-{run_id}",
                lease_status="active",
                heartbeat=datetime.utcnow(),
            )
            session.add(new_claim)
            session.commit()
            return new_claim
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


if __name__ == "__main__":
    # Initialize database if running this module directly
    init_db()
    print(f"Database initialized at {DB_PATH}")
