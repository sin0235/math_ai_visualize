import React from 'react';

export function PrivacyPolicyPage() {
  return (
    <section className="legal-page product-page-card professional-legal-doc">
      <div className="legal-hero-row">
        <div>
          <h2>Chính Sách Bảo Mật</h2>
          <p className="legal-update-date">Cập nhật lần cuối: 08 tháng 05, 2026</p>
          <p>AI Math Renderer ("chúng tôi", "nền tảng") cam kết bảo vệ tối đa quyền riêng tư và dữ liệu kỹ thuật của người dùng. Chính sách này được thiết lập nhằm tuân thủ các quy định pháp luật hiện hành, bao gồm Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Thu thập và Xử lý dữ liệu</h3>
          <p>Chúng tôi thu thập các thông tin cần thiết để vận hành kiến trúc phân tích và dựng hình, bao gồm:</p>
          <ul>
            <li><strong>Thông tin định danh:</strong> Địa chỉ email, tên hiển thị và dữ liệu xác thực từ các đối tác tin cậy (Google OAuth).</li>
            <li><strong>Dữ liệu toán học & Biểu thức:</strong> Các yêu cầu dựng hình, biểu thức hàm số, và hình ảnh đề bài (OCR) được người dùng nhập vào hệ thống.</li>
            <li><strong>Dữ liệu Kỹ thuật Scene:</strong> Thông tin về cấu trúc hình học (Scene JSON), tọa độ điểm và các tham số tùy chỉnh do người dùng thiết lập.</li>
            <li><strong>Thông tin thiết bị:</strong> Địa chỉ IP, loại trình duyệt và cookies phiên hoạt động nhằm đảm bảo an ninh hệ thống.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Mục đích xử lý dữ liệu</h3>
          <p>Dữ liệu của bạn được xử lý thông qua hệ thống phân tích đa tầng cho các mục đích:</p>
          <ul>
            <li><strong>Tối ưu hóa Phân tích & Dựng hình:</strong> Đồng bộ hóa lịch sử làm việc, lưu trữ các mẫu hình học và khảo sát hàm số cá nhân hóa.</li>
            <li><strong>Phát triển Hệ thống Suy luận:</strong> Cải thiện độ chính xác của bộ máy giải toán và nhận diện hình ảnh dựa trên các mẫu dữ liệu ẩn danh.</li>
            <li><strong>Duy trì An ninh Hạ tầng:</strong> Ngăn chặn các hành vi xâm nhập, lạm dụng tài nguyên GPU và bảo vệ quyền lợi chung của cộng đồng người dùng.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Tương tác với Hệ sinh thái AI bên thứ ba</h3>
          <p>Nền tảng tích hợp các mô hình ngôn ngữ lớn (LLM) và dịch vụ xử lý từ các nhà cung cấp hàng đầu (OpenAI, Anthropic, Google, NVIDIA, Router9). Khi sử dụng dịch vụ:</p>
          <ul>
            <li>Dữ liệu toán học và hình ảnh sẽ được truyền tải mã hóa đến các API Provider để thực hiện quy trình suy luận và phân tích logic.</li>
            <li>Chúng tôi cam kết không chia sẻ thông tin định danh cá nhân trực tiếp cho các bên này trong quá trình xử lý yêu cầu toán học.</li>
            <li>Người dùng chịu trách nhiệm về nội dung nhập vào và được khuyến cáo không đưa các thông tin cá nhân nhạy cảm vào các mô tả bài toán.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Cam kết Bảo mật & Lưu trữ</h3>
          <ul>
            <li><strong>Mã hóa Toàn diện:</strong> Mọi dữ liệu truyền tải giữa máy khách và máy chủ đều được bảo vệ bởi tiêu chuẩn HTTPS/TLS mạnh mẽ.</li>
            <li><strong>Quyền kiểm soát:</strong> Người dùng hoàn toàn có quyền truy cập, chỉnh sửa hoặc yêu cầu xóa vĩnh viễn dữ liệu cá nhân và lịch sử dựng hình bất cứ lúc nào thông qua bảng điều khiển.</li>
            <li><strong>Lưu trữ an toàn:</strong> Mật khẩu và thông tin quan trọng được bảo vệ bằng các thuật toán băm (hashing) hiện đại, đảm bảo ngay cả quản trị viên cũng không thể truy cập trực tiếp.</li>
          </ul>
        </section>
      </div>
    </section>
  );
}

export function TermsPage() {
  return (
    <section className="legal-page product-page-card professional-legal-doc">
      <div className="legal-hero-row">
        <div>
          <h2>Điều Khoản Sử Dụng</h2>
          <p className="legal-update-date">Cập nhật lần cuối: 08 tháng 05, 2026</p>
          <p>Bằng việc sử dụng AI Math Renderer, bạn đồng ý với các điều khoản vận hành dưới đây nhằm đảm bảo một môi trường học thuật sáng tạo và minh bạch.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Quy ước sử dụng dịch vụ</h3>
          <ul>
            <li><strong>Tài khoản cá nhân:</strong> Người dùng tự chịu trách nhiệm bảo mật thông tin đăng nhập và mọi hoạt động phát sinh từ tài khoản của mình.</li>
            <li><strong>Sử dụng đúng mục đích:</strong> Dịch vụ được thiết kế cho mục đích giáo dục, nghiên cứu và biên soạn tài liệu toán học. Nghiêm cấm mọi hành vi tấn công kỹ thuật, khai thác lỗ hổng hoặc sử dụng tự động hóa (bot) gây quá tải hệ thống.</li>
            <li><strong>Tôn trọng hạ tầng:</strong> Các tài nguyên tính toán (AI/GPU) được phân bổ theo định mức, người dùng cần tuân thủ các giới hạn về tần suất yêu cầu để đảm bảo tính ổn định chung.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Gói dịch vụ và Thanh toán</h3>
          <ul>
            <li><strong>Mô hình dịch vụ:</strong> Nền tảng cung cấp cả gói miễn phí (với hạn mức sử dụng) và các gói trả phí (Premium) với tài nguyên AI ưu tiên.</li>
            <li><strong>Thay đổi mức phí:</strong> Chúng tôi có quyền điều chỉnh chính sách giá và cấu trúc gói dịch vụ. Các thay đổi sẽ được thông báo trước trên giao diện chính hoặc qua email.</li>
            <li><strong>Hoàn tiền:</strong> Việc hoàn phí cho các gói dịch vụ trả phí sẽ được xem xét theo từng trường hợp cụ thể dựa trên tính sẵn sàng của hệ thống và quy định thanh toán của bên thứ ba.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Sở hữu trí tuệ và "Scene-as-Code"</h3>
          <ul>
            <li><strong>Quyền sở hữu công nghệ:</strong> Mọi thuật toán, kiến trúc backend, mã nguồn giao diện và thương hiệu AI Math Renderer thuộc sở hữu độc quyền của Sin Studio.</li>
            <li><strong>Quyền sở hữu nội dung:</strong> Người dùng giữ toàn quyền sở hữu đối với các đề bài và các "Dữ liệu Scene có cấu trúc" do mình tạo ra. Bạn có thể tự do xuất bản, nhúng hoặc sử dụng kết quả (GeoGebra, TikZ, Three.js) cho các mục đích cá nhân và thương mại hợp pháp.</li>
            <li><strong>Đóng góp ý kiến (Feedback):</strong> Bằng việc gửi góp ý, bạn cấp cho chúng tôi quyền sử dụng các ý kiến đó để cải thiện sản phẩm mà không kèm theo nghĩa vụ tài chính.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Liên kết và Dịch vụ bên thứ ba</h3>
          <p>Dịch vụ có tích hợp hoặc liên kết tới các công cụ toán học bên ngoài như GeoGebra, MathJax, và các AI Providers:</p>
          <ul>
            <li>Việc sử dụng các công cụ này cũng đồng thời chịu sự điều chỉnh bởi các điều khoản riêng của từng nhà cung cấp đó.</li>
            <li>Chúng tôi không chịu trách nhiệm về nội dung, chính sách bảo mật hoặc sự cố kỹ thuật phát sinh từ phía các dịch vụ bên thứ ba này.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>5. Tuyên bố Miễn trừ và Giới hạn Trách nhiệm</h3>
          <p><strong>Người dùng cần lưu ý các đặc thù của công nghệ AI trong toán học:</strong></p>
          <ul>
            <li><strong>Độ chính xác của AI:</strong> Mặc dù áp dụng các mô hình suy luận tiên tiến, kết quả đầu ra có thể vẫn chứa sai sót về logic hoặc tọa độ do tính chất của LLM. Chúng tôi <strong>không chịu trách nhiệm</strong> cho bất kỳ sai sót nào trong kết quả học tập, thi cử hoặc xuất bản dựa trên dữ liệu từ nền tảng.</li>
            <li><strong>Trách nhiệm kiểm chứng:</strong> Nền tảng đóng vai trò là "Trợ lý kỹ thuật". Người dùng có trách nhiệm cuối cùng trong việc kiểm tra tính đúng đắn về mặt chuyên môn trước khi đưa vào sử dụng thực tế.</li>
            <li><strong>Tính sẵn sàng:</strong> Dịch vụ phụ thuộc vào các nhà cung cấp hạ tầng AI bên thứ ba. Chúng tôi không đảm bảo dịch vụ luôn hoạt động 100% thời gian hoặc không có gián đoạn kỹ thuật.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>6. Thay đổi và Chấm dứt dịch vụ</h3>
          <ul>
            <li>Chúng tôi có quyền điều chỉnh tính năng, tạm ngừng hoặc chấm dứt một phần dịch vụ để bảo trì hoặc nâng cấp.</li>
            <li>Trường hợp người dùng vi phạm nghiêm trọng các quy định về an ninh hoặc lạm dụng tài nguyên, chúng tôi có quyền khóa tài khoản vĩnh viễn mà không cần thông báo trước.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>7. Điều khoản chung</h3>
          <ul>
            <li><strong>Tính tách biệt:</strong> Nếu bất kỳ điều khoản nào bị coi là vô hiệu bởi cơ quan có thẩm quyền, các điều khoản còn lại vẫn giữ nguyên giá trị pháp lý.</li>
            <li><strong>Luật áp dụng:</strong> Các điều khoản này được điều chỉnh bởi pháp luật Việt Nam. Mọi tranh chấp sẽ được ưu tiên giải quyết qua thương lượng trước khi đưa ra cơ quan tài phán.</li>
          </ul>
        </section>
      </div>
    </section>
  );
}
