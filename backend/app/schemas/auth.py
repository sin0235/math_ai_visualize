from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.scene import MAX_BASE_URL_CHARS, MAX_MODEL_ID_CHARS, MathScene, RenderPayload

MAX_STORED_MODELS = 100
MAX_SETTINGS_JSON_CHARS = 80_000


WEAK_PASSWORDS = {"password", "password123", "12345678", "123456789", "qwerty123", "admin12345"}


class PasswordPolicyMixin(BaseModel):
    @field_validator("password", "new_password", check_fields=False)
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        password = value.strip()
        if len(password) < 10:
            raise ValueError("Mật khẩu cần ít nhất 10 ký tự.")
        if password.lower() in WEAK_PASSWORDS:
            raise ValueError("Mật khẩu quá phổ biến, hãy chọn mật khẩu mạnh hơn.")
        if password.isdigit() or password.isalpha():
            raise ValueError("Mật khẩu cần kết hợp chữ và số hoặc ký tự khác.")
        return value


class AuthRequest(PasswordPolicyMixin):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)

    @field_validator("password")
    @classmethod
    def reject_email_local_part(cls, value: str, info) -> str:
        email = str(info.data.get("email") or "")
        local_part = email.split("@", 1)[0].lower()
        if local_part and len(local_part) >= 4 and local_part in value.lower():
            raise ValueError("Mật khẩu không nên chứa phần tên email.")
        return value


class RegisterRequest(AuthRequest):
    display_name: str | None = Field(default=None, max_length=256)
    accept_privacy_policy: bool
    accept_terms: bool

    @field_validator("accept_privacy_policy", "accept_terms")
    @classmethod
    def require_legal_acceptance(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Bạn cần đồng ý Chính sách bảo mật và Điều khoản sử dụng để tạo tài khoản.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(PasswordPolicyMixin):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=10, max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    otp: str = Field(min_length=6, max_length=16)

    @field_validator("otp")
    @classmethod
    def clean_otp(cls, value: str) -> str:
        otp = "".join(value.split())
        if len(otp) != 6 or not otp.isdigit():
            raise ValueError("Mã OTP phải gồm 6 chữ số.")
        return otp


class ChangePasswordRequest(PasswordPolicyMixin):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=256)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str
    role: Literal["user", "admin"] = "user"
    status: Literal["active", "disabled"] = "active"
    display_name: str | None = None
    last_login_at: str | None = None
    plan: str = "free"
    email_verified_at: str | None = None
    password_changed_at: str | None = None


class AuthResponse(BaseModel):
    user: UserResponse


class SessionResponse(BaseModel):
    id: str
    created_at: str
    expires_at: str
    last_seen_at: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    current: bool = False


class StoredModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=MAX_MODEL_ID_CHARS)
    label: str = Field(max_length=MAX_MODEL_ID_CHARS)
    provider: str = Field(max_length=64)
    owned_by: str | None = Field(default=None, max_length=256)
    created: int | None = None
    context_length: int | None = None


class StoredProviderSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key: Literal[""] = ""
    base_url: str = Field(default="", max_length=MAX_BASE_URL_CHARS)
    model: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    scanned_models: list[StoredModelInfo] = Field(default_factory=list, max_length=MAX_STORED_MODELS)
    last_scanned_at: str = Field(default="", max_length=64)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_api_key(cls, _: object) -> str:
        return ""


class StoredRouter9Settings(StoredProviderSettings):
    only_mode: bool = False
    allowed_model_ids: list[str] = Field(default_factory=list, max_length=MAX_STORED_MODELS)

    @field_validator("allowed_model_ids")
    @classmethod
    def validate_allowed_models(cls, values: list[str]) -> list[str]:
        return [value[:MAX_MODEL_ID_CHARS] for value in values]


class StoredOcrSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openrouter", "router9"] = "openrouter"
    model: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    max_image_mb: int = Field(default=8, ge=1, le=32)


class StoredRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    default_provider: str = Field(default="auto", max_length=64)
    openrouter: StoredProviderSettings = Field(default_factory=StoredProviderSettings)
    nvidia: StoredProviderSettings = Field(default_factory=StoredProviderSettings)
    ollama: StoredProviderSettings = Field(default_factory=StoredProviderSettings)
    router9: StoredRouter9Settings = Field(default_factory=StoredRouter9Settings)
    ocr: StoredOcrSettings = Field(default_factory=StoredOcrSettings)
    openrouter_http_referer: str = Field(default="", max_length=MAX_BASE_URL_CHARS)
    openrouter_x_title: str = Field(default="", max_length=256)
    openrouter_reasoning_enabled: bool = False


class RenderHistoryItem(BaseModel):
    id: str
    problem_text: str
    provider: str | None = None
    model: str | None = None
    created_at: str
    source_type: str = "problem"
    renderer: str | None = None


class RenderHistoryDetail(RenderHistoryItem):
    scene: MathScene
    payload: RenderPayload
    warnings: list[str]
    render_request: dict | None = None
    advanced_settings: dict | None = None
    runtime_settings: dict | None = None


class UserSettingsResponse(BaseModel):
    settings: StoredRuntimeSettings | None = None
    updated_at: str | None = None


class UserSettingsRequest(BaseModel):
    settings: StoredRuntimeSettings


class AdminSummaryResponse(BaseModel):
    users: int
    active_users: int
    admins: int
    render_jobs: int


class AdminUserUpdateRequest(BaseModel):
    role: Literal["user", "admin"] | None = None
    status: Literal["active", "disabled"] | None = None
    display_name: str | None = Field(default=None, max_length=256)
    plan: str | None = Field(default=None, max_length=64)


class SystemSettingResponse(BaseModel):
    key: str
    value: dict
    updated_by: str | None = None
    updated_at: str


class SystemSettingRequest(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: dict = Field(default_factory=dict)


class AuditLogResponse(BaseModel):
    id: str
    actor_user_id: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    metadata: dict
    created_at: str


class AdminRenderHistoryItem(RenderHistoryItem):
    user_id: str | None = None


class AdminRenderHistoryDetail(RenderHistoryDetail):
    user_id: str | None = None
