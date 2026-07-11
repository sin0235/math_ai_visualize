# BÁO CÁO ĐỐI CHIẾU MÃ NGUỒN VÀ NĂNG LỰC HỆ THỐNG ĐÃ TRIỂN KHAI

1. Phạm vi và nguyên tắc rà soát

Tài liệu được xây dựng dựa trên việc rà soát tĩnh và kiểm thử đơn vị đối với toàn bộ kho mã nguồn của dự án bao gồm:

- Giao diện người dùng (frontend) dựa trên React 18 và Vite.
- Máy chủ dịch vụ (backend) dựa trên FastAPI và Python phi đồng bộ.
- Hệ thống lược đồ và file migration cơ sở dữ liệu SQLite, PostgreSQL và Cloudflare D1.
- Kịch bản kiểm thử tự động sử dụng pytest cho backend và kịch bản test cho frontend.
- Cấu hình đóng gói container Docker, cấu hình Nginx, Supervisord và tự động hóa quy trình CI/CD qua GitHub Actions.

**Nguyên tắc trình bày:** Để đảm bảo tính trung lập và tập trung hoàn toàn vào kiến trúc hệ thống và logic nghiệp vụ kỹ thuật, tài liệu này **không chứa** tên tệp tin cụ thể, đường dẫn thư mục nguồn, tên biến cấu hình hệ thống hoặc đường dẫn API endpoint thô trong các phần mô tả chi tiết.

---



## 2. Tổng quan đánh giá theo 10 tiêu chí


| TT  | Tiêu chí đánh giá          | Trạng thái rà soát và đánh giá thực tế                                                                                                                                                                                                |
| --- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Giao diện người dùng**   | Đã triển khai giao diện đơn sắc tương phản cao, hỗ trợ vẽ hình học phẳng/không gian tương tác qua Three.js/GeoGebra và hiển thị công thức toán học sắc nét qua KaTeX.                                                                 |
| 2   | **Trải nghiệm người dùng** | Đã triển khai luồng nhập liệu đa phương thức, hàng đợi theo dõi tiến trình trực quan, quản lý hồ sơ học tập chi tiết và phòng thí nghiệm tương tác.                                                                                   |
| 3   | **Tính logic ứng dụng**    | Đã hoàn thiện xác thực Bcrypt và Google OAuth 2.0, quota sử dụng, định tuyến/dự phòng AI, cùng bộ giải toán SymPy kết hợp kiểm chứng hình học. MinerU (PDF→Word) là frontend độc lập gọi API ngoài, backend không có tích hợp MinerU. |
| 4   | **Backend & API**          | Đã phân tách rõ ràng kiến trúc 3 lớp phi trạng thái trên FastAPI, điều phối bất đồng bộ các tác vụ nặng qua Thread/Process Pool và nén truyền tải dữ liệu.                                                                            |
| 5   | **Cơ sở dữ liệu**          | Đã hoàn thiện cấu trúc lược đồ hoàn chỉnh (36 bảng trên 19 migration files), hỗ trợ SQLite WAL, PostgreSQL connection pool, Cloudflare D1. Chưa có cơ chế sao lưu tự động (pg_dump/sqlite3 backup) — hiện chỉ hỗ trợ thủ công.        |
| 6   | **Bảo mật**                | Đã thiết lập cookie phiên HttpOnly/Secure, kiểm soát nguồn gốc chéo, mã hóa đối xứng Fernet cho khóa cá nhân và Cloudflare Turnstile chống bot (tùy chọn — chỉ active khi biến môi trường TURNSTILE_SECRET_KEY được cấu hình).        |
| 7   | **Hiệu năng & Mở rộng**    | Đã cấu hình cổng kiểm soát tải đồng thời (capacity gate) dựa trên Redis Sorted Sets có TTL, lùi về InProcessGate (asyncio.Lock) nếu Redis unavailable, phân tách worker chạy ngầm, và lazy loading React.lazy + Suspense (Vite).      |
| 8   | **Phân tích & Theo dõi**   | Đã tích hợp hệ thống đo lường hành vi, gom nhóm lỗi theo SHA-256 fingerprint 16 ký tự, giám sát token AI và cơ chế kiểm tra sức khỏe hệ thống đa tầng.                                                                                |
| 9   | **Vận hành & Cập nhật**    | Đã thiết lập quy trình tự động hóa GitHub Actions, đóng gói Docker nhiều giai đoạn, quản lý tiến trình bằng Supervisord, reverse proxy bằng Nginx và rollback nhanh.                                                                  |
| 10  | **Chất lượng sản phẩm**    | Giải quyết trực tiếp các bài toán thực tế trong giáo dục toán học với bộ kiểm thử tự động pytest đồ sộ bao phủ toàn bộ các module nghiệp vụ cốt lõi.                                                                                  |


---



## 3. Chi tiết nội dung đã triển khai theo tiêu chí đánh giá



### Hạng mục 1: Giao diện người dùng (UI)

- **Hệ thống thiết kế và phong cách thẩm mỹ trực quan:**
  - **Ngôn ngữ thiết kế tối giản, chuyên nghiệp:** Giao diện người dùng được phát triển bằng React 18, xây dựng nhất quán theo phong cách đơn sắc tối giản kết hợp nền lưới toán học chuyên sâu. Hệ thống sử dụng bảng màu tương phản cao giúp tăng cường khả năng tập trung vào nội dung học thuật, giảm mỏi mắt khi làm việc thời gian dài.
  - **Biên dịch công thức toán học thời gian thực bằng KaTeX:** Toàn bộ công thức toán học, biểu thức đại số và ký hiệu đặc biệt được hiển thị sắc nét bằng thư viện KaTeX hiệu năng cao. KaTeX thực hiện biên dịch ký tự LaTeX sang đồ họa vector (SVG/HTML) thời gian thực trực tiếp trên trình duyệt, đảm bảo hiển thị hoàn hảo, không bị vỡ nét trên mọi thiết bị và trình duyệt.
- **Các không gian làm việc và công cụ tích hợp:**
  - **Màn hình tương tác hình học WebGL:** Cung cấp viewport kết xuất mô hình đồ họa phẳng 2D và không gian 3D tương tác sử dụng thư viện Three.js, React Three Fiber và thư viện bổ trợ Drei. Người dùng có thể trực tiếp xoay, phóng to, thu nhỏ và thay đổi góc nhìn camera bằng chuột hoặc thao tác vuốt chạm trên thiết bị di động.
  - **Tích hợp học liệu tương tác GeoGebra:** Tích hợp trực tiếp GeoGebra Web Library để phục vụ dựng hình phẳng, dựng hình không gian và không gian thực hành GeoGebra Lab riêng biệt, cho phép người dùng thao tác trực tiếp với các đối tượng toán học.
  - **Bảng điều khiển khảo sát hàm số và bảng biến thiên:** Giao diện chuyên biệt hiển thị đồ thị hàm số động kèm theo bảng thiên biến, tiệm cận và các điểm đặc biệt (cực trị, giao điểm) được cập nhật đồng bộ.
    - *Hiển thị đồ thị hàm số không liên tục chính xác:* Đồ thị vẽ riêng biệt các thành phần liên thông của miền xác định, ngăn chặn hoàn toàn việc vẽ đè hoặc tự động nối liền qua các đường tiệm cận đứng hoặc điểm kỳ dị gián đoạn nhờ dữ liệu lấy mẫu thích ứng từ backend.
  - **Bộ giải toán đại số từng bước:** Hiển thị tiến trình biến đổi toán học theo dạng cây phân cấp trực quan sử dụng KaTeX, làm nổi bật các bước biến đổi trung gian và công thức áp dụng.
  - **Hệ thống quản lý cá nhân:** Bao gồm trang tổng quan lịch sử giải toán, quản lý bộ sưu tập dự án, cài đặt cấu hình khóa AI cá nhân, hồ sơ theo dõi năng lực học tập và trung tâm quản trị hệ thống.
- **Khung tương tác hình học thông minh:**
  - **Cây đối tượng hình học chi tiết:** Hiển thị danh sách phân cấp các thực thể hình học hiện có trong không gian (điểm, đường thẳng, mặt phẳng, góc, thiết diện), cho phép người dùng ẩn/hiện hoặc tô màu tùy biến để dễ dàng quan sát.
  - **Bộ công cụ dựng hình thủ công bổ trợ:** Người dùng có thể tương tác trực tiếp bằng cách di chuyển điểm tự do, nối đoạn thẳng giữa các điểm, chiếu điểm vuông góc lên đoạn thẳng, hoặc thêm các ràng buộc hình học mới.
  - **Thanh trượt tham số động:** Cho phép kéo thả thay đổi giá trị của các tham số đầu vào (như chiều cao hình chóp, bán kính đường tròn) để quan sát sự thay đổi hình dáng mô hình trực quan ngay lập tức trước khi gửi yêu cầu kiểm chứng lên máy chủ.
- **Tính thích ứng thiết bị và hỗ trợ tiếp cận:**
  - **Cảnh báo thiết bị di động thông minh:** Khi người dùng truy cập các màn hình hình học hoặc mô phỏng phức tạp trên thiết bị có chiều rộng viewport hẹp dưới 900px, hệ thống tự động hiển thị màn hình cảnh báo đề xuất chuyển sang chế độ xoay ngang hoặc sử dụng thiết bị màn hình lớn. Người dùng vẫn có thể lựa chọn bỏ qua cảnh báo để tiếp tục trải nghiệm.
  - **Nhất quán giao diện học tập:** Thiết lập ngôn ngữ thiết kế chung và đồng bộ cấu trúc hiển thị toán học thông qua các component giao diện chia sẻ sử dụng ký hiệu toán dạng KaTeX (shared KaTeX primitives), bảo đảm độ phản hồi và co giãn hoàn hảo trên các thiết bị di động có màn hình tỷ lệ khác biệt.
  - **Tối ưu hóa bố cục tài liệu:** Các component giao diện sử dụng hệ thống lưới linh hoạt giúp co giãn tự động. Đối với các công thức toán học quá dài, giao diện kích hoạt thanh cuộn ngang cục bộ để tránh làm vỡ bố cục tổng thể của trang web.

---



### Hạng mục 2: Trải nghiệm người dùng (UX)

- **Quy trình nhập liệu và xác nhận dữ kiện toán học:**
  - **Phương thức nhập liệu đa dạng:** Hỗ trợ nhập đề bài bằng văn bản tiếng Việt tự nhiên, chọn từ thư viện đề mẫu đa dạng, hoặc tải lên hình ảnh đề bài thông qua kéo thả và dán trực tiếp từ bộ nhớ đệm (clipboard).
  - **Chỉ báo trạng thái xử lý trực quan:** Tiến trình nhận diện văn bản bằng AI, phân tích cấu trúc hình học và kết xuất đồ họa được tách biệt rõ ràng thông qua các hiệu ứng chuyển động và thanh tiến độ chi tiết, loại bỏ cảm giác chờ đợi vô định của người dùng.
  - **Cổng duyệt dữ kiện trước khi dựng hình:** Khi hệ thống phân tích đề bài và phát hiện các dữ kiện chưa đầy đủ hoặc phải sử dụng giả định toán học bổ sung để dựng hình, giao diện sẽ hiển thị danh sách các dữ kiện đã bóc tách kèm các lựa chọn sửa đổi để người dùng phê duyệt trước khi tiến hành kết xuất chính thức.
- **Phản hồi hệ thống và hỗ trợ người dùng:**
  - **Hộp thoại thông báo thông minh:** Hệ thống thông báo trạng thái, cảnh báo lỗi hoặc xác nhận thành công thông qua ngăn xếp thông báo góc màn hình với thời gian hiển thị tối ưu và khả năng tắt chủ động.
  - **Mã hóa lỗi và mã yêu cầu định danh:** Khi có lỗi phát sinh từ máy chủ, giao diện hiển thị thông báo lỗi đã được Việt hóa thân thiện kèm theo mã định danh yêu cầu duy nhất để người dùng có thể gửi yêu cầu hỗ trợ nhanh chóng.
  - **Kênh trò chuyện hỗ trợ (REST + WebSocket):** Tích hợp cửa sổ chat hỗ trợ với REST API cho tin nhắn thường và WebSocket cho streaming phản hồi AI, hỗ trợ hiển thị công thức toán học LaTeX trong nội dung trò chuyện.
- **Hệ thống hồ sơ và quản lý học tập cá nhân:**
  - **Cá nhân hóa trải nghiệm học:** Người dùng có thể cấu hình chi tiết thông tin hồ sơ học tập bao gồm: cấp học, trình độ kiến thức hiện tại, mục tiêu học tập cá nhân, phong cách diễn giải lời giải mong muốn (chi tiết hay tóm tắt), và các thiết lập hỗ trợ tiếp cận đặc biệt. *(Giới hạn rà soát: Tính năng này đã được triển khai đầy đủ về lược đồ lưu trữ cơ sở dữ liệu, các API đầu cuối và giao diện cấu hình tài khoản, nhưng hiện tại chưa được tích hợp vào pipeline xử lý prompt của AI solver để thay đổi độ chi tiết của lời giải thực tế).*
  - **Quản lý lịch sử và phiên bản chỉnh sửa:** Cho phép lưu trữ lịch sử dựng hình, khôi phục các phiên bản chỉnh sửa trước đó của mô hình hình học (scene_revisions). Chưa hỗ trợ dự án (projects), gắn thẻ chủ đề (tags), hay đánh dấu yêu thích ở giao diện người dùng. (Lược đồ DB đã có: history_projects, history_tags, history_item_tags).
- **Mô phỏng học tập theo kịch bản tương tác:**
  - **Hệ thống kịch bản mô phỏng trực quan:** Cung cấp hàng chục kịch bản học tập trực quan bao gồm các chủ đề toán học trọng tâm (như định nghĩa đạo hàm, ý nghĩa tích phân, hình chiếu không gian, xác suất thống kê).
  - **Kiến trúc học tập chủ động:** Mỗi kịch bản được thiết kế đi kèm mục tiêu bài học cụ thể, kiến thức cần chuẩn bị trước, hộp thoại dự đoán kết quả trước khi mô phỏng, các câu hỏi kiểm tra tiến trình (checkpoints) xen kẽ giữa các bước thao tác, lời giải thích toán học đi kèm và điều kiện mở khóa các nút công cụ tương tác nâng cao.
  - **Chế độ khám phá tự do (Free Mode):** Ngoài kịch bản học tập theo các bước cố định, hệ thống hỗ trợ chế độ khám phá tự do cho phép người dùng tự thay đổi thông số mô hình và quan sát kết quả mà không bị ràng buộc bởi danh sách nhiệm vụ của bài học.

---



### Hạng mục 3: Tính logic ứng dụng (App Logic)

- **Đăng ký, xác thực và vòng đời tài khoản:**
  - **Mã hóa mật khẩu bằng Bcrypt:** Mật khẩu người dùng được băm bảo mật bằng thuật toán băm khóa Bcrypt mạnh mẽ kết hợp muối ngẫu nhiên (salt) trước khi lưu trữ vào cơ sở dữ liệu.
  - **Quy trình xác minh tài khoản chặt chẽ:** Đăng ký tài khoản mới bắt buộc đi qua bước xác minh hòm thư điện tử thông qua mã xác thực một lần (OTP) hoặc liên kết kích hoạt có giới hạn thời gian tồn tại ngắn.
  - **Liên kết danh tính bên thứ ba qua Google OAuth 2.0:** Hỗ trợ đăng nhập một chạm và liên kết tài khoản an toàn thông qua nhà cung cấp danh tính Google sử dụng giao thức Google OAuth 2.0.
  - **Quản lý phiên đăng nhập nâng cao:** Phiên đăng nhập được quản lý thông qua mã định danh ngẫu nhiên mã hóa lưu trong cơ sở dữ liệu. Hệ thống tự động băm mã phiên này trước khi đối chiếu, cho phép theo dõi danh sách thiết bị đang đăng nhập và hỗ trợ đăng xuất từ xa từng thiết bị hoặc toàn bộ thiết bị khác.
- **Phân quyền hệ thống và kiểm soát giới hạn tài nguyên:**
  - **Phân quyền truy cập dựa trên vai trò (RBAC):** Hệ thống phân định rõ ràng các quyền hạn của tài khoản thông thường và tài khoản quản trị viên.
  - **Chính sách giới hạn tài nguyên (Usage Quotas):** Mỗi người dùng được áp dụng chính sách giới hạn số lượt gọi API nhận diện đề bài, giải toán hoặc dựng hình theo chu kỳ ngày/tháng tùy thuộc vào gói dịch vụ đang sử dụng.
  - **Hạn chế tần suất lạm dụng (Rate Limiting):** Áp dụng thuật toán giới hạn tần suất yêu cầu trên từng địa chỉ IP và từng tài khoản định danh để bảo vệ máy chủ khỏi nguy cơ bị lạm dụng.
  - **Chính sách khóa tài khoản tự động:** Tài khoản tự động bị khóa tạm thời trong một khoảng thời gian xác định nếu thực hiện đăng nhập sai liên tiếp vượt quá số lần cấu hình tối đa.
- **Phân tích hàm số chứa tham số và lấy mẫu đồ thị nâng cao:**
  - **Biện luận tham số tự động (Parameter case analysis):** Tự động phân tích các dòng hàm chứa tham số đại số (như tham số m) để xác định các ranh giới tham số (Parameter Boundaries). Với từng khoảng ranh giới hoặc điểm ranh giới, hệ thống tự động biện luận và phân tích số cực trị, số điểm dừng của đạo hàm, miền xác định thực tế và bậc của họ hàm số, tự động chuyển đổi các điều kiện phức tạp sang biểu thức toán học LaTeX. Tính năng này thuộc function analyzer, không phải algebra solver.
  - **Thuật toán lấy mẫu đồ thị thích ứng (Adaptive Graph Sampling):** Lấy mẫu đồ thị hàm số động dựa trên window vẽ giới hạn. Tự động chia nhỏ miền xác định thành các nhánh đồ thị liên thông độc lập, phân tích và bỏ qua các đường tiệm cận đứng và điểm kỳ dị gián đoạn, tối ưu hóa mật độ điểm lấy mẫu bằng phép chia nhỏ lưới thích ứng (Adaptive Grid Partitioning) với độ sâu giới hạn để bảo đảm đồ thị hiển thị mượt mà tại các khoảng biến thiên lớn.
- **Định tuyến và điều phối tài nguyên trí tuệ nhân tạo:**
  - **Quản lý danh mục mô hình tập trung (AI Model Registry):** Hệ thống duy trì danh sách động các nhà cung cấp trí tuệ nhân tạo (OpenRouter, Nvidia, Ollama, 9router), thông số kết nối, năng lực xử lý cụ thể của từng mô hình (nhận diện hình ảnh, phân tích logic, sinh mã) và chỉ định mô hình tương ứng cho từng tác vụ chuyên biệt.
  - **Cơ chế dự phòng lỗi (AI Provider Fallback):** Khi thực hiện cuộc gọi xử lý AI, nếu nhà cung cấp chính gặp lỗi phản hồi hoặc hết hạn mức sử dụng, hệ thống tự động chuyển hướng yêu cầu sang nhà cung cấp dự phòng đã cấu hình sẵn. Cơ chế fallback dùng in-process counter cho trạng thái provider, không dùng Redis sorted-set.
  - **Xử lý và sửa lỗi cú pháp dữ liệu sinh ra từ AI:** Dữ liệu cấu trúc trả về từ mô hình ngôn ngữ lớn được tự động kiểm tra định dạng, sửa lỗi cú pháp JSON phổ biến, chuẩn hóa dữ liệu theo lược đồ quy chuẩn và đưa qua bộ lọc an toàn trước khi biên dịch thành mô hình dựng hình.
  - **Quản lý an toàn khóa cá nhân (BYOK):** Cho phép người dùng sử dụng khóa API cá nhân. Khóa này được mã hóa bảo mật tại máy chủ, chỉ giải mã tạm thời trong bộ nhớ khi thực hiện yêu cầu tới nhà cung cấp AI và tuyệt đối không bao giờ được trả về dưới dạng văn bản thô cho client.
- **Động cơ phân tích toán học và kiểm chứng:**
  - **Bộ phân loại bài toán thông minh:** Tự động phân tích đề bài để định tuyến tới bộ giải toán phù hợp (đại số, giải tích, lượng giác, hình học).
  - **Động cơ đại số chính xác bằng SymPy:** Sử dụng thư viện tính toán ký hiệu SymPy kết hợp các thuật toán giải toán tất định để tìm ra nghiệm chính xác của phương trình, bất phương trình, ma trận, đạo hàm và tích phân.
    - *Kiểm chứng nghiệm tuần hoàn:* Logic giải các bài toán lượng giác hỗ trợ đầy đủ việc kiểm chứng và xác minh cấu trúc nghiệm tuần hoàn (ví dụ: nghiệm có chu kỳ) thay vì chỉ bó hẹp trong các tập nghiệm hữu hạn, nâng cao độ đúng đắn học thuật.
  - **Kiểm chứng hình học đa chiều:** Bộ giải hình học thực hiện suy diễn các quan hệ ẩn từ dữ kiện đã biết (ví dụ: phát hiện ba điểm thẳng hàng, hai đường thẳng vuông góc từ các mối quan hệ song song và vuông góc khác) và chạy bộ kiểm chứng hệ thống CAS (Computer Algebra System) để đảm bảo tính đúng đắn của tọa độ mô hình trước khi hiển thị.
  - **Quy trình sửa lỗi tọa độ tự động (Auto-repair):** Khi các điểm vẽ hình bị lệch nhẹ do sai số tính toán của AI, hệ thống tự động tinh chỉnh tọa độ trong phạm vi sai số cho phép để thỏa mãn hoàn toàn các ràng buộc hình học của đề bài.
- **Quy trình số hóa tài liệu tích hợp:**
  - Tích hợp dịch vụ chuyển đổi PDF tài liệu toán học sang định dạng Word có khả năng chỉnh sửa công thức thông qua API của MinerU. Cho phép người dùng tải tệp tin lên, cấu hình các tham số OCR, theo dõi tiến trình xử lý dưới dạng nhật ký luồng công việc thời gian thực, xem trước kết quả trực tiếp và tải xuống tài liệu đã số hóa.

---



### Hạng mục 4: Backend & API

- **Kiến trúc hệ thống và phân tách trách nhiệm:**
  - **FastAPI làm nền tảng máy chủ dịch vụ:** Lớp dịch vụ backend được xây dựng hoàn toàn phi trạng thái (stateless) trên nền tảng FastAPI phi đồng bộ, cho phép mở rộng quy mô dễ dàng. Trách nhiệm xử lý được phân tách rõ ràng thành các tầng: Tầng xử lý yêu cầu và kiểm tra phụ thuộc (Routing & Dependency), Tầng dịch vụ nghiệp vụ (Business Logic Services), Tầng truy xuất dữ liệu (Repositories) và Tầng ánh xạ dữ liệu (Data Schemas).
  - **Giao diện API RESTful, WebSocket cho chat và streaming:** Sử dụng chuẩn RESTful cho các dịch vụ truy vấn thông tin, thiết lập trạng thái và quản lý dữ liệu. Kết hợp giao thức WebSocket kết nối dài hạn cho luồng chat trợ giúp và streaming phản hồi AI.
- **Xử lý bất đồng bộ và tối ưu hóa luồng công việc:**
  - **Không chặn luồng chính (Non-blocking I/O):** Toàn bộ các cuộc gọi tới cơ sở dữ liệu và các dịch vụ bên ngoài (gửi email, gọi API AI, lưu trữ đám mây) đều được thực hiện thông qua cơ thức lập trình phi đồng bộ của Python (`async/await`).
  - **Phân phối tác vụ nặng chạy ngầm:** Các tác vụ tốn tài nguyên và thời gian xử lý dài (như giải toán đại số phức tạp, trích xuất OCR từ ảnh lớn, hoặc kết xuất video mô phỏng) được đưa vào hàng đợi cơ sở dữ liệu. Tiến trình worker độc lập sẽ lấy tác vụ từ hàng đợi này để xử lý riêng biệt. Người dùng truy vấn trạng thái xử lý thông qua cơ chế hỏi định kỳ (polling) nhẹ nhàng, giải phóng hoàn toàn tiến trình xử lý HTTP chính.
  - **Tối ưu hóa các tác vụ nghẽn CPU:** Các tác vụ tính toán toán học nặng trên các thư viện tất định (như biến đổi SymPy) hoặc băm mật khẩu được tự động đẩy sang luồng xử lý riêng biệt (`ThreadPoolExecutor` cho các tác vụ blocking I/O hoặc `ProcessPoolExecutor` cho các tác vụ nặng CPU) tùy thuộc vào tính chất nghẽn để tránh làm đóng băng máy chủ.
- **Xử lý lỗi hệ thống và tối ưu hóa băng thông truyền tải:**
  - **Bộ lọc ngoại lệ toàn cục (Global Exception Filters):** Mọi lỗi phát sinh trong hệ thống được bắt giữ tập trung, ghi nhật ký chi tiết kèm theo mã yêu cầu định danh duy nhất (Request ID) và trả về mã lỗi HTTP chuẩn hóa (như 400 cho dữ liệu sai, 401 cho lỗi xác thực, 429 cho quá tải tần suất, và 500 cho lỗi máy chủ). Hệ thống tuyệt đối không trả chi tiết stack trace nội bộ về phía client để tránh lộ lọt cấu trúc mã nguồn.
  - **Pydantic Schema làm chốt kiểm duyệt dữ liệu:** Định nghĩa cấu hình cấm các thuộc tính thừa (`extra='forbid'`) đối với dữ liệu yêu cầu gửi lên từ client, ngăn chặn việc tấn công thông qua gửi kèm tham số lạ.
  - **Tối ưu cấu trúc gói tin (Payload Weight Optimization):** Lược đồ phản hồi dữ liệu được giới hạn chặt chẽ bằng các lớp mô hình kiểm duyệt thuộc tính. Đối với các dữ liệu danh sách lịch sử, hệ thống chỉ trả về thông tin tóm tắt và siêu dữ liệu, chỉ tải chi tiết biểu thức toán học hoặc tọa độ hình ảnh khi người dùng yêu cầu cụ thể trên một đối tượng cụ thể.

---



### Hạng mục 5: Cơ sở dữ liệu (Database)

- **Hạ tầng lưu trữ và khả năng thích ứng đa nền tảng:**
  - **Cơ sở dữ liệu production trên DigitalOcean:** Ở môi trường chạy chính thức (production), hệ thống sử dụng cơ sở dữ liệu quan hệ mạnh mẽ PostgreSQL được lưu trữ và quản lý trực tiếp trên nền tảng đám mây DigitalOcean. Cơ sở dữ liệu được cấu hình đồng lưu trú (co-located) trong cùng một vùng phân phối vật lý (region) với cụm máy chủ ứng dụng nhằm triệt tiêu tối đa độ trễ truyền tải mạng.
  - **Hỗ trợ kiến trúc đa môi trường:**
    - *Cơ sở dữ liệu nhúng (SQLite):* Phục vụ phát triển cục bộ (local development) giúp đơn giản hóa việc thiết lập môi trường, cấu hình chế độ WAL (Write-Ahead Logging) tăng tốc độ ghi đồng thời và foreign key constraints.
    - *Cơ sở dữ liệu phân tán (Cloudflare D1, đang chuyển đổi):* Hỗ trợ thử nghiệm ban đầu, hiện đang trong quá trình chuyển đổi sang PostgreSQL làm database chính (xem `backend/scripts/migrate_d1_to_postgres.py`).
    - *Kết nối phi đồng bộ bằng asyncpg:* Lớp backend FastAPI giao tiếp với PostgreSQL trên DigitalOcean thông qua trình điều khiển phi đồng bộ kết hợp quản lý connection pool.
- **Quản lý kết nối PostgreSQL phi đồng bộ bằng asyncpg:**
  - Sử dụng thư viện `asyncpg` để thiết lập và quản lý connection pool phi đồng bộ đối với PostgreSQL với giới hạn số lượng kết nối tối thiểu và tối đa tùy biến, tránh nghẽn kết nối và giảm thiểu tài nguyên bắt tay TCP.
- **Quản lý tiến trình thay đổi lược đồ (Migration Pipeline):**
  - Hệ thống thiết lập quy trình quản lý migration cơ sở dữ liệu độc lập cho cả dòng cơ sở dữ liệu SQLite/D1 và cơ sở dữ liệu PostgreSQL. Tiến trình chạy ứng dụng tự động kiểm tra trạng thái migration hiện tại, phát hiện sự lệch pha cấu trúc và báo cáo lỗi nếu lược đồ trong cơ sở dữ liệu không khớp với mã nguồn ứng dụng.
- **Lược đồ dữ liệu chi tiết và toàn vẹn:**
Hệ thống triển khai cấu trúc cơ sở dữ liệu đầy đủ bao gồm các bảng thực thể sau:
  1. **Người dùng (Users):** Lưu trữ thông tin tài khoản, email, mật khẩu đã băm, trạng thái kích hoạt và vai trò.
  2. **Phiên làm việc (Sessions):** Mã phiên đã băm, thiết bị đăng nhập, thời gian hoạt động cuối và thời gian hết hạn.
  3. **Xác minh tài khoản (Verifications):** Mã thông báo xác minh email, khôi phục mật khẩu, mã OTP và thời gian hết hạn.
  4. **Liên kết danh tính (OAuth Identities):** Thông tin định danh từ nhà cung cấp bên thứ ba (Google) liên kết với người dùng.
  5. **Gói dịch vụ (Plans & Tier Profiles):** Định nghĩa hạn mức sử dụng và quyền lợi của từng gói dịch vụ.
  6. **Nhật ký sử dụng (Usage Events):** Theo dõi số lượng yêu cầu đã thực hiện của từng người dùng để áp dụng chính sách quota.
  7. **Lịch sử giới hạn tần suất (Rate Limit Events):** Ghi nhận các yêu cầu bị chặn do vượt quá tần suất cho phép để phân tích dấu hiệu tấn công.
  8. **Tác vụ dựng hình (Render Jobs):** Trạng thái xử lý bất đồng bộ, mã đề bài đầu vào, và thông tin lỗi nếu có.
  9. **Lịch sử dựng hình (History Items):** Siêu dữ liệu bài toán, nhãn phân loại, liên kết dự án và quyền sở hữu.
  10. **Phiên bản chỉnh sửa (Scene Revisions):** Lưu lịch sử các thay đổi tọa độ, ràng buộc của mô hình hình học do người dùng tự tay sửa đổi.
  11. **Dự án và nhãn (Projects & Tags):** Cấu trúc thư mục logic để người dùng tổ chức và phân loại các bài toán đã giải.
  12. **Lịch sử giải đại số (Algebra Histories):** Lưu trữ đề bài đại số và các bước biến đổi trung gian đã giải thành công.
  13. **Hồ sơ năng lực học tập (Learning Profiles):** Trình độ, mục tiêu và thói quen học tập cá nhân của học sinh.
  14. **Quản lý tệp tải lên (Uploaded Files):** Lưu đường dẫn tệp tin, kích thước, mã băm nội dung, nhà cung cấp lưu trữ (R2, Appwrite, Database) và trạng thái dọn dẹp.
  15. **Hộp thoại trò chuyện (Conversations & Messages):** Lưu lịch sử chat hỗ trợ, nội dung tin nhắn và siêu dữ liệu hình ảnh đính kèm.
- **Quản lý giao dịch và bảo vệ kết nối:**
  - **Giao dịch an toàn (Transactions):** Mọi thao tác ghi dữ liệu liên đới nhiều bảng được thực hiện trong phạm vi một giao dịch duy nhất để đảm bảo tính nhất quán dữ liệu, tự động hoàn trả (rollback) nếu có bất kỳ bước nào thất bại.
  - **Truy vấn an toàn chống SQL Injection:** Sử dụng cơ chế ràng buộc tham số cho mọi giá trị động trong truy vấn, ngăn chặn tuyệt đối nguy cơ tấn công tiêm mã độc SQL.
- **Chiến lược sao lưu cục bộ tự động (kế hoạch — chưa triển khai):**
  - Hệ thống hiện chưa có cơ chế sao lưu tự động. Kế hoạch dự kiến: thiết lập các tác vụ tự động chạy ngầm định kỳ hàng ngày trên máy chủ để kết xuất dữ liệu (sử dụng lệnh sao chép nóng tệp cơ sở dữ liệu đối với SQLite hoặc xuất bản SQL dump đối với PostgreSQL qua công cụ `pg_dump`). Bản kết xuất này sẽ được tự động nén dưới dạng tệp tin lưu trữ an toàn, gắn nhãn thời gian và truyền tải mã hóa sang các phân vùng lưu trữ đám mây ngoài biệt lập (ví dụ như Cloudflare R2) để đảm bảo khả năng khôi phục nhanh chóng khi xảy ra sự cố phần cứng máy chủ chính.

---



### Hạng mục 6: Bảo mật (Security)

- **Bảo vệ phiên làm việc và định danh:**
  - **Cấu hình Cookie phiên an toàn:** Mã định danh phiên đăng nhập được lưu trữ trong Cookie với các thuộc tính bảo mật cao nhất:
    - *Chỉ truyền qua HTTP (HttpOnly):* Chặn các script chạy trên trình duyệt truy cập vào cookie phiên, vô hiệu hóa nguy cơ bị tấn công đánh cắp phiên qua lỗi XSS.
    - *Chỉ truyền qua HTTPS (Secure):* Bắt buộc truyền cookie qua kết nối mã hóa TLS ở môi trường chạy chính thức, chặn bắt gói tin trên mạng.
    - *Giới hạn nguồn gốc (SameSite=Lax/Strict):* Ngăn chặn trình duyệt tự động gửi cookie phiên trong các yêu cầu xuất phát từ trang web bên thứ ba, triệt tiêu nguy cơ tấn công giả mạo yêu cầu chéo trang (CSRF).
  - **Băm mã phiên trong cơ sở dữ liệu:** Hệ thống chỉ lưu trữ mã băm một chiều của token phiên đăng nhập trong cơ sở dữ liệu, đảm bảo kẻ tấn công nếu có đọc được cơ sở dữ liệu cũng không thể sử dụng mã đó để giả mạo phiên làm việc của người dùng.
- **Cơ chế phòng vệ cổng vào ứng dụng:**
  - **Xác thực nguồn gốc yêu cầu (Origin Verification Gate):** Đối với các yêu cầu thay đổi dữ liệu (POST, PUT, DELETE), máy chủ thực hiện đối chiếu tiêu đề nguồn gốc yêu cầu với danh sách tên miền được tin tưởng đã cấu hình. Nếu không trùng khớp, yêu cầu bị từ chối ngay lập tức từ vòng ngoài.
  - **Xác thực chống Bot tự động (Turnstile Integration, tùy chọn):** Tích hợp giải pháp bảo vệ Cloudflare Turnstile tại các cổng đăng ký, đăng nhập và khôi phục mật khẩu. Chỉ active khi biến môi trường `TURNSTILE_SECRET_KEY` được cấu hình — nếu không có, Turnstile bị bỏ qua (không enforce).
  - **Bộ lọc tên miền email dùng một lần:** Chặn đứng hành vi đăng ký tài khoản rác hàng loạt bằng cách đối chiếu tên miền email đăng ký với danh sách đen chứa hàng ngàn tên miền cung cấp hòm thư ảo dùng một lần (disposable email domains).
- **Mã hóa dữ liệu nhạy cảm và nhật ký an toàn:**
  - **Mã hóa đối xứng thông tin cá nhân qua Fernet:** Các thông tin nhạy cảm của người dùng (như khóa API cá nhân) được mã hóa bằng cơ chế mã hóa đối xứng Fernet (thuộc thư viện mật mã Python Cryptography) trước khi ghi xuống đĩa cứng. Khóa mật mã được quản lý tập trung ở cấu hình máy chủ.
  - **Lọc bỏ thông tin nhạy cảm trong nhật ký hệ thống:** Bộ lọc nhật ký tự động phát hiện, cắt ngắn hoặc thay thế bằng chuỗi ký tự ẩn đối với các thông tin nhạy cảm xuất hiện trong luồng ghi log (như khóa API, mật khẩu, mã phiên làm việc, dữ liệu ảnh base64 kích thước lớn).

---



### Hạng mục 7: Hiệu năng & Mở rộng (Performance & Scalability)

- **Hạn chế và điều phối tải hệ thống (Admission Control Gates):**
  - **Cổng giới hạn tải đồng thời dựa trên Redis Sorted Sets:** Để bảo vệ tài nguyên máy chủ khỏi bị nghẽn do xử lý quá nhiều tác vụ nặng cùng lúc, hệ thống triển khai cổng kiểm soát tải đồng thời sử dụng Sorted Set của bộ nhớ đệm phân tán Redis. Mỗi tác vụ đang chạy được cấp một khóa tạm thời kèm thời gian sống (TTL).
    - *Chống kẹt tài nguyên (Deadlock Protection):* Các khóa quá hạn do worker bị sập đột ngột sẽ tự động bị xóa bỏ để giải phóng slot cho các yêu cầu mới.
    - *Tự động lùi về khóa cục bộ (Local Lock Fallback):* Nếu kết nối tới Redis bị gián đoạn, hệ thống tự động chuyển sang sử dụng cơ chế khóa phi đồng bộ `asyncio.Lock` trong bộ nhớ cục bộ của tiến trình hiện tại để đảm bảo tính sẵn sàng của dịch vụ.
- **Tối ưu hóa tài nguyên kết nối và kết xuất:**
  - **Tái sử dụng kết nối cơ sở dữ liệu:** Thiết lập connection pool mở sẵn đối với PostgreSQL để tránh thời gian bắt tay TCP mỗi khi có truy vấn. Với SQLite, hệ thống duy trì một kết nối ghi duy nhất kết hợp cơ chế khóa ghi để tránh xung đột ghi đồng thời.
  - **Tái sử dụng socket HTTP kết nối dịch vụ ngoài:** Các yêu cầu gọi tới nhà cung cấp AI hoặc dịch vụ lưu trữ đám mây được thực hiện thông qua một HTTP Client dùng chung duy nhất được cấu hình connection pool để tái sử dụng socket TCP đã mở sẵn.
- **Tối ưu hóa tài nguyên phía giao diện:**
  - **Lazy loading component giao diện (Lazy Loading & Code Splitting):** Toàn bộ các không gian làm việc lớn và các công cụ toán học nặng được tách ra thành các gói mã nguồn riêng biệt tại cấu hình biên dịch của Vite và chỉ được tải về trình duyệt của người dùng khi họ bắt đầu truy cập vào chức năng tương ứng, giảm thời gian tải trang đầu tiên của ứng dụng xuống mức tối thiểu.
  - **Cập nhật tham số hình học cục bộ:** Khi người dùng tương tác kéo thả các điểm hình học trên không gian 3D, tọa độ và các ràng buộc được tính toán và cập nhật trực tiếp trên trình duyệt bằng engine đồ họa phía client, chỉ gửi yêu cầu tính toán lên máy chủ khi người dùng thực hiện thao tác kiểm chứng chính thức.

---



### Hạng mục 8: Phân tích & Theo dõi (Analytics & Monitoring)

- **Hệ thống phân tích hành vi người dùng (Product Analytics):**
  - **Theo dõi tương tác và số lượng sử dụng:** Nhật ký hoạt động chi tiết đo lường số lượt mở (opens), số lượng người dùng duy nhất (unique users), số phiên hoạt động (sessions) nhóm theo từng tính năng, đồng thời phân tích tỷ lệ các tác vụ hoàn thành (completed outcomes) so với tác vụ thất bại.
  - **Đo lường hiệu quả phễu chuyển đổi:** Bảng điều khiển quản trị cung cấp công cụ phân tích phễu chuyển đổi từ bước đăng ký tài khoản -> xác minh email -> thực hiện lượt giải toán đầu tiên -> nâng cấp gói dịch vụ để giúp đội ngũ vận hành đánh giá và cải tiến trải nghiệm người dùng.
  - **Hiển thị biểu đồ phân tích một ngày duy nhất:** Trong trường hợp cơ sở dữ liệu hoạt động có thời gian tích lũy dữ liệu quá ngắn (dưới 2 ngày), hệ thống tự động lùi về chế độ hiển thị danh sách phân tích một ngày duy nhất sử dụng bảng màu đơn sắc tương phản cao để đảm bảo bảng điều khiển quản trị không bị lỗi vẽ biểu đồ.
- **Theo dõi lỗi hệ thống và phân tích dấu ngăn xếp (Stack Fingerprinting):**
  - **Gom nhóm lỗi thông minh:** Mọi lỗi nghiêm trọng phát sinh trên máy chủ hoặc client gửi về được gắn nhãn định danh dựa trên dấu vân tay ngăn xếp lỗi.
    - *Mã vân tay lỗi 16 ký tự ổn định:* Stack trace được lọc bỏ khoảng trắng thừa trước khi băm SHA-256, lấy 16 ký tự hex đầu tiên làm mã định danh ổn định giúp gom nhóm các lỗi giống nhau một cách chuẩn xác nhất.
- **Giám sát chi phí và hiệu năng cuộc gọi AI:**
  - **Theo dõi chi tiết số lượng token tiêu thụ:** Nhật ký cuộc gọi AI ghi nhận cụ thể số lượng token đầu vào, token đầu ra, thời gian phản hồi của nhà cung cấp và trạng thái cuộc gọi. Dữ liệu này được tổng hợp thành biểu đồ chi phí thời gian thực trên trang quản trị theo từng mô hình và từng nhà cung cấp.
- **Kiểm tra sức khỏe hệ thống đa tầng (Health Checks):**
  - **Cổng kiểm tra hoạt động cơ bản (Liveness Probe):** Một endpoint gọn nhẹ trả về mã trạng thái thành công để hệ thống giám sát hạ tầng nhận biết tiến trình ứng dụng vẫn đang hoạt động bình thường.
  - **Cổng kiểm tra sẵn sàng phục vụ (Readiness Probe):** Thực hiện kiểm tra thực tế kết nối tới cơ sở dữ liệu cục bộ và trạng thái migration. Nếu cơ sở dữ liệu bị ngắt kết nối hoặc đang bị lỗi khóa, hệ thống sẽ trả về mã lỗi dịch vụ không sẵn sàng để ngăn chặn bộ cân bằng tải phân phối lưu lượng truy cập vào máy chủ này.
  - **Trang chẩn đoán sức khỏe chuyên sâu (Health Detail):** Giao diện riêng biệt dành cho admin hiển thị chi tiết: số lượng kết nối đang hoạt động và nhàn rỗi trong connection pool cơ sở dữ liệu, số lượng tác vụ đang chiếm giữ trong cổng kiểm soát tải đồng thời, trạng thái phản hồi của từng nhà cung cấp AI và biểu đồ tần suất lỗi trong vòng 24 giờ qua. Tích hợp tùy chọn SDK của Sentry cho giám sát lỗi ứng dụng.
  - **Tác vụ giám sát cảnh báo và dọn dẹp định kỳ:** Hệ thống thiết lập worker chạy ngầm định kỳ quét qua tỷ lệ lỗi và tỷ lệ kết xuất thất bại, tự động kích hoạt thông báo cảnh báo qua webhook (generic JSON — không có Slack/Discord-specific template) khi vượt ngưỡng, đồng thời chạy tiến trình dọn dẹp dữ liệu nhật ký cũ quá hạn để giải phóng bộ nhớ.

---



### Hạng mục 9: Vận hành & Cập nhật (Operations & Update / CI/CD)

- **Quy trình tích hợp tự động hóa (Continuous Integration):**
  - **Tự động hóa kiểm thử mã nguồn:** Mỗi khi có yêu cầu tích hợp mã nguồn mới, hệ thống tự động kích hoạt luồng công việc kiểm tra trên GitHub Actions: chạy toàn bộ bộ kiểm thử đơn vị của máy chủ dịch vụ bằng pytest, thực hiện biên dịch mã nguồn giao diện để phát hiện lỗi kiểu dữ liệu và chạy thử quy trình xây dựng container để đảm bảo tệp tin ảnh máy ảo không bị lỗi đóng gói.
- **Đóng gói container khép kín và phân phối:**
  - **Quy trình xây dựng ảnh máy ảo nhiều giai đoạn (Multi-stage Docker Build):** Giai đoạn đầu tiên sử dụng môi trường Node để biên dịch và tối ưu hóa tài nguyên giao diện người dùng thành các tệp tin tĩnh. Giai đoạn thứ hai sử dụng môi trường Python để cài đặt mã nguồn backend, sau đó sao chép các tệp tin giao diện tĩnh vào thư mục phục vụ của máy chủ web nội bộ.
  - **Quản lý tiến trình trong container:** Sử dụng Supervisord để quản lý và khởi chạy song song tiến trình Uvicorn phục vụ API và tiến trình python worker xử lý tác vụ dựng hình ngầm dưới quyền hạn của người dùng không có đặc quyền quản trị (non-root user) nhằm tăng cường bảo mật.
- **Triển khai không gián đoạn dịch vụ (Zero-downtime Deployment):**
  - Khi đẩy phiên bản mã nguồn ổn định lên nhánh triển khai chính thức, nền tảng đám mây tự động thực hiện quy trình rolling update sử dụng máy chủ web Nginx làm reverse proxy. Container mới sẽ được khởi động và chạy các bước kiểm tra sẵn sàng phục vụ (Readiness Probes). Chỉ khi container mới báo cáo hoàn toàn khỏe mạnh, hệ thống cân bằng tải mới bắt đầu chuyển lưu lượng truy cập từ container cũ sang container mới và tắt container cũ, đảm bảo người dùng không gặp bất kỳ gián đoạn nào trong quá trình cập nhật phiên bản.
- **Quy trình khôi phục nhanh khi xảy ra sự cố** 
  - **Khôi phục phiên bản tức thời:** Kế hoạch: quản trị viên có thể thực hiện khôi phục tức thì về phiên bản ổn định trước đó ngay trên bảng điều khiển đám mây bằng cách tái kích hoạt ảnh container cũ. Hiện tại chưa có cơ chế tự động — rollback thủ công qua Git + redeploy.

---



### Hạng mục 10: Chất lượng sản phẩm (Product Quality)

- **Giải quyết triệt để bài toán thực tế của ngành giáo dục:**
  - **Trực quan hóa hình học không gian và giải tích:** Sản phẩm giải quyết bài toán khó khăn nhất trong việc dạy và học toán: sự thiếu hụt tư duy trực quan không gian. Bằng cách tự động chuyển đổi các đề bài hình học hoặc biểu thức giải tích từ dạng chữ viết thô sơ sang mô hình 3D tương tác đa chiều, hệ thống giúp học sinh hiểu sâu sắc bản chất toán học thay vì học vẹt.
  - **Số hóa tài liệu dạy học nhanh chóng:** Giảm thiểu tối đa thời gian biên soạn của giáo viên. Thay vì mất hàng giờ tự vẽ hình trên các công cụ vẽ vector truyền thống, giáo viên chỉ cần chụp ảnh đề bài để nhận về sơ đồ hình vẽ chính xác và mã nguồn đồ họa chất lượng cao chỉ trong vài giây.
- **Xác định rõ ràng đối tượng phục vụ:**
  - **Học sinh:** Sử dụng hệ thống để kiểm tra kết quả bài tập tự luyện, xem các bước biến đổi chi tiết để học phương pháp giải toán, xoay mô hình 3D để hiểu cấu trúc các khối đa diện phức tạp và tương tác với các mô phỏng giải tích để nắm bắt khái niệm trừu tượng.
  - **Giáo viên:** Tiết kiệm thời gian soạn bài bằng cách chụp ảnh đề bài để hệ thống tự động sinh hình minh họa, tùy chỉnh sơ đồ và xuất hình vẽ chất lượng cao để chèn vào đề thi.
  - **Tác giả và nhà xuất bản tài liệu học thuật:** Sử dụng tính năng xuất mã đồ họa vector chất lượng cao (như định dạng TikZ) để tích hợp trực tiếp vào quy trình dàn trang tài liệu chuyên nghiệp mà không bị vỡ nét hình ảnh.
- **Hệ thống kiểm thử tự động toàn diện bằng pytest:**
  - Kho mã nguồn tích hợp bộ kiểm thử tự động đồ sộ sử dụng khung kiểm thử pytest bao phủ toàn diện từ luồng xác thực tài khoản, kiểm tra bảo mật, logic nghiệp vụ của các bộ giải toán đại số, tính đúng đắn của động cơ suy diễn quan hệ hình học, chất lượng các bộ lọc chuẩn hóa dữ liệu, đến khả năng ghi nhận sự kiện của hệ thống phân tích đo lường.
    - *Kiểm thử tính đúng đắn toán học sâu:* Tích hợp các bộ kiểm thử chuyên sâu về logic tuần hoàn của hàm lượng giác, kiểm thử các trường hợp biên của biện luận tham số họ hàm số và kiểm chứng phân tích miền xác định.
- **Lộ trình phát triển thực tế và bền vững:**
  - **Giai đoạn 1: Đo lường chất lượng toán học bằng dữ liệu thực nghiệm:** Thiết lập hệ thống đo lường độ phủ của kịch bản kiểm thử mã nguồn trên từng phân hệ cụ thể. Xây dựng bộ bài toán mẫu chuẩn hóa tiếng Việt với đầy đủ các dạng đề thi tốt nghiệp trung học phổ thông để chạy kiểm tra độ chính xác của mô hình định kỳ, phát hiện sớm các trường hợp suy luận sai lệch.
  - **Giai đoạn 2: Cải tiến logic hình học và hệ thống CAS:** Mở rộng năng lực của bộ giải hình học để nhận diện được các quan hệ phức tạp hơn (như các ràng buộc đồng quy, tiếp xúc, hoặc quỹ tích chuyển động). Tích hợp sâu hơn các thư viện toán học tất định để thay thế các suy luận không chắc chắn của AI ở các khâu tính toán số học cơ bản.
  - **Giai đoạn 3: Tối ưu hóa mô hình AI chuyên sâu (Fine-tuning):** Thu thập và làm sạch hàng chục ngàn mẫu đề bài toán học tiếng Việt kèm theo mã cấu trúc dựng hình và lời giải chuẩn mực đã được kiểm duyệt bởi các chuyên gia giáo dục. Tiến hành tinh chỉnh (fine-tune) các mô hình ngôn ngữ lớn mã nguồn mở có quy mô phù hợp để chạy độc lập trên hạ tầng máy chủ GPU tự chủ, giảm thiểu sự phụ thuộc vào các dịch vụ API bên ngoài và tối ưu hóa chi phí vận hành lâu dài.
  - **Giai đoạn 4: Thiết lập cụm máy chủ worker độc lập:** Khi quy mô người dùng tăng trưởng, tiến hành tách biệt hoàn toàn tiến trình worker xử lý tác vụ dựng hình và OCR ra các máy ảo chuyên dụng độc lập có khả năng tự động tăng giảm số lượng dựa trên độ dài của hàng đợi công việc, đảm bảo thời gian phản hồi cho người dùng luôn ổn định dưới ngưỡng tiêu chuẩn.

