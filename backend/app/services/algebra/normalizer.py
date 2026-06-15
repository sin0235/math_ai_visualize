from __future__ import annotations

import re
import unicodedata

_REPLACEMENTS = {
    "−": "-",
    "–": "-",
    "—": "-",
    "×": "*",
    "·": "*",
    "⋅": "*",
    "÷": "/",
    "≤": "<=",
    "≥": ">=",
    "≠": "!=",
    "π": "pi",
    "∞": "oo",
    "√": "sqrt",
}
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_STRUCTURED_PREFIXES = (
    "arithmetic(",
    "arithmetic_sum(",
    "geometric(",
    "geometric_sum(",
    "coefficient(",
    "factorial(",
    "binomial(",
    "C(",
    "A(",
    "quadratic_double_root(",
    "quadratic_has_two_roots(",
    "quadratic_has_real_root(",
    "quadratic_no_real_root(",
    "quadratic_positive_all(",
    "derivative(",
    "limit(",
    "integral(",
)


def normalize_algebra_input(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw.strip())
    text = _strip_math_delimiters(text)
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    text = _replace_superscripts(text)
    text = unicodedata.normalize("NFKC", text)
    text = _replace_latex_calculus(text)
    text = _replace_subscript_log_base(text)
    text = _replace_latex_cases(text)
    text = _replace_latex_frac(text)
    text = _replace_latex_sqrt(text)
    text = _replace_latex_log_base(text)
    text = _replace_latex_inverse_trig(text)
    text = _replace_latex_commands(text)
    text = _normalize_function_parentheses(text)
    text = text.replace("^", "**")
    text = _normalize_structured_template(text)
    text = re.sub(r"\s*(<=|>=|!=|=|<|>)\s*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _replace_latex_calculus(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("\\"):
        return text
    return _latex_derivative_template(stripped) or _latex_integral_template(stripped) or _latex_limit_template(stripped) or text


def _latex_derivative_template(text: str) -> str | None:
    match = re.match(r"\\frac\s*\{\s*d\s*\}\s*\{\s*d\s*([A-Za-z])\s*\}", text)
    if not match:
        return None
    variable = match.group(1)
    arg_start = _skip_spaces_and_latex_left(text, match.end())
    expression, arg_end = _read_group_or_token(text, arg_start)
    if expression is None:
        expression = text[arg_start:].strip()
        arg_end = len(text)
    if text[arg_end:].strip():
        return None
    expression = _clean_latex_group(expression)
    if not expression:
        return None
    return f"derivative(expr={expression},var={variable})"


def _latex_integral_template(text: str) -> str | None:
    if not text.startswith("\\int"):
        return None
    index = len("\\int")
    lower: str | None = None
    upper: str | None = None
    index = _skip_spaces(text, index)
    if text.startswith("\\limits", index):
        index += len("\\limits")
        index = _skip_spaces(text, index)
    if index < len(text) and text[index] == "_":
        lower, index = _read_script_value(text, index + 1)
        index = _skip_spaces(text, index)
    if index < len(text) and text[index] == "^":
        upper, index = _read_script_value(text, index + 1)
        index = _skip_spaces(text, index)
    body = text[index:].strip()
    body = re.sub(r"\\[,;!]\s*", " ", body).strip()
    match = re.match(
        r"(.+?)\s*(?:\\mathrm\s*\{\s*d\s*\}|\\operatorname\s*\{\s*d\s*\}|\\text\s*\{\s*d\s*\}|\{\s*d\s*\}|d)\s*([A-Za-z])\s*$",
        body,
    )
    if match:
        expression = match.group(1).strip()
        variable = match.group(2)
    else:
        expression = body
        variable = "x"
    expression = _clean_latex_group(expression)
    if not expression:
        return None
    if lower is not None and upper is not None and lower.strip() and upper.strip():
        return f"integral(expr={expression},var={variable},a={_clean_latex_group(lower)},b={_clean_latex_group(upper)})"
    return f"integral(expr={expression},var={variable})"


def _latex_limit_template(text: str) -> str | None:
    if not text.startswith("\\lim"):
        return None
    index = len("\\lim")
    index = _skip_spaces(text, index)
    if index >= len(text) or text[index] != "_":
        return None
    subscript, index = _read_script_value(text, index + 1)
    if subscript is None:
        return None
    subscript = _clean_latex_group(subscript)
    target = re.match(r"\s*([A-Za-z])\s*\\to\s*(.+?)\s*$", subscript)
    if not target:
        return None
    variable, point = target.groups()
    arg_start = _skip_spaces_and_latex_left(text, index)
    expression, arg_end = _read_group_or_token(text, arg_start)
    if expression is None:
        expression = text[arg_start:].strip()
        arg_end = len(text)
    if text[arg_end:].strip():
        return None
    expression = _clean_latex_group(expression)
    if not expression:
        return None
    return f"limit(expr={expression},var={variable},to={_clean_latex_group(point)})"


def _read_script_value(text: str, start: int) -> tuple[str | None, int]:
    index = _skip_spaces(text, start)
    if index < len(text) and text[index] == "{":
        return _read_braced(text, index)
    end = index
    while end < len(text) and re.match(r"[A-Za-z0-9.+\-*/]", text[end]):
        end += 1
    if end == index:
        return None, start
    return text[index:end], end


def _skip_spaces(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def is_structured_algebra_input(text: str) -> bool:
    return text.strip().startswith(_STRUCTURED_PREFIXES) or bool(re.fullmatch(r"\d+!", text.strip()))


def _strip_math_delimiters(text: str) -> str:
    text = text.strip()
    if text.startswith("$$") and text.endswith("$$") and len(text) >= 4:
        return text[2:-2].strip()
    if text.startswith("$") and text.endswith("$") and len(text) >= 2:
        return text[1:-1].strip()
    if text.startswith("\\(") and text.endswith("\\)"):
        return text[2:-2].strip()
    if text.startswith("\\[") and text.endswith("\\]"):
        return text[2:-2].strip()
    return text


def _replace_superscripts(text: str) -> str:
    return re.sub(r"([A-Za-z0-9\)])([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)", lambda match: f"{match.group(1)}**{match.group(2).translate(_SUPERSCRIPTS)}", text)


def _replace_subscript_log_base(text: str) -> str:
    return re.sub(r"log([₀₁₂₃₄₅₆₇₈₉]+)", lambda match: f"log_{match.group(1).translate(_SUBSCRIPTS)}", text)


def _replace_latex_cases(text: str) -> str:
    pattern = re.compile(r"\\begin\{cases\}(.+?)\\end\{cases\}", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        parts = [part.strip() for part in re.split(r"\\\\|\\;|;|\n", body) if part.strip()]
        return "; ".join(parts)

    return pattern.sub(replace, text)


def _replace_latex_frac(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        match = re.search(r"\\frac\s*\{", text)
        if not match:
            break
        replacement = _replace_first_latex_binary_command(text, match.start(), "\\frac", lambda left, right: f"(({left})/({right}))")
        if replacement is None:
            break
        text = replacement
    return text


def _replace_latex_sqrt(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\sqrt\s*\[\s*([^\[\]{}]+)\s*\]\s*\{([^{}]+)\}", r"root(\2, \1)", text)
        text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    return text


def _replace_latex_log_base(text: str) -> str:
    index = 0
    result: list[str] = []
    while index < len(text):
        start = _find_next_log_base(text, index)
        if start < 0:
            result.append(text[index:])
            break
        result.append(text[index:start])
        prefix = "\\log_" if text.startswith("\\log_", start) else "log_"
        base_start = start + len(prefix)
        base, base_end = _read_log_base(text, base_start)
        if base is None:
            result.append(text[start:base_start])
            index = base_start
            continue
        arg_start = _skip_spaces_and_latex_left(text, base_end)
        arg, arg_end = _read_group_or_token(text, arg_start)
        if arg is None:
            result.append(text[start:base_end])
            index = base_end
            continue
        result.append(f"log({_clean_latex_group(arg)}, {_clean_latex_group(base)})")
        index = arg_end
    return "".join(result)


def _replace_latex_inverse_trig(text: str) -> str:
    replacements = {
        "sin": "asin",
        "cos": "acos",
        "tan": "atan",
        "cot": "acot",
    }
    for source, target in replacements.items():
        text = _replace_inverse_trig_command(text, source, target)
    return text


def _replace_inverse_trig_command(text: str, source: str, target: str) -> str:
    pattern = re.compile(rf"\\{source}\s*\^\s*\{{\s*-1\s*\}}")
    index = 0
    result: list[str] = []
    while True:
        match = pattern.search(text, index)
        if not match:
            result.append(text[index:])
            break
        result.append(text[index:match.start()])
        arg_start = _skip_spaces_and_latex_left(text, match.end())
        arg, arg_end = _read_group_or_token(text, arg_start)
        if arg is None:
            result.append(text[match.start():match.end()])
            index = match.end()
            continue
        result.append(f"{target}({_clean_latex_group(arg)})")
        index = arg_end
    return "".join(result)


def _find_next_log_base(text: str, start: int) -> int:
    candidates = [position for position in (text.find("\\log_", start), text.find("log_", start)) if position >= 0]
    return min(candidates) if candidates else -1


def _read_log_base(text: str, start: int) -> tuple[str | None, int]:
    if start < len(text) and text[start] == "{":
        return _read_braced(text, start)
    end = start
    while end < len(text) and re.match(r"[A-Za-z0-9.+\-*/^]", text[end]):
        end += 1
    if end == start:
        return None, start
    return text[start:end], end


def _skip_spaces_and_latex_left(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    if text.startswith("\\left", index):
        index += len("\\left")
        while index < len(text) and text[index].isspace():
            index += 1
    return index


def _read_group_or_token(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text):
        return None, start
    if text[start] == "(":
        return _read_parenthesized(text, start)
    if text[start] == "{":
        return _read_braced(text, start)
    end = start
    while end < len(text) and re.match(r"[A-Za-z0-9.+\-*/^]", text[end]):
        end += 1
    if end == start:
        return None, start
    return text[start:end], end


def _read_parenthesized(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] != "(":
        return None, start
    depth = 0
    content_start = start + 1
    for position in range(start, len(text)):
        char = text[position]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[content_start:position], position + 1
    return None, start


def _clean_latex_group(value: str) -> str:
    return value.replace("\\left", "").replace("\\right", "").strip()


def _replace_latex_commands(text: str) -> str:
    commands = {
        r"\\sin": "sin",
        r"\\cos": "cos",
        r"\\tan": "tan",
        r"\\cot": "cot",
        r"\\arcsin": "asin",
        r"\\arccos": "acos",
        r"\\arctan": "atan",
        r"\\arccot": "acot",
        r"\\ln": "log",
        r"\\log": "log",
        r"\\pi": "pi",
        r"\\cdot": "*",
        r"\\times": "*",
        r"\\leq?\b": "<=",
        r"\\geq?\b": ">=",
        r"\\neq?\b": "!=",
        r"\\left": "",
        r"\\right": "",
    }
    for source, target in commands.items():
        text = re.sub(source, target, text)
    text = text.replace("{", "(").replace("}", ")")
    return text


def _normalize_function_parentheses(text: str) -> str:
    for name in ("sin", "cos", "tan", "cot", "asin", "acos", "atan", "acot", "arcsin", "arccos", "arctan", "arccot", "log", "sqrt", "Abs", "abs"):
        text = re.sub(rf"\b{name}\s+([A-Za-z0-9.]+)", rf"{name}(\1)", text)
    return text


def _normalize_structured_template(text: str) -> str:
    match = re.fullmatch(r"(derivative|limit|integral)\((.*)\)", text.strip())
    if not match:
        return text
    name, args_text = match.groups()
    parts: list[str] = []
    for part in _split_top_level_args(args_text):
        if "=" not in part:
            parts.append(part.strip())
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"expr", "to", "a", "b", "order"}:
            value = _normalize_structured_value(value)
        parts.append(f"{key}={value}")
    return f"{name}({','.join(parts)})"


def _split_top_level_args(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _normalize_structured_value(value: str) -> str:
    text = value.strip(" :;,.")
    text = re.sub(r"\s+", "", text)
    text = text.replace("^", "**")
    text = re.sub(r"(\d)([A-Za-z])", r"\1*\2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1*\2", text)
    text = re.sub(r"(\))(\()", r"\1*\2", text)
    text = re.sub(r"(\d)(\()", r"\1*\2", text)
    text = re.sub(r"(\))([A-Za-z])", r"\1*\2", text)
    return text


def _replace_first_latex_binary_command(text: str, start: int, command: str, formatter) -> str | None:
    index = start + len(command)
    left, left_end = _read_braced(text, index)
    if left is None:
        return None
    right, right_end = _read_braced(text, left_end)
    if right is None:
        return None
    return text[:start] + formatter(left, right) + text[right_end:]


def _read_braced(text: str, start: int) -> tuple[str | None, int]:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "{":
        return None, start
    depth = 0
    content_start = index + 1
    for position in range(index, len(text)):
        char = text[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[content_start:position], position + 1
    return None, start
