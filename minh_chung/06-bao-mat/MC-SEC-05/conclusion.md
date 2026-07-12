# MC-SEC-05 — SAST Python

## Kết quả

- Bandit: 46.069 LOC, 0 high, 37 medium, 60 low.
- Semgrep: 200 rules, 202 target, 4 finding, không lỗi scanner.
- Hai finding log chỉ chứa `email_hash`; finding XML nằm ở hàm tạo XML bằng escape, không parse XML; hai nhóm này là false positive theo data flow.
- `safe_eval` chặn attribute/import/lambda/comprehension bằng AST allowlist và chạy với empty builtins. Semgrep vẫn đúng khi yêu cầu review; giới hạn resource exhaustion chưa được chứng minh đầy đủ.

## Kết luận

**Không đạt tiêu chí SAST sạch.** Không có finding high, nhưng 37 medium Bandit chưa được phân loại hết và `eval` còn phạm vi review. Giữ `failed` thay vì hạ severity hoặc xóa output.