import { useEffect, useState } from 'react';

import type { SessionResponse, UserResponse } from '../api/client';

interface AccountPageProps {
  user: UserResponse;
  authLoading: boolean;
  onBackWorkspace: () => void;
  onLogout: () => Promise<void>;
  onResendVerification: () => Promise<string>;
  onUpdateProfile: (displayName: string) => Promise<void>;
  onChangePassword: (currentPassword: string, newPassword: string) => Promise<string>;
  onLoadSessions: () => Promise<SessionResponse[]>;
  onRevokeSession: (id: string) => Promise<string>;
  onRevokeOtherSessions: () => Promise<string>;
}

export function AccountPage({
  user,
  authLoading,
  onBackWorkspace,
  onLogout,
  onResendVerification,
  onUpdateProfile,
  onChangePassword,
  onLoadSessions,
  onRevokeSession,
  onRevokeOtherSessions,
}: AccountPageProps) {
  const [displayName, setDisplayName] = useState(user.display_name ?? '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDisplayName(user.display_name ?? '');
  }, [user.display_name]);

  useEffect(() => {
    refreshSessions().catch((error) => setMessage(error instanceof Error ? error.message : 'Không thể tải phiên đăng nhập.'));
  }, []);

  async function refreshSessions() {
    setSessions(await onLoadSessions());
  }

  async function submitProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      await onUpdateProfile(displayName);
      setMessage('Hồ sơ đã được cập nhật.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể cập nhật hồ sơ.');
    } finally {
      setLoading(false);
    }
  }

  async function submitPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    if (newPassword !== confirmPassword) {
      setMessage('Mật khẩu xác nhận chưa khớp.');
      return;
    }
    setLoading(true);
    try {
      setMessage(await onChangePassword(currentPassword, newPassword));
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      await refreshSessions();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể đổi mật khẩu.');
    } finally {
      setLoading(false);
    }
  }

  async function handleResendVerification() {
    setLoading(true);
    setMessage('');
    try {
      setMessage(await onResendVerification());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể gửi lại email xác minh.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeSession(id: string) {
    setLoading(true);
    setMessage('');
    try {
      setMessage(await onRevokeSession(id));
      await refreshSessions();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể thu hồi phiên.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeOthers() {
    setLoading(true);
    setMessage('');
    try {
      setMessage(await onRevokeOtherSessions());
      await refreshSessions();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể thu hồi các phiên khác.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page">
      <div className="account-card">
        <div className="account-header">
          <div>
            <h2>{user.display_name || user.email}</h2>
            <p className="field-hint">Quản lý bảo mật, hồ sơ và các phiên đăng nhập của bạn.</p>
          </div>
          <div className={user.email_verified_at ? 'status-pill success' : 'status-pill warning'}>
            {user.email_verified_at ? 'Email đã xác minh' : 'Chưa xác minh email'}
          </div>
        </div>

        {!user.email_verified_at && (
          <div className="account-panel highlight-panel">
            <strong>Xác minh email để bảo vệ tài khoản.</strong>
            <p className="field-hint">Nếu chưa thấy email, bạn có thể gửi lại liên kết xác minh.</p>
            <button type="button" onClick={handleResendVerification} disabled={loading}>Gửi lại email xác minh</button>
          </div>
        )}

        <div className="account-grid">
          <form className="account-panel" onSubmit={submitProfile}>
            <h3>Hồ sơ</h3>
            <label className="field-label">
              Email
              <input value={user.email} disabled />
            </label>
            <label className="field-label">
              Tên hiển thị
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Tên của bạn" maxLength={256} />
            </label>
            <button type="submit" disabled={loading}>Lưu hồ sơ</button>
          </form>

          <form className="account-panel" onSubmit={submitPassword}>
            <h3>Đổi mật khẩu</h3>
            <label className="field-label">
              Mật khẩu hiện tại
              <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required />
            </label>
            <label className="field-label">
              Mật khẩu mới
              <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={10} required />
            </label>
            <label className="field-label">
              Nhập lại mật khẩu mới
              <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={10} required />
            </label>
            <p className="field-hint">Mật khẩu mới nên dài ít nhất 10 ký tự và kết hợp chữ với số hoặc ký tự khác.</p>
            <button type="submit" disabled={loading}>Đổi mật khẩu</button>
          </form>
        </div>

        <div className="account-panel">
          <div className="account-section-title">
            <h3>Phiên đăng nhập</h3>
            <button type="button" className="secondary-button" onClick={handleRevokeOthers} disabled={loading}>Đăng xuất thiết bị khác</button>
          </div>
          <div className="session-list">
            {sessions.map((session) => (
              <div className="session-item" key={session.id}>
                <div>
                  <strong>{session.current ? 'Phiên hiện tại' : 'Thiết bị khác'}</strong>
                  <p>{session.user_agent || 'Không rõ trình duyệt'}</p>
                  <span>{session.ip_address || 'Không rõ IP'} · hoạt động {formatDate(session.last_seen_at || session.created_at)}</span>
                </div>
                {!session.current && <button type="button" className="secondary-button" onClick={() => handleRevokeSession(session.id)} disabled={loading}>Thu hồi</button>}
              </div>
            ))}
            {sessions.length === 0 && <p className="field-hint">Chưa có phiên đăng nhập nào.</p>}
          </div>
        </div>

        <div className="auth-actions">
          <button type="button" onClick={onBackWorkspace}>Vào workspace</button>
          <button type="button" className="secondary-button" onClick={onLogout} disabled={authLoading}>Đăng xuất</button>
        </div>
        {message && <p className="login-message">{message}</p>}
      </div>
    </section>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN');
}
