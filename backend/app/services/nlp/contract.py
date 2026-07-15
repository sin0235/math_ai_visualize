from __future__ import annotations

from app.schemas.nlp import InterpretationCandidate, InterpretationValidation, NlpFact

PROMPT_CONTRACT_VERSION = "nlp-ir-v2"
_NON_GOAL_TASKS = {"unknown", "render_scene", "extract_from_ocr", "normalize", "identify"}


def finalize_candidate_contract(candidate: InterpretationCandidate) -> InterpretationCandidate:
    """Chiếu candidate cũ sang IR v2 rồi đánh giá tính nhất quán nội bộ."""
    givens = candidate.givens or [
        NlpFact(
            kind=item.kind,
            name=item.name,
            value=item.value,
            confidence=item.confidence,
            provenance=item.provenance,
        )
        for item in candidate.entities
    ] + [
        NlpFact(
            kind=item.kind,
            arguments=item.arguments,
            value=item.value,
            confidence=item.confidence,
            provenance=item.provenance,
        )
        for item in candidate.constraints
    ]
    goals = candidate.goals
    if not goals and candidate.intent.task not in _NON_GOAL_TASKS:
        goals = [
            NlpFact(
                kind="goal",
                name=candidate.intent.task,
                arguments=[item.name for item in candidate.entities[:8]],
                confidence=_field_confidence(candidate, "intent"),
                provenance=candidate.provenance,
            )
        ]
    unknowns = list(dict.fromkeys([*candidate.unknowns, *candidate.missing_fields]))
    clarification_options = candidate.clarification_options or list(dict.fromkeys(
        option for ambiguity in candidate.ambiguities for option in ambiguity.alternatives
    ))[:8]
    projected = candidate.model_copy(update={
        "givens": givens,
        "goals": goals,
        "unknowns": unknowns,
        "clarification_options": clarification_options,
    })
    return projected.model_copy(update={"validation": validate_candidate_contract(projected)})


def validate_candidate_contract(candidate: InterpretationCandidate) -> InterpretationValidation:
    blocking: list[str] = []
    review: list[str] = []
    if candidate.unsupported_reason:
        blocking.append("unsupported")
    if candidate.intent.domain == "unknown" or candidate.intent.task == "unknown":
        review.append("unknown_intent")
    if candidate.missing_fields:
        review.append("missing_fields")
    if candidate.ambiguities:
        review.append("ambiguities")
    if candidate.intent.task not in _NON_GOAL_TASKS and not candidate.goals:
        review.append("missing_goal")
    if candidate.intent.domain in {"algebra", "function"} and not candidate.canonical_text:
        blocking.append("missing_canonical_text")
    codes = list(dict.fromkeys([*blocking, *review]))
    state = "rejected" if blocking else "needs_review" if review else "validated"
    return InterpretationValidation(state=state, codes=codes, contract_version=PROMPT_CONTRACT_VERSION)


def _field_confidence(candidate: InterpretationCandidate, field: str) -> float:
    matched = next((item.confidence for item in candidate.field_confidences if item.field == field), None)
    return min(candidate.confidence, matched) if matched is not None else candidate.confidence