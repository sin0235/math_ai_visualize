# CHECKLIST RÀ SOÁT VÀ CẢI TIẾN CHỨC NĂNG `/analyzer`

## 1. Thông tin tài liệu

- **Dự án:** AI Math Renderer
- **Chức năng:** `https://math-renderer.sin-studio.tech/analyzer`
- **Tên chức năng hiện tại:** Khảo sát hàm số
- **Repository rà soát:** `sin0235/math_ai_visualize`
- **Nhánh rà soát:** `product`
- **Ngày rà soát:** 21/06/2026
- **Phương pháp:** Rà soát tĩnh mã nguồn frontend, API, schema, parser, bộ phân tích hàm, bộ dựng đồ thị, OCR, công cụ GTLN/GTNN, tương giao, tiếp tuyến, biến đổi đồ thị, bảng biến thiên và test hiện có.
- **Giới hạn:** Chưa chạy toàn bộ kiểm thử end-to-end trên production, chưa fuzz parser, chưa benchmark CPU/RAM thực tế, chưa kiểm thử trực tiếp GeoGebra trên nhiều thiết bị và chưa đối chiếu với một bộ đề khảo sát hàm số THPT chuẩn hóa quy mô lớn.

---

# 2. Phạm vi rà soát

## 2.1. Frontend

- `frontend/src/App.tsx`
- `frontend/src/api/analyze.ts`
- `frontend/src/components/FunctionAnalyzerPanel.tsx`
- `frontend/src/components/function-analyzer/useFunctionAnalysis.ts`
- `frontend/src/components/function-analyzer/AnalyzerInput.tsx`
- `frontend/src/components/function-analyzer/AnalyzerToolControls.tsx`
- `frontend/src/components/function-analyzer/AnalyzerResult.tsx`
- `frontend/src/components/function-analyzer/FunctionGraph.tsx`
- `frontend/src/components/function-analyzer/VariationTable.tsx`
- `frontend/src/components/function-analyzer/constants.ts`
- `frontend/src/components/AppPages.tsx`
- `frontend/src/hooks/useNotifications.ts`
- `frontend/src/refactor-boundaries.test.tsx`

## 2.2. Backend

- `backend/app/api/routes_function_analysis.py`
- `backend/app/schemas/analysis.py`
- `backend/app/services/function_analyzer.py`
- `backend/app/services/function_graph_builder.py`

## 2.3. Test

- `backend/tests/test_function_analyzer.py`
- `backend/tests/test_math_core_large_scale.py`
- `backend/tests/test_refactor_boundaries.py`
- Các test contract frontend hiện có.

---

# 3. Quy ước mức ưu tiên

| Mức | Ý nghĩa |
|---|---|
| **P0** | Có thể trả kết luận toán học sai, thiếu, gây hiểu nhầm nghiêm trọng, mở lỗ hổng parser, làm cạn tài nguyên hoặc làm đồ thị mâu thuẫn với kết quả phân tích. |
| **P1** | Cần thiết để nâng độ tin cậy, khả năng giải thích, UX, khả năng bảo trì, tính nhất quán và phạm vi chương trình THPT. |
| **P2** | Tính năng nâng cao phục vụ giáo viên, học sinh, cộng tác, luyện tập, chia sẻ, xuất bản và nghiên cứu. |

Quy ước trạng thái:

```text
[ ] Chưa thực hiện
[-] Đang thực hiện
[x] Đã hoàn thành
[!] Cần quyết định sản phẩm hoặc kiến trúc
```

---

# 4. Mục tiêu sản phẩm đề xuất

Nâng cấp `/analyzer` từ công cụ:

```text
Nhập biểu thức
→ SymPy tính một số đại lượng
→ Dựng đồ thị
→ Hiển thị bảng biến thiên
```

thành một hệ thống khảo sát hàm số có thể:

```text
Nhập hàm
→ Chuẩn hóa và xác nhận cách hiểu
→ Xác định biến, tham số, miền và giả thiết
→ Phân tích theo các miền liên thông
→ Tính giới hạn, đạo hàm, dấu và điểm đặc biệt
→ Kiểm chứng chéo kết quả
→ Lập bảng biến thiên có dữ liệu giới hạn thật
→ Dựng đồ thị bảo toàn miền xác định
→ Hiển thị mức chính xác và cảnh báo
→ Cho phép khảo sát tham số, khoảng, đường thẳng và biến đổi
→ Lưu, xuất, chia sẻ và tạo bài luyện tập
```

Nguyên tắc cốt lõi:

> Đồ thị, bảng biến thiên và kết luận chữ phải cùng xuất phát từ một mô hình toán học có cấu trúc; không được để frontend tự suy diễn giá trị toán học từ ký hiệu mũi tên hoặc dữ liệu lấy mẫu.

---

# 5. Tóm tắt đánh giá

## 5.1. Điểm mạnh hiện tại

- [x] Có route riêng `/analyzer`.
- [x] Có API `/api/analyze`.
- [x] Có OCR ảnh.
- [x] Có parser cho plain text và một phần LaTeX.
- [x] Có tập xác định.
- [x] Có tập giá trị.
- [x] Có đạo hàm cấp một và cấp hai.
- [x] Có điểm dừng.
- [x] Có phân loại cực đại/cực tiểu ở một số trường hợp.
- [x] Có điểm uốn.
- [x] Có khoảng đồng biến/nghịch biến.
- [x] Có khoảng lồi/lõm.
- [x] Có tiệm cận ngang, đứng và xiên.
- [x] Có giao điểm với trục.
- [x] Có bảng biến thiên.
- [x] Có đồ thị GeoGebra.
- [x] Có SVG fallback.
- [x] Có công cụ GTLN/GTNN theo vùng khảo sát.
- [x] Có công cụ tương giao với đường thẳng.
- [x] Có tiếp tuyến tại điểm.
- [x] Có biến đổi đồ thị.
- [x] Có một phần xử lý tham số `m`.
- [x] Có debounce cho thay đổi công cụ.
- [x] Có request ID phía frontend để bỏ qua response cũ.
- [x] Có một số test parser và happy path.

## 5.2. Điểm yếu trọng yếu

- [ ] Parser dùng `parse_expr` với đầu vào không tin cậy nhưng chưa có sandbox và timeout.
- [ ] Endpoint phân tích deterministic không có rate limit.
- [ ] Phép phân tích CPU-bound chạy trực tiếp trong async API worker.
- [ ] Module dùng `sp.*` nhưng không import `sympy as sp`; lỗi bị `try/except` nuốt nên nhánh symbolic chính xác âm thầm không chạy.
- [ ] Bảng biến thiên frontend tự suy ra giá trị ở `±∞` từ chiều mũi tên.
- [ ] Giá trị biên của bảng biến thiên có thể sai với hàm bị chặn hoặc có giới hạn hữu hạn.
- [ ] GTLN/GTNN trên khoảng/đoạn không xét đầy đủ điểm gián đoạn bên trong.
- [ ] Hàm có tiệm cận đứng nằm trong đoạn có thể bị kết luận có GTLN/GTNN hữu hạn.
- [ ] Khoảng mở của hàm hằng có thể bị kết luận không có GTLN/GTNN.
- [ ] Điểm uốn dùng bước thử cố định `0.001`, dễ sai theo thang đo.
- [ ] Lồi/lõm không được tính nếu `f''(x)=0` không có nghiệm.
- [ ] Tiệm cận đứng chỉ tìm từ mẫu số sau `cancel`, bỏ sót nhiều hàm.
- [ ] Nghiệm phức có thể lọt vào danh sách giao điểm Ox.
- [ ] Danh sách nghiệm/giao điểm bị cắt im lặng.
- [ ] Numeric root fallback chỉ quét `[-20,20]`, chỉ phát hiện đổi dấu và không tinh chỉnh nghiệm.
- [ ] Đồ thị dùng biểu thức đã rút gọn, có thể xóa lỗ hổng miền xác định.
- [ ] Đồ thị không truyền tập xác định thật vào GeoGebra.
- [ ] Animation có chu kỳ 160 ms nhưng debounce 220 ms, nên request có thể liên tục bị hủy lịch.
- [ ] Mỗi thay đổi slider có thể yêu cầu phân tích toàn bộ hàm từ đầu.
- [ ] Tham số `m` mặc định bằng 1 và bị clamp âm thầm nhưng UI không có control tham số.
- [ ] OCR tự phân tích ngay, không cho người dùng xác nhận biểu thức.
- [ ] Hướng dẫn quảng bá một số hàm không thật sự tương thích với allowlist.
- [ ] Schema dùng nhiều `dict[str, Any]`, thiếu enum và validation.
- [ ] Không có verification report, provenance, timing hoặc confidence.
- [ ] Không có lịch sử riêng cho analyzer.
- [ ] Không có xuất báo cáo khảo sát.
- [ ] Test hiện tại chưa bao phủ các trường hợp có thể làm sai toán học.

---

# 6. Kiến trúc hiện tại

```text
AnalyzerInput
    ↓
useFunctionAnalysis
    ↓
POST /api/analyze
    ↓
function_analyzer.analyze_function
    ├── parse/preprocess
    ├── domain/range
    ├── derivative
    ├── critical points
    ├── concavity
    ├── asymptotes
    ├── intercepts
    ├── interval tool
    ├── line tool
    ├── parameter conditions
    └── transform preview
    ↓
function_graph_builder
    ├── MathScene
    ├── GeoGebra commands
    └── sampled graph points
    ↓
AnalyzerResult
    ├── GeoGebra or SVG graph
    ├── quick summary
    ├── variation table
    └── tool results
```

## 6.1. Luồng OCR hiện tại

```text
Ảnh
→ upload
→ OCR
→ LLM trích biểu thức
→ analyze_function
→ dựng graph
→ frontend nhận cả expression và kết quả
```

Khoảng trống:

- Không có bước chỉ trích xuất.
- Không có confidence.
- Không có preview ảnh/crop.
- Không có xác nhận biểu thức.
- Không có diff giữa OCR text và biểu thức.
- Không có khả năng sửa trước khi tính.

## 6.2. Luồng công cụ tương tác hiện tại

```text
Bật một công cụ
→ thay slider/input
→ debounce 220 ms
→ gọi lại toàn bộ /api/analyze
→ tính lại domain, range, đạo hàm, tiệm cận, graph
→ trả full response
```

Khoảng trống:

- Không cache base analysis.
- Không có endpoint tool riêng.
- Không abort request cũ phía server.
- Animation có thể không gửi request trong khi chạy.
- Backend vẫn chịu tải dù frontend bỏ response cũ.

---

# 7. Checklist P0 — Bảo mật parser

# P0-01. Không dùng `parse_expr` trực tiếp trên input người dùng trong API worker

## Hiện trạng

```python
expr = parse_expr(
    cleaned,
    local_dict=locals_map,
    transformations=standard_transformations
        + (implicit_multiplication_application,),
)
```

Không truyền `global_dict` tối thiểu.

## Rủi ro

- Namespace mặc định của SymPy có thể cho phép nhiều constructor ngoài phạm vi công bố.
- Chỉ kiểm tra `free_symbols` sau parse không đủ để kiểm soát AST.
- Biểu thức có thể tạo cây rất lớn.
- Có thể kích hoạt phép evaluate nặng ngay trong parse.
- Parser chạy cùng process với API.

## Checklist

- [ ] Thiết kế SafeMath AST.
- [ ] Tokenize trước khi parse.
- [ ] Chỉ cho phép node type đã đăng ký.
- [ ] Chỉ cho phép function đã đăng ký.
- [ ] Không cho attribute access.
- [ ] Không cho lambda.
- [ ] Không cho string literal.
- [ ] Không cho object constructor tùy ý.
- [ ] Không cho matrix không giới hạn.
- [ ] Không cho Piecewise quá nhiều nhánh.
- [ ] Không dùng global namespace mặc định.
- [ ] Đặt `evaluate=False` ở giai đoạn parse khi phù hợp.
- [ ] Tách parse và simplify.
- [ ] Chạy trong process riêng.
- [ ] Fuzz parser.
- [ ] Security regression test.

---

# P0-02. Loại bỏ đường parse thứ hai bằng `sympify`

## Hiện trạng

`function_graph_builder._sample_graph_points` tiếp tục parse lại chuỗi biểu thức:

```python
sympify(expression.replace("^", "**"), locals=...)
```

## Rủi ro

- Hai parser cho cùng một input.
- Hai allowlist khác nhau.
- Kết quả phân tích và kết quả vẽ có thể khác.
- Mở thêm bề mặt tấn công.
- Không bảo toàn AST và miền.

## Checklist

- [ ] Chỉ parse một lần.
- [ ] Truyền AST đã duyệt sang graph builder.
- [ ] Không serialize rồi parse lại.
- [ ] Dùng canonical expression object hoặc safe IR.
- [ ] Kiểm tra hash/version của IR.
- [ ] Không dùng `sympify` với input gốc.

---

# P0-03. Thêm giới hạn độ phức tạp

- [ ] Giới hạn số ký tự.
- [ ] Giới hạn số token.
- [ ] Giới hạn AST nodes.
- [ ] Giới hạn độ sâu AST.
- [ ] Giới hạn số hàm lồng nhau.
- [ ] Giới hạn số Piecewise branch.
- [ ] Giới hạn mũ.
- [ ] Giới hạn kích thước integer.
- [ ] Giới hạn degree.
- [ ] Giới hạn số singularity.
- [ ] Giới hạn số nghiệm.
- [ ] Giới hạn kích thước response.
- [ ] Giới hạn số điểm graph.
- [ ] Giới hạn số GeoGebra command.
- [ ] Trả `ANALYZER_COMPLEXITY_LIMIT`.
- [ ] Ghi complexity score.

---

# 8. Checklist P0 — Timeout, rate limit và isolation

# P0-04. Thêm timeout tổng và timeout theo stage

Các phép có thể rất nặng:

- `continuous_domain`
- `function_range`
- `simplify`
- `diff`
- `solve`
- `solveset`
- `singularities`
- `limit`
- `Integral(...).evalf()`
- `lambdify`
- GeoGebra scene generation

## Checklist

- [ ] Timeout parse.
- [ ] Timeout simplify.
- [ ] Timeout domain.
- [ ] Timeout range.
- [ ] Timeout derivative.
- [ ] Timeout root solving.
- [ ] Timeout limits.
- [ ] Timeout interval tool.
- [ ] Timeout line tool.
- [ ] Timeout graph sampling.
- [ ] Timeout toàn request.
- [ ] Kill worker process.
- [ ] Trả stage bị timeout.
- [ ] Cho phép partial response.
- [ ] Không tiếp tục graph khi core analysis timeout.

---

# P0-05. Rate limit `/api/analyze`

## Hiện trạng

`/api/analyze/ocr` có rate limit và yêu cầu đăng nhập.

`/api/analyze` chỉ kiểm tra trusted origin.

## Rủi ro

- CPU DoS không cần đăng nhập.
- Spam `function_range` hoặc `solve`.
- Slider/animation phát sinh nhiều request.
- Bypass quota OCR bằng nhập công thức trực tiếp.

## Checklist

- [ ] Rate limit theo IP.
- [ ] Rate limit theo user.
- [ ] Concurrent limit.
- [ ] Cost-based limit.
- [ ] Cache identical request.
- [ ] Deduplicate in-flight request.
- [ ] Quota analyzer riêng.
- [ ] Quota tool request riêng.
- [ ] Circuit breaker.
- [ ] Backpressure.
- [ ] 429 có retry-after.

---

# P0-06. Không chạy CPU-bound code trực tiếp trong async endpoint

## Checklist

- [ ] Process pool hoặc dedicated worker.
- [ ] Không block event loop.
- [ ] Job ID.
- [ ] Cancellation.
- [ ] Worker health.
- [ ] Memory limit.
- [ ] CPU time limit.
- [ ] Worker recycle.
- [ ] Queue depth metric.
- [ ] Graceful overload response.

---

# 9. Checklist P0 — Lỗi import làm mất nhánh symbolic

# P0-07. Bổ sung và kiểm soát namespace `sympy as sp`

## Hiện trạng

Module import nhiều symbol riêng lẻ nhưng không có:

```python
import sympy as sp
```

Trong khi các hàm sau dùng `sp.*`:

- `_sign_intervals`
- `_classify_stationary_point`
- Một số xử lý tập hợp và giới hạn.

Các lệnh này nằm trong `try/except Exception`, vì vậy `NameError` bị nuốt.

## Hậu quả

- Nhánh giải dấu symbolic không chạy.
- Nhánh giới hạn đạo hàm trái/phải để phân loại cực trị không chạy.
- Hệ thống âm thầm rơi xuống numeric sampling.
- Test happy path vẫn có thể pass.
- Người dùng không nhận cảnh báo về việc hạ cấp phương pháp.

## Checklist

- [ ] Import namespace nhất quán.
- [ ] Không trộn import symbol và namespace tùy tiện.
- [ ] Không dùng broad exception để che lỗi lập trình.
- [ ] Tách `SymPyNotImplementedError` khỏi `NameError`.
- [ ] Fail test khi exact branch không được thực thi.
- [ ] Coverage test cho từng branch.
- [ ] Static lint `F821`.
- [ ] Type check.
- [ ] CI chặn undefined name.
- [ ] Ghi method used trong response.

---

# 10. Checklist P0 — Tập xác định và miền liên thông

# P0-08. Dùng tập xác định làm nguồn sự thật cho toàn bộ phân tích

## Hiện trạng

Tập xác định được tính nhưng nhiều bước sau không giao với tập xác định:

- Nghiệm đạo hàm.
- Khoảng tăng giảm.
- Khoảng lồi lõm.
- Giao điểm.
- GTLN/GTNN.
- Sampling graph.
- Tương giao đường thẳng.

## Checklist

- [ ] Lưu domain dưới dạng SymPy Set/IR.
- [ ] Phân rã domain thành connected components.
- [ ] Mọi critical point phải thuộc domain.
- [ ] Mọi interval monotonic phải giao domain.
- [ ] Mọi concavity interval phải giao domain.
- [ ] Mọi intercept phải thuộc domain.
- [ ] Mọi line intersection phải thuộc domain.
- [ ] Mọi graph segment phải thuộc domain.
- [ ] Mọi endpoint phải xét open/closed.
- [ ] Không dùng chuỗi domain làm nguồn tính toán.

---

# P0-09. Không dùng biểu thức đã rút gọn để vẽ nếu làm mất lỗ hổng miền

## Ví dụ

```text
f(x) = (x^2 - 1)/(x - 1)
```

Sau rút gọn:

```text
f(x) = x + 1
```

nhưng hàm gốc không xác định tại `x=1`.

## Hiện trạng

Graph builder ưu tiên `evaluated_expression`.

## Rủi ro

- Đồ thị vẽ liền qua lỗ hổng.
- Bảng và domain nói một điều, hình nói điều khác.
- Giao điểm tại điểm bị loại có thể xuất hiện.

## Checklist

- [ ] Giữ original expression.
- [ ] Giữ simplified expression riêng.
- [ ] Vẽ theo original domain.
- [ ] Render removable hole.
- [ ] Không thêm intercept tại điểm bị loại.
- [ ] Có annotation “điểm khuyết”.
- [ ] Test cancellation holes.
- [ ] GeoGebra command có domain restriction.

---

# 11. Checklist P0 — Bảng biến thiên

# P0-10. Không tự suy ra giá trị tại `±∞` từ mũi tên

## Hiện trạng frontend

Khi row biên không có `y`, frontend suy luận:

```text
nếu tăng → -∞ ở đầu trái, +∞ ở đầu phải
nếu giảm → +∞ ở đầu trái, -∞ ở đầu phải
```

## Sai với các hàm

- `e^x`
- `1/x`
- `arctan(x)`
- Hàm hữu tỉ có tiệm cận ngang.
- Hàm tăng nhưng bị chặn.
- Hàm giảm nhưng bị chặn.
- Hàm tuần hoàn.
- Hàm chỉ có miền nửa trục.

## Checklist

- [ ] Backend tính limit ở từng boundary.
- [ ] Variation row có `left_limit`.
- [ ] Variation row có `right_limit`.
- [ ] Boundary có exact value.
- [ ] Boundary có status finite/infinite/DNE/unknown.
- [ ] Frontend chỉ render dữ liệu backend.
- [ ] Không suy luận từ arrow.
- [ ] Không dùng `∞` khi chưa tính được.
- [ ] Hiển thị `?` hoặc “chưa xác định”.
- [ ] Test hàm bị chặn.

---

# P0-11. Bảng biến thiên phải có giới hạn hai phía tại tiệm cận đứng

## Hiện trạng

Row tiệm cận chỉ có:

```text
x
kind = asymptote
y = null
```

## Thiếu

- Giới hạn trái.
- Giới hạn phải.
- Dấu vô cực.
- Miền hai bên.
- Arrow tách hai nhánh.

## Checklist

- [ ] `limit_left`.
- [ ] `limit_right`.
- [ ] Hai cột giá trị riêng.
- [ ] Hai nhánh biến thiên riêng.
- [ ] Không nối đường qua tiệm cận.
- [ ] Hiển thị `||`.
- [ ] Test `1/x`.
- [ ] Test `1/(x-1)^2`.
- [ ] Test tan.
- [ ] Test log tại biên miền.

---

# P0-12. Không biến trạng thái “không biết” thành mũi tên ngang

## Hiện trạng

Nếu không xác định được chiều:

```text
arrow_to_next = "→"
```

Frontend hiển thị như hàm hằng.

## Checklist

- [ ] `direction = unknown`.
- [ ] Không dùng arrow ngang cho unknown.
- [ ] Chỉ dùng ngang khi chứng minh hàm hằng.
- [ ] Hiển thị cảnh báo.
- [ ] Ghi verification status từng interval.
- [ ] Không gọi bảng biến thiên hoàn chỉnh khi có unknown.

---

# P0-13. Không xây bảng biến thiên từ chuỗi interval đã format

## Hiện trạng

Backend:

- Format interval thành chuỗi.
- Parse chuỗi lại bằng regex.
- Dùng số giả `±1e10`.
- Chọn midpoint.
- Gán mũi tên.

## Checklist

- [ ] Dùng structured interval object.
- [ ] Không parse ngược display string.
- [ ] Không thay vô cực bằng số lớn giả.
- [ ] Dùng SymPy Set.
- [ ] Ghi open/closed.
- [ ] Ghi exact endpoints.
- [ ] Ghi sign evidence.
- [ ] Serialize cuối pipeline.

---

# 12. Checklist P0 — Đồng biến và nghịch biến

# P0-14. Không dùng một điểm mẫu cho interval khi breakpoint chưa đầy đủ

## Hiện trạng fallback

```text
bounds = [-1e9] + breakpoints + [1e9]
sample midpoint
```

## Rủi ro

- Bỏ sót nhiều lần đổi dấu.
- Sai với hàm tuần hoàn.
- Sai khi có singularity chưa phát hiện.
- Sai khi nghiệm đạo hàm nằm ngoài danh sách.
- Sai khi biểu thức không liên tục.

## Checklist

- [ ] Giải dấu symbolic khi có thể.
- [ ] Phân rã domain.
- [ ] Tìm đầy đủ zero/singularity.
- [ ] Mỗi component có proof/evidence.
- [ ] Periodic function có mô tả chu kỳ.
- [ ] Numeric fallback phải adaptive.
- [ ] Có error bound.
- [ ] Không gọi exact khi dùng sampling.
- [ ] Response ghi method.

---

# P0-15. Hỗ trợ hàm tuần hoàn đúng nghĩa

## Ví dụ

```text
sin(x)
cos(x)
tan(x)
```

Một danh sách interval hữu hạn không thể đại diện toàn bộ `R` nếu không có tham số chu kỳ.

## Checklist

- [ ] Structured periodic intervals.
- [ ] Tham số `k ∈ Z`.
- [ ] Chọn khoảng cơ sở.
- [ ] Hiển thị nghiệm tổng quát.
- [ ] Không dùng fixed range.
- [ ] Tách tan/cot domain.
- [ ] Bảng biến thiên theo một chu kỳ.
- [ ] Cho chọn interval khảo sát.
- [ ] Test periodicity.

---

# 13. Checklist P0 — Lồi, lõm và điểm uốn

# P0-16. Tính lồi/lõm ngay cả khi `f''(x)=0` không có nghiệm

## Hiện trạng

Chỉ tính khoảng lồi/lõm khi danh sách breakpoint điểm uốn không rỗng.

## Ví dụ sai

```text
f(x)=x^2
f''(x)=2>0
```

Đúng:

```text
Lồi trên R
```

Nhưng danh sách có thể rỗng.

## Checklist

- [ ] Nếu f'' không có zero, vẫn xét dấu trên từng domain component.
- [ ] Hàm bậc hai.
- [ ] Hàm mũ.
- [ ] Hàm log.
- [ ] Hàm có miền rời.
- [ ] Không phụ thuộc danh sách điểm uốn.
- [ ] Test constant second derivative.

---

# P0-17. Không phát hiện điểm uốn bằng bước cố định `±0.001`

## Rủi ro

- Hai nghiệm gần nhau.
- Biến đổi tỉ lệ lớn/nhỏ.
- Điểm rất lớn.
- Singular point.
- Floating cancellation.
- f'' gần 0 lâu.

## Checklist

- [ ] Dùng sign intervals symbolic.
- [ ] Kiểm tra continuity tại candidate.
- [ ] Kiểm tra đổi dấu f''.
- [ ] Adaptive sampling khi cần.
- [ ] Scale epsilon theo candidate.
- [ ] Multiple epsilon consistency.
- [ ] Không coi nghiệm f''=0 tự động là điểm uốn.
- [ ] Không bỏ điểm uốn nơi f'' không tồn tại.
- [ ] Ghi evidence.

---

# 14. Checklist P0 — Điểm tới hạn và cực trị

# P0-18. Phân biệt điểm dừng, điểm tới hạn và cực trị

## Checklist

- [ ] `stationary_point`.
- [ ] `critical_nondifferentiable`.
- [ ] `local_max`.
- [ ] `local_min`.
- [ ] `stationary_inflection`.
- [ ] `cusp`.
- [ ] `corner`.
- [ ] `endpoint_extremum`.
- [ ] `unknown`.
- [ ] Không dùng một nhãn “điểm đặc biệt” quá chung.

---

# P0-19. Không dùng `f''(x0)=0` hoặc nghiệm kép của `f'` để suy ra một cực trị

## Vấn đề tham số

Logic đếm cực trị khi `f'` là tam thức:

```text
Delta = 0 → có 1 cực trị
```

Điều này sai trong nhiều trường hợp.

Ví dụ:

```text
f'(x)=(x-a)^2
```

Đạo hàm không đổi dấu, nên không có cực đại/cực tiểu.

## Checklist

- [ ] Đếm sign changes của f'.
- [ ] Không đếm số nghiệm f' đơn thuần.
- [ ] Xử lý nghiệm bội.
- [ ] Xử lý hệ số đầu phụ thuộc tham số.
- [ ] Tách case degree giảm.
- [ ] Kiểm chứng mẫu từng component tham số.
- [ ] Test `x^3`.
- [ ] Test quartic parameter.
- [ ] Đổi label nếu chỉ đang đếm nghiệm f'.

---

# 15. Checklist P0 — Tiệm cận

# P0-20. Tiệm cận đứng không chỉ đến từ mẫu số hữu tỉ

## Hiện trạng

Tìm nghiệm mẫu số của `cancel(f)`.

## Bỏ sót

- `log(x)` tại `x=0`.
- `tan(x)` tại `π/2+kπ`.
- `cot(x)` tại `kπ`.
- Căn/phân thức lồng nhau.
- Piecewise.
- Endpoint của domain với giới hạn vô cực.
- Hàm hợp.

## Checklist

- [ ] Dùng domain boundary.
- [ ] Dùng singularities.
- [ ] Kiểm tra limit trái/phải.
- [ ] Hỗ trợ periodic families.
- [ ] Không giới hạn rational denominator.
- [ ] Không coi removable hole là asymptote.
- [ ] Ghi direction.
- [ ] Ghi exact x.
- [ ] Test log/tan/cot.

---

# P0-21. Tiệm cận xiên phải xét cả `+∞` và `-∞`

## Hiện trạng

Chỉ tính tại `+∞`.

## Checklist

- [ ] Xiên tại `+∞`.
- [ ] Xiên tại `-∞`.
- [ ] Hai kết quả có thể khác.
- [ ] Ghi direction.
- [ ] Render cả hai.
- [ ] Kiểm tra `f(x)-(ax+b)→0`.
- [ ] Không chỉ dựa trên a,b hữu hạn.
- [ ] Hỗ trợ polynomial division khi phù hợp.

---

# P0-22. Không mất exact value của tiệm cận

## Hiện trạng

Tiệm cận được format bằng float khoảng 4 chữ số.

## Checklist

- [ ] Exact expression.
- [ ] Exact LaTeX.
- [ ] Approximation riêng.
- [ ] Không làm tròn `sqrt(2)`.
- [ ] Không làm tròn `pi/2`.
- [ ] Không dùng approximate làm command nguồn.
- [ ] Ghi precision.

---

# 16. Checklist P0 — Giao điểm trục

# P0-23. Không đưa nghiệm phức vào giao điểm Ox

## Hiện trạng

Nếu nghiệm không convert được sang float, hệ thống thêm chuỗi symbolic mà chưa chắc là nghiệm thực.

## Ví dụ

```text
f(x)=x^2+1
```

Không có giao điểm Ox trên R.

## Checklist

- [ ] Intersect solution with Reals.
- [ ] Kiểm tra `is_real`.
- [ ] Không dùng `solve` không domain.
- [ ] Kiểm tra thuộc domain.
- [ ] Không thêm ConditionSet như một điểm.
- [ ] Test nghiệm phức.
- [ ] Test symbolic real unknown.
- [ ] Trả trạng thái partial nếu chưa giải đủ.

---

# P0-24. Không cắt 6 giao điểm im lặng

## Hiện trạng

```text
solve(f,x)[:6]
```

## Checklist

- [ ] `max_points` có metadata.
- [ ] `truncated=true`.
- [ ] `total_known`.
- [ ] Không cắt trước khi lọc nghiệm thực.
- [ ] Cho xem tất cả khi hợp lý.
- [ ] Với periodic roots, dùng family.
- [ ] UI nói rõ giới hạn.
- [ ] Không gọi danh sách là đầy đủ khi đã cắt.

---

# 17. Checklist P0 — Numeric root fallback

# P0-25. Thay quét cố định `[-20,20]` bước `0.05`

## Hiện trạng

- Chỉ tìm đổi dấu.
- Lấy trung điểm.
- Không refine.
- Không kiểm tra residual.
- Không xét domain.

## Bỏ sót

- Nghiệm bội chẵn.
- Tiếp xúc đường thẳng.
- Nghiệm ngoài `[-20,20]`.
- Hai nghiệm gần nhau.
- Nghiệm ở điểm đạo hàm lớn.
- Nghiệm gần tiệm cận.

## Có thể tạo nghiệm giả

- Đổi dấu qua tiệm cận đứng.
- Giá trị overflow.
- Nhánh rời.

## Checklist

- [ ] Symbolic first.
- [ ] Polynomial real roots.
- [ ] Adaptive root isolation.
- [ ] Bracketing per domain component.
- [ ] Tangency detection bằng minima của |f|.
- [ ] Refine bằng bisection/Brent.
- [ ] Residual check.
- [ ] Domain check.
- [ ] Error bound.
- [ ] Configurable window.
- [ ] Không gọi approximate root exact.
- [ ] Không đếm sign change qua singularity.

---

# 18. Checklist P0 — GTLN/GTNN trên khoảng hoặc đoạn

# P0-26. Xét mọi singularity bên trong interval

## Hiện trạng

Candidate chỉ gồm:

- Hai đầu.
- Điểm dừng.

Thiếu:

- Điểm gián đoạn bên trong.
- Giới hạn một phía tại singularity.
- Boundary của domain.
- Điểm không khả vi nhưng có cực trị.
- Cusp/corner.

## Ví dụ

```text
f(x)=1/(x-1), x∈[0,2]
```

Hàm không bị chặn nhưng có thể bị kết luận từ các candidate hữu hạn.

## Checklist

- [ ] Intersect interval với domain.
- [ ] Split thành connected components.
- [ ] Tìm singularity trong interval.
- [ ] Tính one-sided limits.
- [ ] Xét stationary và nondifferentiable points.
- [ ] Xét endpoint đóng.
- [ ] Xét endpoint mở bằng limit.
- [ ] Phân biệt maximum, supremum, unbounded.
- [ ] Phân biệt minimum, infimum, unbounded.
- [ ] Ghi điểm đạt giá trị.
- [ ] Ghi tất cả điểm đạt.
- [ ] Kiểm chứng range trên interval.

---

# P0-27. Sửa logic khoảng mở của hàm hằng

## Ví dụ

```text
f(x)=1, x∈(0,1)
```

Hàm đạt cả GTLN và GTNN bằng 1 tại mọi x trong khoảng.

Không thể kết luận “không có GTLN/GTNN” chỉ vì candidate đến từ endpoint limit.

## Checklist

- [ ] Xác định value có được đạt trong interior.
- [ ] Không gắn conclusion theo loại candidate duy nhất.
- [ ] Xử lý tie.
- [ ] Xử lý continuum of maximizers.
- [ ] Trả attainment set.
- [ ] Test constant/open interval.

---

# P0-28. Không mất trường hợp tie giữa endpoint limit và interior point

## Ví dụ

Supremum ở endpoint mở có cùng giá trị với một điểm nội bộ.

## Checklist

- [ ] Gom tất cả candidate cùng giá trị.
- [ ] Xét có ít nhất một candidate attained.
- [ ] Không phụ thuộc thứ tự list.
- [ ] Exact comparison trước.
- [ ] Numeric tolerance có kiểm soát.
- [ ] Ghi all argmax/argmin.

---

# 19. Checklist P0 — Tương giao với đường thẳng

# P0-29. Không đếm giao điểm từ nghiệm approximate chưa kiểm chứng

- [ ] Substitute vào `f(x)=kx+b`.
- [ ] Residual tolerance.
- [ ] Domain check.
- [ ] Deduplicate theo error bound.
- [ ] Không đếm singularity.
- [ ] Ghi exact/approx.
- [ ] Truncated metadata.
- [ ] Unknown count khi chưa giải đủ.

---

# P0-30. Tính diện tích theo từng miền kín hợp lệ

## Hiện trạng

Nếu có ít nhất hai giao điểm:

```text
integrate |f-line| từ nghiệm đầu đến nghiệm cuối
```

## Rủi ro

- Có nhiều miền rời.
- Có singularity bên trong.
- Tích phân phân kỳ.
- Có hơn hai giao điểm.
- Phần giữa không tạo miền kín.
- Lấy first/last có thể gộp nhiều miền.

## Checklist

- [ ] Sắp tất cả intersection.
- [ ] Xét từng cặp liên tiếp.
- [ ] Kiểm tra continuity.
- [ ] Kiểm tra miền kín.
- [ ] Tính từng area component.
- [ ] Exact integral.
- [ ] Numeric approximation riêng.
- [ ] Divergence detection.
- [ ] Không trả area khi chưa đủ giao điểm.
- [ ] UI hiển thị tổng và từng phần.

---

# P0-31. Tiếp tuyến phải kiểm tra điểm thuộc miền và đạo hàm hữu hạn

## Checklist

- [ ] `x0 ∈ domain`.
- [ ] `f(x0)` xác định.
- [ ] `f'(x0)` tồn tại.
- [ ] Xử lý tiếp tuyến đứng.
- [ ] Xử lý cusp.
- [ ] Không tính `None` như số.
- [ ] Exact slope.
- [ ] Exact equation.
- [ ] Verification by contact.
- [ ] Không làm tròn sớm.

---

# 20. Checklist P0 — Đồ thị

# P0-32. Truyền domain thật vào GeoGebra

## Hiện trạng

Domain graph chỉ lấy từ công cụ interval, không phải tập xác định.

## Checklist

- [ ] FunctionGraph nhận domain components.
- [ ] GeoGebra `Function[...]` theo từng component.
- [ ] Open endpoint.
- [ ] Closed endpoint.
- [ ] Hole.
- [ ] Vertical asymptote.
- [ ] Piecewise.
- [ ] Không nối qua discontinuity.
- [ ] Domain source từ analyzer core.

---

# P0-33. Không sampling cố định `[-8,8]`

## Rủi ro

- Cực trị ngoài range.
- Nghiệm ngoài range.
- Tiệm cận ngoài range.
- Hàm scale lớn.
- Hàm rất hẹp.
- Hàm periodic quá dày.

## Checklist

- [ ] Plot window option.
- [ ] Auto-window từ features.
- [ ] Adaptive sampling.
- [ ] Sample quanh singularity.
- [ ] Sample quanh critical point.
- [ ] Sample around intercept.
- [ ] Max point count.
- [ ] LOD.
- [ ] User pan/zoom load thêm data.
- [ ] Exact GeoGebra function ưu tiên.

---

# P0-34. Không nối đoạn qua discontinuity bằng heuristic đơn giản

## Hiện trạng SVG fallback

Tách path dựa trên:

- Chênh lệch x.
- Chênh lệch y.

## Checklist

- [ ] Domain component segment.
- [ ] Singularity-aware split.
- [ ] One-sided sample.
- [ ] Không nối qua hole.
- [ ] Không nối qua vertical asymptote.
- [ ] Adaptive curvature.
- [ ] Test tan/rational/Piecewise.

---

# P0-35. Fallback khi GeoGebra lỗi

## Hiện trạng

Nếu có command thì render GeoGebra, không có circuit fallback trong component.

## Checklist

- [ ] GeoGebra load timeout.
- [ ] Error boundary.
- [ ] Fallback SVG.
- [ ] Retry.
- [ ] Report renderer used.
- [ ] Không để khu đồ thị trắng.
- [ ] Telemetry renderer failure.
- [ ] User switch renderer.

---

# 21. Checklist P0 — Tham số

# P0-36. Không mặc định `m=1` âm thầm

## Hiện trạng

Nếu biểu thức có `m` và frontend không gửi parameters:

```text
m = 1
```

UI hiện không có control tham số.

## Rủi ro

- Người dùng tưởng đang khảo sát hàm tham số tổng quát.
- Kết quả thực tế chỉ tại một giá trị.
- Warning dạng toast có thể biến mất sau 10 giây.
- Đồ thị và bảng không ghi nổi bật `m=1`.

## Checklist

- [ ] Nếu có parameter, yêu cầu chọn mode.
- [ ] Mode symbolic.
- [ ] Mode substitute.
- [ ] Hiển thị m rõ trong header.
- [ ] Slider parameter.
- [ ] Input exact parameter.
- [ ] Không default im lặng.
- [ ] Persist parameter in result.
- [ ] Graph label chứa parameter.
- [ ] Export chứa parameter.
- [ ] Test no-parameter-value.

---

# P0-37. Không clamp parameter âm thầm

## Hiện trạng

Giá trị ngoài `[-10,10]` bị ép vào biên.

## Checklist

- [ ] Validate và báo lỗi.
- [ ] Hoặc hiển thị rõ giá trị đã clamp.
- [ ] Không thay input im lặng.
- [ ] Range là UI suggestion, không phải định luật toán.
- [ ] Cho nhập giá trị ngoài slider.
- [ ] Exact parameter support.
- [ ] Rational/pi/sqrt parameter.
- [ ] Config per expression.

---

# P0-38. Điều kiện tham số phải xử lý suy biến bậc

- [ ] Hệ số đầu bằng 0.
- [ ] Degree thay đổi theo m.
- [ ] Domain thay đổi theo m.
- [ ] Singularities phụ thuộc m.
- [ ] Critical point multiplicity.
- [ ] Case split.
- [ ] Boundary m.
- [ ] Verification mỗi component.
- [ ] Không chỉ dùng discriminant của derivative.

---

# 22. Checklist P0 — OCR

# P0-39. OCR phải có bước xác nhận

## Hiện trạng

OCR:

```text
extract expression
→ analyze immediately
```

Trong khi hướng dẫn nói người dùng kiểm tra rồi bấm phân tích.

## Checklist

- [ ] OCR extract-only endpoint.
- [ ] Hiển thị ảnh gốc.
- [ ] Hiển thị OCR text.
- [ ] Hiển thị expression.
- [ ] Confidence.
- [ ] Ambiguity.
- [ ] Cho sửa.
- [ ] Xác nhận.
- [ ] Sau đó mới analyze.
- [ ] Không tính quota analyze trước xác nhận.
- [ ] Lưu provenance.

---

# P0-40. Không dùng output LLM một dòng mà thiếu schema

## Checklist

- [ ] JSON schema.
- [ ] `expression`.
- [ ] `variable`.
- [ ] `parameters`.
- [ ] `confidence`.
- [ ] `warnings`.
- [ ] `ambiguous_tokens`.
- [ ] `needs_confirmation`.
- [ ] Không nhận prose.
- [ ] Validate bằng safe parser.
- [ ] Không tự chạy expression không hợp lệ.

---

# 23. Checklist P0 — API schema và lỗi

# P0-41. Thay `dict[str, Any]` bằng model typed

Các trường cần model riêng:

- interval
- line
- parameter conditions
- transform
- plot window
- analysis options

## Checklist

- [ ] `extra="forbid"`.
- [ ] Enum line mode.
- [ ] Enum transform type.
- [ ] Validate finite number.
- [ ] Validate a < b.
- [ ] Validate bounds.
- [ ] Validate extrema count.
- [ ] Validate parameter names.
- [ ] Validate target list.
- [ ] Không chấp nhận field lạ.
- [ ] OpenAPI rõ ràng.

---

# P0-42. Không gom mọi exception thành HTTP 400

## Phân loại đề xuất

| Tình huống | HTTP | Code |
|---|---:|---|
| Input sai | 422 | `ANALYZER_INPUT_INVALID` |
| Parse lỗi | 422 | `ANALYZER_PARSE_FAILED` |
| Dạng chưa hỗ trợ | 200/422 | `ANALYZER_UNSUPPORTED` |
| Quá phức tạp | 413/422 | `ANALYZER_COMPLEXITY_LIMIT` |
| Timeout | 504 | `ANALYZER_TIMEOUT` |
| Rate limit | 429 | `ANALYZER_RATE_LIMITED` |
| OCR lỗi | 502 | `ANALYZER_OCR_FAILED` |
| Solver nội bộ | 500 | `ANALYZER_INTERNAL_ERROR` |
| Renderer lỗi | 502 | `ANALYZER_GRAPH_FAILED` |

## Checklist

- [ ] Không trả raw exception.
- [ ] Correlation ID.
- [ ] Stage.
- [ ] Retryable.
- [ ] Partial result.
- [ ] Server log riêng.
- [ ] Redact provider response.
- [ ] Không coi unsupported là internal error.

---

# 24. Checklist P0 — Verification

# P0-43. Thêm verification report

Hiện response không nói:

- Kết quả nào exact.
- Kết quả nào numeric.
- Kết quả nào fallback.
- Kết quả nào chưa kiểm chứng.
- Phần nào bị cắt.
- Phần nào có thể thiếu.

## Schema đề xuất

```json
{
  "verification": {
    "status": "partially_verified",
    "checks": [
      {
        "name": "derivative_backcheck",
        "status": "pass",
        "method": "symbolic"
      },
      {
        "name": "monotonicity_components",
        "status": "warn",
        "detail": "Một khoảng dùng numeric sampling."
      }
    ]
  }
}
```

## Checklist

- [ ] Verify domain.
- [ ] Verify derivative.
- [ ] Verify critical point membership.
- [ ] Verify sign each interval.
- [ ] Verify inflection sign change.
- [ ] Verify asymptote limits.
- [ ] Verify intercept substitution.
- [ ] Verify tangent.
- [ ] Verify extrema attainment.
- [ ] Verify graph/domain consistency.
- [ ] Ghi exact/numeric/fallback.
- [ ] Không gọi complete khi có truncation.

---

# 25. Checklist P1 — Frontend state

# P1-01. Xóa hoặc đánh dấu kết quả cũ khi biểu thức đổi

## Hiện trạng

Người dùng sửa input nhưng result cũ vẫn còn cho tới khi bấm phân tích.

## Checklist

- [ ] Clear result.
- [ ] Hoặc badge “Kết quả của biểu thức trước”.
- [ ] Disable export.
- [ ] Disable tool analysis.
- [ ] Reset selected point.
- [ ] Reset animation.
- [ ] Preserve history riêng.
- [ ] Không nhầm input hiện tại với graph cũ.

---

# P1-02. Abort request cũ thật sự

Frontend hiện chỉ bỏ response cũ bằng request ID.

## Checklist

- [ ] `AbortController`.
- [ ] Backend cancellation.
- [ ] Cancel tool request.
- [ ] Cancel khi expression đổi.
- [ ] Cancel khi rời trang.
- [ ] Không lãng phí CPU.
- [ ] Metric cancelled request.

---

# P1-03. Sửa animation 160 ms và debounce 220 ms

## Hiện trạng

Animation tick nhanh hơn debounce.

Mỗi tick có thể xóa timeout trước, khiến phân tích chỉ chạy sau khi animation dừng.

## Hướng đề xuất

Animation đồ thị biến đổi không nên gọi full analyzer.

```text
Base AST
→ cập nhật transform parameter client-side/GeoGebra
→ không tính lại domain/range toàn bộ mỗi frame
```

## Checklist

- [ ] Client-side transform.
- [ ] GeoGebra slider.
- [ ] `requestAnimationFrame`.
- [ ] 30/60 FPS.
- [ ] Không gọi backend mỗi frame.
- [ ] Backend chỉ tạo base transform model.
- [ ] Pause/resume.
- [ ] Reset.
- [ ] Reduced motion.
- [ ] Animation state visible.

---

# P1-04. Hiển thị warning gắn với result

## Hiện trạng

Warning là notification tự biến mất.

Tool slider warning còn bị bỏ qua.

## Checklist

- [ ] Warning panel trong result.
- [ ] Stage.
- [ ] Severity.
- [ ] Persistent.
- [ ] Tool warnings.
- [ ] OCR warnings.
- [ ] Dismiss riêng.
- [ ] Export kèm warning.
- [ ] Không chỉ toast.

---

# 26. Checklist P1 — Input UX

# P1-05. Dùng math editor hoặc preview công thức

- [ ] MathQuill/MathLive.
- [ ] Plain text mode.
- [ ] LaTeX mode.
- [ ] Live preview.
- [ ] Syntax error position.
- [ ] Function autocomplete.
- [ ] Variable detection.
- [ ] Parameter detection.
- [ ] Copy normalized expression.
- [ ] Mobile keyboard.

---

# P1-06. Không chiếm chuột phải để OCR

## Hiện trạng

Chuột phải vào input bị chặn và dùng để đọc clipboard ảnh.

## Vấn đề

- Mất menu copy/paste.
- Hành vi không chuẩn.
- Khó khám phá.
- Có thể gây khó chịu.

## Checklist

- [ ] Nút dán ảnh riêng.
- [ ] Hỗ trợ Ctrl+V.
- [ ] Giữ native context menu.
- [ ] Tooltip.
- [ ] Permission state.
- [ ] Fallback file picker.
- [ ] Accessibility.

---

# P1-07. Đồng bộ hướng dẫn với capability thật

Hướng dẫn hiện liệt kê:

- sinh/cosh/tanh
- floor/ceil
- sign
- Min/Max
- Piecewise

Trong khi parser chỉ công bố rõ `x`, `m` và một nhóm function nhỏ.

## Checklist

- [ ] Capability registry dùng chung.
- [ ] Guide sinh tự động từ registry.
- [ ] Không quảng bá function chưa test.
- [ ] Test từng ví dụ guide.
- [ ] `Min(a,b)` phải giải thích a,b là gì.
- [ ] Piecewise parser typed.
- [ ] Hyperbolic support explicit.
- [ ] floor/ceil derivative limitations.

---

# 27. Checklist P1 — Result UX

# P1-08. Hiển thị đầy đủ kết quả nhanh

Hiện quick summary chỉ có:

- Tập xác định.
- Tập giá trị.
- Đạo hàm.

Nên có:

- [ ] Chẵn/lẻ.
- [ ] Giao Ox.
- [ ] Giao Oy.
- [ ] Cực trị.
- [ ] Điểm uốn.
- [ ] Đồng biến.
- [ ] Nghịch biến.
- [ ] Lồi.
- [ ] Lõm.
- [ ] Tiệm cận.
- [ ] Analysis mode.
- [ ] Parameter value.
- [ ] Verification status.

---

# P1-09. Exact và approximate tách riêng

## Checklist

- [ ] `x_exact`.
- [ ] `x_approx`.
- [ ] `y_exact`.
- [ ] `y_approx`.
- [ ] Precision.
- [ ] Copy exact.
- [ ] Copy approximate.
- [ ] Không format float quá sớm.
- [ ] Không dùng string làm storage chính.

---

# P1-10. Có chế độ “Khảo sát từng bước”

Các phần nên trình bày:

```text
1. Tập xác định
2. Giới hạn tại biên miền và vô cực
3. Đạo hàm
4. Nghiệm và dấu đạo hàm
5. Cực trị
6. Đạo hàm cấp hai
7. Lồi/lõm và điểm uốn
8. Tiệm cận
9. Giao trục
10. Bảng biến thiên
11. Đồ thị
```

## Checklist

- [ ] Mỗi bước có công thức.
- [ ] Có giải thích.
- [ ] Có evidence.
- [ ] Có cảnh báo.
- [ ] Có thu gọn.
- [ ] Phù hợp lớp 12.
- [ ] Không chỉ trả kết quả rời.

---

# 28. Checklist P1 — Bảng biến thiên UI

- [ ] Responsive.
- [ ] Scroll ngang.
- [ ] Tiệm cận trái/phải.
- [ ] Open endpoint.
- [ ] Domain boundary.
- [ ] Điểm khuyết.
- [ ] Cực trị.
- [ ] Stationary inflection.
- [ ] Exact labels.
- [ ] Unknown state.
- [ ] Không tự dựng infinity.
- [ ] Fullscreen modal có Escape.
- [ ] Focus trap.
- [ ] Print/export.

---

# 29. Checklist P1 — Graph UX

- [ ] Auto-fit.
- [ ] Manual window.
- [ ] Reset domain fit.
- [ ] Toggle grid.
- [ ] Toggle axes.
- [ ] Toggle asymptotes.
- [ ] Toggle points.
- [ ] Hover coordinates.
- [ ] Trace point.
- [ ] Show derivative graph.
- [ ] Show second derivative graph.
- [ ] Show tangent.
- [ ] Show intervals by color.
- [ ] Show hole.
- [ ] Show endpoint open/closed.
- [ ] Renderer switch.
- [ ] Export PNG/SVG.
- [ ] Copy GeoGebra commands.

---

# 30. Checklist P1 — Công cụ GTLN/GTNN

- [ ] Đổi nhãn “đoạn” thành “khoảng/đoạn”.
- [ ] Exact endpoints.
- [ ] Open/closed chips.
- [ ] Domain intersection.
- [ ] Unbounded state.
- [ ] Supremum/infimum.
- [ ] Attainment.
- [ ] All maximizers/minimizers.
- [ ] Step-by-step candidate table.
- [ ] Verification.
- [ ] Visual highlight on graph.
- [ ] Shade interval.

---

# 31. Checklist P1 — Công cụ đường thẳng

## Tương giao

- [ ] Exact line equation.
- [ ] Exact intersections.
- [ ] Approximation.
- [ ] Complete/truncated.
- [ ] Relative position.
- [ ] Domain components.
- [ ] Area components.
- [ ] Highlight regions.
- [ ] Tangency detection.
- [ ] Multiple roots.

## Tiếp tuyến

- [ ] At x0.
- [ ] At point.
- [ ] Parallel to line.
- [ ] Perpendicular to line.
- [ ] Through external point.
- [ ] Vertical tangent.
- [ ] Normal line.
- [ ] Exact equation.
- [ ] Visual tangent.

---

# 32. Checklist P1 — Biến đổi đồ thị

# P1-11. Đồng bộ label và công thức horizontal shift

Frontend hiển thị:

```text
f(x+a)
```

Backend với `a>0` tạo:

```text
f(x-a)
```

và mô tả dịch phải.

## Checklist

- [ ] Chọn một quy ước.
- [ ] Label động theo dấu.
- [ ] Công thức đúng.
- [ ] Mô tả đúng.
- [ ] Test positive/negative.
- [ ] Không dùng label cố định mâu thuẫn.

---

# P1-12. Giải thích đúng horizontal scale

Với:

```text
g(x)=f(ax)
```

- `|a|>1`: co ngang hệ số `1/|a|`.
- `0<|a|<1`: giãn ngang hệ số `1/|a|`.
- `a<0`: có đối xứng qua Oy.
- `a=0`: hàm hằng nếu f(0) xác định.

## Checklist

- [ ] Mô tả theo |a|.
- [ ] Xử lý a<0.
- [ ] Xử lý a=0.
- [ ] Không nói “hệ số a” chung chung.
- [ ] Visual anchor points.
- [ ] Domain transformation.

---

# P1-13. Giải thích đúng vertical scale

- [ ] `a>1`.
- [ ] `0<a<1`.
- [ ] `a<0`.
- [ ] `a=0`.
- [ ] Reflection through Ox.
- [ ] Range transformation.
- [ ] Critical values transformation.

---

# P1-14. Không yêu cầu slider `a` với transform không dùng giá trị

Các transform:

- `-f(x)`
- `f(-x)`
- `|f(x)|`
- `f(|x|)`

không cần slider.

## Checklist

- [ ] Ẩn slider.
- [ ] Ẩn animation nếu không có parameter.
- [ ] Không gửi value thừa.
- [ ] Typed transform union.

---

# P1-15. Phân tích lại hàm biến đổi

Hiện transform preview chủ yếu trả expression.

## Checklist

- [ ] Domain mới.
- [ ] Range mới.
- [ ] Critical points mới.
- [ ] Intercepts mới.
- [ ] Variation mới.
- [ ] Graph overlay.
- [ ] Explain invariant/changed properties.
- [ ] Không phải full backend recompute mỗi frame.

---

# 33. Checklist P1 — Tham số và simulation

- [ ] Hiển thị parameter panel khi phát hiện m.
- [ ] Slider.
- [ ] Numeric input.
- [ ] Exact input.
- [ ] Auto range.
- [ ] User range.
- [ ] Multiple parameters.
- [ ] Symbolic mode.
- [ ] Case split.
- [ ] Bifurcation points.
- [ ] Number of extrema by parameter.
- [ ] Roots by parameter.
- [ ] Asymptotes by parameter.
- [ ] Animation client-side.
- [ ] Snapshot values.
- [ ] Compare multiple m.

---

# 34. Checklist P1 — Capabilities

Hiện backend trả cố định:

```json
{
  "trig_periodic": true,
  "exact_solving": true,
  "numeric_fallback": true
}
```

Điều này không phản ánh từng kết quả cụ thể.

## Checklist

- [ ] Capability registry.
- [ ] Per-expression capability.
- [ ] Exact domain available.
- [ ] Exact range available.
- [ ] Exact roots complete.
- [ ] Periodic result.
- [ ] Numeric fallback used.
- [ ] Graph renderer available.
- [ ] Parameter mode available.
- [ ] Tool compatibility.
- [ ] UI đọc registry.
- [ ] Không hardcode true.

---

# 35. Checklist P1 — Response schema mục tiêu

```json
{
  "request_id": "fa_...",
  "status": "complete",
  "interpretation": {
    "raw_expression": "...",
    "canonical_expression": "...",
    "variable": "x",
    "parameters": [],
    "source": "text",
    "confirmed": true
  },
  "function": {
    "original": "...",
    "simplified": "...",
    "domain": {
      "exact": "...",
      "components": []
    }
  },
  "analysis": {
    "limits": [],
    "derivatives": [],
    "critical_points": [],
    "monotonic_intervals": [],
    "concavity_intervals": [],
    "inflection_points": [],
    "asymptotes": [],
    "intercepts": [],
    "variation_table": []
  },
  "graph": {
    "renderer": "geogebra_2d",
    "domain_components": [],
    "commands": [],
    "fallback_points": []
  },
  "verification": {
    "status": "partially_verified",
    "checks": []
  },
  "provenance": {
    "parser_version": "...",
    "analyzer_version": "...",
    "sympy_version": "...",
    "ocr_used": false,
    "numeric_fallback_used": false
  },
  "timings": {
    "parse_ms": 0,
    "domain_ms": 0,
    "derivative_ms": 0,
    "roots_ms": 0,
    "limits_ms": 0,
    "graph_ms": 0
  },
  "warnings": []
}
```

---

# 36. Checklist P1 — Tách endpoint công cụ

## Kiến trúc đề xuất

```text
POST /api/analyzer/analyze
→ base analysis + analysis_id

POST /api/analyzer/tools/interval-extrema
POST /api/analyzer/tools/line
POST /api/analyzer/tools/tangent
POST /api/analyzer/tools/transform
POST /api/analyzer/tools/parameter
```

## Lợi ích

- Không tính lại full analysis.
- Cache AST.
- Cache derivative.
- Cache roots.
- Animation nhẹ.
- Rate limit theo tool.
- Error riêng từng công cụ.
- Response nhỏ hơn.

## Checklist

- [ ] analysis_id có TTL.
- [ ] Cache user-scoped.
- [ ] Cache expression hash.
- [ ] Version-aware.
- [ ] Tool payload typed.
- [ ] Tool cancellation.
- [ ] Không lưu AST không an toàn.
- [ ] Cache invalidation.

---

# 37. Checklist P1 — Accessibility

- [ ] Input có description.
- [ ] Error liên kết aria-describedby.
- [ ] Graph có text alternative.
- [ ] Bảng biến thiên accessible table.
- [ ] Modal có focus trap.
- [ ] Escape close.
- [ ] Restore focus.
- [ ] Slider có label.
- [ ] Slider disabled đúng.
- [ ] Không chỉ dùng màu.
- [ ] Keyboard pan/zoom.
- [ ] Reduced motion.
- [ ] Screen reader đọc exact expression.
- [ ] OCR dropzone keyboard accessible.

---

# 38. Checklist P1 — Slider disabled và validation

## Hiện trạng

Component slider không nhận prop `disabled`.

## Checklist

- [ ] Truyền disabled.
- [ ] Không gọi request khi loading.
- [ ] Không gửi NaN.
- [ ] Empty number state.
- [ ] Min/max dynamic.
- [ ] Manual value ngoài slider.
- [ ] Exact value input.
- [ ] Commit-on-blur option.
- [ ] Debounce hợp lý.
- [ ] Validation inline.

---

# 39. Checklist P1 — History và persistence

- [ ] Lịch sử analyzer riêng.
- [ ] Lưu biểu thức gốc.
- [ ] Lưu canonical expression.
- [ ] Lưu parameter.
- [ ] Lưu plot window.
- [ ] Lưu tools.
- [ ] Lưu result version.
- [ ] Lưu verification.
- [ ] Mở lại không tính quota.
- [ ] Re-analyze với engine mới.
- [ ] So sánh version.
- [ ] Pin.
- [ ] Tag lớp/chương.
- [ ] Search.

---

# 40. Checklist P1 — Export

- [ ] Markdown.
- [ ] PDF.
- [ ] DOCX.
- [ ] PNG graph.
- [ ] SVG graph.
- [ ] Bảng biến thiên ảnh.
- [ ] GeoGebra file/commands.
- [ ] LaTeX.
- [ ] JSON.
- [ ] Teacher report.
- [ ] Student worksheet.
- [ ] Export warnings.
- [ ] Export exact/approx metadata.

---

# 41. Checklist P1 — Phù hợp chương trình THPT

## Lớp 10

- [ ] Hàm bậc nhất.
- [ ] Hàm bậc hai.
- [ ] Parabol.
- [ ] Tập xác định cơ bản.
- [ ] Đồ thị và biến đổi.

## Lớp 11

- [ ] Hàm lượng giác.
- [ ] Chu kỳ.
- [ ] Giới hạn.
- [ ] Liên tục.
- [ ] Biến đổi đồ thị.

## Lớp 12

- [ ] Đạo hàm.
- [ ] Đồng biến/nghịch biến.
- [ ] Cực trị.
- [ ] GTLN/GTNN.
- [ ] Tiệm cận.
- [ ] Khảo sát và vẽ đồ thị.
- [ ] Bài toán tham số.
- [ ] Tương giao.
- [ ] Tiếp tuyến.
- [ ] Tích phân diện tích liên quan.

## Checklist sư phạm

- [ ] Chọn lớp.
- [ ] Chọn chương.
- [ ] Chọn mức giải thích.
- [ ] Dùng thuật ngữ SGK.
- [ ] Không dùng phương pháp vượt chương trình mặc định.
- [ ] Có bước giải.
- [ ] Có lỗi thường gặp.
- [ ] Có câu hỏi dự đoán.
- [ ] Có bài tương tự.

---

# 42. Checklist P2 — Chế độ giáo viên

- [ ] Tạo phiếu khảo sát hàm số.
- [ ] Ẩn đáp án.
- [ ] Chỉ hiện gợi ý.
- [ ] Chọn phần cần phân tích.
- [ ] Tạo nhiều biến thể.
- [ ] Rubric.
- [ ] Đáp án chi tiết.
- [ ] Xuất Word/PDF.
- [ ] Lớp học.
- [ ] Assignment link.
- [ ] Thống kê lỗi học sinh.
- [ ] So sánh lời giải.

---

# 43. Checklist P2 — Chế độ học sinh

- [ ] Predict trước graph.
- [ ] Tự nhập domain.
- [ ] Tự nhập derivative.
- [ ] Tự lập sign chart.
- [ ] Tự chọn cực trị.
- [ ] Reveal từng bước.
- [ ] Hint.
- [ ] Check answer.
- [ ] Explain mistake.
- [ ] Progress.
- [ ] Mastery by topic.
- [ ] Daily practice.

---

# 44. Checklist P2 — So sánh nhiều hàm

- [ ] Overlay f và g.
- [ ] Compare domains.
- [ ] Compare derivatives.
- [ ] Compare extrema.
- [ ] Compare asymptotes.
- [ ] Difference function.
- [ ] Intersection.
- [ ] Area.
- [ ] Parameter family.
- [ ] Save comparison.

---

# 45. Checklist P2 — Liên kết hệ sinh thái

- [ ] Mở `/algebra-solver` để giải f'(x)=0.
- [ ] Mở `/simulation` để mô phỏng parameter.
- [ ] Mở `/geogebra-lab`.
- [ ] Gửi graph sang `/render`.
- [ ] Tạo bài luyện tập.
- [ ] Chia sẻ permalink.
- [ ] Embed.
- [ ] API public có kiểm soát.

---

# 46. Ma trận test bắt buộc

## 46.1. Parser và bảo mật

- [ ] Plain polynomial.
- [ ] LaTeX fraction.
- [ ] Nested fraction.
- [ ] Root.
- [ ] Absolute value.
- [ ] Log base.
- [ ] Piecewise.
- [ ] Unsupported function.
- [ ] Unsupported symbol.
- [ ] Deep nesting.
- [ ] Huge exponent.
- [ ] Huge integer.
- [ ] Malicious attribute.
- [ ] Constructor attempt.
- [ ] Timeout parse.
- [ ] AST node limit.

## 46.2. Domain

- [ ] Polynomial.
- [ ] Rational.
- [ ] Removable hole.
- [ ] Even root.
- [ ] Odd root.
- [ ] Log.
- [ ] Tan.
- [ ] Cot.
- [ ] Piecewise.
- [ ] Abs.
- [ ] Composite domain.
- [ ] Parameter domain.

## 46.3. Range

- [ ] Quadratic.
- [ ] Cubic.
- [ ] Exp.
- [ ] Log.
- [ ] Rational.
- [ ] Abs.
- [ ] Periodic.
- [ ] Piecewise.
- [ ] Unavailable range.
- [ ] Timeout.

## 46.4. Derivative

- [ ] Polynomial.
- [ ] Rational.
- [ ] Root.
- [ ] Abs.
- [ ] Piecewise.
- [ ] Trig.
- [ ] Exp/log.
- [ ] Parameter.
- [ ] Unevaluated derivative.
- [ ] Verification.

## 46.5. Critical points

- [ ] Simple max/min.
- [ ] Double root of f'.
- [ ] Stationary inflection.
- [ ] Cusp.
- [ ] Corner.
- [ ] Endpoint extremum.
- [ ] Nondifferentiable critical point.
- [ ] Point outside domain.
- [ ] Multiple close points.
- [ ] Periodic family.

## 46.6. Concavity

- [ ] `x^2` lồi toàn R.
- [ ] `-x^2` lõm toàn R.
- [ ] `exp(x)` lồi toàn R.
- [ ] `x^3` đổi độ cong tại 0.
- [ ] `x^(1/3)`.
- [ ] Rational with singularity.
- [ ] Piecewise.
- [ ] Close inflection points.
- [ ] f'' unavailable.

## 46.7. Asymptotes

- [ ] Rational vertical.
- [ ] Removable hole not vertical.
- [ ] `log(x)` vertical.
- [ ] `tan(x)` periodic vertical.
- [ ] Horizontal at +∞.
- [ ] Horizontal at -∞.
- [ ] Different horizontal asymptotes.
- [ ] Oblique +∞.
- [ ] Oblique -∞.
- [ ] Exact irrational asymptote.
- [ ] No asymptote.

## 46.8. Intercepts

- [ ] Real polynomial roots.
- [ ] No real roots.
- [ ] Complex roots excluded.
- [ ] Root outside plot.
- [ ] Root at domain hole excluded.
- [ ] More than six roots.
- [ ] Periodic roots.
- [ ] y-intercept undefined.
- [ ] Exact irrational root.
- [ ] Approx root metadata.

## 46.9. Monotonicity

- [ ] Polynomial.
- [ ] Rational disconnected domain.
- [ ] Exp.
- [ ] Log.
- [ ] Sin periodic.
- [ ] Tan periodic.
- [ ] Constant.
- [ ] Piecewise.
- [ ] Unknown.
- [ ] Numeric fallback warning.

## 46.10. Variation table

- [ ] `exp(x)` boundary limits.
- [ ] `atan(x)` finite boundaries.
- [ ] `1/x` two branches.
- [ ] Rational horizontal asymptote.
- [ ] Log domain boundary.
- [ ] Removable hole.
- [ ] Constant function.
- [ ] Unknown interval.
- [ ] Vertical asymptote limits.
- [ ] Export.

## 46.11. Interval extrema

- [ ] Closed interval polynomial.
- [ ] Open interval polynomial.
- [ ] Constant open interval.
- [ ] Internal vertical asymptote.
- [ ] Domain partially overlaps interval.
- [ ] Empty intersection.
- [ ] Nondifferentiable extremum.
- [ ] Tie.
- [ ] Multiple argmax.
- [ ] Unbounded above.
- [ ] Unbounded below.
- [ ] Exact endpoint.
- [ ] Parameterized function.

## 46.12. Line analysis

- [ ] Two intersections.
- [ ] Tangent double root.
- [ ] No intersection.
- [ ] Root outside `[-20,20]`.
- [ ] Close roots.
- [ ] Vertical asymptote sign change.
- [ ] More than 12 roots.
- [ ] Periodic intersections.
- [ ] Relative position.
- [ ] Multiple closed areas.
- [ ] Divergent area.
- [ ] Domain hole.
- [ ] Tangent at invalid x0.
- [ ] Vertical tangent.

## 46.13. Transform

- [ ] Vertical shift positive/negative.
- [ ] Horizontal shift positive/negative.
- [ ] Vertical scale >1.
- [ ] Vertical scale between 0 and 1.
- [ ] Vertical scale negative.
- [ ] Vertical scale zero.
- [ ] Horizontal scale >1.
- [ ] Horizontal scale between 0 and 1.
- [ ] Horizontal scale negative.
- [ ] Horizontal scale zero.
- [ ] Reflect x.
- [ ] Reflect y.
- [ ] Abs function.
- [ ] Abs argument.
- [ ] Domain transformation.
- [ ] Unknown transform rejected.

## 46.14. Parameter

- [ ] No parameter.
- [ ] m unspecified.
- [ ] m exact.
- [ ] m outside slider range.
- [ ] Multiple parameter values.
- [ ] Degree degeneration.
- [ ] Domain changes with m.
- [ ] Number of extrema.
- [ ] Double derivative root not extremum.
- [ ] Symbolic mode.
- [ ] Bifurcation.

## 46.15. OCR

- [ ] Clear formula.
- [ ] No formula.
- [ ] Ambiguous exponent.
- [ ] Fraction.
- [ ] Root.
- [ ] Parameter.
- [ ] Multiple functions in image.
- [ ] Confidence low.
- [ ] User correction.
- [ ] No auto-analysis before confirmation.
- [ ] Provider timeout.
- [ ] Upload validation.

## 46.16. API

- [ ] 422 parse.
- [ ] 429 rate limit.
- [ ] 504 timeout.
- [ ] Partial response.
- [ ] Unsupported.
- [ ] Cancellation.
- [ ] Invalid tool enum.
- [ ] NaN/Infinity input.
- [ ] Extra fields.
- [ ] Correlation ID.

## 46.17. Frontend E2E

- [ ] Input expression.
- [ ] Edit stale result.
- [ ] OCR confirmation.
- [ ] Open/closed interval.
- [ ] Tool warning.
- [ ] Animation.
- [ ] Cancel.
- [ ] GeoGebra failure fallback.
- [ ] Mobile.
- [ ] Keyboard.
- [ ] Modal focus.
- [ ] Export.
- [ ] History.

---

# 47. Các test hồi quy P0 nên bổ sung ngay

```python
analyze_function("x^2 + 1")
# x_intercepts phải rỗng.
```

```python
analyze_function("x^2")
# concave_up_intervals phải là R.
```

```python
analyze_function("exp(x)")
# bảng biến thiên phải có lim x→-∞ = 0, không phải -∞.
```

```python
analyze_function("atan(x)")
# lim tại ±∞ phải là ±pi/2.
```

```python
analyze_function("1/x", interval={"a": 0, "b": 2})
# Không được kết luận GTLN/GTNN hữu hạn.
```

```python
analyze_function("1/(x-1)", interval={"a": 0, "b": 2})
# Phải phát hiện không bị chặn do x=1.
```

```python
analyze_function("1", interval={"a": 0, "b": 1, "open_a": True, "open_b": True})
# GTLN=GTNN=1 và đạt tại mọi x trong (0,1).
```

```python
analyze_function("(x^2-1)/(x-1)")
# Đồ thị phải có lỗ tại x=1.
```

```python
analyze_function("log(x)")
# Phải nhận x=0 là biên miền có giới hạn -∞.
```

```python
analyze_function("tan(x)")
# Phải có họ tiệm cận đứng.
```

```python
analyze_function("(x-1)^2", line={"k": 0, "b": 0})
# Numeric fallback không được bỏ nghiệm tiếp xúc x=1.
```

```python
analyze_function("(x-100)^2", line={"k": 0, "b": 0})
# Không được bỏ nghiệm vì ngoài [-20,20].
```

```python
analyze_function("x^3", parameter_conditions={"targets": ["extrema_count"], "extrema_count": 1})
# Không được kết luận có 1 cực trị chỉ vì f' có nghiệm kép.
```

---

# 48. Kiến trúc mục tiêu

```text
AnalyzerInput
    ↓
InputNormalizer
    ↓
SafeMathParser
    ↓
ExpressionIR
    ↓
DomainDecomposer
    ↓
AnalysisPlanner
    ├── limits
    ├── derivatives
    ├── roots
    ├── sign charts
    ├── extrema
    ├── concavity
    ├── asymptotes
    └── intercepts
    ↓
IndependentVerifier
    ↓
VariationModelBuilder
    ↓
GraphSpecBuilder
    ↓
ResultWorkspace
```

## 48.1. Nguyên tắc

- Parse một lần.
- AST an toàn.
- Domain là nguồn sự thật.
- Phân tích theo connected component.
- Exact trước, numeric sau.
- Numeric phải có error bound.
- Không tự suy diễn ở frontend.
- Bảng và graph dùng cùng model.
- Có verification.
- Có provenance.
- Tool không tính lại toàn bộ.
- Animation client-side.
- OCR phải xác nhận.

---

# 49. State machine đề xuất

```text
draft
→ parsing
→ needs_confirmation
→ confirmed
→ planning
→ analyzing
→ verifying
→ graph_building
→ complete
```

Trạng thái một phần:

```text
partial_domain
partial_range
partial_roots
partial_monotonicity
partial_graph
```

Trạng thái lỗi:

```text
input_invalid
parse_failed
unsupported
complexity_limited
timeout
rate_limited
analysis_failed
verification_failed
graph_failed
ocr_failed
```

---

# 50. Lộ trình triển khai

## Giai đoạn 1 — Sửa lỗi P0 nền tảng

- [ ] Safe parser.
- [ ] Remove second sympify parse.
- [ ] Import/lint SymPy namespace.
- [ ] Timeout.
- [ ] Worker isolation.
- [ ] Rate limit.
- [ ] Typed schema.
- [ ] Error codes.
- [ ] Domain-centric model.

## Giai đoạn 2 — Sửa độ đúng toán học

- [ ] Variation boundary limits.
- [ ] Vertical asymptote branches.
- [ ] Concavity without roots.
- [ ] Inflection sign proof.
- [ ] Real intercept filtering.
- [ ] No silent truncation.
- [ ] Adaptive roots.
- [ ] Interval extrema with singularities.
- [ ] Tangent validation.
- [ ] Parameter extrema logic.

## Giai đoạn 3 — Đồng bộ đồ thị

- [ ] Original domain graph.
- [ ] Removable holes.
- [ ] Domain components.
- [ ] Adaptive sample.
- [ ] GeoGebra fallback.
- [ ] Exact points.
- [ ] Asymptote rendering.
- [ ] Plot window.

## Giai đoạn 4 — UX và tương tác

- [ ] Stale result state.
- [ ] Abort requests.
- [ ] Persistent warnings.
- [ ] Math editor.
- [ ] Parameter UI.
- [ ] OCR confirmation.
- [ ] Client-side animation.
- [ ] Tool endpoints.
- [ ] Full result summary.

## Giai đoạn 5 — Sản phẩm hoàn chỉnh

- [ ] Step-by-step analysis.
- [ ] History.
- [ ] Export.
- [ ] Share.
- [ ] Teacher mode.
- [ ] Student practice.
- [ ] Curriculum mapping.
- [ ] Analytics.

---

# 51. Tiêu chí hoàn thành phiên bản ổn định đầu tiên

Phiên bản `/analyzer` chỉ nên được xem là ổn định khi:

- [ ] Parser không dùng namespace mặc định không kiểm soát.
- [ ] Không còn parse lại bằng `sympify`.
- [ ] Có complexity limit.
- [ ] Có timeout.
- [ ] Có rate limit.
- [ ] Có worker isolation.
- [ ] Không còn undefined namespace `sp`.
- [ ] Exact sign branch có test.
- [ ] Domain là nguồn sự thật.
- [ ] Concavity của `x^2` đúng.
- [ ] Intercept của `x^2+1` rỗng.
- [ ] Variation của `e^x` có limit 0 ở -∞.
- [ ] Variation của `atan(x)` có limit hữu hạn.
- [ ] `1/x` có hai nhánh.
- [ ] GTLN/GTNN không sai qua singularity.
- [ ] Hàm hằng trên khoảng mở xử lý đúng.
- [ ] Tiệm cận log/tan được phát hiện.
- [ ] Oblique asymptote xét hai phía.
- [ ] Nghiệm numeric được refine và verify.
- [ ] Không cắt kết quả im lặng.
- [ ] Đồ thị bảo toàn lỗ miền.
- [ ] GeoGebra dùng domain components.
- [ ] OCR có xác nhận.
- [ ] m không mặc định/clamp âm thầm.
- [ ] Animation không gọi full analysis mỗi frame.
- [ ] Response có verification.
- [ ] Response có provenance.
- [ ] Warning gắn với result.
- [ ] Tool schema typed.
- [ ] Có regression suite P0.
- [ ] Có security fuzz test.
- [ ] Có benchmark p95/p99.

---

# 52. Hai mươi hạng mục ưu tiên cao nhất

```text
1. Khóa parser bằng SafeMath AST
2. Thêm timeout và worker isolation
3. Rate limit /api/analyze
4. Sửa thiếu import sympy as sp và chặn broad exception che lỗi
5. Không parse lại bằng sympify trong graph builder
6. Thiết kế domain-centric analysis
7. Sửa bảng biến thiên không tự suy ra ±∞
8. Thêm giới hạn thật tại biên và tiệm cận
9. Sửa GTLN/GTNN qua singularity và khoảng mở
10. Sửa concavity khi f'' không có nghiệm
11. Lọc nghiệm thực và domain cho giao Ox
12. Bỏ silent truncation nghiệm
13. Thay fixed numeric root scan
14. Vẽ graph theo biểu thức gốc và domain
15. Phát hiện log/tan/cot vertical asymptotes
16. Sửa parameter m mặc định và clamp âm thầm
17. OCR extract → confirm → analyze
18. Sửa animation 160 ms/220 ms và tách tool endpoint
19. Thêm verification/provenance
20. Mở rộng regression test theo ma trận toán học
```

---

# 53. Kết luận

`/analyzer` có nền tảng sản phẩm khá tốt:

- Có giao diện độc lập.
- Có OCR.
- Có SymPy.
- Có GeoGebra.
- Có bảng biến thiên.
- Có nhiều công cụ tương tác.
- Có khả năng mở rộng thành phòng thí nghiệm hàm số.

Tuy nhiên, phiên bản hiện tại đang trộn ba lớp dữ liệu:

```text
kết quả symbolic
kết quả numeric sampling
suy diễn hiển thị của frontend
```

mà chưa ghi rõ ranh giới và mức tin cậy.

Ba rủi ro lớn nhất là:

## 53.1. Kết luận toán học có thể sai nhưng không có verification

Đặc biệt ở:

- Bảng biến thiên.
- GTLN/GTNN.
- Lồi/lõm.
- Điểm uốn.
- Giao điểm.
- Tiệm cận.
- Bài tham số.

## 53.2. Đồ thị có thể không đại diện đúng hàm gốc

Do:

- Dùng biểu thức rút gọn.
- Không truyền domain thật.
- Sampling cố định.
- Không mô hình hóa lỗ hổng.
- Không có renderer fallback rõ ràng.

## 53.3. Tài nguyên và parser chưa được bảo vệ đủ

Do:

- Parse trực tiếp input.
- Không timeout.
- Không rate limit deterministic.
- Không worker isolation.
- Slider có thể phát sinh nhiều full-analysis request.

Định hướng phù hợp nhất là chuyển từ:

> Tính được gì thì đưa lên giao diện.

sang:

> Phân tích theo miền xác định, ghi rõ exact/numeric/unknown, kiểm chứng từng kết luận, rồi dùng một mô hình chung để dựng bảng và đồ thị.

Thứ tự ưu tiên:

```text
Bảo mật parser
→ Timeout và rate limit
→ Độ đúng toán học
→ Variation model
→ Graph-domain consistency
→ Verification
→ UX minh bạch
→ Tương tác và animation
→ History/export
→ Mở rộng chương trình THPT
```

Không nên mở rộng thêm nhiều loại hàm trước khi sửa các lỗi nền tảng về domain, bảng biến thiên, interval extrema, graph holes và numeric fallback.
