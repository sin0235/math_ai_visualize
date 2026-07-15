from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.schemas.nlp import InputEnvelope, InterpretationCandidate, InterpretationResponse
from app.services.nlp.pipeline import interpret_input

RolloutMode = Literal["off", "shadow", "authoritative"]


@dataclass(frozen=True)
class NlpRolloutDecision:
    mode: RolloutMode
    response: InterpretationResponse
    candidate: InterpretationCandidate | None
    mismatch: bool

    @property
    def can_apply(self) -> bool:
        return self.mode == "authoritative" and self.response.status.value == "accepted" and self.candidate is not None

    @property
    def safe_metadata(self) -> dict[str, Any]:
        return {
            "taxonomy_code": "shadow_mismatch" if self.mismatch else "rollout_match",
            "target": self.response.target,
            "status": self.response.status.value,
            "confidence_bucket": confidence_bucket(self.candidate.confidence if self.candidate else None),
            "candidate_count": len(self.response.candidates),
            "adapter_version": self.response.adapter_version,
            "validation_state": self.candidate.validation.state if self.candidate else None,
            "validation_codes": self.candidate.validation.codes if self.candidate else [],
            "mode": self.mode,
            "mismatch": self.mismatch,
        }


def evaluate_nlp_rollout(
    envelope: InputEnvelope,
    *,
    shadow_rules: list[str],
    authoritative_rules: list[str],
    response: InterpretationResponse | None = None,
    force_authoritative: bool = False,
    legacy_intent: str | None = None,
    legacy_status: str | None = None,
    legacy_canonical: str | None = None,
) -> NlpRolloutDecision | None:
    if response is None and not _target_has_rules(envelope.target, shadow_rules, authoritative_rules):
        return None
    response = response or interpret_input(envelope)
    candidate = _selected_candidate(response)
    mode = "authoritative" if force_authoritative else rollout_mode(response, candidate, shadow_rules, authoritative_rules)
    if mode == "off":
        return None
    mismatch = _is_mismatch(response, candidate, legacy_intent, legacy_status, legacy_canonical)
    return NlpRolloutDecision(mode=mode, response=response, candidate=candidate, mismatch=mismatch)


def rollout_mode(
    response: InterpretationResponse,
    candidate: InterpretationCandidate | None,
    shadow_rules: list[str],
    authoritative_rules: list[str],
) -> RolloutMode:
    keys = _candidate_rule_keys(response.target, candidate)
    if any(rule in keys for rule in authoritative_rules):
        return "authoritative"
    if any(rule in keys for rule in shadow_rules):
        return "shadow"
    return "off"


def confidence_bucket(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    if confidence < 0.2:
        return "very_low"
    if confidence < 0.4:
        return "low"
    if confidence < 0.65:
        return "medium"
    if confidence < 0.85:
        return "high"
    return "very_high"


def _target_has_rules(target: str, *rule_groups: list[str]) -> bool:
    prefix = f"{target}:"
    return any(rule == target or rule.startswith(prefix) for rules in rule_groups for rule in rules)


def _selected_candidate(response: InterpretationResponse) -> InterpretationCandidate | None:
    if response.selected_candidate_id:
        return next(
            (candidate for candidate in response.candidates if candidate.candidate_id == response.selected_candidate_id),
            None,
        )
    return response.candidates[0] if response.candidates else None


def _candidate_rule_keys(target: str, candidate: InterpretationCandidate | None) -> set[str]:
    keys = {target}
    if candidate is None:
        return keys
    for value in (candidate.intent.domain, candidate.intent.topic, candidate.intent.task, candidate.intent.subtype):
        if value:
            keys.add(f"{target}:{value.lower()}")
    return keys


def _is_mismatch(
    response: InterpretationResponse,
    candidate: InterpretationCandidate | None,
    legacy_intent: str | None,
    legacy_status: str | None,
    legacy_canonical: str | None,
) -> bool:
    if legacy_status is not None and legacy_status != response.status.value:
        return True
    if legacy_intent is not None:
        current_intent = candidate.intent.task if candidate else "unknown"
        if legacy_intent.lower() != current_intent.lower():
            return True
    if legacy_canonical is not None and candidate is not None and candidate.canonical_text is not None:
        if _normalize_canonical(legacy_canonical) != _normalize_canonical(candidate.canonical_text):
            return True
    return False


def _normalize_canonical(value: str | None) -> str | None:
    return "".join(value.split()).replace("**", "^").lower() if value is not None else None
