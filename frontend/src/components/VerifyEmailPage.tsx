import { useState } from 'react';

interface VerifyEmailPageProps {
  token: string;
  onVerifyEmail: (token: string, otp: string) => Promise<void>;
  onBackWorkspace: () => void;
  onBackLogin: () => void;
}

export function VerifyEmailPage({ token, onVerifyEmail, onBackWorkspace, onBackLogin }: VerifyEmailPageProps) {
  const [otp, setOtp] = useState('');
  const [message, setMessage] = useState(token ? 'Nhập mã OTP gồm 6 chữ số trong email xác minh.' : 'Liên kết xác minh không hợp lệ hoặc thiếu token.');
  const [loading, setLoading] = useState(false);
  const [verified, setVerified] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanOtp = otp.replace(/\s/g, '');
    if (!token) {
      setMessage('Liên kết xác minh không hợp lệ hoặc thiếu token.');
      return;
    }
    if (!/^\d{6}$/.test(cleanOtp)) {
      setMessage('Mã OTP phải gồm 6 chữ số.');
      return;
    }
    setLoading(true);
    try {
      await onVerifyEmail(token, cleanOtp);
      setVerified(true);
      setMessage('Email đã được xác minh thành công. Bạn có thể quay lại đăng nhập hoặc mở workspace.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể xác minh email.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page">
      <form className="login-form standalone-auth-card" onSubmit={handleSubmit}>
        <span className="home-eyebrow">Xác minh email</span>
        <h2>Bảo vệ tài khoản của bạn</h2>
        <p className="field-hint">{message}</p>
        {token && !verified && (
          <label className="field-label">
            Mã OTP
            <input
              className="otp-input"
              value={otp}
              onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="123456"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
            />
          </label>
        )}
        <div className="auth-actions">
          {token && !verified && <button type="submit" disabled={loading}>{loading ? 'Đang xác minh...' : 'Xác minh email'}</button>}
          {verified && <button type="button" onClick={onBackLogin}>Trang đăng nhập</button>}
          <button type="button" className="secondary-button" onClick={onBackWorkspace}>Vào workspace</button>
        </div>
      </form>
    </section>
  );
}
