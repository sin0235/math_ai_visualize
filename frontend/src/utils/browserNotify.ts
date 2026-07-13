/**
 * Browser Notification API helpers (phase 1 — no Web Push server).
 * In-app toast remains primary; OS notifications are optional and opt-in.
 */

export type BrowserNotifyPermission = NotificationPermission | 'unsupported';

export type BrowserNotifyKind = 'error' | 'warning' | 'info';

export type BrowserNotifyOptions = {
  title: string;
  body?: string;
  kind?: BrowserNotifyKind;
  /** Dedupe / replace previous of same category. */
  tag?: string;
  requireInteraction?: boolean;
  icon?: string;
  /**
   * When true (default for most workflows), only fire if document is hidden.
   * Pass false to force when focused (rarely used).
   */
  onlyWhenHidden?: boolean;
  /**
   * Skip user preference check (e.g. after user just granted permission).
   */
  force?: boolean;
};

const STORAGE_ENABLED = 'math_ai_browser_notify_enabled';
const STORAGE_ONLY_HIDDEN = 'math_ai_browser_notify_only_hidden';
const STORAGE_PROMPTED = 'math_ai_browser_notify_prompted';
const STORAGE_SOFT_DISMISSED = 'math_ai_browser_notify_soft_dismissed';

const IMPORTANT_TITLE_HINTS = [
  'dựng hình',
  'giải',
  'lời giải',
  'không giải',
  'thất bại',
  'lỗi',
  'cần xác nhận',
  'chưa đủ',
  'lưu ý',
  'gợi ý',
];

export function isBrowserNotifySupported(): boolean {
  return typeof window !== 'undefined' && typeof Notification !== 'undefined';
}

export function getBrowserNotifyPermission(): BrowserNotifyPermission {
  if (!isBrowserNotifySupported()) return 'unsupported';
  return Notification.permission;
}

export function getBrowserNotifyEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem(STORAGE_ENABLED);
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    // Default: treat as enabled only after browser permission granted.
    return getBrowserNotifyPermission() === 'granted';
  } catch {
    return false;
  }
}

export function setBrowserNotifyEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_ENABLED, enabled ? 'true' : 'false');
  } catch {
    // ignore quota / private mode
  }
}

export function getBrowserNotifyOnlyWhenHidden(): boolean {
  try {
    const raw = window.localStorage.getItem(STORAGE_ONLY_HIDDEN);
    if (raw === 'false') return false;
    return true;
  } catch {
    return true;
  }
}

export function setBrowserNotifyOnlyWhenHidden(onlyHidden: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_ONLY_HIDDEN, onlyHidden ? 'true' : 'false');
  } catch {
    // ignore
  }
}

export function hasSoftPromptedBrowserNotify(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_PROMPTED) === 'true'
      || window.localStorage.getItem(STORAGE_SOFT_DISMISSED) === 'true';
  } catch {
    return true;
  }
}

export function markBrowserNotifySoftPrompted(): void {
  try {
    window.localStorage.setItem(STORAGE_PROMPTED, 'true');
  } catch {
    // ignore
  }
}

export function markBrowserNotifySoftDismissed(): void {
  try {
    window.localStorage.setItem(STORAGE_SOFT_DISMISSED, 'true');
    window.localStorage.setItem(STORAGE_PROMPTED, 'true');
  } catch {
    // ignore
  }
}

/** Soft prompt is eligible after first successful long workflow if permission still default. */
export function shouldShowBrowserNotifySoftPrompt(): boolean {
  if (!isBrowserNotifySupported()) return false;
  if (getBrowserNotifyPermission() !== 'default') return false;
  if (hasSoftPromptedBrowserNotify()) return false;
  return true;
}

export async function requestBrowserNotifyPermission(): Promise<BrowserNotifyPermission> {
  if (!isBrowserNotifySupported()) return 'unsupported';
  markBrowserNotifySoftPrompted();
  try {
    const result = await Notification.requestPermission();
    if (result === 'granted') setBrowserNotifyEnabled(true);
    if (result === 'denied') setBrowserNotifyEnabled(false);
    return result;
  } catch {
    return getBrowserNotifyPermission();
  }
}

export function isDocumentHidden(): boolean {
  if (typeof document === 'undefined') return false;
  return Boolean(document.hidden);
}

export function truncateNotifyBody(text: string, max = 120): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}

export function isImportantWorkflowNotification(title: string, kind: BrowserNotifyKind): boolean {
  if (kind === 'error' || kind === 'warning') return true;
  const lower = title.toLowerCase();
  return IMPORTANT_TITLE_HINTS.some((hint) => lower.includes(hint));
}

export function canShowBrowserNotify(options: {
  onlyWhenHidden?: boolean;
  force?: boolean;
  kind?: BrowserNotifyKind;
  title?: string;
} = {}): boolean {
  if (!isBrowserNotifySupported()) return false;
  if (getBrowserNotifyPermission() !== 'granted') return false;
  if (!options.force && !getBrowserNotifyEnabled()) return false;
  const onlyHidden = options.onlyWhenHidden ?? getBrowserNotifyOnlyWhenHidden();
  if (onlyHidden && !isDocumentHidden()) return false;
  // force=true (post-grant test / explicit UI) skips the workflow importance filter.
  if (
    !options.force
    && options.title
    && options.kind
    && !isImportantWorkflowNotification(options.title, options.kind)
  ) {
    return false;
  }
  return true;
}

export function showBrowserNotify(options: BrowserNotifyOptions): boolean {
  const kind = options.kind ?? 'info';
  const onlyWhenHidden = options.onlyWhenHidden ?? getBrowserNotifyOnlyWhenHidden();
  if (!canShowBrowserNotify({
    onlyWhenHidden,
    force: options.force,
    kind,
    title: options.title,
  })) {
    return false;
  }

  const body = truncateNotifyBody(options.body || '');
  try {
    const notification = new Notification(options.title, {
      body: body || undefined,
      tag: options.tag || `math-ai-${kind}`,
      icon: options.icon || '/logo.svg',
      requireInteraction: options.requireInteraction ?? kind === 'error',
      silent: false,
    });
    notification.onclick = () => {
      try {
        window.focus();
      } catch {
        // ignore
      }
      notification.close();
    };
    return true;
  } catch {
    return false;
  }
}

/**
 * Bridge from in-app toast API → optional OS notification.
 * Returns whether a browser notification was shown.
 */
export function maybeBrowserNotifyFromToast(
  title: string,
  message: string,
  kind: BrowserNotifyKind = 'info',
  details: string[] = [],
  tag?: string,
): boolean {
  if (!isImportantWorkflowNotification(title, kind)) return false;
  const bodyParts = [message, ...details].filter(Boolean);
  return showBrowserNotify({
    title,
    body: bodyParts.join(' · '),
    kind,
    tag: tag || defaultTagForTitle(title, kind),
  });
}

function defaultTagForTitle(title: string, kind: BrowserNotifyKind): string {
  const t = title.toLowerCase();
  if (t.includes('dựng hình') && (t.includes('thất') || kind === 'error')) return 'render-error';
  if (t.includes('dựng hình') && (t.includes('xác nhận') || t.includes('lưu ý'))) return 'render-warn';
  if (t.includes('dựng hình')) return 'render-done';
  if (t.includes('giải') && kind === 'error') return 'solve-error';
  if (t.includes('giải') && kind === 'warning') return 'solve-warn';
  if (t.includes('giải') || t.includes('lời giải')) return 'solve-done';
  return `math-ai-${kind}`;
}

export const browserNotifyStorageKeys = {
  enabled: STORAGE_ENABLED,
  onlyHidden: STORAGE_ONLY_HIDDEN,
  prompted: STORAGE_PROMPTED,
  softDismissed: STORAGE_SOFT_DISMISSED,
} as const;
