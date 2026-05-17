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
    resolve_task_profile,
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
async def test_registry_model_overrides_env_without_dropping_env_api_key(db, monkeypatch):
    settings = Settings(_env_file=None, openrouter_api_key="env-secret", openrouter_base_url="https://env-openrouter.example/v1", openrouter_text_model="env/model")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openrouter", "https://registry-openrouter.example/v1", "registry/model", api_key_configured=True)

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_api_key == "env-secret"
    assert effective.openrouter_base_url == "https://registry-openrouter.example/v1"
    assert effective.openrouter_text_model == "registry/model"


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
async def test_registry_disables_stale_scanned_models_after_rescan(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)

    await upsert_scanned_models(db, "router9", [
        AiModelInfo(id="stale-model", label="Stale", provider="router9"),
        AiModelInfo(id="fresh-model", label="Fresh", provider="router9"),
    ])
    await set_allowed_models(db, "router9", ["stale-model", "fresh-model"])
    await upsert_scanned_models(db, "router9", [
        AiModelInfo(id="fresh-model", label="Fresh", provider="router9"),
    ])

    registry = await load_model_registry(db, settings)
    stale = next(model for model in registry.models["router9"] if model.id == "stale-model")

    assert stale.enabled is False
    assert stale.allowed is False
    assert registry.allowed_model_ids("router9") == ["fresh-model"]
    assert [model.id for model in registry.scanned_model_infos("router9")] == ["fresh-model"]


@pytest.mark.anyio
async def test_registry_reenables_scanned_model_when_it_reappears(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)

    await upsert_scanned_models(db, "router9", [AiModelInfo(id="model-a", label="Model A", provider="router9")])
    await upsert_scanned_models(db, "router9", [])
    await upsert_scanned_models(db, "router9", [AiModelInfo(id="model-a", label="Model A", provider="router9")])

    registry = await load_model_registry(db, settings)

    assert registry.scanned_model_infos("router9")[0].id == "model-a"
    assert registry.models["router9"][0].enabled is True


@pytest.mark.anyio
async def test_registry_uses_allowed_default_for_openrouter_when_saved_default_is_disallowed(db, monkeypatch):
    settings = Settings(_env_file=None, openrouter_text_model="env/openrouter")
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openrouter", "https://openrouter.example/v1", "stale/model")
    await set_allowed_models(db, "openrouter", ["allowed/model"])

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_text_model == "allowed/model"


@pytest.mark.anyio
async def test_explicit_provider_without_model_uses_that_provider_default(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)
    await save_provider_config(db, "openrouter", "https://openrouter.example/v1", "openrouter/model")
    await save_provider_config(db, "openai_compat", "https://compat.example/v1", "compat/default")
    await save_task_profile(db, "render", "openrouter", "openrouter/model", [])

    registry = await load_model_registry(db, settings)
    profile = resolve_task_profile(registry, "render", preferred_provider="openai_compat")

    assert profile is not None
    assert profile.provider_id == "openai_compat"
    assert profile.model_id == "compat/default"


@pytest.mark.anyio
async def test_save_task_profile_rejects_provider_model_mismatch(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)

    with pytest.raises(ValueError, match="thuộc provider openrouter"):
        await save_task_profile(db, "ocr", "router9", "openrouter/google/gemma-4-26b-a4b-it:free", [])


@pytest.mark.anyio
async def test_load_model_registry_canonicalizes_legacy_profile_mismatch(db):
    settings = Settings(_env_file=None)
    await load_model_registry(db, settings)
    await save_provider_config(db, "router9", "https://router9.example/v1", "gh/gpt-5.2")
    await save_provider_config(db, "openrouter", "https://openrouter.example/v1", "openrouter/google/gemma-4-26b-a4b-it:free")
    await db.execute(
        """
        INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(task) DO UPDATE SET provider_id = excluded.provider_id, model_id = excluded.model_id, fallbacks_json = excluded.fallbacks_json
        """,
        ["ocr", "router9", "openrouter/google/gemma-4-26b-a4b-it:free", json.dumps(["openrouter/google/gemma-4-31b-it:free", "cc/codex-5.5-image"])],
    )

    registry = await load_model_registry(db, settings)
    profile = resolve_task_profile(registry, "ocr")
    row = await db.fetch_one("SELECT provider_id, model_id, fallbacks_json FROM ai_task_profiles WHERE task = ?", ["ocr"])

    assert profile is not None
    assert profile.provider_id == "openrouter"
    assert profile.model_id == "google/gemma-4-26b-a4b-it:free"
    assert row["provider_id"] == "openrouter"
    assert row["model_id"] == "google/gemma-4-26b-a4b-it:free"
    assert json.loads(row["fallbacks_json"]) == ["google/gemma-4-31b-it:free", "cc/codex-5.5-image"]


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


def test_validate_system_setting_removes_non_router9_only_mode():
    from app.api.routes_admin import validate_system_setting

    validated = validate_system_setting("ai_settings", {
        "version": 1,
        "openrouter": {"only_mode": False, "model": "openrouter/model"},
        "openai_compat": {"only_mode": False, "model": "compat/model"},
        "router9": {"only_mode": True, "model": "gh/gpt-5.2"},
    })

    assert "only_mode" not in validated["openrouter"]
    assert "only_mode" not in validated["openai_compat"]
    assert validated["router9"]["only_mode"] is True


def test_validate_system_setting_rejects_mismatched_provider_model():
    from fastapi import HTTPException
    from app.api.routes_admin import validate_system_setting

    with pytest.raises(HTTPException) as error:
        validate_system_setting("ai_profiles", {
            "version": 1,
            "ocr": {"provider": "router9", "model": "openrouter/google/gemma-4-26b-it:free"},
        })

    assert error.value.status_code == 422
    assert "thuộc provider openrouter" in str(error.value.detail)


@pytest.mark.anyio
async def test_sync_ai_settings_accepts_scanned_model_capabilities(db):
    await load_model_registry(db, Settings(_env_file=None))

    await sync_ai_settings_to_registry(db, {
        "version": 1,
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "vision/model",
            "scanned_models": [{
                "id": "vision/model",
                "label": "Vision model",
                "provider": "openrouter",
                "capabilities": {"input_modalities": ["text", "image"]},
            }],
            "allowed_model_ids": ["vision/model"],
        },
    })

    registry = await load_model_registry(db, Settings(_env_file=None))
    model = next(model for model in registry.models["openrouter"] if model.id == "vision/model")

    assert model.capabilities == {"input_modalities": ["text", "image"]}


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
async def test_openrouter_scan_accepts_vendor_namespaced_models(db):
    await load_model_registry(db, Settings(_env_file=None))

    await upsert_scanned_models(db, "openrouter", [
        AiModelInfo(id="nvidia/llama-3.3-nemotron-super-49b-v1.5", label="Nemotron", provider="openrouter"),
    ])

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert any(model.id == "nvidia/llama-3.3-nemotron-super-49b-v1.5" for model in registry.models["openrouter"])


@pytest.mark.anyio
async def test_scanned_model_capabilities_round_trip(db):
    await load_model_registry(db, Settings(_env_file=None))
    await upsert_scanned_models(db, "openrouter", [
        AiModelInfo(
            id="openrouter/vision-model",
            label="Vision Model",
            provider="openrouter",
            context_length=128000,
            capabilities={"input_modalities": ["text", "image"], "supported_parameters": ["temperature"]},
        )
    ])
    await set_allowed_models(db, "openrouter", ["vision-model"])
    await upsert_scanned_models(db, "openrouter", [
        AiModelInfo(
            id="openrouter/vision-model",
            label="Vision Model Updated",
            provider="openrouter",
            context_length=128000,
            capabilities={"input_modalities": ["text", "image"], "supported_parameters": ["temperature", "tools"]},
        )
    ])

    registry = await load_model_registry(db, Settings(_env_file=None))
    model = next(model for model in registry.models["openrouter"] if model.id == "vision-model")
    scanned = next(model for model in registry.scanned_model_infos("openrouter") if model.id == "vision-model")

    assert model.allowed is True
    assert model.capabilities == {"input_modalities": ["text", "image"], "supported_parameters": ["temperature", "tools"]}
    assert scanned.capabilities == model.capabilities


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
async def test_sync_ai_settings_persists_ocr_profile_without_name_error(db, monkeypatch):
    settings = Settings(_env_file=None)
    monkeypatch.setattr("app.services.admin_settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    await load_model_registry(db, settings)

    await sync_ai_settings_to_registry(db, {
        "version": 1,
        "ocr": {
            "provider": "nvidia",
            "model": "nvidia/vision",
            "max_image_mb": 7,
        },
    })

    registry = await load_model_registry(db, settings)

    assert registry.settings["ocr_max_image_mb"] == 7
    assert registry.task_profiles["ocr"].provider_id == "nvidia"
    assert registry.task_profiles["ocr"].model_id == "nvidia/vision"


@pytest.mark.anyio
async def test_ai_profiles_auto_provider_accepts_cross_provider_fallbacks(db):
    await load_model_registry(db, Settings(_env_file=None))

    await sync_ai_profiles_to_registry(db, {
        "version": 1,
        "geometry_reasoning": {"provider": "auto", "model": "", "fallbacks": ["openai/gpt-oss-120b:free"]},
    }, {
        "geometry_reasoning": {"provider": "auto", "model": "", "fallbacks": ["openai/gpt-oss-120b:free"]},
    })

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.task_profiles["render"].provider_id == "auto"
    assert registry.task_profiles["render"].fallbacks == ["openai/gpt-oss-120b:free"]


@pytest.mark.anyio
async def test_ai_profiles_sync_to_registry_task_profiles(db):
    await load_model_registry(db, Settings(_env_file=None))

    await sync_ai_profiles_to_registry(db, {
        "version": 1,
        "geometry_reasoning": {"provider": "openrouter", "model": "openrouter/geometry", "fallbacks": ["openrouter/fallback", "router9/fallback"]},
        "solver_explanation": {"provider": "router9", "model": "router9/solver", "fallbacks": ["router9/fallback", "openrouter/fallback"]},
    }, {
        "geometry_reasoning": {"provider": "openrouter", "model": "openrouter/geometry", "fallbacks": ["openrouter/fallback", "router9/fallback"]},
        "solver_explanation": {"provider": "router9", "model": "router9/solver", "fallbacks": ["router9/fallback", "openrouter/fallback"]},
    })

    registry = await load_model_registry(db, Settings(_env_file=None))

    assert registry.task_profiles["render"].provider_id == "openrouter"
    assert registry.task_profiles["render"].model_id == "geometry"
    assert registry.task_profiles["reasoning"].fallbacks == ["fallback", "router9/fallback"]
    assert registry.task_profiles["solver_explanation"].provider_id == "router9"
    assert registry.task_profiles["solver_explanation"].model_id == "solver"
    assert registry.task_profiles["solver_explanation"].fallbacks == ["fallback", "openrouter/fallback"]


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
