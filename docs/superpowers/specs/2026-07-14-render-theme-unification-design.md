# Thiết kế đồng bộ theme theo Render

## Mục tiêu

Đồng bộ toàn bộ giao diện theo ngôn ngữ thị giác hiện có của trang `/render`: monochrome, rõ ràng, thiên về công cụ, mật độ thông tin vừa phải và dùng nền lưới cho không gian làm việc. Thay đổi chỉ tác động presentation; không đổi nghiệp vụ, luồng dữ liệu, API hoặc quyền truy cập.

## Phạm vi

Áp dụng cho mọi route và trạng thái giao diện trong frontend, gồm:

- Trang chủ, header, menu công cụ, footer và thông báo.
- Render, khảo sát hàm, giải đại số, mô phỏng, GeoGebra Lab và PDF-to-Word.
- Lịch sử, hướng dẫn, giới thiệu, phản hồi và trang pháp lý.
- Đăng nhập, xác minh email, đặt lại mật khẩu, tài khoản và cài đặt.
- Admin, modal, dropdown, drawer, loading, empty, error, disabled và permission state.

Các thay đổi frontend đang có trong working tree phải được giữ nguyên; phần theme chỉ chỉnh presentation quanh chúng.

## Baseline thị giác

### Màu sắc

- Dùng bảng màu trung tính đang có ở `/render`: nền `surface`, giấy `paper`, đường viền `line`, chữ `ink` và accent đen.
- Chỉ dùng màu ngữ nghĩa cho success, warning, danger và information; không dùng màu trang trí riêng theo từng màn hình.
- Giữ nền lưới ở canvas hoặc workspace nơi lưới có ý nghĩa; không đưa lưới vào mọi card hoặc form.
- Không thêm gradient trang trí, glow hoặc shadow nặng.

### Typography

- Dùng cùng system sans stack hiện tại cho toàn ứng dụng; KaTeX tiếp tục chịu trách nhiệm hiển thị công thức.
- Chuẩn hóa thang chữ theo vai trò: metadata/eyebrow, caption, body, control, section title, page title và hero title.
- Heading dùng trọng lượng và line-height nhất quán; nội dung dài ưu tiên khả năng đọc thay vì tăng font tùy từng trang.
- Số liệu và dữ liệu đo dùng kiểu số tabular khi phù hợp.

### Kích thước và spacing

- Chuẩn hóa chiều cao control, padding ngang, khoảng cách giữa label và field, khoảng cách section và page gutter.
- Giữ mật độ gần `/render`: compact nhưng không chật, ưu tiên 40–44 px cho control chính và vùng bấm tối thiểu phù hợp trên mobile.
- Dùng hệ radius nhỏ đến vừa; pill chỉ dành cho badge, chip hoặc segmented control.
- Shadow chỉ dùng cho lớp nổi như dropdown, modal và notification.

## Kiến trúc CSS

1. Mở rộng token trong `:root` thành nhóm semantic rõ ràng cho màu, typography, control size, spacing, radius, shadow và z-index.
2. Chuẩn hóa base element và các primitive hiện có: button, input, select, textarea, card/panel, badge, modal, empty state và feedback state.
3. Cập nhật các section CSS theo từng module để dùng token thay cho màu, font size, radius và spacing hardcode. Không tạo một lớp override khổng lồ ở cuối file để che legacy CSS.
4. Đồng bộ stylesheet riêng của Function Analyzer với token toàn cục, vẫn giữ token đồ thị chuyên biệt cho grid, curve và điểm dữ liệu.
5. Chỉ sửa JSX khi cần thêm class dùng chung, semantic HTML hoặc thuộc tính accessibility; không di chuyển business logic vào component trình bày.

## Hành vi và accessibility

- Giữ nguyên data flow và toàn bộ callback hiện có.
- Giữ focus-visible rõ ràng, label gắn đúng control và aria-label cho nút chỉ có icon.
- Disabled, loading, empty và error phải dễ phân biệt nhưng dùng cùng hệ visual.
- Không thêm animation mới. Transition tương tác nếu có không quá 200 ms và chỉ dùng cho feedback cục bộ.
- Responsive giữ nguyên chức năng; layout nhiều cột chuyển thành một cột có thứ tự đọc hợp lý trên màn hình nhỏ.

## Chiến lược triển khai

1. Lập inventory token và các cụm selector đang lệch chuẩn.
2. Chuẩn hóa foundation và chrome toàn cục.
3. Đồng bộ nhóm công cụ toán học và workspace.
4. Đồng bộ nhóm nội dung, auth, account/settings và admin.
5. Rà soát responsive, interaction state và loại bỏ hardcode còn làm lệch theme.

## Kiểm tra

- Chạy toàn bộ test frontend hiện có liên quan đến các component bị chạm.
- Chạy `npm run build` để kiểm tra TypeScript và Vite build.
- Chụp và so sánh các route đại diện ở desktop 1440×1000 và mobile 390×844.
- Kiểm tra thủ công header/menu, form controls, modal/dropdown, loading, empty, error, disabled và focus-visible.
- Kiểm tra `git diff` để bảo đảm không ghi đè các thay đổi nghiệp vụ đang có trong working tree.

## Tiêu chí hoàn thành

- Các route dùng cùng font stack, thang chữ, màu, control size, spacing, radius và elevation.
- `/render` vẫn giữ đúng cảm giác hiện tại và đóng vai trò baseline.
- Không còn cụm UI lớn mang palette hoặc density riêng không có lý do nghiệp vụ.
- Build và test liên quan thành công; các giới hạn kiểm tra được báo cáo chính xác.
