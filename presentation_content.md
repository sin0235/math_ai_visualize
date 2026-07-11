# Nội dung trình bày dự án AI Math Renderer

## 1. Lý do chọn đề tài

### Bối cảnh thực tế

Trong quá trình gia sư cho một học sinh chuyển từ lớp 11 lên lớp 12, nhóm nhận thấy một vấn đề rất rõ: học sinh thường không yếu vì thiếu công thức, mà yếu vì khó hình dung đối tượng toán học.

Đặc biệt với hình học không gian, các khái niệm như đường thẳng chéo nhau, mặt phẳng, góc giữa hai mặt phẳng, khoảng cách từ điểm đến mặt phẳng hoặc thiết diện thường bị trình bày bằng hình tĩnh trên giấy. Khi học sinh không thể xoay, quan sát hoặc kiểm chứng hình ở nhiều góc nhìn, việc học dễ trở thành ghi nhớ máy móc.

### Khó khăn khi soạn tài liệu

Ở phía người dạy, việc chuẩn bị tài liệu cũng gặp nhiều trở ngại:

- Dựng hình toán học đẹp và chính xác tốn nhiều thời gian.
- Chuyển đổi tài liệu từ PDF sang Word thường làm hỏng công thức.
- Nhiều công cụ convert đưa ký hiệu toán học thành unicode hoặc văn bản thường, thay vì giữ dạng công thức có thể chỉnh sửa bằng LaTeX/Equation.
- Khi cần sửa đề, sửa lời giải hoặc biên soạn lại tài liệu, người dạy phải làm lại nhiều thao tác thủ công.

### Lý do hình thành dự án

Từ hai nhu cầu đó, nhóm chọn xây dựng **AI Math Renderer**: một nền tảng giúp biến đề toán thành mô hình trực quan, lời giải có kiểm chứng và tài liệu dễ biên soạn hơn.

Dự án không chỉ nhắm đến việc “dùng AI để giải toán”, mà nhắm đến một quy trình học và dạy toán đầy đủ hơn:

```text
Đề bài → phân tích → kiểm chứng toán học → trực quan hóa → chỉnh sửa → xuất tài liệu
```

Câu chốt khi trình bày:

> Nhóm chọn đề tài này vì bài toán đến từ trải nghiệm dạy học thật: học sinh cần nhìn thấy toán học, còn giáo viên cần công cụ giúp biên soạn tài liệu nhanh nhưng vẫn giữ được độ chính xác.

## 2. Mô tả tổng quan sản phẩm

**AI Math Renderer** là nền tảng web hỗ trợ học, dạy và biên soạn tài liệu Toán học. Người dùng có thể nhập đề bằng tiếng Việt, dùng ảnh/PDF hoặc thao tác trực tiếp trong các phòng thí nghiệm toán học. Hệ thống kết hợp AI, bộ lõi toán học, công cụ dựng hình 2D/3D và các module xuất bản tài liệu.

Mục tiêu của sản phẩm là giúp người dùng:

- Hiểu bài toán trực quan hơn.
- Kiểm chứng kết quả đáng tin cậy hơn.
- Giảm thời gian dựng hình và soạn tài liệu.
- Chuyển từ đề toán tĩnh sang môi trường tương tác.

### 6 chức năng hiện có

#### 1. Render hình học 2D/3D

Chức năng render cho phép người dùng nhập đề toán bằng ngôn ngữ tự nhiên hoặc dữ liệu toán học có cấu trúc. Hệ thống phân tích đề, dựng scene toán học và hiển thị bằng renderer phù hợp.

Năng lực chính:

- Dựng hình học phẳng.
- Dựng hình học không gian.
- Hỗ trợ tọa độ Oxy, Oxyz.
- Hiển thị mô hình 3D có thể xoay, phóng to, quan sát từ nhiều góc.
- Cho phép chỉnh sửa scene sau khi dựng.

Giá trị trình bày:

> Đây là phần giúp học sinh chuyển từ “đọc đề” sang “nhìn thấy đề”.

#### 2. Analyzer khảo sát hàm số

Analyzer hỗ trợ phân tích hàm số và đồ thị. Người dùng nhập biểu thức, hệ thống xử lý, vẽ đồ thị và trả về các thông tin phục vụ khảo sát.

Năng lực chính:

- Nhập công thức toán học.
- Hỗ trợ OCR ảnh công thức.
- Vẽ đồ thị hàm số.
- Phân tích đạo hàm, cực trị, tiệm cận, bảng biến thiên và các đặc điểm quan trọng.
- Hiển thị kết quả bằng công thức toán học dễ đọc.

Giá trị trình bày:

> Analyzer giúp học sinh không chỉ thấy đồ thị, mà còn hiểu vì sao đồ thị có hình dạng đó.

#### 3. Bộ giải toán học

Bộ giải toán học xử lý các bài toán đại số và một số nhóm bài toán phổ thông theo từng bước.

Năng lực chính:

- Giải phương trình, hệ phương trình, bất phương trình.
- Phân tích biểu thức.
- Trình bày lời giải theo bước.
- Kiểm chứng kết quả bằng math core thay vì chỉ tin vào phản hồi AI.
- Hỗ trợ hiển thị công thức bằng LaTeX/KaTeX.

Giá trị trình bày:

> AI có thể diễn đạt, nhưng lõi toán học mới là nơi kiểm tra tính đúng đắn.

#### 4. PDF sang Word phục vụ biên soạn tài liệu

Chức năng PDF to Word hỗ trợ chuyển tài liệu PDF sang định dạng dễ chỉnh sửa hơn, phục vụ giáo viên, gia sư và người biên soạn đề.

Năng lực chính:

- Tải PDF lên hệ thống.
- Chọn cấu hình OCR và nhận diện công thức.
- Hỗ trợ pipeline MinerU/API xử lý tài liệu.
- Có chế độ nhận diện bảng, công thức và nội dung học thuật.
- Trả về kết quả phục vụ chỉnh sửa lại trong Word hoặc tài liệu biên soạn.

Giá trị trình bày:

> Chức năng này giải quyết nỗi đau khi convert tài liệu toán: công thức cần được giữ như công thức, không bị biến thành ký tự rời rạc khó sửa.

#### 5. GeoLab tích hợp GeoGebra API

GeoLab là phòng thí nghiệm toán học tích hợp GeoGebra API trực tiếp trong sản phẩm. Người dùng có thể thao tác với đồ thị, hình học phẳng, hình học 3D và xác suất mà không cần mở công cụ rời bên ngoài.

Năng lực chính:

- Graphing Calculator cho đồ thị 2D.
- Geometry cho hình học phẳng.
- 3D Calculator cho mặt phẳng, mặt cầu, khối đa diện, bề mặt.
- Probability cho mô phỏng xác suất.
- Hỗ trợ lệnh dựng hình và preset có sẵn.
- Có thể dùng như môi trường thử nghiệm nhanh cho giáo viên và học sinh.

Giá trị trình bày:

> GeoLab giữ sức mạnh của GeoGebra nhưng đặt vào quy trình học dễ tiếp cận hơn, có preset và giao diện định hướng sẵn.

#### 6. Simulation/Mô phỏng toán học

Module Simulation cung cấp các mô phỏng tương tác theo chủ đề, giúp học sinh quan sát sự thay đổi của tham số và hiểu bản chất khái niệm.

Năng lực chính:

- Mô phỏng diện tích giữa hai đường cong.
- Mô phỏng thể tích khối tròn xoay.
- Mô phỏng thiết diện và thể tích.
- Mô phỏng lượng giác, đạo hàm, nguyên hàm, giới hạn, dãy số, xác suất, thống kê.
- Có bước hướng dẫn, checkpoint và chế độ tự do.

Giá trị trình bày:

> Simulation biến toán học thành quá trình có thể kéo, đổi tham số, thử sai và quan sát ngay kết quả.

## 3. Điểm mới và sáng tạo

### 3.1. AI không thay thế toán học, AI chỉ là lớp ngôn ngữ

Điểm khác biệt quan trọng của dự án là nhóm không đặt AI ở vị trí “nguồn chân lý”. AI chủ yếu đóng vai trò lớp NLP:

- Hiểu đề bài tiếng Việt.
- Chuyển yêu cầu tự nhiên thành cấu trúc máy có thể xử lý.
- Diễn đạt lời giải hoặc phản hồi theo ngôn ngữ dễ hiểu.

Sau đó, dữ liệu đầu vào được đưa qua **math core** để validate:

```text
Ngôn ngữ tự nhiên → AI/NLP → dữ liệu có cấu trúc → math core validate → render/solve/analyze
```

Cách làm này giảm rủi ro thường thấy ở các sản phẩm AI thuần túy: trả lời nghe hợp lý nhưng sai toán.

Câu chốt khi trình bày:

> AI trong dự án không được dùng như người phán quyết đúng sai. AI là lớp giao tiếp, còn kiểm chứng thuộc về lõi toán học.

### 3.2. Kết nối các điểm thiếu của công cụ hiện có

Các công cụ hiện nay mạnh nhưng thường bị rời rạc:

- AI chatbot dễ dùng nhưng không đảm bảo độ tin cậy toán học.
- GeoGebra rất mạnh nhưng người mới có thể khó tiếp cận, nhất là khi chưa quen cú pháp và công cụ.
- Công cụ convert PDF sang Word thường chưa tối ưu cho tài liệu toán học, dễ làm hỏng công thức.
- Công cụ vẽ hình, giải toán, khảo sát hàm và xuất tài liệu thường nằm ở nhiều nơi khác nhau.
- Nền tảng nội dung học tập thường đưa lời giải tĩnh, ít tương tác và khó cá nhân hóa theo đề người học đang có.

AI Math Renderer kết nối các phần đó vào một luồng thống nhất:

```text
Nhập đề/OCR/PDF → phân tích toán → dựng hình/giải/analyze → mô phỏng → xuất tài liệu
```

Điểm mới không chỉ nằm ở từng chức năng riêng lẻ, mà nằm ở cách ghép chúng thành một workflow phục vụ học và dạy thật.

### 3.3. Tập trung vào trực quan hóa có kiểm chứng

Sản phẩm không dừng ở việc đưa ra đáp án. Mục tiêu là giúp người dùng kiểm chứng bằng hình ảnh và thao tác:

- Học sinh xoay mô hình 3D để hiểu quan hệ không gian.
- Giáo viên dựng hình nhanh từ đề tiếng Việt.
- Người học thay đổi tham số trong mô phỏng để thấy bản chất thay vì học thuộc.
- Kết quả được biểu diễn bằng công thức, đồ thị và mô hình tương tác cùng lúc.

### 3.4. Một sản phẩm cho cả học, dạy và biên soạn

Nhiều sản phẩm chỉ phục vụ một nhóm người dùng. Dự án này kết nối ba nhu cầu:

- Học sinh: hiểu bài và tự kiểm chứng.
- Giáo viên/gia sư: chuẩn bị bài giảng, hình vẽ, ví dụ minh họa.
- Người biên soạn tài liệu: chuyển đổi, chỉnh sửa và xuất bản nội dung toán học.

Điểm sáng tạo nằm ở việc nhìn toán học như một quy trình làm việc liên tục, không phải một tác vụ đơn lẻ.

### 3.5. Thiết kế mở rộng được bằng API và module

Sản phẩm đã có nhiều module độc lập: render, analyzer, solver, simulation, GeoLab, PDF to Word. Cách chia này giúp dự án không bị đóng khung ở một tính năng duy nhất.

Trong tương lai, nhóm có thể mở rộng thêm:

- Nhiều dạng bài toán hơn.
- Nhiều renderer hơn.
- Nhiều provider AI hơn.
- API cho giáo viên hoặc nền tảng học tập khác tích hợp.
- Bộ dữ liệu bài học và mô phỏng theo chương trình phổ thông.

## 4. Hiện trạng sản phẩm

Ở thời điểm hiện tại, AI Math Renderer đã là một sản phẩm web có nhiều chức năng hoạt động được, không chỉ là bản demo giao diện.

### Đã có

- Frontend web React/Vite.
- Backend FastAPI.
- Nhập đề toán bằng văn bản và ảnh/OCR.
- Render hình học 2D/3D.
- Chỉnh sửa scene sau khi dựng.
- Analyzer khảo sát hàm số.
- Bộ giải toán học theo bước.
- Thư viện Simulation tương tác.
- GeoLab tích hợp GeoGebra API.
- PDF to Word qua pipeline MinerU/API.
- Xuất tài liệu/hình vẽ ở nhiều định dạng.
- Hệ thống tài khoản, lịch sử dựng hình, cấu hình người dùng.
- Hỗ trợ nhiều AI provider.

### Mức độ sẵn sàng

Sản phẩm hiện phù hợp để:

- Demo trực tiếp các luồng học toán.
- Thử nghiệm với học sinh/gia sư/giáo viên.
- Thu thập phản hồi thực tế.
- Mở rộng thành nền tảng hỗ trợ biên soạn tài liệu và học toán trực quan.

### Giới hạn hiện tại

Nhóm cũng xác định rõ một số giới hạn cần tiếp tục cải thiện:

- Chưa thể bao phủ toàn bộ mọi dạng bài toán phổ thông.
- OCR và PDF conversion vẫn phụ thuộc chất lượng tài liệu đầu vào.
- Một số bài toán hình học phức tạp cần bổ sung luật kiểm chứng chuyên sâu hơn.
- Trải nghiệm người mới cần thêm hướng dẫn và ví dụ theo từng chương học.
- Cần kiểm thử thực tế với nhiều học sinh và giáo viên hơn để tối ưu luồng sử dụng.

Câu chốt khi trình bày:

> Hiện trạng của dự án là một nền tảng đã có lõi chức năng, có thể demo và thử nghiệm thật; phần tiếp theo là mở rộng độ phủ bài toán, tăng độ tin cậy và hoàn thiện trải nghiệm người dùng.

## 5. Lộ trình phát triển sau cuộc thi

### Giai đoạn 1: Hoàn thiện độ ổn định và trải nghiệm người dùng

Mục tiêu: biến sản phẩm từ bản có thể demo thành bản có thể dùng thường xuyên.

Việc cần làm:

- Tối ưu giao diện cho học sinh và giáo viên mới dùng lần đầu.
- Thêm hướng dẫn theo từng luồng: dựng hình, khảo sát hàm, PDF to Word, GeoLab.
- Tăng số ví dụ mẫu theo chương trình lớp 11 và lớp 12.
- Cải thiện thông báo lỗi khi đề nhập chưa rõ hoặc OCR nhận sai.
- Bổ sung kiểm thử cho các dạng bài phổ biến.

Kết quả kỳ vọng:

> Người dùng mới có thể tự dùng sản phẩm mà không cần nhóm hướng dẫn trực tiếp.

### Giai đoạn 2: Mở rộng math core và thư viện bài toán

Mục tiêu: tăng độ tin cậy và độ phủ toán học.

Việc cần làm:

- Bổ sung luật kiểm chứng cho hình học không gian.
- Mở rộng solver cho các chuyên đề lớp 11, 12.
- Chuẩn hóa output lời giải theo phong cách sư phạm.
- Tạo thư viện bài toán mẫu có phân loại theo lớp, chương, mức độ.
- Thêm benchmark để đo độ đúng của render/analyzer/solver.

Kết quả kỳ vọng:

> Sản phẩm không chỉ dựng được hình đẹp, mà còn kiểm chứng được nhiều quan hệ toán học hơn.

### Giai đoạn 3: Phục vụ giáo viên và biên soạn tài liệu

Mục tiêu: biến sản phẩm thành công cụ soạn bài thực tế.

Việc cần làm:

- Cải thiện PDF to Word cho tài liệu toán nhiều công thức.
- Xuất bài giảng theo template Word/LaTeX/HTML.
- Tạo bộ công cụ lưu, chỉnh sửa và tái sử dụng hình vẽ.
- Hỗ trợ xuất worksheet, đề kiểm tra, lời giải và hình minh họa.
- Cho phép giáo viên tạo bộ sưu tập bài học riêng.

Kết quả kỳ vọng:

> Giáo viên có thể dùng sản phẩm để giảm thời gian soạn tài liệu, không chỉ dùng để demo trên lớp.

### Giai đoạn 4: Mở API và hợp tác tích hợp

Mục tiêu: đưa sản phẩm ra khỏi phạm vi một website đơn lẻ.

Việc cần làm:

- Chuẩn hóa API render/analyze/solve cho hệ thống bên ngoài.
- Tạo tài liệu API cho đối tác giáo dục.
- Hỗ trợ nhúng mô hình hoặc mô phỏng vào LMS, website học tập hoặc bài giảng số.
- Tích hợp sâu hơn với GeoGebra, storage và các AI provider.
- Xây dựng cơ chế quản trị, giới hạn lượt dùng và theo dõi chất lượng.

Kết quả kỳ vọng:

> AI Math Renderer có thể trở thành hạ tầng trực quan hóa toán học cho nhiều nền tảng giáo dục khác.

### Giai đoạn 5: Cá nhân hóa học tập

Mục tiêu: giúp học sinh học theo năng lực thật của mình.

Việc cần làm:

- Lưu hồ sơ học tập và lịch sử lỗi sai.
- Gợi ý bài tập tương tự dựa trên điểm yếu.
- Sinh mô phỏng theo dạng bài học sinh đang gặp khó.
- Tạo chế độ luyện tập có phản hồi từng bước.
- Phân tích tiến bộ theo thời gian.

Kết quả kỳ vọng:

> Sản phẩm không chỉ trả lời câu hỏi, mà còn đồng hành với quá trình học toán dài hạn.

## 6. Thông điệp kết luận

AI Math Renderer được xây dựng từ một vấn đề thật trong dạy và học Toán: toán học khó không chỉ vì công thức, mà vì người học thiếu công cụ để nhìn thấy và tương tác với đối tượng toán học.

Điểm khác biệt của dự án nằm ở ba yếu tố:

1. **Trực quan hóa:** biến đề toán thành hình ảnh, mô hình và mô phỏng tương tác.
2. **Kiểm chứng:** AI chỉ xử lý ngôn ngữ, còn math core chịu trách nhiệm kiểm tra cấu trúc toán học.
3. **Workflow đầy đủ:** từ nhập đề, giải, phân tích, dựng hình đến xuất tài liệu.

Câu kết gợi ý:

> Nhóm không muốn tạo thêm một chatbot giải toán. Nhóm muốn xây dựng một không gian toán học nơi học sinh có thể nhìn thấy, giáo viên có thể giảng dễ hơn, và tài liệu toán học có thể được biên soạn nhanh nhưng vẫn chính xác.

## 7. Gợi ý chia slide

1. Vấn đề thực tế từ quá trình gia sư.
2. Nỗi đau của học sinh: khó hình dung hình học không gian.
3. Nỗi đau của giáo viên: dựng hình và convert tài liệu toán.
4. Tổng quan AI Math Renderer.
5. 6 chức năng chính.
6. Demo workflow: nhập đề → validate → render/analyze/solve.
7. Điểm mới: AI là lớp NLP, math core kiểm chứng.
8. So sánh với AI chatbot, GeoGebra, công cụ convert tài liệu.
9. Hiện trạng sản phẩm.
10. Lộ trình phát triển sau cuộc thi.
11. Tầm nhìn và lời kết.