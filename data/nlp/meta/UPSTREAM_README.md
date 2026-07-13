# Math AI Renderer Corpus v2

Bộ corpus NLP tiếng Việt cho hệ thống Math AI Renderer, tập trung chương trình Toán THCS và THPT từ lớp 6 đến lớp 12.

## Quy mô

- Tổng số bản ghi: **19,431**
- Dữ liệu mẫu ban đầu: **83**
- Bản ghi sinh mới sau khử trùng lặp: **19,348**
- Input text duy nhất: **19,361**
- Canonical duy nhất: **13,815**
- Lỗi schema: **0**

Phân chia dữ liệu:

- Train: **15,731**
- Validation: **1,827**
- Test: **1,873**

Phân bố target:

- algebra: **10,488**
- geometry_solve: **2,882**
- render: **1,695**
- analyzer: **1,291**
- ocr: **3,075**

Phân bố trạng thái:

- accepted: **17,265**
- needs_confirmation: **1,758**
- unsupported: **255**
- abstained: **153**

## Nội dung được mở rộng

Corpus bao phủ các nhóm chính:

- Lớp 6: số tự nhiên, số nguyên, phân số, số thập phân, chia hết, UCLN/BCNN, hình học cơ bản, đối xứng, dữ liệu và xác suất.
- Lớp 7: số hữu tỉ, số thực, biểu thức đại số, tỉ lệ thức, đường thẳng song song, tam giác bằng nhau, hình khối, thống kê và xác suất.
- Lớp 8: đa thức, hằng đẳng thức, phân tích nhân tử, phương trình, hàm số, Pythagore, tứ giác, Thalès, đồng dạng, dữ liệu và xác suất.
- Lớp 9: căn thức, phương trình và hệ phương trình, bất phương trình, hàm bậc hai, lượng giác tam giác vuông, đường tròn, hình khối, thống kê và xác suất.
- Lớp 10: mệnh đề và tập hợp, bất phương trình hai ẩn, hàm số, lượng giác tam giác, vectơ, Oxy, thống kê, tổ hợp, xác suất, nhị thức Newton và conic.
- Lớp 11: lượng giác, dãy số, giới hạn, liên tục, mũ-logarit, đạo hàm, hình học không gian, xác suất, thống kê ghép nhóm và phép biến hình.
- Lớp 12: khảo sát hàm số, cực trị, tiệm cận, nguyên hàm, tích phân, Oxyz, mặt phẳng, đường thẳng, mặt cầu, thống kê ghép nhóm và xác suất có điều kiện.

Ngoài mẫu chuẩn, corpus có biến thể:

- Không dấu, viết thường, viết tắt học sinh và ký hiệu toán Unicode.
- Nhiễu OCR như `0/O`, `1/l`, mất dấu mũ, nhầm căn thức, rơi ký tự và nhầm ngoặc.
- Đề thiếu dữ kiện hoặc mơ hồ cần hỏi lại.
- Input ngoài phạm vi, prompt injection, SQL, code và yêu cầu không liên quan.
- Mẫu render 2D/3D, đồ thị hàm số, biểu đồ thống kê và sơ đồ xác suất.

## Các tệp

- `math_ai_corpus_v2_compatible.jsonl`: bản đầy đủ, giữ đúng schema 5 trường của `v1.jsonl`.
- `math_ai_corpus_v2_rich.jsonl`: thêm metadata về lớp, cấp học, độ khó, nguồn gốc, split và semantic group.
- `train.jsonl`, `validation.jsonl`, `test.jsonl`: các tập đã chia theo semantic group.
- `taxonomy_v2.json`: taxonomy chương trình lớp 6–12 và các chiều NLP.
- `schema_v1_compatible.json`: JSON Schema để kiểm tra dữ liệu.
- `validation_report.json`: báo cáo phân bố và kiểm tra.
- `generate_math_ai_corpus.py`: script tái tạo corpus từ seed.
- `seed_v1.jsonl`: bản sao dữ liệu mẫu do người dùng cung cấp.

## Chống rò rỉ dữ liệu

Các bản diễn đạt khác nhau và bản OCR của cùng canonical được gán chung `semantic_group_id`. Việc chia train/validation/test dựa trên group này thay vì chia ngẫu nhiên từng dòng, nhờ đó giảm nguy cơ cùng một bài xuất hiện ở nhiều tập.

## Chính sách nguồn tham khảo

Cấu trúc môn học và phạm vi chủ đề được đối chiếu từ các chuyên mục lớp 6–12 trên Toán Math. Corpus không sao chép hàng loạt nguyên văn đề, lời giải hoặc PDF từ website. Các mẫu v2 được sinh mới bằng template tham số; 83 mẫu đầu là dữ liệu người dùng cung cấp.

## Giới hạn hiện tại

Đây là corpus mạnh cho intent routing, canonicalization, entity/constraint extraction, robustness và kiểm thử parser. Trường `math_solution_verified` trong bản rich được đặt là `false` vì chưa có bước xác minh toàn bộ đáp án toán học bằng CAS hoặc geometry engine.

Để dùng cho fine-tuning sinh lời giải hoặc scene hoàn chỉnh, cần bổ sung một gold set được kiểm duyệt gồm:

- đáp án chính xác;
- biểu thức CAS;
- scene graph đầy đủ;
- quan hệ hình học;
- lời giải từng bước;
- kết quả validator;
- tiêu chí chất lượng render.
