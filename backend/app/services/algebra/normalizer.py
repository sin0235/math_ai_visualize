from __future__ import annotations

import re

_REPLACEMENTS = {
    "−": "-",
    "–": "-",
    "—": "-",
    "×": "*",
    "·": "*",
    "÷": "/",
    "≤": "<=",
    "≥": ">=",
    "π": "pi",
    "∞": "oo",
    "√": "sqrt",
}
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def normalize_algebra_input(raw: str) -> str:
    text = raw.strip()
    text = _strip_math_delimiters(text)
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    text = _replace_superscripts(text)
    text = _replace_latex_frac(text)
    text = _replace_latex_sqrt(text)
    text = _replace_latex_log_base(text)
    text = _replace_latex_commands(text)
    text = text.replace("^", "**")
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
    return re.sub(r"([A-Za-z0-9\)])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: f"{m.group(1)}**{m.group(2).translate(_SUPERSCRIPTS)}", text)


def _replace_latex_frac(text: str) -> str:
    pattern = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(lambda m: f"(({m.group(1)})/({m.group(2)}))", text)
    return text


def _replace_latex_sqrt(text: str) -> str:
    text = re.sub(r"\\sqrt\s*\[\s*3\s*\]\s*\{([^{}]+)\}", r"root(\1, 3)", text)
    return re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)


def _replace_latex_log_base(text: str) -> str:
    return re.sub(r"\\log_\{?([^{}\s]+)\}?\s*\(?([^\s()]+)\)?", r"log(\2, \1)", text)


def _replace_latex_commands(text: str) -> str:
    commands = {
        r"\\sin": "sin",
        r"\\cos": "cos",
        r"\\tan": "tan",
        r"\\cot": "cot",
        r"\\ln": "log",
        r"\\log": "log",
        r"\\pi": "pi",
        r"\\cdot": "*",
        r"\\times": "*",
        r"\\leq": "<=",
        r"\\geq": ">=",
        r"\\neq": "!=",
        r"\\left": "",
        r"\\right": "",
    }
    for source, target in commands.items():
        text = re.sub(source, target, text)
    text = text.replace("{", "(").replace("}", ")")
    return text
