import { useState } from 'react';

interface LoginPageProps {
  logoUrl: string;
  onBackHome: () => void;
  onContinueAsGuest: () => void;
}

export function LoginPage({ logoUrl, onBackHome, onContinueAsGuest }: LoginPageProps) {
  const [message, setMessage] = useState('');

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('Tính năng tài khoản sẽ được kết nối sau. Bạn vẫn có thể tiếp tục dựng hình ngay.');
  }

  return (
    <section className="login-page">
      <div className="login-card">
        <div className="login-visual">
          <div className="login-brand">
            <img src={logoUrl} alt="AI Math Renderer" />
            <div>
              <span>AI Math Renderer</span>
              <strong>Không gian học hình học thông minh</strong>
            </div>
          </div>
          <LoginIllustration />
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <span className="home-eyebrow">Đăng nhập</span>
          <h2>Quay lại workspace của bạn</h2>
          <p className="field-hint">Đăng nhập sẽ dùng cho lịch sử dựng hình và bộ cấu hình cá nhân. Hiện tại bạn có thể tiếp tục không cần tài khoản.</p>
          <label className="field-label">
            Email
            <input type="email" placeholder="you@example.com" autoComplete="email" />
          </label>
          <label className="field-label">
            Mật khẩu
            <input type="password" placeholder="••••••••" autoComplete="current-password" />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" />
            Ghi nhớ phiên đăng nhập
          </label>
          <div className="auth-actions">
            <button type="submit">Đăng nhập</button>
            <button type="button" className="secondary-button" onClick={onContinueAsGuest}>Tiếp tục không cần đăng nhập</button>
          </div>
          <button type="button" className="link-button" onClick={onBackHome}>Quay về trang chủ</button>
          {message && <p className="login-message">{message}</p>}
        </form>
      </div>
    </section>
  );
}

function LoginIllustration() {
  return (
    <svg className="login-illustration" viewBox="0 0 460 360" role="img" aria-label="Bảo mật workspace toán học">
      <defs>
        <linearGradient id="loginShield" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#eff6ff" />
          <stop offset="1" stopColor="#ede9fe" />
        </linearGradient>
      </defs>
      <rect x="28" y="28" width="404" height="286" rx="30" fill="#ffffff" stroke="#d4d4d4" />
      <path d="M230 72L320 104V170C320 228 284 270 230 292C176 270 140 228 140 170V104L230 72Z" fill="url(#loginShield)" stroke="#111827" strokeWidth="4" />
      <path d="M190 184L218 212L274 148" fill="none" stroke="#2563eb" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M86 254L150 204M374 250L312 204M94 116L146 142M366 116L314 142" stroke="#94a3b8" strokeWidth="3" strokeDasharray="7 8" strokeLinecap="round" />
      {[[86, 254, 'A'], [374, 250, 'B'], [94, 116, 'C'], [366, 116, 'D']].map(([cx, cy, label]) => (
        <g key={label as string}>
          <circle cx={cx as number} cy={cy as number} r="15" fill="#111827" />
          <text x={(cx as number) - 5} y={(cy as number) + 6} fill="#ffffff" fontSize="16" fontWeight="800">{label}</text>
        </g>
      ))}
      <text x="172" y="322" fill="#475569" fontSize="18" fontWeight="700">Secure math workspace</text>
    </svg>
  );
}
