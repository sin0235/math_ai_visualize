CREATE TABLE IF NOT EXISTS algebra_history (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT,
  problem_preview TEXT NOT NULL DEFAULT '',
  topic TEXT NOT NULL DEFAULT 'auto',
  status TEXT NOT NULL DEFAULT 'solved',
  request_id TEXT,
  request_json TEXT NOT NULL DEFAULT '{}',
  response_json TEXT NOT NULL DEFAULT '{}',
  is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
  archived_at TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_algebra_history_user_created
  ON algebra_history(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_algebra_history_user_topic
  ON algebra_history(user_id, topic, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_algebra_history_user_favorite
  ON algebra_history(user_id, is_favorite, updated_at DESC);
