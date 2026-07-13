from __future__ import annotations

import json
import time
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
    CanonicalModelRef,
    canonical_provider_id,
    canonicalize_explicit_provider_model,
    canonicalize_fallback_models,
    canonicalize_legacy_model_ref,
    canonicalize_model_ref,
    format_provider_model_ref,
    normalize_model_for_provider,
    parse_provider_model_ref,
)

_REGISTRY_CACHE: tuple[float, str, Settings, ModelRegistry] | None = None
_REGISTRY_CACHE_TTL_SECONDS = 45.0

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
    api_key_configured: bool
    engine: str = "openai_compat"
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
    is_free_endpoint: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    supported_parameters: list[str] = field(default_factory=list)
    pricing: dict[str, Any] = field(default_factory=dict)
    endpoint_metadata: dict[str, Any] = field(default_factory=dict)
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
            AiModelInfo(
                id=model.id,
                label=model.label,
                provider=provider_id,
                owned_by=model.owned_by,
                context_length=model.context_length,
                capabilities=model.capabilities,
                is_free_endpoint=model.is_free_endpoint,
                supports_thinking=model.supports_thinking,
                supports_vision=model.supports_vision,
                supported_parameters=model.supported_parameters,
                pricing=model.pricing,
                endpoint_metadata=model.endpoint_metadata,
            )
            for model in self.models.get(provider_id, []) if model.enabled
        ]


async def load_model_registry(db: DatabaseClient, settings: Settings | None = None) -> ModelRegistry:
    global _REGISTRY_CACHE
    settings = settings or get_settings()
    now = time.monotonic()
    db_token = _database_cache_token(db)
    if _REGISTRY_CACHE is not None:
        cached_at, cached_db_token, cached_settings, cached_registry = _REGISTRY_CACHE
        if now - cached_at < _REGISTRY_CACHE_TTL_SECONDS and cached_db_token == db_token and cached_settings is settings:
            return cached_registry
    registry = await _load_model_registry_uncached(db, settings)
    _REGISTRY_CACHE = (now, db_token, settings, registry)
    return registry


def invalidate_model_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


def _database_cache_token(db: DatabaseClient) -> str:
    backend = str(getattr(db, "backend", db.__class__.__name__))
    path = getattr(db, "path", None)
    return f"{backend}:{path}" if path else f"{backend}:{id(db)}"


async def _load_model_registry_uncached(db: DatabaseClient, settings: Settings) -> ModelRegistry:
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
            api_key_configured=bool(row["api_key_configured"]),
            engine=str(row.get("engine") or "openai_compat"),
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
            is_free_endpoint=bool(row.get("is_free_endpoint", 0)),
            supports_thinking=bool(row.get("supports_thinking", 0)),
            supports_vision=bool(row.get("supports_vision", 0)),
            supported_parameters=_json_list(row.get("supported_parameters_json")),
            pricing=_json_dict(row.get("pricing_json")),
            endpoint_metadata=_json_dict(row.get("endpoint_metadata_json")),
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


def _router9_default_model(settings: Settings) -> str:
    if settings.router9_text_model:
        return settings.router9_text_model
    if settings.router9_allowed_models:
        from app.services.router9_bootstrap import select_router9_render_model_ids_from_ids

        selected = select_router9_render_model_ids_from_ids(list(settings.router9_allowed_models))
        return selected[0] if selected else settings.router9_allowed_models[0]
    return ""


def _provider_has_credentials(settings: Settings, provider_id: str) -> bool:
    if provider_id == "ollama":
        return True
    if provider_id == "router9":
        return provider_configured(settings.router9_api_key)
    if provider_id == "nvidia":
        return provider_configured(settings.nvidia_api_key)
    if provider_id == "openrouter":
        return provider_configured(settings.openrouter_api_key)
    if provider_id == "openai_compat":
        return provider_configured(settings.openai_compat_api_key)
    return False


def default_text_profile(settings: Settings, preferred_provider: str | None = None) -> tuple[str, str]:
    provider_id = canonical_provider_id(preferred_provider) or "auto"
    models = {
        "router9": _router9_default_model(settings),
        "nvidia": settings.nvidia_text_model,
        "openrouter": settings.openrouter_text_model,
        "openai_compat": settings.openai_compat_text_model,
        "ollama": settings.ollama_text_model,
    }
    if settings.router9_only:
        provider_id = "router9"
    if provider_id in models and models[provider_id] and _provider_has_credentials(settings, provider_id):
        return provider_id, models[provider_id]
    candidates = [
        ("router9", provider_configured(settings.router9_api_key)),
        ("nvidia", provider_configured(settings.nvidia_api_key)),
        ("openrouter", provider_configured(settings.openrouter_api_key)),
        ("openai_compat", provider_configured(settings.openai_compat_api_key)),
        ("ollama", True),
    ]
    for candidate, configured in candidates:
        if configured and models[candidate]:
            return candidate, models[candidate]
    # Soft seed for bare installs (no env models / keys): skip hard crash; ensure_task_profiles
    # will only insert profiles when a usable pair exists, and admin can complete setup later.
    for candidate in ("openrouter", "router9", "nvidia", "openai_compat", "ollama"):
        if models.get(candidate):
            return candidate, models[candidate]
    raise ValueError("Không có model nào để khởi tạo task profile.")


async def seed_model_registry(db: DatabaseClient, settings: Settings) -> None:
    repo = ModelRegistryRepository(db)
    if await repo.has_any_provider():
        return
    provider_data = _provider_seed_data(settings, None)
    for provider_id, data in provider_data.items():
        await repo.insert_seed_provider(provider_id, PROVIDER_LABELS[provider_id], data["base_url"], bool(data["api_key_configured"]))
        for model in data["models"]:
            allowed = provider_id == "local" or model.id in data["allowed_model_ids"]
            await upsert_model(db, provider_id, model, allowed=allowed, source="env")
        if provider_id == "router9" and settings.router9_allowed_models:
            for model_id in settings.router9_allowed_models:
                await upsert_model(
                    db,
                    provider_id,
                    AiModelInfo(id=model_id, label=model_id, provider=provider_id),
                    allowed=True,
                    source="env",
                )
    await set_model_setting(db, "router9_only", settings.router9_only)
    await set_model_setting(db, "openrouter_reasoning_enabled", settings.openrouter_reasoning_enabled)
    await set_model_setting(db, "ocr_max_image_mb", 5)
    await set_model_setting(db, "default_provider", settings.ai_provider)
    ocr_provider, ocr_model = default_ocr_profile(settings)
    text_provider, text_model = default_text_profile(settings, settings.ai_provider)
    for task in TIERED_TASKS:
        for tier in TIER_KEYS:
            await save_task_profile(db, f"{task}_{tier}", text_provider, text_model, [])
    await save_task_profile(db, "reasoning", text_provider, text_model, [])
    await save_task_profile(db, "solver_explanation", text_provider, text_model, [])
    if ocr_model:
        await save_task_profile(db, "ocr", ocr_provider, ocr_model, [])



async def load_legacy_ai_settings(db: DatabaseClient) -> SystemAiSettings | None:
    from app.services.model_provider import normalize_provider_defaults

    value_json = await ModelRegistryRepository(db).load_legacy_ai_settings_json()
    if value_json is None:
        return None
    try:
        value = json.loads(value_json)
        if not isinstance(value, dict):
            return None
        value = normalize_provider_defaults(value) or {}
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
        db_api_key = (getattr(provider_settings, "api_key", "") or "").strip()
        if db_base_url and not (registry_provider and registry_provider.base_url):
            data[f"{provider_id}_base_url"] = db_base_url
        if db_api_key and (db_base_url or getattr(provider_settings, "allowed_model_ids", []) or getattr(provider_settings, "scanned_models", [])):
            data[f"{provider_id}_api_key"] = db_api_key
        allowed = list(getattr(provider_settings, "allowed_model_ids", None) or [])
        if provider_id == "router9" and allowed:
            data["router9_allowed_models"] = allowed
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
    invalidate_model_registry_cache()


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
        ref = canonicalize_explicit_provider_model(provider_id, model_id)
        if ref.model_id not in canonical_ids:
            canonical_ids.append(ref.model_id)
    for model_id in canonical_ids:
        await repo.allow_model(provider_id, model_id)
    await repo.delete_unallowed_manual_models(provider_id)
    invalidate_model_registry_cache()


async def save_provider_config(db: DatabaseClient, provider_id: str, base_url: str, enabled: bool = True, api_key_configured: bool | None = None) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    await ModelRegistryRepository(db).upsert_provider(provider_id, PROVIDER_LABELS.get(provider_id, provider_id), base_url, enabled, api_key_configured)
    invalidate_model_registry_cache()


async def save_provider_check(db: DatabaseClient, provider_id: str, status: str, message: str) -> None:
    await ensure_provider(db, provider_id)
    await ModelRegistryRepository(db).update_provider_check(provider_id, status, message)
    invalidate_model_registry_cache()


async def save_task_profile(db: DatabaseClient, task: str, provider_id: str, model_id: str, fallbacks: list[str]) -> None:
    if provider_id == "auto":
        raise ValueError("Task profile phải lưu provider_id rõ ràng, không dùng auto.")
    if not model_id:
        raise ValueError(f"Task profile {task} phải chọn model.")
    ref = canonicalize_explicit_provider_model(provider_id, model_id)
    provider_id = ref.provider_id
    model_id = ref.model_id
    fallbacks, _ = canonicalize_fallback_models(provider_id, fallbacks, strict=True)
    await ModelRegistryRepository(db).upsert_task_profile(task, provider_id, model_id, fallbacks)
    invalidate_model_registry_cache()


async def set_model_setting(db: DatabaseClient, key: str, value: Any) -> None:
    await ModelRegistryRepository(db).set_model_setting(key, value)
    invalidate_model_registry_cache()


async def ensure_provider(db: DatabaseClient, provider_id: str) -> None:
    provider_id = canonical_provider_id(provider_id) or provider_id
    await ModelRegistryRepository(db).ensure_provider(provider_id, PROVIDER_LABELS.get(provider_id, provider_id))


def _canonical_model_info(provider_id: str, model: AiModelInfo) -> AiModelInfo:
    if provider_id == "openrouter" and model.provider == "openrouter" and not model.id.startswith("openrouter/"):
        model_id = model.id.strip()
        return model.model_copy(update={"provider": provider_id, "id": model_id, "label": model.label or model_id})
    ref = canonicalize_model_ref(provider_id, model.id, strict=True, allow_auto=False)
    label = model.label or model.id
    if label == model.id:
        label = ref.model_id
    return model.model_copy(update={"provider": provider_id, "id": ref.model_id, "label": label})


def _canonicalize_legacy_tier_model_ref(provider_id: str, model_id: str) -> CanonicalModelRef:
    provider_id = canonical_provider_id(provider_id) or "auto"
    model_id = (model_id or "").strip()
    if not model_id:
        return CanonicalModelRef(provider_id=provider_id, model_id="")
    explicit_ref = parse_provider_model_ref(model_id, allow_legacy_slash=False)
    if explicit_ref is not None:
        return explicit_ref
    if provider_id != "auto":
        normalized = normalize_model_for_provider(provider_id, model_id) or ""
        return CanonicalModelRef(provider_id=provider_id, model_id=normalized, changed=normalized != model_id)
    return CanonicalModelRef(provider_id="auto", model_id=model_id)


def _canonicalize_legacy_tier_fallbacks(provider_id: str, fallbacks: list[str]) -> list[str]:
    output: list[str] = []
    for fallback in fallbacks:
        value = (fallback or "").strip()
        if not value:
            continue
        ref = parse_provider_model_ref(value, allow_legacy_slash=True)
        if ref is None and provider_id != "auto":
            ref = canonicalize_model_ref(provider_id, value, strict=False, allow_auto=False)
        if ref is None:
            continue
        model_ref = format_provider_model_ref(ref.provider_id, ref.model_id)
        if model_ref and model_ref not in output:
            output.append(model_ref)
    return output


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
        if task.startswith("render_tier"):
            ref = _canonicalize_legacy_tier_model_ref(provider_id, model_id)
            canonical_fallbacks = _canonicalize_legacy_tier_fallbacks(ref.provider_id, fallbacks)
            if ref.provider_id != provider_id or ref.model_id != model_id or canonical_fallbacks != fallbacks:
                await repo.update_task_profile(task, ref.provider_id, ref.model_id, canonical_fallbacks)
                changed += 1
            continue
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
        "local": {"base_url": "", "seed_model_id": settings.local_ocr_model_name, "api_key_configured": True},
        "openrouter": {"base_url": settings.openrouter_base_url, "seed_model_id": settings.openrouter_text_model, "api_key_configured": provider_configured(settings.openrouter_api_key)},
        "nvidia": {"base_url": settings.nvidia_base_url, "seed_model_id": settings.nvidia_text_model, "api_key_configured": provider_configured(settings.nvidia_api_key)},
        "ollama": {"base_url": settings.ollama_base_url, "seed_model_id": settings.ollama_text_model, "api_key_configured": bool(settings.ollama_api_key)},
        "openai_compat": {"base_url": settings.openai_compat_base_url, "seed_model_id": settings.openai_compat_text_model, "api_key_configured": provider_configured(settings.openai_compat_api_key)},
        "router9": {"base_url": settings.router9_base_url, "seed_model_id": settings.router9_text_model or "", "api_key_configured": provider_configured(settings.router9_api_key)},
    }
    for provider_id, item in base.items():
        configured = provider_settings[provider_id]
        scanned = []
        allowed = []
        if configured is not None:
            item["base_url"] = configured.base_url or item["base_url"]
            scanned = configured.scanned_models
            allowed = configured.allowed_model_ids
        elif provider_id == "router9":
            allowed = settings.router9_allowed_models
        seed_model_id = item["seed_model_id"]
        models = [AiModelInfo(id=seed_model_id, label=seed_model_id, provider=provider_id)] if seed_model_id else []
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
                is_free_endpoint=model.is_free_endpoint,
                supports_thinking=model.supports_thinking,
                supports_vision=model.supports_vision,
                supported_parameters=model.supported_parameters,
                pricing=model.pricing,
                endpoint_metadata=model.endpoint_metadata,
                allowed=model.id in data["allowed_model_ids"],
                source="env",
            )
            for model in data["models"]
        ]
        for provider_id, data in seed.items()
    }
    text_provider, text_model = default_text_profile(settings, settings.ai_provider)
    task_profiles = {
        "reasoning": TaskProfile("reasoning", text_provider, text_model, []),
        "solver_explanation": TaskProfile("solver_explanation", text_provider, text_model, []),
        "ocr": TaskProfile("ocr", *default_ocr_profile(settings), []),
    }
    for task in TIERED_TASKS:
        for tier in TIER_KEYS:
            task_key = f"{task}_{tier}"
            task_profiles[task_key] = TaskProfile(task_key, text_provider, text_model, [])
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


def health_check_model(registry: ModelRegistry, provider_id: str) -> str:
    if not provider_is_enabled(registry, provider_id):
        return ""
    allowed_model_ids = registry.allowed_model_ids(provider_id)
    if allowed_model_ids:
        return allowed_model_ids[0]
    enabled_model_ids = registry.enabled_model_ids(provider_id)
    return enabled_model_ids[0] if enabled_model_ids else ""


def resolve_task_profile(registry: ModelRegistry, task: str, preferred_provider: str | None = None, preferred_model: str | None = None) -> TaskProfile:
    profile = registry.task_profiles.get(task)
    preferred_provider_id = canonical_provider_id(preferred_provider)
    profile_provider = canonical_provider_id(profile.provider_id) if profile else None
    provider_id = preferred_provider_id or profile_provider
    if not provider_id or provider_id == "auto":
        raise ValueError(f"Task profile {task} phải chọn provider rõ ràng.")
    if provider_id != "local" and not provider_is_enabled(registry, provider_id):
        raise ValueError(f"Provider {provider_id} của task profile {task} đang bị tắt.")

    if preferred_model:
        raw_model_id = canonicalize_model_ref(provider_id, preferred_model, strict=True, allow_auto=False).model_id
    elif profile and profile_provider == provider_id:
        raw_model_id = profile.model_id
    else:
        raw_model_id = ""
    model_id = normalize_model_for_provider(provider_id, raw_model_id) or ""
    if not model_id:
        # Prefer first allowed/enabled model; empty bare profile (no preferred) stays empty for default fallback.
        allowed = registry.allowed_model_ids(provider_id)
        enabled = registry.enabled_model_ids(provider_id)
        model_id = (allowed[0] if allowed else enabled[0] if enabled else "") or ""
        if not model_id:
            if preferred_provider_id or preferred_model:
                raise ValueError(f"Task profile {task} phải chọn model.")
            fallbacks = _resolve_profile_fallbacks(registry, profile.fallbacks, provider_id) if profile else []
            return TaskProfile(task, provider_id, "", fallbacks)
    if not model_is_allowed(registry, provider_id, model_id):
        raise ValueError(f"Model {model_id} của task profile {task} không khả dụng trong provider {provider_id}.")

    fallbacks = _resolve_profile_fallbacks(registry, profile.fallbacks, provider_id) if profile else []
    if task == "reasoning":
        provider_id, model_id, fallbacks = _prefer_thinking_model(registry, provider_id, model_id, fallbacks)
    return TaskProfile(task, provider_id, model_id, fallbacks)


def resolve_render_tier_candidates(registry: ModelRegistry, tier: str) -> list[TierModelCandidate]:
    profile = registry.task_profiles.get(f"render_{tier}")
    return _tier_profile_candidates(registry, profile)


def _tier_profile_candidates(registry: ModelRegistry, profile: TaskProfile | None) -> list[TierModelCandidate]:
    if profile is None:
        return []
    provider_id = canonical_provider_id(profile.provider_id)
    if provider_id == "auto" and profile.model_id:
        return []
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
        fallback_provider, fallback_model = _tier_fallback_provider_model(fallback)
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
            value = model_id if provider_id == primary_provider_id else format_provider_model_ref(provider_id, model_id)
            if value not in resolved:
                resolved.append(value)
    return resolved


def _fallback_provider_model(fallback: str, primary_provider_id: str) -> tuple[str, str]:
    try:
        explicit_ref = parse_provider_model_ref(fallback, allow_legacy_slash=False)
    except ValueError:
        explicit_ref = None
    if explicit_ref is not None:
        return explicit_ref.provider_id, explicit_ref.model_id
    return primary_provider_id, normalize_model_for_provider(primary_provider_id, fallback) or ""


def _tier_fallback_provider_model(fallback: str) -> tuple[str, str]:
    try:
        ref = parse_provider_model_ref(fallback, allow_legacy_slash=False)
    except ValueError:
        ref = None
    if ref is None:
        return "", ""
    return ref.provider_id, ref.model_id





def model_supports_thinking(registry: ModelRegistry, provider_id: str | None, model_id: str | None) -> bool | None:
    provider_id = canonical_provider_id(provider_id)
    model_id = normalize_model_for_provider(provider_id, model_id or "") if provider_id else model_id
    if not provider_id or not model_id:
        return None
    for model in registry.models.get(provider_id, []):
        if model.id == model_id:
            return model.supports_thinking
    return None


def _prefer_thinking_model(registry: ModelRegistry, provider_id: str, model_id: str, fallbacks: list[str]) -> tuple[str, str, list[str]]:
    candidates: list[tuple[str, str, str | None]] = []
    if model_id:
        candidates.append((provider_id, model_id, None))
    for fallback in fallbacks:
        fallback_provider, fallback_model = _fallback_provider_model(fallback, provider_id)
        if fallback_model:
            candidates.append((fallback_provider, fallback_model, fallback))
    for candidate_provider, candidate_model, fallback_value in candidates:
        if model_supports_thinking(registry, candidate_provider, candidate_model) is True:
            if fallback_value is None:
                return provider_id, model_id, fallbacks
            remaining = [_format_fallback_model(provider_id, model_id, candidate_provider), *[fallback for fallback in fallbacks if fallback != fallback_value]]
            return candidate_provider, candidate_model, [fallback for fallback in remaining if fallback]
    return provider_id, model_id, fallbacks


def _format_fallback_model(provider_id: str, model_id: str, primary_provider_id: str) -> str:
    if not model_id:
        return ""
    return model_id if provider_id == primary_provider_id else format_provider_model_ref(provider_id, model_id)


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
