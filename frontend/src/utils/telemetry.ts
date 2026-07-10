import { apiUrl } from '../api/core';

const CLIENT_SESSION_KEY = 'hinh-client-session-id';

export function getClientSessionId(): string {
  try {
    const existing = window.localStorage.getItem(CLIENT_SESSION_KEY);
    if (existing) return existing;
    const value = crypto.randomUUID();
    window.localStorage.setItem(CLIENT_SESSION_KEY, value);
    return value;
  } catch {
    return 'anonymous';
  }
}

export function reportClientError(input: {
  message: string;
  error_code?: string;
  stack?: string;
  route?: string;
  component?: string;
  metadata?: Record<string, unknown>;
}): void {
  const payload = {
    message: String(input.message || 'Unknown client error').slice(0, 1000),
    error_code: input.error_code || 'CLIENT_ERROR',
    stack: input.stack?.slice(0, 4000),
    route: input.route || window.location.pathname,
    component: input.component,
    metadata: {
      client_session_id: getClientSessionId(),
      href: window.location.href,
      ...(input.metadata || {}),
    },
  };
  void fetch(apiUrl('/api/telemetry/client-error'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {
    /* fire-and-forget */
  });
}

export function installGlobalErrorReporting(): void {
  window.addEventListener('error', (event) => {
    reportClientError({
      message: event.message || 'window.error',
      stack: event.error?.stack,
      component: 'window.onerror',
    });
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    reportClientError({
      message: reason instanceof Error ? reason.message : String(reason || 'unhandledrejection'),
      stack: reason instanceof Error ? reason.stack : undefined,
      component: 'unhandledrejection',
    });
  });
}
