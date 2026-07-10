# CI/CD & vận hành

## Hiện trạng

| Lớp | Công cụ | Hành vi |
|-----|---------|---------|
| CI | **GitHub Actions** (`.github/workflows/ci.yml`) | Test backend + build frontend (+ Docker smoke trên PR/`product`) |
| CD | **DigitalOcean App Platform** | `deploy_on_push: true` từ branch `product` → build Dockerfile → live |
| DB backup | DO Managed Postgres | Backup hàng ngày (xem DO control panel) |
| Source | GitHub | Repo `sin0235/math_ai_visualize` |

Luồng khuyến nghị:

```text
feature branch → PR vào product
       ↓
  GitHub Actions CI (bắt buộc xanh)
       ↓
  merge / push product
       ↓
  DO auto deploy
       ↓
  smoke: /api/health + /api/health/ready
```

## GitHub Actions jobs

1. **backend** — Python 3.11, `pip install -r requirements.txt`, `pytest` (bỏ large-scale suites).
2. **frontend** — Node 20, `npm ci`, `npm run build` (tsc + vite).
3. **docker** — build image (không push), chỉ PR hoặc push `product`.

### Chạy local giống CI

```bash
# Backend
cd backend
pip install -r requirements.txt 'pytest>=8.3.0'
python -m pytest -q --tb=line \
  --ignore=tests/test_geometry_scenes_large_scale.py \
  --ignore=tests/test_math_core_large_scale.py

# Frontend
cd frontend
npm ci
npm run build
```

## Bảo vệ branch `product` (làm 1 lần trên GitHub)

Repo Settings → Branches → Branch protection rule cho `product`:

- [x] Require a pull request before merging *(khuyến nghị)*
- [x] Require status checks to pass before merging  
  - Checks: `Backend tests`, `Frontend build` (và `Docker build (smoke)` nếu muốn chặt)
- [x] Require branches to be up to date before merging
- [ ] (Tuỳ chọn) Require review from Code Owners
- [x] Do not allow bypassing the above settings *(admin vẫn nên giữ ngoại lệ khẩn cấp có kiểm soát)*

Hoặc dùng `gh` (cần quyền admin):

```bash
gh api -X PUT repos/sin0235/math_ai_visualize/branches/product/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["Backend tests","Frontend build"]}' \
  -F enforce_admins=false \
  -F required_pull_request_reviews=null \
  -F restrictions=null
```

> Lưu ý: API protection schema có thể thay đổi; UI Settings thường dễ hơn.

## DigitalOcean deploy

- App: `starfish-app` / service `math-ai-visualize`
- Branch deploy: **`product`**
- Health check hiện tại: `/api/health` (liveness)
- Nên bổ sung / chuyển dần sang **`/api/health/ready`** (DB readiness) trong App settings

### Rollback nhanh

1. Tìm commit trước trên `product` còn ổn.
2. `git push origin <good-sha>:product` (hoặc revert PR).
3. DO sẽ auto rebuild.
4. Hoặc trên DO: Deployments → Redeploy deployment cũ.

### Migration

- Postgres: auto apply lúc startup (`apply_migrations`).
- **Luôn** kiểm tra migration trên staging/local trước khi merge `product`.
- CI có guard cấm `TIMESTAMPTZ` + `CURRENT_TIMESTAMP` (vì client cast timestamp → text).

## Backup & khôi phục

| Dữ liệu | Cơ chế |
|---------|--------|
| Postgres | DO automated backups (daily) — test restore định kỳ |
| Uploads R2/Appwrite | Bật versioning / lifecycle trên bucket nếu dùng |
| Chat images Cloudinary | Backup theo gói Cloudinary hoặc export định kỳ |
| Secrets | DO App env; không commit `.env` |

Restore Postgres (outline):

1. DO → Databases → `math-ai-visualize-pg` → Backups → Restore / fork.
2. Cập nhật `DATABASE_URL` app trỏ DB mới (hoặc restore in-place theo wizard DO).
3. Redeploy app, kiểm tra `/api/health/ready`.

## Checklist sau mỗi deploy production

```bash
curl -fsS https://math-renderer.sin-studio.tech/api/health
curl -fsS https://math-renderer.sin-studio.tech/api/health/ready
# Admin: /admin → Phân tích + Database diagnostics
```

## Nâng cấp tiếp (chưa bắt buộc)

- Staging app DO + branch `staging`
- Job migrate-before-deploy tách khỏi cold start
- Slack/email notify khi CI hoặc deploy fail
- Dependabot PRs (đã bật cấu hình `.github/dependabot.yml`)
