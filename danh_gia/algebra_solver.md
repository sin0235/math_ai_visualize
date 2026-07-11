# CHECKLIST RÀ SOÁT VÀ CẢI TIẾN CHỨC NĂNG `/algebra-solver`

## 1. Thông tin tài liệu

- **Dự án:** AI Math Renderer
- **Chức năng:** `https://math-renderer.sin-studio.tech/algebra-solver`
- **Repository rà soát:** `sin0235/math_ai_visualize`
- **Nhánh rà soát gốc:** `product`
- **Ngày rà soát gốc:** 21/06/2026
- **Nhánh đối chiếu lại:** `deploy/product-oauth-clean`
- **Ngày đối chiếu lại:** 10/07/2026
- **Phương pháp:** Rà soát tĩnh mã nguồn frontend, API, schema, bộ diễn giải đầu vào, normalizer, parser, classifier, các solver deterministic, verifier, AI extraction, AI explanation và test hiện có.
- **Giới hạn:** Chưa chạy kiểm thử end-to-end toàn bộ trên production, chưa benchmark độ trễ hoặc tài nguyên với biểu thức cực lớn, chưa fuzz parser, chưa đánh giá xác suất đúng trên một bộ đề THPT chuẩn hóa quy mô lớn.
- **Phạm vi đối chiếu lại:** Bỏ qua multi-user interaction và chia sẻ; vẫn đánh giá lưu/export cá nhân, correctness, safety, UX một người dùng.
- **Kết luận đối chiếu 10/07/2026:** ~90% checklist vẫn phản ánh đúng codebase. Lệch chính: rate limit thô deterministic đã có; AI explainer giữ công thức deterministic khi match `index`; dự án có `safe_math_parser`/`expression_eval` ở analyzer nhưng algebra chưa tái sử dụng đầy đủ. Slice A (10/07/2026): variables default rỗng, AI merge explicit fields, safe parse `global_dict` + precheck, timeout deterministic.

---

# 2. Phạm vi rà soát

## 2.1. Frontend

- `frontend/src/components/AlgebraSolverPage.tsx`
- `frontend/src/components/algebra-solver/AlgebraInput.tsx`
- `frontend/src/components/algebra-solver/AlgebraResult.tsx`
- `frontend/src/components/algebra-solver/AlgebraStepList.tsx`
- `frontend/src/api/algebra.ts`
- `frontend/src/components/KatexSpan.tsx`

## 2.2. Backend API và schema

- `backend/app/api/routes_algebra_solve.py`
- `backend/app/schemas/algebra.py`

## 2.3. Pipeline xử lý

- `backend/app/services/algebra/service.py`
- `backend/app/services/algebra/interpreter.py`
- `backend/app/services/algebra/normalizer.py`
- `backend/app/services/algebra/parser.py`
- `backend/app/services/algebra/classifier.py`
- `backend/app/services/algebra/domain.py`
- `backend/app/services/algebra/formatting.py`
- `backend/app/services/algebra/verifier.py`
- `backend/app/services/algebra/ai_extraction.py`
- `backend/app/services/algebra/ai_explainer.py`

## 2.4. Các solver

- `equation_solver.py`
- `inequality_solver.py`
- `exp_log_solver.py`
- `trig_solver.py`
- `system_solver.py`
- `complex_solver.py`
- `sequence_solver.py`
- `combinatorics_probability_solver.py`
- `parameter_solver.py`
- `calculus_solver.py`
- `expression_solver.py`

## 2.5. Test

- `test_routes_algebra_solve.py`
- `test_algebra_parser.py`
- `test_algebra_interpreter.py`
- `test_algebra_equation_solver.py`
- `test_algebra_inequality_solver.py`
- `test_algebra_exp_log_solver.py`
- `test_algebra_trig_solver.py`
- `test_algebra_system_solver.py`
- `test_algebra_complex_solver.py`
- `test_algebra_sequence_solver.py`
- `test_algebra_parameter_solver.py`
- `test_algebra_calculus_solver.py`
- `test_algebra_combinatorics_solver.py`
- `test_algebra_domain.py`
- `test_algebra_verifier.py`
- `test_algebra_ai_explainer.py`

---

# 3. Mục tiêu cải tiến

Nâng cấp `/algebra-solver` từ một giao diện:

```text
Nhập đề
→ Chuẩn hóa
→ SymPy giải
→ Sinh lời giải
→ Hiển thị đáp án
```

thành một hệ thống giải Toán THPT có thể:

```text
Nhập đề
→ Công khai cách hiểu đề
→ Xác nhận biến, tham số, miền và khoảng
→ Phân loại dạng toán
→ Lập kế hoạch giải
→ Giải deterministic
→ Kiểm chứng độc lập
→ Phân biệt chính xác / một phần / chưa kiểm chứng
→ Giải thích từng phép biến đổi
→ Cho phép sửa cách hiểu và giải lại
→ Lưu/xuất cá nhân và tạo bài tương tự
```

> Ghi chú phạm vi: chia sẻ multi-user / collab thuộc P2 và nằm ngoài đợt nâng cấp hiện tại. Ưu tiên lưu/export cá nhân, correctness và safety.

Nguyên tắc cốt lõi:

> AI chỉ được hỗ trợ diễn giải ngôn ngữ và diễn đạt lời giải. Đáp án, điều kiện, phép biến đổi và trạng thái kiểm chứng phải do pipeline deterministic có kiểm soát quyết định.

---

# 4. Quy ước mức ưu tiên

| Mức | Ý nghĩa |
|---|---|
| **P0** | Có thể làm sai đáp án, thiếu nghiệm, sai miền, báo “đã kiểm chứng” không đúng, gây rủi ro bảo mật hoặc làm cạn tài nguyên hệ thống. |
| **P1** | Cần thiết để nâng chất lượng sản phẩm, độ minh bạch, trải nghiệm học tập, khả năng bảo trì và mở rộng. |
| **P2** | Tính năng nâng cao phục vụ giáo viên, học sinh, cộng tác, luyện tập và tích hợp hệ sinh thái. |

Quy ước trạng thái:

```text
[ ] Chưa thực hiện
[-] Đang thực hiện
[x] Đã hoàn thành
[~] Đúng một phần / đã giảm rủi ro (còn gap)
[!] Cần quyết định sản phẩm hoặc kiến trúc
```

---

# 5. Đánh giá tổng quan

## 5.1. Điểm mạnh hiện tại

- [x] Có kiến trúc solver deterministic tách khỏi LLM.
- [x] Có interpreter tiếng Việt theo rule.
- [x] Có AI extraction tùy chọn.
- [x] Có normalizer cho plain text, Unicode và một phần LaTeX.
- [x] Có MathQuill để nhập công thức.
- [x] Có KaTeX để hiển thị kết quả.
- [x] Có schema response tương đối giàu thông tin.
- [x] Có lời giải từng bước.
- [x] Có điều kiện xác định cho nhiều phương trình.
- [x] Có thay nghiệm để kiểm tra nghiệm hữu hạn.
- [x] Có xử lý nghiệm ngoại lai cho một số phương trình căn/phân thức.
- [x] Có solver cho phương trình.
- [x] Có solver cho bất phương trình.
- [x] Có solver mũ-log.
- [x] Có solver lượng giác.
- [x] Có solver hệ phương trình.
- [x] Có solver số phức.
- [x] Có solver cấp số.
- [x] Có một số bài tổ hợp.
- [x] Có một số template tham số bậc hai.
- [x] Có đạo hàm, giới hạn và tích phân.
- [x] Có test khá chi tiết cho nhiều happy path (unit solvers + verifier + AI explainer).
- [x] Có fallback từ AI extraction sang interpreter rule-based.
- [x] Có giới hạn chiều dài input ở schema.
- [x] Có phân biệt `solved`, `partial`, `unsupported`, `error`.
- [x] Có rate limit thô cho mọi `/api/algebra/solve` (guest 20/phút, user 60/phút; AI có bucket riêng).
- [x] AI explainer khi match `index` giữ công thức deterministic (`before_latex`/`after_latex`/`result*`).

## 5.2. Điểm yếu trọng yếu

- [~] Parser algebra: `global_dict` + precheck + tokenize allowlist; process isolation killable; chưa full AST `safe_math_parser` build.
- [~] Rate limit thô + concurrent `AlgebraSlot`; chưa cost-based / daily quota algebra / circuit breaker.
- [x] Timeout deterministic + process hard-kill khi `algebra_process_isolation=true`.
- [x] AI extraction merge + rule-first/opt-in; FE confirm panel trước solve (natural/AI).
- [x] Pre-solve confirmation (topic/miền/biến/khoảng); post-solve interpretation + apply canonical.
- [x] Frontend variables default rỗng; placeholder gợi ý tự nhận diện.
- [x] Phương trình lượng giác mặc định trên R trả nghiệm tổng quát (không còn cắt [0, 2π) im lặng).
- [x] Nút `°` đã ẩn; solver vẫn radian (chưa có angle_unit).
- [~] Verification semantics thắt chặt (symbolic/sample/empty-set); một số path calculus/combinatorics vẫn rule-based verified.
- [x] Tập nghiệm symbolic không còn auto-verified (partially_verified).
- [~] Vô nghiệm: sample corroboration + warning chưa full unsat proof; status bài vẫn có thể `solved`.
- [x] Bất phương trình mũ-log/lượng giác route sang inequality solver.
- [x] Parameter case-split a(m)=0.
- [x] `n` cấp số: reject phân số/thập phân (không truncate).
- [~] Topic UI “Tổ hợp”; C/A/n! có cap; chưa solver xác suất.
- [x] Toolbar capability registry ẩn ký hiệu backend chưa hỗ trợ.
- [~] Options `verify`/`return_steps`/`max_solutions` đã thực thi; `prefer_exact` chỉ bổ sung approximate.
- [~] FE interpretation + verification + confirm; còn thiếu sửa field-by-field sau AI.
- [x] AI explainer lock: không tạo/xóa/đảo step deterministic (công thức neo index).
- [x] Timeout → 504 ALGEBRA_TIMEOUT; exception nội bộ → 500 không raw; parse soft 200 body.
- [x] Đã xóa `patch.py`, `new_calculus_features.py`, `test_limit.py`.
- [~] Route test còn mỏng so với unit solver; đã có isolation/security tests.
- [~] Export/copy `.md` + copy structured; chưa history algebra / PDF/DOCX (share multi-user ngoài scope).
- [~] Handoff Function Analyzer; chưa GeoGebra/simulation.
- [ ] Tên “Algebra Solver” không còn đúng vì chức năng đã bao gồm giải tích, tổ hợp và số phức.

---

# 6. Luồng xử lý hiện tại

```text
Người dùng nhập tiếng Việt hoặc công thức
        ↓
Frontend chọn topic, domain, variables
        ↓
Natural mode mặc định bật AI extraction
        ↓
AI extraction hoặc rule-based interpreter
        ↓
Canonical input
        ↓
Topic resolution
        ↓
Normalizer
        ↓
Parser SymPy hoặc parser structured template
        ↓
Classifier
        ↓
Solver chuyên biệt
        ↓
Verifier
        ↓
AI explanation tùy chọn
        ↓
Frontend hiển thị đáp án và các bước
```

## 6.1. Luồng natural mode hiện tại

```text
Người dùng nhập tiếng Việt
→ frontend luôn đặt use_ai_extraction=true
→ backend yêu cầu đăng nhập
→ AI tạo request mới
→ request mới có thể thay topic/domain/variables
→ deterministic solver giải request mới
```

## 6.2. Luồng math mode hiện tại

```text
MathQuill sinh LaTeX
→ frontend gửi input_format=latex
→ normalizer chuyển một phần LaTeX sang biểu thức
→ parser hoặc template solver xử lý
```

## 6.3. Các khoảng trống trong luồng

- Không có màn hình xác nhận canonical input.
- Không có kế hoạch giải trước khi chạy.
- Không có trạng thái tiến trình theo stage.
- Không có nút hủy.
- Không có giới hạn thời gian.
- Không có sandbox process cho SymPy.
- Không có independent verifier cho nhiều loại bài.
- Không có provenance rõ ràng của answer/steps.
- Không có lưu lịch sử.
- Không có retry riêng cho extraction/explanation.

---

# 7. Checklist P0 — An toàn parser và tài nguyên

# P0-01. Không parse trực tiếp đầu vào không tin cậy trong process API chính

## Hiện trạng

Parser algebra dùng `parse_expr` với `local_dict` allowlist. **Slice A (10/07/2026):** đã thêm `global_dict` tối thiểu (`Integer`/`Float`/`Rational`/`Symbol`, `__builtins__={}`) và precheck complexity (độ dài, chữ số nguyên, ngoặc, lũy thừa).

Vẫn chưa: sandbox process, AST allowlist đầy đủ, tái sử dụng triệt để `safe_math_parser` / `expression_eval` (analyzer đã có).

Một số structured solver còn dùng:

```python
sympy.sympify(user_text, locals=...)
```

Các điểm xuất hiện gồm:

- Parser tổng quát.
- Solver hệ số tổ hợp.
- Solver tham số.
- Solver giải tích.
- Một số helper expression.

## Rủi ro

- Biểu thức độc hại hoặc bất thường.
- Tạo object SymPy có độ phức tạp cực lớn.
- Expression expansion bùng nổ.
- Tốn CPU/RAM.
- Treo worker API.
- Tấn công từ người dùng không đăng nhập.
- Khả năng gọi các constructor hoặc thuộc tính ngoài allowlist nếu parser không được khóa đúng.

## Checklist

- [~] Không dùng `parse_expr` với global namespace mặc định (Slice A: global_dict tối thiểu).
- [x] Truyền `global_dict` tối thiểu.
- [ ] Chỉ cho phép AST/node type đã đăng ký.
- [ ] Không cho attribute access.
- [ ] Không cho function call ngoài allowlist.
- [ ] Không cho symbol name tùy ý vô hạn.
- [ ] Không cho string literal.
- [ ] Không cho lambda.
- [ ] Không cho indexing tùy ý.
- [ ] Không cho matrix kích thước không giới hạn.
- [ ] Không cho Piecewise quá nhiều nhánh.
- [ ] Không cho nested power quá sâu.
- [~] Không cho integer có quá nhiều chữ số (precheck Slice A, chưa full AST).
- [ ] Không cho factorial quá lớn.
- [ ] Chạy solve trong process riêng.
- [ ] Đặt CPU time limit.
- [ ] Đặt memory limit.
- [ ] Kill process khi timeout.
- [ ] Không tái sử dụng worker bị lỗi bộ nhớ.
- [ ] Fuzz parser.

## Kiến trúc đề xuất

```text
API worker
→ validate input envelope
→ compile SafeMath AST
→ submit isolated solve worker
→ hard timeout
→ structured result
```

---

# P0-02. Thêm timeout cho toàn bộ phép giải

## Hiện trạng

Endpoint gọi trực tiếp:

```text
solve_algebra_with_optional_ai(request)
```

Không có `asyncio.wait_for` cho toàn pipeline deterministic.

## Rủi ro

- `solveset`, `simplify`, `factor`, `integrate`, `limit`, `nonlinsolve` có thể chạy rất lâu.
- Một input làm kẹt worker.
- Nhiều request đồng thời làm cạn server.
- Client đóng trang nhưng backend vẫn tính.

## Checklist

- [~] Timeout tổng cho deterministic solve (Slice A, `algebra_solve_timeout_seconds`).
- [ ] Timeout riêng cho parsing.
- [ ] Timeout riêng cho normalize.
- [ ] Timeout riêng cho solve.
- [ ] Timeout riêng cho verify.
- [ ] Timeout riêng cho AI extraction.
- [ ] Timeout riêng cho AI explanation.
- [ ] Cancel token.
- [ ] Kill isolated worker.
- [~] Trả `ALGEBRA_TIMEOUT` trong errors/status error (Slice A; chưa HTTP 504 riêng).
- [ ] Gợi ý rút gọn input.
- [ ] Không tiếp tục AI explanation sau timeout.
- [ ] Ghi stage bị timeout.
- [ ] Metric p50/p95/p99 theo solver.

---

# P0-03. Rate limit / quota đủ cho solver deterministic

## Hiện trạng (đã cập nhật 10/07/2026)

Endpoint **đã** rate limit mọi request:

```python
await enforce_rate_limit(..., "algebra_solve", 60 if user else 20, 60, settings)
```

Khi dùng AI còn thêm `algebra_ai` rate limit + `enforce_render_access`.

## Rủi ro còn lại

- Rate limit thô theo số request, không theo chi phí CPU.
- Guest vẫn gọi SymPy nặng trong hạn 20 req/phút.
- Chưa cost-based quota, concurrent job limit, circuit breaker.

## Checklist

- [x] Rate limit mọi `/api/algebra/solve`.
- [ ] Rate limit nhẹ cho parse-only.
- [ ] Rate limit cao hơn cho solve đơn giản.
- [ ] Cost-based quota theo solver.
- [ ] Cost score theo node count.
- [ ] Cost score theo degree.
- [ ] Cost score theo operation.
- [ ] Giới hạn concurrent jobs theo IP.
- [ ] Giới hạn concurrent jobs theo user.
- [ ] Circuit breaker.
- [ ] Không dùng quota render để đại diện algebra.
- [ ] Tạo quota `algebra_daily_limit`.
- [ ] Tạo quota `algebra_ai_daily_limit`.
- [ ] Tách AI extraction và deterministic solve.

---

# P0-04. Giới hạn độ phức tạp biểu thức

## Checklist

- [ ] Số ký tự.
- [ ] Số token.
- [ ] Số AST nodes.
- [ ] Độ sâu AST.
- [ ] Bậc đa thức tối đa.
- [ ] Số biến tối đa.
- [ ] Số phương trình tối đa.
- [ ] Số Piecewise branch tối đa.
- [ ] Số căn lồng nhau.
- [ ] Số log lồng nhau.
- [ ] Kích thước số nguyên.
- [ ] Mũ tuyệt đối tối đa.
- [ ] Factorial input tối đa.
- [ ] Combination `n` tối đa.
- [ ] Số nghiệm trả về tối đa.
- [ ] Số bước tối đa.
- [ ] Kích thước LaTeX response tối đa.
- [ ] Số sub-step tối đa.
- [ ] Kích thước AI explanation tối đa.

## Tiêu chí

Input vượt ngưỡng phải trả:

```json
{
  "code": "ALGEBRA_COMPLEXITY_LIMIT",
  "message": "Biểu thức vượt giới hạn xử lý an toàn.",
  "stage": "precheck"
}
```

---

# 8. Checklist P0 — AI extraction và quyền quyết định của người dùng

# P0-05. AI không được âm thầm ghi đè topic, domain và variables

## Hiện trạng

AI extraction tạo một `AlgebraSolveRequest` mới từ payload AI:

- `input`
- `input_format`
- `topic`
- `variables`
- `parameters`
- `domain`

Chỉ một số option của request gốc được giữ lại.

## Ví dụ rủi ro

Người dùng chọn:

```text
Miền nghiệm: Z
Biến cần giải: y
Dạng bài: hệ phương trình
```

AI có thể trả:

```text
domain = R
variables = ["x"]
topic = equation
```

Solver sau đó giải một bài khác lựa chọn người dùng.

## Checklist

- [ ] Phân biệt `user_explicit` và `auto`.
- [ ] AI chỉ điền trường đang ở `auto`.
- [~] Không ghi đè domain người dùng chọn (Slice A: giữ khi domain ≠ R).
- [~] Không ghi đè variables người dùng nhập (Slice A: giữ khi non-empty).
- [~] Không ghi đè topic explicit (Slice A: giữ khi topic ≠ auto).
- [ ] Không ghi đè interval explicit.
- [ ] Không ghi đè parameter explicit.
- [ ] Trả diff giữa request gốc và extraction.
- [ ] Yêu cầu xác nhận khi có conflict.
- [ ] Có `extraction_confidence`.
- [ ] Có `conflicts`.
- [ ] Có `missing_fields`.
- [ ] Có `requires_confirmation`.

## Schema đề xuất

```json
{
  "interpretation": {
    "canonical_input": "x^2-5x+6=0",
    "topic": "equation",
    "variables": ["x"],
    "domain": "R",
    "source": "ai",
    "conflicts": [],
    "confidence": 0.94
  }
}
```

---

# P0-06. Không “đoán gần nhất” khi AI không chắc

## Hiện trạng

Prompt extraction hướng dẫn model:

```text
Nếu không chắc, vẫn trả JSON gần nhất và thêm cảnh báo.
```

## Rủi ro

- Solver giải một đề khác.
- Cảnh báo bị UI ẩn.
- Người dùng chỉ nhìn đáp án.
- Đáp án deterministic nhưng đầu vào đã sai.

## Checklist

- [ ] AI được phép trả `ambiguous`.
- [ ] AI được phép trả `unsupported`.
- [ ] AI được phép trả `needs_clarification`.
- [ ] Không ép model luôn chọn topic.
- [ ] Không giải nếu confidence dưới ngưỡng.
- [ ] Hiển thị canonical input trước.
- [ ] Cho phép chỉnh canonical input.
- [ ] Cho phép chọn lại biến/miền.
- [ ] Không gọi kết quả là deterministic-correct nếu extraction chưa xác nhận.

---

# P0-07. Natural mode không nên mặc định bắt buộc AI và đăng nhập

## Hiện trạng

Frontend natural mode luôn gửi:

```json
{
  "use_ai_extraction": true
}
```

Backend yêu cầu đăng nhập khi dùng AI.

Trong khi hệ thống đã có interpreter tiếng Việt rule-based.

## Checklist

- [x] Chạy rule-based trước.
- [x] Chỉ gọi AI khi rule-based thất bại hoặc confidence thấp (và user bật AI).
- [x] Có tùy chọn `Dùng AI diễn giải`.
- [~] Nói rõ tính năng nào cần đăng nhập (hint UI).
- [x] Người chưa đăng nhập vẫn dùng được bài đơn giản (rule-based).
- [x] Không tiêu quota AI khi rule-based đủ.
- [ ] Có fallback user-visible.
- [ ] Ghi nguồn extraction trong result.

---

# 9. Checklist P0 — Lỗi biến của hệ phương trình

# P0-08. Không gửi mặc định `variables=["x"]` cho mọi bài

## Hiện trạng frontend

```text
variables state mặc định = "x"
```

Mọi request đều gửi danh sách biến sau khi split.

## Hiện trạng parser

Parser chỉ tự chọn `["x","y"]` cho topic system khi `variables is None`.

Nhưng frontend gửi `["x"]`, vì vậy cơ chế suy luận không chạy.

## Ví dụ

```text
x + y = 3
x - y = 1
```

Có thể bị tạo problem với chỉ biến `x`; `y` trở thành symbol tham số.

## Checklist

- [x] Giá trị mặc định variables là rỗng (FE Slice A).
- [~] Tự suy ra free symbols từ toàn hệ (system default x,y khi empty; chưa free-symbol scan đầy đủ).
- [x] Chỉ dùng danh sách user khi user thực sự nhập.
- [ ] Hiển thị biến đã nhận diện.
- [ ] Cảnh báo biến tự do.
- [ ] Cảnh báo số biến khác số phương trình.
- [ ] Hỗ trợ hệ thiếu phương trình.
- [ ] Hỗ trợ hệ vô số nghiệm.
- [ ] Hỗ trợ hệ 3 ẩn.
- [ ] Hỗ trợ thứ tự biến ổn định.
- [ ] Không coi tham số là ẩn.
- [ ] Cho đánh dấu parameter riêng.

## Test bắt buộc

- [x] Hệ 2 ẩn không nhập variables.
- [ ] Hệ 3 ẩn.
- [ ] Hệ có tham số m.
- [ ] User chỉ định thứ tự y,x.
- [ ] Hệ thiếu ẩn.
- [ ] Hệ vô số nghiệm.
- [ ] Hệ vô nghiệm.
- [ ] Hệ phi tuyến.

---

# 10. Checklist P0 — Lượng giác và khoảng nghiệm

# P0-09. Không mặc định trả nghiệm trên `[0, 2π)` như nghiệm cuối cùng trên R

## Hiện trạng

Solver lượng giác ưu tiên:

```text
solveset(..., domain=[0, 2π))
```

Nếu thành công, kết quả hữu hạn được trả làm đáp án.

UI chỉ hiển thị:

```text
Miền nghiệm: R
```

Không có lựa chọn interval và không báo rõ lời giải đã bị giới hạn.

## Ví dụ

```text
sin(x) = 1/2, x ∈ R
```

Đúng phải là nghiệm tổng quát tuần hoàn.

Hệ thống hiện có thể trả:

```text
{π/6, 5π/6}
```

Đây chỉ là nghiệm trong một chu kỳ.

## Checklist

- [x] Nếu domain là R và không có interval, trả nghiệm tổng quát.
- [x] Chỉ dùng `[0,2π)` khi user chọn interval.
- [x] Thêm interval selector (preset).
- [x] Hỗ trợ `[0,2π)`.
- [ ] Hỗ trợ `[0,360°)`.
- [ ] Hỗ trợ interval tùy chỉnh.
- [ ] Ghi đơn vị radian/degree.
- [x] Không gọi finite cycle result là tập nghiệm trên R (mặc định).
- [x] Có `periodic` solution kind.
- [ ] Có parameter `k ∈ Z`.
- [ ] Kiểm tra nghiệm tổng quát.
- [ ] Test endpoint và UI.

---

# P0-10. Hỗ trợ đơn vị góc rõ ràng

## Hiện trạng

Toolbar có nút `°`, nhưng normalizer không chuyển độ và solver dùng SymPy theo radian.

## Checklist

- [ ] Thêm `angle_unit`.
- [ ] Giá trị `radian`.
- [ ] Giá trị `degree`.
- [ ] Mặc định hiển thị rõ.
- [ ] Chuyển độ sang radian nội bộ.
- [ ] Trả đáp án theo đơn vị người dùng.
- [ ] Không trộn `π` và độ vô tình.
- [ ] Kiểm tra inverse trig.
- [ ] Kiểm tra interval degree.
- [x] Ẩn nút độ cho tới khi backend hỗ trợ.

---

# 11. Checklist P0 — Verification semantics

# P0-11. Không coi “SymPy trả kết quả” là “đã kiểm chứng”

## Hiện trạng

Nhiều solver tạo report:

```text
status = verified
method = sympy.diff / sympy.limit / sympy.integrate / sympy.simplify
```

Trong một số trường hợp, cùng engine vừa giải vừa “xác minh”.

## Các trường hợp cụ thể

- Biến đổi biểu thức được verified khi `expand`, `factor` hoặc `simplify` chạy xong.
- Đạo hàm verified khi `sympy.diff` trả kết quả.
- Giới hạn verified khi `sympy.limit` trả kết quả.
- Tích phân verified khi `sympy.integrate` trả kết quả.
- Tập nghiệm symbolic khác rỗng được verified.
- Tổ hợp verified từ chính công thức vừa tính.
- Cấp số verified từ chính công thức vừa tính.

## Rủi ro

- Unevaluated result vẫn được gọi verified.
- `ConditionSet` có thể được gọi verified.
- Cùng một bug của engine không được phát hiện.
- Người dùng hiểu “verified” là chắc chắn đúng.

## Trạng thái đề xuất

```text
computed
symbolically_checked
numerically_cross_checked
independently_verified
partially_verified
unverifiable
failed
```

## Checklist

- [ ] Đổi tên semantic của verification.
- [~] Symbolic set không còn verified chỉ vì non-empty; finite substitution vẫn verified.
- [ ] Tách `solver_method`.
- [ ] Tách `verification_method`.
- [ ] Ghi engine/version.
- [ ] Ghi kiểm tra độc lập.
- [ ] Ghi phạm vi kiểm chứng.
- [ ] Ghi các giả định.
- [ ] Ghi mức tin cậy.
- [ ] Không nâng status chỉ vì không exception.

---

# P0-12. Không coi mọi tập nghiệm symbolic khác rỗng là verified

## Hiện trạng

Logic gần tương đương:

```text
solution_set != EmptySet
→ symbolic_solution_set pass
→ verification verified
```

## Các loại tập cần xử lý riêng

- `ConditionSet`
- `ImageSet`
- `Union`
- `Intersection`
- `Complement`
- `FiniteSet`
- `Interval`
- `EmptySet`
- `UniversalSet`
- Tập có parameter tự do
- Tập chưa evaluate

## Checklist

- [x] Detect `ConditionSet`.
- [ ] Detect unevaluated object.
- [ ] Không gọi `ConditionSet` solved.
- [ ] Kiểm tra membership mẫu.
- [ ] Kiểm tra điểm biên.
- [ ] Kiểm tra ngoài tập nghiệm.
- [ ] Kiểm tra periodic representative.
- [ ] Kiểm tra điều kiện domain.
- [ ] Trả `partially_verified` đúng nghĩa.
- [ ] Không chỉ kiểm tra tập khác rỗng.

---

# P0-13. Chứng minh vô nghiệm thay vì chỉ không có nghiệm để thử

## Hiện trạng

Khi `solutions=[]`:

- Report thêm warning.
- Status `partially_verified`.
- Solver vẫn có thể trả `solved`.

## Checklist

- [ ] Phân biệt `proven_empty` và `solver_returned_empty`.
- [ ] Với đa thức, kiểm tra nghiệm/root count.
- [ ] Với phương trình đơn điệu, kiểm tra dấu.
- [ ] Với phương trình căn, kiểm tra miền.
- [ ] Với hệ tuyến tính, kiểm tra rank.
- [ ] Với inequality, xác minh tập rỗng bằng sign chart.
- [ ] Với trig, kiểm tra range.
- [ ] Với log, kiểm tra domain/range.
- [ ] Nếu chưa chứng minh, status phải partial.
- [ ] UI phải nói rõ.

---

# P0-14. Kiểm chứng bất phương trình không chỉ bằng vài điểm mẫu

## Hiện trạng

Verifier chọn tối đa một số điểm mẫu rồi so sánh:

```text
point ∈ result_set
so với
relation(point)
```

## Rủi ro

- Bỏ sót khoảng sai nhỏ.
- Sai endpoint.
- Sai điểm loại trừ.
- Sai tập rời rạc.
- Sai miền Z/N.
- Sai biểu thức đổi dấu nhiều lần.

## Checklist

- [ ] Xây sign decomposition chính thức.
- [ ] Kiểm tra mọi cell.
- [ ] Kiểm tra từng critical point.
- [ ] Kiểm tra open/closed boundary.
- [ ] Kiểm tra denominator roots.
- [ ] Kiểm tra domain restriction.
- [ ] Kiểm tra Z/N bằng intersection.
- [ ] Sample chỉ là bổ sung.
- [ ] Không gọi sample-only là independently verified.

---

# P0-15. Exception khi kiểm chứng không được coi là fail toán học

## Hiện trạng

Một số helper:

```text
except Exception:
    return False
```

## Rủi ro

- “Không kiểm tra được” bị biến thành “nghiệm sai”.
- Kết quả đúng có thể bị gắn failed.
- Không phân biệt lỗi engine và sai toán.

## Checklist

- [ ] Trạng thái `unverifiable`.
- [ ] Trạng thái `verification_error`.
- [ ] Ghi stage.
- [ ] Ghi expression an toàn.
- [ ] Không lộ stack trace.
- [ ] Không chuyển exception thành pass.
- [ ] Không chuyển exception thành mathematical false.
- [ ] Retry verifier độc lập khi phù hợp.

---

# 12. Checklist P0 — Routing và classifier

# P0-16. Bất phương trình mũ-log/lượng giác phải vào solver phù hợp

## Hiện trạng

Classifier ưu tiên nhận diện:

```text
có log/exp → exponential_log
có sin/cos/tan → trigonometry
```

Trong khi:

- `exp_log_solver` chỉ hỗ trợ equality.
- `trig_solver` chỉ hỗ trợ equality hoặc expression.
- Bất phương trình có thể bị route sai và trả unsupported.

## Ví dụ

```text
log(x) > 0
sin(x) >= 1/2
2^x < 8
```

## Checklist

- [x] Phân loại theo cả domain function và relation type.
- [~] `exp_log_equation` (topic exponential_log + equality).
- [~] `exp_log_inequality` → inequality solver.
- [~] `trig_equation`.
- [~] `trig_inequality` → inequality solver.
- [x] Route inequality vào solver có hỗ trợ.
- [ ] Không dùng topic quá rộng.
- [ ] Capability registry.
- [ ] Test toàn bộ ma trận topic × relation.

---

# P0-17. Parser phải xử lý hoặc từ chối rõ bất phương trình kép

## Ví dụ

```text
0 < x < 1
-1 <= 2x+1 <= 3
```

Parser hiện tách relation theo operator đầu tiên và không có model chain relation đầy đủ.

## Checklist

- [x] Parse chained inequality.
- [ ] Chuyển thành `And`.
- [ ] Hoặc tách thành hai relation.
- [ ] Không parse sai thành expression.
- [ ] Hiển thị canonical chain.
- [ ] Hỗ trợ hệ bất phương trình.
- [ ] Test strict/non-strict boundary.

---

# P0-18. Xử lý `!=` riêng

## Hiện trạng

`!=` được parse thành `Ne`, sau đó classification coi là inequality.

Một số helper dựng relation từ `rel_op` chỉ xử lý `>`, `>=`, `<`, còn trường hợp khác có thể rơi vào `<=`.

## Checklist

- [x] Có branch `!=`.
- [ ] Tập nghiệm là domain trừ zero set.
- [ ] Không dùng sign relation `<=`.
- [ ] Test polynomial.
- [ ] Test rational.
- [ ] Test domain Z/N.
- [ ] Test expression không xác định.

---

# 13. Checklist P0 — Bài tham số

# P0-19. Tách trường hợp hệ số bậc hai bằng 0 theo tham số

## Hiện trạng

Template chỉ kiểm tra:

```text
a identically equals 0
```

Nếu:

```text
a = m
```

thì tại `m=0`, phương trình không còn bậc hai.

Những công thức:

```text
Delta > 0
Delta = 0
a > 0 and Delta < 0
```

không thể áp dụng đồng nhất cho mọi m nếu bậc thay đổi.

## Checklist

- [x] Tìm tập `a(parameter)=0`.
- [x] Tách case `a ≠ 0`.
- [ ] Giải case tuyến tính.
- [ ] Giải case hằng.
- [ ] Hợp các điều kiện.
- [ ] Loại giá trị làm template vô nghĩa.
- [ ] Ghi rõ case split trong steps.
- [ ] Kiểm chứng boundary.
- [ ] Không dùng vài mẫu nguyên làm verification chính.

## Test bắt buộc

- [ ] `m*x^2 + x + 1 = 0`.
- [ ] `(m-1)x^2 + 2x + 1 = 0`.
- [ ] Hệ số b và c cùng suy biến.
- [ ] Nghiệm kép tại giá trị làm a=0.
- [ ] Tam thức dương mọi x khi a phụ thuộc m.

---

# P0-20. Verification tham số không chỉ dùng mẫu -3 đến 3

## Hiện trạng

Verifier thử các số nguyên nhỏ.

## Rủi ro

- Bỏ sót boundary phân số.
- Bỏ sót interval xa.
- Bỏ sót điểm loại trừ.
- Bỏ sót case a=0.
- Bỏ sót tập rời rạc.

## Checklist

- [ ] Kiểm tra symbolic equivalence.
- [ ] Kiểm tra boundary.
- [ ] Kiểm tra mỗi connected component.
- [ ] Chọn sample trong và ngoài mỗi component.
- [ ] Kiểm tra điểm suy biến.
- [ ] Kiểm tra noninteger sample.
- [ ] Ghi coverage của verification.

---

# 14. Checklist P0 — Cấp số

# P0-21. Không ép `n` phân số thành số nguyên bằng `int()`

## Hiện trạng

```python
n = int(args.get("n", 0))
```

Nếu `n=3/2`, `Fraction(3,2)` có thể bị ép thành `1` thay vì báo lỗi.

## Checklist

- [x] Parse n là Fraction.
- [x] Kiểm tra denominator bằng 1.
- [x] Kiểm tra n > 0.
- [x] Không truncate.
- [x] Không round.
- [x] Báo `SEQUENCE_N_NOT_INTEGER`.
- [x] Test `n=3/2`.
- [ ] Test `n=1.5`.
- [ ] Test `n=-2`.
- [x] Test `n=0`.
- [ ] Test n rất lớn.

---

# P0-22. Validate key structured input của cấp số

## Hiện trạng

- Key lạ có thể bị bỏ qua.
- Key lặp có thể ghi đè.
- Chưa giới hạn độ lớn.
- Chỉ hỗ trợ số numeric.

## Checklist

- [ ] Allowlist key theo kind.
- [ ] Reject duplicate key.
- [ ] Reject unknown key.
- [ ] Reject missing key.
- [ ] Giới hạn numerator/denominator.
- [ ] Giới hạn n.
- [ ] Giới hạn exponent.
- [ ] Trả lỗi theo field.
- [ ] Không dùng regex/string parser rời rạc nếu có thể dùng schema typed.

---

# 15. Checklist P0 — Tổ hợp và xác suất

# P0-23. Đổi tên phạm vi hoặc bổ sung xác suất thật

## Hiện trạng

Topic được gọi:

```text
combinatorics_probability
```

UI hiển thị:

```text
Tổ hợp-xác suất
```

Nhưng solver chỉ hỗ trợ:

- Tổ hợp.
- Chỉnh hợp.
- Giai thừa.
- Hệ số khai triển.

Không có:

- Xác suất cổ điển.
- Biến cố.
- Xác suất có điều kiện.
- Quy tắc cộng/nhân.
- Bayes.
- Phân phối nhị thức.

## Checklist

- [x] Đổi nhãn thành `Tổ hợp`.
- [ ] Hoặc triển khai probability solver.
- [ ] Không quảng bá phạm vi chưa có.
- [ ] Capability badge.
- [ ] Danh sách dạng hỗ trợ.
- [ ] Example đúng với capability.

---

# P0-24. Giới hạn factorial, permutation và combination

## Checklist

- [ ] Giới hạn `n`.
- [ ] Giới hạn số chữ số kết quả.
- [ ] Chế độ symbolic cho n lớn.
- [ ] Không tính factorial khổng lồ trong API worker.
- [ ] Timeout.
- [ ] Cost estimation trước khi tính.
- [ ] Trả scientific/log representation khi cần.
- [ ] Không render LaTeX hàng triệu ký tự.

---

# 16. Checklist P0 — Giải tích

# P0-25. Đạo hàm phải được kiểm tra độc lập hơn

## Hiện trạng

```text
diff(expression)
→ status verified
```

## Checklist

- [ ] So sánh derivative candidate bằng simplify.
- [ ] Numeric finite-difference cross-check tại nhiều điểm hợp lệ.
- [ ] Loại singular point.
- [ ] Ghi domain.
- [ ] Kiểm tra piecewise boundary.
- [ ] Kiểm tra order dương.
- [ ] Giới hạn derivative order.
- [ ] Detect unevaluated `Derivative`.
- [ ] Không gọi unevaluated result solved.

---

# P0-26. Nguyên hàm phải kiểm tra bằng đạo hàm ngược

## Hiện trạng

```text
integrate(expression)
→ status verified
```

## Checklist

- [ ] Detect unevaluated `Integral`.
- [ ] Tính `diff(F,x)-f`.
- [ ] Simplify về 0 trên domain.
- [ ] Numeric sample.
- [ ] Ghi constant `C`.
- [ ] Kiểm tra branch/log absolute value.
- [ ] Với definite integral, kiểm tra singularity.
- [ ] Phân biệt proper/improper.
- [ ] Không áp dụng Newton-Leibniz đơn giản qua điểm gián đoạn.
- [ ] Không gọi divergent result là tích phân hữu hạn.
- [ ] Xử lý principal value riêng.

---

# P0-27. Giới hạn cần kiểm tra unevaluated và một phía

## Checklist

- [ ] Detect unevaluated `Limit`.
- [ ] Validate `dir`.
- [ ] Hỗ trợ `+`, `-`, `+-`.
- [ ] Không tự mặc định sai.
- [ ] Kiểm tra một phía.
- [ ] Numeric asymptotic sample.
- [ ] Phân biệt infinity và DNE.
- [ ] Phân biệt complex infinity.
- [ ] Không coi `zoo` là kết quả verified.
- [ ] Ghi loại giới hạn.

---

# P0-28. Giới hạn order đạo hàm và cấu trúc template

## Hiện trạng

`order` được ép `int(...)` nhưng không có bound rõ ràng.

## Checklist

- [ ] order >= 1.
- [ ] order <= giới hạn cấu hình.
- [ ] Không nhận order phân số.
- [ ] Không nhận số cực lớn.
- [ ] Validate direction.
- [ ] Validate lower/upper.
- [ ] Validate target variable.
- [ ] Reject duplicate structured keys.
- [ ] Reject unknown keys.

---

# P0-29. Continuity report không được verified với checks rỗng

## Hiện trạng

Nhánh hàm không xác định tại điểm có thể trả:

```text
verification.status = verified
checks = []
```

## Checklist

- [ ] Có check `function_value_defined`.
- [ ] Có check left limit.
- [ ] Có check right limit.
- [ ] Có check equality.
- [ ] Không verified khi không có check.
- [ ] Không dùng solution_set kind expression cho boolean property.
- [ ] Tạo result kind `property`.
- [ ] Test removable/jump/infinite discontinuity.
- [ ] Test Piecewise boundary.
- [ ] Test undefined value but removable extension.

---

# 17. Checklist P0 — Contract option chưa được thực thi

# P0-30. Thực thi `verify`

## Hiện trạng

Schema có:

```text
options.verify
```

Nhưng solver vẫn thường chạy verification.

## Checklist

- [x] `verify=false` thực sự bỏ qua verifier.
- [ ] Response status `skipped`.
- [ ] UI nói rõ chưa kiểm chứng.
- [ ] `verify=true` bắt buộc report.
- [ ] Không gọi AI explanation khi verification skipped, trừ khi user đồng ý.
- [ ] Test option.

---

# P0-31. Thực thi `return_steps`

- [x] `return_steps=false` xóa steps sau solve.
- [ ] Giảm CPU.
- [ ] Giảm payload.
- [ ] Không gọi AI explanation.
- [ ] Vẫn trả answer và verification.
- [ ] Test.

---

# P0-32. Thực thi `max_solutions`

- [x] Giới hạn values (max_solutions).
- [x] Không truncate im lặng (có warning).
- [ ] Có `truncated=true` field schema.
- [ ] Có total estimate.
- [ ] Không làm sai set symbolic.
- [ ] Test hệ nhiều nghiệm.
- [ ] Test polynomial degree lớn.

---

# P0-33. Thực thi `prefer_exact`

- [ ] Exact result khi true.
- [ ] Numeric result khi false.
- [ ] Precision option.
- [ ] Không biến gần đúng thành exact.
- [ ] Không mất căn/pi.
- [ ] Ghi approximation.
- [ ] Test.

---

# 18. Checklist P0 — API error handling

# P0-34. Không gom mọi lỗi thành HTTP 400

## Phân loại đề xuất

| Lỗi | HTTP | Code |
|---|---:|---|
| Input không hợp lệ | 422 | `ALGEBRA_INPUT_INVALID` |
| Parse lỗi | 422 | `ALGEBRA_PARSE_FAILED` |
| Dạng chưa hỗ trợ | 200 hoặc 422 | `ALGEBRA_UNSUPPORTED` |
| Quá phức tạp | 413/422 | `ALGEBRA_COMPLEXITY_LIMIT` |
| Timeout | 504 | `ALGEBRA_TIMEOUT` |
| Hết quota | 429 | `ALGEBRA_QUOTA_EXCEEDED` |
| Rate limit | 429 | `RATE_LIMITED` |
| AI extraction lỗi | 502 | `ALGEBRA_AI_EXTRACTION_FAILED` |
| AI explanation lỗi | Không làm fail answer | warning |
| Solver nội bộ lỗi | 500 | `ALGEBRA_INTERNAL_ERROR` |
| Bảo trì | 503 | `MAINTENANCE_MODE` |

## Checklist

- [~] Exception nội bộ không còn raw message (500 generic).
- [ ] Có correlation ID.
- [ ] Có stage.
- [ ] Có retryable.
- [ ] Có suggestions.
- [ ] Log stack trace server-side.
- [ ] Redact provider data.
- [ ] Không coi unsupported là server error.

---

# 19. Checklist P0 — Dọn mã giải tích thừa

## Hiện trạng

Repository còn:

- `new_calculus_features.py`
- `patch.py`

`patch.py` đọc file và append code vào `calculus_solver.py`.

`new_calculus_features.py` có placeholder chưa hoàn chỉnh.

## Rủi ro

- Import nhầm.
- Duplicate implementation.
- Patch chạy lại làm append trùng code.
- Code review khó xác định source of truth.
- Coverage sai lệch.
- Packaging nhầm file.

## Checklist

- [ ] Chọn một source of truth.
- [x] Xóa script patch khỏi runtime package.
- [x] Xóa file placeholder.
- [ ] Git history giữ lại thay vì file patch.
- [ ] Thêm lint chặn placeholder.
- [ ] Thêm test import toàn module.
- [ ] Thêm dead-code scan.
- [ ] Không đặt script migration trong package app.

---

# 20. Checklist P1 — Input UX

# P1-01. Thêm bước “Hệ thống hiểu đề”

## Nội dung cần hiển thị

```text
Đề gốc
Canonical input
Dạng toán
Biến cần giải
Tham số
Miền
Khoảng
Đơn vị góc
Điều kiện
Cảnh báo
Nguồn diễn giải
```

## Checklist

- [x] Hiển thị canonical input.
- [x] Hiển thị topic.
- [x] Hiển thị variables.
- [ ] Hiển thị parameters.
- [x] Hiển thị domain.
- [ ] Hiển thị interval.
- [ ] Hiển thị angle unit.
- [ ] Hiển thị assumptions.
- [ ] Hiển thị conflicts.
- [ ] Hiển thị confidence.
- [ ] Cho sửa từng trường.
- [ ] Cho xác nhận rồi giải.
- [ ] Cho bỏ qua AI.
- [ ] Cho dùng rule-based.

---

# P1-02. Không để kết quả cũ trông như kết quả của input mới

## Hiện trạng

Khi người dùng sửa input sau khi đã có result:

- Result cũ vẫn hiển thị.
- Không có badge stale.
- Người dùng có thể nhầm.

## Checklist

- [~] Clear result khi input thay đổi (giữ + badge stale).
- [x] Gắn badge kết quả đề trước.
- [ ] Clear khi topic đổi.
- [ ] Clear khi domain đổi.
- [ ] Clear khi variables đổi.
- [ ] Clear khi interval đổi.
- [ ] Giữ history riêng.
- [ ] Disable export result stale.

---

# P1-03. Toolbar phải phản ánh đúng capability backend

## Hiện trạng toolbar có

- Tổng.
- Tích.
- Vector.
- Tập hợp.
- Logic.
- Ký hiệu thuộc.
- Hợp/giao.
- Lượng giác độ.

Nhiều mục không có solver tương ứng.

## Checklist

- [ ] Capability registry dùng chung frontend/backend.
- [ ] Ẩn nút chưa hỗ trợ.
- [ ] Badge `Sắp có`.
- [ ] Tooltip dạng input được hỗ trợ.
- [ ] Không đưa ký hiệu vào input rồi để parser lỗi.
- [ ] Test từng nút toolbar.
- [ ] Contract test toolbar → normalizer → solver.

---

# P1-04. Chọn interval

- [ ] Không giới hạn.
- [ ] Khoảng tùy chỉnh.
- [ ] Đóng/mở hai đầu.
- [ ] Interval lượng giác preset.
- [ ] Interval số nguyên.
- [ ] Hiển thị interval trong answer.
- [ ] Gửi vào request.
- [ ] Solver thực sự sử dụng.
- [ ] Verification thực sự sử dụng.

---

# P1-05. Chọn biến và tham số theo chip

Thay vì textbox:

```text
x,y,z
```

nên dùng:

```text
Biến cần giải: [x] [y]
Tham số: [m]
```

## Checklist

- [ ] Auto-detect.
- [ ] Add/remove chip.
- [ ] Không trùng.
- [ ] Không dùng reserved function.
- [ ] Không nhầm e, pi, I.
- [ ] Chọn biến chính.
- [ ] Chọn tham số.
- [ ] Cảnh báo free symbols.

---

# P1-06. Grade và chương trình THPT

Schema hiện chỉ có `grade_level = C3`.

## Checklist

- [ ] Lớp 10.
- [ ] Lớp 11.
- [ ] Lớp 12.
- [ ] Tự nhận diện.
- [ ] Giới hạn phương pháp theo lớp.
- [ ] Không dùng kỹ thuật ngoài chương trình khi không cần.
- [ ] Lời giải phù hợp ngôn ngữ SGK.
- [ ] Cho phép phương pháp nâng cao.
- [ ] Metadata chương/chủ đề.
- [ ] Preset dạng bài.

---

# P1-07. Chế độ lời giải

- [ ] Chỉ đáp án.
- [ ] Ngắn gọn.
- [ ] Chuẩn.
- [ ] Chi tiết.
- [ ] Gợi ý từng bước.
- [ ] Không hiện đáp án ngay.
- [ ] Kiểm tra bài làm của học sinh.
- [ ] So sánh hai phương pháp.

---

# 21. Checklist P1 — Result UX

# P1-08. Hiển thị input interpretation

Frontend có type cho interpretation nhưng result UI gần như không hiển thị.

## Checklist

- [ ] Đề gốc.
- [ ] Canonical input.
- [ ] Detected format.
- [ ] Source.
- [ ] Topic hint.
- [ ] Variables.
- [ ] Domain.
- [ ] Chips.
- [ ] Warnings.
- [ ] Nút sửa cách hiểu.
- [ ] Nút giải lại.

---

# P1-09. Hiển thị cả verification pass

Hiện UI lọc bỏ các check `pass`.

## Rủi ro

- Người dùng chỉ thấy lỗi/cảnh báo.
- Không biết hệ thống đã kiểm tra gì.
- Badge “Đã giải được” không có evidence.

## Checklist

- [x] Summary k/n checks passed.
- [x] Cho mở chi tiết pass checks.
- [x] Hiển thị pass/warn/fail/skip.
- [ ] Hiển thị method.
- [ ] Hiển thị scope.
- [ ] Hiển thị engine.
- [ ] Hiển thị numerical cross-check.
- [ ] Không overload giao diện mặc định.

---

# P1-10. Hiển thị đủ dữ liệu step

Backend step có:

- `goal`
- `why`
- `rule`
- `operation`
- `pitfall`
- `check`
- `confidence`

Frontend hiện chủ yếu hiển thị:

- title
- rule/method
- formulas
- explanation

## Checklist

- [x] Mục tiêu bước.
- [x] Vì sao dùng bước.
- [ ] Quy tắc.
- [ ] Thao tác.
- [ ] Sai lầm thường gặp.
- [ ] Cách kiểm tra.
- [ ] Confidence.
- [ ] Nguồn deterministic/AI.
- [ ] Thu gọn theo mức chi tiết.

---

# P1-11. Hiển thị solution set có cấu trúc

- [ ] Exact values.
- [ ] Approximation.
- [ ] Interval.
- [ ] Periodic family.
- [ ] Conditions.
- [ ] Empty proof status.
- [ ] Truncated status.
- [ ] Copy LaTeX.
- [ ] Copy plain text.
- [ ] Copy JSON.
- [ ] Chuyển sang đồ thị.

---

# P1-12. Không ẩn routine interpretation notice hoàn toàn

UI đang lọc một số notice về diễn giải đầu vào.

## Checklist

- [ ] Chuyển thành compact badge.
- [ ] Không chiếm diện tích lớn.
- [ ] Vẫn cho người dùng kiểm tra.
- [ ] Đặc biệt hiển thị khi AI extraction.
- [ ] Hiển thị khi canonical khác input nhiều.

---

# 22. Checklist P1 — AI explanation

# P1-13. AI không được thay toàn bộ deterministic steps tùy ý

## Hiện trạng (đã cập nhật 10/07/2026)

AI explainer vẫn trả danh sách steps mới. Mapper khi match `index` **giữ** công thức deterministic (`before_latex`, `after_latex`, `expression*`, `result*`, `kind`, `confidence`).

## Rủi ro còn lại

- AI vẫn có thể tạo/xóa/đảo step nếu index không khớp.
- Domain/verify steps deterministic có thể biến mất khỏi danh sách hiển thị.
- Prompt vẫn khuyến khích viết lại list steps + sub_steps.

## Hướng đề xuất

AI chỉ được bổ sung:

```text
step.explanation
step.why
step.pitfall
step.short_explanation
```

Không được thay:

```text
kind
method
before_latex
after_latex
result
confidence
step order
```

## Checklist

- [~] Khi match index: giữ công thức deterministic (đã có).
- [~] Deterministic step ID = index.
- [x] AI rewrite theo step ID/index.
- [x] Không tạo/xóa step toán học.
- [x] Không đổi công thức.
- [x] Không đổi thứ tự.
- [ ] Validate semantic anchor.
- [ ] Giới hạn độ dài.
- [ ] Provenance `ai_explanation`.
- [ ] Cho tắt AI explanation.
- [ ] Cache explanation.

---

# P1-14. Sửa mapping công thức AI step

Hiện prompt cho phép AI trả `before_latex`, `after_latex`, nhưng mapper với step mới có thể bỏ các trường này.

## Checklist

- [ ] Hoặc cấm AI sinh công thức.
- [ ] Hoặc validate rồi dùng.
- [ ] Không có contract mâu thuẫn.
- [ ] Test sub-step mới.
- [ ] Test mapping index.
- [ ] Test missing original step.

---

# P1-15. Không tuyên bố lời giải AI “được bảo đảm” quá rộng

Cảnh báo hiện có ý:

```text
đáp án và kiểm chứng vẫn được bảo đảm
```

Dù answer không đổi, lời giải diễn đạt có thể sai.

## Checklist

- [ ] Nói rõ answer deterministic.
- [ ] Nói rõ phần diễn giải do AI.
- [ ] Không gọi toàn bộ lời giải verified.
- [ ] Có badge từng step.
- [ ] Cho xem bản deterministic gốc.
- [ ] Cho báo lỗi step.

---

# 23. Checklist P1 — Solver phương trình

## Checklist

- [ ] Linear.
- [ ] Quadratic.
- [ ] Biquadratic.
- [ ] Cubic.
- [ ] Rational.
- [ ] Radical.
- [ ] Absolute value.
- [ ] Polynomial degree cao.
- [ ] Equation with parameter.
- [ ] Transcendental.
- [ ] Domain Z/N/C.
- [ ] Multiple variables.
- [ ] Conditional solutions.
- [ ] ConditionSet.
- [ ] Unevaluated solve.

## Cải tiến

- [ ] Tách method planner khỏi solver output.
- [ ] Không dùng approximate Cardano answer nếu exact có thể trình bày.
- [ ] Cho chọn phương pháp.
- [ ] Kiểm tra phép biến đổi tương đương.
- [ ] Gắn transformation type.
- [ ] Gắn generated candidates.
- [ ] Gắn filtered candidates.

---

# 24. Checklist P1 — Solver bất phương trình

- [ ] Polynomial.
- [ ] Rational.
- [ ] Absolute value.
- [ ] Radical.
- [ ] Exponential.
- [ ] Logarithmic.
- [ ] Trigonometric.
- [ ] Chained.
- [ ] System of inequalities.
- [ ] Domain Z/N.
- [ ] Parameter inequality.
- [ ] Sign chart UI.
- [ ] Critical point table.
- [ ] Boundary evidence.
- [ ] Interactive number line.

---

# 25. Checklist P1 — Solver mũ-log

- [ ] Equation.
- [ ] Inequality.
- [ ] Same base.
- [ ] Substitution.
- [ ] Log sum/product.
- [ ] Variable base.
- [ ] Base conditions.
- [ ] Argument conditions.
- [ ] Multiple logs.
- [ ] Transcendental ConditionSet.
- [ ] Numeric root mode.
- [ ] Verify finite solutions.
- [ ] Verify symbolic solutions.

---

# 26. Checklist P1 — Solver lượng giác

- [ ] Radian.
- [ ] Degree.
- [ ] General solution.
- [ ] Interval solution.
- [ ] Basic equations.
- [ ] Quadratic substitution.
- [ ] Sum-to-product.
- [ ] Product-to-sum.
- [ ] a sin x + b cos x.
- [ ] Double angle.
- [ ] Trig inequalities.
- [ ] Domain of tan/cot.
- [ ] Inverse trig principal value.
- [ ] Periodic verification.
- [ ] Unit circle visualization handoff.

---

# 27. Checklist P1 — Solver hệ

- [ ] Auto-detect variables.
- [ ] Explicit variables.
- [ ] Parameters.
- [ ] Linear 2×2.
- [ ] Linear 3×3.
- [ ] Underdetermined.
- [ ] Overdetermined.
- [ ] Infinite solutions.
- [ ] No solution.
- [ ] Nonlinear finite.
- [ ] Positive-dimensional set.
- [ ] Domain restriction.
- [ ] Substitution verification.
- [ ] Rank evidence.
- [ ] Matrix method.
- [ ] Elimination steps.

---

# 28. Checklist P1 — Số phức

- [ ] Expression.
- [ ] Equation.
- [ ] Conjugate.
- [ ] Modulus.
- [ ] Argument.
- [ ] Algebraic form.
- [ ] Trigonometric form.
- [ ] Exponential form.
- [ ] Roots.
- [ ] Locus.
- [ ] Complex plane visualization.
- [ ] Independent verification.
- [ ] Không dùng equation verifier cho expression.

---

# 29. Checklist P1 — Cấp số

- [ ] Arithmetic term.
- [ ] Arithmetic sum.
- [ ] Geometric term.
- [ ] Geometric sum.
- [ ] Infer from listed sequence.
- [ ] Find d/q.
- [ ] Find n.
- [ ] Find u1.
- [ ] Multiple constraints.
- [ ] Symbolic parameter.
- [ ] Recurrence relation.
- [ ] Monotonicity.
- [ ] Infinite geometric series.
- [ ] Validation typed schema.
- [ ] Independent recomputation.

---

# 30. Checklist P1 — Tổ hợp và xác suất

## Tổ hợp

- [ ] Factorial.
- [ ] Permutation.
- [ ] Combination.
- [ ] Binomial coefficient.
- [ ] Coefficient extraction.
- [ ] Counting word problems.
- [ ] Repetition.
- [ ] Circular permutation.

## Xác suất

- [ ] Sample space.
- [ ] Classical probability.
- [ ] Addition rule.
- [ ] Multiplication rule.
- [ ] Conditional probability.
- [ ] Bayes.
- [ ] Independence.
- [ ] Binomial probability.
- [ ] Tree diagram.
- [ ] Exact fraction.
- [ ] Event definitions.

---

# 31. Checklist P1 — Bài tham số

- [ ] Quadratic root count.
- [ ] Degenerate leading coefficient.
- [ ] Root sign.
- [ ] Vieta conditions.
- [ ] Root interval.
- [ ] Integer roots.
- [ ] Parameter inequalities.
- [ ] Function parameter.
- [ ] Piecewise case split.
- [ ] Boundary verification.
- [ ] Symbolic condition set.
- [ ] Case tree UI.

---

# 32. Checklist P1 — Giải tích

## Đạo hàm

- [ ] Basic rules.
- [ ] Chain rule.
- [ ] Product.
- [ ] Quotient.
- [ ] Log differentiation.
- [ ] Implicit differentiation.
- [ ] Higher order.
- [ ] Definition.
- [ ] At a point.
- [ ] Piecewise.
- [ ] Domain.
- [ ] Independent check.

## Giới hạn

- [ ] Direct substitution.
- [ ] Factorization.
- [ ] Conjugate.
- [ ] Standard trig.
- [ ] Infinity.
- [ ] One-sided.
- [ ] L'Hospital.
- [ ] Sequence limit.
- [ ] DNE.
- [ ] Divergent.
- [ ] Independent numeric check.

## Tích phân

- [ ] Indefinite.
- [ ] Definite.
- [ ] Substitution.
- [ ] By parts.
- [ ] Partial fractions.
- [ ] Trig identities.
- [ ] Improper.
- [ ] Area.
- [ ] Parameter bound.
- [ ] Absolute convergence.
- [ ] Differentiate-back verification.

## Liên tục

- [ ] Function value.
- [ ] Left limit.
- [ ] Right limit.
- [ ] Equal comparison.
- [ ] Removable.
- [ ] Jump.
- [ ] Infinite.
- [ ] Piecewise parameter.
- [ ] Verification checks nonempty.

---

# 33. Checklist P1 — Schema response mới

## 33.1. Vấn đề schema hiện tại

- `verified` quá rộng.
- Không có solve stage timings.
- Không có provenance.
- Không có transformation semantics.
- Không có truncation metadata.
- Không có interval/angle unit trong response chính.
- Không có engine version.
- Không có user-confirmation state.
- Không có retryability.
- Không có capability information.

## 33.2. Đề xuất

```json
{
  "request_id": "alg_...",
  "status": "solved",
  "interpretation": {
    "raw_input": "...",
    "canonical_input": "...",
    "source": "rule_based",
    "confirmed": true,
    "topic": "trig_equation",
    "variables": ["x"],
    "parameters": [],
    "domain": "R",
    "interval": null,
    "angle_unit": "radian"
  },
  "solution": {
    "kind": "periodic",
    "exact": "...",
    "approximate": null,
    "truncated": false
  },
  "steps": [],
  "verification": {
    "status": "independently_verified",
    "checks": [],
    "scope": "...",
    "engine": "sympy",
    "engine_version": "..."
  },
  "provenance": {
    "solver": "trig_solver",
    "solver_version": "...",
    "ai_extraction": false,
    "ai_explanation": false
  },
  "timings": {
    "interpret_ms": 2,
    "parse_ms": 3,
    "solve_ms": 20,
    "verify_ms": 5
  }
}
```

---

# 34. Checklist P1 — Transformation model

Mỗi bước nên nói rõ loại quan hệ toán học.

## Loại đề xuất

```text
equivalent
forward_implication
backward_implication
candidate_generation
domain_restriction
case_split
approximation
identity
definition
numeric_check
conclusion
```

## Ví dụ

Bình phương hai vế:

```json
{
  "relation": "forward_implication",
  "may_introduce_extraneous": true,
  "requires_back_substitution": true
}
```

Khử mẫu:

```json
{
  "relation": "equivalent_under_conditions",
  "conditions": ["denominator != 0"]
}
```

## Checklist

- [ ] Transformation type.
- [ ] Preconditions.
- [ ] Postconditions.
- [ ] Generated candidates.
- [ ] Lost solutions risk.
- [ ] Extraneous solutions risk.
- [ ] Evidence.
- [ ] Verification status.

---

# 35. Checklist P1 — Capability registry

Tạo registry dùng chung:

```json
{
  "topic": "trigonometry",
  "problem_types": [
    "equation",
    "expression"
  ],
  "domains": ["R"],
  "interval_supported": true,
  "angle_units": ["radian"],
  "input_formats": ["plain", "latex"],
  "verification_level": "partial"
}
```

## Checklist

- [ ] Frontend render option từ registry.
- [ ] Backend route theo registry.
- [ ] Toolbar theo registry.
- [ ] Example theo registry.
- [ ] Help page theo registry.
- [ ] Test registry-contract.
- [ ] Không hardcode danh sách topic ở nhiều nơi.

---

# 36. Checklist P1 — History và lưu bài (cá nhân)

> Ngoài scope: chia sẻ multi-user / collab.

- [ ] Lịch sử bài giải.
- [ ] Lưu đề gốc.
- [ ] Lưu canonical input.
- [ ] Lưu lựa chọn domain/interval.
- [ ] Lưu solver version.
- [ ] Lưu verification.
- [ ] Lưu AI provenance.
- [ ] Đặt tên.
- [ ] Pin.
- [ ] Xóa.
- [ ] Tìm kiếm.
- [ ] Tag lớp/chương.
- [ ] Không tính mở history là lượt solve mới.
- [ ] Re-run với version mới.
- [ ] So sánh kết quả cũ/mới.

---

# 37. Checklist P1 — Export và copy

- [x] Copy answer plain.
- [x] Copy answer LaTeX.
- [x] Copy full solution Markdown.
- [ ] Copy JSON.
- [ ] Export PDF.
- [ ] Export DOCX.
- [ ] Export HTML.
- [ ] Export image.
- [ ] Export teacher version.
- [ ] Export student worksheet without answer.
- [ ] Giữ verification metadata.
- [ ] Giữ warnings.
- [ ] Không copy hidden AI content.

---

# 38. Checklist P1 — Handoff sang module khác

- [ ] Vẽ đồ thị hàm.
- [x] Mở Function Analyzer (prefill).
- [ ] Mở simulation.
- [ ] Mở GeoGebra Lab.
- [ ] Vẽ tập nghiệm bất phương trình.
- [ ] Unit circle cho lượng giác.
- [ ] Complex plane.
- [ ] Number line.
- [ ] Sign chart.
- [ ] Probability tree.
- [ ] Không nhập lại đề.

---

# 39. Checklist P1 — Accessibility

- [ ] Accordion header là button.
- [ ] Hỗ trợ Enter/Space.
- [ ] `type="button"` đầy đủ.
- [ ] Focus state.
- [ ] KaTeX có MathML.
- [ ] Screen reader đọc công thức.
- [ ] Không chỉ dùng màu cho status.
- [ ] Progress có aria-live.
- [ ] Error gắn input.
- [ ] Keyboard toolbar.
- [ ] Mobile MathQuill usable.
- [ ] Reduced motion.
- [ ] Contrast.
- [ ] Copy button accessible.

---

# 40. Checklist P1 — Observability

- [x] Request ID.
- [ ] User/IP hash.
- [ ] Topic.
- [ ] Problem type.
- [ ] Input format.
- [ ] Parse status.
- [ ] Solve status.
- [ ] Verification status.
- [~] Stage timings (total_ms).
- [ ] Timeout stage.
- [ ] Expression complexity.
- [ ] Solver selected.
- [ ] SymPy version.
- [ ] AI provider/model.
- [ ] AI extraction fallback.
- [ ] AI explanation fallback.
- [ ] Error code.
- [ ] Không log raw sensitive input mặc định.
- [ ] Sample anonymized failures.

---

# 41. Checklist P1 — Testing strategy

## 41.1. Unit test

- [ ] Normalizer.
- [ ] Interpreter.
- [ ] Safe parser.
- [ ] Classifier.
- [ ] Domain.
- [ ] Solver.
- [ ] Verifier.
- [ ] Formatter.
- [ ] AI mapping.

## 41.2. Property-based test

- [ ] Generated polynomial equations.
- [ ] Rational equations.
- [ ] Inequalities.
- [ ] Systems.
- [ ] Differentiation identities.
- [ ] Integration derivative-back.
- [ ] Sequence formulas.
- [ ] Parameter boundaries.

## 41.3. Differential test

- [ ] So sánh SymPy method A/B.
- [ ] So sánh numerical root.
- [ ] So sánh direct substitution.
- [ ] So sánh finite differences.
- [ ] So sánh quadrature.
- [ ] Không phụ thuộc một engine path.

## 41.4. Security test

- [ ] Malicious parse strings.
- [ ] Deep nested expression.
- [ ] Huge integer.
- [ ] Huge factorial.
- [ ] Huge exponent.
- [ ] Many variables.
- [ ] Many equations.
- [ ] Timeout.
- [ ] Memory pressure.
- [ ] Concurrent flood.

## 41.5. Frontend E2E

- [ ] Natural input.
- [ ] Math input.
- [ ] Topic change.
- [ ] Domain change.
- [ ] Variables auto-detect.
- [ ] Interpretation confirmation.
- [ ] Error.
- [ ] Timeout.
- [ ] Cancel.
- [ ] Copy/export.
- [ ] Mobile.
- [ ] Keyboard.

---

# 42. Test matrix bắt buộc

## 42.1. Phương trình

- [ ] Linear.
- [ ] Quadratic.
- [ ] Cubic.
- [ ] Quartic.
- [ ] Rational.
- [ ] Radical.
- [ ] Absolute.
- [ ] Empty.
- [ ] Infinite.
- [ ] Z.
- [ ] N.
- [ ] C.
- [ ] ConditionSet.
- [ ] Extraneous root.
- [ ] Domain hole after cancellation.

## 42.2. Bất phương trình

- [ ] Polynomial.
- [ ] Rational.
- [ ] Chained.
- [ ] Not equal.
- [ ] Absolute.
- [ ] Radical.
- [ ] Log.
- [ ] Exponential.
- [ ] Trig.
- [ ] Empty.
- [ ] Universal.
- [ ] Z/N.
- [ ] Boundary.

## 42.3. Hệ

- [ ] 2×2.
- [ ] 3×3.
- [ ] Nonlinear.
- [ ] Infinite.
- [ ] Empty.
- [ ] Parameter.
- [ ] Variables omitted.
- [ ] Variables reordered.
- [ ] Domain restriction.

## 42.4. Lượng giác

- [ ] General R.
- [ ] `[0,2π)`.
- [ ] Degree interval.
- [ ] Basic sin.
- [ ] Basic cos.
- [ ] Tan domain.
- [ ] Double angle.
- [ ] a sin+b cos.
- [ ] Identity.
- [ ] Inequality.
- [ ] Periodic verification.

## 42.5. Mũ-log

- [ ] Same base.
- [ ] Log sum.
- [ ] Domain.
- [ ] Invalid base.
- [ ] Equation.
- [ ] Inequality.
- [ ] Symbolic set.
- [ ] No solution.
- [ ] Transcendental numeric.

## 42.6. Tham số

- [ ] Delta=0.
- [ ] Delta>0.
- [ ] Delta>=0.
- [ ] Delta<0.
- [ ] Positive all.
- [ ] a(parameter)=0.
- [ ] Fraction boundary.
- [ ] Far interval.
- [ ] Discrete set.
- [ ] Multiple cases.

## 42.7. Cấp số

- [ ] Arithmetic term.
- [ ] Arithmetic sum.
- [ ] Geometric term.
- [ ] Geometric sum.
- [ ] q=1.
- [ ] Fraction values.
- [ ] Fraction n rejected.
- [ ] Duplicate key.
- [ ] Unknown key.
- [ ] Huge n.
- [ ] Infer from list.

## 42.8. Tổ hợp

- [ ] C.
- [ ] A.
- [ ] Factorial.
- [ ] Coefficient.
- [ ] k>n.
- [ ] Negative.
- [ ] Huge n.
- [ ] Malicious coefficient expression.
- [ ] Probability request returns honest unsupported.

## 42.9. Giải tích

- [ ] Derivative.
- [ ] Higher order.
- [ ] Definition.
- [ ] Piecewise.
- [ ] Limit two-sided.
- [ ] One-sided.
- [ ] DNE.
- [ ] Infinity.
- [ ] Indefinite integral.
- [ ] Definite integral.
- [ ] Improper integral.
- [ ] Divergent integral.
- [ ] Unevaluated result.
- [ ] Continuity.
- [ ] Invalid order.
- [ ] Invalid direction.

## 42.10. AI extraction

- [ ] AI agrees with user.
- [ ] AI conflicts topic.
- [ ] AI conflicts domain.
- [ ] AI conflicts variables.
- [ ] AI low confidence.
- [ ] AI malformed JSON.
- [ ] Provider timeout.
- [ ] Fallback.
- [ ] Rule-based success without AI.
- [ ] User confirmation.

## 42.11. AI explanation

- [ ] No step deletion.
- [ ] No formula mutation.
- [ ] No reordering.
- [ ] Correct step IDs.
- [ ] Safe text.
- [ ] Timeout.
- [ ] Fallback deterministic.
- [ ] Provenance badge.

---

# 43. Kiến trúc mục tiêu đề xuất

```text
AlgebraInput
    ↓
InputPrecheck
    ↓
RuleBasedInterpreter
    ↓
OptionalAIInterpreter
    ↓
InterpretationDiff
    ↓
UserConfirmation
    ↓
SafeMathParser
    ↓
ProblemClassifier
    ↓
SolvePlanner
    ↓
IsolatedDeterministicSolver
    ↓
IndependentVerifier
    ↓
DeterministicStepBuilder
    ↓
OptionalAITextRewriter
    ↓
ResultWorkspace
```

## 43.1. Nguyên tắc

- User explicit choice ưu tiên cao nhất.
- AI không được sửa answer.
- AI không được sửa formula.
- Solver và verifier không nên là cùng một thao tác duy nhất.
- Không verified khi không có evidence.
- Không chạy SymPy nặng trong API process.
- Không có input unlimited.
- Mọi capability phải được registry hóa.
- UI chỉ hiển thị chức năng backend hỗ trợ.
- Kết quả phải truy vết được.

---

# 44. State machine đề xuất

```text
draft
→ interpreting
→ needs_confirmation
→ confirmed
→ parsing
→ planning
→ solving
→ verifying
→ solved
→ partially_verified
→ explanation_pending
→ ready
```

Trạng thái lỗi:

```text
input_invalid
ambiguous
parse_failed
unsupported
complexity_limited
timeout
solve_failed
verification_failed
ai_extraction_failed
internal_error
```

---

# 45. Solve plan đề xuất

Trước khi chạy solver, tạo plan:

```json
{
  "problem_type": "rational_equation",
  "variable": "x",
  "domain": "R",
  "steps": [
    "determine_domain",
    "clear_denominator",
    "solve_numerator",
    "filter_candidates",
    "substitute_original"
  ],
  "risks": [
    "domain_loss",
    "extraneous_solution"
  ]
}
```

## Checklist

- [ ] Plan typed.
- [ ] Plan deterministic.
- [ ] Plan visible.
- [ ] Plan can select solver.
- [ ] Plan informs verifier.
- [ ] Plan defines required checks.
- [ ] Plan drives step builder.
- [ ] Plan versioned.

---

# 46. Lộ trình triển khai

## Giai đoạn 1 — Bảo mật và độ đúng

- [ ] Safe parser.
- [ ] Isolated worker.
- [ ] Timeout.
- [ ] Deterministic rate limit.
- [ ] Complexity limits.
- [ ] Error codes.
- [ ] User field precedence.
- [ ] Variables auto-detect.
- [ ] Trig interval fix.
- [ ] Verification semantics.

## Giai đoạn 2 — Sửa solver trọng yếu

- [ ] Exp/log/trig inequality routing.
- [ ] Chained inequality.
- [ ] Not-equal.
- [ ] Parameter degeneracy.
- [ ] Sequence n validation.
- [ ] Calculus independent checks.
- [ ] Continuity verification.
- [ ] Factorial limits.
- [ ] Dọn dead patch code.

## Giai đoạn 3 — UX minh bạch

- [ ] Interpretation confirmation.
- [ ] Canonical input display.
- [ ] Capability-driven toolbar.
- [ ] Interval.
- [ ] Angle unit.
- [ ] Variable/parameter chips.
- [ ] Clear stale result.
- [ ] Progress/cancel.
- [ ] Full verification panel.

## Giai đoạn 4 — Lời giải sư phạm

- [ ] Transformation semantics.
- [ ] Goal/why/pitfall/check UI.
- [ ] AI rewrite theo step ID.
- [ ] Detail modes.
- [ ] Hint mode.
- [ ] Grade-aware method.
- [ ] Graph handoff.

## Giai đoạn 5 — Sản phẩm hoàn chỉnh

- [ ] History.
- [ ] Export.
- [ ] Share.
- [ ] Practice generation.
- [ ] Teacher mode.
- [ ] Analytics.
- [ ] Curriculum mapping.
- [ ] Probability solver.

---

# 47. Tiêu chí hoàn thành phiên bản ổn định đầu tiên

Phiên bản chỉ nên được xem là ổn định khi:

- [ ] Parser đầu vào đã được khóa an toàn.
- [ ] Solve chạy trong môi trường có timeout.
- [ ] Deterministic endpoint có rate limit.
- [ ] Có complexity precheck.
- [ ] AI không ghi đè lựa chọn explicit.
- [ ] Người dùng xác nhận canonical input.
- [ ] Hệ tự nhận đúng biến khi frontend không chỉ định.
- [ ] Lượng giác trên R trả nghiệm tổng quát.
- [ ] Interval được sử dụng đúng.
- [ ] Degree/radian rõ ràng.
- [ ] Verification không còn đồng nghĩa “SymPy chạy xong”.
- [ ] ConditionSet không được gọi solved/verified.
- [ ] Vô nghiệm có proof status.
- [ ] Bất phương trình log/trig route đúng.
- [ ] Chained inequality hoạt động.
- [ ] `!=` hoạt động.
- [ ] Bài tham số tách case a=0.
- [ ] Sequence reject n không nguyên.
- [ ] Factorial/combination có giới hạn.
- [ ] Derivative/integral/limit có cross-check.
- [ ] Continuity có checks không rỗng.
- [ ] Options schema được thực thi.
- [ ] API error code cụ thể.
- [ ] Mã patch thừa đã xóa.
- [ ] Frontend hiển thị interpretation.
- [ ] Frontend hiển thị verification evidence.
- [ ] Frontend hiển thị đủ dữ liệu step.
- [ ] AI explanation không được xóa/đổi bước toán học.
- [ ] Có E2E test các luồng chính.
- [ ] Có fuzz/security test parser.
- [ ] Có benchmark input nặng.
- [ ] Có bộ đề regression THPT.

---

# 48. Mười lăm hạng mục ưu tiên cao nhất

```text
1. Sandbox và timeout cho SymPy
2. Rate limit solver deterministic
3. Khóa parser/sympify bằng SafeMath AST
4. Không cho AI ghi đè topic/domain/variables explicit
5. Sửa biến mặc định x làm sai hệ phương trình
6. Sửa lượng giác mặc định [0,2π) khi miền là R
7. Thiết kế lại verification status
8. Không gọi symbolic nonempty set là verified
9. Sửa routing bất phương trình mũ-log/lượng giác
10. Tách trường hợp a(parameter)=0
11. Reject n cấp số không nguyên
12. Giới hạn factorial/combination/expression complexity
13. Thêm xác nhận canonical input
14. AI explanation chỉ rewrite văn bản, không thay cấu trúc bước
15. Dọn new_calculus_features.py và patch.py
```

---

# 49. Kết luận

`/algebra-solver` hiện có nền tảng tốt hơn một chatbot giải toán thuần LLM:

- Có deterministic solver.
- Có SymPy.
- Có parser và normalizer.
- Có nhiều solver chuyên biệt.
- Có bước giải sư phạm.
- Có verification report.
- Có AI extraction và AI explanation được tách khỏi answer.

Tuy nhiên, ba vấn đề lớn nhất hiện tại là:

## 49.1. Trust boundary chưa đủ chặt

Đáp án deterministic không đồng nghĩa đề đã được diễn giải đúng. AI extraction có thể làm thay đổi:

- Dạng bài.
- Biến.
- Tham số.
- Miền.
- Canonical input.

Trong khi người dùng không được xác nhận.

## 49.2. “Verified” đang bị dùng quá rộng

Nhiều report chỉ chứng minh rằng:

```text
SymPy đã trả một object
```

chứ chưa chứng minh:

```text
Kết quả đúng, đầy đủ, đúng miền và tương đương với đề gốc
```

## 49.3. Tài nguyên tính toán chưa được bảo vệ

Endpoint deterministic:

- Có thể không cần đăng nhập.
- Không rate limit.
- Không timeout.
- Dùng parser và SymPy trên input người dùng.
- Có các phép tính rất nặng.

Định hướng cần chuyển từ:

> SymPy trả kết quả thì hiển thị lời giải.

sang:

> Hiểu đúng đề, giải trong sandbox, kiểm chứng theo phạm vi rõ ràng, rồi mới công bố kết quả.

Thứ tự phát triển phù hợp nhất:

```text
Bảo mật
→ Độ đúng
→ Verification
→ Interpretation confirmation
→ Solver coverage
→ UX sư phạm
→ History/export/share
→ Mở rộng chương trình THPT
```

Không nên mở rộng thêm nhiều dạng toán trước khi hoàn thiện parser an toàn, timeout, biến/miền/interval và semantics của trạng thái kiểm chứng.

---

# 43. Lộ trình nâng cấp (đối chiếu 10/07/2026)

> Phạm vi: single-user correctness/safety/UX. Ngoài scope: multi-user, share collab.

## Wave 0 — Doc sync

- [x] Cập nhật metadata, §5, P0-03, P1-13, test list, roadmap.

## Wave 1 — Safety (Slice A một phần)

- [x] `global_dict` + precheck complexity cơ bản.
- [x] Timeout deterministic (`algebra_solve_timeout_seconds`).
- [x] Token allowlist (safe_math-inspired) + process isolation killable worker (`algebra_process_isolation`).
- [~] Concurrent limit có; chưa cost-based / daily quota algebra.

## Wave 2 — User intent & AI control

- [x] Variables default rỗng + system auto x,y.
- [x] AI merge: không đè topic/domain/variables explicit.
- [x] Natural: rule-based trước (backend + FE), AI opt-in checkbox (cần đăng nhập khi bật).
- [x] Interpretation confirmation panel (pre-solve cho natural/AI).

## Wave 3 — Correctness

- [x] Trig general solution trên R (không cắt [0, 2π) mặc định).
- [x] Interval selector UI (preset + custom) + honor interval request backend.
- [x] Verification semantics: symbolic set / sample-only → partially_verified; ConditionSet warn; exception → warn.
- [x] Routing inequality exp-log/trig; chained `0<x<1`; `!=` complement.
- [x] Sequence n: reject phân số/thập phân (SEQUENCE_N_NOT_INTEGER).
- [x] Combinatorics label UI → “Tổ hợp”; ẩn nút ° toolbar; cap n!≤20, C/A n≤30.
- [x] Parameter case-split a(m)=0.
- [x] Options verify/return_steps/max_solutions; timeout HTTP 504; xóa patch/new_calculus/test_limit.
- [x] EmptySet: sample corroboration + warn chưa full unsat proof.

## Wave 4 — Product UX

- [x] Interpretation panel (canonical, source, domain, variables, chips).
- [x] Stale result badge khi sửa input sau khi đã giải.
- [x] Verification summary + toggle hiện checks pass.
- [x] Copy đáp án / LaTeX / Markdown.
- [x] Handoff Function Analyzer (sessionStorage prefill).
- [x] Step expand: goal / why / operation / pitfall / check.
- [x] Interval preset [0,2π) + custom bounds trên FE + honor backend.
- [x] AI explanation lock: không tạo/xóa/đảo step deterministic.
- [x] Toolbar/capability registry (ẩn capability chưa hỗ trợ).
- [~] Export cá nhân `.md`; chưa PDF/DOCX dedicated API.

## Wave 5 — Tests & observability

- [x] AI explainer merge lock tests.
- [x] Parameter case-split a(m).
- [x] Trig interval filter + request_id/timings_ms.
- [x] Correctness matrix mở rộng (wave3/5 tests).
- [~] Security parser fuzz + isolation tests; chưa full concurrent flood matrix.
- [x] Stage timings: interpret/parse/solve/options/total_ms.

## Review fixes (post /review)

- [x] Chained inequality verification checks all relations (And).
- [x] `solve_interval` honored in inequality/equation/exp_log (not only trig equality).
- [x] Timeout path does not call AI or second solve after first timeout.
- [x] Sticky domain on AI merge; sanitized extraction error messages.
- [x] Invalid interval warns instead of silent drop.
- [x] Stronger parameter a(m) case-split assertions + extra regression tests.

## Tiếp theo sau review fixes

- [x] Calculus independent verify (diff-back / finite-diff / limit recompute / unevaluated detect).
- [x] Derivative order bound 1..5.
- [x] Toolbar capability registry (ẩn sum/product/vector/set/logic chưa hỗ trợ).
- [x] Export cá nhân: tải file Markdown (.md).
- [x] Concurrent algebra limit (`algebra_max_concurrent`, HTTP 429).
- [x] Security fuzz tests parser (parens/powers/huge int/oversized input).
- [x] Process isolation / hard kill SymPy worker (`process_worker` + `algebra_process_isolation`).
- [x] Export PDF algebra API (`POST /api/algebra/export/pdf`); DOCX vẫn backlog.
- [x] Daily quota + cost-based soft limit + circuit breaker timeout.
- [x] Probability (P/P_not/P_and/Punion/Pcond/Pcomb), angle_unit, history server+local.
- [ ] Full safe_math AST multi-symbol (token allowlist + process isolation đã có).

## Review #2 fixes

- [x] Concurrent gate: atomic HTTP slots + worker thread counting (timeout orphans still count).
- [x] Semaphore acquire race eliminated (no wait_for on acquire).
- [x] Interval bounds via restricted `parse_interval_bound` allowlist.
- [x] FE clears result on API error (504/429 no longer show old answer).
- [x] `max_solutions` syncs answer + answer_latex + solution_set.latex/text.
- [x] Submit lock ref; deferred revokeObjectURL on .md download.
- [x] Mixed eq+ineq → unsupported classification.

## Review #3 + remaining P0/P1 (10/07/2026)

- [x] AlgebraSlot giữ capacity qua multi-worker + timeout orphan.
- [x] Interval allowlist `-pi`/`pi/2`/`e`.
- [x] Cap factorial/combinatorics.
- [x] Empty-set sample corroboration.
- [x] Token allowlist pre-parse (no attribute / unknown names).
- [x] Process isolation killable.
- [x] Stage timings interpret/parse/solve.
- [x] FE confirm panel + interval custom editor.
