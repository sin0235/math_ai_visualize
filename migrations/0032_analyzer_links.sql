CREATE TABLE IF NOT EXISTS analyzer_links (
  short_id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('handoff', 'share')),
  target TEXT NOT NULL CHECK (target IN ('algebra_solver', 'simulation', 'geogebra_lab', 'render', 'practice')),
  payload_version TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  visibility TEXT NOT NULL CHECK (visibility IN ('user', 'public')),
  scopes_json TEXT NOT NULL DEFAULT '[]',
  allowed_origins_json TEXT NOT NULL DEFAULT '[]',
  max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses BETWEEN 1 AND 1000),
  use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  consumed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyzer_links_owner_created ON analyzer_links(owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyzer_links_expiry ON analyzer_links(expires_at);