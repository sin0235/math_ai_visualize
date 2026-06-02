from __future__ import annotations

import re
import unicodedata

from app.schemas.algebra import AlgebraInputChip, AlgebraInputInterpretation, AlgebraSolveRequest
from app.services.algebra.normalizer import is_structured_algebra_input, normalize_algebra_input

_RELATION_RE = re.compile(r"(<=|>=|!=|=|<|>|≤|≥|≠)")
_VARIABLE_RE = re.compile(r"\b([a-zA-Z])\b")
_LATEX_HINT_RE = re.compile(r"\\(?:frac|sqrt|sin|cos|tan|log|ln)|\$\$?|\\\(|\\\[")


def interpret_algebra_input(request: AlgebraSolveRequest) -> AlgebraInputInterpretation:
    raw = request.input.strip()
    detected_format = _detect_format(raw, request.input_format)
    canonical = _canonical_from_natural_language(raw) if detected_format in {"natural_vi", "mixed"} else raw
    structured = _structured_from_natural_language(raw)
    if structured:
        canonical = structured
    is_structured = is_structured_algebra_input(canonical)
    canonical = canonical.strip() if is_structured else _clean_canonical(canonical)
    normalized_preview = normalize_algebra_input(canonical)
    topic_hint = request.topic if request.topic != "auto" else _detect_topic(raw, normalized_preview)
    variables = request.variables or _detect_variables(raw, normalized_preview, topic_hint)
    domain = _detect_domain(raw, request.domain, topic_hint)
    chips = _build_chips(raw, canonical, topic_hint, variables, domain, detected_format)
    warnings: list[str] = []
    if canonical != raw and detected_format in {"natural_vi", "mixed"}:
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
    has_vi = bool(re.search(r"[À-ỹ]", raw)) or bool(re.search(r"\b(giai|giải|tim|tìm|phuong|phương|bat|bất|he|hệ|nghiem|nghiệm|to hop|tổ hợp|chinh hop|chỉnh hợp|cap so|cấp số|tham so|tham số|giai thua|giai thừa)\b", raw, re.IGNORECASE))
    has_math = bool(_RELATION_RE.search(raw) or re.search(r"[\^*/()]|[a-zA-Z]\d|\d[a-zA-Z]", raw))
    if has_vi and has_math:
        return "mixed"
    if has_vi:
        return "natural_vi"
    return "plain"


def _canonical_from_natural_language(raw: str) -> str:
    structured = _structured_from_natural_language(raw)
    if structured:
        return structured
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


def _structured_from_natural_language(raw: str) -> str | None:
    text = _normalize_text(raw)
    plain = _strip_accents(text.lower())
    combination = re.search(r"(?:to hop|c)\s*(?:chap\s*)?(\d+)\s*(?:cua|trong|,)?\s*(\d+)", plain)
    if combination:
        k, n = combination.groups()
        return f"C({n},{k})"
    permutation = re.search(r"(?:chinh hop|a)\s*(?:chap\s*)?(\d+)\s*(?:cua|trong|,)?\s*(\d+)", plain)
    if permutation:
        k, n = permutation.groups()
        return f"A({n},{k})"
    factorial = re.search(r"\b(\d+)\s*(?:giai thua|!)\b", plain)
    if factorial:
        return f"{factorial.group(1)}!"
    coefficient = re.search(r"he so cua\s+([a-zA-Z])\^?(\d+)\s+trong\s+(.+)$", plain)
    if coefficient:
        variable, power, expression = coefficient.groups()
        return f"coefficient({_clean_canonical(expression)},{variable},{power})"
    parameter_template = _parameter_template_from_text(text, plain)
    if parameter_template:
        return parameter_template
    sequence_template = _sequence_template_from_text(plain)
    if sequence_template:
        return sequence_template
    return None


def _parameter_template_from_text(text: str, plain: str) -> str | None:
    if "tham so" not in plain and not re.search(r"\btim\s+m\b", plain):
        return None
    relation = _extract_relation_sentence(_replace_vietnamese_math_words(text))
    if not relation:
        return None
    expression = relation.split("=", 1)[0] if "=" in relation else relation
    a, b, c, variable, parameter = _extract_quadratic_coefficients(expression)
    if a is None:
        return None
    if "nghiem kep" in plain:
        kind = "quadratic_double_root"
    elif "hai nghiem phan biet" in plain or "2 nghiem phan biet" in plain:
        kind = "quadratic_has_two_roots"
    elif "vo nghiem" in plain:
        kind = "quadratic_no_real_root"
    elif "duong voi moi" in plain or "lon hon 0 voi moi" in plain:
        kind = "quadratic_positive_all"
    elif "co nghiem" in plain:
        kind = "quadratic_has_real_root"
    else:
        return None
    return f"{kind}(a={a},b={b},c={c},var={variable},param={parameter})"


def _extract_quadratic_coefficients(expression: str) -> tuple[str | None, str | None, str | None, str, str]:
    normalized = _clean_canonical(expression)
    match = re.fullmatch(r"(.+?)\*?([a-zA-Z])\^2([+-].+?)\*?([a-zA-Z])([+-].+)", normalized)
    if not match:
        return None, None, None, "x", "m"
    a, variable, b, linear_variable, c = match.groups()
    if variable != linear_variable:
        return None, None, None, variable, "m"
    a = a.rstrip("*") or "1"
    if a == "-":
        a = "-1"
    parameter_match = re.search(r"\b([a-zA-Z])\b", b)
    parameter = parameter_match.group(1) if parameter_match else "m"
    return a, b.rstrip("*"), c, variable, parameter


def _sequence_template_from_text(plain: str) -> str | None:
    if "cap so" not in plain:
        return None
    values = dict(re.findall(r"\b(u1|d|q|n)\s*=\s*(-?\d+(?:/\d+)?)", plain))
    if "u1" not in values or "n" not in values:
        return None
    asks_sum = "tong" in plain or "s_n" in plain or "sn" in plain
    if "cong" in plain and "d" in values:
        name = "arithmetic_sum" if asks_sum else "arithmetic"
        return f"{name}(u1={values['u1']},d={values['d']},n={values['n']})"
    if "nhan" in plain and "q" in values:
        name = "geometric_sum" if asks_sum else "geometric"
        return f"{name}(u1={values['u1']},q={values['q']},n={values['n']})"
    return None


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
        (r"\blogarit\b|\bloga\b", "log"),
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
        r"^\s*(hãy\s+)?(giải|giai|tìm tập nghiệm của|tim tap nghiem cua|tìm tập nghiệm|tim tap nghiem|tìm nghiệm của|tim nghiem cua|tìm nghiệm|tim nghiem|tìm x thỏa mãn|tim x thoa man|tìm|tim)\s+",
        r"^\s*(phương trình|phuong trinh|bất phương trình|bat phuong trinh|hệ phương trình|he phuong trinh|biểu thức|bieu thuc)\s+",
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
    if any(key in plain for key in ("log", "ln", "mu", "luy thua", "logarit", "loga")) or re.search(r"\blog\(|\bexp\(", normalized):
        return "exponential_log"
    if any(key in plain for key in ("luong giac", "sin", "cos", "tan", "cot")):
        return "trigonometry"
    if any(key in plain for key in ("so phuc", "complex", "mo dun", "module", "phan thuc", "phan ao", "lien hop")) or re.search(r"\bi\b|I", normalized):
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
