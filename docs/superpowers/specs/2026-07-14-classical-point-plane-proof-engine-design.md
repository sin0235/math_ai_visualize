# Thiết kế proof engine tổng quát cho khoảng cách điểm–mặt phẳng

## Mục tiêu

Mode `classical` giải các bài `distance_point_plane` bằng fact và định lý có thể phát lại, kể cả khi chân đường vuông góc chưa được cho trực tiếp. Engine không được đọc tọa độ render để quyết định premise, dựng proof hoặc tính đáp án.

Cấu hình hình lập phương `ABCD.MNPQ`, `F` là trung điểm `CD`, cần tính `d(M,(PFB))` chỉ là một regression test. Không có rule nào được phụ thuộc vào các tên `A, B, C, D, M, N, P, Q, F`, chuỗi `PFB` hoặc loại khối hình lập phương cụ thể.

## Phương án được chọn

Mở rộng fact graph và theorem engine thành tìm kiếm chứng minh deterministic có giới hạn:

1. Chuẩn hóa premise đáng tin cậy thành fact hình học.
2. Dùng forward chaining để sinh fact dẫn xuất qua các theorem rule tổng quát.
3. Sinh ứng viên điểm phụ từ midpoint, center, intersection và projection construction hợp lệ.
4. Tìm một đoạn từ điểm nguồn đến một điểm thuộc mặt phẳng đích, đồng thời chứng minh đoạn đó vuông góc với hai đường cắt nhau trong mặt phẳng.
5. Tính độ dài đoạn bằng symbolic metric chỉ từ các độ dài/quan hệ đã chứng minh.
6. Xuất proof certificate và bắt buộc `replay_proof_plan` chấp nhận trước khi trả kết quả.

Không chọn fallback sang Oxyz vì sẽ phá contract của mode classical. Không dùng AI sinh theorem chain vì không deterministic và có nguy cơ thêm premise không tồn tại.

## Phạm vi fact

### Fact đầu vào

- `length`, `equal_length`, `scalar_measure`.
- `midpoint`, `intersection`, `point_on_line`, `point_on_plane`, `plane_points`.
- `perpendicular_lines`, `perpendicular_line_plane`, `parallel_lines`.
- `right_angle`, `collinear`, `coplanar`.
- Fact cấu trúc hình học đã được scene/extractor xác nhận: tam giác đặc biệt, hình vuông, hình chữ nhật, hình bình hành, lăng trụ đứng, hình hộp chữ nhật và hình lập phương.

Fact cấu trúc phải được biểu diễn bằng loại fact và operand tổng quát. Parser có thể đọc mệnh đề trực tiếp trong `problem_text` để tạo fact `given`, nhưng không được tạo đáp án hoặc theorem chain dựa trên tên điểm cố định.

### Fact dẫn xuất

- Midpoint suy ra thuộc đường thẳng và hai đoạn bằng nhau.
- Tâm/giao điểm đường chéo suy ra incidence và midpoint tương ứng khi premise cấu trúc cho phép.
- Hình vuông/hình chữ nhật suy ra cạnh vuông góc, cạnh đối song song và công thức đường chéo.
- Lăng trụ đứng/hình hộp/hình lập phương suy ra cạnh bên vuông góc đáy, các mặt tương ứng và các cạnh bằng nhau theo cấu trúc.
- Tam giác cân/đều cộng midpoint suy ra đường trung tuyến đồng thời là đường cao khi đủ premise.
- Định lý Pythagore và đảo Pythagore sinh độ dài hoặc quan hệ vuông góc từ biểu thức exact.
- Một đường vuông góc với hai đường cắt nhau trong mặt phẳng suy ra vuông góc mặt phẳng.

Mỗi fact dẫn xuất phải ghi `source_fact_ids`, `theorem_id`, cost và biểu thức symbolic nếu có.

## Tìm kiếm điểm phụ và chân đường vuông góc

Engine tạo ứng viên có giới hạn, theo thứ tự chi phí:

1. Điểm có sẵn thuộc mặt phẳng và đã có quan hệ vuông góc trực tiếp.
2. Midpoint, center hoặc intersection đã có trong fact graph.
3. Midpoint của một đoạn có hai đầu thuộc mặt phẳng và liên quan tới điểm nguồn hoặc các fact metric hiện có.
4. Giao điểm của hai đường đã có incidence rõ ràng.
5. Projection construction chỉ được nhận khi theorem chain chứng minh được hai quan hệ vuông góc cần thiết; không lấy projection số học từ tọa độ.

Với mỗi ứng viên `H`, engine phải chứng minh:

- `H` thuộc mặt phẳng đích.
- Có hai đường phân biệt, cắt nhau tại `H`, cùng thuộc mặt phẳng đích.
- Đoạn từ điểm nguồn đến `H` vuông góc với cả hai đường.

Chỉ khi đủ ba điều kiện mới sinh fact `perpendicular_line_plane` và dùng định nghĩa khoảng cách điểm–mặt phẳng.

## Symbolic metric

- Dùng SymPy hoặc biểu thức rational/radical đã có trong project.
- Chỉ nhận biến/giá trị từ fact đáng tin cậy và fact dẫn xuất đã có proof dependency.
- Các rule metric phải tạo cả biểu thức, LaTeX exact và dependency graph.
- Không làm tròn trong proof. API trả dạng exact; UI hoặc tầng trình bày mới làm tròn theo yêu cầu đề bài.
- Nếu có nhiều proof cho cùng mục tiêu, chọn proof có cost thấp nhất rồi số bước ít nhất.

## Giới hạn tìm kiếm

- Tái sử dụng `MAX_PROOF_STEPS` và `MAX_PROOF_COST`.
- Thêm giới hạn số fact dẫn xuất, số ứng viên điểm phụ và độ sâu forward chaining.
- Dedupe fact theo loại, operand chuẩn hóa và biểu thức symbolic.
- Không retry hoặc mở rộng tìm kiếm vô hạn.
- Khi vượt giới hạn, trả `Không đủ dữ kiện` kèm warning phân biệt `proof_search_exhausted` với `missing_premise`.

## Kiến trúc module

- `geometry_facts.py`: chuẩn hóa fact đầu vào và fact cấu trúc, không thực hiện tìm kiếm.
- `geometry_theorems.py`: đăng ký theorem tổng quát, premise contract, conclusion và cost.
- Module mới trong `services/geometry/`: forward chaining, auxiliary candidate generation và tìm proof cho `distance_point_plane`.
- `proof_search.py`: tiếp tục chịu trách nhiệm tạo/replay proof certificate; mở rộng để fact dẫn xuất có thể được replay theo dependency thay vì tự động tin cậy.
- `solver_service.py`: điều phối. Với mode classical, gọi proof engine trước nhánh tính bằng tọa độ; chỉ trả kết quả khi certificate hợp lệ.
- Route, schema và frontend giữ nguyên trừ khi cần bổ sung mã warning nội bộ tương thích ngược.

## Data flow

1. Chuẩn hóa câu hỏi thành goal điểm–mặt phẳng.
2. Xây trusted fact graph từ scene và premise đề bài.
3. Forward-chain các theorem rule trong giới hạn.
4. Sinh và xếp hạng ứng viên chân đường vuông góc.
5. Với từng ứng viên, tìm proof incidence, hai quan hệ vuông góc và độ dài exact.
6. Chọn proof hợp lệ có cost thấp nhất.
7. Chuyển proof thành `SolverStep`, construction action và proof plan.
8. Replay certificate; chỉ kết quả `accepted=true` mới được trả cho người dùng.

## Xử lý lỗi

- Fact `construction`, `render_only`, verification `failed/error` không được dùng làm premise.
- Scene có metric mâu thuẫn phải trả insufficient; không chọn một giá trị tùy ý.
- Không tìm được chân hoặc không chứng minh đủ hai đường vuông góc phải trả insufficient.
- Có kết quả symbolic nhưng certificate replay thất bại phải bỏ kết quả và ghi warning verifier.
- Oxyz giữ behavior hiện tại và không bị ảnh hưởng bởi proof engine classical.

## Ma trận kiểm thử

### Positive

- Chân đường cao được cho trực tiếp.
- Chân là midpoint đã cho trong tam giác cân/đều.
- Chân là tâm hoặc giao điểm đường chéo trong hình vuông/hình chữ nhật.
- Bài lăng trụ đứng/hình hộp có cạnh bên vuông góc đáy.
- Cấu hình hình lập phương–midpoint–mặt phẳng PFB cạnh `4` trả `2\sqrt{6}`.
- Cùng cấu hình với cạnh khác trả công thức tỉ lệ đúng, chứng minh không hardcode số.
- Đổi toàn bộ tên đỉnh nhưng giữ graph đẳng cấu vẫn nhận cùng proof pattern.
- Scene không có tọa độ render nhưng đủ fact vẫn giải được.

### Negative

- Thiếu midpoint/center/intersection cần thiết.
- Điểm phụ không chứng minh được thuộc mặt phẳng.
- Chỉ chứng minh được vuông góc với một đường trong mặt phẳng.
- Độ dài đến từ annotation render-only hoặc fact verification failed.
- Metric mâu thuẫn.
- Graph vượt giới hạn tìm kiếm.
- Mặt phẳng suy biến hoặc goal không phải point-plane distance.

### Backward compatibility

- Các direct-height classical test hiện có tiếp tục pass và ưu tiên proof chi phí thấp.
- Oxyz tests tiếp tục pass; test cũ kỳ vọng decimal được cập nhật để chấp nhận LaTeX exact.
- Proof replay từ các dạng góc, diện tích, thể tích và quan hệ khác không thay đổi.

## Phân kỳ triển khai

Đây là một thay đổi nhiều lớp nhưng cùng một subsystem. Triển khai theo thứ tự:

1. Fact derivation contract và theorem registry.
2. Generic bounded forward chaining.
3. Auxiliary point candidates và point-plane goal search.
4. Symbolic metric derivation.
5. Proof replay cho derived facts.
6. Solver integration và regression matrix.

Mỗi lớp phải có unit test độc lập trước khi tích hợp lớp kế tiếp.

## Rủi ro còn lại

Proof search rule-based không thể cam kết giải mọi bài hình học có thể phát biểu. “Toàn diện” trong phạm vi này nghĩa là kiến trúc và luật tổng quát, không hardcode một đề; các họ định lý mới vẫn cần được đăng ký bằng rule và test tương ứng.
