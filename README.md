# Hình toán AI

Ứng dụng MVP dựng hình toán 10-12 từ đề bài dạng văn bản. Backend trích xuất scene JSON có cấu trúc, frontend render bằng GeoGebra cho 2D/đồ thị và React Three Fiber cho hình học không gian.

## Trạng thái hiện tại

- Backend FastAPI có mock extractor, chưa gọi OpenRouter.
- Frontend React/Vite có form nhập đề, GeoGebra renderer, Three.js renderer và JSON debug panel.
- Hỗ trợ mẫu:
  - `Cho A(1,2), B(4,5). Vẽ đường thẳng AB.`
  - `Vẽ đồ thị hàm số y = x^2 - 2x + 1.`
  - `Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.`

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
OPENROUTER_TEXT_MODEL=openrouter/nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_VISION_MODEL=qwen/qwen2.5-vl-72b-instruct:free
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TEXT_MODEL=qwen3.5
OLLAMA_API_KEY=
```

`AI_PROVIDER=auto` sẽ thử Ollama trước, sau đó OpenRouter, rồi fallback mock nếu provider chưa sẵn sàng. Có thể đặt `AI_PROVIDER=ollama`, `openrouter`, hoặc `mock` để ép một chế độ.

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

Response gồm `scene` và `payload`. Frontend dùng `payload.renderer` để chọn GeoGebra hoặc Three.js.

## Nguyên tắc an toàn

LLM sau này chỉ được sinh JSON theo schema. Backend validate JSON rồi tự tạo GeoGebra commands hoặc Three.js scene; không chạy code tuỳ ý do LLM sinh ra.
