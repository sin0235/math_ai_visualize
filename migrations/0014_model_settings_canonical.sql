CREATE INDEX IF NOT EXISTS idx_ai_task_profiles_provider_model ON ai_task_profiles(provider_id, model_id);

INSERT INTO ai_model_settings (key, value_json, updated_at)
VALUES ('model_registry_schema_version', '2', CURRENT_TIMESTAMP)
ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP;
