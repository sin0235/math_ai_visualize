from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings, merge_runtime_settings
from app.db.session import DatabaseClient
from app.repositories.model_registry import ModelRegistryRepository
from app.schemas.auth import SystemAiSettings
from app.schemas.scene import AiModelInfo, RuntimeSettings
from app.services.ai_fallback import provider_configured
from app.services.model_provider import (
    canonical_provider_id,
    canonicalize_fallback_models,
    canonicalize_legacy_model_ref,
    canonicalize_model_ref,
    normalize_model_for_provider,
)

PROVIDER_LABELS = {
    "local": "Local OCR",
    "openrouter": "OpenRouter",
    "nvidia": "NVIDIA",
    "ollama": "Ollama",
    "openai_compat": "OpenAI-compatible",
    "router9": "9router",
}
TIER_KEYS = ("tier1", "tier2", "tier3")
TIERED_TASKS = ("render",)


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
    capabilities: dict[str, Any] = field(default_factory=dict)
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
class TierModelCandidate:
    provider_id: str
    model_id: str


@dataclass(frozen=True)
class ModelRegistry:
    providers: dict[str, ProviderRegistryItem]
    models: dict[str, list[ModelRegistryItem]]
    task_profiles: dict[str, TaskProfile]
    settings: dict[str, Any]
    legacy_used: bool = False

    def allowed_model_ids(self, provider_id: str) -> list[str]:
        return [model.id for model in self.models.get(provider_id, []) if model.allowed and model.enabled]

    def enabled_model_ids(self, provider_id: str) -> list[str]:
        return [model.id for model in self.models.get(provider_id, []) if model.enabled]

    def has_allowlist(self, provider_id: str) -> bool:
        return any(model.allowed and model.enabled for model in self.models.get(provider_id, []))

    def scanned_model_infos(self, provider_id: str) -> list[AiModelInfo]:
        return [
            AiModelInfo(id=model.id, label=model.label, provider=provider_id, owned_by=model.owned_by, context_length=model.context_length, capabilities=model.capabilities)
            for model in self.models.get(provider_id, []) if model.enabled
        ]


async def load_model_registry(db: DatabaseClient, settings: Settings | None = None) -> ModelRegistry:
    settings = settings or get_settings()
    try:
        repo = ModelRegistryRepository(db)
        await seed_model_registry(db, settings)
        await ensure_model_registry_canonical(db)
        provider_rows = await repo.list_providers()
    except RuntimeError as error:
        if "no such table" not in str(error).lower():
            raise
        return registry_from_settings(settings)
    model_rows = await repo.list_models()
    profile_rows = await repo.list_task_profiles()
    setting_rows = await repo.list_model_settings()

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
            capabilities=_json_dict(row.get("capabilities_json")),
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
    return ModelRegistry(providers=providers, models=models, task_profiles=profiles, settings=registry_settings, legacy_used=await repo.has_legacy_ai_settings())


def default_ocr_profile(settings: Settings, legacy: SystemAiSettings | None = None) -> tuple[str, str]:
    if legacy is not None:
        model = legacy.ocr.model or (settings.local_ocr_model_name if legacy.ocr.provider == "local" else "")
        return legacy.ocr.provider, model
    if settings.local_ocr_enabled and settings.local_ocr_prefer in {"auto", "always"} and not settings.router9_only:
        return "local", settings.local_ocr_model_name
    if settings.router9_ocr_model:
        return "router9", settings.router9_ocr_model
    return "openrouter", settings.openrouter_vision_model


async def seed_model_registry(db: DatabaseClient, settings: Settings) -> None:
    repo = ModelRegistryRepository(db)
    if await repo.has_any_provider():
        await ensure_task_profiles(db, settings)
        return
    legacy = await load_legacy_ai_settings(db)
    provider_data = _provider_seed_data(settings, legacy)
    for provider_id, data in provider_data.items():
        await repo.insert_seed_provider(provider_id, PROVIDER_LABELS[provider_id], data["base_url"], data["model"], bool(data["api_key_configured"]))
        for model in data["models"]:
            allowed = provider_id == "local" or model.id in data["allowed_model_ids"]
            await upsert_model(db, provider_id, model, allowed=allowed, source="legacy" if legacy else "env")
    router9_only = legacy.router9.only_mode if legacy else settings.router9_only
    openrouter_reasoning = legacy.openrouter_reasoning_enabled if legacy else settings.openrouter_reasoning_enabled
    ocr_max = legacy.ocr.max_image_mb if legacy else 5
    default_provider = legacy.default_provider if legacy else settings.ai_provider
    await set_model_setting(db, "router9_only", router9_only)
    await set_model_setting(db, "openrouter_reasoning_enabled", openrouter_reasoning)
    await set_model_setting(db, "ocr_max_image_mb", ocr_max)
    await set_model_setting(db, "default_provider", default_provider)
    ocr_provider, ocr_model = default_ocr_profile(settings, legacy)
    for task in TIERED_TASKS:
        for tier in TIER_KEYS:
            await save_task_profile(db, f"{task}_{tier}", default_provider, "", [])
    await save_task_profile(db, "ocr", ocr_provider, ocr_model or "", [])


async def load_legacy_ai_settings(db: DatabaseClient) -> SystemAiSettings | None:
    value_json = await ModelRegistryRepository(db).load_legacy_ai_settings_json()
    if value_json is None:
        return None
    try:
        value = json.loads(value_json)
        if not isinstance(value, dict):
            return None
        return SystemAiSettings.model_validate(value)
    except (json.JSONDecodeError, ValidationError):
        return None


async def resolve_effective_settings(db: DatabaseClient | None, runtime_settings: RuntimeSettings | None = None) -> Settings:
    settings = get_settings()
    if db is not None:
        registry = await load_model_registry(db, settings)
        admin_settings = await load_legacy_ai_settings(db) if hasattr(db, "fetch_one") else None
        settings = settings_from_registry(settings, registry)
        settings = settings_from_admin_ai_settings(settings, admin_settings, registry)
    return merge_runtime_settings(settings, runtime_settings)


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
        if db_api_key and (db_base_url or db_model or getattr(provider_settings, "allowed_model_ids", []) or getattr(provider_settings, "scanned_models", [])):
            data[f"{provider_id}_api_key"] = db_api_key
    return Settings.model_validate(data)



def settings_from_registry(settings: Settings, registry: ModelRegistry) -> Settings:
    data = settings.model_dump()
    default_provider = registry.settings.get("default_provider")
    if isinstance(default_provider, str) and default_provider and provider_is_enabled(registry, default_provider):
        data["ai_provider"] = default_provider
    elif isinstance(default_provider, str) and default_provider not in {"", "auto", "mock"}:
        data["ai_provider"] = "auto"
    for provider_id, provider in registry.providers.items():
        env_api_key = (getattr(settings, f"{provider_id}_api_key", "") or "").strip()
        keep_env_connection = provider_id == "openai_compat" and env_api_key and not provider.api_key_configured
        if provider.base_url and not keep_env_connection:
            data[f"{provider_id}_base_url"] = provider.base_url
        default_model_id = effective_provider_default_model(registry, provider_id, provider.default_model_id)
        if default_model_id and not keep_env_connection and provider_id != "local":
            key = "router9_text_model" if provider_id == "router9" else f"{provider_id}_text_model"
            data[key] = default_model_id
    data["router9_only"] = bool(registry.settings.get("router9_only", settings.router9_only))
    data["openrouter_reasoning_enabled"] = bool(registry.settings.get("openrouter_reasoning_enabled", settings.openrouter_reasoning_enabled))
    router9_allowed = registry.allowed_model_ids("router9")
    if router9_allowed:
        data["router9_allowed_models"] = router9_allowed
    ocr_profile = registry.task_profiles.get("ocr")
    if ocr_profile and ocr_profile.model_id:
        provider_id = ocr_profile.provider_id
        model_id = normalize_model_for_provider(provider_id, ocr_profile.model_id) or ""
        if provider_id == "router9" and model_id and model_is_allowed(registry, provider_id, model_id):
            data["router9_ocr_model"] = model_id
        elif provider_id == "openrouter" and model_id and model_is_allowed(registry, provider_id, model_id):
            data["openrouter_vision_model"] = model_id
        elif provider_id in {"nvidia", "ollama", "openai_compat"} and model_id and model_is_allowed(registry, provider_id, model_id):
            data[f"{provider_id}_text_model"] = model_id
    return Settings.model_validate(data)


async def upsert_scanned_models(db: DatabaseClient, provider_id: str, models: list[AiModelInfo]) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    canonical_models = [_canonical_model_info(provider_id, model) for model in models]
    repo = ModelRegistryRepository(db)
    existing_allowed = await repo.enabled_allowed_model_ids(provider_id)
    await ensure_provider(db, provider_id)
    existing_scanned = await repo.scanned_model_ids(provider_id)
    scanned_ids = {model.id for model in canonical_models if model.id}
    for stale_id in existing_scanned - scanned_ids:
        await repo.disable_scanned_model(provider_id, stale_id)
    for model in canonical_models:
        await upsert_model(db, provider_id, model, allowed=model.id in existing_allowed, source="scan")


async def upsert_model(db: DatabaseClient, provider_id: str, model: AiModelInfo, allowed: bool, source: str) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    model = _canonical_model_info(provider_id, model)
    await ModelRegistryRepository(db).upsert_model(provider_id, model, allowed, source)


async def set_allowed_models(db: DatabaseClient, provider_id: str, model_ids: list[str]) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    repo = ModelRegistryRepository(db)
    await ensure_provider(db, provider_id)
    await repo.clear_allowed_models(provider_id)
    canonical_ids = []
    for model_id in model_ids:
        ref = canonicalize_model_ref(provider_id, model_id, strict=True, allow_auto=False)
        if ref.model_id not in canonical_ids:
            canonical_ids.append(ref.model_id)
    for model_id in canonical_ids:
        await repo.allow_model(provider_id, model_id)


async def save_provider_config(db: DatabaseClient, provider_id: str, base_url: str, default_model_id: str, enabled: bool = True, api_key_configured: bool | None = None) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    default_model_id = canonicalize_model_ref(provider_id, default_model_id, strict=True, allow_auto=False).model_id if default_model_id else ""
    await ModelRegistryRepository(db).upsert_provider(provider_id, PROVIDER_LABELS.get(provider_id, provider_id), base_url, default_model_id, enabled, api_key_configured)


async def save_provider_check(db: DatabaseClient, provider_id: str, status: str, message: str) -> None:
    await ensure_provider(db, provider_id)
    await ModelRegistryRepository(db).update_provider_check(provider_id, status, message)


async def save_task_profile(db: DatabaseClient, task: str, provider_id: str, model_id: str, fallbacks: list[str]) -> None:
    if provider_id == "auto" and not model_id:
        fallbacks, _ = canonicalize_fallback_models(provider_id, fallbacks, strict=True)
        await ModelRegistryRepository(db).upsert_task_profile(task, provider_id, "", fallbacks)
        return
    ref = canonicalize_model_ref(provider_id, model_id, strict=True)
    provider_id = ref.provider_id
    model_id = ref.model_id
    fallbacks, _ = canonicalize_fallback_models(provider_id, fallbacks, strict=True)
    await ModelRegistryRepository(db).upsert_task_profile(task, provider_id, model_id, fallbacks)


async def set_model_setting(db: DatabaseClient, key: str, value: Any) -> None:
    await ModelRegistryRepository(db).set_model_setting(key, value)


async def ensure_task_profiles(db: DatabaseClient, settings: Settings) -> None:
    await ensure_local_ocr_provider(db, settings)
    ocr_provider, ocr_model = default_ocr_profile(settings)
    defaults = {
        "reasoning": (settings.ai_provider, "", []),
        "solver_explanation": (settings.ai_provider, "", []),
        "ocr": (ocr_provider, ocr_model, []),
    }
    for task in TIERED_TASKS:
        for tier in TIER_KEYS:
            defaults[f"{task}_{tier}"] = (settings.ai_provider, "", [])
    repo = ModelRegistryRepository(db)
    await repo.delete_unsupported_tier_profiles()
    for task, (provider_id, model_id, fallbacks) in defaults.items():
        if not await repo.task_profile_exists(task):
            await save_task_profile(db, task, provider_id, model_id, fallbacks)


async def ensure_provider(db: DatabaseClient, provider_id: str) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    await ModelRegistryRepository(db).ensure_provider(provider_id, PROVIDER_LABELS.get(provider_id, provider_id))


async def ensure_local_ocr_provider(db: DatabaseClient, settings: Settings) -> None:
    await save_provider_config(
        db,
        "local",
        "",
        settings.local_ocr_model_name,
        enabled=bool(settings.local_ocr_enabled),
        api_key_configured=True,
    )
    await upsert_model(
        db,
        "local",
        AiModelInfo(id=settings.local_ocr_model_name, label=settings.local_ocr_model_name, provider="local"),
        allowed=True,
        source="env",
    )


def _canonical_model_info(provider_id: str, model: AiModelInfo) -> AiModelInfo:
    ref = canonicalize_model_ref(provider_id, model.id, strict=True, allow_auto=False)
    label = model.label or model.id
    if label == model.id:
        label = ref.model_id
    return model.model_copy(update={"provider": provider_id, "id": ref.model_id, "label": label})


async def ensure_model_registry_canonical(db: DatabaseClient) -> None:
    repo = ModelRegistryRepository(db)
    rows = await repo.canonical_task_profile_rows()
    warnings: list[str] = []
    changed = 0
    for row in rows:
        task = str(row["task"])
        provider_id = str(row["provider_id"] or "auto")
        model_id = str(row["model_id"] or "")
        fallbacks = _json_list(row.get("fallbacks_json"))
        ref = canonicalize_legacy_model_ref(provider_id, model_id)
        canonical_fallbacks, fallback_warnings = canonicalize_fallback_models(ref.provider_id, fallbacks, strict=False)
        canonical_model_id = model_id if task == "ocr" and provider_id == ref.provider_id and model_id.startswith(f"{ref.provider_id}/") else ref.model_id
        if ref.warning:
            warnings.append(f"{task}: {ref.warning}")
        warnings.extend(f"{task}: {warning}" for warning in fallback_warnings)
        if ref.provider_id != provider_id or canonical_model_id != model_id or canonical_fallbacks != fallbacks:
            await repo.update_task_profile(task, ref.provider_id, canonical_model_id, canonical_fallbacks)
            changed += 1
    if changed or warnings:
        await set_model_setting(db, "last_canonicalization_report", {"changed_profiles": changed, "warnings": warnings[:50]})
    await set_model_setting(db, "model_registry_schema_version", 2)


def _provider_seed_data(settings: Settings, legacy: SystemAiSettings | None) -> dict[str, dict[str, Any]]:
    provider_settings = {
        "local": None,
        "openrouter": legacy.openrouter if legacy else None,
        "nvidia": legacy.nvidia if legacy else None,
        "ollama": legacy.ollama if legacy else None,
        "openai_compat": None,
        "router9": legacy.router9 if legacy else None,
    }
    base = {
        "local": {"base_url": "", "model": settings.local_ocr_model_name, "api_key_configured": True},
        "openrouter": {"base_url": settings.openrouter_base_url, "model": settings.openrouter_text_model, "api_key_configured": provider_configured(settings.openrouter_api_key)},
        "nvidia": {"base_url": settings.nvidia_base_url, "model": settings.nvidia_text_model, "api_key_configured": provider_configured(settings.nvidia_api_key)},
        "ollama": {"base_url": settings.ollama_base_url, "model": settings.ollama_text_model, "api_key_configured": bool(settings.ollama_api_key)},
        "openai_compat": {"base_url": settings.openai_compat_base_url, "model": settings.openai_compat_text_model, "api_key_configured": provider_configured(settings.openai_compat_api_key)},
        "router9": {"base_url": settings.router9_base_url, "model": settings.router9_text_model or "", "api_key_configured": provider_configured(settings.router9_api_key)},
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
                capabilities=model.capabilities,
                allowed=model.id in data["allowed_model_ids"],
                source="env",
            )
            for model in data["models"]
        ]
        for provider_id, data in seed.items()
    }
    task_profiles = {
        "reasoning": TaskProfile("reasoning", settings.ai_provider, "", []),
        "solver_explanation": TaskProfile("solver_explanation", settings.ai_provider, "", []),
        "ocr": TaskProfile("ocr", *default_ocr_profile(settings), []),
    }
    for task in TIERED_TASKS:
        for tier in TIER_KEYS:
            task_key = f"{task}_{tier}"
            task_profiles[task_key] = TaskProfile(task_key, settings.ai_provider, "", [])
    return ModelRegistry(
        providers=providers,
        models=models,
        task_profiles=task_profiles,
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


def provider_is_enabled(registry: ModelRegistry, provider_id: str) -> bool:
    provider = registry.providers.get(provider_id)
    return bool(provider and provider.enabled)


def model_is_enabled(registry: ModelRegistry, provider_id: str, model_id: str) -> bool:
    if not model_id:
        return False
    models = registry.models.get(provider_id, [])
    if not models:
        return True
    matched = [model for model in models if model.id == model_id]
    if not matched:
        return True
    return any(model.enabled for model in matched)


def model_is_allowed(registry: ModelRegistry, provider_id: str, model_id: str) -> bool:
    if provider_id == "local":
        return bool(model_id)
    if not provider_is_enabled(registry, provider_id) or not model_is_enabled(registry, provider_id, model_id):
        return False
    allowed_model_ids = registry.allowed_model_ids(provider_id)
    return not allowed_model_ids or model_id in allowed_model_ids


def effective_provider_default_model(registry: ModelRegistry, provider_id: str, default_model_id: str) -> str:
    if not provider_is_enabled(registry, provider_id):
        return ""
    allowed_model_ids = registry.allowed_model_ids(provider_id)
    if allowed_model_ids:
        if default_model_id in allowed_model_ids:
            return default_model_id
        return allowed_model_ids[0]
    if model_is_enabled(registry, provider_id, default_model_id):
        return default_model_id
    enabled_model_ids = registry.enabled_model_ids(provider_id)
    if enabled_model_ids:
        return enabled_model_ids[0]
    # Admin-entered provider defaults are stored on ai_providers before a model scan
    # creates ai_models rows. Treat that database default as usable so OCR and
    # profile resolution do not silently fall back to env OpenRouter vision values.
    return default_model_id or ""


def resolve_task_profile(registry: ModelRegistry, task: str, preferred_provider: str | None = None, preferred_model: str | None = None) -> TaskProfile | None:
    profile = registry.task_profiles.get(task)
    preferred_provider_id = normalize_registry_provider_id(preferred_provider)
    profile_provider = normalize_registry_provider_id(profile.provider_id) if profile else "auto"
    if preferred_provider_id:
        provider_id = preferred_provider_id
    else:
        provider_id = profile_provider or "auto"
    if provider_id == "auto":
        default_provider = registry.settings.get("default_provider")
        provider_id = default_provider if isinstance(default_provider, str) and provider_is_enabled(registry, default_provider) else "auto"
    if provider_id == "auto" or (provider_id != "local" and not provider_is_enabled(registry, provider_id)):
        return None

    raw_model_id = ""
    if preferred_model:
        raw_model_id = canonicalize_model_ref(provider_id, preferred_model, strict=True, allow_auto=False).model_id
    elif profile and not preferred_provider_id:
        raw_model_id = profile.model_id
    elif profile and profile_provider == provider_id:
        raw_model_id = profile.model_id

    model_id = normalize_model_for_provider(provider_id, raw_model_id) or ""
    if not model_id:
        provider = registry.providers.get(provider_id)
        model_id = effective_provider_default_model(registry, provider_id, provider.default_model_id if provider else "")
    if model_id and not model_is_allowed(registry, provider_id, model_id):
        model_id = effective_provider_default_model(registry, provider_id, "")
    fallbacks = []
    if profile:
        fallbacks = _resolve_profile_fallbacks(registry, profile.fallbacks, provider_id)
    return TaskProfile(task, provider_id, model_id, fallbacks)


def resolve_render_tier_candidates(registry: ModelRegistry, tier: str) -> list[TierModelCandidate]:
    profile = registry.task_profiles.get(f"render_{tier}")
    return _tier_profile_candidates(registry, profile)


def _tier_profile_candidates(registry: ModelRegistry, profile: TaskProfile | None) -> list[TierModelCandidate]:
    if profile is None:
        return []
    provider_id = normalize_registry_provider_id(profile.provider_id)
    if provider_id == "auto":
        default_provider = registry.settings.get("default_provider")
        provider_id = default_provider if isinstance(default_provider, str) and provider_is_enabled(registry, default_provider) else None
    if not provider_id or not provider_is_enabled(registry, provider_id):
        return []

    candidates: list[TierModelCandidate] = []

    model_id = normalize_model_for_provider(provider_id, profile.model_id) or ""
    if model_id and model_is_allowed(registry, provider_id, model_id):
        candidates.append(TierModelCandidate(provider_id, model_id))

    for fallback in profile.fallbacks:
        fallback_provider, fallback_model = _fallback_provider_model(fallback, provider_id)
        if fallback_model and model_is_allowed(registry, fallback_provider, fallback_model):
            candidate = TierModelCandidate(fallback_provider, fallback_model)
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _resolve_profile_fallbacks(registry: ModelRegistry, fallbacks: list[str], primary_provider_id: str, *, same_provider_only: bool = False) -> list[str]:
    resolved: list[str] = []
    for fallback in fallbacks:
        provider_id, model_id = _fallback_provider_model(fallback, primary_provider_id)
        if same_provider_only and provider_id != primary_provider_id:
            continue
        if model_id and model_is_allowed(registry, provider_id, model_id):
            value = model_id if provider_id == primary_provider_id else f"{provider_id}/{model_id}"
            if value not in resolved:
                resolved.append(value)
    return resolved


def _fallback_provider_model(fallback: str, primary_provider_id: str) -> tuple[str, str]:
    provider_id = primary_provider_id
    model_id = fallback
    for candidate in ("openrouter", "nvidia", "ollama", "openai_compat", "router9"):
        prefix = f"{candidate}/"
        if fallback.startswith(prefix):
            provider_id = candidate
            model_id = fallback.removeprefix(prefix)
            break
    return provider_id, normalize_model_for_provider(provider_id, model_id) or ""


def normalize_registry_provider_id(provider_id: str | None) -> str | None:
    if provider_id == "ollama_gpt_oss":
        return "ollama"
    if provider_id in {"openrouter_gpt_oss", "opencode_nemotron"}:
        return "openrouter"
    return provider_id


# Backwards-compatible private alias for older imports/tests.
_effective_provider_default_model = effective_provider_default_model


def _json_value(value: Any) -> Any:
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[str]:
    parsed = _json_value(value)
    return [str(item) for item in parsed] if isinstance(parsed, list) else []
