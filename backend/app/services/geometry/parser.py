from __future__ import annotations

import re

_POINT = r"[A-Za-z](?:[0-9]+|')?"
_PLANE_BODY = r"[A-Za-z0-9'\s.]+"


def normalize_solver_question(question: str) -> str:
    """Normalize Vietnamese / mixed geometry questions to solver canonical forms.

    Examples:
    - \"Khoảng cách từ điểm M đến mặt phẳng (PFB)\" → d(M,(PFB))
    - long problem text with one clear metric question → that metric form
    """
    normalized = (question or "").strip()
    if not normalized:
        return ""

    replacements = {
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
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

    # Collapse nested plane parens: ((PFB)) → (PFB); single-letter (M) stays for later.
    for _ in range(4):
        updated = re.sub(r"\(\(([^()]+)\)\)", r"(\1)", normalized)
        if updated == normalized:
            break
        normalized = updated

    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Prefer the metric question sentence when user pastes full problem text.
    normalized = _extract_primary_metric_question(normalized)

    # Unwrap parenthesized single points: điểm (M) → điểm M
    normalized = re.sub(
        rf"\b(diem|điểm)\s*\((\s*{_POINT}\s*)\)",
        lambda m: f"{m.group(1)} {m.group(2).strip()}",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(rf"\((\s*{_POINT}\s*)\)", lambda m: m.group(1).strip(), normalized)

    # --- Distance phrases BEFORE stripping connecting words ---
    # khoảng cách từ [điểm] M đến [mặt phẳng] (PFB)
    normalized = re.sub(
        rf"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\s+"
        rf"(?:tu|từ|from)?\s*"
        rf"(?:diem|điểm)?\s*"
        rf"({_POINT})\s+"
        rf"(?:den|đến|toi|tới|to|vao|vào)?\s*"
        rf"(?:mp|mat\s+phang|mặt\s+phẳng)?\s*"
        rf"(\({_PLANE_BODY}\)|{_POINT}(?:\s*{_POINT}){{1,}})",
        lambda m: f"d({m.group(1).upper()},{_normalize_distance_target_text(m.group(2))})",
        normalized,
        flags=re.IGNORECASE,
    )
    # khoảng cách từ [điểm] A đến [điểm] B / đến đường BC
    normalized = re.sub(
        rf"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\s+"
        rf"(?:tu|từ|from)?\s*"
        rf"(?:diem|điểm)?\s*"
        rf"({_POINT})\s+"
        rf"(?:den|đến|toi|tới|to)?\s*"
        rf"(?:diem|điểm|duong|đường|duong\s+thang|đường\s+thẳng)?\s*"
        rf"({_POINT}(?:\s*{_POINT})?|\({_PLANE_BODY}\))",
        lambda m: f"d({m.group(1).upper()},{_normalize_distance_target_text(m.group(2))})",
        normalized,
        flags=re.IGNORECASE,
    )

    # Generic alias: khoảng cách → d (remaining cases)
    normalized = re.sub(
        r"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\b",
        "d",
        normalized,
        flags=re.IGNORECASE,
    )

    # d điểm M mặt phẳng (PFB)  (after từ/đến stripped elsewhere or leftover)
    normalized = re.sub(
        rf"\bd\s+(?:diem|điểm)?\s*({_POINT})\s+"
        rf"(?:mp|mat\s+phang|mặt\s+phẳng)?\s*"
        rf"(\({_PLANE_BODY}\))",
        lambda m: f"d({m.group(1).upper()},{_normalize_distance_target_text(m.group(2))})",
        normalized,
        flags=re.IGNORECASE,
    )

    # Protect congruence phrase before stripping standalone "bằng" connectors
    # ("bằng nhau" must survive for triangle_congruence goal detection).
    _BANG_NHAU = "\u0000BANG_NHAU\u0000"
    normalized = re.sub(r"\b(?:bang|bằng)\s+nhau\b", _BANG_NHAU, normalized, flags=re.IGNORECASE)

    # Strip light connecting words only when not already in d(...) form
    if not re.search(r"\bd\s*\(", normalized, flags=re.IGNORECASE):
        normalized = re.sub(
            r"\b(?:den|đến|toi|tới|tu|từ|cua|của|bang|bằng|bao\s+nhieu|bao\s+nhiêu|la\s+bao\s+nhieu)\b",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
    normalized = normalized.replace(_BANG_NHAU, "bằng nhau")

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
        rf"\bd\s+({_POINT})\s+(\({_PLANE_BODY}\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){{1,}})",
        lambda match: f"d({match.group(1).upper()},{_normalize_distance_target_text(match.group(2))})",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b({_POINT})\s*-\s*({_POINT})\b",
        lambda match: f"{match.group(1).upper()}-{match.group(2).upper()}",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    # Drop trailing filler after a canonical metric form
    metric = re.search(
        r"(d\([^)]+\)|S\([^)]+\)|P\([^)]+\)|V\([^)]+\)|góc\b[^?]*)",
        normalized,
        flags=re.IGNORECASE,
    )
    if metric:
        # Keep only the first solid metric expression when leftover prose remains.
        head = normalized[: metric.end()].strip()
        if re.match(r"^[dDsSpPvV]\(", head) or head.lower().startswith("góc"):
            # Prefer pure d(...)/S(...)/V(...) if present
            pure = re.search(r"\b([dDsSpPvV])\(([^()]*(?:\([^()]*\)[^()]*)*)\)", normalized)
            if pure:
                name = pure.group(1)
                canon = f"{'d' if name.lower() == 'd' else name.upper()}({pure.group(2)})"
                return re.sub(r"\bGOC\b", "góc", canon, flags=re.IGNORECASE)
    return re.sub(r"\bGOC\b", "góc", normalized, flags=re.IGNORECASE)


def _extract_primary_metric_question(text: str) -> str:
    """From a full exam prompt, keep the sentence that states the metric goal."""
    if len(text) < 80 and not re.search(r"[.?!;]", text):
        return text
    # Split soft: period / question mark / newline / "Cho hình" often starts construction
    chunks = re.split(r"(?<=[.?!\n])\s+|(?=\bCho\s+hình\b)|(?=\bGọi\b)", text, flags=re.IGNORECASE)
    chunks = [c.strip(" \t\n;:") for c in chunks if c and c.strip(" \t\n;:")]
    metric_re = re.compile(
        r"khoảng\s+cách|khoang\s+cach|\bd\s*\(|diện\s+tích|dien\s+tich|\bS\s*\(|"
        r"thể\s+tích|the\s+tich|\bV\s*\(|góc\b|goc\b|chu\s+vi",
        re.IGNORECASE,
    )
    # Prefer the last metric-looking chunk (often "Tính ... bằng bao nhiêu?")
    metric_chunks = [c for c in chunks if metric_re.search(c)]
    if not metric_chunks:
        return text
    # Prefer short pure questions over long "Cho hình... Tính d..."
    metric_chunks.sort(key=lambda c: (len(c) > 160, -len(metric_re.findall(c)), len(c)))
    return metric_chunks[0]


def _normalize_distance_target_text(value: str) -> str:
    target = value.strip()
    if target.startswith("(") and target.endswith(")"):
        return f"({_compact_point_sequence_text(target[1:-1])})"
    compact = _compact_point_sequence_text(target)
    # 3+ letters without parens after "mp/mặt phẳng" → plane ref
    if len(compact) >= 3:
        return f"({compact})"
    return compact


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
        inner = _normalize_parenthesized_geometry(question[index + 1 : end])
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
