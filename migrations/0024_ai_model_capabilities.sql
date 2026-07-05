ALTER TABLE ai_models ADD COLUMN is_free_endpoint INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN supports_thinking INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN supports_vision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN pricing_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_models ADD COLUMN endpoint_metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_models ADD COLUMN supported_parameters_json TEXT NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS idx_ai_models_provider_free_allowed ON ai_models(provider_id, is_free_endpoint, enabled, allowed);
CREATE INDEX IF NOT EXISTS idx_ai_models_provider_thinking_allowed ON ai_models(provider_id, supports_thinking, enabled, allowed);

ALTER TABLE model_scan_jobs ADD COLUMN runtime_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE model_scan_jobs ADD COLUMN base_url TEXT NOT NULL DEFAULT '';
ALTER TABLE model_scan_jobs ADD COLUMN result_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE model_scan_jobs ADD COLUMN free_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE model_scan_jobs ADD COLUMN thinking_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE model_scan_jobs ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE model_scan_jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS model_scan_job_models (
  scan_id TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  label TEXT NOT NULL,
  is_free_endpoint INTEGER NOT NULL DEFAULT 0,
  supports_thinking INTEGER NOT NULL DEFAULT 0,
  supports_vision INTEGER NOT NULL DEFAULT 0,
  context_length INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scan_id, provider_id, model_id),
  FOREIGN KEY (scan_id) REFERENCES model_scan_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_model_scan_job_models_scan ON model_scan_job_models(scan_id);
CREATE INDEX IF NOT EXISTS idx_model_scan_job_models_provider ON model_scan_job_models(provider_id, model_id);