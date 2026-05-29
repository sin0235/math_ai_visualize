# Plan: Hệ thống 3-tier model AI theo chất lượng

## Tổng quan

Thiết kế hệ thống phân loại AI model thành 3 tier theo chất lượng (tier1: kém/nhanh → tier2: trung bình → tier3: tốt/chậm). Admin cấu hình toàn bộ model cho từng tier. User chỉ chọn tier, không chọn model cụ thể.

## Thay đổi lớn

### Loại bỏ hoàn toàn user model selection
- **Xóa:** `preferred_ai_provider`, `preferred_ai_model` từ `RenderRequest`
- **Xóa:** `runtime_settings` liên quan đến model selection
- **Xóa:** Trang cài đặt cá nhân hóa model của user
- **Lý do:** Tránh xung đột giữa admin settings và user preferences

### Luồng mới
```
User chọn tier (mặc định tier1)
  ↓
Backend load tier profile từ admin settings
  ↓
Dùng model mặc định của tier
  ↓
Nếu lỗi → fallback trong tier (theo thứ tự admin cấu hình)
  ↓
Nếu hết fallback → báo lỗi
```

## Kiến trúc hiện tại (phân tích)

### 1. Task profiles hiện có
- Bảng `ai_task_profiles`: lưu cấu hình cho từng task (render, reasoning, solver_explanation, ocr)
- Mỗi task có: `provider_id`, `model_id`, `fallbacks_json`
- `fallbacks_json` chứa danh sách model dự phòng

### 2. Luồng gọi AI hiện tại (SẼ THAY ĐỔI)
**File:** `backend/app/services/extractor.py`
- `extract_scene()` nhận `preferred_ai_provider`, `preferred_ai_model` → **SẼ XÓA**
- `_render_provider_order()` → **SẼ ĐƠN GIẢN HÓA** (chỉ dùng provider từ tier profile)
- `_profile_model_candidates()` → **SẼ ĐƠN GIẢN HÓA** (chỉ dùng model từ tier profile)

### 3. Admin UI hiện có
**File:** `backend/app/schemas/auth.py`
- `SystemAiProfiles`: chứa 3 profile (geometry_reasoning, solver_explanation, ocr)
- `AiTaskProfile`: có `provider`, `model`, `fallbacks`

## Thiết kế 3-tier system

### 1. Schema database

**Mở rộng bảng `ai_task_profiles`:**
Thêm cột `tier` (nullable, default NULL để tương thích ngược):
```sql
ALTER TABLE ai_task_profiles ADD COLUMN tier TEXT;
```

**Convention đặt tên task:**
- Format: `{base_task}_{tier}` (ví dụ: `render_tier1`, `render_tier2`, `render_tier3`)
- Base tasks có tier: `render`, `reasoning`, `solver_explanation`
- Task không có tier: `ocr` (giữ nguyên logic cũ)
- Tiers: `tier1` (kém/fast), `tier2` (trung bình/balanced), `tier3` (tốt/best)

**Tương thích ngược:**
- Task không có suffix `_tierN` → coi như tier NULL (legacy, sẽ bị deprecated)
- Khi migrate, giữ nguyên các task hiện có nhưng sẽ không dùng nữa

### 2. Schema Pydantic (API)

**File:** `backend/app/schemas/auth.py`

Thêm model mới:
```python
class AiTierProfile(BaseModel):
    """Cấu hình model cho một tier cụ thể"""
    model_config = ConfigDict(extra="forbid")
    
    tier: Literal["tier1", "tier2", "tier3"]
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

class AiTaskTierProfiles(BaseModel):
    """Cấu hình 3 tier cho một task"""
    model_config = ConfigDict(extra="forbid")
    
    tier1: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier1"))
    tier2: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier2"))
    tier3: AiTierProfile = Field(default_factory=lambda: AiTierProfile(tier="tier3"))

class SystemAiTierProfiles(BaseModel):
    """Cấu hình tier cho các task hỗ trợ tier (không bao gồm OCR)"""
    model_config = ConfigDict(extra="forbid")
    
    version: int = 2
    render: AiTaskTierProfiles = Field(default_factory=AiTaskTierProfiles)
    reasoning: AiTaskTierProfiles = Field(default_factory=AiTaskTierProfiles)
    solver_explanation: AiTaskTierProfiles = Field(default_factory=AiTaskTierProfiles)
```

**Cập nhật `SYSTEM_SETTING_KEYS`:**
```python
SYSTEM_SETTING_KEYS = {"ai_settings", "plan_settings", "feature_flags", "ai_profiles", "ai_tier_profiles", "ai_prompts"}
```

### 3. Service layer

**File:** `backend/app/services/model_registry.py`

Thêm hàm mới:
```python
def resolve_tier_profile(
    registry: ModelRegistry, 
    task: str, 
    tier: Literal["tier1", "tier2", "tier3"]
) -> TaskProfile | None:
    """
    Resolve task profile với tier cụ thể.
    Trả về profile từ `{task}_{tier}`.
    Không fallback về logic cũ.
    """
    task_key = f"{task}_{tier}"
    profile = registry.task_profiles.get(task_key)
    if not profile:
        return None
    
    provider_id = profile.provider_id
    if provider_id == "auto":
        default_provider = registry.settings.get("default_provider")
        provider_id = default_provider if isinstance(default_provider, str) and provider_is_enabled(registry, default_provider) else None
    
    if not provider_id or not provider_is_enabled(registry, provider_id):
        return None
    
    model_id = profile.model_id
    if not model_id:
        provider = registry.providers.get(provider_id)
        model_id = effective_provider_default_model(registry, provider_id, provider.default_model_id if provider else "")
    
    if model_id and not model_is_allowed(registry, provider_id, model_id):
        model_id = effective_provider_default_model(registry, provider_id, "")
    
    fallbacks = _resolve_profile_fallbacks(registry, profile.fallbacks, provider_id)
    
    return TaskProfile(task_key, provider_id, model_id, fallbacks)
```

**File:** `backend/app/services/admin_settings.py`

Thêm hàm sync tier profiles:
```python
async def sync_ai_tier_profiles_to_registry(db: DatabaseClient, value: dict, patch: dict | None = None) -> None:
    """Đồng bộ tier profiles từ admin UI vào ai_task_profiles (không bao gồm OCR)"""
    profiles = SystemAiTierProfiles.model_validate(value)
    patch_keys = set(patch or value)
    
    for task_name in ["render", "reasoning", "solver_explanation"]:
        if task_name not in patch_keys:
            continue
        
        task_tiers = getattr(profiles, task_name)
        for tier_name in ["tier1", "tier2", "tier3"]:
            tier_profile = getattr(task_tiers, tier_name)
            task_key = f"{task_name}_{tier_name}"
            await save_task_profile(
                db, 
                task_key, 
                tier_profile.provider, 
                tier_profile.model, 
                tier_profile.fallbacks
            )
```

### 4. Fallback logic (chỉ trong tier)

**File:** `backend/app/services/extractor.py`

**Đơn giản hóa signature:**
```python
async def extract_scene(
    problem_text: str,
    grade: int | None = None,
    tier: Literal["tier1", "tier2", "tier3"] = "tier1",  # Mặc định tier1
    advanced_settings: AdvancedRenderSettings | None = None,
    db: DatabaseClient | None = None,
) -> tuple[MathScene, list[str]]:
    """
    XÓA: preferred_ai_provider, preferred_ai_model, runtime_settings
    THÊM: tier (mặc định tier1)
    """
    settings = get_settings()  # Không cần resolve_effective_settings vì không có runtime_settings
    registry = await load_model_registry(db, settings) if db is not None else None
    
    # Load profile theo tier
    render_profile = resolve_tier_profile(registry, "render", tier) if registry else None
    reasoning_profile = resolve_tier_profile(registry, "reasoning", tier) if registry else None
    
    if not render_profile:
        raise RuntimeError(f"Tier {tier} chưa được cấu hình cho task render.")
    
    render_settings = advanced_settings or AdvancedRenderSettings()
    warnings: list[str] = []
    attempts: list[RenderAttempt] = []
    use_two_stage = render_settings.reasoning_layer in ("auto", "force")
    started_at = time.monotonic()
    
    # --- TẢI SYSTEM PROMPTS ---
    scene_sys_prompt, reasoning_sys_prompt = await get_system_prompts(db)
    
    # --- TẦNG 1: Suy luận (nếu bật) ---
    reasoning_plan: dict | None = None
    if use_two_stage and reasoning_profile:
        reasoning_plan = await _run_reasoning_stage_with_tier(
            settings, problem_text, grade,
            reasoning_profile,
            warnings, system_prompt=reasoning_sys_prompt,
        )
        if reasoning_plan is not None:
            warnings.append("Đã hoàn thành tầng suy luận (reasoning layer).")
    
    # --- TẦNG 2: Trích xuất scene ---
    # Chỉ thử các model trong tier profile (provider + model + fallbacks)
    provider = render_profile.provider_id
    models = [render_profile.model_id, *render_profile.fallbacks]
    
    for model in models:
        if not model:
            continue
        
        remaining = _render_budget_remaining(started_at)
        if remaining < _RENDER_MIN_ATTEMPT_SECONDS:
            raise RuntimeError(_format_tier_render_failure(f"Tier {tier} đã gần hết thời gian.", attempts))
        
        attempt_timeout = min(remaining, _RENDER_MAX_ATTEMPT_SECONDS)
        try:
            scene_json = await asyncio.wait_for(
                _extract_with_provider(
                    provider, settings, problem_text, grade,
                    render_settings.reasoning_layer,
                    preferred_ai_model=model,
                    reasoning_plan=reasoning_plan,
                    system_prompt=scene_sys_prompt,
                ),
                timeout=attempt_timeout,
            )
            warnings.extend(_render_attempt_warnings(attempts))
            scene, cas_warnings = build_scene_with_cas_fix(scene_json)
            warnings.extend(cas_warnings)
            return scene, warnings
        except TimeoutError as error:
            attempts.append(RenderAttempt(provider, model, f"timeout after {attempt_timeout:.0f}s"))
        except (RuntimeError, ValidationError, ValueError, KeyError) as error:
            attempts.append(RenderAttempt(provider, model, str(error)))
        except Exception as error:
            message = str(error) or error.__class__.__name__
            attempts.append(RenderAttempt(provider, model, message))
    
    warnings.extend(_render_attempt_warnings(attempts))
    raise RuntimeError(_format_tier_render_failure(f"Tất cả model trong tier {tier} đều lỗi.", attempts))
```

**Thêm helper mới:**
```python
async def _run_reasoning_stage_with_tier(
    settings: Settings,
    problem_text: str,
    grade: int | None,
    reasoning_profile: TaskProfile,
    warnings: list[str],
    system_prompt: str | None = None,
) -> dict | None:
    """Chạy reasoning stage với tier profile (không fallback cross-provider)"""
    provider = reasoning_profile.provider_id
    models = [reasoning_profile.model_id, *reasoning_profile.fallbacks]
    
    for model in models:
        if not model:
            continue
        try:
            result = await asyncio.wait_for(
                _reasoning_with_provider(provider, settings, problem_text, grade, model, system_prompt),
                timeout=_REASONING_TOTAL_TIMEOUT_SECONDS,
            )
            return result
        except Exception:
            continue
    
    warnings.append("Reasoning layer lỗi, tiếp tục với render trực tiếp.")
    return None

def _format_tier_render_failure(message: str, attempts: list[RenderAttempt]) -> str:
    """Format lỗi khi tier render thất bại"""
    if not attempts:
        return message
    attempt_summary = " | ".join(attempt.warning() for attempt in attempts)
    return f"{message}\n\nCác lần thử: {attempt_summary}"
```

**Xóa các hàm không còn dùng:**
- `_render_provider_order()` → không cần nữa vì chỉ dùng provider từ tier profile
- `_profile_model_candidates()` → không cần nữa vì model list đã có trong tier profile
- `_provider_order()` → không cần nữa
- `_fast_provider_order()` → không cần nữa

### 5. API admin

**File:** `backend/app/api/routes_admin.py`

Thêm endpoint mới:
```python
@router.patch("/settings/ai_tier_profiles", dependencies=[Depends(require_trusted_origin)])
async def update_ai_tier_profiles(
    request: SystemSettingRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> SystemSettingResponse:
    """Cập nhật cấu hình tier profiles"""
    await enforce_rate_limit(db, http_request, admin, "admin_settings_update", 20, 60)
    
    if request.key != "ai_tier_profiles":
        raise HTTPException(status_code=400, detail="Key phải là 'ai_tier_profiles'")
    
    # Validate
    validated = SystemAiTierProfiles.model_validate(request.value)
    
    # Validate: mỗi tier phải có ít nhất 1 model
    for task_name in ["render", "reasoning", "solver_explanation"]:
        task_tiers = getattr(validated, task_name)
        for tier_name in ["tier1", "tier2", "tier3"]:
            tier_profile = getattr(task_tiers, tier_name)
            if not tier_profile.model and not tier_profile.fallbacks:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tier {tier_name} của task {task_name} phải có ít nhất 1 model (model hoặc fallbacks)."
                )
    
    # Sync vào registry
    await sync_ai_tier_profiles_to_registry(db, validated.model_dump(), request.value)
    
    # Lưu vào system_settings
    repo = AdminRepository(db)
    setting = await repo.upsert_system_setting("ai_tier_profiles", json.dumps(validated.model_dump(), ensure_ascii=False), admin.id)
    await repo.audit(admin.id, "admin.settings.update", "system_setting", "ai_tier_profiles", {})
    
    return SystemSettingResponse(
        key="ai_tier_profiles", 
        value=validated.model_dump(), 
        updated_at=setting.updated_at, 
        updated_by=admin.id
    )

@router.get("/settings/ai_tier_profiles")
async def get_ai_tier_profiles(
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> SystemSettingResponse:
    """Lấy cấu hình tier profiles hiện tại"""
    repo = AdminRepository(db)
    setting = await repo.find_system_setting("ai_tier_profiles")
    
    if not setting:
        # Trả về default
        default = SystemAiTierProfiles()
        return SystemSettingResponse(
            key="ai_tier_profiles",
            value=default.model_dump(),
            updated_at=None,
            updated_by=None
        )
    
    value = json.loads(setting.value_json)
    return SystemSettingResponse(
        key="ai_tier_profiles",
        value=value,
        updated_at=setting.updated_at,
        updated_by=setting.updated_by
    )
```

### 6. API render (user)

**File:** `backend/app/schemas/scene.py`

**Đơn giản hóa `RenderRequest`:**
```python
class RenderRequest(BaseModel):
    problem_text: str = Field(min_length=1, max_length=MAX_PROBLEM_TEXT_CHARS)
    grade: int | None = Field(default=None, ge=1, le=12)
    tier: Literal["tier1", "tier2", "tier3"] = Field(default="tier1")  # Mặc định tier1
    advanced_settings: AdvancedRenderSettings = Field(default_factory=AdvancedRenderSettings)
    
    # XÓA: preferred_ai_provider, preferred_ai_model, runtime_settings
```

**File:** `backend/app/api/routes_render.py`

Cập nhật endpoint:
```python
@router.post("/render", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_problem(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    await enforce_render_access(db, user)
    
    try:
        response = await asyncio.wait_for(
            build_problem_render_response(request, db), 
            timeout=RENDER_TIMEOUT_SECONDS
        )
    except TimeoutError as error:
        raise api_error(
            status.HTTP_504_GATEWAY_TIMEOUT,
            f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.",
            "TIMEOUT",
            ["Thử lại sau hoặc chọn tier thấp hơn (tier1 nhanh hơn tier3)."],
        ) from error
    except (RuntimeError, ValueError, KeyError) as error:
        payload = render_error_payload(error)
        raise api_error(
            status.HTTP_400_BAD_REQUEST, 
            payload["debug_message"], 
            payload["code"], 
            payload["suggestions"]
        ) from error
    
    if user is not None:
        await RenderHistoryRepository(db).create(
            user.id,
            request.problem_text,
            None,  # preferred_ai_provider → None
            None,  # preferred_ai_model → None
            response,
            render_request_json=json.dumps(request.model_dump(), ensure_ascii=False),
            advanced_settings_json=request.advanced_settings.model_dump_json(),
            runtime_settings_json=None,  # runtime_settings → None
            source_type="problem",
            renderer=response.scene.renderer,
        )
    return response

async def build_problem_render_response(request: RenderRequest, db: DatabaseClient) -> RenderResponse:
    scene, warnings = await extract_scene(
        request.problem_text,
        request.grade,
        request.tier,
        request.advanced_settings,
        db,
    )
    # ... phần còn lại giữ nguyên
```

### 7. Migration

**File:** `migrations/0009_ai_tier_profiles.sql`

```sql
-- Thêm cột tier vào ai_task_profiles (nullable để tương thích ngược)
ALTER TABLE ai_task_profiles ADD COLUMN tier TEXT;

-- Tạo index cho tier
CREATE INDEX IF NOT EXISTS idx_ai_task_profiles_tier ON ai_task_profiles(tier);

-- Seed tier profiles mặc định (tier3 = auto, tier2/tier1 = rỗng)
-- OCR không có tier, giữ nguyên task 'ocr' hiện có
INSERT OR IGNORE INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json, tier)
VALUES 
  ('render_tier1', 'auto', '', '[]', 'tier1'),
  ('render_tier2', 'auto', '', '[]', 'tier2'),
  ('render_tier3', 'auto', '', '[]', 'tier3'),
  ('reasoning_tier1', 'auto', '', '[]', 'tier1'),
  ('reasoning_tier2', 'auto', '', '[]', 'tier2'),
  ('reasoning_tier3', 'auto', '', '[]', 'tier3'),
  ('solver_explanation_tier1', 'auto', '', '[]', 'tier1'),
  ('solver_explanation_tier2', 'auto', '', '[]', 'tier2'),
  ('solver_explanation_tier3', 'auto', '', '[]', 'tier3');
```

## Kế hoạch triển khai

### Phase 1: Database & Schema (ưu tiên cao)
1. Tạo migration `0009_ai_tier_profiles.sql`
2. Thêm `AiTierProfile`, `AiTaskTierProfiles`, `SystemAiTierProfiles` vào `schemas/auth.py`
3. Test migration trên SQLite và D1

### Phase 2: Service layer (ưu tiên cao)
1. Thêm `resolve_tier_profile()` vào `model_registry.py`
2. Thêm `sync_ai_tier_profiles_to_registry()` vào `admin_settings.py`
3. Đơn giản hóa `extract_scene()`: xóa preferred_ai_provider/model/runtime_settings, thêm tier
4. Thêm `_run_reasoning_stage_with_tier()`, `_format_tier_render_failure()`
5. Xóa các hàm không dùng: `_render_provider_order()`, `_profile_model_candidates()`, `_provider_order()`, `_fast_provider_order()`
6. Test logic fallback trong tier

### Phase 3: API (ưu tiên cao)
1. Thêm endpoint GET/PATCH `/api/admin/settings/ai_tier_profiles`
2. Đơn giản hóa `RenderRequest`: xóa preferred_ai_provider/model/runtime_settings, thêm tier
3. Cập nhật `routes_render.py` gọi `extract_scene()` với tier
4. Test API với Postman/curl

### Phase 4: Cleanup (ưu tiên trung bình)
1. Xóa code liên quan `RuntimeSettings` model selection (giữ lại phần khác nếu có)
2. Xóa endpoint/UI user model selection (nếu có)
3. Cập nhật documentation

### Phase 5: Frontend (ưu tiên thấp)
1. Admin UI: form cấu hình 3 tier cho mỗi task
2. User UI: dropdown chọn tier (tier1/tier2/tier3), mặc định tier1
3. Xóa UI user model selection cũ

## Rủi ro & giảm thiểu

### Rủi ro 1: Breaking change cho client cũ
**Giảm thiểu:** 
- Field `tier` mặc định = "tier1", client cũ không gửi tier vẫn hoạt động
- Xóa `preferred_ai_provider`/`preferred_ai_model` là breaking change → cần thông báo trước
- Có thể giữ lại các field cũ nhưng ignore (deprecated) để tránh break API

### Rủi ro 2: Admin chưa cấu hình tier
**Giảm thiểu:**
- Migration seed tier profiles mặc định với `provider=auto`, `model=""`, `fallbacks=[]`
- API validation: bắt buộc mỗi tier phải có ít nhất 1 model
- Nếu tier profile rỗng → báo lỗi rõ ràng cho user

### Rủi ro 3: Fallback trong tier không đủ model
**Giảm thiểu:**
- Admin phải cấu hình ít nhất 1 model cho mỗi tier (validation trong API)
- Nếu tier lỗi hết → báo lỗi rõ ràng, không fallback sang tier khác
- Gợi ý user chọn tier thấp hơn trong error message

### Rủi ro 4: Migration lỗi trên D1
**Giảm thiểu:**
- Test migration trên SQLite trước
- Dùng `INSERT OR IGNORE` để tránh conflict
- Cột `tier` nullable để tương thích ngược

### Rủi ro 5: OCR logic bị ảnh hưởng
**Giảm thiểu:**
- OCR không có tier, giữ nguyên task `ocr` hiện có
- Không đụng vào logic OCR trong `extractor.py`
- Test riêng OCR sau khi deploy

## Checklist triển khai

- [ ] Tạo migration `0009_ai_tier_profiles.sql`
- [ ] Thêm schema Pydantic (`AiTierProfile`, `SystemAiTierProfiles`)
- [ ] Thêm `resolve_tier_profile()` vào `model_registry.py`
- [ ] Thêm `sync_ai_tier_profiles_to_registry()` vào `admin_settings.py`
- [ ] Đơn giản hóa `extract_scene()`: xóa preferred params, thêm tier
- [ ] Thêm `_run_reasoning_stage_with_tier()`, `_format_tier_render_failure()`
- [ ] Xóa hàm không dùng: `_render_provider_order()`, `_profile_model_candidates()`, etc.
- [ ] Thêm endpoint GET/PATCH `/api/admin/settings/ai_tier_profiles`
- [ ] Đơn giản hóa `RenderRequest`: xóa preferred params, thêm tier
- [ ] Cập nhật `routes_render.py` gọi `extract_scene()` với tier
- [ ] Test migration trên SQLite
- [ ] Test migration trên D1
- [ ] Test API tier profiles
- [ ] Test fallback logic trong tier
- [ ] Test OCR không bị ảnh hưởng
- [ ] Xóa code RuntimeSettings model selection
- [ ] Xóa endpoint/UI user model selection
- [ ] Tạo UI admin cho tier profiles
- [ ] Tạo UI user chọn tier

## Breaking changes cần thông báo

1. **API `/api/render`:**
   - Xóa: `preferred_ai_provider`, `preferred_ai_model`, `runtime_settings` (phần model selection)
   - Thêm: `tier` (mặc định "tier1")

2. **User workflow:**
   - Không còn chọn model cụ thể
   - Chỉ chọn tier (tier1/tier2/tier3)

3. **Admin workflow:**
   - Phải cấu hình tier profiles qua `/api/admin/settings/ai_tier_profiles`
   - Mỗi tier phải có ít nhất 1 model
