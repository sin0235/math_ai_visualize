from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator, model_validator

from app.schemas.scene import MAX_IMAGE_DATA_URL_CHARS, RuntimeSettings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FunctionOcrProvenance(StrictModel):

    source: Literal["ocr", "ocr_confirmed"]
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=256)
    extraction_version: str = Field(default="function-ocr-v2", max_length=64)


class LineMode(str, Enum):
    INTERSECT = "intersect"
    TANGENT_AT = "tangent_at"
    TANGENT_AT_POINT = "tangent_at_point"
    NORMAL_AT = "normal_at"
    TANGENT_PARALLEL = "tangent_parallel"
    TANGENT_PERPENDICULAR = "tangent_perpendicular"
    TANGENT_THROUGH_POINT = "tangent_through_point"


class TransformType(str, Enum):
    VERTICAL_SHIFT = "vertical_shift"
    HORIZONTAL_SHIFT = "horizontal_shift"
    VERTICAL_SCALE = "vertical_scale"
    HORIZONTAL_SCALE = "horizontal_scale"
    REFLECT_X = "reflect_x"
    REFLECT_Y = "reflect_y"
    ABSOLUTE_ALL = "absolute_all"
    ABSOLUTE_X = "absolute_x"


class ParameterConditionTarget(str, Enum):
    INCREASING_R = "increasing_r"
    DECREASING_R = "decreasing_r"
    EXTREMA_COUNT = "extrema_count"


BoundedFiniteFloat = Annotated[FiniteFloat, Field(ge=-1_000_000, le=1_000_000)]


class ParameterValues(StrictModel):
    m: str | FiniteFloat | None = None

    @field_validator("m")
    @classmethod
    def validate_exact_value(cls, value: str | float | None) -> str | float | None:
        if isinstance(value, str):
            value = value.strip()
            if not value or len(value) > 128:
                raise ValueError("Giá trị tham số exact phải có từ 1 đến 128 ký tự.")
        return value


class AnalysisInterval(StrictModel):
    a: BoundedFiniteFloat
    b: BoundedFiniteFloat
    open_a: bool = False
    open_b: bool = False

    @model_validator(mode="after")
    def validate_order(self) -> "AnalysisInterval":
        if self.a >= self.b:
            raise ValueError("a phải nhỏ hơn b.")
        return self


class AnalysisLine(StrictModel):
    mode: LineMode = LineMode.INTERSECT
    k: BoundedFiniteFloat = 0
    b: BoundedFiniteFloat = 0
    x0: BoundedFiniteFloat = 0
    y0: BoundedFiniteFloat = 0


class ParameterConditionRequest(StrictModel):
    targets: list[ParameterConditionTarget] = Field(min_length=1, max_length=3)
    extrema_count: int | None = Field(default=None, ge=0, le=2)

    @field_validator("targets")
    @classmethod
    def validate_unique_targets(cls, value: list[ParameterConditionTarget]) -> list[ParameterConditionTarget]:
        if len(set(value)) != len(value):
            raise ValueError("Danh sách target không được trùng lặp.")
        return value

    @model_validator(mode="after")
    def validate_extrema_target(self) -> "ParameterConditionRequest":
        needs_count = ParameterConditionTarget.EXTREMA_COUNT in self.targets
        if needs_count and self.extrema_count is None:
            raise ValueError("extrema_count là bắt buộc khi target là extrema_count.")
        if not needs_count and self.extrema_count is not None:
            raise ValueError("extrema_count chỉ hợp lệ với target extrema_count.")
        return self


class ValuedGraphTransform(StrictModel):
    type: Literal[
        TransformType.VERTICAL_SHIFT,
        TransformType.HORIZONTAL_SHIFT,
        TransformType.VERTICAL_SCALE,
        TransformType.HORIZONTAL_SCALE,
    ]
    value: BoundedFiniteFloat


class FixedGraphTransform(StrictModel):
    type: Literal[
        TransformType.REFLECT_X,
        TransformType.REFLECT_Y,
        TransformType.ABSOLUTE_ALL,
        TransformType.ABSOLUTE_X,
    ]
    # Giữ value optional cho client legacy; frontend mới không gửi field này.
    value: BoundedFiniteFloat | None = None


GraphTransform = Annotated[ValuedGraphTransform | FixedGraphTransform, Field(discriminator="type")]


class AnalysisOptions(StrictModel):
    parameters: ParameterValues | None = None
    parameter_mode: Literal["symbolic", "substitute"] | None = None
    interval: AnalysisInterval | None = None
    line: AnalysisLine | None = None
    parameter_conditions: ParameterConditionRequest | None = None
    transform: GraphTransform | None = None

    @model_validator(mode="after")
    def validate_parameter_mode(self) -> "AnalysisOptions":
        has_parameter_value = self.parameters is not None and self.parameters.m is not None
        if self.parameter_mode == "substitute" and not has_parameter_value:
            raise ValueError("Chế độ substitute cần giá trị tham số m.")
        return self


class AnalyzerBaseRequest(StrictModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: ParameterValues | None = None
    parameter_mode: Literal["symbolic", "substitute"] | None = None
    provenance: FunctionOcrProvenance | None = None

    @model_validator(mode="after")
    def validate_parameter_mode(self) -> "AnalyzerBaseRequest":
        has_parameter_value = self.parameters is not None and self.parameters.m is not None
        if self.parameter_mode == "substitute" and not has_parameter_value:
            raise ValueError("Chế độ substitute cần giá trị tham số m.")
        return self


class AnalyzerSessionReference(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)


class AnalyzerIntervalToolRequest(AnalyzerSessionReference):
    interval: AnalysisInterval


class AnalyzerLineToolRequest(AnalyzerSessionReference):
    line: AnalysisLine


class AnalyzerTangentToolRequest(AnalyzerSessionReference):
    x0: BoundedFiniteFloat


class AnalyzerTransformToolRequest(AnalyzerSessionReference):
    transform: GraphTransform


class AnalyzerParameterToolRequest(AnalyzerSessionReference, ParameterConditionRequest):
    pass


class AnalyzeRequest(AnalysisOptions):
    expression: str = Field(min_length=1, max_length=1000)
    provenance: FunctionOcrProvenance | None = None


class PlotWindow(StrictModel):
    x_min: BoundedFiniteFloat
    x_max: BoundedFiniteFloat

    @model_validator(mode="after")
    def validate_bounds(self) -> "PlotWindow":
        if self.x_min >= self.x_max:
            raise ValueError("x_min phải nhỏ hơn x_max.")
        if self.x_max - self.x_min > 1_000_000:
            raise ValueError("Cửa sổ vẽ quá rộng.")
        return self


# Tên cũ giữ lại cho import nội bộ/client cũ.
GraphWindow = PlotWindow


class GraphSamplesRequest(StrictModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: ParameterValues | None = None
    window: PlotWindow
    max_points: int = Field(default=500, ge=32, le=2_000)


class GraphNumber(StrictModel):
    exact: str
    latex: str
    approx: FiniteFloat | None = None


class GraphEndpoint(GraphNumber):
    open: bool
    attained: bool
    y: FiniteFloat | None = None


class GraphPoint(StrictModel):
    x: FiniteFloat
    y: FiniteFloat


class GraphSegment(StrictModel):
    component_id: str
    expression_exact: str
    expression_latex: str
    start: GraphNumber
    end: GraphNumber
    left_open: bool
    right_open: bool
    left_endpoint: GraphEndpoint
    right_endpoint: GraphEndpoint
    points: list[GraphPoint]
    sample_count: int = Field(ge=0, le=2_000)
    verification: str


class GraphAnalysis(StrictModel):
    status: Literal["complete", "partial", "unknown"]
    method: str
    window: PlotWindow
    max_points: int = Field(ge=32, le=2_000)
    point_count: int = Field(ge=0, le=2_000)
    segments: list[GraphSegment]
    singularities: list[GraphNumber]
    features: list[GraphNumber] = Field(default_factory=list)
    warnings: list[str]


class GraphSamplesResponse(StrictModel):
    graph_analysis_v2: GraphAnalysis


class AnalyzeOcrRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_data_url: str | None = Field(default=None, min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    upload_id: str | None = Field(default=None, min_length=1, max_length=128)
    runtime_settings: RuntimeSettings | None = None

    @model_validator(mode="after")
    def validate_image_source(self) -> "AnalyzeOcrRequest":
        if bool(self.image_data_url) == bool(self.upload_id):
            raise ValueError("Cần gửi đúng một trong hai trường image_data_url hoặc upload_id.")
        return self


class FunctionOcrAmbiguousToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=64)
    alternatives: list[str] = Field(default_factory=list, max_length=8)
    reason: str = Field(default="", max_length=256)
    start: int | None = Field(default=None, ge=0, le=1000)
    end: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_range(self) -> "FunctionOcrAmbiguousToken":
        if (self.start is None) != (self.end is None):
            raise ValueError("Vị trí token OCR phải có đủ start và end.")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("Vị trí token OCR không hợp lệ.")
        return self


class FunctionOcrCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(default="", max_length=1000)
    variable: Literal["x"] = "x"
    parameters: list[Literal["m"]] = Field(default_factory=list, max_length=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    ambiguous_tokens: list[FunctionOcrAmbiguousToken] = Field(default_factory=list, max_length=20)
    needs_confirmation: bool = True

    @model_validator(mode="after")
    def validate_token_ranges(self) -> "FunctionOcrCandidate":
        if any(token.end is not None and token.end > len(self.expression) for token in self.ambiguous_tokens):
            raise ValueError("Vị trí token OCR vượt ngoài biểu thức.")
        return self


class FunctionOcrExtraction(FunctionOcrCandidate):
    ocr_text: str = Field(default="", max_length=20_000)
    provenance: FunctionOcrProvenance


class ExactApproxValue(StrictModel):
    exact: str
    latex: str
    approx: FiniteFloat | None = None
    precision: int | None = Field(default=None, ge=1, le=50)
    method: str = Field(min_length=1, max_length=64)


class CriticalPoint(BaseModel):
    x: str
    x_exact: str
    x_value: ExactApproxValue | None = None
    y: str | None = None
    y_exact: str | None = None
    y_value: ExactApproxValue | None = None
    kind: str
    kind_label: str


class VariationRow(BaseModel):
    x: str
    y: str | None = None
    kind: str
    arrow_to_next: str | None = None


class VariationLimit(BaseModel):
    value: str | None = None
    status: str = "unknown"


class VariationNode(BaseModel):
    kind: str
    x: str
    x_exact: str | None = None
    y: str | None = None
    y_exact: str | None = None
    label: str | None = None
    open: bool | None = None
    left_limit: VariationLimit | None = None
    right_limit: VariationLimit | None = None


class VariationSegment(BaseModel):
    left: str
    right: str
    direction: str
    verification: str
    derivative_sign: str


class VariationTableV2(BaseModel):
    status: str = "unknown"
    warnings: list[str] = Field(default_factory=list)
    nodes: list[VariationNode] = Field(default_factory=list)
    segments: list[VariationSegment] = Field(default_factory=list)


class AnalyzerCapabilityExample(StrictModel):
    category: str
    label: str
    expression: str
    latex: str


class AnalyzerCapabilityRegistry(StrictModel):
    version: str
    parser: dict[str, Any]
    derivative: dict[str, Any]
    piecewise_conditions: dict[str, Any]
    parameters: dict[str, Any]
    tools: list[str]
    renderers: list[str]
    examples: list[AnalyzerCapabilityExample]


class ExpressionCapabilities(StrictModel):
    registry_version: str
    expression: dict[str, Any]
    exactness: dict[str, str]
    completeness: dict[str, Any]
    numeric_fallback: dict[str, bool]
    renderer: dict[str, bool]
    tools: dict[str, bool]
    limitations: list[str] = Field(default_factory=list)


class VerificationCheck(StrictModel):
    name: str
    status: Literal["pass", "warn", "fail", "unknown"]
    method: Literal["symbolic", "numeric", "fallback", "unknown"]
    detail: str | None = None
    error_bound: FiniteFloat | None = None


class VerificationReport(StrictModel):
    status: Literal["verified", "partially_verified", "unverified", "failed"]
    checks: list[VerificationCheck] = Field(default_factory=list)
    truncated: bool = False
    possibly_incomplete: bool = False


class TransformAnchor(StrictModel):
    source_x: FiniteFloat
    source_y: FiniteFloat
    target_x: FiniteFloat
    target_y: FiniteFloat


class TransformPreview(StrictModel):
    type: TransformType
    value: str
    label: str
    expression: str
    expression_latex: str
    convention: str
    expression_template: str
    requires_value: bool
    transformed_domain: str | None = None
    transformed_range: str | None = None
    invariants: list[str] = Field(default_factory=list)
    anchors: list[TransformAnchor] = Field(default_factory=list)
    pedagogical_steps: list[str] = Field(default_factory=list)


class AnalysisStep(StrictModel):
    key: str = Field(min_length=1, max_length=64)
    order: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=128)
    status: Literal["complete", "partial", "unknown", "skipped"]
    formula_latex: str | None = None
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    expression: str
    expression_latex: str | None = None
    evaluated_expression: str | None = None
    evaluated_expression_latex: str | None = None
    parameters: dict[str, Any] | None = None
    analysis_mode: str | None = None
    parameter_mode: str | None = None
    requires_parameter_confirmation: bool = False
    requires_substitution_for_graph: bool = False
    parameter_analysis_v2: dict[str, Any] | None = None
    derivative: str | None = None
    derivative_latex: str | None = None
    second_derivative: str | None = None
    second_derivative_latex: str | None = None
    critical_points: list[CriticalPoint] = Field(default_factory=list)
    inflection_points: list[dict[str, str]] = Field(default_factory=list)
    intervals_increasing: list[str] = Field(default_factory=list)
    intervals_decreasing: list[str] = Field(default_factory=list)
    concave_up_intervals: list[str] = Field(default_factory=list)
    concave_down_intervals: list[str] = Field(default_factory=list)
    horizontal_asymptotes: list[dict[str, str]] = Field(default_factory=list)
    vertical_asymptotes: list[dict[str, str]] = Field(default_factory=list)
    oblique_asymptote: str | None = None
    x_intercepts: list[str] = Field(default_factory=list)
    x_intercepts_v2: dict[str, Any] | None = None
    y_intercept: str | None = None
    variation_table: list[VariationRow] = Field(default_factory=list)
    variation_table_v2: VariationTableV2 | None = None
    domain_partition_v2: dict[str, Any] | None = None
    periodicity: dict[str, Any] | None = None
    monotonicity_v2: dict[str, Any] | None = None
    concavity_v2: dict[str, Any] | None = None
    critical_points_v2: list[dict[str, Any]] = Field(default_factory=list)
    inflection_points_v2: list[dict[str, Any]] = Field(default_factory=list)
    asymptotes_v2: dict[str, Any] | None = None
    domain: str | None = None
    domain_latex: str | None = None
    range_val: str | None = None
    range_latex: str | None = None
    parity: str | None = None
    geogebra_commands: list[str] = Field(default_factory=list)
    graph_scene: dict[str, Any] | None = None
    graph_points: list[dict[str, float]] = Field(default_factory=list)
    graph_analysis_v2: dict[str, Any] | None = None
    ocr_text: str | None = None
    ocr_expression: str | None = None
    provenance: FunctionOcrProvenance | None = None
    interval_analysis: dict[str, Any] | None = None
    line_analysis: dict[str, Any] | None = None
    parameter_conditions: list[dict[str, Any]] = Field(default_factory=list)
    transform_preview: TransformPreview | None = None
    capabilities: dict[str, Any] | None = None
    capabilities_v2: ExpressionCapabilities | None = None
    method_used: dict[str, Any] | None = None
    complexity_score: int | None = None
    stage_statuses: dict[str, Any] | None = None
    verification: VerificationReport | None = None
    analysis_steps: list[AnalysisStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None


class AnalyzerSessionResponse(AnalyzeResponse):
    analysis_id: str
    engine_version: str
    expires_at: str


class AnalyzerToolResponse(StrictModel):
    analysis_id: str
    engine_version: str
    tool: Literal["interval-extrema", "line", "tangent", "transform", "parameter"]
    interval_analysis: dict[str, Any] | None = None
    line_analysis: dict[str, Any] | None = None
    transform_preview: TransformPreview | None = None
    parameter_conditions: list[dict[str, Any]] | None = None
