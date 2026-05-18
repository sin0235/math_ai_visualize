CREATE TABLE IF NOT EXISTS uploaded_files (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  data_base64 TEXT NOT NULL,
  storage_key TEXT,
  public_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_created ON uploaded_files(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_sha256 ON uploaded_files(sha256);
