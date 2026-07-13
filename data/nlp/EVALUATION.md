# Đánh giá Math AI Corpus v2

```json
{
  "evaluated_at": "2026-07-14",
  "source": "math_ai_corpus_v2 (compatible)",
  "records": 19431,
  "schema_validation": "pass (tests.nlp.benchmark.validate_case, 0 errors)",
  "pipeline_metrics_rule_based": {
    "case_count": 19431,
    "intent_macro_f1": 0.205281,
    "canonical_exact_match": 0.07311,
    "canonical_semantic_match": 0.07311,
    "entity_f1": 0.311019,
    "constraint_f1": 0.046316,
    "unsupported_recall": 0.309804,
    "abstention_precision": 0.129877,
    "brier_score": 0.253558,
    "ece_10": 0.200006
  },
  "legacy_metrics_rule_based": {
    "case_count": 19431,
    "intent_macro_f1": 0.180093,
    "canonical_exact_match": 0.065279,
    "canonical_semantic_match": 0.065279,
    "entity_f1": 0.279461,
    "constraint_f1": 0.0,
    "unsupported_recall": 0.0,
    "abstention_precision": 0.073266,
    "brier_score": 0.210672,
    "ece_10": 0.213914
  },
  "notes": [
    "Schema v1-compatible; all 5 required fields present.",
    "Seed (83) identical to previous project v1 corpus.",
    "Rule-based NLP intent_macro_f1 ~0.20 on full v2 — corpus is broader than current rule-based coverage; use as regression floor + future LLM NLP training/eval, not as gold solutions (math_solution_verified=false).",
    "Primary path for loaders: data/nlp/corpus/v2.jsonl"
  ]
}
```

## Kết luận

- **Chấp nhận thay thế** corpus v1 (83) bằng v2 compatible (19,431).
- Dùng cho intent/canonicalization/robustness; **không** coi là gold lời giải.
- Metric rule-based thấp trên full set là kỳ vọng — baseline CI khóa sàn hiện tại để theo dõi hồi quy.
