"""Xác minh Cloudflare Turnstile cho các luồng auth.

Bật khi cờ admin turnstile_enabled = true và đã cấu hình đủ site key + secret key qua env.
Khi gọi Cloudflare lỗi mạng, coi như xác minh thất bại (fail-closed) để ưu tiên an toàn.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings
from app.schemas.auth import SystemFeatureFlags

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_required(flags: SystemFeatureFlags, settings: Settings) -> bool:
    return bool(flags.turnstile_enabled and settings.turnstile_secret_key and settings.turnstile_site_key)


async def verify_turnstile_token(settings: Settings, token: str, remote_ip: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": remote_ip,
                },
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Turnstile verify thất bại do lỗi gọi Cloudflare: %s", error)
        return False
    return payload.get("success") is True


async def enforce_turnstile(flags: SystemFeatureFlags, settings: Settings, token: str | None, remote_ip: str) -> None:
    if not turnstile_required(flags, settings):
        return
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng hoàn tất xác minh con người (Turnstile).")
    if not await verify_turnstile_token(settings, token, remote_ip):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Xác minh Turnstile thất bại. Vui lòng thử lại.")
