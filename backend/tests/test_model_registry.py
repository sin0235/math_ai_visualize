import json

import pytest

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.schemas.scene import AiModelInfo
from app.services.admin_settings import sync_ai_profiles_to_registry, sync_ai_settings_to_registry
from app.services.model_registry import (
    load_model_registry,
    resolve_effective_settings,
    save_provider_config,
    save_task_profile,
    set_allowed_models,
    upsert_scanned_models,
)


@pytest.fixture
async def db(tmp_path):
    client = SQLiteClient(str(tmp_path / "test.db"))
    await apply_sqlite_migrations(client)
    return client


@pytest.mark.anyio
async def test_registry_seeds_from_env(db):
    settings = Settings(_env_file=None, router9_text_model="router/model", router9_allowed_models=["router/model"])

    registry = await load_model_registry(db, settings)

    assert registry.providers["router9"].default_model_id == "router/model"
    assert registry.allowed_model_ids("router9") == ["router/model"]


@pytest.mark.anyio
async def test_registry_seeds_router9_ocr_profile_from_env(db):
    settings = Settings(_env_file=None, router9_ocr_model="cx/gpt-5.2")

    registry = await load_model_registry(db, settings)

    assert registry.task_profiles["ocr"].provider_id == "router9"
    assert registry.task_profiles["ocr"].model_id == "cx/gpt-5.2"


@pytest.mark.anyio
async def test_registry_db_overrides_env(db, monkeypatch):
    settings = Settings(_env_file=None, router9_text_model="env/model")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "router9", "http://registry.local/v1", "db/model")

    effective = await resolve_effective_settings(db, None)

    assert effective.router9_base_url == "http://registry.local/v1"
    assert effective.router9_text_model == "db/model"


@pytest.mark.anyio
async def test_ollama_registry_db_overrides_env(db, monkeypatch):
    settings = Settings(_env_file=None, ollama_base_url="http://env-ollama.local", ollama_text_model="env-ollama")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "ollama", "http://db-ollama.local", "db-ollama")

    effective = await resolve_effective_settings(db, None)

    assert effective.ollama_base_url == "http://db-ollama.local"
    assert effective.ollama_text_model == "db-ollama"


@pytest.mark.anyio
async def test_registry_preserves_allowed_models_after_scan(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)
    await set_allowed_models(db, "router9", ["model-a"])

    await upsert_scanned_models(db, "router9", [
        AiModelInfo(id="model-a", label="Model A", provider="router9"),
        AiModelInfo(id="model-b", label="Model B", provider="router9"),
    ])
    registry = await load_model_registry(db, settings)

    assert registry.allowed_model_ids("router9") == ["model-a"]
    assert {model.id for model in registry.models["router9"]} >= {"model-a", "model-b"}


@pytest.mark.anyio
async def test_registry_uses_allowed_default_for_openrouter_when_saved_default_is_disallowed(db, monkeypatch):
    settings = Settings(_env_file=None, openrouter_text_model="env/openrouter")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openrouter", "https://openrouter.example/v1", "stale/model")
    await set_allowed_models(db, "openrouter", ["allowed/model"])

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_text_model == "allowed/model"


def test_validate_system_setting_normalizes_default_to_allowlist():
    from app.api.routes_admin import validate_system_setting

    validated = validate_system_setting("ai_settings", {
        "version": 1,
        "openai_compat": {
            "base_url": "https://deepseek-reverse-api.sin-studio.tech/v1",
            "model": "stale-model",
            "allowed_model_ids": ["deepseek-v4-flash"],
        },
    })

    assert validated["openai_compat"]["model"] == "deepseek-v4-flash"


@pytest.mark.anyio
async def test_sync_ai_settings_normalizes_nvidia_default_to_allowlist(db):
    await load_model_registry(db, Settings(_env_file=None))

    await sync_ai_settings_to_registry(db, {
        "version": 1,
        "default_provider": "nvidia",
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "stale-nvidia-model",
            "scanned_models": [{"id": "allowed-nvidia-model", "label": "Allowed NVIDIA", "provider": "nvidia"}],
            "allowed_model_ids": ["allowed-nvidia-model"],
        },
    })

    effective = await resolve_effective_settings(db, None)
    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.providers["nvidia"].default_model_id == "allowed-nvidia-model"
    assert effective.nvidia_text_model == "allowed-nvidia-model"


@pytest.mark.anyio
async def test_sync_ai_settings_patch_only_updates_touched_provider(db):
    await load_model_registry(db, Settings(_env_file=None))
    await save_provider_config(db, "openrouter", "https://old-openrouter.example/v1", "old/openrouter")
    await save_provider_config(db, "nvidia", "https://old-nvidia.example/v1", "old-nvidia")

    await sync_ai_settings_to_registry(db, {
        "version": 1,
        "openrouter": {
            "base_url": "https://new-openrouter.example/v1",
            "model": "new/openrouter",
            "scanned_models": [{"id": "new/openrouter", "label": "New OpenRouter", "provider": "openrouter"}],
            "allowed_model_ids": ["new/openrouter"],
        },
        "nvidia": {
            "base_url": "https://new-nvidia.example/v1",
            "model": "new-nvidia",
            "scanned_models": [{"id": "new-nvidia", "label": "New NVIDIA", "provider": "nvidia"}],
            "allowed_model_ids": ["new-nvidia"],
        },
    }, {"openrouter": {"model": "new/openrouter"}})

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.providers["openrouter"].default_model_id == "new/openrouter"
    assert registry.providers["nvidia"].default_model_id == "old-nvidia"


@pytest.mark.anyio
async def test_registry_ocr_profile_updates_openrouter_vision_model(db):
    await load_model_registry(db, Settings(_env_file=None, openrouter_vision_model="env/vision"))
    await save_task_profile(db, "ocr", "openrouter", "registry/vision", [])

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_vision_model == "registry/vision"


@pytest.mark.anyio
async def test_empty_ocr_profile_keeps_vision_defaults(db, monkeypatch):
    settings = Settings(_env_file=None, openrouter_text_model="admin/text", openrouter_vision_model="env/vision")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openrouter", "https://openrouter.example/v1", "admin/text")
    await save_task_profile(db, "ocr", "openrouter", "", [])

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_text_model == "admin/text"
    assert effective.openrouter_vision_model == "env/vision"


@pytest.mark.anyio
async def test_registry_ocr_profile_updates_router9_ocr_model(db):
    await load_model_registry(db, Settings(_env_file=None, router9_ocr_model="env/ocr"))
    await save_task_profile(db, "ocr", "router9", "registry/ocr", [])

    effective = await resolve_effective_settings(db, None)

    assert effective.router9_ocr_model == "registry/ocr"


@pytest.mark.anyio
async def test_admin_ai_settings_api_key_is_not_active_after_registry_seed(db, monkeypatch):
    settings = Settings(_env_file=None, ollama_api_key="env-ollama-key")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({"version": 1, "ollama": {"api_key": "db-ollama-key"}})],
    )

    effective = await resolve_effective_settings(db, None)

    assert effective.ollama_api_key == "env-ollama-key"


@pytest.mark.anyio
async def test_empty_admin_ai_settings_fall_back_to_env(db, monkeypatch):
    settings = Settings(_env_file=None, ollama_base_url="http://env-ollama.local", ollama_text_model="env-ollama")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({"version": 1, "ollama": {"api_key": "", "base_url": "", "model": ""}})],
    )

    effective = await resolve_effective_settings(db, None)

    assert effective.ollama_base_url == "http://env-ollama.local"
    assert effective.ollama_text_model == "env-ollama"


@pytest.mark.anyio
async def test_env_secret_keeps_env_openai_compat_connection_when_registry_has_stale_defaults(db, monkeypatch):
    settings = Settings(
        _env_file=None,
        openai_compat_api_key="env-secret",
        openai_compat_base_url="https://env-openai-compatible.example/v1",
        openai_compat_text_model="",
    )
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openai_compat", "http://localhost:8080/v1", "", api_key_configured=False)

    effective = await resolve_effective_settings(db, None)

    assert effective.openai_compat_api_key == "env-secret"
    assert effective.openai_compat_base_url == "https://env-openai-compatible.example/v1"
    assert effective.openai_compat_text_model == ""


@pytest.mark.anyio
async def test_sync_ai_settings_persists_openai_compat_provider_config(db, monkeypatch):
    settings = Settings(_env_file=None, openai_compat_api_key="env-secret")
    monkeypatch.setattr("app.services.admin_settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await sync_ai_settings_to_registry(db, {
        "version": 1,
        "default_provider": "openai_compat",
        "openai_compat": {
            "base_url": "https://deepseek-reverse-api.sin-studio.tech/v1",
            "model": "deepseek-chat",
            "scanned_models": [{"id": "deepseek-chat", "label": "deepseek-chat", "provider": "openai_compat"}],
            "allowed_model_ids": ["deepseek-chat"],
            "last_scanned_at": "2026-05-08T00:00:00.000Z",
        },
    })

    effective = await resolve_effective_settings(db, None)
    registry = await load_model_registry(db, Settings(_env_file=None))

    assert effective.ai_provider == "openai_compat"
    assert effective.openai_compat_base_url == "https://deepseek-reverse-api.sin-studio.tech/v1"
    assert effective.openai_compat_text_model == "deepseek-chat"
    assert registry.allowed_model_ids("openai_compat") == ["deepseek-chat"]
    assert registry.scanned_model_infos("openai_compat")[0].id == "deepseek-chat"


@pytest.mark.anyio
async def test_ai_profiles_sync_to_registry_task_profiles(db):
    await load_model_registry(db, Settings(_env_file=None))

    await sync_ai_profiles_to_registry(db, {
        "version": 1,
        "geometry_reasoning": {"provider": "openrouter", "model": "openrouter/geometry", "fallbacks": ["openrouter/fallback"]},
        "solver_explanation": {"provider": "router9", "model": "router9/solver", "fallbacks": ["router9/fallback"]},
    }, {
        "geometry_reasoning": {"provider": "openrouter", "model": "openrouter/geometry", "fallbacks": ["openrouter/fallback"]},
        "solver_explanation": {"provider": "router9", "model": "router9/solver", "fallbacks": ["router9/fallback"]},
    })

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.task_profiles["render"].provider_id == "openrouter"
    assert registry.task_profiles["render"].model_id == "openrouter/geometry"
    assert registry.task_profiles["reasoning"].fallbacks == ["openrouter/fallback"]
    assert registry.task_profiles["solver_explanation"].provider_id == "router9"
    assert registry.task_profiles["solver_explanation"].model_id == "router9/solver"


@pytest.mark.anyio
async def test_registry_imports_legacy_ai_settings(db):
    await db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({
            "version": 1,
            "default_provider": "router9",
            "router9": {
                "base_url": "http://legacy.local/v1",
                "model": "legacy/model",
                "allowed_model_ids": ["legacy/model"],
                "only_mode": True,
            },
        })],
    )

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.providers["router9"].base_url == "http://legacy.local/v1"
    assert registry.providers["router9"].default_model_id == "legacy/model"
    assert registry.settings["router9_only"] is True
    assert registry.allowed_model_ids("router9") == ["legacy/model"]
