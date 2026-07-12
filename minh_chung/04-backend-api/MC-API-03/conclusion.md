# MC-API-03 — Validation và request ID

## Ca âm tính

`POST /api/analyzer/analyze` với body `{}` và Origin production hợp lệ trả:

- HTTP 422;
- mã `ANALYZER_INPUT_INVALID`;
- stage `request`;
- `retryable=false`;
- `correlation_id=bdc7cdfed3474176aef6a36e4ba6b345`.

Header `X-Request-Id` có cùng giá trị với `correlation_id`. Body không có stack trace, secret hoặc đường dẫn nội bộ.

## Ca dương tính đọc-only

`GET /api/analyze/capabilities` trả HTTP 200 và registry capability có cấu trúc.

## Kết luận

**Đạt** đối với chuẩn hóa lỗi validation và liên kết request ID trên production tại thời điểm kiểm tra.
