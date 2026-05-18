import React from 'react';

export function PrivacyPolicyPage() {
  return (
    <section className="legal-page product-page-card professional-legal-doc">
      <div className="legal-hero-row">
        <div>
          <h2>Chính Sách Bảo Mật (Privacy Policy)</h2>
          <p className="legal-update-date">Cập nhật lần cuối: 18 tháng 05, 2026</p>
          <p>AI Math Renderer ("chúng tôi", "nền tảng") cam kết bảo vệ quyền riêng tư và dữ liệu của người dùng. Chính sách này tuân thủ các quy định pháp luật hiện hành, bao gồm <strong><a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/4/13nd.signed.pdf" target="_blank" rel="noopener noreferrer" title="Văn bản gốc (PDF)">Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân (PDPD)</a></strong>, <strong><a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/86.signed.pdf" target="_blank" rel="noopener noreferrer" title="Văn bản gốc (PDF)">Luật An toàn thông tin mạng 2015</a></strong> của Việt Nam, cũng như tham chiếu các tiêu chuẩn quốc tế như <strong>GDPR (Châu Âu)</strong> và <strong>CCPA (California)</strong> nhằm mang lại sự minh bạch tối đa.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Dữ liệu chúng tôi thu thập</h3>
          <p>Để cung cấp toàn bộ các chức năng bao gồm AI Math Modeling, Function Analysis, Simulation, và GeoGebra Lab Suite, chúng tôi thu thập:</p>
          <ul>
            <li><strong>Thông tin định danh:</strong> Tên, email, ảnh đại diện, và token xác thực khi đăng nhập qua các đối tác (Google, GitHub, v.v.).</li>
            <li><strong>Dữ liệu Đầu vào (Prompts & OCR):</strong> Các câu lệnh văn bản, công thức toán học, biểu thức hàm số, và hình ảnh đề bài (OCR) mà người dùng tải lên để AI xử lý.</li>
            <li><strong>Dữ liệu Phiên làm việc (Workspace State):</strong> Cấu trúc hình học (Scene JSON), trạng thái của các module GeoGebra (2D Graphing, 3D Calculator, Geometry, Probability), tham số mô phỏng (Simulation), và lịch sử phân tích hàm số.</li>
            <li><strong>Khóa API (API Keys):</strong> Nếu bạn sử dụng tính năng "Bring Your Own Key" (OpenAI, OpenRouter), khóa API của bạn sẽ được lưu trữ an toàn và chỉ dùng để giao tiếp trực tiếp với nhà cung cấp.</li>
            <li><strong>Dữ liệu Thiết bị & Phân tích:</strong> Địa chỉ IP, loại trình duyệt, ngôn ngữ, cookie phiên bản, và log lỗi hệ thống (nhằm gỡ lỗi luồng render AI và fallback cơ chế).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Mục đích và Quy trình Xử lý Dữ liệu</h3>
          <ul>
            <li><strong>Vận hành tính năng lõi:</strong> Phân tích và chuyển đổi ngôn ngữ tự nhiên (hoặc hình ảnh) thành các mô hình toán học tương tác, biểu đồ 2D/3D, và mã nguồn (LaTeX/TikZ, React/Three.js).</li>
            <li><strong>Cơ chế Đa LLM (Multi-AI Fallback):</strong> Dữ liệu toán học của bạn sẽ được truyền tải qua lại giữa máy chủ của chúng tôi và các nhà cung cấp AI (như OpenAI, Anthropic, Google thông qua OpenRouter hoặc OpenAI Compat API) để đảm bảo hệ thống luôn phản hồi khi có một mô hình gặp sự cố.</li>
            <li><strong>Cá nhân hóa & Đồng bộ:</strong> Lưu trữ cấu hình ứng dụng, lịch sử render và các tệp workspace để bạn có thể tiếp tục công việc trên nhiều thiết bị.</li>
            <li><strong>Nghiên cứu & Cải thiện:</strong> Chúng tôi có thể sử dụng dữ liệu ẩn danh (anonymized data) về cách người dùng tương tác với GeoGebra Lab hoặc các kết quả phân tích để tối ưu hóa thuật toán render và độ chính xác của AI.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Chia sẻ Dữ liệu với Bên thứ ba</h3>
          <p>Hệ thống của chúng tôi là một trung tâm kết nối, do đó dữ liệu của bạn có thể được xử lý bởi các đối tác sau:</p>
          <ul>
            <li><strong>AI Providers (OpenRouter, OpenAI, v.v.):</strong> Nhận câu lệnh và hình ảnh của bạn để thực hiện suy luận AI. Dữ liệu này tuân thủ chính sách bảo mật của riêng các nhà cung cấp đó. Chúng tôi cam kết <strong>không</strong> gửi thông tin định danh cá nhân (PII) kèm theo các truy vấn toán học.</li>
            <li><strong>Dịch vụ Đám mây & Cơ sở dữ liệu:</strong> AWS, Google Cloud, hoặc Vercel (nếu có) được dùng để lưu trữ dữ liệu an toàn.</li>
            <li><strong>Yêu cầu Pháp lý:</strong> Chúng tôi chỉ cung cấp dữ liệu cho cơ quan chức năng khi có yêu cầu hợp pháp theo Luật An ninh mạng 2018 và các quy định tố tụng tại Việt Nam.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Quyền của Chủ thể Dữ liệu (Theo NĐ 13/2023/NĐ-CP & GDPR)</h3>
          <p>Bạn có toàn quyền kiểm soát dữ liệu cá nhân của mình, bao gồm:</p>
          <ul>
            <li><strong>Quyền được biết & Đồng ý:</strong> Bạn được thông báo rõ ràng về loại dữ liệu được thu thập (qua chính sách này) và có quyền rút lại sự đồng ý bất cứ lúc nào.</li>
            <li><strong>Quyền truy cập & Cung cấp dữ liệu:</strong> Bạn có thể xem và tải xuống lịch sử phiên làm việc, dữ liệu Scene JSON, và thông tin cá nhân.</li>
            <li><strong>Quyền xóa dữ liệu (Right to be Forgotten):</strong> Yêu cầu xóa hoàn toàn tài khoản, lịch sử chat AI, dữ liệu render, và API Keys khỏi hệ thống của chúng tôi.</li>
            <li><strong>Quyền phản đối & Hạn chế:</strong> Từ chối việc sử dụng dữ liệu của bạn cho mục đích phân tích hành vi hoặc huấn luyện AI (nếu tính năng này được kích hoạt).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>5. Biện pháp Bảo vệ và Lưu trữ</h3>
          <ul>
            <li><strong>Mã hóa đầu cuối & Lưu trữ:</strong> Dữ liệu truyền tải được mã hóa TLS 1.3. Khóa API (API Keys) và mật khẩu được mã hóa an toàn tại database (ví dụ: AES-256) hoặc lưu trữ cục bộ trên trình duyệt của bạn (tùy cấu hình).</li>
            <li><strong>Lưu trữ có thời hạn:</strong> Dữ liệu không hoạt động, log lỗi và dữ liệu tạm thời (temp scenes) sẽ tự động bị xóa sau một khoảng thời gian quy định nhằm giảm thiểu rủi ro rò rỉ.</li>
            <li><strong>Trách nhiệm về phía người dùng:</strong> Không nhập thông tin thẻ tín dụng, căn cước công dân, thẻ bảo hiểm, hoặc bí mật thương mại vào các khung nhập liệu toán học AI.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>6. Liên hệ</h3>
          <p>Mọi yêu cầu thực thi quyền dữ liệu cá nhân hoặc thắc mắc về bảo mật, vui lòng liên hệ Bộ phận Bảo vệ Dữ liệu (DPO) của chúng tôi qua hệ thống hỗ trợ trên nền tảng.</p>
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
          <h2>Điều Khoản Sử Dụng (Terms of Service)</h2>
          <p className="legal-update-date">Cập nhật lần cuối: 18 tháng 05, 2026</p>
          <p>Vui lòng đọc kỹ các Điều khoản này. Bằng việc truy cập, đăng ký tài khoản hoặc sử dụng hệ sinh thái AI Math Renderer (bao gồm AI Math Modeling, Function Analysis, Simulation, GeoGebra Lab Suite, và kiến trúc Multi-AI), bạn thiết lập một thỏa thuận pháp lý ràng buộc và đồng ý tuân thủ toàn bộ các quy định dưới đây, phù hợp với <strong><a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/8/luat20-2023-qh15..pdf" target="_blank" rel="noopener noreferrer" title="Văn bản gốc (PDF)">Luật Giao dịch điện tử 2023</a></strong>, <strong><a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/86.signed.pdf" target="_blank" rel="noopener noreferrer" title="Văn bản gốc (PDF)">Luật An toàn thông tin mạng 2015</a></strong> và <strong><a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/07/07-2022-qh15..pdf" target="_blank" rel="noopener noreferrer" title="Văn bản gốc (PDF)">Luật Sở hữu trí tuệ 2005 (sửa đổi 2022)</a></strong> của Việt Nam.</p>
        </div>
      </div>

      <div className="legal-content">
        <section className="legal-section">
          <h3>1. Định nghĩa và Phạm vi Dịch vụ</h3>
          <ul>
            <li><strong>AI Math Renderer:</strong> Là môi trường tính toán và dựng hình toán học dựa trên Trí tuệ Nhân tạo, hỗ trợ phân tích hàm số, mô phỏng không gian 2D/3D (qua Three.js) và cung cấp bộ công cụ trực quan hóa (GeoGebra Graphing, Geometry, 3D Calculator, Probability).</li>
            <li><strong>Mô hình "Scene-as-Code":</strong> Là cơ chế cốt lõi của nền tảng, cho phép chuyển đổi ngôn ngữ tự nhiên thành dữ liệu JSON cấu trúc và mã nguồn (LaTeX/TikZ, React) để render theo thời gian thực.</li>
            <li><strong>Người dùng:</strong> Bất kỳ cá nhân hoặc tổ chức nào truy cập và tương tác với các API hoặc giao diện của nền tảng.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>2. Tài khoản và Định danh Điện tử</h3>
          <ul>
            <li><strong>Bảo mật thông tin:</strong> Người dùng cam kết cung cấp thông tin chính xác khi đăng nhập qua các OAuth Providers (Google, GitHub). Bạn chịu trách nhiệm hoàn toàn về việc bảo vệ thiết bị và thông tin xác thực phiên (session tokens).</li>
            <li><strong>Hành vi trái phép:</strong> Mọi hành vi mua bán, cho thuê tài khoản, hoặc chia sẻ Khóa API nội bộ của hệ thống cho các mục đích thương mại ngoài phạm vi nền tảng đều bị nghiêm cấm.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>3. Cơ chế Multi-AI và "Bring Your Own Key" (BYOK)</h3>
          <p>Nền tảng sử dụng kiến trúc AI dự phòng (Fallback) tích hợp với các đối tác như OpenRouter và OpenAI Compat API:</p>
          <ul>
            <li><strong>Chế độ Mặc định:</strong> Dữ liệu của bạn được luân chuyển qua các mô hình LLM sẵn có trên hệ thống để tối ưu hóa tỷ lệ thành công khi dựng hình. Tốc độ và chất lượng phụ thuộc vào tải của máy chủ tại thời điểm đó.</li>
            <li><strong>Chế độ BYOK (Sử dụng Khóa cá nhân):</strong> Nếu bạn cấu hình API Key cá nhân để bỏ qua giới hạn (Rate Limits) của nền tảng, bạn <strong>chịu 100% trách nhiệm về mặt pháp lý và chi phí tài chính</strong> phát sinh trên tài khoản của nhà cung cấp đó. Nền tảng cam kết chỉ mã hóa (AES-256) và sử dụng khóa này cho chính các yêu cầu do bạn khởi tạo.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>4. Cảnh báo Ảo giác AI (Hallucinations) & Miễn trừ Kỹ thuật</h3>
          <p><strong>CẢNH BÁO ĐẶC BIỆT:</strong> AI Math Renderer là một "Trợ lý Phác thảo Toán học", KHÔNG PHẢI là một cỗ máy tính toán hoàn hảo.</p>
          <ul>
            <li><strong>Rủi ro Sai lệch:</strong> Các mô hình ngôn ngữ lớn (LLMs) có thể gặp hiện tượng "ảo giác" (hallucinations), dẫn đến việc sinh ra các công thức toán học sai logic, vẽ sai tọa độ, nhận diện sai ký tự hình ảnh (OCR), hoặc nội suy sai quỹ đạo trong không gian 3D.</li>
            <li><strong>Nghiêm cấm Áp dụng Thực tiễn Khắt khe:</strong> Kết quả từ nền tảng <strong>tuyệt đối không được sử dụng trực tiếp</strong> (mà không qua kiểm duyệt bởi chuyên gia con người) cho các hệ thống kỹ thuật trọng yếu như: thiết kế kiến trúc/cầu đường, y tế (đo liều lượng phóng xạ, thiết bị y sinh), hàng không vũ trụ, hoặc các lĩnh vực mà sai số toán học có thể gây thiệt hại về tính mạng hoặc tài sản nghiêm trọng.</li>
            <li><strong>Trách nhiệm Học thuật:</strong> Sinh viên và nhà nghiên cứu tự chịu trách nhiệm về tính trung thực và độ chính xác của số liệu khi đưa kết quả sinh ra từ AI vào luận văn, bài kiểm tra, hoặc các xuất bản phẩm khoa học.</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>5. Sở hữu Trí tuệ và Cấp phép Chéo (Cross-Licensing)</h3>
          <ul>
            <li><strong>Sở hữu của Nền tảng:</strong> Giao diện (UI/UX), kiến trúc backend, thuật toán phân tích "Scene-as-Code", log logic và thương hiệu AI Math Renderer là tài sản độc quyền của Sin Studio. Việc sao chép, dịch ngược (reverse-engineering) là vi phạm pháp luật.</li>
            <li><strong>Sở hữu của Bên thứ ba:</strong> Nền tảng nhúng các công cụ như <strong>GeoGebra</strong> (thuộc GeoGebra GmbH), <strong>MathJax</strong>, và <strong>Three.js</strong>. Việc bạn sử dụng các chức năng này phải tuân thủ Giấy phép Mã nguồn mở hoặc điều khoản thương mại (nếu có) của chính các tác giả đó. Chúng tôi không cấp quyền thay mặt cho GeoGebra.</li>
            <li><strong>Sở hữu của Người dùng:</strong> Bạn sở hữu toàn bộ các Prompts (câu lệnh) và hình ảnh đề bài do bạn tạo ra. Đối với các hình ảnh render (Exported SVG/PNG/PDF) và đoạn mã (LaTeX) được AI tạo ra, bạn được quyền sử dụng tự do theo giấy phép MIT/Creative Commons, miễn là không vi phạm bản quyền của đề bài gốc (ví dụ: chụp từ sách giáo khoa có bản quyền).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>6. Tiêu chuẩn Hành vi và Các lệnh Cấm</h3>
          <p>Nhằm bảo vệ hạ tầng máy chủ và API, các hành vi sau sẽ dẫn đến việc <strong>khóa tài khoản vĩnh viễn không cần báo trước</strong>:</p>
          <ul>
            <li><strong>Lạm dụng Tài nguyên (Abuse & Scraping):</strong> Sử dụng Scripts/Bots tự động để gửi hàng loạt yêu cầu (DDoS, Mass OCR, Mass Render) làm cạn kiệt Quota API của hệ thống.</li>
            <li><strong>Bypass Cơ chế:</strong> Lợi dụng lỗi logic của cơ chế Multi-AI Fallback để ép hệ thống gọi các mô hình cao cấp (Premium Models) trái phép.</li>
            <li><strong>Nội dung độc hại:</strong> Bơm (Prompt Injection) các đoạn mã độc (XSS, SQLi) qua các khung nhập liệu biểu thức toán học hoặc cố gắng thao túng luồng thực thi của máy chủ AI (Jailbreaking).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>7. Gói Dịch vụ và Chính sách Hoàn tiền</h3>
          <ul>
            <li>Nền tảng duy trì hạng mức Miễn phí (Free Tier) với các giới hạn về độ phức tạp của hàm số và số lần render. Chúng tôi có quyền thay đổi các giới hạn này vào bất kỳ lúc nào để cân bằng chi phí máy chủ.</li>
            <li>Trong trường hợp triển khai các Gói Trả phí (Premium/Pro Tier), các khoản thanh toán sẽ không được hoàn lại (Non-refundable) trừ phi dịch vụ bị gián đoạn hoàn toàn (Downtime 100%) liên tục trong quá 72 giờ do lỗi từ phía máy chủ của chúng tôi (không tính lỗi do OpenAI/OpenRouter sập).</li>
          </ul>
        </section>

        <section className="legal-section">
          <h3>8. Tính Sẵn sàng (SLA) và Bảo trì</h3>
          <p>AI Math Renderer là dự án có tính thử nghiệm cao (Experimental/Beta). Chúng tôi <strong>không cung cấp bất kỳ cam kết SLA nào (No Service Level Agreement)</strong> về thời gian Uptime. Dịch vụ, hoặc một phần của dịch vụ (như tính năng giải toán AI), có thể bị bảo trì, gián đoạn, hoặc gỡ bỏ hoàn toàn mà không phát sinh bất kỳ nghĩa vụ bồi thường nào.</p>
        </section>

        <section className="legal-section">
          <h3>9. Giải quyết Tranh chấp và Luật Áp dụng</h3>
          <ul>
            <li><strong>Tính hiệu lực từng phần:</strong> Nếu bất kỳ điều khoản nào trong văn bản này bị Tòa án phán quyết là vô hiệu, các điều khoản còn lại vẫn có đầy đủ giá trị thi hành.</li>
            <li><strong>Thẩm quyền Giải quyết:</strong> Mọi tranh chấp, khiếu nại phát sinh sẽ được ưu tiên giải quyết thông qua thương lượng thiện chí trong vòng 30 ngày. Nếu không thành, vụ việc sẽ được đưa ra phân xử tại <strong>Tòa án Nhân dân có thẩm quyền tại Thành phố Hồ Chí Minh, Việt Nam</strong>. Luật áp dụng là Pháp luật của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.</li>
          </ul>
        </section>
      </div>
    </section>
  );
}
