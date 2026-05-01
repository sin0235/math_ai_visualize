ALTER TABLE render_jobs ADD COLUMN render_request_json TEXT;
ALTER TABLE render_jobs ADD COLUMN advanced_settings_json TEXT;
ALTER TABLE render_jobs ADD COLUMN runtime_settings_json TEXT;
ALTER TABLE render_jobs ADD COLUMN source_type TEXT NOT NULL DEFAULT 'problem';
ALTER TABLE render_jobs ADD COLUMN renderer TEXT;
