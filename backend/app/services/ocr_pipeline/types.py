from __future__ import annotations

from dataclasses import dataclass, field


BBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class OcrTextLine:
    text: str
    confidence: float
    bbox: BBox | None = None


@dataclass(frozen=True)
class LocalOcrResult:
    text: str
    model: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    used_formula_ocr: bool = False
