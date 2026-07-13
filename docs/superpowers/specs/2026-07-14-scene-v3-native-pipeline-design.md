# Thiết kế pipeline dựng hình Scene v3 native

Ngày: 2026-07-14

## 1. Mục tiêu

Thay luồng dựng hình `MathScene` v2 qua adapter bằng pipeline Scene v3 native. LLM giữ vai trò hiểu đề và điều phối topology; schema, relation contract và geometry kernel giữ vai trò xác minh. Loại bỏ toàn bộ Scene v2 khỏi API, frontend và downstream.

Tiêu chí chính:

- `POST /api/render/v3` không còn gọi extractor v2 hoặc `migrate_scene_v2_dict()`.
- LLM sinh `MathSceneV3` với stable ID và typed relation operands ngay từ đầu.
- NLP không ghi đè nguyên văn đề.
- Scene sai contract được LLM sửa đúng một lần rồi fail rõ nếu vẫn không hợp lệ.
- Solver, export, variants, renderer, history và commands chỉ dùng Scene v3 hoặc `RenderProjectionV3`.
- Bộ đề hồi quy chứng minh tỷ lệ dựng thành công và fidelity không giảm.

## 2. Phạm vi

### Trong phạm vi

- Native Scene v3 reasoning, extraction và repair.
- Prompt, parser và provider orchestration cho Scene v3.
- Validation, issue taxonomy và API error mapping.
- Loại toàn bộ route, schema, adapter, frontend state và test Scene v2.
- Chuyển downstream còn dùng shape legacy sang Scene v3 native.
- Reset dữ liệu development theo quy trình database setup hiện có; không cần tương thích dữ liệu Scene v2.
- Corpus hồi quy 2D/3D và kiểm tra end-to-end.

### Ngoài phạm vi

- Thay provider/model registry hiện tại.
- Cho LLM quyết định tính hợp lệ cuối cùng.
- Dựng best-effort bằng cách âm thầm bỏ object, relation hoặc annotation lỗi.
- Giữ fallback, alias hoặc adapter Scene v2.
- Migration dữ liệu production; dự án hiện ở development và chưa có dữ liệu thật cần bảo toàn.

## 3. Kiến trúc

```text
Nguyên văn đề
    |
    +-- NLP preflight
    |     Chỉ tạo hints, entities, ambiguity và telemetry
    |     Không sửa problem_text
    |
    v
LLM reasoning
    Tạo kế hoạch dựng hình typed
    |
    v
LLM Scene v3 extraction
    Sinh MathSceneV3 trực tiếp
    |
    v
Schema + relation contract + geometry verification
    |
    +-- hợp lệ --> RenderProjectionV3 --> renderer/workspace/downstream
    |
    +-- không hợp lệ --> LLM repair đúng một lần
                           |
                           +-- hợp lệ --> projection
                           +-- vẫn lỗi --> coded API error
```

### Phân quyền

- LLM: hiểu ngôn ngữ, giải quyết mơ hồ, lập construction plan, chọn object/relation/annotation/view và sinh Scene v3.
- NLP: cung cấp metadata phụ; không thay thế hiểu ngôn ngữ của LLM và không sửa nguồn.
- Pydantic schema: bảo vệ shape, type, uniqueness và reference integrity.
- Relation registry: bảo vệ operand contract.
- Geometry kernel: kiểm chứng constraint toán học.
- Projection: chuyển scene đã qua pipeline sang renderer payload.
- Renderer và downstream: không đọc raw LLM response.

## 4. Thành phần

### 4.1 Reasoning plan

Contract nội bộ typed, tối thiểu chứa:

- dimension và renderer intent;
- objects cần dựng và identity ổn định;
- relations đã cho, cần suy ra và provenance;
- construction order;
- annotations cần hiển thị;
- ambiguity còn lại;
- evidence gắn với nguyên văn đề.

Reasoning plan không phải public API và không thay Scene v3.

### 4.2 Native Scene v3 extractor

Extractor dùng model registry và provider fallback hiện tại nhưng parser trực tiếp sang `MathSceneV3`.

Input:

- nguyên văn đề;
- grade;
- NLP hints tách riêng;
- reasoning plan;
- Scene v3 schema và relation contract instructions.

Output:

- `MathSceneV3` hoàn chỉnh;
- stable IDs;
- typed operands tham chiếu object IDs;
- annotations liên kết relation/object;
- audit/provenance phù hợp schema.

Không tạo intermediate `MathScene` v2.

### 4.3 Deterministic pipeline

Thứ tự:

1. Parse JSON và validate schema.
2. Validate reference integrity.
3. Validate relation operand contracts.
4. Build geometry index.
5. Verify constraints.
6. Attach verification status.
7. Build `RenderProjectionV3`.

Mỗi lỗi mang stage, code và entity context.

### 4.4 LLM repair

Repair nhận:

- nguyên văn đề;
- reasoning plan;
- scene lỗi;
- issues có cấu trúc;
- contract liên quan tới lỗi.

Repair chỉ được sửa Scene v3. Không diễn giải lại bằng canonical text, không quay về v2, không xóa relation để làm validator xanh nếu relation có bằng chứng trong đề.

Chỉ một lượt repair. Scene sau repair chạy lại toàn bộ deterministic pipeline.

### 4.5 API và workspace

Chỉ giữ:

- `POST /api/render/v3`;
- workspace v3 create/get/confirm;
- command v3.

Xóa `/api/render`, `/api/render/jobs` và response types v2. Frontend dựng hình chỉ gọi v3 và quản lý workspace v3.

### 4.6 Downstream

- Renderer nhận `RenderProjectionV3`.
- Solver nhận committed `MathSceneV3` qua projector native có contract riêng, không qua model v2.
- Export đọc Scene v3/projection v3.
- Problem variants đọc committed Scene v3.
- History lưu Scene v3/workspace reference.
- Commands sửa Scene v3 và chạy lại deterministic pipeline.

Sau khi mọi caller đã chuyển, xóa schema v2, adapter v2-to-v3, legacy validators chỉ phục vụ v2 và test tương ứng.

## 5. Data flow và tính toàn vẹn

`problem_text` trong Scene v3 luôn giữ nguyên input người dùng. NLP output truyền bằng field nội bộ riêng vào prompt. Khi NLP hints mâu thuẫn nguồn, LLM phải ưu tiên nguồn; deterministic validation vẫn quyết định output có được project hay không.

Stable ID do extraction tạo trong cùng response và mọi operand tham chiếu ID đó. Label chỉ phục vụ hiển thị, không dùng làm identity hoặc suy ngược relation semantics.

Không chuyển shorthand `AB` thành hai point operands sau extraction. Nếu đề nói đoạn `AB`, reasoning/extraction phải tạo segment object với endpoint references rồi relation operand tham chiếu segment ID.

Workspace revision, optimistic concurrency và trust gate hiện tại được giữ.

## 6. Error handling

Issue chuẩn hóa chứa tối thiểu:

- `code`;
- `stage`;
- `message`;
- `object_id` hoặc `relation_id` khi có;
- expected contract;
- actual operands/kinds;
- retryability;
- correlation ID tại API boundary.

Phân loại:

- Provider timeout, quota, rate limit, unavailable: provider error.
- JSON/schema sai: extraction schema error.
- Reference hoặc operand sai: scene contract error.
- Constraint không thỏa: geometry verification error.
- Projection không hỗ trợ: renderer/projection error.

Không ánh xạ scene contract error thành “Dịch vụ AI chưa sẵn sàng”. Sau một repair thất bại, API trả lỗi scene chính xác và không retry provider vô hạn.

## 7. Loại bỏ Scene v2

Loại bỏ theo dependency order:

1. Chuyển render v3 sang extractor native.
2. Chuyển frontend sang v3-only.
3. Chuyển solver/export/variants/history/renderer còn dùng shape legacy.
4. Xóa route và job v2.
5. Xóa schema, adapter, validator, frontend types/state và tests v2.
6. Xóa database artifacts chỉ phục vụ v2 sau khi kiểm tra references.
7. Reset development database bằng setup/migration hiện tại.

Không giữ alias route, compatibility shim hoặc dead code.

## 8. Kiểm thử

### Unit

- Parse native Scene v3.
- Stable ID và reference integrity.
- Relation registry với typed operands.
- Prompt input giữ nguyên `problem_text`.
- Repair issue serialization.
- Provider/model selection không đổi semantics.

### Regression

Bắt buộc có shorthand và relation phổ biến:

- `AB`, `SA`, `plane(ABCD)`;
- midpoint;
- equal length;
- parallel và perpendicular line-line, line-plane, plane-plane;
- intersection;
- collinear/coplanar;
- distance, angle, tangent;
- bài 2D và 3D thiếu object tường minh trong câu chữ nhưng object được relation ngụ ý.

### Integration

- `reason -> extract -> validate -> project`.
- `reason -> extract lỗi -> repair -> validate -> project`.
- repair vẫn lỗi trả coded error đúng stage.
- NLP authoritative config không làm thay `problem_text` ở render.
- workspace/commands giữ revision và chạy lại verification.
- downstream chỉ nhận trusted Scene v3.

### API và frontend

- `/api/render/v3` trả workspace/projection hợp lệ.
- Frontend hiển thị scene, warning và coded error đúng taxonomy.
- Không còn request tới route v2.
- Type-check bảo đảm không còn import type v2.

### Corpus chất lượng

Corpus cố định gồm đề hình học 2D/3D đại diện. Ghi nhận:

- tỷ lệ dựng thành công;
- tỷ lệ vượt schema/relation contract;
- tỷ lệ cần repair và repair thành công;
- relation recall so với đề;
- annotation hợp lệ;
- geometry verification;
- fidelity giữa đề, scene và hình;
- latency và số lượt LLM call.

Baseline lấy từ phiên bản trước thay đổi trên cùng corpus/model/config. Native v3 không được rollout nếu hết `RELATION_CONTRACT_INVALID` nhưng fidelity hoặc relation recall giảm đáng kể.

## 9. Kiểm tra hoàn thành

Chạy tối thiểu:

- backend unit/integration/API tests liên quan;
- corpus regression;
- frontend tests;
- backend lint/type-check nếu project hỗ trợ;
- frontend lint/type-check/build;
- end-to-end từ nhập đề tới renderer, workspace command và downstream solve/export/variants;
- tìm toàn repository để xác nhận không còn route, schema, adapter hoặc import Scene v2.

## 10. Rủi ro và kiểm soát

- Chi phí/latency tăng do reasoning và repair: repair chỉ chạy khi deterministic validation lỗi; đo trên corpus.
- Model sinh stable ID không nhất quán: schema/reference validation chặn và repair nhận issue cụ thể.
- Xóa v2 làm diff lớn: chuyển caller theo dependency order, giữ test xanh từng chặng, chỉ xóa sau khi không còn reference.
- NLP hints gây lệch: giữ nguyên nguồn, hints tách riêng và ưu tiên nguồn khi mâu thuẫn.
- Geometry verifier chưa phủ mọi relation: phân biệt unsupported/needs-confirmation với contradicted; không giả vờ verified.
- Dữ liệu development cũ không tương thích: reset bằng quy trình setup hiện có, không viết migration compatibility không cần thiết.
