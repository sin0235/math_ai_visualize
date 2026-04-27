from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hinh Math Renderer"
    cors_origins: list[str] = ["http://localhost:5173"]
    openrouter_api_key: str | None = None
    openrouter_text_model: str = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_vision_model: str = "qwen/qwen2.5-vl-72b-instruct:free"
    openrouter_reasoning_enabled: bool = False
    openrouter_http_referer: str | None = None
    openrouter_x_title: str = "Hinh Math Renderer"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_text_model: str = "deepseek-ai/deepseek-v3.1-terminus"
    ai_provider: str = "auto"

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
