from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import Settings
from app.services.provider_logging import redact_sensitive
from app.services.router9_bootstrap import select_router9_ocr_model_ids_from_ids, select_router9_render_model_ids_from_ids

OPENROUTER_GPT_OSS_MODEL = "openai/gpt-oss-120b:free"


@dataclass(frozen=True)
class Attempt:
    provider: str
    model: str
    task: str
    error: str

    def warning(self) -> str:
        return f"{self.provider}/{self.model}: {_short_error(self.error)}"


def text_provider_order(settings: Settings, preferred_provider: str | None = None) -> list[str]:
    if settings.router9_only:
        if preferred_provider and preferred_provider != "router9":
            raise RuntimeError("9router-only đang bật nên không fallback sang provider khác.")
        return ["router9"]

    provider = preferred_provider or settings.ai_provider or "auto"
    router9 = ["router9"] if settings.router9_api_key else []
    openrouter = ["openrouter"] if settings.openrouter_api_key else []
    nvidia = ["nvidia"] if settings.nvidia_api_key else []
    custom = ["openai_compat"] if settings.openai_compat_api_key and settings.openai_compat_text_model else []
    ollama = ["ollama_gpt_oss"]

    if provider == "router9":
        return dedupe([*router9, *openrouter, *nvidia, *custom, *ollama])
    if provider == "openrouter":
        return dedupe([*openrouter, *router9, *nvidia, *custom, *ollama])
    if provider == "nvidia":
        return dedupe([*nvidia, *router9, *openrouter, *custom, *ollama])
    if provider == "openai_compat":
        return dedupe([*custom, *router9, *openrouter, *nvidia, *ollama])
    if provider == "ollama_gpt_oss":
        return dedupe([*ollama, *router9, *openrouter, *nvidia, *custom])
    return dedupe([*router9, *nvidia, *openrouter, *custom, *ollama])


def text_model_candidates(provider: str, settings: Settings, explicit_model: str | None = None) -> list[str | None]:
    if provider == "router9":
        if explicit_model:
            return [explicit_model]
        if settings.router9_allowed_models:
            return router9_text_candidates(settings)
        return dedupe([settings.router9_text_model or "", *settings.router9_text_fallback_models])
    if provider == "openrouter":
        if explicit_model:
            return [explicit_model]
        return openrouter_text_candidates(settings)
    if provider == "nvidia":
        return [explicit_model or settings.nvidia_text_model]
    if provider == "openai_compat":
        return [explicit_model or settings.openai_compat_text_model or None]
    if provider == "ollama_gpt_oss":
        return [explicit_model or settings.ollama_text_model]
    return [explicit_model]


def router9_text_candidates(settings: Settings) -> list[str]:
    if settings.router9_allowed_models:
        candidates = dedupe([
            settings.router9_text_model or "",
            *select_router9_render_model_ids_from_ids(settings.router9_allowed_models),
            *settings.router9_allowed_models,
        ])
        return [model for model in candidates if model in settings.router9_allowed_models]
    return dedupe([settings.router9_text_model or "", *settings.router9_text_fallback_models])


def router9_ocr_candidates(settings: Settings, explicit_model: str | None = None) -> list[str]:
    if explicit_model:
        return [explicit_model]
    if settings.router9_allowed_models:
        candidates = dedupe([
            settings.router9_ocr_model or "",
            *select_router9_ocr_model_ids_from_ids(settings.router9_allowed_models),
            *settings.router9_allowed_models,
        ])
        return [model for model in candidates if model in settings.router9_allowed_models]
    return dedupe([settings.router9_ocr_model or "", *settings.router9_ocr_fallback_models])


def openrouter_text_candidates(settings: Settings, explicit_model: str | None = None) -> list[str]:
    if explicit_model:
        return [explicit_model]
    return dedupe([settings.openrouter_text_model, OPENROUTER_GPT_OSS_MODEL])


def openrouter_vision_candidates(settings: Settings, explicit_model: str | None = None) -> list[str]:
    if explicit_model:
        return [explicit_model]
    return dedupe([settings.openrouter_vision_model, settings.openrouter_vision_fallback_model])


def dedupe(models: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def format_attempts(attempts: list[Attempt]) -> str:
    return " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", redact_sensitive(message)).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")
