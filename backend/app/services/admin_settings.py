from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.db.session import DatabaseClient
from app.repositories.admin import AdminRepository
from app.schemas.auth import SystemAiProfiles, SystemAiSettings
from app.schemas.scene import AiModelInfo
from app.services.model_registry import (
    load_model_registry,
    save_provider_config,
    save_task_profile,
    set_allowed_models,
    set_model_setting,
    upsert_scanned_models,
)

DIAGNOSTIC_TABLES = [
    "users",
    "sessions",
    "render_jobs",
    "user_settings",
    "system_settings",
    "audit_logs",
    "auth_tokens",
    "rate_limit_events",
    "legal_acceptances",
    "oauth_identities",
    "oauth_states",
    "usage_events",
    "ai_providers",
    "ai_models",
    "ai_task_profiles",
    "ai_model_settings",
    "schema_migrations",
]


async def build_database_diagnostics(db: DatabaseClient) -> dict[str, Any]:
    settings = get_settings()
    counts: dict[str, int | str] = {}
    for table in DIAGNOSTIC_TABLES:
        try:
            row = await db.fetch_one(f"SELECT COUNT(*) AS count FROM {table}")
            counts[table] = int(row["count"]) if row is not None else 0
        except Exception as error:
            counts[table] = str(error)

    migrations = await db.fetch_all("SELECT filename, applied_at FROM schema_migrations ORDER BY filename")
    setting_rows = await AdminRepository(db).list_system_settings()
    settings_summary = {item.key: {"updated_at": item.updated_at, "updated_by": item.updated_by} for item in setting_rows}
    ai_settings_row = next((item for item in setting_rows if item.key == "ai_settings"), None)
    ai_settings = _parse_setting_value(ai_settings_row.value_json) if ai_settings_row else {}
    router9 = ai_settings.get("router9") if isinstance(ai_settings.get("router9"), dict) else {}
    registry = await load_model_registry(db, settings)
    stale_allowed = sum(
        1
        for models in registry.models.values()
        for model in models
        if model.allowed and not model.last_seen_at and model.source == "manual"
    )

    return {
        "backend": getattr(db, "backend", "unknown"),
        "sqlite_path": getattr(db, "path", None),
        "configured_sqlite_path": settings.sqlite_path,
        "migrations": migrations,
        "counts": counts,
        "system_settings": settings_summary,
        "ai_settings": {
            "exists": ai_settings_row is not None,
            "default_provider": ai_settings.get("default_provider"),
            "router9_model": router9.get("model"),
            "router9_only_mode": router9.get("only_mode"),
            "router9_allowed_model_count": len(router9.get("allowed_model_ids") or []),
            "router9_scanned_model_count": len(router9.get("scanned_models") or []),
        },
        "model_registry": {
            "provider_count": len(registry.providers),
            "model_count": sum(len(models) for models in registry.models.values()),
            "allowed_model_count": sum(1 for models in registry.models.values() for model in models if model.allowed),
            "stale_allowed_model_count": stale_allowed,
            "task_profiles": {task: profile.__dict__ for task, profile in registry.task_profiles.items()},
            "legacy_ai_settings_present": registry.legacy_used,
        },
    }


async def sync_ai_profiles_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    profiles = SystemAiProfiles.model_validate(value)
    patch_keys = set(patch or value)
    if "geometry_reasoning" in patch_keys:
        await save_task_profile(db, "reasoning", profiles.geometry_reasoning.provider, profiles.geometry_reasoning.model, profiles.geometry_reasoning.fallbacks)
        await save_task_profile(db, "render", profiles.geometry_reasoning.provider, profiles.geometry_reasoning.model, profiles.geometry_reasoning.fallbacks)
    if "solver_explanation" in patch_keys:
        await save_task_profile(db, "solver_explanation", profiles.solver_explanation.provider, profiles.solver_explanation.model, profiles.solver_explanation.fallbacks)
    if "ocr" in patch_keys:
        await save_task_profile(db, "ocr", profiles.ocr.provider, profiles.ocr.model, profiles.ocr.fallbacks)


async def sync_ai_settings_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    value = normalize_provider_defaults(value)
    patch = normalize_provider_defaults(patch) if patch is not None else None
    ai_settings = SystemAiSettings.model_validate(value)
    patch_data = patch or value
    patch_keys = set(patch_data)
    providers = {
        "openrouter": ai_settings.openrouter,
        "nvidia": ai_settings.nvidia,
        "ollama": ai_settings.ollama,
        "openai_compat": ai_settings.openai_compat,
        "router9": ai_settings.router9,
    }
    for provider_id, provider in providers.items():
        if provider_id not in patch_keys:
            continue
        default_model_id = provider.model
        if provider.allowed_model_ids and default_model_id not in provider.allowed_model_ids:
            default_model_id = provider.allowed_model_ids[0]
        provider_patch = patch_data.get(provider_id) if isinstance(patch_data.get(provider_id), dict) else {}
        env_key = (getattr(get_settings(), f"{provider_id}_api_key", None) or "").strip()
        await save_provider_config(db, provider_id, provider.base_url, default_model_id, api_key_configured=bool(provider.api_key or env_key))
        if "scanned_models" in provider_patch:
            await upsert_scanned_models(db, provider_id, [AiModelInfo.model_validate(model.model_dump() | {"provider": provider_id}) for model in provider.scanned_models])
        if "allowed_model_ids" in provider_patch:
            await set_allowed_models(db, provider_id, provider.allowed_model_ids)
    if "default_provider" in patch_keys:
        await set_model_setting(db, "default_provider", ai_settings.default_provider)
        await save_task_profile(db, "render", ai_settings.default_provider, "", [])
        await save_task_profile(db, "reasoning", ai_settings.default_provider, "", [])
        await save_task_profile(db, "solver_explanation", ai_settings.default_provider, "", [])
    if "router9" in patch_keys:
        await set_model_setting(db, "router9_only", ai_settings.router9.only_mode)
    if "openrouter_reasoning_enabled" in patch_keys:
        await set_model_setting(db, "openrouter_reasoning_enabled", ai_settings.openrouter_reasoning_enabled)
    if "ocr" in patch_keys:
        await set_model_setting(db, "ocr_max_image_mb", ai_settings.ocr.max_image_mb)
        await save_task_profile(db, "ocr", ai_settings.ocr.provider, ai_settings.ocr.model, [])


def normalize_provider_defaults(value: dict | None) -> dict | None:
    if value is None:
        return None
    normalized = dict(value)
    for provider_id in ("openrouter", "nvidia", "ollama", "openai_compat", "router9"):
        provider = normalized.get(provider_id)
        if not isinstance(provider, dict):
            continue
        provider_normalized = dict(provider)
        allowed = provider_normalized.get("allowed_model_ids")
        model = provider_normalized.get("model")
        if isinstance(allowed, list) and allowed and isinstance(model, str) and model and model not in allowed:
            provider_normalized["model"] = str(allowed[0])
        normalized[provider_id] = provider_normalized
    return normalized


def _parse_setting_value(value: str) -> dict:
    import json

    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}
