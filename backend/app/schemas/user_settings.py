from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BYOK_TASKS = {"render", "reasoning", "ocr", "solver", "chat"}
MAX_USER_MODELS = 50
MAX_MODEL_ID_CHARS = 256
MAX_BASE_URL_CHARS = 500
MAX_API_KEY_CHARS = 4096

UserAiTask = Literal["render", "reasoning", "ocr", "solver", "chat"]


class UserAiProviderSettingsResponse(BaseModel):
    enabled: bool = False
    base_url: str = ""
    api_key_configured: bool = False
    api_key_last4: str | None = None
    api_key_updated_at: str | None = None
    updated_at: str | None = None


class UserAiModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=MAX_MODEL_ID_CHARS)
    label: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    supports_vision: bool = False
    enabled: bool = True

    @field_validator("model_id")
    @classmethod
    def clean_model_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Model BYOK không được để trống.")
        return text

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def default_label(self) -> "UserAiModelSettings":
        if not self.label:
            self.label = self.model_id
        return self


class UserAiModelSettingsResponse(UserAiModelSettings):
    id: str


class UserAiTaskProfileSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: UserAiTask
    model_id: str = Field(min_length=1, max_length=MAX_MODEL_ID_CHARS)
    enabled: bool = True

    @field_validator("model_id")
    @classmethod
    def clean_model_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Model BYOK không được để trống.")
        return text


class UserSettingsResponse(BaseModel):
    ai_provider: UserAiProviderSettingsResponse = Field(default_factory=UserAiProviderSettingsResponse)
    models: list[UserAiModelSettingsResponse] = Field(default_factory=list)
    task_profiles: list[UserAiTaskProfileSettings] = Field(default_factory=list)


class UserAiProviderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    base_url: str = Field(default="", max_length=MAX_BASE_URL_CHARS)
    api_key: str | None = Field(default=None, max_length=MAX_API_KEY_CHARS)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def clean_base_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def clean_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class UserAiModelsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[UserAiModelSettings] = Field(default_factory=list, max_length=MAX_USER_MODELS)

    @model_validator(mode="after")
    def validate_unique_models(self) -> "UserAiModelsUpdateRequest":
        seen: set[str] = set()
        for model in self.models:
            if model.model_id in seen:
                raise ValueError("Danh sách model BYOK bị trùng.")
            seen.add(model.model_id)
        return self


class UserAiTaskProfilesUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_profiles: list[UserAiTaskProfileSettings] = Field(default_factory=list, max_length=len(BYOK_TASKS))

    @model_validator(mode="after")
    def validate_unique_tasks(self) -> "UserAiTaskProfilesUpdateRequest":
        seen: set[str] = set()
        for profile in self.task_profiles:
            if profile.task in seen:
                raise ValueError("Danh sách task profile BYOK bị trùng.")
            seen.add(profile.task)
        return self


class UserAiProviderCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1, max_length=MAX_BASE_URL_CHARS)
    api_key: str | None = Field(default=None, max_length=MAX_API_KEY_CHARS)
    model: str = Field(default="gpt-4o-mini", max_length=MAX_MODEL_ID_CHARS)

    @field_validator("base_url", "model")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Base URL và model kiểm tra BYOK không được để trống.")
        return text

    @field_validator("api_key")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class UserAiProviderCheckResponse(BaseModel):
    ok: bool
    message: str
