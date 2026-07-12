ALTER TABLE scene_revisions ADD COLUMN scene_id TEXT;
ALTER TABLE scene_revisions ADD COLUMN snapshot_revision INTEGER;

CREATE INDEX IF NOT EXISTS idx_scene_revisions_scene_snapshot
  ON scene_revisions(scene_id, snapshot_revision DESC);