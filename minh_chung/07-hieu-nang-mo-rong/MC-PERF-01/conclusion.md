# MC-PERF-01 — Đồng thời và atomicity

## Quan sát

Baseline Redis thất bại: 40 lần tranh chấp, limit 4 nhưng chỉ 1 slot được nhận. Cơ chế `ZCARD`/`ZADD` không nguyên tử làm các request tự loại nhau.

Sau khi chuyển acquire sang một Lua script nguyên tử:

- `accepted=4/40`;
- `zcard_before_release=4`;
- `zcard_after_release=0`;
- 6/6 test concurrency và conflict đạt.

## Kết luận

**Đạt cho correctness của capacity gate local sau sửa.** Chưa đủ căn cứ cho throughput, latency hoặc số user production; không dùng kết quả này như load benchmark production.