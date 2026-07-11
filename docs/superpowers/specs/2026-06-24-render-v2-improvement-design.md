# Thiết kế cải thiện toàn diện `/render` v2

## 1. Bối cảnh

Tài liệu `danh_gia/render.md` và rà soát code hiện tại cho thấy `/render` đã có nền tảng tốt: schema `MathScene`, semantic validator, CAS verifier, auto-fix, nhiều renderer, scene editing, export, solver, variants và history. Vấn đề chính không còn là thiếu khả năng vẽ hình, mà là ranh giới tin cậy giữa AI, validator/CAS, scene edit, renderer, solver, export và history.

Đợt cải thiện này chọn hướng **Trust Boundary First**:

- Sửa contract và pipeline để không tạo xác nhận giả.
- Không trình bày mock/fallback như kết quả thành công bình thường.
- Chạy lại validation và verification sau mọi scene edit.
- Dùng một `activeScene` duy nhất cho renderer, editor, solver, variants và export.
- Lưu history/revision với metadata v2 đầy đủ.
- Giữ theme, style và ngôn ngữ giao diện hiện tại; không thiết kế lại UI toàn cục.

## 2. Phạm vi

### Trong phạm vi

- Breaking contract `/render` sang v2.
- Thay trực tiếp v1 trong frontend/backend/tests.
- Không hỗ trợ mở lại history/scene cũ sau khi nâng cấp.
- Schema scene v2 với ID, revision, provenance và verification theo relation instance.
- Pipeline chung cho `/render` và `/render/scene`.
- Relation registry dùng chung giữa validator, CAS, renderer compatibility và auto-fix policy.
- Render fallback status rõ ràng.
- Scene edit revalidation.
- Active scene frontend.
- History/revision metadata mới.
- Error code theo stage.
- Test backend, frontend và e2e tối thiểu cho P0/P1 lõi.

### Ngoài phạm vi đợt đầu

- P2 như public share, collaboration, LMS embed, teacher approval.
- Migration/backfill dữ liệu history cũ.
- Xóa hoặc biến đổi dữ liệu production.
- Thiết kế lại toàn bộ giao diện.
- Mở rộng nhiều object/relation mới ngoài những relation cần để đồng bộ registry hiện có.

Nếu cần xóa dữ liệu thật hoặc chạy migration phá hủy production, phải xin xác nhận riêng.

## 3. Nguyên tắc thiết kế

1. **Không có issue không đồng nghĩa verified.** Verification phải trả kết quả cho từng relation ID.
2. **Không drop im lặng.** Object/relation unsupported phải được giữ trong report với trạng thái rõ ràng.
3. **Không mock như success.** Mock/fallback luôn có trạng thái riêng và yêu cầu xác nhận trước khi dùng cho solver/variants/export sạch.
4. **Edit làm mất hiệu lực verification liên quan.** Mọi scene edit phải revalidate/reverify.
5. **Auto-fix có giới hạn.** Không tự di chuyển điểm `given` hoặc `user_edited` nếu chưa có xác nhận.
6. **Renderer chỉ nhận scene tương thích.** Preferred renderer phải đi qua compatibility validation.
7. **Frontend có một nguồn sự thật.** `activeScene` là scene duy nhất cho render, edit, solve, variants và export.
8. **Giữ style hiện tại.** UI mới dùng component/pattern hiện có, hạn chế card nổi, không đổi theme toàn cục.

## 4. Contract v2

### 4.1. Render status

```ts
type RenderStatus =
  | 'verified'
  | 'partially_verified'
  | 'needs_confirmation'
  | 'fallback'
  | 'failed';
```

Ý nghĩa:

- `verified`: validation và verification quan trọng đều pass.
- `partially_verified`: scene dựng được nhưng có relation unsupported/unverifiable hoặc advisory risk.
- `needs_confirmation`: có assumptions, missing data, repair proposal hoặc fallback cần người dùng xác nhận.
- `fallback`: hệ thống dùng mock hoặc fallback không đáng tin cậy như kết quả AI chính.
- `failed`: không dựng được scene/payload an toàn.

### 4.2. Render response

```ts
type RenderResponseV2 = {
  status: RenderStatus;
  source: RenderSource;
  scene: MathSceneV2;
  payload: RenderPayload;
  validation_report: ValidationReport;
  verification_report: VerificationReport;
  repair_report?: RepairReport;
  renderer_compatibility: RendererCompatibilityReport;
  advisory?: RenderAdvisory;
  requires_user_confirmation: boolean;
  warnings: string[];
};
```

`RenderSource`:

```ts
type RenderSource = {
  kind: 'ai' | 'byok' | 'mock' | 'scene_edit' | 'manual';
  provider?: string;
  model?: string;
  fallback_used: boolean;
  fallback_reason?: string;
  candidate_attempts: CandidateAttempt[];
};
```

### 4.3. Scene v2

```ts
type MathSceneV2 = {
  scene_id: string;
  schema_version: '2.0';
  revision: number;
  problem_text: string;
  topic: string;
  renderer: RendererKind;
  view: SceneView;
  interpretation: SceneInterpretation;
  objects: SceneObjectV2[];
  relations: RelationV2[];
  annotations: AnnotationV2[];
  parameters: SceneParameter[];
  construction_steps: ConstructionStep[];
  audit: SceneAudit;
};
```

Object v2 phải có:

```ts
type SceneObjectV2 = {
  id: string;
  type: string;
  name?: string;
  source: 'given' | 'ai_inferred' | 'construction' | 'user_created' | 'user_edited';
  locked: boolean;
  user_edited: boolean;
  metadata?: Record<string, unknown>;
};
```

Relation v2 phải có:

```ts
type RelationV2 = {
  id: string;
  type: string;
  args: Record<string, unknown>;
  source: 'given' | 'ai_inferred' | 'construction' | 'user_created';
  verification: RelationVerification;
  metadata?: Record<string, unknown>;
};
```

Relation vẫn có thể lưu name/string reference để tương thích renderer hiện tại trong nội bộ, nhưng verification/report không được dùng `relation_type` làm khóa.

## 5. Verification model

### 5.1. Relation verification

```ts
type VerificationStatus =
  | 'verified'
  | 'failed'
  | 'unsupported'
  | 'unverifiable'
  | 'error';

type RelationVerification = {
  relation_id: string;
  status: VerificationStatus;
  method?: string;
  tolerance?: number;
  evidence?: string;
  message?: string;
  verifier_version: string;
};
```

Quy tắc:

- CAS verifier phải trả result cho từng relation ID.
- Exception trong verifier tạo `status='error'` và được log ở backend.
- Parser không đọc được relation tạo `unverifiable` hoặc `error`, tùy nguyên nhân.
- Relation chưa hỗ trợ tạo `unsupported`.
- Không relation nào được mark `verified` chỉ vì không có issue.

### 5.2. Verification report

```ts
type VerificationReport = {
  status: 'passed' | 'partial' | 'failed';
  relations: RelationVerification[];
  summary: {
    verified: number;
    failed: number;
    unsupported: number;
    unverifiable: number;
    error: number;
  };
};
```

`status='passed'` chỉ khi các relation trọng yếu đều verified và không có verification error.

## 6. Relation registry

Tạo registry dùng chung cho relation type:

```python
RELATION_REGISTRY = {
    "perpendicular": {
        "parse": parse_perpendicular,
        "semantic_validate": validate_perpendicular,
        "verify": verify_perpendicular,
        "renderer_support": {...},
        "auto_fix_policy": "proposal_or_safe",
    },
}
```

Registry phải dùng ở:

- Pre-validator.
- Semantic validator.
- CAS verifier dispatch.
- Renderer compatibility.
- Auto-fix policy.
- Contract tests.

Relation đang có trong CAS nhưng bị validator drop, như `point_on_segment`, `line_in_plane`, `parallel_planes`, `perpendicular_planes`, `ratio`, phải được đưa vào registry hoặc trả `unsupported` có chủ đích. `intersection` không được pass ngầm nếu chưa có verifier.

## 7. Backend pipeline chung

Tạo pipeline dùng chung, ví dụ:

```python
validate_normalize_verify_scene(input_scene, options) -> ScenePipelineResult
```

Luồng:

```text
raw input / AI scene / edited scene
→ normalize to v2
→ semantic validate
→ relation registry parse/support
→ verify per relation
→ repair proposal hoặc safe repair
→ renderer compatibility validation
→ build payload
→ build advisory
→ save history/revision nếu policy cho phép
```

### 7.1. `/api/render`

- Candidate AI invalid phải được xem là candidate failure.
- Tiếp tục thử candidate kế tiếp nếu còn thời gian/candidate.
- Chỉ dùng mock sau khi toàn bộ candidate thất bại hoặc không có model.
- Mock trả `status='fallback'` hoặc `needs_confirmation`, không phải success thường.
- Preferred renderer áp trước compatibility validation.

### 7.2. `/api/render/scene`

- Nhận `MathSceneV2` hoặc scene edit operation.
- Không tin `verification`/`cas_issues` cũ từ request.
- Revalidate/reverify toàn bộ hoặc ít nhất invalid/reverify relation bị ảnh hưởng.
- Không tự tạo render history item thông thường cho mỗi edit.
- Trả `RenderResponseV2` mới với verification/advisory cập nhật.

## 8. Repair và auto-fix policy

Auto-fix chỉ tự áp dụng khi:

- Điểm/object là `construction` hoặc `ai_inferred`.
- Không có `locked=true`.
- Không có `user_edited=true`.
- Displacement nhỏ theo scale scene.
- Không làm relation đã verified chuyển thành failed.
- Có `repair_report` ghi diff.

Nếu ảnh hưởng `given`, `user_edited`, displacement lớn hoặc nhiều nghiệm hợp lệ, pipeline trả repair proposal:

```ts
type RepairReport = {
  status: 'none' | 'applied' | 'proposal' | 'rejected';
  changes: RepairChange[];
  requires_confirmation: boolean;
};
```

Sửa riêng lỗi hình chiếu:

- Công cụ tạo chân vuông góc phải chiếu source point xuống target line/segment, không chiếu click point.
- Tách `project_to_line` và `project_to_segment`.
- Với line: không clamp.
- Với segment: clamp và báo nếu chân nằm ngoài đoạn.
- Thêm relation `perpendicular` và `on_line` hoặc `point_on_segment`.
- Reverify sau khi thêm.

Sửa riêng on-plane inference:

- Không chọn candidate có displacement lớn nhất.
- Nếu chỉ một tọa độ unknown rõ ràng, chỉ giải tọa độ đó.
- Nếu không có unknown rõ ràng, dùng projection trong repair proposal hoặc safe repair theo policy.

## 9. Renderer compatibility

Tạo `validate_renderer_compatibility(scene, requested_renderer)`.

Quy tắc tối thiểu:

- Chặn 3D scene ép GeoGebra 2D nếu có Point3D/Plane/Sphere/Face 3D.
- Chặn scene 2D/function graph ép Three.js nếu chưa có conversion rõ ràng.
- Đồng bộ `scene.renderer` và `scene.view.dimension`.
- Không tự bỏ trục z để ép 2D.
- Trả lỗi `RENDERER_INCOMPATIBLE` hoặc report `requires_user_confirmation`.

## 10. Frontend workspace

### 10.1. State

```ts
type RenderWorkspaceState = {
  response: RenderResponseV2 | null;
  activeScene: MathSceneV2 | null;
  activeRevision: number;
  pendingEdit: SceneEditDraft | null;
  confirmation: {
    fallback_confirmed: boolean;
    assumptions_confirmed: boolean;
    repair_confirmed: boolean;
  };
};
```

Nguyên tắc:

- Renderer dùng `activeScene`.
- Editor dùng `activeScene`.
- Solver dùng `activeScene` qua quality gate.
- Variants dùng `activeScene` qua quality gate.
- Export dùng `activeScene` và giữ warning/advisory nếu partial/fallback.
- History restore khôi phục toàn bộ response v2 và advanced settings.

### 10.2. UI và style

UI mới phải giữ theme/style hiện tại:

- Dùng typography, spacing, button, panel, tab và màu đang có.
- Không đổi global theme.
- Không dùng emoji làm icon hoặc trạng thái.
- Tránh lạm dụng card nổi, shadow nặng, glassmorphism hoặc layout quá khác hiện tại.
- Ưu tiên panel phẳng, border nhẹ, section header rõ, table/list đơn giản.
- Nếu thêm Object Tree, Verification Panel, Property Panel thì đặt trong bố cục hiện tại, không biến trang thành dashboard mới.
- Error/warning text phải bằng tiếng Việt có dấu và không lộ chi tiết nội bộ.

Gợi ý workspace:

- Left panel: interpretation summary, assumptions, missing data, object tree, revision list.
- Center: renderer, banner trạng thái, action chính.
- Right panel: verification report, advisory risk, property panel, repair proposal diff.

Có thể triển khai theo từng bước để không phá UI:

1. Trước tiên thêm banner/report/gate vào layout hiện tại.
2. Sau đó thêm object tree/property panel gọn.
3. Cuối cùng thêm revision UI.

## 11. Quality gates frontend

Solver, variants và export phải kiểm tra response trước khi chạy:

- `status='fallback'` và chưa confirm: disable solver/variants, export phải kèm warning hoặc yêu cầu confirm.
- Có `verification.error` hoặc relation trọng yếu failed: disable solver/variants.
- `partially_verified`: cho export nhưng giữ warning/advisory.
- `needs_confirmation`: hiển thị action xác nhận assumptions/fallback/repair.

## 12. History và revision

Breaking v2 không hỗ trợ history cũ. History mới lưu full `RenderResponseV2`.

Đề xuất tối thiểu phase đầu:

- AI render mới tạo history job.
- Scene edit không tạo history job mặc định.
- User bấm `Lưu phiên bản` mới tạo revision/history snapshot.
- Mở history khôi phục full response v2, including:
  - status;
  - source provider/model;
  - verification report;
  - advisory;
  - advanced settings;
  - renderer compatibility;
  - revision.

Nếu chưa thêm bảng revision riêng ngay, có thể lưu snapshot v2 vào history với `source_type='manual_snapshot'`, nhưng không dùng `scene_edit` cho mọi drag/edit.

## 13. Error handling

Thay error chung bằng mã theo stage:

- `RENDER_INPUT_INVALID`
- `RENDER_EXTRACTION_FAILED`
- `RENDER_SCHEMA_INVALID`
- `RENDER_SEMANTIC_INVALID`
- `RENDER_VERIFICATION_FAILED`
- `RENDERER_INCOMPATIBLE`
- `RENDER_FALLBACK_REQUIRES_CONFIRMATION`
- `RENDER_TIMEOUT`
- `PLAN_QUOTA_EXCEEDED`
- `MAINTENANCE_MODE`

Error payload:

```ts
type RenderError = {
  code: string;
  message: string;
  stage: 'input' | 'extraction' | 'schema' | 'semantic' | 'verification' | 'renderer' | 'quota';
  suggestions: string[];
  correlation_id?: string;
};
```

Không trả stack trace hoặc raw exception cho frontend. Backend log chi tiết với correlation ID nếu hạ tầng hiện có hỗ trợ.

## 14. Testing

### 14.1. Backend tests

Bắt buộc có test cho:

- Candidate A invalid, Candidate B success.
- Tất cả candidate fail thì response là fallback/needs confirmation.
- CAS exception tạo relation verification `error`.
- Unsupported relation tạo `unsupported`, không bị drop im lặng.
- Relation supported bởi CAS không bị pre-validator drop.
- `/render/scene` reverify và không giữ issue/verification cũ.
- Renderer mismatch trả `RENDERER_INCOMPATIBLE` hoặc compatibility report failed.
- Auto-fix không di chuyển `given`, `locked`, `user_edited`.
- On-plane inference không chọn displacement lớn nhất.
- Projection tool tạo relation đúng nếu logic backend tham gia.

### 14.2. Frontend tests

Bắt buộc có test cho:

- `activeScene` được dùng cho edit/export/solve.
- Solver/variants disabled khi fallback chưa confirmed.
- Export partial/fallback có warning.
- Mở history khôi phục full response v2 và advanced settings.
- Projection tool dùng source point.
- Three và GeoGebra đều hiển thị status banner.
- Advisory/verification panel render đúng trạng thái failed/unsupported/unverifiable/error.

### 14.3. E2E tối thiểu

- Render đề 2D rõ ràng.
- Render đề 3D rõ ràng.
- AI invalid candidate fallback sang candidate kế.
- Mock fallback cần confirm.
- Kéo điểm phá relation rồi reverify thấy failed.
- Tạo chân vuông góc đúng.
- Export scene partial có warning.
- Mở lại history mới vẫn giữ verification/advisory.

## 15. Rủi ro và kiểm soát

### Rủi ro: breaking v2 làm hỏng caller cũ

Kiểm soát: cập nhật frontend/backend/tests cùng lúc, không duy trì v1, chấp nhận không mở history cũ theo quyết định sản phẩm.

### Rủi ro: phạm vi quá lớn

Kiểm soát: triển khai theo phase kỹ thuật:

1. Contract v2 và tests schema.
2. Relation registry và verifier report.
3. Pipeline chung `/render` + `/render/scene`.
4. Fallback/status/error codes.
5. Frontend activeScene và gates.
6. History/revision tối thiểu.
7. UI panels theo style hiện tại.

### Rủi ro: UI bị lệch style

Kiểm soát: mọi UI mới phải reuse component/class hiện tại, dùng panel phẳng, border nhẹ, typography hiện tại, không lạm dụng card nổi hoặc shadow. Trước khi triển khai UI lớn, rà soát component tương tự trong codebase.

### Rủi ro: auto-fix làm thay đổi dữ kiện

Kiểm soát: object provenance, lock policy, repair proposal, diff và test cho `given/user_edited`.

## 16. Tiêu chí hoàn thành

Đợt cải thiện P0 + P1 lõi hoàn thành khi:

- Mock/fallback không còn là success bình thường.
- Candidate invalid không chặn candidate sau.
- Verification theo từng relation ID.
- CAS exception không thành pass ngầm.
- Relation registry đồng bộ validator/CAS.
- `/render/scene` revalidate/reverify.
- Renderer compatibility được chặn rõ.
- Projection tool tạo đúng chân vuông góc và relation liên quan.
- Auto-fix không di chuyển dữ kiện locked/given/user-edited.
- Frontend có `activeScene` duy nhất.
- Solver/variants/export có quality gates.
- History mới lưu full response v2 và không tạo item cho mọi drag/edit.
- UI mới giữ theme/style hiện tại, không lạm dụng card nổi.
- Backend/frontend tests và e2e tối thiểu chạy thành công hoặc có lý do rõ ràng nếu chưa chạy được.
