-- Thêm cột tier vào ai_task_profiles để hỗ trợ phân loại model theo chất lượng
ALTER TABLE ai_task_profiles ADD COLUMN tier TEXT;

-- Tạo index cho tier để tăng tốc query
CREATE INDEX IF NOT EXISTS idx_ai_task_profiles_tier ON ai_task_profiles(tier);

-- Seed tier profiles mặc định chỉ cho task dựng hình.
INSERT OR IGNORE INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier)
VALUES
  ('render_tier1', 'auto', '', '[]', 'tier1'),
  ('render_tier2', 'auto', '', '[]', 'tier2'),
  ('render_tier3', 'auto', '', '[]', 'tier3');
