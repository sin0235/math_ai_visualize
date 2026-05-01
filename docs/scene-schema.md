# Scene schema

Scene JSON là định dạng trung gian giữa AI extractor và renderer.

## Trường chính

- `problem_text`: đề bài gốc, tối đa 20.000 ký tự.
- `grade`: lớp 10, 11, 12 hoặc `null`.
- `topic`: `coordinate_2d`, `function_graph`, `conic`, `vector_2d`, `solid_geometry`, `coordinate_3d`, hoặc `unknown`.
- `renderer`: `geogebra_2d`, `geogebra_3d`, hoặc `threejs_3d`.
- `objects`: danh sách đối tượng toán học.
- `relations`: quan hệ như vuông góc, song song, bằng nhau, trung điểm, thuộc mặt phẳng.
- `annotations`: nhãn/highlight bổ sung.
- `view`: cấu hình view 2D/3D.

## Object types hiện hỗ trợ

- `point_2d`: `name`, `x`, `y`.
- `point_3d`: `name`, `x`, `y`, `z`.
- `segment`: `name`, `points`, `hidden`, `color`, `line_width`, `style` (`solid`, `dashed`, `dotted`).
- `line_2d`: `name`, `through`.
- `line_3d`: `name`, `through`, `color`.
- `vector_2d`: `name`, `from_point`, `to_point`.
- `vector_3d`: `name`, `from_point`, `to_point`, `color`.
- `circle_2d`: `name`, `center`, `through` hoặc `radius`.
- `function_graph`: `name`, `expression`.
- `face`: `name`, `points`, `color`, `opacity`.
- `sphere`: `name`, `center`, `radius`, `color`, `opacity`.
- `plane`: `name`, `points`, `color`, `opacity`, `show_normal`.

## Annotation contract

- `length`: target dạng `A-B`, label hiển thị độ dài.
- `angle`: target là đỉnh, ví dụ `B`; `metadata.arms = ["A", "C"]`.
- `right_angle`: target là đỉnh; `metadata.arms = ["A", "C"]`.
- `equal_marks`: target dạng `A-B`; `metadata.group` dùng để nhóm các đoạn bằng nhau.
- `coordinate_label`: target là tên điểm.

Backend có normalize một số dạng phổ biến, ví dụ angle target `ABC` có thể chuyển thành target `B` kèm arms `A`, `C`.

## Renderer payload

- GeoGebra: backend tạo `geogebra_commands` từ scene đã validate.
- Three.js: backend tạo `three_scene` gồm `points`, `segments`, `faces`, `spheres`, `lines`, `vectors`, `planes`, `computed`, `view`.

`three_scene.computed` có thể gồm:

- `intersections`: giao tuyến/giao điểm với status như `intersect`, `parallel`, `coincident`, `skew`, `line_in_plane`, `degenerate`.
- `vectors`: vector phụ trợ, ví dụ pháp tuyến mặt phẳng khi `show_normal=true`.
- `measurements`: đo đạc như quan hệ mặt cầu-mặt phẳng.
- `warnings`: cảnh báo hình học suy biến hoặc thiếu dữ liệu.

## Runtime settings và giới hạn request

- `RenderRequest.problem_text`: tối đa 20.000 ký tự.
- `OcrRequest.image_data_url`: tối đa 12.000.000 ký tự; ảnh decode tối đa 8MB.
- Runtime provider fields có giới hạn độ dài: API key 4096, base URL 2048, model id 512.
- API key override từ frontend chỉ giữ trong phiên/tab hiện tại và không persist vào `localStorage` mặc định. Cấu hình lâu dài nên đặt trong backend `.env`.
