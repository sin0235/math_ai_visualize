from typing import Literal

from pydantic import BaseModel, Field


ClassificationSource = Literal["rules", "existing_metadata", "hybrid_rules"]
AdvisorySeverity = Literal["info", "warning", "risk", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class ProblemClassification(BaseModel):
    domain: str = "unknown"
    topic: str = "unknown"
    task_type: str | None = None
    sub_type: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: ClassificationSource = "rules"
    signals: list[str] = Field(default_factory=list)
    supported_by_current_solver: bool | None = None


class AdvisoryFactor(BaseModel):
    code: str
    severity: AdvisorySeverity
    message: str
    weight: float = 0.0


class QualityRiskAdvisory(BaseModel):
    classification: ProblemClassification
    quality_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    factors: list[AdvisoryFactor] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
