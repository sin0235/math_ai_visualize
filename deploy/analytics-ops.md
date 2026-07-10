# Analytics & Monitoring — vận hành

## Endpoints

| Method | Path | Ai dùng |
|--------|------|---------|
| POST | `/api/telemetry/client-error` | FE lỗi client |
| POST | `/api/telemetry/events` | FE page.view / feature.open (user login) |
| GET | `/api/admin/analytics/overview` | Admin dashboard |
| GET | `/api/admin/analytics/renders` | Fail rate, duration |
| GET | `/api/admin/analytics/errors` | Recent errors |
| GET | `/api/admin/analytics/error-groups` | Fingerprint groups |
| GET | `/api/admin/analytics/activity` | Activity feed |
| GET | `/api/admin/analytics/funnel` | Register → verify → render + feature opens |
| GET | `/api/admin/analytics/ai-usage` | Token/latency by provider |
| GET | `/api/admin/analytics/users/{id}/timeline` | User journey |
| GET | `/api/admin/analytics/export` | CSV export |
| POST | `/api/admin/analytics/run-alerts` | Chạy alert checks thủ công |

## Env

```bash
LOG_FORMAT=json
TELEMETRY_CLIENT_ENABLED=true
SENTRY_DSN=                    # optional
ALERT_WEBHOOK_URL=             # Slack/Discord webhook optional
ALERT_ERROR_SPIKE_THRESHOLD=30
ALERT_RENDER_FAIL_RATE_PERCENT=25
ANALYTICS_RETENTION_ERRORS_DAYS=90
ANALYTICS_RETENTION_ACTIVITY_DAYS=180
ANALYTICS_RETENTION_AI_METRICS_DAYS=180
```

## Tables

- `user_activity_events` — product behavior
- `error_events` — server/client/worker errors
- `usage_events` — quota
- `ai_call_metrics` — provider latency + tokens
- `audit_logs` — auth/admin

## Worker jobs

Render worker (hourly): alert checks.  
Daily: retention delete old analytics rows.

## Response playbook

1. Spike errors → Admin Phân tích → error groups → fingerprint.
2. Render fail rate → renders by status + provider.
3. Queue lag → check worker process / logs.
4. Rollback app if bad deploy: push previous `product` SHA.
