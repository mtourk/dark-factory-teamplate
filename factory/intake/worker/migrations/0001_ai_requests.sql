-- Provider-neutral AI request monitoring.
-- Apply to the existing dark-factory-intake D1 database before deploying Worker code.
-- Existing ollama_requests rows are intentionally preserved.

CREATE TABLE IF NOT EXISTS ai_requests (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  request_type TEXT NOT NULL,
  requested_model TEXT NOT NULL,
  actual_model TEXT,
  provider TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'error')),
  prompt_text TEXT NOT NULL,
  prompt_length INTEGER,
  response_text TEXT,
  response_length INTEGER,
  error_message TEXT,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at TEXT,
  duration_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd TEXT,
  gateway_latency_ms INTEGER,
  fallback_attempts INTEGER NOT NULL DEFAULT 0,
  cache_hit BOOLEAN,
  gateway_request_id TEXT,
  gateway_version TEXT,
  raw_metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_requests_started_at ON ai_requests(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_requests_status ON ai_requests(status);
CREATE INDEX IF NOT EXISTS idx_ai_requests_conversation_id ON ai_requests(conversation_id);
CREATE INDEX IF NOT EXISTS idx_ai_requests_provider_model ON ai_requests(provider, actual_model);
