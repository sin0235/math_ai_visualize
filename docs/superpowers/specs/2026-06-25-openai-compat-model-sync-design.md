# Thiết kế sửa đồng bộ model OpenAI-compatible

## Bối cảnh

Khi quét model cho provider OpenAI-compatible, ví dụ `https://kiraai.vn/api/v1`, model không còn xuất hiện trong `/v1/models` vẫn có thể hiện ở giao diện và còn trạng thái cho phép dùng trong database. Nguyên nhân chính nằm ở luồng đồng bộ registry: model cũ được giữ lại để bảo toàn cấu hình, nhưng chưa bị hạ trạng thái đúng khi scan mới không còn trả về model đó.

## Mục tiêu

- Xem kết quả scan `/v1/models` là nguồn sự thật cho các model có `source = scan` của provider đó.
- Model từng scan nhưng không còn trong response mới phải bị đánh dấu stale: `enabled = false`, `allowed = false`.
- Không xóa record khỏi database để giữ audit và tránh mất cấu hình lịch sử.
- Không cho model stale xuất hiện như lựa chọn mới trên UI.
- Nếu model stale đang được profile/task/fallback dùng, UI vẫn có thể hiển thị để admin biết cấu hình cũ cần đổi, kèm trạng thái không còn khả dụng.

## Ngoài phạm vi

- Không thay đổi contract `/v1/models` của provider ngoài.
- Không xóa model khỏi database.
- Không tự xóa profile/task/fallback đang tham chiếu model stale.
- Không thêm dependency mới.

## Thiết kế backend

### Đồng bộ scan

Trong luồng `upsert_scanned_models(...)`:

1. Lấy allowlist hiện tại của provider.
2. Xác định danh sách model id vừa scan được.
3. Với scanned model cũ không nằm trong danh sách mới:
   - set `enabled = false`
   - set `allowed = false`
4. Với model còn trong danh sách mới:
   - upsert metadata và `last_seen_at`
   - giữ `allowed = true` chỉ nếu model đã nằm trong allowlist trước đó
   - model mới mặc định không tự allowed
5. Sau khi stale model bị bỏ allowed, đảm bảo default model của provider không còn trỏ tới model disabled hoặc không allowed.

### Default model

Nếu default hiện tại không còn enabled và allowed sau scan:

- Chọn allowed model còn khả dụng đầu tiên nếu có.
- Nếu không có allowed model còn khả dụng, clear default model.

Cách này giữ tương thích với logic hiện có: admin vẫn kiểm soát allowlist, scan không tự bật model mới.

## Thiết kế UI

Provider form đang lọc `allowed_model_ids` và `model` theo danh sách scan mới sau khi bấm quét. Giữ behavior này.

Cần đảm bảo các select dùng registry không hiển thị stale model như lựa chọn mới. Với model đang được profile/task/fallback chọn sẵn nhưng stale, UI có thể giữ hiển thị giá trị đó để admin nhận biết và thay đổi, nhưng phải phân biệt với model còn khả dụng.

## Data flow

1. Admin bấm quét provider OpenAI-compatible.
2. Backend gọi endpoint OpenAI-compatible `/models`.
3. Backend persist scan vào registry.
4. Model scan cũ không còn xuất hiện bị đánh dấu disabled và không allowed.
5. Default provider được sửa nếu đang trỏ tới model stale.
6. Frontend nhận scan result, lọc local allowlist/default theo response mới.
7. Khi reload settings, `/api/settings/defaults` không còn trả model stale như model allowed/enabled cho lựa chọn mới.

## Error handling

- Nếu provider scan lỗi, không thay đổi registry hiện tại.
- Chỉ đánh dấu stale sau khi scan thành công và parse được danh sách model hợp lệ.
- Không xóa dữ liệu nên thao tác có thể hoàn tác bằng scan lại hoặc admin bật model hợp lệ.

## Kiểm thử

### Backend regression

Tạo hoặc cập nhật test cho registry scan:

1. Seed provider OpenAI-compatible với model `gpt-old` từ scan, `allowed = true`, `enabled = true`, default là `gpt-old`.
2. Chạy sync scan mới chỉ có `kira-new`.
3. Kiểm tra:
   - `gpt-old.enabled = false`
   - `gpt-old.allowed = false`
   - provider default không còn là `gpt-old`
   - `kira-new.enabled = true`
   - `kira-new.allowed = false` nếu trước đó chưa nằm trong allowlist

### Frontend nếu test hạ tầng có sẵn

- Model stale không nằm trong option khả dụng mới.
- Nếu stale model đang được chọn trong profile/fallback, UI vẫn thể hiện cấu hình cũ để admin đổi, không silently drop.

## Rủi ro còn lại

Nếu một task đang trỏ tới model stale và không có fallback allowed khác, runtime có thể cần admin chọn model mới trước khi dùng ổn định. Thiết kế không tự đổi profile/task để tránh thay đổi nghiệp vụ ngầm.