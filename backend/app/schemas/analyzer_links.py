from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from app.schemas.analysis import StrictModel

AnalyzerTarget = Literal["algebra_solver", "simulation", "geogebra_lab", "render", "practice"]
AnalyzerLinkScope = Literal["open", "embed", "api"]


class AnalyzerLinkCreateRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    target: AnalyzerTarget


class AnalyzerShareCreateRequest(AnalyzerLinkCreateRequest):
    visibility: Literal["user", "public"] = "user"
    expires_in_minutes: int = Field(default=1440, ge=5, le=10_080)
    scopes: list[AnalyzerLinkScope] = Field(default_factory=lambda: ["open"], min_length=1, max_length=3)
    allowed_origins: list[HttpUrl] = Field(default_factory=list, max_length=8)
    max_uses: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_public_policy(self) -> "AnalyzerShareCreateRequest":
        self.scopes = list(dict.fromkeys(self.scopes))
        if {"embed", "api"}.intersection(self.scopes) and not self.allowed_origins:
            raise ValueError("Share có scope embed hoặc api phải khai báo allowed_origins.")
        return self


class AnalyzerLinkConsumeRequest(StrictModel):
    target: AnalyzerTarget
    scope: AnalyzerLinkScope = "open"


class AlgebraHandoffPayload(StrictModel):
    version: Literal["algebra-solver-v1"] = "algebra-solver-v1"
    input: str = Field(min_length=1, max_length=2000)
    input_format: Literal["plain"] = "plain"
    topic: Literal["equation"] = "equation"
    domain: Literal["R"] = "R"


class SimulationHandoffPayload(StrictModel):
    version: Literal["function-simulation-v1"] = "function-simulation-v1"
    simulation_id: Literal["g12.calc.derivative-survey"] = "g12.calc.derivative-survey"
    expression: str = Field(min_length=1, max_length=1000)
    x_min: float = Field(ge=-1_000_000, le=1_000_000)
    x_max: float = Field(ge=-1_000_000, le=1_000_000)
    verification_status: str = Field(max_length=64)


class GeoGebraHandoffPayload(StrictModel):
    version: Literal["geogebra-commands-v1"] = "geogebra-commands-v1"
    mode: Literal["graphing"] = "graphing"
    commands: list[str] = Field(min_length=1, max_length=40)


class RenderHandoffPayload(StrictModel):
    version: Literal["render-problem-v1"] = "render-problem-v1"
    problem_text: str = Field(min_length=1, max_length=2000)
    preferred_renderer: Literal["geogebra"] = "geogebra"


class PracticeHandoffPayload(StrictModel):
    version: Literal["practice-prompt-v1"] = "practice-prompt-v1"
    problem_text: str = Field(min_length=1, max_length=3000)
    source_verification: str = Field(max_length=64)


AnalyzerHandoffPayload = AlgebraHandoffPayload | SimulationHandoffPayload | GeoGebraHandoffPayload | RenderHandoffPayload | PracticeHandoffPayload


class AnalyzerLinkCreated(StrictModel):
    short_id: str
    kind: Literal["handoff", "share"]
    target: AnalyzerTarget
    url: str
    expires_at: str
    visibility: Literal["user", "public"]
    scopes: list[AnalyzerLinkScope]


class AnalyzerLinkConsumed(StrictModel):
    short_id: str
    kind: Literal["handoff", "share"]
    target: AnalyzerTarget
    payload_version: str
    payload: AnalyzerHandoffPayload
    expires_at: str