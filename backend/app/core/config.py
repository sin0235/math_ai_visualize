from functools import lru_cache
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.scene import RuntimeSettings


class Settings(BaseSettings):
    app_name: str = "AI Math Renderer"
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://math-renderer.sin-studio.tech",
        "https://math-renderer.sin235.live",
    ]
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "openai/gpt-oss-120b:free"
    openrouter_vision_model: str = "google/gemma-4-31b-it:free"
    openrouter_vision_fallback_model: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_reasoning_enabled: bool = False
    openrouter_http_referer: str | None = None
    openrouter_x_title: str = "AI Math Renderer"
    openai_api_key: str | None = None
    opencode_nemotron_model: str = "oc/nemotron-3-super-free"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_text_model: str = "qwen/qwen3-coder-480b-a35b-instruct"
    openai_compat_api_key: str | None = None
    openai_compat_base_url: str = "http://localhost:8080/v1"
    openai_compat_text_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_text_model: str = "gpt-oss:120b"
    ollama_api_key: str | None = None
    router9_api_key: str | None = None
    router9_base_url: str = "http://localhost:20128/v1"
    router9_text_model: str | None = None
    router9_text_fallback_models: list[str] = ["codex-5.5", "codex-5.4", "codex-5.3", "github/gpt-5.2"]
    router9_ocr_model: str | None = None
    router9_ocr_fallback_models: list[str] = ["codex-5.5-image", "codex-5.4-image", "github/gpt-5.2"]
    router9_only: bool = False
    router9_allowed_models: list[str] = []
    ai_provider: str = "auto"
    database_backend: str = "d1"
    sqlite_path: str = "backend/.data/hinh.db"
    d1_account_id: str | None = None
    d1_database_id: str | None = None
    d1_api_token: str | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_public_base_url: str | None = None
    r2_upload_prefix: str = "uploads"
    appwrite_endpoint: str | None = None
    appwrite_project_id: str | None = None
    appwrite_api_key: str | None = None
    appwrite_database_id: str | None = None
    appwrite_storage_bucket_id: str | None = None
    appwrite_upload_prefix: str = "uploads"
    appwrite_public_base_url: str | None = None
    ocr_upload_storage_provider: Literal["auto", "appwrite", "r2", "database"] = "auto"
    ocr_image_max_mb: int = 10
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_chat_folder: str = "hinh/chat"
    chat_image_max_mb: int = 5
    auto_apply_sqlite_migrations: bool = True
    auto_apply_d1_migrations: bool = False
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str | None = None
    public_app_url: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@example.local"
    smtp_use_tls: bool = True
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    auth_email_dev_mode: bool = True
    require_email_verification: bool = True
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "https://math-renderer-api.sin-studio.tech/api/auth/google/callback"
    turnstile_secret_key: str | None = None
    turnstile_site_key: str | None = None
    register_ip_daily_limit: int = 20
    allow_missing_origin_for_cookie_mutations: bool = True
    trusted_proxy_ips: list[str] = []
    cas_repair_enabled: bool = False
    cas_repair_max_iterations: int = 2
    cas_repair_min_severity: Literal["warning", "error"] = "warning"
    advisory_enabled: bool = True
    advisory_include_debug_signals: bool = False
    local_ocr_enabled: bool = True
    local_ocr_prefer: Literal["auto", "always", "never"] = "auto"
    local_ocr_min_confidence: float = 0.55
    local_ocr_timeout_seconds: int = 30
    local_ocr_max_concurrency: int = 1
    local_ocr_paddle_lang: str = "vi"
    local_ocr_use_pix2tex: bool = True
    local_ocr_fallback_to_llm: bool = True
    local_ocr_model_name: str = "paddleocr+pix2tex"
    dev_bypass_auth: bool = False

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def apply_openai_compat_defaults(self) -> "Settings":
        if not self.openai_compat_api_key:
            self.openai_compat_api_key = _clean_optional_text(getattr(self, "openai_api_key", None))
        return self

    @model_validator(mode="after")
    def validate_cookie_settings(self) -> "Settings":
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true")
        if self.environment == "production" and not self.session_cookie_secure:
            raise ValueError("ENVIRONMENT=production requires SESSION_COOKIE_SECURE=true")
        if self.environment == "production" and self.allow_missing_origin_for_cookie_mutations:
            raise ValueError("ENVIRONMENT=production requires ALLOW_MISSING_ORIGIN_FOR_COOKIE_MUTATIONS=false")
        return self


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

    if runtime_settings.openai_compat:
        if api_key := _clean_optional_text(runtime_settings.openai_compat.api_key):
            data["openai_compat_api_key"] = api_key
        if base_url := _clean_optional_text(runtime_settings.openai_compat.base_url):
            data["openai_compat_base_url"] = base_url
        if model := _clean_optional_text(runtime_settings.openai_compat.model):
            data["openai_compat_text_model"] = model

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
