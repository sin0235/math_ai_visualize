# Thiết kế phục hồi fidelity và topology cho Scene v3

Ngày: 2026-07-14

## 1. Bối cảnh và nguyên nhân

Prompt Scene v2 đã được cải thiện qua các commit `f357a49`, `74ff050` và `00a3c8e` với quy tắc đầy đủ về tọa độ, topology, cạnh thật/cạnh phụ, màu mặt, annotation, khối tròn xoay, thiết diện và self-check. Khi chuyển sang Scene v3 native tại `80b68ee`, prompt mới giữ contract ID/typed operands nhưng chỉ còn một ví dụ 2D tối thiểu. Phần lớn quy tắc fidelity của v2 không được chuyển sang contract v3.

Hệ quả quan sát được:

- khối hộp có thể chỉ chứa các point dù JSON vẫn đúng schema;
- cạnh và mặt không được tạo đầy đủ;
- nhiều mặt dùng cùng màu mặc định;
- model tham chiếu segment chưa khai báo;
- scene đúng schema nhưng chất lượng hiển thị thấp vẫn vượt qua extraction.

## 2. Mục tiêu

- Chuyển các quy tắc fidelity có giá trị từ prompt v2 sang Scene v3 bằng stable ID và typed references.
- Bảo đảm khối chuẩn có topology hiển thị đầy đủ: point, cạnh và mặt.
- Phối màu mặt kề nhau đủ khác biệt, cạnh chính rõ, đường phụ có style riêng.
- Tự hoàn thiện topology chỉ khi có thể suy ra chắc chắn.
- Từ chối candidate và fallback khi scene thiếu topology nhưng không đủ căn cứ sửa.
- Giữ validation reference và geometry fail-closed; không bịa dữ kiện toán học.

## 3. Phạm vi

### Trong phạm vi

- Prompt extraction v3 và repair v3.
- Quy tắc fidelity dùng chung, viết theo schema v3.
- Topology completion cho hình hộp, lăng trụ, hình chóp và tứ diện.
- Quality gate trước khi chấp nhận candidate model.
- Chuẩn hóa màu/style cho object hiển thị do AI sinh.
- Regression test prompt, topology, quality gate và fallback.

### Ngoài phạm vi

- Thay đổi schema hoặc public API Scene v3.
- Thay renderer/frontend.
- Tự suy diễn quan hệ, số đo hoặc tọa độ mới từ văn bản mơ hồ.
- Tự sửa object do người dùng tạo hoặc chỉnh sửa.
- Sinh topology cho khối bất kỳ không thuộc tập chuẩn nêu trên.

## 4. Kiến trúc

```text
problem_text + NLP hints + reasoning plan
    |
    v
Scene v3 fidelity prompt
    |
    v
raw normalization + safe pre-validation topology repair
    |
    v
schema/reference validation
    |
    v
StandardSolidTopologyCompleter
    |-- topology xác định được: thêm segment/face còn thiếu
    |-- topology mơ hồ: không sửa
    v
SceneFidelityGate
    |-- đạt: geometry pipeline -> projection -> render
    |-- không đạt: candidate failure -> model fallback
```

### 4.1. Prompt fidelity v3

Prompt v3 được tổ chức thành các phần rõ ràng thay vì sao chép nguyên khối prompt v2:

1. Contract object và typed reference v3.
2. Quy tắc tọa độ và dữ kiện symbolic.
3. Quy tắc topology theo loại hình.
4. Quy tắc cạnh, mặt, màu và style.
5. Quy tắc annotation và provenance.
6. Reference integrity.
7. Self-check trước khi xuất JSON.
8. Ví dụ v3 hoàn chỉnh cho ít nhất một khối hộp 3D.

Đối với khối đa diện, prompt phải yêu cầu:

- khai báo mọi đỉnh trước;
- tạo object `segment` cho mọi cạnh thật;
- tạo object `face` cho mọi mặt hữu hạn;
- không coi danh sách point là một khối hoàn chỉnh;
- cạnh thật của khối 3D dùng `hidden=false`, `style="solid"`;
- chỉ đường phụ trợ dùng `dashed` hoặc `dotted`;
- mặt kề nhau dùng màu khác nhau từ palette ổn định;
- relation chỉ tham chiếu segment/face/plane object đã tồn tại.

### 4.2. StandardSolidTopologyCompleter

Tạo module nội bộ có interface tương đương:

```python
complete_standard_solid_topology(scene: MathSceneV3) -> TopologyCompletionResult
```

Module có hai entry point dùng chung một topology registry:

- pre-validation repair nhận raw dict, chỉ tạo segment bị relation tham chiếu thiếu khi ID/label hai đầu mút ánh xạ duy nhất vào một cạnh chuẩn;
- post-validation completion nhận `MathSceneV3`, bổ sung toàn bộ segment/face hiển thị còn thiếu.

Registry nhận diện ký hiệu khối chuẩn từ `problem_text` và đối chiếu với label point duy nhất trong scene. Chỉ khi toàn bộ đỉnh bắt buộc tồn tại và mapping không mơ hồ, module mới tạo object còn thiếu.

Topology hỗ trợ đợt đầu:

- hình hộp `ABCD.A'B'C'D'` hoặc `ABCD.EFGH`: 12 cạnh, 6 mặt;
- lăng trụ tam giác/tứ giác: cạnh hai đáy, cạnh bên và các mặt bên;
- hình chóp `S.ABC...`: cạnh đáy, cạnh bên, mặt đáy và các mặt bên;
- tứ diện `ABCD`: 6 cạnh, 4 mặt tam giác.

Quy tắc an toàn:

- Không thay đổi tọa độ point.
- Không tạo relation hoặc annotation.
- Không ghi đè object cùng ID.
- Không sửa object có `source=user_created`, `user_edited=true` hoặc `locked=true`.
- Object bổ sung có `source=construction` và metadata chỉ rõ topology rule.
- Hàm idempotent: chạy lần hai không tạo thêm object.
- Segment bị relation tham chiếu nhưng chưa tồn tại chỉ được tạo khi hai đầu mút và cạnh đó thuộc topology chuẩn đã xác nhận.

### 4.3. Màu và style

Palette mặt ổn định:

- `#5da9ff`
- `#ffb86b`
- `#ffd166`
- `#c9a0dc`
- `#7fcdbb`
- `#a8edea`

Face mới được gán màu theo thứ tự topology để các mặt kề nhau không trùng màu. Với face AI sinh không có màu tường minh và tất cả rơi về màu mặc định, normalization gán palette theo index. Không đổi màu object do người dùng tạo/chỉnh sửa.

Cạnh thật dùng màu `#1d3557`, độ rộng mặc định rõ ràng và style `solid`. Đường phụ giữ style do model chỉ định nếu hợp lệ.

### 4.4. SceneFidelityGate

Quality gate chạy sau completion và trước khi candidate được chấp nhận. Gate phát issue có cấu trúc, không âm thầm bỏ object.

Các kiểm tra chính:

- khối chuẩn có đủ số đỉnh, cạnh và mặt mong đợi;
- mọi cạnh/mặt tham chiếu point tồn tại;
- không có cạnh trùng endpoint hoặc face trùng tập đỉnh;
- scene 3D không chỉ có point khi đề yêu cầu khối;
- mặt của khối không toàn bộ cùng màu mặc định;
- renderer và dimension tương thích.

Issue retryable như `SOLID_TOPOLOGY_INCOMPLETE` hoặc `SOLID_APPEARANCE_INCOMPLETE` được xem là candidate failure để extractor thử model kế tiếp. Validation schema/reference hiện tại vẫn chạy độc lập và nghiêm ngặt.

## 5. Data flow và xử lý lỗi

1. Provider trả JSON.
2. Raw normalizer xử lý sai lệch shape có thể sửa mà không đổi nghĩa, như scalar trong `interpretation.values` và màu face bị bỏ trống.
3. Pre-validation topology repair chỉ bổ sung segment bị tham chiếu thiếu khi cạnh đó thuộc topology chuẩn đã xác nhận.
4. Pydantic bảo vệ schema và reference integrity.
5. Post-validation topology completer bổ sung object hiển thị xác định được.
6. Fidelity gate kiểm tra độ đầy đủ.
7. Geometry pipeline xác minh relation và projection.

Missing reference không thỏa quy tắc pre-validation repair tiếp tục fail và fallback. Không bắt `ValidationError` rồi bỏ relation để làm scene hợp lệ.

Mọi lỗi provider parse phải giữ nguyên nguyên nhân gốc; logging không được tạo `NameError` hoặc che lỗi JSON thật.

## 6. Kiểm thử

### Unit

- Prompt v3 chứa invariant về cạnh, mặt, màu, style và self-check.
- Hình hộp chỉ có 8 point được bổ sung đúng 12 segment và 6 face.
- Lăng trụ, hình chóp và tứ diện có topology đúng.
- Completion idempotent.
- Không sửa scene mơ hồ hoặc object do người dùng chỉnh sửa.
- Face được phân palette ổn định.
- Scalar `interpretation.values` được bảo toàn dưới dạng object.

### Integration

- Candidate thiếu topology nhưng đủ dữ kiện được completion rồi project thành công.
- Candidate thiếu topology và mơ hồ bị gate từ chối, extractor thử candidate kế tiếp.
- Relation tham chiếu segment chuẩn chưa khai báo được sửa an toàn.
- Missing reference không thuộc topology chuẩn vẫn fail-closed.
- Parse error của OpenRouter và 9router được log mà không phát sinh lỗi thứ cấp.

### Regression corpus

Ít nhất gồm:

- hình hộp chữ nhật;
- hình lập phương;
- lăng trụ tam giác;
- hình chóp đáy vuông;
- tứ diện đều;
- một scene mơ hồ không được tự hoàn thiện;
- một bài thiết diện để bảo đảm màu/viền không giảm so với prompt v2.

## 7. Rollout và quan sát

- Gỡ fallback `router9::cx/gpt-5.3-codex` khỏi profile `render_tier2` production vì tài khoản hiện tại không hỗ trợ model này.
- Giữ thứ tự model còn lại.
- Theo dõi candidate attempt, issue fidelity và thời gian render sau deploy.
- Không giảm validation để tăng tỷ lệ thành công.
- Nếu completion tạo sai topology trong corpus hoặc production, tắt riêng rule tương ứng; prompt và quality gate vẫn hoạt động.

## 8. Tiêu chí hoàn thành

- Prompt v3 khôi phục các invariant fidelity quan trọng của v2 theo contract v3.
- Khối hộp chuẩn không còn scene chỉ có point.
- Face của khối chuẩn có nhiều màu phân biệt.
- Topology mơ hồ không bị tự đoán.
- Regression test và backend suite liên quan qua.
- Production không còn thử model `cx/gpt-5.3-codex` không tương thích.
- Log parse không còn lỗi `log_provider_parse_error` chưa định nghĩa.
