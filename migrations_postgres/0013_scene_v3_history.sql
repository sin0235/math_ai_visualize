ALTER TABLE scene_revisions ADD COLUMN IF NOT EXISTS scene_id TEXT;
ALTER TABLE scene_revisions ADD COLUMN IF NOT EXISTS snapshot_revision INTEGER;

CREATE INDEX IF NOT EXISTS idx_scene_revisions_scene_snapshot
  ON scene_revisions(scene_id, snapshot_revision DESC);