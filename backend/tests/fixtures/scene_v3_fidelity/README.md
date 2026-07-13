# Scene v3 fidelity corpus (offline)

Golden `MathSceneV3` fixtures — **no live LLM**. CI runs contract + geometry kernel (+ optional solver) and fails on regression.

## Files

| File | Role |
|------|------|
| `corpus.jsonl` | 35 cases (2D/3D, positive + negative) |
| `thresholds.json` | Minimum rates enforced in CI |

## Run locally

```bash
cd backend
python -m app.math_curriculum.scene_fidelity
python -m app.math_curriculum.scene_fidelity --json
pytest -q tests/test_scene_v3_fidelity.py
```

## Case shape

```json
{
  "case_id": "solid-pyramid-height-001",
  "tags": ["solid_geometry", "distance"],
  "problem_text": "...",
  "scene": { "...MathSceneV3..." },
  "expect": {
    "pipeline_status_in": ["verified"],
    "can_project": true,
    "require_no_constraint_failed": true,
    "solve": {
      "question": "d(S,(ABC))",
      "geometry_method": "classical",
      "answer_contains": ["3"],
      "confidence_in": ["verified"]
    }
  }
}
```

Negative cases use tags including `negative` and expects such as `require_constraint_failed` or `can_project: false`.
