-- Phase 18 Proposed Migration — Autonomous Intake-to-Deploy Pipeline (ADR-007)
--
-- STATUS: design only. NOT yet applied to the live D1 database.
-- Apply with: wrangler d1 execute dark-factory-intake --file=./schema_phase18.sql
-- (run against the live DB only after Phase 18 implementation is approved).
--
-- Adds one table, build_queue, to the existing schema.sql (conversations, messages,
-- pending_profiles). This table is the only coordination surface between the cloud
-- (Worker/D1/web UI) and the local queue runner (factory/intake/queue_runner.py) —
-- it carries identifiers and status text only, never secrets.

CREATE TABLE IF NOT EXISTS build_queue (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),

  -- Links back to the conversation/issue that produced this job
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  repo_url TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  issue_url TEXT NOT NULL,

  -- Cross-link to the visibility-only tracking issue filed on dark-factory-teamplate itself (ADR-007 §5)
  tracking_issue_number INTEGER,
  tracking_issue_url TEXT,

  -- Submission-time flags captured from the repo-selection modal
  is_new_repo BOOLEAN NOT NULL DEFAULT 0,       -- true if this job created the repo (vs. editing an existing one)
  needs_new_app BOOLEAN NOT NULL DEFAULT 0,     -- true => provision a new subdomain/app; false => edit existing app, or no deploy
  existing_app_url TEXT,                        -- user-supplied, informational only, when they said "I already have a running app"
  desired_project_slug TEXT,                    -- used to build <slug>.mtourk.com when needs_new_app is true

  -- Queue mechanics
  status TEXT NOT NULL DEFAULT 'queued' CHECK (
    status IN ('queued', 'claimed', 'implementing', 'testing', 'reviewing', 'deploying', 'done', 'failed')
  ),
  position INTEGER,                             -- informational display order among queued rows; not used for claim correctness
  claimed_at TEXT,
  claimed_by TEXT,                               -- hostname/identifier of the queue_runner.py instance that claimed it

  -- Progress reporting (written by factory/intake/queue_runner.py via POST /build-queue/:id/progress)
  progress_step TEXT,                            -- short machine-readable step name, e.g. "implementing"
  progress_detail TEXT,                          -- short human-readable detail, e.g. "Running BMAD critics (3 of 5)"

  -- Terminal state
  result_url TEXT,                               -- deployed app URL (new app) or PR URL (existing-repo edit), set on 'done'
  error TEXT,                                     -- set on 'failed'

  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Single-flight claim: the queue runner claims via
--   UPDATE build_queue SET status = 'claimed', claimed_at = datetime('now'), claimed_by = ?
--   WHERE id = ? AND status = 'queued'
-- and checks the affected-row count — this is what makes "process one at a time" a DB-level
-- guarantee rather than a convention, even if two runner instances were started by mistake.

CREATE INDEX IF NOT EXISTS idx_build_queue_status ON build_queue(status);
CREATE INDEX IF NOT EXISTS idx_build_queue_conversation_id ON build_queue(conversation_id);
CREATE INDEX IF NOT EXISTS idx_build_queue_created_at ON build_queue(created_at);

-- Mid-flight amendments (ADR-007 §7): track user-submitted details appended while a job is in progress
CREATE TABLE IF NOT EXISTS build_queue_updates (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  build_queue_id TEXT NOT NULL REFERENCES build_queue(id) ON DELETE CASCADE,
  detail_text TEXT NOT NULL,                     -- the user-submitted detail/clarification
  appended_to_github_issue BOOLEAN NOT NULL DEFAULT 0,  -- true once the Worker has posted it as a GitHub comment
  github_comment_id INTEGER,                    -- GitHub's comment ID, for tracking/editing
  github_comment_url TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_build_queue_updates_queue_id ON build_queue_updates(build_queue_id);
CREATE INDEX IF NOT EXISTS idx_build_queue_updates_appended ON build_queue_updates(appended_to_github_issue);
