from __future__ import annotations

import json
from typing import Any

from app.db.session import DatabaseClient
from app.schemas.scene import AiModelInfo


def render_tier_for_task(task: str) -> str | None:
    return task.removeprefix("render_") if task in {"render_tier1", "render_tier2", "render_tier3"} else None


class ModelRegistryRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def has_any_provider(self) -> bool:
        return await self.db.fetch_one("SELECT 1 FROM ai_providers LIMIT 1") is not None

    async def list_providers(self) -> list[Any]:
        return await self.db.fetch_all("SELECT * FROM ai_providers ORDER BY id")

    async def list_models(self) -> list[Any]:
        return await self.db.fetch_all("SELECT * FROM ai_models ORDER BY provider_id, lower(label), lower(id)")

    async def list_task_profiles(self) -> list[Any]:
        return await self.db.fetch_all("SELECT * FROM ai_task_profiles ORDER BY task")

    async def delete_unsupported_tier_profiles(self) -> None:
        await self.db.execute(
            """
            DELETE FROM ai_task_profiles
            WHERE task IN (
              'reasoning_tier1',
              'reasoning_tier2',
              'reasoning_tier3',
              'solver_explanation_tier1',
              'solver_explanation_tier2',
              'solver_explanation_tier3'
            )
            """
        )

    async def delete_legacy_render_profile(self) -> None:
        await self.db.execute("DELETE FROM ai_task_profiles WHERE task = 'render'")

    async def list_model_settings(self) -> list[Any]:
        return await self.db.fetch_all("SELECT key, value_json FROM ai_model_settings")

    async def load_legacy_ai_settings_json(self) -> str | None:
        row = await self.db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", ["ai_settings"])
        return str(row["value_json"]) if row is not None else None

    async def has_legacy_ai_settings(self) -> bool:
        return await self.db.fetch_one("SELECT 1 FROM system_settings WHERE key = ?", ["ai_settings"]) is not None

    async def upsert_provider(self, provider_id: str, label: str, base_url: str, enabled: bool, api_key_configured: bool | None = None) -> None:
        if api_key_configured is None:
            await self.db.execute(
                """
                INSERT INTO ai_providers (id, label, base_url, enabled, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                  base_url = excluded.base_url,
                  enabled = excluded.enabled,
                  updated_at = CURRENT_TIMESTAMP
                """,
                [provider_id, label, base_url, int(enabled)],
            )
            return
        await self.db.execute(
            """
            INSERT INTO ai_providers (id, label, base_url, api_key_configured, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
              base_url = excluded.base_url,
              api_key_configured = excluded.api_key_configured,
              enabled = excluded.enabled,
              updated_at = CURRENT_TIMESTAMP
            """,
            [provider_id, label, base_url, int(api_key_configured), int(enabled)],
        )

    async def insert_seed_provider(self, provider_id: str, label: str, base_url: str, api_key_configured: bool) -> None:
        await self.db.execute(
            """
            INSERT INTO ai_providers (id, label, base_url, api_key_configured, enabled)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
              label = excluded.label,
              base_url = excluded.base_url,
              api_key_configured = excluded.api_key_configured,
              enabled = 1,
              updated_at = CURRENT_TIMESTAMP
            """,
            [provider_id, label, base_url, int(api_key_configured)],
        )

    async def enabled_allowed_model_ids(self, provider_id: str) -> set[str]:
        rows = await self.db.fetch_all("SELECT id FROM ai_models WHERE provider_id = ? AND allowed = 1 AND enabled = 1", [provider_id])
        return {str(row["id"]) for row in rows}

    async def scanned_model_ids(self, provider_id: str) -> set[str]:
        rows = await self.db.fetch_all("SELECT id FROM ai_models WHERE provider_id = ? AND source = 'scan'", [provider_id])
        return {str(row["id"]) for row in rows}

    async def disable_scanned_model(self, provider_id: str, model_id: str) -> None:
        await self.db.execute(
            """
            UPDATE ai_models
            SET enabled = 0, allowed = 0, updated_at = CURRENT_TIMESTAMP
            WHERE provider_id = ? AND source = 'scan' AND id = ?
            """,
            [provider_id, model_id],
        )

    async def upsert_model(self, provider_id: str, model: AiModelInfo, allowed: bool, source: str) -> None:
        await self.db.execute(
            """
            INSERT INTO ai_models (
              provider_id, id, label, owned_by, context_length, capabilities_json,
              is_free_endpoint, supports_thinking, supports_vision, pricing_json,
              endpoint_metadata_json, supported_parameters_json,
              source, enabled, allowed, last_seen_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(provider_id, id) DO UPDATE SET
              label = excluded.label,
              owned_by = excluded.owned_by,
              context_length = excluded.context_length,
              capabilities_json = excluded.capabilities_json,
              is_free_endpoint = excluded.is_free_endpoint,
              supports_thinking = excluded.supports_thinking,
              supports_vision = excluded.supports_vision,
              pricing_json = excluded.pricing_json,
              endpoint_metadata_json = excluded.endpoint_metadata_json,
              supported_parameters_json = excluded.supported_parameters_json,
              source = excluded.source,
              enabled = 1,
              last_seen_at = CURRENT_TIMESTAMP,
              updated_at = CURRENT_TIMESTAMP
            """,
            [
                provider_id,
                model.id,
                model.label or model.id,
                model.owned_by,
                model.context_length,
                json.dumps(model.capabilities, ensure_ascii=False, sort_keys=True),
                int(model.is_free_endpoint),
                int(model.supports_thinking),
                int(model.supports_vision),
                json.dumps(model.pricing, ensure_ascii=False, sort_keys=True),
                json.dumps(model.endpoint_metadata, ensure_ascii=False, sort_keys=True),
                json.dumps(model.supported_parameters, ensure_ascii=False, sort_keys=True),
                source,
                int(allowed),
            ],
        )

    async def clear_allowed_models(self, provider_id: str) -> None:
        await self.db.execute("UPDATE ai_models SET allowed = 0 WHERE provider_id = ?", [provider_id])

    async def allow_model(self, provider_id: str, model_id: str) -> None:
        await self.db.execute(
            """
            INSERT INTO ai_models (
              provider_id, id, label, capabilities_json, pricing_json, endpoint_metadata_json,
              supported_parameters_json, source, enabled, allowed, updated_at
            )
            VALUES (?, ?, ?, '{}', '{}', '{}', '[]', 'manual', 1, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(provider_id, id) DO UPDATE SET allowed = 1, enabled = 1, updated_at = CURRENT_TIMESTAMP
            """,
            [provider_id, model_id, model_id],
        )

    async def delete_unallowed_manual_models(self, provider_id: str) -> None:
        await self.db.execute(
            "DELETE FROM ai_models WHERE provider_id = ? AND source = 'manual' AND allowed = 0",
            [provider_id],
        )

    async def record_model_scan_job(
        self,
        scan_id: str,
        user_id: str,
        provider_id: str,
        base_url: str,
        runtime_json: dict[str, Any],
        models: list[AiModelInfo],
        warnings: list[str],
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO model_scan_jobs (
              id, user_id, provider, status, models_json, runtime_json, base_url,
              result_count, free_count, thinking_count, warnings_json,
              created_at, started_at, finished_at, updated_at
            )
            VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [
                scan_id,
                user_id,
                provider_id,
                json.dumps([model.model_dump() for model in models], ensure_ascii=False, sort_keys=True),
                json.dumps(runtime_json, ensure_ascii=False, sort_keys=True),
                base_url,
                len(models),
                sum(1 for model in models if model.is_free_endpoint),
                sum(1 for model in models if model.supports_thinking),
                json.dumps(warnings, ensure_ascii=False, sort_keys=True),
            ],
        )
        for model in models:
            await self.db.execute(
                """
                INSERT INTO model_scan_job_models (
                  scan_id, provider_id, model_id, label, is_free_endpoint, supports_thinking,
                  supports_vision, context_length, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    scan_id,
                    provider_id,
                    model.id,
                    model.label,
                    int(model.is_free_endpoint),
                    int(model.supports_thinking),
                    int(model.supports_vision),
                    model.context_length,
                    json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True),
                ],
            )

    async def update_provider_check(self, provider_id: str, status: str, message: str) -> None:
        await self.db.execute(
            "UPDATE ai_providers SET last_checked_at = CURRENT_TIMESTAMP, last_check_status = ?, last_check_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [status, message[:1000], provider_id],
        )

    async def upsert_task_profile(self, task: str, provider_id: str, model_id: str, fallbacks: list[str]) -> None:
        tier = render_tier_for_task(task)
        await self.db.execute(
            """
            INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(task) DO UPDATE SET
              provider_id = excluded.provider_id,
              model_id = excluded.model_id,
              fallbacks_json = excluded.fallbacks_json,
              tier = excluded.tier,
              updated_at = CURRENT_TIMESTAMP
            """,
            [task, provider_id, model_id, json.dumps(fallbacks), tier],
        )

    async def task_profile_exists(self, task: str) -> bool:
        return await self.db.fetch_one("SELECT 1 FROM ai_task_profiles WHERE task = ?", [task]) is not None

    async def canonical_task_profile_rows(self) -> list[Any]:
        return await self.db.fetch_all("SELECT task, provider_id, model_id, fallbacks_json FROM ai_task_profiles ORDER BY task")

    async def update_task_profile(self, task: str, provider_id: str, model_id: str, fallbacks: list[str]) -> None:
        await self.db.execute(
            """
            UPDATE ai_task_profiles
            SET provider_id = ?, model_id = ?, fallbacks_json = ?, tier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task = ?
            """,
            [provider_id, model_id, json.dumps(fallbacks), render_tier_for_task(task), task],
        )

    async def set_model_setting(self, key: str, value: Any) -> None:
        await self.db.execute(
            """
            INSERT INTO ai_model_settings (key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
            """,
            [key, json.dumps(value)],
        )

    async def ensure_provider(self, provider_id: str, label: str) -> None:
        await self.db.execute("INSERT INTO ai_providers (id, label) VALUES (?, ?) ON CONFLICT(id) DO NOTHING", [provider_id, label])
