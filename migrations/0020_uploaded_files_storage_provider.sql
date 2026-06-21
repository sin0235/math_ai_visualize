ALTER TABLE uploaded_files ADD COLUMN storage_provider TEXT NOT NULL DEFAULT 'database';
ALTER TABLE uploaded_files ADD COLUMN storage_bucket TEXT;
ALTER TABLE uploaded_files ADD COLUMN external_file_id TEXT;
ALTER TABLE uploaded_files ADD COLUMN remote_metadata_json TEXT;

UPDATE uploaded_files
SET storage_provider = 'r2'
WHERE storage_key IS NOT NULL
  AND storage_key != ''
  AND storage_provider = 'database';
