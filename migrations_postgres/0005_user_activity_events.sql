CREATE TABLE IF NOT EXISTS user_activity_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id TEXT,
  event_type TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  source TEXT NOT NULL DEFAULT 'server',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_activity_events_user_created ON user_activity_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_events_type_created ON user_activity_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_events_target ON user_activity_events(target_type, target_id);