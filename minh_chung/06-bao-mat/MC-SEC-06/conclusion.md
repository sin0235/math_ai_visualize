# MC-SEC-06 — TLS production

Chứng chỉ được các trust store xác nhận, OCSP `GOOD`; TLS cũ bị tắt; TLS 1.2/1.3, forward secrecy và secure renegotiation hoạt động. SSLyze không phát hiện Heartbleed, ROBOT hoặc client renegotiation DoS.

Mozilla intermediate profile vẫn `FAILED` vì edge hỗ trợ `secp521r1`, trong khi profile yêu cầu loại curve này.

## Kết luận

**Đạt phần nền tảng nhưng chưa compliant toàn profile.** Giữ `inconclusive` cho mệnh đề compliance; không biến các kiểm tra thành công thành kết luận TLS tuyệt đối.