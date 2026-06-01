"""Kiểm tra email dùng một lần (disposable) dựa trên danh sách vendored.

Danh sách lấy từ nguồn công khai, cập nhật bằng scripts/update_disposable_domains.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DISPOSABLE_DOMAINS_PATH = Path(__file__).resolve().parent.parent / "data" / "disposable_email_domains.txt"


@lru_cache(maxsize=1)
def _load_disposable_domains() -> frozenset[str]:
    try:
        text = DISPOSABLE_DOMAINS_PATH.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    )


def is_disposable_email(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if not domain:
        return False
    blocklist = _load_disposable_domains()
    if domain in blocklist:
        return True
    # Chặn cả subdomain của domain bị chặn (vd a@x.mailinator.com).
    return any(domain.endswith(f".{blocked}") for blocked in blocklist)
