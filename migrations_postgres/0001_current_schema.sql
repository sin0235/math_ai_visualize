CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  role TEXT NOT NULL DEFAULT 'user',
  status TEXT NOT NULL DEFAULT 'active',
  display_name TEXT,
  last_login_at TEXT,
  plan TEXT NOT NULL DEFAULT 'free',
  email_verified_at TEXT,
  password_changed_at TEXT,
  failed_login_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  last_failed_login_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT,
  revoked_at TEXT,
  ip_address TEXT,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON sessions(user_id, revoked_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_ip TEXT,
  user_agent TEXT,
  otp_hash TEXT,
  otp_attempts INTEGER NOT NULL DEFAULT 0,
  max_otp_attempts INTEGER NOT NULL DEFAULT 5
);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_purpose ON auth_tokens(user_id, purpose, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_expires ON auth_tokens(expires_at);

CREATE TABLE IF NOT EXISTS rate_limit_events (
  key TEXT NOT NULL,
  bucket TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (key, bucket)
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_events_expires ON rate_limit_events(expires_at);

CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS render_jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  problem_text TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  scene_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  warnings_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  render_request_json TEXT,
  advanced_settings_json TEXT,
  runtime_settings_json TEXT,
  source_type TEXT NOT NULL DEFAULT 'problem',
  renderer TEXT,
  status TEXT NOT NULL DEFAULT 'completed',
  error_json TEXT,
  started_at TEXT,
  finished_at TEXT,
  degraded INTEGER NOT NULL DEFAULT 0 CHECK (degraded IN (0, 1)),
  fallback_source TEXT NOT NULL DEFAULT 'none' CHECK (fallback_source IN ('none', 'mock', 'provider_fallback')),
  ai_source TEXT NOT NULL DEFAULT 'none' CHECK (ai_source IN ('admin', 'byok', 'none')),
  response_json TEXT,
  schema_version TEXT DEFAULT '1.0'
);

CREATE INDEX IF NOT EXISTS idx_render_jobs_user_created ON render_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_render_jobs_user_status_created ON render_jobs(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status_created ON render_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_render_jobs_schema_version ON render_jobs(schema_version);

CREATE TABLE IF NOT EXISTS system_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS legal_acceptances (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,
  document_version TEXT NOT NULL,
  accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  accepted_ip TEXT,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_document ON legal_acceptances(user_id, document_type, document_version);

CREATE TABLE IF NOT EXISTS oauth_identities (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  provider_subject TEXT NOT NULL,
  email TEXT NOT NULL,
  email_verified INTEGER NOT NULL DEFAULT 0,
  display_name TEXT,
  picture_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_subject),
  UNIQUE(provider, user_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_identities_user ON oauth_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_identities_email ON oauth_identities(email);

CREATE TABLE IF NOT EXISTS oauth_states (
  state_hash TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  redirect_after TEXT,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_ip TEXT,
  user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON oauth_states(expires_at);

CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_usage_events_user_type_created ON usage_events(user_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at);

CREATE TABLE IF NOT EXISTS ai_providers (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  default_model_id TEXT NOT NULL DEFAULT '',
  api_key_configured INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_checked_at TEXT,
  last_check_status TEXT,
  last_check_message TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_models (
  provider_id TEXT NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
  id TEXT NOT NULL,
  label TEXT NOT NULL,
  owned_by TEXT,
  context_length INTEGER,
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  is_free_endpoint INTEGER NOT NULL DEFAULT 0,
  supports_thinking INTEGER NOT NULL DEFAULT 0,
  supports_vision INTEGER NOT NULL DEFAULT 0,
  pricing_json TEXT NOT NULL DEFAULT '{}',
  endpoint_metadata_json TEXT NOT NULL DEFAULT '{}',
  supported_parameters_json TEXT NOT NULL DEFAULT '[]',
  source TEXT NOT NULL DEFAULT 'scan',
  enabled INTEGER NOT NULL DEFAULT 1,
  allowed INTEGER NOT NULL DEFAULT 0,
  last_seen_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (provider_id, id)
);

CREATE INDEX IF NOT EXISTS idx_ai_models_provider_allowed ON ai_models(provider_id, allowed, enabled);
CREATE INDEX IF NOT EXISTS idx_ai_models_provider_free_allowed ON ai_models(provider_id, is_free_endpoint, enabled, allowed);
CREATE INDEX IF NOT EXISTS idx_ai_models_provider_thinking_allowed ON ai_models(provider_id, supports_thinking, enabled, allowed);
CREATE INDEX IF NOT EXISTS idx_ai_models_last_seen ON ai_models(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS ai_task_profiles (
  task TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL DEFAULT 'auto',
  model_id TEXT NOT NULL DEFAULT '',
  fallbacks_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  tier TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_task_profiles_provider_model ON ai_task_profiles(provider_id, model_id);

CREATE TABLE IF NOT EXISTS ai_model_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'received', 'accepted')),
  admin_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT,
  resolved_by TEXT REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_one_pending_per_user ON feedback(user_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_feedback_user_status ON feedback(user_id, status);
CREATE INDEX IF NOT EXISTS idx_feedback_status_created ON feedback(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_user_created ON feedback(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  daily_render_limit INTEGER CHECK(daily_render_limit IS NULL OR daily_render_limit >= 0),
  daily_ocr_limit INTEGER CHECK(daily_ocr_limit IS NULL OR daily_ocr_limit >= 0),
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_scan_jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  models_json TEXT NOT NULL DEFAULT '[]',
  error_json TEXT,
  runtime_json TEXT NOT NULL DEFAULT '{}',
  base_url TEXT NOT NULL DEFAULT '',
  result_count INTEGER NOT NULL DEFAULT 0,
  free_count INTEGER NOT NULL DEFAULT 0,
  thinking_count INTEGER NOT NULL DEFAULT 0,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_scan_jobs_user_created ON model_scan_jobs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS model_scan_job_models (
  scan_id TEXT NOT NULL REFERENCES model_scan_jobs(id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  label TEXT NOT NULL,
  is_free_endpoint INTEGER NOT NULL DEFAULT 0,
  supports_thinking INTEGER NOT NULL DEFAULT 0,
  supports_vision INTEGER NOT NULL DEFAULT 0,
  context_length INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scan_id, provider_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_model_scan_job_models_scan ON model_scan_job_models(scan_id);
CREATE INDEX IF NOT EXISTS idx_model_scan_job_models_provider ON model_scan_job_models(provider_id, model_id);

CREATE TABLE IF NOT EXISTS uploaded_files (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  data_base64 TEXT NOT NULL,
  storage_key TEXT,
  public_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  storage_provider TEXT NOT NULL DEFAULT 'database',
  storage_bucket TEXT,
  external_file_id TEXT,
  remote_metadata_json TEXT,
  base64_cleared_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_created ON uploaded_files(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_sha256 ON uploaded_files(sha256);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_provider_created ON uploaded_files(storage_provider, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_conversations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
  assigned_admin_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  last_message_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_last_read_at TEXT,
  admin_last_read_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_status ON chat_conversations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_last_message ON chat_conversations(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_status_last_message ON chat_conversations(status, last_message_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conversations_one_open_per_user ON chat_conversations(user_id) WHERE status = 'open';

CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  sender_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sender_role TEXT NOT NULL CHECK(sender_role IN ('user', 'admin', 'system')),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  message_type TEXT NOT NULL DEFAULT 'text',
  image_url TEXT,
  image_public_id TEXT,
  image_width INTEGER,
  image_height INTEGER,
  image_bytes INTEGER,
  image_format TEXT,
  image_original_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created ON chat_messages(conversation_id, created_at ASC);

CREATE TABLE IF NOT EXISTS user_ai_provider_settings (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  base_url TEXT NOT NULL DEFAULT '',
  api_key_ciphertext TEXT,
  api_key_last4 TEXT,
  api_key_updated_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_ai_models (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  supports_vision INTEGER NOT NULL DEFAULT 0 CHECK (supports_vision IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_user_ai_models_user_enabled ON user_ai_models(user_id, enabled);

CREATE TABLE IF NOT EXISTS user_ai_task_profiles (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  task TEXT NOT NULL CHECK (task IN ('render', 'reasoning', 'ocr', 'solver', 'chat')),
  model_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, task)
);

CREATE INDEX IF NOT EXISTS idx_user_ai_task_profiles_user_enabled ON user_ai_task_profiles(user_id, enabled);