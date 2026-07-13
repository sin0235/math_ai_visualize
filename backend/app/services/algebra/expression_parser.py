from __future__ import annotations

import re
from typing import Literal

ExpressionAction = Literal["simplify", "expand", "factor"]

_ACTION_PATTERNS: tuple[tuple[ExpressionAction, re.Pattern[str]], ...] = (
    (
        "expand",
        re.compile(r"^\s*(?:hãy\s+)?(?:khai\s+triển|khai\s+trien)\s+(?:biểu\s+thức|bieu\s+thuc)?\s*(.+)$", re.IGNORECASE),
    ),
    (
        "factor",
        re.compile(
            r"^\s*(?:hãy\s+)?(?:phân\s+tích|phan\s+tich)\s+(?:(?:đa\s+thức|da\s+thuc|biểu\s+thức|bieu\s+thuc)\s+)?(.+?)\s+(?:thành|thanh)\s+(?:nhân\s+tử|nhan\s+tu)\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "factor",
        re.compile(
            r"^\s*(?:hãy\s+)?(?:phân\s+tích|phan\s+tich)\s+(?:đa\s+thức|da\s+thuc|biểu\s+thức|bieu\s+thuc)?\s*(.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "simplify",
        re.compile(r"^\s*(?:hãy\s+)?(?:thu\s+gọn|thu\s+gon|rút\s+gọn|rut\s+gon)\s+(?:biểu\s+thức|bieu\s+thuc)?\s*(.+)$", re.IGNORECASE),
    ),
)


def parse_expression_instruction(raw: str) -> tuple[ExpressionAction, str] | None:
    for action, pattern in _ACTION_PATTERNS:
        match = pattern.fullmatch(raw.strip())
        if match and match.group(1).strip():
            return action, match.group(1).strip()
    return None