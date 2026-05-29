-- Thêm cột tier vào ai_task_profiles để hỗ trợ phân loại model theo chất lượng
ALTER TABLE ai_task_profiles ADD COLUMN tier TEXT;

-- Tạo index cho tier để tăng tốc query
CREATE INDEX IF NOT EXISTS idx_ai_task_profiles_tier ON ai_task_profiles(tier);

-- Seed tier profiles mặc định cho các task hỗ trợ tier
-- OCR không có tier, giữ nguyên task 'ocr' hiện có
INSERT OR IGNORE INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier)
VALUES
  ('render_tier1', 'auto', '', '[]', 'tier1'),
  ('render_tier2', 'auto', '', '[]', 'tier2'),
  ('render_tier3', 'auto', '', '[]', 'tier3'),
  ('reasoning_tier1', 'auto', '', '[]', 'tier1'),
  ('reasoning_tier2', 'auto', '', '[]', 'tier2'),
  ('reasoning_tier3', 'auto', '', '[]', 'tier3'),
  ('solver_explanation_tier1', 'auto', '', '[]', 'tier1'),
  ('solver_explanation_tier2', 'auto', '', '[]', 'tier2'),
  ('solver_explanation_tier3', 'auto', '', '[]', 'tier3');
