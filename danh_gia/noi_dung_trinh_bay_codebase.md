# Nội dung trình bày dự án AI Math Renderer sau khi rà soát codebase

Tài liệu này dùng để trình bày dự án. Nội dung được đối chiếu theo mã nguồn hiện có, không tin tuyệt đối vào README hay mô tả cũ.

## 1. Nguyên tắc rà soát

Nguyên tắc chính:

- Code là nguồn sự thật chính.
- Docs chỉ dùng để tham khảo ngữ cảnh.
- Chỉ trình bày là “đã có” khi frontend/backend/migration/config/test có bằng chứng tương ứng.
- Phần chưa đủ bằng chứng được chuyển sang “lộ trình”, không nói như hiện trạng hoàn tất.

Các nhóm code đã đối chiếu:

- Frontend React/Vite: routing, page/component, module render, analyzer, algebra solver, simulation, GeoLab, PDF to Word, account, admin.
- Backend FastAPI: router đăng ký trong app, API render, OCR, analyzer, algebra, solve, export, auth, admin, health, telemetry.
- Database: SQLite/D1/PostgreSQL client, migrations, repositories.
- Security: session, origin gate, rate limit, Turnstile, Google OAuth, BYOK, mã hóa API key, upload validation.
- Vận hành: GitHub Actions, Dockerfile, nginx, supervisord, render worker, health check.

## 2. Lý do chọn đề tài

Trong quá trình gia sư cho một học sinh từ lớp 11 lên lớp 12, nhóm nhận thấy một vấn đề rất rõ: học sinh không chỉ thiếu công thức, mà còn khó hình dung đối tượng toán học.

Vấn đề này đặc biệt rõ ở hình học không gian. Các khái niệm như đường thẳng chéo nhau, mặt phẳng, góc giữa đường thẳng và mặt phẳng, khoảng cách trong không gian, hình chóp, lăng trụ thường được trình bày bằng hình tĩnh. Khi học sinh không thể xoay, phóng to, quan sát từ nhiều góc nhìn hoặc kiểm tra quan hệ hình học, việc học dễ trở thành học thuộc.

Ở phía người dạy, việc soạn tài liệu cũng gặp khó khăn:

- Dựng hình toán học chính xác tốn nhiều thời gian.
- Chuyển PDF sang Word thường làm hỏng công thức.
- Công cụ convert hay biến công thức thành unicode hoặc text thường, không phải Equation/LaTeX dễ chỉnh sửa.
- Khi cần sửa đề, sửa lời giải hoặc tái sử dụng hình vẽ, giáo viên/gia sư phải thao tác thủ công nhiều lần.

Từ hai nhu cầu đó, nhóm xây dựng AI Math Renderer như một workspace hỗ trợ học, dạy và biên soạn tài liệu toán học.

Câu chốt:

> Nhóm chọn đề tài này vì bài toán đến từ trải nghiệm dạy học thật: học sinh cần nhìn thấy toán học, còn giáo viên cần công cụ giúp dựng hình và soạn tài liệu nhanh nhưng vẫn giữ được độ chính xác.

## 3. Tổng quan sản phẩm theo codebase

AI Math Renderer là nền tảng web hỗ trợ nhập đề toán, nhận dạng ảnh, phân tích hàm số, giải toán, dựng hình 2D/3D, mô phỏng tương tác và xuất tài liệu.

Các màn hình chính trong frontend:

- Render hình học.
- Analyzer khảo sát hàm số.
- Algebra Solver.
- Simulation Library.
- GeoGebra Lab.
- PDF to Word.
- History.
- Account/Settings/Admin/Feedback.

Backend có các nhóm API chính:

- Auth, user profile, user settings.
- Render, render jobs, history, export.
- OCR, analyzer, algebra solver, solver/advisory.
- Admin, analytics, telemetry, health, AI models.
- Chat và feedback.

Luồng sản phẩm tổng quát:

```text
Đề bài / ảnh / PDF
→ OCR hoặc AI extraction
→ dữ liệu có cấu trúc
→ validate / solver / analyzer / renderer
→ hình ảnh, lời giải, mô phỏng hoặc tài liệu xuất ra
```

## 4. Sáu chức năng hiện có

### 4.1. Render hình học 2D/3D

Chức năng render cho phép người dùng nhập đề toán bằng văn bản hoặc ảnh. Hệ thống phân tích đề, dựng scene toán học và hiển thị bằng renderer phù hợp.

Bằng chứng từ code:

- Frontend có `ProblemInput`, `RendererPanel`, `GeoGebraView`, `ThreeGeometryView`, `SceneEditorPanel`.
- Backend có API render đồng bộ và render job bất đồng bộ.
- Có render history để lưu lại kết quả theo tài khoản.
- Có export scene sang TikZ, GeoGebra, PDF, PNG, JPG, SVG, KaTeX HTML.

Năng lực đã có:

- Nhập text hoặc OCR ảnh.
- Dựng hình 2D/3D bằng GeoGebra hoặc Three.js.
- Chỉnh sửa scene sau khi dựng.
- Kéo điểm, thêm điểm, nối đoạn, tạo chân chiếu/giao điểm/vector.
- Thay đổi tham số cục bộ bằng slider.
- Hiển thị trạng thái tin cậy: verified, fallback, cần xác nhận, có giả định, không theo tỉ lệ.

Giá trị khi trình bày:

> Render giúp học sinh chuyển từ “đọc đề” sang “nhìn thấy đề”, đồng thời cho biết kết quả nào đã kiểm chứng và kết quả nào chỉ nên xem như minh họa.

### 4.2. Analyzer khảo sát hàm số

Analyzer hỗ trợ phân tích biểu thức hàm số, vẽ đồ thị và hiển thị các thông tin phục vụ khảo sát.

Bằng chứng từ code:

- Frontend có `FunctionAnalyzerPanel`, `AnalyzerInput`, `AnalyzerResult`, `AnalyzerToolControls`, `FunctionGraph`, `VariationTable`.
- Backend có API analyze, graph samples và OCR extraction cho hàm số.
- Backend có parser, domain sampling, semaphore, cache ngắn hạn và timeout.

Năng lực đã có:

- Nhập biểu thức hàm số.
- OCR công thức từ ảnh.
- Phân tích đạo hàm, cực trị, bảng biến thiên, tiệm cận và đồ thị.
- Hỗ trợ khoảng xét, đường thẳng phụ, phép biến đổi đồ thị.
- Lấy mẫu đồ thị theo miền xác định, tránh nối sai qua điểm gián đoạn hoặc tiệm cận đứng.

Giá trị khi trình bày:

> Analyzer không chỉ vẽ đồ thị mà còn nối đồ thị với bảng biến thiên và các đặc trưng toán học của hàm số.

### 4.3. Bộ giải toán học / Algebra Solver

Bộ giải toán học xử lý các bài đại số và trình bày kết quả theo cấu trúc.

Bằng chứng từ code:

- Frontend có `AlgebraSolverPage` và nhóm component `algebra-solver`.
- Backend có API `/api/algebra/solve`, export PDF, algebra history.
- Service algebra có cost limit, timeout, concurrency gate và circuit breaker.

Năng lực đã có:

- Giải bài đại số theo input có cấu trúc.
- Hỗ trợ AI extraction hoặc AI explanation khi bật tùy chọn.
- Giới hạn bài quá nặng bằng cost score.
- Có quota ngày, rate limit và concurrency limit.
- Có circuit breaker khi nhiều timeout gần nhau.
- Có process isolation cho SymPy theo cấu hình.
- Có lưu lịch sử và export PDF lời giải.

Giá trị khi trình bày:

> AI có thể hỗ trợ nhận dạng và diễn giải, nhưng bộ giải có lớp kiểm soát tải, timeout và xử lý toán học riêng, không phụ thuộc hoàn toàn vào câu trả lời AI.

### 4.4. PDF to Word

Chức năng PDF to Word phục vụ nhu cầu biên soạn tài liệu toán học.

Bằng chứng từ code:

- Frontend có `PdfToWordPage`.
- Module này gọi API MinerU qua `frontend/src/api/mineru.ts`.
- Có cấu hình backend xử lý, parse method, ngôn ngữ, nhận diện công thức, bảng, LLM mode/provider/model.

Năng lực đã có:

- Tải PDF lên.
- Theo dõi trạng thái queued/running/completed/failed.
- Hiển thị progress và terminal logs.
- Xem preview artifact.
- Cấu hình OCR, công thức, bảng, khoảng trang, chế độ LLM review.

Giới hạn cần nói rõ:

- Chức năng phụ thuộc dịch vụ MinerU/API tương ứng.
- Chất lượng Word đầu ra phụ thuộc chất lượng PDF và engine OCR/parse.

Giá trị khi trình bày:

> PDF to Word giải quyết nỗi đau khi convert tài liệu toán: công thức cần được giữ ở dạng có thể chỉnh sửa, không biến thành chuỗi ký tự rời rạc.

### 4.5. GeoLab tích hợp GeoGebra API

GeoLab là phòng thí nghiệm toán học tích hợp GeoGebra trực tiếp vào sản phẩm.

Bằng chứng từ code:

- Frontend có `GeoGebraLabPage`.
- Code load `GGBApplet` từ GeoGebra deploy script.
- Có các mode: Graphing Calculator, Geometry, 3D Calculator, Probability.

Năng lực đã có:

- Dùng Graphing Calculator cho đồ thị 2D.
- Dùng Geometry cho hình học phẳng.
- Dùng 3D Calculator cho mặt phẳng, mặt cầu, khối đa diện, bề mặt.
- Dùng Probability cho mô phỏng xác suất.
- Có preset lệnh dựng hình.
- Có command input, history, save state, undo/redo.

Giá trị khi trình bày:

> GeoLab không thay thế GeoGebra, mà đưa sức mạnh của GeoGebra vào workflow học toán dễ tiếp cận hơn, có preset và ngữ cảnh sẵn cho người mới.

### 4.6. Simulation / mô phỏng toán học

Simulation cung cấp thư viện mô phỏng tương tác theo chủ đề.

Bằng chứng từ code:

- Frontend có `SimulationHubPage`, `SimulationLibraryPage`, `SimulationShell`.
- Catalog `SIMULATIONS` chứa nhiều mô phỏng lớp 11/12.
- Có template mô phỏng đạo hàm, nguyên hàm, diện tích, khối tròn xoay, xác suất, thống kê, lượng giác, không gian.

Năng lực đã có:

- Mô phỏng theo bước.
- Có learning outcomes, prerequisites, predict prompt, checkpoint.
- Có chế độ khám phá tự do ở nhiều mô phỏng.
- Có slider/tham số và đồ thị/mô hình tương tác.

Giá trị khi trình bày:

> Simulation biến toán học từ kết quả tĩnh thành quá trình có thể thay đổi tham số, quan sát và tự kiểm chứng.

## 5. Điểm mới và sáng tạo

### 5.1. AI chỉ là lớp NLP, không phải nguồn chân lý duy nhất

Điểm khác biệt của dự án là không đặt AI ở vị trí phán quyết đúng sai tuyệt đối.

AI chủ yếu đảm nhiệm:

- Hiểu đề bài tiếng Việt.
- Trích xuất dữ liệu từ ảnh hoặc văn bản.
- Sinh cấu trúc ban đầu.
- Diễn giải lời giải hoặc phản hồi bằng ngôn ngữ dễ hiểu.

Sau đó dữ liệu đi qua các lớp khác:

- Schema validation.
- Safe parser.
- Math service.
- Renderer compatibility check.
- Render quality gate.
- Solver/analyzer riêng.
- Trạng thái verified/fallback/cần xác nhận.

Luồng nên trình bày:

```text
Ngôn ngữ tự nhiên
→ AI/OCR/NLP
→ dữ liệu có cấu trúc
→ math core / validator / solver / renderer
→ kết quả trực quan hoặc lời giải
```

Câu chốt:

> AI trong dự án là lớp giao tiếp. Tính đúng đắn phải đi qua lõi toán học, parser, validator và các lớp kiểm chứng.

### 5.2. Kết nối điểm thiếu của nhiều công cụ riêng lẻ

So với AI chatbot:

- Chatbot dễ dùng nhưng dễ trả lời sai mà nghe hợp lý.
- Sản phẩm có trạng thái tin cậy, validator, analyzer, solver và cảnh báo fallback.

So với GeoGebra thuần:

- GeoGebra mạnh nhưng người mới khó bắt đầu vì cần biết công cụ/lệnh.
- Sản phẩm có preset, nhập đề tự nhiên, render từ đề và tích hợp vào workspace học toán.

So với PDF converter:

- Converter thường không hiểu ngữ cảnh toán học, dễ phá công thức.
- Sản phẩm có module PDF to Word riêng với cấu hình formula/table/OCR/LLM review.

So với nền tảng nội dung học tập tĩnh:

- Nội dung tĩnh chỉ giải bài mẫu cố định.
- Sản phẩm cho người dùng nhập bài của họ, dựng hình, phân tích, giải và mô phỏng tương tác.

### 5.3. Một workflow đầy đủ cho học, dạy và biên soạn

Workflow sản phẩm:

```text
Nhập đề / ảnh / PDF
→ OCR hoặc AI extraction
→ validate
→ render / analyze / solve / simulate
→ chỉnh sửa scene hoặc tham số
→ lưu lịch sử / export tài liệu
```

Điểm mới không chỉ là từng chức năng riêng lẻ, mà là cách nối chúng thành một không gian làm việc toán học.

### 5.4. Kiến trúc có khả năng mở rộng

Codebase đã chia module khá rõ:

- API routes riêng theo domain.
- Service layer cho OCR, render, analyzer, algebra, AI provider, storage.
- Repository layer cho auth, history, analytics, user settings, upload.
- Schema layer cho contract dữ liệu.
- Frontend page/component tách theo chức năng.

Điều này giúp mở rộng thêm dạng bài, provider AI, renderer, export format hoặc mô phỏng mà không phải viết lại toàn bộ hệ thống.

## 6. Hiện trạng sản phẩm

Hiện trạng có thể nói chắc:

- Có frontend web React/Vite.
- Có backend FastAPI.
- Có auth email/password, email verification, Google OAuth, reset password.
- Có session, hashed session token, trusted origin gate, rate limit.
- Có OCR ảnh cho đề bài và analyzer.
- Có render hình học 2D/3D.
- Có scene editor và parameter slider.
- Có analyzer khảo sát hàm số.
- Có algebra solver.
- Có simulation library.
- Có GeoLab tích hợp GeoGebra.
- Có PDF to Word qua MinerU/API.
- Có export nhiều định dạng.
- Có history, account, settings, admin, feedback.
- Có BYOK OpenAI-compatible với mã hóa API key bằng Fernet.
- Có validate base URL chống SSRF cho BYOK.
- Có SQLite/D1/PostgreSQL client và migrations.
- Có render worker, Docker, nginx, supervisord.
- Có CI chạy backend tests, frontend build và Docker smoke build.
- Có analytics/admin, error events, AI call metrics và health checks.

Điểm nên nói thận trọng:

- Sản phẩm đã có lõi chức năng và có thể demo/thử nghiệm thật.
- Chưa nên nói là đã bao phủ toàn bộ toán phổ thông.
- Chưa nên nói PDF to Word luôn giữ đúng mọi công thức.
- Chưa nên nói đã có backup/rollback/zero-downtime hoàn chỉnh nếu chưa có bằng chứng vận hành.

## 7. Những claim không nên dùng như hiện trạng

Không nên nói các ý sau là đã hoàn tất:

- Backup cloud định kỳ và khôi phục thảm họa hoàn chỉnh.
- Zero-downtime deployment được bảo đảm toàn bộ.
- Cụm worker autoscale độc lập.
- Fine-tuning model bằng hàng chục nghìn mẫu đã hoàn thành.
- Bao phủ toàn bộ chương trình phổ thông.
- Đã qua pentest hoặc đạt chuẩn bảo mật cụ thể.
- PDF to Word đảm bảo đúng mọi công thức trong mọi tài liệu.
- AI luôn cho kết quả đúng.

Cách nói đúng hơn:

> Các phần này là hướng phát triển hoặc đã có nền tảng kỹ thuật ban đầu, nhưng cần thêm dữ liệu vận hành, kiểm thử thực nghiệm và hạ tầng triển khai trước khi khẳng định là năng lực hoàn chỉnh.

## 8. Lộ trình phát triển sau cuộc thi

### Giai đoạn 1: Ổn định demo thành sản phẩm dùng thường xuyên

Mục tiêu: người dùng mới có thể tự dùng sản phẩm mà không cần nhóm hướng dẫn trực tiếp.

Việc cần làm:

- Chuẩn hóa các workflow demo chính.
- Thêm hướng dẫn trong app cho render, analyzer, solver, GeoLab, PDF to Word.
- Cải thiện thông báo khi OCR nhận sai, render fallback hoặc cần xác nhận.
- Bổ sung ví dụ theo chương trình lớp 11 và 12.
- Thêm end-to-end test cho luồng nhập đề → render → chỉnh scene → export.

### Giai đoạn 2: Tăng độ đúng toán học

Mục tiêu: tăng độ tin cậy bằng dữ liệu kiểm thử thực nghiệm.

Việc cần làm:

- Xây bộ benchmark đề toán tiếng Việt có đáp án chuẩn.
- Đo riêng độ đúng OCR, trích xuất đề, render scene, analyzer, algebra solver.
- Mở rộng rule kiểm chứng hình học không gian.
- Tách rõ kết quả đã kiểm chứng, minh họa, fallback và cần xác nhận.
- Ưu tiên các dạng bài lớp 11/12 có tần suất cao.

### Giai đoạn 3: Phục vụ giáo viên và biên soạn tài liệu

Mục tiêu: biến sản phẩm thành công cụ soạn bài thực tế.

Việc cần làm:

- Cải thiện PDF to Word bằng bộ tài liệu toán thực tế.
- Tối ưu export Word/LaTeX/PDF/ảnh cho giáo viên.
- Thêm template đề kiểm tra, worksheet và lời giải.
- Cho phép lưu bộ sưu tập hình vẽ/bài học theo chương.
- Thêm quy trình sửa công thức sau OCR/PDF conversion.

### Giai đoạn 4: Mở rộng vận hành và tích hợp

Mục tiêu: chuẩn bị cho lượng người dùng và tích hợp bên ngoài.

Việc cần làm:

- Tách worker render/OCR khi tải tăng thật.
- Chuẩn hóa public API cho render/analyze/solve nếu có đối tác tích hợp.
- Thêm dashboard chất lượng toán học và chi phí AI.
- Thiết lập backup/restore có script kiểm chứng.
- Bổ sung rolling deployment hoặc rollback có bằng chứng vận hành.

### Giai đoạn 5: Cá nhân hóa học tập

Mục tiêu: giúp học sinh học theo điểm mạnh/yếu thật của mình.

Việc cần làm:

- Dựa trên learning profile và history để gợi ý bài luyện tập.
- Ghi nhận lỗi sai phổ biến theo chủ đề.
- Sinh mô phỏng hoặc ví dụ tương tự theo điểm yếu.
- Tạo chế độ luyện tập từng bước có phản hồi.
- Theo dõi tiến bộ theo thời gian.

## 9. Câu kết luận để trình bày

> AI Math Renderer không phải một chatbot giải toán đơn thuần. Sản phẩm là một workspace toán học gồm nhập đề, OCR, phân tích, kiểm chứng, dựng hình, giải toán, mô phỏng và xuất tài liệu. AI được dùng để giúp người dùng giao tiếp tự nhiên hơn với hệ thống, còn độ tin cậy đến từ các lớp cấu trúc dữ liệu, parser, solver, renderer và quality gate trong code.

## 10. Gợi ý chia slide

1. Vấn đề thực tế khi gia sư lớp 11 lên 12.
2. Nỗi đau học sinh: khó hình dung hình học không gian.
3. Nỗi đau giáo viên: dựng hình và convert tài liệu toán.
4. Tổng quan AI Math Renderer.
5. 6 chức năng chính đã có.
6. Demo workflow: nhập đề/ảnh/PDF → OCR/AI → validate → render/analyze/solve.
7. Điểm mới: AI là lớp NLP, math core/validator là lớp kiểm chứng.
8. So sánh với AI chatbot, GeoGebra, PDF converter, nền tảng học tĩnh.
9. Hiện trạng codebase: frontend, backend, DB, auth, worker, CI.
10. Giới hạn hiện tại: không claim quá mức.
11. Lộ trình sau cuộc thi.
12. Kết luận: nhìn thấy toán học, kiểm chứng được toán học, soạn tài liệu nhanh hơn.