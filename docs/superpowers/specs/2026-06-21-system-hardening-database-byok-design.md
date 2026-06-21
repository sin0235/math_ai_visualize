# Thiết kế nâng cấp database, BYOK và hardening hệ thống

## Bối cảnh

Project đang ở giai đoạn phát triển và chưa có người dùng thật. Vì vậy đợt nâng cấp này được phép thay đổi schema, API nội bộ và UI cấu hình mạnh tay để làm sạch kiến trúc. Dữ liệu SQLite local hiện tại được xem là disposable, không phải nguồn dữ liệu chuẩn.

Các kiểm tra trước thiết kế cho thấy:

- Backend FastAPI đã có route/service/repository cho auth, render, OCR, upload, model registry, admin, chat và history.
- Database dùng SQLite hoặc Cloudflare D1 qua `DatabaseClient`.
- Migration SQL hiện có nhiều bước mới hơn DB local đang track.
- Frontend React/Vite đang build được nhưng bundle chính lớn.
- `routes_user_settings.py` hiện chỉ là stub.
- Runtime settings hiện có thể mang API key/base URL trong request, cần thay bằng BYOK có kiểm soát.

## Mục tiêu

1. Dọn artifact local khỏi git tracking.
2. Chuẩn hóa database/migration cho giai đoạn phát triển mới.
3. Thêm BYOK OpenAI-compatible an toàn cho user.
4. Không để API key người dùng lộ qua response, log, admin UI hoặc localStorage.
5. Không trừ quota admin/provider khi request dùng BYOK, nhưng vẫn có rate-limit kỹ thuật.
6. Hardening endpoint tính toán nặng, upload OCR và local OCR concurrency.
7. Làm rõ render degraded/mock fallback trong API, history và UI.
8. Giảm bundle frontend bằng code-splitting các phần nặng.
9. Giữ test/build pass sau khi triển khai.

## Ngoài phạm vi

- Không triển khai billing/payment thật.
- Không hỗ trợ nhiều BYOK provider cùng lúc.
- Không xây dựng secret manager bên ngoài. Secret người dùng được mã hóa bằng app-level encryption key trong backend.
- Không đảm bảo compatibility với SQLite local stale đang được track.
- Không chạy migration trên production thật trong quá trình triển khai này.

## Nguyên tắc dữ liệu

Vì chưa có user thật, schema có thể breaking với dữ liệu dev. Tuy nhiên migration vẫn nên rõ ràng, có thể chạy trên fresh DB và không làm thao tác ngoài repo. DB local được bỏ track khỏi git và có thể tạo lại từ migration.

Nếu cần xóa file vật lý hoặc chạy thao tác destructive ngoài working tree, cần xác nhận riêng.

## Thiết kế database

### Artifact local

Dừng tracking các file không thuộc source:

- `backend/.data/hinh.db`
- `backend/backend/.data/hinh.db`
- `backend/.codex_pytest_tmp_base_url/**`
- `.wrangler/cache/wrangler-account.json`

Giữ `.gitignore` hiện có vì đã có rule ignore các đường dẫn này.

### Migration runner

Nâng migration runner theo hướng:

- SQLite chạy từng migration file trong transaction.
- `schema_migrations` chỉ được ghi sau khi toàn bộ statement của migration thành công.
- D1 dùng batch/transaction nếu API hiện tại hỗ trợ an toàn; nếu chưa hỗ trợ đầy đủ, migration mới phải idempotent và test fresh DB phải bao phủ schema cuối.
- Giảm phụ thuộc vào parser `script.split(";")`. Nếu chưa thay bằng parser hoàn chỉnh, quy định migration không dùng semicolon trong string/trigger và thêm test để phát hiện rủi ro.

### Transaction/batch abstraction

Mở rộng `DatabaseClient` tối thiểu để hỗ trợ các workflow cần atomicity:

- rate-limit increment,
- auth token invalidate/create,
- chat get-or-create open conversation,
- cleanup/reset dev data,
- migration SQLite.

Không cần xây ORM lớn. Mục tiêu là thêm boundary giao dịch vừa đủ, phù hợp SQLite và D1.

### BYOK schema

Tạo schema riêng cho user AI settings, thay vì tiếp tục để `routes_user_settings.py` là stub.

Đề xuất bảng:

#### `user_ai_provider_settings`

- `user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE`
- `enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1))`
- `base_url TEXT NOT NULL DEFAULT ''`
- `api_key_ciphertext TEXT`
- `api_key_last4 TEXT`
- `api_key_updated_at TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

#### `user_ai_models`

- `id TEXT PRIMARY KEY`
- `user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `model_id TEXT NOT NULL`
- `label TEXT NOT NULL DEFAULT ''`
- `supports_vision INTEGER NOT NULL DEFAULT 0 CHECK (supports_vision IN (0, 1))`
- `enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- unique `(user_id, model_id)`

#### `user_ai_task_profiles`

- `user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `task TEXT NOT NULL`
- `model_id TEXT NOT NULL`
- `enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- primary key `(user_id, task)`

Task ban đầu:

- `render`
- `reasoning`
- `ocr`
- `solver`
- `chat`

`ocr` chỉ hợp lệ khi model tương ứng có `supports_vision = 1`.

### Constraint/index bổ sung

Thêm migration chuẩn hóa:

- Unique partial index cho mỗi user chỉ có một chat conversation `open` nếu vẫn giữ mô hình open conversation.
- Index cleanup/report:
  - `usage_events(created_at)`
  - `render_jobs(status, created_at)`
  - `chat_conversations(status, last_message_at DESC)`
- CHECK cho boolean/status quan trọng nếu tương thích schema mới:
  - user role/status,
  - provider/model enabled/allowed,
  - chat message type,
  - feedback status.

Vì đang ở dev stage, có thể dùng migration breaking để làm sạch schema nếu cần.

## Thiết kế BYOK OpenAI-compatible

### Chính sách

- Admin settings/model registry vẫn là mặc định toàn hệ thống.
- User có thể bật BYOK riêng.
- BYOK chỉ hỗ trợ một OpenAI-compatible base URL cho mỗi user.
- User tự quản model list và task profile của mình.
- Không nhận raw `api_key` hoặc `base_url` trong request render/OCR/solver nữa.
- API key chỉ được gửi ở endpoint lưu cấu hình BYOK.
- API key không được trả về response.
- API key không được lưu ở frontend storage.
- Admin không xem được raw API key của user.

### Encryption

Thêm cấu hình backend bắt buộc cho BYOK:

- `USER_SECRET_ENCRYPTION_KEY`

Yêu cầu:

- Nếu chưa cấu hình key, backend không cho lưu hoặc bật BYOK.
- Key phải có độ dài/format hợp lệ.
- API key lưu trong DB dưới dạng ciphertext.
- Decrypt chỉ diễn ra trong memory khi cần gọi provider.
- Response chỉ trả `api_key_configured`, `api_key_last4`, `api_key_updated_at`.

Nếu thư viện mã hóa hiện có chưa đủ, có thể thêm dependency nhỏ, ổn định như `cryptography`. Dependency này chỉ dùng ở backend service mã hóa secret.

### SSRF protection

Base URL BYOK phải được validate trước khi lưu và trước khi dùng:

- Production chỉ cho `https`.
- Development có thể cho `http://localhost` hoặc loopback nếu cần test local.
- Chặn private IP, loopback trong production, link-local, multicast, unspecified, metadata IP.
- Resolve hostname và chặn nếu bất kỳ resolved IP nào thuộc dải cấm.
- Không follow redirect chéo host.
- Timeout ngắn.
- Không log URL kèm credential hoặc Authorization header.

### API user settings

Thay `routes_user_settings.py` bằng API thật.

#### `GET /api/user/settings`

Trả về:

- BYOK enabled hay không.
- base URL.
- `api_key_configured`.
- `api_key_last4`.
- danh sách model user khai báo.
- task profiles.
- metadata validation an toàn.

Không trả raw API key.

#### `PUT /api/user/settings/ai-provider`

Cập nhật:

- enabled,
- base URL,
- API key mới nếu user gửi,
- nếu API key field rỗng hoặc absent thì giữ key cũ.

#### `PUT /api/user/settings/ai-models`

Thay thế hoặc cập nhật danh sách model user quản lý.

Validation:

- model id không rỗng,
- giới hạn số model,
- label length,
- supports_vision boolean.

#### `PUT /api/user/settings/ai-task-profiles`

Cập nhật task-to-model mapping.

Validation:

- task thuộc allowlist,
- model tồn tại và enabled,
- `ocr` yêu cầu model `supports_vision = 1`.

#### `POST /api/user/settings/ai-provider/check`

Kiểm tra base URL/API key OpenAI-compatible bằng request nhẹ.

Yêu cầu:

- Không lưu secret nếu check fail.
- Không log secret.
- Trả lỗi rõ nhưng không lộ credential.

## AI resolution flow

Tạo service riêng, ví dụ `user_ai_settings` hoặc `byok_settings`, để route không chứa logic nghiệp vụ.

Khi một tác vụ cần AI:

1. Load user BYOK settings nếu có user đăng nhập.
2. Nếu BYOK enabled và task profile hợp lệ:
   - decrypt API key,
   - dựng OpenAI-compatible client,
   - dùng model user chọn,
   - gắn metadata `ai_source = "byok"`,
   - không record quota usage provider admin.
3. Nếu BYOK không hợp lệ hoặc disabled:
   - dùng model registry/admin settings hiện tại,
   - giữ quota hiện tại.
4. Nếu BYOK được bật nhưng cấu hình thiếu hoặc lỗi validation:
   - trả lỗi rõ cho user thay vì âm thầm dùng admin provider, trừ khi UI/request chọn fallback admin một cách rõ ràng.

Luồng này áp dụng cho các task phù hợp:

- render,
- reasoning,
- OCR/vision,
- solver explanation,
- chat nếu chat AI dùng cùng provider.

## Rate-limit, timeout và quota

### Endpoint cần bảo vệ thêm

- `/api/analyze`
- `/api/algebra/solve` kể cả non-AI path
- các route có SymPy hoặc xử lý biểu thức nặng

### Nguyên tắc

- BYOK không trừ quota AI/admin.
- BYOK vẫn chịu rate-limit kỹ thuật theo user/IP để bảo vệ CPU/RAM/backend.
- Non-AI deterministic solver cũng chịu rate-limit và timeout nếu có thể tốn CPU.
- Input có complexity guard:
  - độ dài text/expression,
  - số symbol,
  - nested depth hoặc số phép biến đổi nếu có thể đo an toàn.

### Atomic rate-limit

Refactor rate-limit repository sang atomic increment:

- dùng UPSERT/increment một statement nếu SQLite/D1 hỗ trợ,
- nếu không, dùng transaction/batch abstraction,
- trả `remaining` và `retry_after_seconds` từ trạng thái sau increment.

## Upload và OCR

### Upload hardening

Nâng `upload_storage`:

- đọc file theo chunk,
- dừng ngay khi vượt `ocr_image_max_mb`,
- không đọc toàn bộ body trước khi check size,
- validate image bằng magic bytes hoặc decoder an toàn,
- chuẩn hóa content type từ nội dung thực tế nếu có thể,
- giữ checksum sha256 và size verification cho remote storage.

### Local OCR concurrency

- Enforce `local_ocr_max_concurrency` bằng semaphore global.
- Nếu hết slot, trả `429` hoặc `503` với thông báo thử lại.
- Timeout vẫn áp dụng trên từng job.
- Không tạo fire-and-forget task.

## Render degraded/mock fallback

Giữ mock fallback để không phá dev/test flow, nhưng response phải rõ ràng.

Thêm metadata vào `RenderResponse` hoặc schema tương đương:

- `degraded: bool`
- `fallback_source: "none" | "mock" | "provider_fallback"`
- `ai_source: "admin" | "byok" | "none"`

History lưu các field này để admin/user có thể biết render nào là degraded.

Frontend hiển thị warning rõ khi kết quả là mock/degraded.

## Frontend

### User settings UI

Thay UI/settings liên quan bằng BYOK settings thực:

- bật/tắt BYOK,
- nhập base URL OpenAI-compatible,
- nhập/cập nhật API key,
- hiển thị trạng thái key đã cấu hình và last4,
- không hiển thị lại raw key,
- thêm/sửa/xóa model,
- đánh dấu model hỗ trợ vision,
- chọn model theo task.

Không lưu API key trong localStorage/sessionStorage.

### Runtime settings

Loại bỏ hoặc vô hiệu hóa phần gửi `api_key/base_url` theo từng request render/OCR/solver. Runtime request chỉ được chọn các lựa chọn không chứa secret, hoặc dùng task profile đã lưu.

### Code-splitting

Giảm bundle chính bằng lazy import:

- admin console,
- analyzer/function analysis,
- solver/algebra/simulation,
- GeoGebra lab,
- PDF tool,
- Three/renderer-heavy components nếu tách được an toàn.

Mục tiêu là `npm run build` vẫn pass và cảnh báo chunk lớn giảm đáng kể nếu có thể.

## Error handling và logging

- Chuẩn hóa DB constraint errors giữa SQLite và D1.
- Không log raw API key, Authorization header hoặc ciphertext.
- Error response không chứa secret.
- Audit chỉ ghi metadata an toàn như user id, task, provider type, model id, status.
- Khi provider BYOK lỗi, trả lỗi giúp user chỉnh cấu hình, không dump response nhạy cảm.

## Testing

### Backend

Thêm hoặc cập nhật test cho:

- fresh DB apply all migrations,
- artifact path không còn tracked,
- BYOK encryption không trả raw secret,
- thiếu `USER_SECRET_ENCRYPTION_KEY` thì không bật/lưu BYOK,
- URL validation chặn private/link-local/metadata,
- user settings API CRUD,
- task profile validation, đặc biệt OCR cần vision model,
- BYOK AI resolution dùng OpenAI-compatible client,
- BYOK không trừ quota admin,
- rate-limit atomic,
- upload quá lớn, MIME giả, file rỗng,
- OCR concurrency limit,
- render degraded/fallback metadata,
- D1/SQLite constraint error mapping nếu có hạ tầng test phù hợp.

### Frontend

- `npm run build`.
- Type-check qua build.
- Nếu test hiện có hỗ trợ React component, thêm test cho BYOK settings form.

### Full verification

- `cd backend && python -m pytest`
- `cd frontend && npm run build`

## Kế hoạch rollout trong repo dev

1. Dọn tracking artifact local.
2. Nâng database/migration foundation.
3. Thêm BYOK schema/service/API.
4. Tích hợp BYOK vào AI resolution flow.
5. Hardening rate-limit/upload/OCR/render degraded.
6. Cập nhật frontend user settings và code-splitting.
7. Chạy test/build đầy đủ.
8. Báo cáo thay đổi và rủi ro còn lại.

## Tiêu chí hoàn thành

- Không còn DB/cache local tracked.
- Fresh DB apply migration thành công.
- User có thể cấu hình BYOK OpenAI-compatible mà không lộ key.
- Runtime request không còn mang raw API key/base URL cho tác vụ AI.
- BYOK không trừ quota admin nhưng vẫn bị rate-limit kỹ thuật.
- Upload/OCR có hard cap và concurrency guard.
- Render fallback hiển thị degraded rõ ràng.
- Frontend build pass và settings UI phù hợp BYOK.
- Backend test pass.
