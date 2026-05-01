import { useState } from 'react';

import type { UserResponse } from '../api/client';

interface LoginPageProps {
  logoUrl: string;
  user: UserResponse | null;
  authLoading: boolean;
  onBackHome: () => void;
  onContinueAsGuest: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
  onLogout: () => Promise<void>;
}

export function LoginPage({ logoUrl, user, authLoading, onBackHome, onContinueAsGuest, onLogin, onRegister, onLogout }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [message, setMessage] = useState('');

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    try {
      if (mode === 'login') {
        await onLogin(email, password);
        setMessage('Đăng nhập thành công. Lịch sử dựng hình và cấu hình cá nhân đã được bật.');
      } else {
        await onRegister(email, password);
        setMessage('Tạo tài khoản thành công. Bạn có thể lưu lịch sử dựng hình từ bây giờ.');
      }
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không thể xử lý đăng nhập.');
    }
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
          <span className="home-eyebrow">{user ? 'Tài khoản' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</span>
          <h2>{user ? 'Workspace của bạn đã được đồng bộ' : 'Quay lại workspace của bạn'}</h2>
          {user ? (
            <>
              <p className="field-hint">Bạn đang đăng nhập bằng <strong>{user.email}</strong>. Render mới sẽ được lưu vào Cloudflare D1 nếu backend đang dùng D1.</p>
              <div className="auth-actions">
                <button type="button" onClick={onContinueAsGuest}>Vào workspace</button>
                <button type="button" className="secondary-button" onClick={onLogout} disabled={authLoading}>Đăng xuất</button>
              </div>
            </>
          ) : (
            <>
              <p className="field-hint">Đăng nhập để lưu lịch sử dựng hình và bộ cấu hình cá nhân. API key provider không được lưu lên server.</p>
              <label className="field-label">
                Email
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" required />
              </label>
              <label className="field-label">
                Mật khẩu
                <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} required />
              </label>
              <div className="auth-mode-toggle" role="group" aria-label="Chọn chế độ tài khoản">
                <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Đăng nhập</button>
                <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Tạo tài khoản</button>
              </div>
              <div className="auth-actions">
                <button type="submit" disabled={authLoading}>{authLoading ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</button>
                <button type="button" className="secondary-button" onClick={onContinueAsGuest}>Tiếp tục không cần đăng nhập</button>
              </div>
            </>
          )}
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
