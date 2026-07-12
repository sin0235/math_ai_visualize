# MC-SEC-04 — Dependency audit

`npm audit` kiểm tra 193 dependency và `pip-audit` kiểm tra 60 dependency Python. Cả hai không tìm thấy CVE đã biết tại thời điểm `2026-07-12`.

## Kết luận

**Đạt trong phạm vi advisory dependency.** Kết quả không thay thế SAST, DAST hoặc review data flow; advisory database có thể thay đổi sau thời điểm thu.