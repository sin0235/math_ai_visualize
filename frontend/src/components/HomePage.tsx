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

const useCases = [
  'Vẽ nhanh hình Oxy/Oxyz từ đề kiểm tra.',
  'Biến ảnh đề bài thành hình dựng lại được.',
  'Kiểm tra lời giải hình học bằng mô hình trực quan.',
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

        <button type="button" className="home-visual-card" aria-label="Bắt đầu demo dựng hình toán học" onClick={onStartRender}>
          <GeometryShowcase />
        </button>
      </div>

      <section className="use-case-section" aria-label="Ứng dụng thực tế">
        <div>
          <span>Ứng dụng thực tế</span>
          <h3>Cho bài giảng, lời giải và kiểm tra mô hình hình học.</h3>
        </div>
        <ul>
          {useCases.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

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

function GeometryShowcase() {
  return (
    <svg className="geometry-showcase" viewBox="0 0 560 420" role="img" aria-label="Lưới tọa độ và hình học minh họa">
      <defs>
        <linearGradient id="homeGridGradient" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#2563eb" stopOpacity="0.18" />
          <stop offset="1" stopColor="#7c3aed" stopOpacity="0.08" />
        </linearGradient>
        <radialGradient id="homeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#60a5fa" stopOpacity="0.55" />
          <stop offset="1" stopColor="#60a5fa" stopOpacity="0" />
        </radialGradient>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" fill="#2563eb" />
        </marker>
      </defs>
      <rect x="24" y="24" width="512" height="348" rx="28" fill="url(#homeGridGradient)" stroke="#d4d4d4" />
      {Array.from({ length: 9 }).map((_, index) => (
        <path key={`v-${index}`} d={`M${72 + index * 52} 56V340`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 8" />
      ))}
      {Array.from({ length: 6 }).map((_, index) => (
        <path key={`h-${index}`} d={`M56 ${84 + index * 46}H504`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 8" />
      ))}
      <path d="M72 318H500" stroke="#111827" strokeWidth="2" strokeLinecap="round" />
      <path d="M92 338V72" stroke="#111827" strokeWidth="2" strokeLinecap="round" />
      <circle cx="164" cy="286" r="54" fill="none" stroke="#2563eb" strokeWidth="4" />
      <path d="M164 286L312 130L430 286Z" fill="rgba(37,99,235,0.08)" stroke="#111827" strokeWidth="4" strokeLinejoin="round" />
      <path d="M312 130V286" stroke="#7c3aed" strokeWidth="3" strokeDasharray="8 9" />
      <path d="M164 286C226 226 274 178 312 130" fill="none" stroke="#f97316" strokeWidth="5" strokeLinecap="round" />
      <path d="M356 180L456 116" stroke="#2563eb" strokeWidth="4" strokeLinecap="round" markerEnd="url(#arrow)" />
      <circle cx="312" cy="130" r="72" fill="url(#homeGlow)" />
      {[[164, 286, 'A'], [312, 130, 'S'], [430, 286, 'B'], [312, 286, 'H']].map(([cx, cy, label]) => (
        <g key={label as string}>
          <circle cx={cx as number} cy={cy as number} r="8" fill="#111827" />
          <text x={(cx as number) + 12} y={(cy as number) - 12} fill="#111827" fontSize="20" fontWeight="700">{label}</text>
        </g>
      ))}
      <text x="112" y="98" fill="#475569" fontSize="18" fontWeight="700">Oxy/Oxyz</text>
      <text x="352" y="330" fill="#475569" fontSize="16" fontWeight="600">GeoGebra + Three.js</text>
    </svg>
  );
}
