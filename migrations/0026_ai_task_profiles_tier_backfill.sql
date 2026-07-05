UPDATE ai_task_profiles
SET tier = CASE task
  WHEN 'render_tier1' THEN 'tier1'
  WHEN 'render_tier2' THEN 'tier2'
  WHEN 'render_tier3' THEN 'tier3'
  ELSE NULL
END
WHERE task IN ('render_tier1', 'render_tier2', 'render_tier3')
   OR tier IS NOT NULL;