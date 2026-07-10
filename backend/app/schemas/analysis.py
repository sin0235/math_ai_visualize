from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scene import MAX_IMAGE_DATA_URL_CHARS, RuntimeSettings


class AnalyzeRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, float] | None = None
    interval: dict[str, Any] | None = None
    line: dict[str, Any] | None = None
    parameter_conditions: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None


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
    ocr_text: str | None = None
    ocr_expression: str | None = None
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
