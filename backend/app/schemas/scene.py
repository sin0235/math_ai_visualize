from typing import Any, Literal

from pydantic import BaseModel, Field


Renderer = Literal["geogebra_2d", "geogebra_3d", "threejs_3d"]
AiProvider = Literal["auto", "openrouter", "openrouter_gpt_oss", "nvidia", "nvidia_v4_flash", "nvidia_kimi_k2", "mock"]
Topic = Literal[
    "coordinate_2d",
    "function_graph",
    "conic",
    "vector_2d",
    "solid_geometry",
    "coordinate_3d",
    "unknown",
]


class Point2D(BaseModel):
    type: Literal["point_2d"] = "point_2d"
    name: str
    x: float
    y: float


class Point3D(BaseModel):
    type: Literal["point_3d"] = "point_3d"
    name: str
    x: float
    y: float
    z: float


class Segment(BaseModel):
    type: Literal["segment"] = "segment"
    name: str | None = None
    points: list[str] = Field(min_length=2, max_length=2)
    hidden: bool = False


class Line2D(BaseModel):
    type: Literal["line_2d"] = "line_2d"
    name: str | None = None
    through: list[str] = Field(min_length=2, max_length=2)


class Vector2D(BaseModel):
    type: Literal["vector_2d"] = "vector_2d"
    name: str | None = None
    from_point: str
    to_point: str


class Circle2D(BaseModel):
    type: Literal["circle_2d"] = "circle_2d"
    name: str | None = None
    center: str
    through: str | None = None
    radius: float | None = None


class FunctionGraph(BaseModel):
    type: Literal["function_graph"] = "function_graph"
    name: str = "f"
    expression: str


class Face(BaseModel):
    type: Literal["face"] = "face"
    name: str | None = None
    points: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = 0.22


class Sphere(BaseModel):
    type: Literal["sphere"] = "sphere"
    name: str | None = None
    center: str
    radius: float
    color: str = "#5da9ff"
    opacity: float = 0.18


class Relation(BaseModel):
    type: str  # perpendicular, equal_length, parallel, ...
    object_1: str
    object_2: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Annotation(BaseModel):
    """Annotation to display on the rendered figure.

    Supported types:
    - length: label showing distance on a segment (target = "A-B", label = "a")
    - angle: label showing angle measure (target = "B", metadata.arms = ["A","C"], label = "60°")
    - right_angle: small square symbol at a right angle (target = "B", metadata.arms = ["A","C"])
    - equal_marks: tick marks on edges with equal length (target = "A-B", metadata.group = 1)
    - coordinate_label: show (x,y,z) next to a point (target = "A")
    """
    type: str
    target: str
    label: str | None = None
    color: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneView(BaseModel):
    dimension: Literal["2d", "3d"]
    show_axes: bool = True
    show_grid: bool = True
    show_coordinates: bool = False  # show coords next to points


SceneObject = Point2D | Point3D | Segment | Line2D | Vector2D | Circle2D | FunctionGraph | Face | Sphere


class MathScene(BaseModel):
    problem_text: str
    grade: int | None = Field(default=None, ge=10, le=12)
    topic: Topic = "unknown"
    renderer: Renderer
    objects: list[SceneObject] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    view: SceneView


class RenderRequest(BaseModel):
    problem_text: str = Field(min_length=1)
    grade: int | None = Field(default=None, ge=10, le=12)
    preferred_ai_provider: AiProvider | None = None
    preferred_renderer: Renderer | None = None


class RenderPayload(BaseModel):
    renderer: Renderer
    geogebra_commands: list[str] = Field(default_factory=list)
    three_scene: dict[str, Any] | None = None


class RenderResponse(BaseModel):
    scene: MathScene
    payload: RenderPayload
    warnings: list[str] = Field(default_factory=list)
