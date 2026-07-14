# Thiết kế solver tọa độ từ khung hình học đáng tin cậy

Ngày: 2026-07-14

## 1. Bối cảnh

Với đề hình lập phương `ABCD.MNPQ` cạnh `8`, `F` là trung điểm của `CD`, cần tính `d(M,(PFB))`, parser đã nhận đúng mục tiêu nhưng mode `oxyz` trả về `Không đủ dữ kiện`.

Nguyên nhân là metric guard hiện chỉ mở khóa khi scene có annotation/relation định lượng phù hợp. Dữ kiện định lượng đã có trong `problem_text` dưới dạng “hình lập phương cạnh 8”, nhưng nhánh `oxyz` không sử dụng fact cấu trúc này. Regression test hiện tại gọi solver trên scene không có `problem_text`, nên bỏ qua guard và không tái hiện luồng production.

Engine `classical` đã có khả năng trích xuất một `orthogonal_frame` đáng tin cậy từ đề gốc, nhận diện cạnh hình lập phương và suy ra điểm trung điểm. Thiết kế này chia sẻ năng lực đó cho mode `oxyz` thay vì hạ thấp guard trên toàn hệ thống.

## 2. Mục tiêu

- Mode `oxyz` giải được bài toán từ dữ kiện hình học định lượng được phát biểu rõ trong đề, kể cả khi AI không tạo annotation độ dài.
- Tọa độ tính toán được dựng từ fact đáng tin cậy, không phụ thuộc tọa độ render có thể bị co giãn hoặc sai tỉ lệ.
- Kết quả giữ dạng exact và bổ sung dạng gần đúng khi đề yêu cầu làm tròn.
- Với đề regression cạnh `8`, kết quả là `d(M,(PFB)) = 4\sqrt{6} \approx 9{,}8`.
- Guard được nới có kiểm soát cho cấu trúc và phép dựng đã xác minh; scene chung chỉ có tọa độ AI vẫn bị từ chối.
- Không thay đổi public API hoặc schema Scene v3.

## 3. Ngoài phạm vi

- Không cho phép mọi scene `solid_geometry` dùng tọa độ render để kết luận số học.
- Không hardcode riêng các nhãn `M`, `P`, `F`, `B` hoặc cạnh `8`.
- Không thay thế toàn bộ geometry solver hoặc proof planner.
- Không thêm dependency mới.
- Không thay đổi renderer, topology visualization hoặc style hiện có.

## 4. Các phương án đã xem xét

### 4.1. Bỏ metric guard

Phương án này giúp demo chạy rộng nhất nhưng cho phép tọa độ AI minh họa trở thành dữ kiện tính toán. Nó có thể trả lời chắc chắn từ một scene không đúng tỉ lệ nên không được chọn.

### 4.2. Tự tạo annotation cạnh từ `problem_text`

Phương án này ít thay đổi nhưng vẫn phụ thuộc vào tọa độ render để tính các điểm và khoảng cách còn lại. Nếu AI dựng hình đồng dạng hoặc dùng kích thước hiển thị khác số đo đề bài, annotation sẽ mâu thuẫn với tọa độ.

### 4.3. Dựng khung tọa độ chuẩn từ fact đáng tin cậy

Đây là phương án được chọn. Solver dùng cấu trúc khối, độ dài trục và phép dựng được phát biểu trong đề để tạo hệ tọa độ exact. Tọa độ render chỉ tiếp tục phục vụ hiển thị và highlight.

## 5. Thiết kế kiến trúc

### 5.1. Bộ giải khung vuông góc dùng chung

Tách phần mô hình và tính toán khung vuông góc đang nằm trong classical point-plane engine thành một module geometry nội bộ dùng chung. Module nhận `GeometryFactGraph` và cung cấp:

- Các khung có fact `orthogonal_frame` đáng tin cậy.
- Tọa độ exact của các đỉnh trên ba trục vuông góc.
- Các điểm dẫn xuất từ fact đáng tin cậy, trước mắt gồm chuỗi phép dựng trung điểm.
- Phép chiếu điểm lên mặt phẳng và khoảng cách exact bằng SymPy.
- Danh sách fact IDs thực sự đã dùng.

Module tính toán không tạo `SolverStep` và không phụ thuộc mode trình bày. Classical engine và Oxyz engine dùng chung kết quả nhưng xây các bước giải phù hợp với từng phương pháp.

Giới hạn hiện có về số khung và số điểm dẫn xuất được giữ để tránh vòng lặp hoặc scene bất thường gây tăng chi phí không kiểm soát.

### 5.2. Nguồn fact đáng tin cậy

`problem_text` là nguồn cho premise khi parser xác định rõ:

- Tên hai đáy của hình lập phương hoặc hình hộp chữ nhật.
- Độ dài cạnh hoặc ba độ dài trục là số hữu hạn dương.
- Phép dựng trung điểm có đúng một điểm và hai đầu mút.

Fact có source `given` được phép dùng. Fact construction/inferred chỉ được dùng khi contract hiện tại đánh dấu verified/exact. Relation có verification `failed` hoặc `error` không được dùng.

Nếu cùng một đại lượng có hai premise định lượng mâu thuẫn, solver không chọn tùy ý mà trả trạng thái dữ kiện không nhất quán.

### 5.3. Luồng mode Oxyz

Với metric point-plane trong mode `oxyz`:

1. Chuẩn hóa câu hỏi và xác định điểm nguồn cùng ba điểm mặt phẳng.
2. Chạy luồng evidence hiện có cho tọa độ/annotation đã được kiểm chứng.
3. Nếu evidence đó thiếu, xây fact graph từ scene và thử resolve một khung vuông góc đáng tin cậy chứa điểm nguồn.
4. Dẫn xuất đủ ba điểm mặt phẳng bằng các construction fact.
5. Dựng hệ tọa độ chuẩn exact, tính hai vectơ trong mặt phẳng, pháp tuyến và khoảng cách.
6. Nếu giải được, bỏ qua tọa độ render cho phần tính toán nhưng vẫn dùng object IDs của scene để highlight.
7. Nếu không resolve đủ hoặc geometry suy biến, giữ kết quả `Không đủ dữ kiện` cùng lý do cụ thể.

Metric guard coi “khung đáng tin cậy và goal resolve đủ” là evidence hợp lệ. Việc chỉ phát hiện từ khóa “hình lập phương” nhưng thiếu cạnh hoặc thiếu phép dựng cần thiết không đủ để mở guard.

### 5.4. Các bước giải Oxyz

Mode `oxyz` trình bày các bước deterministic:

1. Chọn gốc và ba trục theo ba phương cạnh vuông góc của khối.
2. Gán tọa độ exact cho các đỉnh từ số đo đã cho.
3. Suy ra tọa độ điểm dựng, ví dụ `F` là trung điểm của `CD`.
4. Lập hai vectơ của mặt phẳng và tính pháp tuyến bằng tích có hướng.
5. Áp dụng công thức khoảng cách điểm–mặt phẳng.
6. Rút gọn exact, sau đó mới tính gần đúng nếu đề yêu cầu.

Mỗi bước gắn fact IDs và object IDs liên quan để giữ grounding và highlight. Nội dung không tuyên bố tọa độ render là tọa độ đề bài.

### 5.5. Chính sách exact và làm tròn

Thêm parser nhỏ cho yêu cầu độ chính xác trong `problem_text` và câu hỏi. Các dạng hỗ trợ ban đầu:

- `hàng phần mười` hoặc `1 chữ số thập phân`.
- `hàng phần trăm` hoặc `2 chữ số thập phân`.
- `hàng phần nghìn` hoặc `3 chữ số thập phân`.

Số chữ số được giới hạn trong một khoảng an toàn. Việc làm tròn dùng trực tiếp biểu thức exact, không dùng kết quả trung gian đã làm tròn.

Khi có yêu cầu làm tròn và kết quả exact không phải số thập phân hữu hạn ở độ chính xác đó:

- `answer` chứa cả exact và approximate, ví dụ `d(M,(PFB)) = 4\sqrt{6} \approx 9{,}8`.
- Bước kết luận giữ biểu thức exact và nêu rõ chỉ làm tròn ở kết quả cuối.
- Dấu phẩy thập phân được biểu diễn theo cú pháp LaTeX an toàn `9{,}8` để frontend hiển thị đúng locale Việt Nam.

Khi đề không yêu cầu làm tròn, hành vi hiện tại được giữ: ưu tiên chỉ trả dạng exact.

## 6. Luồng dữ liệu

```text
problem_text + scene + question
    -> normalize goal
    -> existing verified metric evidence
    -> nếu thiếu: GeometryFactGraph
    -> trusted orthogonal-frame resolver
    -> exact canonical coordinates + derived points
    -> exact point-plane calculation
    -> precision policy từ problem_text/question
    -> answer + grounded Oxyz steps
```

Tọa độ render không đi vào nhánh `exact canonical coordinates`.

## 7. Xử lý lỗi và giới hạn nới guard

- Thiếu độ dài cạnh/trục: báo thiếu premise định lượng.
- Độ dài bằng `0`, âm, không hữu hạn hoặc không parse được: từ chối khung.
- Thiếu fact trung điểm/incidence cần cho một điểm goal: nêu đúng điểm không dẫn xuất được.
- Ba điểm mặt phẳng thẳng hàng: báo mặt phẳng suy biến.
- Có nhiều khung phù hợp nhưng cho kết quả khác nhau: báo dữ kiện mâu thuẫn.
- Tọa độ render mâu thuẫn với đề nhưng fact đề đầy đủ: tính theo đề và không dùng tọa độ render.
- Chỉ có tọa độ render và mô tả khối chung không số đo: vẫn `Không đủ dữ kiện`.
- AI explainer không được sửa exact answer, approximate answer hoặc precision đã tính deterministic.

## 8. Kiểm thử

### 8.1. Regression chính

- Dùng nguyên văn đề có nhiều ngoặc, cạnh `8`, trung điểm `F`, câu hỏi tiếng Việt và yêu cầu làm tròn một chữ số.
- Đi qua Scene v3 adapter như production thay vì gọi solver bằng scene thiếu `problem_text`.
- Mode `oxyz` trả `4\sqrt{6} \approx 9{,}8`, confidence `verified` và có các bước tọa độ.

### 8.2. Tính đúng và tính tổng quát

- Cạnh `18` trả `9\sqrt{6}` và approximate đúng nếu có precision request.
- Đổi tên hai đáy và điểm trung điểm vẫn giải được cùng dạng tổng quát.
- Tọa độ render bị co giãn hoặc cố ý sai vẫn không đổi kết quả từ đề.
- Hình hộp chữ nhật có ba độ dài trục rõ ràng tiếp tục dùng cùng resolver.

### 8.3. Guard và error path

- Thiếu cạnh, thiếu trung điểm, cạnh không hợp lệ hoặc mặt phẳng suy biến đều không mở guard.
- Khối chung chỉ có tọa độ AI vẫn bị từ chối như test an toàn hiện tại.
- Annotation định lượng đã verified tiếp tục hoạt động.
- Annotation/relation mâu thuẫn hoặc failed không được dùng.

### 8.4. Presentation và contract

- Không có precision request thì đáp án exact hiện tại không đổi.
- `hàng phần mười`, `phần trăm`, `phần nghìn` cho đúng số chữ số và dùng dấu phẩy.
- `result_latex`, answer, grounding, proof/solution projection và AI explainer giữ nhất quán.
- Public response schema không thay đổi.

### 8.5. Kiểm tra rộng

- Chạy unit/regression cho parser, fact graph, classical point-plane, Oxyz solver, Scene v3 adapter và solver route.
- Chạy toàn bộ backend test liên quan geometry.
- Chạy frontend test cho solver notice/Katex nếu thay đổi chuỗi làm tròn ảnh hưởng hiển thị.
- Chạy frontend build, backend compile/type/static checks có sẵn trong project.

## 9. Tiêu chí hoàn thành

- Đề regression không còn hiện toast `Chưa đủ dữ kiện` trong mode `Dùng tọa độ`.
- Đáp án hiển thị cả `4√6` và `≈ 9,8`.
- Các phép tính trung gian giữ exact.
- Steps giải thích rõ hệ tọa độ được suy ra từ dữ kiện hình học.
- Tọa độ render sai không làm thay đổi đáp án.
- Generic scene thiếu số đo vẫn không bị solver đoán kết quả.
- Test cũ về guard, classical engine và metric solver tiếp tục xanh.
- Không có thay đổi public contract, dependency mới, log debug hoặc artifact tạm.
