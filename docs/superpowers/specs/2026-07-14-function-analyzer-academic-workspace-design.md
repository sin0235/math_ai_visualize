# Thiết kế Academic Workspace cho Function Analyzer

## Mục tiêu

Làm lại phân cấp thị giác của trang `/analyzer` theo hướng học thuật hiện đại, sáng rõ và dễ đọc. Đồ thị là nội dung chính; công thức, kết luận và đặc trưng toán học được đọc theo thứ tự tự nhiên mà không tạo cảm giác dashboard nặng hoặc nhiều card nổi.

Thay đổi chỉ tác động presentation và cấu trúc trình bày cục bộ. Không thay đổi phép phân tích, dữ liệu trả về, public API, route, quyền truy cập hoặc nghiệp vụ của Function Analyzer.

## Vấn đề hiện tại

- Workspace, vùng nhập, đồ thị và kết quả đều dùng bề mặt trắng gần như giống nhau nên không có tiêu điểm.
- Lưới nền xuất hiện cả ngoài workspace lẫn trong đồ thị, làm tăng nhiễu và cạnh tranh với hệ trục toán học.
- CSS của analyzer được định nghĩa ở cả `frontend/src/styles.css` và `frontend/src/components/function-analyzer/function-analyzer.css`; lớp override cuối xóa nền, shadow và radius của nhiều khối nhưng không tạo hệ phân cấp thay thế.
- Kết quả chính dùng nhiều đường kẻ rời và các khối nhỏ thiếu nhóm, trong khi một số trạng thái khác lại dùng card lồng card. Hai cách trình bày tạo cảm giác vừa phẳng vừa thô.
- Bố cục desktop có các cột và control với kích thước tối thiểu cạnh tranh nhau, có nguy cơ tràn khi viewport hoặc vùng nội dung hẹp hơn dự kiến.

## Hướng thiết kế đã duyệt

Sử dụng Academic Workspace bản phẳng:

1. Bỏ lưới khỏi nền trang và nền workspace; chỉ giữ lưới toán học bên trong biểu đồ.
2. Dùng một khối nhập công thức có ranh giới rõ ở đầu trang.
3. Gộp đồ thị và kết quả vào một workspace chính duy nhất trên desktop, ngăn hai vùng bằng đường phân cách thay vì hai card nổi.
4. Không dùng card lồng card cho từng dữ kiện. Kết quả dùng section, grid và separator trên cùng một bề mặt.
5. Chỉ dùng elevation cho phần tử thực sự nổi như popover, modal, menu và toast. Workspace chính không dùng shadow hoặc chỉ dùng shadow nền tảng hiện có ở mức gần như không nhận thấy.
6. Màu xanh lá biểu thị đường hàm và trạng thái đã kiểm chứng; màu phụ chỉ dùng khi mang ý nghĩa dữ liệu. Không dùng gradient trang trí.

## Cấu trúc giao diện

### Phần giới thiệu

- Tiêu đề `Khảo sát hàm số` và mô tả ngắn nằm trên vùng nhập.
- Không dùng hero lớn; chiều cao gọn để đồ thị vẫn xuất hiện sớm trong viewport.
- Metadata hoặc nhãn công cụ dùng cỡ chữ nhỏ và màu trung tính, không cạnh tranh với tiêu đề.

### Thanh nhập công thức

- Một panel phẳng, viền rõ và radius vừa phải.
- Desktop dùng grid gồm biểu thức, chọn ảnh, nút phân tích và xem trước.
- Biểu thức là vùng co giãn chính; các nút giữ kích thước theo nội dung; vùng xem trước có giới hạn an toàn.
- Khi thiếu chiều rộng, vùng xem trước xuống hàng trước. Trên mobile, nút chính chiếm hàng riêng nếu cần.
- Mọi grid item dùng `min-width: 0`; nội dung công thức dài dùng overflow ngang hoặc ellipsis theo ngữ cảnh, không làm rộng container.

### Workspace phân tích

- Một outer surface chứa hai cột: đồ thị và kết quả.
- Cột đồ thị rộng hơn và là tiêu điểm. Biểu đồ có viền cục bộ vì đó là canvas tương tác độc lập.
- Cột kết quả không bọc thêm card. Tiêu đề, công thức chuẩn hóa, trạng thái kiểm chứng, dữ kiện tổng quan và đặc trưng chi tiết được phân tầng bằng spacing và separator.
- Desktop dùng đường phân cách dọc giữa hai cột. Khi xuống một cột, đường phân cách chuyển thành ngang.

### Kết quả chính

- Công thức đã chuẩn hóa đứng đầu, có typography toán học lớn hơn dữ kiện phụ.
- Badge kiểm chứng dùng nền success rất nhạt, viền và chữ đủ tương phản.
- Tập xác định, tập giá trị, giao Ox và giao Oy dùng grid hai cột; các ô chỉ có separator, không có nền và shadow riêng.
- Cực trị, đơn điệu, tiệm cận và các đặc trưng khác dùng danh sách label–value thẳng hàng.
- Các phần nâng cao tiếp tục dùng disclosure hiện có nhưng phải cùng ngôn ngữ separator, spacing và focus-visible.

## Màu sắc và độ sâu

- Nền trang: `surface` trung tính.
- Bề mặt nhập và workspace: `paper`.
- Bề mặt phụ rất nhẹ chỉ dùng trong input hoặc trạng thái cần nhóm: `surface-raised` hoặc `surface`.
- Đường phân cách: `line`; ranh giới control: `line-2`.
- Chữ chính: `ink`; metadata: `ink-3` hoặc `ink-4` nếu vẫn đạt tương phản.
- Đường hàm và trạng thái tích cực dùng semantic green hiện có. Điểm dữ liệu phụ dùng màu chart hiện có, không tạo palette trang trí mới.
- Không dùng gradient, glow hoặc shadow nặng. Không dùng radius pill ngoài badge hoặc chip.

## Responsive và chống tràn

- Outer layout dùng `minmax(0, ...)`; mọi cột, section và control con có `min-width: 0`.
- Container analyzer có `width: 100%` và `max-width` theo layout hiện tại; padding được tính trong box model.
- Ở breakpoint tablet, workspace chuyển một cột nếu cột kết quả không còn đủ chiều rộng đọc.
- Thanh nhập chuyển từ bốn vùng sang ba vùng, sau đó hai vùng; xem trước được ưu tiên xuống hàng.
- Công thức, bảng và KaTeX dài có vùng cuộn ngang cục bộ với `overscroll-behavior-inline: contain`; toàn trang không phát sinh horizontal scrollbar.
- Đồ thị giữ chiều cao hữu ích trên mobile nhưng không vượt quá viewport; các toolbar có thể cuộn ngang cục bộ thay vì làm rộng trang.
- Vùng bấm chính trên mobile tối thiểu 44 px.

## Kiến trúc CSS

- `function-analyzer.css` là nơi sở hữu layout và appearance riêng của analyzer.
- `styles.css` chỉ giữ design token và primitive dùng chung. Các selector `.fa2-*` trùng hoặc override mang tính layout sẽ được hợp nhất hoặc loại khỏi lớp global khi có thể làm an toàn.
- Không thêm một lớp override mới ở cuối `styles.css` để che các khai báo cũ.
- JSX chỉ thay đổi khi cần nhóm semantic rõ hơn, thêm class có trách nhiệm cụ thể hoặc sửa accessibility; không đưa logic toán học vào component trình bày.
- Giữ nguyên callback, state và contract của `AnalyzerInput`, `AnalyzerResult`, `FunctionGraph` và các tool controls.

## Accessibility và tương tác

- Giữ label hoặc accessible name cho toàn bộ control và nút chỉ có icon.
- Dùng `button` cho action, giữ keyboard interaction mặc định của `details/summary` và control native.
- Mọi interactive element có trạng thái hover, active và `:focus-visible` rõ ràng.
- Loading, error và cập nhật bất đồng bộ tiếp tục dùng live region phù hợp.
- Không chặn paste hoặc zoom trình duyệt.
- Không thêm animation mới. Nếu giữ transition hiện có, chỉ chuyển các thuộc tính cụ thể và tôn trọng `prefers-reduced-motion`.

## Phạm vi triển khai dự kiến

- `frontend/src/components/function-analyzer/function-analyzer.css`: nguồn chính cho layout, surface, responsive và chống tràn.
- `frontend/src/styles.css`: hợp nhất hoặc loại selector analyzer trùng, nhưng phải bảo toàn các thay đổi chưa commit hiện có của người dùng.
- `frontend/src/components/function-analyzer/AnalyzerInput.tsx`: chỉ điều chỉnh cấu trúc semantic/class nếu CSS hiện tại không đủ biểu đạt bố cục đã duyệt.
- `frontend/src/components/function-analyzer/AnalyzerResult.tsx`: chỉ điều chỉnh nhóm presentation nếu cần loại card lồng card và tạo separator đúng trách nhiệm.
- Test appearance hoặc component liên quan được cập nhật khi selector hay cấu trúc DOM thay đổi.

## Kiểm tra

- Chạy test frontend hiện có cho Function Analyzer và utility appearance liên quan.
- Chạy type-check hoặc production build bằng script của frontend.
- Chạy lint nếu project có script tương ứng.
- Kiểm tra thủ công ở desktop rộng, desktop hẹp, tablet và mobile.
- Xác nhận không có horizontal scrollbar ở page level với công thức dài, KaTeX dài, toolbar mở và bảng biến thiên.
- Xác nhận loading, empty, success, warning, error, parameter mode, disclosure, popover và graph toolbar vẫn dễ đọc.
- Kiểm tra keyboard focus, accessible name và contrast của text phụ/badge.
- Rà `git diff` để bảo đảm không ghi đè phần `frontend/src/styles.css` đang có thay đổi trước tác vụ này.

## Tiêu chí hoàn thành

- Lưới chỉ còn trong biểu đồ; nền analyzer sạch và không cạnh tranh với dữ liệu.
- Đồ thị là tiêu điểm rõ ràng, kết quả được đọc theo thứ tự công thức, kết luận chính rồi chi tiết.
- Không còn card lồng card trong phần kết quả chính và không lạm dụng shadow.
- Không có horizontal overflow ở các viewport đại diện.
- Layout responsive giữ đủ chức năng và thứ tự đọc hợp lý.
- Không thay đổi logic phân tích, API hoặc dữ liệu toán học.
- Test liên quan và production build thành công; mọi giới hạn kiểm tra được báo cáo chính xác.
