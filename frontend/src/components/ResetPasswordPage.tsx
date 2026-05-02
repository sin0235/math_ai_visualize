import { useState } from 'react';

interface ResetPasswordPageProps {
  token: string;
  onResetPassword: (token: string, password: string) => Promise<string>;
  onBackLogin: () => void;
}

export function ResetPasswordPage({ token, onResetPassword, onBackLogin }: ResetPasswordPageProps) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    if (password !== confirmPassword) {
      setMessage('Mật khẩu xác nhận chưa khớp.');
      return;
    }
    setLoading(true);
    try {
      setMessage(await onResetPassword(token, password));
      setPassword('');
      setConfirmPassword('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể đặt lại mật khẩu.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page">
      <form className="login-form standalone-auth-card" onSubmit={handleSubmit}>
        <div className="auth-page-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 7a4 4 0 1 0-3.46 3.97L4 18.5V21h2.5L14 13.5" />
            <path d="M17 14v7" />
            <path d="M13.5 17.5h7" />
          </svg>
        </div>
        <span className="home-eyebrow">Đặt lại mật khẩu</span>
        <h2>Tạo mật khẩu mới</h2>
        <p className="field-hint">Sau khi đặt lại mật khẩu, các phiên đăng nhập cũ sẽ bị thu hồi và bạn cần đăng nhập lại.</p>
        <label className="field-label">
          Mật khẩu mới
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={10} autoComplete="new-password" required />
        </label>
        <label className="field-label">
          Nhập lại mật khẩu mới
          <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={10} autoComplete="new-password" required />
        </label>
        <div className="auth-actions">
          <button type="submit" disabled={loading}>{loading ? 'Đang xử lý...' : 'Đặt lại mật khẩu'}</button>
          <button type="button" className="secondary-button" onClick={onBackLogin}>Quay lại đăng nhập</button>
        </div>
        {message && <p className="login-message">{message}</p>}
      </form>
    </section>
  );
}
