import { useEffect, useState } from 'react';
import { ByokSettingsPanel } from './ByokSettingsPanel';
import {
  getBrowserNotifyEnabled,
  getBrowserNotifyOnlyWhenHidden,
  getBrowserNotifyPermission,
  isBrowserNotifySupported,
  requestBrowserNotifyPermission,
  setBrowserNotifyEnabled,
  setBrowserNotifyOnlyWhenHidden,
  showBrowserNotify,
  type BrowserNotifyPermission,
} from '../utils/browserNotify';

type ToastKind = 'error' | 'warning' | 'info';

interface SettingsPageProps {
  onToast: (title: string, message: string, kind?: ToastKind) => void;
  onBackWorkspace: () => void;
  onOpenAccount: () => void;
}

export function SettingsPage({ onToast, onBackWorkspace, onOpenAccount }: SettingsPageProps) {
  const supported = isBrowserNotifySupported();
  const [permission, setPermission] = useState<BrowserNotifyPermission>(() => getBrowserNotifyPermission());
  const [enabled, setEnabled] = useState(() => getBrowserNotifyEnabled());
  const [onlyHidden, setOnlyHidden] = useState(() => getBrowserNotifyOnlyWhenHidden());

  useEffect(() => {
    setPermission(getBrowserNotifyPermission());
    setEnabled(getBrowserNotifyEnabled());
    setOnlyHidden(getBrowserNotifyOnlyWhenHidden());
  }, []);

  async function handleEnable() {
    const next = await requestBrowserNotifyPermission();
    setPermission(next);
    if (next === 'granted') {
      setBrowserNotifyEnabled(true);
      setEnabled(true);
      onToast('Thông báo hệ thống', 'Đã bật. Bạn sẽ nhận thông báo khi dựng hình/giải xong nếu đang ở tab khác.', 'info');
      showBrowserNotify({
        title: 'Thông báo đã bật',
        body: 'Math AI Renderer sẽ báo khi công việc dài hoàn tất.',
        kind: 'info',
        tag: 'notify-test',
        onlyWhenHidden: false,
        force: true,
      });
      return;
    }
    if (next === 'denied') {
      setBrowserNotifyEnabled(false);
      setEnabled(false);
      onToast('Thông báo hệ thống', 'Trình duyệt đã chặn thông báo. Hãy bật lại trong cài đặt site của trình duyệt.', 'warning');
      return;
    }
    onToast('Thông báo hệ thống', 'Chưa nhận được quyền thông báo.', 'warning');
  }

  function handleToggleEnabled(next: boolean) {
    if (next && permission !== 'granted') {
      void handleEnable();
      return;
    }
    setBrowserNotifyEnabled(next);
    setEnabled(next);
    onToast('Thông báo hệ thống', next ? 'Đã bật thông báo hệ thống.' : 'Đã tắt thông báo hệ thống.', 'info');
  }

  function handleOnlyHidden(next: boolean) {
    setBrowserNotifyOnlyWhenHidden(next);
    setOnlyHidden(next);
  }

  return (
    <section className="login-page account-page settings-page">
      <div className="account-card account-shell settings-shell">
        <div className="account-hero settings-hero">
          <div className="account-identity">
            <SettingsIcon />
            <div>
              <div className="status-pill success">Cấu hình cá nhân</div>
              <h2>Cài đặt</h2>
              <p className="field-hint">Cấu hình AI cá nhân, model theo tác vụ và thông báo hệ thống.</p>
            </div>
          </div>
          <div className="settings-action-row">
            <button type="button" className="secondary-button" onClick={onOpenAccount}>Tài khoản</button>
            <button type="button" className="secondary-button" onClick={onBackWorkspace}>Vào workspace</button>
          </div>
        </div>

        <section className="settings-notify-card" aria-labelledby="browser-notify-heading">
          <h3 id="browser-notify-heading">Thông báo hệ thống</h3>
          <p className="field-hint">
            Nhận thông báo ngoài trang khi dựng hình hoặc giải xong — hữu ích khi bạn đang xem tab khác.
            Không dùng Web Push; chỉ hoạt động khi site vẫn mở.
          </p>
          {!supported && (
            <p className="field-hint">Trình duyệt này không hỗ trợ Notification API.</p>
          )}
          {supported && (
            <>
              <p className="field-hint">Quyền trình duyệt: <strong>{permissionLabel(permission)}</strong></p>
              <label className="settings-toggle-row">
                <input
                  type="checkbox"
                  checked={enabled && permission === 'granted'}
                  disabled={permission === 'denied'}
                  onChange={(event) => handleToggleEnabled(event.target.checked)}
                />
                <span>Bật thông báo hệ thống</span>
              </label>
              <label className="settings-toggle-row">
                <input
                  type="checkbox"
                  checked={onlyHidden}
                  disabled={!enabled || permission !== 'granted'}
                  onChange={(event) => handleOnlyHidden(event.target.checked)}
                />
                <span>Chỉ báo khi tab đang ẩn (khuyến nghị)</span>
              </label>
              {permission === 'default' && (
                <button type="button" className="primary-button" onClick={() => void handleEnable()}>
                  Xin quyền thông báo
                </button>
              )}
              {permission === 'denied' && (
                <p className="field-hint">
                  Bạn đã chặn thông báo. Mở biểu tượng ổ khóa trên thanh địa chỉ → Quyền thông báo → Cho phép, rồi tải lại trang.
                </p>
              )}
            </>
          )}
        </section>

        <ByokSettingsPanel onToast={onToast} />
      </div>
    </section>
  );
}

function permissionLabel(permission: BrowserNotifyPermission): string {
  if (permission === 'granted') return 'Đã cho phép';
  if (permission === 'denied') return 'Đã chặn';
  if (permission === 'unsupported') return 'Không hỗ trợ';
  return 'Chưa hỏi';
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
