import type { Notification } from '../hooks/useNotifications';

export function NotificationStack({ notifications, onDismiss }: { notifications: Notification[]; onDismiss: (id: number) => void }) {
  if (notifications.length === 0) return null;
  return (
    <div className="notification-stack" role="region" aria-label="Thông báo" aria-live="polite">
      {notifications.map((notification) => (
        <section className={`notification-card ${notification.kind}`} key={notification.id} role="status">
          <div className="notification-header">
            <strong>{notification.title}</strong>
            <button type="button" className="notification-close" onClick={() => onDismiss(notification.id)} aria-label="Đóng thông báo">×</button>
          </div>
          <p>{notification.message}</p>
          {notification.action && (
            notification.action.href ? (
              <a className="notification-action" href={notification.action.href}>{notification.action.label}</a>
            ) : (
              <button type="button" className="notification-action" onClick={notification.action.onClick}>{notification.action.label}</button>
            )
          )}
          {notification.details.length > 0 && (
            <details className="notification-details">
              <summary>Chi tiết và hướng dẫn</summary>
              <ul>
                {notification.details.map((detail) => <li key={detail}>{detail}</li>)}
              </ul>
            </details>
          )}
        </section>
      ))}
    </div>
  );
}
