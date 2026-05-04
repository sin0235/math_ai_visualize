import { HomeTetrahedronShowcase } from './HomeTetrahedronShowcase';

export interface HomeBackendStatus {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
  settingsDefaults: unknown;
}

interface HomePageProps {
  logoUrl: string;
  backendStatus: HomeBackendStatus;
  onStartRender: () => void;
  onOpenSettings: () => void;
  onOpenLogin: () => void;
}

const features = [
  { title: 'Nhập đề tự nhiên', text: 'Viết đề bài toán như cách học sinh đọc đề, hệ thống sẽ chuyển thành scene hình học có cấu trúc.' },
  { title: 'OCR ảnh đề bài', text: 'Tải ảnh, kéo thả hoặc dán ảnh từ clipboard để trích xuất nội dung đề nhanh hơn.' },
  { title: 'Render 2D/3D', text: 'Dùng GeoGebra cho Oxy, đồ thị hàm số và Three.js cho hình học không gian sinh động.' },
  { title: 'Chỉnh hình linh hoạt', text: 'Tinh chỉnh điểm, đoạn, góc nhìn và tiếp tục dựng lại khi cần.' },
];

const trustSignals = ['Dành cho giáo viên và học sinh THPT', 'Hỗ trợ Oxy/Oxyz', 'Xuất GeoGebra/Three.js'];

export function HomePage({ onStartRender, onOpenSettings, onOpenLogin }: HomePageProps) {
  return (
    <section className="home-page">
      <div className="home-hero">
        <div className="home-hero-copy">
          <h2>Dựng hình toán học đẹp, nhanh và dễ kiểm soát.</h2>
          <p>
            Biến đề bài tiếng Việt, ảnh chụp hoặc dữ liệu tọa độ thành hình vẽ GeoGebra và Three.js.
            Phù hợp để học hình học 10-12, kiểm tra mô hình Oxy/Oxyz và tinh chỉnh trực quan.
          </p>
          <div className="home-actions">
            <button type="button" onClick={onStartRender}>Dùng thử miễn phí — không cần tài khoản</button>
            <button type="button" className="secondary-button" onClick={onOpenSettings}>Tùy chỉnh trải nghiệm</button>
          </div>
          <div className="home-trust-strip" aria-label="Điểm nổi bật">
            {trustSignals.map((item) => <span key={item}>{item}</span>)}
          </div>
          <button type="button" className="home-login-link" onClick={onOpenLogin}>Đã có tài khoản? Đăng nhập để đồng bộ lịch sử.</button>
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

