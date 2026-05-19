# Tài liệu Dự án: Hình toán AI (Hinh Math AI)

## 1. Tổng quan
**Hình toán AI** là một nền tảng giáo dục toán học tại Việt Nam, tập trung vào việc mô phỏng và dựng hình hình học (Lớp 10-12) từ đề bài văn bản hoặc hình ảnh. Ứng dụng sử dụng trí tuệ nhân tạo (LLM) để hiểu đề bài, trích xuất cấu trúc toán học và hiển thị chúng một cách trực quan thông qua GeoGebra hoặc Three.js.

## 2. Các Tính năng Chính
- **AI Rendering:** Tự động dựng hình 2D/3D từ mô tả tiếng Việt.
- **OCR (Nhận diện chữ từ ảnh):** Trích xuất đề bài từ ảnh chụp, clipboard hoặc file tải lên.
- **Khảo sát Hàm số:** Phân tích đạo hàm, bảng biến thiên, cực trị, tiệm cận bằng SymPy.
- **Geometry Solver:** Cung cấp lời giải hình học từng bước.
- **GeoGebra Lab:** Phòng thí nghiệm toán học tương tác tích hợp (Graphing, Geometry, 3D, Probability).
- **Lưu trữ & Lịch sử:** Lưu lại các hình đã dựng và lịch sử render cho người dùng.
- **Quản lý Model:** Hỗ trợ nhiều AI Provider (OpenRouter, NVIDIA, Ollama, 9router) với cơ chế fallback tự động.

## 3. Kiến trúc Kỹ thuật

### 3.1 Backend (Python / FastAPI)
Backend chịu trách nhiệm xử lý logic AI, tính toán hình học và quản lý dữ liệu.
- **Extractor Service:** Sử dụng LLM để chuyển đổi đề bài văn bản thành **MathScene JSON**.
- **Geometry Engine:** Chuẩn hóa tọa độ, tính toán giao điểm, kiểm tra tính hợp lệ của hình học.
- **Function Analyzer:** Sử dụng thư viện `SymPy` để phân tích các hàm số toán học lớp 12.
- **Renderers:** 
  - `geogebra_commands.py`: Chuyển đổi MathScene thành tập lệnh GeoGebra.
  - `solid_presets.py`: Cung cấp các khối hình học không gian mẫu (hình chóp, lăng trụ, v.v.).
- **Database:** Sử dụng `aiosqlite` (local) hoặc `Cloudflare D1` (production).
- **Authentication:** Hệ thống Auth hoàn chỉnh với JWT, Cookie session, và Google OAuth.

### 3.2 Frontend (TypeScript / React / Vite)
Frontend hiện đại, responsive và tập trung vào trải nghiệm người dùng.
- **Renderer Components:**
  - `GeoGebraView`: Nhúng GeoGebra applet để hiển thị hình học 2D và đồ thị.
  - `ThreeView`: Sử dụng `React Three Fiber` (Three.js) để hiển thị hình học không gian 3D tương tác.
- **UI/UX:**
  - Sidebar điều hướng, bảng điều khiển cấu hình AI (Settings).
  - Debug panel để xem và chỉnh sửa trực tiếp Scene JSON.
  - Hỗ trợ Markdown và LaTeX (KaTeX) cho đề bài và lời giải.

### 3.3 MinerU (Dịch vụ PDF)
Một module riêng biệt (đặt trong folder `MinerU`) chuyên trách việc chuyển đổi các file PDF toán học sang định dạng Markdown hoặc Word, hỗ trợ trích xuất công thức toán học bằng AI.

## 4. Cấu trúc Thư mục Chính
- `/backend`: Mã nguồn server FastAPI, services, và api routes.
- `/frontend`: Mã nguồn React app, components, hooks, và styles.
- `/migrations`: Các file SQL để khởi tạo và cập nhật cấu trúc database.
- `/docs`: Tài liệu chi tiết về Schema JSON và các loại bài toán hỗ trợ.
- `/MinerU`: Dịch vụ xử lý tài liệu PDF.

## 5. Luồng Xử lý Dữ liệu (Render Flow)
1. **Input:** Người dùng nhập văn bản hoặc tải ảnh đề bài.
2. **OCR (nếu có):** Chuyển ảnh thành văn bản.
3. **Extraction:** LLM phân tích văn bản -> sinh **MathScene JSON**.
4. **Validation/Normalization:** Backend kiểm tra và tính toán tọa độ cho các đối tượng.
5. **Rendering:** 
   - Nếu là 2D/Hàm số: Trả về tập lệnh GeoGebra.
   - Nếu là 3D: Trả về payload cho Three.js hoặc GeoGebra 3D.
6. **Display:** Frontend nhận payload và hiển thị lên UI.

## 6. Cấu hình AI & Môi trường
Dự án hỗ trợ linh hoạt các AI Provider:
- `AI_PROVIDER=auto`: Tự động chọn provider khả dụng.
- **OpenRouter/NVIDIA:** Dùng cho production với các model mạnh (GPT-4o, Claude 3.5, v.v.).
- **Ollama:** Dùng cho phát triển local với các model như Llama 3, Qwen 2.5.
- **9router:** Một proxy cục bộ để quản lý và định tuyến các yêu cầu AI.

## 7. Triển khai (Deployment)
- **Local:** 
  - Backend: `uvicorn app.main:app`
  - Frontend: `npm run dev`
- **Production:**
  - Frontend: Thường triển khai trên `Vercel` hoặc `Cloudflare Pages`.
  - Backend: Hỗ trợ `Docker`, `Heroku`, hoặc `VPS` chạy với `Gunicorn`.
  - Database: `Cloudflare D1`.
  - Storage: `Cloudflare R2` để lưu trữ ảnh tải lên.

---
*Tài liệu này được tạo tự động bởi Gemini CLI để tóm tắt kiến trúc và tính năng của dự án Hình toán AI.*
