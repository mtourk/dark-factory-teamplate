-- Phase 17 Intake Database Schema (Cloudflare D1)
-- Three tables: conversations (discovery session), messages (chat history), pending_profiles (new repos awaiting sync)

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  status TEXT NOT NULL CHECK (status IN ('draft', 'filed', 'completed')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  issue_number INTEGER,
  repo_url TEXT,
  issue_url TEXT,
  title TEXT,
  description TEXT,
  acceptance_criteria TEXT,
  non_goals TEXT,
  constraints TEXT,
  data_needed TEXT,
  error_handling TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'ai')),
  text TEXT NOT NULL,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  token_count INTEGER
);

CREATE TABLE IF NOT EXISTS pending_profiles (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  name TEXT NOT NULL UNIQUE,
  repo_url TEXT NOT NULL UNIQUE,
  owner TEXT NOT NULL,
  repo_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  synced BOOLEAN NOT NULL DEFAULT 0,
  synced_at TEXT,
  error TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_pending_profiles_synced ON pending_profiles(synced);
