# PHẦN NGƯỜI DÙNG CẦN THỰC HIỆN

Tệp này chỉ liệt kê phần không thể tự thu do cần access token DigitalOcean, tài khoản ứng dụng hoặc thao tác trực quan. Dùng tài khoản test; không dùng dữ liệu người dùng thật.

## 1. Xác thực DigitalOcean và thu dữ liệu production

### 1.1. Đăng nhập

```bash
doctl auth init
```

Nhập token có quyền đọc App Platform và Managed Database trực tiếp trong terminal. Không gửi token qua hội thoại, không lưu token vào `minh_chung/`, shell history hoặc ảnh chụp.

Kiểm tra phiên:

```bash
doctl account get
```

Chỉ tiếp tục khi lệnh trả thông tin tài khoản hợp lệ. Không đưa output `account get` vào hồ sơ vì không cần cho mệnh đề kỹ thuật.

### 1.2. Chạy phép xác minh tổng hợp

```bash
cd /home/sin235/Projects/math_ai_visualize
mkdir -p minh_chung/09-van-hanh-cap-nhat/MC-OPS-03/01-raw
set -o pipefail
./deploy/verify-production.sh 2>&1 \
  | tee minh_chung/09-van-hanh-cap-nhat/MC-OPS-03/01-raw/verify-production.log
printf 'exit_code=%s\n' "${PIPESTATUS[0]}" \
  > minh_chung/09-van-hanh-cap-nhat/MC-OPS-03/01-raw/exit-code.txt
```

Tiêu chí đạt: log kết thúc bằng `OK`, exit code bằng `0`, deployment `ACTIVE`, branch `product`, backup không quá ngưỡng script, worker có dấu vết `RUNNING`, health/readiness đạt, ruleset active.

Nếu script lỗi, giữ nguyên log. Không chạy lại rồi xóa lần lỗi.

### 1.3. Thu dữ liệu DigitalOcean đã tối giản

Đặt ID dùng trong dự án:

```bash
export APP_ID='f94827d0-9d28-4047-9a06-68129dc99199'
export DB_CLUSTER_ID='d1e9bd7a-b85f-4f29-ad5c-234a58740585'
```

Thu deployment hiện hành, lịch sử deployment và cấu hình app không chứa giá trị secret:

```bash
doctl apps get "$APP_ID" --output json \
  | jq '(.[]? // .) | {
      id,
      active_deployment: (.active_deployment | {id, phase, created_at, updated_at}),
      spec: {
        region: .spec.region,
        services: [.spec.services[] | {
          name,
          github: (.github | {repo, branch, deploy_on_push}),
          instance_count,
          instance_size_slug,
          health_check,
          envs: [.envs[]? | {key, type}]
        }]
      }
    }' \
  > minh_chung/09-van-hanh-cap-nhat/MC-OPS-03/01-raw/app-sanitized.json

doctl apps list-deployments "$APP_ID" --output json \
  | jq '[.[] | {id, phase, cause, created_at, updated_at}]' \
  > minh_chung/09-van-hanh-cap-nhat/MC-OPS-03/01-raw/deployments.json
```

Thu trạng thái PostgreSQL và danh sách backup:

```bash
doctl databases get "$DB_CLUSTER_ID" --output json \
  | jq '[.[] | {id, name, engine, version, status, region, num_nodes, size, created_at}]' \
  > minh_chung/05-postgresql/MC-DB-01/01-raw/cluster-sanitized.json

doctl databases backups "$DB_CLUSTER_ID" --output json \
  | jq '[.[] | {created_at, size_gigabytes}]' \
  > minh_chung/05-postgresql/MC-DB-01/01-raw/backups-sanitized.json
```

Không lưu output đầy đủ nếu có connection URI, host, user, password hoặc private network metadata. Kiểm tra bốn JSON bằng mắt trước khi bàn giao.

### 1.4. Cập nhật kết luận sau khi thu

Trong `MC-OPS-03/metadata.yaml`, cập nhật:

- `commit_sha`: SHA hoặc artifact tương ứng deployment nếu output cung cấp;
- `actual`: deployment phase, branch, thời điểm backup gần nhất, worker state;
- `result`: `passed`, `failed` hoặc `inconclusive`;
- `raw_files`: các file vừa tạo.

Không đổi thành `passed` nếu chỉ health/readiness đạt nhưng thiếu deployment hoặc backup.

## 2. Thu minh chứng UX bằng trình duyệt

Tạo thư mục:

```bash
cd /home/sin235/Projects/math_ai_visualize
mkdir -p minh_chung/02-trai-nghiem-nguoi-dung/{MC-UX-01,MC-UX-02,MC-UX-03,MC-UX-04}/01-raw
```

Quay video ở độ phân giải tối thiểu 1440×900. Hiện đồng hồ UTC đầu video. Chỉ dùng tài khoản test và đề không chứa dữ liệu cá nhân. Mỗi video phải thấy URL/môi trường, đề đầu vào, thao tác, trạng thái trung gian và kết quả cuối.

### MC-UX-01 — Nhập đề và trạng thái xử lý

1. Mở production trong cửa sổ sạch, đăng nhập tài khoản test.
2. Nhập một đề hình học có đủ dữ kiện nhận diện.
3. Bắt đầu xử lý.
4. Quay các trạng thái loading/progress đã xuất hiện; không cắt đoạn chờ.
5. Quay kết quả scene và thông báo hoàn tất hoặc lỗi.
6. Lưu video `MC-UX-01-input-processing-production-<UTC>.webm`.

Đạt khi đầu vào, trạng thái chuyển tiếp và kết quả liên kết được trong một phiên quay liên tục.

### MC-UX-02 — Xác nhận kết quả và chỉnh scene

1. Chọn ca tạo trạng thái yêu cầu xác nhận nếu hệ thống trả `requires_user_confirmation`.
2. Quay thông báo yêu cầu xác nhận và scene trước xác nhận.
3. Thực hiện xác nhận trên UI; quay trạng thái sau xác nhận.
4. Chỉnh một thuộc tính scene đang được UI hỗ trợ.
5. Quay kết quả sau chỉnh và bảo đảm thay đổi nhìn thấy được.
6. Lưu video `MC-UX-02-confirm-edit-production-<UTC>.webm`.

Đạt khi video chứng minh cùng scene đi qua trước xác nhận, sau xác nhận và sau chỉnh sửa. Nếu không tạo được `requires_user_confirmation`, ghi `inconclusive`; không dùng scene khác để ghép chuỗi.

### MC-UX-03 — Lưu và mở lịch sử

1. Hoàn thành một bài bằng tài khoản test.
2. Ghi lại dấu hiệu nhận diện không nhạy cảm của bài, ví dụ vài từ đầu đề và timestamp.
3. Điều hướng khỏi màn hình hiện tại hoặc tải lại trang.
4. Mở lịch sử và chọn đúng bản ghi.
5. Quay đề, scene và trạng thái được khôi phục.
6. Lưu video `MC-UX-03-history-production-<UTC>.webm`.

Đạt khi bản ghi mở lại khớp đầu vào và kết quả đã lưu; ảnh danh sách lịch sử riêng lẻ không đủ.

### MC-UX-04 — Mô phỏng từng bước và xuất kết quả

1. Mở một mô phỏng có nhiều bước.
2. Quay trạng thái ban đầu, chuyển ít nhất hai bước, quay thay đổi nội dung/scene ở từng bước.
3. Từ cùng kết quả đã kiểm chứng, mở menu export.
4. Xuất từng định dạng đang hiện thực sự trên UI; không ghi thêm định dạng không xuất hiện.
5. Mở từng tệp bằng ứng dụng phù hợp và quay nội dung mở thành công.
6. Lưu video `MC-UX-04-simulation-export-production-<UTC>.webm`; lưu file xuất trong cùng `01-raw/`.

Đạt khi trình tự bước quan sát được và các file xuất cùng tham chiếu một kết quả nguồn.

## 3. Thu minh chứng quyền truy cập và giám sát

Dùng hai tài khoản test: user thường và admin.

### 3.1. Bảo mật runtime

- Gọi chức năng lưu BYOK bằng giá trị test, sau đó đọc lại settings.
- Lưu request/response đã che token; chứng minh response không trả plaintext.
- Truy cập health detail bằng user thường, lưu response bị từ chối.
- Truy cập cùng endpoint bằng admin, lưu response thành công đã che provider/internal metadata.
- Quay UI quản lý phiên: liệt kê phiên và thu hồi một phiên test nếu chức năng hiển thị.

Không đưa API key test dạng đầy đủ vào file, terminal log hoặc video.

### 3.2. Monitoring runtime

- Mở dashboard admin.
- Chụp cùng một khoảng UTC cho metric tổng hợp, cảnh báo và error fingerprint nếu UI có.
- Tạo một lỗi vô hại trên staging hoặc bằng ca validation production đã có; đối chiếu request ID với bản ghi quan sát được.
- Không tạo tải, thay đổi capacity hoặc cố tình gây lỗi production.

Nếu không có quyền admin, đánh dấu `inconclusive` và ghi rõ tài khoản thiếu quyền nào.

## 4. Kiểm tra Docker local

Docker chưa được cài trên máy. GitHub Actions đã xác nhận job `Docker build (smoke)` thành công cho commit product; local workspace chưa được Docker kiểm tra.

Nếu bắt buộc chứng minh workspace local:

```bash
cd /home/sin235/Projects/math_ai_visualize
docker version
set -o pipefail
docker build -t math-ai-visualize:evidence . 2>&1 \
  | tee minh_chung/09-van-hanh-cap-nhat/MC-OPS-04-docker-build.log
printf 'exit_code=%s\n' "${PIPESTATUS[0]}" \
  > minh_chung/09-van-hanh-cap-nhat/MC-OPS-04-docker-exit-code.txt
```

Chỉ thực hiện sau khi cài Docker Engine. Không cần cài Docker nếu CI product đủ cho phạm vi nộp.

## 5. Chốt lại hồ sơ sau khi bổ sung

Sau mọi bổ sung:

1. Cập nhật `metadata.yaml`, `conclusion.md`, `BANG_CHI_MUC.csv`, `BANG_ANH_XA_MENH_DE.csv`.
2. Quét secret và dữ liệu cá nhân.
3. Xóa `SHA256SUMS.txt` cũ rồi tạo lại checksum.
4. Chạy `sha256sum --check minh_chung/00-chi-muc/SHA256SUMS.txt`.
5. Không sửa vật chứng sau khi checksum đã chốt; nếu sửa, tạo lại toàn bộ manifest.
