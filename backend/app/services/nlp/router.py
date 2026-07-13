from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

from app.schemas.nlp import ExcludeAutoTarget, InputEnvelope, InterpretationCandidate
from app.services.nlp.normalization import NormalizedInput

Adapter = Callable[[InputEnvelope, NormalizedInput], list[InterpretationCandidate]]


@dataclass(frozen=True)
class AdapterRegistry:
    adapters: Mapping[ExcludeAutoTarget, Adapter]

    @classmethod
    def from_mapping(cls, adapters: Mapping[ExcludeAutoTarget, Adapter]) -> "AdapterRegistry":
        return cls(MappingProxyType(dict(adapters)))

    def with_adapter(self, target: ExcludeAutoTarget, adapter: Adapter) -> "AdapterRegistry":
        return AdapterRegistry.from_mapping({**self.adapters, target: adapter})

    def resolve(self, target: ExcludeAutoTarget) -> Adapter:
        try:
            return self.adapters[target]
        except KeyError as error:
            raise ValueError(f"Chưa có NLP adapter cho target {target}") from error


def infer_target(text: str) -> ExcludeAutoTarget:
    lowered = text.lower()
    if any(token in lowered for token in ("khảo sát hàm", "khao sat ham", "cực trị", "cuc tri", "tiệm cận", "tiem can", "f(x)=", "y=")):
        return "analyzer"
    if any(token in lowered for token in ("vẽ ", "ve ", "dựng ", "dung ")):
        return "render"
    if any(token in lowered for token in ("khoảng cách", "khoang cach", "thể tích", "the tich", "chứng minh", "chung minh", "mặt phẳng", "mat phang")):
        return "geometry_solve"
    return "algebra"