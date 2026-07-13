from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


GeometryTask = Literal[
    "distance",
    "angle",
    "area",
    "volume",
    "prove",
    "construct",
    "intersection",
    "projection",
    "reflection",
    "equation",
    "relation",
]
GeometryVerificationState = Literal["verified", "partial", "insufficient", "unsupported"]
GeometryEvidenceStatus = Literal["given", "verified", "derived", "unverified", "failed"]
ConstructionActionType = Literal[
    "highlight",
    "add_point",
    "connect_points",
    "project_point",
    "intersect_objects",
    "add_auxiliary_line",
    "add_auxiliary_plane",
]


class GeometryReasoningModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeometryGoal(GeometryReasoningModel):
    task: GeometryTask
    subtype: str = Field(min_length=1, max_length=96)
    target_object_ids: list[str] = Field(min_length=1, max_length=12)
    relation_type: str | None = Field(default=None, max_length=64)
    method: Literal["classical", "oxyz"] = "classical"


class VerificationEvidence(GeometryReasoningModel):
    source: Literal["object", "relation", "annotation", "derived_fact", "theorem"]
    ref_id: str = Field(min_length=1, max_length=128)
    status: GeometryEvidenceStatus
    verifier: str | None = Field(default=None, max_length=80)
    details: dict[str, Any] = Field(default_factory=dict)


class GeometryFact(GeometryReasoningModel):
    fact_id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=64)
    object_ids: list[str] = Field(default_factory=list, max_length=12)
    value: str | float | int | bool | None = None
    provenance: Literal["given", "verified", "derived", "construction_only"]
    evidence: list[VerificationEvidence] = Field(min_length=1, max_length=16)


class ProofClaim(GeometryReasoningModel):
    claim_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=2_000)
    fact_ids: list[str] = Field(default_factory=list, max_length=32)
    theorem_id: str | None = Field(default=None, max_length=128)
    depends_on: list[str] = Field(default_factory=list, max_length=32)


class ConstructionAction(GeometryReasoningModel):
    action_id: str = Field(min_length=1, max_length=128)
    type: ConstructionActionType
    source_object_ids: list[str] = Field(default_factory=list, max_length=12)
    result_object_id: str | None = Field(default=None, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)


class GeometryProofStep(GeometryReasoningModel):
    index: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=4_000)
    claim: ProofClaim
    highlight_object_ids: list[str] = Field(default_factory=list, max_length=32)
    relation_ids: list[str] = Field(default_factory=list, max_length=32)
    construction_actions: list[ConstructionAction] = Field(default_factory=list, max_length=16)


class GeometryProofPlan(GeometryReasoningModel):
    goal: GeometryGoal
    facts: list[GeometryFact] = Field(default_factory=list, max_length=256)
    steps: list[GeometryProofStep] = Field(default_factory=list, max_length=128)
    answer: str = Field(min_length=1, max_length=4_000)
    verification_state: GeometryVerificationState

    @model_validator(mode="after")
    def validate_proof_graph(self) -> "GeometryProofPlan":
        fact_ids = [fact.fact_id for fact in self.facts]
        claim_ids = [step.claim.claim_id for step in self.steps]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("fact_id phải duy nhất")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id phải duy nhất")

        known_facts = set(fact_ids)
        known_claims: set[str] = set()
        for expected_index, step in enumerate(self.steps, start=1):
            if step.index != expected_index:
                raise ValueError("index của proof step phải liên tục từ 1")
            missing_facts = set(step.claim.fact_ids) - known_facts
            if missing_facts:
                raise ValueError(f"Claim {step.claim.claim_id} tham chiếu fact không tồn tại: {sorted(missing_facts)}")
            missing_claims = set(step.claim.depends_on) - known_claims
            if missing_claims:
                raise ValueError(f"Claim {step.claim.claim_id} phụ thuộc claim chưa được chứng minh: {sorted(missing_claims)}")
            known_claims.add(step.claim.claim_id)
        return self