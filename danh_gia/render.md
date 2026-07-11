# CHECKLIST RÀ SOÁT VÀ CẢI TIẾN CHỨC NĂNG `/render`

## 1. Thông tin tài liệu

- **Dự án:** AI Math Renderer
- **Chức năng:** `https://math-renderer.sin-studio.tech/render`
- **Repository rà soát:** `sin0235/math_ai_visualize`
- **Nhánh rà soát:** `product`
- **Ngày rà soát:** 21/06/2026
- **Phương pháp:** Rà soát tĩnh mã nguồn frontend, backend, schema, validator, CAS verifier, renderer, editor, export, history và test hiện có.
- **Giới hạn:** Chưa thực hiện kiểm thử end-to-end trực tiếp trên toàn bộ môi trường production, chưa đo hiệu năng thực tế trên nhiều thiết bị và chưa kiểm tra chất lượng đầu ra của tất cả model AI đang cấu hình.

---



# 2. Mục tiêu cải tiến

Nâng cấp `/render` từ một luồng:

```text
Nhập đề
→ AI sinh scene
→ Hiển thị hình
```

thành một workspace dựng hình toán học có khả năng:

```text
Nhập đề
→ Kiểm tra nội dung nhận diện
→ Công khai giả định và dữ kiện thiếu
→ Xác nhận cấu trúc toán học
→ Dựng scene
→ Kiểm chứng từng quan hệ
→ Chỉnh sửa có ràng buộc
→ Quản lý phiên bản
→ Xuất và chia sẻ kết quả
```

Mục tiêu cuối cùng:

> `/render` phải tạo được hình có thể giải thích, kiểm chứng, chỉnh sửa và truy vết; không chỉ tạo một hình “có vẻ đúng”.

---



# 3. Quy ước mức ưu tiên


| Mức    | Ý nghĩa                                                                                                                            |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| **P0** | Có thể làm sai hình, làm sai quan hệ toán học, báo thành công không đáng tin cậy, mất dữ liệu hoặc gây lỗi kiến trúc nghiêm trọng. |
| **P1** | Cần thiết để nâng chất lượng sản phẩm, khả năng chỉnh sửa, kiểm chứng và trải nghiệm người dùng.                                   |
| **P2** | Tính năng nâng cao phục vụ giáo viên, học sinh, cộng tác và mở rộng hệ sinh thái.                                                  |


Quy ước trạng thái:

```text
[ ] Chưa thực hiện
[-] Đang thực hiện
[x] Đã hoàn thành
[!] Cần quyết định sản phẩm hoặc kiến trúc
```

---



# 4. Phạm vi mã nguồn đã rà soát



## 4.1. Frontend

- `frontend/src/App.tsx`
- `frontend/src/components/ProblemInput.tsx`
- `frontend/src/components/RendererPanel.tsx`
- `frontend/src/components/SceneEditorPanel.tsx`
- `frontend/src/components/GeoGebraView.tsx`
- `frontend/src/components/ThreeGeometryView.tsx`
- `frontend/src/components/ExportMenu.tsx`
- `frontend/src/api/render.ts`
- `frontend/src/types/scene.ts`
- `frontend/src/utils/sceneEditing.ts`



## 4.2. Backend

- `backend/app/api/routes_render.py`
- `backend/app/api/routes_export.py`
- `backend/app/schemas/scene.py`
- `backend/app/services/extractor.py`
- `backend/app/services/scene_validator.py`
- `backend/app/services/cas_verifier.py`
- `backend/app/services/geometry_engine.py`
- `backend/app/services/renderer_router.py`
- `backend/app/renderers/geogebra_commands.py`



## 4.3. Kiểm thử

- `backend/tests/test_routes_render.py`
- `backend/tests/test_scene_validator.py`
- `backend/tests/test_cas_verifier.py`

---



# 5. Đánh giá tổng quan



## 5.1. Điểm mạnh hiện tại

- [ ] Có schema `MathScene` chung cho nhiều renderer.
- [x] Có pipeline kiểm tra schema bằng Pydantic.
- [x] Có semantic validator riêng.
- [x] Có CAS verifier cho nhiều quan hệ hình học.
- [x] Có auto-fix cho một số quan hệ.
- [x] Có GeoGebra 2D.
- [x] Có GeoGebra 3D.
- [x] Có Three.js 3D.
- [x] Có chỉnh sửa điểm trực tiếp.
- [x] Có tham số động.
- [x] Có OCR ảnh đề bài.
- [x] Có fallback provider AI.
- [x] Có rate limit và quota render.
- [x] Có lịch sử.
- [x] Có xuất PNG, JPG, SVG, HTML và TikZ trên frontend.
- [x] Backend đã có thêm PDF và GGB.
- [x] Có giải từng bước dựa trên scene.
- [x] Có sinh đề biến thể.
- [x] Có quality advisory trong response.
- [x] Có kiểm tra một số lỗi tham chiếu, trùng tên và sai chiều dữ liệu.



## 5.2. Điểm yếu trọng yếu

- [ ] AI thất bại có thể trả mock scene như một kết quả render thành công.
- [ ] Scene sửa bởi người dùng không được chạy lại đầy đủ semantic validator và CAS.
- [ ] Công cụ tạo chân vuông góc đang tính sai điểm chiếu.
- [ ] Ép renderer được thực hiện sau bước validation.
- [ ] Cơ chế gắn nhãn `verified` có nguy cơ tạo xác nhận giả.
- [ ] Danh sách relation hợp lệ giữa validator và CAS không đồng bộ.
- [ ] Auto-fix mặt phẳng có thể chọn phương án dịch chuyển lớn nhất.
- [ ] Mỗi thao tác chỉnh sửa có thể tạo thêm một lịch sử render.
- [ ] Không có bước xác nhận cách AI hiểu đề.
- [ ] Không công khai dữ kiện thiếu và giả định do AI thêm.
- [ ] Không có object tree và property panel đầy đủ.
- [ ] Không có undo/redo.
- [ ] Không có versioning scene.
- [ ] Frontend chưa sử dụng đầy đủ advisory và nguồn kiểm chứng.
- [ ] Export frontend thiếu PDF và GGB dù backend đã hỗ trợ.
- [ ] SVG/HTML của Three.js thực chất là ảnh raster được nhúng.
- [ ] Camera 3D còn đơn giản.
- [ ] GeoGebra có thể bị khởi tạo lại khi mở bảng đại số.
- [ ] Giới hạn input frontend và backend không thống nhất.
- [ ] Trường `grade` có trong API nhưng frontend không gửi.
- [ ] Error code render còn quá chung.

---



# 6. Luồng xử lý hiện tại

```text
Người dùng nhập văn bản hoặc OCR ảnh
        ↓
Frontend gửi problem_text + tier + renderer + advanced settings
        ↓
Backend chọn model theo tier
        ↓
Có thể chạy reasoning layer
        ↓
AI sinh JSON MathScene
        ↓
Pre-validator loại dữ liệu không hợp lệ
        ↓
Normalize scene
        ↓
Pydantic validate
        ↓
Semantic validator
        ↓
CAS inference và auto-fix
        ↓
Có thể ép renderer theo lựa chọn người dùng
        ↓
Geometry normalization
        ↓
Sinh GeoGebra commands hoặc Three scene
        ↓
Trả response
        ↓
Lưu lịch sử
```



## 6.1. Vấn đề của luồng hiện tại

- Renderer được ép sau khi scene đã qua validation.
- Khi model trả scene không hợp lệ, pipeline có thể dừng fallback và chuyển thẳng sang mock.
- Mock scene vẫn được trả với HTTP thành công.
- Người dùng không được duyệt cách AI hiểu đề trước khi render.
- Scene edit dùng một endpoint khác nhưng không chạy lại cùng pipeline kiểm chứng ban đầu.
- Lịch sử không phân biệt rõ chỉnh sửa nhỏ với một render mới.

---



# 7. Checklist P0 — Các lỗi phải xử lý trước



# P0-01. Không trả mock scene như một kết quả thành công bình thường



## Mô tả

Khi:

- Không có provider/model khả dụng.
- Tất cả provider lỗi.
- Model timeout.
- Model trả scene sai schema.
- Model trả scene không hợp lệ.

Pipeline hiện có thể gọi `extract_scene_mock()` và trả về một scene generic dựa trên từ khóa.

Ví dụ:

- Gặp từ “hình chóp” có thể sinh preset hình chóp đáy vuông.
- Gặp từ “tứ diện” có thể sinh preset tứ diện.
- Gặp từ “vector” nhưng thiếu dữ liệu có thể tự sinh A, B mặc định.
- Gặp “đường tròn” nhưng thiếu dữ kiện có thể sinh O và A mặc định.

Một hình generic như vậy có thể nhìn hợp lý nhưng không phản ánh đúng đề.

## Rủi ro

- Người dùng tưởng AI đã hiểu và dựng đúng đề.
- Solver phía sau sử dụng scene giả để giải.
- Sinh đề biến thể từ scene giả.
- Xuất hình sai nhưng không có lỗi chặn.
- Lịch sử lưu một scene không đáng tin cậy.



## Checklist

- [ ] Không trả `status=success` thông thường khi đang dùng mock fallback.
- [ ] Bổ sung `render_status`.
- [ ] Bổ sung `render_source`.
- [ ] Bổ sung `fallback_used`.
- [ ] Bổ sung `fallback_reason`.
- [ ] Bổ sung `source_provider`.
- [ ] Bổ sung `source_model`.
- [ ] Không cho dùng Solver khi scene là mock chưa xác nhận.
- [ ] Không cho sinh đề biến thể từ mock scene chưa xác nhận.
- [ ] Gắn watermark hoặc banner `Hình minh họa dự phòng`.
- [ ] Cho phép người dùng chọn `Dùng hình minh họa` hoặc `Thử lại AI`.
- [ ] Không tự động lưu mock scene vào lịch sử như scene hoàn chỉnh.
- [ ] Gửi lỗi rõ ràng nếu đề không thể dựng đáng tin cậy.



## Schema đề xuất

```json
{
  "render_status": "fallback",
  "render_source": "mock",
  "fallback_used": true,
  "fallback_reason": "all_providers_failed",
  "requires_user_confirmation": true
}
```



## Test bắt buộc

- [ ] Tất cả provider lỗi.
- [ ] Model trả JSON sai.
- [ ] Model trả scene thiếu object bắt buộc.
- [ ] Model timeout.
- [ ] Không cấu hình model.
- [ ] Mock scene không được hiển thị là kết quả đã kiểm chứng.

---



# P0-02. Khi một model trả scene sai, phải thử model dự phòng tiếp theo



## Mô tả

Trong luồng hiện tại, nếu một candidate AI trả response nhưng scene không qua validation, pipeline có thể chuyển ngay sang mock thay vì thử candidate tiếp theo.

## Rủi ro

- Fallback chain không hoạt động đúng kỳ vọng.
- Tier có nhiều model nhưng chỉ candidate đầu thực sự được tận dụng.
- Tỷ lệ mock fallback cao không cần thiết.
- Người dùng mất thời gian chờ rồi nhận hình generic.



## Checklist

- [ ] Validation failure của một candidate được xem là candidate failure.
- [ ] Tiếp tục model fallback kế tiếp.
- [ ] Chỉ dùng mock sau khi toàn bộ candidate thất bại.
- [ ] Giới hạn số candidate.
- [ ] Theo dõi thời gian còn lại.
- [ ] Ghi log loại lỗi `extraction`, `schema`, `semantic`, `CAS`.
- [ ] Không lặp model đã thất bại.
- [ ] Có metric tỷ lệ thành công theo model.
- [ ] Có metric tỷ lệ scene invalid theo model.



## Tiêu chí hoàn thành

- [ ] Candidate A sai schema không ngăn Candidate B được thử.
- [ ] Response ghi rõ model nào thực sự tạo scene cuối.

---



# P0-03. Chạy validation sau khi ép renderer



## Mô tả

Backend hiện:

```text
extract_scene
→ validate/CAS
→ preferred_renderer override
→ normalize_scene
→ build payload
```

Nếu AI tạo scene 3D nhưng người dùng ép GeoGebra 2D:

- Scene vẫn có point 3D.
- View có thể vẫn là 3D.
- GeoGebra 2D nhận command 3D.
- Semantic validator không được chạy lại sau override.



## Checklist

- [ ] Chuyển `preferred_renderer` vào trước bước validation.
- [ ] Hoặc chạy compatibility validation sau override.
- [ ] Đồng bộ `scene.renderer`.
- [ ] Đồng bộ `scene.view.dimension`.
- [ ] Chuyển đổi object 2D/3D chỉ khi an toàn.
- [ ] Không tự bỏ trục z mà không thông báo.
- [ ] Chặn ép 2D với scene cần 3D.
- [ ] Chặn Three.js cho scene không được renderer hỗ trợ.
- [ ] Hiển thị lý do không tương thích.
- [ ] Cho phép `auto` chọn renderer khác.



## Test bắt buộc

- [ ] Scene 3D ép GeoGebra 2D.
- [ ] Scene 2D ép Three.js.
- [ ] Function graph ép Three.js.
- [ ] Sphere ép GeoGebra 2D.
- [ ] Renderer và dimension luôn nhất quán.

---



# P0-04. Endpoint `/render/scene` phải chạy lại validator và CAS



## Mô tả

Endpoint dựng lại scene sau chỉnh sửa hiện chủ yếu:

```text
normalize_scene
→ build_render_payload
```

Nó không chạy lại đầy đủ:

- `pre_validate_raw`
- `validate_and_repair`
- `infer_point_coordinates`
- `auto_fix_scene`
- cập nhật verification metadata

Test route hiện còn xác nhận việc giữ lại `cas_issues` cũ thay vì tính lại.

## Rủi ro

- Người dùng kéo điểm làm mất quan hệ vuông góc nhưng scene vẫn giữ metadata verified.
- CAS issue cũ vẫn tồn tại sau khi đã sửa đúng.
- Scene mới sai không bị phát hiện.
- Solver dùng dữ kiện không còn đúng.
- Export chứa hình sai.
- History lưu scene sai.



## Checklist

- [ ] Tạo pipeline chung `validate_normalize_verify_scene`.
- [ ] Cả `/render` và `/render/scene` dùng cùng pipeline.
- [ ] Xóa `cas_issues` cũ trước khi kiểm chứng lại.
- [ ] Tính lại CAS issues.
- [ ] Tính lại relation confidence.
- [ ] Tính lại advisory.
- [ ] Không tự sửa điểm người dùng vừa kéo nếu chưa xác nhận.
- [ ] Phân biệt validation-only và auto-fix.
- [ ] Cho phép chế độ `strict`.
- [ ] Cho phép chế độ `preserve_user_edit`.
- [ ] Trả diff các thay đổi validator thực hiện.



## Tiêu chí hoàn thành

- [ ] Sau khi sửa scene, mọi quan hệ đều được kiểm chứng lại.
- [ ] CAS issue cũ không được tái sử dụng.
- [ ] Scene edit không thể giữ trạng thái verified sai.

---



# P0-05. Sửa công cụ “Tạo chân nối”



## Mô tả lỗi

Luồng hiện tại:

1. Người dùng chọn điểm nguồn.
2. Người dùng click vào đoạn đích.
3. Frontend truyền tọa độ click vào `projectPointToSegment`.
4. Hệ thống chiếu chính điểm click lên đoạn.
5. Điểm mới thường nằm gần vị trí click, không phải chân vuông góc từ điểm nguồn.

Ngoài ra, phép chiếu bị clamp về đoạn `[0,1]`, trong khi “chân đường vuông góc” có thể nằm ngoài đoạn nếu đang chiếu lên đường thẳng.

Scene mới chỉ thêm:

- Một điểm.
- Một segment nối điểm nguồn với điểm mới.

Không thêm:

- Relation `perpendicular`.
- Relation `on_line` hoặc `point_on_segment`.
- Metadata nguồn dựng.



## Hướng sửa

```text
source point
→ projection of source onto target line/segment
→ create foot point H
→ create SH
→ create on_line relation
→ create perpendicular relation
→ reverify
```



## Checklist

- [ ] Dùng tọa độ điểm nguồn để tính projection.
- [ ] Tách chế độ `project_to_line`.
- [ ] Tách chế độ `project_to_segment`.
- [ ] Với line: không clamp `t`.
- [ ] Với segment: clamp và báo nếu chân nằm ngoài đoạn.
- [ ] Thêm relation `on_line`.
- [ ] Thêm relation `perpendicular`.
- [ ] Thêm annotation góc vuông.
- [ ] Đặt tên điểm hợp lý.
- [ ] Kiểm chứng sau khi thêm.
- [ ] Thêm unit test cho phép chiếu.
- [ ] Thêm end-to-end test trên canvas.



## Test bắt buộc

- [ ] Chân nằm trong đoạn.
- [ ] Chân nằm ngoài đoạn.
- [ ] Đoạn suy biến.
- [ ] Điểm nguồn nằm trên đoạn.
- [ ] Hình 2D.
- [ ] Hình 3D.

---



# P0-06. Đồng bộ allowlist relation giữa validator và CAS



## Mô tả

Semantic pre-validator chỉ cho phép một tập relation.

CAS verifier hỗ trợ thêm:

- `point_on_segment`
- `line_in_plane`
- `parallel_planes`
- `perpendicular_planes`
- `ratio`
- các alias liên quan

Nhưng các relation này có thể bị pre-validator loại trước khi CAS nhận được.

Ngược lại:

- `intersection` được validator cho phép.
- CAS dispatch không có logic kiểm chứng tương ứng.



## Rủi ro

- Relation hợp lệ bị mất.
- Relation chưa được CAS hỗ trợ vẫn có thể được xem như không có lỗi.
- Hệ thống báo verification sai.



## Checklist

- [ ] Tạo enum relation dùng chung.
- [ ] Tạo registry relation.
- [ ] Mỗi relation khai báo parser.
- [ ] Mỗi relation khai báo validator.
- [ ] Mỗi relation khai báo verifier.
- [ ] Mỗi relation khai báo renderer support.
- [ ] Mỗi relation khai báo auto-fix policy.
- [ ] Không dùng string tự do trong schema public.
- [ ] Relation chưa hỗ trợ phải có trạng thái `unsupported`.
- [ ] Không drop relation im lặng.
- [ ] Thêm contract test giữa validator và CAS.



## Registry đề xuất

```python
RELATION_REGISTRY = {
    "perpendicular": {
        "schema": ...,
        "verify": ...,
        "render": ...,
        "auto_fix": False
    }
}
```

---



# P0-07. Không suy ra “verified” chỉ vì không phát hiện issue



## Mô tả

Cơ chế hiện tại có xu hướng:

```text
relation type không nằm trong unresolved issue types
→ confidence = verified
→ verified_by = cas
```

Đây là suy luận không an toàn.

Không có issue có thể do:

- Relation thực sự đúng.
- Verifier không hỗ trợ relation.
- Parser relation thất bại.
- Thiếu điểm tham chiếu.
- Verifier ném exception.
- Tolerance quá rộng.
- Relation bị bỏ qua.
- Relation cùng type khác đã thất bại.

Ngoài ra, verification đang nhóm theo `relation_type`, không theo relation instance.

## Checklist

- [ ] Mỗi relation có `relation_id`.
- [ ] Verifier trả kết quả cho từng `relation_id`.
- [ ] Trạng thái gồm `verified`, `failed`, `unsupported`, `unverifiable`, `error`.
- [ ] Không suy ra pass từ việc không có issue.
- [ ] Exception phải tạo `verification_error`.
- [ ] Thiếu dữ liệu phải tạo `unverifiable`.
- [ ] Không dùng relation type làm khóa kết quả.
- [ ] Không downgrade toàn bộ relation cùng type khi chỉ một relation sai.
- [ ] Ghi phương pháp kiểm chứng.
- [ ] Ghi tolerance.
- [ ] Ghi evidence.
- [ ] Ghi timestamp và verifier version.



## Schema đề xuất

```json
{
  "relation_id": "rel_001",
  "status": "verified",
  "method": "dot_product",
  "evidence": "|u.v| < 1e-6",
  "tolerance": 0.000001
}
```

---



# P0-08. Không nuốt exception trong CAS verifier



## Mô tả

`verify_scene` hiện có thể bắt mọi exception và xem như relation không sinh issue.

## Rủi ro

```text
verifier lỗi
→ không có issue
→ relation có thể bị gắn verified
```



## Checklist

- [ ] Không chuyển exception thành pass ngầm.
- [ ] Trả `verification_error`.
- [ ] Ghi relation ID.
- [ ] Ghi verifier function.
- [ ] Không lộ stack trace cho người dùng.
- [ ] Log stack trace ở backend.
- [ ] Advisory phải tăng risk khi verification error.
- [ ] Chặn Solver nếu relation trọng yếu chưa kiểm chứng.

---



# P0-09. Sửa logic nội suy điểm trên mặt phẳng



## Mô tả

Khi điểm không nằm trên mặt phẳng, logic hiện thử giải từng trục riêng rồi chọn candidate có độ dịch chuyển lớn nhất.

Đây không phải:

- Hình chiếu vuông góc.
- Phương án thay đổi tối thiểu.
- Lựa chọn có căn cứ từ đề.



## Rủi ro

- Điểm bị dịch chuyển nhiều không cần thiết.
- Hình thay đổi mạnh nhưng bị gọi là auto-fix.
- Quan hệ khác bị phá vỡ.
- Dữ kiện người dùng bị sửa.



## Checklist

- [ ] Nếu cần projection, dùng hình chiếu vuông góc chính xác.
- [ ] Nếu một tọa độ được đánh dấu unknown, chỉ giải tọa độ đó.
- [ ] Nếu nhiều tọa độ tự do, không tự chọn trục tùy ý.
- [ ] Chọn phương án dịch chuyển nhỏ nhất.
- [ ] Giữ các điểm `given` cố định.
- [ ] Không di chuyển điểm người dùng chỉnh thủ công.
- [ ] Trả diff trước/sau.
- [ ] Yêu cầu xác nhận nếu displacement vượt ngưỡng.
- [ ] Cấu hình ngưỡng theo scale scene.
- [ ] Thêm test cho mặt phẳng xiên.

---



# P0-10. Giới hạn auto-fix và optimizer



## Mô tả

Optimizer có thể điều chỉnh nhiều điểm để giảm số issue. Ngưỡng displacement hiện tương đối lớn so với kích thước scene.

## Checklist

- [ ] Phân loại điểm `given`.
- [ ] Phân loại điểm `inferred`.
- [ ] Phân loại điểm `construction`.
- [ ] Phân loại điểm `user_edited`.
- [ ] Không di chuyển điểm `given`.
- [ ] Không di chuyển điểm `user_edited` nếu chưa xác nhận.
- [ ] Chỉ tối ưu điểm phụ thuộc.
- [ ] Giới hạn displacement nhỏ hơn.
- [ ] Tính displacement theo từng điểm.
- [ ] Không chỉ tính issue count.
- [ ] Kiểm tra relation bị phá sau optimization.
- [ ] Lưu optimizer report.
- [ ] Cho phép rollback.
- [ ] Không gọi sửa lớn là “chuẩn hóa”.

---



# P0-11. Không tạo history item cho mọi thao tác kéo điểm



## Mô tả

Mỗi lần `handleSceneEdit` gọi `/render/scene`, backend tạo một bản ghi lịch sử `scene_edit`.

Khi kéo điểm:

- GeoGebra debounce khoảng 350 ms rồi gửi.
- Three.js gửi khi thả điểm.
- Mỗi thao tác có thể tạo thêm history.
- Quota render được kiểm tra trên số render job.



## Rủi ro

- History bị rác.
- Người dùng nhanh hết quota.
- Database tăng nhanh.
- Khó xác định phiên bản quan trọng.
- Không có undo thực sự.



## Checklist

- [ ] Tách `render job` và `scene autosave`.
- [ ] Scene edit không tính như AI render mới.
- [ ] Không tính scene edit vào quota AI.
- [ ] Debounce autosave.
- [ ] Coalesce nhiều edit liên tiếp.
- [ ] Chỉ tạo snapshot khi người dùng chọn `Lưu phiên bản`.
- [ ] Lưu event diff thay vì toàn scene cho từng thao tác.
- [ ] Có retention policy.
- [ ] Có giới hạn số version.
- [ ] Có undo/redo local.
- [ ] Có save status.

---



# P0-12. Chỉnh sửa phải dựa trên scene đang hiển thị



## Mô tả

Khi có parameter slider:

- Frontend tạo `effectiveResult` từ scene gốc và `paramValues`.
- Một số thao tác chỉnh sửa lại dựa trên `result.scene`.
- Scene người dùng nhìn thấy có thể khác scene được gửi khi chỉnh sửa.



## Rủi ro

- Thêm điểm vào tọa độ không khớp với hình đang nhìn.
- Kéo điểm làm mất giá trị parameter hiện tại.
- Kết nối dựa trên scene cũ.
- Export và edit không cùng trạng thái.



## Checklist

- [ ] Xác định một `activeScene` duy nhất.
- [ ] Mọi edit dùng scene đang hiển thị.
- [ ] Mọi export dùng scene đang hiển thị.
- [ ] Mọi solve dùng scene đang hiển thị.
- [ ] Khi materialize parameter, ghi rõ đã tách khỏi expression.
- [ ] Có lựa chọn `Giữ liên kết tham số`.
- [ ] Có lựa chọn `Chuyển thành tọa độ cố định`.
- [ ] Test edit sau khi đổi slider.

---



# P0-13. Phân loại lỗi render cụ thể



## Mô tả

Nhiều lỗi RuntimeError, ValueError và KeyError hiện được gom thành:

```text
RENDER_FAILED
```



## Mã lỗi đề xuất


| Trường hợp                 | Mã                           |
| -------------------------- | ---------------------------- |
| Đầu vào trống hoặc sai     | `RENDER_INPUT_INVALID`       |
| Đề mơ hồ                   | `RENDER_AMBIGUOUS_INPUT`     |
| Thiếu dữ kiện              | `RENDER_MISSING_DATA`        |
| Không hỗ trợ dạng hình     | `RENDER_UNSUPPORTED`         |
| AI extraction lỗi          | `RENDER_EXTRACTION_FAILED`   |
| Scene sai schema           | `RENDER_SCHEMA_INVALID`      |
| Scene sai ngữ nghĩa        | `RENDER_SEMANTIC_INVALID`    |
| CAS kiểm chứng lỗi         | `RENDER_VERIFICATION_FAILED` |
| Renderer không tương thích | `RENDERER_INCOMPATIBLE`      |
| GeoGebra command lỗi       | `GEOGEBRA_COMMAND_FAILED`    |
| Three.js lỗi               | `THREE_RENDER_FAILED`        |
| Timeout                    | `RENDER_TIMEOUT`             |
| Hết quota                  | `PLAN_QUOTA_EXCEEDED`        |
| Bảo trì                    | `MAINTENANCE_MODE`           |




## Checklist

- [ ] Trả error code theo từng stage.
- [ ] Không lộ debug message nhạy cảm.
- [ ] Trả suggestion phù hợp.
- [ ] Có correlation ID.
- [ ] Có retry policy theo stage.
- [ ] Không gọi lại AI nếu chỉ renderer lỗi.

---



# 8. Checklist P1 — Luồng nhập đề và xác nhận



# P1-01. Thêm bước “Hệ thống hiểu đề”



## Mô tả

Hiện người dùng nhấn `Dựng hình` và hệ thống đi thẳng sang render.

Cần có bước trung gian:

```text
Đề gốc
→ Đối tượng
→ Quan hệ
→ Số liệu
→ Giả định
→ Dữ kiện thiếu
→ Renderer dự kiến
→ Xác nhận
```



## Checklist

- [ ] Hiển thị các điểm.
- [ ] Hiển thị đoạn và đường.
- [ ] Hiển thị mặt phẳng.
- [ ] Hiển thị mặt và khối.
- [ ] Hiển thị đường tròn, mặt cầu.
- [ ] Hiển thị quan hệ.
- [ ] Hiển thị số liệu.
- [ ] Hiển thị giả định.
- [ ] Hiển thị dữ kiện thiếu.
- [ ] Hiển thị đối tượng do AI tự thêm.
- [ ] Hiển thị renderer dự kiến.
- [ ] Cho phép sửa.
- [ ] Cho phép phân tích lại.
- [ ] Cho phép xác nhận và dựng.

---



# P1-02. Phân biệt hình chính xác và hình minh họa



## Checklist

- [ ] Nhãn `Dựng theo dữ kiện`.
- [ ] Nhãn `Hình minh họa`.
- [ ] Nhãn `Không theo tỉ lệ`.
- [ ] Nhãn `Có giả định`.
- [ ] Không hiển thị số đo giả định như dữ kiện.
- [ ] Không dùng hình minh họa để suy ra quan hệ.
- [ ] Solver không dùng giả định chưa xác nhận.
- [ ] Export giữ warning khi cần.

---



# P1-03. Nâng cấp OCR



## Hiện trạng

OCR:

- Upload ảnh.
- Nhận text.
- Ghi trực tiếp vào textarea.

Response không có:

- Bounding box.
- Confidence từng đoạn.
- Phân tách văn bản và hình.
- Vùng nghi ngờ.



## Checklist

- [ ] Preview ảnh.
- [ ] Crop.
- [ ] Rotate.
- [ ] Tăng tương phản.
- [ ] Chọn vùng đề.
- [ ] Chọn vùng hình.
- [ ] So sánh ảnh và text.
- [ ] Highlight ký tự confidence thấp.
- [ ] Cho sửa trước khi render.
- [ ] Không tự render sau OCR.
- [ ] Nhận diện công thức.
- [ ] Nhận diện tên điểm.
- [ ] Nhận diện ký hiệu song song.
- [ ] Nhận diện ký hiệu vuông góc.
- [ ] Nhận diện mặt phẳng.
- [ ] Lưu ảnh gốc theo chính sách rõ ràng.
- [ ] Có nút xóa ảnh.

---



# P1-04. Đồng bộ giới hạn input



## Hiện trạng

- Frontend giới hạn khoảng 2.000 ký tự.
- Backend cho phép khoảng 20.000 ký tự.



## Checklist

- [ ] Chọn một giới hạn chính thức.
- [ ] Đồng bộ frontend và backend.
- [ ] Hiển thị số ký tự còn lại.
- [ ] Giới hạn theo token ước tính.
- [ ] Cảnh báo đề quá dài.
- [ ] Hướng dẫn tách câu hỏi khỏi phần không cần dựng.

---



# P1-05. Thêm lựa chọn lớp học

Backend có `grade` từ 10 đến 12 nhưng frontend chưa gửi.

## Checklist

- [ ] Chọn lớp 10.
- [ ] Chọn lớp 11.
- [ ] Chọn lớp 12.
- [ ] Chế độ tự nhận diện.
- [ ] Dùng grade để chọn prompt.
- [ ] Dùng grade để giới hạn thuật ngữ.
- [ ] Dùng grade để chọn template hình.
- [ ] Hiển thị grade trong history.

---



# P1-06. Hiển thị tiến trình theo stage và cho phép hủy



## Hiện trạng

UI chủ yếu hiển thị:

```text
Đang dựng hình...
```

Trong khi backend có thể chạy tới hơn 300 giây.

## Checklist

- [ ] Đang phân tích đề.
- [ ] Đang chạy reasoning.
- [ ] Đang gọi model.
- [ ] Đang kiểm tra schema.
- [ ] Đang kiểm chứng CAS.
- [ ] Đang dựng renderer.
- [ ] Đang lưu lịch sử.
- [ ] Có nút hủy.
- [ ] Hủy request phía client.
- [ ] Hủy task phía server khi có thể.
- [ ] Không khóa toàn bộ workspace.
- [ ] Giữ kết quả stage đã hoàn thành.
- [ ] Retry renderer riêng.
- [ ] Retry extraction riêng.

---



# 9. Checklist P1 — Nâng cấp schema `MathScene`



## 9.1. Vấn đề hiện tại

`MathScene` chưa có cấu trúc đầy đủ cho:

- Interpretation.
- Assumptions.
- Missing facts.
- Provenance của object.
- ID ổn định.
- Construction steps.
- Verification report.
- Scene version.
- Renderer compatibility.
- User edit state.



## 9.2. Schema đề xuất

```json
{
  "scene_id": "scene_...",
  "schema_version": "2.0",
  "revision": 4,
  "problem_text": "...",
  "interpretation": {
    "objects": [],
    "relations": [],
    "values": [],
    "missing_data": [],
    "assumptions": []
  },
  "objects": [
    {
      "id": "obj_A",
      "type": "point_3d",
      "name": "A",
      "source": "given",
      "locked": true
    }
  ],
  "relations": [
    {
      "id": "rel_001",
      "type": "perpendicular",
      "source": "given",
      "verification": {
        "status": "verified",
        "method": "dot_product"
      }
    }
  ],
  "construction_steps": [],
  "renderer_compatibility": [],
  "view": {},
  "audit": {}
}
```



## Checklist

- [ ] `scene_id`.
- [ ] `schema_version`.
- [ ] `revision`.
- [ ] Object ID độc lập với tên hiển thị.
- [ ] Relation ID.
- [ ] Annotation ID.
- [ ] `source`.
- [ ] `locked`.
- [ ] `user_edited`.
- [ ] `assumptions`.
- [ ] `missing_data`.
- [ ] `construction_steps`.
- [ ] `verification_report`.
- [ ] `renderer_compatibility`.
- [ ] `created_by`.
- [ ] `updated_at`.
- [ ] `generator_provider`.
- [ ] `generator_model`.
- [ ] `generator_prompt_version`.

---



# 10. Checklist P1 — Scene editor



# P1-07. Thêm object tree

```text
Scene
├── Điểm
├── Đường
├── Đoạn
├── Vectơ
├── Mặt
├── Mặt phẳng
├── Khối
├── Quan hệ
├── Chú thích
└── Đối tượng phụ
```



## Checklist

- [ ] Chọn object từ tree.
- [ ] Highlight trên canvas.
- [ ] Ẩn/hiện.
- [ ] Khóa/mở khóa.
- [ ] Đổi tên.
- [ ] Xóa.
- [ ] Nhân bản.
- [ ] Xem dependency.
- [ ] Xem relation liên quan.
- [ ] Filter theo source.
- [ ] Filter theo verification status.

---



# P1-08. Thêm property panel



## Điểm

- [ ] Tên.
- [ ] Tọa độ.
- [ ] Biểu thức tham số.
- [ ] Source.
- [ ] Locked.
- [ ] Label position.
- [ ] Màu.
- [ ] Kích thước.



## Segment/line

- [ ] Điểm đầu/cuối.
- [ ] Kiểu nét.
- [ ] Màu.
- [ ] Độ dày.
- [ ] Hidden edge.
- [ ] Độ dài.
- [ ] Relation.



## Face/plane

- [ ] Danh sách điểm.
- [ ] Màu.
- [ ] Opacity.
- [ ] Normal.
- [ ] Visibility.
- [ ] Planarity status.



## Checklist chung

- [ ] Preview trước khi commit.
- [ ] Validate tại client.
- [ ] Validate tại server.
- [ ] Hiển thị object bị ảnh hưởng.
- [ ] Không âm thầm phá relation.

---



# P1-09. Undo, redo và transaction



## Checklist

- [ ] Undo.
- [ ] Redo.
- [ ] Phím tắt.
- [ ] Batch edit.
- [ ] Cancel edit.
- [ ] Snapshot trước auto-fix.
- [ ] Rollback auto-fix.
- [ ] Diff trước/sau.
- [ ] Không gọi backend cho mỗi thay đổi nhỏ.
- [ ] Commit khi thả điểm hoặc bấm lưu.
- [ ] Autosave sau debounce.

---



# P1-10. Tách công cụ dựng hình theo ngữ cảnh



## Khi chọn hai điểm

- [ ] Tạo đoạn.
- [ ] Tạo đường.
- [ ] Tạo vector.
- [ ] Trung điểm.
- [ ] Đo khoảng cách.



## Khi chọn điểm và đường

- [ ] Hình chiếu lên đường.
- [ ] Hình chiếu lên đoạn.
- [ ] Đường song song.
- [ ] Đường vuông góc.
- [ ] Khoảng cách.



## Khi chọn điểm và mặt phẳng

- [ ] Hình chiếu.
- [ ] Đường vuông góc.
- [ ] Mặt phẳng song song.
- [ ] Khoảng cách.



## Khi chọn hai đường

- [ ] Giao điểm.
- [ ] Góc.
- [ ] Khoảng cách chéo nhau.
- [ ] Kiểm tra song song.
- [ ] Kiểm tra vuông góc.

---



# 11. Checklist P1 — CAS và kiểm chứng



# P1-11. Tách validation, verification và repair



## Đề xuất

```text
validate
→ verify
→ report
→ user decides
→ repair
→ verify again
```

Không nên mặc định:

```text
verify
→ tự sửa
→ chỉ báo đã chuẩn hóa
```



## Checklist

- [ ] Validation report riêng.
- [ ] Verification report riêng.
- [ ] Repair proposal riêng.
- [ ] User confirmation.
- [ ] Repair diff.
- [ ] Verify lại sau repair.
- [ ] Lưu cả original và repaired scene.
- [ ] Không sửa dữ kiện given.
- [ ] Không gọi unresolved issue là normalized.

---



# P1-12. Hiển thị báo cáo kiểm chứng

```text
Kiểm chứng scene

✓ 12/12 object hợp lệ
✓ 18/18 reference hợp lệ
✓ SA ⟂ (ABCD)
△ H là điểm giả định
? Quan hệ tiếp tuyến chưa kiểm chứng được
✕ AB không bằng BC
```



## Checklist

- [ ] Object validation.
- [ ] Reference validation.
- [ ] Relation verification.
- [ ] Annotation validation.
- [ ] Parameter validation.
- [ ] Renderer compatibility.
- [ ] Auto-fix summary.
- [ ] Unsupported relation.
- [ ] Verification error.
- [ ] Cho click vào item để highlight object.

---



# 12. Checklist P1 — GeoGebra renderer



# P1-13. Không khởi tạo lại applet khi mở bảng đại số



## Hiện trạng

State `showAlgebraPanel` tham gia dependency khởi tạo applet.

## Checklist

- [ ] Dùng API thay đổi perspective tại runtime.
- [ ] Không inject applet mới.
- [ ] Không reset scene.
- [ ] Không mất camera.
- [ ] Không mất selection.
- [ ] Không mất object user vừa kéo.
- [ ] Test toggle liên tục.

---



# P1-14. Cải thiện auto-fit 2D



## Hiện trạng

Auto-fit chủ yếu dựa vào:

- Point 2D.
- Circle có radius explicit.

Chưa bao phủ đầy đủ:

- Function graph.
- Line vô hạn.
- Vector.
- Circle qua điểm.
- Annotation.
- Intersection.



## Checklist

- [ ] Fit point.
- [ ] Fit circle by radius.
- [ ] Fit circle by through point.
- [ ] Fit vector.
- [ ] Fit function theo domain.
- [ ] Fit conic.
- [ ] Có nút reset view.
- [ ] Có preset view.
- [ ] Không zoom quá xa vì outlier.

---



# P1-15. Xử lý command error tốt hơn

- [ ] Nhóm command theo object.
- [ ] Chỉ rõ object gây lỗi.
- [ ] Cho retry command.
- [ ] Không reset toàn bộ nếu một style command lỗi.
- [ ] Phân biệt object creation và side-effect.
- [ ] Ghi command compatibility theo app mode.
- [ ] Fallback renderer nếu phù hợp.
- [ ] Không hiển thị raw command cho người dùng phổ thông.

---



# 13. Checklist P1 — Three.js renderer



# P1-16. Camera và góc nhìn



## Checklist

- [ ] Perspective.
- [ ] Orthographic.
- [ ] View front.
- [ ] View back.
- [ ] View left.
- [ ] View right.
- [ ] View top.
- [ ] View bottom.
- [ ] Isometric.
- [ ] Reset camera.
- [ ] Fit all.
- [ ] Lock camera.
- [ ] Save camera preset.
- [ ] Camera state trong URL hoặc scene version.

---



# P1-17. Cạnh khuất



## Hiện trạng

Three.js tính hidden edge động theo hướng camera và face normals.

Tuy nhiên:

- `segment.hidden` không được dùng trực tiếp trong logic dashed quan sát được.
- Cạnh phụ và cạnh thuộc khối có quy tắc khác nhau.
- GeoGebra lại xử lý `hidden=true` bằng cách ẩn hoàn toàn.



## Checklist

- [ ] Thống nhất semantic `hidden`.
- [ ] Tách `visibility`.
- [ ] Tách `occlusion_style`.
- [ ] Hỗ trợ `visible`.
- [ ] Hỗ trợ `dashed_when_hidden`.
- [ ] Hỗ trợ `always_dashed`.
- [ ] Hỗ trợ `hidden`.
- [ ] Đồng bộ GeoGebra và Three.js.
- [ ] Không dùng cùng một boolean cho nhiều ý nghĩa.
- [ ] Test khi xoay camera.
- [ ] Test khối lõm.
- [ ] Test mặt không khép kín.

---



# P1-18. Hiệu năng Three.js



## Hiện trạng cần lưu ý

- `preserveDrawingBuffer` bật thường trực.
- Hidden-edge computation chạy trong `useFrame`.
- Hidden set được tính lại theo frame.
- Sphere có độ chia lưới khá cao.
- Label dùng nhiều text object.



## Checklist

- [ ] Chỉ bật preserve buffer lúc export nếu có thể.
- [ ] Chỉ tính hidden edge khi camera thay đổi.
- [ ] Debounce computation.
- [ ] Cache face data.
- [ ] Giới hạn số label.
- [ ] LOD cho sphere.
- [ ] Frameloop demand khi scene đứng yên.
- [ ] Dispose geometry.
- [ ] Dispose material.
- [ ] Dispose texture.
- [ ] Theo dõi FPS.
- [ ] Chế độ chất lượng thấp.
- [ ] Test thiết bị tích hợp GPU yếu.

---



# P1-19. Label layout

- [ ] Tránh chồng nhãn.
- [ ] Offset theo camera.
- [ ] Cho kéo label.
- [ ] Khóa label.
- [ ] Ẩn label phụ.
- [ ] Culling label xa.
- [ ] Không để label xuyên mặt.
- [ ] Có chế độ trình chiếu.
- [ ] Có chế độ đen trắng.

---



# 14. Checklist P1 — Export



# P1-20. Đồng bộ format frontend và backend

Backend đã có:

- TikZ.
- GGB.
- PDF.
- PNG.
- JPG.
- SVG.
- HTML KaTeX.

Frontend hiện chưa đưa GGB và PDF vào menu chính.

## Checklist

- [ ] Thêm PDF.
- [ ] Thêm GGB.
- [ ] Thêm JSON MathScene.
- [ ] Thêm file scene package.
- [ ] Kiểm tra quyền/quota export riêng.
- [ ] Không chặn export chỉ vì hết quota AI nếu scene đã có.

---



# P1-21. Không gọi raster snapshot là vector hoặc interactive



## Hiện trạng

Với Three.js:

- SVG có thể chỉ chứa ảnh PNG nhúng.
- HTML có thể chỉ chứa ảnh PNG.
- Không phải SVG hình học thật.
- Không phải HTML 3D tương tác.



## Checklist

- [ ] Ghi nhãn `SVG chứa ảnh raster` nếu giữ cách hiện tại.
- [ ] Ghi nhãn `HTML tĩnh`.
- [ ] Hoặc xây SVG vector projection thật.
- [ ] Hoặc export HTML Three.js tương tác thật.
- [ ] Không quảng bá “phóng to không vỡ” với SVG raster.
- [ ] Không quảng bá “tương tác” với HTML ảnh tĩnh.

---



# P1-22. Preview export

- [ ] Preview vùng xuất.
- [ ] Crop khoảng trắng.
- [ ] Nền trắng.
- [ ] Nền trong suốt.
- [ ] Độ phân giải.
- [ ] Tỉ lệ khung.
- [ ] Kích thước trang.
- [ ] Bật/tắt axes.
- [ ] Bật/tắt grid.
- [ ] Bật/tắt label.
- [ ] Bật/tắt warning.
- [ ] Preset Word.
- [ ] Preset PowerPoint.
- [ ] Preset A4.
- [ ] Preset bài giảng.
- [ ] Kiểm tra font trước export.

---



# 15. Checklist P1 — History và versioning



## Checklist

- [ ] Phân biệt `AI render`.
- [ ] Phân biệt `scene edit`.
- [ ] Phân biệt `autosave`.
- [ ] Phân biệt `manual snapshot`.
- [ ] Group các revision của cùng scene.
- [ ] Hiển thị diff.
- [ ] Khôi phục revision.
- [ ] Đặt tên revision.
- [ ] Pin revision.
- [ ] Xóa cả scene hoặc một revision.
- [ ] Không tạo history rác.
- [ ] Lưu advisory.
- [ ] Lưu CAS report.
- [ ] Lưu provider/model.
- [ ] Lưu schema version.
- [ ] Lưu prompt version.
- [ ] Không mất top-level advisory khi mở lại history.

---



# 16. Checklist P1 — Accessibility và responsive



## Checklist

- [ ] Focus trap cho scene editor dialog.
- [ ] Đóng dialog bằng Escape.
- [ ] Trả focus về nút mở.
- [ ] Object tree dùng keyboard.
- [ ] Canvas có mô tả văn bản.
- [ ] Công cụ 3D có hướng dẫn không phụ thuộc chuột.
- [ ] Không chỉ dùng màu để phân biệt source/status.
- [ ] Nút đủ lớn trên mobile.
- [ ] Không phụ thuộc context menu để dùng OCR.
- [ ] Có alternative cho drag-and-drop.
- [ ] Có reduced motion.
- [ ] Có high contrast.
- [ ] Có aria-live cho tiến trình.
- [ ] Có lỗi gắn với input tương ứng.
- [ ] Mobile editor không che canvas.
- [ ] Tablet có split view.

---



# 17. Checklist P1 — Security và privacy



## Checklist

- [ ] Validate MIME bằng nội dung, không chỉ `file.type`.
- [ ] Scan file upload.
- [ ] Xóa file OCR theo retention.
- [ ] Không công khai URL upload nếu không cần.
- [ ] Giới hạn kích thước ảnh.
- [ ] Giới hạn pixel count.
- [ ] Chống decompression bomb.
- [ ] Redact API key trong log.
- [ ] Không gửi runtime API key từ client phổ thông.
- [ ] CSP cho GeoGebra CDN.
- [ ] SRI hoặc self-host khi phù hợp.
- [ ] Sanitize HTML export.
- [ ] Sanitize TikZ label.
- [ ] Giới hạn expression complexity.
- [ ] Giới hạn số object.
- [ ] Giới hạn số intersection pair.
- [ ] Giới hạn số annotation.
- [ ] Rate limit export riêng.
- [ ] Không ghi problem text nhạy cảm quá mức.

---



# 18. Checklist P2 — Giá trị học tập



# P2-01. Dựng hình từng bước

- [ ] Construction timeline.
- [ ] Bước trước.
- [ ] Bước sau.
- [ ] Auto play.
- [ ] Highlight object mới.
- [ ] Giải thích mục đích bước.
- [ ] Xuất từng bước.
- [ ] Chế độ giáo viên.
- [ ] Chế độ học sinh.

---



# P2-02. Giải thích quan hệ

Khi chọn một relation:

```text
SA ⟂ (ABCD)

Nguồn:
Đề bài cho.

Kiểm chứng:
Vector SA song song với pháp tuyến của mặt phẳng.

Trạng thái:
Đã kiểm chứng.

Hệ quả:
SA ⟂ AB
SA ⟂ AD
```



## Checklist

- [ ] Source.
- [ ] Evidence.
- [ ] Verification method.
- [ ] Direct consequences.
- [ ] Link tới solver step.
- [ ] Không dùng AI cho hệ quả chưa kiểm chứng.

---



# P2-03. Chia sẻ scene tương tác

- [ ] Permalink.
- [ ] Public/private.
- [ ] Read-only.
- [ ] Copy allowed.
- [ ] Edit allowed.
- [ ] Expiration.
- [ ] Revoke.
- [ ] Embed.
- [ ] LMS.
- [ ] Thumbnail.
- [ ] Không lộ prompt nội bộ.
- [ ] Không lộ model config.

---



# P2-04. Cộng tác

- [ ] Multi-user edit.
- [ ] Presence.
- [ ] Comment gắn object.
- [ ] Conflict resolution.
- [ ] Audit log.
- [ ] Teacher approval.
- [ ] Assignment mode.

---



# 19. Kiến trúc mục tiêu đề xuất

```text
ProblemInput
   ↓
InputInterpreter
   ↓
InterpretationSpec
   ↓
UserConfirmation
   ↓
SceneGenerator
   ↓
SchemaValidator
   ↓
SemanticValidator
   ↓
RelationVerifier
   ↓
RepairProposal
   ↓
UserApproval
   ↓
RendererAdapter
   ↓
SceneWorkspace
   ↓
Export / Solve / Variants / Share
```



## 19.1. Nguyên tắc

- AI không phải nguồn sự thật cuối cùng.
- Không có issue không đồng nghĩa verified.
- Auto-fix không được thay đổi dữ kiện gốc.
- Renderer chỉ hiển thị scene đã tương thích.
- Mọi edit phải làm invalid các verification liên quan.
- Mọi verification phải gắn với relation ID.
- Mock/fallback phải được công khai.
- History phải quản lý revision, không quản lý từng thao tác.

---



# 20. State machine đề xuất

```text
draft
→ interpreting
→ needs_confirmation
→ generating
→ validating
→ verification_pending
→ verified
→ partially_verified
→ repair_proposed
→ user_edited
→ revalidating
→ ready
→ exported
```

Trạng thái lỗi:

```text
input_invalid
ambiguous
unsupported
generation_failed
schema_invalid
semantic_invalid
verification_failed
renderer_failed
timeout
```

---



# 21. Thiết kế response đề xuất

```json
{
  "status": "partially_verified",
  "source": {
    "kind": "ai",
    "provider": "router9",
    "model": "model-id",
    "fallback_used": false
  },
  "interpretation": {
    "objects": [],
    "relations": [],
    "assumptions": [],
    "missing_data": []
  },
  "scene": {},
  "validation": {
    "status": "passed",
    "errors": [],
    "warnings": [],
    "repairs": []
  },
  "verification": {
    "status": "partial",
    "relations": []
  },
  "payload": {},
  "advisory": {},
  "requires_user_confirmation": false
}
```

---



# 22. Test matrix bắt buộc



## 22.1. Input

- [ ] Đề 2D rõ ràng.
- [ ] Đề 3D rõ ràng.
- [ ] Đề thiếu dữ kiện.
- [ ] Đề mâu thuẫn.
- [ ] Đề nhiều cách hiểu.
- [ ] Đề dài.
- [ ] Đề có LaTeX.
- [ ] Đề có Unicode toán.
- [ ] Đề có nhiều câu nhưng chỉ một yêu cầu vẽ.



## 22.2. OCR

- [ ] Ảnh rõ.
- [ ] Ảnh mờ.
- [ ] Ảnh xoay.
- [ ] Ảnh có hình.
- [ ] Ảnh có nhiều cột.
- [ ] Công thức.
- [ ] Ký hiệu vuông góc.
- [ ] Ký hiệu song song.
- [ ] Tên điểm dễ nhầm.



## 22.3. Provider fallback

- [ ] Candidate đầu timeout.
- [ ] Candidate đầu sai schema.
- [ ] Candidate đầu sai semantic.
- [ ] Candidate thứ hai thành công.
- [ ] Tất cả candidate lỗi.
- [ ] Mock fallback.
- [ ] Router-only.
- [ ] Tier không có model.



## 22.4. Validator

- [ ] Trùng tên.
- [ ] Thiếu reference.
- [ ] Sai dimension.
- [ ] Radius âm.
- [ ] Face suy biến.
- [ ] Plane không đồng phẳng.
- [ ] Parameter lỗi.
- [ ] Relation unsupported.
- [ ] Annotation unsupported.



## 22.5. CAS

- [ ] Perpendicular.
- [ ] Parallel.
- [ ] Equal length.
- [ ] Midpoint.
- [ ] Collinear.
- [ ] Coplanar.
- [ ] On line.
- [ ] On segment.
- [ ] On plane.
- [ ] On sphere.
- [ ] On circle.
- [ ] Tangent.
- [ ] Distance.
- [ ] Angle.
- [ ] Ratio.
- [ ] Parallel planes.
- [ ] Perpendicular planes.
- [ ] Verifier exception.
- [ ] Missing evidence.



## 22.6. Scene edit

- [ ] Kéo điểm phá relation.
- [ ] Kéo điểm sửa relation.
- [ ] Thêm điểm.
- [ ] Xóa điểm.
- [ ] Nối đoạn.
- [ ] Hình chiếu.
- [ ] Giao điểm 2D.
- [ ] Giao điểm 3D.
- [ ] Vector đối.
- [ ] Parameter rồi edit.
- [ ] Undo.
- [ ] Redo.
- [ ] Autosave.
- [ ] Revision.



## 22.7. Renderer

- [ ] GeoGebra 2D.
- [ ] GeoGebra 3D.
- [ ] Three.js.
- [ ] Ép renderer sai.
- [ ] CDN GeoGebra lỗi.
- [ ] WebGL không có.
- [ ] Nhiều object.
- [ ] Nhiều label.
- [ ] Camera rotate.
- [ ] Hidden edge.
- [ ] Responsive resize.



## 22.8. Export

- [ ] PNG.
- [ ] JPG.
- [ ] SVG.
- [ ] PDF.
- [ ] GGB.
- [ ] HTML.
- [ ] TikZ.
- [ ] JSON.
- [ ] Three current view.
- [ ] Nền trong suốt.
- [ ] Label tiếng Việt.
- [ ] Công thức.
- [ ] Scene lớn.

---



# 23. Lộ trình triển khai



## Giai đoạn 1 — Sửa tính đúng và trust boundary

- [ ] P0-01 mock fallback.
- [ ] P0-02 fallback candidate.
- [ ] P0-03 renderer validation.
- [ ] P0-04 revalidate scene edit.
- [ ] P0-05 projection tool.
- [ ] P0-06 relation registry.
- [ ] P0-07 verification result.
- [ ] P0-08 verifier exception.
- [ ] P0-09 on-plane inference.
- [ ] P0-10 auto-fix limits.



## Giai đoạn 2 — Quản lý edit và history

- [ ] P0-11 history/quota.
- [ ] P0-12 active scene.
- [ ] Undo/redo.
- [ ] Revision.
- [ ] Autosave.
- [ ] Object tree.
- [ ] Property panel.



## Giai đoạn 3 — Interpretation và UX

- [ ] Confirmation step.
- [ ] Assumptions.
- [ ] Missing data.
- [ ] OCR review.
- [ ] Grade.
- [ ] Progress stages.
- [ ] Cancel.



## Giai đoạn 4 — Renderer và export

- [ ] GeoGebra runtime update.
- [ ] 2D auto-fit.
- [ ] Camera preset.
- [ ] Orthographic.
- [ ] Hidden-edge semantics.
- [ ] Three performance.
- [ ] PDF/GGB frontend.
- [ ] Export preview.



## Giai đoạn 5 — Học tập và chia sẻ

- [ ] Construction timeline.
- [ ] Relation explanation.
- [ ] Teacher mode.
- [ ] Share scene.
- [ ] Embed.
- [ ] Collaboration.

---



# 24. Tiêu chí hoàn thành phiên bản ổn định đầu tiên

Phiên bản mới chỉ nên được xem là ổn định khi:

- [ ] Mock fallback không bị trình bày như AI render thành công.
- [ ] Validation failure tiếp tục thử model dự phòng.
- [ ] Renderer và dimension luôn tương thích.
- [ ] Scene edit được semantic validate và CAS verify lại.
- [ ] Công cụ hình chiếu tạo đúng chân vuông góc.
- [ ] Relation registry được đồng bộ.
- [ ] Mỗi relation có verification status riêng.
- [ ] Verifier exception không trở thành pass.
- [ ] Auto-fix không di chuyển điểm given hoặc user-edited.
- [ ] History không tạo một item cho mọi thao tác kéo.
- [ ] Edit, solve và export dùng cùng active scene.
- [ ] Người dùng thấy cách AI hiểu đề.
- [ ] Người dùng thấy giả định và dữ kiện thiếu.
- [ ] Người dùng phân biệt hình minh họa và hình kiểm chứng.
- [ ] Có object tree.
- [ ] Có property panel.
- [ ] Có undo/redo.
- [ ] Có versioning.
- [ ] Có progress theo stage.
- [ ] Có cancel.
- [ ] GeoGebra không reload khi mở panel.
- [ ] Three.js có reset và camera preset.
- [ ] Export frontend có PDF và GGB.
- [ ] SVG/HTML được ghi đúng bản chất.
- [ ] Có test end-to-end cho luồng chính.
- [ ] Có test tái hiện tất cả lỗi P0.

---



# 25. Mười hạng mục ưu tiên cao nhất

```text
1. Không trả mock scene như kết quả thành công
2. Chạy lại semantic validator và CAS sau scene edit
3. Sửa công cụ tạo chân vuông góc
4. Chạy compatibility validation sau renderer override
5. Thiết kế verification theo từng relation ID
6. Đồng bộ relation allowlist giữa validator và CAS
7. Giới hạn và minh bạch auto-fix
8. Tách scene revision khỏi render history/quota
9. Thêm bước xác nhận cách AI hiểu đề
10. Thêm object tree, property panel và undo/redo
```

---



# 26. Kết luận

`/render` hiện có nền tảng kỹ thuật mạnh:

- Multi-renderer.
- Schema chung.
- Semantic validation.
- CAS verification.
- Auto-fix.
- Scene editing.
- Export.
- Solver.
- History.

Tuy nhiên, hệ thống hiện ưu tiên “có hình để hiển thị” hơn “hình được chứng minh là phản ánh đúng đề”. Điều này thể hiện ở:

- Mock fallback.
- Drop relation/object để scene render được.
- Auto-fix tương đối mạnh.
- Xác nhận verification dựa trên absence of issue.
- Scene edit không được kiểm chứng lại đầy đủ.
- Không công khai cách AI hiểu đề.

Định hướng cần chuyển từ:

> Render-first.

sang:

> Interpretation-first, verification-aware, user-confirmed rendering.

Thứ tự triển khai phù hợp nhất:

```text
Độ đúng
→ Tính minh bạch
→ Kiểm chứng
→ Chỉnh sửa an toàn
→ Quản lý phiên bản
→ UX
→ Renderer
→ Export
→ Tính năng học tập
```

Không nên mở rộng thêm nhiều object hoặc quan hệ mới trước khi hoàn thiện trust boundary giữa AI, validator, CAS và người dùng.