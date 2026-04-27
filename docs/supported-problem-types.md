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

## Chưa làm trong giai đoạn này

- Database/lịch sử dựng hình.
- OCR ảnh đề bài qua vision model.
- Conic đầy đủ, lượng giác nâng cao, mặt phẳng/mặt cầu Oxyz đầy đủ.
- Giải thích từng bước và highlight theo lời giải.
