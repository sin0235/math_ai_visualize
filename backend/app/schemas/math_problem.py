from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.math_curriculum import CURRICULUM_VERSION, SKILLS


ProblemDomain = Literal["algebra", "function", "geometry"]
ProblemInputKind = Literal["expression", "function_analysis", "geometry_scene"]
ProblemSourceKind = Literal["manual", "mathlive", "ocr", "api", "scene"]


class ProblemIrModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemSource(ProblemIrModel):
    kind: ProblemSourceKind
    original: str = Field(min_length=1, max_length=20_000)
    canonical: str = Field(min_length=1, max_length=20_000)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CurriculumReference(ProblemIrModel):
    version: str = CURRICULUM_VERSION
    skill_ids: list[str] = Field(default_factory=list)
    grade_min: int | None = Field(default=None, ge=6, le=12)
    grade_max: int | None = Field(default=None, ge=6, le=12)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != CURRICULUM_VERSION:
            raise ValueError(f"Curriculum version không được hỗ trợ: {value}")
        return value

    @field_validator("skill_ids")
    @classmethod
    def validate_skill_ids(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        unknown = sorted(set(unique) - set(SKILLS))
        if unknown:
            raise ValueError(f"Skill ID không tồn tại: {', '.join(unknown)}")
        return unique


class ExpressionProblemInput(ProblemIrModel):
    kind: Literal["expression"] = "expression"
    expression: str
    variables: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    domain: Literal["R", "C", "N", "Z"] = "R"
    relations: list[str] = Field(default_factory=list)


class FunctionAnalysisProblemInput(ProblemIrModel):
    kind: Literal["function_analysis"] = "function_analysis"
    expression: str
    variable: str = "x"
    parameters: dict[str, str | float | None] = Field(default_factory=dict)
    requested_analyses: list[str] = Field(default_factory=lambda: ["analyze"])


class GeometrySceneProblemInput(ProblemIrModel):
    kind: Literal["geometry_scene"] = "geometry_scene"
    scene_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    scene_topic: str
    method: Literal["oxyz", "classical"]


ProblemInput = Annotated[
    ExpressionProblemInput | FunctionAnalysisProblemInput | GeometrySceneProblemInput,
    Field(discriminator="kind"),
]


class ProblemEnvelope(ProblemIrModel):
    schema_version: Literal["math-problem-ir-v1"] = "math-problem-ir-v1"
    domain: ProblemDomain
    task: str = Field(min_length=1, max_length=128)
    source: ProblemSource
    curriculum: CurriculumReference
    input: ProblemInput
    goal: str = Field(min_length=1, max_length=20_000)
    givens: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)