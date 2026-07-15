# Thiết kế hardening contract Scene v3 cho model 9router `cx/gpt-*`

## 1. Mục tiêu

Loại bỏ lỗi Scene v3 do output LLM dùng tên field hoặc shape gần đúng nhưng không khớp `MathSceneV3`, đồng thời giữ nguyên cơ chế fail-closed cho dữ liệu sai hình học.

Thay đổi không được:

- Chuyển Pydantic sang `extra="ignore"`.
- Xóa field lạ một cách tổng quát để làm validation pass.
- Nuốt conflict giữa hai field có cùng ý nghĩa.
- Hạ mức kiểm tra reference, topology, metric hoặc fidelity.
- Sửa `.env`, allowlist hoặc task profile trong D1.

## 2. Bằng chứng baseline live

Kiểm chứng ngày 2026-07-15 bằng `.env` hiện tại, qua endpoint 9router thật:

| Model | Case 2D | Case 3D | Lỗi chính |
|---|---|---|---|
| `cx/gpt-5.6-luna` | Pass | Fail | `relations[].provenance`; `derived_facts` sai shape |
| `cx/gpt-5.5` | Pass | Fail | `derived_facts` thiếu `kind`/`provenance`, dùng `text`/`source`/`object_ids` |

Các log production còn cho thấy:

- `annotations[].provenance="construction"` không thuộc enum hiện tại.
- `annotations[].render_only` là field thừa.
- `line_2d` thường nhận `hidden`, `color`, `line_width`, `style`, trong khi contract object chưa hỗ trợ dù projection đã có các thuộc tính style tương ứng.
- Một số model dùng relation `line_through_points` với một linear object và hai point; relation registry trước đây chưa có contract/verifier tương ứng.

HTTP và JSON parsing đều thành công; lỗi nằm tại boundary chuyển JSON LLM sang `MathSceneV3`.

## 3. Nguồn chân lý

- `MathSceneV3` và các model con là contract runtime duy nhất.
- Prompt phải mô tả đúng contract này, không dùng khái niệm chung chung khác tên field.
- Compatibility normalizer chỉ nhận các alias có ánh xạ ngữ nghĩa xác định.
- Sau normalize, toàn bộ payload vẫn phải qua Pydantic, repair reference có kiểm soát, geometry kernel và fidelity validation hiện có.

## 4. Thiết kế thay đổi

### 4.1. Làm đầy đủ prompt contract

Prompt Scene v3 phải bổ sung signature JSON chính xác cho:

- Mọi object type, gồm field style được hỗ trợ thực sự.
- `RelationV3`: `id`, `type`, `operands`, `args`, `source`, `verification`, `metadata`; cấm `provenance`.
- `AnnotationV3`: chỉ dùng provenance `given`, `verified`, `computed`, `render_only`.
- `DerivedFactV3`: `id`, `kind`, `source_ids`, `value`, `provenance`, `relation_id`.
- `ParameterV3`, `ConstructionStepV3`, `InterpretationV3` và `AuditV3`.

Quy tắc provenance phải nói theo từng collection, không yêu cầu chung “gắn provenance cho mọi dữ kiện”. Construction chỉ dùng `source="construction"` trên object/relation; annotation phục vụ dựng hình dùng `provenance="render_only"`.

### 4.2. Compatibility normalizer tường minh

Normalizer xử lý trước Pydantic và chỉ áp dụng các trường hợp sau.

**Relation**

- Nếu chỉ có `provenance`, đổi sang `source` theo bảng:
  - `given` → `given`
  - `construction` hoặc `render_only` → `construction`
  - `inferred`, `ai_inferred`, `computed`, `verified` → `ai_inferred`
- Nếu có cả `source` và `provenance`, chỉ bỏ alias khi hai giá trị tương đương.
- Nếu conflict hoặc giá trị không biết, raise lỗi có đường dẫn relation rõ ràng.

**Annotation**

- `provenance="construction"` hoặc `"ai_inferred"` → `render_only`; không nâng thành fact đã kiểm chứng.
- `render_only=true` → `provenance="render_only"` khi không conflict.
- `render_only=false` không được tự suy diễn provenance; nếu thiếu provenance hợp lệ thì giữ lỗi.

**Derived fact dạng gần đúng**

- `object_ids` → `source_ids`.
- `statement` hoặc `text` → `value.text`.
- `source` được chuẩn hóa vào `provenance`: `given` → `given`, `verified` → `verified`, `computed`/`inferred`/`ai_inferred` → `computed`, `construction`/`render_only` → `render_only`.
- Chỉ suy ra `kind="annotation"` khi payload có fact dạng văn bản; không suy đoán measurement/intersection.
- Conflict, field không có ánh xạ hoặc derived fact không đủ nội dung vẫn fail.

Mỗi lần compatibility normalization phải ghi structured warning bằng mã ổn định và path, không ghi raw đề hoặc raw response. Nhờ đó hệ thống hoạt động nhưng contract drift không bị che giấu.

### 4.3. Đồng bộ style object với projection

Các thuộc tính `hidden`, `color`, `line_width`, `style` là intent hiển thị hợp lệ cho linear object và projection đã có contract tương ứng. Thay vì xóa chúng:

- Mở rộng line/vector schema ở backend theo cùng giới hạn đang dùng cho segment.
- Truyền field qua `build_render_projection_v3`.
- Đồng bộ type frontend.
- Không thêm field style cho point, face hoặc object không có renderer support.

### 4.4. Error handling

- Lỗi compatibility không xác định phải giữ nguyên fail-closed và kích hoạt model fallback hiện tại.
- Error message phải rút gọn theo collection/path/mã lỗi; không dump toàn bộ 10-30 Pydantic error vào log một dòng.
- Provider/model log phải giữ đúng model thay vì `model=<unknown>` tại bước parse summary khi context đã có model.

## 5. Kiểm thử

### 5.1. Regression test bắt buộc

Thêm fixture tối thiểu từ các failure đã quan sát:

- Luna relation dùng `provenance`.
- Luna derived fact dùng `statement`, `object_ids`, provenance `inferred`.
- GPT-5.5 derived fact dùng `text`, `source`, `object_ids` và thiếu `kind`.
- Annotation `construction` và `render_only=true`.
- Line 2D có đầy đủ style.
- Conflict `source`/`provenance` phải fail.
- Alias không biết phải fail.
- Payload sau normalize vẫn fail nếu reference hoặc geometry sai.

### 5.2. Kiểm tra local

- Unit test `test_extractor_v3.py` và projection/type liên quan.
- Test prompt contract.
- Toàn bộ backend test module Scene v3 bị ảnh hưởng.
- Frontend type-check/build nếu type object thay đổi.
- `git diff --check`.

### 5.3. Ma trận live 9router

Thứ tự rollout:

1. Chạy lại hai case 2D/3D với `cx/gpt-5.6-luna` và `cx/gpt-5.5`.
2. Khi hai model này pass schema và fidelity, quét danh sách `/models` live và chạy cùng ma trận cho mọi model có prefix `cx/gpt-`.
3. Phân loại riêng: request/timeout, invalid JSON, compatibility normalization, schema, reference, geometry/fidelity.

Live test không đưa vào CI vì phụ thuộc quota và mạng. Các payload lỗi tối thiểu thu được sẽ thành regression test deterministic trong CI.

### 5.4. Ma trận provider kiểm chứng sau triển khai

Với cùng một case 2D và một case 3D:

| Provider/model | 2D | 3D | Kết quả |
|---|---|---|---|
| 9router `kr/claude-haiku-4.5` | verified | verified | Đạt |
| Ollama `gpt-oss:120b` | verified | verified | Đạt |
| NVIDIA `openai/gpt-oss-120b` | security/JSON fail | JSON/security fail | Giữ fail-closed |
| OpenRouter `openai/gpt-oss-120b` | verified | security leak | Giữ fail-closed |
| OpenCode `oc/deepseek-v4-flash-free` | verified | gateway 524 | Lỗi hạ tầng, không nuốt |

NVIDIA GPT-OSS được gửi `reasoning_effort=low` mặc định để tránh dùng hết token cho reasoning trước JSON; điều này không tắt security gate và không biến model chưa đạt thành pass.

## 6. Definition of Done

- Hai model ưu tiên pass cả case 2D và 3D qua `parse_math_scene_v3` và pipeline fidelity.
- Không còn failure từ các alias/shape đã liệt kê.
- Không dùng generic extra stripping hoặc `extra="ignore"`.
- Conflict và dữ liệu sai hình học vẫn fail rõ ràng.
- Structured warning cho mọi compatibility normalization.
- Unit test, backend test liên quan, frontend build/type-check và diff check đều pass.
- Có báo cáo ma trận live cho toàn bộ model `cx/gpt-*` hiện diện tại thời điểm test.
