CREATE TABLE IF NOT EXISTS user_learning_profiles (
  user_id TEXT PRIMARY KEY,
  preferred_name TEXT,
  locale TEXT NOT NULL DEFAULT 'vi-VN',
  timezone TEXT,
  education_level TEXT,
  grade_level TEXT,
  math_level TEXT,
  learning_goals_json TEXT NOT NULL DEFAULT '[]',
  subject_focus_json TEXT NOT NULL DEFAULT '[]',
  preferred_explanation_style TEXT,
  accessibility_needs_json TEXT NOT NULL DEFAULT '[]',
  profile_json TEXT NOT NULL DEFAULT '{}',
  onboarding_completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history_projects (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  archived_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_projects_user_updated ON history_projects(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS history_items (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  render_job_id TEXT UNIQUE,
  project_id TEXT,
  title TEXT,
  problem_preview TEXT NOT NULL DEFAULT '',
  topic TEXT NOT NULL DEFAULT 'unknown',
  grade TEXT,
  tier TEXT,
  renderer TEXT,
  provider TEXT,
  model TEXT,
  source_type TEXT NOT NULL DEFAULT 'problem',
  status TEXT NOT NULL DEFAULT 'completed',
  is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
  archived_at TEXT,
  last_opened_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (render_job_id) REFERENCES render_jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (project_id) REFERENCES history_projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_history_items_user_created ON history_items(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_items_user_updated ON history_items(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_items_user_favorite ON history_items(user_id, is_favorite, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_items_user_topic ON history_items(user_id, topic, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_items_project_updated ON history_items(project_id, updated_at DESC);

INSERT OR IGNORE INTO history_items (
  id, user_id, render_job_id, title, problem_preview, topic, grade, tier, renderer, provider, model,
  source_type, status, created_at, updated_at
)
SELECT
  id, user_id, id, NULL, substr(problem_text, 1, 240), 'unknown', NULL, NULL, renderer, provider, model,
  source_type, status, created_at, COALESCE(finished_at, started_at, created_at)
FROM render_jobs
WHERE user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS scene_revisions (
  id TEXT PRIMARY KEY,
  history_item_id TEXT NOT NULL,
  render_job_id TEXT,
  revision_no INTEGER NOT NULL,
  change_source TEXT NOT NULL DEFAULT 'render',
  change_summary TEXT,
  scene_json TEXT NOT NULL,
  response_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (history_item_id) REFERENCES history_items(id) ON DELETE CASCADE,
  FOREIGN KEY (render_job_id) REFERENCES render_jobs(id) ON DELETE SET NULL,
  UNIQUE(history_item_id, revision_no)
);

CREATE INDEX IF NOT EXISTS idx_scene_revisions_item_created ON scene_revisions(history_item_id, created_at DESC);

INSERT OR IGNORE INTO scene_revisions (
  id, history_item_id, render_job_id, revision_no, change_source, change_summary, scene_json, response_json, created_at
)
SELECT
  id || ':r1', id, id, 1, source_type, 'Bản dựng đầu tiên', scene_json, response_json, created_at
FROM render_jobs
WHERE user_id IS NOT NULL AND scene_json IS NOT NULL AND scene_json != '{}';

CREATE TABLE IF NOT EXISTS history_tags (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  label TEXT NOT NULL,
  color TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, label)
);

CREATE INDEX IF NOT EXISTS idx_history_tags_user_label ON history_tags(user_id, label);

CREATE TABLE IF NOT EXISTS history_item_tags (
  history_item_id TEXT NOT NULL,
  tag_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (history_item_id, tag_id),
  FOREIGN KEY (history_item_id) REFERENCES history_items(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES history_tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_item_tags_tag ON history_item_tags(tag_id, history_item_id);