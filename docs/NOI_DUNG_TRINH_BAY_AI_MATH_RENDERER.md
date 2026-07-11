# NỘI DUNG TRÌNH BÀY DỰ ÁN AI MATH RENDERER

> Tài liệu dùng cho phần thuyết trình tại vòng chung kết hoặc buổi giới thiệu sản phẩm.  
> Thời lượng đề xuất: **8–10 phút trình bày + 3–5 phút demo**.

---

## 1. Thông điệp cốt lõi

**AI Math Renderer là một không gian học và biên soạn toán học thông minh, giúp chuyển đề bài bằng tiếng Việt hoặc hình ảnh thành mô hình trực quan, phân tích có cấu trúc, lời giải từng bước và tài liệu có thể tiếp tục chỉnh sửa.**

Sản phẩm được xây dựng để giải quyết hai khó khăn rất thực tế:

1. Học sinh khó hình dung các đối tượng và quan hệ trong hình học không gian.
2. Giáo viên, gia sư và học sinh mất nhiều thời gian khi số hóa đề toán, đặc biệt khi công thức bị chuyển thành ký tự Unicode hoặc văn bản thuần thay vì công thức toán học có cấu trúc.

---

# PHẦN I. KỊCH BẢN TRÌNH BÀY

## Slide 1. Mở đầu

### Nội dung trên slide

- AI Math Renderer
- Từ đề bài đến mô hình toán học trực quan
- Dành cho học sinh, giáo viên và người biên soạn học liệu

### Lời trình bày

Kính thưa quý thầy cô và hội đồng,

Nhóm chúng em xin giới thiệu **AI Math Renderer**, một nền tảng hỗ trợ học, dạy và biên soạn toán học bằng trí tuệ nhân tạo.

Sản phẩm giúp người dùng đi từ một đề bài viết bằng tiếng Việt, một biểu thức toán học hoặc một ảnh chụp đề bài đến các kết quả có thể quan sát và tương tác trực tiếp, bao gồm hình học 2D, hình học không gian 3D, đồ thị hàm số, phân tích hàm, lời giải đại số, mô phỏng kiến thức và tài liệu Word có thể tiếp tục chỉnh sửa.

Mục tiêu của nhóm không phải là tạo thêm một chatbot chỉ trả về đáp án. Chúng em muốn xây dựng một **không gian làm việc toán học**, nơi người học có thể nhìn thấy, kiểm tra, tương tác và hiểu được quá trình hình thành kết quả.

---

## Slide 2. Lý do chọn đề tài

### Nội dung trên slide

- Khó hình dung hình học không gian
- Khó kiểm chứng hình vẽ từ đề bài
- Mất thời gian soạn và số hóa tài liệu
- Công thức thường bị biến thành Unicode hoặc văn bản thuần

### Lời trình bày

Ý tưởng của dự án bắt đầu từ một trải nghiệm cá nhân trong quá trình gia sư cho một học sinh từ lớp 11 lên lớp 12.

Trong quá trình học, em nhận thấy học sinh có thể nhớ công thức nhưng vẫn gặp rất nhiều khó khăn khi phải hình dung một mặt phẳng cắt hình chóp như thế nào, hai đường thẳng chéo nhau nằm ở đâu, góc giữa đường thẳng và mặt phẳng được tạo thành ra sao, hoặc vì sao một quan hệ hình học lại đúng.

Với hình học không gian, một hình vẽ tĩnh trên giấy đôi khi chưa đủ. Chỉ cần góc nhìn chưa phù hợp hoặc một nét khuất được thể hiện không rõ, học sinh có thể hiểu sai toàn bộ cấu trúc của bài toán. Trong khi đó, các công cụ dựng hình hiện nay thường yêu cầu người dùng biết nhiều thao tác hoặc cú pháp riêng.

Khó khăn thứ hai xuất hiện khi em soạn tài liệu. Nhiều công cụ chuyển đổi PDF hoặc ảnh sang văn bản chỉ nhận diện công thức dưới dạng ký tự Unicode hay chuỗi văn bản rời rạc. Khi đưa vào Word, công thức không còn là một cấu trúc toán học dễ chỉnh sửa. Người soạn phải nhập lại bằng LaTeX hoặc Equation, vừa tốn thời gian vừa dễ sai.

Từ hai vấn đề đó, nhóm đặt ra câu hỏi:

> Liệu có thể tạo một hệ thống để người dùng chỉ cần nhập đề bài bằng ngôn ngữ tự nhiên hoặc tải ảnh lên, sau đó hệ thống tự hiểu cấu trúc toán học, dựng hình, phân tích, giải và hỗ trợ số hóa tài liệu trong cùng một nền tảng hay không?

AI Math Renderer được phát triển để trả lời câu hỏi đó.

---

## Slide 3. Bài toán mà sản phẩm giải quyết

### Nội dung trên slide

| Đối tượng | Khó khăn hiện tại | Giá trị sản phẩm mang lại |
|---|---|---|
| Học sinh | Khó hình dung và tự kiểm chứng | Hình 2D/3D tương tác, mô phỏng từng bước |
| Giáo viên, gia sư | Tốn thời gian dựng hình và soạn đề | Tạo hình, phân tích và xuất tài liệu nhanh hơn |
| Người biên soạn học liệu | Công thức OCR sai hoặc mất cấu trúc | Nhận diện công thức, bảng và nội dung toán học |
| Người tự học | Công cụ rời rạc, phải chuyển qua nhiều ứng dụng | Một luồng làm việc thống nhất từ đề bài đến kết quả |

### Lời trình bày

Hiện nay người dùng thường phải sử dụng nhiều công cụ riêng biệt. Một công cụ để OCR, một công cụ để vẽ hình, một công cụ để khảo sát hàm số, một công cụ để giải phương trình, một công cụ để mô phỏng và một công cụ khác để chuyển PDF sang Word.

Sự phân mảnh này khiến dữ liệu bị đứt đoạn, người dùng phải nhập lại nhiều lần và khó kiểm tra kết quả giữa các bước.

AI Math Renderer kết nối những công việc đó thành một quy trình thống nhất:

**Nhập đề bài → nhận diện nội dung → chuẩn hóa cấu trúc toán học → kiểm tra → trực quan hóa hoặc giải → tương tác → lưu và xuất kết quả.**

---

## Slide 4. Tổng quan sản phẩm

### Nội dung trên slide

Sáu phân hệ hiện có:

1. Dựng hình AI
2. Analyzer – khảo sát hàm số
3. Bộ giải đại số
4. Thư viện mô phỏng toán học
5. GeoGebra Lab
6. PDF sang Word

### Lời trình bày

Ở phiên bản hiện tại, sản phẩm đã có sáu phân hệ chính. Mỗi phân hệ giải quyết một nhu cầu riêng, nhưng đều được thiết kế theo cùng một định hướng: giảm rào cản nhập liệu, tăng khả năng quan sát và giúp người dùng kiểm tra kết quả thay vì chỉ nhận một đáp án cuối cùng.

Sau đây là mô tả ngắn gọn từng chức năng.

---

## Slide 5. Chức năng 1 – Dựng hình AI

### Nội dung trên slide

- Nhập đề bằng tiếng Việt, tọa độ hoặc ảnh chụp
- Dựng hình phẳng và hình học không gian
- Hiển thị bằng GeoGebra hoặc Three.js
- Kiểm tra schema, quan hệ và khả năng tương thích renderer
- Cho phép chỉnh sửa, xoay, kéo thả và xuất kết quả

### Lời trình bày

Chức năng trung tâm của dự án là **Dựng hình AI**.

Người dùng có thể nhập một đề bài bằng tiếng Việt, dán dữ liệu tọa độ hoặc tải ảnh chụp đề bài. Hệ thống không yêu cầu người dùng phải viết sẵn lệnh GeoGebra hay mã Three.js.

AI đảm nhiệm bước đọc và chuyển nội dung thành một scene toán học có cấu trúc, gồm các điểm, đoạn thẳng, đường, mặt phẳng, đa giác, khối hình và các quan hệ hình học. Scene này tiếp tục đi qua các bước kiểm tra schema, chuẩn hóa dữ liệu, kiểm chứng quan hệ và đánh giá khả năng tương thích với bộ dựng hình.

Sau đó, hệ thống lựa chọn cách hiển thị phù hợp:

- **GeoGebra** phù hợp với hình học phẳng, hệ trục Oxy và đồ thị.
- **Three.js hoặc GeoGebra 3D** phù hợp với hình học không gian, hệ trục Oxyz, khối đa diện, mặt phẳng và các đối tượng ba chiều.

Người dùng có thể xoay góc nhìn, kéo các điểm, chỉnh sửa scene và xuất kết quả dưới nhiều định dạng như PNG, JPG, SVG, TikZ, PDF, tệp GeoGebra hoặc HTML có KaTeX.

Điểm quan trọng là hệ thống không mặc định coi mọi kết quả AI là đúng. Nếu AI phải đưa ra giả định, sử dụng dữ liệu thay thế hoặc tự sửa một phần scene, sản phẩm có thể đưa ra cảnh báo và yêu cầu người dùng xác nhận.

---

## Slide 6. Chức năng 2 – Analyzer khảo sát hàm số

### Nội dung trên slide

- Nhập biểu thức hoặc OCR từ ảnh
- Tập xác định và tập giá trị
- Đạo hàm, đạo hàm cấp hai
- Khoảng đồng biến, nghịch biến
- Cực trị, điểm uốn, độ cong
- Tiệm cận, giao trục, bảng biến thiên
- Đồ thị và phép biến đổi tương tác

### Lời trình bày

Phân hệ thứ hai là **Analyzer**, hỗ trợ khảo sát hàm số theo một quy trình có cấu trúc.

Người dùng có thể nhập biểu thức trực tiếp hoặc dùng OCR từ ảnh. Hệ thống trả về các thành phần như tập xác định, đạo hàm, đạo hàm cấp hai, điểm tới hạn, khoảng đồng biến và nghịch biến, điểm uốn, khoảng lõm lên và lõm xuống, tiệm cận, giao điểm với các trục và bảng biến thiên.

Kết quả không chỉ được hiển thị bằng văn bản. Analyzer còn tạo dữ liệu đồ thị và các lệnh GeoGebra để người dùng quan sát trực tiếp.

Ngoài khảo sát cơ bản, người dùng có thể thử nghiệm khoảng xét, đường thẳng tham chiếu hoặc phép biến đổi hàm số. Khi tham số thay đổi, kết quả và hình ảnh được cập nhật để người học quan sát mối quan hệ giữa biểu thức đại số và đồ thị.

---

## Slide 7. Chức năng 3 – Bộ giải đại số

### Nội dung trên slide

- Nhập bằng tiếng Việt hoặc công thức
- Hỗ trợ nhiều chủ đề và miền nghiệm
- Chọn radian hoặc độ, khoảng nghiệm và biến cần tìm
- Trình bày lời giải từng bước
- Kiểm chứng kết quả
- Lưu lịch sử bài đã giải

### Lời trình bày

Phân hệ thứ ba là **Bộ giải đại số**.

Người dùng có thể nhập trực tiếp công thức hoặc mô tả bài toán bằng tiếng Việt. Hệ thống hỗ trợ lựa chọn chủ đề, miền nghiệm như số thực, số phức, số tự nhiên hoặc số nguyên, biến cần tìm, đơn vị góc và khoảng nghiệm.

Với dữ liệu nhập bằng ngôn ngữ tự nhiên, hệ thống có thể sử dụng AI để trích xuất biểu thức toán học. Trước khi giải, người dùng được kiểm tra lại cách hệ thống hiểu đề, nhờ đó giảm nguy cơ giải đúng một bài toán nhưng lại khác với ý định ban đầu.

Kết quả được trình bày từng bước bằng định dạng toán học dễ đọc, có trạng thái kiểm chứng và có lịch sử để người dùng mở lại những bài gần đây.

Giá trị của chức năng này không chỉ là đưa ra nghiệm, mà là hỗ trợ người học theo dõi quá trình biến đổi và đối chiếu từng bước.

---

## Slide 8. Chức năng 4 – Thư viện mô phỏng toán học

### Nội dung trên slide

- Học theo từng bước hoặc chế độ khám phá tự do
- Diện tích giữa hai đường cong
- Khối tròn xoay và thể tích theo thiết diện
- Đường tròn lượng giác
- Đạo hàm, nguyên hàm, giới hạn và tiệm cận
- Dãy số, xác suất, Bayes, thống kê
- Tọa độ và quan hệ trong không gian

### Lời trình bày

Phân hệ thứ tư là **Thư viện mô phỏng toán học**.

Thay vì chỉ đọc định nghĩa và công thức, học sinh có thể quan sát khái niệm thay đổi theo từng bước. Ví dụ, số hình chữ nhật Riemann tăng lên thì phần diện tích xấp xỉ thay đổi ra sao; một miền phẳng quay quanh trục tạo thành khối tròn xoay như thế nào; điểm trên đường tròn lượng giác liên hệ với sin và cos ra sao.

Thư viện hiện có nhiều nhóm mô phỏng như diện tích giữa hai đường cong, khối tròn xoay, thể tích theo thiết diện, khảo sát đạo hàm, họ nguyên hàm, giới hạn và tính liên tục, tiệm cận của hàm hữu tỉ, dãy số, phương trình lượng giác, xác suất Bayes, thống kê, cây xác suất và hình học tọa độ không gian.

Người dùng có thể học theo tiến trình được hướng dẫn hoặc chuyển sang chế độ tự do để thay đổi tham số và tự khám phá.

---

## Slide 9. Chức năng 5 – GeoGebra Lab

### Nội dung trên slide

- Tích hợp trực tiếp GeoGebra API
- Bốn chế độ: Graphing, Geometry, 3D và Probability
- Chạy lệnh và dùng mẫu dựng sẵn
- Undo, redo, lưu và khôi phục trạng thái
- Xuất PNG, SVG và PDF

### Lời trình bày

Phân hệ thứ năm là **GeoGebra Lab**, một phòng thí nghiệm toán học tương tác được tích hợp thông qua GeoGebra API.

GeoGebra Lab cung cấp bốn không gian làm việc gồm đồ thị 2D, hình học phẳng, hình học 3D và xác suất. Người dùng có thể thao tác bằng thanh công cụ của GeoGebra, chạy lệnh trực tiếp hoặc chọn các mẫu dựng sẵn như parabol, đường tròn, tam giác, mặt phẳng, mặt cầu, hình nón, hình trụ và tứ diện.

Hệ thống hỗ trợ hoàn tác, làm lại, theo dõi số đối tượng, lưu trạng thái làm việc, khôi phục trạng thái và xuất hình dưới dạng PNG, SVG hoặc PDF.

GeoGebra Lab được đặt trong cùng nền tảng để người dùng không phải rời khỏi quá trình học và có thể chuyển nhanh từ kết quả do AI tạo sang môi trường thực hành thủ công.

---

## Slide 10. Chức năng 6 – PDF sang Word

### Nội dung trên slide

- Tích hợp API MinerU
- Nhận diện văn bản, công thức và bảng
- Hỗ trợ OCR cho tài liệu scan
- Chọn ngôn ngữ và phạm vi trang
- Theo dõi tiến trình xử lý
- Xem trước và tải các tệp kết quả

### Lời trình bày

Phân hệ thứ sáu là **PDF sang Word**, được phát triển từ chính khó khăn khi soạn tài liệu toán học.

Người dùng có thể tải một tệp PDF, chọn phạm vi trang, ngôn ngữ, phương pháp phân tích, chế độ OCR, nhận diện công thức và nhận diện bảng. Hệ thống gọi dịch vụ MinerU để phân tích tài liệu và theo dõi công việc theo từng trạng thái.

Khác với việc chỉ sao chép phần văn bản nhìn thấy, quy trình được thiết kế để nhận diện riêng các thành phần toán học như công thức, bảng và bố cục. Việc cho phép cấu hình kiểu dấu phân cách LaTeX giúp hạn chế tình trạng công thức bị biến thành một chuỗi Unicode khó chỉnh sửa.

Người dùng có thể theo dõi tiến độ, xem thông báo của quá trình xử lý, xem trước kết quả và tải xuống các tệp được tạo ra.

Đây là chức năng hướng trực tiếp đến giáo viên, gia sư, sinh viên và những người thường xuyên xây dựng ngân hàng câu hỏi hoặc số hóa học liệu.

---

## Slide 11. Luồng demo đề xuất

### Nội dung trên slide

**Một đề bài – nhiều cách tiếp cận**

1. Tải ảnh đề bài
2. OCR và dựng hình
3. Xoay mô hình 3D
4. Mở Analyzer hoặc Bộ giải
5. Xuất hình hoặc tài liệu

### Kịch bản demo

Có thể sử dụng một đề hình học không gian ngắn, chẳng hạn:

> Cho hình chóp S.ABCD có đáy ABCD là hình vuông. SA vuông góc với mặt phẳng đáy. Dựng hình, làm nổi bật đường chéo AC và mặt phẳng (SAC).

Quy trình demo:

1. Dán đề bài hoặc tải ảnh chụp.
2. Chọn renderer 3D và yêu cầu dựng hình.
3. Cho hội đồng quan sát scene được tạo và xoay góc nhìn.
4. Chỉ ra các đối tượng S, A, B, C, D, đường chéo AC và mặt phẳng (SAC).
5. Thử kéo hoặc chỉnh sửa một điểm để thể hiện tính tương tác.
6. Mở menu xuất để cho thấy kết quả có thể được đưa vào bài giảng hoặc tài liệu.
7. Nếu còn thời gian, chuyển sang PDF sang Word để cho thấy quy trình số hóa đề.

### Lưu ý khi demo

- Chuẩn bị trước một đề ngắn đã kiểm thử.
- Có ảnh chụp hoặc video dự phòng trong trường hợp mạng yếu.
- Không dùng đề quá dài hoặc có quá nhiều giả thiết trong phần demo chính.
- Nếu hệ thống hiển thị cảnh báo giả định, nên dùng đó để giải thích cơ chế human-in-the-loop thay vì cố che giấu.

---

## Slide 12. Điểm mới và sáng tạo

### Nội dung trên slide

1. Không chỉ trả lời, mà tạo không gian toán học có thể kiểm tra
2. Kết hợp AI sinh với công cụ toán học xác định
3. Chuyển ngôn ngữ tự nhiên thành scene tương tác, không chỉ ảnh tĩnh
4. Liên kết toàn bộ quy trình học và biên soạn
5. Thiết kế ưu tiên tiếng Việt và nhu cầu lớp 11–12
6. Minh bạch về giả định, sửa lỗi và nguồn xử lý

### Lời trình bày

Điểm mới của dự án không nằm ở việc gọi một mô hình AI để trả lời câu hỏi. Sự khác biệt nằm ở cách nhóm xây dựng một quy trình toán học có cấu trúc và có thể kiểm tra.

### 1. Từ câu trả lời sang không gian tương tác

Nhiều sản phẩm AI hiện nay trả về lời giải hoặc tạo một hình ảnh tĩnh. AI Math Renderer tạo ra một scene gồm các đối tượng và quan hệ toán học. Vì có cấu trúc, scene có thể được kiểm tra, chỉnh sửa, dựng lại bằng nhiều renderer và xuất sang nhiều định dạng.

### 2. Kết hợp AI với các thành phần xác định

AI phù hợp với việc đọc ngôn ngữ tự nhiên và nhận diện ý định. Tuy nhiên, toán học cần tính chính xác. Vì vậy, sản phẩm kết hợp nhiều lớp:

- AI để hiểu đề và trích xuất cấu trúc.
- Schema để kiểm tra dữ liệu đầu ra.
- Geometry engine để chuẩn hóa scene.
- CAS và bộ kiểm chứng để kiểm tra quan hệ.
- GeoGebra, Three.js và KaTeX để hiển thị.

Cách tiếp cận này giúp giảm phụ thuộc vào một câu trả lời sinh tự do của mô hình ngôn ngữ.

### 3. Human-in-the-loop

Khi hệ thống phải giả định, sửa dữ liệu hoặc dùng phương án fallback, người dùng được cảnh báo. Sản phẩm không cố tạo cảm giác chắc chắn giả tạo, mà cho phép người dùng xác nhận trước khi sử dụng kết quả.

### 4. Một hệ sinh thái thay vì các công cụ rời rạc

Dựng hình, khảo sát hàm số, giải đại số, mô phỏng, GeoGebra Lab và số hóa PDF được đặt trong cùng một hệ thống. Người dùng có thể chuyển từ hiểu đề đến quan sát, giải, kiểm tra và xuất tài liệu mà không phải nhập lại dữ liệu qua nhiều ứng dụng.

### 5. Xuất phát từ nhu cầu giáo dục Việt Nam

Giao diện, hướng dẫn và cách nhập liệu được thiết kế ưu tiên tiếng Việt. Nội dung mô phỏng tập trung vào những chủ đề gần với chương trình phổ thông, đặc biệt là lớp 11 và lớp 12.

### 6. Tính minh bạch trong tích hợp công nghệ

GeoGebra và MinerU là các công nghệ được tích hợp vào hệ thống. Phần nhóm tự phát triển nằm ở luồng xử lý, cấu trúc scene, kiểm tra dữ liệu, cơ chế xác nhận, giao diện học tập, thư viện mô phỏng, quản lý lịch sử và việc kết nối các thành phần thành một sản phẩm hoàn chỉnh.

Nhóm không xem việc tích hợp API là điểm mới duy nhất. Giá trị cốt lõi nằm ở cách các công nghệ được điều phối để giải quyết một quy trình giáo dục cụ thể.

---

## Slide 13. Kiến trúc sản phẩm

### Nội dung trên slide

```text
Người dùng
   ↓
React/Vite frontend
   ↓ REST / WebSocket
FastAPI backend
   ├─ AI providers
   ├─ OCR
   ├─ Scene pipeline
   ├─ Geometry engine / CAS verifier
   ├─ Analyzer / Solver
   ├─ Export services
   └─ Database / Storage / Analytics
   ↓
GeoGebra · Three.js · KaTeX · MinerU
```

### Lời trình bày

Về kỹ thuật, sản phẩm sử dụng frontend React và Vite, backend FastAPI, giao tiếp qua REST và WebSocket.

Backend được chia thành các module cho AI provider, OCR, dựng hình, kiểm tra scene, phân tích hàm, giải đại số, xuất tệp, lưu trữ và quản lý dữ liệu.

Sản phẩm hỗ trợ nhiều nhà cung cấp mô hình AI thay vì phụ thuộc vào duy nhất một dịch vụ. Điều này giúp hệ thống linh hoạt hơn về chi phí, chất lượng và khả năng dự phòng.

Hệ thống đã có tài khoản người dùng, lịch sử, quản trị, phân tích hành vi sử dụng, logging, health check, test tự động và quy trình CI/CD. Đây là nền tảng để nhóm tiếp tục thử nghiệm với người dùng thật sau cuộc thi.

---

## Slide 14. Hiện trạng sản phẩm

### Nội dung trên slide

### Đã hoàn thành

- Sáu phân hệ chính đã có giao diện và luồng sử dụng
- Dựng hình 2D/3D từ văn bản và ảnh
- OCR, Analyzer và Bộ giải đại số
- Thư viện mô phỏng có chế độ hướng dẫn và tự do
- GeoGebra Lab và PDF sang Word
- Đăng nhập, lịch sử, quản trị và analytics
- Test backend, build frontend, Docker và CI/CD

### Cần tiếp tục hoàn thiện

- Độ chính xác với đề dài và hình phức tạp
- Chất lượng OCR công thức trong ảnh mờ
- Benchmark định lượng theo chương trình phổ thông
- Trải nghiệm chỉnh sửa scene trên thiết bị di động
- Quy trình xuất Word với công thức có thể chỉnh sửa ổn định hơn

### Lời trình bày

Sản phẩm hiện không còn ở mức ý tưởng hay bản thiết kế giao diện. Nhóm đã xây dựng được một ứng dụng web có frontend, backend, cơ sở dữ liệu, xác thực, lịch sử sử dụng, analytics và pipeline triển khai.

Sáu chức năng chính đã có thể được mở và sử dụng trong sản phẩm. Hệ thống cũng đã có test tự động và quy trình CI/CD để giảm lỗi khi phát triển.

Tuy nhiên, nhóm xác định rõ đây vẫn là giai đoạn cần kiểm chứng thực tế. Những bài toán dài, ảnh chất lượng thấp hoặc hình học có nhiều giả thiết vẫn có thể làm giảm độ chính xác. Việc giữ công thức có thể chỉnh sửa hoàn toàn trong Word cũng cần tiếp tục được đánh giá trên nhiều loại tài liệu.

Nhóm chủ động nêu các giới hạn này vì mục tiêu sau cuộc thi là phát triển sản phẩm dựa trên dữ liệu sử dụng thật, không chỉ hoàn thiện một bản demo.

---

## Slide 15. Lộ trình phát triển trong 2 tháng sau cuộc thi

### Nội dung trên slide

| Thời gian | Mục tiêu | Kết quả đầu ra |
|---|---|---|
| Tuần 1–2 | Ổn định và đo lường | Bộ test chuẩn, sửa lỗi ưu tiên, dashboard chỉ số |
| Tuần 3–4 | Nâng chất lượng toán học và OCR | Benchmark, cơ chế sửa công thức, tăng độ chính xác |
| Tuần 5–6 | Hoàn thiện trải nghiệm giáo viên và học sinh | Workspace lớp học, chia sẻ bài, bộ mẫu bài giảng |
| Tuần 7–8 | Thử nghiệm thực tế | Pilot với người dùng, báo cáo kết quả, kế hoạch mở rộng |

### Lời trình bày

Sau cuộc thi, nhóm dự kiến triển khai lộ trình hai tháng theo bốn giai đoạn.

### Tuần 1–2: Ổn định sản phẩm và xây dựng bộ đo lường

- Chuẩn hóa bộ đề kiểm thử theo các chủ đề lớp 11 và lớp 12.
- Theo dõi tỷ lệ dựng hình thành công, thời gian xử lý, số lần người dùng phải sửa và tỷ lệ hoàn thành tác vụ.
- Sửa các lỗi ảnh hưởng trực tiếp đến demo và trải nghiệm cốt lõi.
- Hoàn thiện giám sát lỗi, cảnh báo và dashboard sử dụng.

### Tuần 3–4: Nâng chất lượng OCR, LaTeX và kiểm chứng

- Xây dựng tập benchmark gồm đề dạng văn bản, ảnh chụp và PDF scan.
- Đánh giá riêng độ chính xác của văn bản, công thức, bảng và cấu trúc hình học.
- Bổ sung giao diện cho phép người dùng sửa nhanh biểu thức OCR trước khi gửi xử lý.
- Cải thiện quy trình xuất Word để công thức giữ được cấu trúc và dễ chỉnh sửa hơn.
- Mở rộng kiểm chứng quan hệ hình học và kết quả đại số.

### Tuần 5–6: Phát triển công cụ dành cho giáo viên và lớp học

- Tạo bộ mẫu dựng hình và mô phỏng theo từng chủ đề.
- Cho phép giáo viên lưu, sao chép và chia sẻ một bài toán hoặc một scene.
- Xây dựng workspace theo bài học, trong đó có đề bài, hình, lời giải và tài liệu đính kèm.
- Bổ sung hồ sơ học tập để đề xuất mức giải thích phù hợp với người dùng.

### Tuần 7–8: Pilot với người dùng thật

- Thử nghiệm với một nhóm học sinh, gia sư và giáo viên.
- Thu thập phản hồi định tính và các chỉ số định lượng.
- So sánh thời gian hoàn thành khi dùng sản phẩm với quy trình dùng nhiều công cụ rời rạc.
- Công bố báo cáo thử nghiệm, xác định nhóm tính năng có giá trị cao nhất và xây dựng kế hoạch phát triển giai đoạn tiếp theo.

---

## Slide 16. Chỉ số đánh giá trong giai đoạn tiếp theo

### Nội dung trên slide

- Tỷ lệ dựng hình thành công
- Tỷ lệ quan hệ hình học được kiểm chứng
- Độ chính xác OCR công thức
- Tỷ lệ công thức giữ được khả năng chỉnh sửa sau khi xuất
- Thời gian tiết kiệm khi soạn tài liệu
- Tỷ lệ học sinh hoàn thành mô phỏng
- Mức độ hài lòng của giáo viên và học sinh

### Lời trình bày

Nhóm không muốn đánh giá sản phẩm chỉ bằng cảm giác hình ảnh đẹp hay câu trả lời có vẻ hợp lý.

Trong giai đoạn tiếp theo, nhóm sẽ tập trung vào các chỉ số có thể đo lường, như tỷ lệ dựng đúng đối tượng, tỷ lệ quan hệ được kiểm chứng, độ chính xác OCR công thức, thời gian tiết kiệm khi biên soạn và tỷ lệ người học hoàn thành tác vụ.

Các chỉ số này giúp nhóm biết tính năng nào thực sự tạo giá trị và lỗi nào cần được ưu tiên sửa trước.

---

## Slide 17. Tầm nhìn phát triển

### Nội dung trên slide

**Từ công cụ dựng hình → nền tảng thực hành toán học số**

- Kho học liệu tương tác
- Không gian lớp học
- Cá nhân hóa theo trình độ
- API cho nền tảng giáo dục
- Hỗ trợ thêm môn học có công thức và mô phỏng

### Lời trình bày

Tầm nhìn dài hạn của nhóm là phát triển AI Math Renderer từ một công cụ dựng hình thành một nền tảng thực hành toán học số.

Trong đó, giáo viên có thể tạo và chia sẻ học liệu tương tác; học sinh có thể quan sát, thử nghiệm và lưu lại quá trình học; còn các nền tảng giáo dục khác có thể sử dụng API để tích hợp chức năng dựng hình, phân tích hoặc số hóa tài liệu.

Sau khi hoàn thiện toán học phổ thông, kiến trúc của hệ thống có thể mở rộng sang các nội dung cần công thức và mô phỏng như vật lý, xác suất thống kê hoặc kỹ thuật.

---

## Slide 18. Kết thúc

### Nội dung trên slide

> Không chỉ giúp học sinh tìm ra đáp án,  
> AI Math Renderer giúp các em nhìn thấy và kiểm chứng toán học.

### Lời trình bày

AI Math Renderer được bắt đầu từ một khó khăn rất cụ thể trong quá trình gia sư và soạn tài liệu. Từ vấn đề đó, nhóm đã phát triển một sản phẩm kết nối AI, công cụ toán học và trực quan hóa thành một quy trình thống nhất.

Chúng em tin rằng công nghệ giáo dục có giá trị nhất khi không thay thế tư duy của người học, mà giúp những khái niệm trừu tượng trở nên có thể quan sát, tương tác và kiểm chứng.

Thông điệp mà nhóm muốn gửi gắm là:

> AI Math Renderer không chỉ giúp học sinh tìm ra đáp án. Sản phẩm giúp các em nhìn thấy cấu trúc của bài toán, thử nghiệm giả thiết và hiểu vì sao kết quả được hình thành.

Nhóm xin cảm ơn quý thầy cô và hội đồng đã lắng nghe.

---

# PHẦN II. PHIÊN BẢN TRÌNH BÀY NGẮN 3 PHÚT

Kính thưa quý thầy cô và hội đồng,

Nhóm chúng em xin giới thiệu AI Math Renderer, một nền tảng hỗ trợ học, dạy và biên soạn toán học bằng trí tuệ nhân tạo.

Ý tưởng bắt đầu khi em gia sư cho một học sinh từ lớp 11 lên lớp 12. Em nhận thấy học sinh thường khó hình dung các quan hệ trong hình học không gian dù đã nhớ công thức. Đồng thời, khi soạn tài liệu, nhiều công cụ chuyển đổi PDF hoặc ảnh chỉ biến công thức thành Unicode hay văn bản thuần, khiến người dùng phải nhập lại rất nhiều.

AI Math Renderer giải quyết hai vấn đề đó bằng một luồng làm việc thống nhất. Người dùng có thể nhập đề bài bằng tiếng Việt, công thức hoặc ảnh chụp. Hệ thống nhận diện nội dung, chuẩn hóa cấu trúc toán học, kiểm tra và tạo kết quả có thể tương tác.

Sản phẩm hiện có sáu phân hệ. Dựng hình AI tạo hình 2D và 3D bằng GeoGebra hoặc Three.js. Analyzer khảo sát hàm số, tạo đạo hàm, bảng biến thiên, tiệm cận và đồ thị. Bộ giải đại số nhận đề tiếng Việt hoặc công thức và trình bày lời giải từng bước. Thư viện mô phỏng giúp học sinh quan sát các khái niệm như diện tích, khối tròn xoay, lượng giác, giới hạn, xác suất và hình học không gian. GeoGebra Lab cung cấp môi trường thực hành trực tiếp. PDF sang Word hỗ trợ nhận diện văn bản, công thức và bảng từ tài liệu.

Điểm khác biệt của dự án là không chỉ dùng AI để sinh câu trả lời. AI được kết hợp với schema, geometry engine, CAS và các renderer để tạo dữ liệu toán học có cấu trúc, có thể kiểm tra, chỉnh sửa và xuất lại. Khi hệ thống phải giả định hoặc tự sửa dữ liệu, người dùng được cảnh báo và xác nhận.

Sản phẩm đã có frontend, backend, tài khoản, lịch sử, quản trị, analytics, test và CI/CD. Trong hai tháng sau cuộc thi, nhóm sẽ xây dựng bộ benchmark lớp 11–12, nâng độ chính xác OCR và dựng hình, hoàn thiện xuất Word, phát triển workspace cho giáo viên và thử nghiệm với người dùng thật.

AI Math Renderer không chỉ giúp học sinh nhận được đáp án, mà giúp các em nhìn thấy, tương tác và kiểm chứng toán học.

Nhóm xin cảm ơn hội đồng.

---

# PHẦN III. CÂU HỎI PHẢN BIỆN CÓ THỂ GẶP

## 1. Dự án có phải chỉ là một giao diện gọi API không?

**Trả lời đề xuất:**

Không. Sản phẩm có tích hợp GeoGebra và MinerU vì đây là những công nghệ phù hợp cho dựng hình và phân tích tài liệu. Tuy nhiên, phần nhóm phát triển bao gồm luồng nhập đề, OCR, chuẩn hóa scene, schema toán học, kiểm tra và sửa scene, kiểm chứng quan hệ, lựa chọn renderer, giao diện chỉnh sửa, lịch sử, thư viện mô phỏng, bộ giải, Analyzer, quản lý tài khoản và hệ thống vận hành.

Giá trị của dự án nằm ở việc kết nối những thành phần này thành một quy trình giáo dục hoàn chỉnh, thay vì chỉ hiển thị trực tiếp một API có sẵn.

## 2. Làm sao bảo đảm kết quả AI chính xác?

**Trả lời đề xuất:**

Nhóm không dựa hoàn toàn vào kết quả sinh của AI. Dữ liệu do AI tạo phải tuân theo schema, sau đó được kiểm tra, chuẩn hóa và đánh giá quan hệ bằng các thành phần xác định. Hệ thống cũng có trạng thái verified, partially verified, needs confirmation hoặc failed.

Khi có giả định, sửa tự động hoặc fallback, người dùng được cảnh báo. Trong giai đoạn tiếp theo, nhóm sẽ đánh giá độ chính xác bằng bộ benchmark riêng thay vì chỉ dựa trên một vài ví dụ demo.

## 3. Đối tượng sử dụng chính là ai?

**Trả lời đề xuất:**

Đối tượng ban đầu là học sinh THPT, đặc biệt lớp 11 và lớp 12, cùng giáo viên và gia sư thường xuyên dựng hình hoặc soạn tài liệu. Sau khi sản phẩm ổn định, nhóm có thể mở rộng sang sinh viên các ngành kỹ thuật và các nền tảng giáo dục cần API toán học.

## 4. Sản phẩm khác GeoGebra ở điểm nào?

**Trả lời đề xuất:**

GeoGebra là một công cụ toán học tương tác rất mạnh. AI Math Renderer không thay thế GeoGebra mà giảm rào cản trước khi người dùng đến được với GeoGebra.

Người dùng không cần biết trước toàn bộ lệnh dựng hình. Hệ thống có thể đọc đề tiếng Việt hoặc ảnh, tạo scene, kiểm tra và chuyển thành lệnh hoặc dữ liệu hiển thị. Ngoài GeoGebra, sản phẩm còn có Three.js, Analyzer, Bộ giải, mô phỏng, OCR và PDF sang Word trong cùng một nền tảng.

## 5. Nếu AI dựng sai hình thì sao?

**Trả lời đề xuất:**

Sản phẩm cho phép người dùng xem cảnh báo, chỉnh sửa scene, kéo điểm, tạo lại hình bằng mô tả rõ hơn hoặc chuyển sang GeoGebra Lab để điều chỉnh thủ công. Mục tiêu của nhóm không phải che giấu lỗi AI, mà giúp người dùng nhận biết và sửa kết quả một cách thuận tiện.

## 6. Tại sao phải tích hợp nhiều AI provider?

**Trả lời đề xuất:**

Các model có thế mạnh, chi phí và độ ổn định khác nhau. Kiến trúc nhiều provider giúp nhóm thay đổi model theo loại tác vụ, tránh phụ thuộc hoàn toàn vào một nhà cung cấp và có phương án dự phòng khi một dịch vụ gặp lỗi.

## 7. Sản phẩm có thể thương mại hóa như thế nào?

**Trả lời đề xuất:**

Nhóm có thể phát triển theo mô hình freemium. Người dùng miễn phí được sử dụng một số lượt dựng hình hoặc phân tích mỗi ngày. Gói giáo viên có thể bổ sung kho học liệu, quản lý lớp, chia sẻ bài, xuất chất lượng cao và xử lý PDF dung lượng lớn. Ngoài ra, sản phẩm có thể cung cấp API cho trung tâm hoặc nền tảng EdTech.

Trong ngắn hạn, ưu tiên của nhóm vẫn là chứng minh giá trị sử dụng và đo lường chất lượng trước khi mở rộng mô hình doanh thu.

## 8. Hai tháng có đủ để hoàn thiện sản phẩm không?

**Trả lời đề xuất:**

Mục tiêu trong hai tháng không phải hoàn thiện toàn bộ tầm nhìn, mà là đưa sản phẩm từ phiên bản kỹ thuật hiện tại sang một phiên bản có thể thử nghiệm có kiểm soát với người dùng thật. Nhóm tập trung vào ba kết quả đo được: bộ benchmark, độ ổn định của chức năng cốt lõi và báo cáo pilot.

---

# PHẦN IV. CHECKLIST TRƯỚC KHI THUYẾT TRÌNH

## Nội dung

- [ ] Thống nhất tên sáu chức năng trong toàn bộ slide.
- [ ] Không nói GeoGebra hoặc MinerU là công nghệ do nhóm tự phát triển.
- [ ] Nhấn mạnh phần nhóm tự xây dựng: orchestration, scene schema, validation, verification, giao diện và luồng sản phẩm.
- [ ] Có một ví dụ thực tế từ quá trình gia sư.
- [ ] Nêu rõ giới hạn hiện tại để tăng tính thuyết phục.
- [ ] Lộ trình phải có mốc thời gian và kết quả đầu ra đo được.

## Demo

- [ ] Kiểm tra backend, AI provider và GeoGebra trước giờ trình bày.
- [ ] Chuẩn bị sẵn tài khoản demo.
- [ ] Chuẩn bị một đề hình học 3D ngắn.
- [ ] Chuẩn bị một biểu thức để demo Analyzer.
- [ ] Chuẩn bị một PDF 1–3 trang để demo chuyển đổi.
- [ ] Có video hoặc ảnh dự phòng.
- [ ] Tắt thông báo hệ điều hành và đóng các tab không liên quan.

## Cách trình bày

- [ ] Không đọc toàn bộ chữ trên slide.
- [ ] Mỗi chức năng chỉ nói vấn đề, cách hoạt động và giá trị chính.
- [ ] Dành nhiều thời gian nhất cho lý do chọn đề tài, demo và điểm mới.
- [ ] Khi được hỏi về độ chính xác, trả lời bằng cơ chế kiểm chứng và kế hoạch benchmark.
- [ ] Khi được hỏi về API, minh bạch phần tích hợp và phần do nhóm phát triển.
