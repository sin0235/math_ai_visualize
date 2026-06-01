import asyncio

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.auth import SystemFeatureFlags
from app.services import turnstile as turnstile_service
from app.services.email_guard import is_disposable_email
from app.services.turnstile import enforce_turnstile, turnstile_required


def test_is_disposable_email_blocks_known_domain():
    assert is_disposable_email("user@mailinator.com") is True


def test_is_disposable_email_blocks_subdomain():
    assert is_disposable_email("user@inbox.mailinator.com") is True


def test_is_disposable_email_allows_normal_domain():
    assert is_disposable_email("user@gmail.com") is False


def test_turnstile_required_only_when_flag_and_keys_are_configured():
    flags_on = SystemFeatureFlags(turnstile_enabled=True)
    flags_off = SystemFeatureFlags(turnstile_enabled=False)
    with_keys = Settings(_env_file=None, turnstile_secret_key="secret", turnstile_site_key="site")
    without_secret = Settings(_env_file=None, turnstile_secret_key=None, turnstile_site_key="site")
    without_site_key = Settings(_env_file=None, turnstile_secret_key="secret", turnstile_site_key=None)

    assert turnstile_required(flags_on, with_keys) is True
    assert turnstile_required(flags_on, without_secret) is False
    assert turnstile_required(flags_on, without_site_key) is False
    assert turnstile_required(flags_off, with_keys) is False


def test_enforce_turnstile_skips_when_disabled():
    flags = SystemFeatureFlags(turnstile_enabled=False)
    settings = Settings(_env_file=None, turnstile_secret_key=None)
    # Không bật thì không raise dù thiếu token.
    asyncio.run(enforce_turnstile(flags, settings, None, "127.0.0.1"))


def test_enforce_turnstile_requires_token_when_enabled():
    flags = SystemFeatureFlags(turnstile_enabled=True)
    settings = Settings(_env_file=None, turnstile_secret_key="secret", turnstile_site_key="site")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(enforce_turnstile(flags, settings, None, "127.0.0.1"))
    assert exc.value.status_code == 400


def test_enforce_turnstile_rejects_invalid_token(monkeypatch):
    flags = SystemFeatureFlags(turnstile_enabled=True)
    settings = Settings(_env_file=None, turnstile_secret_key="secret", turnstile_site_key="site")

    async def fake_verify(*args, **kwargs):
        return False

    monkeypatch.setattr(turnstile_service, "verify_turnstile_token", fake_verify)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(enforce_turnstile(flags, settings, "token", "127.0.0.1"))
    assert exc.value.status_code == 403


def test_enforce_turnstile_passes_with_valid_token(monkeypatch):
    flags = SystemFeatureFlags(turnstile_enabled=True)
    settings = Settings(_env_file=None, turnstile_secret_key="secret", turnstile_site_key="site")

    async def fake_verify(*args, **kwargs):
        return True

    monkeypatch.setattr(turnstile_service, "verify_turnstile_token", fake_verify)
    asyncio.run(enforce_turnstile(flags, settings, "token", "127.0.0.1"))
