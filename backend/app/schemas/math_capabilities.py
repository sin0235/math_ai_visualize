from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.math_curriculum.models import SkillStatus


class CapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MathCapability(CapabilityModel):
    capability_id: str
    skill_id: str
    strand: str
    grades: list[int]
    status: SkillStatus
    accepted_input_kinds: list[Literal["expression", "function_analysis", "geometry_scene"]]
    tasks: list[str]
    solvers: list[str]
    verifier_methods: list[str]
    minimum_exactness: Literal["exact", "symbolic_checked", "numeric_checked", "partial"]
    limits: dict[str, int | float | str | bool] = Field(default_factory=dict)
    examples: list[dict[str, str]] = Field(default_factory=list)


class AlgebraTopicCapability(CapabilityModel):
    topic: str
    label: str
    skill_ids: list[str]
    status: SkillStatus


class MathCapabilityUi(CapabilityModel):
    algebra_topics: list[AlgebraTopicCapability]
    keyboard_actions: dict[str, list[str]]


class MathCapabilityRegistry(CapabilityModel):
    version: str
    curriculum_version: str
    capabilities: list[MathCapability]
    ui: MathCapabilityUi


class CapabilitySnapshot(CapabilityModel):
    registry_version: str
    capability_ids: list[str]
    skill_ids: list[str]
    statuses: list[SkillStatus]
    accepted: bool
    reason: str | None = None
    limits: dict[str, int | float | str | bool] = Field(default_factory=dict)
    verifier_methods: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)