from typing import Any

from pydantic import BaseModel, Field

from app.schemas.scene import MAX_IMAGE_DATA_URL_CHARS, RuntimeSettings


class AnalyzeRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, float] | None = None
    interval: dict[str, Any] | None = None
    line: dict[str, Any] | None = None
    parameter_conditions: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None


class AnalyzeOcrRequest(BaseModel):
    image_data_url: str = Field(min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    runtime_settings: RuntimeSettings | None = None


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
    y_intercept: str | None = None
    variation_table: list[VariationRow] = Field(default_factory=list)
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
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
