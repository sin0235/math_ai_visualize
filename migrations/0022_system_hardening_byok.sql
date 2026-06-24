CREATE TABLE IF NOT EXISTS user_ai_provider_settings (
  user_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  base_url TEXT NOT NULL DEFAULT '',
  api_key_ciphertext TEXT,
  api_key_last4 TEXT,
  api_key_updated_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_ai_models (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  supports_vision INTEGER NOT NULL DEFAULT 0 CHECK (supports_vision IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE (user_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_user_ai_models_user_enabled ON user_ai_models(user_id, enabled);

CREATE TABLE IF NOT EXISTS user_ai_task_profiles (
  user_id TEXT NOT NULL,
  task TEXT NOT NULL CHECK (task IN ('render', 'reasoning', 'ocr', 'solver', 'chat')),
  model_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, task),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_ai_task_profiles_user_enabled ON user_ai_task_profiles(user_id, enabled);

ALTER TABLE render_jobs ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0 CHECK (degraded IN (0, 1));
ALTER TABLE render_jobs ADD COLUMN fallback_source TEXT NOT NULL DEFAULT 'none' CHECK (fallback_source IN ('none', 'mock', 'provider_fallback'));
ALTER TABLE render_jobs ADD COLUMN ai_source TEXT NOT NULL DEFAULT 'none' CHECK (ai_source IN ('admin', 'byok', 'none'));

CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status_created ON render_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_status_last_message ON chat_conversations(status, last_message_at DESC);
UPDATE chat_conversations
SET status = 'closed', updated_at = CURRENT_TIMESTAMP
WHERE status = 'open'
  AND EXISTS (
    SELECT 1
    FROM chat_conversations newer
    WHERE newer.user_id = chat_conversations.user_id
      AND newer.status = 'open'
      AND (
        newer.last_message_at > chat_conversations.last_message_at
        OR (newer.last_message_at = chat_conversations.last_message_at AND newer.id > chat_conversations.id)
      )
  );
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conversations_one_open_per_user ON chat_conversations(user_id) WHERE status = 'open';
