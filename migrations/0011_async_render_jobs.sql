ALTER TABLE render_jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'completed';
ALTER TABLE render_jobs ADD COLUMN error_json TEXT;
ALTER TABLE render_jobs ADD COLUMN started_at TEXT;
ALTER TABLE render_jobs ADD COLUMN finished_at TEXT;

CREATE INDEX IF NOT EXISTS idx_render_jobs_user_status_created ON render_jobs(user_id, status, created_at DESC);
