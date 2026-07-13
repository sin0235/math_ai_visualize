from __future__ import annotations

from dataclasses import dataclass

from app.schemas.nlp import Provenance, TextSpan

_PUNCTUATION = str.maketrans({
    "−": "-",
    "–": "-",
    "—": "-",
    "×": "*",
    "✕": "*",
    "·": "*",
    "•": "*",
    "÷": "/",
    "≤": "<=",
    "≥": ">=",
    "≠": "!=",
    "（": "(",
    "）": ")",
    "［": "[",
    "］": "]",
    "，": ",",
    "；": ";",
    "²": "^2",
    "³": "^3",
    "⁰": "^0",
    "¹": "^1",
    "⁴": "^4",
    "⁵": "^5",
    "⁶": "^6",
    "⁷": "^7",
    "⁸": "^8",
    "⁹": "^9",
    " ": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
})


@dataclass(frozen=True)
class NormalizedInput:
    raw: str
    text: str
    source_indices: tuple[int, ...]

    def source_span(self, start: int, end: int) -> TextSpan | None:
        if start < 0 or end <= start or end > len(self.source_indices):
            return None
        indices = self.source_indices[start:end]
        return TextSpan(start=min(indices), end=max(indices) + 1)

    def provenance(self, start: int = 0, end: int | None = None) -> Provenance:
        span = self.source_span(start, len(self.text) if end is None else end)
        return Provenance(source="normalized", adapter="shared-normalization", version="v1", spans=[span] if span else [])


def normalize_input(raw: str) -> NormalizedInput:
    output: list[str] = []
    indices: list[int] = []
    pending_space_index: int | None = None

    for raw_index, character in enumerate(raw):
        translated = character.translate(_PUNCTUATION)
        for normalized_character in translated:
            if normalized_character.isspace():
                if output:
                    pending_space_index = raw_index
                continue
            if pending_space_index is not None:
                output.append(" ")
                indices.append(pending_space_index)
                pending_space_index = None
            output.append(normalized_character)
            indices.append(raw_index)

    return NormalizedInput(raw=raw, text="".join(output), source_indices=tuple(indices))