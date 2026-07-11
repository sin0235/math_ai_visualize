# CHECKLIST CẢI TIẾN CHỨC NĂNG SIMULATION

## Dự án AI Math Renderer

> **Cách đọc file này**
>
> - Đây là **roadmap + checklist mục tiêu** (tầm nhìn sản phẩm), không phải báo cáo “đã ship hết”.
> - Mục **0** bên dưới là **audit hiện trạng** (cập nhật 2026-07-10).
> - Checkbox `[ ]` = chưa đạt chuẩn mục tiêu; `[~]` = đã có seed/một phần; `[x]` = đạt mức checklist.
> - Plan triển khai chi tiết: [`docs/superpowers/specs/2026-07-10-simulation-thpt-implementation-plan.md`](../docs/superpowers/specs/2026-07-10-simulation-thpt-implementation-plan.md)

---

# 0. Hiện trạng vs tầm nhìn (audit 2026-07-10, cập nhật sau Phase 3)

## 0.1. Kết luận nhanh

| Câu hỏi | Trả lời |
| --- | --- |
| Simulation hiện có “nông” không? | **Vẫn hẹp coverage** (4 published), nhưng đã có **thư viện + shell + pedagogy + verify client** (Phase 0–3) |
| Checklist bên dưới phản ánh đúng dự án? | **Đúng khoảng trống nội dung P0 còn lại**; engine nền tảng Phase 1–3 **đã ship frontend** |
| Backend simulation? | **Cố ý chưa có** — verify client-only, không đụng API khác |
| Sẵn sàng scale theo lớp 10–12? | **Có khung catalog/spec**; thêm P0 = thêm template + entry catalog |

**Định vị hiện tại (sau Phase 3):** thư viện public VI, 4 mô phỏng published (Riemann, khối tròn xoay, thiết diện, lượng giác), shell chung, checkpoint, không multi-user/chia sẻ.  
**Định vị mục tiêu dài hạn:** đủ 12 P0 + teacher mode (Phase 4–5), không AI cho đến Phase 7.

## 0.2. Inventory code hiện có

| Module | File chính | Loại | Mức độ |
| --- | --- | --- | --- |
| Shell playbar (chạy/dừng/bước/tốc độ/reset) | `frontend/src/components/CalculusSimulationPage.tsx` | process-simulation shell | `[~]` dùng được, chưa engine chung |
| Diện tích giữa hai đường + Riemann | `calculus/AreaBetweenCurvesSimulation.tsx` | interactive + process | `[~]` khá tốt; thiếu left/right/midpoint tách biệt, pedagogy |
| Khối tròn xoay disk/washer 3D | `calculus/SolidOfRevolutionSimulation.tsx` + `CalculusThreeViews.tsx` | interactive + process | `[~]` Ox OK; Oy disabled; thiếu full pedagogy |
| Thiết diện song song (V=∫S) | `calculus/CrossSectionVolumeSimulation.tsx` | interactive + process | `[~]` seed; ngoài checklist P0 chính |
| Đường tròn lượng giác + sóng | `trigonometry/TrigonometrySimulation.tsx` | interactive + process | `[~]` sin/cos/tan/cot, pha, tốc độ; thiếu A,ω,k đầy đủ chuẩn P0 |
| Numerics client-side | `utils/calculusExpression.ts`, `calculusNumerics.ts`, `trigonometryNumerics.ts` | math helpers | `[~]` frontend only, không SymPy |
| GeoGebra Lab (tách biệt) | `GeoGebraLabPage.tsx` | lab ngoài Simulation | Không tính là simulation template |

**Quy mô:** ~1.6k dòng UI simulation + ~0.5k dòng numerics. Không có bảng `simulation_*` / API `/simulation`.

## 0.3. Ma trận coverage so với checklist

| Khối checklist | Ước lượng hoàn thành | Ghi chú |
| --- | --- | --- |
| §2 Chương trình GDPT 2018 (cây lớp/mạch/chủ đề) | ~25% | Catalog tĩnh + filter lớp/mạch; chưa DB/SGK |
| §3 Bốn loại hình mô phỏng (schema) | ~40% | `SimulationSpec.kind` + 2 loại đang dùng |
| §4 Nội dung lớp 10 | ~0% | Chưa có module (Phase 4) |
| §5 Nội dung lớp 11 | ~20% | Unit circle + sóng A/B/φ published |
| §6 Nội dung lớp 12 | ~30% | Riemann modes + solid + cross-section |
| §7 UI thư viện + chi tiết | ~70% | Library cards, breadcrumb, pedagogy; không share/favorite |
| §8 Kiến trúc SimulationSpec / renderer | ~45% | Spec + shell + template map; renderer interface chưa full |
| §9 AI authoring simulation | ~0% | Cắt khỏi Phase 3 |
| §10 DB curriculum/assessment/analytics | ~0% | Cắt khỏi Phase 3 |
| §11 UX controls/formulas/responsive | ~55% | Shell + filters responsive cơ bản |
| §12 Kiểm thử (math/UI/perf/sư phạm) | ~25% | `npm run test:simulation` baseline |
| §13 Publish gate | ~30% | `status` trên catalog; chưa workflow admin |
| §14 12 mô phỏng P0 | ~2.5 / 12 | 4 seed published, chưa đủ 12 topic P0 |
| §15 Giai đoạn 0–3 | **Done (frontend)** | GĐ4–7 chưa |

## 0.4. Map seed → mục checklist (không đếm là “xong”)

| Seed hiện có | Map tới | Đã có | Còn thiếu so với chuẩn P0 |
| --- | --- | --- | --- |
| AreaBetweenCurves | §6.4 Riemann + diện tích | n, exact vs approx, \|f−g\|, giao điểm, step playbar | left/right/mid; dấu trên/dưới trục; pedagogy; verification backend |
| SolidOfRevolution | §6.5 Khối tròn xoay | disk/washer, 3D sweep, lát cắt, n | quay Oy; shell; pedagogy đầy đủ |
| CrossSectionVolume | mở rộng §6.4/6.5 | stack lát cắt | ngoài 12 P0 chính; giữ làm bonus |
| Trigonometry | §5.1 (+ một phần 5.2) | unit circle ↔ sin/cos; tan/cot; phase; animation | biên độ/tần số; tiệm cận; phương trình; checkpoint |

## 0.5. Điểm mạnh cần giữ khi refactor

1. Playbar process-simulation (step + progress + speed) đã quen UX.
2. `compileExpression` + numerics client đủ nhanh cho slider realtime.
3. 3D Three.js khối tròn xoay đã chứng minh renderer 3D trong Simulation.
4. Preset + ResultCard + Katex — pattern UI nên chuẩn hóa thành shared kit.
5. GeoGebra Lab và MathScene (Render) là **tài sản tái sử dụng**, không nhồi vào cùng một monocomponent.

## 0.6. Rủi ro nếu triển khai “toàn bộ checklist” một lần

- Scope checklist ≈ **nền tảng curriculum + engine + 12 P0 + AI + teacher mode + analytics** → nhiều quý, không phải một sprint.
- Hardcode thêm module mà không có `SimulationSpec` → technical debt tăng tuyến tính.
- Pedagogy (dự đoán/checkpoint) và math verification dễ bị bỏ qua nếu chỉ chase visual.

**Nguyên tắc:** ship theo **phase có PR độc lập**; mỗi phase có definition of done; P0 trước P1/P2; AI authoring **sau** template ổn định.

---

# 1. Mục tiêu cải tiến

Nâng cấp chức năng `Simulation` từ tập hợp các mô phỏng toán học riêng lẻ thành một **thư viện mô phỏng Toán THPT có cấu trúc**, bám sát Chương trình Giáo dục phổ thông 2018.

Hệ thống cần:

* Phân loại nội dung theo lớp 10, 11 và 12.
* Phân loại theo mạch kiến thức, chủ đề và nội dung học.
* Hỗ trợ trực quan hóa, mô phỏng, khám phá và kiểm chứng kiến thức.
* Tái sử dụng các engine toán học, đồ họa 2D và 3D hiện có.
* Hỗ trợ học sinh tự học và giáo viên trình chiếu trên lớp.
* Bảo đảm kết quả toán học được kiểm chứng, không phụ thuộc hoàn toàn vào LLM.

---

# 2. Checklist tổng thể

## 2.1. Khảo sát và chuẩn hóa chương trình

* [ ] Thu thập cấu trúc nội dung Toán lớp 10 theo Chương trình GDPT 2018.
* [ ] Thu thập cấu trúc nội dung Toán lớp 11 theo Chương trình GDPT 2018.
* [ ] Thu thập cấu trúc nội dung Toán lớp 12 theo Chương trình GDPT 2018.
* [ ] Chia nội dung theo ba mạch kiến thức chính:

  * [ ] Số, Đại số và Giải tích.
  * [ ] Hình học và Đo lường.
  * [ ] Thống kê và Xác suất.
* [ ] Xây dựng danh sách chủ đề chuẩn, không phụ thuộc vào một bộ sách giáo khoa cụ thể.
* [ ] Ánh xạ chủ đề chuẩn với bộ sách Kết nối tri thức.
* [ ] Ánh xạ chủ đề chuẩn với bộ sách Chân trời sáng tạo.
* [ ] Ánh xạ chủ đề chuẩn với bộ sách Cánh Diều.
* [ ] Xác định mục tiêu cần đạt của từng chủ đề.
* [ ] Xác định kiến thức tiên quyết của từng mô phỏng.
* [ ] Xác định nội dung bắt buộc và nội dung mở rộng.
* [ ] Loại bỏ các nội dung không phù hợp với phạm vi THPT.
* [ ] Xác định nội dung nào thực sự cần mô phỏng.
* [ ] Xác định nội dung nào chỉ cần hình minh họa hoặc biểu đồ tương tác.

### Kết quả cần đạt

Hệ thống có một cây chương trình thống nhất:

```text
Lớp
└── Mạch kiến thức
    └── Chủ đề
        └── Nội dung
            └── Mô phỏng
```

---

# 3. Phân loại loại hình mô phỏng

## 3.1. Trực quan hóa

* [ ] Xây dựng loại nội dung `visualization`.
* [ ] Dùng cho các nội dung chủ yếu cần hiển thị hình, biểu đồ hoặc quan hệ.
* [ ] Không bắt buộc phải có hoạt ảnh theo thời gian.
* [ ] Cho phép bật, tắt các lớp thông tin.

### Ví dụ

* Biểu đồ Venn.
* Đồ thị hàm số.
* Biểu đồ thống kê.
* Hình biểu diễn vectơ.
* Cây xác suất.

---

## 3.2. Mô hình tương tác

* [ ] Xây dựng loại nội dung `interactive-model`.
* [ ] Cho phép kéo điểm, kéo hình hoặc thay đổi tham số.
* [ ] Kết quả phải cập nhật theo thời gian thực.
* [ ] Công thức và hình ảnh phải đồng bộ.
* [ ] Có nút khôi phục trạng thái ban đầu.

### Ví dụ

* Kéo đỉnh tam giác.
* Thay đổi hệ số hàm số bậc hai.
* Thay đổi biên độ và chu kỳ hàm lượng giác.
* Thay đổi tâm và bán kính đường tròn.

---

## 3.3. Mô phỏng quá trình

* [ ] Xây dựng loại nội dung `process-simulation`.
* [ ] Có timeline hoặc tiến trình theo bước.
* [ ] Có nút chạy, dừng, chuyển bước và đặt lại.
* [ ] Có điều chỉnh tốc độ.
* [ ] Có thể quan sát trạng thái tại từng thời điểm.

### Ví dụ

* Điểm chuyển động trên đường tròn lượng giác.
* Tổng Riemann tiến tới tích phân.
* Thí nghiệm tung đồng xu hoặc xúc xắc.
* Cát tuyến tiến tới tiếp tuyến.

---

## 3.4. Phòng thí nghiệm khám phá

* [ ] Xây dựng loại nội dung `exploration-lab`.
* [ ] Có câu hỏi dự đoán trước khi thao tác.
* [ ] Cho phép học sinh thay đổi dữ kiện.
* [ ] Có phần ghi nhận kết quả quan sát.
* [ ] Có câu hỏi kết luận.
* [ ] Có bài kiểm tra ngắn sau hoạt động.

### Chu trình đề xuất

```text
Dự đoán
→ Thao tác
→ Quan sát
→ Giải thích
→ Kiểm tra
```

---

# 4. Checklist nội dung lớp 10

## 4.1. Mệnh đề và tập hợp

* [ ] Biểu đồ Venn cho phép hợp, giao, hiệu và phần bù.
* [ ] Mô phỏng quan hệ tập con.
* [ ] Bảng chân trị cho các phép toán logic.
* [ ] Hiển thị quan hệ giữa mệnh đề và tập hợp.
* [ ] Tạo bài tập kéo thả phần tử vào tập hợp phù hợp.

### Mức ưu tiên

`P2 — Có thể triển khai sau`

---

## 4.2. Bất phương trình hai ẩn

* [ ] Hiển thị đường biên của bất phương trình.
* [ ] Cho phép thay đổi các hệ số `a`, `b`, `c`.
* [ ] Cho phép chọn điểm thử.
* [ ] Hiển thị nửa mặt phẳng thỏa mãn.
* [ ] Hiển thị nửa mặt phẳng không thỏa mãn.
* [ ] Hỗ trợ nhiều bất phương trình đồng thời.
* [ ] Tô miền giao của hệ bất phương trình.
* [ ] Hiển thị tọa độ các đỉnh của miền nghiệm.
* [ ] Hỗ trợ bài toán tối ưu tuyến tính đơn giản.
* [ ] Cho phép di chuyển đường biểu diễn hàm mục tiêu.

### Mức ưu tiên

`P0 — Nên triển khai sớm`

---

## 4.3. Hàm số và đồ thị

* [ ] Xây dựng mô phỏng hàm số bậc hai.
* [ ] Cho phép thay đổi `a`, `b`, `c`.
* [ ] Hiển thị đỉnh của parabol.
* [ ] Hiển thị trục đối xứng.
* [ ] Hiển thị số nghiệm của phương trình.
* [ ] Hiển thị giá trị biệt thức.
* [ ] Hiển thị bảng dấu tam thức.
* [ ] Đồng bộ giữa công thức, đồ thị và bảng biến thiên.
* [ ] Hỗ trợ tịnh tiến đồ thị.
* [ ] Hỗ trợ co giãn đồ thị.
* [ ] Hỗ trợ đối xứng đồ thị.
* [ ] So sánh nhiều đồ thị trên cùng hệ trục.

### Mức ưu tiên

`P0 — Nên triển khai sớm`

---

## 4.4. Hệ thức lượng trong tam giác

* [ ] Cho phép kéo ba đỉnh của tam giác.
* [ ] Hiển thị độ dài ba cạnh.
* [ ] Hiển thị ba góc.
* [ ] Kiểm chứng định lý sin.
* [ ] Kiểm chứng định lý cos.
* [ ] Hiển thị diện tích tam giác.
* [ ] Hiển thị bán kính đường tròn ngoại tiếp.
* [ ] Hiển thị bán kính đường tròn nội tiếp.
* [ ] Cho phép bật hoặc tắt đường cao.
* [ ] Cho phép bật hoặc tắt đường trung tuyến.
* [ ] Cho phép bật hoặc tắt đường phân giác.
* [ ] Có câu hỏi khám phá trước khi hiển thị kết luận.

### Mức ưu tiên

`P0 — Nên triển khai sớm`

---

## 4.5. Vectơ

* [ ] Mô phỏng quy tắc ba điểm.
* [ ] Mô phỏng quy tắc hình bình hành.
* [ ] Mô phỏng phép cộng vectơ.
* [ ] Mô phỏng phép trừ vectơ.
* [ ] Mô phỏng nhân vectơ với một số.
* [ ] Hiển thị tọa độ vectơ.
* [ ] Phân tích một vectơ theo hai vectơ không cùng phương.
* [ ] Hiển thị tích vô hướng.
* [ ] Hiển thị góc giữa hai vectơ.
* [ ] Hiển thị hình chiếu của vectơ.
* [ ] Nhận biết điều kiện vuông góc.
* [ ] Nhận biết điều kiện cùng phương.

### Mức ưu tiên

`P0 — Nên triển khai sớm`

---

## 4.6. Tọa độ trong mặt phẳng

* [ ] Mô phỏng phương trình đường thẳng.
* [ ] Thay đổi vectơ chỉ phương.
* [ ] Thay đổi vectơ pháp tuyến.
* [ ] Hiển thị hệ số góc.
* [ ] Hiển thị vị trí tương đối của hai đường thẳng.
* [ ] Tính khoảng cách từ điểm đến đường thẳng.
* [ ] Mô phỏng phương trình đường tròn.
* [ ] Thay đổi tâm và bán kính.
* [ ] Mô phỏng elip.
* [ ] Mô phỏng hypebol.
* [ ] Mô phỏng parabol.
* [ ] Hiển thị tiêu điểm và đường chuẩn của đường conic.

### Mức ưu tiên

`P1 — Triển khai sau nhóm P0`

---

## 4.7. Thống kê và xác suất

* [ ] Nhập hoặc sinh tập dữ liệu.
* [ ] Hiển thị bảng tần số.
* [ ] Hiển thị biểu đồ cột.
* [ ] Hiển thị histogram.
* [ ] Hiển thị trung bình.
* [ ] Hiển thị trung vị.
* [ ] Hiển thị mốt.
* [ ] Hiển thị tứ phân vị.
* [ ] Hiển thị khoảng biến thiên.
* [ ] Cho phép kéo các điểm dữ liệu.
* [ ] Cập nhật các đại lượng thống kê theo thời gian thực.
* [ ] Mô phỏng tung đồng xu.
* [ ] Mô phỏng tung xúc xắc.
* [ ] So sánh xác suất lý thuyết và tần suất thực nghiệm.
* [ ] Hiển thị sự hội tụ khi số lần thử tăng lên.

### Mức ưu tiên

`P1`

---

# 5. Checklist nội dung lớp 11

## 5.1. Hàm số lượng giác

* [ ] Nâng cấp mô phỏng đường tròn lượng giác hiện có.
* [ ] Liên kết điểm trên đường tròn với tọa độ `cos` và `sin`.
* [ ] Liên kết chuyển động trên đường tròn với đồ thị `sin`.
* [ ] Liên kết chuyển động trên đường tròn với đồ thị `cos`.
* [ ] Hiển thị dấu theo từng góc phần tư.
* [ ] Hiển thị các góc đặc biệt.
* [ ] Hỗ trợ đơn vị độ và radian.
* [ ] Hiển thị chu kỳ của hàm số.
* [ ] Thay đổi biên độ.
* [ ] Thay đổi tần số.
* [ ] Thay đổi pha.
* [ ] Thay đổi độ dịch chuyển theo phương đứng.
* [ ] So sánh `sin`, `cos`, `tan` và `cot`.
* [ ] Hiển thị tiệm cận của hàm `tan` và `cot`.

### Mức ưu tiên

`P0`

---

## 5.2. Phương trình lượng giác

* [ ] Hiển thị nghiệm trên đường tròn lượng giác.
* [ ] Hiển thị giao điểm trên đồ thị.
* [ ] Hiển thị họ nghiệm tổng quát.
* [ ] Cho phép giới hạn nghiệm trong một khoảng.
* [ ] So sánh nghiệm trên đường tròn và trên trục số.
* [ ] Hỗ trợ phương trình `sin x = m`.
* [ ] Hỗ trợ phương trình `cos x = m`.
* [ ] Hỗ trợ phương trình `tan x = m`.
* [ ] Hỗ trợ phương trình `cot x = m`.
* [ ] Cảnh báo khi phương trình vô nghiệm.
* [ ] Sinh câu hỏi xác định số nghiệm trong một khoảng.

### Mức ưu tiên

`P0`

---

## 5.3. Dãy số, cấp số cộng và cấp số nhân

* [ ] Hiển thị các số hạng của dãy trên trục số.
* [ ] Hiển thị dãy dưới dạng biểu đồ điểm.
* [ ] Hiển thị dãy dưới dạng biểu đồ cột.
* [ ] Thay đổi số hạng đầu.
* [ ] Thay đổi công sai.
* [ ] Thay đổi công bội.
* [ ] So sánh cấp số cộng và cấp số nhân.
* [ ] Hỗ trợ công thức truy hồi.
* [ ] Hiển thị tổng `n` số hạng đầu.
* [ ] Mô phỏng bài toán lãi kép.
* [ ] Mô phỏng tăng trưởng và suy giảm.

### Mức ưu tiên

`P1`

---

## 5.4. Giới hạn và tính liên tục

* [ ] Cho phép điểm `x` tiến tới `a`.
* [ ] Hiển thị giá trị hàm số tương ứng.
* [ ] Hiển thị bảng giá trị.
* [ ] Hiển thị giới hạn trái.
* [ ] Hiển thị giới hạn phải.
* [ ] Hiển thị trường hợp giới hạn hữu hạn.
* [ ] Hiển thị trường hợp giới hạn vô cực.
* [ ] Hiển thị tiệm cận đứng.
* [ ] Hiển thị tiệm cận ngang.
* [ ] Mô phỏng điểm gián đoạn có thể khử.
* [ ] Mô phỏng điểm gián đoạn nhảy.
* [ ] Cho phép thay đổi tham số để hàm số liên tục.
* [ ] Có chế độ từng bước giải thích điều kiện liên tục.

### Mức ưu tiên

`P0`

---

## 5.5. Đạo hàm

* [ ] Hiển thị cát tuyến qua hai điểm.
* [ ] Cho một điểm tiến gần điểm còn lại.
* [ ] Hiển thị cát tuyến tiến tới tiếp tuyến.
* [ ] Hiển thị hệ số góc cát tuyến.
* [ ] Hiển thị hệ số góc tiếp tuyến.
* [ ] Hiển thị giá trị đạo hàm tại điểm.
* [ ] Liên kết đồ thị hàm số và đồ thị đạo hàm.
* [ ] Mô phỏng tốc độ biến thiên.
* [ ] Mô phỏng chuyển động với vị trí và vận tốc.
* [ ] Hỗ trợ tìm phương trình tiếp tuyến.
* [ ] Sinh câu hỏi dự đoán dấu đạo hàm.

### Mức ưu tiên

`P0`

---

## 5.6. Hình học không gian

* [ ] Dựng đường thẳng và mặt phẳng trong không gian.
* [ ] Cho phép xoay mô hình 3D.
* [ ] Cho phép phóng to và thu nhỏ.
* [ ] Hiển thị giao tuyến của hai mặt phẳng.
* [ ] Hiển thị điều kiện hai đường thẳng song song.
* [ ] Hiển thị điều kiện đường thẳng song song với mặt phẳng.
* [ ] Hiển thị điều kiện hai mặt phẳng song song.
* [ ] Hiển thị đường vuông góc với mặt phẳng.
* [ ] Hiển thị góc giữa đường thẳng và mặt phẳng.
* [ ] Hiển thị góc giữa hai mặt phẳng.
* [ ] Hiển thị hình chiếu vuông góc.
* [ ] Hiển thị khoảng cách từ điểm đến mặt phẳng.
* [ ] Hiển thị khoảng cách giữa hai đường thẳng chéo nhau.
* [ ] Mô phỏng thiết diện của hình chóp.
* [ ] Mô phỏng thiết diện của lăng trụ.
* [ ] Cho phép bật hoặc tắt các mặt phẳng phụ.

### Mức ưu tiên

`P0`

---

## 5.7. Xác suất

* [ ] Xây dựng biểu đồ Venn tương tác.
* [ ] Xây dựng cây xác suất.
* [ ] Cho phép thay đổi xác suất trên từng nhánh.
* [ ] Kiểm tra tổng xác suất.
* [ ] Mô phỏng biến cố hợp.
* [ ] Mô phỏng biến cố giao.
* [ ] Mô phỏng biến cố độc lập.
* [ ] Mô phỏng nhiều giai đoạn.
* [ ] So sánh kết quả lý thuyết với thực nghiệm.
* [ ] Sinh dữ liệu ngẫu nhiên cho thí nghiệm.

### Mức ưu tiên

`P0`

---

# 6. Checklist nội dung lớp 12

## 6.1. Ứng dụng đạo hàm và khảo sát hàm số

* [ ] Liên kết đồ thị hàm số với dấu đạo hàm.
* [ ] Hiển thị khoảng đồng biến.
* [ ] Hiển thị khoảng nghịch biến.
* [ ] Hiển thị điểm cực đại.
* [ ] Hiển thị điểm cực tiểu.
* [ ] Hiển thị giá trị lớn nhất.
* [ ] Hiển thị giá trị nhỏ nhất.
* [ ] Hiển thị tiệm cận đứng.
* [ ] Hiển thị tiệm cận ngang.
* [ ] Hiển thị tiệm cận xiên.
* [ ] Đồng bộ đồ thị, đạo hàm và bảng biến thiên.
* [ ] Cho phép thay đổi tham số của hàm số.
* [ ] Quan sát sự xuất hiện hoặc biến mất của cực trị.
* [ ] Mô phỏng bài toán tối ưu hình học.
* [ ] Mô phỏng bài toán tối ưu thực tế.

### Mức ưu tiên

`P0`

---

## 6.2. Vectơ và tọa độ trong không gian

* [ ] Hiển thị hệ trục `Oxyz`.
* [ ] Tạo điểm bằng tọa độ.
* [ ] Tạo vectơ bằng tọa độ.
* [ ] Thực hiện phép cộng vectơ.
* [ ] Thực hiện phép trừ vectơ.
* [ ] Tính tích vô hướng.
* [ ] Tính góc giữa hai vectơ.
* [ ] Mô phỏng phương trình mặt phẳng.
* [ ] Mô phỏng phương trình đường thẳng.
* [ ] Hiển thị vị trí tương đối của hai đường thẳng.
* [ ] Hiển thị vị trí tương đối của đường thẳng và mặt phẳng.
* [ ] Hiển thị vị trí tương đối của hai mặt phẳng.
* [ ] Tính giao điểm.
* [ ] Tính giao tuyến.
* [ ] Hiển thị khoảng cách trong không gian.

### Mức ưu tiên

`P0`

---

## 6.3. Mặt cầu

* [ ] Thay đổi tâm mặt cầu.
* [ ] Thay đổi bán kính.
* [ ] Hiển thị phương trình mặt cầu.
* [ ] Hiển thị giao của mặt cầu với mặt phẳng.
* [ ] Hiển thị giao của mặt cầu với đường thẳng.
* [ ] Hiển thị tiếp diện của mặt cầu.
* [ ] Hiển thị khoảng cách từ tâm đến mặt phẳng.
* [ ] Phân loại trường hợp không giao, tiếp xúc và cắt nhau.
* [ ] Cho phép xoay mô hình 3D.

### Mức ưu tiên

`P0`

---

## 6.4. Nguyên hàm và tích phân

* [ ] Hiển thị họ nguyên hàm `F(x) + C`.
* [ ] Cho phép thay đổi hằng số `C`.
* [ ] So sánh các đường cong trong cùng một họ nguyên hàm.
* [ ] Mô phỏng tổng Riemann trái.
* [ ] Mô phỏng tổng Riemann phải.
* [ ] Mô phỏng tổng Riemann trung điểm.
* [ ] Thay đổi số khoảng chia `n`.
* [ ] Hiển thị sai số gần đúng.
* [ ] So sánh tổng Riemann với tích phân chính xác.
* [ ] Phân biệt tích phân và diện tích hình phẳng.
* [ ] Hiển thị phần diện tích phía trên trục hoành.
* [ ] Hiển thị phần diện tích phía dưới trục hoành.
* [ ] Hỗ trợ diện tích giữa hai đồ thị.
* [ ] Tự động tìm giao điểm.
* [ ] Xác định hàm trên và hàm dưới.
* [ ] Chia khoảng khi hai hàm đổi vị trí.

### Mức ưu tiên

`P0`

---

## 6.5. Khối tròn xoay

* [ ] Hiển thị miền phẳng ban đầu.
* [ ] Cho phép chọn trục quay.
* [ ] Hiển thị quá trình quay.
* [ ] Hiển thị khối 3D được tạo thành.
* [ ] Hiển thị một lát cắt đại diện.
* [ ] Hỗ trợ phương pháp đĩa.
* [ ] Hỗ trợ phương pháp vòng đệm.
* [ ] Thay đổi độ dày lát cắt.
* [ ] Tăng hoặc giảm số lát cắt.
* [ ] So sánh tổng thể tích gần đúng với thể tích tích phân.
* [ ] Cho phép bật hoặc tắt phần khối bên trong.
* [ ] Cho phép xem mặt cắt của khối.

### Mức ưu tiên

`P0`

---

## 6.6. Thống kê

* [ ] Nhập dữ liệu ghép nhóm.
* [ ] Thay đổi khoảng ghép nhóm.
* [ ] Hiển thị bảng tần số ghép nhóm.
* [ ] Hiển thị giá trị đại diện.
* [ ] Tính trung bình mẫu.
* [ ] Tính phương sai.
* [ ] Tính độ lệch chuẩn.
* [ ] Tính khoảng tứ phân vị.
* [ ] So sánh hai mẫu dữ liệu.
* [ ] Giải thích mức độ phân tán.
* [ ] Quan sát ảnh hưởng của giá trị ngoại lệ.

### Mức ưu tiên

`P1`

---

## 6.7. Xác suất có điều kiện và định lý Bayes

* [ ] Hiển thị xác suất có điều kiện bằng biểu đồ vùng.
* [ ] Hiển thị xác suất có điều kiện bằng bảng hai chiều.
* [ ] Hiển thị xác suất có điều kiện bằng cây xác suất.
* [ ] Phân biệt `P(A|B)` và `P(B|A)`.
* [ ] Cho phép thay đổi xác suất nền.
* [ ] Cho phép thay đổi độ nhạy.
* [ ] Cho phép thay đổi độ đặc hiệu.
* [ ] Hiển thị số lượng giả định trên 1.000 đối tượng.
* [ ] Hiển thị số trường hợp dương tính thật.
* [ ] Hiển thị số trường hợp dương tính giả.
* [ ] Hiển thị số trường hợp âm tính thật.
* [ ] Hiển thị số trường hợp âm tính giả.
* [ ] Mô phỏng công thức xác suất toàn phần.
* [ ] Mô phỏng định lý Bayes.
* [ ] Có câu hỏi dự đoán trước khi hiển thị kết quả.

### Mức ưu tiên

`P0`

---

# 7. Checklist cấu trúc giao diện

## 7.1. Trang thư viện Simulation

* [ ] Có tab lớp 10.
* [ ] Có tab lớp 11.
* [ ] Có tab lớp 12.
* [ ] Có bộ lọc theo mạch kiến thức.
* [ ] Có bộ lọc theo chủ đề.
* [ ] Có bộ lọc theo loại mô phỏng.
* [ ] Có bộ lọc theo mức độ.
* [ ] Có ô tìm kiếm.
* [ ] Có sắp xếp theo lớp.
* [ ] Có sắp xếp theo độ phổ biến.
* [ ] Có sắp xếp theo nội dung mới.
* [ ] Có card mô phỏng thống nhất.
* [ ] Card hiển thị lớp.
* [ ] Card hiển thị chủ đề.
* [ ] Card hiển thị mục tiêu ngắn.
* [ ] Card hiển thị loại tương tác.
* [ ] Card hiển thị nhãn 2D hoặc 3D.
* [ ] Card hiển thị trạng thái hoàn thiện.
* [ ] Card có nút mở mô phỏng.
* [ ] Card có nút lưu yêu thích.

---

## 7.2. Trang chi tiết mô phỏng

* [ ] Hiển thị breadcrumb.
* [ ] Hiển thị tên mô phỏng.
* [ ] Hiển thị lớp và chủ đề.
* [ ] Hiển thị mục tiêu cần đạt.
* [ ] Hiển thị kiến thức tiên quyết.
* [ ] Hiển thị khu vực mô phỏng chính.
* [ ] Hiển thị bảng điều khiển.
* [ ] Có nút chạy.
* [ ] Có nút dừng.
* [ ] Có nút chuyển bước.
* [ ] Có nút đặt lại.
* [ ] Có điều chỉnh tốc độ.
* [ ] Có bật hoặc tắt lớp hình ảnh.
* [ ] Có hiển thị công thức.
* [ ] Có hiển thị giá trị hiện tại.
* [ ] Có câu hỏi khám phá.
* [ ] Có phần kết luận.
* [ ] Có bài kiểm tra ngắn.
* [ ] Có nút chia sẻ.
* [ ] Có chế độ toàn màn hình.
* [ ] Có chế độ trình chiếu.

---

## 7.3. Chế độ sử dụng

* [ ] Chế độ khám phá tự do.
* [ ] Chế độ hướng dẫn từng bước.
* [ ] Chế độ thử thách.
* [ ] Chế độ trình chiếu cho giáo viên.
* [ ] Chế độ xem nhanh.
* [ ] Chế độ ẩn công thức.
* [ ] Chế độ hiển thị lời giải.
* [ ] Chế độ tự động chạy.

---

# 8. Checklist kiến trúc kỹ thuật

## 8.1. SimulationSpec

* [ ] Xây dựng schema chuẩn cho mô phỏng.
* [ ] Có trường `id`.
* [ ] Có trường `version`.
* [ ] Có trường `grade`.
* [ ] Có trường `strand`.
* [ ] Có trường `topicCode`.
* [ ] Có trường `template`.
* [ ] Có trường `parameters`.
* [ ] Có trường `formulas`.
* [ ] Có trường `renderer`.
* [ ] Có trường `learningOutcomes`.
* [ ] Có trường `checkpoints`.
* [ ] Có trường `verification`.
* [ ] Có trường `textbookMappings`.
* [ ] Kiểm tra schema bằng Pydantic hoặc JSON Schema.
* [ ] Hỗ trợ versioning cho nội dung mô phỏng.
* [ ] Hỗ trợ migrate cấu hình cũ.

---

## 8.2. Renderer

* [ ] Tách renderer khỏi logic toán học.
* [ ] Xây dựng interface chung cho renderer.
* [ ] Hỗ trợ renderer 2D.
* [ ] Hỗ trợ renderer 3D.
* [ ] Hỗ trợ renderer biểu đồ.
* [ ] Hỗ trợ renderer GeoGebra.
* [ ] Hỗ trợ renderer tùy chỉnh bằng Canvas.
* [ ] Chuẩn hóa phương thức khởi tạo.
* [ ] Chuẩn hóa phương thức cập nhật tham số.
* [ ] Chuẩn hóa phương thức reset.
* [ ] Chuẩn hóa phương thức destroy.
* [ ] Chuẩn hóa hệ thống event.
* [ ] Hạn chế rò rỉ bộ nhớ khi chuyển trang.

### Cấu trúc đề xuất

```text
SimulationSpec
├── JSXGraphRenderer
├── ThreeRenderer
├── PlotlyRenderer
├── GeoGebraRenderer
└── CustomCanvasRenderer
```

---

## 8.3. Math engine

* [ ] Dùng SymPy để kiểm tra biểu thức.
* [ ] Dùng SymPy để tính đạo hàm.
* [ ] Dùng SymPy để tính tích phân.
* [ ] Dùng SymPy để giải phương trình.
* [ ] Dùng SymPy để tính giới hạn.
* [ ] Kiểm tra miền xác định.
* [ ] Kiểm tra các trường hợp tham số biên.
* [ ] Kiểm tra nghiệm gần đúng.
* [ ] Phân biệt kết quả chính xác và kết quả số.
* [ ] Không dùng trực tiếp kết quả do LLM tự suy luận.
* [ ] Có fallback khi SymPy không giải được.
* [ ] Hiển thị cảnh báo khi kết quả chỉ là gần đúng.

---

## 8.4. Hình học 2D và 3D

* [ ] Tái sử dụng cấu trúc `MathScene`.
* [ ] Chuẩn hóa đối tượng điểm.
* [ ] Chuẩn hóa đoạn thẳng.
* [ ] Chuẩn hóa đường thẳng.
* [ ] Chuẩn hóa vectơ.
* [ ] Chuẩn hóa mặt phẳng.
* [ ] Chuẩn hóa mặt.
* [ ] Chuẩn hóa khối.
* [ ] Chuẩn hóa quan hệ song song.
* [ ] Chuẩn hóa quan hệ vuông góc.
* [ ] Chuẩn hóa góc.
* [ ] Chuẩn hóa khoảng cách.
* [ ] Chuẩn hóa hình chiếu.
* [ ] Chuẩn hóa thiết diện.
* [ ] Tối ưu hiệu năng khi có nhiều đối tượng 3D.

---

# 9. Checklist AI

## 9.1. Phân loại yêu cầu

* [ ] Nhận diện lớp học.
* [ ] Nhận diện chủ đề.
* [ ] Nhận diện loại mô phỏng.
* [ ] Nhận diện công thức.
* [ ] Nhận diện tham số.
* [ ] Nhận diện miền giá trị.
* [ ] Nhận diện yêu cầu 2D hoặc 3D.
* [ ] Nhận diện mục tiêu học tập.
* [ ] Yêu cầu bổ sung thông tin khi đầu vào thiếu nghiêm trọng.
* [ ] Không tự ý đưa nội dung vượt chương trình.

---

## 9.2. Sinh cấu hình mô phỏng

* [ ] AI chỉ được chọn template đã có.
* [ ] AI chỉ được sinh tham số theo schema.
* [ ] Không cho AI sinh JavaScript tùy ý.
* [ ] Không cho AI sinh shader tùy ý.
* [ ] Kiểm tra kiểu dữ liệu.
* [ ] Kiểm tra khoảng giá trị.
* [ ] Kiểm tra biểu thức.
* [ ] Kiểm tra template tồn tại.
* [ ] Kiểm tra renderer hỗ trợ.
* [ ] Có trạng thái lỗi rõ ràng khi cấu hình không hợp lệ.

### Luồng đề xuất

```text
Yêu cầu tiếng Việt
→ Phân loại lớp và chủ đề
→ Chọn template
→ Trích xuất tham số
→ Kiểm tra schema
→ Kiểm chứng toán học
→ Dựng mô phỏng
→ Sinh giải thích
```

---

## 9.3. Sinh nội dung học tập

* [ ] Sinh câu hỏi dự đoán.
* [ ] Sinh hướng dẫn thao tác.
* [ ] Sinh câu hỏi quan sát.
* [ ] Sinh phần kết luận.
* [ ] Sinh bài kiểm tra ngắn.
* [ ] Kiểm tra đáp án bằng math engine.
* [ ] Phân biệt nội dung do AI sinh và nội dung đã được duyệt.
* [ ] Cho phép giáo viên chỉnh sửa trước khi công bố.
* [ ] Lưu phiên bản nội dung.
* [ ] Có cơ chế báo cáo nội dung sai.

---

# 10. Checklist cơ sở dữ liệu

## 10.1. Curriculum

* [ ] Tạo collection hoặc bảng `curriculum_nodes`.
* [ ] Lưu phiên bản chương trình.
* [ ] Lưu lớp.
* [ ] Lưu mạch kiến thức.
* [ ] Lưu mã chủ đề.
* [ ] Lưu tên chuẩn.
* [ ] Lưu chủ đề cha.
* [ ] Lưu thứ tự hiển thị.
* [ ] Lưu trạng thái bắt buộc hoặc mở rộng.

---

## 10.2. Textbook mapping

* [ ] Tạo `textbook_mappings`.
* [ ] Lưu bộ sách.
* [ ] Lưu tập sách.
* [ ] Lưu chương.
* [ ] Lưu bài.
* [ ] Lưu số thứ tự bài.
* [ ] Cho phép một chủ đề ánh xạ với nhiều bộ sách.

---

## 10.3. Simulation

* [ ] Tạo `simulation_templates`.
* [ ] Tạo `simulation_versions`.
* [ ] Tạo `simulation_presets`.
* [ ] Lưu renderer.
* [ ] Lưu cấu hình JSON.
* [ ] Lưu mức độ.
* [ ] Lưu trạng thái nháp.
* [ ] Lưu trạng thái đã duyệt.
* [ ] Lưu tác giả.
* [ ] Lưu người kiểm duyệt.
* [ ] Lưu ngày cập nhật.

---

## 10.4. Assessment

* [ ] Tạo `assessment_items`.
* [ ] Lưu câu hỏi dự đoán.
* [ ] Lưu câu hỏi quan sát.
* [ ] Lưu câu hỏi kiểm tra.
* [ ] Lưu đáp án.
* [ ] Lưu giải thích.
* [ ] Lưu mức độ khó.
* [ ] Lưu chủ đề liên quan.

---

## 10.5. Learning analytics

* [ ] Tạo `simulation_sessions`.
* [ ] Tạo `simulation_events`.
* [ ] Ghi nhận mở mô phỏng.
* [ ] Ghi nhận thay đổi tham số.
* [ ] Ghi nhận bật hoặc tắt layer.
* [ ] Ghi nhận gửi dự đoán.
* [ ] Ghi nhận trả lời checkpoint.
* [ ] Ghi nhận mở gợi ý.
* [ ] Ghi nhận reset.
* [ ] Ghi nhận hoàn thành.
* [ ] Không lưu dữ liệu cá nhân không cần thiết.
* [ ] Có chính sách xóa dữ liệu học tập.

---

# 11. Checklist trải nghiệm người dùng

## 11.1. Điều khiển

* [ ] Các slider có nhãn rõ ràng.
* [ ] Hiển thị giá trị hiện tại của slider.
* [ ] Có thể nhập giá trị bằng bàn phím.
* [ ] Không cho nhập giá trị ngoài miền hợp lệ.
* [ ] Có nút đặt lại từng tham số.
* [ ] Có nút đặt lại toàn bộ.
* [ ] Các nút có trạng thái disabled hợp lý.
* [ ] Không để điều khiển che khuất hình vẽ.
* [ ] Hỗ trợ màn hình cảm ứng.
* [ ] Hỗ trợ thao tác chuột.

---

## 11.2. Công thức

* [ ] Công thức dùng LaTeX.
* [ ] Công thức cập nhật cùng hình.
* [ ] Công thức không bị tràn trên màn hình nhỏ.
* [ ] Có chú thích ký hiệu.
* [ ] Có thể ẩn hoặc hiện công thức.
* [ ] Phân biệt công thức chính xác và gần đúng.
* [ ] Hiển thị đơn vị khi có.
* [ ] Không hiển thị quá nhiều công thức cùng lúc.

---

## 11.3. Hình ảnh và màu sắc

* [ ] Màu sắc nhất quán giữa các mô phỏng.
* [ ] Không dùng màu làm tín hiệu duy nhất.
* [ ] Có ký hiệu hoặc kiểu nét bổ sung.
* [ ] Bảo đảm tương phản.
* [ ] Hỗ trợ dark mode.
* [ ] Hạn chế hiệu ứng gây mất tập trung.
* [ ] Có chú giải màu.
* [ ] Các đối tượng quan trọng được làm nổi bật.
* [ ] Các đối tượng phụ có thể ẩn.

---

## 11.4. Responsive

* [ ] Hoạt động trên màn hình desktop.
* [ ] Hoạt động trên tablet.
* [ ] Hoạt động trên mobile.
* [ ] Bảng điều khiển có thể thu gọn.
* [ ] Công thức không bị cắt.
* [ ] Canvas tự điều chỉnh kích thước.
* [ ] Mô hình 3D không vượt khung.
* [ ] Không xuất hiện thanh cuộn ngang không cần thiết.

---

# 12. Checklist kiểm thử

## 12.1. Kiểm thử toán học

* [ ] Kiểm thử công thức chuẩn.
* [ ] Kiểm thử tham số bằng 0.
* [ ] Kiểm thử tham số âm.
* [ ] Kiểm thử giá trị rất nhỏ.
* [ ] Kiểm thử giá trị rất lớn.
* [ ] Kiểm thử trường hợp vô nghiệm.
* [ ] Kiểm thử trường hợp vô số nghiệm.
* [ ] Kiểm thử trường hợp suy biến.
* [ ] So sánh với kết quả SymPy.
* [ ] Kiểm tra sai số số thực.

---

## 12.2. Kiểm thử giao diện

* [ ] Kiểm tra slider.
* [ ] Kiểm tra kéo thả.
* [ ] Kiểm tra zoom.
* [ ] Kiểm tra xoay mô hình.
* [ ] Kiểm tra reset.
* [ ] Kiểm tra chạy và dừng.
* [ ] Kiểm tra thay đổi tốc độ.
* [ ] Kiểm tra chuyển bước.
* [ ] Kiểm tra chế độ toàn màn hình.
* [ ] Kiểm tra trên nhiều trình duyệt.

---

## 12.3. Kiểm thử hiệu năng

* [ ] Đo thời gian tải trang Simulation.
* [ ] Lazy-load renderer nặng.
* [ ] Lazy-load mô hình 3D.
* [ ] Giảm số lần render lại.
* [ ] Hủy animation frame khi rời trang.
* [ ] Giải phóng Three.js scene.
* [ ] Giải phóng geometry và material.
* [ ] Giới hạn số lượng đối tượng đồng thời.
* [ ] Kiểm tra trên thiết bị cấu hình thấp.
* [ ] Theo dõi mức sử dụng bộ nhớ.

---

## 12.4. Kiểm thử sư phạm

* [ ] Mục tiêu hoạt động được trình bày rõ.
* [ ] Học sinh hiểu cách thao tác.
* [ ] Mô phỏng không tiết lộ kết luận quá sớm.
* [ ] Câu hỏi dự đoán phù hợp.
* [ ] Câu hỏi kiểm tra bám sát nội dung.
* [ ] Không gây hiểu sai bản chất toán học.
* [ ] Thử nghiệm với học sinh lớp 10.
* [ ] Thử nghiệm với học sinh lớp 11.
* [ ] Thử nghiệm với học sinh lớp 12.
* [ ] Thu thập phản hồi giáo viên.
* [ ] Điều chỉnh theo phản hồi thực tế.

---

# 13. Checklist kiểm duyệt trước khi công bố

Một mô phỏng chỉ được chuyển sang trạng thái `published` khi đáp ứng đầy đủ:

## 13.1. Đúng chương trình

* [ ] Có lớp học cụ thể.
* [ ] Có mã chủ đề.
* [ ] Có mạch kiến thức.
* [ ] Có mục tiêu cần đạt.
* [ ] Có kiến thức tiên quyết.
* [ ] Có ánh xạ với sách giáo khoa khi cần.
* [ ] Không chứa nội dung sai phạm vi.

---

## 13.2. Đúng toán học

* [ ] Công thức đã được kiểm tra.
* [ ] Các trường hợp biên đã được kiểm tra.
* [ ] Kết quả số có sai số phù hợp.
* [ ] Hình vẽ đúng với dữ kiện.
* [ ] Nhãn và ký hiệu không mâu thuẫn.
* [ ] Lời giải thích không phụ thuộc hoàn toàn vào LLM.

---

## 13.3. Có giá trị sư phạm

* [ ] Có nội dung để học sinh thao tác.
* [ ] Có câu hỏi dự đoán.
* [ ] Có kết quả để quan sát.
* [ ] Có kết luận kiến thức.
* [ ] Có ít nhất một checkpoint.
* [ ] Không chỉ là hoạt ảnh tự chạy.
* [ ] Không biến thành công cụ giải bài tự động đơn thuần.

---

## 13.4. Dễ sử dụng

* [ ] Có hướng dẫn ngắn.
* [ ] Có nút reset.
* [ ] Có thông báo lỗi dễ hiểu.
* [ ] Không có thao tác ẩn khó phát hiện.
* [ ] Hoạt động trên thiết bị di động.
* [ ] Có thể dùng bằng bàn phím.
* [ ] Màu sắc đủ tương phản.

---

# 14. Checklist 12 mô phỏng ưu tiên P0

> Cập nhật trạng thái seed: `[~]` = có demo/một phần, chưa đạt publish gate §13.

## Lớp 10

* [ ] Miền nghiệm hệ bất phương trình hai ẩn.
* [ ] Hàm số bậc hai và dấu tam thức.
* [ ] Tam giác động và hệ thức lượng.
* [ ] Vectơ, tích vô hướng và góc.

## Lớp 11

* [~] Đường tròn lượng giác liên kết với đồ thị. *(seed `TrigonometrySimulation`)*
* [ ] Giới hạn và tính liên tục.
* [ ] Quan hệ song song và vuông góc trong không gian.
* [ ] Cây xác suất và quy tắc xác suất.

## Lớp 12

* [ ] Đạo hàm, bảng biến thiên và đồ thị.
* [ ] Đường thẳng, mặt phẳng và mặt cầu trong `Oxyz`.
* [~] Tổng Riemann, diện tích và khối tròn xoay. *(seed Area + Solid; CrossSection là bonus)*
* [ ] Xác suất có điều kiện và định lý Bayes.

---

# 15. Thứ tự triển khai đề xuất

## Giai đoạn 1 — Chuẩn hóa dữ liệu chương trình

* [x] Hoàn thiện cây nội dung lớp 10–12. *(catalog tĩnh tối thiểu)*
* [x] Định nghĩa mã chủ đề. *(topicCode nội bộ)*
* [ ] Ánh xạ với các bộ sách. *(cắt Phase 3)*
* [x] Chuyển các mô phỏng hiện tại vào cây nội dung mới.

### Đầu ra

```text
curriculum_nodes (TS)
simulation catalog (TS)
learning_outcomes (trên mỗi SimulationSpec)
```

---

## Giai đoạn 2 — Chuẩn hóa Simulation Engine

* [x] Xây dựng `SimulationSpec`.
* [~] Xây dựng renderer interface. *(template host; adapter interface đầy đủ để Phase 4)*
* [~] Xây dựng hệ thống parameter chung. *(vẫn theo template; shell chung playbar)*
* [x] Xây dựng timeline chung. *(useSimulationPlayer)*
* [~] Xây dựng layer control chung. *(per-template, ví dụ bật/tắt sin/cos)*
* [x] Xây dựng checkpoint chung. *(PedagogyPanel)*
* [x] Xây dựng math verification. *(client `simulation/math/verify.ts`)*

### Đầu ra

Một engine có thể tái sử dụng cho nhiều chủ đề, không phải viết lại toàn bộ giao diện cho từng mô phỏng.

---

## Giai đoạn 3 — Chuyển đổi chức năng hiện tại

* [x] Chuyển mô phỏng đường tròn lượng giác sang cấu trúc mới.
* [x] Chuyển mô phỏng sóng lượng giác sang cấu trúc mới. *(A, B, φ)*
* [x] Chuyển mô phỏng tổng Riemann sang cấu trúc mới. *(left/mid/right)*
* [x] Chuyển mô phỏng diện tích hình phẳng sang cấu trúc mới.
* [x] Chuyển mô phỏng khối tròn xoay sang cấu trúc mới.
* [x] Bổ sung mục tiêu học tập.
* [x] Bổ sung câu hỏi khám phá.
* [x] Bổ sung checkpoint.

---

## Giai đoạn 4 — Phát triển 12 mô phỏng P0

* [ ] Hoàn thành bốn mô phỏng lớp 10.
* [ ] Hoàn thành bốn mô phỏng lớp 11.
* [ ] Hoàn thành bốn mô phỏng lớp 12.
* [ ] Kiểm thử toán học.
* [ ] Kiểm thử giao diện.
* [ ] Kiểm thử sư phạm.

---

## Giai đoạn 5 — Chế độ giáo viên

* [ ] Chế độ toàn màn hình.
* [ ] Chế độ trình chiếu.
* [ ] Khóa tham số.
* [ ] Tạo preset.
* [ ] Chia sẻ bằng liên kết.
* [ ] Tạo danh sách mô phỏng cho một bài học.
* [ ] Xuất hình ảnh.
* [ ] Xuất phiếu học tập.
* [ ] Theo dõi kết quả checkpoint.

---

## Giai đoạn 6 — AI authoring

* [ ] Cho phép giáo viên nhập mô tả hoạt động.
* [ ] AI lựa chọn template.
* [ ] AI sinh tham số.
* [ ] AI sinh câu hỏi.
* [ ] AI sinh hướng dẫn.
* [ ] Kiểm tra đáp án bằng math engine.
* [ ] Cho phép xem trước.
* [ ] Cho phép chỉnh sửa.
* [ ] Chỉ công bố sau khi giáo viên xác nhận.

---

# 16. Tiêu chí hoàn thành phiên bản đầu tiên

> Phân tầng release (xem plan §6, §10):
>
> - **MVP (Phase 0–3 + Wave A):** library shell + engine + seed published + pedagogy.
> - **v1 đầy đủ (hết Phase 4 + 5):** 12 P0 + teacher mode.
> - **v1.x:** persistence, AI authoring (Phase 6–7).

Phiên bản cải tiến **v1 đầy đủ** được xem là hoàn thành khi:

* [ ] Có cấu trúc lớp 10, 11 và 12.
* [ ] Có phân loại theo mạch kiến thức.
* [ ] Có phân loại theo chủ đề.
* [ ] Có ít nhất 12 mô phỏng P0.
* [ ] Mỗi lớp có ít nhất bốn mô phỏng.
* [ ] Có cả mô phỏng Đại số, Giải tích, Hình học và Xác suất.
* [ ] Mỗi mô phỏng có mục tiêu cần đạt.
* [ ] Mỗi mô phỏng có câu hỏi khám phá.
* [ ] Mỗi mô phỏng có checkpoint.
* [ ] Có math verification.
* [ ] Có giao diện responsive.
* [ ] Có chế độ giáo viên.
* [ ] Có chức năng chia sẻ preset.
* [ ] Có kiểm thử toán học.
* [ ] Có kiểm thử với người dùng thực tế.

---

# 17. Định vị chức năng sau cải tiến

Chức năng không nên chỉ được mô tả là:

> Công cụ mô phỏng toán học.

Nên định vị thành:

> **Phòng thí nghiệm Toán học số dành cho chương trình THPT**, hỗ trợ học sinh lớp 10–12 khám phá kiến thức bằng đồ thị tương tác, hình học động, mô hình 3D, thí nghiệm xác suất và các hoạt động toán học được kiểm chứng.

Các thành phần tạo nên khác biệt của hệ thống:

```text
Chương trình Toán THPT
+ Mô phỏng tương tác 2D và 3D
+ AI hiểu yêu cầu tiếng Việt
+ Template được kiểm chứng
+ Math engine xác thực kết quả
+ Hoạt động khám phá
+ Công cụ dành cho giáo viên
```
