from __future__ import annotations

from dataclasses import dataclass, field


BBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class OcrTextLine:
    text: str
    confidence: float
    bbox: BBox | None = None


@dataclass(frozen=True)
class OcrFormulaCandidate:
    latex: str
    confidence: float | None = None
    bbox: BBox | None = None
    source: str = "formula_ocr"


@dataclass(frozen=True)
class LocalOcrResult:
    text: str
    model: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    used_formula_ocr: bool = False
    raw_text: str | None = None
    normalized_text: str | None = None
    lines: list[OcrTextLine] = field(default_factory=list)
    formula_candidates: list[OcrFormulaCandidate] = field(default_factory=list)
