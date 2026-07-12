CREATE TABLE IF NOT EXISTS scene_confirmations (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scene_id TEXT NOT NULL REFERENCES scene_workspaces(scene_id) ON DELETE CASCADE,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, scene_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_scene_confirmations_scene_revision
  ON scene_confirmations(scene_id, revision);