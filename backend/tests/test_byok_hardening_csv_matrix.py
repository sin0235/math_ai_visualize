from __future__ import annotations

import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, merge_runtime_settings
from app.repositories.user_ai_settings import UserAiModelRecord
from app.schemas.scene import RuntimeSettings
from app.schemas.user_settings import UserAiProviderUpdateRequest, UserAiTaskProfileSettings
from app.services.secret_crypto import api_key_last4, decrypt_user_secret, encrypt_user_secret, generate_user_secret_key
from app.services.ssrf import UnsafeUrlError, validate_openai_compat_base_url
from app.services.user_ai_settings import UserAiSettingsError, validate_task_profiles

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "byok_hardening_matrix_500.csv"
EXPECTED_RECORD_COUNT = 500


def load_rows(category: str | None = None) -> list[dict[str, str]]:
    with FIXTURE_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if category is not None:
        return [row for row in rows if row["category"] == category]
    return rows


def settings_for_environment(environment: str) -> Settings:
    data = {"_env_file": None, "environment": environment}
    if environment == "production":
        data.update({"session_cookie_secure": True, "allow_missing_origin_for_cookie_mutations": False})
    return Settings(**data)


def truthy(value: str) -> bool:
    return value.lower() in {"1", "true", "yes"}


def test_byok_hardening_fixture_has_exactly_500_records() -> None:
    rows = load_rows()

    assert len(rows) == EXPECTED_RECORD_COUNT
    assert len({row["case_id"] for row in rows}) == EXPECTED_RECORD_COUNT
    assert {row["category"] for row in rows} == {
        "provider_schema",
        "runtime_settings",
        "secret_crypto",
        "ssrf",
        "task_profile",
    }


@pytest.mark.parametrize("row", load_rows("ssrf"), ids=lambda row: row["case_id"])
def test_csv_ssrf_base_url_matrix(row: dict[str, str]) -> None:
    settings = settings_for_environment(row["environment"])

    if row["expected"] == "allow":
        normalized = validate_openai_compat_base_url(row["input_url"], settings, resolve_dns=False)
        assert normalized == row["expected_value"]
    else:
        with pytest.raises(UnsafeUrlError):
            validate_openai_compat_base_url(row["input_url"], settings, resolve_dns=False)


@pytest.mark.parametrize("row", load_rows("runtime_settings"), ids=lambda row: row["case_id"])
def test_csv_runtime_settings_do_not_accept_or_apply_user_secrets(row: dict[str, str]) -> None:
    provider = row["provider"]
    provider_payload = {"model": row["model_id"]}
    runtime = RuntimeSettings.model_validate({"default_provider": provider, provider: provider_payload})
    settings = Settings(
        _env_file=None,
        openrouter_api_key="sk-env-openrouter",
        openrouter_base_url="https://openrouter.example/v1",
        nvidia_api_key="sk-env-nvidia",
        nvidia_base_url="https://nvidia.example/v1",
        ollama_api_key="sk-env-ollama",
        ollama_base_url="https://ollama.example/v1",
        openai_compat_api_key="sk-env-openai-compat",
        openai_compat_base_url="https://compat.example/v1",
        router9_api_key="sk-env-router9",
        router9_base_url="https://router9.example/v1",
    )

    merged = merge_runtime_settings(settings, runtime)

    assert getattr(merged, f"{provider}_base_url") == getattr(settings, f"{provider}_base_url")
    assert getattr(merged, f"{provider}_api_key") == getattr(settings, f"{provider}_api_key")
    model_key = "router9_text_model" if provider == "router9" else f"{provider}_text_model"
    assert getattr(merged, model_key) == row["model_id"]

    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate({"default_provider": provider, provider: {"model": row["model_id"], "api_key": row["api_key"], "base_url": row["input_url"]}})


@pytest.mark.parametrize("row", load_rows("secret_crypto"), ids=lambda row: row["case_id"])
def test_csv_secret_crypto_roundtrips_without_plaintext_leak(row: dict[str, str]) -> None:
    key = generate_user_secret_key()
    plaintext = row["api_key"].strip()

    ciphertext = encrypt_user_secret(row["api_key"], key)

    assert ciphertext != plaintext
    assert plaintext not in ciphertext
    assert decrypt_user_secret(ciphertext, key) == plaintext
    assert api_key_last4(row["api_key"]) == row["expected_value"]


@pytest.mark.parametrize("row", load_rows("task_profile"), ids=lambda row: row["case_id"])
def test_csv_task_profile_model_validation_matrix(row: dict[str, str]) -> None:
    stored_model_id = row["provider"]
    profile_model_id = row["model_id"]
    models = [
        UserAiModelRecord(
            id=f"id-{row['case_id']}",
            user_id="user-csv",
            model_id=stored_model_id,
            label=stored_model_id,
            supports_vision=truthy(row["supports_vision"]),
            enabled=truthy(row["enabled"]),
        )
    ]
    profiles = [UserAiTaskProfileSettings(task=row["task"], model_id=profile_model_id, enabled=True)]

    if row["expected"] == "allow":
        validate_task_profiles(models, profiles)
    else:
        with pytest.raises(UserAiSettingsError):
            validate_task_profiles(models, profiles)


@pytest.mark.parametrize("row", load_rows("provider_schema"), ids=lambda row: row["case_id"])
def test_csv_user_provider_update_schema_matrix(row: dict[str, str]) -> None:
    payload = {"enabled": False, "base_url": row["input_url"], "api_key": row["api_key"]}
    if row["expected"] == "reject_extra":
        payload["unexpected"] = "blocked"

    if row["expected"].startswith("reject"):
        with pytest.raises(ValidationError):
            UserAiProviderUpdateRequest.model_validate(payload)
        return

    request = UserAiProviderUpdateRequest.model_validate(payload)
    assert request.base_url == row["expected_value"]
    if row["expected"] == "allow_empty_key":
        assert request.api_key is None
    else:
        assert request.api_key == row["api_key"].strip()
