ALTER TABLE uploaded_files ADD COLUMN base64_cleared_at TEXT;

CREATE INDEX IF NOT EXISTS idx_uploaded_files_provider_created ON uploaded_files(storage_provider, created_at);
