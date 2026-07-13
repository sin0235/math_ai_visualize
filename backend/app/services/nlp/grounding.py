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
    theorem_id: str | None
    claim: str | None
    depends_on: list[str]
    highlight_object_ids: list[str]
    relation_ids: list[str]
    construction_actions: list[dict[str, object]]
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
        allowed_entities = _geometry_entities(_claim_anchors(claim)) if _has_geometry_anchors(claim) else None
        validated[rewrite.claim_id] = LanguageRewrite(
            claim_id=rewrite.claim_id,
            **{
                field: _validated_text(getattr(rewrite, field), allowed_tokens, allowed_entities)
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
        claim_text=step.claim,
        formula_latex=step.formula_latex or step.substitution_latex,
        result_latex=step.result_latex,
        theorem=step.theorem,
        theorem_id=step.theorem_id,
        depends_on=list(step.depends_on),
        highlight_object_ids=list(step.highlight_object_ids),
        relation_ids=list(step.relation_ids),
        construction_actions=[dict(action) for action in step.construction_actions],
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


def _validated_text(
    value: str | None,
    allowed_tokens: set[str],
    allowed_entities: set[str] | None = None,
) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned or _LATEX_RE.search(cleaned):
        return None
    if not _math_tokens(cleaned) <= allowed_tokens:
        return None
    if allowed_entities is not None and not _geometry_entities(cleaned) <= allowed_entities:
        return None
    return cleaned


def _geometry_entities(value: str) -> set[str]:
    entities: set[str] = set()
    for match in re.finditer(r"(?<![\wÀ-ỹ])(?:[A-Z](?:\d+|')?|[A-Z]{2,})(?![\wÀ-ỹ])", value):
        prefix = value[:match.start()].rstrip()
        if not prefix or prefix[-1] in ".!?;:":
            continue
        entities.add(match.group(0))
    return entities


def _has_geometry_anchors(claim: GroundedClaim) -> bool:
    return bool(claim.theorem_id or claim.highlight_object_ids or claim.relation_ids or claim.construction_actions)


def _math_tokens(value: str) -> set[str]:
    return {token.lower() for token in _MATH_TOKEN_RE.findall(value)}


def _claim_anchors(claim: GroundedClaim) -> str:
    scalar_values = (
        claim.deterministic_text,
        claim.claim_text,
        claim.formula_latex,
        claim.result_latex,
        claim.theorem,
        claim.theorem_id,
        *claim.depends_on,
        *claim.highlight_object_ids,
        *claim.relation_ids,
    )
    construction_values = (
        str(value)
        for action in claim.construction_actions
        for value in action.values()
    )
    return " ".join(str(value) for value in (*scalar_values, *construction_values) if value)


def _plan_anchors(plan: ExplanationPlan) -> tuple:
    return (
        plan.answer,
        plan.answer_latex,
        plan.verification_state,
        tuple(
            (
                claim.claim_id,
                claim.kind,
                claim.claim_text,
                claim.formula_latex,
                claim.result_latex,
                claim.theorem,
                claim.theorem_id,
                tuple(claim.depends_on),
                tuple(claim.highlight_object_ids),
                tuple(claim.relation_ids),
                tuple(_freeze_mapping(action) for action in claim.construction_actions),
                claim.confidence,
            )
            for claim in plan.claims
        ),
    )


def _freeze_mapping(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze_mapping(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_mapping(item) for item in value)
    return value


def _engine_provenance(adapter: str) -> Provenance:
    return Provenance(source="deterministic_engine", adapter=adapter, version="grounding-v1")