import { useEffect, useState } from 'react';

interface VerifyEmailPageProps {
  token: string;
  onVerifyEmail: (token: string) => Promise<void>;
  onBackWorkspace: () => void;
  onBackLogin: () => void;
}

export function VerifyEmailPage({ token, onVerifyEmail, onBackWorkspace, onBackLogin }: VerifyEmailPageProps) {
  const [message, setMessage] = useState('Đang xác minh email...');
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    onVerifyEmail(token)
      .then(() => {
        if (!cancelled) {
          setMessage('Email đã được xác minh thành công.');
          setDone(true);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : 'Không thể xác minh email.');
          setDone(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, onVerifyEmail]);

  return (
    <section className="login-page">
      <div className="login-form standalone-auth-card">
        <span className="home-eyebrow">Xác minh email</span>
        <h2>Bảo vệ tài khoản của bạn</h2>
        <p className="field-hint">{message}</p>
        {done && (
          <div className="auth-actions">
            <button type="button" onClick={onBackWorkspace}>Vào workspace</button>
            <button type="button" className="secondary-button" onClick={onBackLogin}>Trang đăng nhập</button>
          </div>
        )}
      </div>
    </section>
  );
}
