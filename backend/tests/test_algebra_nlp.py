"""Tests for unified algebra NLP orchestration (LLM primary → mathcore-ready form)."""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.schemas.algebra import AlgebraSolveOptions, AlgebraSolveRequest
from app.services.algebra.ai_extraction import AlgebraExtractionPayload, merge_extraction_request
from app.services.algebra import ai_extraction
from app.services.nlp.algebra_nlp import resolve_algebra_nlp


def test_structured_equation_passthrough_no_llm(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("LLM must not run for symbolic input")

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", boom)
    result = asyncio.run(
        resolve_algebra_nlp(
            AlgebraSolveRequest(input="x^2-5*x+6=0", options=AlgebraSolveOptions(use_ai_extraction=True)),
            Settings(),
        )
    )
    assert result.source == "structured_passthrough"
    assert result.used_llm is False
    assert result.canonical_input == "x^2-5*x+6=0"


def test_template_passthrough_no_llm(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("LLM must not run for structured template")

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", boom)
    result = asyncio.run(
        resolve_algebra_nlp(
            AlgebraSolveRequest(
                input="arithmetic(u1=2,d=3,n=10)",
                options=AlgebraSolveOptions(use_ai_extraction=True),
            ),
            Settings(),
        )
    )
    assert result.source == "structured_passthrough"
    assert result.used_llm is False


def test_natural_language_uses_llm(monkeypatch):
    async def fake_extract(problem_text, base_request, settings):
        payload = AlgebraExtractionPayload(
            input="arithmetic(u1=2,u2=6,n=9)",
            input_format="structured",
            topic="sequence",
            domain="R",
        )
        return merge_extraction_request(base_request, payload)

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", fake_extract)
    result = asyncio.run(
        resolve_algebra_nlp(
            AlgebraSolveRequest(
                input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
                options=AlgebraSolveOptions(use_ai_extraction=True),
            ),
            Settings(),
        )
    )
    assert result.source == "llm"
    assert result.used_llm is True
    assert result.canonical_input == "arithmetic(u1=2,u2=6,n=9)"


def test_llm_failure_falls_back_rule_based(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", boom)
    result = asyncio.run(
        resolve_algebra_nlp(
            AlgebraSolveRequest(
                input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
                options=AlgebraSolveOptions(use_ai_extraction=True),
            ),
            Settings(),
        )
    )
    assert result.source == "rule_based_fallback"
    assert "arithmetic" in result.canonical_input
    assert "n=9" in result.canonical_input or "n=9" in result.canonical_input.replace(" ", "")
