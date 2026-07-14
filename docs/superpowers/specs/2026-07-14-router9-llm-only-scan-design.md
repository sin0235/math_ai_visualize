# Thiết kế quét model LLM của 9router

## Mục tiêu

Inventory model AI của 9router chỉ chứa các model từ catalog LLM `/models`. Không đưa TTS, STT, image generation, embedding, image-to-text hoặc web service vào allowlist dùng cho các tác vụ LLM.

## Phạm vi

- `Router9Adapter` chỉ gọi `/models` và tiếp tục đọc toàn bộ các trang nếu response có cursor.
- Chấp nhận mọi model hợp lệ trong `data[]` của `/models`; không lọc theo prefix, vendor, capability, giá hoặc tên model.
- Giữ nguyên API response, schema, registry persistence và UI hiện tại.
- Khi quét lại, cơ chế registry hiện có vô hiệu hóa các model phi LLM cũ không còn xuất hiện trong kết quả.

## Luồng dữ liệu

1. Admin yêu cầu quét model 9router.
2. Backend lấy cấu hình kết nối hiệu lực và gọi `{base_url}/models`.
3. Adapter đọc từng trang, parse toàn bộ model hợp lệ và gắn `service_kind=llm` vào metadata.
4. Route loại ID rỗng hoặc trùng lặp rồi đồng bộ kết quả vào registry.
5. UI nhận inventory chỉ gồm LLM.

## Xử lý lỗi

- Lỗi của `/models` tiếp tục làm toàn bộ lần quét thất bại để tránh ghi một inventory rỗng hoặc thiếu model không có chủ đích.
- Cursor lặp lại tiếp tục được chặn để tránh vòng lặp vô hạn.
- Không gọi các catalog phi LLM nên lỗi của chúng không ảnh hưởng lần quét LLM.

## Kiểm thử

- Adapter chỉ gọi `/models`, không gọi các endpoint theo loại dịch vụ.
- Kết quả giữ đủ model từ nhiều trang của `/models` và loại ID trùng lặp ở boundary hiện tại.
- Regression test xác nhận model có ID bất kỳ từ `/models` vẫn được giữ, kể cả model không có capability metadata.
- Regression test xác nhận `edge-tts/...` từ catalog TTS không xuất hiện vì endpoint TTS không được gọi.
- Chạy test adapter, test registry liên quan và suite backend phù hợp với phạm vi thay đổi.

## Không thuộc phạm vi

- Tạo màn hình quản trị riêng cho TTS, STT, image hoặc embedding.
- Suy đoán một model có phải LLM dựa trên ID.
- Thay đổi cách 9router công bố catalog `/models`.
