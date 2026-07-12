# MC-API-04 — OpenAPI contract fuzzing

Schemathesis chạy 2.265 test case trên 25 operation, phát hiện 31 failure duy nhất:

- 9 response không khớp schema;
- 1 request vi phạm schema vẫn được API chấp nhận;
- 21 HTTP status không được OpenAPI khai báo;
- 11 operation chỉ quan sát được 401/403 vì thiếu credential test.

## Kết luận

**Không đạt.** Runtime có validation và auth hoạt động, nhưng OpenAPI không mô tả đúng error envelope/status và có ít nhất một đường nhận input sai schema. HAR, JUnit, NDJSON và lệnh tái hiện được giữ nguyên.