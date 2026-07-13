"""Unified algebra NLP orchestration.

LLM = natural-language understanding only (canonical form for mathcore).
Rule-based = structured/symbolic fast path + fallback.
Mathcore = all solving (never AI).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import Settings
from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra.normalizer import is_structured_algebra_input, normalize_algebra_input

NlpSource = Literal[
    "structured_passthrough",
    "rule_based",
    "llm",
    "rule_based_fallback",
    "raw",
]


@dataclass(frozen=True)
class AlgebraNlpResult:
    """Result of NLP only — never contains a solved answer."""

    original_input: str
    request: AlgebraSolveRequest
    source: NlpSource
    confidence: float
    warnings: list[str] = field(default_factory=list)
    used_llm: bool = False

    @property
    def canonical_input(self) -> str:
        return self.request.input


async def resolve_algebra_nlp(
    request: AlgebraSolveRequest,
    settings: Settings,
    *,
    allow_llm: bool | None = None,
) -> AlgebraNlpResult:
    """Resolve natural language (if any) into a mathcore-ready AlgebraSolveRequest.

    Parameters
    ----------
    allow_llm:
        Defaults to ``request.options.use_ai_extraction``. When False, only
        rule-based NLP is used.
    """
    original = (request.input or "").strip()
    use_llm = request.options.use_ai_extraction if allow_llm is None else allow_llm

    if _is_already_mathcore_ready(request):
        return AlgebraNlpResult(
            original_input=original,
            request=request.model_copy(update={"input": original}),
            source="structured_passthrough",
            confidence=0.98,
            used_llm=False,
        )

    needs_llm_nlp = use_llm and _needs_natural_language_nlp(request)

    if needs_llm_nlp:
        try:
            from app.services.algebra.ai_extraction import extract_algebra_request_with_ai

            extracted, extract_warnings = await extract_algebra_request_with_ai(
                original, request, settings
            )
            from app.services.algebra.service import _preserve_explicit_request_contract

            extracted = _preserve_explicit_request_contract(request, extracted)
            if _is_mathcore_ready_text(extracted.input) and not _still_natural_prose(extracted.input):
                return AlgebraNlpResult(
                    original_input=original,
                    request=extracted,
                    source="llm",
                    confidence=0.86,
                    warnings=_internal_warnings(extract_warnings),
                    used_llm=True,
                )
            # LLM returned something that still looks like prose / unusable.
            return AlgebraNlpResult(
                original_input=original,
                request=_rule_based_request(request),
                source="rule_based_fallback",
                confidence=0.55,
                warnings=[
                    *_internal_warnings(extract_warnings),
                    "NLP LLM trả form chưa sẵn sàng cho mathcore; đã fallback rule-based.",
                ],
                used_llm=True,
            )
        except Exception:
            return AlgebraNlpResult(
                original_input=original,
                request=_rule_based_request(request),
                source="rule_based_fallback",
                confidence=0.5,
                warnings=["NLP LLM không khả dụng; đã fallback rule-based rồi mathcore."],
                used_llm=False,
            )

    # Rule-based only (structured path already handled; natural without LLM).
    return AlgebraNlpResult(
        original_input=original,
        request=_rule_based_request(request),
        source="rule_based",
        confidence=0.72 if _is_mathcore_ready_text(request.input) else 0.55,
        used_llm=False,
    )


def _rule_based_request(request: AlgebraSolveRequest) -> AlgebraSolveRequest:
    from app.services.algebra.interpreter import interpret_algebra_input

    interpretation = interpret_algebra_input(request)
    return request.model_copy(
        update={
            "input": interpretation.canonical_input,
            "topic": request.topic if request.topic != "auto" else interpretation.topic_hint,
            "variables": list(request.variables) or list(interpretation.variables),
            "expression_action": request.expression_action or interpretation.expression_action,
        }
    )


def _is_already_mathcore_ready(request: AlgebraSolveRequest) -> bool:
    if request.input_format in {"structured", "latex"}:
        return True
    raw = (request.input or "").strip()
    if not raw:
        return False
    if is_structured_algebra_input(raw):
        return True
    if _needs_natural_language_nlp(request):
        return False
    # Symbolic equation / expression without Vietnamese prose.
    return _is_mathcore_ready_text(raw) and not _still_natural_prose(raw)


def _needs_natural_language_nlp(request: AlgebraSolveRequest) -> bool:
    raw = (request.input or "").strip()
    if not raw or request.input_format in {"structured", "latex"}:
        return False
    if is_structured_algebra_input(raw):
        return False
    from app.services.algebra.interpreter import interpret_algebra_input

    interpretation = interpret_algebra_input(request)
    if interpretation.detected_format in {"natural_vi", "mixed"}:
        return True
    return _still_natural_prose(raw)


def _is_mathcore_ready_text(text: str) -> bool:
    """Heuristic: text looks like something deterministic solvers can consume."""
    raw = (text or "").strip()
    if not raw:
        return False
    if is_structured_algebra_input(raw):
        return True
    normalized = normalize_algebra_input(raw)
    if is_structured_algebra_input(normalized):
        return True
    # Equation / inequality / multi-line system
    if any(op in raw for op in ("=", "<=", ">=", "!=", "<", ">")):
        return True
    # Pure expression (factor/expand) with math operators, short, no prose
    if re.fullmatch(r"[0-9a-zA-Z_+\-*/^().,\s]+", raw) and len(raw) <= 200:
        return True
    return False


def _still_natural_prose(text: str) -> bool:
    raw = text or ""
    if re.search(r"[À-ỹ]", raw):
        return True
    return bool(
        re.search(
            r"\b(giai|giải|tim|tìm|tinh|tính|phuong|phương|bat|bất|he|hệ|"
            r"cap so|cấp số|so hang|số hạng|dao ham|đạo hàm|gioi han|giới hạn|"
            r"tich phan|tích phân|voi|với|hoi|hỏi|bang|bằng|bao nhieu|bao nhiêu|"
            r"cho biet|cho biết|biet|biết)\b",
            raw,
            re.IGNORECASE,
        )
    )


def _internal_warnings(warnings: list[str]) -> list[str]:
    """Drop learner-facing NLP noise; keep real merge/API issues."""
    drop_markers = (
        "NLP:",
        "rule-based",
        "mathcore",
        "diễn giải đề",
        "AI để diễn giải",
    )
    kept: list[str] = []
    for warning in warnings:
        lower = warning.lower()
        if any(marker.lower() in lower or marker in warning for marker in drop_markers):
            continue
        kept.append(warning)
    return kept
