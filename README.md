# AI Math Renderer

Ứng dụng AI hỗ trợ dựng hình và phân tích toán học từ đề bài văn bản hoặc ảnh. Backend chuyển đề bài thành dữ liệu toán học có cấu trúc, kiểm tra schema và tạo payload render; frontend hiển thị bằng GeoGebra, Three.js, KaTeX và các công cụ tương tác.

## Nội dung

- [Tổng quan](#tổng-quan)
- [Kiến trúc](#kiến-trúc)
- [Yêu cầu môi trường](#yêu-cầu-môi-trường)
- [Cài đặt local](#cài-đặt-local)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Database và migration](#database-và-migration)
- [Lệnh kiểm tra](#lệnh-kiểm-tra)
- [Triển khai production](#triển-khai-production)
- [API chính](#api-chính)
- [Vận hành](#vận-hành)
- [Bảo mật](#bảo-mật)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)

## Tổng quan

AI Math Renderer hiện hỗ trợ:

- Dựng hình 2D/3D từ đề bài tự nhiên.
- OCR ảnh đề bài và ảnh trong clipboard.
- Dựng scene GeoGebra, Three.js, xuất PNG/JPG/SVG/TikZ/PDF/HTML KaTeX.
- Khảo sát hàm số, giải đại số, phân tích biểu thức và mô phỏng giải tích.
- Auth backend bằng email/password, xác minh email, Google OAuth, session cookie.
- Lịch sử dựng hình, tài khoản người dùng, gói sử dụng, admin console.
- Chat hỗ trợ người dùng qua REST và WebSocket.
- Nhiều provider AI: OpenRouter, NVIDIA, Ollama, OpenAI-compatible, 9router.
- Lưu upload OCR qua database, R2 hoặc Appwrite.
- Lưu ảnh chat qua Cloudinary.

## Kiến trúc

```text
frontend React/Vite
  |
  | /api, /ws
  v
FastAPI backend
  |
  |-- API routes: auth, render, OCR, analyze, export, admin, chat
  |-- Services: AI provider, OCR, solver, geometry, storage, cleanup
  |-- Repositories: auth, history, admin, upload, feedback, chat
  |-- Database client: SQLite hoặc Cloudflare D1
  |-- External storage: R2, Appwrite, Cloudinary
```

Trong Docker production, nginx phục vụ frontend static và proxy `/api/`, `/ws/` vào Uvicorn nội bộ.

## Yêu cầu môi trường

Local:

- Python `>=3.11`
- Node.js `20` hoặc phiên bản tương thích với Vite 5
- npm
- SQLite cho môi trường phát triển local

Production:

- HTTPS bắt buộc nếu `ENVIRONMENT=production`
- D1 hoặc SQLite tuỳ cách deploy
- Provider AI đã cấu hình key/model
- Email provider nếu bật xác minh email
- Storage ngoài nếu muốn lưu upload ngoài database

## Cài đặt local

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Backend chạy mặc định tại:

```text
http://localhost:8000
```

Nếu cần OCR local đầy đủ:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-ocr.txt
```

`requirements-ocr.txt` gồm PaddleOCR, PaddlePaddle CPU, PyTorch CPU, OpenCV headless và pix2tex. Nhóm dependency này nặng hơn dependency backend chính.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend chạy mặc định tại:

```text
http://localhost:5173
```

Trong dev, `frontend/vite.config.ts` proxy:

- `/api` sang `http://localhost:8000`
- `/ws` sang `ws://localhost:8000`

## Cấu hình môi trường

Backend đọc biến môi trường từ `.env` và `backend/.env`. Không commit file `.env`.

### Cấu hình bắt buộc cho production

```bash
ENVIRONMENT=production
PUBLIC_APP_URL=https://your-app.example.com
CORS_ORIGINS=["https://your-app.example.com"]

SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
ALLOW_MISSING_ORIGIN_FOR_COOKIE_MUTATIONS=false
```

`Settings` sẽ chặn startup production nếu:

- `ENVIRONMENT=production` nhưng `SESSION_COOKIE_SECURE=false`
- `ENVIRONMENT=production` nhưng `ALLOW_MISSING_ORIGIN_FOR_COOKIE_MUTATIONS=true`
- `SESSION_COOKIE_SAMESITE=none` nhưng `SESSION_COOKIE_SECURE=false`

### Database

SQLite:

```bash
DATABASE_BACKEND=sqlite
SQLITE_PATH=backend/.data/hinh.db
AUTO_APPLY_SQLITE_MIGRATIONS=true
```

Cloudflare D1:

```bash
DATABASE_BACKEND=d1
D1_ACCOUNT_ID=...
D1_DATABASE_ID=...
D1_API_TOKEN=...
AUTO_APPLY_D1_MIGRATIONS=false
```

Trong production với D1, nên áp dụng migration trong pipeline deploy thay vì bật tự động khi startup.

### AI provider

Chọn provider mặc định:

```bash
AI_PROVIDER=auto
```

OpenRouter:

```bash
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEXT_MODEL=openai/gpt-oss-120b:free
OPENROUTER_VISION_MODEL=google/gemma-4-31b-it:free
OPENROUTER_VISION_FALLBACK_MODEL=google/gemma-4-26b-a4b-it:free
OPENROUTER_HTTP_REFERER=https://your-app.example.com
OPENROUTER_X_TITLE=AI Math Renderer
OPENROUTER_REASONING_ENABLED=false
```

NVIDIA:

```bash
NVIDIA_API_KEY=...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_TEXT_MODEL=qwen/qwen3-coder-480b-a35b-instruct
```

Ollama:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TEXT_MODEL=gpt-oss:120b
OLLAMA_API_KEY=
```

OpenAI-compatible:

```bash
OPENAI_COMPAT_API_KEY=...
OPENAI_COMPAT_BASE_URL=http://localhost:8080/v1
OPENAI_COMPAT_TEXT_MODEL=...
```

9router:

```bash
ROUTER9_BASE_URL=http://localhost:20128/v1
ROUTER9_API_KEY=...
ROUTER9_TEXT_MODEL=
ROUTER9_OCR_MODEL=
ROUTER9_ONLY=false
ROUTER9_ALLOWED_MODELS=[]
```

### Auth và email

Email gửi qua Resend:

```bash
RESEND_API_KEY=...
RESEND_FROM_EMAIL=no-reply@example.com
AUTH_EMAIL_DEV_MODE=false
REQUIRE_EMAIL_VERIFICATION=true
```

Email gửi qua SMTP:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_USE_TLS=true
AUTH_EMAIL_DEV_MODE=false
```

Google OAuth:

```bash
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-api.example.com/api/auth/google/callback
```

Cloudflare Turnstile:

```bash
TURNSTILE_SECRET_KEY=...
TURNSTILE_SITE_KEY=...
```

### Upload và storage

OCR upload:

```bash
OCR_IMAGE_MAX_MB=10
OCR_UPLOAD_STORAGE_PROVIDER=auto
OCR_UPLOAD_BASE64_RETENTION=retain
```

Giá trị hợp lệ của `OCR_UPLOAD_STORAGE_PROVIDER`:

- `auto`
- `appwrite`
- `r2`
- `database`

Giá trị hợp lệ của `OCR_UPLOAD_BASE64_RETENTION`:

- `retain`
- `external_only`

Cloudflare R2:

```bash
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_PUBLIC_BASE_URL=https://cdn.example.com
R2_UPLOAD_PREFIX=uploads
```

Appwrite:

```bash
APPWRITE_ENDPOINT=...
APPWRITE_PROJECT_ID=...
APPWRITE_API_KEY=...
APPWRITE_DATABASE_ID=...
APPWRITE_STORAGE_BUCKET_ID=...
APPWRITE_UPLOAD_PREFIX=uploads
APPWRITE_PUBLIC_BASE_URL=...
```

Cloudinary cho ảnh chat:

```bash
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
CLOUDINARY_CHAT_FOLDER=hinh/chat
CHAT_IMAGE_MAX_MB=5
```

### Phân tích & theo dõi

```bash
LOG_FORMAT=json                 # standard | json
SENTRY_DSN=                     # optional
TELEMETRY_CLIENT_ENABLED=true   # FE telemetry
ALERT_WEBHOOK_URL=              # optional Slack/Discord
ALERT_ERROR_SPIKE_THRESHOLD=30
ALERT_RENDER_FAIL_RATE_PERCENT=25
```

- `POST /api/telemetry/client-error` — client error (rate limited)
- `POST /api/telemetry/events` — page.view / feature.open (user login)
- `GET /api/health/ready` — readiness (DB)
- Admin: `/api/admin/analytics/*` + tab **Phân tích** (errors, funnel, AI usage, CSV export)
- Ops: [`deploy/analytics-ops.md`](deploy/analytics-ops.md)

### Hiệu năng & mở rộng

```bash
# Postgres connection pool (per process)
DATABASE_POOL_MIN=1
DATABASE_POOL_MAX=10

# Concurrent admission (system capacity, besides per-user rate limits)
RENDER_MAX_CONCURRENT=4
OCR_MAX_CONCURRENT=4
ALGEBRA_MAX_CONCURRENT=8

# Async render: POST /api/render/jobs + poll; worker: python -m app.worker
RENDER_ASYNC_ENABLED=false

# Optional Redis for multi-instance gates, job notify, chat WS pub/sub
REDIS_URL=redis://localhost:6379/0
```

Công thức pool Postgres: `instance_count × DATABASE_POOL_MAX < max_connections` của DB.

Container Docker chạy thêm `render-worker` qua supervisord. Bật `RENDER_ASYNC_ENABLED=true` để frontend poll job thay vì giữ HTTP 5 phút.

### OCR local

```bash
LOCAL_OCR_ENABLED=true
LOCAL_OCR_PREFER=auto
LOCAL_OCR_MIN_CONFIDENCE=0.55
LOCAL_OCR_TIMEOUT_SECONDS=30
LOCAL_OCR_MAX_CONCURRENCY=1
LOCAL_OCR_PADDLE_LANG=vi
LOCAL_OCR_USE_PIX2TEX=true
LOCAL_OCR_FALLBACK_TO_LLM=true
LOCAL_OCR_MODEL_NAME=paddleocr+pix2tex
```

### Frontend

Frontend đọc `frontend/.env` hoặc biến môi trường build:

```bash
VITE_API_BASE_URL=
VITE_MINERU_API_BASE_URL=
VITE_PDF_WORD_MAX_UPLOAD_MB=128
```

Nếu frontend và backend cùng origin, để trống `VITE_API_BASE_URL`. Nếu tách domain:

```bash
VITE_API_BASE_URL=https://your-api.example.com
```

## Database và migration

Migration SQL nằm trong thư mục `migrations/`.

Backend tự apply migration khi:

- `DATABASE_BACKEND=sqlite` và `AUTO_APPLY_SQLITE_MIGRATIONS=true`
- `DATABASE_BACKEND=d1` và `AUTO_APPLY_D1_MIGRATIONS=true`

Production khuyến nghị:

1. Apply migration trước khi deploy app mới.
2. Backup database trước migration.
3. Giữ `AUTO_APPLY_D1_MIGRATIONS=false` nếu dùng D1.
4. Kiểm tra `/api/admin/database/diagnostics` bằng tài khoản admin sau deploy.

Repository hiện có hai cặp migration legacy trùng prefix số:

- `0008_firebase_auth.sql` và `0008_model_management.sql`
- `0009_ai_tier_profiles.sql` và `0009_feedback.sql`

Code migration đã cho phép hai cặp legacy này. Migration mới nên dùng prefix số duy nhất.

Nếu dùng Cloudflare Wrangler, `wrangler.toml` đã khai báo:

```toml
name = "hinh"
migrations_dir = "migrations"
```

Hãy áp dụng migration D1 theo quy trình Cloudflare của môi trường deploy đang dùng.

## CI/CD

- **CI:** GitHub Actions — `.github/workflows/ci.yml` (pytest + frontend build + Docker smoke).
- **CD:** DigitalOcean App Platform deploy khi push branch `product`.
- Chi tiết vận hành, rollback, backup, branch protection: [`deploy/ci-cd.md`](deploy/ci-cd.md).

## Lệnh kiểm tra

Frontend:

```bash
cd frontend
npm run build
```

Backend:

```bash
cd backend
python -m pytest
```

Chạy một nhóm test cụ thể:

```bash
cd backend
python -m pytest tests/test_routes_render.py tests/test_auth_product.py
```

Lưu ý: một số test có thể phụ thuộc môi trường async, database tạm hoặc provider mock. Không dùng dữ liệu production để chạy test.

## Triển khai production

### Docker một container

Dockerfile hiện build frontend bằng Node 20, sau đó build image Python 3.11 chạy nginx và Uvicorn qua supervisord.

Build image:

```bash
docker build -t ai-math-renderer .
```

Run với SQLite local:

```bash
docker run --rm -p 8080:8080 \
  -e ENVIRONMENT=production \
  -e PUBLIC_APP_URL=https://your-app.example.com \
  -e CORS_ORIGINS='["https://your-app.example.com"]' \
  -e SESSION_COOKIE_SECURE=true \
  -e SESSION_COOKIE_SAMESITE=lax \
  -e ALLOW_MISSING_ORIGIN_FOR_COOKIE_MUTATIONS=false \
  -e DATABASE_BACKEND=sqlite \
  -e SQLITE_PATH=/app/data/hinh.db \
  -v "$PWD/.runtime-data:/app/data" \
  ai-math-renderer
```

Container lắng nghe cổng `8080`.

Trong container:

- nginx phục vụ frontend tại `/`
- nginx proxy `/api/` vào `127.0.0.1:8000`
- nginx proxy `/ws/` vào `127.0.0.1:8000`
- Uvicorn chạy `app.main:app`

### Backend API tách riêng

Nếu chạy backend riêng:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production cần reverse proxy HTTPS phía trước backend. Cấu hình timeout nên đủ dài cho render/OCR:

- API render: tối thiểu khoảng 320 giây nếu dùng fallback nhiều provider.
- WebSocket chat: tối thiểu khoảng 3600 giây.

### Frontend tách riêng

Build:

```bash
cd frontend
npm ci
npm run build
```

Deploy thư mục:

```text
frontend/dist
```

Nếu frontend tách domain với backend, đặt:

```bash
VITE_API_BASE_URL=https://your-api.example.com
```

SPA cần fallback mọi route về `index.html`. File `frontend/public/_redirects` hỗ trợ nền tảng dùng `_redirects`.

## API chính

Health:

```http
GET /api/health
GET /api/health/detail
GET /api/ai/status
```

Render:

```http
POST /api/render
POST /api/render/scene
```

OCR:

```http
POST /api/ocr
POST /api/ocr/uploads
```

Giải toán và phân tích:

```http
POST /api/solve
POST /api/algebra/solve
POST /api/analyze
POST /api/analyze/ocr
POST /api/problem/variants
```

Export:

```http
POST /api/export/png
POST /api/export/jpg
POST /api/export/svg
POST /api/export/tikz
POST /api/export/ggb
POST /api/export/pdf
POST /api/export/katex-html
```

Auth:

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
POST /api/auth/forgot-password
POST /api/auth/reset-password
POST /api/auth/verify-email
POST /api/auth/resend-verification
GET  /api/auth/google/start
GET  /api/auth/google/callback
```

User data:

```http
GET    /api/history
GET    /api/history/{job_id}
DELETE /api/history/{job_id}
GET    /api/user/settings
PUT    /api/user/settings
GET    /api/feedback/status
POST   /api/feedback
```

Admin:

```http
GET  /api/admin/summary
GET  /api/admin/database/diagnostics
POST /api/admin/database/cleanup
GET  /api/admin/system-settings
PUT  /api/admin/system-settings
POST /api/admin/providers/check-all
```

Chat:

```http
GET       /api/chat/conversation
POST      /api/chat/ws-ticket
WebSocket /ws/chat
```

## Vận hành

### Health check

Kiểm tra sau deploy:

```bash
curl -fsS https://your-app.example.com/api/health
```

Kiểm tra chi tiết hơn:

```bash
curl -fsS https://your-app.example.com/api/health/detail
```

### Admin diagnostics

Vào admin console hoặc gọi endpoint admin để kiểm tra:

- migration drift
- số lượng bản ghi từng bảng
- trạng thái system settings
- trạng thái uploaded file storage
- provider AI

### Cleanup dữ liệu

Endpoint admin:

```http
POST /api/admin/database/cleanup
```

Mặc định nên chạy `dry_run=true` trước. Với upload đã lưu ngoài R2/Appwrite, cleanup base64 nên giữ `verify_remote=true` để kiểm tra size và checksum trước khi xoá base64 trong database.

### Log

Trong Docker:

- stdout/stderr của Uvicorn ra log container.
- stdout/stderr của nginx ra log container.
- supervisord không ghi log file lâu dài.

### Backup

Production cần backup:

- Database D1 hoặc SQLite volume.
- Storage R2/Appwrite nếu dùng upload ngoài database.
- Cloudinary nếu ảnh chat là dữ liệu cần lưu dài hạn.
- Biến môi trường và secret trong secret manager của nền tảng deploy.

## Bảo mật

Checklist production:

- Bật HTTPS.
- Đặt `ENVIRONMENT=production`.
- Đặt `SESSION_COOKIE_SECURE=true`.
- Đặt `ALLOW_MISSING_ORIGIN_FOR_COOKIE_MUTATIONS=false`.
- Cấu hình `CORS_ORIGINS` đúng origin frontend.
- Không commit `.env`, database local, cache Wrangler hoặc file credential.
- Không bật `DEV_BYPASS_AUTH` ở production.
- Tắt `AUTH_EMAIL_DEV_MODE` nếu yêu cầu xác minh email thật.
- Dùng secret manager cho API key.
- Giới hạn quyền token D1/R2/Appwrite theo nhu cầu thực tế.
- Không log raw API key, bearer token hoặc ảnh base64.
- Backup trước migration hoặc cleanup destructive.

## Cấu trúc thư mục

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── core/             # cấu hình và logging
│   │   ├── db/               # database client và migration runner
│   │   ├── renderers/        # GeoGebra, Three.js, export renderer
│   │   ├── repositories/     # truy cập dữ liệu
│   │   ├── schemas/          # Pydantic schema
│   │   └── services/         # logic nghiệp vụ và tích hợp ngoài
│   ├── tests/                # test backend
│   ├── requirements.txt
│   ├── requirements-ocr.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/              # client gọi backend
│   │   ├── components/       # React components
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
├── migrations/               # SQL migrations
├── deploy/                   # nginx và supervisord config cho Docker
├── Dockerfile
└── wrangler.toml             # Cloudflare D1 metadata
```

## Ghi chú phát triển

- Giữ frontend API client theo domain trong `frontend/src/api/*`; `frontend/src/api/client.ts` chỉ là barrel export.
- Không commit artifact build như `dist`, `*.tsbuildinfo`, `*.egg-info`, `.data`, `.wrangler`.
- Migration mới nên có prefix số duy nhất.
- Khi thêm API mutation, kiểm tra `require_trusted_origin`.
- Khi thêm upload hoặc dữ liệu người dùng, kiểm tra ownership, storage provider và cleanup path.
- Khi sửa render/OCR, kiểm tra cả schema Pydantic, frontend type và test route liên quan.
