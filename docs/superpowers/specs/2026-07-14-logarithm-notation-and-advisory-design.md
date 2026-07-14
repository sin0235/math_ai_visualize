# Thiết kế quy ước logarit và phân tầng thông báo

## Mục tiêu

- Hiểu và tính đúng `ln(x)` là logarit cơ số `e`.
- Hiểu `log(x)` không ghi cơ số là logarit cơ số `10` theo quy ước sản phẩm.
- Giữ đúng cơ số với `log_a(x)`, `log(x, a)` và cách diễn đạt tiếng Việt tương đương.
- Hiển thị ký hiệu nhất quán với ý nghĩa toán học, không để SymPy âm thầm đổi `ln` thành `log`.
- Chỉ đưa ra giao diện những thông báo có thể giúp người học hành động hoặc ảnh hưởng đến độ đúng của đáp án.

## Phạm vi

Thay đổi tập trung vào pipeline Algebra: diễn giải đầu vào, biểu diễn chuẩn, solver, xuất LaTeX, API response và giao diện kết quả. Không thay đổi quy ước của Function Analyzer hoặc Scene V3 nếu chúng không dùng chung boundary Algebra đang sửa; các caller dùng chung sẽ được kiểm tra tương thích trước khi mở rộng.

## Quy ước ngữ nghĩa

| Đầu vào | Ý nghĩa | Ký hiệu đầu ra |
| --- | --- | --- |
| `ln(x)` | Logarit cơ số `e` | `\ln(x)` |
| `log(x)` | Logarit cơ số `10` | `\log_{10}(x)` |
| `log(x, a)` | Logarit cơ số `a` | `\log_a(x)` |
| `log_a(x)` | Logarit cơ số `a` | `\log_a(x)` |

Parser phải gắn ngữ nghĩa cơ số trước khi tạo biểu thức cho solver. Renderer chỉ trình bày biểu thức đã có ngữ nghĩa; không đoán lại cơ số từ chuỗi LaTeX.

## Kiến trúc

### Diễn giải đầu vào

- Mở rộng normalization tại boundary Algebra để phân biệt token `ln` và `log` trần.
- Chuẩn hóa `ln` thành logarit tự nhiên nội bộ.
- Chuẩn hóa `log` trần thành logarit cơ số 10 nội bộ.
- Giữ cơ số được khai báo rõ và không thay đổi public request schema.
- Không dùng phép thay chuỗi toàn cục sau khi parse vì có thể làm sai biểu thức lồng nhau hoặc log có cơ số.

### Tính toán và biểu diễn

- Solver nhận biểu thức đã phân biệt cơ số nên đạo hàm, tích phân và phương trình dùng đúng công thức.
- Tạo một điểm xuất LaTeX có chính sách logarit rõ ràng cho các trường answer, step và milestone thuộc Algebra.
- Ký hiệu kết quả phải giữ `\ln`, `\log_{10}` hoặc `\log_a`; không dùng `\log` mơ hồ.
- Dạng text và LaTeX trong cùng response phải cùng ngữ nghĩa.

### Phân tầng thông báo

Thông báo được chia theo ý nghĩa trước khi trình bày:

1. Lỗi hoặc cảnh báo ảnh hưởng kết quả: đề mơ hồ, thiếu dữ kiện, miền không hợp lệ, kiểm chứng thất bại, kết quả gần đúng. Hiển thị nổi bật và cụ thể.
2. Điều kiện toán học bắt buộc: miền xác định, giả thiết độc lập, đơn vị góc. Đặt trong mục `Điều kiện`, không gọi là lỗi.
3. Thông tin nội bộ: interpreter rule-based, fallback provider, normalization, consistency replay thành công. Giữ trong log/metadata phục vụ vận hành, không hiện cho người học.

Kết quả `solved` và kiểm chứng đạt không hiện cảnh báo xác nhận thừa. Kết quả kiểm chứng một phần chỉ hiện khi giới hạn đó làm thay đổi cách người dùng nên tin hoặc sử dụng đáp án.

## Tương thích

- Giữ nguyên request và response schema hiện tại.
- Các field `warnings`, `assumptions`, `steps` vẫn tồn tại; chỉ thay đổi nội dung và chính sách hiển thị.
- Dữ liệu lịch sử cũ vẫn đọc được. Bộ lọc giao diện phải xử lý được cả thông báo cũ và mới.
- Đây là thay đổi hành vi có chủ đích: `log(x)` từ nay là cơ số 10 trong Algebra thay vì ngữ nghĩa mặc định của SymPy.

## Xử lý lỗi

- `log` có cơ số bằng 0, 1 hoặc không hợp lệ phải trả lỗi/điều kiện rõ ràng, không fallback sang logarit tự nhiên.
- Ký hiệu log không xác định được đối số hoặc cơ số không được sửa đoán âm thầm.
- Nếu một kết quả không thể kiểm chứng đủ, giữ kết quả ở trạng thái phù hợp và chỉ nêu giới hạn kiểm chứng một lần.

## Kiểm thử

- Unit test parser cho `ln(x)`, `log(x)`, `log(x, 2)`, `log_2(x)` và câu tiếng Việt.
- Regression tích phân `x*ln(x)` phải dùng `\ln` ở đáp án và mọi bước.
- Regression tích phân `x*log(x)` phải tính theo cơ số 10 và hiển thị `\log_{10}`.
- Test đạo hàm và phương trình để chứng minh cơ số ảnh hưởng đúng tới kết quả.
- Test API bảo đảm text/LaTeX thống nhất và không phát sinh thông báo nội bộ cho kết quả đã xác minh.
- Test frontend bảo đảm chỉ cảnh báo có thể hành động được mới xuất hiện, không lặp thông báo.
- Chạy full backend, frontend test/build, CI, sau đó kiểm tra production với các ca `ln`, `log` và log cơ số bất kỳ.

## Tiêu chí hoàn thành

- Không còn ca nhập `ln` nhưng hiển thị `log`.
- `log(x)` được tính như logarit cơ số 10, không chỉ đổi nhãn.
- Logarit có cơ số rõ giữ nguyên cơ số qua toàn bộ pipeline.
- Kết quả đúng và đã xác minh không hiện ghi chú kỹ thuật hoặc cảnh báo thừa.
- Các cảnh báo còn lại mô tả rõ tác động và hành động người dùng cần thực hiện.
