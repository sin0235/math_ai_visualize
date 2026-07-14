# Thiết kế ổn định workspace và trực quan hóa goal khoảng cách Scene v3

Ngày: 2026-07-14

## 1. Bối cảnh

Luồng `POST /api/render/v3` hiện có ba lỗi liên quan nhưng độc lập:

- AI có thể trả lại cùng một `scene_id` ổn định cho các lượt dựng cùng đề. `scene_workspaces.scene_id` là khóa duy nhất nên lần lưu sau phát sinh `409 SCENE_WORKSPACE_EXISTS`, dù provider đã trả scene thành công.
- Minh họa khoảng cách điểm–mặt phẳng chỉ được backend hoàn thiện khi model đã để lại một metric goal có đúng object IDs. Nếu model bỏ `distance relation`, không tạo face/plane mục tiêu hoặc làm mất operands, backend không có goal để dựng chân chiếu.
- Khối chuẩn đang dùng sáu màu pastel khác nhau. Khi các mặt trong suốt chồng lên nhau, màu cạnh tranh với nội dung cần chú ý và làm mặt phẳng mục tiêu khó nhận biết.

Ví dụ regression chính là hình lập phương `ABCD.MNPQ`, `F` là trung điểm `CD`, cần minh họa `d(M,(PFB))`. Thiết kế phải tổng quát cho câu hỏi khoảng cách từ một điểm đến mặt phẳng ba điểm, không được hardcode các nhãn `M`, `P`, `F`, `B` hoặc riêng hình lập phương.

## 2. Mục tiêu

- Mỗi lượt dựng mới tạo một workspace mới, kể cả khi đề và JSON AI giống lượt trước.
- Nhận diện goal khoảng cách điểm–mặt phẳng từ nguyên văn đề, độc lập với việc model có tạo relation hay không.
- Bảo đảm canvas có mặt mục tiêu, chân chiếu, đoạn vuông góc, ký hiệu góc vuông và nhãn đại lượng.
- Không hiển thị đáp số trên canvas. Solver tiếp tục chịu trách nhiệm tính và trình bày kết quả.
- Giảm màu cạnh tranh nhưng vẫn phân biệt được từng mặt: các mặt kề nhau dùng màu khác nhau trong một hệ hài hòa; mặt cắt/mặt mục tiêu và đoạn khoảng cách có accent riêng.
- Thể hiện được cả dữ kiện đề mô tả và đại lượng đề hỏi: cạnh/mặt/quan hệ đã cho ở tầng nền, construction cho góc/khoảng cách ở tầng nhấn mạnh.
- Giữ schema/public response hiện tại và không sửa style thuộc quyền sở hữu của người dùng.

## 3. Ngoài phạm vi

- Không thay đổi thuật toán giải hoặc đáp số của classical point-plane engine.
- Không đổi schema `MathSceneV3`, response API hoặc contract command/confirm/export.
- Không dựng goal từ văn bản mơ hồ không xác định được duy nhất một điểm và ba điểm mặt phẳng.
- Không viết lại toàn bộ pipeline geometry hoặc renderer.

## 4. Thiết kế

### 4.1. Identity do server sở hữu

AI không phải nguồn tin cậy cho identity persistence. Ở boundary tạo mới của `POST /api/render/v3`, server cấp `scene_id` mới sau extraction/repair và trước projection/persistence. ID dùng prefix hiện tại và entropy đủ để không va chạm.

Việc cấp ID chỉ áp dụng cho một lượt render mới. Các luồng nhận scene đã tồn tại như workspace command, confirm, restore, solve và export tiếp tục giữ nguyên `scene_id` để bảo toàn revision/reference. Endpoint tạo workspace từ scene tường minh cũng không bị âm thầm đổi ID vì caller có thể đang quản lý reference đó.

Kết quả pipeline, projection, response, history revision và workspace row phải cùng một ID được server cấp.

### 4.2. Trích xuất metric goal deterministic từ nguyên văn

Sau raw normalization và trước bước hoàn thiện goal visualization, backend chạy parser goal cho `problem_text`:

1. Dùng normalization hiện có để thu gọn ngoặc kép như `((PFB))` và nhận các dạng tiếng Việt tương đương.
2. Chỉ chấp nhận dạng khoảng cách từ đúng một point label đến mặt phẳng tạo bởi ít nhất ba point labels.
3. Resolve label sang point object IDs trong scene. Mỗi label phải ánh xạ duy nhất.
4. Tìm face/plane có tập điểm chứa ba điểm mục tiêu. Nếu chưa có, tạo một `FaceV3` với `source=construction` và metadata role `distance_goal_plane` từ ba point IDs để biểu diễn vùng hữu hạn cần nhấn mạnh.
5. Tạo `DerivedFactV3` role `goal`, quantity `distance` với source IDs gồm point và face/plane mục tiêu nếu chưa có goal tương đương.

Parser không tạo constraint `distance` và không thêm giá trị số. Goal trích từ nguyên văn chỉ điều khiển phần trình bày, không được dùng như premise solver.

Nếu không resolve duy nhất hoặc ba điểm thẳng hàng, không dựng giả. Pipeline giữ scene hiện có và phát warning `DISTANCE_GOAL_UNRESOLVED` để chẩn đoán.

### 4.3. Hoàn thiện minh họa khoảng cách

`scene_goal_visualization_v3` tiếp tục là điểm thực thi duy nhất cho minh họa goal:

- Chiếu điểm nguồn xuống face/plane bằng geometry kernel.
- Tái sử dụng point hiện có tại tọa độ chân chiếu trong tolerance; nếu không có thì tạo `H`, `H1`, ... với `source=construction`.
- Tạo hoặc chuẩn hóa segment từ điểm nguồn đến chân chiếu: visible, dashed, màu teal `#0f766e`, line width 3.
- Tạo measurement label chính xác theo label mặt phẳng từ đề, ví dụ `d(M,(PFB))`.
- Tạo right-angle annotation tại chân chiếu với một arm nằm trong mặt phẳng.
- Gắn metadata `visualization_role` để renderer/style normalization nhận biết mặt mục tiêu và đoạn goal.

Completion phải idempotent và không tạo object/annotation trùng khi model đã dựng đúng.

### 4.4. Phân cấp màu

Khối chuẩn không dùng sáu màu pastel bão hòa cao. Palette topology chuyển sang bốn tông slate-blue nhạt và được gán theo adjacency graph để các mặt kề nhau khác màu; các mặt không kề nhau được phép tái sử dụng màu:

- `#dbe4ee`
- `#cbd8e6`
- `#b9c9db`
- `#a8bbd1`

Opacity mặt khối giữ thấp và nhất quán. Mặt goal dùng hổ phách `#f59e0b` với opacity vừa đủ để thấy tam giác/mặt phẳng nhưng không che cạnh. Segment goal dùng teal `#0f766e`. Cạnh thật dùng `#1d3557`; cạnh khuất tiếp tục dùng slate xám.

Không đổi màu object có `locked=true`, `user_edited=true` hoặc source `user_created`/`user_edited`. Mặt thiết diện/cross-section có role riêng tiếp tục dùng palette thiết diện hiện tại; goal styling không được ghi đè nó.

Frontend giữ một accent chính cho từng loại goal và không thêm animation, gradient hoặc glow. `faceOpacity` phải tôn trọng hierarchy này thay vì nâng mọi face thường đến mức cạnh tranh với mặt goal.

Quy ước semantic:

- mặt khối: bốn tông slate-blue được graph-coloring để mọi mặt kề nhau khác màu;
- mặt cắt/thiết diện: cam đậm, opacity cao hơn mặt khối, viền đỏ rõ;
- mặt phẳng đang được hỏi hoặc dùng cho distance/angle: hổ phách trong suốt;
- khoảng cách/chân chiếu: teal nét đứt, measurement và right-angle cùng màu;
- góc giữa hai đường: cung góc với hai arm nhìn thấy;
- góc đường–mặt: vẽ hình chiếu của đường lên mặt phẳng rồi đánh dấu góc giữa đường và hình chiếu;
- góc hai mặt phẳng: vẽ giao tuyến nếu xác định được và hai đoạn vuông góc giao tuyến trong từng mặt, sau đó đánh dấu góc giữa hai đoạn;
- cạnh khuất của mặt khối: renderer quyết định theo camera và hiển thị slate xám nét đứt; cạnh construction không bị thuật toán cạnh khuất ghi đè tùy tiện.

Mọi construction góc/khoảng cách chỉ được tạo khi operands resolve duy nhất và geometry không suy biến. Nếu chưa đủ căn cứ, scene giữ dữ kiện đã có và phát warning có cấu trúc thay vì bịa hình.

### 4.5. Prompt extraction và repair

Prompt vẫn phải hướng model đến output tốt để giảm công việc repair:

- `scene_id` là placeholder, identity cuối cùng do server cấp.
- Với câu hỏi point-plane distance, bắt buộc tạo face/plane đúng ba điểm được nêu trong câu hỏi, không chỉ chọn một mặt sẵn có của khối.
- Tạo point chân chiếu, segment, right-angle và measurement nếu tính được từ tọa độ đã chọn.
- Không tạo `distance relation` thiếu `args.value` và không hiển thị đáp số tự suy ra.
- Dùng màu trung tính cho khối; chỉ face/plane mục tiêu và segment goal dùng accent.
- Thêm một ví dụ v3 hoàn chỉnh theo schema cho goal khoảng cách điểm–mặt phẳng, có object IDs hợp lệ và self-check.
- Với câu hỏi góc, phải giữ đúng hai thành phần được hỏi và dựng construction chuẩn theo loại line-line, line-plane hoặc plane-plane; không dùng annotation cung góc nếu chưa có hai arm hình học hợp lệ.
- Self-check phải đối chiếu hai danh sách: dữ kiện/quan hệ xuất hiện trong đề và goal xuất hiện sau từ khóa hỏi/tính/chứng minh; scene chỉ hoàn thành khi cả hai đều có representation nhìn thấy hoặc issue giải thích vì sao không thể dựng.

Repair prompt giữ cùng invariant để không xóa goal render-only khi sửa contract.

## 5. Luồng dữ liệu

```text
problem_text
    -> provider extraction/repair
    -> normalize + topology completion
    -> deterministic metric-goal extraction từ problem_text
    -> goal visualization completion
    -> request overrides + server-generated scene_id
    -> scene pipeline + projection
    -> history/workspace persistence
```

Mọi bước sau khi server cấp identity phải dùng cùng scene object đã cập nhật. Không phát sinh projection mang ID khác workspace.

## 6. Xử lý lỗi

- Va chạm ID ngẫu nhiên cực hiếm vẫn trả conflict nội bộ có log request ID; không tái dùng workspace cũ hoặc ghi đè dữ liệu.
- Goal không resolve được phát issue chỉ rõ label thiếu/không duy nhất, không tạo điểm hoặc mặt phẳng giả.
- Geometry kernel từ chối mặt phẳng suy biến; lỗi được giữ nguyên nguyên nhân.
- Persistence không đổi ownership guard: scene của user này không được ghi đè workspace của user khác.
- Không catch rộng rồi chuyển mọi lỗi sang thông báo provider unavailable. `SCENE_WORKSPACE_EXISTS` không còn được frontend diễn giải như lỗi AI.

## 7. Kiểm thử

### Backend unit/regression

- Hai lượt render cùng problem/model output nhận hai `scene_id` khác nhau và đều persist thành công.
- Luồng command/confirm/restore giữ nguyên ID của workspace đã tồn tại.
- Parser nhận các dạng `Khoảng cách từ điểm M đến mặt phẳng (PFB)`, `((PFB))`, `d(M,(PFB))`.
- Scene không có distance relation vẫn tạo goal từ nguyên văn khi point labels resolve đủ.
- Scene kết quả có face/plane PFB, chân chiếu, segment MH, measurement và right-angle.
- Completion idempotent; không nhân đôi object khi model đã dựng đủ.
- Mặt phẳng suy biến hoặc label mơ hồ không bị dựng giả.
- Hình lập phương vẫn đủ 8 đỉnh, 12 cạnh, 6 mặt và giữ user-owned style.
- Palette mới dùng tông trung tính, face goal và segment goal có accent đúng.
- Prompt extraction/repair có invariant và ví dụ goal đầy đủ.

### Frontend

- Appearance test phân biệt mặt khối thường, mặt goal và thiết diện.
- Cạnh chính/cạnh khuất/segment goal giữ đúng màu, line width và dash.
- Cung góc và construction line-plane/plane-plane có đủ arm, projection/intersection và metadata semantic.
- Render projection giữ metadata/style cần thiết đến `ThreeGeometryView`.
- Build và TypeScript type-check thành công.

### Kiểm tra rộng

- Chạy backend test liên quan extractor, prompt, fidelity, goal visualization, routes/history/workspace và point-plane parser.
- Chạy frontend unit tests liên quan projection/appearance.
- Chạy backend suite, frontend build và lint nếu project có script lint.

## 8. Tiêu chí hoàn thành

- Dựng lại cùng đề không còn trả `409 Scene workspace đã tồn tại`.
- Hình lập phương hiển thị đủ cạnh và mặt khi xoay.
- Mặt `(PFB)` là vùng màu nổi bật duy nhất; `MH`, ký hiệu vuông góc và `d(M,(PFB))` nhìn thấy rõ.
- Các mặt kề nhau nhìn phân biệt; mặt cắt không lẫn với mặt khối; cạnh khuất đổi nét theo camera.
- Với đề hỏi góc, canvas cho thấy đúng hai thành phần tạo góc và construction cần thiết; với đề hỏi khoảng cách, canvas cho thấy đoạn đại diện khoảng cách và chân vuông góc.
- Dữ kiện hình học đề đã mô tả và mục tiêu đề hỏi đều có biểu diễn trực quan hoặc warning có cấu trúc, không bị bỏ âm thầm.
- Canvas không hiện `2√6` hoặc đáp số khác.
- Không có thay đổi public schema, không mất history/workspace cũ và không ghi đè style người dùng.
- Test, build, type-check/lint phù hợp đều xanh hoặc phần không chạy được được báo chính xác.
