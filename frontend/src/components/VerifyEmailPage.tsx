import { useState } from 'react';

type ToastKind = 'error' | 'warning' | 'info';

interface VerifyEmailPageProps {
  token: string;
  email?: string;
  onVerifyEmail: (token: string, otp: string) => Promise<void>;
  onBackWorkspace: () => void;
  onBackLogin: () => void;
  onToast: (title: string, message: string, kind?: ToastKind) => void;
}

export function VerifyEmailPage({ token, email, onVerifyEmail, onBackWorkspace, onBackLogin, onToast }: VerifyEmailPageProps) {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  function cleanOtpInput(value: string) {
    return value.replace(/\D/g, '').slice(0, 6);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanOtp = cleanOtpInput(otp);
    if (!token) {
      onToast('Xác minh email', 'Liên kết xác minh không hợp lệ hoặc thiếu token. Hãy dùng liên kết mới nhất trong email.', 'error');
      return;
    }
    if (!/^\d{6}$/.test(cleanOtp)) {
      onToast('Xác minh email', 'Mã OTP phải gồm đúng 6 chữ số.', 'error');
      return;
    }
    setLoading(true);
    try {
      await onVerifyEmail(token, cleanOtp);
    } catch (error) {
      onToast('Xác minh email', error instanceof Error ? error.message : 'Không thể xác minh email.', 'error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page auth-focus-page">
      <form className="login-form standalone-auth-card auth-flow-card" onSubmit={handleSubmit}>
        <div className="auth-page-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 5h16v14H4z" />
            <path d="m4 7 8 6 8-6" />
            <path d="m9 16 2 2 4-5" />
          </svg>
        </div>
        <span className="home-eyebrow">Xác minh email</span>
        <h2>Mở khóa workspace bằng mã OTP</h2>
        <p className="field-hint auth-flow-copy">
          {token
            ? <>Nhập mã 6 chữ số đã gửi tới {email ? <strong>{email}</strong> : 'email đăng ký của bạn'}. Mã này giúp kích hoạt lịch sử dựng hình.</>
            : 'Liên kết xác minh không hợp lệ hoặc thiếu token. Hãy mở lại email xác minh mới nhất.'}
        </p>
        {token && (
          <label className="field-label otp-field-label">
            Mã OTP
            <input
              className="otp-input"
              type="text"
              pattern="\d{6}"
              value={otp}
              onChange={(event) => setOtp(cleanOtpInput(event.target.value))}
              onPaste={(event) => {
                event.preventDefault();
                setOtp(cleanOtpInput(event.clipboardData.getData('text')));
              }}
              placeholder="000000"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
            />
            <span className="input-hint">Bạn có thể dán trực tiếp mã từ email. Hệ thống chỉ giữ 6 chữ số.</span>
          </label>
        )}
        <div className="auth-actions auth-actions-split">
          {token && <button type="submit" disabled={loading}>{loading ? 'Đang xác minh...' : 'Xác minh và mở workspace'}</button>}
          <button type="button" className="secondary-button" onClick={onBackLogin}>Quay lại đăng nhập</button>
          <button type="button" className="secondary-button" onClick={onBackWorkspace}>Vào workspace</button>
        </div>
      </form>
    </section>
  );
}
