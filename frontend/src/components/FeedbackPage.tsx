import { useEffect, useState } from 'react';
import { ApiError, getFeedbackStatus, getMyFeedback, submitFeedback, type FeedbackResponse, type FeedbackStatusResponse, type UserResponse } from '../api/client';

interface FeedbackPageProps {
  user: UserResponse | null;
  onLogin: () => void;
  onBackWorkspace: () => void;
  onToast: (title: string, message: string, kind?: 'error' | 'warning' | 'info') => void;
}

export function FeedbackPage({ user, onLogin, onBackWorkspace, onToast }: FeedbackPageProps) {
  const [status, setStatus] = useState<FeedbackStatusResponse | null>(null);
  const [items, setItems] = useState<FeedbackResponse[]>([]);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    void loadFeedback();
  }, [user?.id]);

  async function loadFeedback() {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextItems] = await Promise.all([getFeedbackStatus(), getMyFeedback()]);
      setStatus(nextStatus);
      setItems(nextItems);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Không thể tải góp ý.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const cleanSubject = subject.trim();
    const cleanMessage = message.trim();
    if (cleanSubject.length < 3) {
      setError('Tiêu đề góp ý cần ít nhất 3 ký tự.');
      return;
    }
    if (cleanMessage.length < 10) {
      setError('Nội dung góp ý cần ít nhất 10 ký tự.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback(cleanSubject, cleanMessage);
      setSubject('');
      setMessage('');
      await loadFeedback();
      onToast('Đã gửi góp ý', 'Cảm ơn bạn. Admin sẽ tiếp nhận góp ý này.', 'info');
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Không thể gửi góp ý.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!user) {
    return (
      <section className="feedback-page product-page-card">
        <div className="page-title-row">
          <div>
            <p className="eyebrow">Góp ý sản phẩm</p>
            <h2>Đăng nhập để gửi góp ý</h2>
            <p>Mỗi tài khoản có thể gửi một góp ý đang chờ. Sau khi admin tiếp nhận, bạn có thể gửi góp ý mới.</p>
          </div>
        </div>
        <div className="feedback-actions">
          <button type="button" className="primary-button" onClick={onLogin}>Đăng nhập</button>
          <button type="button" className="secondary-button" onClick={onBackWorkspace}>Về workspace</button>
        </div>
      </section>
    );
  }

  const pending = status?.pending_feedback ?? null;
  const canSubmit = Boolean(status?.can_submit && !pending);

  return (
    <section className="feedback-page product-page-card">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Góp ý sản phẩm</p>
          <h2>Gửi góp ý cho Hình</h2>
          <p>Gửi lỗi, đề xuất, hoặc điểm chưa rõ. Mỗi tài khoản chỉ có một góp ý đang chờ tiếp nhận.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onBackWorkspace}>Về workspace</button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <p className="muted-text">Đang tải góp ý...</p>}

      {!loading && pending && (
        <div className="feedback-pending-card">
          <div className="feedback-card-header">
            <span className="feedback-status-badge pending">Đang chờ</span>
            <span>{formatDate(pending.created_at)}</span>
          </div>
          <h3>{pending.subject}</h3>
          <p>{pending.message}</p>
          <p className="muted-text">Admin cần đánh dấu đã tiếp nhận trước khi bạn gửi góp ý tiếp theo.</p>
        </div>
      )}

      {!loading && canSubmit && (
        <form className="feedback-form" onSubmit={handleSubmit}>
          <label>
            <span className="field-label">Tiêu đề</span>
            <input value={subject} maxLength={120} onChange={(event) => setSubject(event.target.value)} placeholder="Ví dụ: OCR đọc sai hình tam giác" />
          </label>
          <label>
            <span className="field-label">Nội dung</span>
            <textarea value={message} maxLength={4000} rows={8} onChange={(event) => setMessage(event.target.value)} placeholder="Mô tả góp ý, bước tái hiện, hoặc mong muốn của bạn..." />
          </label>
          <div className="feedback-actions">
            <button type="submit" className="primary-button" disabled={submitting}>{submitting ? 'Đang gửi...' : 'Gửi góp ý'}</button>
            <span className="muted-text">{message.trim().length}/4000 ký tự</span>
          </div>
        </form>
      )}

      <div className="feedback-history">
        <h3>Lịch sử góp ý</h3>
        {items.length === 0 ? (
          <p className="muted-text">Chưa có góp ý nào.</p>
        ) : (
          <div className="feedback-history-list">
            {items.map((item) => (
              <article className="feedback-history-item" key={item.id}>
                <div className="feedback-card-header">
                  <span className={`feedback-status-badge ${item.status}`}>{statusLabel(item.status)}</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
                <h4>{item.subject}</h4>
                <p>{item.message}</p>
                {item.admin_note && <p className="feedback-admin-note">Admin: {item.admin_note}</p>}
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function statusLabel(status: FeedbackResponse['status']) {
  if (status === 'received') return 'Đã tiếp nhận';
  if (status === 'accepted') return 'Đã chấp nhận';
  return 'Đang chờ';
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}
