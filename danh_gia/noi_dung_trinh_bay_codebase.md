# Nội dung thuyết trình dự án AI Math Renderer

## 1. Mở đầu từ trải nghiệm thực tế

Trong quá trình gia sư cho một học sinh chuẩn bị từ lớp 11 lên lớp 12, nhóm gặp một tình huống lặp lại nhiều lần. Khi học đến hình học không gian, học sinh có thể nhớ công thức nhưng không hình dung rõ đường thẳng chéo nhau, vị trí của mặt phẳng, chân đường vuông góc hay góc giữa các đối tượng trong không gian. Một hình vẽ tĩnh trên giấy không đủ để em quan sát từ nhiều góc, xoay mô hình hoặc tự kiểm tra giả thuyết.

Ở phía người dạy, để tạo một tiết học trực quan phải chuyển qua nhiều công cụ rời rạc: nhập lại đề, dựng hình, khảo sát hàm số, soạn lời giải rồi xuất tài liệu. Mỗi bước đều có chi phí thao tác và nguy cơ sai lệch dữ liệu. Từ trải nghiệm đó, nhóm nhận ra đây không phải khó khăn của riêng một học sinh, mà là khoảng trống chung giữa đề toán, công cụ trực quan và quá trình dạy học.

Câu hỏi đặt ra là: có thể biến một đề toán thành học liệu trực quan, có lời giải và có khả năng kiểm chứng trong cùng một không gian làm việc hay không?

## 2. Vấn đề và định vị sản phẩm

Ba vấn đề chính dẫn đến AI Math Renderer là nội dung toán học, nhất là hình học không gian và giải tích, khó trực quan hóa; các công cụ hỗ trợ hiện có mạnh nhưng rời rạc và đòi hỏi nhiều thao tác; chatbot AI tiếp nhận ngôn ngữ tự nhiên linh hoạt nhưng có thể tạo câu trả lời nghe hợp lý mà sai về mặt toán học.

> **AI Math Renderer là không gian làm việc toán học sử dụng AI để hiểu yêu cầu bằng ngôn ngữ tự nhiên, đồng thời sử dụng các lõi toán học chuyên biệt để dựng hình, phân tích và tính toán chính xác.**

Thông điệp xuyên suốt sản phẩm là:

> **AI hiểu ngôn ngữ; lõi chuyên biệt chịu trách nhiệm về toán học.**

Sản phẩm có frontend React/Vite và backend FastAPI. Luồng toán học chính gồm render hình học, OCR ảnh, analyzer khảo sát hàm số, algebra solver, mô phỏng tương tác, GeoGebra Lab, export và lịch sử. Bên cạnh đó, codebase có nhánh tiện ích tài liệu PDF to Word qua MinerU cùng các module tài khoản, quản trị và phản hồi. PDF to Word hoạt động độc lập, không phải đầu vào của renderer, analyzer hay solver.

## 3. Câu chuyện sản phẩm: từ đề toán đến học liệu tương tác

Tình huống trung tâm của phần trình bày là một giáo viên có đề hình học không gian ở dạng văn bản hoặc ảnh và muốn biến đề đó thành học liệu trực quan có lời giải. Giáo viên không chỉ cần một ảnh hình học đẹp, mà cần dữ liệu có thể rà soát, mô hình có thể tương tác, kết quả có trạng thái tin cậy và đầu ra có thể tái sử dụng.

Chuỗi giá trị mà AI Math Renderer hướng tới là:

```text
Đề bài
→ dữ liệu có cấu trúc
→ trực quan hóa
→ phân tích
→ lời giải
→ học liệu tương tác
```

Luồng này bắt đầu từ văn bản hoặc ảnh đề bài. PDF không nằm trong contract đầu vào của luồng và không tự động chuyển thành scene hay yêu cầu giải toán.

### 3.1. Tiếp nhận đề bài

Đề bài đi vào luồng chính bằng văn bản hoặc ảnh. Với ảnh, backend có API upload và OCR, có giới hạn tải, kiểm soát quyền truy cập và giới hạn đồng thời để tránh quá tải. Văn bản hoặc nội dung nhận dạng từ ảnh sau đó mới được trích xuất và chuẩn hóa cho renderer, analyzer hay solver.

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

### 3.7. Nhánh PDF to Word độc lập

PDF to Word là tiện ích chuyển đổi tài liệu riêng, không thuộc chuỗi xử lý từ đề bài đến scene, phân tích hay lời giải. Giao diện gọi dịch vụ MinerU được cấu hình và cho phép chọn phương thức parse, ngôn ngữ, OCR bắt buộc, nhận diện công thức, bảng, phạm vi trang và chế độ LLM review khi provider sẵn sàng.

Module theo dõi các trạng thái `queued`, `running`, `completed` và `failed`, đồng thời hiển thị tiến độ, log xử lý, preview và artifact đầu ra. Đầu ra phục vụ chỉnh sửa hoặc lưu trữ tài liệu; hệ thống hiện không chuyển tiếp artifact này sang renderer, analyzer hay solver.

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

So với một PDF converter thông thường, nhánh PDF to Word tập trung vào tài liệu toán: lựa chọn OCR, công thức, bảng, phạm vi trang và artifact để chỉnh sửa tiếp. Kết quả phụ thuộc chất lượng PDF đầu vào và dịch vụ MinerU đang kết nối; module hiển thị trạng thái xử lý, preview và cảnh báo từ job. Nhánh này độc lập với luồng toán học chính.

So với nền tảng học tĩnh, Simulation Library cho phép thay đổi tham số, dự đoán, quan sát và đi qua checkpoint. Người học không chỉ xem đáp án cuối, mà có thể quan sát quá trình biến đổi của đối tượng toán học.

## 6. Phạm vi triển khai hiện tại và nguyên tắc kiểm soát độ tin cậy

Phiên bản hiện tại ưu tiên các chuyên đề có nhu cầu trực quan hóa và kiểm chứng cao: hình học phẳng, hình học không gian, tọa độ Oxyz, khảo sát hàm số, một số mảng đại số–giải tích, xác suất–thống kê và mô phỏng lớp 11–12. Nhóm lựa chọn phát triển theo chiều sâu của luồng xử lý và độ tin cậy trước khi mở rộng sang toàn bộ chương trình phổ thông.

Các ranh giới triển khai hiện tại gồm:

- Render hình học có cơ chế phân loại `verified`, `partially_verified`, `fallback`, `needs_confirmation` và `failed`. Hình minh họa không được dùng để suy ra quan hệ hoặc kết luận số học.
- Analyzer biểu diễn mức độ hoàn chỉnh của kiểm chứng theo từng check. Một đặc trưng không có evidence đủ sẽ ở trạng thái cảnh báo hoặc chưa kiểm chứng.
- Algebra Solver có giới hạn độ phức tạp và thời gian. Khi vượt ngân sách, hệ thống trả timeout thay vì cố tạo câu trả lời không có căn cứ.
- PDF to Word là nhánh độc lập gọi API MinerU đã cấu hình. Code hiện có hiển thị trạng thái job, artifact và cảnh báo từ dịch vụ, nhưng chưa có bằng chứng về một cơ chế cấp độ ký tự hay vùng công thức để tự cô lập mọi kết quả OCR có độ tin cậy thấp.
- Không có contract chuyển PDF hoặc artifact đã parse sang scene render, analyzer hay solver; PDF không phải đầu vào của luồng toán học chính.
- Không có căn cứ trong codebase để khẳng định bao phủ toàn bộ toán phổ thông, autoscale worker độc lập, zero-downtime cho mọi triển khai, pentest đạt chuẩn cụ thể hoặc độ chính xác tuyệt đối của AI và OCR.

Các ranh giới này là tiêu chuẩn thiết kế: hệ thống ưu tiên báo đúng mức độ chắc chắn, yêu cầu xác nhận khi cần và chặn thao tác downstream ở các trust boundary quan trọng.

## 7. Hiện trạng kỹ thuật có thể kiểm chứng

Codebase hiện có frontend React/Vite, backend FastAPI, migration cho SQLite/D1/PostgreSQL, render worker, cấu hình Docker, nginx và supervisord. Backend đăng ký route cho auth, profile, settings, render, OCR, analyzer, algebra solver, export, history, chat, feedback, admin, telemetry, health và AI models.

Hệ thống tài khoản có email/password, xác minh email, Google OAuth, reset password, session và gate trusted origin cho mutation. BYOK OpenAI-compatible có mã hóa secret bằng Fernet và validation base URL chống SSRF. Những thành phần này phục vụ vận hành sản phẩm, không phải điểm trình diễn chính của bài toán học.

CI trên GitHub Actions chạy backend tests, kiểm tra migration, frontend typecheck/build và Docker smoke build theo điều kiện branch. Codebase cũng có health check, error event, analytics, AI call metrics và các bài test cho render, scene trust, analyzer, OCR, algebra, auth, export, migration và upload.

Các chi tiết kỹ thuật này chứng minh sản phẩm không chỉ là mockup giao diện hoặc một lớp gọi API. Tuy vậy, việc có CI, health check và test không đồng nghĩa với tuyên bố sản phẩm đã hoàn thiện mọi năng lực vận hành ở quy mô lớn.

## 8. Lộ trình phát triển sản phẩm sau cuộc thi

Cuộc thi là mốc kiểm chứng nguyên mẫu, không phải điểm kết thúc của AI Math Renderer. Sau cuộc thi, sản phẩm tiếp tục được vận hành dưới dạng ứng dụng web với tài khoản, lịch sử, phản hồi, telemetry, CI và quy trình triển khai đã có trong codebase. Lộ trình phát triển dựa trên một vòng lặp liên tục:

```text
Phát hành phiên bản
→ người học và giáo viên sử dụng
→ ghi nhận lỗi, phản hồi và chỉ số
→ bổ sung dữ liệu kiểm thử
→ cải thiện ứng dụng và lõi toán học
→ phát hành phiên bản tiếp theo
```

Mỗi giai đoạn chỉ mở rộng khi giai đoạn trước có dữ liệu sử dụng và chất lượng đủ rõ. Cách này tránh biến sản phẩm thành bản demo nhiều tính năng nhưng không có người dùng thường xuyên.

### Giai đoạn 1. Sau cuộc thi: duy trì bản beta công khai

- **Ứng dụng:** ổn định luồng chính từ văn bản hoặc ảnh đề bài đến scene, phân tích, lời giải và export; sửa các điểm khiến người dùng mới không thể tự hoàn thành tác vụ.
- **Người dùng:** mời nhóm nhỏ học sinh và giáo viên dùng lại hằng tuần, tiếp nhận phản hồi ngay trong ứng dụng và xây bộ tình huống lỗi thực tế.
- **Nền tảng:** duy trì CI, health check, telemetry, backup và quy trình phát hành; theo dõi lỗi theo từng workflow thay vì chỉ kiểm tra trang web còn hoạt động.
- **Chỉ số quyết định:** tỷ lệ hoàn thành tác vụ, tỷ lệ kết quả cần sửa, thời gian xử lý, lỗi hệ thống và tỷ lệ người dùng quay lại.

### Giai đoạn 2. Thí điểm học tập và đo độ chính xác

- **Ứng dụng:** tinh chỉnh trải nghiệm renderer, analyzer, solver và simulation theo các buổi học thật; bổ sung hướng dẫn tại đúng bước người dùng gặp khó khăn.
- **Người dùng:** tổ chức thí điểm với giáo viên hoặc nhóm học sinh theo từng chuyên đề lớp 11–12, không mở rộng đồng loạt khi chưa đo được hiệu quả.
- **Nền tảng:** xây benchmark đề toán tiếng Việt có đáp án chuẩn, tách riêng phép đo OCR, trích xuất dữ kiện, scene, analyzer và solver; đưa các lỗi đã xác nhận thành regression test.
- **Chỉ số quyết định:** độ chính xác theo chuyên đề, tỷ lệ phải sửa dữ kiện, thời gian chuẩn bị bài của giáo viên, mức độ hoàn thành bài của học sinh và mức độ quay lại sau đợt thí điểm.

### Giai đoạn 3. Hoàn thiện ứng dụng cho giáo viên và học sinh

- **Ứng dụng giáo viên:** cải thiện scene editor, quản lý lịch sử, tái sử dụng kết quả và export học liệu. PDF to Word tiếp tục là nhánh chuyển đổi tài liệu độc lập, không bị ghép thành đầu vào của renderer.
- **Ứng dụng học sinh:** tổ chức mô phỏng và bài luyện theo chuyên đề, làm rõ trạng thái kiểm chứng, giả định và lỗi để người học không nhầm hình minh họa với kết luận toán học.
- **Nền tảng:** hoàn thiện learning profile ở mức dữ liệu tối thiểu cần thiết, phân quyền dữ liệu cá nhân và dashboard chất lượng cho nhóm vận hành.
- **Chỉ số quyết định:** số học liệu được tạo và tái sử dụng, số phiên học hoàn thành, tỷ lệ người dùng quay lại và phản hồi định tính từ giáo viên.

### Giai đoạn 4. Fine-tune model từ dữ liệu đã kiểm duyệt

- **Ứng dụng:** giảm số bước người dùng phải sửa khi nhập đề tiếng Việt, nhưng giữ cơ chế xác nhận khi model không chắc chắn.
- **Dữ liệu:** xây dataset từ đề toán, scene cấu trúc, yêu cầu solver và các trường hợp người dùng đã sửa; dữ liệu phải được ẩn thông tin cá nhân, gắn nhãn và kiểm duyệt trước khi huấn luyện.
- **Nền tảng AI:** fine-tune model phù hợp cho hiểu ý định, trích xuất dữ kiện và chuẩn hóa đầu vào. Model mới chỉ được phát hành khi vượt baseline của Giai đoạn 2 trên tập kiểm thử tách biệt.
- **Ranh giới:** kết quả toán học vẫn đi qua validator, geometry engine, CAS hoặc solver. Fine-tune không thay thế lõi kiểm chứng.
- **Chỉ số quyết định:** độ chính xác trích xuất, tỷ lệ người dùng phải sửa, độ trễ, chi phí mỗi tác vụ và mức phụ thuộc vào API bên ngoài.

### Giai đoạn 5. Phát triển thành nền tảng có khả năng mở rộng

- **Ứng dụng:** giữ web app là kênh chính; chỉ đầu tư thêm PWA hoặc ứng dụng di động khi dữ liệu thiết bị và tần suất sử dụng chứng minh nhu cầu.
- **Nền tảng:** chuẩn hóa contract giữa frontend và các lõi toán học, tách worker khi hàng đợi và tải thực tế yêu cầu, kiểm chứng backup/restore, tăng khả năng quan sát và cô lập tác vụ nặng.
- **Tích hợp:** mở API hoặc tích hợp với hệ thống trường học, kho học liệu khi có đối tác và use case cụ thể; không mở rộng API chỉ để có thêm tính năng trình diễn.
- **Vận hành:** xác định quota, chi phí hạ tầng và gói sử dụng phù hợp cho cá nhân hoặc tổ chức để sản phẩm có nguồn lực duy trì lâu dài.
- **Chỉ số quyết định:** độ ổn định, chi phí trên người dùng hoạt động, thời gian phản hồi, số tích hợp được sử dụng thật và khả năng duy trì vận hành.

### Giai đoạn 6. Hệ sinh thái học tập cá nhân hóa

- **Ứng dụng:** dùng history và learning profile để gợi ý mô phỏng, bài luyện hoặc ví dụ theo năng lực; giáo viên có thể theo dõi tiến trình trong phạm vi được người học cho phép.
- **Nội dung:** mở rộng chuyên đề dựa trên nhu cầu và benchmark, ưu tiên chiều sâu kiểm chứng thay vì tuyên bố bao phủ toàn bộ chương trình.
- **Nền tảng:** cung cấp cơ chế để giáo viên đóng góp, rà soát và tái sử dụng học liệu có phiên bản và nguồn gốc rõ ràng.
- **Chỉ số quyết định:** tiến bộ học tập, mức độ tái sử dụng học liệu, tỷ lệ đóng góp được kiểm duyệt và tỷ lệ duy trì người dùng dài hạn.

Cam kết phát triển sau cuộc thi không nằm ở số lượng tính năng dự kiến, mà ở vòng lặp phát hành–đo lường–cải tiến, nhóm người dùng thí điểm, dữ liệu benchmark và nền tảng vận hành đã được đặt làm phần chính của sản phẩm. Nếu một hướng mở rộng không tạo giá trị sử dụng hoặc không đạt ngưỡng chất lượng, nhóm dừng hướng đó và ưu tiên workflow đang được dùng thật.

## 9. Kết luận

AI Math Renderer không phải chatbot giải toán đơn thuần và cũng không chỉ là công cụ dựng hình. Sản phẩm tạo một không gian làm việc toán học, nơi đề bài có thể đi từ dữ liệu đầu vào đến trực quan hóa, phân tích, lời giải, mô phỏng và học liệu xuất ra.

AI giúp người dùng giao tiếp tự nhiên với hệ thống. Parser, validator, geometry engine, analyzer, solver, CAS, renderer và quality gate chịu trách nhiệm biến yêu cầu đó thành kết quả có cấu trúc, có trạng thái tin cậy và có thể kiểm chứng.

> **Mục tiêu của AI Math Renderer là giúp người học nhìn thấy toán học, giúp người dạy tạo học liệu nhanh hơn, và giữ cho sự linh hoạt của AI đi cùng trách nhiệm kiểm chứng của lõi toán học.**

