import { useEffect, useState } from 'react';
import { ApiError } from '../api/client';

export type Notification = {
  id: number;
  kind: 'error' | 'warning' | 'info';
  title: string;
  message: string;
  details: string[];
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
};

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    if (notifications.length === 0) return;
    const timers = notifications.map((item) => window.setTimeout(() => dismissNotification(item.id), 10000));
    return () => timers.forEach(window.clearTimeout);
  }, [notifications]);

  function showNotification(title: string, message: string, details: string[] = [], kind: Notification['kind'] = 'error', action?: Notification['action']) {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setNotifications((current) => [...current.slice(-2), { id, kind, title, message: friendlyMessage(message), details: friendlyDetails(details), action }]);
  }

  function dismissNotification(id: number) {
    setNotifications((current) => current.filter((item) => item.id !== id));
  }

  function showApiError(title: string, error: ApiError, fallbackSuggestion: string) {
    const details = error.details.length > 0 ? error.details : [fallbackSuggestion];
    showNotification(errorTitle(title, error.message), error.message, details, 'error');
  }

  function showWarnings(warnings: string[]) {
    if (warnings.length === 0) return;
    const usedMock = warnings.some((warning) => warning.includes('đang dùng mock extractor'));
    showNotification(
      'Đã dựng hình với lưu ý',
      usedMock ? 'Hình đã được tạo, nhưng hệ thống phải dùng phương án dự phòng.' : 'Hình đã được tạo, nhưng một số lần gọi model trước đó bị lỗi.',
      warnings,
      'warning',
    );
  }

  function showAnalyzerWarnings(warnings: string[]) {
    if (warnings.length === 0) return;
    showNotification('Phân tích có lưu ý', 'Kết quả đã được tạo, nhưng có một số lưu ý cần kiểm tra.', warnings, 'warning');
  }

  return { notifications, showNotification, dismissNotification, showApiError, showWarnings, showAnalyzerWarnings };
}

function friendlyMessage(message: string) {
  const text = message.trim();
  if (!text) return 'Có lỗi xảy ra. Hãy thử lại hoặc đổi cấu hình model.';
  if (/MAINTENANCE_MODE|bảo trì/i.test(text)) return text.replace(/^\[MAINTENANCE_MODE\]\s*/, '') || 'Hệ thống đang bảo trì. Vui lòng quay lại sau.';
  if (/PLAN_QUOTA_EXCEEDED|hạn mức.*gói/i.test(text)) return text.replace(/^\[PLAN_QUOTA_EXCEEDED\]\s*/, '') || 'Bạn đã hết hạn mức sử dụng hôm nay của gói hiện tại.';
  if (/Không kết nối được backend|Failed to fetch|NetworkError|ERR_|ECONNREFUSED|Load failed|fetch failed|timeout|timed out|Request quá lâu|quá tải/i.test(text)) return 'Hệ thống đang quá tải do lượng người dùng tăng cao. Vui lòng thử lại sau ít phút.';
  if (/quota|rate limit|429/i.test(text)) return 'Hệ thống đang nhận quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.';
  if (/api key|unauthorized|401|403|forbidden/i.test(text)) return 'Hệ thống chưa sẵn sàng xử lý yêu cầu này. Vui lòng thử lại sau hoặc liên hệ quản trị viên.';
  if (/model.*not found|not found.*model/i.test(text)) return 'Dịch vụ tạo hình hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút.';
  if (/validation|field required|Input should/i.test(text)) return 'Dữ liệu hình chưa hợp lệ. Hãy thử dựng lại hoặc chỉnh hình đơn giản hơn.';
  return text.length > 220 ? `${text.slice(0, 217)}...` : text;
}

function errorTitle(fallback: string, message: string) {
  if (/MAINTENANCE_MODE|bảo trì/i.test(message)) return 'Hệ thống đang bảo trì';
  if (/PLAN_QUOTA_EXCEEDED|hạn mức.*gói/i.test(message)) return 'Bạn đã hết hạn mức gói';
  if (/Không kết nối được backend|Failed to fetch|NetworkError|ERR_|ECONNREFUSED|Load failed|fetch failed|timeout|timed out|Request quá lâu|quá tải/i.test(message)) return 'Hệ thống đang quá tải';
  return fallback;
}

function friendlyDetails(details: string[]) {
  if (details.length === 0) return [];
  return details.map((detail) => friendlyDetail(detail)).filter(Boolean).slice(0, 6);
}

function friendlyDetail(detail: string) {
  const text = detail.trim();
  if (!text) return '';
  if (/mock extractor/i.test(text)) return 'AI provider hiện không sẵn sàng nên hệ thống dùng hình mẫu dự phòng.';
  if (/Không kết nối được backend|Failed to fetch|NetworkError|ERR_|ECONNREFUSED|Load failed|fetch failed|timeout|timed out|Request quá lâu|quá tải/i.test(text)) return '';
  if (/Đã thử:|provider|router9|openrouter|nvidia|ollama/i.test(text)) return 'Dịch vụ AI hiện chưa sẵn sàng, hệ thống sẽ thử lại khi bạn gửi yêu cầu mới.';
  if (/api key|unauthorized|401|403|forbidden/i.test(text)) return 'Hệ thống cần quản trị viên kiểm tra lại cấu hình dịch vụ.';
  if (/PLAN_QUOTA_EXCEEDED|hạn mức.*gói/i.test(text)) return text.replace(/^\[PLAN_QUOTA_EXCEEDED\]\s*/, '') || 'Chờ sang ngày mới hoặc nâng cấp gói để có thêm lượt sử dụng.';
  if (/MAINTENANCE_MODE|bảo trì/i.test(text)) return text.replace(/^\[MAINTENANCE_MODE\]\s*/, '') || 'Hệ thống đang tạm bảo trì, vui lòng quay lại sau.';
  if (/quota|rate limit|429/i.test(text)) return 'Hệ thống đang nhận quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.';
  if (/not found|404/i.test(text)) return 'Dịch vụ tạo hình hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút.';
  return text.length > 240 ? `${text.slice(0, 237)}...` : text;
}
