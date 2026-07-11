# Nội dung thuyết trình dự án AI Math Renderer

## 1. Mở đầu từ trải nghiệm thực tế

Trong quá trình gia sư cho một học sinh chuẩn bị từ lớp 11 lên lớp 12, nhóm gặp một tình huống lặp lại nhiều lần. Khi học đến hình học không gian, học sinh có thể nhớ công thức nhưng không hình dung rõ đường thẳng chéo nhau, vị trí của mặt phẳng, chân đường vuông góc hay góc giữa các đối tượng trong không gian. Một hình vẽ tĩnh trên giấy không đủ để em quan sát từ nhiều góc, xoay mô hình hoặc tự kiểm tra giả thuyết.

Ở phía người dạy, để tạo một tiết học trực quan phải chuyển qua nhiều công cụ rời rạc: đọc đề từ ảnh hoặc PDF, gõ lại dữ kiện, dựng hình, khảo sát hàm số, soạn lời giải rồi xuất tài liệu. Mỗi bước đều có chi phí thao tác và nguy cơ sai lệch dữ liệu. Từ trải nghiệm đó, nhóm nhận ra đây không phải khó khăn của riêng một học sinh, mà là khoảng trống chung giữa đề toán, công cụ trực quan và quá trình dạy học.

Câu hỏi đặt ra là: có thể biến một đề toán thành học liệu trực quan, có lời giải và có khả năng kiểm chứng trong cùng một không gian làm việc hay không?

## 2. Vấn đề và định vị sản phẩm

Ba vấn đề chính dẫn đến AI Math Renderer là nội dung toán học, nhất là hình học không gian và giải tích, khó trực quan hóa; các công cụ hỗ trợ hiện có mạnh nhưng rời rạc và đòi hỏi nhiều thao tác; chatbot AI tiếp nhận ngôn ngữ tự nhiên linh hoạt nhưng có thể tạo câu trả lời nghe hợp lý mà sai về mặt toán học.

> **AI Math Renderer là không gian làm việc toán học sử dụng AI để hiểu yêu cầu bằng ngôn ngữ tự nhiên, đồng thời sử dụng các lõi toán học chuyên biệt để dựng hình, phân tích và tính toán chính xác.**

Thông điệp xuyên suốt sản phẩm là:

> **AI hiểu ngôn ngữ; lõi chuyên biệt chịu trách nhiệm về toán học.**

Sản phẩm có frontend React/Vite và backend FastAPI. Codebase hiện có các luồng render hình học, OCR ảnh, analyzer khảo sát hàm số, algebra solver, mô phỏng tương tác, GeoGebra Lab, chuyển đổi PDF qua MinerU, export, lịch sử, tài khoản, quản trị và phản hồi. Các module này không được định vị là các công cụ tách rời, mà là các thành phần của một workspace phục vụ học, dạy và biên soạn học liệu toán.

## 3. Câu chuyện sản phẩm: từ đề toán đến học liệu tương tác

Tình huống trung tâm của phần trình bày là một giáo viên có đề hình học không gian trong tệp PDF và muốn biến đề đó thành học liệu trực quan có lời giải. Giáo viên không chỉ cần một ảnh hình học đẹp, mà cần dữ liệu có thể rà soát, mô hình có thể tương tác, kết quả có trạng thái tin cậy và đầu ra có thể tái sử dụng.

Chuỗi giá trị mà AI Math Renderer hướng tới là:

```text
Đề bài
→ dữ liệu có cấu trúc
→ trực quan hóa
→ phân tích
→ lời giải
→ học liệu tương tác
```

Trong phiên bản hiện tại, PDF to Word là module chuyển đổi qua API MinerU riêng, còn luồng render nhận văn bản hoặc ảnh đề bài. Vì vậy, câu chuyện PDF là workflow dạy học thống nhất, không phải tuyên bố rằng PDF đã tự động chuyển thẳng sang renderer qua một API liên thông. Giáo viên có thể dùng PDF to Word để tạo bản có thể chỉnh sửa, sau đó đưa dữ kiện đã rà soát vào luồng OCR, renderer, analyzer hoặc solver.

### 3.1. Tiếp nhận đề bài

Đề bài có thể bắt đầu từ văn bản, ảnh hoặc PDF. Với ảnh, backend có API upload và OCR, có giới hạn tải, kiểm soát quyền truy cập và giới hạn đồng thời để tránh quá tải. Với PDF, giao diện PDF to Word gọi trực tiếp dịch vụ MinerU đang được chọn, hỗ trợ lựa chọn phương thức parse, ngôn ngữ, OCR bắt buộc, nhận diện công thức, bảng, phạm vi trang và chế độ LLM review khi provider sẵn sàng.

PDF to Word theo dõi trạng thái `queued`, `running`, `completed` và `failed`, đồng thời hiển thị tiến độ, log xử lý, preview và artifact đầu ra. Cơ chế này giúp người dùng biết tài liệu đang ở giai đoạn nào thay vì chỉ chờ một kết quả cuối cùng.

### 3.2. Trích xuất và chuẩn hóa dữ kiện

Dữ liệu đầu vào không được đưa thẳng vào mô hình toán học. Trong renderer, AI hoặc BYOK có thể trích xuất scene ban đầu từ đề bài tiếng Việt; scene này tiếp tục đi qua validator, bước sửa chuẩn hóa, kiểm chứng quan hệ hình học, kiểm tra khả năng tương thích renderer và quality gate.

Analyzer cũng có luồng OCR biểu thức riêng. Prompt trích xuất yêu cầu trả về biểu thức, biến, tham số, độ tin cậy, token mơ hồ và cờ `needs_confirmation`. Khi độ tin cậy thấp, có token mơ hồ hoặc biểu thức trống, hệ thống yêu cầu xác nhận trước khi dùng biểu thức cho khảo sát.

Đây là điểm quan trọng trong cách hệ thống xử lý đầu vào không chắc chắn: dữ liệu được mô tả bằng trạng thái và cảnh báo, không bị âm thầm biến thành một kết luận toán học.

### 3.3. Dựng hình và trực quan hóa

Sau chuẩn hóa, renderer tạo scene 2D hoặc 3D bằng GeoGebra hoặc Three.js. Scene có cấu trúc gồm đối tượng, quan hệ, annotation, góc nhìn và thông tin audit về nguồn sinh. Geometry engine còn chuẩn hóa các cạnh từ mặt, nhận diện giao điểm đoạn thẳng, biểu diễn dấu bằng nhau và góc vuông khi quan hệ đạt điều kiện hình học tương ứng.

Giao diện renderer có thể hiển thị GeoGebra 2D, GeoGebra 3D hoặc mô hình Three.js. Người dùng có thể thao tác scene, kéo điểm và chỉnh sửa đối tượng. Kết quả có export sang TikZ, GeoGebra, PDF, PNG, JPG, SVG và KaTeX HTML, phục vụ cả trình chiếu lẫn biên soạn tài liệu.

### 3.4. Phân tích toán học

Analyzer phục vụ khảo sát hàm số với biểu thức, đạo hàm, cực trị, bảng biến thiên, tiệm cận, đồ thị, tiếp tuyến, khoảng xét, phép biến đổi và tham số. Backend có cache ngắn hạn, giới hạn đồng thời, timeout, giới hạn đầu ra và session cho các công cụ phân tích tiếp theo.

Điểm kỹ thuật nằm ở việc analyzer không chỉ vẽ đường cong. Module kiểm tra tập xác định, backcheck đạo hàm, kiểm tra điểm tới hạn thuộc miền xác định, dấu trên các khoảng, tiệm cận, nghiệm giao trục, tiếp tuyến, cực trị trên khoảng và sự phù hợp giữa graph sampling với miền xác định. Báo cáo trả về trạng thái `verified`, `partially_verified`, `failed` hoặc `unverified` tùy evidence thực tế.

Khi dùng cho hình học, bộ dựng hình và bộ kiểm chứng quan hệ cung cấp phần phân tích tương ứng: đối tượng nào được dựng, quan hệ nào đã kiểm tra, quan hệ nào còn cần xác nhận. Khi dùng cho giải tích, Analyzer nối đồ thị với bằng chứng toán học thay vì chỉ trả về một hình ảnh.

### 3.5. Giải toán và kiểm chứng lời giải

Algebra Solver nhận input có cấu trúc, phân loại bài toán và chuyển đến solver phù hợp cho phương trình, bất phương trình, mũ–logarit, lượng giác, hệ phương trình, số phức, dãy số, xác suất–thống kê và một số bài giải tích. Lõi này dùng parser, normalizer, interpreter, bộ phân loại và SymPy; lời giải được tạo theo từng bước và có thông tin thời gian xử lý.

AI có thể hỗ trợ trích xuất đề hoặc diễn giải lời giải khi người dùng bật tùy chọn. Tuy nhiên, code thực tế ưu tiên đường giải rule-based/tất định trước. Chỉ khi đường này chưa giải được hoặc không hỗ trợ, hệ thống mới dùng AI extraction để tạo request chuẩn hóa rồi quay lại lõi giải toán. Khi lần giải tất định thành công, hệ thống không gọi AI extraction không cần thiết.

Để tránh một bài nặng làm ảnh hưởng toàn hệ thống, API solver có cost score, rate limit, quota ngày, giới hạn đồng thời, timeout, circuit breaker và tùy chọn process isolation cho worker SymPy. Lời giải có thể lưu lịch sử và xuất PDF.

### 3.6. Mô phỏng, khám phá và xuất học liệu

Sau khi có hình hoặc kết quả phân tích, người học có thể tiếp tục khám phá bằng Simulation Library. Catalog hiện có các mô phỏng lớp 11 và 12 về đạo hàm, nguyên hàm, diện tích, khối tròn xoay, tiệm cận, xác suất, thống kê, lượng giác và quan hệ không gian. Nhiều mô phỏng có mục tiêu học tập, điều kiện tiên quyết, câu hỏi dự đoán, checkpoint và tham số tương tác.

GeoGebra Lab mở rộng khả năng thao tác tự do với bốn không gian: Graphing Calculator, Geometry, 3D Calculator và Probability. Code tích hợp `GGBApplet`, có preset lệnh, command input, command history, save state và undo/redo. Module này không thay thế GeoGebra; nó đặt GeoGebra vào cùng ngữ cảnh học toán của sản phẩm.

Kết quả cuối cùng có thể là hình dựng, lời giải, mô phỏng hoặc tài liệu xuất ra. Giá trị của workflow không nằm ở việc gom nhiều nút bấm vào một màn hình, mà nằm ở việc giảm đứt gãy giữa tiếp nhận đề, xử lý dữ kiện, kiểm chứng, trực quan hóa và tái sử dụng học liệu.

## 4. Kiến trúc tạo độ tin cậy

AI Math Renderer được thiết kế theo kiến trúc tách biệt giữa lớp hiểu ngôn ngữ và động cơ toán học chuyên biệt. LLM và OCR giúp hệ thống tiếp nhận yêu cầu linh hoạt bằng tiếng Việt, nhận dạng ảnh và tạo cấu trúc ban đầu. Kết quả toán học được xử lý, kiểm tra và trình bày bởi parser, validator, CAS, geometry engine, analyzer, solver, renderer và simulation runtime.

```text
Người dùng
    ↓
Lớp xử lý ngôn ngữ tự nhiên và OCR
Hiểu ý định, trích xuất, chuẩn hóa yêu cầu
    ↓
Bộ kiểm tra dữ kiện và ràng buộc
Schema validation | scene validation | relation verification
    ↓
Lõi toán học chuyên biệt
Renderer | Geometry engine | Analyzer | Solver | CAS | Simulation
    ↓
Kết quả trực quan, có cấu trúc và có thể kiểm chứng
```

Thiết kế này giải quyết một rủi ro phổ biến của chatbot: tạo lời giải hoặc hình vẽ có vẻ hợp lý nhưng không có đủ cơ sở toán học. AI vẫn có vai trò quan trọng ở lớp giao tiếp và trích xuất, nhưng không thay thế các thành phần có trách nhiệm kiểm tra ràng buộc.

> **Sự linh hoạt của AI được bảo chứng bởi độ chính xác của động cơ toán học chuyên biệt.**

### 4.1. Ranh giới tin cậy của scene hình học

Render pipeline áp dụng một chuỗi rõ ràng: validate và repair scene, kiểm chứng quan hệ bằng CAS, chuẩn hóa hình học, kiểm tra tương thích renderer, gắn advisory và xác định trạng thái kết quả. Nếu scene dùng mock fallback, dùng provider fallback, có giả định, có dữ kiện thiếu, quan hệ kiểm chứng lỗi hoặc renderer không tương thích, kết quả không được gắn nhãn như một hình dựng chính xác.

Giao diện phân biệt `Dựng theo dữ kiện` và `Hình minh họa`. Hình không đạt điều kiện dựng chính xác được gắn thêm `Không theo tỉ lệ`; scene có dữ kiện thiếu hoặc giả định được gắn `Có giả định`. Các nhãn đo hoặc quan hệ không có nguồn tin cậy có thể bị ẩn khỏi hiển thị.

Các thao tác downstream như giải, tạo biến thể hoặc export bị chặn khi scene fallback chưa được người dùng xác nhận, khi giả định chưa được xác nhận, khi có quan hệ kiểm chứng thất bại hoặc khi còn lỗi CAS chặn. Đây là cơ chế thực tế trong codebase, không phải chỉ là mô tả định hướng.

### 4.2. Bằng chứng và khả năng truy vết

Render response giữ source, provider, model, trạng thái fallback, lý do fallback, cảnh báo, validation report, verification report, repair report, renderer compatibility và cờ cần xác nhận. Analyzer giữ provenance cho input và report các check của từng đặc trưng hàm số. Algebra Solver trả request ID, cảnh báo, lỗi, trạng thái, cost score và thời gian xử lý.

Khả năng truy vết này giúp người dùng và người vận hành phân biệt giữa kết quả đã kiểm chứng, kết quả kiểm chứng một phần, fallback và kết quả cần xác nhận. Nó cũng là nền tảng để kiểm thử, đo chất lượng và cải thiện các bước trích xuất sau này.

## 5. Giá trị khác biệt của sản phẩm

So với chatbot AI, AI Math Renderer không dừng ở một câu trả lời văn bản. Sản phẩm chuyển đề bài thành dữ liệu có cấu trúc, đi qua validator và lõi toán học, sau đó trả về scene, đồ thị, báo cáo kiểm chứng hoặc lời giải có trạng thái rõ ràng. Điều này không làm AI kém linh hoạt; nó đặt AI vào đúng vị trí có giá trị cao nhất là hiểu yêu cầu và hỗ trợ diễn giải.

So với GeoGebra thuần, sản phẩm giữ sức mạnh thao tác của GeoGebra nhưng giảm rào cản bắt đầu cho người mới. Người dùng có thể xuất phát từ đề bài, ảnh hoặc preset thay vì phải biết trước toàn bộ câu lệnh và công cụ dựng hình.

So với một PDF converter, module PDF to Word tập trung vào workflow tài liệu toán: lựa chọn OCR, công thức, bảng, phạm vi trang và artifact để chỉnh sửa tiếp. Kết quả phụ thuộc chất lượng PDF đầu vào và dịch vụ MinerU đang kết nối; sản phẩm hiển thị trạng thái xử lý, preview và cảnh báo từ job thay vì coi mọi PDF là đầu vào hoàn hảo.

So với nền tảng học tĩnh, Simulation Library cho phép thay đổi tham số, dự đoán, quan sát và đi qua checkpoint. Người học không chỉ xem đáp án cuối, mà có thể quan sát quá trình biến đổi của đối tượng toán học.

## 6. Phạm vi triển khai hiện tại và nguyên tắc kiểm soát độ tin cậy

Phiên bản hiện tại ưu tiên các chuyên đề có nhu cầu trực quan hóa và kiểm chứng cao: hình học phẳng, hình học không gian, tọa độ Oxyz, khảo sát hàm số, một số mảng đại số–giải tích, xác suất–thống kê và mô phỏng lớp 11–12. Nhóm lựa chọn phát triển theo chiều sâu của luồng xử lý và độ tin cậy trước khi mở rộng sang toàn bộ chương trình phổ thông.

Các ranh giới triển khai hiện tại gồm:

- Render hình học có cơ chế phân loại `verified`, `partially_verified`, `fallback`, `needs_confirmation` và `failed`. Hình minh họa không được dùng để suy ra quan hệ hoặc kết luận số học.
- Analyzer biểu diễn mức độ hoàn chỉnh của kiểm chứng theo từng check. Một đặc trưng không có evidence đủ sẽ ở trạng thái cảnh báo hoặc chưa kiểm chứng.
- Algebra Solver có giới hạn độ phức tạp và thời gian. Khi vượt ngân sách, hệ thống trả timeout thay vì cố tạo câu trả lời không có căn cứ.
- PDF to Word gọi API MinerU đã cấu hình. Code hiện có hiển thị trạng thái job, artifact và cảnh báo từ dịch vụ, nhưng chưa có bằng chứng về một cơ chế cấp độ ký tự hay vùng công thức để tự cô lập mọi kết quả OCR có độ tin cậy thấp.
- PDF to Word và renderer chưa có contract tự động nối PDF đã parse sang scene render. Đây là điểm mở rộng hợp lý của workflow, không phải năng lực đã hoàn thành.
- Không có căn cứ trong codebase để khẳng định bao phủ toàn bộ toán phổ thông, autoscale worker độc lập, zero-downtime cho mọi triển khai, pentest đạt chuẩn cụ thể hoặc độ chính xác tuyệt đối của AI và OCR.

Các ranh giới này là tiêu chuẩn thiết kế: hệ thống ưu tiên báo đúng mức độ chắc chắn, yêu cầu xác nhận khi cần và chặn thao tác downstream ở các trust boundary quan trọng.

## 7. Hiện trạng kỹ thuật có thể kiểm chứng

Codebase hiện có frontend React/Vite, backend FastAPI, migration cho SQLite/D1/PostgreSQL, render worker, cấu hình Docker, nginx và supervisord. Backend đăng ký route cho auth, profile, settings, render, OCR, analyzer, algebra solver, export, history, chat, feedback, admin, telemetry, health và AI models.

Hệ thống tài khoản có email/password, xác minh email, Google OAuth, reset password, session và gate trusted origin cho mutation. BYOK OpenAI-compatible có mã hóa secret bằng Fernet và validation base URL chống SSRF. Những thành phần này phục vụ vận hành sản phẩm, không phải điểm trình diễn chính của bài toán học.

CI trên GitHub Actions chạy backend tests, kiểm tra migration, frontend typecheck/build và Docker smoke build theo điều kiện branch. Codebase cũng có health check, error event, analytics, AI call metrics và các bài test cho render, scene trust, analyzer, OCR, algebra, auth, export, migration và upload.

Các chi tiết kỹ thuật này chứng minh sản phẩm không chỉ là mockup giao diện hoặc một lớp gọi API. Tuy vậy, việc có CI, health check và test không đồng nghĩa với tuyên bố sản phẩm đã hoàn thiện mọi năng lực vận hành ở quy mô lớn.

## 8. Lộ trình phát triển gắn với người dùng

### Giai đoạn 1. Ổn định nguyên mẫu

Mục tiêu kỹ thuật là hoàn thiện workflow chính từ đề bài đến scene, phân tích, lời giải và export; đồng thời làm rõ trạng thái fallback, cần xác nhận và lỗi đầu vào. Mục tiêu kiểm chứng thực tế là chạy bộ đề chuẩn nội bộ, đo khả năng tái lập kết quả và bảo đảm một người dùng mới có thể hoàn thành luồng demo mà không cần hỗ trợ trực tiếp từ nhóm.

### Giai đoạn 2. Đo độ chính xác

Mục tiêu kỹ thuật là xây benchmark đề toán tiếng Việt có đáp án chuẩn, đo tách riêng OCR, trích xuất dữ kiện, render scene, analyzer và algebra solver. Mục tiêu kiểm chứng thực tế là cho học sinh dùng thử trên các dạng bài đã chọn, đo thời gian hoàn thành, tỷ lệ phải sửa dữ kiện và mức độ hiểu sau khi dùng trực quan hóa.

### Giai đoạn 3. Hoàn thiện công cụ giáo viên

Mục tiêu kỹ thuật là cải thiện PDF to Word, chỉnh sửa công thức, scene editor, export và chuyển dữ liệu giữa các module. Điểm mở rộng quan trọng là contract an toàn từ dữ liệu PDF đã được xác nhận sang renderer hoặc solver. Mục tiêu kiểm chứng thực tế là thí điểm với giáo viên hoặc lớp học, thu thập phản hồi về thời gian chuẩn bị bài, chất lượng đầu ra và các bước còn gây cản trở.

### Giai đoạn 4. Mở rộng vận hành

Mục tiêu kỹ thuật là tối ưu hiệu năng, tách worker theo nhu cầu tải thật, hoàn thiện backup/restore có kiểm chứng và chuẩn hóa API nếu có đối tác tích hợp. Mục tiêu kiểm chứng thực tế là theo dõi tỷ lệ quay lại, tần suất sử dụng, thời gian xử lý và tỷ lệ lỗi của các workflow chính trong môi trường sử dụng thường xuyên.

### Giai đoạn 5. Cá nhân hóa học tập

Mục tiêu kỹ thuật là dùng history và learning profile để gợi ý mô phỏng, bài luyện hoặc ví dụ theo năng lực. Mục tiêu kiểm chứng thực tế là đánh giá tác động đến trải nghiệm học, khả năng tự phát hiện lỗi và tiến bộ theo thời gian, thay vì chỉ đo số lượng tính năng đã thêm.

Ba ưu tiên xuyên suốt lộ trình là hoàn thiện workflow thay vì bổ sung công cụ rời rạc, đo độ tin cậy bằng dữ liệu thay vì chỉ mô tả bằng cảm nhận, và đưa phản hồi của học sinh–giáo viên vào chu kỳ phát triển.

## 9. Kết luận

AI Math Renderer không phải chatbot giải toán đơn thuần và cũng không chỉ là công cụ dựng hình. Sản phẩm tạo một không gian làm việc toán học, nơi đề bài có thể đi từ dữ liệu đầu vào đến trực quan hóa, phân tích, lời giải, mô phỏng và học liệu xuất ra.

AI giúp người dùng giao tiếp tự nhiên với hệ thống. Parser, validator, geometry engine, analyzer, solver, CAS, renderer và quality gate chịu trách nhiệm biến yêu cầu đó thành kết quả có cấu trúc, có trạng thái tin cậy và có thể kiểm chứng.

> **Mục tiêu của AI Math Renderer là giúp người học nhìn thấy toán học, giúp người dạy tạo học liệu nhanh hơn, và giữ cho sự linh hoạt của AI đi cùng trách nhiệm kiểm chứng của lõi toán học.**