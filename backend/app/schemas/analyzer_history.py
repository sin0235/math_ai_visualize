from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.analysis import (
    AnalysisOptions,
    AnalyzerSessionResponse,
    CurriculumPresentation,
    CurriculumProfile,
    PlotWindow,
    StrictModel,
)


class AnalyzerHistoryCreateRequest(StrictModel):
    analysis_id: str = Field(min_length=16, max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=12)
    pinned: bool = False
    curriculum_profile: CurriculumProfile = Field(default_factory=CurriculumProfile)
    window: PlotWindow | None = None
    tools: AnalysisOptions | None = None


class AnalyzerHistoryPatchRequest(StrictModel):
    tags: list[str] | None = Field(default=None, max_length=12)
    pinned: bool | None = None
    chapter: str | None = Field(default=None, min_length=1, max_length=96)


class AnalyzerHistoryItem(StrictModel):
    id: str
    original_expression: str
    canonical_expression: str
    parameters: dict[str, Any]
    tags: list[str]
    pinned: bool
    grade: int | None
    chapter: str | None
    explanation_level: str
    engine_version: str
    schema_version: str
    parent_history_id: str | None = None
    created_at: str
    updated_at: str
    last_opened_at: str | None = None


class AnalyzerVersionDiff(StrictModel):
    engine_changed: bool
    schema_changed: bool
    verification_changed: bool
    warning_count_before: int
    warning_count_after: int


class AnalyzerHistoryDetail(AnalyzerHistoryItem):
    result: AnalyzerSessionResponse
    window: dict[str, Any]
    tools: dict[str, Any]
    version_diff: AnalyzerVersionDiff | None = None


class AnalyzerReanalyzeRequest(StrictModel):
    curriculum_profile: CurriculumProfile | None = None


class AnalyzerExportRequest(StrictModel):
    analysis_id: str | None = Field(default=None, min_length=16, max_length=128)
    history_id: str | None = Field(default=None, min_length=16, max_length=128)
    format: Literal["markdown", "json", "latex", "pdf"]
    template: Literal["full", "teacher_report", "student_worksheet"] = "full"
    curriculum_profile: CurriculumProfile = Field(default_factory=CurriculumProfile)

    @model_validator(mode="after")
    def validate_source(self) -> "AnalyzerExportRequest":
        if bool(self.analysis_id) == bool(self.history_id):
            raise ValueError("Cần gửi đúng một trong analysis_id hoặc history_id.")
        return self


class AnalyzerExportSection(StrictModel):
    key: str
    title: str
    status: str
    formula_latex: str | None = None
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalyzerExportDocument(StrictModel):
    schema_version: Literal["analyzer-export-v1"] = "analyzer-export-v1"
    template: Literal["full", "teacher_report", "student_worksheet"]
    title: str
    expression: str
    expression_latex: str | None = None
    engine_version: str
    verification: dict[str, Any]
    exact_approx_metadata: list[dict[str, Any]]
    curriculum: CurriculumPresentation
    sections: list[AnalyzerExportSection]
    warnings: list[str]