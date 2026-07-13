from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol

from app.schemas.algebra import AlgebraSolveResponse, AlgebraSolveStep
from app.schemas.nlp import ExplanationPlan, GroundedClaim, Provenance

_MATH_TOKEN_RE = re.compile(r"(?:(?<![\w])\d+(?:[.,]\d+)?(?![\w])|[=<>≤≥≠±×÷^]|\\[A-Za-z]+)")
_LATEX_RE = re.compile(r"\\[A-Za-z]+(?:\{[^{}]*\})*|[$^_=<>≤≥≠±×÷]")


class GeometryStep(Protocol):
    index: int
    title: str
    explanation: str
    kind: str | None
    formula_latex: str | None
    substitution_latex: str | None
    result_latex: str | None
    theorem: str | None
    depends_on: list[str]
    sub_steps: list["GeometryStep"]


@dataclass(frozen=True)
class LanguageRewrite:
    claim_id: str
    title: str | None = None
    explanation: str | None = None
    goal: str | None = None
    why: str | None = None
    rule: str | None = None
    operation: str | None = None
    pitfall: str | None = None
    check: str | None = None


def build_algebra_explanation_plan(response: AlgebraSolveResponse) -> ExplanationPlan:
    claims = [
        claim
        for step in response.steps
        for claim in _algebra_claims(step, prefix="step")
    ]
    if not claims:
        claims = [_fallback_claim("step-0", response.answer, response.verification.status)]
    return ExplanationPlan(
        plan_id=f"algebra:{response.request_id or 'pending'}",
        claims=claims,
        answer=response.answer,
        answer_latex=response.answer_latex,
        verification_state=response.verification.status,
    )


def build_geometry_explanation_plan(result) -> ExplanationPlan:
    claims = [
        claim
        for step in result.steps
        for claim in _geometry_claims(step, prefix="step")
    ]
    if not claims:
        claims = [_fallback_claim("step-0", result.answer, result.confidence)]
    return ExplanationPlan(
        plan_id="geometry:current",
        claims=claims,
        answer=result.answer,
        verification_state=result.confidence,
    )


def validate_language_rewrites(
    plan: ExplanationPlan,
    rewrites: Iterable[LanguageRewrite],
) -> dict[str, LanguageRewrite]:
    claims = {claim.claim_id: claim for claim in plan.claims}
    validated: dict[str, LanguageRewrite] = {}
    seen: set[str] = set()
    for rewrite in rewrites:
        if rewrite.claim_id in seen or rewrite.claim_id not in claims:
            continue
        seen.add(rewrite.claim_id)
        claim = claims[rewrite.claim_id]
        allowed_tokens = _math_tokens(_claim_anchors(claim))
        validated[rewrite.claim_id] = LanguageRewrite(
            claim_id=rewrite.claim_id,
            **{
                field: _validated_text(getattr(rewrite, field), allowed_tokens)
                for field in (
                    "title",
                    "explanation",
                    "goal",
                    "why",
                    "rule",
                    "operation",
                    "pitfall",
                    "check",
                )
            },
        )
    return validated


def assert_plan_anchors_unchanged(before: ExplanationPlan, after: ExplanationPlan) -> None:
    if _plan_anchors(before) != _plan_anchors(after):
        raise ValueError("Language realization đã thay đổi grounded anchors")


def _algebra_claims(step: AlgebraSolveStep, *, prefix: str) -> list[GroundedClaim]:
    claim_id = f"{prefix}-{step.index}"
    claim = GroundedClaim(
        claim_id=claim_id,
        kind=step.kind or "step",
        deterministic_text=step.explanation or step.title,
        formula_latex=step.after_latex or step.expression_latex or step.before_latex,
        result_latex=step.result_latex,
        theorem=step.rule,
        confidence=step.confidence or "unverified",
        provenance=[_engine_provenance("algebra")],
    )
    children = [
        nested
        for sub_step in step.sub_steps
        for nested in _algebra_claims(sub_step, prefix=claim_id)
    ]
    return [claim, *children]


def _geometry_claims(step: GeometryStep, *, prefix: str) -> list[GroundedClaim]:
    claim_id = f"{prefix}-{step.index}"
    claim = GroundedClaim(
        claim_id=claim_id,
        kind=step.kind or "step",
        deterministic_text=step.explanation or step.title,
        formula_latex=step.formula_latex or step.substitution_latex,
        result_latex=step.result_latex,
        theorem=step.theorem,
        depends_on=list(step.depends_on),
        confidence="verified",
        provenance=[_engine_provenance("geometry")],
    )
    children = [
        nested
        for sub_step in step.sub_steps
        for nested in _geometry_claims(sub_step, prefix=claim_id)
    ]
    return [claim, *children]


def _fallback_claim(claim_id: str, answer: str, confidence: str) -> GroundedClaim:
    return GroundedClaim(
        claim_id=claim_id,
        kind="answer",
        deterministic_text=answer,
        confidence=confidence,
        provenance=[_engine_provenance("fallback")],
    )


def _validated_text(value: str | None, allowed_tokens: set[str]) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned or _LATEX_RE.search(cleaned):
        return None
    if not _math_tokens(cleaned) <= allowed_tokens:
        return None
    return cleaned


def _math_tokens(value: str) -> set[str]:
    return {token.lower() for token in _MATH_TOKEN_RE.findall(value)}


def _claim_anchors(claim: GroundedClaim) -> str:
    return " ".join(
        value
        for value in (
            claim.deterministic_text,
            claim.formula_latex,
            claim.result_latex,
            claim.theorem,
            *claim.depends_on,
        )
        if value
    )


def _plan_anchors(plan: ExplanationPlan) -> tuple:
    return (
        plan.answer,
        plan.answer_latex,
        plan.verification_state,
        tuple(
            (
                claim.claim_id,
                claim.kind,
                claim.formula_latex,
                claim.result_latex,
                claim.theorem,
                tuple(claim.depends_on),
                claim.confidence,
            )
            for claim in plan.claims
        ),
    )


def _engine_provenance(adapter: str) -> Provenance:
    return Provenance(source="deterministic_engine", adapter=adapter, version="grounding-v1")