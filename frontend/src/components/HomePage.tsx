import type { SettingsDefaults } from '../types/settings';

export interface HomeBackendStatus {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
  settingsDefaults: SettingsDefaults | null;
}

interface HomePageProps {
  logoUrl: string;
  backendStatus: HomeBackendStatus;
  onStartRender: () => void;
  onOpenSettings: () => void;
  onOpenLogin: () => void;
}

const features = [
  { title: 'Nhập đề tự nhiên', text: 'Viết đề bài toán như cách học sinh đọc đề, hệ thống sẽ chuyển thành scene hình học có cấu trúc.', icon: '∑' },
  { title: 'OCR ảnh đề bài', text: 'Tải ảnh, kéo thả hoặc dán ảnh từ clipboard để trích xuất nội dung đề nhanh hơn.', icon: 'OCR' },
  { title: 'Render 2D/3D', text: 'Dùng GeoGebra cho Oxy, đồ thị hàm số và Three.js cho hình học không gian sinh động.', icon: '3D' },
  { title: 'Chỉnh hình linh hoạt', text: 'Tinh chỉnh điểm, đoạn, góc nhìn, xem Scene JSON và tiếp tục dựng lại khi cần.', icon: '{}'},
];

const steps = ['Nhập đề', 'Chọn model', 'Dựng hình', 'Tinh chỉnh'];

export function HomePage({ logoUrl, backendStatus, onStartRender, onOpenSettings, onOpenLogin }: HomePageProps) {
  const providerSummary = summarizeProviders(backendStatus.settingsDefaults);

  return (
    <section className="home-page">
      <div className="home-hero">
        <div className="home-hero-copy">
          <span className="home-eyebrow">AI Math Renderer</span>
          <h2>Dựng hình toán học đẹp, nhanh và dễ kiểm soát.</h2>
          <p>
            Biến đề bài tiếng Việt, ảnh chụp hoặc dữ liệu tọa độ thành hình vẽ GeoGebra và Three.js.
            Phù hợp để học hình học 10-12, kiểm tra mô hình Oxy/Oxyz và tinh chỉnh trực quan.
          </p>
          <div className="home-actions">
            <button type="button" onClick={onStartRender}>Bắt đầu dựng hình</button>
            <button type="button" className="secondary-button" onClick={onOpenSettings}>Cấu hình model</button>
            <button type="button" className="link-button" onClick={onOpenLogin}>Đăng nhập</button>
          </div>
          <div className="home-status-grid" aria-label="Trạng thái hệ thống">
            <StatusCard title="Backend" value={backendStatusLabel(backendStatus.state)} tone={backendStatus.state} detail={backendStatus.appName || 'API render và OCR'} />
            <StatusCard title="Provider" value={providerSummary.value} tone={providerSummary.tone} detail={providerSummary.detail} />
            <StatusCard title="Model mặc định" value={backendStatus.settingsDefaults?.default_provider || 'Đang kiểm tra'} tone={backendStatus.state} detail="Có thể đổi trong Setting" />
          </div>
        </div>

        <div className="home-visual-card" aria-label="Minh họa dựng hình toán học">
          <div className="hero-logo-card">
            <img src={logoUrl} alt="AI Math Renderer" />
            <span>Scene AI</span>
          </div>
          <GeometryShowcase />
          <div className="floating-card floating-card-ocr">OCR ảnh</div>
          <div className="floating-card floating-card-geo">GeoGebra 2D</div>
          <div className="floating-card floating-card-three">Three.js 3D</div>
          <div className="floating-card floating-card-json">Scene JSON</div>
        </div>
      </div>

      <div className="feature-grid">
        {features.map((feature) => (
          <article className="feature-card" key={feature.title}>
            <span className="feature-icon">{feature.icon}</span>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>

      <div className="workflow-strip">
        {steps.map((step, index) => (
          <div className="workflow-step" key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusCard({ title, value, detail, tone }: { title: string; value: string; detail: string; tone: HomeBackendStatus['state'] | 'warning' }) {
  return (
    <article className={`home-status-card ${tone}`}>
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function backendStatusLabel(state: HomeBackendStatus['state']) {
  if (state === 'online') return 'Đang hoạt động';
  if (state === 'offline') return 'Mất kết nối';
  return 'Đang kiểm tra';
}

function summarizeProviders(defaults: SettingsDefaults | null): { value: string; detail: string; tone: HomeBackendStatus['state'] | 'warning' } {
  if (!defaults) return { value: 'Đang kiểm tra', detail: 'Đọc cấu hình backend', tone: 'checking' };
  const configured = [
    defaults.openrouter.api_key_configured && 'OpenRouter',
    defaults.nvidia.api_key_configured && 'NVIDIA',
    defaults.router9.api_key_configured && '9router',
  ].filter(Boolean);

  if (configured.length > 0) {
    return { value: `${configured.length} provider sẵn sàng`, detail: configured.join(', '), tone: 'online' };
  }

  return { value: 'Chưa có API key', detail: 'Có thể nhập key tạm thời trong Setting', tone: 'warning' };
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
