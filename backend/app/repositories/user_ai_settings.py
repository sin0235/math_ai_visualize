from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.db.models import DbRow
from app.db.session import DatabaseClient


@dataclass(frozen=True)
class UserAiProviderSettingsRecord:
    user_id: str
    enabled: bool
    base_url: str
    api_key_ciphertext: str | None
    api_key_last4: str | None
    api_key_updated_at: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class UserAiModelRecord:
    id: str
    user_id: str
    model_id: str
    label: str
    supports_vision: bool
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class UserAiTaskProfileRecord:
    user_id: str
    task: str
    model_id: str
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


class UserAiSettingsRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def get_provider_settings(self, user_id: str) -> UserAiProviderSettingsRecord | None:
        row = await self.db.fetch_one("SELECT * FROM user_ai_provider_settings WHERE user_id = ?", [user_id])
        return provider_settings_from_row(row) if row else None

    async def upsert_provider_settings(
        self,
        user_id: str,
        *,
        enabled: bool,
        base_url: str,
        api_key_ciphertext: str | None,
        api_key_last4: str | None,
        update_api_key: bool,
    ) -> UserAiProviderSettingsRecord:
        existing = await self.get_provider_settings(user_id)
        if existing is None:
            await self.db.execute(
                """
                INSERT INTO user_ai_provider_settings (
                  user_id, enabled, base_url, api_key_ciphertext, api_key_last4, api_key_updated_at
                ) VALUES (?, ?, ?, ?, ?, CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END)
                """,
                [user_id, 1 if enabled else 0, base_url, api_key_ciphertext, api_key_last4, api_key_ciphertext],
            )
        elif update_api_key:
            await self.db.execute(
                """
                UPDATE user_ai_provider_settings
                SET enabled = ?, base_url = ?, api_key_ciphertext = ?, api_key_last4 = ?,
                    api_key_updated_at = CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                [1 if enabled else 0, base_url, api_key_ciphertext, api_key_last4, api_key_ciphertext, user_id],
            )
        else:
            await self.db.execute(
                """
                UPDATE user_ai_provider_settings
                SET enabled = ?, base_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                [1 if enabled else 0, base_url, user_id],
            )
        record = await self.get_provider_settings(user_id)
        if record is None:
            raise RuntimeError("Không thể lưu cấu hình BYOK.")
        return record

    async def list_models(self, user_id: str) -> list[UserAiModelRecord]:
        rows = await self.db.fetch_all("SELECT * FROM user_ai_models WHERE user_id = ? ORDER BY created_at ASC, model_id ASC", [user_id])
        return [model_from_row(row) for row in rows]

    async def replace_models(self, user_id: str, models: list[dict]) -> list[UserAiModelRecord]:
        statements: list[tuple[str, list | tuple | None]] = []
        model_ids: list[str] = []
        for model in models:
            model_id = model["model_id"]
            model_ids.append(model_id)
            statements.append((
                """
                INSERT INTO user_ai_models (id, user_id, model_id, label, supports_vision, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, model_id) DO UPDATE SET
                  label = excluded.label,
                  supports_vision = excluded.supports_vision,
                  enabled = excluded.enabled,
                  updated_at = CURRENT_TIMESTAMP
                """,
                [uuid4().hex, user_id, model_id, model.get("label") or model_id, 1 if model.get("supports_vision") else 0, 1 if model.get("enabled", True) else 0],
            ))
        if model_ids:
            placeholders = ", ".join("?" for _ in model_ids)
            statements.append((f"DELETE FROM user_ai_models WHERE user_id = ? AND model_id NOT IN ({placeholders})", [user_id, *model_ids]))
        else:
            statements.append(("DELETE FROM user_ai_models WHERE user_id = ?", [user_id]))
        await self.db.execute_many(statements)
        return await self.list_models(user_id)

    async def list_task_profiles(self, user_id: str) -> list[UserAiTaskProfileRecord]:
        rows = await self.db.fetch_all("SELECT * FROM user_ai_task_profiles WHERE user_id = ? ORDER BY task ASC", [user_id])
        return [task_profile_from_row(row) for row in rows]

    async def replace_task_profiles(self, user_id: str, profiles: list[dict]) -> list[UserAiTaskProfileRecord]:
        statements: list[tuple[str, list | tuple | None]] = []
        tasks: list[str] = []
        for profile in profiles:
            task = profile["task"]
            tasks.append(task)
            statements.append((
                """
                INSERT INTO user_ai_task_profiles (user_id, task, model_id, enabled, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, task) DO UPDATE SET
                  model_id = excluded.model_id,
                  enabled = excluded.enabled,
                  updated_at = CURRENT_TIMESTAMP
                """,
                [user_id, task, profile["model_id"], 1 if profile.get("enabled", True) else 0],
            ))
        if tasks:
            placeholders = ", ".join("?" for _ in tasks)
            statements.append((f"DELETE FROM user_ai_task_profiles WHERE user_id = ? AND task NOT IN ({placeholders})", [user_id, *tasks]))
        else:
            statements.append(("DELETE FROM user_ai_task_profiles WHERE user_id = ?", [user_id]))
        await self.db.execute_many(statements)
        return await self.list_task_profiles(user_id)



def provider_settings_from_row(row: DbRow) -> UserAiProviderSettingsRecord:
    return UserAiProviderSettingsRecord(
        user_id=str(row["user_id"]),
        enabled=bool(row.get("enabled") or 0),
        base_url=str(row.get("base_url") or ""),
        api_key_ciphertext=str(row["api_key_ciphertext"]) if row.get("api_key_ciphertext") is not None else None,
        api_key_last4=str(row["api_key_last4"]) if row.get("api_key_last4") is not None else None,
        api_key_updated_at=str(row["api_key_updated_at"]) if row.get("api_key_updated_at") is not None else None,
        created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") is not None else None,
    )


def model_from_row(row: DbRow) -> UserAiModelRecord:
    return UserAiModelRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        model_id=str(row["model_id"]),
        label=str(row.get("label") or row["model_id"]),
        supports_vision=bool(row.get("supports_vision") or 0),
        enabled=bool(row.get("enabled") or 0),
        created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") is not None else None,
    )


def task_profile_from_row(row: DbRow) -> UserAiTaskProfileRecord:
    return UserAiTaskProfileRecord(
        user_id=str(row["user_id"]),
        task=str(row["task"]),
        model_id=str(row["model_id"]),
        enabled=bool(row.get("enabled") or 0),
        created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") is not None else None,
    )
