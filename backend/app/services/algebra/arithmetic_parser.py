from __future__ import annotations

import re
import unicodedata

_NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
_INTEGER_LIST = r"-?\d+(?:\s*(?:,|;|va)\s*-?\d+){1,7}"


def parse_arithmetic_natural_language(raw: str) -> str | None:
    plain = _plain_text(raw)

    gcd_match = re.search(rf"(?:ucln|uoc chung lon nhat|gcd)\s*(?:cua)?\s*\(?\s*({_INTEGER_LIST})\s*\)?", plain)
    if gcd_match:
        return _integer_operation("gcd", gcd_match.group(1))

    lcm_match = re.search(rf"(?:bcnn|boi chung nho nhat|lcm)\s*(?:cua)?\s*\(?\s*({_INTEGER_LIST})\s*\)?", plain)
    if lcm_match:
        return _integer_operation("lcm", lcm_match.group(1))

    power_match = re.search(r"(?:tinh\s+)?(?:luy thua\s+)?(-?\d+)\s+mu\s+(-?\d+)", plain)
    if power_match:
        return f"power({power_match.group(1)},{power_match.group(2)})"

    divisible_match = re.search(r"(?:kiem tra\s+)?(-?\d+)\s*(?:co\s+)?chia het\s+(?:cho\s+)?(-?\d+)", plain)
    if divisible_match:
        return f"divisible({divisible_match.group(1)},{divisible_match.group(2)})"

    percent_ratio = re.search(
        rf"({_NUMBER})\s*(?:la|chiem)\s*(?:bao nhieu|may)\s*(?:%|phan tram)\s*cua\s*({_NUMBER})",
        plain,
    )
    if percent_ratio:
        part, whole = map(_decimal_point, percent_ratio.groups())
        return f"percent_ratio(part={part},whole={whole})"

    percent_base = re.search(
        rf"({_NUMBER})\s*(?:%|phan tram)\s*cua\s*(?:so do|no|mot so)\s*(?:bang|la)\s*({_NUMBER})",
        plain,
    )
    if percent_base:
        rate, part = map(_decimal_point, percent_base.groups())
        return f"percent_base(rate={rate},part={part})"

    percent_of = re.search(rf"({_NUMBER})\s*(?:%|phan tram)\s*cua\s*({_NUMBER})", plain)
    if percent_of:
        rate, value = map(_decimal_point, percent_of.groups())
        return f"percent(rate={rate},value={value})"

    ratio_match = re.search(r"(?:rut gon\s+)?(?:ti le|ti so|ratio)\s*(-?\d+)\s*(?::|/|va)\s*(-?\d+)", plain)
    if ratio_match:
        return f"ratio({ratio_match.group(1)},{ratio_match.group(2)})"

    product = re.search(
        rf"(?:co|gom)\s*({_NUMBER})\s*(?:hop|tui|ro|nhom|day)\b.*?moi\s*(?:hop|tui|ro|nhom|day)\s*({_NUMBER})\s+([a-z]+(?:\s+[a-z]+)?)",
        plain,
    )
    if product and re.search(r"tat ca|tong cong|bao nhieu", plain):
        groups, size, unit = product.groups()
        return f"word_product(groups={_decimal_point(groups)},size={_decimal_point(size)},unit={_unit_token(unit)})"

    share = re.search(
        rf"(?:co|gom)\s*({_NUMBER})\s+([a-z]+(?:\s+[a-z]+)?)\s+chia\s+deu\s+(?:cho|thanh)\s*({_NUMBER})\b",
        plain,
    )
    if share and re.search(r"moi|bao nhieu", plain):
        total, unit, groups = share.groups()
        return f"word_share(total={_decimal_point(total)},groups={_decimal_point(groups)},unit={_unit_token(unit)})"

    inventory = _parse_inventory_problem(plain)
    if inventory:
        return inventory

    return None


def _parse_inventory_problem(plain: str) -> str | None:
    start_match = re.search(rf"(?:co|ban dau co|luc dau co)\s*({_NUMBER})\s+([a-z]+(?:\s+[a-z]+)?)", plain)
    if start_match is None or not re.search(r"con lai|hien co|bao nhieu", plain):
        return None
    start, unit = start_match.groups()
    actions: list[str] = []
    action_pattern = re.compile(
        rf"\b(ban|cho|mat|dung|an|giam|nhap them|mua them|duoc them|them)\s*({_NUMBER})(?:\s+([a-z]+(?:\s+[a-z]+)?))?\b"
    )
    for action, value, action_unit in action_pattern.findall(plain[start_match.end():]):
        if action_unit and not _units_compatible(unit, action_unit):
            return None
        operation = "add" if action in {"nhap them", "mua them", "duoc them", "them"} else "sub"
        actions.append(f"{operation}:{_decimal_point(value)}")
    if not actions:
        return None
    return f"word_inventory(start={_decimal_point(start)},unit={_unit_token(unit)};steps={'|'.join(actions)})"


def _unit_token(unit: str) -> str:
    return re.sub(r"\s+", "_", unit.strip())


def _units_compatible(expected: str, actual: str) -> bool:
    return expected.split()[0] == actual.split()[0]


def _integer_operation(operation: str, values_text: str) -> str:
    values = re.findall(r"-?\d+", values_text)
    return f"{operation}({','.join(values)})"


def _decimal_point(value: str) -> str:
    return value.replace(",", ".")


def _plain_text(raw: str) -> str:
    normalized = unicodedata.normalize("NFD", raw.lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents.replace("đ", "d")).strip()