"""Lightweight cost scoring for algebra requests (soft quota / reject heavy loads)."""

from __future__ import annotations

import re

from app.schemas.algebra import AlgebraSolveRequest

_TOPIC_WEIGHT = {
    "auto": 1.0,
    "equation": 1.0,
    "inequality": 1.2,
    "expression": 0.8,
    "exponential_log": 1.3,
    "trigonometry": 1.5,
    "complex": 1.3,
    "system": 1.6,
    "sequence": 0.7,
    "combinatorics_probability": 0.6,
    "statistics": 0.7,
    "parameter": 1.4,
    "calculus_derivative": 1.4,
    "calculus_limit": 1.5,
    "calculus_integral": 1.5,
    "calculus_derivative_by_definition": 1.6,
    "calculus_continuous_at": 1.3,
}


def algebra_request_cost(request: AlgebraSolveRequest) -> int:
    text = request.input or ""
    length = len(text)
    parens = text.count("(") + text.count("[")
    powers = len(re.findall(r"\*\*|\^", text))
    semis = text.count(";")
    weight = _TOPIC_WEIGHT.get(str(request.topic), 1.0)
    ai_boost = 1.35 if (request.options.use_ai_extraction or request.options.ai_explanation) else 1.0
    raw = (length / 40.0) + parens * 1.5 + powers * 3.0 + semis * 4.0
    return int(max(1, round(raw * weight * ai_boost)))


def cost_exceeds_limit(score: int, max_cost: int) -> bool:
    return score > max(1, int(max_cost))
