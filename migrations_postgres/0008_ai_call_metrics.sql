CREATE TABLE IF NOT EXISTS ai_call_metrics (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  request_id TEXT,
  task TEXT NOT NULL DEFAULT 'unknown',
  provider TEXT,
  model TEXT,
  success INTEGER NOT NULL DEFAULT 1,
  error_code TEXT,
  elapsed_ms INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_call_metrics_created ON ai_call_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_call_metrics_task_created ON ai_call_metrics(task, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_call_metrics_provider_created ON ai_call_metrics(provider, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_call_metrics_user_created ON ai_call_metrics(user_id, created_at DESC);
