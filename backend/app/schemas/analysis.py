from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scene import MAX_IMAGE_DATA_URL_CHARS, RuntimeSettings


class FunctionOcrProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ocr", "ocr_confirmed"]
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=256)
    extraction_version: str = Field(default="function-ocr-v2", max_length=64)


class AnalyzeRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, str | float] | None = None
    parameter_mode: Literal["symbolic", "substitute"] | None = None
    provenance: FunctionOcrProvenance | None = None
    interval: dict[str, Any] | None = None
    line: dict[str, Any] | None = None
    parameter_conditions: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None


class GraphWindow(BaseModel):
    x_min: float
    x_max: float

    @model_validator(mode="after")
    def validate_bounds(self) -> "GraphWindow":
        if self.x_min >= self.x_max:
            raise ValueError("x_min phải nhỏ hơn x_max.")
        if self.x_max - self.x_min > 1_000_000:
            raise ValueError("Cửa sổ vẽ quá rộng.")
        return self


class GraphSamplesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, str | float] | None = None
    window: GraphWindow
    max_points: int = Field(default=500, ge=32, le=2_000)


class GraphSamplesResponse(BaseModel):
    graph_analysis_v2: dict[str, Any]


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


class CriticalPoint(BaseModel):
    x: str
    x_exact: str
    y: str | None = None
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
    transform_preview: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None
    method_used: dict[str, Any] | None = None
    complexity_score: int | None = None
    stage_statuses: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
