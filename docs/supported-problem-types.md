# Supported problem types

## MVP hiện tại

### Toạ độ Oxy

```text
Cho A(1,2), B(4,5). Vẽ đường thẳng AB.
```

Kết quả: GeoGebra render hai điểm và đường thẳng qua hai điểm đầu tiên.

### Vector 2D

```text
Cho A(1,2), B(4,5). Vẽ vector AB.
```

Kết quả: GeoGebra render hai điểm và vector từ A đến B.

### Đường tròn

```text
Vẽ đường tròn tâm O bán kính 3.
```

Hoặc:

```text
Cho O(0,0), A(2,0). Vẽ đường tròn tâm O đi qua A.
```

Kết quả: GeoGebra render đường tròn.

### Đồ thị hàm số

```text
Vẽ đồ thị hàm số y = x^2 - 2x + 1.
```

Kết quả: GeoGebra render function graph.

### Hình chóp tứ giác

```text
Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.
```

Kết quả: Three.js render hình chóp tứ giác minh hoạ.

### Tứ diện / hình chóp tam giác

```text
Cho tứ diện S.ABC.
```

Kết quả: Three.js render tứ diện/hình chóp tam giác.

### Lăng trụ tam giác

```text
Cho lăng trụ tam giác ABC.A'B'C'.
```

Kết quả: Three.js render hai đáy tam giác và các mặt bên.

### Hình hộp chữ nhật

```text
Cho hình hộp chữ nhật ABCD.A'B'C'D'.
```

Kết quả: Three.js render hình hộp với đáy, mặt trên và mặt bên chính.

### Oxyz cơ bản

```text
Trong Oxyz cho A(1,2,3), B(4,5,6).
```

Kết quả: Three.js render các điểm 3D và đoạn nối theo thứ tự nhập.

### OCR ảnh đề bài

OCR hiện có ở mức beta qua endpoint `/api/ocr`.

- Ảnh đầu vào là data URL base64 PNG/JPEG/WebP/GIF.
- Backend giới hạn ảnh decode tối đa 8MB và schema giới hạn body data URL khoảng 12MB.
- Provider OCR chính: OpenRouter và 9router.
- Khi cấu hình fallback phù hợp, backend có thể thử model OpenRouter fallback và NVIDIA OCR fallback.
- Nếu bật 9router-only, OCR chỉ dùng 9router và không fallback sang provider khác.

### Hình học 3D mở rộng

Scene schema hiện hỗ trợ thêm `line_3d`, `plane`, `sphere`, `vector_3d`, segment ẩn/dashed/dotted, annotation độ dài/góc/vuông góc/equal marks, và computed payload cho giao tuyến/đo đạc. Mức độ đúng phụ thuộc khả năng AI sinh scene phù hợp từ đề bài.

## Chưa làm hoặc chưa đầy đủ

- Database/lịch sử dựng hình.
- Conic đầy đủ, lượng giác nâng cao, mặt phẳng/mặt cầu Oxyz ở mọi dạng đề.
- Giải thích từng bước và highlight theo lời giải.
- OCR/layout phức tạp nhiều cột hoặc ảnh chất lượng thấp chưa đảm bảo ổn định.
