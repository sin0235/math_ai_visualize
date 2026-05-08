import json

import pytest

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.schemas.scene import AiModelInfo
from app.services.admin_settings import sync_ai_settings_to_registry
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
async def test_registry_db_overrides_env(db):
    settings = Settings(_env_file=None, router9_text_model="env/model")
    await load_model_registry(db, settings)
    await save_provider_config(db, "router9", "http://registry.local/v1", "db/model")

    effective = await resolve_effective_settings(db, None)

    assert effective.router9_base_url == "http://registry.local/v1"
    assert effective.router9_text_model == "db/model"


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
async def test_registry_ocr_profile_updates_openrouter_vision_model(db):
    await load_model_registry(db, Settings(_env_file=None, openrouter_vision_model="env/vision"))
    await save_task_profile(db, "ocr", "openrouter", "registry/vision", [])

    effective = await resolve_effective_settings(db, None)

    assert effective.openrouter_vision_model == "registry/vision"


@pytest.mark.anyio
async def test_registry_ocr_profile_updates_router9_ocr_model(db):
    await load_model_registry(db, Settings(_env_file=None, router9_ocr_model="env/ocr"))
    await save_task_profile(db, "ocr", "router9", "registry/ocr", [])

    effective = await resolve_effective_settings(db, None)

    assert effective.router9_ocr_model == "registry/ocr"


@pytest.mark.anyio
async def test_sync_ai_settings_persists_openai_compat_provider_config(db):
    await load_model_registry(db, Settings(_env_file=None))
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
