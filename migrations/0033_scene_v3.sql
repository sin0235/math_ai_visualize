ALTER TABLE render_jobs ADD COLUMN migration_report_json TEXT;
ALTER TABLE scene_revisions ADD COLUMN schema_version TEXT NOT NULL DEFAULT '2.0';
ALTER TABLE scene_revisions ADD COLUMN migration_report_json TEXT;
ALTER TABLE scene_revisions ADD COLUMN command_log_json TEXT NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS scene_workspaces (
  scene_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  history_item_id TEXT,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  scene_json TEXT NOT NULL,
  status TEXT NOT NULL,
  verification_json TEXT NOT NULL DEFAULT '[]',
  issues_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (history_item_id) REFERENCES history_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_scene_workspaces_user_updated ON scene_workspaces(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS scene_commands (
  id TEXT PRIMARY KEY,
  scene_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  history_item_id TEXT,
  base_revision INTEGER NOT NULL CHECK (base_revision >= 1),
  result_revision INTEGER NOT NULL CHECK (result_revision > base_revision),
  command_type TEXT NOT NULL,
  command_json TEXT NOT NULL,
  inverse_command_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (history_item_id) REFERENCES history_items(id) ON DELETE SET NULL,
  UNIQUE(scene_id, result_revision)
);

CREATE INDEX IF NOT EXISTS idx_scene_commands_scene_revision ON scene_commands(scene_id, result_revision DESC);
CREATE INDEX IF NOT EXISTS idx_scene_commands_user_created ON scene_commands(user_id, created_at DESC);