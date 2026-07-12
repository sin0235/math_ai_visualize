# MC-QA-01 — Bộ kiểm thử backend

## Quan sát local

- Môi trường: Python 3.12.3, pytest 9.1.1.
- Lệnh chạy theo cấu hình CI và loại hai bộ `test_geometry_scenes_large_scale.py`, `test_math_core_large_scale.py`.
- Kết quả: **1463 passed**, 17 warnings, 177,19 giây.
- Exit code: 0.
- JUnit XML được lưu để kiểm tra máy đọc được.

## Quan sát CI production

- Workflow product tại commit `26b21f0d5ef69cb4c87c2f28bd30569f09d1a4b4` kết thúc thành công.
- Job backend dùng Python 3.11.15 và ghi nhận **1447 passed**, 9 warnings, 136,77 giây.

## Kết luận

**Đạt** đối với bộ test được thực thi ở hai phạm vi đã ghi. Số lượng local cao hơn CI vì workspace chứa thay đổi và test mới chưa commit; hai kết quả không được gộp thành một phiên bản duy nhất.