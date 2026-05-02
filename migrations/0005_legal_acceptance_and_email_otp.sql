ALTER TABLE auth_tokens ADD COLUMN otp_hash TEXT;
ALTER TABLE auth_tokens ADD COLUMN otp_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE auth_tokens ADD COLUMN max_otp_attempts INTEGER NOT NULL DEFAULT 5;

CREATE TABLE IF NOT EXISTS legal_acceptances (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  document_type TEXT NOT NULL,
  document_version TEXT NOT NULL,
  accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  accepted_ip TEXT,
  user_agent TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_document ON legal_acceptances(user_id, document_type, document_version);
