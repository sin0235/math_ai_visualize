import { HomeTetrahedronShowcase } from './HomeTetrahedronShowcase';

export interface HomeBackendStatus {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
  settingsDefaults: unknown;
}

interface HomePageProps {
  logoUrl: string;
  backendStatus: HomeBackendStatus;
  onOpenLogin: () => void;
}

const features = [
  { title: 'Nhận diện đề bài thông minh', text: 'Trích xuất tự động giả thiết hình học và toán học từ văn bản tự nhiên, hình ảnh hoặc tài liệu bằng AI đa mô hình.' },
  { title: 'Mô phỏng trực quan 2D/3D', text: 'Hiển thị sinh động qua GeoGebra và Three.js. Hỗ trợ toàn diện hình học phẳng, không gian Oxyz và đồ thị hàm số.' },
  { title: 'Phân tích & Giải toán', text: 'Hệ thống tích hợp công cụ CAS và bộ máy suy luận hình học giúp phân tích từng bước và cung cấp lời giải chính xác.' },
  { title: 'Xuất bản chuẩn học thuật', text: 'Hỗ trợ trích xuất hình vẽ chất lượng cao sang định dạng mã TikZ (LaTeX), nhúng GeoGebra hoặc kết xuất PDF.' },
];

const trustSignals = ['Tích hợp AI Đa mô hình', 'Hệ thống Giải toán Tự động', 'Đồ họa tương tác Oxyz'];

const learningOutcomes = [
  { value: 'Nhanh chóng', label: 'Tự động hóa phân tích đề và dựng hình.' },
  { value: 'Trực quan', label: 'Tương tác linh hoạt với không gian 2D, 3D.' },
  { value: 'Chuẩn học thuật', label: 'Tối ưu quy trình biên soạn tài liệu giảng dạy.' },
];

export function HomePage({ onOpenLogin }: HomePageProps) {
  return (
    <section className="home-page">
      <div className="home-hero">
        <div className="home-hero-copy">
          <h2>Giải pháp AI toàn diện cho số hóa hình học và toán học.</h2>
          <p>
            Chuyển đổi bài toán từ văn bản và hình ảnh thành mô hình đồ họa tương tác.
            Nền tảng đột phá giúp đơn giản hóa việc dựng hình, khảo sát hàm số và biên soạn tài liệu sư phạm chuyên sâu.
          </p>
          <div className="home-trust-strip" aria-label="Điểm nổi bật">
            {trustSignals.map((item) => <span key={item}>{item}</span>)}
          </div>
          <button type="button" className="home-login-link" onClick={onOpenLogin}>Đăng nhập để đồng bộ dữ liệu và trải nghiệm đầy đủ tính năng.</button>
          <div className="home-outcome-strip" aria-label="Giá trị cốt lõi">
            {learningOutcomes.map((item) => (
              <div key={item.value}>
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="home-visual-card home-visual-card--3d" role="region" aria-label="Minh họa tứ diện đều SABC, kéo để xoay góc nhìn.">
          <HomeTetrahedronShowcase />
        </div>
      </div>

      <div className="feature-grid">
        {features.map((feature, index) => (
          <article className="feature-card" key={feature.title}>
            <span className="feature-index">0{index + 1}</span>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

