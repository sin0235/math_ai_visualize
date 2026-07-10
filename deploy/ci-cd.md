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

## Bảo vệ branch `product`

Ruleset `Protect product delivery` (`18782037`) đang bắt buộc:

- Pull request trước khi merge.
- Branch phải cập nhật với `product`.
- `Backend tests`, `Frontend build`, `Docker build (smoke)` phải thành công.
- Giải quyết toàn bộ review thread.
- Không có bypass actor.
- Merge bằng squash hoặc rebase để giữ linear history.

Ruleset toàn repo hiện có tiếp tục chặn xóa branch, force-push và yêu cầu signed commit.

## DigitalOcean deploy

- App: `starfish-app` / service `math-ai-visualize`
- Branch deploy: **`product`**, `deploy_on_push: true`
- Health check App Platform: **`/api/health/ready`**

### Rollback nhanh

1. Trong DO App Platform, chọn deployment ổn định trước đó và **Redeploy**; cách này không cần vượt ruleset GitHub.
2. Kiểm tra `/api/health` và `/api/health/ready`.
3. Tạo revert PR để `product` khớp lại trạng thái production.

Không push SHA trực tiếp vào `product`; ruleset cố ý chặn đường này.

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

### Xoay credential

Thứ tự ưu tiên, không ghi giá trị vào log hoặc ticket:

1. Danh tính và dữ liệu: `GOOGLE_OAUTH_CLIENT_SECRET`, `FIREBASE_CREDENTIALS_JSON`, `APPWRITE_API_KEY`, `DATABASE_URL`, `TURNSTILE_SECRET_KEY`.
2. Nhà cung cấp AI: `D1_API_TOKEN`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_COMPAT_API_KEY`, `ROUTER9_API_KEY`, `OLLAMA_API_KEY`.
3. Gửi mail và media: `RESEND_API_KEY`, `CLOUDINARY_API_SECRET`, `CLOUDINARY_API_KEY`.

Với từng credential: tạo key mới nhưng giữ key cũ → cập nhật DO dưới loại `SECRET` → deploy → chạy `./deploy/verify-production.sh` và smoke integration liên quan → thu hồi key cũ. Không xoay nhiều provider cùng lúc.

Restore Postgres:

1. Xem backup: `doctl databases backups d1e9bd7a-b85f-4f29-ad5c-234a58740585`.
2. Fork từ backup gần nhất vào cluster tạm:

```bash
doctl databases fork math-ai-visualize-restore-drill \
  --restore-from-cluster-id d1e9bd7a-b85f-4f29-ad5c-234a58740585 \
  --wait
```

3. Kiểm tra schema và dữ liệu trên cluster tạm; không đổi `DATABASE_URL` production trong restore drill.
4. Xóa cluster tạm sau khi ghi nhận kết quả để dừng chi phí.

Fork restore tạo tài nguyên có phí. Chỉ chạy drill khi đã chấp nhận chi phí và lịch kiểm tra.

## Kiểm tra production bằng CLI

```bash
./deploy/verify-production.sh
```

Script dừng lỗi nếu backup quá 36 giờ, branch deploy/ruleset sai, credential chưa là `SECRET`, worker không chạy hoặc health/readiness lỗi. Có thể ghi đè `APP_ID`, `DB_CLUSTER_ID`, `BASE_URL`, `PRODUCT_RULESET_ID`, `MAX_BACKUP_AGE_HOURS` qua env.

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
