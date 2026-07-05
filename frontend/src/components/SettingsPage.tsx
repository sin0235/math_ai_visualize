import { ByokSettingsPanel } from './ByokSettingsPanel';

type ToastKind = 'error' | 'warning' | 'info';

interface SettingsPageProps {
  onToast: (title: string, message: string, kind?: ToastKind) => void;
  onBackWorkspace: () => void;
  onOpenAccount: () => void;
}

export function SettingsPage({ onToast, onBackWorkspace, onOpenAccount }: SettingsPageProps) {
  return (
    <section className="login-page account-page settings-page">
      <div className="account-card account-shell settings-shell">
        <div className="account-hero settings-hero">
          <div className="account-identity">
            <SettingsIcon />
            <div>
              <div className="status-pill success">Cấu hình cá nhân</div>
              <h2>Cài đặt</h2>
              <p className="field-hint">Cấu hình AI cá nhân và model theo tác vụ.</p>
            </div>
          </div>
          <div className="settings-action-row">
            <button type="button" className="secondary-button" onClick={onOpenAccount}>Tài khoản</button>
            <button type="button" className="secondary-button" onClick={onBackWorkspace}>Vào workspace</button>
          </div>
        </div>

        <ByokSettingsPanel onToast={onToast} />
      </div>
    </section>
  );
}

function SettingsIcon() {
  return (
    <span className="account-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 8.92 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.36.64.98 1 1.6 1h.09a2 2 0 1 1 0 4H21c-.62 0-1.24.36-1.6 1Z" />
      </svg>
    </span>
  );
}