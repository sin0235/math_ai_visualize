from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.schemas.advisory import QualityRiskAdvisory


MAX_PROBLEM_TEXT_CHARS = 20_000
MAX_IMAGE_DATA_URL_CHARS = 12_000_000
MAX_API_KEY_CHARS = 4_096
MAX_BASE_URL_CHARS = 2_048
MAX_MODEL_ID_CHARS = 512
MAX_REFERER_CHARS = 2_048
MAX_TITLE_CHARS = 256

Renderer = Literal["geogebra_2d", "geogebra_3d", "threejs_3d"]
AiProvider = Literal["auto", "router9", "openrouter", "openrouter_gpt_oss", "opencode_nemotron", "nvidia", "ollama", "ollama_gpt_oss", "openai_compat", "mock"]
CoordinateAssignment = Literal["ai", "auto_origin", "prefer_o_origin"]
ReasoningLayerMode = Literal["off", "auto", "force"]
RenderJobStatus = Literal["queued", "running", "completed", "failed"]
RenderStatus = Literal["verified", "partially_verified", "needs_confirmation", "fallback", "failed"]
RenderSourceKind = Literal["ai", "byok", "mock", "scene_edit", "manual", "none"]
VerificationStatus = Literal["verified", "failed", "unsupported", "unverifiable", "error"]
ReportStatus = Literal["passed", "partial", "failed"]
RepairStatus = Literal["none", "applied", "proposal", "rejected"]
ObjectSource = Literal["given", "ai_inferred", "construction", "user_created", "user_edited"]
RelationSource = Literal["given", "ai_inferred", "construction", "user_created"]
RendererCompatibilityStatus = Literal["compatible", "incompatible", "requires_confirmation"]
Topic = Literal[
    "coordinate_2d",
    "function_graph",
    "conic",
    "vector_2d",
    "solid_geometry",
    "coordinate_3d",
    "unknown",
]


class SceneObjectBase(BaseModel):
    id: str | None = None
    source: ObjectSource = "ai_inferred"
    locked: bool = False
    user_edited: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("metadata")
    def serialize_object_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)

    @model_validator(mode="after")
    def ensure_object_identity(self) -> "SceneObjectBase":
        if not self.id:
            raw_name = getattr(self, "name", None)
            prefix = str(raw_name).strip() if raw_name else self.__class__.__name__.lower()
            safe_prefix = "".join(ch if ch.isalnum() else "_" for ch in prefix).strip("_") or "obj"
            self.id = f"obj_{safe_prefix}_{uuid4().hex[:8]}"
        return self


class Point2D(SceneObjectBase):
    type: Literal["point_2d"] = "point_2d"
    name: str
    x: float
    y: float
    # Tham số động: nếu set, frontend sẽ tự eval lại khi slider thay đổi.
    # x/y vẫn lưu giá trị đã eval với defaults để backward compatible.
    x_expr: str | None = None
    y_expr: str | None = None


class Point3D(SceneObjectBase):
    type: Literal["point_3d"] = "point_3d"
    name: str
    x: float
    y: float
    z: float
    x_expr: str | None = None
    y_expr: str | None = None
    z_expr: str | None = None


class Segment(SceneObjectBase):
    type: Literal["segment"] = "segment"
    name: str | None = None
    points: list[str] = Field(min_length=2, max_length=2)
    hidden: bool = False
    color: str | None = None
    line_width: float | None = None
    style: Literal["solid", "dashed", "dotted"] | None = None


class Line2D(SceneObjectBase):
    type: Literal["line_2d"] = "line_2d"
    name: str | None = None
    through: list[str] = Field(min_length=2, max_length=2)


class Vector2D(SceneObjectBase):
    type: Literal["vector_2d"] = "vector_2d"
    name: str | None = None
    from_point: str
    to_point: str


class Vector3D(SceneObjectBase):
    type: Literal["vector_3d"] = "vector_3d"
    name: str | None = None
    from_point: str
    to_point: str
    color: str = "#7c3aed"


class Line3D(SceneObjectBase):
    type: Literal["line_3d"] = "line_3d"
    name: str | None = None
    through: list[str] = Field(min_length=2, max_length=2)
    color: str = "#1d3557"


class Circle2D(SceneObjectBase):
    type: Literal["circle_2d"] = "circle_2d"
    name: str | None = None
    center: str
    through: str | None = None
    radius: float | None = None
    radius_expr: str | None = None


class FunctionGraph(SceneObjectBase):
    type: Literal["function_graph"] = "function_graph"
    name: str = "f"
    expression: str
    domain: tuple[float | str, float | str] | None = None


class Face(SceneObjectBase):
    type: Literal["face"] = "face"
    name: str | None = None
    points: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = 0.22


class Sphere(SceneObjectBase):
    type: Literal["sphere"] = "sphere"
    name: str | None = None
    center: str
    radius: float
    radius_expr: str | None = None
    color: str = "#5da9ff"
    opacity: float = 0.18


class Plane(SceneObjectBase):
    type: Literal["plane"] = "plane"
    name: str | None = None
    points: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = 0.16
    show_normal: bool = True


class ValidationItem(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("metadata")
    def serialize_validation_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)


class ValidationReportResponse(BaseModel):
    status: ReportStatus = "passed"
    items: list[ValidationItem] = Field(default_factory=list)


class RelationVerificationResponse(BaseModel):
    relation_id: str
    status: VerificationStatus
    method: str | None = None
    tolerance: float | None = None
    evidence: str | None = None
    message: str | None = None
    verified_at: str | None = None
    verifier_version: str = "cas-v2"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("metadata")
    def serialize_verification_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)


class VerificationSummary(BaseModel):
    verified: int = 0
    failed: int = 0
    unsupported: int = 0
    unverifiable: int = 0
    error: int = 0


class VerificationReportResponse(BaseModel):
    status: ReportStatus = "passed"
    relations: list[RelationVerificationResponse] = Field(default_factory=list)
    summary: VerificationSummary = Field(default_factory=VerificationSummary)


class RepairChange(BaseModel):
    target_id: str | None = None
    target_name: str | None = None
    field: str
    before: Any = None
    after: Any = None
    reason: str | None = None


class RepairReportResponse(BaseModel):
    status: RepairStatus = "none"
    changes: list[RepairChange] = Field(default_factory=list)
    requires_confirmation: bool = False
    warnings: list[str] = Field(default_factory=list)


class RendererCompatibilityReport(BaseModel):
    status: RendererCompatibilityStatus = "compatible"
    renderer: Renderer | None = None
    dimension: Literal["2d", "3d"] | None = None
    messages: list[str] = Field(default_factory=list)
    unsupported_objects: list[str] = Field(default_factory=list)
    unsupported_relations: list[str] = Field(default_factory=list)


class CandidateAttemptResponse(BaseModel):
    provider: str | None = None
    model: str | None = None
    stage: str
    success: bool = False
    message: str | None = None


class RenderSourceResponse(BaseModel):
    kind: RenderSourceKind = "none"
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    candidate_attempts: list[CandidateAttemptResponse] = Field(default_factory=list)


class Relation(BaseModel):
    id: str | None = None
    type: str  # perpendicular, equal_length, parallel, ...
    object_1: str
    object_2: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    source: RelationSource = "ai_inferred"
    verification: RelationVerificationResponse | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("args")
    def serialize_args(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)

    @field_serializer("metadata")
    def serialize_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)

    @model_validator(mode="after")
    def ensure_relation_identity(self) -> "Relation":
        if not self.id:
            self.id = f"rel_{uuid4().hex[:12]}"
        if self.verification is not None and self.verification.relation_id != self.id:
            self.verification.relation_id = self.id
        return self


class Annotation(BaseModel):
    id: str | None = None
    source: ObjectSource = "ai_inferred"
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

    @field_serializer("metadata")
    def serialize_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)

    @model_validator(mode="after")
    def ensure_annotation_identity(self) -> "Annotation":
        if not self.id:
            self.id = f"ann_{uuid4().hex[:12]}"
        return self


class SceneView(BaseModel):
    dimension: Literal["2d", "3d"]
    show_axes: bool = True
    show_grid: bool = True
    show_coordinates: bool = False  # show coords next to points


class Parameter(BaseModel):
    """Tham số động để học sinh tương tác (slider) tổng quát hoá bài toán.

    Khi parameter thay đổi, frontend sẽ eval lại các *_expr trong objects
    và recompute toạ độ điểm tương ứng. Backend không tự re-render; trách nhiệm
    chính là cung cấp scene runtime ban đầu với giá trị default đã eval sẵn.
    """
    name: str  # ví dụ: a, h, alpha
    label: str | None = None  # nhãn hiển thị ("a", "Cạnh đáy a", "α (độ)")
    min: float
    max: float
    default: float
    step: float = 0.1


class CasIssueResponse(BaseModel):
    relation_type: str
    description: str
    severity: str = "warning"
    auto_fixed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("metadata")
    def serialize_metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        return _json_safe(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_safe(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return _json_safe(item())
    return value


SceneObject = Point2D | Point3D | Segment | Line2D | Vector2D | Vector3D | Line3D | Circle2D | FunctionGraph | Face | Sphere | Plane


class SceneInterpretation(BaseModel):
    objects: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    values: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class SceneAudit(BaseModel):
    created_by: RenderSourceKind = "ai"
    generator_provider: str | None = None
    generator_model: str | None = None
    generator_prompt_version: str | None = None
    updated_at: str | None = None


class ConstructionStep(BaseModel):
    id: str | None = None
    description: str
    object_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_step_identity(self) -> "ConstructionStep":
        if not self.id:
            self.id = f"step_{uuid4().hex[:12]}"
        return self


class MathScene(BaseModel):
    scene_id: str | None = None
    schema_version: str = "2.0"
    revision: int = 1
    problem_text: str = Field(max_length=MAX_PROBLEM_TEXT_CHARS)
    grade: int | None = Field(default=None, ge=10, le=12)
    topic: Topic = "unknown"
    renderer: Renderer
    objects: list[SceneObject] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    view: SceneView
    interpretation: SceneInterpretation = Field(default_factory=SceneInterpretation)
    construction_steps: list[ConstructionStep] = Field(default_factory=list)
    audit: SceneAudit = Field(default_factory=SceneAudit)
    cas_issues: list[CasIssueResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_scene_identity(self) -> "MathScene":
        if not self.scene_id:
            self.scene_id = f"scene_{uuid4().hex[:12]}"
        if self.schema_version != "2.0":
            self.schema_version = "2.0"
        return self


class AdvancedRenderSettings(BaseModel):
    coordinate_assignment: CoordinateAssignment = "ai"
    reasoning_layer: ReasoningLayerMode = "off"
    thinking_enabled: bool | None = None
    show_coordinates: bool | None = None
    auto_segments_from_faces: bool = True
    verify_scene: bool = True
    graph_intersections: bool = False
    show_axes: bool | None = None
    show_grid: bool | None = None


class ProviderRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)


class Router9RuntimeSettings(ProviderRuntimeSettings):
    only_mode: bool | None = None
    allowed_model_ids: list[str] | None = None


class RuntimeSettings(BaseModel):
    default_provider: AiProvider | None = None
    openrouter: ProviderRuntimeSettings | None = None
    nvidia: ProviderRuntimeSettings | None = None
    ollama: ProviderRuntimeSettings | None = None
    openai_compat: ProviderRuntimeSettings | None = None
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
    capabilities: dict[str, Any] = Field(default_factory=dict)
    is_free_endpoint: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    supported_parameters: list[str] = Field(default_factory=list)
    pricing: dict[str, Any] = Field(default_factory=dict)
    endpoint_metadata: dict[str, Any] = Field(default_factory=dict)


ModelScanProvider = Literal["openrouter", "openai_compat", "nvidia", "ollama"]


class ModelScanRequest(BaseModel):
    runtime_settings: RuntimeSettings | None = None


class ProviderModelScanRequest(ModelScanRequest):
    provider: ModelScanProvider


class ModelScanResponse(BaseModel):
    models: list[AiModelInfo]
    warnings: list[str] = Field(default_factory=list)


ModelScanJobStatus = Literal["queued", "running", "completed", "failed"]


class ModelScanJobCreateResponse(BaseModel):
    scan_id: str
    status: ModelScanJobStatus


class ModelScanJobStatusResponse(BaseModel):
    scan_id: str
    provider: str
    status: ModelScanJobStatus
    models: list[AiModelInfo] = Field(default_factory=list)
    error: dict[str, Any] | None = None


OcrProvider = Literal["local", "openrouter", "router9", "nvidia", "ollama", "openai_compat"]
OcrMode = Literal["problem", "diagram"]


class OcrRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_data_url: str | None = Field(default=None, min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    upload_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_image_source(self) -> "OcrRequest":
        if bool(self.image_data_url) == bool(self.upload_id):
            raise ValueError("Cần gửi đúng một trong hai trường image_data_url hoặc upload_id.")
        return self


class OcrUploadResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size: int
    storage_provider: str
    public_url: str | None = None


class OcrResponse(BaseModel):
    text: str
    provider: OcrProvider
    model: str
    warnings: list[str] = Field(default_factory=list)


class DiagramOcrRequest(BaseModel):
    image_data_url: str = Field(min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    preferred_ai_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    runtime_settings: RuntimeSettings | None = None


class DiagramOcrResponse(BaseModel):
    description: str
    provider: str
    model: str


class ProblemVariantsRequest(BaseModel):
    scene: MathScene
    response: RenderResponse | None = None
    count: int = Field(default=3, ge=1, le=10)
    original_problem: str | None = Field(default=None, max_length=MAX_PROBLEM_TEXT_CHARS)
    preferred_ai_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    runtime_settings: RuntimeSettings | None = None


class ProblemVariantsResponse(BaseModel):
    variants: list[str]
    provider: str
    model: str


class ProviderSettingsDefaults(BaseModel):
    api_key_configured: bool
    base_url: str
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


class OcrSettingsDefaults(BaseModel):
    provider: OcrProvider
    model: str
    max_image_mb: int


class RegistryProviderDefaults(BaseModel):
    id: str
    label: str
    base_url: str
    api_key_configured: bool
    enabled: bool
    last_checked_at: str | None = None
    last_check_status: str | None = None
    last_check_message: str | None = None


class RegistryModelDefaults(BaseModel):
    provider_id: str
    id: str
    label: str
    owned_by: str | None = None
    context_length: int | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    is_free_endpoint: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    supported_parameters: list[str] = Field(default_factory=list)
    pricing: dict[str, Any] = Field(default_factory=dict)
    endpoint_metadata: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    allowed: bool
    source: str
    last_seen_at: str | None = None


class RegistryTaskProfileDefaults(BaseModel):
    task: str
    provider_id: str
    model_id: str
    fallbacks: list[str] = Field(default_factory=list)


class FeatureFlagsDefaults(BaseModel):
    maintenance_mode: bool = False
    maintenance_message: str = ""
    google_oauth_enabled: bool = True
    ocr_enabled: bool = True
    render_enabled: bool = True
    turnstile_enabled: bool = False
    turnstile_site_key: str | None = None


class SettingsDefaultsResponse(BaseModel):
    app_name: str
    default_provider: str
    openrouter: OpenRouterSettingsDefaults
    nvidia: ProviderSettingsDefaults
    ollama: ProviderSettingsDefaults
    openai_compat: ProviderSettingsDefaults
    router9: Router9SettingsDefaults
    ocr: OcrSettingsDefaults
    registry_providers: list[RegistryProviderDefaults] = Field(default_factory=list)
    registry_models: list[RegistryModelDefaults] = Field(default_factory=list)
    registry_task_profiles: list[RegistryTaskProfileDefaults] = Field(default_factory=list)
    registry_legacy_ai_settings_present: bool = False
    feature_flags: FeatureFlagsDefaults = Field(default_factory=FeatureFlagsDefaults)
    render_async_enabled: bool = False


class RenderRequest(BaseModel):
    problem_text: str = Field(min_length=1, max_length=MAX_PROBLEM_TEXT_CHARS)
    grade: int | None = Field(default=None, ge=10, le=12)
    tier: Literal["tier1", "tier2", "tier3"] = Field(default="tier1")
    preferred_renderer: Renderer | None = None
    advanced_settings: AdvancedRenderSettings = Field(default_factory=AdvancedRenderSettings)
    # Deprecated compatibility fields. The current UI sends `tier`; keeping these
    # optional prevents older clients and tests from failing on request parsing.
    preferred_ai_provider: str | None = Field(default=None, max_length=64)
    preferred_ai_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    runtime_settings: RuntimeSettings | None = None


class ExportViewCapture(BaseModel):
    mime_type: Literal["image/png", "image/jpeg"]
    data_url: str = Field(max_length=MAX_IMAGE_DATA_URL_CHARS)
    width: int = Field(ge=8, le=8192)
    height: int = Field(ge=8, le=8192)

    @model_validator(mode="after")
    def validate_data_url_prefix(self) -> "ExportViewCapture":
        prefix = f"data:{self.mime_type};base64,"
        if not self.data_url.startswith(prefix):
            raise ValueError("view_capture.data_url không khớp mime_type.")
        return self


class SceneRenderRequest(BaseModel):
    scene: MathScene
    advanced_settings: AdvancedRenderSettings = Field(default_factory=AdvancedRenderSettings)
    response: RenderResponse | None = None
    view_capture: ExportViewCapture | None = None


class RenderPayload(BaseModel):
    renderer: Renderer
    geogebra_commands: list[str] = Field(default_factory=list)
    three_scene: dict[str, Any] | None = None


class RenderResponse(BaseModel):
    status: RenderStatus = "partially_verified"
    source: RenderSourceResponse = Field(default_factory=RenderSourceResponse)
    scene: MathScene
    payload: RenderPayload
    warnings: list[str] = Field(default_factory=list)
    validation_report: ValidationReportResponse = Field(default_factory=ValidationReportResponse)
    verification_report: VerificationReportResponse = Field(default_factory=VerificationReportResponse)
    repair_report: RepairReportResponse = Field(default_factory=RepairReportResponse)
    renderer_compatibility: RendererCompatibilityReport = Field(default_factory=RendererCompatibilityReport)
    requires_user_confirmation: bool = False
    user_confirmed: bool = False
    cas_issues: list[CasIssueResponse] = Field(default_factory=list)
    advisory: QualityRiskAdvisory | None = None
    degraded: bool = False
    fallback_source: Literal["none", "mock", "provider_fallback"] = "none"
    ai_source: Literal["admin", "byok", "none"] = "none"

    @model_validator(mode="after")
    def sync_legacy_metadata(self) -> "RenderResponse":
        if self.fallback_source != "none" or self.degraded:
            self.source.fallback_used = True
            if self.source.kind == "none":
                self.source.kind = "mock" if self.fallback_source == "mock" else "ai"
        if self.fallback_source != "none" and not self.source.fallback_reason:
            self.source.fallback_reason = self.fallback_source
        if self.status == "fallback" or self.source.fallback_used:
            self.requires_user_confirmation = True
        return self


SceneRenderRequest.model_rebuild()
ProblemVariantsRequest.model_rebuild()


class RenderJobCreateResponse(BaseModel):
    job_id: str
    status: RenderJobStatus


class RenderJobStatusResponse(BaseModel):
    job_id: str
    status: RenderJobStatus
    response: RenderResponse | None = None
    error: dict[str, Any] | None = None
