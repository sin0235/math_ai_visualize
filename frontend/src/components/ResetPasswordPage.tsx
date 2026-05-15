import { useState } from 'react';

type ToastKind = 'error' | 'warning' | 'info';

interface ResetPasswordPageProps {
  token: string;
  onResetPassword: (token: string, password: string) => Promise<string>;
  onBackLogin: () => void;
  onToast: (title: string, message: string, kind?: ToastKind) => void;
}

export function ResetPasswordPage({ token, onResetPassword, onBackLogin, onToast }: ResetPasswordPageProps) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const strength = passwordStrength(password);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      onToast('Đặt lại mật khẩu', 'Liên kết đặt lại mật khẩu không hợp lệ hoặc thiếu token.', 'error');
      return;
    }
    if (password.length < 10) {
      onToast('Đặt lại mật khẩu', 'Mật khẩu mới cần tối thiểu 10 ký tự.', 'error');
      return;
    }
    if (password !== confirmPassword) {
      onToast('Đặt lại mật khẩu', 'Mật khẩu xác nhận chưa khớp.', 'error');
      return;
    }
    setLoading(true);
    try {
      await onResetPassword(token, password);
      setPassword('');
      setConfirmPassword('');
    } catch (error) {
      onToast('Đặt lại mật khẩu', error instanceof Error ? error.message : 'Không thể đặt lại mật khẩu.', 'error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page auth-focus-page">
      <form className="login-form standalone-auth-card auth-flow-card" onSubmit={handleSubmit}>
        <div className="auth-page-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 7a4 4 0 1 0-3.46 3.97L4 18.5V21h2.5L14 13.5" />
            <path d="M17 14v7" />
            <path d="M13.5 17.5h7" />
          </svg>
        </div>
        <span className="home-eyebrow">Đặt lại mật khẩu</span>
        <h2>Tạo mật khẩu mới để quay lại workspace</h2>
        <p className="field-hint auth-flow-copy">
          {token ? 'Sau khi đặt lại, các phiên đăng nhập cũ sẽ bị thu hồi. Bạn sẽ quay lại trang đăng nhập để mở workspace bằng mật khẩu mới.' : 'Liên kết đặt lại mật khẩu không hợp lệ hoặc thiếu token. Hãy yêu cầu email đặt lại mật khẩu mới.'}
        </p>
        {token && (
          <>
            <label className="field-label">
              Mật khẩu mới
              <PasswordInput value={password} visible={showPassword} onChange={setPassword} onToggle={() => setShowPassword((value) => !value)} autoComplete="new-password" />
              <span className="input-hint">Tối thiểu 10 ký tự. Nên kết hợp chữ, số và ký tự đặc biệt.</span>
            </label>
            <div className={`password-strength strength-${strength.level}`} aria-live="polite">
              <span style={{ width: `${strength.score}%` }} />
              <strong>{strength.label}</strong>
            </div>
            <label className="field-label">
              Nhập lại mật khẩu mới
              <PasswordInput value={confirmPassword} visible={showConfirmPassword} onChange={setConfirmPassword} onToggle={() => setShowConfirmPassword((value) => !value)} autoComplete="new-password" />
            </label>
          </>
        )}
        <div className="auth-actions auth-actions-split">
          {token && <button type="submit" disabled={loading}>{loading ? 'Đang xử lý...' : 'Đặt lại và quay lại đăng nhập'}</button>}
          <button type="button" className="secondary-button" onClick={onBackLogin}>Quay lại đăng nhập</button>
        </div>
      </form>
    </section>
  );
}

function PasswordInput({ value, visible, onChange, onToggle, autoComplete }: { value: string; visible: boolean; onChange: (value: string) => void; onToggle: () => void; autoComplete: string }) {
  return (
    <div className="password-field">
      <input type={visible ? 'text' : 'password'} value={value} onChange={(event) => onChange(event.target.value)} placeholder="••••••••••" autoComplete={autoComplete} minLength={10} required />
      <button type="button" className="password-field-toggle" onClick={onToggle} aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={visible}>
        {visible ? 'Ẩn' : 'Hiện'}
      </button>
    </div>
  );
}

function passwordStrength(password: string) {
  const checks = [password.length >= 10, /[A-ZÀ-Ỹ]/.test(password), /\d/.test(password), /[^A-Za-zÀ-ỹ0-9]/.test(password)];
  const count = checks.filter(Boolean).length;
  if (!password) return { level: 'empty', score: 8, label: 'Chưa nhập mật khẩu' };
  if (count <= 1) return { level: 'weak', score: 30, label: 'Yếu' };
  if (count <= 3) return { level: 'medium', score: 68, label: 'Ổn' };
  return { level: 'strong', score: 100, label: 'Mạnh' };
}
