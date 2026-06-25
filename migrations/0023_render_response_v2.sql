ALTER TABLE render_jobs ADD COLUMN response_json TEXT;
ALTER TABLE render_jobs ADD COLUMN schema_version TEXT DEFAULT '1.0';
CREATE INDEX IF NOT EXISTS idx_render_jobs_schema_version ON render_jobs(schema_version);
