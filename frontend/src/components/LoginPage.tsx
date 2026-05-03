import { useState } from 'react';

import type { UserResponse } from '../api/client';

type ToastKind = 'error' | 'warning' | 'info';

interface LoginPageProps {
  logoUrl: string;
  user: UserResponse | null;
  authLoading: boolean;
  onContinueAsGuest: () => void;
  onToast: (title: string, message: string, kind?: ToastKind) => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onGoogleLogin: () => void;
  onRegister: (email: string, password: string, displayName: string | undefined, acceptPrivacyPolicy: boolean, acceptTerms: boolean) => Promise<void>;
  onForgotPassword: (email: string) => Promise<string>;
  onLogout: () => Promise<void>;
  onOpenAccount: () => void;
  onOpenPrivacyPolicy: () => void;
  onOpenTerms: () => void;
}

type AuthMode = 'login' | 'register' | 'forgot';

export function LoginPage({ logoUrl, user, authLoading, onContinueAsGuest, onToast, onLogin, onGoogleLogin, onRegister, onForgotPassword, onLogout, onOpenAccount, onOpenPrivacyPolicy, onOpenTerms }: LoginPageProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [mode, setMode] = useState<AuthMode>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [acceptPrivacyPolicy, setAcceptPrivacyPolicy] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setPassword('');
    setConfirmPassword('');
    setShowPassword(false);
    setShowConfirmPassword(false);
    if (nextMode !== 'register') {
      setDisplayName('');
      setAcceptPrivacyPolicy(false);
      setAcceptTerms(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      onToast('Đăng nhập', 'Hãy nhập email.', 'error');
      return;
    }
    try {
      if (mode === 'forgot') {
        const text = await onForgotPassword(cleanEmail);
        onToast('Quên mật khẩu', text, 'info');
        return;
      }
      if (!password) {
        onToast(mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản', 'Hãy nhập mật khẩu.', 'error');
        return;
      }
      if (mode === 'login') {
        await onLogin(cleanEmail, password);
        onToast('Đăng nhập', 'Đăng nhập thành công. Lịch sử dựng hình và cấu hình cá nhân đã được bật.', 'info');
        return;
      }
      if (password.length < 10) {
        onToast('Tạo tài khoản', 'Mật khẩu cần tối thiểu 10 ký tự.', 'error');
        return;
      }
      if (password !== confirmPassword) {
        onToast('Tạo tài khoản', 'Mật khẩu xác nhận chưa khớp.', 'error');
        return;
      }
      if (!acceptPrivacyPolicy || !acceptTerms) {
        onToast('Tạo tài khoản', 'Bạn cần đồng ý Chính sách bảo mật và Điều khoản sử dụng để tạo tài khoản.', 'error');
        return;
      }
      await onRegister(cleanEmail, password, displayName.trim() || undefined, acceptPrivacyPolicy, acceptTerms);
      onToast('Tạo tài khoản', 'Tạo tài khoản thành công. Hãy kiểm tra email, mở liên kết xác minh và nhập mã OTP.', 'info');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Không thể xử lý đăng nhập.';
      const title = mode === 'register' ? 'Tạo tài khoản' : mode === 'forgot' ? 'Quên mật khẩu' : 'Đăng nhập';
      const hint = /xác minh email|verify/i.test(message) ? `${message} Hãy kiểm tra hộp thư hoặc dùng trang tài khoản để gửi lại email xác minh.` : message;
      onToast(title, hint, 'error');
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
              <strong>Workspace dựng hình toán học</strong>
            </div>
          </div>
          <div className="login-value-copy">
            <h3>Lưu lại mọi scene, tiếp tục dựng hình ở bất cứ đâu.</h3>
            <p>Đồng bộ lịch sử, cấu hình model và phiên làm việc để biến đề hình học thành bản dựng GeoGebra/Three.js nhanh hơn.</p>
          </div>
          <LoginGeometryIllustration />
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
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
              <p className="field-hint">{mode === 'forgot' ? 'Nhập email tài khoản. Nếu email tồn tại, hệ thống sẽ gửi liên kết đặt lại mật khẩu.' : 'AI Math Renderer biến đề bài thành hình GeoGebra và 3D. Đăng nhập để lưu lịch sử dựng hình, giữ cấu hình riêng và tiếp tục chỉnh sửa khi bạn quay lại.'}</p>
              {mode !== 'forgot' && (
                <button type="button" className="oauth-button" onClick={onGoogleLogin} disabled={authLoading}>
                  <svg className="oauth-google-icon" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                  Tiếp tục với Google
                </button>
              )}
              {mode !== 'forgot' && <div className="auth-divider"><span>hoặc dùng email</span></div>}
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
                  <div className="password-field">
                    <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'login' ? 1 : 10} required />
                    <PasswordToggleButton visible={showPassword} onToggle={() => setShowPassword((value) => !value)} />
                  </div>
                  {mode === 'register' && <span className="input-hint">Tối thiểu 10 ký tự, nên kết hợp chữ và số hoặc ký tự khác.</span>}
                </label>
              )}
              {mode === 'login' && (
                <div className="login-forgot-password-row">
                  <button type="button" className="login-forgot-password-link" onClick={() => switchMode('forgot')}>Quên mật khẩu?</button>
                </div>
              )}
              {mode === 'register' && (
                <label className="field-label">
                  Nhập lại mật khẩu
                  <div className="password-field">
                    <input type={showConfirmPassword ? 'text' : 'password'} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="••••••••••" autoComplete="new-password" minLength={10} required />
                    <PasswordToggleButton visible={showConfirmPassword} onToggle={() => setShowConfirmPassword((value) => !value)} />
                  </div>
                  <span className="input-hint">Nhập lại đúng mật khẩu để tránh khóa nhầm tài khoản mới.</span>
                </label>
              )}
              {mode === 'register' && (
                <div className="legal-consent-group">
                  <label className="legal-consent-row">
                    <input type="checkbox" checked={acceptPrivacyPolicy} onChange={(event) => setAcceptPrivacyPolicy(event.target.checked)} />
                    <span>Tôi đã đọc và đồng ý với <button type="button" onClick={onOpenPrivacyPolicy}>Chính sách bảo mật</button>.</span>
                  </label>
                  <label className="legal-consent-row">
                    <input type="checkbox" checked={acceptTerms} onChange={(event) => setAcceptTerms(event.target.checked)} />
                    <span>Tôi đồng ý với <button type="button" onClick={onOpenTerms}>Điều khoản sử dụng</button> của AI Math Renderer.</span>
                  </label>
                </div>
              )}
              <button type="submit" className="auth-primary-button" disabled={authLoading}>{authLoading ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Tạo tài khoản' : 'Gửi hướng dẫn'}</button>
              <button type="button" className="auth-guest-button" onClick={onContinueAsGuest}>Tiếp tục không cần đăng nhập</button>
              <div className="auth-secondary-links">
                {mode === 'login' && (
                  <span>Chưa có tài khoản? <button type="button" onClick={() => switchMode('register')}>Tạo tài khoản</button></span>
                )}
                {mode === 'register' && <span>Đã có tài khoản? <button type="button" onClick={() => switchMode('login')}>Đăng nhập</button></span>}
                {mode === 'forgot' && <span>Nhớ mật khẩu rồi? <button type="button" onClick={() => switchMode('login')}>Quay lại đăng nhập</button></span>}
              </div>
            </>
          )}
        </form>
      </div>
    </section>
  );
}

function PasswordToggleButton({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className="password-field-toggle"
      onClick={onToggle}
      aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
      aria-pressed={visible}
    >
      {visible ? (
        <svg className="password-field-toggle-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
          />
          <path fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" d="M2 2l20 20" />
        </svg>
      ) : (
        <svg className="password-field-toggle-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
          />
          <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
      )}
    </button>
  );
}

function LoginGeometryIllustration() {
  return (
    <svg className="login-illustration" viewBox="0 0 560 420" role="img" aria-label="Scene dựng hình toán học từ AI">
      <defs>
        <linearGradient id="loginIllusGridGradient" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#2563eb" stopOpacity="0.18" />
          <stop offset="1" stopColor="#7c3aed" stopOpacity="0.08" />
        </linearGradient>
        <radialGradient id="loginIllusGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#60a5fa" stopOpacity="0.55" />
          <stop offset="1" stopColor="#60a5fa" stopOpacity="0" />
        </radialGradient>
        <marker id="loginIllusArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" fill="#2563eb" />
        </marker>
      </defs>
      <rect x="24" y="24" width="512" height="348" rx="28" fill="url(#loginIllusGridGradient)" stroke="#d4d4d4" />
      {Array.from({ length: 9 }).map((_, index) => (
        <path key={`login-grid-v-${index}`} d={`M${72 + index * 52} 56V340`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 8" />
      ))}
      {Array.from({ length: 6 }).map((_, index) => (
        <path key={`login-grid-h-${index}`} d={`M56 ${84 + index * 46}H504`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 8" />
      ))}
      <path d="M72 318H500" stroke="#111827" strokeWidth="2" strokeLinecap="round" />
      <path d="M92 338V72" stroke="#111827" strokeWidth="2" strokeLinecap="round" />
      <circle cx="164" cy="286" r="54" fill="none" stroke="#2563eb" strokeWidth="4" />
      <path d="M164 286L312 130L430 286Z" fill="rgba(37,99,235,0.08)" stroke="none" />
      <path d="M164 286L430 286" stroke="#111827" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M312 130L430 286" stroke="#111827" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M312 130V286" stroke="#7c3aed" strokeWidth="3" strokeDasharray="8 9" />
      <path d="M312 286h12v-12h-12z" fill="none" stroke="#111827" strokeWidth="2" strokeLinejoin="miter" />
      <path d="M164 286L312 130" stroke="#f97316" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M356 180L456 116" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" markerEnd="url(#loginIllusArrow)" />
      <circle cx="312" cy="130" r="72" fill="url(#loginIllusGlow)" />
      {[[164, 286, 'A'], [312, 130, 'S'], [430, 286, 'B'], [312, 286, 'H']].map(([cx, cy, label]) => (
        <g key={label as string}>
          <circle cx={cx as number} cy={cy as number} r="8" fill="#111827" />
          <text x={(cx as number) + 12} y={(cy as number) - 12} fill="#111827" fontSize="20" fontWeight="700">{label}</text>
        </g>
      ))}
      <text x="112" y="98" fill="#475569" fontSize="18" fontWeight="700">Đề bài → Scene → Renderer</text>
      <text x="352" y="350" fill="#475569" fontSize="16" fontWeight="400">GeoGebra + Three.js</text>
    </svg>
  );
}
