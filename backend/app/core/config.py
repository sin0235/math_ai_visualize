from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.scene import RuntimeSettings


class Settings(BaseSettings):
    app_name: str = "Hinh Math Renderer"
    cors_origins: list[str] = ["*"]
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_vision_model: str = "google/gemma-4-31b-it:free"
    openrouter_vision_fallback_model: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_reasoning_enabled: bool = False
    openrouter_http_referer: str | None = None
    openrouter_x_title: str = "Hinh Math Renderer"
    opencode_nemotron_model: str = "oc/nemotron-3-super-free"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_text_model: str = "qwen/qwen3-coder-480b-a35b-instruct"
    ollama_base_url: str = "http://localhost:11434"
    ollama_text_model: str = "gpt-oss:120b"
    ollama_api_key: str | None = None
    router9_api_key: str | None = None
    router9_base_url: str = "http://localhost:20128/v1"
    router9_text_model: str | None = None
    router9_only: bool = False
    router9_allowed_models: list[str] = []
    ai_provider: str = "auto"

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def merge_runtime_settings(settings: Settings, runtime_settings: RuntimeSettings | None) -> Settings:
    if runtime_settings is None:
        return settings

    data: dict[str, Any] = settings.model_dump()

    if runtime_settings.default_provider is not None:
        data["ai_provider"] = runtime_settings.default_provider

    if runtime_settings.openrouter:
        if api_key := _clean_optional_text(runtime_settings.openrouter.api_key):
            data["openrouter_api_key"] = api_key
        if base_url := _clean_optional_text(runtime_settings.openrouter.base_url):
            data["openrouter_base_url"] = base_url
        if model := _clean_optional_text(runtime_settings.openrouter.model):
            data["openrouter_text_model"] = model

    if runtime_settings.nvidia:
        if api_key := _clean_optional_text(runtime_settings.nvidia.api_key):
            data["nvidia_api_key"] = api_key
        if base_url := _clean_optional_text(runtime_settings.nvidia.base_url):
            data["nvidia_base_url"] = base_url
        if model := _clean_optional_text(runtime_settings.nvidia.model):
            data["nvidia_text_model"] = model

    if runtime_settings.ollama:
        if api_key := _clean_optional_text(runtime_settings.ollama.api_key):
            data["ollama_api_key"] = api_key
        if base_url := _clean_optional_text(runtime_settings.ollama.base_url):
            data["ollama_base_url"] = base_url
        if model := _clean_optional_text(runtime_settings.ollama.model):
            data["ollama_text_model"] = model

    if runtime_settings.router9:
        if api_key := _clean_optional_text(runtime_settings.router9.api_key):
            data["router9_api_key"] = api_key
        if base_url := _clean_optional_text(runtime_settings.router9.base_url):
            data["router9_base_url"] = base_url
        if model := _clean_optional_text(runtime_settings.router9.model):
            data["router9_text_model"] = model
        if runtime_settings.router9.only_mode is not None:
            data["router9_only"] = runtime_settings.router9.only_mode
        if runtime_settings.router9.allowed_model_ids is not None:
            data["router9_allowed_models"] = runtime_settings.router9.allowed_model_ids

    if referer := _clean_optional_text(runtime_settings.openrouter_http_referer):
        data["openrouter_http_referer"] = referer
    if title := _clean_optional_text(runtime_settings.openrouter_x_title):
        data["openrouter_x_title"] = title
    if runtime_settings.openrouter_reasoning_enabled is not None:
        data["openrouter_reasoning_enabled"] = runtime_settings.openrouter_reasoning_enabled

    return Settings.model_validate(data)


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
