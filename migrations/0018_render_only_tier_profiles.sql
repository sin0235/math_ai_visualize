DELETE FROM ai_task_profiles
WHERE task IN (
  'reasoning_tier1',
  'reasoning_tier2',
  'reasoning_tier3',
  'solver_explanation_tier1',
  'solver_explanation_tier2',
  'solver_explanation_tier3'
);
