import type { ReactNode } from 'react';
import type {
  AdminAnalyticsActivity,
  AdminAnalyticsAiUsage,
  AdminAnalyticsErrors,
  AdminAnalyticsFunnel,
  AdminAnalyticsOverview,
  AdminAnalyticsProductUsage,
  AdminAnalyticsRenders,
} from '../../api/client';
import { adminAnalyticsExportUrl } from '../../api/client';
import { apiUrl } from '../../api/core';
import { formatHistoryDate, MetricCard } from './AdminComponents';

export type AnalyticsSource = 'overview' | 'product' | 'renders' | 'errors' | 'activity' | 'funnel' | 'ai';
export type AnalyticsSourceErrors = Partial<Record<AnalyticsSource, string>>;

interface AdminAnalyticsSectionProps {
  days: number;
  loading: boolean;
  refreshedAt: Date | null;
  sourceErrors: AnalyticsSourceErrors;
  overview: AdminAnalyticsOverview | null;
  productUsage: AdminAnalyticsProductUsage | null;
  renders: AdminAnalyticsRenders | null;
  diagnostics: AdminAnalyticsErrors | null;
  activity: AdminAnalyticsActivity | null;
  funnel: AdminAnalyticsFunnel | null;
  aiUsage: AdminAnalyticsAiUsage | null;
  onDaysChange: (days: number) => void;
  onRefresh: () => void;
}

export function AdminAnalyticsSection({
  days,
  loading,
  refreshedAt,
  sourceErrors,
  overview,
  productUsage,
  renders,
  diagnostics,
  activity,
  funnel,
  aiUsage,
  onDaysChange,
  onRefresh,
}: AdminAnalyticsSectionProps) {
  const topFeature = productUsage?.feature_usage[0];
  const weakestOutcome = [...(productUsage?.outcomes ?? [])]
    .filter((item) => item.completed + item.failed > 0)
    .sort((a, b) => (a.success_rate ?? 100) - (b.success_rate ?? 100))[0];
  const unstableProvider = [...(renders?.by_provider ?? [])]
    .filter((item) => item.completed + item.failed > 0)
    .sort((a, b) => (b.fail_rate ?? 0) - (a.fail_rate ?? 0))[0];
  const slowProvider = [...(renders?.by_provider ?? [])]
    .filter((item) => item.avg_ms != null)
    .sort((a, b) => (b.avg_ms ?? 0) - (a.avg_ms ?? 0))[0];
  const topError = diagnostics?.top_codes[0];
  const failedSources = Object.keys(sourceErrors).length;

  return (
    <>
      <header className="admin-page-header admin-analytics-header">
        <div>
          <h2>Phân tích hành vi sản phẩm</h2>
          <p>Độ phủ tính năng, độ tin cậy luồng và hiệu suất AI trong {days} ngày gần nhất.</p>
        </div>
        <div className="admin-analytics-actions">
          <label>
            <span className="sr-only">Khoảng thời gian phân tích</span>
            <select value={days} onChange={(event) => onDaysChange(Number(event.target.value))} disabled={loading}>
              <option value={7}>7 ngày</option>
              <option value={14}>14 ngày</option>
              <option value={30}>30 ngày</option>
            </select>
          </label>
          <a className="secondary-button" href={apiUrl(adminAnalyticsExportUrl('errors', days))} target="_blank" rel="noreferrer">Errors CSV</a>
          <a className="secondary-button" href={apiUrl(adminAnalyticsExportUrl('activity', days))} target="_blank" rel="noreferrer">Activity CSV</a>
          <button type="button" className="secondary-button" onClick={onRefresh} disabled={loading} aria-busy={loading}>
            {loading ? 'Đang tải…' : 'Làm mới'}
          </button>
        </div>
      </header>

      <div className="admin-section-stack admin-analytics-dashboard">
        <div className="admin-analytics-scope" role="note">
          <strong>Phạm vi mẫu:</strong> feature/page analytics chỉ gồm người dùng đã đăng nhập. Lỗi có thể gồm khách. Token phản ánh mức tiêu thụ, không phải chi phí tiền.
          <span>{refreshedAt ? `Cập nhật ${formatHistoryDate(refreshedAt.toISOString())}` : 'Chưa tải dữ liệu'}{failedSources ? ` · ${failedSources} nguồn lỗi` : ''}</span>
        </div>

        <PanelState error={sourceErrors.product} loading={loading && !productUsage}>
          <section className="admin-analytics-insights" aria-label="Insight ưu tiên">
            <InsightCard label="Độ phủ cao nhất" value={topFeature?.feature ?? 'Chưa có dữ liệu'} detail={topFeature ? `${topFeature.unique_users} người dùng · ${topFeature.opens} lượt mở` : 'Cần traffic từ user đăng nhập'} tone="accent" />
            <InsightCard label="Luồng cần chú ý" value={weakestOutcome?.feature ?? 'Chưa có dữ liệu'} detail={weakestOutcome ? `${formatPercent(weakestOutcome.success_rate)} thành công · ${weakestOutcome.failed} lỗi` : 'Chưa có outcome kết thúc'} tone={weakestOutcome && (weakestOutcome.success_rate ?? 100) < 90 ? 'danger' : 'neutral'} />
            <InsightCard label="Lỗi nổi bật" value={topError?.error_code ?? 'Không ghi nhận'} detail={topError ? `${topError.count} lần trong kỳ` : 'Không có error event'} tone={topError ? 'danger' : 'neutral'} />
            <InsightCard label="Provider cần chú ý" value={unstableProvider?.key ?? slowProvider?.key ?? 'Chưa có dữ liệu'} detail={unstableProvider ? `${formatPercent(unstableProvider.fail_rate)} lỗi · ${unstableProvider.avg_ms ?? '—'}ms trung bình` : slowProvider ? `${slowProvider.avg_ms}ms trung bình` : 'Chưa đủ mẫu render'} tone={unstableProvider && (unstableProvider.fail_rate ?? 0) > 5 ? 'warning' : 'neutral'} />
          </section>
        </PanelState>

        <PanelState error={sourceErrors.product} loading={loading && !productUsage}>
          <section className="admin-panel admin-panel-full">
            <PanelHeading title="Xu hướng hoạt động" description="DAU, outcome hoàn tất và lỗi theo ngày." />
            <TrendChart productUsage={productUsage} diagnostics={diagnostics} />
          </section>
        </PanelState>

        <section className="admin-analytics-comparison" aria-label="So sánh với kỳ trước">
          {(['active_users', 'feature_opens', 'completed_outcomes', 'errors'] as const).map((key) => {
            const metric = productUsage?.period_comparison[key];
            return (
              <article key={key}>
                <span>{comparisonLabel(key)}</span>
                <strong>{metric?.current ?? 0}</strong>
                <small className={changeTone(key, metric?.change_pct)}>{changeLabel(metric?.change_pct)} so với kỳ trước ({metric?.previous ?? 0})</small>
              </article>
            );
          })}
        </section>

        <div className="admin-analytics-grid">
          <PanelState error={sourceErrors.product} loading={loading && !productUsage}>
            <section className="admin-panel">
              <PanelHeading title="Độ phủ tính năng" description="Xếp theo unique users; opens chỉ thể hiện tần suất quay lại." />
              <FeatureBars items={productUsage?.feature_usage ?? []} />
            </section>
          </PanelState>

          <PanelState error={sourceErrors.product} loading={loading && !productUsage}>
            <section className="admin-panel">
              <PanelHeading title="Độ tin cậy luồng" description="Outcome hoàn tất và thất bại theo chức năng." />
              <OutcomeBars items={productUsage?.outcomes ?? []} />
            </section>
          </PanelState>

          <PanelState error={sourceErrors.renders} loading={loading && !renders}>
            <section className="admin-panel">
              <PanelHeading title="Chất lượng render" description="Volume, fail rate và latency theo provider." />
              <QualityTable items={renders?.by_provider ?? []} empty="Chưa có render theo provider." />
              <h4 className="admin-analytics-subtitle">Theo renderer</h4>
              <QualityTable items={renders?.by_renderer ?? []} empty="Chưa có dữ liệu renderer." />
            </section>
          </PanelState>

          <PanelState error={sourceErrors.ai} loading={loading && !aiUsage}>
            <section className="admin-panel">
              <PanelHeading title="Hiệu suất AI" description="Token là mức sử dụng; chưa quy đổi thành chi phí." />
              <div className="admin-metric-grid admin-metric-grid-4 admin-analytics-mini-metrics">
                <MetricCard label="Calls" value={aiUsage?.calls ?? 0} variant="primary" icon="models" />
                <MetricCard label="Success" value={aiUsage?.success_rate ?? 0} suffix="%" variant="success" icon="active" />
                <MetricCard label="Tokens" value={aiUsage?.tokens ?? 0} variant="info" icon="chart" />
                <MetricCard label="Latency" value={aiUsage?.avg_ms ?? 0} suffix="ms" variant="info" icon="chart" />
              </div>
              <AiTable title="Theo provider" items={(aiUsage?.by_provider ?? []).map((item) => ({ ...item, key: item.provider }))} />
              <AiTable title="Theo tác vụ" items={(aiUsage?.by_task ?? []).map((item) => ({ ...item, key: item.task }))} />
            </section>
          </PanelState>

          <PanelState error={sourceErrors.errors} loading={loading && !diagnostics}>
            <section className="admin-panel admin-panel-full">
              <PanelHeading title="Chẩn đoán lỗi" description={`${diagnostics?.affected_users ?? 0} người dùng đăng nhập bị ảnh hưởng; route và source giữ riêng khỏi feature.`} />
              <div className="admin-analytics-diagnostics">
                <CountList title="Theo route" items={diagnostics?.by_route ?? []} />
                <CountList title="Theo mã lỗi" items={(diagnostics?.top_codes ?? []).map((item) => ({ key: item.error_code, count: item.count }))} />
                <CountList title="Theo source" items={diagnostics?.by_source ?? []} />
              </div>
              <h4 className="admin-analytics-subtitle">Fingerprint nổi bật</h4>
              <div className="admin-table">
                {(diagnostics?.top_fingerprints ?? []).slice(0, 8).map((item) => (
                  <article className="admin-row" key={`${item.fingerprint}-${item.error_code}`}>
                    <div><strong>{item.error_code}</strong><span>{item.count} lần · {item.fingerprint.slice(0, 12)}</span><small>{item.sample_message}</small></div>
                  </article>
                ))}
                {(diagnostics?.top_fingerprints ?? []).length === 0 && <EmptyState text="Chưa có nhóm lỗi." />}
              </div>
              <h4 className="admin-analytics-subtitle">Lỗi gần đây</h4>
              <div className="admin-table">
                {(diagnostics?.recent ?? []).slice(0, 15).map((item) => (
                  <article className="admin-row" key={item.id}>
                    <div><strong>{item.error_code || 'UNKNOWN'}</strong><span>{item.message}</span><small>{item.source} · {item.route || 'không có route'} · {formatHistoryDate(item.created_at)}</small></div>
                  </article>
                ))}
                {(diagnostics?.recent ?? []).length === 0 && <EmptyState text="Chưa có error event." />}
              </div>
            </section>
          </PanelState>

          <PanelState error={sourceErrors.funnel} loading={loading && !funnel}>
            <section className="admin-panel">
              <PanelHeading title="Kích hoạt người dùng" description={`Funnel tài khoản trong ${days} ngày.`} />
              <div className="admin-metric-grid admin-metric-grid-4 admin-analytics-mini-metrics">
                <MetricCard label="Đăng ký" value={funnel?.registered ?? 0} variant="primary" icon="users" />
                <MetricCard label="Xác minh" value={funnel?.verified ?? 0} variant="success" icon="active" />
                <MetricCard label="Render OK" value={funnel?.users_with_completed_render ?? 0} variant="info" icon="renders" />
                <MetricCard label="Có OCR" value={funnel?.users_with_ocr ?? 0} variant="info" icon="chart" />
              </div>
            </section>
          </PanelState>

          <PanelState error={sourceErrors.activity} loading={loading && !activity}>
            <section className="admin-panel">
              <PanelHeading title="Hoạt động gần đây" description="Dữ liệu từ user đã đăng nhập." />
              <div className="admin-table">
                {(activity?.recent ?? []).slice(0, 12).map((item) => (
                  <article className="admin-row" key={item.id}>
                    <div><strong>{item.event_type}</strong><span>{item.target_id || item.target_type || 'không có target'}</span><small>user {item.user_id.slice(0, 8)} · {formatHistoryDate(item.created_at)}</small></div>
                  </article>
                ))}
                {(activity?.recent ?? []).length === 0 && <EmptyState text="Chưa có activity event." />}
              </div>
            </section>
          </PanelState>
        </div>

        {sourceErrors.overview ? <p className="admin-analytics-source-error">Overview: {sourceErrors.overview}</p> : overview && (
          <p className="admin-analytics-footnote">Render kỳ này: {overview.renders} · fail rate {overview.render_fail_rate}% · p95 {overview.duration_p95_ms ?? '—'}ms · errors 24h {overview.errors_24h}</p>
        )}
      </div>
    </>
  );
}

function PanelState({ error, loading, children }: { error?: string; loading: boolean; children: ReactNode }) {
  if (error) return <section className="admin-panel admin-analytics-panel-state is-error"><strong>Không tải được panel</strong><p>{error}</p></section>;
  if (loading) return <section className="admin-panel admin-analytics-panel-state" aria-busy="true">Đang tải dữ liệu…</section>;
  return <>{children}</>;
}

function PanelHeading({ title, description }: { title: string; description: string }) {
  return <div className="admin-panel-title-row"><div><h3>{title}</h3><p>{description}</p></div></div>;
}

function InsightCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: 'accent' | 'danger' | 'warning' | 'neutral' }) {
  return <article className={`admin-analytics-insight is-${tone}`}><span>{label}</span><strong>{value}</strong><p>{detail}</p></article>;
}

function TrendChart({ productUsage, diagnostics }: { productUsage: AdminAnalyticsProductUsage | null; diagnostics: AdminAnalyticsErrors | null }) {
  const activityByDay = new Map((productUsage?.daily_active_users ?? []).map((item) => [item.day, item]));
  const errorsByDay = new Map((diagnostics?.daily ?? []).map((item) => [item.day, item.count]));
  const days = [...new Set([...activityByDay.keys(), ...errorsByDay.keys()])].sort();
  if (days.length === 0) return <EmptyState text="Chưa có dữ liệu xu hướng." />;

  const rows = days.map((day) => ({
    day,
    users: activityByDay.get(day)?.unique_users ?? 0,
    completed: activityByDay.get(day)?.completed ?? 0,
    errors: errorsByDay.get(day) ?? 0,
  }));
  const width = 720;
  const height = 220;
  const padding = 28;
  const max = Math.max(1, ...rows.flatMap((item) => [item.users, item.completed, item.errors]));
  const points = (key: 'users' | 'completed' | 'errors') => rows.map((item, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(1, rows.length - 1);
    const y = height - padding - (item[key] / max) * (height - padding * 2);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="admin-analytics-trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Biểu đồ DAU, outcome hoàn tất và lỗi theo ngày">
        {[0, 0.5, 1].map((ratio) => <line key={ratio} x1={padding} x2={width - padding} y1={padding + ratio * (height - padding * 2)} y2={padding + ratio * (height - padding * 2)} className="grid-line" />)}
        <polyline points={points('users')} className="trend-users" />
        <polyline points={points('completed')} className="trend-completed" />
        <polyline points={points('errors')} className="trend-errors" />
        {rows.map((item, index) => {
          const x = padding + (index * (width - padding * 2)) / Math.max(1, rows.length - 1);
          return <g key={item.day}><title>{item.day}: {item.users} DAU, {item.completed} hoàn tất, {item.errors} lỗi</title><circle cx={x} cy={height - padding - (item.users / max) * (height - padding * 2)} r="3" className="trend-users-dot" /></g>;
        })}
      </svg>
      <div className="admin-analytics-legend"><span className="is-users">DAU</span><span className="is-completed">Hoàn tất</span><span className="is-errors">Lỗi</span><small>{rows[0].day} – {rows[rows.length - 1].day}</small></div>
    </div>
  );
}

function FeatureBars({ items }: { items: AdminAnalyticsProductUsage['feature_usage'] }) {
  const max = Math.max(1, ...items.map((item) => item.unique_users));
  if (items.length === 0) return <EmptyState text="Chưa có feature.open từ user đăng nhập." />;
  return <div className="admin-horizontal-bars" role="img" aria-label="Độ phủ tính năng theo unique users">{items.slice(0, 10).map((item) => <div key={item.feature} className="admin-horizontal-bar"><div><strong>{item.feature}</strong><span>{item.unique_users} users · {item.sessions} sessions · {item.opens} opens</span></div><i><b style={{ width: `${(item.unique_users / max) * 100}%` }} /></i><small>{item.share_pct}% opens</small></div>)}</div>;
}

function OutcomeBars({ items }: { items: AdminAnalyticsProductUsage['outcomes'] }) {
  if (!items.some((item) => item.completed + item.failed > 0)) return <EmptyState text="Chưa có outcome kết thúc." />;
  return <div className="admin-outcome-list">{items.map((item) => { const total = item.completed + item.failed; return <article key={item.feature}><div><strong>{item.feature}</strong><span>{formatPercent(item.success_rate)}</span></div><div className="admin-outcome-bar" aria-label={`${item.feature}: ${item.completed} hoàn tất, ${item.failed} lỗi`}><i className="is-success" style={{ width: `${total ? (item.completed / total) * 100 : 0}%` }} /><i className="is-failed" style={{ width: `${total ? (item.failed / total) * 100 : 0}%` }} /></div><small>{item.completed} hoàn tất · {item.failed} lỗi · {item.unique_users} users</small></article>; })}</div>;
}

function QualityTable({ items, empty }: { items: AdminAnalyticsRenders['by_provider']; empty: string }) {
  if (items.length === 0) return <EmptyState text={empty} />;
  return <div className="admin-analytics-table"><div className="is-header"><span>Nhóm</span><span>Jobs</span><span>Fail</span><span>Latency</span></div>{items.slice(0, 8).map((item) => <div key={item.key}><strong>{item.key}</strong><span>{item.count}</span><span className={(item.fail_rate ?? 0) > 5 ? 'is-danger' : ''}>{formatPercent(item.fail_rate)}</span><span>{item.avg_ms ?? '—'}ms</span></div>)}</div>;
}

function AiTable({ title, items }: { title: string; items: Array<{ key: string; calls: number; success_rate?: number | null; tokens: number; avg_ms?: number | null }> }) {
  return <div className="admin-ai-breakdown"><h4>{title}</h4>{items.length ? <div className="admin-analytics-table"><div className="is-header"><span>Nhóm</span><span>Calls</span><span>Success</span><span>Tokens / latency</span></div>{items.slice(0, 8).map((item) => <div key={item.key}><strong>{item.key}</strong><span>{item.calls}</span><span className={(item.success_rate ?? 100) < 95 ? 'is-danger' : ''}>{formatPercent(item.success_rate)}</span><span>{item.tokens} / {item.avg_ms ?? '—'}ms</span></div>)}</div> : <EmptyState text="Chưa có AI metrics." />}</div>;
}

function CountList({ title, items }: { title: string; items: Array<{ key: string; count: number }> }) {
  return <div><h4>{title}</h4>{items.slice(0, 8).map((item) => <p key={item.key}><span>{item.key}</span><strong>{item.count}</strong></p>)}{items.length === 0 && <small>Chưa có dữ liệu.</small>}</div>;
}

function EmptyState({ text }: { text: string }) {
  return <p className="admin-analytics-empty">{text}</p>;
}

function formatPercent(value?: number | null) {
  return value == null ? 'Chưa có mẫu' : `${value}%`;
}

function comparisonLabel(key: keyof AdminAnalyticsProductUsage['period_comparison']) {
  return { active_users: 'Active users', feature_opens: 'Feature opens', completed_outcomes: 'Outcome hoàn tất', errors: 'Errors' }[key];
}

function changeLabel(value?: number | null) {
  if (value == null) return 'Mới';
  if (value === 0) return 'Không đổi';
  return `${value > 0 ? '+' : ''}${value}%`;
}

function changeTone(key: keyof AdminAnalyticsProductUsage['period_comparison'], value?: number | null) {
  if (value == null || value === 0) return '';
  const positive = key === 'errors' ? value < 0 : value > 0;
  return positive ? 'is-positive' : 'is-negative';
}