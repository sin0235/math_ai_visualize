from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_ALGEBRA_INPUT_CHARS = 2_000

AlgebraTopic = Literal[
    "auto",
    "equation",
    "inequality",
    "exponential_log",
    "trigonometry",
    "complex",
    "sequence",
    "combinatorics_probability",
    "system",
    "parameter",
]
AlgebraStatus = Literal["solved", "partial", "unsupported", "error"]
VerificationStatus = Literal["verified", "partially_verified", "failed", "skipped"]
VerificationCheckStatus = Literal["pass", "fail", "warn", "skip"]
InputChipKind = Literal["intent", "format", "topic", "domain", "variable", "expression", "relation", "system"]


class AlgebraInterval(BaseModel):
    variable: str = "x"
    start: str | None = None
    end: str | None = None
    closed_start: bool = True
    closed_end: bool = True


class AlgebraSolveOptions(BaseModel):
    return_steps: bool = True
    verify: bool = True
    max_solutions: int = 50
    prefer_exact: bool = True
    grade_level: Literal["C3"] = "C3"
    use_ai_extraction: bool = False
    ai_explanation: bool = False


class AlgebraInputChip(BaseModel):
    kind: InputChipKind
    label: str
    value: str


class AlgebraInputInterpretation(BaseModel):
    detected_format: Literal["plain", "latex", "natural_vi", "mixed", "structured"] = "plain"
    source: Literal["raw", "rule_based_vi", "latex_normalizer", "structured_ui"] = "raw"
    canonical_input: str
    topic_hint: AlgebraTopic = "auto"
    variables: list[str] = Field(default_factory=list)
    domain: Literal["R", "C", "N", "Z"] = "R"
    chips: list[AlgebraInputChip] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AlgebraSolveRequest(BaseModel):
    input: str = Field(min_length=1, max_length=MAX_ALGEBRA_INPUT_CHARS)
    input_format: Literal["auto", "plain", "latex", "structured"] = "auto"
    topic: AlgebraTopic = "auto"
    variables: list[str] = Field(default_factory=list, max_length=8)
    parameters: list[str] = Field(default_factory=list, max_length=8)
    domain: Literal["R", "C", "N", "Z"] = "R"
    interval: AlgebraInterval | None = None
    options: AlgebraSolveOptions = Field(default_factory=AlgebraSolveOptions)


class AlgebraSolveStep(BaseModel):
    index: int
    title: str
    explanation: str
    goal: str | None = None
    why: str | None = None
    rule: str | None = None
    operation: str | None = None
    before_latex: str | None = None
    after_latex: str | None = None
    pitfall: str | None = None
    check: str | None = None
    expression: str | None = None
    expression_latex: str | None = None
    result: str | None = None
    result_latex: str | None = None
    kind: Literal["normalize", "domain", "transform", "solve", "verify", "conclusion"] | None = None
    confidence: Literal["verified", "symbolic", "numeric_checked", "unverified"] | None = None


class AlgebraSolutionValue(BaseModel):
    text: str
    latex: str | None = None
    approximate: str | None = None


class AlgebraSolutionSet(BaseModel):
    kind: Literal["finite", "set", "interval", "periodic", "conditions", "expression", "empty", "unknown"] = "unknown"
    text: str = ""
    latex: str | None = None
    values: list[AlgebraSolutionValue] = Field(default_factory=list)


class AlgebraVerificationCheck(BaseModel):
    name: str
    status: VerificationCheckStatus
    detail: str
    latex: str | None = None


class AlgebraVerificationReport(BaseModel):
    status: VerificationStatus = "skipped"
    checks: list[AlgebraVerificationCheck] = Field(default_factory=list)
    method: list[str] = Field(default_factory=list)


class AlgebraSolveResponse(BaseModel):
    input: str
    normalized_input: str
    input_interpretation: AlgebraInputInterpretation | None = None
    topic: str
    problem_type: str
    status: AlgebraStatus
    answer: str
    answer_latex: str | None = None
    solution_set: AlgebraSolutionSet = Field(default_factory=AlgebraSolutionSet)
    steps: list[AlgebraSolveStep] = Field(default_factory=list)
    verification: AlgebraVerificationReport = Field(default_factory=AlgebraVerificationReport)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
