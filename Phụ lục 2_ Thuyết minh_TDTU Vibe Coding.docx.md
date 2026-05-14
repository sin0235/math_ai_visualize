
**TRƯỜNG ĐẠI HỌC TÔN ĐỨC THẮNG**

**CUỘC THI**  
**Cuộc thi "TDTU Vibe Coding" mở rộng năm 2026**

**Tên đề tài: AI Math Renderer – Nền tảng dựng hình toán học từ ngôn ngữ tự nhiên bằng trí tuệ nhân tạo**

Thuộc lĩnh vực: Ứng dụng trí tuệ nhân tạo (AI) trong giáo dục

**NHÓM/CÁ NHÂN THỰC HIỆN:**

| STT | Họ và tên | MSSV | Khoa |
| :---: | :---- | :---: | :---- |
| 1 | Trần Phúc Toàn | 23110344 | Khoa Công nghệ Thông tin |

*TP. Hồ Chí Minh, tháng 05/2026*

---

## A. Tóm tắt đề tài

**AI Math Renderer** là nền tảng web ứng dụng trí tuệ nhân tạo (AI) để chuyển đổi bài toán hình học và đại số từ ngôn ngữ tự nhiên (văn bản hoặc hình ảnh đề bài) thành mô hình đồ họa tương tác 2D/3D. Hệ thống hỗ trợ học sinh lớp 10–12 trực quan hóa các bài toán hình học phẳng, hình học không gian Oxyz, đồ thị hàm số, đồng thời cung cấp công cụ khảo sát hàm số, giải từng bước (step-by-step solver), mô phỏng tích phân – lượng giác và phòng thí nghiệm GeoGebra tích hợp.

Sản phẩm giải quyết bài toán thực tế: học sinh và giáo viên thường gặp khó khăn trong việc dựng hình chính xác từ đề bài văn bản, đặc biệt là hình học không gian 3D. AI Math Renderer tự động hóa hoàn toàn quy trình này — từ nhận diện đề bài (bao gồm OCR ảnh), trích xuất thông tin hình học bằng AI, đến render hình tương tác và xuất bản dưới dạng TikZ/LaTeX/PDF chuẩn học thuật.

**Link sản phẩm:** [https://math-renderer.sin-studio.tech/](https://math-renderer.sin-studio.tech/)

---

## B. Nội dung đề tài

### 1. Lý do chọn đề tài

Trong chương trình toán THPT (lớp 10–12), hình học chiếm tỉ trọng lớn và là phần gây khó khăn nhất cho học sinh do đòi hỏi khả năng tưởng tượng không gian và dựng hình chính xác. Cụ thể:

- **Hình học không gian (lớp 11–12):** Học sinh cần hình dung các hình chóp, lăng trụ, mặt phẳng cắt trong không gian 3D — điều rất khó thực hiện chỉ trên giấy 2D. Nhiều học sinh mất điểm không phải vì thiếu kiến thức mà vì không dựng được hình đúng.

- **Đồ thị hàm số (lớp 12):** Khảo sát và vẽ đồ thị hàm số đòi hỏi nhiều bước tính toán (đạo hàm, cực trị, tiệm cận, bảng biến thiên) trước khi có thể vẽ hình. Quy trình thủ công dễ sai sót và mất thời gian.

- **Hình học tọa độ Oxyz (lớp 12):** Biểu diễn điểm, đường thẳng, mặt phẳng trong không gian 3D trên giấy 2D luôn là thách thức cho cả học sinh lẫn giáo viên.

- **Giáo viên soạn tài liệu:** Việc tạo hình minh họa chất lượng cao cho đề thi, bài giảng đòi hỏi phần mềm chuyên dụng (GeoGebra, TikZ) với đường cong học tập cao.

Các giải pháp hiện có trên thị trường (GeoGebra, Desmos, Wolfram Alpha) đều yêu cầu người dùng nhập lệnh hoặc công thức toán — không hỗ trợ nhập bằng ngôn ngữ tự nhiên tiếng Việt. **AI Math Renderer** là giải pháp đầu tiên cho phép học sinh chỉ cần nhập đề bài bằng tiếng Việt (hoặc chụp ảnh đề) và hệ thống tự động dựng hình tương ứng.

---

### 2. Đối tượng người dùng hướng tới

| Đối tượng | Nhu cầu chính |
| :---- | :---- |
| **Học sinh THPT (lớp 10–12)** | Dựng hình nhanh từ đề bài, kiểm tra bài làm hình học, khảo sát hàm số, ôn thi trực quan |
| **Giáo viên Toán** | Soạn hình minh họa cho đề thi/bài giảng, xuất hình dạng TikZ/LaTeX/PDF chuẩn học thuật |
| **Sinh viên Đại học** | Trực quan hóa bài toán hình học giải tích, hình học không gian nâng cao, tọa độ Oxyz |
| **Người tự học** | Công cụ học toán trực quan, tương tác, có lời giải từng bước bằng tiếng Việt |

---

### 3. Mô tả ý tưởng và hướng dẫn sử dụng sản phẩm

#### 3.1. Ý tưởng cốt lõi

AI Math Renderer hoạt động theo pipeline 4 giai đoạn:

```
Đề bài (văn bản/ảnh) → AI trích xuất Scene JSON → Validate & Normalize → Render tương tác 2D/3D
```

1. **Nhận diện đề bài:** Người dùng nhập văn bản tiếng Việt hoặc chụp/dán ảnh đề bài. Hệ thống OCR trích xuất text từ ảnh.
2. **AI trích xuất hình học:** Mô hình AI (đa nhà cung cấp: OpenRouter, NVIDIA, Ollama) phân tích ngữ nghĩa đề bài và sinh ra Scene JSON chứa thông tin hình học (điểm, đoạn thẳng, đường tròn, mặt phẳng, hàm số...).
3. **Validate & Normalize:** Backend xác thực dữ liệu JSON theo schema chặt, tự tính toán tọa độ giao điểm, chuẩn hóa hình học.
4. **Render tương tác:** Frontend render bằng GeoGebra (2D, đồ thị) hoặc Three.js (hình học không gian 3D) với đầy đủ tương tác: xoay, zoom, kéo điểm, thêm điểm, nối đoạn.

#### 3.2. Các chức năng chính

**Chức năng 1: Dựng hình từ ngôn ngữ tự nhiên (Trang chính)**

Người dùng nhập đề bài toán bằng tiếng Việt, hệ thống tự động dựng hình tương ứng.

- Hỗ trợ hình học phẳng 2D (tam giác, tứ giác, đường tròn, đường thẳng...)
- Hỗ trợ hình học không gian 3D (hình chóp, lăng trụ, mặt phẳng cắt...)
- Hỗ trợ đồ thị hàm số (hàm bậc 2, bậc 3, phân thức, lượng giác...)
- Hỗ trợ hình học tọa độ Oxyz (điểm, vector, mặt phẳng trong không gian)
- OCR: nhận dạng đề bài từ ảnh chụp/clipboard
- Chọn AI model phù hợp (auto hoặc thủ công)

*Ví dụ đầu vào:*
- `Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Vẽ đường trung tuyến AM.`
- `Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.`
- `Vẽ đồ thị hàm số y = x^2 - 2x + 1.`

**Chức năng 2: Khảo sát hàm số**

Công cụ phân tích toàn diện hàm số bằng SymPy:

- Tính đạo hàm, đạo hàm cấp 2
- Xác định cực trị (cực đại, cực tiểu), điểm uốn
- Tìm tiệm cận (đứng, ngang, xiên)
- Tìm giao điểm với trục tọa độ
- Lập bảng biến thiên (BBT) kiểu Việt Nam với mũi tên ↗/↘
- Vẽ đồ thị hàm số tương tác qua GeoGebra
- Hỗ trợ ký hiệu Việt: `x^2`, `sqrt(x)`, `exp(x)`, `ln(x)`...

**Chức năng 3: Giải từng bước (Step-by-Step Solver)**

- Giải bài toán hình học chi tiết từng bước bằng AI
- Trình bày lời giải bằng tiếng Việt với công thức LaTeX
- Hỗ trợ các dạng bài: tính khoảng cách, góc, diện tích, thể tích

**Chức năng 4: Mô phỏng toán học (Simulation)**

- Mô phỏng tích phân (diện tích dưới đường cong) với animation
- Mô phỏng đường tròn lượng giác tương tác
- Trực quan hóa các khái niệm giải tích

**Chức năng 5: GeoGebra Lab**

- Phòng thí nghiệm toán học tích hợp đầy đủ 4 module GeoGebra:
  - Graphing Calculator (Máy tính đồ thị)
  - Geometry (Hình học)
  - 3D Calculator (Máy tính 3D)
  - Probability Calculator (Máy tính xác suất)
- Nhập lệnh GeoGebra trực tiếp
- Mẫu nhanh (preset): Parabol, đường tròn, elip, hyperbol, sin(x)...
- Xuất hình: PNG, SVG, PDF
- Lưu/tải trạng thái workspace

**Chức năng 6: Xuất bản chuẩn học thuật**

- Xuất hình dưới dạng mã TikZ (LaTeX)
- Xuất GeoGebra commands
- Xuất PNG/SVG/PDF
- Phù hợp cho soạn đề thi, bài giảng, luận văn

#### 3.3. Hướng dẫn sử dụng

**Bước 1:** Truy cập [https://math-renderer.sin-studio.tech/](https://math-renderer.sin-studio.tech/)

**Bước 2:** Chọn công cụ phù hợp từ menu **"Công cụ"**:
- **Dựng hình:** Nhập đề bài toán → Nhấn "Dựng hình" → Xem kết quả 2D/3D
- **Khảo sát hàm:** Nhập công thức hàm số → Nhấn "Phân tích" → Xem đồ thị, BBT, cực trị
- **Mô phỏng:** Chọn mô phỏng tích phân hoặc lượng giác → Tương tác với animation
- **GeoGebra Lab:** Chọn module → Nhập lệnh hoặc dùng mẫu nhanh → Vẽ và xuất hình

**Bước 3:** Tương tác với hình đã dựng:
- **2D:** Kéo điểm, zoom, pan
- **3D:** Xoay hình, zoom, kéo điểm, thêm/nối điểm, tạo chân nối
- **Xuất:** Chọn định dạng xuất (PNG, SVG, PDF, TikZ, GeoGebra)

**Bước 4 (tùy chọn):** Đăng nhập để đồng bộ lịch sử dựng hình, cài đặt cá nhân

**Liên kết truy cập sản phẩm:** [https://math-renderer.sin-studio.tech/](https://math-renderer.sin-studio.tech/)

---

### 4. Công nghệ và kỹ thuật sử dụng

#### 4.1. Kiến trúc tổng quan

Hệ thống theo kiến trúc **Client-Server** với frontend và backend tách biệt:

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Client)                        │
│  React 18 + TypeScript + Vite                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ GeoGebra │ │ Three.js │ │  KaTeX   │ │ Firebase Auth    │   │
│  │ Renderer │ │ Renderer │ │ (LaTeX)  │ │ (Đăng nhập)      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API (JSON)
┌──────────────────────────▼──────────────────────────────────────┐
│                        BACKEND (Server)                         │
│  Python FastAPI                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ AI Scene │ │ Function │ │ Geometry │ │ OCR Service      │   │
│  │Extractor │ │ Analyzer │ │  Solver  │ │ (Vision AI)      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         Multi-Provider AI Infrastructure                  │   │
│  │  OpenRouter │ NVIDIA NIM │ Ollama │ 9router │ Mock       │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐                │
│  │ SQLite   │ │ SymPy    │ │ Geometry Engine  │                │
│  │ Database │ │ (CAS)    │ │ (Normalization)  │                │
│  └──────────┘ └──────────┘ └──────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.2. Chi tiết công nghệ

| Thành phần | Công nghệ | Mục đích |
| :---- | :---- | :---- |
| **Frontend** | React 18, TypeScript, Vite | Giao diện người dùng SPA hiện đại, responsive |
| **Backend** | Python, FastAPI | API server hiệu năng cao, async, type-safe |
| **AI/LLM** | OpenRouter, NVIDIA NIM, Ollama, 9router | Trích xuất scene hình học từ ngôn ngữ tự nhiên |
| **OCR** | Vision AI (multi-provider fallback) | Nhận dạng văn bản từ ảnh đề bài |
| **Tính toán symbolic** | SymPy (Computer Algebra System) | Khảo sát hàm số: đạo hàm, cực trị, tiệm cận |
| **Render 2D/đồ thị** | GeoGebra Apps Embedding API | Render hình hình học 2D, đồ thị hàm số tương tác |
| **Render 3D** | Three.js, React Three Fiber | Render hình học không gian 3D tương tác |
| **Công thức toán** | KaTeX 0.16 | Render công thức LaTeX trong giao diện |
| **Xác thực** | Firebase Authentication | Đăng nhập Google, email/password |
| **Cơ sở dữ liệu** | SQLite (aiosqlite) | Lưu user, lịch sử, cài đặt |
| **Deploy Frontend** | Vercel | Hosting frontend tĩnh, CDN toàn cầu |
| **Deploy Backend** | Cloud Server | API server Python |

#### 4.3. Kỹ thuật AI đáng chú ý

- **Multi-Provider Fallback Chain:** Hệ thống tự động thử nhiều nhà cung cấp AI (OpenRouter → NVIDIA → Ollama → Mock) để đảm bảo luôn hoạt động ngay cả khi một provider gặp sự cố.

- **Two-Stage Scene Extraction:** AI xử lý đề bài qua 2 giai đoạn — (1) reasoning (phân tích ngữ nghĩa) và (2) extraction (trích xuất JSON có cấu trúc) — giúp tăng độ chính xác.

- **Schema-Constrained Output:** LLM chỉ sinh JSON theo schema định sẵn (MathScene). Backend validate JSON rồi tự tạo GeoGebra commands hoặc Three.js scene, **không chạy code tùy ý do LLM sinh ra** — đảm bảo an toàn bảo mật.

- **Geometry Engine:** Module tự động tính toán tọa độ giao điểm, chuẩn hóa hình học, sinh annotation cho hình dựng.

#### 4.4. Quy mô codebase

| Phần | Dòng code | Ngôn ngữ |
| :---- | :---: | :---- |
| Backend | ~8,330 | Python |
| Frontend | ~8,550 | TypeScript |
| **Tổng** | **~16,880** | — |

---

### 5. Khả năng ứng dụng và giá trị mang lại

#### 5.1. Giá trị giáo dục

- **Hỗ trợ học sinh tự học:** Chỉ cần nhập đề bài tiếng Việt, hệ thống tự dựng hình và giải bài — giúp học sinh kiểm tra bài làm, hiểu sâu bài toán hình học mà không cần thầy cô bên cạnh.

- **Trực quan hóa 3D:** Học sinh có thể xoay, zoom hình không gian 3D — khắc phục hoàn toàn hạn chế của sách giáo khoa in 2D. Đây là lợi thế lớn nhất so với phương pháp truyền thống.

- **Khảo sát hàm số tự động:** Thay vì tính toán thủ công nhiều bước, học sinh nhập hàm số → hệ thống tự phân tích đạo hàm, cực trị, tiệm cận, lập BBT và vẽ đồ thị. Học sinh đối chiếu kết quả với bài làm để tự sửa sai.

- **Giải từng bước:** Lời giải chi tiết bằng tiếng Việt giúp học sinh hiểu phương pháp, không chỉ biết đáp án.

#### 5.2. Giá trị cho giáo viên

- **Tiết kiệm thời gian soạn đề:** Giáo viên nhập đề bài → hệ thống tự dựng hình → xuất TikZ/LaTeX/PDF cho đề thi, bài giảng. Thay vì mất 15–30 phút vẽ hình thủ công, giáo viên chỉ cần vài giây.

- **Hình minh họa chất lượng cao:** Hình xuất ra đạt chuẩn học thuật (TikZ/LaTeX), phù hợp in ấn và trình bày chuyên nghiệp.

- **GeoGebra Lab tích hợp:** Giáo viên có ngay phòng thí nghiệm toán học với đủ 4 module GeoGebra mà không cần cài đặt phần mềm riêng.

#### 5.3. Khả năng mở rộng

- **Đa ngôn ngữ:** Kiến trúc cho phép mở rộng sang tiếng Anh, tiếng Pháp... bằng cách thay đổi AI prompt.
- **Đa nền tảng:** Web app responsive, hoạt động tốt trên cả desktop và mobile.
- **API mở:** Backend cung cấp REST API chuẩn, có thể tích hợp vào LMS (Learning Management System) của trường học.
- **Mở rộng lên toán Đại học:** Kiến trúc modular cho phép bổ sung các dạng toán nâng cao (đại số tuyến tính, giải tích đa biến...).

---

### 6. Tình trạng hoàn thiện sản phẩm (demo/chạy thử)

#### 6.1. Trạng thái: ✅ Hoàn thiện — Đã triển khai production

Sản phẩm đã được triển khai và chạy ổn định tại: [https://math-renderer.sin-studio.tech/](https://math-renderer.sin-studio.tech/)

#### 6.2. Các tính năng đã hoàn thiện

| Tính năng | Trạng thái | Ghi chú |
| :---- | :---: | :---- |
| Dựng hình 2D từ ngôn ngữ tự nhiên | ✅ Hoàn thiện | GeoGebra renderer |
| Dựng hình 3D không gian | ✅ Hoàn thiện | Three.js renderer, xoay/zoom/kéo |
| Đồ thị hàm số | ✅ Hoàn thiện | GeoGebra renderer |
| Hình học tọa độ Oxyz | ✅ Hoàn thiện | Three.js renderer |
| OCR ảnh đề bài | ✅ Hoàn thiện | PNG/JPEG/WebP/GIF, upload/clipboard/kéo-thả |
| Khảo sát hàm số (SymPy) | ✅ Hoàn thiện | Đạo hàm, BBT, cực trị, tiệm cận, đồ thị |
| Giải từng bước (Solver) | ✅ Hoàn thiện | AI giải bài, trình bày LaTeX |
| Mô phỏng tích phân & lượng giác | ✅ Hoàn thiện | Animation tương tác |
| GeoGebra Lab (4 module) | ✅ Hoàn thiện | Graphing, Geometry, 3D, Probability |
| Xuất TikZ/LaTeX/PDF/PNG/SVG | ✅ Hoàn thiện | Chuẩn học thuật |
| Đăng nhập (Firebase Auth) | ✅ Hoàn thiện | Google, email/password |
| Lịch sử dựng hình | ✅ Hoàn thiện | Lưu và xem lại kết quả |
| Multi-provider AI | ✅ Hoàn thiện | OpenRouter, NVIDIA, Ollama, 9router, Mock |
| Responsive mobile | ✅ Hoàn thiện | Tối ưu cho cả desktop và mobile |
| Admin console | ✅ Hoàn thiện | Quản lý user, cài đặt hệ thống |

#### 6.3. Thông số kỹ thuật

- **Tổng dòng code:** ~16,880 dòng (8,330 Python + 8,550 TypeScript)
- **Số component frontend:** 25+ components React
- **Số API endpoint:** 12 endpoint RESTful
- **Số service backend:** 11 service modules
- **Độ phủ tính năng:** 100% các dạng bài hình học THPT phổ biến

#### 6.4. Demo mẫu có thể chạy thử

Truy cập [https://math-renderer.sin-studio.tech/](https://math-renderer.sin-studio.tech/) và thử các mẫu sau:

1. **Hình học phẳng:** `Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Vẽ đường trung tuyến AM.`
2. **Đồ thị hàm số:** `Vẽ đồ thị hàm số y = x^2 - 2x + 1.`
3. **Hình học không gian:** `Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.`
4. **Tọa độ Oxyz:** `Trong Oxyz cho A(1,2,3), B(4,5,6).`
5. **Khảo sát hàm số:** Vào "Khảo sát hàm" → nhập `y = x^3 - 3*x + 2` → xem kết quả phân tích đầy đủ.


|  | *TP. Hồ Chí Minh, ngày 14 tháng 05 năm 2026* Đại diện nhóm *(Ký tên và ghi rõ họ tên)*   **Trần Phúc Toàn** |
| ----: | :---: |
