# Hình toán AI

Ứng dụng dựng hình toán 10-12 từ đề bài văn bản hoặc ảnh đề bài. Backend trích xuất scene JSON có cấu trúc, validate dữ liệu rồi tạo payload render; frontend render bằng GeoGebra cho 2D/đồ thị và React Three Fiber cho hình học không gian.

## Trạng thái hiện tại

- Backend FastAPI hỗ trợ OpenRouter, NVIDIA, Ollama/OpenAI-compatible, 9router và mock fallback khi AI provider không sẵn sàng.
- Frontend React/Vite có form nhập đề, OCR ảnh/clipboard, chọn provider/model, quét model 9router, GeoGebra renderer, Three.js renderer, chỉnh hình 3D và Scene JSON debug panel.
- API key override nhập trên UI chỉ dùng trong phiên/tab hiện tại và không persist vào `localStorage`; cấu hình lâu dài nên đặt trong backend `.env`.
- Hỗ trợ mẫu:
  - `Cho A(1,2), B(4,5). Vẽ đường thẳng AB.`
  - `Vẽ đồ thị hàm số y = x^2 - 2x + 1.`
  - `Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.`
  - `Trong Oxyz cho A(1,2,3), B(4,5,6).`

## Chạy backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
uvicorn app.main:app --reload
```

Backend chạy tại `http://localhost:8000`.

## Cấu hình AI

Các biến môi trường backend hỗ trợ:

```bash
AI_PROVIDER=auto
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEXT_MODEL=...
OPENROUTER_VISION_MODEL=...
OPENROUTER_VISION_FALLBACK_MODEL=...
NVIDIA_API_KEY=...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_TEXT_MODEL=...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TEXT_MODEL=...
OLLAMA_API_KEY=...
ROUTER9_BASE_URL=http://localhost:20128/v1
ROUTER9_API_KEY=...
ROUTER9_ONLY_MODE=false
```

`AI_PROVIDER=auto` sẽ thử provider theo cấu hình backend và fallback về mock nếu không có provider khả dụng. Có thể chọn trực tiếp provider/model trên UI cho từng lần dựng hình.

Nếu chạy Ollama local thì dùng `OLLAMA_BASE_URL=http://localhost:11434` và có thể để trống `OLLAMA_API_KEY`. Nếu dùng Ollama cloud/OpenAI-compatible endpoint thì dùng base URL tương ứng và cấu hình API key nếu endpoint yêu cầu.

9router chạy local mặc định tại `http://localhost:20128/v1`. Sau khi mở 9router và cấu hình provider trong dashboard của nó, vào tab `9router` trên UI để quét `GET /v1/models`, chọn model được phép hiển thị, rồi chọn model đó ở form dựng hình. Khi bật 9router-only, render/OCR chỉ dùng các model 9router đã chọn.

## Cấu hình production backend

Auth chạy hoàn toàn qua backend: email/password, email verification bằng Resend/SMTP, Google OAuth backend và cookie `hinh_session`.

```bash
DATABASE_BACKEND=d1
D1_ACCOUNT_ID=...
D1_DATABASE_ID=...
D1_API_TOKEN=...

R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_UPLOAD_PREFIX=uploads

PUBLIC_APP_URL=https://your-domain.com
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax

RESEND_API_KEY=...
RESEND_FROM_EMAIL=...
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-domain.com/api/auth/google/callback
```

D1 migrations nên được apply trong workflow deploy hoặc bật `AUTO_APPLY_D1_MIGRATIONS=true` nếu muốn backend tự apply khi startup.

## Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend chạy tại `http://localhost:5173` và proxy API sang backend.

## API chính

```http
POST /api/render
Content-Type: application/json

{
  "problem_text": "Cho A(1,2), B(4,5). Vẽ đường thẳng AB.",
  "grade": 10
}
```

Response gồm `scene`, `payload` và `warnings`. Frontend dùng `payload.renderer` để chọn GeoGebra hoặc Three.js.

```http
POST /api/ocr
Content-Type: application/json

{
  "image_data_url": "data:image/png;base64,..."
}
```

OCR nhận ảnh PNG/JPEG/WebP/GIF dạng data URL, có giới hạn kích thước ở backend và phù hợp nhất với ảnh đề bài rõ chữ.

## Tính năng frontend đáng chú ý

- OCR bằng upload ảnh, kéo-thả ảnh hoặc dán ảnh từ clipboard.
- Settings cho provider/model, OCR, fallback và 9router-only.
- Three.js hỗ trợ xoay hình, zoom, pan/kéo góc nhìn, kéo điểm, nối điểm, thêm điểm và tạo chân nối xuống đoạn.
- Trên mobile có cảnh báo renderer tối ưu cho desktop, tự cuộn xuống kết quả sau khi render và nút “Xem hình vừa dựng”.
- Scene JSON debug panel cho phép xem, sao chép và tải JSON render.

## Nguyên tắc an toàn

LLM chỉ được sinh JSON theo schema. Backend validate JSON rồi tự tạo GeoGebra commands hoặc Three.js scene; không chạy code tuỳ ý do LLM sinh ra. Log/error provider được rút gọn và che API key, bearer token, secret và dữ liệu ảnh base64.
