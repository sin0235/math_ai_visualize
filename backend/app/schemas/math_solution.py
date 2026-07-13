from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.math_capabilities import CapabilitySnapshot
from app.schemas.math_problem import ProblemEnvelope


SolutionStatus = Literal[
    "solved_verified",
    "solved_partial",
    "needs_clarification",
    "unsupported",
    "invalid",
    "timeout",
]
Exactness = Literal["exact", "symbolic_checked", "numeric_checked", "partial", "unverified"]
VerificationCheckStatus = Literal["pass", "fail", "warn", "skip"]


class SolutionIrModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SolutionValue(SolutionIrModel):
    text: str
    latex: str | None = None
    exact: str | None = None
    approximate: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class SolutionStep(SolutionIrModel):
    step_id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=1)
    title: str
    explanation: str
    rule: str | None = None
    before: str | None = None
    after: str | None = None
    result: SolutionValue | None = None
    dependencies: list[str] = Field(default_factory=list)
    verification_level: Exactness = "unverified"


class SolutionClaim(SolutionIrModel):
    claim_id: str = Field(min_length=1, max_length=128)
    statement: str
    dependencies: list[str] = Field(default_factory=list)
    verification_level: Exactness = "unverified"


class VerificationEvidence(SolutionIrModel):
    policy_methods: list[str] = Field(default_factory=list)
    status: VerificationCheckStatus
    method: str
    detail: str | None = None
    error_bound: float | None = None


class Solution(SolutionIrModel):
    schema_version: Literal["math-solution-ir-v1"] = "math-solution-ir-v1"
    capability_version: str
    capability: CapabilitySnapshot
    problem: ProblemEnvelope
    status: SolutionStatus
    exactness: Exactness
    result: SolutionValue | None = None
    steps: list[SolutionStep] = Field(default_factory=list)
    claims: list[SolutionClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    verification: list[VerificationEvidence] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "Solution":
        if self.status == "solved_verified" and not self.verification:
            raise ValueError("solved_verified cần verification evidence")
        if self.status == "unsupported" and not self.unsupported_reason:
            raise ValueError("unsupported cần unsupported_reason")
        return self