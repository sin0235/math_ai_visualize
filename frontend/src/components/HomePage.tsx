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

const steps = [
  { title: 'Nhập đề', text: 'Gõ đề tiếng Việt hoặc dán ảnh bài toán từ clipboard.' },
  { title: 'Chọn model', text: 'Dùng model mặc định hoặc cấu hình provider riêng.' },
  { title: 'Dựng hình', text: 'AI sinh scene, renderer chuyển thành hình 2D/3D.' },
  { title: 'Tinh chỉnh', text: 'Kéo điểm, sửa scene và lưu lịch sử khi đăng nhập.' },
];

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
            <button type="button" onClick={onStartRender}>Bắt đầu dựng hình</button>
            <button type="button" className="secondary-button" onClick={onOpenSettings}>Cấu hình model</button>
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

      <div className="workflow-strip">
        {steps.map((step, index) => (
          <div className="workflow-step" key={step.title}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <p>{step.text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

