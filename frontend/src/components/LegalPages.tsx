import React from 'react';

export function PrivacyPolicyPage() {
  return (
    <section className="legal-page product-page-card professional-legal-doc">
      <div className="legal-hero-row">
        <div>
          <h2>Chính Sách Bảo Mật</h2>
          <p className="legal-update-date">Cập nhật lần cuối: 02 tháng 05, 2026</p>
          <p>AI Math Renderer ("chúng tôi", "dịch vụ") cam kết bảo vệ quyền riêng tư và dữ liệu cá nhân của người dùng. Chính sách này được thiết lập nhằm tuân thủ các quy định pháp luật hiện hành về bảo vệ dữ liệu cá nhân, bao gồm Nghị định 13/2023/NĐ-CP.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Thu thập dữ liệu cá nhân</h3>
          <p>Chúng tôi thu thập các thông tin cần thiết để cung cấp và cải thiện dịch vụ, bao gồm:</p>
          <ul>
            <li><strong>Thông tin định danh:</strong> Địa chỉ email, tên hiển thị được cung cấp khi đăng ký tài khoản hoặc thông qua dịch vụ xác thực bên thứ ba (Google OAuth).</li>
            <li><strong>Dữ liệu kỹ thuật:</strong> Địa chỉ IP, loại trình duyệt (User Agent), cookies phiên hoạt động nhằm mục đích bảo mật và duy trì trạng thái đăng nhập.</li>
            <li><strong>Dữ liệu nội dung:</strong> Các yêu cầu dựng hình (prompt), hình ảnh tải lên cho mục đích OCR, và cấu hình thông số hình học mà người dùng tạo ra.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Mục đích và phạm vi xử lý dữ liệu</h3>
          <p>Dữ liệu của bạn được xử lý cho các mục đích cụ thể sau:</p>
          <ul>
            <li><strong>Cung cấp dịch vụ cốt lõi:</strong> Đồng bộ hóa lịch sử dựng hình, lưu trữ cấu hình cá nhân và quản lý phiên làm việc trên nhiều thiết bị.</li>
            <li><strong>Giao tiếp hệ thống:</strong> Gửi thông báo xác thực tài khoản (OTP), liên kết khôi phục mật khẩu và các cập nhật quan trọng về dịch vụ.</li>
            <li><strong>An toàn và bảo mật:</strong> Giám sát các hoạt động bất thường, ngăn chặn hành vi tấn công từ chối dịch vụ (DoS) và bảo vệ tính toàn vẹn của hệ thống.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Xử lý dữ liệu qua bên thứ ba (AI Providers)</h3>
          <p>Dịch vụ này sử dụng các mô hình trí tuệ nhân tạo (LLM) từ các nhà cung cấp bên thứ ba (như OpenAI, Anthropic, Google, NVIDIA, 9Router). Khi bạn thực hiện yêu cầu render:</p>
          <ul>
            <li>Nội dung đề bài và dữ liệu hình ảnh sẽ được gửi đến máy chủ của nhà cung cấp AI để xử lý.</li>
            <li>Chúng tôi không kiểm soát cách các bên thứ ba này lưu trữ hoặc đào tạo mô hình dựa trên dữ liệu đó. Người dùng được khuyến cáo <strong>không nhập thông tin cá nhân nhạy cảm</strong> vào các yêu cầu dựng hình.</li>
            <li>Đối với các API Key cá nhân do người dùng cung cấp trong phần cài đặt, dữ liệu này chỉ được lưu trữ cục bộ tại trình duyệt hoặc truyền tải mã hóa đến backend để thực hiện yêu cầu, tuyệt đối không được sử dụng cho mục đích khác.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Thời gian lưu trữ và bảo vệ dữ liệu</h3>
          <ul>
            <li><strong>Lưu trữ:</strong> Dữ liệu được lưu trữ cho đến khi người dùng yêu cầu xóa tài khoản hoặc khi dịch vụ ngừng cung cấp.</li>
            <li><strong>Biện pháp bảo vệ:</strong> Chúng tôi áp dụng các tiêu chuẩn bảo mật ngành, bao gồm mã hóa HTTPS/TLS, cơ chế băm (hashing) mật khẩu một chiều và quản lý phiên đăng nhập an toàn (HttpOnly Cookies).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>5. Quyền của chủ thể dữ liệu</h3>
          <p>Theo quy định của pháp luật Việt Nam, bạn có các quyền sau đối với dữ liệu cá nhân của mình:</p>
          <ul>
            <li>Quyền được biết, truy cập, chỉnh sửa hoặc yêu cầu xóa dữ liệu cá nhân.</li>
            <li>Quyền rút lại sự đồng ý xử lý dữ liệu (có thể dẫn đến việc ngừng cung cấp một số tính năng của dịch vụ).</li>
            <li>Quyền yêu cầu cung cấp dữ liệu cá nhân của mình dưới dạng cấu trúc thông dụng.</li>
          </ul>
          <p>Để thực hiện các quyền này, bạn có thể sử dụng các công cụ trong mục "Quản lý tài khoản" hoặc liên hệ với chúng tôi qua kênh hỗ trợ.</p>
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
          <p className="legal-update-date">Cập nhật lần cuối: 02 tháng 05, 2026</p>
          <p>Chào mừng bạn đến với AI Math Renderer. Bằng việc truy cập hoặc sử dụng dịch vụ, bạn xác nhận đã đọc, hiểu và đồng ý tuân thủ các điều khoản dưới đây.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Quyền và trách nhiệm của người dùng</h3>
          <ul>
            <li><strong>Đăng ký tài khoản:</strong> Bạn có trách nhiệm cung cấp thông tin email chính xác và bảo mật thông tin đăng nhập. Mọi hoạt động phát sinh dưới tài khoản của bạn sẽ thuộc trách nhiệm của bạn.</li>
            <li><strong>Sử dụng hợp lệ:</strong> Bạn đồng ý sử dụng dịch vụ cho mục đích học tập, giảng dạy hoặc nghiên cứu hợp pháp. Nghiêm cấm mọi hành vi lạm dụng, tấn công hạ tầng, hoặc sử dụng dịch vụ để phát tán nội dung vi phạm pháp luật.</li>
            <li><strong>Nội dung người dùng:</strong> Bạn giữ quyền sở hữu đối với các đề bài và dữ liệu do bạn nhập vào, nhưng bạn cấp cho chúng tôi quyền hạn chế để xử lý các dữ liệu này nhằm mục đích hiển thị và cung cấp dịch vụ cho chính bạn.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Sở hữu trí tuệ</h3>
          <ul>
            <li><strong>Phần mềm và Giao diện:</strong> Toàn bộ mã nguồn, thiết kế giao diện, logo và thuật toán của AI Math Renderer là tài sản trí tuệ của chúng tôi hoặc các đối tác liên quan.</li>
            <li><strong>Kết quả dựng hình (Output):</strong> Các Scene JSON, mã GeoGebra hoặc mô hình Three.js được tạo ra bởi AI có thể được bạn sử dụng tự do cho mục đích cá nhân và giáo dục. Tuy nhiên, chúng tôi không đảm bảo tính duy nhất của các kết quả này.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Giới hạn trách nhiệm và Miễn trừ bảo đảm</h3>
          <p><strong>Dịch vụ được cung cấp trên cơ sở "nguyên trạng" (As-Is) và "có sẵn" (As-Available):</strong></p>
          <ul>
            <li><strong>Độ chính xác của AI:</strong> Bạn hiểu và thừa nhận rằng kết quả dựng hình từ AI có thể chứa sai sót về toán học, tọa độ hoặc logic hình học. Chúng tôi <strong>không chịu trách nhiệm</strong> đối với bất kỳ thiệt hại nào (trực tiếp hoặc gián tiếp) phát sinh từ việc sử dụng các kết quả này trong thi cử, xuất bản hoặc các quyết định quan trọng khác.</li>
            <li><strong>Kiểm chứng dữ liệu:</strong> Người dùng có trách nhiệm tự kiểm tra và xác nhận lại tính đúng đắn của hình ảnh trước khi sử dụng.</li>
            <li><strong>Sự cố kỹ thuật:</strong> Chúng tôi không bảo đảm dịch vụ sẽ luôn hoạt động liên tục, không có lỗi hoặc không bị gián đoạn do sự cố từ phía nhà cung cấp hạ tầng hoặc các dịch vụ AI bên thứ ba.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Chấm dứt và Thay đổi dịch vụ</h3>
          <ul>
            <li>Chúng tôi có quyền tạm ngừng hoặc chấm dứt cung cấp dịch vụ đối với các tài khoản vi phạm điều khoản sử dụng hoặc có dấu hiệu lạm dụng gây ảnh hưởng đến hệ thống mà không cần thông báo trước.</li>
            <li>Các điều khoản này có thể được cập nhật định kỳ. Việc bạn tiếp tục sử dụng dịch vụ sau khi có thay đổi đồng nghĩa với việc bạn chấp nhận các điều khoản mới.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>5. Luật áp dụng và Giải quyết tranh chấp</h3>
          <p>Các điều khoản này được điều chỉnh và giải thích theo pháp luật Cộng hòa Xã hội Chủ nghĩa Việt Nam. Mọi tranh chấp phát sinh từ hoặc liên quan đến việc sử dụng dịch vụ sẽ được ưu tiên giải quyết thông qua thương lượng, trường hợp không đạt được thỏa thuận sẽ được đưa ra cơ quan tài phán có thẩm quyền tại Việt Nam.</p>
        </section>
      </div>
    </section>
  );
}
