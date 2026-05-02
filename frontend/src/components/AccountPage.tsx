import { useEffect, useState } from 'react';

import type { SessionResponse, UserResponse } from '../api/client';

type AccountIconName = 'profile' | 'lock' | 'sessions' | 'shield' | 'workspace' | 'logout';
type ToastKind = 'error' | 'warning' | 'info';

interface AccountPageProps {
  user: UserResponse;
  authLoading: boolean;
  onToast: (title: string, message: string, kind?: ToastKind) => void;
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
  onToast,
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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDisplayName(user.display_name ?? '');
  }, [user.display_name]);

  useEffect(() => {
    refreshSessions().catch((error) =>
      onToast('Phiên đăng nhập', error instanceof Error ? error.message : 'Không thể tải phiên đăng nhập.', 'error'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ tải danh sách phiên khi vào trang
  }, []);

  async function refreshSessions() {
    setSessions(await onLoadSessions());
  }

  async function submitProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      await onUpdateProfile(displayName);
      onToast('Hồ sơ', 'Hồ sơ đã được cập nhật.', 'info');
    } catch (error) {
      onToast('Hồ sơ', error instanceof Error ? error.message : 'Không thể cập nhật hồ sơ.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function submitPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      onToast('Đổi mật khẩu', 'Mật khẩu xác nhận chưa khớp.', 'error');
      return;
    }
    setLoading(true);
    try {
      const text = await onChangePassword(currentPassword, newPassword);
      onToast('Đổi mật khẩu', text, 'info');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      await refreshSessions();
    } catch (error) {
      onToast('Đổi mật khẩu', error instanceof Error ? error.message : 'Không thể đổi mật khẩu.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function handleResendVerification() {
    setLoading(true);
    try {
      onToast('Xác minh email', await onResendVerification(), 'info');
    } catch (error) {
      onToast('Xác minh email', error instanceof Error ? error.message : 'Không thể gửi lại email xác minh.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeSession(id: string) {
    setLoading(true);
    try {
      onToast('Phiên đăng nhập', await onRevokeSession(id), 'info');
      await refreshSessions();
    } catch (error) {
      onToast('Phiên đăng nhập', error instanceof Error ? error.message : 'Không thể thu hồi phiên.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeOthers() {
    setLoading(true);
    try {
      onToast('Phiên đăng nhập', await onRevokeOtherSessions(), 'info');
      await refreshSessions();
    } catch (error) {
      onToast('Phiên đăng nhập', error instanceof Error ? error.message : 'Không thể thu hồi các phiên khác.', 'error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page">
      <div className="account-card">
        <div className="account-header">
          <div className="account-header-title">
            <AccountIcon name="shield" />
            <div>
              <h2>{user.display_name || user.email}</h2>
              <p className="field-hint">Quản lý bảo mật, hồ sơ và các phiên đăng nhập của bạn.</p>
            </div>
          </div>
          <div className={user.email_verified_at ? 'status-pill success' : 'status-pill warning'}>
            {user.email_verified_at ? 'Email đã xác minh' : 'Chưa xác minh email'}
          </div>
        </div>

        {!user.email_verified_at && (
          <div className="account-panel highlight-panel">
            <div className="account-panel-title"><AccountIcon name="shield" /><strong>Xác minh email để bảo vệ tài khoản.</strong></div>
            <p className="field-hint">Nếu chưa thấy email, bạn có thể gửi lại liên kết xác minh.</p>
            <button type="button" onClick={handleResendVerification} disabled={loading}>Gửi lại email xác minh</button>
          </div>
        )}

        <div className="account-grid">
          <form className="account-panel" onSubmit={submitProfile}>
            <div className="account-panel-title"><AccountIcon name="profile" /><h3>Hồ sơ</h3></div>
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
            <div className="account-panel-title"><AccountIcon name="lock" /><h3>Đổi mật khẩu</h3></div>
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
            <div className="account-panel-title"><AccountIcon name="sessions" /><h3>Phiên đăng nhập</h3></div>
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
          <button type="button" className="icon-button-content" onClick={onBackWorkspace}><AccountIcon name="workspace" />Vào workspace</button>
          <button type="button" className="secondary-button icon-button-content" onClick={onLogout} disabled={authLoading}><AccountIcon name="logout" />Đăng xuất</button>
        </div>
      </div>
    </section>
  );
}

function AccountIcon({ name }: { name: AccountIconName }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <span className="account-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="20" height="20">
        {name === 'profile' && <><path {...common} d="M20 21a8 8 0 1 0-16 0" /><circle {...common} cx="12" cy="7" r="4" /></>}
        {name === 'lock' && <><rect {...common} x="4" y="10" width="16" height="10" rx="2" /><path {...common} d="M8 10V7a4 4 0 0 1 8 0v3" /></>}
        {name === 'sessions' && <><rect {...common} x="3" y="4" width="18" height="12" rx="2" /><path {...common} d="M8 20h8" /><path {...common} d="M12 16v4" /></>}
        {name === 'shield' && <><path {...common} d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path {...common} d="m9 12 2 2 4-5" /></>}
        {name === 'workspace' && <><path {...common} d="M4 19V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14" /><path {...common} d="M2 19h20" /><path {...common} d="M8 9h8M8 13h5" /></>}
        {name === 'logout' && <><path {...common} d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path {...common} d="M16 17l5-5-5-5" /><path {...common} d="M21 12H9" /></>}
      </svg>
    </span>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN');
}
