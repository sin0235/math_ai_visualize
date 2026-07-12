# BÁO CÁO THUYẾT MINH NĂNG LỰC VÀ KẾT QUẢ TRIỂN KHAI HỆ THỐNG AI MATH RENDERER

## 1. Mục đích và phạm vi báo cáo

Báo cáo trình bày kết quả xây dựng và triển khai hệ thống AI Math Renderer — nền tảng hỗ trợ tiếp nhận đề toán, phân tích nội dung, hình thành mô hình toán học có cấu trúc, trực quan hóa kết quả và cung cấp các công cụ phục vụ học tập, giảng dạy, biên soạn học liệu.

Phạm vi đánh giá bao quát toàn bộ chuỗi hoạt động của sản phẩm, từ giao diện người dùng, trải nghiệm tương tác, logic nghiệp vụ, dịch vụ backend và cơ sở dữ liệu PostgreSQL đến bảo mật, hiệu năng, theo dõi vận hành, quy trình cập nhật và chất lượng đầu ra. Việc đánh giá không dừng ở sự hiện diện của từng chức năng riêng lẻ, mà tập trung xem xét mức độ liên kết giữa các thành phần, tính nhất quán của dữ liệu và khả năng duy trì trạng thái xuyên suốt quá trình xử lý.

Mỗi nhận định trong báo cáo được giới hạn trong phạm vi năng lực đã được thể hiện bằng mã nguồn, hành vi vận hành, dữ liệu hệ thống hoặc kết quả kiểm thử. Hồ sơ kiểm chứng được tổ chức riêng theo mã minh chứng, phiên bản mã nguồn, môi trường thực hiện và tiêu chí kết luận. Cách tổ chức này giữ cho báo cáo có tính thuyết minh, đồng thời bảo đảm từng nội dung đều có căn cứ kỹ thuật để đối chiếu độc lập.

---

## 2. Kiến trúc và nguyên lý vận hành tổng thể

AI Math Renderer được xây dựng theo kiến trúc phân lớp, trong đó mỗi lớp đảm nhiệm một nhóm trách nhiệm rõ ràng và trao đổi với nhau thông qua dữ liệu có cấu trúc.

| Lớp hệ thống | Trách nhiệm | Đầu vào chủ yếu | Kết quả tạo ra |
| --- | --- | --- | --- |
| Giao diện tương tác | Tiếp nhận đề bài, phản ánh trạng thái xử lý, hiển thị và chỉnh sửa kết quả | Văn bản, hình ảnh, lựa chọn bộ dựng hình, thao tác người dùng | Yêu cầu có cấu trúc và trạng thái trình bày trên trình duyệt |
| API và điều phối nghiệp vụ | Xác thực yêu cầu, áp dụng chính sách sử dụng, lựa chọn luồng xử lý | Yêu cầu HTTP hoặc WebSocket đã được kiểm tra | Phản hồi chuẩn hóa hoặc tác vụ xử lý nền |
| Phân tích toán học và xử lý scene | Trích xuất dữ kiện, chuẩn hóa, kiểm chứng quan hệ và tạo dữ liệu dựng hình | Đề bài, biểu thức toán học hoặc scene đã chỉnh sửa | Scene có trạng thái chất lượng và dữ liệu dành cho renderer |
| Dữ liệu và xử lý nền | Lưu trạng thái lâu dài, bảo đảm giao dịch và thực thi tác vụ bất đồng bộ | Tài khoản, phiên, lịch sử, tác vụ, số liệu vận hành | Bản ghi nhất quán và kết quả xử lý được lưu bền vững |
| Hạ tầng phục vụ | Đóng gói ứng dụng, phân phối lưu lượng, kiểm tra sức khỏe và cập nhật phiên bản | Container, cấu hình môi trường và tín hiệu giám sát | Dịch vụ có thể triển khai, kiểm tra và vận hành tập trung |

Trong luồng dựng hình điển hình, đề bài được tiếp nhận từ giao diện dưới dạng văn bản hoặc ảnh. Sau bước xác định người dùng, hạn mức và cấu hình xử lý, nội dung toán học được chuyển thành scene có cấu trúc. Scene này lần lượt đi qua các bước kiểm tra dữ liệu, sửa chữa trong phạm vi an toàn, kiểm chứng quan hệ toán học, chuẩn hóa tọa độ và đánh giá mức độ tương thích với bộ dựng hình. Chỉ sau chuỗi xử lý đó, hệ thống mới hình thành dữ liệu hiển thị dành cho GeoGebra hoặc Three.js.

Kết quả trả về không chỉ chứa hình ảnh hoặc mô hình trực quan. Cùng với scene, hệ thống cung cấp nguồn sinh dữ liệu, cảnh báo, báo cáo kiểm tra cấu trúc, báo cáo kiểm chứng quan hệ, thông tin sửa chữa và trạng thái cần người dùng xác nhận. Nhờ đó, giao diện có đủ căn cứ để phân biệt kết quả đã được kiểm chứng với hình minh họa có giả định, thay vì suy đoán chất lượng từ một thông báo chung.

Đối với tác vụ kéo dài, yêu cầu được ghi nhận thành render job trong PostgreSQL. Worker xử lý tác vụ độc lập với vòng đời của kết nối HTTP, cập nhật tuần tự các trạng thái chờ xử lý, đang xử lý, hoàn tất hoặc thất bại, sau đó lưu kết quả trở lại hệ thống lịch sử. Thiết kế này duy trì tính liên tục của công việc ngay cả khi người dùng không giữ kết nối mạng trong suốt quá trình dựng hình.

Kiến trúc trên tạo ra ranh giới cần thiết giữa ba hoạt động vốn có bản chất khác nhau: AI đề xuất cấu trúc, thuật toán kiểm tra tính hợp lệ và renderer biểu diễn kết quả. Sự phân tách này là nền tảng để hệ thống vừa khai thác khả năng diễn giải linh hoạt của mô hình AI, vừa duy trì cơ chế kiểm soát bằng logic tất định trước khi cung cấp kết quả cho người dùng.

---

## 3. Kết quả triển khai theo các tiêu chí đánh giá

### 3.1. Giao diện người dùng

Giao diện được phát triển bằng React 18, TypeScript và Vite theo mô hình ứng dụng một trang. Bố cục chính duy trì vùng nhập đề, khu vực hiển thị kết quả và nhóm công cụ liên quan trong cùng một không gian làm việc. Hệ thống sử dụng ngôn ngữ trình bày thống nhất giữa các chức năng dựng hình, khảo sát hàm số, giải đại số và mô phỏng, qua đó hạn chế cảm giác rời rạc khi người dùng chuyển đổi giữa các loại bài toán.

Cấu trúc giao diện được phân chia theo trách nhiệm. Vùng nhập quản lý đề bài, ảnh và trạng thái gửi; vùng kết quả tiếp nhận scene cùng dữ liệu dựng hình đã được chuẩn hóa; khu vực thông báo phản ánh lỗi, cảnh báo và trạng thái nghiệp vụ mà không làm gián đoạn nội dung chính. Các không gian chức năng lớn được tách thành module độc lập và chỉ tải khi được mở, giúp trang khởi đầu không phải tiếp nhận toàn bộ tài nguyên của ứng dụng.

Nội dung toán học được biểu diễn phù hợp với bản chất của từng loại dữ liệu. Công thức và lời giải được trình bày bằng KaTeX để giữ cấu trúc ký hiệu. Hình học phẳng và hình học không gian được chuyển đến GeoGebra 2D, GeoGebra 3D hoặc Three.js theo đặc điểm của scene. Các mô hình Three.js cho phép xoay, phóng to và thu nhỏ để quan sát không gian; các scene hình học hỗ trợ tương tác với điểm, đoạn và đối tượng liên quan. Đối với khảo sát hàm số, đồ thị được đặt trong mối liên hệ với miền xác định, chiều biến thiên, cực trị và tiệm cận. Đối với giải đại số, hệ thống trình bày tiến trình biến đổi theo từng bước thay vì chỉ cung cấp đáp số cuối cùng.

Khả năng thích ứng theo thiết bị cũng được xem xét trong tổ chức giao diện. Khi không gian hình học được mở trên màn hình hẹp, hệ thống đưa ra đề xuất xoay ngang nhằm cải thiện vùng quan sát, đồng thời vẫn bảo toàn quyền tiếp tục sử dụng theo chiều dọc. Các trạng thái tải được biểu diễn tại đúng khu vực đang chờ dữ liệu, tránh làm người dùng hiểu rằng toàn bộ ứng dụng đã ngừng phản hồi.

Nhờ cách tổ chức trên, nhiều dạng đầu ra — công thức, lời giải, đồ thị, hình 2D, mô hình 3D và mô phỏng — được tích hợp trong cùng một hệ thống tương tác. Đây là cơ sở để sản phẩm phục vụ liên tục từ bước tiếp nhận bài toán đến bước quan sát và khai thác kết quả.

### 3.2. Trải nghiệm người dùng

Trải nghiệm sử dụng được thiết kế thành một hành trình liền mạch gồm nhập đề, theo dõi quá trình xử lý, đánh giá kết quả, hiệu chỉnh, xác nhận, lưu trữ và tái sử dụng. Mỗi giai đoạn có trạng thái giao diện tương ứng, giúp người dùng nhận biết rõ hệ thống đang chờ dữ liệu, đang đọc ảnh, đang dựng hình, đã tạo kết quả hay đang cần thêm quyết định xác nhận.

Ở bước nhập liệu, người dùng có thể gõ đề, lựa chọn đề mẫu, tải ảnh, kéo thả ảnh hoặc dán ảnh trực tiếp từ clipboard. Bộ đếm ký tự giúp quan sát quy mô nội dung trước khi gửi. Tùy chọn renderer cho phép định hướng phương thức biểu diễn mà không buộc người dùng phải sửa lại đề bài. Với dữ liệu ảnh, trạng thái nhận dạng nội dung được tách khỏi trạng thái dựng hình, nhờ đó tiến trình xử lý được truyền đạt rõ ràng hơn.

Trong thời gian hệ thống thực hiện OCR hoặc dựng hình, vùng nhập và nút gửi được tạm khóa; spinner và thông điệp trạng thái thay đổi theo công đoạn đang diễn ra. Cơ chế này vừa ngăn phát sinh yêu cầu trùng do thao tác lặp, vừa duy trì mối liên hệ trực quan giữa dữ liệu đã gửi và kết quả đang chờ nhận.

Kết quả trực quan luôn đi kèm thông tin về mức độ tin cậy. Kết quả đáp ứng điều kiện kiểm chứng được nhận diện là hình dựng theo dữ kiện. Trường hợp có giả định, thiếu dữ kiện, sử dụng nguồn dự phòng, chỉ được kiểm chứng một phần hoặc không hoàn toàn tương thích với renderer sẽ được trình bày như hình minh họa và kèm cảnh báo phù hợp. Việc phân biệt này có ý nghĩa sư phạm quan trọng: người học được biết khi nào có thể dựa vào quan hệ đã kiểm chứng và khi nào hình ảnh chỉ có vai trò hỗ trợ quan sát.

Khi kết quả cần sự chấp thuận, giao diện duy trì trạng thái xác nhận riêng thay vì mặc nhiên coi dữ liệu do hệ thống sinh ra là kết quả cuối cùng. Quyết định xác nhận của người dùng được lưu cùng trạng thái hiện tại và tham gia điều kiện xuất kết quả. Vì vậy, thao tác xác nhận mang ý nghĩa nghiệp vụ thực chất, tạo ranh giới giữa kết quả được đề xuất và kết quả đã được người dùng chấp thuận để tiếp tục sử dụng.

Các công cụ chỉnh scene cho phép di chuyển điểm, nối đoạn, chiếu điểm lên đoạn và bổ sung điểm. Thay đổi được phản ánh ngay tại trình duyệt để bảo đảm cảm giác tương tác liên tục. Sau đó, scene được chuyển sang trạng thái chờ kiểm chứng lại trên máy chủ; dữ liệu dành cho Three.js hoặc GeoGebra được đồng bộ theo cấu trúc mới. Cách tổ chức này kết hợp tốc độ phản hồi cục bộ với yêu cầu kiểm tra nhất quán trước khi lưu phiên bản chỉnh sửa.

Đối với người dùng đã đăng nhập, lịch sử lưu giữ đề bài, scene và renderer tương ứng. Người dùng có thể mở lại kết quả, đánh dấu yêu thích, lưu trữ, bỏ lưu trữ hoặc xóa mục không còn nhu cầu. Chức năng này biến mỗi lần xử lý từ một kết quả tức thời thành một tài nguyên học tập có thể tiếp tục khai thác trong các phiên sau.

Không gian mô phỏng trình bày nội dung theo từng bước và đồng bộ số thứ tự, tiến độ, nhiệm vụ học tập cùng hình ảnh tương tác. Các điều khiển chạy, tạm dừng, lùi, tiến, đặt lại, điều chỉnh tốc độ và khám phá tự do cho phép người học chủ động thay đổi nhịp độ quan sát. Do nội dung giải thích và mô hình cùng xuất hiện trong một workspace, mỗi thao tác điều khiển luôn gắn với ý nghĩa toán học của bước đang xét.

Phản hồi hệ thống được trình bày bằng thông điệp tiếng Việt theo ngữ cảnh và công bố qua vùng `aria-live`. Những lỗi kỹ thuật phổ biến được chuyển thành nội dung có ý nghĩa sử dụng như quá tải, hết hạn mức, dữ liệu không hợp lệ hoặc dịch vụ tạm thời không sẵn sàng. Thông báo có thể tự đóng, đóng chủ động và cung cấp hành động tiếp theo khi cần, nhưng không đưa chi tiết nội bộ không cần thiết ra giao diện.

### 3.3. Logic ứng dụng

Logic ứng dụng được tổ chức thành ba miền chính: chính sách người dùng, điều phối mô hình AI và xử lý toán học tất định. Sự phân chia này giúp mỗi quy tắc được đặt tại đúng phạm vi trách nhiệm, tránh trộn lẫn quản lý tài khoản, lựa chọn nhà cung cấp AI và thuật toán toán học trong cùng một chuỗi xử lý.

Miền chính sách người dùng bao gồm đăng ký, xác minh email, đăng nhập, Google OAuth 2.0, đặt lại mật khẩu, đổi mật khẩu và quản lý phiên hoạt động. Phiên đăng nhập gắn với người dùng và thông tin thiết bị, cho phép thu hồi một phiên cụ thể hoặc các phiên còn lại. Quota theo gói kiểm soát tổng quyền sử dụng; rate limit kiểm soát tần suất yêu cầu trong khoảng thời gian ngắn; cơ chế khóa tạm thời phản ứng với chuỗi đăng nhập sai. Ba cơ chế được tách biệt vì giải quyết ba loại rủi ro khác nhau: mức sử dụng, tải tức thời và hành vi dò mật khẩu.

Miền AI duy trì danh mục nhà cung cấp, mô hình và khả năng tương ứng với từng loại tác vụ. Hệ thống có thể lựa chọn mô hình theo công việc, sử dụng khóa dịch vụ do hệ thống quản lý hoặc khóa riêng do người dùng cung cấp, đồng thời chuyển sang nguồn tiếp theo theo chuỗi fallback được cấu hình. Tuy nhiên, phản hồi từ mô hình chỉ được xem là dữ liệu đầu vào cho bước xử lý tiếp theo; cấu trúc JSON phải được hiệu chỉnh, chuẩn hóa theo schema và kiểm tra trước khi được chuyển thành scene.

Pipeline scene giữ vai trò trung tâm trong kiểm soát chất lượng dựng hình. Scene trước hết được gắn thông tin nguồn sinh để duy trì khả năng truy vết. Validator tiếp tục phát hiện lỗi cấu trúc, cảnh báo và những sửa chữa có thể thực hiện trong phạm vi an toàn. Khối kiểm chứng đánh giá các quan hệ hình học; báo cáo sửa chữa xác định trường hợp cần người dùng chấp thuận. Sau đó, scene được chuẩn hóa tọa độ, đánh giá khả năng tương thích và chuyển thành dữ liệu hiển thị cho renderer tương ứng.

Trạng thái kết quả được mô hình hóa rõ ràng. `verified` biểu thị kết quả đáp ứng điều kiện kiểm tra; `partially_verified` biểu thị mức kiểm chứng chưa đầy đủ; `needs_confirmation` được sử dụng khi tồn tại nguồn dự phòng, giả định hoặc sửa chữa cần chấp thuận; `fallback` nhận diện kết quả được hình thành từ phương án dự phòng; `failed` phản ánh trường hợp scene hoặc renderer không thể tạo đầu ra hợp lệ. Đi kèm trạng thái chính là các báo cáo validation, verification, repair và compatibility, nhờ đó mọi quyết định hiển thị đều dựa trên dữ liệu có cấu trúc.

Khối toán học tất định sử dụng SymPy cùng các thuật toán chuyên biệt để xử lý phương trình, bất phương trình, lượng giác, dãy số, ma trận, đạo hàm, tích phân và bài toán tham số. Function Analyzer thực hiện chuẩn hóa biểu thức, xác định miền xác định, tìm nghiệm và điểm tới hạn, phân tích chiều biến thiên, cực trị, tiệm cận, đồng thời lấy mẫu đồ thị trên từng khoảng liên thông. Kết quả vì vậy không chỉ phục vụ vẽ đồ thị mà còn cung cấp dữ liệu cần thiết cho bảng biến thiên và phần diễn giải toán học.

Các định dạng xuất cùng sử dụng scene và trạng thái chất lượng làm nguồn dữ liệu thống nhất. PNG, JPG, SVG, HTML KaTeX, TikZ, PDF và GeoGebra không được tạo từ những luồng nội dung tách rời, qua đó giảm nguy cơ sai khác giữa kết quả người dùng đang quan sát và nội dung được đưa vào học liệu.

### 3.4. Backend và API

Backend được phát triển bằng FastAPI trên Python 3.11 và phân tách theo các lớp route, dependency, service, repository và schema. Route chịu trách nhiệm về giao thức HTTP; dependency cung cấp người dùng, kết nối dữ liệu và điều kiện truy cập; service thực thi nghiệp vụ; repository quản lý thao tác lưu trữ; schema xác định cấu trúc dữ liệu vào ra. Ranh giới này cho phép cùng một nghiệp vụ được sử dụng bởi request trực tiếp hoặc worker mà không phải xây dựng hai pipeline khác nhau.

Các nhóm API phục vụ xác thực, dựng hình, OCR, giải toán, khảo sát hàm số, lịch sử, xuất file, cấu hình cá nhân, quản trị và telemetry. REST được sử dụng cho các tác vụ có vòng đời request–response rõ ràng; WebSocket phục vụ luồng chat cần truyền phản hồi theo thời gian thực. Mỗi nhóm được đăng ký qua router riêng, giúp phạm vi chức năng và chính sách truy cập được xác định minh bạch.

Tại biên hệ thống, Pydantic kiểm tra kiểu dữ liệu, trường bắt buộc và cấu trúc lồng nhau trước khi request đi vào tầng nghiệp vụ. Lỗi validation của Analyzer được chuẩn hóa thành mã lỗi, công đoạn phát sinh, khả năng thử lại và correlation ID. Lỗi nghiệp vụ giữ nguyên thông tin cần thiết cho client; lỗi máy chủ được ghi nhận nội bộ và trả về thông điệp tổng quát, không công bố stack trace hoặc đường dẫn nội bộ.

Mỗi request được gắn `X-Request-Id`, sử dụng giá trị hợp lệ từ client hoặc sinh mới tại server. Mã này được duy trì trong ngữ cảnh xử lý, trả lại qua response header và liên kết với bản ghi lỗi. Nhờ vậy, một phản hồi quan sát trên trình duyệt có thể được đối chiếu với log và dữ liệu theo dõi mà không cần đưa thông tin nội bộ vào thông báo người dùng.

Render có thể được thực hiện trực tiếp hoặc qua hàng đợi nền. Với luồng trực tiếp, API gọi pipeline và trả kết quả trong cùng request. Với luồng bất đồng bộ, yêu cầu cùng cấu hình renderer và runtime được lưu trong PostgreSQL; API trả job ID để giao diện theo dõi các trạng thái `queued`, `running`, `completed` hoặc `failed`.

Worker nhận quyền xử lý job thông qua thao tác cập nhật có điều kiện. Việc chuyển từ `queued` sang `running` chỉ thành công nếu bản ghi vẫn đang ở trạng thái chờ, qua đó ngăn nhiều worker cùng thực thi một tác vụ. Worker khôi phục request đã lưu, kiểm tra người dùng, chiếm capacity slot, chạy pipeline với giới hạn thời gian và ghi kết quả hoặc lỗi trở lại database. Nếu tài nguyên xử lý đang đạt giới hạn, job được đưa về trạng thái chờ thay vì bị kết luận thất bại.

PostgreSQL là nguồn trạng thái bền vững của hàng đợi. Khi Redis được cấu hình, Redis cung cấp tín hiệu đánh thức worker để giảm thời gian polling; quyền sở hữu và trạng thái cuối cùng của job vẫn được xác định bằng bản ghi PostgreSQL. Cách phân vai này giúp tối ưu thời gian phản hồi mà không đánh đổi tính nhất quán của tác vụ.

### 3.5. Cơ sở dữ liệu PostgreSQL

Hệ thống production sử dụng PostgreSQL 16 được quản lý trên DigitalOcean. Backend kết nối bất đồng bộ qua `asyncpg`, duy trì connection pool dùng chung trong vòng đời mỗi tiến trình và đóng pool khi ứng dụng kết thúc. Cơ chế pool giúp tái sử dụng kết nối, kiểm soát tổng số phiên đồng thời và giảm chi phí thiết lập kết nối mới cho từng request.

Lược đồ dữ liệu được tổ chức theo miền nghiệp vụ. Nhóm định danh quản lý người dùng, phiên, xác minh email, OAuth và trạng thái bảo vệ đăng nhập. Nhóm quyền sử dụng quản lý gói, đăng ký dịch vụ và quota. Nhóm học tập và toán học quản lý render job, lịch sử dựng hình, phiên bản scene, lịch sử đại số, lịch sử phân tích hàm, hồ sơ học tập và liên kết chia sẻ. Nhóm AI và vận hành lưu danh mục mô hình, khả năng mô hình, số liệu cuộc gọi AI, hoạt động người dùng và sự kiện lỗi.

Các quan hệ khóa ngoại duy trì vòng đời dữ liệu giữa người dùng và các bản ghi phụ thuộc. Render job lưu riêng yêu cầu, thiết lập nâng cao, cấu hình runtime, trạng thái, thời điểm bắt đầu, thời lượng, kết quả và lỗi. Việc lưu đồng thời đầu vào và đầu ra cho phép worker xử lý độc lập với request ban đầu, đồng thời tạo lịch sử sau khi tác vụ kết thúc.

Scene được quản lý theo phiên bản thay vì chỉ ghi đè lên một dữ liệu duy nhất. Khi chỉnh sửa được kiểm chứng và chấp nhận, phiên bản mới được liên kết với mục lịch sử tương ứng. Mô hình này duy trì mối quan hệ giữa đề bài, kết quả ban đầu và trạng thái sau hiệu chỉnh, giúp thao tác mở lại khôi phục đúng renderer cùng dữ liệu hình học đã lưu.

Các migration PostgreSQL được áp dụng trong vòng đời khởi động ứng dụng và ghi nhận trong bảng quản lý phiên bản schema. Readiness kiểm tra đồng thời khả năng truy cập database và trạng thái migration, nên một tiến trình đang phản hồi nhưng sử dụng lược đồ không phù hợp sẽ không được coi là sẵn sàng phục vụ. Truy vấn nghiệp vụ sử dụng tham số thay cho ghép trực tiếp dữ liệu đầu vào; những thao tác ghi nhiều bước được đặt trong transaction để tránh trạng thái dở dang.

Cơ chế sao lưu production do DigitalOcean Managed PostgreSQL cung cấp. Ứng dụng chịu trách nhiệm về tính nhất quán của lược đồ, giao dịch và trạng thái dữ liệu; nền tảng cơ sở dữ liệu chịu trách nhiệm lưu bản sao theo chính sách vận hành. Sự phân tách này làm rõ phạm vi trách nhiệm giữa phần mềm nghiệp vụ và dịch vụ dữ liệu được quản lý.

### 3.6. Bảo mật

Bảo mật được triển khai theo nhiều lớp, tương ứng với vòng đời của một yêu cầu: bảo vệ thông tin xác thực, bảo vệ phiên, kiểm soát nguồn request, hạn chế hành vi lạm dụng, bảo vệ bí mật dịch vụ và kiểm soát dữ liệu được ghi nhận trong vận hành.

Mật khẩu được băm bằng Bcrypt trước khi lưu. Session token, token xác minh và OAuth state được lưu dưới dạng băm, nhờ đó giá trị trong database không thể trực tiếp được sử dụng như bearer token. Cookie phiên trên production áp dụng các thuộc tính `HttpOnly`, `Secure` và `SameSite`, lần lượt hạn chế truy cập từ JavaScript, yêu cầu truyền qua HTTPS và giảm request chéo ngữ cảnh ngoài ý muốn.

Các request thay đổi dữ liệu được đối chiếu Origin với danh sách miền tin cậy. CORS kiểm soát miền trình duyệt được phép trao đổi với API, trong khi kiểm tra Origin bảo vệ hành động làm thay đổi trạng thái. Quyền truy cập endpoint vẫn được xác định bằng xác thực và dependency phân quyền, không dựa trên việc chức năng có xuất hiện trên giao diện hay không.

Rate limit được áp dụng theo tài khoản hoặc địa chỉ IP tùy ngữ cảnh; quota kiểm soát tổng quyền sử dụng theo gói; cơ chế khóa tạm thời phản ứng với chuỗi đăng nhập sai. Upload chịu giới hạn kích thước và validation tại biên. Cấu hình proxy tin cậy quy định trường hợp backend được phép sử dụng header chuyển tiếp để xác định địa chỉ client, tránh coi dữ liệu header tùy ý là nguồn định danh đáng tin cậy.

Khóa API do người dùng cung cấp được mã hóa bằng Fernet trước khi lưu trong PostgreSQL. API quản lý khóa chỉ trả trạng thái cấu hình và phần ký tự nhận diện cuối, không trả lại plaintext. Khóa giải mã được đặt trong cấu hình bí mật của môi trường triển khai, tách khỏi dữ liệu nghiệp vụ.

Trước khi log hoặc error event được ghi, các trường nhạy cảm như mật khẩu, token, API key và payload ảnh dung lượng lớn được loại bỏ hoặc che giá trị. Endpoint quản trị và health detail yêu cầu quyền phù hợp; liveness và readiness chỉ công bố lượng thông tin cần thiết cho hạ tầng điều phối. Nhờ đó, khả năng quan sát hệ thống được duy trì mà không mở rộng không cần thiết bề mặt công bố dữ liệu.

### 3.7. Hiệu năng và khả năng mở rộng

Chiến lược hiệu năng được triển khai theo ba tầng: giảm tài nguyên tải ban đầu trên trình duyệt, tái sử dụng tài nguyên I/O ở backend và giới hạn công việc nặng bằng capacity gate kết hợp hàng đợi xử lý nền.

Frontend áp dụng code splitting đối với các workspace lớn. Mã của quản trị, khảo sát hàm số, giải đại số, mô phỏng, GeoGebra Lab và các công cụ chuyên biệt chỉ được tải khi người dùng mở chức năng tương ứng. Trong quá trình chỉnh scene, phép biến đổi tọa độ và cập nhật dữ liệu hiển thị được thực hiện cục bộ để thao tác không phải chờ một request mạng ở từng chuyển động; máy chủ tập trung vào kiểm chứng và lưu trạng thái.

Backend duy trì pool kết nối PostgreSQL và HTTP client dùng chung cho các dịch vụ ngoài. Việc tái sử dụng tài nguyên giảm số lần thiết lập kết nối và cho phép đặt giới hạn phù hợp với từng tiến trình. Những thao tác blocking hoặc tính toán nặng được chuyển khỏi event loop khi phù hợp, giúp API tiếp tục tiếp nhận request trong khi công việc chuyên sâu được xử lý ở ngữ cảnh khác.

Capacity gate giới hạn số tác vụ render, OCR và đại số được thực hiện đồng thời. Cơ chế này bảo vệ CPU, số kết nối và lượng lời gọi đến dịch vụ ngoài trước các đợt tải tăng nhanh. Khi Redis được cấu hình, trạng thái capacity có thể được phối hợp giữa các tiến trình; trường hợp không nhận được slot được xử lý thành một trạng thái có chủ đích thay vì để công việc tiếp tục vượt giới hạn tài nguyên.

Hàng đợi render tách thời gian sống của tác vụ khỏi kết nối HTTP. API chịu trách nhiệm xác thực, ghi job và trả mã theo dõi; worker chịu trách nhiệm xử lý nặng, áp dụng timeout và cập nhật kết quả. PostgreSQL bảo toàn job qua vòng đời tiến trình, còn cơ chế claim có điều kiện tạo nền tảng để nhiều worker cùng hoạt động mà không thay đổi quy tắc sở hữu tác vụ.

### 3.8. Phân tích và theo dõi

Khả năng quan sát được tổ chức quanh ba nhóm dữ liệu: hành vi sử dụng, chất lượng lời gọi AI và sự cố kỹ thuật. Mỗi nhóm có cấu trúc lưu trữ riêng, phục vụ một câu hỏi phân tích riêng, thay vì phụ thuộc hoàn toàn vào log văn bản khó tổng hợp.

Sự kiện hoạt động ghi nhận người dùng, phiên, loại hành động, đối tượng và metadata liên quan. Các sự kiện render hoàn tất hoặc thất bại lưu tier, renderer, provider, model, thời lượng, chế độ bất đồng bộ và trạng thái suy giảm chất lượng. Trên cơ sở đó, trang quản trị có thể tổng hợp mức sử dụng theo tính năng, người dùng hoạt động, phễu đăng ký — xác minh — sử dụng và tỷ lệ hoàn thành theo từng nhóm chức năng.

AI call metrics ghi nhận provider, model, loại tác vụ, số token đầu vào, số token đầu ra, độ trễ và trạng thái cuộc gọi. Việc tách số liệu từng lời gọi AI khỏi kết quả render cuối cùng giúp phân biệt lỗi nhà cung cấp với lỗi validation scene hoặc lỗi renderer. Dữ liệu có thể được tổng hợp theo provider, model và khoảng thời gian để đánh giá mức sử dụng tài nguyên và độ ổn định của tầng AI.

Error event tiếp nhận sự cố từ client hoặc server sau khi thông tin nhạy cảm đã được lọc. Fingerprint SHA-256 rút gọn 16 ký tự được sử dụng để gom các lỗi cùng mẫu thành một nhóm, giúp quan sát tần suất lặp lại ngay cả khi một phần thông điệp thay đổi. Request ID, route, method, status code và error code bổ sung ngữ cảnh cần thiết để liên kết sự cố với request tương ứng.

Health check được phân thành liveness, readiness và health detail. Liveness xác nhận tiến trình có phản hồi; readiness đánh giá khả năng nhận lưu lượng dựa trên PostgreSQL và migration; health detail tổng hợp trạng thái database, connection pool, migration, nhà cung cấp AI, capacity gate, Redis, lỗi gần đây và render thất bại trong 24 giờ cho người có quyền quản trị.

Worker thực hiện kiểm tra cảnh báo theo chu kỳ và dọn dữ liệu analytics theo thời hạn cấu hình. Mỗi nhóm error event, hoạt động người dùng và AI call metrics có thời gian lưu riêng, giúp kiểm soát tăng trưởng dữ liệu quan sát mà không tác động đến dữ liệu nghiệp vụ như tài khoản, lịch sử hoặc scene.

### 3.9. Vận hành và cập nhật

Ứng dụng được đóng gói bằng Docker nhiều giai đoạn. Giai đoạn Node 20 biên dịch frontend thành tài nguyên tĩnh; giai đoạn Python 3.11 cài đặt backend và tiếp nhận sản phẩm build. Một artifact thống nhất được hình thành từ mã frontend, backend và cấu hình phục vụ, qua đó giảm khác biệt giữa phiên bản đã kiểm tra và phiên bản được đưa lên nền tảng.

Trong container, Supervisord điều phối ba tiến trình có trách nhiệm riêng. Uvicorn thực thi ứng dụng FastAPI; render worker vận hành vòng lặp xử lý hàng đợi; Nginx phục vụ frontend tĩnh, chuyển tiếp REST API và nâng cấp kết nối WebSocket. Mỗi tiến trình được quản lý độc lập nhưng cùng thuộc một cấu hình phát hành.

DigitalOcean App Platform triển khai container từ nhánh `product` và sử dụng readiness endpoint để xác định instance đủ điều kiện phục vụ. Rolling update do nền tảng triển khai điều phối: phiên bản mới phải đáp ứng điều kiện sức khỏe trước khi nhận lưu lượng theo cơ chế của App Platform. Nginx chịu trách nhiệm định tuyến bên trong container, không thay thế vai trò điều phối phiên bản của nền tảng.

GitHub Actions thực hiện kiểm thử backend bằng pytest, kiểm tra kiểu và build frontend, đồng thời chạy Docker build smoke. Workflow hoạt động trên pull request và nhánh triển khai; lượt chạy cũ trên cùng ref được hủy khi có commit mới, tránh tiếp tục sử dụng tài nguyên cho phiên bản đã được thay thế.

Quy trình xác minh production đối chiếu trạng thái deployment, nhánh phát hành, cấu hình secret, bản sao lưu cơ sở dữ liệu, branch ruleset, trạng thái worker và các health endpoint. Sự kết hợp này giúp đánh giá đồng thời artifact, cấu hình và trạng thái vận hành, thay vì sử dụng một lần build thành công như căn cứ duy nhất cho kết luận production.

### 3.10. Chất lượng sản phẩm

Chất lượng được kiểm soát tại nhiều thời điểm trong vòng đời dữ liệu. Schema validation bảo vệ biên API; scene validator và khối kiểm chứng đại số máy tính bảo vệ cấu trúc toán học; kiểm tra tương thích bảo vệ khả năng dựng hình; điều kiện chất lượng bảo vệ đầu ra xuất; kiểm thử tự động bảo vệ hành vi khi mã nguồn thay đổi.

Bộ kiểm thử backend bao phủ xác thực, phiên, OAuth, quota, PostgreSQL, migration, API, OCR, nhà cung cấp AI, fallback, solver đại số, Function Analyzer, hình học, scene validation, capacity, Redis, worker, export, analytics, health và bảo mật. Kiểm thử không chỉ đánh giá các hàm riêng lẻ mà còn xác nhận những chuyển đổi trạng thái có ý nghĩa hệ thống như claim job, hoàn tất hoặc thất bại, phát hiện migration drift, phân quyền endpoint và quyết định cho phép xuất kết quả.

Frontend có bước kiểm tra kiểu và build bắt buộc trong CI. Mô phỏng có kiểm thử baseline cho cấu trúc bài học và runtime, bảo vệ tính nhất quán giữa số bước, bộ điều khiển và dữ liệu scene. Kiểu `RenderResponse` trong TypeScript duy trì sự đồng bộ giữa trạng thái, báo cáo chất lượng và yêu cầu xác nhận mà giao diện sử dụng.

Sản phẩm tạo ra một chuỗi đầu ra thống nhất. Người học có thể quan sát hình 2D hoặc 3D, tương tác với scene, đọc lời giải từng bước, tiếp tục bằng mô phỏng và mở lại lịch sử. Giáo viên hoặc người biên soạn có thể chuyển cùng kết quả sang PNG, JPG, SVG, HTML KaTeX, TikZ, PDF hoặc GeoGebra. Các đầu ra này kế thừa trạng thái chất lượng của scene, giúp nội dung học liệu duy trì mối liên hệ với thông tin kiểm chứng và giả định của dữ liệu nguồn.

Sự kết hợp giữa kiểm thử tự động và trạng thái chất lượng trong từng response tạo thành hai lớp bảo đảm bổ sung. Kiểm thử xác nhận mã nguồn thực thi đúng quy tắc đã thiết kế; báo cáo validation và verification xác nhận từng kết quả cụ thể đáp ứng các quy tắc đó ở mức độ nào.

---

## 4. Hệ thống phụ lục minh chứng

Hồ sơ minh chứng được tổ chức thành các nhóm tương ứng với 10 tiêu chí của báo cáo. Mỗi nhóm chứa dữ liệu gốc, bản trình bày đã loại bỏ thông tin nhạy cảm, thông tin phiên bản và phiếu kết luận. Mã minh chứng được sử dụng nhất quán trong báo cáo, bảng chỉ mục và tên tệp bàn giao.

| Tiêu chí | Nhóm phụ lục | Phạm vi chứng minh |
| --- | --- | --- |
| Giao diện người dùng | MC-UI | Kết quả build, hình ảnh và hành vi của các không gian hiển thị |
| Trải nghiệm người dùng | MC-UX | Chuỗi thao tác, trạng thái phản hồi, xác nhận, chỉnh sửa và lịch sử |
| Logic ứng dụng | MC-LOGIC | Kiểm thử chính sách, pipeline scene, solver và đầu ra |
| Backend và API | MC-API | Giao thức, validation, request ID, WebSocket và render job |
| PostgreSQL | MC-DB | Phiên bản, migration, pool, lược đồ và trạng thái dữ liệu |
| Bảo mật | MC-SEC | Cookie, Origin, phiên, mã hóa bí mật và kiểm soát truy cập |
| Hiệu năng và mở rộng | MC-PERF | Code splitting, capacity, worker và số liệu theo khoảng đo |
| Phân tích và theo dõi | MC-MON | Activity, AI metrics, error fingerprint và health check |
| Vận hành và cập nhật | MC-OPS | CI, container, deployment và trạng thái production |
| Chất lượng sản phẩm | MC-QA | Kiểm thử tổng thể, bộ bài toán đại diện và tập tin xuất |

Giá trị của từng minh chứng được xác lập theo ba điều kiện: nguồn dữ liệu có thể truy vết, quy trình thu thập có thể tái lập và kết luận chỉ nằm trong phạm vi mà dữ liệu quan sát được cho phép. Nội dung chi tiết về phương pháp thu thập, cấu trúc thư mục, quy tắc bảo toàn dữ liệu và tiêu chí đạt được quy định trong tài liệu `huong_dan_lay_minh_chung.md`.

---

## 5. Kết luận

AI Math Renderer đã hình thành một chuỗi xử lý hoàn chỉnh từ tiếp nhận đề bài, điều phối AI, phân tích toán học, tạo và kiểm chứng scene, trực quan hóa, tương tác, xác nhận, lưu phiên bản đến xuất học liệu. Các lớp hệ thống được phân định theo trách nhiệm và trao đổi qua dữ liệu có cấu trúc; trạng thái chất lượng được duy trì từ backend đến giao diện và đầu ra cuối cùng.

Giá trị cốt lõi của hệ thống không chỉ nằm ở khả năng sử dụng AI hoặc tạo hình trực quan, mà ở việc đặt kết quả AI trong một quy trình có kiểm tra, công bố mức độ tin cậy, cho phép người dùng hiệu chỉnh và bảo toàn dữ liệu trong PostgreSQL. Worker xử lý nền, cơ chế quan sát, bộ kiểm thử và hạ tầng triển khai production tiếp tục hoàn thiện chuỗi trách nhiệm từ thuật toán toán học đến khả năng phục vụ thực tế.

Với cơ chế phụ lục được tổ chức theo phiên bản, môi trường, dữ liệu gốc và tiêu chí kết luận, các năng lực trình bày trong báo cáo có thể được đối chiếu bằng những dấu vết kỹ thuật độc lập, khách quan và có khả năng tái lập.
