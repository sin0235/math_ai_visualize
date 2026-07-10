CREATE TABLE IF NOT EXISTS ai_providers (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  api_key_configured INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_checked_at TEXT,
  last_check_status TEXT,
  last_check_message TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_models (
  provider_id TEXT NOT NULL,
  id TEXT NOT NULL,
  label TEXT NOT NULL,
  owned_by TEXT,
  context_length INTEGER,
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'scan',
  enabled INTEGER NOT NULL DEFAULT 1,
  allowed INTEGER NOT NULL DEFAULT 0,
  last_seen_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (provider_id, id),
  FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_models_provider_allowed ON ai_models(provider_id, allowed, enabled);
CREATE INDEX IF NOT EXISTS idx_ai_models_last_seen ON ai_models(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS ai_task_profiles (
  task TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL DEFAULT 'auto',
  model_id TEXT NOT NULL DEFAULT '',
  fallbacks_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_model_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
