import React, { useState, useEffect } from 'react';
import type { 
  AdminRenderHistoryDetail, 
  AdminRenderHistoryItem, 
  AdminSessionResponse, 
  AdminSummaryResponse,
  AuditLogResponse, 
  SystemSettingResponse, 
  UserResponse,
  AdminUserFilters,
  AdminRenderJobFilters,
  AdminAuditLogFilters,
  AdminDatabaseDiagnostics,
  AdminFeedbackFilters,
  AdminFeedbackResponse,
  FeedbackStatus
} from '../../api/client';
import { 
  getAdminSummary, 
  getAdminUsers, 
  updateAdminUser, 
  getAdminUserSessions, 
  revokeAdminUserSession, 
  revokeAllAdminUserSessions, 
  getAdminRenderJobs, 
  getAdminRenderJobDetail, 
  deleteAdminRenderJob, 
  getAdminSystemSettings, 
  updateAdminSystemSetting, 
  getAdminAuditLogs,
  getAdminFeedback,
  updateAdminFeedback,
  getSettingsDefaults,
  getAdminDatabaseDiagnostics
} from '../../api/client';
import { 
  formatHistoryDate, 
  MetricCard, 
  AdminNavButton,
  AdminDetails,
  AdminIcon,
  hasObjectKeys 
} from './AdminComponents';
import { 
  AdminAiSettingsForm, 
  AdminPlanSettingsForm, 
  AdminFeatureFlagsForm, 
  AdminAiProfilesForm,
  AdminAiPromptsForm,
} from './AdminForms';
import { buildPlanOptions, distinctOptions, providerLabels, rendererOptions, renderSourceOptions } from '../../utils/settingsOptions';
import type { SettingsDefaults } from '../../types/settings';
import adminLogoUrl from '../../../logo.svg';

type AdminToastKind = 'error' | 'warning' | 'info';

type AdminToast = (title: string, message: string, kind?: AdminToastKind) => void;

interface AdminConsoleProps {
  user: UserResponse;
  onBackToApp: () => void;
  onOpenRenderJobDetail: (detail: AdminRenderHistoryDetail) => void;
  onToast: AdminToast;
}

function AdminToolbarRefreshButton({ loading, onClick }: { loading: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`secondary-button admin-button-with-icon admin-topbar-refresh${loading ? ' is-loading' : ''}`}
      onClick={onClick}
      disabled={loading}
      aria-busy={loading}
      aria-label={loading ? 'Đang tải dữ liệu' : 'Làm mới dữ liệu'}
    >
      <AdminIcon name="refresh" />
    </button>
  );
}

export function AdminConsole({ user, onBackToApp, onOpenRenderJobDetail, onToast }: AdminConsoleProps) {
  const [activeSection, setActiveSection] = useState<'overview' | 'users' | 'renders' | 'models' | 'settings' | 'feedback' | 'audit'>('overview');
  const [summary, setSummary] = useState<AdminSummaryResponse | null>(null);
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [renderJobs, setRenderJobs] = useState<AdminRenderHistoryItem[]>([]);
  const [settings, setSettings] = useState<SystemSettingResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [feedbackItems, setFeedbackItems] = useState<AdminFeedbackResponse[]>([]);
  const [loading, setLoading] = useState(false);

  // User list state
  const [userQuery, setUserQuery] = useState('');
  const [userFilters, setUserFilters] = useState<AdminUserFilters>({});
  const [searchingUsers, setSearchingUsers] = useState(false);

  // Render job list state
  const [localRenderJobFilters, setLocalRenderJobFilters] = useState<AdminRenderJobFilters>({});
  const [filteringRenderJobs, setFilteringRenderJobs] = useState(false);
  const [selectedJobDetail, setSelectedJobDetail] = useState<AdminRenderHistoryDetail | null>(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [jobDetailError, setJobDetailError] = useState<string | null>(null);

  // AI settings state
  const [aiSettings, setAiSettings] = useState<Record<string, unknown>>({});
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsDefaults | null>(null);
  const [databaseDiagnostics, setDatabaseDiagnostics] = useState<AdminDatabaseDiagnostics | null>(null);
  const [savingAiSettings, setSavingAiSettings] = useState(false);

  // Feedback filters
  const [localFeedbackFilters, setLocalFeedbackFilters] = useState<AdminFeedbackFilters>({});
  const [filteringFeedback, setFilteringFeedback] = useState(false);
  const [updatingFeedbackId, setUpdatingFeedbackId] = useState<string | null>(null);

  // Audit log filters
  const [localAuditLogFilters, setLocalAuditLogFilters] = useState<AdminAuditLogFilters>({});
  const [filteringAuditLogs, setFilteringAuditLogs] = useState(false);

  const onRefresh = async (showSuccess = false) => {
    setLoading(true);
    try {
      const [s, u, r, st, a, f, defaults, diagnostics] = await Promise.all([
        getAdminSummary(),
        getAdminUsers({}),
        getAdminRenderJobs({}),
        getAdminSystemSettings(),
        getAdminAuditLogs({}),
        getAdminFeedback({}),
        getSettingsDefaults(),
        getAdminDatabaseDiagnostics(),
      ]);
      setSummary(s);
      setUsers(u);
      setRenderJobs(r);
      setSettings(st);
      setAuditLogs(a);
      setFeedbackItems(f);
      setSettingsDefaults(defaults);
      setDatabaseDiagnostics(diagnostics);

      const ai = st.find((item) => item.key === 'ai_settings');
      if (ai) setAiSettings(ai.value);
      if (showSuccess) onToast('Admin dashboard', 'Đã làm mới dữ liệu admin.', 'info');
    } catch (error) {
      onToast('Admin dashboard', getErrorMessage(error, 'Không thể tải dữ liệu admin.'), 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void onRefresh();
  }, []);

  const onSearchUsers = async (q: string, filters: AdminUserFilters) => {
    setSearchingUsers(true);
    try {
      setUsers(await getAdminUsers({ ...filters, q }));
    } catch (error) {
      onToast('Người dùng', getErrorMessage(error, 'Không thể tìm người dùng.'), 'error');
    } finally {
      setSearchingUsers(false);
    }
  };

  const submitUserSearch = (event: React.FormEvent) => {
    event.preventDefault();
    void onSearchUsers(userQuery, userFilters);
  };

  const onUpdateUser = async (u: UserResponse, patch: any) => {
    try {
      await updateAdminUser(u.id, patch);
      await onRefresh();
      onToast('Người dùng', 'Đã cập nhật người dùng.', 'info');
    } catch (error) {
      onToast('Người dùng', getErrorMessage(error, 'Không thể cập nhật người dùng.'), 'error');
    }
  };

  const onToggleUserStatus = async (u: UserResponse) => {
    const nextStatus = u.status === 'active' ? 'disabled' : 'active';
    try {
      await updateAdminUser(u.id, { status: nextStatus });
      await onRefresh();
      onToast('Người dùng', nextStatus === 'active' ? 'Đã kích hoạt người dùng.' : 'Đã vô hiệu hoá người dùng.', 'info');
    } catch (error) {
      onToast('Người dùng', getErrorMessage(error, 'Không thể đổi trạng thái người dùng.'), 'error');
    }
  };

  const onSearchRenderJobs = async (filters: AdminRenderJobFilters) => {
    setFilteringRenderJobs(true);
    try {
      setRenderJobs(await getAdminRenderJobs(filters));
    } catch (error) {
      onToast('Render jobs', getErrorMessage(error, 'Không thể lọc render jobs.'), 'error');
    } finally {
      setFilteringRenderJobs(false);
    }
  };

  const submitRenderJobFilters = (event: React.FormEvent) => {
    event.preventDefault();
    void onSearchRenderJobs(localRenderJobFilters);
  };

  const inspectRenderJob = async (id: string) => {
    setJobDetailLoading(true);
    setJobDetailError(null);
    try {
      setSelectedJobDetail(await getAdminRenderJobDetail(id));
    } catch (error) {
      const message = getErrorMessage(error, 'Không thể tải chi tiết render job.');
      setJobDetailError(message);
      onToast('Render job', message, 'error');
    } finally {
      setJobDetailLoading(false);
    }
  };

  const onDeleteRenderJob = async (id: string) => {
    if (!window.confirm('Xoá render job này?')) return;
    try {
      await deleteAdminRenderJob(id);
      await onSearchRenderJobs(localRenderJobFilters);
      onToast('Render job', 'Đã xoá render job.', 'info');
    } catch (error) {
      onToast('Render job', getErrorMessage(error, 'Không thể xoá render job.'), 'error');
    }
  };

  const saveAiSettingsPatch = async (patch: Record<string, unknown>) => {
    setSavingAiSettings(true);
    try {
      const next = { ...aiSettings, ...patch };
      const updated = await updateAdminSystemSetting('ai_settings', next);
      setAiSettings(updated.value);
      setSettings((prev) =>
        prev.some((item) => item.key === 'ai_settings')
          ? prev.map((item) => (item.key === 'ai_settings' ? updated : item))
          : [...prev, updated]
      );
    } catch {
      throw new Error('Không thể lưu cấu hình AI.');
    } finally {
      setSavingAiSettings(false);
    }
  };

  const saveAdminSystemSetting = async (key: string, value: any) => {
    try {
      await updateAdminSystemSetting(key, value);
      await onRefresh();
    } catch (error) {
      throw error;
    }
  };

  const onSearchFeedback = async (filters: AdminFeedbackFilters) => {
    setFilteringFeedback(true);
    try {
      setFeedbackItems(await getAdminFeedback(filters));
    } catch (error) {
      onToast('Góp ý', getErrorMessage(error, 'Không thể lọc góp ý.'), 'error');
    } finally {
      setFilteringFeedback(false);
    }
  };

  const submitFeedbackFilters = (event: React.FormEvent) => {
    event.preventDefault();
    void onSearchFeedback(localFeedbackFilters);
  };

  const onUpdateFeedback = async (item: AdminFeedbackResponse, status: FeedbackStatus, adminNote?: string) => {
    setUpdatingFeedbackId(item.id);
    try {
      await updateAdminFeedback(item.id, status, adminNote);
      await onSearchFeedback(localFeedbackFilters);
      setAuditLogs(await getAdminAuditLogs(localAuditLogFilters));
      onToast('Góp ý', status === 'received' ? 'Đã đánh dấu góp ý là đã tiếp nhận.' : 'Đã chấp nhận góp ý.', 'info');
    } catch (error) {
      onToast('Góp ý', getErrorMessage(error, 'Không thể cập nhật góp ý.'), 'error');
    } finally {
      setUpdatingFeedbackId(null);
    }
  };

  const onSearchAuditLogs = async (filters: AdminAuditLogFilters) => {
    setFilteringAuditLogs(true);
    try {
      setAuditLogs(await getAdminAuditLogs(filters));
    } catch (error) {
      onToast('Nhật ký kiểm toán', getErrorMessage(error, 'Không thể lọc nhật ký kiểm toán.'), 'error');
    } finally {
      setFilteringAuditLogs(false);
    }
  };

  const submitAuditLogFilters = (event: React.FormEvent) => {
    event.preventDefault();
    void onSearchAuditLogs(localAuditLogFilters);
  };

  const providerStats = summarizeRenderJobs(renderJobs);
  const planSettings = settings.find((item) => item.key === 'plan_settings')?.value as Record<string, unknown> | undefined;
  const planOptions = buildPlanOptions(planSettings);
  const renderProviderOptions = distinctOptions(renderJobs.map((job) => job.provider), [
    { id: 'auto', label: providerLabels.auto },
    { id: 'openrouter', label: providerLabels.openrouter },
    { id: 'nvidia', label: providerLabels.nvidia },
    { id: 'ollama', label: providerLabels.ollama },
    { id: 'openai_compat', label: providerLabels.openai_compat },
    { id: 'router9', label: providerLabels.router9 },
    { id: 'mock', label: providerLabels.mock },
  ]);
  const aiModelIds = collectAdminModelIds(aiSettings);
  const renderModelOptions = distinctOptions(renderJobs.map((job) => job.model), aiModelIds.map((id) => ({ id, label: id })));
  const renderRendererOptions = distinctOptions(renderJobs.map((job) => job.renderer), rendererOptions);
  const renderSourceFilterOptions = distinctOptions(renderJobs.map((job) => job.source_type), renderSourceOptions);
  const auditActionOptions = distinctOptions(auditLogs.map((log) => log.action));
  const auditTargetOptions = distinctOptions(auditLogs.map((log) => log.target_type));
  const dailyActivity = buildDailyActivity(summary?.daily_stats ?? []);
  const dailyActivityTotal = dailyActivity.reduce((total, item) => total + item.count, 0);
  const dailyActivityMax = Math.max(...dailyActivity.map((item) => item.count), 1);

  if (user.role !== 'admin') {
    return (
      <section className="admin-dashboard">
        <div className="admin-error">
          <h3>Truy cập bị từ chối</h3>
          <p>Trang này chỉ dành cho tài khoản admin đang hoạt động.</p>
          <button type="button" onClick={onBackToApp}>Quay lại trang chính</button>
        </div>
      </section>
    );
  }

  return (
    <section className="admin-dashboard">
      <aside className="admin-sidebar">
        <div className="admin-brand"><span><img src={adminLogoUrl} alt="" className="admin-brand-logo" width={32} height={32} decoding="async" /></span><div><strong>Admin Dashboard</strong><small>Operations Center</small></div></div>
        <nav className="admin-sidebar-nav">
          <AdminNavButton active={activeSection === 'overview'} onClick={() => setActiveSection('overview')} icon="overview" label="Tổng quan" />
          <AdminNavButton active={activeSection === 'users'} onClick={() => setActiveSection('users')} icon="users" label="Người dùng" />
          <AdminNavButton active={activeSection === 'renders'} onClick={() => setActiveSection('renders')} icon="renders" label="Lượt dựng hình" />
          <AdminNavButton active={activeSection === 'models'} onClick={() => setActiveSection('models')} icon="models" label="Model & AI" />
          <AdminNavButton active={activeSection === 'settings'} onClick={() => setActiveSection('settings')} icon="settings" label="Database" />
          <AdminNavButton active={activeSection === 'feedback'} onClick={() => setActiveSection('feedback')} icon="audit" label="Góp ý" />
          <AdminNavButton active={activeSection === 'audit'} onClick={() => setActiveSection('audit')} icon="audit" label="Nhật ký kiểm toán" />
        </nav>
        <div className="admin-sidebar-footer"><small>{user.email}</small><button type="button" className="secondary-button admin-button-with-icon" onClick={onBackToApp}><AdminIcon name="back" />Trang người dùng</button></div>
      </aside>

      <main className="admin-main">
        {activeSection === 'overview' && (
          <>
            <header className="admin-topbar">
              <div><span className="home-eyebrow">Admin Dashboard</span><h2>Quản lý dự án AI Math Renderer</h2><p>Khu vực vận hành, phân tích, quản lý người dùng, model, cài đặt và nhật ký.</p></div>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <div className="admin-section-stack">
              <div className="admin-metric-groups">
                <section className="admin-metric-group metric-group-users">
                  <div className="admin-metric-group-header">
                    <span>Người dùng</span>
                    <small>Tài khoản và phân quyền</small>
                  </div>
                  <div className="admin-metric-grid admin-metric-grid-4">
                    <MetricCard label="Người dùng" value={summary?.users ?? 0} variant="primary" icon="users" />
                    <MetricCard label="Đang hoạt động" value={summary?.active_users ?? 0} variant="success" icon="active" />
                    <MetricCard label="Admin" value={summary?.admins ?? 0} variant="info" icon="admin" />
                    <MetricCard label="User mới hôm nay" value={summary?.users_today ?? 0} variant="info" icon="users" />
                  </div>
                </section>
                <section className="admin-metric-group metric-group-renders">
                  <div className="admin-metric-group-header">
                    <span>Render</span>
                    <small>Lưu lượng dựng hình</small>
                  </div>
                  <div className="admin-metric-grid admin-metric-grid-2">
                    <MetricCard label="Lượt dựng hình" value={summary?.render_jobs ?? 0} variant="primary" icon="renders" />
                    <MetricCard label="Render hôm nay" value={summary?.render_jobs_today ?? 0} variant="success" icon="chart" />
                  </div>
                </section>
                <section className="admin-metric-group metric-group-ai-health">
                  <div className="admin-metric-group-header">
                    <span>AI Health</span>
                    <small>Cảnh báo và chất lượng</small>
                  </div>
                  <div className="admin-metric-grid admin-metric-grid-2">
                    <MetricCard label="Job cảnh báo AI" value={summary?.ai_warning_jobs ?? 0} variant="warning" icon="warning" />
                    <MetricCard label="Tỉ lệ cảnh báo AI" value={summary?.ai_warning_rate ?? 0} suffix="%" variant="warning" icon="warning" />
                  </div>
                </section>
              </div>

            <section className="admin-panel admin-panel-full">
              <div className="admin-panel-title-row">
                <div>
                  <h3>Biểu đồ hoạt động</h3>
                  <p>14 ngày gần nhất, bao gồm cả ngày chưa có lượt dựng hình.</p>
                </div>
              </div>
              <div className="admin-chart-container">
                {dailyActivityTotal > 0 ? (
                  <div className="admin-bar-chart">
                    {dailyActivity.map((item) => {
                      const height = item.count > 0 ? Math.max((item.count / dailyActivityMax) * 100, 8) : 3;
                      return (
                        <div key={item.day} className="admin-chart-bar-group" title={`${item.day}: ${item.count} lượt dựng`}>
                          <div className={`admin-chart-bar${item.count === 0 ? ' is-empty' : ''}`} style={{ height: `${height}%` }}>
                            {item.count > 0 && <span className="admin-chart-value">{item.count}</span>}
                          </div>
                          <span className="admin-chart-label">{item.label}</span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="admin-chart-empty-state">
                    <AdminIcon name="chart" />
                    <strong>Chưa có hoạt động trong 14 ngày gần nhất</strong>
                    <p>Khi có lượt dựng hình mới, biểu đồ sẽ hiển thị theo từng ngày.</p>
                  </div>
                )}
              </div>
            </section>

            <div className="admin-grid">
              <section className="admin-panel"><h3>Phân tích provider/model</h3><div className="admin-table">{providerStats.map((item) => <article className="admin-row" key={item.key}><div><strong>{item.key}</strong><span>{item.count} render jobs</span></div></article>)}{providerStats.length === 0 && <p className="field-hint">Chưa có dữ liệu render để phân tích.</p>}</div></section>
              <section className="admin-panel"><h3>Tình trạng cấu hình</h3><div className="admin-table"><article className="admin-row"><div><strong>Database</strong><span>{databaseDiagnostics ? `${databaseDiagnostics.backend}${databaseDiagnostics.sqlite_path ? ` · ${databaseDiagnostics.sqlite_path}` : ''}` : 'Đang tải...'}</span></div></article><article className="admin-row"><div><strong>ai_settings</strong><span>{databaseDiagnostics?.ai_settings.exists ? `Đã lưu · allowlist ${databaseDiagnostics.ai_settings.router9_allowed_model_count} model · scanned ${databaseDiagnostics.ai_settings.router9_scanned_model_count}` : 'Chưa cấu hình trong database'}</span></div></article><article className="admin-row"><div><strong>Migrations</strong><span>{databaseDiagnostics ? `${databaseDiagnostics.migrations.length} migration đã áp dụng` : 'Đang tải...'}</span></div></article><article className="admin-row"><div><strong>Audit</strong><span>{auditLogs.length} sự kiện gần nhất</span></div></article></div></section>
            </div>
            </div>
          </>
        )}

        {activeSection === 'users' && (
          <>
            <header className="admin-page-header">
              <h2>Quản lý người dùng</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            <form className="admin-toolbar" onSubmit={submitUserSearch}>
              <input value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder="Tìm email, tên hiển thị hoặc ID" />
              <select value={userFilters.role ?? ''} onChange={(event) => setUserFilters((current) => ({ ...current, role: event.target.value }))}><option value="">Vai trò</option><option value="user">user</option><option value="admin">admin</option></select>
              <select value={userFilters.status ?? ''} onChange={(event) => setUserFilters((current) => ({ ...current, status: event.target.value }))}><option value="">Trạng thái</option><option value="active">active</option><option value="disabled">disabled</option></select>
              <select value={userFilters.plan ?? ''} onChange={(event) => setUserFilters((current) => ({ ...current, plan: event.target.value }))}><option value="">Gói</option>{planOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select>
              <button type="submit" className="secondary-button" disabled={searchingUsers}>{searchingUsers ? 'Đang tìm...' : 'Tìm user'}</button>
              <button type="button" className="secondary-button" onClick={() => { setUserQuery(''); setUserFilters({}); void onSearchUsers('', {}); }}>Xoá lọc</button>
            </form>
            <div className="admin-table">
              {users.map((item) => <AdminUserRow key={item.id} item={item} currentUserId={user.id} planOptions={planOptions} onUpdate={onUpdateUser} onToggleStatus={onToggleUserStatus} onToast={onToast} />)}
              {users.length === 0 && <p className="field-hint">Không tìm thấy người dùng phù hợp.</p>}
            </div>
          </section>
          </>
        )}

        {activeSection === 'renders' && (
          <>
            <header className="admin-page-header">
              <h2>Quản lý render jobs</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            <form className="admin-toolbar admin-filter-grid" onSubmit={submitRenderJobFilters}>
              <input value={localRenderJobFilters.q ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, q: event.target.value }))} placeholder="Tìm đề bài hoặc ID" />
              <select value={localRenderJobFilters.provider ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, provider: event.target.value }))}><option value="">Provider</option>{renderProviderOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select>
              <select value={localRenderJobFilters.model ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, model: event.target.value }))}><option value="">Model</option>{renderModelOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select>
              <select value={localRenderJobFilters.renderer ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, renderer: event.target.value }))}><option value="">Renderer</option>{renderRendererOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select>
              <select value={localRenderJobFilters.source_type ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, source_type: event.target.value }))}><option value="">Nguồn</option>{renderSourceFilterOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select>
              <input list="admin-user-id-options" value={localRenderJobFilters.user_id ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, user_id: event.target.value }))} placeholder="ID người dùng" />
              <button type="submit" className="secondary-button" disabled={filteringRenderJobs}>{filteringRenderJobs ? 'Đang lọc...' : 'Lọc jobs'}</button>
              <button type="button" className="secondary-button" onClick={() => { setLocalRenderJobFilters({}); void onSearchRenderJobs({}); }}>Xoá lọc</button>
            </form>
            <datalist id="admin-user-id-options">{users.map((item) => <option key={item.id} value={item.id}>{item.email}</option>)}</datalist>
            <div className="admin-table">
              {renderJobs.map((job) => (
                <article className="admin-row" key={job.id}>
                  <div><strong>{job.problem_text}</strong><span>{formatHistoryDate(job.created_at)} · {job.user_id || 'guest'} · {job.provider || 'auto'} · {job.model || 'default'} · {job.renderer || 'auto'}</span></div>
                  <div className="admin-row-actions"><button type="button" className="secondary-button" onClick={() => void inspectRenderJob(job.id)}>Chi tiết</button><button type="button" className="history-delete" onClick={() => onDeleteRenderJob(job.id)} aria-label="Xoá render job">×</button></div>
                </article>
              ))}
              {renderJobs.length === 0 && <p className="field-hint">Chưa có render job nào.</p>}
            </div>
            {jobDetailLoading && <p className="field-hint">Đang tải chi tiết render job...</p>}
            {jobDetailError && <p className="error-box">{jobDetailError}</p>}
            {selectedJobDetail && <AdminRenderJobDetailPanel detail={selectedJobDetail} onOpen={() => onOpenRenderJobDetail(selectedJobDetail)} onClose={() => setSelectedJobDetail(null)} />}
          </section>
          </>
        )}

        {activeSection === 'models' && (
          <>
            <header className="admin-page-header">
              <h2>Quản lý model & AI</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            <AdminAiSettingsForm value={aiSettings} defaults={settingsDefaults} saving={savingAiSettings} onSave={saveAiSettingsPatch} onToast={onToast} />
            <AdminAiProfilesForm value={settings.find((item) => item.key === 'ai_profiles')?.value ?? {}} aiSettings={aiSettings} onSave={(value) => saveAdminSystemSetting('ai_profiles', value)} onToast={onToast} />
            <AdminAiPromptsForm value={settings.find((item) => item.key === 'ai_prompts')?.value ?? {}} onSave={(value) => saveAdminSystemSetting('ai_prompts', value)} onToast={onToast} />
          </section>
          </>
        )}

        {activeSection === 'settings' && (
          <>
            <header className="admin-page-header">
              <h2>Database</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            {databaseDiagnostics && <AdminDatabaseDiagnosticsPanel diagnostics={databaseDiagnostics} />}
            {!databaseDiagnostics && <p className="field-hint">Đang tải chẩn đoán database...</p>}
            <AdminDetails title="system_settings raw" value={settings.map(({ key, updated_at, updated_by }) => ({ key, updated_at, updated_by }))} />
          </section>
          </>
        )}

        {activeSection === 'feedback' && (
          <>
            <header className="admin-page-header">
              <h2>Quản lý góp ý</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
              <form className="admin-toolbar admin-filter-grid" onSubmit={submitFeedbackFilters}>
                <input value={localFeedbackFilters.q ?? ''} onChange={(event) => setLocalFeedbackFilters((current) => ({ ...current, q: event.target.value }))} placeholder="Tìm nội dung, email hoặc ID" />
                <select value={localFeedbackFilters.status ?? ''} onChange={(event) => setLocalFeedbackFilters((current) => ({ ...current, status: event.target.value }))}>
                  <option value="">Trạng thái</option>
                  <option value="pending">pending</option>
                  <option value="received">received</option>
                  <option value="accepted">accepted</option>
                </select>
                <input list="admin-user-id-options" value={localFeedbackFilters.user_id ?? ''} onChange={(event) => setLocalFeedbackFilters((current) => ({ ...current, user_id: event.target.value }))} placeholder="ID người dùng" />
                <button type="submit" className="secondary-button" disabled={filteringFeedback}>{filteringFeedback ? 'Đang lọc...' : 'Lọc góp ý'}</button>
                <button type="button" className="secondary-button" onClick={() => { setLocalFeedbackFilters({}); void onSearchFeedback({}); }}>Xoá lọc</button>
              </form>
              <datalist id="admin-user-id-options">{users.map((item) => <option key={item.id} value={item.id}>{item.email}</option>)}</datalist>
              <div className="admin-table">
                {feedbackItems.map((item) => <AdminFeedbackRow key={item.id} item={item} updating={updatingFeedbackId === item.id} onUpdate={onUpdateFeedback} />)}
                {feedbackItems.length === 0 && <p className="field-hint">Chưa có góp ý phù hợp.</p>}
              </div>
            </section>
          </>
        )}

        {activeSection === 'audit' && (
          <>
            <header className="admin-page-header">
              <h2>Nhật ký kiểm toán</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void onRefresh(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            <form className="admin-toolbar admin-filter-grid" onSubmit={submitAuditLogFilters}>
              <input list="admin-audit-action-options" value={localAuditLogFilters.action ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action" />
              <input list="admin-user-id-options" value={localAuditLogFilters.actor_user_id ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, actor_user_id: event.target.value }))} placeholder="Actor user ID" />
              <input list="admin-audit-target-options" value={localAuditLogFilters.target_type ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, target_type: event.target.value }))} placeholder="Target type" />
              <button type="submit" className="secondary-button" disabled={filteringAuditLogs}>{filteringAuditLogs ? 'Đang lọc...' : 'Lọc audit'}</button>
              <button type="button" className="secondary-button" onClick={() => { setLocalAuditLogFilters({}); void onSearchAuditLogs({}); }}>Xoá lọc</button>
            </form>
            <datalist id="admin-audit-action-options">{auditActionOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</datalist>
            <datalist id="admin-audit-target-options">{auditTargetOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</datalist>
            <div className="admin-table">
              {auditLogs.map((log) => <AdminAuditLogRow key={log.id} log={log} />)}
              {auditLogs.length === 0 && <p className="field-hint">Chưa có audit log.</p>}
            </div>
          </section>
          </>
        )}
      </main>
    </section>
  );
}

// --- Sub-components moved here for simplicity in this turn ---

function AdminFeedbackRow({ item, updating, onUpdate }: { item: AdminFeedbackResponse; updating: boolean; onUpdate: (item: AdminFeedbackResponse, status: FeedbackStatus, adminNote?: string) => Promise<void> }) {
  const [note, setNote] = useState(item.admin_note ?? '');

  useEffect(() => {
    setNote(item.admin_note ?? '');
  }, [item.id, item.admin_note]);

  const statusText = item.status === 'pending' ? 'Đang chờ' : item.status === 'received' ? 'Đã tiếp nhận' : 'Đã chấp nhận';

  return (
    <article className="admin-row admin-row-block admin-feedback-row">
      <div>
        <strong>{item.subject}</strong>
        <span>{formatHistoryDate(item.created_at)} · {item.user_email || item.user_id} · {statusText}</span>
        <p className="admin-problem-text">{item.message}</p>
      </div>
      <label className="field-label admin-feedback-note">Ghi chú admin<textarea value={note} rows={3} onChange={(event) => setNote(event.target.value)} placeholder="Ghi chú nội bộ hoặc phản hồi ngắn" /></label>
      <div className="admin-row-actions">
        <button type="button" className="secondary-button" onClick={() => void onUpdate(item, 'received', note)} disabled={updating || item.status !== 'pending'}>{updating ? 'Đang lưu...' : 'Đánh dấu đã nhận'}</button>
        <button type="button" className="secondary-button" onClick={() => void onUpdate(item, 'accepted', note)} disabled={updating || item.status !== 'pending'}>Chấp nhận</button>
      </div>
    </article>
  );
}

function AdminUserRow({ item, currentUserId, planOptions, onUpdate, onToggleStatus, onToast }: { item: UserResponse; currentUserId: string; planOptions: Array<{ id: string; label: string }>; onUpdate: (user: UserResponse, patch: any) => Promise<void>; onToggleStatus: (user: UserResponse) => Promise<void>; onToast: AdminToast }) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(item.display_name ?? '');
  const [role, setRole] = useState<UserResponse['role']>(item.role);
  const [status, setStatus] = useState<UserResponse['status']>(item.status);
  const [plan, setPlan] = useState(item.plan);
  const [saving, setSaving] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessions, setSessions] = useState<AdminSessionResponse[]>([]);
  const isSelf = item.id === currentUserId;

  useEffect(() => {
    setDisplayName(item.display_name ?? '');
    setRole(item.role);
    setStatus(item.status);
    setPlan(item.plan);
  }, [item]);

  async function loadSessions() {
    setSessionsLoading(true);
    try {
      setSessions(await getAdminUserSessions(item.id));
      setSessionsOpen(true);
    } catch (error) {
      onToast('Phiên đăng nhập', getErrorMessage(error, 'Không thể tải phiên đăng nhập.'), 'error');
    } finally {
      setSessionsLoading(false);
    }
  }

  async function revokeSession(sessionId: string) {
    try {
      await revokeAdminUserSession(item.id, sessionId);
      await loadSessions();
      onToast('Phiên đăng nhập', 'Đã thu hồi phiên đăng nhập.', 'info');
    } catch (error) {
      onToast('Phiên đăng nhập', getErrorMessage(error, 'Không thể thu hồi phiên đăng nhập.'), 'error');
    }
  }

  async function revokeAllSessions() {
    try {
      await revokeAllAdminUserSessions(item.id);
      await loadSessions();
      onToast('Phiên đăng nhập', 'Đã thu hồi tất cả phiên đăng nhập.', 'info');
    } catch (error) {
      onToast('Phiên đăng nhập', getErrorMessage(error, 'Không thể thu hồi các phiên đăng nhập.'), 'error');
    }
  }

  async function save() {
    const patch: any = {};
    const nextDisplayName = displayName.trim() || null;
    const nextPlan = plan.trim() || 'free';
    if (nextDisplayName !== (item.display_name ?? null)) patch.display_name = nextDisplayName;
    if (!isSelf && role !== item.role) patch.role = role;
    if (!isSelf && status !== item.status) patch.status = status;
    if (nextPlan !== item.plan) patch.plan = nextPlan;
    if (Object.keys(patch).length === 0) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      await onUpdate(item, patch);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <article className="admin-row">
        <div style={{ flex: 1, minWidth: 0 }}>
          <strong>{item.display_name || item.email}</strong>
          <span>{item.email} · {item.role} · {item.status} · {item.plan}</span>
        </div>
        <div className="admin-row-actions">
          <button type="button" className="secondary-button" onClick={() => setEditing(!editing)}>{editing ? 'Huỷ' : 'Sửa'}</button>
          <button type="button" className="secondary-button" onClick={() => void onToggleStatus(item)} disabled={isSelf}>{item.status === 'active' ? 'Vô hiệu' : 'Kích hoạt'}</button>
          <button type="button" className="secondary-button" onClick={() => (sessionsOpen ? setSessionsOpen(false) : void loadSessions())} disabled={sessionsLoading}>{sessionsLoading ? '...' : 'Sessions'}</button>
        </div>
      </article>
      {editing && (
        <div className="admin-edit-panel">
          <div className="admin-field-grid">
            <label className="field-label">Tên hiển thị<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
            <label className="field-label">Vai trò<select value={role} onChange={(event) => setRole(event.target.value as UserResponse['role'])} disabled={isSelf}><option value="user">user</option><option value="admin">admin</option></select></label>
            <label className="field-label">Trạng thái<select value={status} onChange={(event) => setStatus(event.target.value as UserResponse['status'])} disabled={isSelf}><option value="active">active</option><option value="disabled">disabled</option></select></label>
            <label className="field-label">Gói<select value={plan} onChange={(event) => setPlan(event.target.value)}>{!planOptions.some((option) => option.id === plan) && <option value={plan}>{plan}</option>}{planOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
          </div>
          {isSelf && <p className="field-hint">Bạn không thể thay đổi role/status của chính mình.</p>}
          <button type="button" className="secondary-button" onClick={() => void save()} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu thay đổi'}</button>
        </div>
      )}
      {sessionsOpen && (
        <div className="admin-session-panel">
          <div className="admin-detail-header"><h4>Phiên đăng nhập</h4><button type="button" className="secondary-button" onClick={() => void revokeAllSessions()}>Thu hồi tất cả</button></div>
          {sessions.map((session) => (
            <article className="admin-row" key={session.id}>
              <div><strong>{session.id}</strong><span>{formatHistoryDate(session.created_at)} · hết hạn {formatHistoryDate(session.expires_at)} · {session.ip_address || 'unknown IP'}</span><span>{session.user_agent || 'unknown user agent'}</span></div>
              <button type="button" className="secondary-button" onClick={() => void revokeSession(session.id)}>Thu hồi</button>
            </article>
          ))}
          {sessions.length === 0 && <p className="field-hint">Không có phiên còn hiệu lực.</p>}
        </div>
      )}
    </>
  );
}

function AdminRenderJobDetailPanel({ detail, onOpen, onClose }: { detail: AdminRenderHistoryDetail; onOpen: () => void; onClose: () => void }) {
  return (
    <section className="admin-detail-panel">
      <div className="admin-detail-header">
        <div><h4>Chi tiết render job</h4><p>{detail.id}</p></div>
        <div className="admin-row-actions"><button type="button" className="secondary-button" onClick={onOpen}>Mở trong renderer</button><button type="button" className="secondary-button" onClick={onClose}>Đóng</button></div>
      </div>
      <div className="admin-field-grid">
        <span><strong>User</strong>{detail.user_id || 'guest'}</span>
        <span><strong>Thời gian</strong>{formatHistoryDate(detail.created_at)}</span>
        <span><strong>Provider</strong>{detail.provider || 'auto'}</span>
        <span><strong>Model</strong>{detail.model || 'default'}</span>
        <span><strong>Renderer</strong>{detail.renderer || 'auto'}</span>
        <span><strong>Nguồn</strong>{detail.source_type}</span>
      </div>
      <p className="admin-problem-text">{detail.problem_text}</p>
      {detail.warnings.length > 0 && <AdminDetails title="Warnings" value={detail.warnings} />}
      <AdminDetails title="Scene JSON" value={detail.scene} />
      <AdminDetails title="Payload JSON" value={detail.payload} />
      <AdminDetails title="Render request" value={detail.render_request} />
      <AdminDetails title="Advanced settings" value={detail.advanced_settings} />
      <AdminDetails title="Runtime settings" value={detail.runtime_settings} />
    </section>
  );
}

function AdminSystemSettingRow({ item }: { item: SystemSettingResponse }) {
  return (
    <article className="admin-row admin-row-block">
      <div><strong>{item.key}</strong><span>Cập nhật {formatHistoryDate(item.updated_at)}{item.updated_by ? ` · ${item.updated_by}` : ''}</span></div>
      <AdminDetails title="Giá trị JSON" value={item.value} />
    </article>
  );
}

function AdminDatabaseDiagnosticsPanel({ diagnostics }: { diagnostics: AdminDatabaseDiagnostics }) {
  const countRows = Object.entries(diagnostics.counts);
  const settingRows = Object.entries(diagnostics.system_settings);
  return (
    <div className="admin-section-stack">
      <div className="admin-field-grid">
        <span><strong>Backend</strong>{diagnostics.backend}</span>
        <span><strong>SQLite path</strong>{diagnostics.sqlite_path || diagnostics.configured_sqlite_path || 'Không dùng SQLite'}</span>
        <span><strong>Migrations</strong>{diagnostics.migrations.length} đã áp dụng</span>
        <span><strong>Legacy ai_settings</strong>{diagnostics.ai_settings.exists ? 'Có' : 'Không'}</span>
      </div>
      <section className="admin-settings-section">
        <h4>Bảng dữ liệu</h4>
        <div className="admin-table">
          {countRows.map(([name, count]) => <article className="admin-row" key={name}><div><strong>{name}</strong><span>{String(count)} bản ghi</span></div></article>)}
          {countRows.length === 0 && <p className="field-hint">Chưa có thống kê bảng.</p>}
        </div>
      </section>
      <section className="admin-settings-section">
        <h4>system_settings</h4>
        <div className="admin-table">
          {settingRows.map(([key, meta]) => <article className="admin-row" key={key}><div><strong>{key}</strong><span>Cập nhật {formatHistoryDate(meta.updated_at)}{meta.updated_by ? ` · ${meta.updated_by}` : ''}</span></div></article>)}
          {settingRows.length === 0 && <p className="field-hint">Chưa có bản ghi system_settings.</p>}
        </div>
      </section>
      <AdminDetails title="Migration raw" value={diagnostics.migrations} />
    </div>
  );
}

function AdminAuditLogRow({ log }: { log: AuditLogResponse }) {
  const truncateId = (id: string | null) => {
    if (!id) return '';
    if (id.length <= 12) return id;
    return `${id.slice(0, 8)}...${id.slice(-4)}`;
  };

  const actorDisplay = log.actor_user_id ? truncateId(log.actor_user_id) : 'system';
  const targetDisplay = log.target_id ? `${log.target_type}/${truncateId(log.target_id)}` : log.target_type;

  return (
    <article className="admin-row admin-row-block">
      <div>
        <strong>{log.action}</strong>
        <span>{formatHistoryDate(log.created_at)} · {actorDisplay} · {targetDisplay}</span>
      </div>
      {hasObjectKeys(log.metadata) && <AdminDetails title="Metadata" value={log.metadata} />}
    </article>
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function collectAdminModelIds(aiSettings: Record<string, unknown>) {
  const ids = new Set<string>();
  ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'].forEach((provider) => {
    const item = aiSettings[provider];
    if (!item || typeof item !== 'object') return;
    const data = item as Record<string, unknown>;
    if (typeof data.model === 'string' && data.model) ids.add(data.model);
    if (Array.isArray(data.allowed_model_ids)) data.allowed_model_ids.map(String).filter(Boolean).forEach((id) => ids.add(id));
    if (Array.isArray(data.scanned_models)) {
      data.scanned_models.forEach((modelItem) => {
        const id = typeof modelItem === 'string' ? modelItem : modelItem && typeof modelItem === 'object' ? (modelItem as Record<string, unknown>).id : '';
        if (typeof id === 'string' && id) ids.add(id);
      });
    }
  });
  return [...ids];
}

function buildDailyActivity(stats: Array<{ day: string; count: number }>) {
  const counts = new Map(stats.map((item) => [item.day, Number(item.count) || 0]));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Array.from({ length: 14 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (13 - index));
    const day = formatLocalDateKey(date);
    return {
      day,
      count: counts.get(day) ?? 0,
      label: date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' }),
    };
  });
}

function formatLocalDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function summarizeRenderJobs(renderJobs: AdminRenderHistoryItem[]) {
  const counts = new Map<string, number>();
  renderJobs.forEach((job) => {
    const key = `${job.provider || 'auto'} / ${job.model || 'default'}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return [...counts.entries()].map(([key, count]) => ({ key, count })).sort((left, right) => right.count - left.count).slice(0, 8);
}
