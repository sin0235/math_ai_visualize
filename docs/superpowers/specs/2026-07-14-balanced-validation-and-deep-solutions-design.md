# Thiết kế validation cân bằng và lời giải chi tiết

## Mục tiêu

Làm mượt luồng render và giải toán trong buổi demo mà không hạ độ đúng của đáp án. Hệ thống phải phục hồi được các lỗi trình bày nhỏ, giữ lời giải deterministic khi LLM không đạt yêu cầu, và chỉ chặn khi dữ liệu cốt lõi thực sự không an toàn hoặc không thể kiểm chứng.

## Phạm vi

- Scene V3: validation, repair và thông báo đối với relation, annotation và metadata có thể bỏ qua an toàn.
- Bộ giải đại số: xử lý lỗi biến đổi, độ chi tiết của các bước và cơ chế diễn giải LLM.
- Bộ giải hình học: diễn giải LLM và cách hiển thị fallback.
- Frontend: chỉ hiển thị cảnh báo có hành động cụ thể dành cho người dùng.

Không thay đổi public API, authentication, database schema, phép kiểm chứng đáp án hoặc chính sách bảo mật prompt.

## Nguyên tắc validation

Validation được chia thành ba mức:

1. **Chặn cứng**: input nguy hiểm, JSON hoặc schema cốt lõi không đọc được, topology không đủ để xác định khối sau repair, tham chiếu làm sai đối tượng toán học, đáp án không vượt qua kiểm chứng bắt buộc.
2. **Phục hồi mềm**: relation hoặc annotation phụ thiếu field, style ngoài giới hạn, metadata trình bày không hợp lệ, một field ngôn ngữ từ LLM không đạt grounding. Hệ thống bỏ hoặc chuẩn hóa đúng phần lỗi, giữ phần còn lại và ghi telemetry nội bộ.
3. **Thông tin nội bộ**: fallback provider, normalization, repair thành công và kiểm tra phụ không ảnh hưởng kết quả. Không đưa các nội dung này thành toast hoặc warning cho người học.

Không chuyển lỗi mức 1 xuống mức 2. Đây là mức “hạ nhẹ”, không phải vô hiệu hóa validation.

## Lời giải đại số

### Xử lý lỗi biến đổi

- Chỉ gọi phân tích phân thức `apart()` khi biểu thức là phân thức hữu tỉ theo biến đang xét.
- Bắt lỗi biến đổi cục bộ và chuyển sang chiến lược tổng quát thay vì làm hỏng toàn request.
- Biểu thức `2*x - 1/x + e**(x-1)` phải được tách theo tính tuyến tính của tích phân và giải từng hạng.

### Chiều sâu bước giải

Solver deterministic là nguồn sự thật và tạo đủ milestone:

1. Nhận dạng dạng bài và biểu thức.
2. Nêu quy tắc hoặc phương pháp được chọn.
3. Tách biểu thức thành các thành phần nếu có thể.
4. Biến đổi hoặc tính từng thành phần.
5. Ghép và rút gọn kết quả.
6. Kiểm tra bằng đạo hàm, thế nghiệm hoặc phép kiểm tra tương ứng.

Với tích phân từng phần, lời giải phải hiển thị lựa chọn `u`, `dv`, suy ra `du`, `v`, áp dụng công thức, thay biểu thức và rút gọn. Không được chỉ ghi “dùng tích phân từng phần”.

### Diễn giải LLM

- LLM chỉ viết lại ngôn ngữ; không thay công thức, milestone hoặc đáp án.
- Giữ các trường deterministic `goal`, `why`, `rule`, `operation`, `pitfall`, `check`; không xóa sau khi LLM trả về.
- Validation diễn giải theo từng field. Field không đạt grounding dùng lại bản deterministic; không loại cả lời giải.
- Nếu toàn bộ LLM thất bại, trả lời giải deterministic đầy đủ và ghi fallback nội bộ, không cảnh báo người dùng.

## Render và giải hình học

- Giữ chặn cứng khi scene không có đối tượng cốt lõi hoặc topology vẫn sai sau repair.
- Relation/annotation phụ thiếu argument nhưng không quyết định topology sẽ bị loại riêng và ghi nhận nội bộ.
- Các construction quan trọng cho câu hỏi như chân chiếu, đoạn khoảng cách, góc vuông và thiết diện vẫn phải được tạo hoặc repair; không được bỏ để scene “pass” dễ hơn.
- Diễn giải hình học dùng cùng cơ chế fallback theo field như đại số và giữ toàn bộ bước deterministic.
- Không dùng tọa độ minh họa để tạo số đo chính xác; có thể trả kết quả ký hiệu khi construction đã được backend xác nhận.

## Trải nghiệm người dùng

Chỉ hiển thị cảnh báo khi người dùng có thể hành động, ví dụ đề mơ hồ, thiếu dữ kiện bắt buộc, input không hợp lệ hoặc không thể kiểm chứng kết quả. Không hiển thị:

- Tên provider/model fallback.
- Chi tiết schema hoặc Pydantic.
- Repair đã thành công.
- Grounding từ chối một field nhưng đã dùng lại nội dung deterministic.
- Cảnh báo verification phụ khi kết quả cuối đã được kiểm chứng.

Lỗi nội bộ phải có thông báo an toàn và request ID để truy vết, không lộ stack trace.

## Luồng dữ liệu

1. Input được chuẩn hóa và phân loại.
2. Solver hoặc extractor tạo kết quả deterministic.
3. Validation phân loại lỗi thành chặn cứng, phục hồi mềm hoặc thông tin nội bộ.
4. Repair cục bộ chạy trước khi quyết định thất bại.
5. LLM chỉ làm giàu ngôn ngữ trên các anchor đã khóa.
6. Grounding áp dụng theo từng field và fallback về nội dung deterministic.
7. Frontend nhận response tương thích hiện tại và lọc thông báo theo khả năng hành động.

## Kiểm thử

- Regression cho tích phân chứa đồng thời đa thức, phân thức và hàm mũ.
- Regression cho tích phân từng phần có đầy đủ `u`, `dv`, `du`, `v` và bước thế công thức.
- Unit test cho phân loại validation và repair relation/annotation phụ.
- Test bảo đảm lỗi topology cốt lõi và đáp án không kiểm chứng vẫn bị chặn.
- Test LLM chỉ sai một field vẫn giữ các field hợp lệ và deterministic fallback.
- Test frontend không hiện warning nội bộ nhưng vẫn hiện cảnh báo có hành động.
- Chạy toàn bộ backend test, Ruff, frontend utility tests và production build.

## Tiêu chí hoàn thành

- Ví dụ trong ảnh không còn trả lỗi 500 và có lời giải từng bước.
- Lời giải tích phân từng phần không dừng ở tên phương pháp.
- Scene có lỗi trình bày nhỏ vẫn render sau repair, nhưng scene sai topology không được coi là hợp lệ.
- Người dùng không thấy warning kỹ thuật đã được hệ thống tự xử lý.
- Không có thay đổi public contract và toàn bộ regression suite liên quan vượt qua.
