from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.db.migrations import build_migration_drift
from app.db.session import DatabaseClient, sqlite_path_diagnostics
from app.repositories.admin import AdminRepository
from app.schemas.auth import SystemAiProfiles, SystemAiSettings
from app.schemas.scene import AiModelInfo
from app.services.model_provider import normalize_provider_defaults, parse_provider_model_ref
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
    "model_scan_jobs",
    "uploaded_files",
    "chat_conversations",
    "chat_messages",
    "feedback",
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
    migration_drift = await build_migration_drift(db)
    uploaded_files_storage = await build_uploaded_files_storage_diagnostics(db)
    setting_rows = await AdminRepository(db).list_system_settings()
    settings_summary = {item.key: {"updated_at": item.updated_at, "updated_by": item.updated_by} for item in setting_rows}
    ai_settings_row = next((item for item in setting_rows if item.key == "ai_settings"), None)
    ai_settings = _parse_setting_value(ai_settings_row.value_json) if ai_settings_row else {}
    router9 = ai_settings.get("router9") if isinstance(ai_settings.get("router9"), dict) else {}
    registry = await load_model_registry(db, settings)
    ai_settings_drift = build_ai_settings_drift(ai_settings, registry)
    stale_allowed = sum(
        1
        for models in registry.models.values()
        for model in models
        if model.allowed and not model.last_seen_at and model.source == "manual"
    )

    sqlite_diagnostics = sqlite_path_diagnostics(settings.sqlite_path)
    return {
        "backend": getattr(db, "backend", "unknown"),
        "sqlite_path": getattr(db, "path", None),
        "configured_sqlite_path": settings.sqlite_path,
        "resolved_sqlite_path": sqlite_diagnostics["resolved_path"],
        "sqlite_path_diagnostics": sqlite_diagnostics,
        "migration_drift": migration_drift,
        "migrations": migrations,
        "counts": counts,
        "uploaded_files_storage": uploaded_files_storage,
        "system_settings": settings_summary,
        "ai_settings": {
            "exists": ai_settings_row is not None,
            "default_provider": ai_settings.get("default_provider"),
            "router9_model": router9.get("model"),
            "router9_only_mode": router9.get("only_mode"),
            "router9_allowed_model_count": len(router9.get("allowed_model_ids") or []),
            "router9_scanned_model_count": len(router9.get("scanned_models") or []),
            "legacy_canonical_drift": ai_settings_drift,
        },
        "model_registry": {
            "provider_count": len(registry.providers),
            "model_count": sum(len(models) for models in registry.models.values()),
            "allowed_model_count": sum(1 for models in registry.models.values() for model in models if model.allowed),
            "stale_allowed_model_count": stale_allowed,
            "task_profiles": {task: profile.__dict__ for task, profile in registry.task_profiles.items()},
            "legacy_ai_settings_present": registry.legacy_used,
            "canonical_registry_active": bool(registry.providers),
        },
    }


async def build_uploaded_files_storage_diagnostics(db: DatabaseClient) -> dict[str, Any]:
    try:
        total_row = await db.fetch_one("SELECT COUNT(*) AS count FROM uploaded_files")
        provider_rows = await db.fetch_all(
            """
            SELECT COALESCE(storage_provider, 'database') AS provider, COUNT(*) AS count
            FROM uploaded_files
            GROUP BY COALESCE(storage_provider, 'database')
            """
        )
        stats_row = await db.fetch_one(
            """
            SELECT
              SUM(CASE WHEN data_base64 IS NOT NULL AND data_base64 != '' THEN 1 ELSE 0 END) AS rows_with_base64,
              SUM(CASE WHEN storage_provider IN ('appwrite', 'r2') AND data_base64 IS NOT NULL AND data_base64 != '' THEN 1 ELSE 0 END) AS external_rows_with_base64,
              SUM(CASE WHEN storage_provider IN ('appwrite', 'r2') AND (data_base64 IS NULL OR data_base64 = '') THEN 1 ELSE 0 END) AS external_only_rows,
              SUM(CASE WHEN COALESCE(storage_provider, 'database') = 'database' THEN 1 ELSE 0 END) AS database_provider_rows,
              SUM(CASE WHEN data_base64 IS NOT NULL AND data_base64 != '' THEN LENGTH(data_base64) ELSE 0 END) AS base64_chars,
              SUM(CASE WHEN storage_provider IN ('appwrite', 'r2') AND data_base64 IS NOT NULL AND data_base64 != '' THEN 1 ELSE 0 END) AS default_cleanup_candidates,
              SUM(CASE WHEN storage_provider IN ('appwrite', 'r2') AND data_base64 IS NOT NULL AND data_base64 != '' THEN LENGTH(data_base64) ELSE 0 END) AS default_cleanup_base64_chars
            FROM uploaded_files
            """
        )
    except Exception as error:
        return {"error": str(error)}

    base64_chars = int((stats_row or {}).get("base64_chars") or 0)
    cleanup_base64_chars = int((stats_row or {}).get("default_cleanup_base64_chars") or 0)
    return {
        "total_rows": int((total_row or {}).get("count") or 0),
        "rows_by_provider": {str(row["provider"]): int(row["count"] or 0) for row in provider_rows},
        "rows_with_base64": int((stats_row or {}).get("rows_with_base64") or 0),
        "external_rows_with_base64": int((stats_row or {}).get("external_rows_with_base64") or 0),
        "external_only_rows": int((stats_row or {}).get("external_only_rows") or 0),
        "database_provider_rows": int((stats_row or {}).get("database_provider_rows") or 0),
        "base64_chars": base64_chars,
        "estimated_inline_bytes": base64_chars * 3 // 4,
        "default_cleanup_candidates": int((stats_row or {}).get("default_cleanup_candidates") or 0),
        "default_cleanup_reclaimable_bytes": cleanup_base64_chars * 3 // 4,
    }


async def sync_ai_profiles_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    profiles = SystemAiProfiles.model_validate(value)
    patch_keys = set(patch or value)
    if "geometry_reasoning" in patch_keys:
        await save_task_profile(db, "render", profiles.geometry_reasoning.provider, profiles.geometry_reasoning.model, profiles.geometry_reasoning.fallbacks)
        await save_task_profile(db, "reasoning", profiles.geometry_reasoning.provider, profiles.geometry_reasoning.model, profiles.geometry_reasoning.fallbacks)
    if "solver_explanation" in patch_keys:
        await save_task_profile(db, "solver_explanation", profiles.solver_explanation.provider, profiles.solver_explanation.model, profiles.solver_explanation.fallbacks)
    if "ocr" in patch_keys:
        await save_task_profile(db, "ocr", profiles.ocr.provider, profiles.ocr.model, profiles.ocr.fallbacks)


async def sync_ai_tier_profiles_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    """Đồng bộ tier model dựng hình từ admin UI vào ai_task_profiles."""
    from app.schemas.auth import SystemAiTierProfiles

    profiles = SystemAiTierProfiles.model_validate(value)
    from app.repositories.model_registry import ModelRegistryRepository

    await ModelRegistryRepository(db).delete_unsupported_tier_profiles()

    for tier_name in ["tier1", "tier2", "tier3"]:
        tier_profile = getattr(profiles, tier_name)
        primary = tier_profile.default_model or (tier_profile.models[0] if tier_profile.models else "")
        if not primary:
            await save_task_profile(db, f"render_{tier_name}", "auto", "", [])
            continue
        primary_ref = parse_provider_model_ref(primary, allow_legacy_slash=False)
        if primary_ref is None:
            raise ValueError("Tier profile phải dùng model ref provider::model.")
        fallbacks = [model for model in tier_profile.models if model != primary]
        await save_task_profile(
            db,
            f"render_{tier_name}",
            primary_ref.provider_id,
            primary_ref.model_id,
            fallbacks,
        )


async def sync_ai_settings_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    current_settings = get_settings()
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
        env_key = (getattr(current_settings, f"{provider_id}_api_key", None) or "").strip()
        await save_provider_config(db, provider_id, provider.base_url, default_model_id, api_key_configured=bool(provider.api_key or env_key))
        if "scanned_models" in provider_patch:
            await upsert_scanned_models(db, provider_id, [AiModelInfo.model_validate(model.model_dump() | {"provider": provider_id}) for model in provider.scanned_models])
        if "allowed_model_ids" in provider_patch:
            await set_allowed_models(db, provider_id, provider.allowed_model_ids)
    if "default_provider" in patch_keys:
        await set_model_setting(db, "default_provider", ai_settings.default_provider)
    if "router9" in patch_keys:
        await set_model_setting(db, "router9_only", ai_settings.router9.only_mode)
    if "openrouter_reasoning_enabled" in patch_keys:
        await set_model_setting(db, "openrouter_reasoning_enabled", ai_settings.openrouter_reasoning_enabled)
    if "ocr" in patch_keys:
        await set_model_setting(db, "ocr_max_image_mb", ai_settings.ocr.max_image_mb)
        registry = await load_model_registry(db, current_settings)
        fallbacks = registry.task_profiles.get("ocr").fallbacks if registry.task_profiles.get("ocr") else []
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
            ["ocr", ai_settings.ocr.provider, ai_settings.ocr.model, json.dumps(fallbacks)],
        )


def build_ai_settings_drift(ai_settings: dict, registry: Any) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    if not ai_settings:
        return {"ok": True, "differences": []}

    default_provider = ai_settings.get("default_provider")
    registry_default = registry.settings.get("default_provider")
    if isinstance(default_provider, str) and default_provider and default_provider != registry_default:
        differences.append({"field": "default_provider", "legacy": default_provider, "canonical": registry_default})

    router9 = ai_settings.get("router9") if isinstance(ai_settings.get("router9"), dict) else {}
    router9_only = router9.get("only_mode")
    registry_router9_only = registry.settings.get("router9_only")
    if router9_only is not None and bool(router9_only) != bool(registry_router9_only):
        differences.append({"field": "router9.only_mode", "legacy": bool(router9_only), "canonical": bool(registry_router9_only)})

    for provider_id in ("openrouter", "nvidia", "ollama", "openai_compat", "router9"):
        provider_settings = ai_settings.get(provider_id) if isinstance(ai_settings.get(provider_id), dict) else {}
        provider = registry.providers.get(provider_id)
        if not provider_settings or provider is None:
            continue
        legacy_base_url = provider_settings.get("base_url")
        if isinstance(legacy_base_url, str) and legacy_base_url and legacy_base_url != provider.base_url:
            differences.append({"field": f"{provider_id}.base_url", "legacy": legacy_base_url, "canonical": provider.base_url})
        legacy_model = provider_settings.get("model")
        if isinstance(legacy_model, str) and legacy_model and legacy_model != provider.default_model_id:
            differences.append({"field": f"{provider_id}.model", "legacy": legacy_model, "canonical": provider.default_model_id})

    ocr = ai_settings.get("ocr") if isinstance(ai_settings.get("ocr"), dict) else {}
    ocr_profile = registry.task_profiles.get("ocr")
    if ocr and ocr_profile is not None:
        legacy_provider = ocr.get("provider")
        legacy_model = ocr.get("model")
        if isinstance(legacy_provider, str) and legacy_provider and legacy_provider != ocr_profile.provider_id:
            differences.append({"field": "ocr.provider", "legacy": legacy_provider, "canonical": ocr_profile.provider_id})
        if isinstance(legacy_model, str) and legacy_model and legacy_model != ocr_profile.model_id:
            differences.append({"field": "ocr.model", "legacy": legacy_model, "canonical": ocr_profile.model_id})

    return {"ok": not differences, "differences": differences[:50]}


def _parse_setting_value(value: str) -> dict:
    import json

    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}
