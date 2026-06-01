"""Cập nhật danh sách disposable email domain (vendored) từ nguồn công khai.

Chạy thủ công định kỳ: python backend/scripts/update_disposable_domains.py
Nguồn: disposable-email-domains (nội dung public-domain).
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/main/disposable_email_blocklist.conf"
OUTPUT_PATH = BACKEND_ROOT / "app" / "data" / "disposable_email_domains.txt"


def normalize_domains(raw_text: str) -> list[str]:
    domains: set[str] = set()
    for line in raw_text.splitlines():
        domain = line.strip().lower()
        if not domain or domain.startswith("#"):
            continue
        domains.add(domain)
    return sorted(domains)


def main() -> None:
    try:
        response = httpx.get(SOURCE_URL, timeout=60, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as error:
        print(f"Không tải được danh sách disposable domain: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    domains = normalize_domains(response.text)
    if not domains:
        print("Danh sách tải về rỗng, giữ nguyên file hiện tại.", file=sys.stderr)
        raise SystemExit(1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(domains) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(domains)} domain vào {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
