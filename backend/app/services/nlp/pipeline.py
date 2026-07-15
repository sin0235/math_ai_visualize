from __future__ import annotations

from app.schemas.nlp import (
    ExcludeAutoTarget,
    InputEnvelope,
    InterpretationCandidate,
    InterpretationResponse,
    InterpretationStatus,
)
from app.services.nlp.adapters import ADAPTER_VERSION, default_registry
from app.services.nlp.contract import finalize_candidate_contract
from app.services.nlp.normalization import normalize_input
from app.services.nlp.router import AdapterRegistry, infer_target

MIN_ACCEPTED_CONFIDENCE = 0.65


def interpret_input(
    envelope: InputEnvelope,
    *,
    registry: AdapterRegistry | None = None,
) -> InterpretationResponse:
    normalized = normalize_input(envelope.text)
    target: ExcludeAutoTarget = infer_target(normalized.text, envelope.context) if envelope.target == "auto" else envelope.target
    active_registry = registry or default_registry()
    candidates = sorted(
        (
            finalize_candidate_contract(_with_input_provenance(candidate, envelope))
            for candidate in active_registry.resolve(target)(envelope, normalized)
        ),
        key=lambda candidate: (-candidate.confidence, candidate.candidate_id),
    )
    status, selected_candidate_id = decide_interpretation(candidates)
    return InterpretationResponse(
        target=target,
        status=status,
        normalized_text=normalized.text,
        candidates=candidates,
        selected_candidate_id=selected_candidate_id,
        adapter_version=ADAPTER_VERSION,
    )


def _with_input_provenance(
    candidate: InterpretationCandidate,
    envelope: InputEnvelope,
) -> InterpretationCandidate:
    provenance = list(candidate.provenance)
    for item in envelope.provenance:
        if item not in provenance:
            provenance.append(item)
    return candidate.model_copy(update={"provenance": provenance[-16:]})


def decide_interpretation(
    candidates: list[InterpretationCandidate],
) -> tuple[InterpretationStatus, str | None]:
    if not candidates:
        return InterpretationStatus.ABSTAINED, None
    if all(candidate.unsupported_reason for candidate in candidates):
        return InterpretationStatus.UNSUPPORTED, None

    supported = [candidate for candidate in candidates if candidate.unsupported_reason is None]
    if not supported:
        return InterpretationStatus.UNSUPPORTED, None
    top = supported[0]
    needs_confirmation = (
        bool(top.missing_fields)
        or bool(top.ambiguities)
        or top.confidence < MIN_ACCEPTED_CONFIDENCE
        or _top_candidates_are_close(supported)
    )
    if needs_confirmation:
        return InterpretationStatus.NEEDS_CONFIRMATION, top.candidate_id
    return InterpretationStatus.ACCEPTED, top.candidate_id


def _top_candidates_are_close(candidates: list[InterpretationCandidate]) -> bool:
    return len(candidates) > 1 and candidates[0].confidence - candidates[1].confidence < 0.1