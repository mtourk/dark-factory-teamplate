"""
FF-P21-01: durable run/stage persistence + FB-12 (engine honors FACTORY_DB).

Covers:
- state._resolve_db_url honors the FACTORY_DB env var.
- A shared in-memory engine is visible across sessions (StaticPool), so
  init_db() + a later get_db_session() see the same data.
- ensure_project / create_or_reset_run / record_stage behave idempotently and
  respect the (project, issue) and stage-id uniqueness.
- ImplementationOrchestrator persists the run lifecycle when given a session,
  and is a no-op when not.
"""

from datetime import datetime

import pytest

from factory import state
from factory.implementation.orchestrator import (
    ImplementationOrchestrator,
    ImplementationPhase,
)


class _DummyBuilder:
    """start_implementation / finalize_run never touch the builder."""


# ---------------------------------------------------------------------------
# FB-12: engine configuration
# ---------------------------------------------------------------------------

def test_resolve_db_url_honors_factory_db(monkeypatch):
    monkeypatch.setenv("FACTORY_DB", ":memory:")
    assert state._resolve_db_url() == "sqlite:///:memory:"

    monkeypatch.setenv("FACTORY_DB", "/tmp/factory-test.db")
    assert state._resolve_db_url() == "sqlite:////tmp/factory-test.db"

    monkeypatch.delenv("FACTORY_DB", raising=False)
    assert state._resolve_db_url().endswith("state.db")


def test_in_memory_engine_shared_across_sessions():
    """StaticPool keeps one connection so schema+rows survive across sessions."""
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")

    other = state.get_db_session()
    assert other.query(state.Project).count() == 1


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def test_ensure_project_is_idempotent():
    session = state.init_db()
    p1 = state.ensure_project(session, "proj", "https://github.com/x/proj")
    p2 = state.ensure_project(session, "proj", "https://github.com/x/proj")
    assert p1.id == p2.id
    assert session.query(state.Project).count() == 1


def test_create_or_reset_run_reuses_row_for_same_issue():
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")

    r1 = state.create_or_reset_run(session, "RUN-1", "proj", 7)
    assert r1.status == "implementing"

    # Simulate progress, then re-process the same issue.
    r1.status = "failed"
    r1.attempts = 3
    session.commit()

    r2 = state.create_or_reset_run(session, "RUN-2", "proj", 7)
    assert r2.id == "RUN-1"               # existing row reused (unique project+issue)
    assert r2.status == "implementing"    # reset to a fresh, resumable state
    assert r2.attempts == 0
    assert session.query(state.Run).filter_by(project_id="proj", issue_number=7).count() == 1


def test_record_stage_upserts_on_same_attempt():
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")
    state.create_or_reset_run(session, "RUN-1", "proj", 7)

    state.record_stage(session, "RUN-1", "build", 1, "running", started_at=datetime.utcnow())
    s2 = state.record_stage(session, "RUN-1", "build", 1, "passed", started_at=datetime.utcnow())

    assert session.query(state.Stage).filter_by(run_id="RUN-1").count() == 1
    assert s2.status == "passed"


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------

def test_orchestrator_persists_run_lifecycle():
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")
    orch = ImplementationOrchestrator(_DummyBuilder(), state_session=session)

    run = orch.start_implementation(
        run_id="RUN-1", issue_number=7, project_id="proj",
        requirement_summary="", allowed_fix_scope="",
    )
    row = session.query(state.Run).filter_by(id="RUN-1").one()
    assert row.status == "implementing"
    assert run.persisted_run_id == "RUN-1"

    orch.finalize_run(run, ImplementationPhase.COMPLETE)
    session.refresh(row)
    assert row.status == "closed"
    assert row.completed_at is not None


def test_orchestrator_without_session_persists_nothing():
    """Default (no session) must not create any Run rows."""
    session = state.init_db()  # a separate inspection session
    orch = ImplementationOrchestrator(_DummyBuilder())  # no state_session
    orch.start_implementation(
        run_id="RUN-X", issue_number=99, project_id="proj",
        requirement_summary="", allowed_fix_scope="",
    )
    assert session.query(state.Run).count() == 0


# ---------------------------------------------------------------------------
# FF-P21-02: checkpoints & resume
# ---------------------------------------------------------------------------

def _seed_run(session, run_id="RUN-1", project="proj", issue=7, status="implementing"):
    state.ensure_project(session, project, f"https://github.com/x/{project}")
    return state.create_or_reset_run(session, run_id, project, issue, status=status)


def test_save_checkpoint_upserts_and_latest_returns_newest():
    session = state.init_db()
    _seed_run(session)

    state.save_checkpoint(
        session, "RUN-1", step_id="attempt-1-applied", step_status="in_progress",
        modified_files=["a.py"], current_operation="verify",
    )
    # Same step id -> upsert (no second row).
    state.save_checkpoint(
        session, "RUN-1", step_id="attempt-1-applied", step_status="completed",
        modified_files=["a.py", "b.py"], current_operation="review",
    )
    assert session.query(state.TaskCheckpoint).filter_by(run_id="RUN-1").count() == 1

    cp = state.latest_checkpoint(session, "RUN-1")
    assert cp.step_status == "completed"
    assert cp.modified_files == ["a.py", "b.py"]
    assert cp.current_operation == "review"


def test_list_resumable_runs_excludes_terminal():
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")
    state.create_or_reset_run(session, "RUN-A", "proj", 1, status="implementing")
    state.create_or_reset_run(session, "RUN-B", "proj", 2, status="verifying")
    state.create_or_reset_run(session, "RUN-C", "proj", 3, status="closed")
    state.create_or_reset_run(session, "RUN-D", "proj", 4, status="failed")

    resumable = state.list_resumable_runs(session, project_id="proj")
    ids = {r.id for r in resumable}
    assert ids == {"RUN-A", "RUN-B"}  # terminal (closed/failed) excluded


def test_list_resumable_runs_scopes_by_project():
    session = state.init_db()
    state.ensure_project(session, "proj", "https://github.com/x/proj")
    state.ensure_project(session, "other", "https://github.com/x/other")
    state.create_or_reset_run(session, "RUN-A", "proj", 1, status="implementing")
    state.create_or_reset_run(session, "RUN-B", "other", 1, status="implementing")

    assert {r.id for r in state.list_resumable_runs(session, project_id="proj")} == {"RUN-A"}
    assert {r.id for r in state.list_resumable_runs(session)} == {"RUN-A", "RUN-B"}  # all projects
