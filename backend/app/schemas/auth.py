import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.scene import MAX_BASE_URL_CHARS, MAX_MODEL_ID_CHARS, MathScene, RenderPayload, RenderResponse
from app.schemas.scene_v3 import SceneCommand, SceneWorkspaceResponseV3

MAX_STORED_MODELS = 1000
PLAN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_+-]{0,63}$")
ADMIN_AI_PROVIDERS = {"openrouter", "nvidia", "ollama", "openai_compat", "router9"}
ADMIN_DEFAULT_PROVIDERS = ADMIN_AI_PROVIDERS | {"auto"}
ADMIN_OCR_PROVIDERS = {"local", "openrouter", "router9", "nvidia", "ollama", "openai_compat"}
SYSTEM_SETTING_KEYS = {"ai_settings", "plan_settings", "feature_flags", "ai_profiles", "ai_tier_profiles", "ai_prompts"}


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
    turnstile_token: str | None = Field(default=None, max_length=4096)

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
    turnstile_token: str | None = Field(default=None, max_length=4096)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    turnstile_token: str | None = Field(default=None, max_length=4096)


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


class UserLearningProfileResponse(BaseModel):
    preferred_name: str | None = None
    locale: str = "vi-VN"
    timezone: str | None = None
    education_level: str | None = None
    grade_level: str | None = None
    math_level: str | None = None
    learning_goals: list[str] = Field(default_factory=list)
    subject_focus: list[str] = Field(default_factory=list)
    preferred_explanation_style: str | None = None
    accessibility_needs: list[str] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)
    onboarding_completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UserLearningProfileUpdateRequest(BaseModel):
    preferred_name: str | None = Field(default=None, max_length=128)
    locale: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    education_level: str | None = Field(default=None, max_length=64)
    grade_level: str | None = Field(default=None, max_length=64)
    math_level: str | None = Field(default=None, max_length=64)
    learning_goals: list[str] | None = Field(default=None, max_length=24)
    subject_focus: list[str] | None = Field(default=None, max_length=24)
    preferred_explanation_style: str | None = Field(default=None, max_length=64)
    accessibility_needs: list[str] | None = Field(default=None, max_length=24)
    profile: dict[str, Any] | None = None
    onboarding_completed_at: str | None = Field(default=None, max_length=64)

    @field_validator("preferred_name", "locale", "timezone", "education_level", "grade_level", "math_level", "preferred_explanation_style", "onboarding_completed_at")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("learning_goals", "subject_focus", "accessibility_needs")
    @classmethod
    def clean_text_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip()[:128] for item in value if item.strip()]


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
    capabilities: dict[str, Any] = Field(default_factory=dict)


class AdminProviderModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(default="", max_length=4096)
    base_url: str = Field(default="", max_length=MAX_BASE_URL_CHARS)
    scanned_models: list[StoredModelInfo] = Field(default_factory=list, max_length=MAX_STORED_MODELS)
    allowed_model_ids: list[str] = Field(default_factory=list, max_length=MAX_STORED_MODELS)
    last_scanned_at: str = Field(default="", max_length=64)

    @field_validator("allowed_model_ids")
    @classmethod
    def validate_allowed_models(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Danh sách model cho phép không được chứa giá trị trống.")
        return cleaned


class AdminRouter9ModelSettings(AdminProviderModelSettings):
    only_mode: bool = False


class AdminOcrModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="openrouter", max_length=64)
    model: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    max_image_mb: int = Field(default=5, ge=1, le=32)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        provider = value.strip()
        if provider not in ADMIN_OCR_PROVIDERS:
            raise ValueError("Nhà cung cấp OCR không hợp lệ.")
        return provider


class SystemAiSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    default_provider: str = Field(default="auto", max_length=64)
    openrouter: AdminProviderModelSettings = Field(default_factory=AdminProviderModelSettings)
    nvidia: AdminProviderModelSettings = Field(default_factory=AdminProviderModelSettings)
    ollama: AdminProviderModelSettings = Field(default_factory=AdminProviderModelSettings)
    openai_compat: AdminProviderModelSettings = Field(default_factory=AdminProviderModelSettings)
    router9: AdminRouter9ModelSettings = Field(default_factory=AdminRouter9ModelSettings)
    ocr: AdminOcrModelSettings = Field(default_factory=AdminOcrModelSettings)
    openrouter_http_referer: str = Field(default="", max_length=MAX_BASE_URL_CHARS)
    openrouter_x_title: str = Field(default="", max_length=256)
    openrouter_reasoning_enabled: bool = False

    @field_validator("default_provider")
    @classmethod
    def validate_default_provider(cls, value: str) -> str:
        provider = value.strip()
        if provider not in ADMIN_DEFAULT_PROVIDERS:
            raise ValueError("Nhà cung cấp mặc định không hợp lệ.")
        return provider

    @model_validator(mode="after")
    def validate_router9_only_mode(self) -> "SystemAiSettings":
        if self.router9.only_mode and not self.router9.allowed_model_ids:
            raise ValueError("Router9 only mode cần ít nhất một model Router9 trong allowlist.")
        return self


class RenderHistoryItem(BaseModel):
    id: str
    problem_text: str
    provider: str | None = None
    model: str | None = None
    created_at: str
    source_type: str = "problem"
    renderer: str | None = None
    degraded: bool = False
    fallback_source: Literal["none", "mock", "provider_fallback"] = "none"
    ai_source: Literal["admin", "byok", "none"] = "none"
    schema_version: str = "1.0"
    title: str | None = None
    problem_preview: str | None = None
    topic: str = "unknown"
    grade: str | None = None
    tier: str | None = None
    is_favorite: bool = False
    archived_at: str | None = None
    last_opened_at: str | None = None
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class RenderHistoryPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, max_length=128)
    is_favorite: bool | None = None
    archived: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=24)

    @field_validator("title", "project_id")
    @classmethod
    def clean_optional_history_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = []
        for item in value:
            label = item.strip()[:64]
            if label and label not in cleaned:
                cleaned.append(label)
        return cleaned


class SceneRevisionResponse(BaseModel):
    id: str
    history_item_id: str
    render_job_id: str | None = None
    revision_no: int
    change_source: str
    change_summary: str | None = None
    created_at: str
    schema_version: str = "2.0"
    scene_id: str | None = None
    snapshot_revision: int | None = None


class RenderHistoryDetailV2(RenderHistoryItem):
    kind: Literal["math_scene_v2"] = "math_scene_v2"
    scene: MathScene
    payload: RenderPayload
    warnings: list[str]
    response: RenderResponse | None = None
    render_request: dict | None = None
    advanced_settings: dict | None = None
    runtime_settings: dict | None = None


class RenderHistoryDetailV3(RenderHistoryItem):
    kind: Literal["math_scene_v3"] = "math_scene_v3"
    workspace: SceneWorkspaceResponseV3
    snapshot_revision: int = Field(ge=1)
    command_log: list[SceneCommand] = Field(default_factory=list)
    render_request: dict | None = None
    runtime_settings: dict | None = None


RenderHistoryDetail = Annotated[RenderHistoryDetailV2 | RenderHistoryDetailV3, Field(discriminator="kind")]


class RestoreHistoryV3Request(BaseModel):
    snapshot_revision: int | None = Field(default=None, ge=1)


class UserSettingsResponse(BaseModel):
    settings: None = None
    updated_at: None = None


class PlanQuotaSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_render_limit: int | None = Field(default=None, ge=0, le=100_000)
    daily_ocr_limit: int | None = Field(default=None, ge=0, le=100_000)


class SystemPlanSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    plans: dict[str, PlanQuotaSettings] = Field(default_factory=lambda: {
        "free": PlanQuotaSettings(daily_render_limit=20, daily_ocr_limit=20),
        "pro": PlanQuotaSettings(daily_render_limit=200, daily_ocr_limit=200),
        "pro_plus": PlanQuotaSettings(),
    })

    @field_validator("plans")
    @classmethod
    def validate_plans(cls, value: dict[str, PlanQuotaSettings]) -> dict[str, PlanQuotaSettings]:
        if not value:
            raise ValueError("Cần cấu hình ít nhất một gói người dùng.")
        if "free" not in value:
            raise ValueError("Cấu hình gói cần có free.")
        invalid = [plan_id for plan_id in value if not PLAN_ID_PATTERN.fullmatch(plan_id)]
        if invalid:
            raise ValueError("Mã gói không hợp lệ.")
        return value


class SystemFeatureFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 2
    maintenance_mode: bool = False
    maintenance_message: str = Field(default="Hệ thống đang bảo trì. Vui lòng thử lại sau.", max_length=500)
    google_oauth_enabled: bool = True
    ocr_enabled: bool = True
    render_enabled: bool = True
    turnstile_enabled: bool = False
    nlp_shadow_rules: list[str] = Field(default_factory=list, max_length=64)
    nlp_authoritative_rules: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("nlp_shadow_rules", "nlp_authoritative_rules")
    @classmethod
    def validate_nlp_rollout_rules(cls, values: list[str]) -> list[str]:
        targets = {"render", "geometry_solve", "algebra", "analyzer", "ocr"}
        cleaned: list[str] = []
        for raw_value in values:
            value = raw_value.strip().lower()
            target, separator, intent = value.partition(":")
            if target not in targets or (separator and (not intent or len(intent) > 96)):
                raise ValueError("Rule NLP phải có dạng target hoặc target:intent.")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned


class AiTaskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="auto", max_length=64)
    model: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    fallbacks: list[str] = Field(default_factory=list, max_length=MAX_STORED_MODELS)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        provider = value.strip()
        if provider not in ADMIN_DEFAULT_PROVIDERS:
            raise ValueError("Nhà cung cấp AI không hợp lệ.")
        return provider

    @field_validator("model")
    @classmethod
    def clean_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("fallbacks")
    @classmethod
    def validate_fallbacks(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Danh sách fallback không được chứa giá trị trống.")
        return cleaned


class SystemAiPrompts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    scene_extraction: str = Field(default="", max_length=50_000)
    reasoning: str = Field(default="", max_length=50_000)


class SystemAiProfiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    geometry_reasoning: AiTaskProfile = Field(default_factory=AiTaskProfile)
    solver_explanation: AiTaskProfile = Field(default_factory=AiTaskProfile)
    ocr: AiTaskProfile = Field(default_factory=AiTaskProfile)


class AiTierProfile(BaseModel):
    """Nhóm model dựng hình cho một tier cụ thể."""
    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier1", "tier2", "tier3"]
    default_model: str = Field(default="", max_length=MAX_MODEL_ID_CHARS)
    models: list[str] = Field(default_factory=list, max_length=MAX_STORED_MODELS)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_profile(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        provider = str(value.get("provider") or "auto").strip()
        models: list[str] = []
        default_model = str(value.get("default_model") or "").strip()
        model = str(value.get("model") or "").strip()
        if default_model:
            default_model = _format_tier_model_ref(provider, default_model)
        elif model:
            default_model = _format_tier_model_ref(provider, model)
        if isinstance(value.get("models"), list):
            models.extend(_format_tier_model_ref(provider, str(item).strip()) for item in value["models"])
        elif default_model:
            models.append(default_model)
        return {"tier": value.get("tier"), "default_model": default_model, "models": models}

    @field_validator("default_model")
    @classmethod
    def validate_default_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def validate_models(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Danh sách model tier không được chứa giá trị trống.")
        if any(_tier_provider_from_model(value) is None for value in cleaned):
            raise ValueError("Model tier phải có dạng provider::model.")
        deduped: list[str] = []
        for value in cleaned:
            if value not in deduped:
                deduped.append(value)
        return deduped

    @model_validator(mode="after")
    def align_default_model(self) -> "AiTierProfile":
        if not self.default_model and self.models:
            self.default_model = self.models[0]
        if self.default_model:
            if _tier_provider_from_model(self.default_model) is None:
                raise ValueError("Model mặc định của tier phải có dạng provider::model.")
            if self.default_model not in self.models:
                self.models = [self.default_model, *self.models]
        return self


class SystemAiTierProfiles(BaseModel):
    """Cấu hình tier model chỉ cho tác vụ dựng hình."""
    model_config = ConfigDict(extra="forbid")

    version: int = 3
    tier1: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier1"))
    tier2: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier2"))
    tier3: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier3"))

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_task_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if any(tier in value for tier in ("tier1", "tier2", "tier3")):
            return value
        render = value.get("render")
        if not isinstance(render, dict):
            return value
        migrated: dict[str, Any] = {"version": 3}
        for tier in ("tier1", "tier2", "tier3"):
            migrated[tier] = render.get(tier, {"tier": tier, "models": []})
        return migrated


def _format_tier_model_ref(provider: str, model: str) -> str:
    if not model:
        return ""
    parsed = _parse_tier_model_ref(model, allow_legacy_slash=True)
    if parsed is not None:
        return f"{parsed[0]}::{parsed[1]}"
    if provider in {"openrouter", "nvidia", "ollama", "openai_compat", "router9"}:
        return f"{provider}::{model}"
    return model


def _tier_provider_from_model(model: str) -> str | None:
    parsed = _parse_tier_model_ref(model, allow_legacy_slash=False)
    return parsed[0] if parsed is not None else None


def _parse_tier_model_ref(model: str, *, allow_legacy_slash: bool) -> tuple[str, str] | None:
    value = model.strip()
    if "::" in value:
        provider, model_id = value.split("::", 1)
        provider = "openai_compat" if provider == "openai-compat" else provider
        if provider in {"openrouter", "nvidia", "ollama", "openai_compat", "router9"} and model_id:
            return provider, model_id
        return None
    if not allow_legacy_slash:
        return None
    for provider in ("openrouter", "nvidia", "ollama", "openai_compat", "router9"):
        prefix = f"{provider}/"
        if value.startswith(prefix) and value != prefix:
            return provider, value.removeprefix(prefix)
    if value.startswith("openai-compat/") and value != "openai-compat/":
        return "openai_compat", value.removeprefix("openai-compat/")
    return None


class AdminSummaryResponse(BaseModel):
    users: int
    active_users: int
    admins: int
    render_jobs: int
    render_jobs_today: int
    users_today: int
    ai_warning_jobs: int
    ai_warning_rate: float
    daily_stats: list[dict[str, Any]] = Field(default_factory=list)



class AdminUserUpdateRequest(BaseModel):
    role: Literal["user", "admin"] | None = None
    status: Literal["active", "disabled"] | None = None
    display_name: str | None = Field(default=None, max_length=256)
    plan: str | None = Field(default=None, max_length=64)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, value: str | None) -> str | None:
        if value is None:
            return None
        plan = value.strip()
        if not plan or not PLAN_ID_PATTERN.fullmatch(plan):
            raise ValueError("Mã gói không hợp lệ.")
        return plan


class AdminPlanResponse(BaseModel):
    id: str
    name: str
    daily_render_limit: int | None = None
    daily_ocr_limit: int | None = None
    sort_order: int = 0
    is_active: bool = True
    created_at: str
    updated_at: str


class AdminPlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    daily_render_limit: int | None = Field(default=None, ge=0, le=100_000)
    daily_ocr_limit: int | None = Field(default=None, ge=0, le=100_000)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Tên gói không được để trống.")
        return text


class SystemSettingResponse(BaseModel):
    key: str
    value: dict
    updated_by: str | None = None
    updated_at: str


class SystemSettingRequest(BaseModel):
    key: Literal["ai_settings", "plan_settings", "feature_flags", "ai_profiles", "ai_tier_profiles", "ai_prompts"]
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


class AdminRenderHistoryDetail(RenderHistoryDetailV2):
    user_id: str | None = None


class AdminSessionResponse(BaseModel):
    id: str
    created_at: str
    expires_at: str
    last_seen_at: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
