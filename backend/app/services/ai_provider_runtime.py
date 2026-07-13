"""Shared AI provider runtime for geometry extract (Scene v3).

Extracted from the legacy MathScene extractor so production paths no longer
depend on CAS / v2 scene pipeline. Provider clients, budget, reasoning, and
fallback ordering live here.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.config import Settings
from app.services.ai_fallback import explicit_model_for_provider, provider_configured, text_model_candidates
from app.services.nvidia_client import NvidiaClient
from app.services.ollama_client import OllamaClient
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import OpenRouterClient
from app.services.router9_bootstrap import select_router9_render_model_ids_from_ids
from app.services.router9_client import Router9Client
from app.services.provider_logging import redact_sensitive
from app.services.model_provider import canonical_provider_id
from app.services.model_registry import ModelRegistry

_provider_attempt_logger = logging.getLogger("app.services.ai_providers")

_RENDER_TOTAL_BUDGET_SECONDS = 300.0
_RENDER_MIN_ATTEMPT_SECONDS = 10.0
_RENDER_MAX_ATTEMPT_SECONDS = 285.0
_REASONING_TOTAL_TIMEOUT_SECONDS = 120.0
_provider_attempt_logger = logging.getLogger("app.services.ai_providers")

@dataclass(frozen=True)
class RenderAttempt:
    provider: str
    model: str
    message: str

    def warning(self) -> str:
        return f"{self.provider}/{self.model}: {_short_error(self.message)}"


RenderFallbackSource = Literal["none", "mock", "provider_fallback"]

async def _run_reasoning_stage(
    settings: Settings,
    problem_text: str,
    grade: int | None,
    preferred_ai_provider: str | None,
    preferred_ai_model: str | None,
    warnings: list[str],
    system_prompt: str | None = None,
    model_supports_thinking: bool | None = None,
    thinking_enabled: bool | None = None,
) -> dict | None:
    """Run the reasoning layer (Task 1) and return the reasoning plan.

    Returns None if reasoning fails (the pipeline will fall back to
    single-stage extraction).
    Giới hạn tối đa 1 lần thử và timeout riêng để không kéo dài pipeline quá mức.
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    _MAX_REASONING_ATTEMPTS = 1
    async def _try_reasoning() -> dict | None:
        attempts = 0
        requested_provider = preferred_ai_provider or settings.ai_provider
        for provider in _provider_order(settings, preferred_ai_provider):
            explicit_model = preferred_ai_model if provider == requested_provider else None
            for model in _provider_model_candidates(provider, settings, explicit_model):
                if attempts >= _MAX_REASONING_ATTEMPTS:
                    return None
                attempts += 1
                try:
                    plan = await _reason_with_provider(
                        provider,
                        settings,
                        problem_text,
                        grade,
                        model,
                        system_prompt=system_prompt,
                        model_supports_thinking=model_supports_thinking if provider == requested_provider and model == preferred_ai_model else None,
                        thinking_enabled=thinking_enabled,
                    )
                    if isinstance(plan, dict):
                        from app.schemas.ai_reasoning import SceneReasoningPlan

                        validated = SceneReasoningPlan.model_validate(plan)
                        if validated.problem_analysis.original_text != problem_text:
                            raise ValueError("Reasoning plan đã thay đổi đề bài gốc.")
                        if grade is not None and validated.problem_analysis.grade != grade:
                            raise ValueError("Reasoning plan đã thay đổi lớp học được yêu cầu.")
                        logger.info("Reasoning stage succeeded via %s/%s", provider, model)
                        return validated.model_dump(mode="json")
                except Exception as error:
                    logger.warning("Reasoning stage failed via %s/%s: %s", provider, model, error)
                    warnings.append(f"Tầng suy luận lỗi ({provider}/{model}): {_short_error(str(error))}")
                    continue
        return None

    try:
        result = await asyncio.wait_for(_try_reasoning(), timeout=_REASONING_TOTAL_TIMEOUT_SECONDS)
        if result is None:
            warnings.append("Tầng suy luận không thành công; sẽ dùng single-stage extraction.")
        return result
    except asyncio.TimeoutError:
        warnings.append(f"Tầng suy luận quá thời gian ({_REASONING_TOTAL_TIMEOUT_SECONDS:.0f}s); sẽ dùng single-stage extraction.")
        return None

def _fast_provider_order(settings: Settings, preferred_ai_provider: str | None = None) -> list[str]:
    return _provider_order(settings, preferred_ai_provider, explicit=preferred_ai_provider is not None)


def _render_provider_order(settings: Settings, preferred_ai_provider: str | None, strict: bool) -> list[str]:
    provider = canonical_provider_id(preferred_ai_provider)
    if strict:
        if settings.router9_only and provider != "router9":
            raise RuntimeError("9router-only đang bật nên chỉ được dùng model 9router.")
        if provider in {None, "auto", "mock"}:
            return []
        return [provider]
    return _fast_provider_order(settings, preferred_ai_provider)


def _provider_order(settings: Settings, preferred_ai_provider: str | None = None, *, explicit: bool | None = None) -> list[str]:
    if explicit is None:
        explicit = preferred_ai_provider is not None
    provider = canonical_provider_id(preferred_ai_provider) or canonical_provider_id(settings.ai_provider)
    router9_providers = ["router9"] if provider_configured(settings.router9_api_key) else []
    nvidia_providers = ["nvidia"] if provider_configured(settings.nvidia_api_key) else []
    custom_providers = ["openai_compat"] if provider_configured(settings.openai_compat_api_key) and settings.openai_compat_text_model else []
    openrouter_providers = ["openrouter"] if provider_configured(settings.openrouter_api_key) else []
    local_providers = ["ollama"]
    if settings.router9_only:
        if provider not in {"auto", "router9"}:
            raise RuntimeError("9router-only đang bật nên chỉ được dùng model 9router.")
        return router9_providers or ["router9"]
    if provider == "mock":
        return []
    if provider == "router9":
        requested = ["router9"] if explicit else []
        return _dedupe([*requested, *router9_providers, *openrouter_providers, *nvidia_providers, *custom_providers, *local_providers])
    if provider == "openai_compat":
        requested = ["openai_compat"] if explicit else []
        return _dedupe([*requested, *custom_providers, *router9_providers, *nvidia_providers, *openrouter_providers, *local_providers])
    if provider == "nvidia":
        requested = ["nvidia"] if explicit else []
        return _dedupe([*requested, *nvidia_providers, *router9_providers, *openrouter_providers, *custom_providers, *local_providers])
    if provider in {"openrouter", "opencode_nemotron", "openrouter_gpt_oss"}:
        requested = [provider] if explicit else []
        return _dedupe([*requested, *openrouter_providers, *router9_providers, *nvidia_providers, *custom_providers, *local_providers])
    if provider == "ollama":
        return _dedupe([*local_providers, *router9_providers, *openrouter_providers, *nvidia_providers, *custom_providers])
    return _dedupe([*router9_providers, *nvidia_providers, *openrouter_providers, *custom_providers, *local_providers])


def _provider_model(provider: str, settings: Settings, preferred_ai_model: str | None = None) -> str:
    provider = canonical_provider_id(provider) or provider
    if provider == "router9":
        return preferred_ai_model or settings.router9_text_model or "<none>"
    if provider == "openrouter":
        return preferred_ai_model or settings.openrouter_text_model
    if provider == "ollama":
        return preferred_ai_model or settings.ollama_text_model
    if provider == "nvidia":
        return preferred_ai_model or settings.nvidia_text_model
    if provider == "openai_compat":
        return preferred_ai_model or settings.openai_compat_text_model or "<none>"
    return "<unknown>"


def _provider_model_candidates(provider: str, settings: Settings, preferred_ai_model: str | None = None) -> list[str | None]:
    provider = canonical_provider_id(provider) or provider
    if provider == "router9":
        return _router9_model_candidates(settings, preferred_ai_model)
    if provider in {"openrouter", "nvidia", "ollama", "openai_compat"}:
        return text_model_candidates(provider, settings, preferred_ai_model)
    return [None]





def _profile_model_candidates(profile: Any, provider: str, settings: Settings, preferred_ai_model: str | None = None) -> list[str | None]:
    provider = canonical_provider_id(provider) or provider
    candidates = _provider_model_candidates(provider, settings, preferred_ai_model)
    profile_provider = canonical_provider_id(profile.provider_id) if profile is not None else None
    if preferred_ai_model:
        return _dedupe_model_candidates(provider, candidates)
    if profile is not None and provider == profile_provider:
        candidates = [*(model or "" for model in candidates), *profile.fallbacks]
    return _dedupe_model_candidates(provider, candidates)


def _log_render_attempt_failure(attempt: RenderAttempt, stage: str) -> None:
    error = _short_error(attempt.message)
    _provider_attempt_logger.warning(
        "AI provider attempt failed provider=%s kind=scene model=%s stage=%s error=%s",
        attempt.provider,
        attempt.model or "<unknown>",
        stage,
        error,
        extra={
            "provider": attempt.provider,
            "kind": "scene",
            "model": attempt.model,
            "stage": stage,
            "error": error,
        },
    )


def _render_attempt_warnings(attempts: list[RenderAttempt]) -> list[str]:
    return [f"AI fallback: {attempt.warning()}" for attempt in attempts]


def _render_budget_remaining(started_at: float) -> float:
    return max(0.0, _RENDER_TOTAL_BUDGET_SECONDS - (time.monotonic() - started_at))


def _render_budget_warning(attempts: list[RenderAttempt], remaining_seconds: float) -> str:
    tried = len(attempts)
    suffix = f" sau {tried} lần thử" if tried else ""
    return f"Dừng fallback AI{suffix} vì chỉ còn {remaining_seconds:.1f}s trước timeout; đang dùng mock extractor."


def _format_render_failure(message: str, attempts: list[RenderAttempt], router9_only: bool) -> str:
    details = " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"
    suggestions = "Hãy kiểm tra API key/gateway, chọn model khác hoặc quét lại model 9router."
    if router9_only:
        suggestions += " Nếu muốn fallback sang provider khác, hãy tắt 9router-only."
    return f"{message} Đã thử: {details}. {suggestions}"


def _format_strict_render_failure(message: str, attempts: list[RenderAttempt], router9_only: bool) -> str:
    details = " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"
    suggestions = "Hãy kiểm tra provider/model đã chọn hoặc cấu hình fallback model cho đúng provider."
    if router9_only:
        suggestions += " 9router-only đang bật nên chỉ được dùng model 9router."
    return f"{message} Không fallback sang provider ngoài lựa chọn. Đã thử: {details}. {suggestions}"


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", redact_sensitive(message)).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")


def _dedupe(providers: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for provider in providers:
        if provider in seen:
            continue
        seen.add(provider)
        ordered.append(provider)
    return ordered


def _dedupe_model_candidates(provider: str, models: list[str | None]) -> list[str | None]:
    seen: set[str] = set()
    ordered: list[str | None] = []
    for model in models:
        normalized = explicit_model_for_provider(provider, model) if model else model
        key = normalized or ""
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _router9_model(settings: Settings, preferred_ai_model: str | None) -> str:
    model = explicit_model_for_provider("router9", preferred_ai_model) or settings.router9_text_model
    if not model:
        raise RuntimeError("Chưa chọn model 9router.")
    if settings.router9_allowed_models and model not in settings.router9_allowed_models:
        raise RuntimeError(f"Model 9router không nằm trong danh sách được phép: {model}")
    return model


def _router9_model_candidates(settings: Settings, preferred_ai_model: str | None) -> list[str]:
    explicit_model = explicit_model_for_provider("router9", preferred_ai_model)
    if explicit_model is not None:
        return [_router9_model(settings, explicit_model)]

    if settings.router9_allowed_models:
        if settings.router9_text_model and settings.router9_text_model in settings.router9_allowed_models:
            candidates = [settings.router9_text_model]
        else:
            selected = select_router9_render_model_ids_from_ids(settings.router9_allowed_models)
            candidates = [selected[0] if selected else settings.router9_allowed_models[0]]
    else:
        candidates = [settings.router9_text_model or settings.router9_text_fallback_models[0]]

    if not candidates:
        raise RuntimeError("Chưa chọn model 9router phù hợp cho render.")
    return candidates


async def _extract_with_provider(
    provider: str,
    settings: Settings,
    problem_text: str,
    grade: int | None,
    reasoning_layer: str,
    registry: ModelRegistry,
    preferred_ai_model: str | None = None,
    reasoning_plan: dict | None = None,
    system_prompt: str | None = None,
    model_supports_thinking: bool | None = None,
    thinking_enabled: bool | None = None,
    nlp_hints: dict | None = None,
    user_prompt: str | None = None,
    schema_version: str = "3.0",
) -> dict:
    engine = _provider_engine(provider, registry)
    common = dict(
        reasoning_plan=reasoning_plan,
        system_prompt=system_prompt,
        nlp_hints=nlp_hints,
        user_prompt=user_prompt,
        schema_version=schema_version,
    )

    if engine == "nvidia":
        return await NvidiaClient(settings, model=preferred_ai_model, thinking=thinking_enabled is True and model_supports_thinking is True).extract_scene_json(problem_text, grade, reasoning_layer, **common)
    if engine == "router9":
        model = _router9_model(settings, preferred_ai_model)
        return await Router9Client(settings, model=model).extract_scene_json(problem_text, grade, reasoning_layer, **common)
    if engine == "openrouter":
        return await OpenRouterClient(settings, model=preferred_ai_model, reasoning_enabled=thinking_enabled, supports_thinking=model_supports_thinking).extract_scene_json(problem_text, grade, reasoning_layer, **common)
    if engine == "openai_compat":
        return await OpenAICompatClient(settings, model=preferred_ai_model).extract_scene_json(problem_text, grade, reasoning_layer, **common)
    if engine == "ollama":
        return await OllamaClient(settings, model=preferred_ai_model, provider_id=provider).extract_scene_json(problem_text, grade, reasoning_layer, **common)
    raise RuntimeError(f"Engine không hỗ trợ: {engine} (provider: {provider})")


async def _reason_with_provider(
    provider: str,
    settings: Settings,
    problem_text: str,
    grade: int | None,
    preferred_ai_model: str | None = None,
    system_prompt: str | None = None,
    model_supports_thinking: bool | None = None,
    thinking_enabled: bool | None = None,
    registry: ModelRegistry | None = None,
) -> dict:
    """Run reasoning task (Task 1) with the given provider."""
    engine = _provider_engine(provider, registry)
    if engine == "nvidia":
        return await NvidiaClient(settings, model=preferred_ai_model, thinking=thinking_enabled is True and model_supports_thinking is True).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if engine == "router9":
        model = _router9_model(settings, preferred_ai_model)
        return await Router9Client(settings, model=model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if engine == "openrouter":
        return await OpenRouterClient(settings, model=preferred_ai_model, reasoning_enabled=thinking_enabled, supports_thinking=model_supports_thinking).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if engine == "openai_compat":
        return await OpenAICompatClient(settings, model=preferred_ai_model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if engine == "ollama":
        return await OllamaClient(settings, model=preferred_ai_model, provider_id=provider).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    raise RuntimeError(f"Engine không hỗ trợ reasoning: {engine} (provider: {provider})")


def _provider_engine(provider: str, registry: ModelRegistry | None = None) -> str:
    """Resolve client engine for a provider id.

    Known provider ids always map to their dedicated client. Registry engine is
    only used for custom openai_compat endpoints — a mis-seeded registry must
    not route router9 → OpenAICompatClient.
    """
    mapping = {
        "nvidia": "nvidia",
        "router9": "router9",
        "openrouter": "openrouter",
        "openai_compat": "openai_compat",
        "ollama": "ollama",
    }
    provider_id = canonical_provider_id(provider) or provider
    if provider_id in mapping:
        return mapping[provider_id]
    if registry is not None:
        provider_config = registry.providers.get(provider_id) or registry.providers.get(provider)
        if provider_config is not None and provider_config.engine:
            return provider_config.engine
    return "openai_compat"


def _format_tier_render_failure(message: str, attempts: list[RenderAttempt]) -> str:
    """Format lỗi khi tier render thất bại"""
    if not attempts:
        return message
    attempt_summary = " | ".join(attempt.warning() for attempt in attempts)
    return f"{message}\n\nCác lần thử: {attempt_summary}"


__all__ = [
    "RenderAttempt",
    "RenderFallbackSource",
    "_RENDER_TOTAL_BUDGET_SECONDS",
    "_RENDER_MIN_ATTEMPT_SECONDS",
    "_RENDER_MAX_ATTEMPT_SECONDS",
    "_REASONING_TOTAL_TIMEOUT_SECONDS",
    "_extract_with_provider",
    "_format_tier_render_failure",
    "_log_render_attempt_failure",
    "_render_attempt_warnings",
    "_render_budget_remaining",
    "_run_reasoning_stage",
    "_short_error",
    "_provider_order",
    "_profile_model_candidates",
]
