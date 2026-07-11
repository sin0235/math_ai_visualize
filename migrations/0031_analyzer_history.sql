CREATE TABLE IF NOT EXISTS analyzer_history (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  original_expression TEXT NOT NULL,
  canonical_expression TEXT NOT NULL,
  parameter_json TEXT NOT NULL DEFAULT '{}',
  window_json TEXT NOT NULL DEFAULT '{}',
  tools_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL,
  verification_json TEXT NOT NULL DEFAULT '{}',
  tags_json TEXT NOT NULL DEFAULT '[]',
  is_pinned INTEGER NOT NULL DEFAULT 0 CHECK (is_pinned IN (0, 1)),
  grade INTEGER,
  chapter TEXT,
  explanation_level TEXT NOT NULL DEFAULT 'standard',
  engine_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  parent_history_id TEXT,
  last_opened_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_history_id) REFERENCES analyzer_history(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_analyzer_history_user_updated ON analyzer_history(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyzer_history_user_pinned ON analyzer_history(user_id, is_pinned, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyzer_history_user_chapter ON analyzer_history(user_id, chapter, updated_at DESC);