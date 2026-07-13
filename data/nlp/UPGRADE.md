# Plan: NLP algebra thống nhất (LLM primary → mathcore)

Ngày: 2026-07-14

## Vấn đề

1. LLM extraction nằm đơn lẻ trong algebra service, không phải lớp NLP chung.
2. Rule-based từng được ưu tiên khi “solved” → LLM bị gạt, NLP yếu.
3. Pipeline `/api/nlp/interpret` chỉ rule-based; solve path có LLM riêng.
4. Corpus chỉ dùng eval, không gắn orchestration.

## Mục tiêu

| Layer | Vai trò |
|---|---|
| **NLP** | Hiểu đề → form chuẩn (canonical). LLM primary cho natural language; rule-based cho structured + fallback. |
| **Mathcore** | Toàn bộ giải, bước, đáp án. **Không** AI giải. |

## Kiến trúc mục tiêu

```text
AlgebraSolveRequest
        │
        v
  nlp.algebra_nlp.resolve_algebra_nlp()
        │
        ├─ structured / symbolic ──► rule-based interpret (no LLM)
        ├─ natural + allow_llm ────► LLM extract → validate mathcore-ready
        │                              └ fail ──► rule-based fallback
        └─ natural + no LLM ───────► rule-based only
        │
        v
  AlgebraNlpResult { request_for_mathcore, source, confidence, warnings }
        │
        v
  solve_algebra_deterministic / mathcore solvers
```

## Phạm vi đợt này

- [x] Tạo `app/services/nlp/algebra_nlp.py` (orchestrator duy nhất)
- [x] Wire `solve_algebra_with_optional_ai` qua orchestrator
- [x] Validate output LLM trước khi đưa vào mathcore
- [x] Tests: structured skips LLM; natural uses LLM; LLM fail → fallback
- [ ] (Sau) `/api/nlp/interpret` async LLM khi client opt-in
- [ ] (Sau) Dùng corpus cho eval gate extraction trong CI

## Ngoài phạm vi

- LLM giải / sinh nghiệm
- Đổi render geometry NLP
- Fine-tune model trên corpus
