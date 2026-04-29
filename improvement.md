1. Tổng quan hiện tại
Ứng dụng là một công cụ AI hỗ trợ dựng hình toán học từ văn bản, render bằng GeoGebra hoặc Three.js. Bố cục gồm 2 cột: cột trái là form nhập liệu, cột phải là vùng hiển thị hình + Scene JSON.

2. Phân tích chi tiết từng phần
2.1. Header / Tiêu đề trang
Vị trí	Nội dung hiện tại	Vấn đề
Tag trên cùng	AI MATH RENDERER	Toàn chữ hoa, font nhỏ, trông như badge phụ — thiếu nổi bật
Tiêu đề chính	Dựng hình từ đề bài	Ổn, nhưng thiếu context về AI
Mô tả phụ	Nhập đề dạng văn bản để sinh scene JSON rồi render bằng GeoGebra hoặc Three.js.	Quá kỹ thuật với người dùng phổ thông — đề cập "scene JSON" không cần thiết
Đề xuất sửa:

Tag: ✦ AI · Toán học

Tiêu đề: giữ nguyên hoặc đổi thành Dựng hình toán học bằng AI

Mô tả: Nhập đề bài bằng ngôn ngữ tự nhiên — AI sẽ tự động vẽ hình minh họa.

2.2. Khu vực nhập đề bài
Vấn đề	Chi tiết
Label Nhập đề bài	Không mô tả rõ định dạng nào được hỗ trợ (2D, 3D, hàm số, hình học, ...)
Placeholder trong textarea	Nhập đề toán cần dựng hình... — ổn nhưng hơi chung chung
Không có giới hạn ký tự hiển thị	Người dùng không biết giới hạn là bao nhiêu
Textarea chiều cao cố định	Quá nhỏ khi đề bài dài (bài hình chóp 3D cần nhiều chữ)
Đề xuất:

Thêm hint nhỏ bên dưới label: Hỗ trợ hình học phẳng (2D), hàm số, hình không gian (3D)

Placeholder: Ví dụ: "Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Vẽ đường trung tuyến AM."

Thêm bộ đếm ký tự góc dưới phải textarea

Cho phép resize dọc tự do

2.3. Dropdown "Model"
Vấn đề	Chi tiết
Tên model rất kỹ thuật	NVIDIA DeepSeek V3.1 Terminus, OpenRouter GPT OSS 120B — người dùng không phân biệt được
Không có mô tả kèm theo	Không biết model nào nhanh, model nào chính xác hơn
Mock extractor xuất hiện trong danh sách	Đây là option debug/dev, không nên hiện với end-user
Đề xuất:

Đổi tên hiển thị thân thiện hơn: Tự động (Khuyến nghị), DeepSeek V3 — Nhanh, Kimi K2 — Tư duy sâu, v.v.

Thêm tooltip hoặc chú thích nhỏ bên dưới mô tả model đang chọn

Ẩn Mock extractor trong môi trường production

2.4. Phần "Cài đặt nâng cao"
Đây là phần có nhiều vấn đề nhất.

Label hiện tại	Vấn đề	Đề xuất sửa
Gán toạ độ	Mơ hồ — không rõ gán toạ độ của cái gì	Gán toạ độ điểm hoặc Chiến lược đặt toạ độ
Theo AI	Không rõ nghĩa	AI tự quyết định
Tự chọn điểm đẹp làm gốc O	Hơi lạ về mặt ngôn ngữ	Tự động chọn gốc toạ độ đẹp
Ưu tiên điểm O làm gốc	Chưa rõ "O" là điểm nào trong đề	Dùng điểm O trong đề làm gốc
Renderer	Ổn với developer, nhưng với user phổ thông nên là	Công cụ vẽ hoặc Loại đồ họa
Tự động (Renderer)	Ổn	Giữ nguyên, thêm ghi chú: (AI tự chọn 2D hoặc 3D)
Hiện toạ độ	Ổn	Có thể đổi thành Hiển thị toạ độ điểm cho rõ hơn
Hiện trục	Ngắn gọn nhưng thiếu rõ	Hiển thị trục tọa độ
Hiện lưới	Ổn	Hiển thị lưới nền
Theo scene	Rất kỹ thuật — người dùng không hiểu "scene"	Đổi thành Mặc định (AI quyết định)
Tự sinh cạnh từ các mặt	Quá technical	Tự động thêm cạnh từ các mặt phẳng
Tìm giao điểm đồ thị bằng GeoGebra	Ổn nhưng dài	Tìm giao điểm tự động (GeoGebra)
Vấn đề UX bổ sung: Cài đặt nâng cao collapsed bằng ▶ Cài đặt nâng cao — ổn cho người mới, nhưng nên thêm tooltip giải thích từng option khi hover.

2.5. Nút "Dựng hình"
Màu xanh dương nổi bật — tốt ✅

Không có icon trực quan (ví dụ: biểu tượng bút vẽ hoặc AI spark)

Không có trạng thái loading/disabled khi đang xử lý (chưa thấy trong UI tĩnh)

Đề xuất: Thêm icon ✦ hoặc ⟳ khi loading, disable nút + hiện spinner khi đang gọi API

2.6. Các nút ví dụ mẫu (Quick prompts)
3 ví dụ hiện tại khá tốt — bao phủ 2D, hàm số, 3D. Tuy nhiên:

Không có nhãn section: người dùng không biết đây là gì

Nút dài, style giống nhau hết — khó phân biệt loại bài

Đề xuất:

Thêm tiêu đề: Thử ngay với ví dụ: hoặc Đề mẫu

Thêm tag nhỏ phân loại: [2D], [Hàm số], [3D]

Thêm 1-2 ví dụ về đường tròn, tam giác

2.7. Vùng hiển thị hình (Canvas bên phải)
Placeholder text Nhập đề bài để bắt đầu dựng hình. — ổn nhưng hơi buồn tẻ

Không có hình minh họa/icon gợi ý

Đề xuất: Thêm icon hình học lớn mờ ở giữa (dạng watermark) + text gợi ý

2.8. Phần "Scene JSON"
Label Scene JSON — thuần kỹ thuật, không cần thiết với end-user

Nội dung Chưa có dữ liệu. — quá ngắn gọn

Đề xuất:

Đổi label: Dữ liệu cảnh (nâng cao) hoặc ẩn hoàn toàn sau collapse

Text trống: Chưa có dữ liệu. Hãy nhập đề bài và nhấn "Dựng hình".

Thêm nút Copy JSON và Download JSON khi có dữ liệu

3. Đề xuất chức năng mới
#	Tính năng	Mức độ ưu tiên
1	Lịch sử đề bài — lưu các lần dựng hình gần đây (localStorage)	🔴 Cao
2	Xuất hình ảnh — nút tải PNG/SVG từ canvas GeoGebra/Three.js	🔴 Cao
3	Chế độ tối (Dark mode) — phù hợp khi dùng ban đêm	🟡 Trung bình
4	Chỉnh sửa hình trực tiếp — sau khi vẽ, cho phép kéo thả điểm	🟡 Trung bình
5	Chia sẻ link — tạo URL chứa encoded đề bài để chia sẻ	🟡 Trung bình
6	Nhập bằng ảnh — chụp/upload đề toán trong sách, AI OCR rồi vẽ	🟠 Thấp
7	Giải thích bước — AI giải thích từng bước dựng hình bên cạnh canvas	🟠 Thấp
8	So sánh 2D/3D — xem song song 2 renderer	🟠 Thấp
không dùng emoij/icon, chỉ được phép sử dụng svg, lấy đen trắng làm theme chủ đạo,    
  (màu của render không ảnh hưởng do tính chất phân biệt) 