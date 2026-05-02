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
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

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
              <strong>Workspace dựng hình toán học</strong>
            </div>
          </div>
          <div className="login-value-copy">
            <h3>Lưu lại mọi scene, tiếp tục dựng hình ở bất cứ đâu.</h3>
            <p>Đồng bộ lịch sử, cấu hình model và phiên làm việc để biến đề hình học thành bản dựng GeoGebra/Three.js nhanh hơn.</p>
          </div>
          <LoginGeometryIllustration />
          <div className="login-value-grid" aria-label="Giá trị tài khoản">
            <span><strong>Oxy/Oxyz</strong> Scene có cấu trúc</span>
            <span><strong>OCR</strong> Từ ảnh đề bài</span>
            <span><strong>History</strong> Lưu và dựng lại</span>
          </div>
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
              {mode !== 'forgot' && (
                <button type="button" className="oauth-button" onClick={() => setMessage('Google OAuth sẽ được hỗ trợ ở bản tiếp theo.')}>Tiếp tục với Google <span>Sắp có</span></button>
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
                <span className="input-hint">Dùng email thật để nhận link xác minh hoặc đặt lại mật khẩu.</span>
              </label>
              {mode !== 'forgot' && (
                <label className="field-label">
                  Mật khẩu
                  <div className="password-field">
                    <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'login' ? 1 : 10} required />
                    <button type="button" onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'Ẩn' : 'Hiện'}</button>
                  </div>
                  <span className="input-hint">{mode === 'login' ? 'Nhập mật khẩu tài khoản của bạn.' : 'Tối thiểu 10 ký tự, nên kết hợp chữ và số hoặc ký tự khác.'}</span>
                </label>
              )}
              {mode === 'register' && (
                <label className="field-label">
                  Nhập lại mật khẩu
                  <div className="password-field">
                    <input type={showConfirmPassword ? 'text' : 'password'} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="••••••••••" autoComplete="new-password" minLength={10} required />
                    <button type="button" onClick={() => setShowConfirmPassword((value) => !value)}>{showConfirmPassword ? 'Ẩn' : 'Hiện'}</button>
                  </div>
                  <span className="input-hint">Nhập lại đúng mật khẩu để tránh khóa nhầm tài khoản mới.</span>
                </label>
              )}
              <button type="submit" className="auth-primary-button" disabled={authLoading}>{authLoading ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Tạo tài khoản' : 'Gửi hướng dẫn'}</button>
              <div className="auth-secondary-links">
                {mode === 'login' && (
                  <>
                    <span>Chưa có tài khoản? <button type="button" onClick={() => setMode('register')}>Tạo tài khoản</button></span>
                    <button type="button" onClick={() => setMode('forgot')}>Quên mật khẩu?</button>
                  </>
                )}
                {mode === 'register' && <span>Đã có tài khoản? <button type="button" onClick={() => setMode('login')}>Đăng nhập</button></span>}
                {mode === 'forgot' && <span>Nhớ mật khẩu rồi? <button type="button" onClick={() => setMode('login')}>Quay lại đăng nhập</button></span>}
                <button type="button" onClick={onContinueAsGuest}>Tiếp tục không cần đăng nhập</button>
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

function LoginGeometryIllustration() {
  return (
    <svg className="login-illustration" viewBox="0 0 520 380" role="img" aria-label="Scene dựng hình toán học từ AI">
      <defs>
        <linearGradient id="scenePanel" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#dbeafe" />
        </linearGradient>
        <radialGradient id="sceneGlow" cx="48%" cy="38%" r="62%">
          <stop offset="0" stopColor="#60a5fa" stopOpacity="0.42" />
          <stop offset="1" stopColor="#60a5fa" stopOpacity="0" />
        </radialGradient>
        <filter id="sceneShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="16" stdDeviation="14" floodColor="#1e3a8a" floodOpacity="0.18" />
        </filter>
      </defs>
      <rect x="34" y="26" width="452" height="308" rx="32" fill="url(#scenePanel)" stroke="#bfdbfe" filter="url(#sceneShadow)" />
      <circle cx="260" cy="182" r="132" fill="url(#sceneGlow)" />
      {Array.from({ length: 7 }).map((_, index) => <path key={`grid-x-${index}`} d={`M${92 + index * 54} 74V286`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 9" />)}
      {Array.from({ length: 5 }).map((_, index) => <path key={`grid-y-${index}`} d={`M82 ${96 + index * 42}H438`} stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 9" />)}
      <path d="M82 286H438M104 304V74" stroke="#0f172a" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M142 252L260 104L386 252Z" fill="rgba(37,99,235,0.08)" stroke="#111827" strokeWidth="4" strokeLinejoin="round" />
      <path d="M260 104V252" stroke="#7c3aed" strokeWidth="3" strokeDasharray="8 8" />
      <circle cx="142" cy="252" r="46" fill="none" stroke="#2563eb" strokeWidth="4" />
      <path d="M142 252C190 202 222 150 260 104" fill="none" stroke="#f97316" strokeWidth="5" strokeLinecap="round" />
      <path d="M318 138L402 90" stroke="#2563eb" strokeWidth="4" strokeLinecap="round" />
      <rect x="306" y="242" width="116" height="42" rx="21" fill="#111827" />
      <text x="326" y="269" fill="#ffffff" fontSize="15" fontWeight="800">Scene AI</text>
      {[[142, 252, 'A'], [260, 104, 'S'], [386, 252, 'B'], [260, 252, 'H']].map(([cx, cy, label]) => (
        <g key={label as string}>
          <circle cx={cx as number} cy={cy as number} r="8" fill="#111827" />
          <text x={(cx as number) + 12} y={(cy as number) - 10} fill="#111827" fontSize="18" fontWeight="800">{label}</text>
        </g>
      ))}
      <text x="88" y="58" fill="#2563eb" fontSize="16" fontWeight="800">Đề bài → Scene → Renderer</text>
      <text x="94" y="326" fill="#475569" fontSize="15" fontWeight="700">GeoGebra 2D · Three.js 3D · Lịch sử dựng hình</text>
    </svg>
  );
}
