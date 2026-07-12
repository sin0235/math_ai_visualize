# QUY TRÌNH THU THẬP VÀ TỔ CHỨC HỒ SƠ MINH CHỨNG

## 1. Mục đích

Tài liệu quy định phương pháp thu thập, bảo toàn, đánh giá và bàn giao minh chứng cho các năng lực được trình bày trong `danh_gia_trien_khai.md`.

Mục tiêu của hồ sơ không phải tạo số lượng lớn ảnh chụp hoặc log, mà hình thành chuỗi chứng minh có thể kiểm tra độc lập:

1. Mỗi nhận định trong báo cáo được ánh xạ đến một hoặc nhiều mã minh chứng.
2. Mỗi minh chứng gắn với phiên bản mã nguồn, môi trường, dữ liệu đầu vào và thời điểm xác định.
3. Dữ liệu gốc được bảo toàn; bản che thông tin hoặc bản trình bày được lưu riêng.
4. Quy trình thực hiện đủ rõ để người khác có thể tái lập.
5. Kết luận chỉ nằm trong phạm vi mà dữ liệu quan sát được cho phép.

Hồ sơ hoàn chỉnh được đính kèm dưới dạng thư mục phụ lục. Bảng chỉ mục tại thư mục gốc liên kết tiêu chí đánh giá, mã minh chứng, tệp dữ liệu và kết luận tương ứng.

---

## 2. Nguyên tắc xác lập minh chứng

### 2.1. Tính khách quan

Minh chứng phải được tạo từ hành vi quan sát được của hệ thống, kết quả lệnh, phản hồi giao thức, dữ liệu truy vấn hoặc kết quả kiểm thử. Nhận xét chủ quan, mô tả mang tính giả định và ảnh chỉ thể hiện giao diện tĩnh không đủ để chứng minh một luồng nghiệp vụ đã hoạt động.

Cùng một mệnh đề nên được kiểm tra bằng ít nhất hai nguồn độc lập khi điều kiện cho phép. Ví dụ, năng lực render bất đồng bộ được xác nhận bằng phản hồi API và chuyển trạng thái trong PostgreSQL; năng lực bảo vệ endpoint được xác nhận bằng request bị từ chối và kiểm thử tự động tương ứng.

### 2.2. Tính kỹ thuật

Mỗi minh chứng phải ghi rõ:

- Mệnh đề cần chứng minh.
- Thành phần hệ thống chịu trách nhiệm.
- Dữ liệu đầu vào.
- Trạng thái ban đầu.
- Thao tác hoặc lệnh thực hiện.
- Kết quả mong đợi.
- Kết quả thực tế.
- Điều kiện kết luận đạt hoặc không đạt.
- Tệp dữ liệu gốc liên quan.

Ảnh giao diện cần thể hiện đủ ngữ cảnh để nhận diện chức năng và kết quả. Minh chứng API cần có HTTP status, header liên quan và body. Minh chứng kiểm thử cần có lệnh chạy, exit code, tổng kết và JUnit XML khi công cụ hỗ trợ. Minh chứng cơ sở dữ liệu cần có câu truy vấn và kết quả, nhưng không chứa chuỗi kết nối hoặc định danh hạ tầng nhạy cảm.

### 2.3. Tính khoa học

Quy trình thu thập tuân theo nguyên tắc thay đổi một biến tại một thời điểm. Khi kiểm tra một trạng thái lỗi, các điều kiện khác phải được giữ ổn định để có thể quy nguyên nhân cho biến đang xét.

Mỗi phép kiểm tra chức năng cần có:

- Ca dương tính: đầu vào hợp lệ tạo kết quả mong đợi.
- Ca âm tính khi có ý nghĩa: đầu vào hoặc quyền truy cập không hợp lệ bị từ chối đúng cách.
- Dữ liệu chuẩn đối chiếu đối với kết quả toán học.
- Phạm vi kết luận phù hợp với kích thước mẫu.

Một lần chạy thành công chứng minh chức năng hoạt động trong điều kiện đã ghi nhận, nhưng không đủ để kết luận độ ổn định hoặc hiệu năng tổng quát. Nhận định về tỷ lệ, độ trễ hoặc tải chỉ được sử dụng khi có tập mẫu, khoảng thời gian đo và cách tổng hợp xác định.

### 2.4. Tính logic

Chuỗi chứng minh của mỗi mệnh đề gồm bốn mắt xích:

| Mắt xích | Câu hỏi cần trả lời |
| --- | --- |
| Điều kiện | Hệ thống đang ở phiên bản, môi trường và trạng thái nào? |
| Tác động | Đầu vào hoặc thao tác nào được áp dụng? |
| Quan sát | Dữ liệu nào được hệ thống tạo ra sau tác động? |
| Kết luận | Quan sát có thỏa tiêu chí đã xác lập hay không? |

Nếu thiếu một mắt xích, minh chứng chỉ được xem là dữ liệu tham khảo. Ví dụ, ảnh một mô hình 3D không kèm đề đầu vào không chứng minh mô hình được sinh từ đề; log `completed` không kèm job ID không chứng minh đó là tác vụ đang được đối chiếu.

### 2.5. Tính toàn vẹn và khả năng truy vết

Dữ liệu gốc được lưu ngay sau khi thu thập và không chỉnh sửa. Nếu cần che token, email hoặc định danh nội bộ, phải tạo một bản sao đã xử lý trong thư mục riêng. Checksum SHA-256 được lập cho toàn bộ tệp bàn giao để phát hiện thay đổi sau thời điểm chốt hồ sơ.

Mỗi bộ minh chứng gắn với commit SHA. Nếu workspace có thay đổi chưa commit, trạng thái đó phải được lưu cùng bản diff; không được ghi nhận một commit sạch như thể nó đã bao gồm các thay đổi đang được kiểm tra.

---

## 3. Phân cấp giá trị chứng cứ

Khi các nguồn có nội dung khác nhau, ưu tiên áp dụng theo thứ tự sau:

| Cấp | Nguồn | Giá trị chứng minh |
| --- | --- | --- |
| E1 | Hành vi runtime quan sát trực tiếp | Xác nhận hệ thống đang thực hiện hành vi cụ thể trong môi trường kiểm tra |
| E2 | Lưu lượng mạng và phản hồi giao thức | Xác nhận request, response, trạng thái, header và trình tự trao đổi |
| E3 | Dữ liệu PostgreSQL, log worker và telemetry | Xác nhận thay đổi trạng thái, tính bền vững và dấu vết vận hành |
| E4 | Kiểm thử tự động và CI | Xác nhận quy tắc có thể tái lập trên phiên bản mã nguồn xác định |
| E5 | Cấu hình triển khai và mã nguồn | Giải thích cơ chế tạo ra hành vi đã quan sát |

Mã nguồn và cấu hình không được sử dụng như bằng chứng duy nhất cho trạng thái production. Ngược lại, một ảnh runtime không đủ giải thích cơ chế bảo đảm tính đúng đắn nếu thiếu phản hồi, dữ liệu hoặc kiểm thử liên quan.

Khi hai nguồn xung đột, hành vi runtime và dữ liệu đang được phục vụ được ưu tiên. Cần kiểm tra tiếp commit triển khai, artifact, cache và cấu hình để giải thích nguyên nhân; không lựa chọn nguồn thuận lợi hơn rồi loại bỏ nguồn còn lại.

---

## 4. Cấu trúc phụ lục bàn giao

### 4.1. Cây thư mục

```text
minh_chung/
├── 00-chi-muc/
│   ├── THONG_TIN_PHIEN_BAN.txt
│   ├── BANG_CHI_MUC.csv
│   ├── BANG_ANH_XA_MENH_DE.csv
│   └── SHA256SUMS.txt
├── 01-giao-dien/
├── 02-trai-nghiem-nguoi-dung/
├── 03-logic-ung-dung/
├── 04-backend-api/
├── 05-postgresql/
├── 06-bao-mat/
├── 07-hieu-nang-mo-rong/
├── 08-phan-tich-theo-doi/
├── 09-van-hanh-cap-nhat/
└── 10-chat-luong-san-pham/
```

Trong mỗi nhóm, từng mã minh chứng có cấu trúc độc lập:

```text
MC-UX-03/
├── metadata.yaml
├── 01-raw/
│   ├── request.json
│   ├── response.json
│   └── screen.webm
├── 02-redacted/
│   └── screen-redacted.webm
└── conclusion.md
```

`01-raw` lưu dữ liệu nguyên bản và được giữ ngoài gói công khai nếu chứa thông tin nhạy cảm. `02-redacted` lưu bản đã che thông tin để bàn giao. `conclusion.md` ghi nhận tiêu chí, quan sát và kết luận; tệp này không thay thế dữ liệu gốc.

### 4.2. Quy tắc đặt tên

Tên tệp sử dụng mẫu:

```text
<ma-minh-chung>-<noi-dung>-<moi-truong>-<YYYYMMDD-HHMMSSZ>.<phan-mo-rong>
```

Ví dụ:

```text
MC-UX-03-trust-state-staging-20260712-143000Z.webm
MC-API-02-job-response-staging-20260712-145500Z.json
MC-DB-02-health-detail-production-20260712-151000Z.json
```

Thời gian dùng UTC. Tên file không chứa email, user ID, token, hostname nội bộ hoặc chuỗi kết nối.

### 4.3. Metadata bắt buộc

Mỗi `metadata.yaml` sử dụng cấu trúc:

```yaml
evidence_id: MC-UX-03
claim: Kết quả dựng hình công bố trạng thái tin cậy và yêu cầu xác nhận khi cần.
commit_sha: <git-commit-sha>
workspace_clean: true
environment: staging
base_url: <redacted>
collected_at_utc: 2026-07-12T14:30:00Z
collector: <name-or-id>
preconditions:
  - Tài khoản test đã đăng nhập.
  - Dịch vụ ở trạng thái ready.
input:
  problem_text: Vẽ tam giác ABC.
procedure_version: 1
expected:
  - Response chứa trạng thái chất lượng.
  - Giao diện hiển thị nhãn tương ứng.
actual:
  - <ghi sau khi thực hiện>
result: pending
raw_files:
  - 01-raw/request.json
  - 01-raw/response.json
  - 01-raw/screen.webm
redactions:
  - <mô tả trường đã che hoặc none>
```

Không điền `result: passed` trước khi đối chiếu dữ liệu thực tế. Nếu kết quả khác mong đợi, giữ nguyên dữ liệu và ghi `failed` hoặc `inconclusive`; không thực hiện lại rồi chỉ lưu lần thành công.

---

## 5. Chuẩn bị và chốt phiên bản kiểm chứng

### 5.1. Tạo cấu trúc thư mục

```bash
cd /home/sin235/Projects/math_ai_visualize
mkdir -p minh_chung/00-chi-muc \
  minh_chung/{01-giao-dien,02-trai-nghiem-nguoi-dung,03-logic-ung-dung,04-backend-api,05-postgresql,06-bao-mat,07-hieu-nang-mo-rong,08-phan-tich-theo-doi,09-van-hanh-cap-nhat,10-chat-luong-san-pham}
```

### 5.2. Ghi thông tin phiên bản

```bash
cd /home/sin235/Projects/math_ai_visualize
{
  printf 'collected_at_utc='
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  printf 'commit_sha='
  git rev-parse HEAD
  printf 'branch='
  git branch --show-current
  printf '%s\n' 'git_status_begin'
  git status --short
  printf '%s\n' 'git_status_end'
  python --version
  node --version
  npm --version
} > minh_chung/00-chi-muc/THONG_TIN_PHIEN_BAN.txt

git diff --binary > minh_chung/00-chi-muc/WORKSPACE.diff
```

Nếu `git status --short` có dữ liệu, `workspace_clean` phải là `false` và `WORKSPACE.diff` trở thành thành phần bắt buộc của hồ sơ.

### 5.3. Xác lập môi trường thực hiện

Đặt URL của môi trường đang được kiểm tra vào biến dùng chung:

```bash
export BASE_URL='https://<staging-or-production-domain>'
```

Đối với phép kiểm tra local, backend phải kết nối đến một PostgreSQL dành riêng cho kiểm chứng:

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
export DATABASE_BACKEND=postgres
export DATABASE_URL='postgresql://<user>:<password>@<host>:5432/<database>'
export ENVIRONMENT=development
uvicorn app.main:app --reload
```

Frontend được khởi chạy trong tiến trình riêng:

```bash
cd /home/sin235/Projects/math_ai_visualize/frontend
npm ci
npm run dev
```

Metadata của từng minh chứng phải ghi chính xác `local`, `staging` hoặc `production`. Không gộp dữ liệu từ nhiều môi trường vào cùng một mã minh chứng nếu không ghi rõ vai trò của từng nguồn.

### 5.4. Kiểm tra nền

Trước mỗi nhóm minh chứng runtime, lưu trạng thái nền:

```bash
curl -fsS "$BASE_URL/api/health" \
  -o minh_chung/00-chi-muc/health-baseline.json
curl -fsS "$BASE_URL/api/health/ready" \
  -o minh_chung/00-chi-muc/readiness-baseline.json
```

Baseline phải được thu trước tác động kiểm tra. Nếu readiness không đạt, dừng thu thập minh chứng chức năng vì kết quả có thể bị nhiễu bởi trạng thái môi trường.

### 5.5. Bảo vệ dữ liệu

Phải loại bỏ khỏi gói bàn giao công khai:

- Giá trị cookie và session token.
- API key, OAuth secret và webhook URL.
- `DATABASE_URL`, hostname nội bộ và thông tin đăng nhập PostgreSQL.
- Email, user ID, nội dung hội thoại và tệp của người dùng thật.
- App ID, cluster ID và định danh repository riêng tư khi không cần thiết cho kết luận.

Không chỉnh sửa HTTP status, timestamp, job ID, request ID, tên bài kiểm thử hoặc nội dung kết quả. Việc che dữ liệu phải được thực hiện trên bản sao; tệp gốc giữ nguyên trong phạm vi lưu trữ có kiểm soát.

Các thao tác tạo lỗi, kiểm tra Origin, rate limit, thu hồi phiên, thay đổi capacity hoặc gây tải chỉ thực hiện bằng tài khoản test trên local hoặc staging. Production chỉ dùng phép kiểm tra đọc, health check, lịch sử deployment, dashboard và dữ liệu vận hành đã được cấp quyền.

---

## 6. Quy trình chuẩn cho một mã minh chứng

Mỗi mã minh chứng được thu thập theo trình tự sau:

1. **Xác lập mệnh đề:** Viết một câu có thể kiểm tra và không chứa nhiều năng lực độc lập.
2. **Chốt điều kiện:** Ghi commit, môi trường, thời gian, tài khoản test, baseline và dữ liệu đầu vào.
3. **Thực hiện tác động:** Chạy đúng thao tác hoặc lệnh đã định; mỗi lần chỉ thay đổi biến đang kiểm tra.
4. **Thu dữ liệu:** Lưu dữ liệu gốc từ giao diện, mạng, PostgreSQL, worker, kiểm thử hoặc hạ tầng.
5. **Đối chiếu:** So sánh kết quả thực tế với tiêu chí đạt; ghi cả sai khác nếu có.
6. **Lập kết luận:** Ghi `passed`, `failed` hoặc `inconclusive`, kèm giới hạn phạm vi.
7. **Bảo toàn:** Tạo bản che thông tin, cập nhật chỉ mục và tính checksum.

Mẫu `conclusion.md`:

```markdown
# MC-UX-03 — Trạng thái tin cậy của kết quả

## Mệnh đề

Kết quả dựng hình công bố trạng thái tin cậy và yêu cầu xác nhận khi tồn tại giả định.

## Điều kiện

- Commit: `<sha>`
- Môi trường: staging
- Thời gian UTC: `<timestamp>`
- Đầu vào: `Vẽ tam giác ABC.`

## Quan sát

- Response: `<trường và giá trị quan sát được>`
- Giao diện: `<nhãn và hành động quan sát được>`
- Tệp gốc: `<danh sách đường dẫn>`

## Đối chiếu tiêu chí

`<đạt hoặc không đạt, nêu dữ kiện trực tiếp>`

## Kết luận

`passed | failed | inconclusive`

Phạm vi kết luận: `<năng lực được chứng minh, không mở rộng sang nội dung khác>`
```

---

### 7. Danh mục minh chứng theo tiêu chí

### 7.1. Giao diện người dùng

#### MC-UI-01 — Khả năng build và phân tách tài nguyên frontend

**Mệnh đề:** Frontend vượt qua kiểm tra kiểu, build thành công và tạo các chunk tải độc lập.

**Dữ liệu chính:** log build, exit code, danh sách `dist/assets`.

```bash
cd /home/sin235/Projects/math_ai_visualize/frontend
set -o pipefail
npm ci 2>&1 | tee ../minh_chung/01-giao-dien/MC-UI-01-npm-ci.txt
npm run build 2>&1 | tee ../minh_chung/01-giao-dien/MC-UI-01-build.txt
printf 'exit_code=%s\n' "$?" > ../minh_chung/01-giao-dien/MC-UI-01-exit-code.txt
ls -lh dist/assets > ../minh_chung/01-giao-dien/MC-UI-01-assets.txt
```

**Tiêu chí đạt:** exit code bằng 0; TypeScript và Vite không báo lỗi; thư mục tài nguyên có nhiều chunk JavaScript.

#### MC-UI-02 — Hiển thị toán học và các renderer

**Mệnh đề:** Hệ thống biểu diễn được công thức, hình học 2D và mô hình 3D bằng renderer tương ứng.

**Bộ ca kiểm tra:**

| Ca | Đầu vào | Renderer | Quan sát bắt buộc |
| --- | --- | --- | --- |
| UI-02A | `Cho A(1,2), B(4,5). Vẽ đường thẳng AB.` | GeoGebra 2D | Điểm và đường thẳng xuất hiện; applet tương tác được |
| UI-02B | `Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.` | Three.js 3D | Mô hình hiển thị; xoay và thay đổi tỷ lệ phản hồi |
| UI-02C | `x^2 - 5x + 6 = 0` | Algebra Solver | Công thức KaTeX và các bước giải xuất hiện |

**Dữ liệu chính:** video toàn bộ thao tác, ảnh kết quả, request và response tương ứng. Ảnh cuối không thay thế video thao tác đối với mệnh đề về tính tương tác.

#### MC-UI-03 — Khả năng thích ứng màn hình hẹp

**Mệnh đề:** Không gian hình học nhận diện màn hình dưới 900 px, đề xuất xoay ngang và vẫn cho phép tiếp tục theo chiều dọc.

**Quy trình:** đặt viewport lần lượt ở 899 px và 901 px, giữ nguyên route và dữ liệu. Ghi video hai trường hợp để tạo cặp đối chứng quanh ngưỡng.

**Tiêu chí đạt:** hộp thoại xuất hiện ở 899 px, không xuất hiện do cùng điều kiện ở 901 px; thao tác tiếp tục theo chiều dọc đóng hộp thoại và giữ workspace hoạt động.

### 7.2. Trải nghiệm người dùng

#### MC-UX-01 — Nhập đề đa phương thức và phản hồi tiến trình

**Mệnh đề:** Người dùng có thể nhập đề bằng văn bản, chọn mẫu, tải ảnh, kéo thả hoặc dán ảnh; hệ thống công bố trạng thái OCR và dựng hình tương ứng.

**Quy trình:** ghi một video liên tục cho từng phương thức. Mỗi ca bắt đầu từ trạng thái trang mới, sử dụng cùng ảnh test và lưu kết quả OCR để so sánh.

**Tiêu chí đạt:** dữ liệu được tiếp nhận; trạng thái “Đang đọc ảnh” xuất hiện ở ca ảnh; nội dung nhận dạng được đưa vào vùng nhập; trạng thái “Đang dựng hình” xuất hiện sau khi gửi; nút gửi bị vô hiệu hóa trong thời gian xử lý.

#### MC-UX-02 — Công bố mức độ tin cậy

**Mệnh đề:** Giao diện phân biệt kết quả đã kiểm chứng với hình minh họa có giả định hoặc cần xác nhận.

**Bộ ca kiểm tra:**

- Ca đầy đủ dữ kiện, lưu đề, response và nhãn kết quả.
- Ca thiếu dữ kiện `Vẽ tam giác ABC`, lưu giả định, `requires_user_confirmation` và nhãn kết quả.

**Tiêu chí đạt:** trạng thái trong response phù hợp với nhãn trên giao diện; đề đầu vào và nhãn phải xuất hiện trong cùng chuỗi dữ liệu; không kết luận dựa trên ảnh đã cắt mất ngữ cảnh.

#### MC-UX-03 — Xác nhận và điều kiện xuất

**Mệnh đề:** Kết quả cần xác nhận không được coi là đã chấp thuận cho đến khi người dùng thực hiện hành động xác nhận.

**Quy trình:** dùng một response có `requires_user_confirmation = true`; lưu trạng thái trước xác nhận, thao tác xác nhận, trạng thái sau xác nhận và trạng thái menu xuất.

**Tiêu chí đạt:** trước thao tác, giao diện thể hiện yêu cầu xác nhận; sau thao tác, `user_confirmed` thay đổi trên kết quả hiện tại; điều kiện xuất phản ánh trạng thái mới.

#### MC-UX-04 — Chỉnh scene và kiểm chứng lại

**Mệnh đề:** Scene phản hồi cục bộ với thao tác chỉnh sửa, sau đó chuyển sang trạng thái chờ máy chủ kiểm chứng.

**Quy trình:** di chuyển một điểm, thêm một đoạn hoặc chiếu điểm lên đoạn; lưu video, response trước chỉnh sửa, trạng thái chờ kiểm chứng và response sau kiểm chứng.

**Tiêu chí đạt:** thay đổi xuất hiện ngay trên hình; scene được đánh dấu chờ kiểm chứng; kết quả sau kiểm chứng có scene và báo cáo chất lượng mới.

#### MC-UX-05 — Lưu và khôi phục lịch sử

**Mệnh đề:** Đề bài, scene và renderer được lưu và khôi phục qua phiên trình duyệt.

**Quy trình:** tạo một kết quả bằng tài khoản test; ghi nhận ID lịch sử; tải lại trang; mở mục vừa tạo; thực hiện yêu thích, lưu trữ và bỏ lưu trữ.

**Tiêu chí đạt:** dữ liệu khôi phục trùng với bản đã lưu; trạng thái tổ chức tồn tại sau khi tải lại. So sánh bằng ID và trường dữ liệu, không chỉ bằng hình ảnh tương tự.

#### MC-UX-06 — Mô phỏng từng bước và khả năng tiếp cận thông báo

**Mệnh đề:** Mô phỏng duy trì đồng bộ bước, tiến độ và hình ảnh; thông báo hệ thống được công bố qua vùng hỗ trợ truy cập.

**Dữ liệu chính:** video điều khiển chạy, dừng, lùi, tiến, đặt lại, đổi tốc độ; ảnh DOM hoặc accessibility tree thể hiện `aria-live`; log kiểm thử baseline mô phỏng.

### 7.3. Logic ứng dụng

#### MC-LOGIC-01 — Vòng đời xác thực và chính sách sử dụng

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_auth_product.py \
  tests/test_auth_guards.py \
  --junitxml=../minh_chung/03-logic-ung-dung/MC-LOGIC-01-auth.xml
```

**Tiêu chí đạt:** lệnh trả exit code 0; JUnit không có failure hoặc error. Video runtime bổ sung cần thể hiện đăng nhập, danh sách phiên, thu hồi phiên và đăng xuất bằng tài khoản test.

#### MC-LOGIC-02 — Định tuyến AI và fallback

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_model_registry.py \
  tests/test_model_provider.py \
  tests/test_ai_provider_fallbacks.py \
  --junitxml=../minh_chung/03-logic-ung-dung/MC-LOGIC-02-ai-routing.xml
```

**Tiêu chí đạt:** toàn bộ test vượt qua; log không chứa khóa dịch vụ. Minh chứng chỉ kết luận quy tắc lựa chọn và fallback hoạt động trong các ca kiểm thử, không tự mở rộng thành kết luận về độ sẵn sàng của nhà cung cấp bên ngoài.

#### MC-LOGIC-03 — Solver và kiểm chứng toán học

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_algebra_equation_solver.py \
  tests/test_algebra_inequality_solver.py \
  tests/test_algebra_trig_solver.py \
  tests/test_algebra_parameter_solver.py \
  tests/test_function_analyzer.py \
  tests/test_geometry_facts.py \
  tests/test_cas_verifier.py \
  tests/test_cas_repair.py \
  --junitxml=../minh_chung/03-logic-ung-dung/MC-LOGIC-03-math.xml
```

Bổ sung bộ bài toán đối chiếu có đáp án chuẩn cho phương trình, bất phương trình, lượng giác, hàm số, bài toán tham số và hình học. Mỗi bài lưu đầu vào, kết quả, đáp án chuẩn, quy tắc so sánh và kết luận riêng.

#### MC-LOGIC-04 — Pipeline trạng thái scene

**Mệnh đề:** Pipeline sinh trạng thái phù hợp từ validation, verification, fallback, giả định và tương thích renderer.

**Dữ liệu chính:** response JSON cho tối thiểu một ca `verified`, một ca `needs_confirmation` hoặc `partially_verified`, cùng kết quả test scene/CAS liên quan.

**Tiêu chí đạt:** trạng thái chính phù hợp với các báo cáo thành phần và `requires_user_confirmation`; không chỉnh sửa response để tạo đủ trạng thái.

### 7.4. Backend và API

#### MC-API-01 — Liveness, readiness và OpenAPI

```bash
mkdir -p minh_chung/04-backend-api/MC-API-01/01-raw
curl -sS -D minh_chung/04-backend-api/MC-API-01/01-raw/health.headers \
  "$BASE_URL/api/health" \
  -o minh_chung/04-backend-api/MC-API-01/01-raw/health.json
curl -sS -D minh_chung/04-backend-api/MC-API-01/01-raw/ready.headers \
  "$BASE_URL/api/health/ready" \
  -o minh_chung/04-backend-api/MC-API-01/01-raw/ready.json
curl -fsS "$BASE_URL/openapi.json" \
  -o minh_chung/04-backend-api/MC-API-01/01-raw/openapi.json
```

**Tiêu chí đạt:** health trả HTTP 200 và `status: ok`; readiness trả HTTP 200, `status: ready`, `database.ok: true`, `database.backend: postgres`; OpenAPI chứa các nhóm route được nêu trong báo cáo.

#### MC-API-02 — Render job bất đồng bộ

**Mệnh đề:** Tác vụ render được lưu bền vững và chuyển qua state machine xác định.

**Dữ liệu chính:** HAR hoặc request/response tạo job, các response polling, truy vấn PostgreSQL theo đúng job ID, log worker chứa cùng ID nếu có.

**Tiêu chí đạt:** request đầu trả job ID; bản ghi khởi tạo ở `queued`; tác vụ được claim theo điều kiện; trạng thái cuối là `completed` kèm kết quả hoặc `failed` kèm lỗi chuẩn hóa. Nếu job hoàn tất quá nhanh để chụp `running`, sử dụng bản ghi thời điểm `started_at` và kiểm thử worker; không dàn dựng ảnh trạng thái.

#### MC-API-03 — Validation, xử lý lỗi và request ID

Thực hiện một ca hợp lệ và một ca thiếu trường bắt buộc trên staging. Lưu request, response headers và body.

**Tiêu chí đạt:** ca hợp lệ trả mã thành công phù hợp; ca sai trả 4xx; response có `X-Request-Id`; body lỗi có cấu trúc; không chứa stack trace, secret hoặc đường dẫn nội bộ.

#### MC-API-04 — WebSocket

Lưu handshake, frame gửi và chuỗi frame nhận của một phiên chat bằng tài khoản test. Request và frame phải cùng timestamp và session kiểm tra. Kết luận chỉ xác nhận dữ liệu được truyền theo thời gian thực khi video giao diện khớp với chuỗi frame mạng.

### 7.5. Cơ sở dữ liệu PostgreSQL

#### MC-DB-01 — PostgreSQL và trạng thái sẵn sàng

```bash
curl -fsS "$BASE_URL/api/health/ready" | jq . \
  > minh_chung/05-postgresql/MC-DB-01-readiness.json
```

**Tiêu chí đạt:** `status = ready`, `database.ok = true`, `database.backend = postgres`.

#### MC-DB-02 — Migration và connection pool

Bằng phiên quản trị, lưu response `/api/health/detail` đã che thông tin nhạy cảm. Đối chiếu các trường trong `database.migration_drift` và `database.pool`.

**Tiêu chí đạt:** database hoạt động; migration drift đạt; pool được khởi tạo và các chỉ số nằm trong giới hạn cấu hình. Chỉ sử dụng tên trường thực tế xuất hiện trong response.

#### MC-DB-03 — Lược đồ và ràng buộc PostgreSQL

```bash
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -c "SELECT version();" \
  > minh_chung/05-postgresql/MC-DB-03-version.txt
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -c "SELECT filename, applied_at FROM schema_migrations ORDER BY filename;" \
  > minh_chung/05-postgresql/MC-DB-03-migrations.txt
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;" \
  > minh_chung/05-postgresql/MC-DB-03-tables.txt
```

Bổ sung truy vấn `information_schema` cho khóa ngoại và chỉ mục của các bảng đại diện như người dùng, phiên, render job và lịch sử. Không đưa `DATABASE_URL` vào log bàn giao.

#### MC-DB-04 — Tính bền vững của render job

Trên staging, tạo một job, lưu job ID, đợi trạng thái cuối, khởi tạo phiên trình duyệt mới và truy vấn lại kết quả. Đối chiếu cùng ID trong API và PostgreSQL.

**Tiêu chí đạt:** request đầu vào, trạng thái cuối và dữ liệu lịch sử liên kết đúng job; kết quả vẫn truy cập được sau khi phiên HTTP ban đầu kết thúc.

#### MC-DB-05 — Backup managed PostgreSQL

Sử dụng trang quản trị DigitalOcean hoặc kết quả script xác minh production để lưu timestamp bản backup gần nhất và trạng thái hợp lệ. Minh chứng phải ghi thời điểm thu thập và giới hạn tuổi backup được áp dụng; che cluster ID và app ID trong bản bàn giao.

### 7.6. Bảo mật

#### MC-SEC-01 — Thuộc tính cookie phiên

Đăng nhập bằng tài khoản test trên production, chụp tên cookie cùng các cờ `HttpOnly`, `Secure`, `SameSite`. Che toàn bộ giá trị cookie. Ảnh thiếu cột thuộc tính không đủ để kết luận.

#### MC-SEC-02 — Kiểm tra Origin và phân quyền

Trên staging, thực hiện cặp request cùng endpoint thay đổi dữ liệu:

- Request hợp lệ từ Origin tin cậy bằng tài khoản test.
- Request có Origin không tin cậy với cùng payload và cùng tài khoản test.

**Tiêu chí đạt:** request hợp lệ đi qua kiểm tra Origin; request đối chứng bị từ chối trước khi thay đổi dữ liệu. Xác nhận trạng thái dữ liệu sau hai request để loại trừ trường hợp response lỗi nhưng thao tác vẫn được thực hiện.

#### MC-SEC-03 — Bảo vệ BYOK và health detail

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_byok_hardening_csv_matrix.py \
  tests/test_user_settings_api.py \
  tests/test_health_security.py \
  --junitxml=../minh_chung/06-bao-mat/MC-SEC-03-security.xml
```

Bổ sung hai response API bằng tài khoản test: lưu khóa và đọc lại trạng thái cấu hình. Bản đọc lại chỉ được chứa trạng thái và phần nhận diện cuối, không chứa plaintext.

#### MC-SEC-04 — Xác thực, session, rate limit và khóa đăng nhập

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_auth_product.py \
  tests/test_auth_guards.py \
  --junitxml=../minh_chung/06-bao-mat/MC-SEC-04-auth.xml
```

Các ca runtime tạo lỗi hoặc khóa tạm thời chỉ chạy trên staging bằng tài khoản dành riêng cho kiểm chứng.

### 7.7. Hiệu năng và khả năng mở rộng

#### MC-PERF-01 — Tải module theo nhu cầu

Sau khi build, mở DevTools Network, tải mới trang chính rồi lần lượt mở Analyzer, Algebra Solver, Simulation và GeoGebra Lab. Xuất HAR cho phiên kiểm tra.

**Tiêu chí đạt:** chunk của workspace chỉ xuất hiện khi route tương ứng được mở. Danh sách file build là chứng cứ bổ sung; HAR là chứng cứ chính cho thời điểm tải.

#### MC-PERF-02 — Worker và capacity gate

Lưu phần `load` và `redis` từ health detail, log xác nhận worker đang chạy và kết quả kiểm thử capacity/worker tương ứng.

**Tiêu chí đạt:** giới hạn đồng thời được công bố; worker hoạt động; job không lấy được slot được xử lý theo trạng thái đã định. Không làm cạn capacity trên production để tạo minh chứng.

#### MC-PERF-03 — Số liệu thời gian xử lý

Nếu hồ sơ đưa ra nhận định định lượng, dữ liệu phải ghi:

- Khoảng thời gian đo.
- Số mẫu và điều kiện chọn mẫu.
- Provider, renderer và loại tác vụ.
- Số lần warm-up bị loại.
- p50, p95, tỷ lệ thành công và tỷ lệ thất bại.

Không dùng một request đơn lẻ hoặc trung bình không kèm phân bố để kết luận hiệu năng chung. Báo cáo hiện tại chỉ cần chứng minh cơ chế tối ưu và giới hạn tài nguyên, nên số liệu định lượng là phụ lục bổ sung, không phải điều kiện bắt buộc.

### 7.8. Phân tích và theo dõi

#### MC-MON-01 — Product analytics

Trên staging, tạo một chuỗi hoạt động bằng tài khoản test: mở tính năng, hoàn tất một render và tạo một lỗi có kiểm soát. Ghi ID hoặc timestamp của từng sự kiện. Sau đó lưu dashboard hoặc response tổng hợp cho cùng khoảng thời gian.

**Tiêu chí đạt:** sự kiện đầu vào xuất hiện trong phép tổng hợp tương ứng; khoảng thời gian và bộ lọc được ghi rõ.

#### MC-MON-02 — AI call metrics

Thực hiện một tác vụ AI bằng tài khoản test; lưu request ID, response và bản ghi metrics tương ứng đã che dữ liệu nhạy cảm.

**Tiêu chí đạt:** provider, model, loại tác vụ, token, thời gian và trạng thái được ghi; request ID liên kết được với tác vụ nguồn.

#### MC-MON-03 — Gom nhóm lỗi

Tạo hai lỗi cùng loại và một lỗi khác loại trên staging. Lưu ba event cùng kết quả nhóm.

**Tiêu chí đạt:** hai lỗi đồng loại có cùng fingerprint và count tăng; lỗi khác loại không bị nhập vào cùng nhóm. Đây là ca đối chứng bắt buộc để chứng minh cơ chế phân nhóm, không chỉ chứng minh trường fingerprint tồn tại.

#### MC-MON-04 — Kiểm thử analytics và cảnh báo

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
python -m pytest -q \
  tests/test_analytics_monitoring.py \
  tests/test_alerts_and_metrics.py \
  --junitxml=../minh_chung/08-phan-tich-theo-doi/MC-MON-04-analytics.xml
```

### 7.9. Vận hành và cập nhật

#### MC-OPS-01 — GitHub Actions

Tại commit dùng để nộp, lưu trang tổng quan workflow và log cuối của ba job `Backend tests`, `Frontend build`, `Docker build (smoke)`. Commit SHA trên workflow phải trùng với phiên bản ghi trong hồ sơ; nếu khác, kết luận phải ghi rõ phạm vi phiên bản.

#### MC-OPS-02 — Docker artifact

```bash
cd /home/sin235/Projects/math_ai_visualize
set -o pipefail
docker build -t math-ai-visualize:evidence . 2>&1 \
  | tee minh_chung/09-van-hanh-cap-nhat/MC-OPS-02-docker-build.txt
docker image inspect math-ai-visualize:evidence \
  > minh_chung/09-van-hanh-cap-nhat/MC-OPS-02-image-inspect.json
```

**Tiêu chí đạt:** build kết thúc với exit code 0; image inspect trả metadata của artifact vừa tạo.

#### MC-OPS-03 — Trạng thái production

```bash
cd /home/sin235/Projects/math_ai_visualize
set -o pipefail
./deploy/verify-production.sh 2>&1 \
  | tee minh_chung/09-van-hanh-cap-nhat/MC-OPS-03-production.txt
```

Kết quả script chỉ có giá trị tại timestamp chạy. Lưu exit code và không diễn giải kết quả này thành cam kết trạng thái cho các thời điểm khác.

#### MC-OPS-04 — Cấu trúc tiến trình container

Lưu cấu hình Supervisord, Nginx và log runtime thể hiện Uvicorn, render worker, Nginx đang thực hiện đúng vai trò. Cấu hình giải thích trách nhiệm; log runtime xác nhận tiến trình hiện hành. Hai nguồn phải tham chiếu cùng artifact hoặc commit.

### 7.10. Chất lượng sản phẩm

#### MC-QA-01 — Toàn bộ kiểm thử backend

```bash
cd /home/sin235/Projects/math_ai_visualize/backend
set -o pipefail
python -m pytest -q \
  --junitxml=../minh_chung/10-chat-luong-san-pham/MC-QA-01-pytest.xml \
  2>&1 | tee ../minh_chung/10-chat-luong-san-pham/MC-QA-01-pytest.txt
printf 'exit_code=%s\n' "$?" \
  > ../minh_chung/10-chat-luong-san-pham/MC-QA-01-exit-code.txt
```

#### MC-QA-02 — Kiểm tra frontend và mô phỏng

```bash
cd /home/sin235/Projects/math_ai_visualize/frontend
set -o pipefail
npm run build 2>&1 \
  | tee ../minh_chung/10-chat-luong-san-pham/MC-QA-02-build.txt
npm run test:simulation 2>&1 \
  | tee ../minh_chung/10-chat-luong-san-pham/MC-QA-02-simulation.txt
npm run test:analyzer-values 2>&1 \
  | tee ../minh_chung/10-chat-luong-san-pham/MC-QA-02-analyzer-values.txt
```

#### MC-QA-03 — Tính nhất quán của các định dạng xuất

Từ cùng một scene đã kiểm chứng, xuất PNG, JPG, SVG, HTML KaTeX, TikZ, PDF và GeoGebra. Hồ sơ gồm response nguồn, ảnh giao diện trước khi xuất, các tệp kết quả và ảnh mở thành công bằng ứng dụng phù hợp.

**Tiêu chí đạt:** tất cả đầu ra tham chiếu cùng scene; tệp mở được; nội dung toán học cốt lõi không thay đổi giữa các định dạng. Chỉ kiểm tra phần mà từng định dạng có khả năng biểu diễn.

#### MC-QA-04 — Bộ bài toán đại diện

Chọn tối thiểu một bài cho mỗi nhóm: hình học phẳng, hình học không gian, phương trình hoặc bất phương trình, lượng giác, đạo hàm hoặc tích phân, hàm số có tiệm cận và bài toán tham số.

Mỗi bài phải có:

- Mã ca kiểm tra.
- Đề đầu vào nguyên văn.
- Kết quả hệ thống.
- Đáp án chuẩn và nguồn đáp án.
- Quy tắc so sánh.
- Kết luận đúng, sai hoặc không đủ dữ liệu.

Không dùng cùng một bài để đại diện cho toàn bộ năng lực toán học. Kết quả hình ảnh được đánh giá riêng với kết quả đại số; hình minh họa không được dùng làm căn cứ duy nhất để khẳng định quan hệ toán học.

---

## 8. Bảng ánh xạ mệnh đề và chỉ mục minh chứng

### 8.1. Bảng ánh xạ mệnh đề

`BANG_ANH_XA_MENH_DE.csv` có cấu trúc:

```csv
claim_id,report_section,claim,evidence_ids,primary_level,status,notes
CL-UI-01,3.1,"Giao diện biểu diễn công thức và nhiều loại renderer","MC-UI-01;MC-UI-02",E1,pending,
CL-UX-01,3.2,"Kết quả công bố mức độ tin cậy","MC-UX-02;MC-LOGIC-04",E1,pending,
CL-API-01,3.4,"Render job có state machine bền vững","MC-API-02;MC-DB-04",E2,pending,
```

Mỗi mệnh đề quan trọng phải có ít nhất một minh chứng E1–E4. E5 chỉ đóng vai trò giải thích cơ chế, không tự xác nhận trạng thái vận hành.

### 8.2. Bảng chỉ mục tệp

`BANG_CHI_MUC.csv` có cấu trúc:

```csv
evidence_id,category,environment,commit_sha,collected_at_utc,result,conclusion_file,public_folder
MC-UI-01,Giao diện,local,<sha>,<timestamp>,passed,01-giao-dien/MC-UI-01/conclusion.md,01-giao-dien/MC-UI-01/02-redacted
MC-DB-01,PostgreSQL,production,<sha>,<timestamp>,passed,05-postgresql/MC-DB-01/conclusion.md,05-postgresql/MC-DB-01/02-redacted
```

`result` chỉ nhận `passed`, `failed` hoặc `inconclusive`. Không để ô trống đối với mã đã đưa vào phụ lục nộp chấm điểm.

---

## 9. Tạo checksum và đóng gói

Sau khi hoàn tất thu thập, tạo checksum từ thư mục dự án:

```bash
cd /home/sin235/Projects/math_ai_visualize
find minh_chung -type f ! -name SHA256SUMS.txt -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > minh_chung/00-chi-muc/SHA256SUMS.txt
```

Kiểm tra lại:

```bash
cd /home/sin235/Projects/math_ai_visualize
sha256sum --check minh_chung/00-chi-muc/SHA256SUMS.txt
```

Gói bàn giao công khai chỉ chứa bản đã che thông tin. Dữ liệu gốc được lưu trong phạm vi kiểm soát và tham chiếu bằng checksum nếu không thể đưa vào phụ lục.

---

## 10. Điều kiện nghiệm thu hồ sơ

Hồ sơ được xem là đủ điều kiện bàn giao khi đáp ứng đồng thời các yêu cầu sau:

1. Mỗi nội dung chính trong báo cáo có `claim_id` và mã minh chứng tương ứng.
2. Commit, môi trường và timestamp được ghi cho từng bộ minh chứng.
3. Dữ liệu gốc và bản đã che thông tin được tách riêng.
4. Ảnh giao diện có đầu vào và ngữ cảnh; video hành vi giữ được trình tự thao tác.
5. Minh chứng API có status, header và body; các tệp cùng request có thể liên kết bằng request ID hoặc timestamp.
6. Minh chứng PostgreSQL có câu truy vấn, kết quả và môi trường, không chứa chuỗi kết nối.
7. Kiểm thử có lệnh, exit code và kết quả máy đọc được khi có thể.
8. Minh chứng production chỉ sử dụng thao tác đọc và ghi rõ thời điểm hiệu lực.
9. Ca lỗi và kết quả không đạt được giữ lại, không bị loại khỏi hồ sơ để tạo thiên lệch lựa chọn.
10. Checksum của gói bàn giao được kiểm tra thành công.
11. Không có token, cookie value, API key, bí mật OAuth, `DATABASE_URL` hoặc dữ liệu người dùng thật.
12. Kết luận không vượt quá phạm vi của dữ liệu đã thu thập.

Một hồ sơ đạt yêu cầu phải cho phép người chấm đi từ mệnh đề trong báo cáo đến mã phụ lục, từ mã phụ lục đến dữ liệu gốc, rồi từ dữ liệu gốc tái hiện được điều kiện, thao tác, quan sát và kết luận. Đây là tiêu chuẩn cốt lõi để minh chứng có tính khách quan, kỹ thuật, khoa học và logic.

---

## 11. Trạng thái thu thập thực tế

Phiên tự động ngày `2026-07-12` đã tạo hồ sơ tại `minh_chung/` trên workspace có thay đổi chưa commit. Commit nền là `5cac5199def7fd960fcf2ab27a02a9fa3cc1f07a`; `workspace_clean=false`; snapshot thay đổi nằm tại `minh_chung/00-chi-muc/WORKSPACE.diff`.

### 11.1. Phần đã hoàn thành bằng máy

| Phạm vi | Mã | Kết quả đã xác minh |
| --- | --- | --- |
| Frontend | `MC-UI-01`, `MC-QA-02` | `npm ci`, typecheck, Vite build, simulation baseline và analyzer values đều thành công |
| Logic ứng dụng | `MC-LOGIC-01` đến `MC-LOGIC-03` | Nhóm test xác thực, định tuyến AI và toán học đều có exit code 0 |
| Backend tổng thể | `MC-QA-01` | 1463 test vượt qua, 17 warnings, exit code 0; có JUnit XML |
| API production | `MC-API-01`, `MC-API-03` | Liveness/readiness HTTP 200; PostgreSQL ready; validation HTTP 422 có mã lỗi và request ID |
| PostgreSQL production | `MC-DB-01` | Readiness xác nhận `database.backend=postgres`, `database.ok=true` tại thời điểm thu |
| Bảo mật | `MC-SEC-03` | 510 test vượt qua; warnings được giữ nguyên và nêu trong kết luận |
| Theo dõi | `MC-MON-04` | 15 test analytics/cảnh báo vượt qua |
| GitHub | `MC-OPS-01` | Workflow product và ba job thành công; ruleset product active với required checks |
| DigitalOcean | `MC-OPS-03` | Health public xác minh được; dữ liệu account yêu cầu đăng nhập nên kết luận còn `inconclusive` |

`GET /openapi.json` production trả frontend HTML. Dữ liệu phản chứng được lưu dưới tên đúng loại nội dung `openapi.html`; hồ sơ không tuyên bố OpenAPI public hoạt động.

### 11.2. Chỉ mục và phần cần bổ sung

- Chỉ mục vật chứng: `minh_chung/00-chi-muc/BANG_CHI_MUC.csv`.
- Ánh xạ 10 tiêu chí: `minh_chung/00-chi-muc/BANG_ANH_XA_MENH_DE.csv`.
- Tổng hợp máy đọc được: `minh_chung/00-chi-muc/TONG_HOP_TU_DONG.txt`.
- Thao tác người dùng cần thực hiện: `minh_chung/00-chi-muc/NGUOI_DUNG_CAN_LAM.md`.
- Manifest toàn vẹn: `minh_chung/00-chi-muc/SHA256SUMS.txt`.

Phần người dùng còn lại gồm xác thực `doctl`, thu deployment/backup PostgreSQL, quay các luồng UX, đối chứng bảo mật/monitoring có quyền và Docker local nếu phạm vi nộp bắt buộc. Mọi output bổ sung phải được quét secret rồi tạo lại checksum; không nối thêm file sau khi giữ nguyên manifest cũ.
