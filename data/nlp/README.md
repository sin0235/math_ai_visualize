# NLP data

Corpus và artifact đánh giá NLP (product datasets — không phải pytest fixture).

## Layout

| Path | Mô tả |
|------|--------|
| `corpus/v2.jsonl` | **Corpus chính** (v1-compatible schema), 19,431 case |
| `corpus/v2_rich.jsonl` | Bản rich + metadata (grade, split, semantic_group, …) |
| `corpus/seed_v1.jsonl` | Seed 83 case (v1 cũ, user-provided) |
| `splits/{train,validation,test}.jsonl` | Chia theo semantic_group |
| `meta/` | taxonomy, schema, validation_report upstream |
| `eval/` | baseline + thresholds regression CI |
| `EVALUATION.md` | Báo cáo đánh giá khi thay v1→v2 |

Loaders mặc định: `tests.nlp.benchmark.CORPUS_PATH` → `corpus/v2.jsonl`.

Runtime solve **không** đọc corpus này (chỉ eval / coverage / offline).
