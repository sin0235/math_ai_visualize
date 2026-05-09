from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings, merge_runtime_settings
from app.db.session import DatabaseClient
from app.schemas.auth import SystemAiSettings
from app.schemas.scene import AiModelInfo, RuntimeSettings

PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "nvidia": "NVIDIA",
    "ollama": "Ollama",
    "openai_compat": "OpenAI-compatible",
    "router9": "9router",
}


@dataclass(frozen=True)
class ProviderRegistryItem:
    id: str
    label: str
    base_url: str
    default_model_id: str
    api_key_configured: bool
    enabled: bool = True
    last_checked_at: str | None = None
    last_check_status: str | None = None
    last_check_message: str | None = None


@dataclass(frozen=True)
class ModelRegistryItem:
    provider_id: str
    id: str
    label: str
    owned_by: str | None = None
    context_length: int | None = None
    enabled: bool = True
    allowed: bool = False
    source: str = "scan"
    last_seen_at: str | None = None


@dataclass(frozen=True)
class TaskProfile:
    task: str
    provider_id: str
    model_id: str
    fallbacks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModelRegistry:
    providers: dict[str, ProviderRegistryItem]
    models: dict[str, list[ModelRegistryItem]]
    task_profiles: dict[str, TaskProfile]
    settings: dict[str, Any]
    legacy_used: bool = False

    def allowed_model_ids(self, provider_id: str) -> list[str]:
        return [model.id for model in self.models.get(provider_id, []) if model.allowed and model.enabled]

    def scanned_model_infos(self, provider_id: str) -> list[AiModelInfo]:
        return [
            AiModelInfo(id=model.id, label=model.label, provider=provider_id, owned_by=model.owned_by, context_length=model.context_length)
            for model in self.models.get(provider_id, [])
        ]


async def load_model_registry(db: DatabaseClient, settings: Settings | None = None) -> ModelRegistry:
    settings = settings or get_settings()
    try:
        await seed_model_registry(db, settings)
        provider_rows = await db.fetch_all("SELECT * FROM ai_providers ORDER BY id")
    except RuntimeError as error:
        if "no such table" not in str(error).lower():
            raise
        return registry_from_settings(settings)
    model_rows = await db.fetch_all("SELECT * FROM ai_models ORDER BY provider_id, label COLLATE NOCASE, id COLLATE NOCASE")
    profile_rows = await db.fetch_all("SELECT * FROM ai_task_profiles ORDER BY task")
    setting_rows = await db.fetch_all("SELECT key, value_json FROM ai_model_settings")

    providers = {
        str(row["id"]): ProviderRegistryItem(
            id=str(row["id"]),
            label=str(row["label"]),
            base_url=str(row["base_url"] or ""),
            default_model_id=str(row["default_model_id"] or ""),
            api_key_configured=bool(row["api_key_configured"]),
            enabled=bool(row["enabled"]),
            last_checked_at=row.get("last_checked_at"),
            last_check_status=row.get("last_check_status"),
            last_check_message=row.get("last_check_message"),
        )
        for row in provider_rows
    }
    models: dict[str, list[ModelRegistryItem]] = {provider_id: [] for provider_id in providers}
    for row in model_rows:
        provider_id = str(row["provider_id"])
        models.setdefault(provider_id, []).append(ModelRegistryItem(
            provider_id=provider_id,
            id=str(row["id"]),
            label=str(row["label"] or row["id"]),
            owned_by=row.get("owned_by"),
            context_length=int(row["context_length"]) if row.get("context_length") is not None else None,
            enabled=bool(row["enabled"]),
            allowed=bool(row["allowed"]),
            source=str(row["source"] or "scan"),
            last_seen_at=row.get("last_seen_at"),
        ))
    profiles = {
        str(row["task"]): TaskProfile(
            task=str(row["task"]),
            provider_id=str(row["provider_id"] or "auto"),
            model_id=str(row["model_id"] or ""),
            fallbacks=_json_list(row.get("fallbacks_json")),
        )
        for row in profile_rows
    }
    registry_settings = {str(row["key"]): _json_value(row["value_json"]) for row in setting_rows}
    return ModelRegistry(providers=providers, models=models, task_profiles=profiles, settings=registry_settings, legacy_used=await _has_legacy_ai_settings(db))


async def seed_model_registry(db: DatabaseClient, settings: Settings) -> None:
    existing = await db.fetch_one("SELECT 1 FROM ai_providers LIMIT 1")
    if existing is not None:
        profile = await db.fetch_one("SELECT 1 FROM ai_task_profiles WHERE task = ?", ["solver_explanation"])
        if profile is None:
            await save_task_profile(db, "solver_explanation", settings.ai_provider, "", [])
        return
    legacy = await load_legacy_ai_settings(db)
    provider_data = _provider_seed_data(settings, legacy)
    for provider_id, data in provider_data.items():
        await db.execute(
            """
            INSERT OR REPLACE INTO ai_providers (id, label, base_url, default_model_id, api_key_configured, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            [provider_id, PROVIDER_LABELS[provider_id], data["base_url"], data["model"], int(data["api_key_configured"])],
        )
        for model in data["models"]:
            await upsert_model(db, provider_id, model, allowed=model.id in data["allowed_model_ids"], source="legacy" if legacy else "env")
    router9_only = legacy.router9.only_mode if legacy else settings.router9_only
    openrouter_reasoning = legacy.openrouter_reasoning_enabled if legacy else settings.openrouter_reasoning_enabled
    ocr_max = legacy.ocr.max_image_mb if legacy else 5
    default_provider = legacy.default_provider if legacy else settings.ai_provider
    await set_model_setting(db, "router9_only", router9_only)
    await set_model_setting(db, "openrouter_reasoning_enabled", openrouter_reasoning)
    await set_model_setting(db, "ocr_max_image_mb", ocr_max)
    await set_model_setting(db, "default_provider", default_provider)
    ocr_provider = legacy.ocr.provider if legacy else "openrouter"
    ocr_model = legacy.ocr.model if legacy else (settings.router9_ocr_model or settings.openrouter_vision_model)
    await save_task_profile(db, "render", default_provider, "", [])
    await save_task_profile(db, "reasoning", default_provider, "", [])
    await save_task_profile(db, "solver_explanation", default_provider, "", [])
    await save_task_profile(db, "ocr", ocr_provider, ocr_model or "", [])


async def load_legacy_ai_settings(db: DatabaseClient) -> SystemAiSettings | None:
    row = await db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", ["ai_settings"])
    if row is None:
        return None
    try:
        value = json.loads(str(row["value_json"]))
        if not isinstance(value, dict):
            return None
        return SystemAiSettings.model_validate(value)
    except (json.JSONDecodeError, ValidationError):
        return None


async def resolve_effective_settings(db: DatabaseClient | None, runtime_settings: RuntimeSettings | None = None) -> Settings:
    settings = get_settings()
    if db is not None:
        registry = await load_model_registry(db, settings)
        settings = settings_from_registry(settings, registry)
        settings = settings_from_admin_ai_settings(settings, await load_legacy_ai_settings(db), registry)
    return merge_runtime_settings(settings, runtime_settings)


def _has_runtime_secret_override(runtime_settings: RuntimeSettings | None) -> bool:
    if runtime_settings is None:
        return False
    return any(
        provider is not None and bool((provider.api_key or "").strip())
        for provider in (runtime_settings.openrouter, runtime_settings.nvidia, runtime_settings.ollama, runtime_settings.openai_compat, runtime_settings.router9)
    )


def settings_from_admin_ai_settings(settings: Settings, admin_settings: SystemAiSettings | None, registry: ModelRegistry) -> Settings:
    if admin_settings is None:
        return settings
    data = settings.model_dump()
    for provider_id in ("openrouter", "nvidia", "ollama", "openai_compat", "router9"):
        provider_settings = getattr(admin_settings, provider_id)
        registry_provider = registry.providers.get(provider_id)
        db_base_url = (provider_settings.base_url or "").strip()
        db_model = (provider_settings.model or "").strip()
        db_api_key = (getattr(provider_settings, "api_key", "") or "").strip()
        if db_base_url and not (registry_provider and registry_provider.base_url):
            data[f"{provider_id}_base_url"] = db_base_url
        if db_model and not (registry_provider and registry_provider.default_model_id):
            key = "router9_text_model" if provider_id == "router9" else f"{provider_id}_text_model"
            data[key] = db_model
        if db_api_key:
            data[f"{provider_id}_api_key"] = db_api_key
    return Settings.model_validate(data)



def settings_from_registry(settings: Settings, registry: ModelRegistry) -> Settings:
    data = settings.model_dump()
    default_provider = registry.settings.get("default_provider")
    if isinstance(default_provider, str) and default_provider:
        data["ai_provider"] = default_provider
    for provider_id, provider in registry.providers.items():
        if provider.base_url:
            data[f"{provider_id}_base_url"] = provider.base_url
        if provider.default_model_id:
            key = "router9_text_model" if provider_id == "router9" else f"{provider_id}_text_model"
            data[key] = provider.default_model_id
    data["router9_only"] = bool(registry.settings.get("router9_only", settings.router9_only))
    data["openrouter_reasoning_enabled"] = bool(registry.settings.get("openrouter_reasoning_enabled", settings.openrouter_reasoning_enabled))
    router9_allowed = registry.allowed_model_ids("router9")
    if router9_allowed:
        data["router9_allowed_models"] = router9_allowed
    ocr_profile = registry.task_profiles.get("ocr")
    if ocr_profile and ocr_profile.model_id:
        if ocr_profile.provider_id == "router9":
            data["router9_ocr_model"] = ocr_profile.model_id
        elif ocr_profile.provider_id == "openrouter":
            data["openrouter_vision_model"] = ocr_profile.model_id
    return Settings.model_validate(data)


async def upsert_scanned_models(db: DatabaseClient, provider_id: str, models: list[AiModelInfo]) -> None:
    existing_allowed = {
        str(row["id"])
        for row in await db.fetch_all("SELECT id FROM ai_models WHERE provider_id = ? AND allowed = 1", [provider_id])
    }
    await ensure_provider(db, provider_id)
    for model in models:
        await upsert_model(db, provider_id, model, allowed=model.id in existing_allowed, source="scan")


async def upsert_model(db: DatabaseClient, provider_id: str, model: AiModelInfo, allowed: bool, source: str) -> None:
    await db.execute(
        """
        INSERT INTO ai_models (provider_id, id, label, owned_by, context_length, source, enabled, allowed, last_seen_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(provider_id, id) DO UPDATE SET
          label = excluded.label,
          owned_by = excluded.owned_by,
          context_length = excluded.context_length,
          source = excluded.source,
          last_seen_at = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP
        """,
        [provider_id, model.id, model.label or model.id, model.owned_by, model.context_length, source, int(allowed)],
    )


async def set_allowed_models(db: DatabaseClient, provider_id: str, model_ids: list[str]) -> None:
    await ensure_provider(db, provider_id)
    await db.execute("UPDATE ai_models SET allowed = 0 WHERE provider_id = ?", [provider_id])
    for model_id in dict.fromkeys(model_ids):
        await db.execute(
            """
            INSERT INTO ai_models (provider_id, id, label, source, enabled, allowed, updated_at)
            VALUES (?, ?, ?, 'manual', 1, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(provider_id, id) DO UPDATE SET allowed = 1, enabled = 1, updated_at = CURRENT_TIMESTAMP
            """,
            [provider_id, model_id, model_id],
        )


async def save_provider_config(db: DatabaseClient, provider_id: str, base_url: str, default_model_id: str, enabled: bool = True) -> None:
    await db.execute(
        """
        INSERT INTO ai_providers (id, label, base_url, default_model_id, enabled, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          base_url = excluded.base_url,
          default_model_id = excluded.default_model_id,
          enabled = excluded.enabled,
          updated_at = CURRENT_TIMESTAMP
        """,
        [provider_id, PROVIDER_LABELS.get(provider_id, provider_id), base_url, default_model_id, int(enabled)],
    )


async def save_provider_check(db: DatabaseClient, provider_id: str, status: str, message: str) -> None:
    await ensure_provider(db, provider_id)
    await db.execute(
        "UPDATE ai_providers SET last_checked_at = CURRENT_TIMESTAMP, last_check_status = ?, last_check_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [status, message[:1000], provider_id],
    )


async def save_task_profile(db: DatabaseClient, task: str, provider_id: str, model_id: str, fallbacks: list[str]) -> None:
    await db.execute(
        """
        INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(task) DO UPDATE SET
          provider_id = excluded.provider_id,
          model_id = excluded.model_id,
          fallbacks_json = excluded.fallbacks_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        [task, provider_id, model_id, json.dumps(fallbacks)],
    )


async def set_model_setting(db: DatabaseClient, key: str, value: Any) -> None:
    await db.execute(
        """
        INSERT INTO ai_model_settings (key, value_json, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
        """,
        [key, json.dumps(value)],
    )


async def ensure_provider(db: DatabaseClient, provider_id: str) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO ai_providers (id, label) VALUES (?, ?)",
        [provider_id, PROVIDER_LABELS.get(provider_id, provider_id)],
    )


async def _has_legacy_ai_settings(db: DatabaseClient) -> bool:
    return await db.fetch_one("SELECT 1 FROM system_settings WHERE key = ?", ["ai_settings"]) is not None


def _provider_seed_data(settings: Settings, legacy: SystemAiSettings | None) -> dict[str, dict[str, Any]]:
    provider_settings = {
        "openrouter": legacy.openrouter if legacy else None,
        "nvidia": legacy.nvidia if legacy else None,
        "ollama": legacy.ollama if legacy else None,
        "openai_compat": None,
        "router9": legacy.router9 if legacy else None,
    }
    base = {
        "openrouter": {"base_url": settings.openrouter_base_url, "model": settings.openrouter_text_model, "api_key_configured": bool(settings.openrouter_api_key)},
        "nvidia": {"base_url": settings.nvidia_base_url, "model": settings.nvidia_text_model, "api_key_configured": bool(settings.nvidia_api_key)},
        "ollama": {"base_url": settings.ollama_base_url, "model": settings.ollama_text_model, "api_key_configured": bool(settings.ollama_api_key)},
        "openai_compat": {"base_url": settings.openai_compat_base_url, "model": settings.openai_compat_text_model, "api_key_configured": bool(settings.openai_compat_api_key)},
        "router9": {"base_url": settings.router9_base_url, "model": settings.router9_text_model or "", "api_key_configured": bool(settings.router9_api_key)},
    }
    for provider_id, item in base.items():
        configured = provider_settings[provider_id]
        scanned = []
        allowed = []
        if configured is not None:
            item["base_url"] = configured.base_url or item["base_url"]
            item["model"] = configured.model or item["model"]
            scanned = configured.scanned_models
            allowed = configured.allowed_model_ids
        elif provider_id == "router9":
            allowed = settings.router9_allowed_models
        models = [AiModelInfo(id=item["model"], label=item["model"], provider=provider_id)] if item["model"] else []
        models.extend(AiModelInfo.model_validate(model.model_dump() | {"provider": provider_id}) for model in scanned)
        item["models"] = _dedupe_models(models)
        item["allowed_model_ids"] = allowed
    return base


def registry_from_settings(settings: Settings) -> ModelRegistry:
    seed = _provider_seed_data(settings, None)
    providers = {
        provider_id: ProviderRegistryItem(
            id=provider_id,
            label=PROVIDER_LABELS[provider_id],
            base_url=data["base_url"],
            default_model_id=data["model"],
            api_key_configured=bool(data["api_key_configured"]),
        )
        for provider_id, data in seed.items()
    }
    models = {
        provider_id: [
            ModelRegistryItem(
                provider_id=provider_id,
                id=model.id,
                label=model.label,
                owned_by=model.owned_by,
                context_length=model.context_length,
                allowed=model.id in data["allowed_model_ids"],
                source="env",
            )
            for model in data["models"]
        ]
        for provider_id, data in seed.items()
    }
    return ModelRegistry(
        providers=providers,
        models=models,
        task_profiles={
            "render": TaskProfile("render", settings.ai_provider, "", []),
            "reasoning": TaskProfile("reasoning", settings.ai_provider, "", []),
            "solver_explanation": TaskProfile("solver_explanation", settings.ai_provider, "", []),
            "ocr": TaskProfile("ocr", "router9" if settings.router9_ocr_model else "openrouter", settings.router9_ocr_model or settings.openrouter_vision_model, []),
        },
        settings={
            "router9_only": settings.router9_only,
            "openrouter_reasoning_enabled": settings.openrouter_reasoning_enabled,
            "ocr_max_image_mb": 5,
            "default_provider": settings.ai_provider,
        },
    )


def _dedupe_models(models: list[AiModelInfo]) -> list[AiModelInfo]:
    seen = set()
    output = []
    for model in models:
        if not model.id or model.id in seen:
            continue
        seen.add(model.id)
        output.append(model)
    return output


def _json_value(value: Any) -> Any:
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def _json_list(value: Any) -> list[str]:
    parsed = _json_value(value)
    return [str(item) for item in parsed] if isinstance(parsed, list) else []
