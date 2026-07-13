import { apiUrl } from '../api/core';

const CLIENT_SESSION_KEY = 'hinh-client-session-id';
const recentFingerprints = new Map<string, number>();
const DEDUPE_MS = 15_000;
const eventQueue: Array<{ event_type: string; path?: string; feature?: string; metadata?: Record<string, unknown> }> = [];
let flushTimer: number | null = null;

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

function shouldReport(message: string, component?: string): boolean {
  const key = `${component || ''}|${message}`.slice(0, 200);
  const now = Date.now();
  const last = recentFingerprints.get(key);
  if (last && now - last < DEDUPE_MS) return false;
  recentFingerprints.set(key, now);
  if (recentFingerprints.size > 100) {
    const oldest = [...recentFingerprints.entries()].sort((a, b) => a[1] - b[1]).slice(0, 40);
    for (const [k] of oldest) recentFingerprints.delete(k);
  }
  return true;
}

function isIgnorableClientError(message: string, name?: string): boolean {
  if (name === 'AbortError') return true;
  return /abort(ed)?|AbortError|The user aborted|signal is aborted|Failed to fetch|NetworkError|Load failed/i.test(message);
}

export function reportClientError(input: {
  message: string;
  error_code?: string;
  stack?: string;
  route?: string;
  component?: string;
  metadata?: Record<string, unknown>;
}): void {
  const message = String(input.message || 'Unknown client error').slice(0, 1000);
  if (isIgnorableClientError(message)) return;
  if (!shouldReport(message, input.component)) return;

  let pathname = '/';
  try {
    pathname = window.location.pathname;
  } catch {
    /* ignore */
  }

  const payload = {
    message,
    error_code: input.error_code || 'CLIENT_ERROR',
    stack: input.stack?.slice(0, 4000),
    route: input.route || pathname,
    component: input.component,
    metadata: {
      client_session_id: getClientSessionId(),
      pathname,
      ...(input.metadata && typeof input.metadata === 'object'
        ? Object.fromEntries(
          Object.entries(input.metadata)
            .filter(([key]) => ['title', 'kind', 'component', 'feature'].includes(key))
            .slice(0, 8)
            .map(([key, value]) => [key, typeof value === 'string' ? value.slice(0, 300) : value]),
        )
        : {}),
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

export function trackPageView(path: string): void {
  enqueueEvent({ event_type: 'page.view', path: path.slice(0, 300) });
}

export function trackFeatureOpen(feature: string): void {
  enqueueEvent({ event_type: 'feature.open', feature: feature.slice(0, 64), path: window.location.pathname });
}

export type NlpTelemetryCode =
  | 'unknown_intent'
  | 'low_confidence'
  | 'clarification_shown'
  | 'clarification_accepted'
  | 'clarification_edited'
  | 'canonical_validation_failure'
  | 'solver_unsupported'
  | 'explainer_fallback'
  | 'shadow_mismatch';

export function trackNlpEvent(input: {
  taxonomyCode: NlpTelemetryCode;
  target: 'render' | 'geometry_solve' | 'algebra' | 'analyzer' | 'ocr';
  status?: 'accepted' | 'needs_confirmation' | 'abstained' | 'unsupported';
  confidence?: number;
  candidateCount?: number;
  adapterVersion?: string;
  requestId?: string;
}): void {
  enqueueEvent({
    event_type: 'nlp.preflight',
    metadata: {
      taxonomy_code: input.taxonomyCode,
      target: input.target,
      status: input.status,
      confidence_bucket: confidenceBucket(input.confidence),
      candidate_count: input.candidateCount,
      adapter_version: input.adapterVersion?.slice(0, 80),
      request_id: input.requestId?.slice(0, 80),
    },
  });
}

function confidenceBucket(confidence?: number) {
  if (confidence === undefined || !Number.isFinite(confidence)) return undefined;
  if (confidence < 0.2) return 'very_low';
  if (confidence < 0.4) return 'low';
  if (confidence < 0.65) return 'medium';
  if (confidence < 0.85) return 'high';
  return 'very_high';
}

function enqueueEvent(event: { event_type: string; path?: string; feature?: string; metadata?: Record<string, unknown> }): void {
  eventQueue.push(event);
  if (eventQueue.length >= 12) {
    void flushEvents();
    return;
  }
  if (flushTimer == null) {
    flushTimer = window.setTimeout(() => {
      flushTimer = null;
      void flushEvents();
    }, 4000);
  }
}

export async function flushEvents(): Promise<void> {
  if (eventQueue.length === 0) return;
  const batch = eventQueue.splice(0, 40);
  try {
    await fetch(apiUrl('/api/telemetry/events'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        client_session_id: getClientSessionId(),
        events: batch,
      }),
      keepalive: true,
    });
  } catch {
    /* drop on failure — analytics must not break UX */
  }
}

export function installGlobalErrorReporting(): void {
  window.addEventListener('error', (event) => {
    const msg = event.message || 'window.error';
    if (isIgnorableClientError(msg)) return;
    reportClientError({
      message: msg,
      stack: event.error?.stack,
      component: 'window.onerror',
    });
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    const name = reason instanceof Error ? reason.name : undefined;
    const message = reason instanceof Error ? reason.message : String(reason || 'unhandledrejection');
    if (isIgnorableClientError(message, name)) return;
    reportClientError({
      message,
      stack: reason instanceof Error ? reason.stack : undefined,
      component: 'unhandledrejection',
    });
  });
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void flushEvents();
  });
}
