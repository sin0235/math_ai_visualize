from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_NLP_INPUT_CHARS = 2_000
MAX_NLP_CONTEXT_CHARS = 20_000

NlpTarget = Literal["auto", "render", "geometry_solve", "algebra", "analyzer", "ocr"]
NlpInputMode = Literal["natural", "math", "mixed"]
NlpInputFormat = Literal["auto", "plain", "latex", "structured"]
ProvenanceSource = Literal[
    "raw",
    "normalized",
    "rule",
    "existing_metadata",
    "ocr",
    "user_confirmed",
    "deterministic_engine",
    "language_model",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterpretationStatus(str, Enum):
    ACCEPTED = "accepted"
    NEEDS_CONFIRMATION = "needs_confirmation"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"


class TextSpan(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "TextSpan":
        if self.end <= self.start:
            raise ValueError("end phải lớn hơn start")
        return self


class Provenance(StrictModel):
    source: ProvenanceSource
    adapter: str | None = Field(default=None, max_length=80)
    version: str | None = Field(default=None, max_length=40)
    spans: list[TextSpan] = Field(default_factory=list, max_length=32)
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=256)


class InputEnvelope(StrictModel):
    text: str = Field(min_length=1, max_length=MAX_NLP_INPUT_CHARS)
    target: NlpTarget = "auto"
    input_mode: NlpInputMode = "natural"
    input_format: NlpInputFormat = "auto"
    context: dict[str, Any] = Field(default_factory=dict)
    provenance: list[Provenance] = Field(default_factory=list, max_length=16)

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("context chỉ được chứa dữ liệu JSON hợp lệ") from error
        if len(serialized) > MAX_NLP_CONTEXT_CHARS:
            raise ValueError(f"context vượt quá {MAX_NLP_CONTEXT_CHARS} ký tự")
        return value


class MathIntent(StrictModel):
    domain: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=1, max_length=96)
    task: str = Field(min_length=1, max_length=96)
    subtype: str | None = Field(default=None, max_length=96)


class Entity(StrictModel):
    kind: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    value: str | float | int | bool | None = None
    unit: str | None = Field(default=None, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: list[Provenance] = Field(default_factory=list, max_length=8)


class Constraint(StrictModel):
    kind: str = Field(min_length=1, max_length=64)
    arguments: list[str] = Field(default_factory=list, max_length=12)
    value: str | float | int | bool | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: list[Provenance] = Field(default_factory=list, max_length=8)


class Ambiguity(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    field: str | None = Field(default=None, max_length=96)
    alternatives: list[str] = Field(default_factory=list, max_length=8)
    provenance: list[Provenance] = Field(default_factory=list, max_length=8)


class FieldConfidence(StrictModel):
    field: str = Field(min_length=1, max_length=96)
    confidence: float = Field(ge=0.0, le=1.0)
    calibrated: bool = False


class InterpretationCandidate(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=96)
    intent: MathIntent
    canonical_text: str | None = Field(default=None, max_length=MAX_NLP_INPUT_CHARS)
    canonical_payload: dict[str, Any] | None = None
    entities: list[Entity] = Field(default_factory=list, max_length=64)
    constraints: list[Constraint] = Field(default_factory=list, max_length=64)
    ambiguities: list[Ambiguity] = Field(default_factory=list, max_length=16)
    field_confidences: list[FieldConfidence] = Field(default_factory=list, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list, max_length=16)
    missing_fields: list[str] = Field(default_factory=list, max_length=16)
    unsupported_reason: str | None = Field(default=None, max_length=500)
    clarification_question: str | None = Field(default=None, max_length=500)
    provenance: list[Provenance] = Field(default_factory=list, max_length=16)


ExcludeAutoTarget = Literal["render", "geometry_solve", "algebra", "analyzer", "ocr"]


class InterpretationResponse(StrictModel):
    target: ExcludeAutoTarget
    status: InterpretationStatus
    normalized_text: str
    candidates: list[InterpretationCandidate] = Field(default_factory=list, max_length=8)
    selected_candidate_id: str | None = Field(default=None, max_length=96)
    adapter_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_selection(self) -> "InterpretationResponse":
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        if self.selected_candidate_id is not None and self.selected_candidate_id not in candidate_ids:
            raise ValueError("selected_candidate_id không tồn tại trong candidates")
        if self.status == InterpretationStatus.ACCEPTED and self.selected_candidate_id is None:
            raise ValueError("accepted cần selected_candidate_id")
        if self.status in {InterpretationStatus.ABSTAINED, InterpretationStatus.UNSUPPORTED} and self.selected_candidate_id is not None:
            raise ValueError("abstained/unsupported không được tự chọn candidate")
        return self


class GroundedClaim(StrictModel):
    claim_id: str = Field(min_length=1, max_length=96)
    kind: str = Field(min_length=1, max_length=64)
    deterministic_text: str = Field(min_length=1, max_length=2_000)
    claim_text: str | None = Field(default=None, max_length=2_000)
    formula_latex: str | None = Field(default=None, max_length=2_000)
    result_latex: str | None = Field(default=None, max_length=2_000)
    theorem: str | None = Field(default=None, max_length=256)
    theorem_id: str | None = Field(default=None, max_length=128)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    highlight_object_ids: list[str] = Field(default_factory=list, max_length=32)
    relation_ids: list[str] = Field(default_factory=list, max_length=32)
    construction_actions: list[dict[str, Any]] = Field(default_factory=list, max_length=16)
    confidence: str = Field(min_length=1, max_length=32)
    provenance: list[Provenance] = Field(default_factory=list, max_length=16)


class ExplanationPlan(StrictModel):
    plan_id: str = Field(min_length=1, max_length=96)
    claims: list[GroundedClaim] = Field(min_length=1, max_length=256)
    answer: str = Field(min_length=1, max_length=4_000)
    answer_latex: str | None = Field(default=None, max_length=4_000)
    verification_state: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExplanationPlan":
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id phải duy nhất")
        return self