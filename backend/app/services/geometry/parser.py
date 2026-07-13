from __future__ import annotations

import re


def normalize_solver_question(question: str) -> str:
    normalized = question.strip()
    if not normalized:
        return ""
    replacements = {
        "​": "",
        "‌": "",
        "‍": "",
        "（": "(",
        "）": ")",
        "，": ",",
        "、": ",",
        "−": "-",
        "–": "-",
        "—": "-",
        "✕": "×",
        "*": "×",
        "·": ".",
        "•": ".",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\b", "d", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(?:den|đến|toi|tới|tu|từ|cua|của)\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\b(?:mp|mat\s+phang|mặt\s+phẳng)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"({_compact_point_sequence_text(match.group(1))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b(?:dien\s+tich|diện\s+tích)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"S({_compact_point_sequence_text(match.group(1))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b(?:chu\s+vi|perimeter)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"P({_compact_point_sequence_text(match.group(1))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b(?:the\s+tich|thể\s+tích)\s+([A-Za-z][A-Za-z0-9']*(?:\s*\.\s*)?[A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"V({_compact_solid_text(match.group(1))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b([dDpPsSvV])\s*\(",
        lambda match: f"{match.group(1).upper()}(" if match.group(1).lower() in {"p", "s", "v"} else "d(",
        normalized,
    )
    normalized = _normalize_parenthesized_geometry(normalized)
    normalized = re.sub(
        r"\bd\s+([A-Za-z](?:[0-9]+|')?)\s+(\([A-Za-z0-9'\s]+\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){1,})",
        lambda match: f"d({match.group(1).upper()},{_normalize_distance_target_text(match.group(2))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\b([A-Za-z](?:[0-9]+|')?)\s*-\s*([A-Za-z](?:[0-9]+|')?)\b",
        lambda match: f"{match.group(1).upper()}-{match.group(2).upper()}",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return re.sub(r"\bGOC\b", "góc", normalized, flags=re.IGNORECASE)


def _normalize_distance_target_text(value: str) -> str:
    target = value.strip()
    if target.startswith("(") and target.endswith(")"):
        return f"({_compact_point_sequence_text(target[1:-1])})"
    return _compact_point_sequence_text(target)


def _compact_point_sequence_text(value: str) -> str:
    return "".join(re.findall(r"[A-Za-z](?:[0-9]+|')?", value)).upper()


def _compact_solid_text(value: str) -> str:
    cleaned = value.strip().replace(" ", "")
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        return f"{_compact_point_sequence_text(left)}.{_compact_point_sequence_text(right)}"
    compact = _compact_point_sequence_text(value)
    return f"{compact[0]}.{compact[1:]}" if len(compact) >= 4 else compact


def _normalize_parenthesized_geometry(question: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(question):
        if question[index] != "(":
            result.append(question[index])
            index += 1
            continue
        end = _find_matching_paren(question, index)
        if end is None:
            result.append(question[index])
            index += 1
            continue
        inner = _normalize_parenthesized_geometry(question[index + 1:end])
        if re.fullmatch(r"[A-Za-z0-9'\s.]+", inner):
            inner = _compact_solid_text(inner) if "." in inner else _compact_point_sequence_text(inner)
        result.append(f"({inner})")
        index = end + 1
    return "".join(result)


def _find_matching_paren(value: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(value)):
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None