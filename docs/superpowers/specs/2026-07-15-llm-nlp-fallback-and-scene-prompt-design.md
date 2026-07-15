# Thiết kế LLM NLP fallback và nâng chất lượng prompt dựng hình

## 1. Mục tiêu

Thay đổi này giải quyết hai vấn đề liên quan trực tiếp:

1. Tăng độ chính xác và độ đầy đủ của prompt dựng `MathSceneV3`, đặc biệt với đề hình học mô tả tự nhiên, dữ kiện ẩn, topology khối, điểm phụ và đại lượng cần minh họa.
2. Cho phép LLM hỗ trợ lớp NLP chung khi rule-based không hiểu đủ đầu vào, nhưng giữ fast path deterministic cho đầu vào rõ ràng.

Thay đổi phải giữ nguyên các public contract hiện có, không cho LLM giải toán thay mathcore và không cho người chưa đăng nhập sử dụng LLM NLP.

## 2. Phạm vi

Các target NLP được hỗ trợ:

- `render`
- `geometry_solve`
- `algebra`
- `analyzer`
- `ocr`

Các thành phần bị ảnh hưởng:

- Prompt mặc định cho Scene v3 và reasoning.
- NLP pipeline, adapter và route `/api/nlp/interpret`.
- NLP rollout tại các endpoint render, giải hình học, Đại số và phân tích hàm.
- `feature_flags` trong `system_settings`.
- Admin Settings và test backend/frontend liên quan.

Không thay đổi schema database vật lý vì `system_settings.value_json` đã hỗ trợ field mới theo cách tương thích ngược.

## 3. Quyết định sản phẩm đã chốt

- Thêm đúng một tùy chọn admin: `nlp_llm_fallback_enabled`.
- Giá trị mặc định là `false`.
- LLM chỉ được gọi khi rule-based yếu; không gọi cho mọi request.
- Người chưa đăng nhập luôn chỉ dùng rule-based, kể cả khi admin đã bật cờ.
- Nếu LLM lỗi, timeout, sai schema hoặc không vượt qua validation, hệ thống giữ kết quả rule-based và tiếp tục hoạt động.

## 4. Kiến trúc NLP

### 4.1. Orchestrator async

Giữ `interpret_input()` đồng bộ làm engine rule-based thuần để không phá test và caller hiện tại. Bổ sung một orchestrator async ở service layer, chịu trách nhiệm:

1. Chạy `interpret_input()` để lấy baseline deterministic.
2. Kiểm tra điều kiện gọi LLM.
3. Gọi LLM adapter nếu đủ điều kiện.
4. Validate và chuyển output LLM thành `InterpretationCandidate` theo contract hiện tại.
5. Chọn candidate cuối cùng bằng cùng quy tắc confidence, ambiguity và missing field.
6. Trả `InterpretationResponse` có `adapter_version` thể hiện pipeline hybrid khi LLM đã thực sự tham gia.

Route và rollout có context database/user sẽ dùng orchestrator async. Các unit test hoặc caller cần kết quả deterministic thuần tiếp tục dùng `interpret_input()`.

### 4.2. Điều kiện gọi LLM

LLM chỉ được gọi khi đồng thời thỏa tất cả điều kiện:

- `nlp_llm_fallback_enabled = true`.
- Có user đã xác thực.
- Kết quả rule-based không phải `unsupported` do prompt injection hoặc ngoài phạm vi rõ ràng.
- Có ít nhất một tín hiệu yếu:
  - status là `needs_confirmation` hoặc `abstained`;
  - không có candidate được hỗ trợ;
  - candidate được chọn có confidence dưới `0.80`;
  - intent/topic/task là `unknown`;
  - có `missing_fields` hoặc `ambiguities`.

Đầu vào structured, symbolic hoặc rule-based có confidence từ `0.80` trở lên và không có ambiguity/missing field sẽ trả ngay, không phát sinh chi phí LLM.

### 4.3. Model và provider

LLM NLP sử dụng task profile canonical `reasoning` hiện có. Lý do:

- Không tạo thêm một vùng cấu hình model ngoài yêu cầu một option admin.
- Task profile này đã có provider/model/fallback và allowlist được kiểm tra.
- NLP extraction cần khả năng hiểu và cấu trúc hóa, phù hợp hơn profile giải thích hoặc render.

Provider/model thực tế phải được ghi vào `Provenance(source="language_model")`, nhưng không đưa input hoặc canonical payload nhạy cảm vào log telemetry.

### 4.4. Contract output nội bộ của LLM

LLM chỉ trả JSON extraction, không trả đáp án hoặc bước giải. Schema nội bộ gồm:

- target đã chọn;
- intent gồm domain, topic, task, subtype;
- canonical text;
- entities;
- constraints;
- assumptions;
- ambiguities;
- missing fields;
- clarification question;
- confidence theo từng field;
- evidence ngắn cho các dữ kiện được trích xuất.

Schema dùng `extra="forbid"`, giới hạn số phần tử và chiều dài tương tự public NLP schema. Output phải đi qua `gate_llm_json_output` và Pydantic validation.

Server không tin trực tiếp `canonical_payload` tùy ý từ LLM. Payload cho từng target được dựng hoặc kiểm tra lại ở adapter:

- `algebra`: dùng `AlgebraSolveRequest`, safe normalizer và contract merge hiện có; field explicit của user luôn thắng.
- `analyzer`: biểu thức phải qua `parse_safe_math_expression`.
- `geometry_solve`: goal phải qua `GeometryGoal`; object ID chỉ được lấy từ catalog scene đã gửi trong context.
- `render`: LLM candidate chỉ tạo NLP hints; không thay `problem_text` nguyên bản.
- `ocr`: giữ provenance OCR, confidence thấp nhất của OCR vẫn là giới hạn trên cho confidence cuối.

### 4.5. Hợp nhất và quyền ưu tiên

Thứ tự tin cậy:

1. Context explicit do user chọn hoặc hệ thống đã xác nhận.
2. Dữ kiện deterministic/rule-based có bằng chứng trực tiếp.
3. LLM extraction có schema hợp lệ và evidence phù hợp.
4. Assumption của LLM.

LLM không được:

- Ghi đè domain, method, topic hoặc biến mà user đã chọn rõ ràng.
- Tạo scene object ID không tồn tại.
- Biến assumption thành given constraint.
- Tự thêm nghiệm, đáp án, số đo hoặc kết luận toán học.
- Làm một kết quả `unsupported` do security trở thành accepted.

Khi LLM và rule-based mâu thuẫn ở field explicit, giữ rule/context và thêm ambiguity hoặc warning nội bộ phù hợp.

## 5. Tích hợp theo luồng

### 5.1. `/api/nlp/interpret`

- Giữ request/response contract.
- Dùng `get_optional_current_user` hiện có để xác định quyền dùng LLM.
- Tải feature flag qua cache hiện có.
- Áp rate limit hiện tại; bổ sung bucket chặt hơn cho lượt LLM nếu cần để chi phí không phụ thuộc bucket rule-based.

### 5.2. Render

- `problem_text` luôn bất biến.
- Candidate hybrid chỉ được chuyển thành `nlp_hints` cho reasoning/extraction prompt.
- Không gọi LLM NLP nếu rule-based render đã đủ chắc chắn.
- Lỗi NLP fallback không được làm thất bại lượt render.

### 5.3. Giải hình học

- Canonical question và `GeometryGoal` chỉ được áp dụng khi candidate accepted.
- Target object IDs phải resolve duy nhất trong scene đang commit.
- Nếu resolve mơ hồ, yêu cầu xác nhận thay vì đoán.

### 5.4. Đại số

- Tái sử dụng extractor/merge contract hiện có thay vì tạo một LLM algebra path thứ hai.
- Khi orchestrator đã có canonical request hợp lệ, solver dùng kết quả đó để tránh gọi LLM lặp lại trong cùng request.
- Mathcore vẫn là nơi duy nhất giải và kiểm chứng.

### 5.5. Analyzer và OCR

- Analyzer chỉ nhận canonical expression đã qua safe parser.
- OCR giữ confidence/provenance từ OCR; LLM chỉ hiểu nội dung text sau OCR, không được nâng confidence vượt bằng chứng OCR.

## 6. Nâng chất lượng prompt dựng hình

Prompt Scene v3 hiện đã có schema, reference integrity, topology, style và self-check. Phần bổ sung tập trung vào các khoảng trống chất lượng thay vì lặp lại quy tắc cũ.

### 6.1. Quy trình nội bộ bắt buộc

Thêm pipeline suy luận rõ thứ tự, không xuất ra response:

1. Bảo toàn nguyên văn đề.
2. Phân loại domain, dimension và renderer.
3. Lập inventory `EXPLICIT_GIVENS`, `DERIVED_GIVENS`, `GOALS`, `UNKNOWNS`.
4. Chọn hệ tọa độ canonical nhưng không làm sai dữ kiện đã cho.
5. Dựng object graph với stable ID trước khi tạo reference.
6. Hoàn thiện topology khối.
7. Tạo construction phục vụ đúng goal.
8. Gắn provenance và phân biệt given/inferred/construction/render-only.
9. Chạy self-check về reference, hình học, topology, exact expression và tính đầy đủ thị giác.
10. Chỉ sau đó xuất một JSON object duy nhất.

### 6.2. Quy tắc chống dựng hình sai nhưng hợp schema

Bổ sung các bất biến:

- Schema hợp lệ chưa đủ; tọa độ phải đồng thời thỏa dữ kiện hình học quan trọng.
- Không chọn tọa độ làm biến dạng hình đặc biệt như hình vuông, tam giác đều, lăng trụ đứng hoặc chóp đều.
- Không dùng số thập phân gần đúng khi có thể biểu diễn exact bằng `*_expr`.
- Không tự suy ra giá trị của goal chưa biết để làm nhãn.
- Khi đề thiếu dữ kiện để xác định duy nhất, chọn một embedding minh họa hợp lệ và ghi assumption; không biến embedding thành dữ kiện toán học.
- Mọi construction phải có mục đích trực quan gắn với goal hoặc given; không thêm điểm phụ vô nghĩa.

### 6.3. Few-shot có chọn lọc

Giữ ví dụ hình hộp đầy đủ và bổ sung các ví dụ compact, mỗi ví dụ bảo vệ một failure mode khác nhau:

- Hình chóp có khoảng cách điểm-mặt: phân biệt goal với numeric relation và dựng chân chiếu.
- Hình phẳng có trung điểm/đường trung tuyến: tạo point, segment, relation và equal marks nhất quán.
- Đồ thị hàm có tham số: renderer 2D, expression, parameter và exact/default contract.
- Một anti-example ngắn chỉ ra output schema-valid nhưng sai vì thiếu cạnh/mặt hoặc bịa số đo goal.

Ví dụ phải ngắn, không nhân đôi toàn bộ schema và có regression test cho các token/contract quan trọng.

### 6.4. Prompt reasoning

Prompt reasoning được đồng bộ với Scene v3:

- Dùng stable object intent thay vì chỉ tên tự do khi có thể.
- Tách explicit, derived, goal và assumption.
- Không tính đáp án goal nếu nhiệm vụ chỉ cần lập kế hoạch dựng hình.
- Yêu cầu kiểm tra consistency giữa coordinates, relation, edge/face và annotation.
- Reasoning plan chỉ là gợi ý có cấu trúc; `problem_text` vẫn là nguồn chân lý.

### 6.5. Admin prompt override

Giữ cơ chế override hiện tại để không phá contract. Security prefix/suffix vẫn được server chèn bắt buộc. Khi override để trống, prompt mặc định mới được dùng. Không tự ghi đè nội dung prompt admin đã lưu.

## 7. Admin Settings

Trong form `Cờ tính năng`, thêm checkbox có label rõ ràng, ví dụ `Cho phép LLM hỗ trợ NLP khi rule-based yếu`.

Payload lưu:

```json
{
  "version": 3,
  "nlp_llm_fallback_enabled": false
}
```

Schema vẫn chấp nhận các record version cũ thông qua default `false`. Cờ này là nội bộ admin, không cần đưa vào public settings response cho client.

## 8. Bảo mật, chi phí và lỗi

- Input tiếp tục được bọc bằng `envelope_untrusted`.
- Prompt dùng `secure_system_prompt` với output mode JSON.
- Không gửi secret, raw provider config hoặc dữ liệu ngoài context cần thiết.
- Chỉ user đã xác thực được phép phát sinh lượt LLM NLP.
- Timeout ngắn hơn lượt render; khi hết thời gian phải fallback rule-based.
- Không retry vô hạn; dùng profile fallback có giới hạn.
- Telemetry chỉ ghi target, status, confidence bucket, adapter version, provider/model và lý do fallback dạng mã; không ghi raw input.
- Prompt injection bị chặn không được chuyển sang LLM fallback.

## 9. Kiểm thử

### 9.1. Unit test NLP

- Fast path không gọi LLM khi rule confidence cao.
- Gọi LLM khi confidence thấp, missing, ambiguity hoặc abstained.
- Không gọi LLM khi flag tắt.
- Không gọi LLM cho anonymous user.
- Không gọi LLM cho unsupported/security input.
- Output sai JSON/schema/security leak fallback rule-based.
- Provenance provider/model được gắn đúng.
- Explicit context thắng LLM.
- Algebra/analyzer/geometry payload bị từ chối khi không qua validator tương ứng.
- OCR confidence không bị nâng quá nguồn OCR.

### 9.2. Integration/API test

- `/api/nlp/interpret` giữ nguyên response contract.
- Authenticated + flag on + weak input sử dụng hybrid adapter.
- Anonymous + flag on vẫn rule-only.
- Feature flag lưu/đọc/cache invalidation đúng.
- Endpoint render, solve, algebra và analyzer dùng cùng orchestrator nhưng fallback an toàn khi provider lỗi.

### 9.3. Prompt regression test

- Prompt chứa pipeline inventory và các invariant mới.
- Các few-shot parse được hoặc phần JSON mẫu validate bằng schema tương ứng.
- Prompt override không bỏ được security boundary.
- `problem_text` bất biến.
- Không có ví dụ dạy model tạo dangling reference, thiếu topology hoặc goal metric giả.

### 9.4. Frontend

- Checkbox đồng bộ đúng khi settings được reload.
- Save gửi version/field mới và giữ các feature flag hiện tại.
- Disabled/saving state và label truy cập bằng keyboard/screen reader vẫn đúng convention form hiện tại.
- TypeScript build và các test hiện có không lỗi.

## 10. Tiêu chí hoàn thành

- Admin có thể bật/tắt LLM NLP fallback; mặc định tắt.
- Anonymous không phát sinh LLM NLP call.
- Đầu vào rõ ràng không phát sinh LLM NLP call.
- Đầu vào yếu của năm target có thể được LLM làm rõ theo cùng public response contract.
- Mọi lỗi LLM giữ được kết quả rule-based và không làm hỏng chức năng chính.
- Prompt Scene v3 và reasoning có thêm quy trình, invariant và few-shot bảo vệ các failure mode đã xác định.
- Test backend liên quan, frontend test/type-check/build và prompt regression đều thành công.

## 11. Rủi ro còn lại và kiểm soát

- LLM có thể tăng latency ở input yếu: giới hạn bằng trigger, timeout ngắn và fallback.
- Hai lượt LLM có thể xảy ra ở render hoặc Đại số: tránh bằng tái sử dụng candidate/canonical extraction trong cùng request, không gọi lại khi đã có kết quả hợp lệ.
- Prompt dài có thể chiếm context: chỉ thêm few-shot compact và loại bỏ nội dung trùng khi chỉnh sửa.
- Confidence của LLM không được hiệu chuẩn tuyệt đối: cap confidence, giữ confirmation khi thiếu evidence và không cho LLM vượt explicit context.
