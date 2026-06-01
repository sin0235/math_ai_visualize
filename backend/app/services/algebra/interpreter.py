from __future__ import annotations

import re
import unicodedata

from app.schemas.algebra import AlgebraInputChip, AlgebraInputInterpretation, AlgebraSolveRequest
from app.services.algebra.normalizer import normalize_algebra_input

_RELATION_RE = re.compile(r"(<=|>=|!=|=|<|>|≤|≥|≠)")
_VARIABLE_RE = re.compile(r"\b([a-zA-Z])\b")
_LATEX_HINT_RE = re.compile(r"\\(?:frac|sqrt|sin|cos|tan|log|ln)|\$\$?|\\\(|\\\[")


def interpret_algebra_input(request: AlgebraSolveRequest) -> AlgebraInputInterpretation:
    raw = request.input.strip()
    detected_format = _detect_format(raw, request.input_format)
    canonical = _canonical_from_natural_language(raw) if detected_format in {"natural_vi", "mixed"} else raw
    is_structured = bool(re.match(r"^(arithmetic|arithmetic_sum|geometric|geometric_sum|coefficient|factorial|binomial|C|A|quadratic_double_root|quadratic_has_two_roots|quadratic_has_real_root|quadratic_no_real_root|quadratic_positive_all)\(", canonical.strip()))
    canonical = canonical.strip() if is_structured else _clean_canonical(canonical)
    normalized_preview = normalize_algebra_input(canonical)
    topic_hint = request.topic if request.topic != "auto" else _detect_topic(raw, normalized_preview)
    variables = request.variables or _detect_variables(raw, normalized_preview, topic_hint)
    domain = _detect_domain(raw, request.domain, topic_hint)
    chips = _build_chips(raw, canonical, topic_hint, variables, domain, detected_format)
    warnings: list[str] = []
    if canonical != raw:
        warnings.append("Đã diễn giải đề tiếng Việt thành biểu thức chuẩn trước khi giải.")
    if detected_format == "mixed":
        warnings.append("Đầu vào gồm cả mô tả tự nhiên và ký hiệu toán; hệ thống ưu tiên phần biểu thức được trích xuất.")
    return AlgebraInputInterpretation(
        detected_format=detected_format,
        source="structured_ui" if detected_format == "structured" else "rule_based_vi" if detected_format in {"natural_vi", "mixed"} else "latex_normalizer" if detected_format == "latex" else "raw",
        canonical_input=canonical,
        topic_hint=topic_hint,
        variables=variables,
        domain=domain,
        chips=chips,
        warnings=warnings,
    )


def _detect_format(raw: str, requested: str) -> str:
    if requested == "structured":
        return "structured"
    if requested == "latex" or _LATEX_HINT_RE.search(raw):
        return "latex"
    has_vi = bool(re.search(r"[À-ỹ]", raw)) or bool(re.search(r"\b(giai|giải|tim|tìm|phuong|phương|bat|bất|he|hệ|nghiem|nghiệm)\b", raw, re.IGNORECASE))
    has_math = bool(_RELATION_RE.search(raw) or re.search(r"[\^*/()]|[a-zA-Z]\d|\d[a-zA-Z]", raw))
    if has_vi and has_math:
        return "mixed"
    if has_vi:
        return "natural_vi"
    return "plain"


def _canonical_from_natural_language(raw: str) -> str:
    text = _normalize_text(raw)
    text = _replace_vietnamese_math_words(text)
    text = _strip_intent_phrases(text)
    system = _extract_system(text)
    if system:
        return system
    relation = _extract_relation_sentence(text)
    if relation:
        return relation
    expression = _extract_expression_after_keywords(text)
    if expression:
        return expression
    return text


def _normalize_text(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw).strip()
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d").replace("Đ", "D")


def _replace_vietnamese_math_words(text: str) -> str:
    replacements = [
        (r"\bbằng\b|\bbang\b", "="),
        (r"\bkhác\b|\bkhac\b", "!="),
        (r"\blớn hơn hoặc bằng\b|\blon hon hoac bang\b|\bkhông nhỏ hơn\b|\bkhong nho hon\b", ">="),
        (r"\bnhỏ hơn hoặc bằng\b|\bnho hon hoac bang\b|\bkhông lớn hơn\b|\bkhong lon hon\b", "<="),
        (r"\blớn hơn\b|\blon hon\b", ">"),
        (r"\bnhỏ hơn\b|\bnho hon\b", "<"),
        (r"\bbình phương\b|\bbinh phuong\b", "^2"),
        (r"\blập phương\b|\blap phuong\b", "^3"),
        (r"\bmũ\b|\bmu\b|\blũy thừa\b|\bluy thua\b", "^"),
        (r"\bcăn bậc hai của\b|\bcan bac hai cua\b|\bcăn của\b|\bcan cua\b", "sqrt"),
        (r"\bcăn\b|\bcan\b", "sqrt"),
        (r"\bnhân\b|\bnhan\b", "*"),
        (r"\bchia\b", "/"),
        (r"\bcộng\b|\bcong\b", "+"),
        (r"\btrừ\b|\btru\b", "-"),
        (r"\bpi\b", "pi"),
    ]
    result = text
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
    result = re.sub(r"\bsin\s+([a-zA-Z0-9(])", r"sin(\1", result)
    result = re.sub(r"\bcos\s+([a-zA-Z0-9(])", r"cos(\1", result)
    result = re.sub(r"\btan\s+([a-zA-Z0-9(])", r"tan(\1", result)
    return result


def _strip_intent_phrases(text: str) -> str:
    patterns = [
        r"^\s*(hãy\s+)?(giải|giai|tìm nghiệm của|tim nghiem cua|tìm nghiệm|tim nghiem|tìm x thỏa mãn|tim x thoa man|tìm|tim)\s+",
        r"^\s*(phương trình|phuong trinh|bất phương trình|bat phuong trinh|hệ phương trình|he phuong trinh)\s+",
        r"\s+(theo|trên|trong)\s+(miền\s+)?(số\s+)?(thực|phức|nguyên|tự nhiên|thuc|phuc|nguyen|tu nhien)\s*$",
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    return result.strip(" :;,.")


def _extract_system(text: str) -> str | None:
    lowered = _strip_accents(text.lower())
    if " he " not in f" {lowered} " and "he phuong trinh" not in lowered:
        return None
    candidates = re.split(r"\s*(?:;|,|\bvà\b|\bva\b|\band\b)\s*", text, flags=re.IGNORECASE)
    equations = [_clean_canonical(_extract_relation_sentence(part) or part) for part in candidates]
    equations = [item for item in equations if _RELATION_RE.search(item)]
    return "; ".join(equations) if len(equations) >= 2 else None


def _extract_relation_sentence(text: str) -> str | None:
    text = text.strip(" :;,.")
    if _RELATION_RE.search(text):
        match = re.search(r"([A-Za-z0-9\\_{}\[\]().,+\-*/^ ≤≥≠=<>]+(?:<=|>=|!=|=|<|>|≤|≥|≠)[A-Za-z0-9\\_{}\[\]().,+\-*/^ ≤≥≠=<>]+)", text)
        if match:
            return _clean_canonical(match.group(1))
        return _clean_canonical(text)
    return None


def _extract_expression_after_keywords(text: str) -> str | None:
    match = re.search(r"(?:biểu thức|bieu thuc|giá trị|gia tri)\s+(.+)$", text, flags=re.IGNORECASE)
    return _clean_canonical(match.group(1)) if match else None


def _clean_canonical(value: str) -> str:
    text = value.strip(" :;,.")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([=<>!+\-*/^;,])\s*", r"\1", text)
    text = text.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    text = re.sub(r"(\d)([A-Za-z])", r"\1*\2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1*\2", text)
    text = re.sub(r"sqrt\s*([A-Za-z0-9]+)", r"sqrt(\1)", text)
    return text


def _detect_topic(raw: str, normalized: str) -> str:
    plain = _strip_accents(raw.lower())
    if normalized.startswith(("arithmetic(", "arithmetic_sum(", "geometric(", "geometric_sum(")):
        return "sequence"
    if normalized.startswith(("C(", "A(", "binomial(", "factorial(", "coefficient(")) or normalized.endswith("!"):
        return "combinatorics_probability"
    if normalized.startswith(("quadratic_double_root(", "quadratic_has_two_roots(", "quadratic_has_real_root(", "quadratic_no_real_root(", "quadratic_positive_all(")):
        return "parameter"
    if ";" in normalized or "he phuong trinh" in plain:
        return "system"
    if any(key in plain for key in ("bat phuong trinh", "lon hon", "nho hon", "khong am", "duong")) or re.search(r"<=|>=|<|>", normalized):
        return "inequality"
    if any(key in plain for key in ("log", "ln", "mu", "luy thua")) or re.search(r"\blog\(|\bexp\(", normalized):
        return "exponential_log"
    if any(key in plain for key in ("luong giac", "sin", "cos", "tan", "cot")):
        return "trigonometry"
    if any(key in plain for key in ("so phuc", "complex")) or re.search(r"\bi\b|I", normalized):
        return "complex"
    if "=" in normalized:
        return "equation"
    return "auto"


def _detect_variables(raw: str, normalized: str, topic_hint: str) -> list[str]:
    plain = _strip_accents(raw.lower())
    explicit = re.search(r"(?:theo|ẩn|an|biến|bien)\s+([a-zA-Z](?:\s*,\s*[a-zA-Z])*)", plain)
    if explicit:
        return [item.strip() for item in explicit.group(1).split(",") if item.strip()]
    variables = sorted({match.group(1) for match in _VARIABLE_RE.finditer(normalized) if match.group(1) not in {"e", "i"}})
    if topic_hint == "system" and len(variables) >= 2:
        return variables[:4]
    if variables:
        return [variables[0]]
    return ["x"]


def _detect_domain(raw: str, requested_domain: str, topic_hint: str) -> str:
    plain = _strip_accents(raw.lower())
    if "so phuc" in plain or topic_hint == "complex":
        return "C"
    if "so nguyen" in plain:
        return "Z"
    if "tu nhien" in plain:
        return "N"
    if "so thuc" in plain:
        return "R"
    return requested_domain


def _build_chips(raw: str, canonical: str, topic: str, variables: list[str], domain: str, detected_format: str) -> list[AlgebraInputChip]:
    chips = [
        AlgebraInputChip(kind="format", label="Dạng nhập", value=_format_label(detected_format)),
        AlgebraInputChip(kind="topic", label="Nhận dạng", value=topic),
        AlgebraInputChip(kind="domain", label="Miền", value=domain),
    ]
    if variables:
        chips.append(AlgebraInputChip(kind="variable", label="Biến", value=", ".join(variables)))
    relation = _RELATION_RE.search(canonical)
    if relation:
        chips.append(AlgebraInputChip(kind="relation", label="Quan hệ", value=relation.group(1)))
    if raw != canonical:
        chips.append(AlgebraInputChip(kind="expression", label="Biểu thức chuẩn", value=canonical))
    return chips


def _format_label(detected_format: str) -> str:
    labels = {
        "plain": "công thức",
        "latex": "LaTeX",
        "natural_vi": "tiếng Việt",
        "mixed": "tiếng Việt + công thức",
        "structured": "ô công thức",
    }
    return labels.get(detected_format, detected_format)
