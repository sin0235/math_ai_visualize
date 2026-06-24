from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient
from app.services.openai_compat_client import OpenAICompatClient
from app.services.user_ai_settings import ByokResolvedTask, UserAiSettingsError, resolve_byok_task


@dataclass(frozen=True)
class ResolvedAiConfig:
    source: str
    provider: str
    model_id: str
    client: OpenAICompatClient | None = None
    supports_vision: bool = False
    settings_override: Settings | None = None

    @property
    def is_byok(self) -> bool:
        return self.source == "byok"


async def resolve_byok_ai_config(db: DatabaseClient, user: UserRecord | None, task: str, settings: Settings) -> ResolvedAiConfig | None:
    if user is None:
        return None
    resolved = await resolve_byok_task(db, user.id, task, settings)
    if resolved is None:
        return None
    return ai_config_from_byok_task(resolved, settings)


def ai_config_from_byok_task(task: ByokResolvedTask, settings: Settings) -> ResolvedAiConfig:
    settings_override = settings.model_copy(update={
        "ai_provider": "openai_compat",
        "openai_compat_base_url": task.base_url,
        "openai_compat_api_key": task.api_key,
        "openai_compat_text_model": task.model_id,
    })
    return ResolvedAiConfig(
        source="byok",
        provider="openai_compat",
        model_id=task.model_id,
        client=OpenAICompatClient.from_connection(base_url=task.base_url, api_key=task.api_key, model=task.model_id),
        supports_vision=task.supports_vision,
        settings_override=settings_override,
    )


def settings_with_byok_connection(settings: Settings, byok: ResolvedAiConfig) -> Settings:
    if byok.settings_override is None:
        raise RuntimeError("BYOK thiếu cấu hình kết nối.")
    return byok.settings_override


def byok_config_error(error: UserAiSettingsError) -> RuntimeError:
    return RuntimeError(f"Cấu hình BYOK không hợp lệ: {error}")
