# Scene schema

Scene JSON là định dạng trung gian giữa AI extractor và renderer.

## Trường chính

- `problem_text`: đề bài gốc.
- `grade`: lớp 10, 11, 12 hoặc `null`.
- `topic`: dạng toán, ví dụ `coordinate_2d`, `function_graph`, `solid_geometry`.
- `renderer`: `geogebra_2d`, `geogebra_3d`, hoặc `threejs_3d`.
- `objects`: danh sách đối tượng toán học.
- `relations`: quan hệ như vuông góc, song song, thuộc mặt phẳng.
- `annotations`: nhãn/highlight bổ sung.
- `view`: cấu hình view 2D/3D.

## Object types MVP

- `point_2d`
- `point_3d`
- `segment`
- `line_2d`
- `vector_2d`
- `circle_2d`
- `function_graph`
- `face`

## Renderer payload

- GeoGebra: backend tạo `geogebra_commands` từ scene đã validate.
- Three.js: backend tạo `three_scene` gồm `points`, `segments`, `faces`, `view`.
