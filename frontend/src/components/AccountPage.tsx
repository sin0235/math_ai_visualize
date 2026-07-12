import { useEffect, useState } from 'react';

import type { SessionResponse, UserLearningProfileResponse, UserLearningProfileUpdateRequest, UserResponse } from '../api/client';

type AccountIconName = 'profile' | 'lock' | 'sessions' | 'shield' | 'workspace' | 'logout';
type AccountTab = 'profile' | 'security';
type ToastKind = 'error' | 'warning' | 'info';

interface AccountPageProps {
  user: UserResponse;
  authLoading: boolean;
  onToast: (title: string, message: string, kind?: ToastKind) => void;
  onBackWorkspace: () => void;
  onOpenSettings: () => void;
  onLogout: () => Promise<void>;
  onResendVerification: () => Promise<string>;
  onUpdateProfile: (displayName: string) => Promise<void>;
  learningProfile: UserLearningProfileResponse | null;
  onUpdateLearningProfile: (patch: UserLearningProfileUpdateRequest) => Promise<void>;
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
  onOpenSettings,
  onLogout,
  onResendVerification,
  onUpdateProfile,
  learningProfile,
  onUpdateLearningProfile,
  onChangePassword,
  onLoadSessions,
  onRevokeSession,
  onRevokeOtherSessions,
}: AccountPageProps) {
  const [displayName, setDisplayName] = useState(user.display_name ?? '');
  const [preferredName, setPreferredName] = useState(learningProfile?.preferred_name ?? '');
  const [educationLevel, setEducationLevel] = useState(learningProfile?.education_level ?? '');
  const [gradeLevel, setGradeLevel] = useState(learningProfile?.grade_level ?? '');
  const [mathLevel, setMathLevel] = useState(learningProfile?.math_level ?? '');
  const [explanationStyle, setExplanationStyle] = useState(learningProfile?.preferred_explanation_style ?? '');
  const [learningGoals, setLearningGoals] = useState(toCommaText(learningProfile?.learning_goals));
  const [subjectFocus, setSubjectFocus] = useState(toCommaText(learningProfile?.subject_focus));
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [activeTab, setActiveTab] = useState<AccountTab>('profile');
  const [sessionsLoaded, setSessionsLoaded] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDisplayName(user.display_name ?? '');
  }, [user.display_name]);

  useEffect(() => {
    setPreferredName(learningProfile?.preferred_name ?? '');
    setEducationLevel(learningProfile?.education_level ?? '');
    setGradeLevel(learningProfile?.grade_level ?? '');
    setMathLevel(learningProfile?.math_level ?? '');
    setExplanationStyle(learningProfile?.preferred_explanation_style ?? '');
    setLearningGoals(toCommaText(learningProfile?.learning_goals));
    setSubjectFocus(toCommaText(learningProfile?.subject_focus));
  }, [learningProfile]);

  useEffect(() => {
    if (activeTab !== 'security' || sessionsLoaded) return;
    refreshSessions()
      .then(() => setSessionsLoaded(true))
      .catch((error) =>
        onToast('Phiên đăng nhập', error instanceof Error ? error.message : 'Không thể tải phiên đăng nhập.', 'error'),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tải một lần khi mở tab bảo mật
  }, [activeTab, sessionsLoaded]);

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

  async function submitLearningProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      await onUpdateLearningProfile({
        preferred_name: emptyToNull(preferredName),
        education_level: emptyToNull(educationLevel),
        grade_level: emptyToNull(gradeLevel),
        math_level: emptyToNull(mathLevel),
        preferred_explanation_style: emptyToNull(explanationStyle),
        learning_goals: toTextList(learningGoals),
        subject_focus: toTextList(subjectFocus),
      });
      onToast('Hồ sơ học tập', 'Hồ sơ học tập đã được cập nhật.', 'info');
    } catch (error) {
      onToast('Hồ sơ học tập', error instanceof Error ? error.message : 'Không thể cập nhật hồ sơ học tập.', 'error');
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

  const accountStats = [
    { label: 'Gói', value: formatLabel(user.plan) },
    { label: 'Vai trò', value: user.role === 'admin' ? 'Admin' : 'Người dùng' },
    { label: 'Tạo tài khoản', value: formatDate(user.created_at) },
    { label: 'Đăng nhập gần nhất', value: formatOptionalDate(user.last_login_at) },
  ];
  const securityRows = [
    { label: 'Trạng thái tài khoản', value: user.status === 'active' ? 'Đang hoạt động' : 'Đã vô hiệu hóa' },
    { label: 'Xác minh email', value: user.email_verified_at ? formatDate(user.email_verified_at) : 'Chưa xác minh' },
    { label: 'Đổi mật khẩu gần nhất', value: formatOptionalDate(user.password_changed_at) },
    { label: 'Phiên đang mở', value: String(sessions.length) },
  ];

  return (
    <section className="login-page account-page">
      <div className="account-card account-shell">
        <div className="account-hero">
          <div className="account-identity">
            <div className="account-avatar" aria-hidden="true">{getInitial(user.display_name || user.email)}</div>
            <div>
              <div className={user.email_verified_at ? 'status-pill success' : 'status-pill warning'}>
                {user.email_verified_at ? 'Email đã xác minh' : 'Chưa xác minh email'}
              </div>
              <h2>{user.display_name || user.email}</h2>
              <p className="field-hint">Quản lý hồ sơ, bảo mật và thiết bị đăng nhập.</p>
            </div>
          </div>
          <div className="account-stat-grid">
            {accountStats.map((item) => (
              <div className="account-stat" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="account-tabs" role="tablist" aria-label="Khu vực tài khoản">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'profile'}
            aria-controls="account-profile-panel"
            className={activeTab === 'profile' ? 'active' : ''}
            onClick={() => setActiveTab('profile')}
          >
            <AccountIcon name="profile" />
            <span><strong>Profile</strong><small>Thông tin và hồ sơ học tập</small></span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'security'}
            aria-controls="account-security-panel"
            className={activeTab === 'security' ? 'active' : ''}
            onClick={() => setActiveTab('security')}
          >
            <AccountIcon name="shield" />
            <span><strong>Security</strong><small>Mật khẩu và phiên đăng nhập</small></span>
          </button>
        </div>

        <div
          id={`account-${activeTab}-panel`}
          className="account-layout"
          role="tabpanel"
          aria-label={activeTab === 'profile' ? 'Profile' : 'Security'}
        >
          <main className="account-main">
            {activeTab === 'profile' && (
              <>
            <form className="account-panel account-panel-card" onSubmit={submitProfile}>
              <div className="account-section-title">
                <div className="account-panel-title"><AccountIcon name="profile" /><h3>Hồ sơ</h3></div>
                <button type="submit" className="secondary-button" disabled={loading}>Lưu hồ sơ</button>
              </div>
              <div className="account-form-grid">
                <label className="field-label">
                  Email
                  <input value={user.email} disabled />
                </label>
                <label className="field-label">
                  Tên hiển thị
                  <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Tên của bạn" maxLength={256} />
                </label>
              </div>
            </form>

            <form className="account-panel account-panel-card" onSubmit={submitLearningProfile}>
              <div className="account-section-title">
                <div className="account-panel-title"><AccountIcon name="profile" /><h3>Hồ sơ học tập</h3></div>
                <button type="submit" className="secondary-button" disabled={loading}>Lưu học tập</button>
              </div>
              <div className="account-form-grid account-learning-grid">
                <label className="field-label">
                  Tên gọi khi học
                  <input value={preferredName} onChange={(event) => setPreferredName(event.target.value)} placeholder="Ví dụ: Minh" maxLength={256} />
                </label>
                <label className="field-label">
                  Cấp học
                  <input value={educationLevel} onChange={(event) => setEducationLevel(event.target.value)} placeholder="THCS, THPT, đại học..." maxLength={64} />
                </label>
                <label className="field-label">
                  Lớp
                  <input value={gradeLevel} onChange={(event) => setGradeLevel(event.target.value)} placeholder="Ví dụ: 12" maxLength={64} />
                </label>
                <label className="field-label">
                  Mức toán
                  <input value={mathLevel} onChange={(event) => setMathLevel(event.target.value)} placeholder="cơ bản, nâng cao..." maxLength={64} />
                </label>
                <label className="field-label">
                  Mục tiêu học
                  <input value={learningGoals} onChange={(event) => setLearningGoals(event.target.value)} placeholder="ôn thi, hiểu hình không gian" />
                </label>
                <label className="field-label">
                  Chủ đề ưu tiên
                  <input value={subjectFocus} onChange={(event) => setSubjectFocus(event.target.value)} placeholder="hình Oxyz, hàm số" />
                </label>
                <label className="field-label account-learning-wide">
                  Cách giải thích ưa thích
                  <input value={explanationStyle} onChange={(event) => setExplanationStyle(event.target.value)} placeholder="ngắn gọn, từng bước, trực quan..." maxLength={128} />
                </label>
              </div>
              <p className="field-hint">Các mục nhiều giá trị cách nhau bằng dấu phẩy.</p>
            </form>
              </>
            )}

            {activeTab === 'security' && (
            <div className="account-panel account-panel-card account-sessions-panel">
              <div className="account-section-title">
                <div className="account-panel-title"><AccountIcon name="sessions" /><h3>Phiên đăng nhập</h3></div>
                <button type="button" className="secondary-button" onClick={handleRevokeOthers} disabled={loading || sessions.length <= 1}>Đăng xuất thiết bị khác</button>
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
                {!sessionsLoaded && <p className="field-hint">Đang tải phiên đăng nhập...</p>}
                {sessionsLoaded && sessions.length === 0 && <p className="field-hint">Chưa có phiên đăng nhập nào.</p>}
              </div>
            </div>
            )}
          </main>

          <aside className="account-side">
            {activeTab === 'security' && (
              <>
            <div className="account-panel account-panel-card">
              <div className="account-panel-title"><AccountIcon name="shield" /><h3>Bảo mật</h3></div>
              <div className="account-info-grid">
                {securityRows.map((item) => (
                  <div className="account-info-row" key={item.label}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
              {!user.email_verified_at && (
                <button type="button" onClick={handleResendVerification} disabled={loading}>Gửi lại email xác minh</button>
              )}
            </div>

            <form className="account-panel account-panel-card" onSubmit={submitPassword}>
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
              <p className="field-hint">Tối thiểu 10 ký tự, nên có chữ và số hoặc ký tự khác.</p>
              <button type="submit" disabled={loading}>Đổi mật khẩu</button>
            </form>
              </>
            )}

            <div className="account-panel account-panel-card account-quick-actions">
              <button type="button" className="icon-button-content" onClick={onBackWorkspace}><AccountIcon name="workspace" />Vào workspace</button>
              <button type="button" className="secondary-button" onClick={onOpenSettings}>Cài đặt AI</button>
              <button type="button" className="secondary-button icon-button-content" onClick={onLogout} disabled={authLoading}><AccountIcon name="logout" />Đăng xuất</button>
            </div>
          </aside>
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

function getInitial(value: string) {
  return (value.trim()[0] || 'A').toUpperCase();
}

function toCommaText(values?: string[] | null) {
  return values?.join(', ') ?? '';
}

function toTextList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function emptyToNull(value: string) {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function formatLabel(value: string) {
  return value ? value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()) : 'Free';
}

function formatOptionalDate(value?: string | null) {
  return value ? formatDate(value) : 'Chưa có dữ liệu';
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN');
}