import { useState } from 'react';

import type { UserResponse } from '../api/client';

interface LoginPageProps {
  logoUrl: string;
  user: UserResponse | null;
  authLoading: boolean;
  onBackHome: () => void;
  onContinueAsGuest: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string, displayName?: string) => Promise<void>;
  onForgotPassword: (email: string) => Promise<string>;
  onLogout: () => Promise<void>;
  onOpenAccount: () => void;
}

type AuthMode = 'login' | 'register' | 'forgot';

export function LoginPage({ logoUrl, user, authLoading, onBackHome, onContinueAsGuest, onLogin, onRegister, onForgotPassword, onLogout, onOpenAccount }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [mode, setMode] = useState<AuthMode>('login');
  const [message, setMessage] = useState('');

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    try {
      if (mode === 'forgot') {
        setMessage(await onForgotPassword(email));
        return;
      }
      if (mode === 'login') {
        await onLogin(email, password);
        setMessage('Đăng nhập thành công. Lịch sử dựng hình và cấu hình cá nhân đã được bật.');
        return;
      }
      if (password !== confirmPassword) {
        setMessage('Mật khẩu xác nhận chưa khớp.');
        return;
      }
      await onRegister(email, password, displayName);
      setMessage('Tạo tài khoản thành công. Hãy kiểm tra email để xác minh tài khoản.');
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
          <span className="home-eyebrow">{user ? 'Tài khoản' : mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Tạo tài khoản' : 'Quên mật khẩu'}</span>
          <h2>{user ? 'Workspace của bạn đã được đồng bộ' : mode === 'forgot' ? 'Khôi phục quyền truy cập' : 'Quay lại workspace của bạn'}</h2>
          {user ? (
            <>
              <p className="field-hint">Bạn đang đăng nhập bằng <strong>{user.email}</strong>. {user.email_verified_at ? 'Email đã được xác minh.' : 'Email chưa được xác minh.'}</p>
              <div className="auth-actions">
                <button type="button" onClick={onOpenAccount}>Quản lý tài khoản</button>
                <button type="button" className="secondary-button" onClick={onContinueAsGuest}>Vào workspace</button>
                <button type="button" className="secondary-button" onClick={onLogout} disabled={authLoading}>Đăng xuất</button>
              </div>
            </>
          ) : (
            <>
              <p className="field-hint">{mode === 'forgot' ? 'Nhập email tài khoản. Nếu email tồn tại, hệ thống sẽ gửi liên kết đặt lại mật khẩu.' : 'Đăng nhập để lưu lịch sử dựng hình và bộ cấu hình cá nhân. API key provider không được lưu lên server.'}</p>
              {mode === 'register' && (
                <label className="field-label">
                  Tên hiển thị
                  <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Tên của bạn" maxLength={256} />
                </label>
              )}
              <label className="field-label">
                Email
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" required />
              </label>
              {mode !== 'forgot' && (
                <label className="field-label">
                  Mật khẩu
                  <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'login' ? 1 : 10} required />
                </label>
              )}
              {mode === 'register' && (
                <>
                  <label className="field-label">
                    Nhập lại mật khẩu
                    <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="••••••••••" autoComplete="new-password" minLength={10} required />
                  </label>
                  <p className="field-hint">Mật khẩu nên dài ít nhất 10 ký tự và kết hợp chữ với số hoặc ký tự khác.</p>
                </>
              )}
              <div className="auth-mode-toggle" role="group" aria-label="Chọn chế độ tài khoản">
                <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Đăng nhập</button>
                <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Tạo tài khoản</button>
                <button type="button" className={mode === 'forgot' ? 'active' : ''} onClick={() => setMode('forgot')}>Quên mật khẩu</button>
              </div>
              <div className="auth-actions">
                <button type="submit" disabled={authLoading}>{authLoading ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Tạo tài khoản' : 'Gửi hướng dẫn'}</button>
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
