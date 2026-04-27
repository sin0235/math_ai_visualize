Dưới đây là phần **mô tả ý tưởng, mục tiêu và chức năng** cho project ứng dụng dạy toán online tự động dựng hình học không gian 3D từ đề bài.

## 1. Ý tưởng dự án

Dự án xây dựng một **ứng dụng dạy toán online** có khả năng tự động đọc đề bài hình học không gian và dựng lại hình vẽ 3D tương tác trên trình duyệt.

Người dùng có thể nhập đề bài bằng **văn bản** hoặc tải lên **hình ảnh chụp từ sách giáo khoa**. Hệ thống sẽ dùng mô hình AI để nhận diện nội dung, trích xuất các yếu tố hình học quan trọng như điểm, cạnh, mặt phẳng, quan hệ vuông góc, song song, sau đó tự động sinh hình 3D để học sinh có thể quan sát, xoay, phóng to, thu nhỏ trực tiếp trên web. Ý tưởng này dựa trên kiến trúc gồm các module như Input Handler, Structured Extractor, Code Generator, Validator/Sandbox và Renderer đã được mô tả trong tài liệu. 

## 2. Mục tiêu dự án

Mục tiêu chính của dự án là tạo ra một công cụ hỗ trợ học hình học không gian trực quan, giúp học sinh dễ hình dung các khối hình và quan hệ hình học vốn khó tưởng tượng khi chỉ nhìn đề bài hoặc hình vẽ 2D.

Cụ thể, dự án hướng đến các mục tiêu sau:

**Thứ nhất**, tự động hóa quá trình dựng hình từ đề bài toán. Thay vì giáo viên hoặc học sinh phải vẽ thủ công, hệ thống có thể tự phân tích đề và tạo hình 3D.

**Thứ hai**, hỗ trợ học sinh học hình học không gian trực quan hơn thông qua hình vẽ có thể xoay, kéo, phóng to và quan sát từ nhiều góc nhìn.

**Thứ ba**, giảm rào cản kỹ thuật cho người dùng. Học sinh chỉ cần dùng trình duyệt, không cần cài Python, Plotly hay phần mềm dựng hình.

**Thứ tư**, tạo nền tảng để mở rộng thành hệ thống dạy toán thông minh, có thể kết hợp giải thích lời giải, gợi ý từng bước, tạo bài giảng động hoặc video minh họa trong tương lai.

## 3. Chức năng chính

### 3.1. Nhập đề bài

Ứng dụng cho phép người dùng nhập đề bài theo hai cách:

Người dùng có thể gõ trực tiếp đề bài hình học không gian dưới dạng văn bản.

Người dùng cũng có thể tải lên ảnh chụp đề bài từ sách giáo khoa, tài liệu học tập hoặc đề kiểm tra. Khi đó hệ thống sử dụng OCR hoặc mô hình đa phương thức để chuyển ảnh thành văn bản.

### 3.2. Phân tích đề bài bằng AI

Sau khi có nội dung đề bài, hệ thống sẽ dùng AI để phân tích và trích xuất thông tin hình học quan trọng.

Ví dụ hệ thống cần nhận diện được:

* Loại hình: hình hộp, hình chóp, lăng trụ, mặt phẳng, tam giác, tứ diện.
* Các điểm và nhãn điểm: A, B, C, D, S, M, N.
* Các cạnh, mặt, đường thẳng, mặt phẳng.
* Quan hệ hình học: song song, vuông góc, trung điểm, giao điểm.
* Các yêu cầu đặc biệt: vẽ đường cao, mặt cắt, đường khuất, nhãn đỉnh.

Kết quả phân tích nên được chuẩn hóa thành một cấu trúc JSON để các bước sau có thể xử lý ổn định.

### 3.3. Sinh dữ liệu hoặc mã dựng hình 3D

Từ dữ liệu hình học đã trích xuất, hệ thống tự động sinh mã hoặc dữ liệu dựng hình.

Ở phiên bản ban đầu, hệ thống có thể sinh mã Python Plotly để tạo hình 3D. Plotly dùng các thành phần như `Mesh3d` để dựng khối, `Scatter3d` để vẽ điểm và đường, `Surface` để biểu diễn mặt phẳng.

Về lâu dài, nên tách phần “dữ liệu hình học” khỏi phần “render”. Khi đó backend chỉ sinh tọa độ, cạnh, mặt, nhãn và quan hệ hình học; frontend sẽ dùng Three.js hoặc React Three Fiber để hiển thị đẹp và linh hoạt hơn.

### 3.4. Kiểm tra và sửa lỗi tự động

Hệ thống cần có bước kiểm tra để đảm bảo hình dựng ra đúng với đề bài.

Chức năng kiểm tra gồm:

* Kiểm tra JSON có đủ điểm, cạnh, mặt, quan hệ hình học hay không.
* Kiểm tra mã sinh ra có lỗi cú pháp hay không.
* Chạy thử mã trong sandbox an toàn.
* Nếu có lỗi, gửi traceback hoặc lỗi logic cho AI để sửa tự động.
* Giới hạn số lần sửa để tránh vòng lặp vô hạn.

### 3.5. Hiển thị hình học 3D trên web

Sau khi dựng hình thành công, ứng dụng trả về hình 3D cho người dùng xem trực tiếp trên trình duyệt.

Người dùng có thể:

* Xoay hình bằng chuột.
* Phóng to, thu nhỏ.
* Quan sát từ nhiều góc nhìn.
* Bật/tắt nhãn điểm.
* Bật/tắt đường khuất.
* Xem các đường đặc biệt như đường cao, đường trung tuyến, giao tuyến, mặt cắt.

### 3.6. Tối ưu cho giáo dục

Vì đây là ứng dụng dạy toán, hình vẽ không chỉ cần đúng mà còn phải dễ học.

Các chức năng nên có:

* Hiển thị nhãn điểm rõ ràng.
* Phân biệt nét liền và nét đứt.
* Làm nổi bật đường cần chứng minh hoặc tính toán.
* Tô màu mặt phẳng hoặc mặt cắt.
* Có chế độ “giải thích từng bước”.
* Có thể hiển thị đề bài, hình vẽ và lời giải trong cùng một giao diện.

## 4. Định hướng phát triển

Phiên bản đầu tiên có thể dùng Flask + Python + Plotly để nhanh chóng tạo prototype.

Phiên bản nâng cao nên chuyển sang kiến trúc ổn định hơn:

* Backend: FastAPI hoặc Flask.
* AI pipeline: OCR/Vision → Structured Extractor → Geometry Engine.
* Renderer: Three.js hoặc React Three Fiber.
* Database: lưu đề bài, JSON hình học, lịch sử dựng hình.
* Frontend: giao diện học tập trực quan, thân thiện với học sinh.
* AI/LLM: OpenRouter API (Qwen2.5-VL cho OCR/vision, nvidia/llama-3.1-nemotron-ultra cho structured extraction + code gen)

## 5. Mô tả ngắn gọn để đưa vào tài liệu dự án

Dự án là một ứng dụng dạy toán online sử dụng AI để tự động phân tích đề bài hình học không gian và dựng hình 3D tương tác trên trình duyệt. Người dùng có thể nhập đề bằng văn bản hoặc hình ảnh. Hệ thống sẽ nhận diện các đối tượng hình học, trích xuất dữ liệu có cấu trúc, sinh mô hình 3D, kiểm tra lỗi và hiển thị hình vẽ trực quan. Mục tiêu của dự án là giúp học sinh dễ hình dung hình học không gian, giảm thao tác vẽ thủ công và tạo nền tảng cho các tính năng học toán thông minh như giải thích từng bước, minh họa động và bài giảng tương tác.
