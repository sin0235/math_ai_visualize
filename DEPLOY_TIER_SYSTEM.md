# Hệ thống 3-Tier Model AI - Tóm tắt triển khai

## 📦 Nhánh: `feature/3-tier-model-system`

**Commit:** `6a8a657` - feat: hệ thống 3-tier model AI theo chất lượng

**Link PR:** https://github.com/sin0235/math_ai_visualize/pull/new/feature/3-tier-model-system

---

## ✅ Đã hoàn thành (Backend 100%)

### 1. Database Migration
- **File:** `migrations/0009_ai_tier_profiles.sql`
- **Nội dung:**
  - Thêm cột `tier` vào bảng `ai_task_profiles`
  - Tạo index `idx_ai_task_profiles_tier`
  - Seed 9 tier profiles mặc định (render/reasoning/solver_explanation × tier1/tier2/tier3)

### 2. Schema & Types
- **File:** `backend/app/schemas/auth.py`
  - `AiTierProfile`: cấu hình 1 tier (provider, model, fallbacks)
  - `AiTaskTierProfiles`: 3 tier cho 1 task
  - `SystemAiTierProfiles`: cấu hình toàn bộ (render, reasoning, solver_explanation)
  - Cập nhật `SYSTEM_SETTING_KEYS` thêm `ai_tier_profiles`

- **File:** `backend/app/schemas/scene.py`
  - **BREAKING:** `RenderRequest` xóa `preferred_ai_provider`, `preferred_ai_model`, `runtime_settings`
  - **BREAKING:** `RenderRequest` thêm `tier` (mặc định `"tier1"`)

### 3. Service Layer
- **File:** `backend/app/services/model_registry.py`
  - `resolve_tier_profile()`: resolve profile theo tier cụ thể

- **File:** `backend/app/services/admin_settings.py`
  - `sync_ai_tier_profiles_to_registry()`: đồng bộ tier profiles vào database

- **File:** `backend/app/services/extractor.py`
  - **BREAKING:** `extract_scene()` đơn giản hóa signature (xóa preferred params, thêm tier)
  - Logic fallback chỉ trong tier (không cross-tier, không cross-provider)
  - Helper: `_run_reasoning_stage_with_tier()`, `_format_tier_render_failure()`

### 4. API
- **File:** `backend/app/api/routes_admin.py`
  - Endpoint `PUT /system-settings` hỗ trợ key `ai_tier_profiles`
  - Validation: `validate_ai_tier_profiles_rules()` - bắt buộc mỗi tier có ít nhất 1 model

- **File:** `backend/app/api/routes_render.py`
  - Cập nhật gọi `extract_scene()` với tier
  - Xóa các hàm không dùng: `log_render_choice()`, `sanitize_runtime_settings()`

### 5. Test
- **File:** `backend/test_tier_system.py`
  - Test schema validation
  - Test migration
  - Test service layer sync
  - Test API validation

---

## 🚨 Breaking Changes

### API `/api/render`

**Trước (không còn hoạt động):**
```json
{
  "problem_text": "Cho tam giác ABC",
  "preferred_ai_provider": "router9",
  "preferred_ai_model": "model-xyz",
  "runtime_settings": { ... }
}
```

**Sau (mới):**
```json
{
  "problem_text": "Cho tam giác ABC",
  "tier": "tier1"
}
```

### Tier levels
- `tier1`: Nhanh/rẻ (mặc định)
- `tier2`: Cân bằng
- `tier3`: Chất lượng cao/chậm

---

## 📋 Checklist Deploy

### Bước 1: Test trên môi trường dev
- [ ] Checkout nhánh `feature/3-tier-model-system`
- [ ] Chạy migration: `python -m app.db.migrations` hoặc restart backend
- [ ] Test API với Postman/curl:
  ```bash
  # Test render với tier
  curl -X POST http://localhost:8000/api/render \
    -H "Content-Type: application/json" \
    -d '{"problem_text": "Cho tam giác ABC", "tier": "tier1"}'
  ```

### Bước 2: Cấu hình tier profiles (Admin)
- [ ] Login admin
- [ ] Gọi API cấu hình tier:
  ```bash
  curl -X PUT http://localhost:8000/api/admin/system-settings \
    -H "Content-Type: application/json" \
    -H "Cookie: session=..." \
    -d '{
      "key": "ai_tier_profiles",
      "value": {
        "version": 2,
        "render": {
          "tier1": {"tier": "tier1", "provider": "router9", "model": "model-fast", "fallbacks": []},
          "tier2": {"tier": "tier2", "provider": "router9", "model": "model-balanced", "fallbacks": ["model-fast"]},
          "tier3": {"tier": "tier3", "provider": "router9", "model": "model-best", "fallbacks": ["model-balanced"]}
        },
        "reasoning": { ... },
        "solver_explanation": { ... }
      }
    }'
  ```

### Bước 3: Test end-to-end
- [ ] Test render với tier1/tier2/tier3
- [ ] Verify fallback hoạt động (tắt model chính, xem có fallback không)
- [ ] Test OCR vẫn hoạt động bình thường (không bị ảnh hưởng)

### Bước 4: Deploy production
- [ ] Merge PR vào `main`/`product`
- [ ] Deploy backend
- [ ] Chạy migration trên production database
- [ ] Cấu hình tier profiles qua admin API
- [ ] Monitor logs để đảm bảo không có lỗi

---

## ⏳ Chưa hoàn thành (Frontend)

### Admin UI
**Cần tạo:** Form cấu hình tier profiles trong admin console

**Vị trí:** `frontend/src/components/admin/AdminForms.tsx`

**Component:** `AdminAiTierProfilesForm`

**Chức năng:**
- 3 sections (Render, Reasoning, Solver Explanation)
- Mỗi section có 3 tier (tier1, tier2, tier3)
- Mỗi tier có:
  - Dropdown chọn model chính
  - Checkboxes chọn fallback models
- Button "Lưu Tier Profiles"

### User UI
**Cần sửa:** Form render của user

**Thay đổi:**
- Xóa dropdown chọn provider/model
- Thêm dropdown chọn tier:
  ```tsx
  <select value={tier} onChange={(e) => setTier(e.target.value)}>
    <option value="tier1">Tier 1 - Nhanh (khuyến nghị)</option>
    <option value="tier2">Tier 2 - Cân bằng</option>
    <option value="tier3">Tier 3 - Chất lượng cao</option>
  </select>
  ```

---

## 🐛 Known Issues

1. **Frontend chưa cập nhật:** User vẫn thấy dropdown chọn provider/model (sẽ lỗi khi gọi API)
2. **Admin UI chưa có:** Phải dùng API trực tiếp để cấu hình tier
3. **Migration chưa chạy trên production:** Cần chạy thủ công

---

## 📚 Tài liệu tham khảo

- **Plan chi tiết:** `plan_3tier_model_system.md`
- **Test script:** `backend/test_tier_system.py`
- **Migration:** `migrations/0009_ai_tier_profiles.sql`

---

## 🔍 Rollback Plan

Nếu cần rollback:

1. **Revert migration:**
   ```sql
   DROP INDEX IF EXISTS idx_ai_task_profiles_tier;
   -- Không xóa cột tier để tránh mất data
   DELETE FROM ai_task_profiles WHERE task LIKE '%_tier%';
   ```

2. **Checkout nhánh cũ:**
   ```bash
   git checkout product
   ```

3. **Redeploy backend cũ**

---

## ✅ Test Results

Tất cả test đã pass:
- ✅ Schema validation
- ✅ Migration trên SQLite
- ✅ Service layer sync
- ✅ API validation
- ✅ Function signatures
- ✅ Import modules

**Sẵn sàng deploy!**
