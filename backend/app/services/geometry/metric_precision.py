from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

import sympy as sp


MAX_DECIMAL_PLACES = 10


@dataclass(frozen=True)
class MetricPrecision:
    decimal_places: int


def parse_metric_precision(*texts: str) -> MetricPrecision | None:
    named_places = (
        (re.compile(r"h[aà]ng\s+ph[aầ]n\s+m[ươu]ời", re.IGNORECASE), 1),
        (re.compile(r"h[aà]ng\s+ph[aầ]n\s+tr[aă]m", re.IGNORECASE), 2),
        (re.compile(r"h[aà]ng\s+ph[aầ]n\s+ngh[iì]n", re.IGNORECASE), 3),
    )
    decimal_pattern = re.compile(
        r"(?:l[aà]m\s+tr[oò]n[^.?!]{0,80}?)?(\d{1,2})\s+ch[ữu]\s+s[ốo]\s+th[aậ]p\s+ph[aâ]n",
        re.IGNORECASE,
    )
    for raw_text in texts:
        text = str(raw_text or "")
        for pattern, places in named_places:
            if pattern.search(text):
                return MetricPrecision(places)
        match = decimal_pattern.search(text)
        if match:
            places = int(match.group(1))
            if 0 <= places <= MAX_DECIMAL_PLACES:
                return MetricPrecision(places)
    return None


def approximate_latex(value: sp.Expr, precision: MetricPrecision) -> str | None:
    simplified = sp.simplify(value)
    if simplified.is_real is not True or simplified.is_finite is not True:
        return None
    try:
        evaluated = Decimal(str(sp.N(simplified, precision.decimal_places + 24)))
        quantum = Decimal(1).scaleb(-precision.decimal_places)
        rounded = evaluated.quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    formatted = format(rounded, f".{precision.decimal_places}f")
    return formatted.replace(".", "{,}")
