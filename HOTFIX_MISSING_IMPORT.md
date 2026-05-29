# 🚨 Hotfix: Missing import get_settings

## Lỗi Production

**Commit:** `304b6b7`

**Lỗi:**
```python
NameError: name 'get_settings' is not defined
File "/app/backend/app/services/extractor.py", line 84, in extract_scene
  settings = get_settings()
```

**Nguyên nhân:**
Khi refactor `extract_scene()` để đơn giản hóa (xóa `runtime_settings`), mình đổi:
```python
# Trước
settings = await _build_render_settings(db, runtime_settings)

# Sau
settings = get_settings()  # ❌ Thiếu import
```

Nhưng quên thêm `get_settings` vào import statement.

## Fix

**File:** `backend/app/services/extractor.py`

**Thay đổi:**
```python
# Trước
from app.core.config import Settings

# Sau
from app.core.config import Settings, get_settings
```

## Test

```bash
✓ Import extract_scene OK
✓ Import get_settings OK
✓ get_settings() returns: <class 'app.core.config.Settings'>
```

## Deploy

1. Pull code mới từ nhánh `feature/3-tier-model-system`
2. Restart backend
3. Test API `/api/render` với tier

**Hoặc cherry-pick commit này vào nhánh product:**
```bash
git cherry-pick 304b6b7
```

## Lesson Learned

- ❌ Test local không đủ (vì import có thể cache)
- ✅ Cần test import trực tiếp: `python -c "from module import function"`
- ✅ Cần test trên môi trường giống production (Docker container)
- ✅ Cần CI/CD pipeline để catch lỗi này trước khi deploy

## Checklist cho lần sau

- [ ] Test import trực tiếp sau mỗi refactor
- [ ] Chạy `python -m py_compile` để check syntax
- [ ] Test trong Docker container trước khi push
- [ ] Setup CI/CD để auto-test imports

---

**Status:** ✅ FIXED - Pushed to feature/3-tier-model-system
