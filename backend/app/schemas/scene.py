from typing import Any, Literal

from pydantic import BaseModel, Field


MAX_PROBLEM_TEXT_CHARS = 20_000
MAX_IMAGE_DATA_URL_CHARS = 12_000_000
MAX_API_KEY_CHARS = 4_096
MAX_BASE_URL_CHARS = 2_048
MAX_MODEL_ID_CHARS = 512
MAX_REFERER_CHARS = 2_048
MAX_TITLE_CHARS = 256

Renderer = Literal["geogebra_2d", "geogebra_3d", "threejs_3d"]
AiProvider = Literal["auto", "router9", "openrouter", "openrouter_gpt_oss", "opencode_nemotron", "nvidia", "ollama_gpt_oss", "mock"]
CoordinateAssignment = Literal["ai", "auto_origin", "prefer_o_origin"]
ReasoningLayerMode = Literal["off", "auto", "force"]
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
    color: str | None = None
    line_width: float | None = None
    style: Literal["solid", "dashed", "dotted"] | None = None


class Line2D(BaseModel):
    type: Literal["line_2d"] = "line_2d"
    name: str | None = None
    through: list[str] = Field(min_length=2, max_length=2)


class Vector2D(BaseModel):
    type: Literal["vector_2d"] = "vector_2d"
    name: str | None = None
    from_point: str
    to_point: str


class Vector3D(BaseModel):
    type: Literal["vector_3d"] = "vector_3d"
    name: str | None = None
    from_point: str
    to_point: str
    color: str = "#7c3aed"


class Line3D(BaseModel):
    type: Literal["line_3d"] = "line_3d"
    name: str | None = None
    through: list[str] = Field(min_length=2, max_length=2)
    color: str = "#1d3557"


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


class Plane(BaseModel):
    type: Literal["plane"] = "plane"
    name: str | None = None
    points: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = 0.16
    show_normal: bool = True


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


SceneObject = Point2D | Point3D | Segment | Line2D | Vector2D | Vector3D | Line3D | Circle2D | FunctionGraph | Face | Sphere | Plane


class MathScene(BaseModel):
    problem_text: str = Field(max_length=MAX_PROBLEM_TEXT_CHARS)
    grade: int | None = Field(default=None, ge=10, le=12)
    topic: Topic = "unknown"
    renderer: Renderer
    objects: list[SceneObject] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    view: SceneView


class AdvancedRenderSettings(BaseModel):
    coordinate_assignment: CoordinateAssignment = "ai"
    reasoning_layer: ReasoningLayerMode = "off"
    show_coordinates: bool | None = None
    auto_segments_from_faces: bool = True
    graph_intersections: bool = False
    show_axes: bool | None = None
    show_grid: bool | None = None


class ProviderRuntimeSettings(BaseModel):
    api_key: str | None = Field(default=None, max_length=MAX_API_KEY_CHARS)
    base_url: str | None = Field(default=None, max_length=MAX_BASE_URL_CHARS)
    model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)


class Router9RuntimeSettings(ProviderRuntimeSettings):
    only_mode: bool | None = None
    allowed_model_ids: list[str] | None = None


class RuntimeSettings(BaseModel):
    default_provider: AiProvider | None = None
    openrouter: ProviderRuntimeSettings | None = None
    nvidia: ProviderRuntimeSettings | None = None
    ollama: ProviderRuntimeSettings | None = None
    router9: Router9RuntimeSettings | None = None
    openrouter_http_referer: str | None = Field(default=None, max_length=MAX_REFERER_CHARS)
    openrouter_x_title: str | None = Field(default=None, max_length=MAX_TITLE_CHARS)
    openrouter_reasoning_enabled: bool | None = None


class AiModelInfo(BaseModel):
    id: str
    label: str
    provider: str = "router9"
    owned_by: str | None = None
    created: int | None = None
    context_length: int | None = None


ModelScanProvider = Literal["openrouter", "nvidia", "ollama"]


class ModelScanRequest(BaseModel):
    runtime_settings: RuntimeSettings | None = None


class ProviderModelScanRequest(ModelScanRequest):
    provider: ModelScanProvider


class ModelScanResponse(BaseModel):
    models: list[AiModelInfo]
    warnings: list[str] = Field(default_factory=list)


OcrProvider = Literal["openrouter", "router9"]


class OcrRequest(BaseModel):
    image_data_url: str = Field(min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    ocr_provider: OcrProvider | None = None
    ocr_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    runtime_settings: RuntimeSettings | None = None


class OcrResponse(BaseModel):
    text: str
    provider: OcrProvider
    model: str
    warnings: list[str] = Field(default_factory=list)


class ProviderSettingsDefaults(BaseModel):
    api_key_configured: bool
    base_url: str
    model: str | None = None
    scanned_models: list[AiModelInfo] = Field(default_factory=list)
    allowed_model_ids: list[str] = Field(default_factory=list)


class OpenRouterSettingsDefaults(ProviderSettingsDefaults):
    vision_model: str
    http_referer: str | None = None
    x_title: str
    reasoning_enabled: bool


class Router9SettingsDefaults(ProviderSettingsDefaults):
    only_mode: bool
    allowed_model_ids: list[str] = Field(default_factory=list)


class SettingsDefaultsResponse(BaseModel):
    app_name: str
    default_provider: str
    openrouter: OpenRouterSettingsDefaults
    nvidia: ProviderSettingsDefaults
    ollama: ProviderSettingsDefaults
    router9: Router9SettingsDefaults


class RenderRequest(BaseModel):
    problem_text: str = Field(min_length=1, max_length=MAX_PROBLEM_TEXT_CHARS)
    grade: int | None = Field(default=None, ge=10, le=12)
    preferred_ai_provider: AiProvider | None = None
    preferred_ai_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    preferred_renderer: Renderer | None = None
    advanced_settings: AdvancedRenderSettings = Field(default_factory=AdvancedRenderSettings)
    runtime_settings: RuntimeSettings | None = None


class SceneRenderRequest(BaseModel):
    scene: MathScene
    advanced_settings: AdvancedRenderSettings = Field(default_factory=AdvancedRenderSettings)


class RenderPayload(BaseModel):
    renderer: Renderer
    geogebra_commands: list[str] = Field(default_factory=list)
    three_scene: dict[str, Any] | None = None


class RenderResponse(BaseModel):
    scene: MathScene
    payload: RenderPayload
    warnings: list[str] = Field(default_factory=list)
