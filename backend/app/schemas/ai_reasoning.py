from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictReasoningModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasoningProblemAnalysis(StrictReasoningModel):
    original_text: str = Field(min_length=1, max_length=20_000)
    problem_type: Literal[
        "solid_geometry",
        "coordinate_2d",
        "coordinate_3d",
        "function_graph",
        "conic",
        "vector_2d",
        "vector_3d",
        "circle",
        "applied_math",
        "unknown",
    ]
    grade: Literal[10, 11, 12] | None = None
    key_conditions: list[str] = Field(default_factory=list, max_length=100)
    implicit_properties: list[str] = Field(default_factory=list, max_length=100)
    requires_auxiliary_points: bool = False


class ReasoningCoordinateSystem(StrictReasoningModel):
    origin_point: str
    x_axis_along: str
    y_axis_along: str
    z_axis_along: str | None = None


class ReasoningGeometricModel(StrictReasoningModel):
    base_shape: str
    renderer: Literal["geogebra_2d", "threejs_3d"]
    dimension: Literal["2d", "3d"]
    coordinate_system: ReasoningCoordinateSystem

    @model_validator(mode="after")
    def validate_renderer_dimension(self) -> "ReasoningGeometricModel":
        expected = "2d" if self.renderer == "geogebra_2d" else "3d"
        if self.dimension != expected:
            raise ValueError("Reasoning renderer không khớp dimension.")
        return self


class ReasoningPoint(StrictReasoningModel):
    name: str = Field(min_length=1, max_length=64)
    role: Literal["vertex", "center", "midpoint", "foot", "intersection", "auxiliary", "focus", "apex"]
    coordinates: dict[str, float | int | None]
    derivation: str = Field(default="", max_length=2_000)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "ReasoningPoint":
        if set(self.coordinates) - {"x", "y", "z"} or not {"x", "y"} <= set(self.coordinates):
            raise ValueError("Reasoning point phải có x, y và chỉ được thêm z.")
        return self


class ReasoningEdgeOrFace(StrictReasoningModel):
    type: Literal["segment", "face", "line", "circle", "function_graph", "sphere", "plane", "vector"]
    points: list[str] = Field(default_factory=list, max_length=100)
    properties: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2_000)


class ReasoningRelation(StrictReasoningModel):
    type: Literal[
        "perpendicular",
        "equal_length",
        "parallel",
        "midpoint",
        "tangent",
        "intersection",
        "collinear",
        "coplanar",
        "on_line",
        "on_plane",
        "on_sphere",
        "on_circle",
        "distance",
        "angle",
    ]
    objects: list[str] = Field(default_factory=list, max_length=20)
    value: float | int | None = None
    reasoning: str = Field(default="", max_length=2_000)


class ReasoningAnnotation(StrictReasoningModel):
    type: Literal["right_angle", "equal_marks", "length", "angle"]
    target: str
    label: str | None = Field(default=None, max_length=120)
    details: str = Field(default="", max_length=1_000)


class ReasoningParameter(StrictReasoningModel):
    name: str
    label: str | None = None
    min: float
    max: float
    default: float
    step: float = Field(gt=0)
    expr_for_points: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> "ReasoningParameter":
        if self.min >= self.max or not self.min <= self.default <= self.max:
            raise ValueError("Khoảng reasoning parameter không hợp lệ.")
        return self


class SceneReasoningPlan(StrictReasoningModel):
    problem_analysis: ReasoningProblemAnalysis
    geometric_model: ReasoningGeometricModel
    points: list[ReasoningPoint] = Field(default_factory=list, max_length=500)
    edges_and_faces: list[ReasoningEdgeOrFace] = Field(default_factory=list, max_length=500)
    relations: list[ReasoningRelation] = Field(default_factory=list, max_length=500)
    annotations_needed: list[ReasoningAnnotation] = Field(default_factory=list, max_length=500)
    parameters: list[ReasoningParameter] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_references(self) -> "SceneReasoningPlan":
        names = [point.name for point in self.points]
        if len(names) != len(set(names)):
            raise ValueError("Reasoning plan có tên điểm trùng nhau.")
        known = set(names)
        for item in self.edges_and_faces:
            if item.points and not set(item.points) <= known:
                raise ValueError("Reasoning plan tham chiếu điểm chưa khai báo.")
        return self