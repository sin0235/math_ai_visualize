# MC-API-01 — Liveness, readiness và OpenAPI

## Quan sát

- `GET /api/health`: HTTP 200, body `{"status":"ok"}`.
- `GET /api/health/ready`: HTTP 200, body xác nhận `status=ready`, `database.ok=true`, `database.backend=postgres`.
- Hai response có `X-Request-Id`.
- `GET /openapi.json` không trả JSON. Nginx áp dụng frontend fallback và trả `index.html`.

## Kết luận

**Đạt** đối với liveness và readiness production.

**Không đủ căn cứ** đối với OpenAPI qua URL public. Tệp `openapi.html` được giữ nguyên như dữ liệu phản chứng: nội dung thực tế là HTML. Không được dùng tệp này để tuyên bố tài liệu OpenAPI đang được public qua Nginx.
