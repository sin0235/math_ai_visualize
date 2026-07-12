from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scene import Renderer, SceneView


DerivedFactProvenance = Literal["given", "verified", "computed", "render_only"]
Position3 = tuple[float, float, float]


class ProjectionModelV3(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectionBoundsV3(ProjectionModelV3):
    minimum: Position3
    maximum: Position3
    center: Position3
    radius: float = Field(gt=0)


class ProjectionPointV3(ProjectionModelV3):
    object_id: str
    name: str
    label: str | None = None
    position: Position3
    visible: bool = True


class ProjectionLinearV3(ProjectionModelV3):
    object_id: str
    name: str
    kind: Literal["segment", "line", "vector"]
    point_ids: tuple[str, str]
    positions: tuple[Position3, Position3]
    visible: bool = True
    color: str | None = None
    line_width: float | None = None
    style: Literal["solid", "dashed", "dotted"] | None = None
    extent: float | None = Field(default=None, gt=0)


class ProjectionCircleV3(ProjectionModelV3):
    object_id: str
    name: str
    center_point_id: str
    center: Position3
    radius: float = Field(gt=0)
    visible: bool = True


class ProjectionFunctionV3(ProjectionModelV3):
    object_id: str
    name: str
    expression: str
    domain: tuple[float | str, float | str] | None = None
    visible: bool = True


class ProjectionSurfaceV3(ProjectionModelV3):
    object_id: str
    name: str
    kind: Literal["face", "plane"]
    point_ids: list[str]
    positions: list[Position3]
    color: str
    opacity: float = Field(ge=0, le=1)
    visible: bool = True
    extent: float | None = Field(default=None, gt=0)
    show_normal: bool = False


class ProjectionSphereV3(ProjectionModelV3):
    object_id: str
    name: str
    center_point_id: str
    center: Position3
    radius: float = Field(gt=0)
    color: str
    opacity: float = Field(ge=0, le=1)
    visible: bool = True


class ProjectionAnnotationV3(ProjectionModelV3):
    annotation_id: str
    type: str
    target_ids: list[str]
    label: str | None = None
    color: str | None = None
    provenance: DerivedFactProvenance
    relation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderProjectionV3(ProjectionModelV3):
    scene_id: str
    revision: int = Field(ge=1)
    renderer: Renderer
    dimension: Literal["2d", "3d"]
    object_names: dict[str, str]
    points: list[ProjectionPointV3] = Field(default_factory=list)
    linear: list[ProjectionLinearV3] = Field(default_factory=list)
    circles: list[ProjectionCircleV3] = Field(default_factory=list)
    functions: list[ProjectionFunctionV3] = Field(default_factory=list)
    surfaces: list[ProjectionSurfaceV3] = Field(default_factory=list)
    spheres: list[ProjectionSphereV3] = Field(default_factory=list)
    annotations: list[ProjectionAnnotationV3] = Field(default_factory=list)
    bounds: ProjectionBoundsV3
    view: SceneView


class RenderPayloadV3(ProjectionModelV3):
    renderer: Renderer
    geogebra_commands: list[str] | None = None
    three_scene: dict[str, Any] | None = None