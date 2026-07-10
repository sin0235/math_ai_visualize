-- Analytics & monitoring: error events + render duration

CREATE TABLE IF NOT EXISTS error_events (
  id TEXT PRIMARY KEY,
  request_id TEXT,
  user_id TEXT,
  source TEXT NOT NULL DEFAULT 'server',
  route TEXT,
  method TEXT,
  status_code INTEGER,
  error_code TEXT,
  message TEXT NOT NULL,
  stack_fingerprint TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_error_events_created ON error_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_events_code_created ON error_events(error_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_events_user_created ON error_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_events_fingerprint ON error_events(stack_fingerprint, created_at DESC);

ALTER TABLE render_jobs ADD COLUMN duration_ms INTEGER;
CREATE INDEX IF NOT EXISTS idx_render_jobs_status_created ON render_jobs(status, created_at DESC);
