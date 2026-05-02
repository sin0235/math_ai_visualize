import { useEffect, useRef, useState } from 'react';

import { ApiError, changePassword, deleteAdminRenderJob, deleteRenderHistory, forgotPassword, getAdminAuditLogs, getAdminRenderJobDetail, getAdminRenderJobs, getAdminSummary, getAdminSystemSettings, getAdminUserSessions, getAdminUsers, getCurrentUser, getGoogleOAuthStartUrl, getHealth, getRenderHistory, getRenderHistoryDetail, getSessions, getSettingsDefaults, getUserSettings, login, logout, ocrImage, register, renderEditedScene, renderProblem, resendVerification, resetPassword, revokeAdminUserSession, revokeAllAdminUserSessions, revokeOtherSessions, revokeSession, saveAdminSystemSetting, saveUserSettings, scanProviderModels, scanRouter9Models, updateAdminUser, updateProfile, verifyEmail, type AdminAuditLogFilters, type AdminRenderHistoryDetail, type AdminRenderHistoryItem, type AdminRenderJobFilters, type AdminSessionResponse, type AdminSummaryResponse, type AdminUserFilters, type AuditLogResponse, type RenderHistoryItem, type SessionResponse, type SystemSettingResponse, type UserResponse } from './api/client';
import { defaultAdvancedSettings, ProblemInput, staticModelOptions, type ModelOption } from './components/ProblemInput';
import { GeneralSettingsPanel } from './components/GeneralSettingsPanel';
import { AccountPage } from './components/AccountPage';
import { HomePage } from './components/HomePage';
import { LoginPage } from './components/LoginPage';
import { ResetPasswordPage } from './components/ResetPasswordPage';
import { VerifyEmailPage } from './components/VerifyEmailPage';
import { RendererPanel } from './components/RendererPanel';
import { SceneEditorPanel, type PointPlacementPlane } from './components/SceneEditorPanel';
import { PrivacyPolicyPage, TermsPage } from './components/LegalPages';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, SETTINGS_STORAGE_VERSION, type OcrProvider, type RuntimeSettings, type SettingsDefaults } from './types/settings';
import logoUrl from '../img.svg';
import './styles.css';

const SETTINGS_STORAGE_KEY = 'hinh-runtime-settings';
const MOBILE_WARNING_STORAGE_KEY = 'hinh-mobile-warning-dismissed';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 900px)';
const DEVELOPER_GITHUB_URL = 'https://github.com/sin0235';
const CONTACT_EMAIL = 'contact@math-renderer.sin235.live';

type AppView = 'home' | 'render' | 'history' | 'guide' | 'about' | 'privacy-policy' | 'terms' | 'login' | 'settings' | 'admin' | 'account' | 'reset-password' | 'verify-email';
type EditTool = 'move' | 'connect' | 'project_to_segment' | 'add_point';
type Vec3 = { x: number; y: number; z: number };
type Notification = {
  id: number;
  kind: 'error' | 'warning' | 'info';
  title: string;
  message: string;
  details: string[];
};
type BackendStatus = {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
};

function FooterNavIcon({ children }: { children: React.ReactNode }) {
  return (
    <svg className="footer-nav-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

function FooterNavButton({ onClick, children, icon }: { onClick: () => void; children: React.ReactNode; icon: React.ReactNode }) {
  return (
    <button type="button" className="footer-nav-link" onClick={onClick}>
      {icon}
      <span className="footer-nav-label">{children}</span>
    </button>
  );
}

function FooterNavMailLink({
  href,
  title,
  children,
  icon,
}: {
  href: string;
  title?: string;
  children: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <a href={href} className="footer-nav-link" title={title}>
      {icon}
      <span className="footer-nav-label">{children}</span>
    </a>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('home');
  const [result, setResult] = useState<RenderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [problemText, setProblemText] = useState('Cho A(1,2), B(4,5). Vẽ đường thẳng AB.');
  const [lastAdvancedSettings, setLastAdvancedSettings] = useState<AdvancedRenderSettings>(defaultAdvancedSettings);
  const [editTool, setEditTool] = useState<EditTool>('move');
  const [pointToSegmentSource, setPointToSegmentSource] = useState<string | null>(null);
  const [pointPlacementPlane, setPointPlacementPlane] = useState<PointPlacementPlane>('xy');
  const [pointPlacementDepth, setPointPlacementDepth] = useState('0');
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettings>(defaultRuntimeSettings);
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsDefaults | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'checking' });
  const [notification, setNotification] = useState<Notification | null>(null);
  const [mobileWarningDismissed, setMobileWarningDismissed] = useState(readMobileWarningDismissed);
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false);
  const [editorButtonTop, setEditorButtonTop] = useState(220);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authToken, setAuthToken] = useState('');
  const [historyItems, setHistoryItems] = useState<RenderHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [remoteSettingsHydrated, setRemoteSettingsHydrated] = useState(false);
  const [adminSummary, setAdminSummary] = useState<AdminSummaryResponse | null>(null);
  const [adminUsers, setAdminUsers] = useState<UserResponse[]>([]);
  const [adminRenderJobs, setAdminRenderJobs] = useState<AdminRenderHistoryItem[]>([]);
  const [adminSettings, setAdminSettings] = useState<SystemSettingResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [adminUserQuery, setAdminUserQuery] = useState('');
  const [adminUserFilters, setAdminUserFilters] = useState<AdminUserFilters>({});
  const [adminRenderJobFilters, setAdminRenderJobFilters] = useState<AdminRenderJobFilters>({});
  const [adminAuditLogFilters, setAdminAuditLogFilters] = useState<AdminAuditLogFilters>({});
  const [adminLoading, setAdminLoading] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const resultAnchorRef = useRef<HTMLDivElement | null>(null);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);
  const editorButtonDragRef = useRef<{ pointerId: number; startY: number; startTop: number; moved: boolean } | null>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (!saved) return;
      setRuntimeSettings(loadStoredSettings(saved));
    } catch {
      // Keep defaults when local storage is invalid.
    }
  }, []);

  useEffect(() => {
    if (!accountMenuOpen) return;
    function handlePointerDown(event: PointerEvent) {
      if (!accountMenuRef.current?.contains(event.target as Node)) setAccountMenuOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setAccountMenuOpen(false);
    }
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [accountMenuOpen]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([getHealth(), getSettingsDefaults()])
      .then(([health, defaults]) => {
        if (cancelled) return;
        setBackendStatus({ state: 'online', appName: health.app });
        setSettingsDefaults(defaults);
        setRuntimeSettings((current) => mergeBackendDefaults(current, defaults));
      })
      .catch(() => {
        if (cancelled) return;
        setBackendStatus({ state: 'offline' });
        setSettingsDefaults(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ version: SETTINGS_STORAGE_VERSION, settings: sanitizeSettingsForStorage(runtimeSettings) }));
  }, [runtimeSettings]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('auth');
    const authError = params.get('auth_error');
    const token = params.get('token');
    if (action === 'google-success') {
      setActiveView('render');
      showNotification('Đăng nhập Google', 'Đăng nhập Google thành công. Workspace của bạn đã được đồng bộ.', [], 'info');
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }
    if (authError) {
      setActiveView('login');
      const message = authError === 'google_unverified_email'
        ? 'Email Google này chưa được xác minh nên chưa thể đăng nhập.'
        : 'Không thể hoàn tất đăng nhập Google. Hãy thử lại hoặc dùng email/mật khẩu.';
      showNotification('Đăng nhập Google', message, [], 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }
    if (action && token) {
      setAuthToken(token);
      if (action === 'reset-password') setActiveView('reset-password');
      if (action === 'verify-email') setActiveView('verify-email');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then(async ({ user }) => {
        if (cancelled) return;
        setUser(user);
        await loadRemoteWorkspace(user);
        if (user.role === 'admin') {
          setActiveView('admin');
          await loadAdminWorkspaceForUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
          setRemoteSettingsHydrated(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!user || !remoteSettingsHydrated) return;
    const timer = window.setTimeout(() => {
      saveUserSettings(sanitizeSettingsForStorage(runtimeSettings)).catch(() => undefined);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [runtimeSettings, user, remoteSettingsHydrated]);

  useEffect(() => {
    if (!notification) return;
    const timer = window.setTimeout(() => setNotification(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notification]);

  useEffect(() => {
    setEditorButtonTop(clamp(window.innerHeight * 0.55, 84, window.innerHeight - 88));
  }, []);

  const modelOptions = buildModelOptions(runtimeSettings, settingsDefaults);
  const threeInteraction = result?.scene.renderer === 'threejs_3d'
    ? {
        mode: editTool,
        selectedPoint: pointToSegmentSource,
        onPointClick: setPointToSegmentSource,
        onSegmentClick: handlePointToSegmentClick,
        onPointDragEnd: handlePointDragEnd,
        onConnectPoints: handleConnectPoints,
        pointPlacementPlane,
        pointPlacementDepth: Number(pointPlacementDepth),
        onCanvasClick: handleCanvasClickToAddPoint,
      }
    : undefined;

  async function handleOcrClipboardImage() {
    if (!navigator.clipboard?.read) {
      const message = 'Trình duyệt chưa hỗ trợ đọc ảnh từ clipboard.';
      showNotification('OCR thất bại', message);
      return;
    }
    try {
      const clipboardItems = await navigator.clipboard.read();
      for (const item of clipboardItems) {
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageType) continue;
        const blob = await item.getType(imageType);
        await handleOcrImage(new File([blob], 'clipboard-image.png', { type: imageType }));
        return;
      }
      const message = 'Clipboard hiện không có ảnh để OCR.';
      showNotification('OCR thất bại', message);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không đọc được ảnh từ clipboard.');
      showApiError('OCR thất bại', apiError, 'Hãy kiểm tra ảnh có rõ chữ không, model OCR đã chọn có hỗ trợ ảnh không, hoặc thử provider/model khác.');
    }
  }

  async function handleOcrImage(file: File) {
    if (settingsDefaults?.router9.only_mode && settingsDefaults.router9.allowed_model_ids.length === 0 && !settingsDefaults.router9.model) {
      const message = '9router-only đang bật nhưng admin chưa cấu hình model OCR khả dụng.';
      showNotification('OCR thất bại', message);
      return;
    }
    if (!file.type.startsWith('image/')) {
      const message = 'File OCR phải là ảnh.';
      showNotification('OCR thất bại', message);
      return;
    }
    const maxBytes = Math.max(1, runtimeSettings.ocr.max_image_mb) * 1024 * 1024;
    if (file.size > maxBytes) {
      const message = `Ảnh OCR vượt quá giới hạn ${runtimeSettings.ocr.max_image_mb}MB.`;
      showNotification('OCR thất bại', message);
      return;
    }

    setOcrLoading(true);
    try {
      const imageDataUrl = await fileToDataUrl(file);
      const response = await ocrImage(imageDataUrl, runtimeSettings);
      setProblemText(response.text.trim());
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể OCR ảnh đề bài.');
      showApiError('OCR thất bại', apiError, 'Hãy kiểm tra ảnh có rõ chữ không, model OCR đã chọn có hỗ trợ ảnh không, hoặc thử provider/model khác.');
    } finally {
      setOcrLoading(false);
    }
  }

  async function handleSubmit(
    problemText: string,
    preferredAiProvider?: string,
    preferredAiModel?: string,
    advancedSettings?: AdvancedRenderSettings,
    preferredRenderer?: Renderer,
  ) {
    setLoading(true);
    setPointToSegmentSource(null);
    setEditTool('move');
    setLastAdvancedSettings(advancedSettings ?? defaultAdvancedSettings);
    try {
      const response = await renderProblem(problemText, preferredAiProvider, preferredAiModel, advancedSettings, preferredRenderer, runtimeSettings);
      setResult(response);
      if (user) void refreshHistory();
      scrollToResultOnMobile();
      showWarnings(response.warnings);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể dựng hình từ đề bài này.');
      showApiError('Dựng hình thất bại', apiError, 'Hãy thử chọn model khác, kiểm tra API key/quota, hoặc viết đề bài rõ hơn.');
    } finally {
      setLoading(false);
    }
  }

  function resetSettings() {
    setRuntimeSettings(defaultRuntimeSettings);
  }

  function dismissMobileWarning() {
    setMobileWarningDismissed(true);
    try {
      window.localStorage.setItem(MOBILE_WARNING_STORAGE_KEY, 'true');
    } catch {
      // Ignore blocked storage.
    }
  }

  function scrollToResult() {
    resultAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function scrollToResultOnMobile() {
    if (!window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches) return;
    window.requestAnimationFrame(() => scrollToResult());
  }

  async function handleLogin(email: string, password: string) {
    setAuthLoading(true);
    try {
      setRemoteSettingsHydrated(false);
      const response = await login(email, password);
      setUser(response.user);
      await loadRemoteWorkspace(response.user);
      if (response.user.role === 'admin') {
        setActiveView('admin');
        await loadAdminWorkspaceForUser(response.user);
      } else {
        setActiveView('render');
      }
    } finally {
      setAuthLoading(false);
    }
  }

  function handleGoogleLogin() {
    window.location.href = getGoogleOAuthStartUrl();
  }

  async function handleRegister(email: string, password: string, displayName: string | undefined, acceptPrivacyPolicy: boolean, acceptTerms: boolean) {
    setAuthLoading(true);
    try {
      setRemoteSettingsHydrated(false);
      const response = await register(email, password, displayName, acceptPrivacyPolicy, acceptTerms);
      setUser(response.user);
      if (response.user.email_verified_at) {
        await saveUserSettings(sanitizeSettingsForStorage(runtimeSettings));
        await refreshHistory();
        setRemoteSettingsHydrated(true);
        setActiveView('account');
      } else {
        setRemoteSettingsHydrated(true);
        setActiveView('login');
      }
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    setAuthLoading(true);
    try {
      await logout();
      setUser(null);
      setHistoryItems([]);
      setHistoryOpen(false);
      setRemoteSettingsHydrated(true);
      setActiveView('login');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleForgotPassword(email: string) {
    const response = await forgotPassword(email);
    return response.message;
  }

  async function handleResetPassword(token: string, password: string) {
    const response = await resetPassword(token, password);
    return response.message;
  }

  async function handleVerifyEmail(token: string, otp: string) {
    const response = await verifyEmail(token, otp);
    setUser(response.user);
  }

  async function handleResendVerification() {
    if (!user?.email) return 'Hãy nhập email ở trang đăng nhập để gửi lại xác minh.';
    const response = await resendVerification(user.email);
    return response.message;
  }

  async function handleUpdateProfile(displayName: string) {
    const response = await updateProfile(displayName);
    setUser(response.user);
  }

  async function handleChangePassword(currentPassword: string, newPassword: string) {
    const response = await changePassword(currentPassword, newPassword);
    return response.message;
  }

  async function handleLoadSessions(): Promise<SessionResponse[]> {
    return getSessions();
  }

  async function handleRevokeSession(id: string) {
    const response = await revokeSession(id);
    return response.message;
  }

  async function handleRevokeOtherSessions() {
    const response = await revokeOtherSessions();
    return response.message;
  }

  async function loadRemoteWorkspace(_: UserResponse) {
    try {
      const [remoteSettings] = await Promise.all([
        getUserSettings().catch(() => null),
        refreshHistory(),
      ]);
      const savedSettings = remoteSettings?.settings;
      if (savedSettings) {
        setRuntimeSettings((current) => loadRemoteSettings(savedSettings, current));
      } else {
        await saveUserSettings(sanitizeSettingsForStorage(runtimeSettings));
      }
    } finally {
      setRemoteSettingsHydrated(true);
    }
  }

  async function refreshHistory() {
    setHistoryLoading(true);
    try {
      setHistoryItems(await getRenderHistory());
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadAdminWorkspace() {
    if (!user) return;
    await loadAdminWorkspaceForUser(user);
  }

  async function loadAdminWorkspaceForUser(targetUser: UserResponse) {
    if (targetUser.role !== 'admin') {
      showNotification('Không có quyền quản trị', 'Tài khoản hiện tại không có quyền truy cập trang quản trị.');
      setActiveView('render');
      return;
    }
    setAdminLoading(true);
    try {
      const [summary, users, jobs, settings, logs] = await Promise.all([
        getAdminSummary(),
        getAdminUsers({ ...adminUserFilters, q: adminUserQuery }),
        getAdminRenderJobs(adminRenderJobFilters),
        getAdminSystemSettings(),
        getAdminAuditLogs(adminAuditLogFilters),
      ]);
      setAdminSummary(summary);
      setAdminUsers(users);
      setAdminRenderJobs(jobs);
      setAdminSettings(settings);
      setAuditLogs(logs);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể tải trang quản trị.');
      showApiError('Không thể tải admin', apiError, 'Hãy kiểm tra tài khoản có quyền admin và phiên đăng nhập còn hiệu lực.');
    } finally {
      setAdminLoading(false);
    }
  }

  async function searchAdminUsers(query: string, filters: AdminUserFilters = adminUserFilters) {
    try {
      setAdminUsers(await getAdminUsers({ ...filters, q: query }));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể tìm người dùng.');
      showApiError('Không thể tìm user', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
    }
  }

  async function searchAdminRenderJobs(filters: AdminRenderJobFilters) {
    setAdminRenderJobFilters(filters);
    try {
      setAdminRenderJobs(await getAdminRenderJobs(filters));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể lọc render jobs.');
      showApiError('Không thể lọc render jobs', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
    }
  }

  async function searchAdminAuditLogs(filters: AdminAuditLogFilters) {
    setAdminAuditLogFilters(filters);
    try {
      setAuditLogs(await getAdminAuditLogs(filters));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể lọc audit logs.');
      showApiError('Không thể lọc audit logs', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
    }
  }

  async function updateAdminUserPatch(target: UserResponse, patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>>) {
    try {
      const updated = await updateAdminUser(target.id, patch);
      setAdminUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      void loadAdminWorkspace();
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể cập nhật người dùng.');
      showApiError('Không thể cập nhật user', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
      throw apiError;
    }
  }

  async function toggleUserStatus(target: UserResponse) {
    const nextStatus = target.status === 'active' ? 'disabled' : 'active';
    await updateAdminUserPatch(target, { status: nextStatus });
  }

  async function removeAdminRenderJob(id: string) {
    try {
      await deleteAdminRenderJob(id);
      setAdminRenderJobs((current) => current.filter((item) => item.id !== id));
      void loadAdminWorkspace();
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể xoá render job.');
      showApiError('Không thể xoá render job', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
    }
  }

  function openAdminRenderJobDetail(detail: AdminRenderHistoryDetail) {
    setProblemText(detail.problem_text);
    setResult({ scene: detail.scene, payload: detail.payload, warnings: detail.warnings });
    setActiveView('render');
    scrollToResultOnMobile();
  }

  async function openHistoryItem(id: string) {
    try {
      const detail = await getRenderHistoryDetail(id);
      setProblemText(detail.problem_text);
      setResult({ scene: detail.scene, payload: detail.payload, warnings: detail.warnings });
      setActiveView('render');
      scrollToResultOnMobile();
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể mở lịch sử dựng hình.');
      showApiError('Không thể mở lịch sử', apiError, 'Hãy đăng nhập lại hoặc thử tải lại trang.');
    }
  }

  async function removeHistoryItem(id: string) {
    try {
      await deleteRenderHistory(id);
      setHistoryItems((current) => current.filter((item) => item.id !== id));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể xoá lịch sử dựng hình.');
      showApiError('Không thể xoá lịch sử', apiError, 'Hãy thử lại sau.');
    }
  }

  async function handleSceneEdit(scene: MathScene) {
    setEditorSaving(true);
    try {
      const response = await renderEditedScene(scene, lastAdvancedSettings);
      setResult(response);
      if (user) void refreshHistory();
      showWarnings(response.warnings);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể lưu chỉnh sửa hình.');
      showApiError('Không thể lưu chỉnh sửa', apiError, 'Hãy kiểm tra thao tác vừa chỉnh có làm thiếu điểm, thiếu đoạn hoặc dữ liệu hình không hợp lệ không.');
    } finally {
      setEditorSaving(false);
    }
  }

  async function handlePointDragEnd(name: string, point: Vec3) {
    if (!result?.scene) return;
    const editedScene: MathScene = {
      ...result.scene,
      objects: result.scene.objects.map((obj) => {
        if ((obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name) {
          if (obj.type === 'point_3d') {
            return { ...obj, x: round(point.x), y: round(point.y), z: round(point.z) };
          }
          return { ...obj, x: round(point.x), y: round(point.y) };
        }
        return obj;
      }),
    };
    await handleSceneEdit(editedScene);
  }

  function showNotification(title: string, message: string, details: string[] = [], kind: Notification['kind'] = 'error') {
    setNotification({ id: Date.now(), kind, title, message: friendlyMessage(message), details: friendlyDetails(details) });
  }

  function showApiError(title: string, error: ApiError, fallbackSuggestion: string) {
    const details = error.details.length > 0 ? error.details : [fallbackSuggestion];
    showNotification(title, error.message, details, 'error');
  }

  function showWarnings(warnings: string[]) {
    if (warnings.length === 0) return;
    showNotification('Đã dựng hình với lưu ý', 'Hình đã được tạo, nhưng hệ thống phải dùng phương án dự phòng.', warnings, 'warning');
  }

  async function handleConnectPoints(start: string, end: string) {
    if (!result?.scene) return;
    if (start === end) {
      const message = 'Chọn hai điểm khác nhau để nối đoạn.';
      showNotification('Không thể nối đoạn', message);
      return;
    }
    if (hasSegment(result.scene, start, end)) {
      const message = `Đoạn ${start}${end} đã tồn tại.`;
      showNotification('Không thể nối đoạn', message);
      return;
    }
    const editedScene: MathScene = {
      ...result.scene,
      objects: [
        ...result.scene.objects,
        { type: 'segment', points: [start, end], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
      ],
    };
    await handleSceneEdit(editedScene);
  }

  async function handlePointToSegmentClick(segmentPoints: [string, string], clickedPoint: Vec3) {
    if (!result?.scene || !pointToSegmentSource || editTool !== 'project_to_segment') {
      const message = 'Chọn công cụ tạo chân nối, chọn một điểm nguồn, rồi click vào đoạn đích.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }
    if (segmentPoints.includes(pointToSegmentSource)) {
      const message = 'Điểm nguồn đang nằm trên đoạn đích. Hãy chọn đoạn khác nếu muốn nối thêm.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }

    const source = findPoint(result.scene, pointToSegmentSource);
    const start = findPoint(result.scene, segmentPoints[0]);
    const end = findPoint(result.scene, segmentPoints[1]);
    if (!source || !start || !end) {
      const message = 'Không tìm thấy điểm nguồn hoặc đoạn đích trong scene.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }

    const newPoint = projectPointToSegment(clickedPoint, start, end);
    const newName = nextPointName(result.scene);
    const editedScene: MathScene = {
      ...result.scene,
      objects: [
        ...result.scene.objects,
        { type: 'point_3d', name: newName, x: round(newPoint.x), y: round(newPoint.y), z: round(newPoint.z) },
        { type: 'segment', points: [pointToSegmentSource, newName], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
      ],
    };

    setPointToSegmentSource(null);
    await handleSceneEdit(editedScene);
  }

  async function handleCanvasClickToAddPoint(clickedPoint: Vec3) {
    if (!result?.scene) return;
    if (editorSaving) return;

    const dim = result.scene.view.dimension;
    const name = nextPointName(result.scene);
    const point = dim === '3d'
      ? { type: 'point_3d' as const, name, x: round(clickedPoint.x), y: round(clickedPoint.y), z: round(clickedPoint.z) }
      : { type: 'point_2d' as const, name, x: round(clickedPoint.x), y: round(clickedPoint.y) };

    const editedScene: MathScene = {
      ...result.scene,
      objects: [...result.scene.objects, point],
    };
    await handleSceneEdit(editedScene);
  }

  function handleEditorButtonPointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    editorButtonDragRef.current = { pointerId: event.pointerId, startY: event.clientY, startTop: editorButtonTop, moved: false };
  }

  function handleEditorButtonPointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = editorButtonDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const delta = event.clientY - drag.startY;
    if (Math.abs(delta) > 3) drag.moved = true;
    setEditorButtonTop(clamp(drag.startTop + delta, 84, window.innerHeight - 88));
  }

  function handleEditorButtonPointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    window.setTimeout(() => {
      editorButtonDragRef.current = null;
    }, 0);
  }

  if (activeView === 'admin') {
    return (
      <>
        <NotificationBanner notification={notification} onDismiss={() => setNotification(null)} />
        <AdminConsole
          user={user}
          summary={adminSummary}
          users={adminUsers}
          renderJobs={adminRenderJobs}
          settings={adminSettings}
          auditLogs={auditLogs}
          userQuery={adminUserQuery}
          loading={adminLoading}
          onRefresh={loadAdminWorkspace}
          onUserQueryChange={setAdminUserQuery}
          userFilters={adminUserFilters}
          renderJobFilters={adminRenderJobFilters}
          auditLogFilters={adminAuditLogFilters}
          onSearchUsers={searchAdminUsers}
          onUserFiltersChange={setAdminUserFilters}
          onSearchRenderJobs={searchAdminRenderJobs}
          onSearchAuditLogs={searchAdminAuditLogs}
          onUpdateUser={updateAdminUserPatch}
          onToggleUserStatus={toggleUserStatus}
          onDeleteRenderJob={removeAdminRenderJob}
          onOpenRenderJobDetail={openAdminRenderJobDetail}
          onBackToApp={() => setActiveView('home')}
        />
      </>
    );
  }

  return (
    <>
      <header className="global-header">
        <div
          className="header-left"
          role="button"
          tabIndex={0}
          onClick={() => setActiveView('home')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setActiveView('home');
            }
          }}
        >
          <img src={logoUrl} alt="App Logo" className="header-logo" />
          <div className="header-titles">
            <h1 className="header-title">AI Math Renderer</h1>
            <span className="header-subtitle">Dựng hình toán học từ ngôn ngữ tự nhiên</span>
          </div>
        </div>
        <nav className="header-nav">
          <button type="button" className={`nav-item ${activeView === 'render' ? 'active' : ''}`} onClick={() => setActiveView('render')}>
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="12" x2="14" y2="12"></line><line x1="4" y1="18" x2="18" y2="18"></line></svg>
            Workspace
          </button>
          {user?.role === 'admin' && (
            <button type="button" className="nav-item" onClick={() => {
              setActiveView('admin');
              void loadAdminWorkspace();
            }}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
              Admin
            </button>
          )}
          {user ? (
            <div className="account-menu" ref={accountMenuRef}>
              <button type="button" className={`account-menu-trigger ${activeView === 'history' || activeView === 'settings' || activeView === 'account' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen((open) => !open)}>
                <span className="account-avatar" aria-hidden="true">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</span>
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>
                <span className="sr-only">Mở menu tài khoản</span>
              </button>
              {accountMenuOpen && (
                <div className="account-dropdown" role="menu">
                  <div className="account-dropdown-email">{user.email}</div>
                  <div className="account-dropdown-group">
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      setActiveView('history');
                      void refreshHistory();
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 3v6h6"></path><path d="M12 7v5l3 2"></path></svg>
                      Lịch sử
                    </button>
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      setActiveView('settings');
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10.91 3H11a2 2 0 1 1 4 0h.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0A1.65 1.65 0 0 0 21 10.91V11a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                      Cài đặt chung
                    </button>
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      setActiveView('account');
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                      Đổi mật khẩu
                    </button>
                  </div>
                  <div className="account-dropdown-group danger">
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      void handleLogout();
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><path d="M16 17l5-5-5-5"></path><path d="M21 12H9"></path></svg>
                      Đăng xuất
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button type="button" className={`nav-item ${activeView === 'login' ? 'active' : ''}`} onClick={() => setActiveView('login')}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><path d="M10 17l5-5-5-5"></path><path d="M15 12H3"></path></svg>
              Đăng nhập
            </button>
          )}
        </nav>
      </header>

      <NotificationBanner notification={notification} onDismiss={() => setNotification(null)} />
      {activeView === 'render' && <MobileRendererWarning dismissed={mobileWarningDismissed} onDismiss={dismissMobileWarning} />}

      <main className="app-shell">
        {activeView === 'home' && (
          <HomePage
            logoUrl={logoUrl}
            backendStatus={{ ...backendStatus, settingsDefaults }}
            onStartRender={() => setActiveView('render')}
            onOpenSettings={() => setActiveView('settings')}
            onOpenLogin={() => setActiveView('login')}
          />
        )}
        {activeView === 'render' && (
          <section className="workspace">
            <div className="workspace-sidebar">
              <ProblemInput
                loading={loading}
                ocrLoading={ocrLoading}
                ocrError={null}
                problemText={problemText}
                modelOptions={modelOptions}
                router9Only={settingsDefaults?.router9.only_mode ?? false}
                onProblemTextChange={setProblemText}
                onOcrImage={handleOcrImage}
                onOcrClipboardImage={handleOcrClipboardImage}
                onOpenRouter9Settings={() => setActiveView(user?.role === 'admin' ? 'admin' : 'settings')}
                onSubmit={handleSubmit}
              />
              {user && (
                <div className="history-drawer-wrap">
                  <button type="button" className="secondary-button history-toggle" onClick={() => setHistoryOpen((open) => !open)}>
                    {historyOpen ? 'Ẩn lịch sử' : `Lịch sử (${historyItems.length})`}
                  </button>
                  {historyOpen && <HistoryPanel items={historyItems} loading={historyLoading} onOpen={openHistoryItem} onDelete={removeHistoryItem} />}
                </div>
              )}
            </div>
            {result && <button type="button" className="mobile-scroll-notice" onClick={scrollToResult}>↓ Xem hình vừa dựng</button>}
            <div className="result-area" ref={resultAnchorRef}>
              <div className="render-stage">
                <RendererPanel result={result} threeInteraction={threeInteraction} onGeoGebraPointChange={handlePointDragEnd} />
                {result?.scene && (
                  <button
                    type="button"
                    className="render-editor-trigger"
                    style={{ top: editorButtonTop }}
                    onPointerDown={handleEditorButtonPointerDown}
                    onPointerMove={handleEditorButtonPointerMove}
                    onPointerUp={handleEditorButtonPointerUp}
                    onPointerCancel={handleEditorButtonPointerUp}
                    onClick={() => {
                      if (editorButtonDragRef.current?.moved) return;
                      setSceneEditorOpen(true);
                    }}
                  >
                    Chỉnh hình
                  </button>
                )}
                {sceneEditorOpen && result?.scene && (
                  <div className="scene-editor-layer" role="presentation" onMouseDown={() => setSceneEditorOpen(false)}>
                    <div className="scene-editor-popover" role="dialog" aria-modal="true" aria-label="Chỉnh hình" onMouseDown={(event) => event.stopPropagation()}>
                      <div className="scene-editor-popover-header">
                        <strong>Chỉnh hình</strong>
                        <button type="button" className="scene-editor-close" onClick={() => setSceneEditorOpen(false)} aria-label="Đóng chỉnh hình">×</button>
                      </div>
                      <SceneEditorPanel
                        scene={result.scene}
                        saving={editorSaving}
                        editTool={editTool}
                        selectedPoint={pointToSegmentSource}
                        pointPlacementPlane={pointPlacementPlane}
                        pointPlacementDepth={pointPlacementDepth}
                        onPointPlacementPlaneChange={setPointPlacementPlane}
                        onPointPlacementDepthChange={setPointPlacementDepth}
                        onEditToolChange={(tool) => {
                          setEditTool(tool);
                          setPointToSegmentSource(null);
                        }}
                        onChange={handleSceneEdit}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
        {activeView === 'history' && (
          <HistoryPage
            user={user}
            items={historyItems}
            loading={historyLoading}
            onOpen={openHistoryItem}
            onDelete={removeHistoryItem}
            onLogin={() => setActiveView('login')}
            onWorkspace={() => setActiveView('render')}
          />
        )}
        {activeView === 'guide' && <GuidePage onStart={() => setActiveView('render')} onSettings={() => setActiveView('settings')} />}
        {activeView === 'about' && <AboutPage onStart={() => setActiveView('render')} onGuide={() => setActiveView('guide')} />}
        {activeView === 'privacy-policy' && <PrivacyPolicyPage />}
        {activeView === 'terms' && <TermsPage />}
        {activeView === 'login' && (
          <LoginPage
            logoUrl={logoUrl}
            user={user}
            authLoading={authLoading}
            onContinueAsGuest={() => setActiveView('render')}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            onLogin={handleLogin}
            onGoogleLogin={handleGoogleLogin}
            onRegister={handleRegister}
            onForgotPassword={handleForgotPassword}
            onLogout={handleLogout}
            onOpenAccount={() => setActiveView('account')}
            onOpenPrivacyPolicy={() => setActiveView('privacy-policy')}
            onOpenTerms={() => setActiveView('terms')}
          />
        )}
        {activeView === 'account' && user && (
          <AccountPage
            user={user}
            authLoading={authLoading}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            onBackWorkspace={() => setActiveView('render')}
            onLogout={handleLogout}
            onResendVerification={handleResendVerification}
            onUpdateProfile={handleUpdateProfile}
            onChangePassword={handleChangePassword}
            onLoadSessions={handleLoadSessions}
            onRevokeSession={handleRevokeSession}
            onRevokeOtherSessions={handleRevokeOtherSessions}
          />
        )}
        {activeView === 'reset-password' && (
          <ResetPasswordPage token={authToken} onResetPassword={handleResetPassword} onBackLogin={() => setActiveView('login')} />
        )}
        {activeView === 'verify-email' && (
          <VerifyEmailPage token={authToken} onVerifyEmail={handleVerifyEmail} onBackWorkspace={() => setActiveView('render')} onBackLogin={() => setActiveView('login')} />
        )}
        {activeView === 'settings' && (
          <section className="settings-page">
            <GeneralSettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onReset={resetSettings} />
          </section>
        )}
      </main>
      <footer className="app-footer">
        <div className="footer-top">
          <div className="footer-brand-block">
            <div className="footer-brand">
              <img src={logoUrl} alt="AI Math Renderer" />
              <strong>AI Math Renderer</strong>
            </div>
            <p>Biến đề bài tiếng Việt, ảnh chụp và dữ liệu tọa độ thành hình GeoGebra/Three.js để học, giảng dạy và kiểm tra lời giải trực quan.</p>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <div>
              <strong>Sản phẩm</strong>
              <FooterNavButton
                onClick={() => setActiveView('guide')}
                icon={
                  <FooterNavIcon>
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                    <path d="M8 7h8M8 11h6" />
                  </FooterNavIcon>
                }
              >
                Hướng dẫn
              </FooterNavButton>
              <FooterNavButton
                onClick={() => setActiveView('about')}
                icon={
                  <FooterNavIcon>
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4" />
                    <path d="M12 8h.01" />
                  </FooterNavIcon>
                }
              >
                About
              </FooterNavButton>
            </div>
            <div>
              <strong>Hỗ trợ</strong>
              <FooterNavButton
                onClick={() => setActiveView(user ? 'account' : 'login')}
                icon={
                  <FooterNavIcon>
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                  </FooterNavIcon>
                }
              >
                Feedback
              </FooterNavButton>
              <FooterNavButton
                onClick={() => setNotification({ id: Date.now(), kind: 'info', title: 'Báo lỗi', message: 'Kênh GitHub issue sẽ được bổ sung khi repository public.', details: [] })}
                icon={
                  <svg className="footer-nav-icon footer-nav-icon--github" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                    <path
                      fill="currentColor"
                      stroke="none"
                      d="M12 .5C5.65.5.5 5.65.5 12c0 5.1 3.29 9.43 7.86 10.96.58.11.79-.25.79-.56 0-.28-.01-1.02-.01-2.04-3.2.69-3.87-1.55-3.87-1.55-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.71.08-.71 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.72 1.26 3.38.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.74 0-1.27.45-2.31 1.2-3.12-.12-.3-.52-1.52.11-3.18 0 0 .98-.31 3.2 1.2a11.14 11.14 0 0 1 5.8 0c2.22-1.51 3.19-1.2 3.19-1.2.64 1.66.24 2.88.12 3.18.75.81 1.19 1.85 1.19 3.12 0 4.48-2.69 5.44-5.26 5.73.42.36.79 1.08.79 2.18 0 1.57-.01 2.84-.01 3.23 0 .31.21.68.8.56A10.48 10.48 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z"
                    />
                  </svg>
                }
              >
                Báo lỗi GitHub
              </FooterNavButton>
              <FooterNavMailLink
                href={`mailto:${CONTACT_EMAIL}`}
                title={CONTACT_EMAIL}
                icon={
                  <FooterNavIcon>
                    <rect x="2" y="4" width="20" height="16" rx="2" />
                    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                  </FooterNavIcon>
                }
              >
                Liên hệ
              </FooterNavMailLink>
            </div>
            <div>
              <strong>Pháp lý</strong>
              <FooterNavButton
                onClick={() => setActiveView('privacy-policy')}
                icon={
                  <FooterNavIcon>
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
                  </FooterNavIcon>
                }
              >
                Chính sách bảo mật
              </FooterNavButton>
              <FooterNavButton
                onClick={() => setActiveView('terms')}
                icon={
                  <FooterNavIcon>
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                    <path d="M10 13h4M10 17h4" />
                  </FooterNavIcon>
                }
              >
                Điều khoản sử dụng
              </FooterNavButton>
            </div>
          </nav>
        </div>
        <div className="footer-bottom">
          <span>
            © 2026 AI Math Renderer · v0.1.0 · Developed by{' '}
            <a href={DEVELOPER_GITHUB_URL} target="_blank" rel="noopener noreferrer" className="footer-developer-link">
              <strong>Sin Tran</strong>
            </a>
          </span>
        </div>
      </footer>
    </>
  );
}

function GuidePage({ onStart, onSettings }: { onStart: () => void; onSettings: () => void }) {
  const guideSteps = [
    { title: 'Nhập đề bài', text: 'Gõ đề hình học tiếng Việt, dán dữ liệu tọa độ hoặc kéo thả ảnh đề bài vào khu vực OCR.' },
    { title: 'Chọn renderer', text: 'Dùng GeoGebra cho Oxy, đồ thị hàm số; dùng Three.js cho hình học không gian hoặc mô hình 3D.' },
    { title: 'Dựng hình', text: 'AI chuyển đề bài thành scene có cấu trúc, sau đó renderer hiển thị hình để bạn kiểm tra trực quan.' },
    { title: 'Tinh chỉnh', text: 'Kéo điểm, chỉnh scene hoặc dựng lại bằng prompt rõ hơn khi hình chưa đúng ý.' },
  ];
  const promptTips = [
    'Nêu rõ hệ tọa độ: Oxy, Oxyz hoặc hình học không gian.',
    'Đặt tên điểm, đường, mặt phẳng nhất quán: A(1,2), B(4,5), mặt phẳng (P).',
    'Tách yêu cầu dựng hình và yêu cầu hiển thị nếu đề dài.',
    'Với OCR, kiểm tra lại ký hiệu toán học trước khi bấm dựng hình.',
  ];

  return (
    <section className="guide-page">
      <div className="guide-hero">
        <h2>Bắt đầu dựng hình toán học trong vài bước.</h2>
        <p>Quy trình tốt nhất là mô tả đề rõ ràng, chọn renderer phù hợp, kiểm tra scene và tinh chỉnh lại khi cần.</p>
        <div className="home-actions">
          <button type="button" onClick={onStart}>Mở workspace</button>
          <button type="button" className="secondary-button" onClick={onSettings}>Cấu hình model</button>
        </div>
      </div>

      <div className="guide-grid">
        {guideSteps.map((step, index) => (
          <article className="guide-card" key={step.title}>
            <span>0{index + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.text}</p>
          </article>
        ))}
      </div>

      <div className="guide-columns">
        <section>
          <h3>Mẹo viết prompt</h3>
          <ul>
            {promptTips.map((tip) => <li key={tip}>{tip}</li>)}
          </ul>
        </section>
        <section>
          <h3>Khi nào dùng renderer nào?</h3>
          <dl>
            <dt>GeoGebra 2D</dt>
            <dd>Bài Oxy, đồ thị hàm số, đường tròn, tam giác và quan hệ phẳng.</dd>
            <dt>GeoGebra 3D / Three.js</dt>
            <dd>Oxyz, khối đa diện, mặt phẳng, đường thẳng không gian và góc nhìn 3D.</dd>
          </dl>
        </section>
      </div>
    </section>
  );
}


function AboutPage({ onStart, onGuide }: { onStart: () => void; onGuide: () => void }) {
  const features = [
    { title: 'Xuất hình phân tích (Reasoning Model)', text: 'Luồng xử lý AI 2 tầng độc lập: Phân tích suy luận (Task 1) trước khi vẽ (Task 2) giảm thiểu hallucination, giúp tọa độ và quan hệ hình học luôn vững chắc.' },
    { title: 'Công nhận tọa độ & OCR', text: 'Hỗ trợ đọc đề bài từ ảnh (kéo thả hoặc clipboard) và giữ nguyên tọa độ người dùng nhập vào, tham chiếu dưới gốc tọa độ.' },
    { title: 'Kiểm soát & Tinh chỉnh', text: 'Không chỉ là vẽ ảnh tĩnh, AI Math Renderer sinh ra Scene JSON có cấu trúc, cho phép bạn kéo thả điểm, thêm chân đường cao và chỉnh sửa trực tiếp trên giao diện.' },
  ];

  return (
    <section className="about-page">
      <div className="about-hero">
        <h2>AI tạo hình toán học với sự kiểm soát tuyệt đối.</h2>
        <p>AI Math Renderer được xây dựng nhằm giải quyết một nỗi đau lớn trong giáo dục: <strong>Việc vẽ hình học không gian hay đồ thị quá mất thời gian</strong>. Chúng tôi tinh lọc quá trình này bằng cách kết hợp LLM, OCR và các renderer mạnh mẽ như GeoGebra, Three.js.</p>
        <div className="home-actions">
          <button type="button" onClick={onStart}>Mở workspace</button>
          <button type="button" className="secondary-button" onClick={onGuide}>Xem hướng dẫn</button>
        </div>
      </div>

      <div className="about-grid">
        {features.map((feature) => (
          <article key={feature.title}>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>

      <section className="about-section">
        <div>
          <span>Định hướng sản phẩm</span>
          <h3>Không thay thế việc học toán, mà giúp quá trình nhìn hình và kiểm tra mô hình trở nên dễ dàng hơn.</h3>
        </div>
        <p>Áp dụng phương pháp <strong>"Infrastructure as Code"</strong> cho hình học. Lời giải của bạn là chân lý, AI chỉ đóng vai trò là "trợ lý vẽ kỹ thuật". Nó giúp bạn <em>Hiển thị hệ tọa độ 3D</em> hoặc <em>Khảo sát đồ thị quỹ tích</em> một cách dễ dàng thay vì phải đánh vật với bút và giấy thước đo độ.</p>
      </section>
    </section>
  );
}


function HistoryPage({ user, items, loading, onOpen, onDelete, onLogin, onWorkspace }: { user: UserResponse | null; items: RenderHistoryItem[]; loading: boolean; onOpen: (id: string) => void; onDelete: (id: string) => void; onLogin: () => void; onWorkspace: () => void }) {
  if (!user) {
    return (
      <section className="product-page-card">
        <span className="home-eyebrow">Lịch sử cá nhân</span>
        <h2>Đăng nhập để lưu và mở lại các lần dựng hình.</h2>
        <p>Lịch sử render chỉ được lưu cho tài khoản đã đăng nhập, giúp bạn tiếp tục chỉnh hình ở các phiên sau.</p>
        <button type="button" onClick={onLogin}>Đăng nhập</button>
      </section>
    );
  }

  return (
    <section className="product-page-card">
      <div className="page-title-row">
        <div>
          <span className="home-eyebrow">Workspace history</span>
          <h2>Lịch sử dựng hình của bạn</h2>
          <p>Mở lại đề bài, scene và renderer đã lưu từ các lần render trước.</p>
        </div>
        <button type="button" onClick={onWorkspace}>Dựng hình mới</button>
      </div>
      <HistoryPanel items={items} loading={loading} onOpen={onOpen} onDelete={onDelete} />
    </section>
  );
}

function AdminConsole({ user, summary, users, renderJobs, settings, auditLogs, userQuery, userFilters, renderJobFilters, auditLogFilters, loading, onRefresh, onUserQueryChange, onUserFiltersChange, onSearchUsers, onSearchRenderJobs, onSearchAuditLogs, onUpdateUser, onToggleUserStatus, onDeleteRenderJob, onOpenRenderJobDetail, onBackToApp }: { user: UserResponse | null; summary: AdminSummaryResponse | null; users: UserResponse[]; renderJobs: AdminRenderHistoryItem[]; settings: SystemSettingResponse[]; auditLogs: AuditLogResponse[]; userQuery: string; userFilters: AdminUserFilters; renderJobFilters: AdminRenderJobFilters; auditLogFilters: AdminAuditLogFilters; loading: boolean; onRefresh: () => void; onUserQueryChange: (query: string) => void; onUserFiltersChange: (filters: AdminUserFilters) => void; onSearchUsers: (query: string, filters?: AdminUserFilters) => Promise<void>; onSearchRenderJobs: (filters: AdminRenderJobFilters) => Promise<void>; onSearchAuditLogs: (filters: AdminAuditLogFilters) => Promise<void>; onUpdateUser: (user: UserResponse, patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>>) => Promise<void>; onToggleUserStatus: (user: UserResponse) => Promise<void>; onDeleteRenderJob: (id: string) => void; onOpenRenderJobDetail: (detail: AdminRenderHistoryDetail) => void; onBackToApp: () => void }) {
  const [activeSection, setActiveSection] = useState<'overview' | 'users' | 'renders' | 'models' | 'settings' | 'audit'>('overview');
  const [savingAiSettings, setSavingAiSettings] = useState(false);
  const [searchingUsers, setSearchingUsers] = useState(false);
  const [filteringRenderJobs, setFilteringRenderJobs] = useState(false);
  const [filteringAuditLogs, setFilteringAuditLogs] = useState(false);
  const [localRenderJobFilters, setLocalRenderJobFilters] = useState<AdminRenderJobFilters>(renderJobFilters);
  const [localAuditLogFilters, setLocalAuditLogFilters] = useState<AdminAuditLogFilters>(auditLogFilters);
  const [selectedJobDetail, setSelectedJobDetail] = useState<AdminRenderHistoryDetail | null>(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [jobDetailError, setJobDetailError] = useState('');
  const aiSettings = settings.find((item) => item.key === 'ai_settings')?.value ?? {};
  const providerStats = summarizeRenderJobs(renderJobs);

  async function saveAiSettingsPatch(patch: Record<string, unknown>) {
    setSavingAiSettings(true);
    try {
      await saveAdminSystemSetting('ai_settings', { ...defaultAdminAiSettings(), ...aiSettings, ...patch });
      onRefresh();
    } finally {
      setSavingAiSettings(false);
    }
  }

  async function submitUserSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearchingUsers(true);
    try {
      await onSearchUsers(userQuery, userFilters);
    } finally {
      setSearchingUsers(false);
    }
  }

  async function submitRenderJobFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilteringRenderJobs(true);
    try {
      await onSearchRenderJobs(localRenderJobFilters);
    } finally {
      setFilteringRenderJobs(false);
    }
  }

  async function submitAuditLogFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilteringAuditLogs(true);
    try {
      await onSearchAuditLogs(localAuditLogFilters);
    } finally {
      setFilteringAuditLogs(false);
    }
  }

  function updateUserFilter(key: keyof AdminUserFilters, value: string) {
    const next = { ...userFilters, [key]: value };
    onUserFiltersChange(next);
    void onSearchUsers(userQuery, next);
  }

  async function inspectRenderJob(id: string) {
    setJobDetailLoading(true);
    setJobDetailError('');
    try {
      setSelectedJobDetail(await getAdminRenderJobDetail(id));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể tải chi tiết render job.');
      setJobDetailError(apiError.message);
    } finally {
      setJobDetailLoading(false);
    }
  }

  if (user?.role !== 'admin') {
    return (
      <section className="admin-dashboard public-denied">
        <div className="product-page-card">
          <span className="home-eyebrow">Admin Dashboard</span>
          <h2>Bạn không có quyền truy cập trang quản trị.</h2>
          <p>Trang này chỉ dành cho tài khoản admin đang hoạt động.</p>
          <button type="button" onClick={onBackToApp}>Quay lại trang chính</button>
        </div>
      </section>
    );
  }

  return (
    <section className="admin-dashboard">
      <aside className="admin-sidebar">
        <div className="admin-brand"><span>H</span><div><strong>Hinh Admin</strong><small>Project Control Center</small></div></div>
        <nav className="admin-sidebar-nav">
          <AdminNavButton active={activeSection === 'overview'} onClick={() => setActiveSection('overview')} label="Tổng quan" />
          <AdminNavButton active={activeSection === 'users'} onClick={() => setActiveSection('users')} label="Người dùng" />
          <AdminNavButton active={activeSection === 'renders'} onClick={() => setActiveSection('renders')} label="Render jobs" />
          <AdminNavButton active={activeSection === 'models'} onClick={() => setActiveSection('models')} label="Model & AI" />
          <AdminNavButton active={activeSection === 'settings'} onClick={() => setActiveSection('settings')} label="Cài đặt DB" />
          <AdminNavButton active={activeSection === 'audit'} onClick={() => setActiveSection('audit')} label="Audit logs" />
        </nav>
        <div className="admin-sidebar-footer"><small>{user.email}</small><button type="button" className="secondary-button" onClick={onBackToApp}>Trang người dùng</button></div>
      </aside>

      <main className="admin-main">
        <header className="admin-topbar">
          <div><span className="home-eyebrow">Admin Dashboard</span><h2>Quản lý dự án AI Math Renderer</h2><p>Dashboard riêng cho admin: vận hành, phân tích, người dùng, model, cài đặt và audit.</p></div>
          <button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? 'Đang tải...' : 'Làm mới dữ liệu'}</button>
        </header>

        {activeSection === 'overview' && (
          <div className="admin-section-stack">
            <div className="admin-metric-grid">
              <MetricCard label="Người dùng" value={summary?.users ?? 0} />
              <MetricCard label="Đang hoạt động" value={summary?.active_users ?? 0} />
              <MetricCard label="Admin" value={summary?.admins ?? 0} />
              <MetricCard label="Render jobs" value={summary?.render_jobs ?? 0} />
              <MetricCard label="Render hôm nay" value={summary?.render_jobs_today ?? 0} />
              <MetricCard label="User mới hôm nay" value={summary?.users_today ?? 0} />
              <MetricCard label="Job cảnh báo AI" value={summary?.ai_warning_jobs ?? 0} />
              <MetricCard label="Tỉ lệ cảnh báo AI" value={summary?.ai_warning_rate ?? 0} suffix="%" />
            </div>
            <div className="admin-grid">
              <section className="admin-panel"><h3>Phân tích provider/model</h3><div className="admin-table">{providerStats.map((item) => <article className="admin-row" key={item.key}><div><strong>{item.key}</strong><span>{item.count} render jobs</span></div></article>)}{providerStats.length === 0 && <p className="field-hint">Chưa có dữ liệu render để phân tích.</p>}</div></section>
              <section className="admin-panel"><h3>Tình trạng cấu hình</h3><div className="admin-table"><article className="admin-row"><div><strong>ai_settings</strong><span>{settings.some((item) => item.key === 'ai_settings') ? 'Đã lưu trong database' : 'Chưa cấu hình trong database'}</span></div></article><article className="admin-row"><div><strong>Audit</strong><span>{auditLogs.length} sự kiện gần nhất</span></div></article></div></section>
            </div>
          </div>
        )}

        {activeSection === 'users' && (
          <section className="admin-panel admin-panel-full">
            <h3>Quản lý người dùng</h3>
            <form className="admin-toolbar" onSubmit={submitUserSearch}>
              <input value={userQuery} onChange={(event) => onUserQueryChange(event.target.value)} placeholder="Tìm email, tên hiển thị hoặc ID" />
              <select value={userFilters.role ?? ''} onChange={(event) => updateUserFilter('role', event.target.value)}><option value="">Role</option><option value="user">user</option><option value="admin">admin</option></select>
              <select value={userFilters.status ?? ''} onChange={(event) => updateUserFilter('status', event.target.value)}><option value="">Status</option><option value="active">active</option><option value="disabled">disabled</option></select>
              <input value={userFilters.plan ?? ''} onChange={(event) => updateUserFilter('plan', event.target.value)} placeholder="Plan" />
              <button type="submit" className="secondary-button" disabled={searchingUsers}>{searchingUsers ? 'Đang tìm...' : 'Tìm user'}</button>
              <button type="button" className="secondary-button" onClick={() => { onUserQueryChange(''); onUserFiltersChange({}); void onSearchUsers('', {}); }}>Xoá lọc</button>
            </form>
            <div className="admin-table">
              {users.map((item) => <AdminUserRow key={item.id} item={item} currentUserId={user.id} onUpdate={onUpdateUser} onToggleStatus={onToggleUserStatus} />)}
              {users.length === 0 && <p className="field-hint">Không tìm thấy người dùng phù hợp.</p>}
            </div>
          </section>
        )}

        {activeSection === 'renders' && (
          <section className="admin-panel admin-panel-full">
            <h3>Quản lý render jobs</h3>
            <form className="admin-toolbar admin-filter-grid" onSubmit={submitRenderJobFilters}>
              <input value={localRenderJobFilters.q ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, q: event.target.value }))} placeholder="Tìm đề bài hoặc ID" />
              <input value={localRenderJobFilters.provider ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, provider: event.target.value }))} placeholder="Provider" />
              <input value={localRenderJobFilters.model ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, model: event.target.value }))} placeholder="Model" />
              <input value={localRenderJobFilters.renderer ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, renderer: event.target.value }))} placeholder="Renderer" />
              <input value={localRenderJobFilters.source_type ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, source_type: event.target.value }))} placeholder="Source" />
              <input value={localRenderJobFilters.user_id ?? ''} onChange={(event) => setLocalRenderJobFilters((current) => ({ ...current, user_id: event.target.value }))} placeholder="User ID" />
              <button type="submit" className="secondary-button" disabled={filteringRenderJobs}>{filteringRenderJobs ? 'Đang lọc...' : 'Lọc jobs'}</button>
              <button type="button" className="secondary-button" onClick={() => { setLocalRenderJobFilters({}); void onSearchRenderJobs({}); }}>Xoá lọc</button>
            </form>
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
        )}

        {activeSection === 'models' && (
          <section className="admin-panel admin-panel-full">
            <h3>Model & AI management</h3>
            <p className="field-hint">Admin quản lý provider, model mặc định, allowlist, OCR và routing AI.</p>
            <AdminAiSettingsForm value={aiSettings} saving={savingAiSettings} onSave={saveAiSettingsPatch} />
          </section>
        )}

        {activeSection === 'settings' && (
          <section className="admin-panel admin-panel-full">
            <h3>Cài đặt lưu trong cơ sở dữ liệu</h3>
            <p className="field-hint">Các cấu hình non-secret được lưu trong bảng system_settings; API key vẫn nằm trong secret/env deploy.</p>
            <AdminPlanSettingsForm value={settings.find((item) => item.key === 'plan_settings')?.value ?? {}} onSave={async (value) => { await saveAdminSystemSetting('plan_settings', value); onRefresh(); }} />
            <AdminFeatureFlagsForm value={settings.find((item) => item.key === 'feature_flags')?.value ?? {}} onSave={async (value) => { await saveAdminSystemSetting('feature_flags', value); onRefresh(); }} />
            <AdminAiProfilesForm value={settings.find((item) => item.key === 'ai_profiles')?.value ?? {}} onSave={async (value) => { await saveAdminSystemSetting('ai_profiles', value); onRefresh(); }} />
            <div className="admin-table">
              {settings.map((item) => <AdminSystemSettingRow key={item.key} item={item} />)}
              {settings.length === 0 && <p className="field-hint">Chưa có cấu hình hệ thống.</p>}
            </div>
          </section>
        )}

        {activeSection === 'audit' && (
          <section className="admin-panel admin-panel-full">
            <h3>Audit logs</h3>
            <form className="admin-toolbar admin-filter-grid" onSubmit={submitAuditLogFilters}>
              <input value={localAuditLogFilters.action ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action" />
              <input value={localAuditLogFilters.actor_user_id ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, actor_user_id: event.target.value }))} placeholder="Actor user ID" />
              <input value={localAuditLogFilters.target_type ?? ''} onChange={(event) => setLocalAuditLogFilters((current) => ({ ...current, target_type: event.target.value }))} placeholder="Target type" />
              <button type="submit" className="secondary-button" disabled={filteringAuditLogs}>{filteringAuditLogs ? 'Đang lọc...' : 'Lọc audit'}</button>
              <button type="button" className="secondary-button" onClick={() => { setLocalAuditLogFilters({}); void onSearchAuditLogs({}); }}>Xoá lọc</button>
            </form>
            <div className="admin-table">
              {auditLogs.map((log) => <AdminAuditLogRow key={log.id} log={log} />)}
              {auditLogs.length === 0 && <p className="field-hint">Chưa có audit log.</p>}
            </div>
          </section>
        )}
      </main>
    </section>
  );
}

function AdminNavButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <button type="button" className={active ? 'active' : ''} onClick={onClick}>{label}</button>;
}

function AdminUserRow({ item, currentUserId, onUpdate, onToggleStatus }: { item: UserResponse; currentUserId: string; onUpdate: (user: UserResponse, patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>>) => Promise<void>; onToggleStatus: (user: UserResponse) => Promise<void> }) {
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
    } finally {
      setSessionsLoading(false);
    }
  }

  async function revokeSession(sessionId: string) {
    await revokeAdminUserSession(item.id, sessionId);
    await loadSessions();
  }

  async function revokeAllSessions() {
    await revokeAllAdminUserSessions(item.id);
    await loadSessions();
  }

  async function save() {
    const patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>> = {};
    const nextDisplayName = displayName.trim() || null;
    const nextPlan = plan.trim() || 'free';
    if (nextDisplayName !== (item.display_name ?? null)) patch.display_name = nextDisplayName;
    if (!isSelf && role !== item.role) patch.role = role;
    if (!isSelf && status !== item.status) patch.status = status;
    if (nextPlan !== item.plan) patch.plan = nextPlan;
    if (Object.keys(patch).length === 0) return;

    setSaving(true);
    try {
      await onUpdate(item, patch);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="admin-row admin-row-editable">
      <div>
        <strong>{item.display_name || item.email}</strong>
        <span>{item.email} · {item.role} · {item.status} · {item.plan}</span>
        {isSelf && <span>Đang đăng nhập: khoá sửa role/status để tránh tự mất quyền.</span>}
      </div>
      <div className="admin-inline-form">
        <label className="field-label">Tên hiển thị<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
        <label className="field-label">Role<select value={role} onChange={(event) => setRole(event.target.value as UserResponse['role'])} disabled={isSelf}><option value="user">user</option><option value="admin">admin</option></select></label>
        <label className="field-label">Status<select value={status} onChange={(event) => setStatus(event.target.value as UserResponse['status'])} disabled={isSelf}><option value="active">active</option><option value="disabled">disabled</option></select></label>
        <label className="field-label">Plan<input value={plan} onChange={(event) => setPlan(event.target.value)} /></label>
      </div>
      <div className="admin-row-actions">
        <button type="button" className="secondary-button" onClick={save} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu'}</button>
        <button type="button" className="secondary-button" onClick={() => void onToggleStatus(item)} disabled={isSelf || saving}>{item.status === 'active' ? 'Vô hiệu hoá' : 'Kích hoạt'}</button>
        <button type="button" className="secondary-button" onClick={() => (sessionsOpen ? setSessionsOpen(false) : void loadSessions())} disabled={sessionsLoading}>{sessionsLoading ? 'Đang tải...' : 'Phiên đăng nhập'}</button>
      </div>
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
    </article>
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
        <span><strong>Source</strong>{detail.source_type}</span>
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

function AdminAuditLogRow({ log }: { log: AuditLogResponse }) {
  return (
    <article className="admin-row admin-row-block">
      <div><strong>{log.action}</strong><span>{formatHistoryDate(log.created_at)} · {log.actor_user_id || 'system'} · {log.target_type}{log.target_id ? `/${log.target_id}` : ''}</span></div>
      {hasObjectKeys(log.metadata) && <AdminDetails title="Metadata" value={log.metadata} />}
    </article>
  );
}

function AdminDetails({ title, value }: { title: string; value: unknown }) {
  return <details className="admin-details"><summary>{title}</summary><AdminJsonBlock value={value} /></details>;
}

function AdminJsonBlock({ value }: { value: unknown }) {
  return <pre className="admin-json-block">{JSON.stringify(value ?? null, null, 2)}</pre>;
}

function hasObjectKeys(value: Record<string, unknown>) {
  return Object.keys(value).length > 0;
}

function summarizeRenderJobs(renderJobs: AdminRenderHistoryItem[]) {
  const counts = new Map<string, number>();
  renderJobs.forEach((job) => {
    const key = `${job.provider || 'auto'} / ${job.model || 'default'}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return [...counts.entries()].map(([key, count]) => ({ key, count })).sort((left, right) => right.count - left.count).slice(0, 8);
}

function AdminAiSettingsForm({ value, saving, onSave }: { value: Record<string, unknown>; saving: boolean; onSave: (patch: Record<string, unknown>) => Promise<void> }) {
  const [provider, setProvider] = useState<'openrouter' | 'nvidia' | 'ollama' | 'router9'>('router9');
  const providerValue = getAdminProviderSettings(value, provider);
  const ocrValue = getAdminOcrSettings(value);
  const [defaultProvider, setDefaultProvider] = useState(getStringValue(value.default_provider, 'auto'));
  const [baseUrl, setBaseUrl] = useState(providerValue.base_url);
  const [model, setModel] = useState(providerValue.model);
  const [allowed, setAllowed] = useState(providerValue.allowed_model_ids.join('\n'));
  const [router9OnlyMode, setRouter9OnlyMode] = useState(providerValue.only_mode);
  const [ocrProvider, setOcrProvider] = useState(ocrValue.provider);
  const [ocrModel, setOcrModel] = useState(ocrValue.model);
  const [ocrMaxImageMb, setOcrMaxImageMb] = useState(String(ocrValue.max_image_mb));
  const [openrouterReferer, setOpenrouterReferer] = useState(getStringValue(value.openrouter_http_referer, ''));
  const [openrouterTitle, setOpenrouterTitle] = useState(getStringValue(value.openrouter_x_title, ''));
  const [openrouterReasoning, setOpenrouterReasoning] = useState(value.openrouter_reasoning_enabled === true);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    const next = getAdminProviderSettings(value, provider);
    setBaseUrl(next.base_url);
    setModel(next.model);
    setAllowed(next.allowed_model_ids.join('\n'));
    setRouter9OnlyMode(next.only_mode);
  }, [provider, value]);

  useEffect(() => {
    const nextOcr = getAdminOcrSettings(value);
    setDefaultProvider(getStringValue(value.default_provider, 'auto'));
    setOcrProvider(nextOcr.provider);
    setOcrModel(nextOcr.model);
    setOcrMaxImageMb(String(nextOcr.max_image_mb));
    setOpenrouterReferer(getStringValue(value.openrouter_http_referer, ''));
    setOpenrouterTitle(getStringValue(value.openrouter_x_title, ''));
    setOpenrouterReasoning(value.openrouter_reasoning_enabled === true);
  }, [value]);

  async function saveGlobalRouting() {
    await onSave({ default_provider: defaultProvider });
  }

  async function saveProvider() {
    const current = getAdminProviderSettings(value, provider);
    await onSave({
      [provider]: {
        ...current,
        base_url: baseUrl.trim(),
        model: model.trim(),
        allowed_model_ids: parseLines(allowed),
        ...(provider === 'router9' ? { only_mode: router9OnlyMode } : {}),
      },
    });
  }

  async function saveOcr() {
    await onSave({
      ocr: {
        provider: ocrProvider,
        model: ocrModel.trim(),
        max_image_mb: clamp(Number(ocrMaxImageMb) || 8, 1, 32),
      },
    });
  }

  async function scanModels() {
    setScanning(true);
    try {
      const runtime = adminSettingsToRuntime(value);
      const models = provider === 'router9' ? await scanRouter9Models(runtime) : await scanProviderModels(provider, runtime);
      await onSave({
        [provider]: {
          ...getAdminProviderSettings(value, provider),
          scanned_models: models,
          last_scanned_at: new Date().toISOString(),
        },
      });
    } finally {
      setScanning(false);
    }
  }

  async function saveOpenRouter() {
    await onSave({
      openrouter_http_referer: openrouterReferer.trim(),
      openrouter_x_title: openrouterTitle.trim(),
      openrouter_reasoning_enabled: openrouterReasoning,
    });
  }

  return (
    <div className="admin-ai-settings">
      <section className="admin-settings-section">
        <h4>Routing mặc định</h4>
        <div className="admin-field-grid">
          <label className="field-label">Default provider<select value={defaultProvider} onChange={(event) => setDefaultProvider(event.target.value)}><option value="auto">auto</option><option value="openrouter">OpenRouter</option><option value="nvidia">NVIDIA</option><option value="ollama">Ollama</option><option value="router9">9router</option></select></label>
        </div>
        <button type="button" className="secondary-button" onClick={saveGlobalRouting} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu routing'}</button>
      </section>

      <section className="admin-settings-section">
        <h4>Provider model</h4>
        <div className="admin-field-grid">
          <label className="field-label">Provider<select value={provider} onChange={(event) => setProvider(event.target.value as typeof provider)}><option value="openrouter">OpenRouter</option><option value="nvidia">NVIDIA</option><option value="ollama">Ollama</option><option value="router9">9router</option></select></label>
          <label className="field-label">Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://..." /></label>
          <label className="field-label">Model mặc định<input value={model} onChange={(event) => setModel(event.target.value)} placeholder="vd: codex-5.5" /></label>
          {provider === 'router9' && <label className="checkbox-label"><input type="checkbox" checked={router9OnlyMode} onChange={(event) => setRouter9OnlyMode(event.target.checked)} /> Chỉ dùng 9router</label>}
        </div>
        <label className="field-label">Allowlist model hiển thị cho user<textarea value={allowed} onChange={(event) => setAllowed(event.target.value)} rows={6} placeholder="Mỗi dòng một model id" /></label>
        <div className="admin-field-grid">
          <span><strong>Scanned models</strong>{providerValue.scanned_models.length} model</span>
          <span><strong>Last scan</strong>{providerValue.last_scanned_at || 'Chưa scan'}</span>
        </div>
        {providerValue.scanned_models.length > 0 && <AdminDetails title="Scanned model JSON" value={providerValue.scanned_models} />}
        <div className="admin-row-actions"><button type="button" className="secondary-button" onClick={scanModels} disabled={saving || scanning}>{scanning ? 'Đang scan...' : 'Scan models'}</button><button type="button" className="secondary-button" onClick={saveProvider} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu provider'}</button></div>
      </section>

      <section className="admin-settings-section">
        <h4>OCR</h4>
        <div className="admin-field-grid">
          <label className="field-label">OCR provider<select value={ocrProvider} onChange={(event) => setOcrProvider(event.target.value)}><option value="openrouter">OpenRouter</option><option value="router9">9router</option></select></label>
          <label className="field-label">OCR model<input value={ocrModel} onChange={(event) => setOcrModel(event.target.value)} /></label>
          <label className="field-label">Max image MB<input type="number" min="1" max="32" value={ocrMaxImageMb} onChange={(event) => setOcrMaxImageMb(event.target.value)} /></label>
        </div>
        <button type="button" className="secondary-button" onClick={saveOcr} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu OCR'}</button>
      </section>

      <section className="admin-settings-section">
        <h4>OpenRouter metadata</h4>
        <div className="admin-field-grid">
          <label className="field-label">HTTP Referer<input value={openrouterReferer} onChange={(event) => setOpenrouterReferer(event.target.value)} /></label>
          <label className="field-label">X-Title<input value={openrouterTitle} onChange={(event) => setOpenrouterTitle(event.target.value)} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={openrouterReasoning} onChange={(event) => setOpenrouterReasoning(event.target.checked)} /> Bật reasoning</label>
        </div>
        <button type="button" className="secondary-button" onClick={saveOpenRouter} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu OpenRouter'}</button>
      </section>
    </div>
  );
}

function AdminPlanSettingsForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const plansValue = value.plans && typeof value.plans === 'object' ? value.plans as Record<string, unknown> : {};
  const free = getPlanQuota(plansValue.free);
  const pro = getPlanQuota(plansValue.pro);
  const [freeRender, setFreeRender] = useState(String(free.daily_render_limit ?? ''));
  const [freeOcr, setFreeOcr] = useState(String(free.daily_ocr_limit ?? ''));
  const [proRender, setProRender] = useState(String(pro.daily_render_limit ?? ''));
  const [proOcr, setProOcr] = useState(String(pro.daily_ocr_limit ?? ''));
  return (
    <section className="admin-settings-section"><h4>Plan quota</h4><div className="admin-field-grid">
      <label className="field-label">Free render/ngày<input type="number" value={freeRender} onChange={(event) => setFreeRender(event.target.value)} /></label>
      <label className="field-label">Free OCR/ngày<input type="number" value={freeOcr} onChange={(event) => setFreeOcr(event.target.value)} /></label>
      <label className="field-label">Pro render/ngày<input type="number" value={proRender} onChange={(event) => setProRender(event.target.value)} /></label>
      <label className="field-label">Pro OCR/ngày<input type="number" value={proOcr} onChange={(event) => setProOcr(event.target.value)} /></label>
    </div><button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, plans: { free: { daily_render_limit: optionalNumber(freeRender), daily_ocr_limit: optionalNumber(freeOcr) }, pro: { daily_render_limit: optionalNumber(proRender), daily_ocr_limit: optionalNumber(proOcr) } } })}>Lưu quota</button></section>
  );
}

function AdminFeatureFlagsForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const [maintenanceMode, setMaintenanceMode] = useState(value.maintenance_mode === true);
  const [message, setMessage] = useState(getStringValue(value.maintenance_message, 'Hệ thống đang bảo trì. Vui lòng thử lại sau.'));
  const [googleOAuth, setGoogleOAuth] = useState(value.google_oauth_enabled !== false);
  const [ocr, setOcr] = useState(value.ocr_enabled !== false);
  const [render, setRender] = useState(value.render_enabled !== false);
  return (
    <section className="admin-settings-section"><h4>Feature flags</h4><div className="admin-field-grid">
      <label className="checkbox-label"><input type="checkbox" checked={maintenanceMode} onChange={(event) => setMaintenanceMode(event.target.checked)} /> Maintenance mode</label>
      <label className="checkbox-label"><input type="checkbox" checked={render} onChange={(event) => setRender(event.target.checked)} /> Render enabled</label>
      <label className="checkbox-label"><input type="checkbox" checked={ocr} onChange={(event) => setOcr(event.target.checked)} /> OCR enabled</label>
      <label className="checkbox-label"><input type="checkbox" checked={googleOAuth} onChange={(event) => setGoogleOAuth(event.target.checked)} /> Google OAuth enabled</label>
    </div><label className="field-label">Maintenance message<input value={message} onChange={(event) => setMessage(event.target.value)} /></label><button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, maintenance_mode: maintenanceMode, maintenance_message: message, google_oauth_enabled: googleOAuth, ocr_enabled: ocr, render_enabled: render })}>Lưu flags</button></section>
  );
}

function AdminAiProfilesForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const geometry = getAiTaskProfile(value.geometry_reasoning);
  const ocr = getAiTaskProfile(value.ocr);
  const [geometryProvider, setGeometryProvider] = useState(geometry.provider);
  const [geometryModel, setGeometryModel] = useState(geometry.model);
  const [geometryFallbacks, setGeometryFallbacks] = useState(geometry.fallbacks.join('\n'));
  const [ocrProvider, setOcrProvider] = useState(ocr.provider);
  const [ocrModel, setOcrModel] = useState(ocr.model);
  const [ocrFallbacks, setOcrFallbacks] = useState(ocr.fallbacks.join('\n'));
  return (
    <section className="admin-settings-section"><h4>AI profiles</h4><div className="admin-field-grid">
      <label className="field-label">Geometry provider<input value={geometryProvider} onChange={(event) => setGeometryProvider(event.target.value)} /></label>
      <label className="field-label">Geometry model<input value={geometryModel} onChange={(event) => setGeometryModel(event.target.value)} /></label>
      <label className="field-label">OCR provider<input value={ocrProvider} onChange={(event) => setOcrProvider(event.target.value)} /></label>
      <label className="field-label">OCR model<input value={ocrModel} onChange={(event) => setOcrModel(event.target.value)} /></label>
    </div><label className="field-label">Geometry fallbacks<textarea rows={3} value={geometryFallbacks} onChange={(event) => setGeometryFallbacks(event.target.value)} /></label><label className="field-label">OCR fallbacks<textarea rows={3} value={ocrFallbacks} onChange={(event) => setOcrFallbacks(event.target.value)} /></label><button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, geometry_reasoning: { provider: geometryProvider, model: geometryModel, fallbacks: parseLines(geometryFallbacks) }, ocr: { provider: ocrProvider, model: ocrModel, fallbacks: parseLines(ocrFallbacks) } })}>Lưu AI profiles</button></section>
  );
}

function defaultAdminAiSettings() {
  return {
    version: 1,
    default_provider: 'auto',
    openrouter: defaultAdminProviderSettings(),
    nvidia: defaultAdminProviderSettings(),
    ollama: defaultAdminProviderSettings(),
    router9: { ...defaultAdminProviderSettings(), only_mode: false },
    ocr: { provider: 'openrouter', model: '', max_image_mb: 8 },
    openrouter_http_referer: '',
    openrouter_x_title: '',
    openrouter_reasoning_enabled: false,
  };
}

function defaultAdminProviderSettings() {
  return { base_url: '', model: '', scanned_models: [] as unknown[], allowed_model_ids: [] as string[], last_scanned_at: '', only_mode: false };
}

function getAdminProviderSettings(value: Record<string, unknown>, provider: 'openrouter' | 'nvidia' | 'ollama' | 'router9') {
  const item = value[provider];
  if (!item || typeof item !== 'object') return defaultAdminProviderSettings();
  const data = item as Record<string, unknown>;
  return {
    ...defaultAdminProviderSettings(),
    ...data,
    base_url: typeof data.base_url === 'string' ? data.base_url : '',
    model: typeof data.model === 'string' ? data.model : '',
    scanned_models: Array.isArray(data.scanned_models) ? data.scanned_models : [],
    allowed_model_ids: Array.isArray(data.allowed_model_ids) ? data.allowed_model_ids.map(String) : [],
    last_scanned_at: typeof data.last_scanned_at === 'string' ? data.last_scanned_at : '',
    only_mode: data.only_mode === true,
  };
}

function adminSettingsToRuntime(value: Record<string, unknown>): RuntimeSettings {
  const router9 = getAdminProviderSettings(value, 'router9');
  return {
    ...defaultRuntimeSettings,
    default_provider: getStringValue(value.default_provider, 'auto'),
    openrouter: { ...defaultRuntimeSettings.openrouter, ...getAdminProviderSettings(value, 'openrouter') },
    nvidia: { ...defaultRuntimeSettings.nvidia, ...getAdminProviderSettings(value, 'nvidia') },
    ollama: { ...defaultRuntimeSettings.ollama, ...getAdminProviderSettings(value, 'ollama') },
    router9: { ...defaultRuntimeSettings.router9, ...router9 },
    ocr: { ...defaultRuntimeSettings.ocr, ...getAdminOcrSettings(value), provider: getAdminOcrSettings(value).provider as OcrProvider },
    openrouter_http_referer: getStringValue(value.openrouter_http_referer, ''),
    openrouter_x_title: getStringValue(value.openrouter_x_title, ''),
    openrouter_reasoning_enabled: value.openrouter_reasoning_enabled === true,
  };
}

function getPlanQuota(value: unknown) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    daily_render_limit: typeof data.daily_render_limit === 'number' ? data.daily_render_limit : null,
    daily_ocr_limit: typeof data.daily_ocr_limit === 'number' ? data.daily_ocr_limit : null,
  };
}

function getAiTaskProfile(value: unknown) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    provider: getStringValue(data.provider, 'auto'),
    model: getStringValue(data.model, ''),
    fallbacks: Array.isArray(data.fallbacks) ? data.fallbacks.map(String) : [],
  };
}

function optionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return Math.max(0, Number(trimmed) || 0);
}

function getAdminOcrSettings(value: Record<string, unknown>) {
  const item = value.ocr;
  const data = item && typeof item === 'object' ? item as Record<string, unknown> : {};
  const maxImageMb = typeof data.max_image_mb === 'number' ? data.max_image_mb : 8;
  return {
    provider: getStringValue(data.provider, 'openrouter'),
    model: getStringValue(data.model, ''),
    max_image_mb: clamp(maxImageMb, 1, 32),
  };
}

function getStringValue(value: unknown, fallback: string) {
  return typeof value === 'string' ? value : fallback;
}

function parseLines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean);
}

function MetricCard({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <article className="admin-metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString('vi-VN')}{suffix}</strong>
    </article>
  );
}

function HistoryPanel({ items, loading, onOpen, onDelete }: { items: RenderHistoryItem[]; loading: boolean; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  return (
    <section className="history-panel">
      <div className="history-panel-header">
        <strong>Lịch sử dựng hình</strong>
        <span>{loading ? 'Đang tải...' : `${items.length} mục`}</span>
      </div>
      {items.length === 0 ? (
        <p>Render mới sau khi đăng nhập sẽ được lưu vào database.</p>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-item" key={item.id}>
              <button type="button" onClick={() => onOpen(item.id)}>
                <strong>{item.problem_text}</strong>
                <span>{formatHistoryDate(item.created_at)} · {historySourceLabel(item.source_type)}{item.renderer ? ` · ${item.renderer}` : ''}{item.model ? ` · ${item.model}` : ''}</span>
              </button>
              <button type="button" className="history-delete" onClick={() => onDelete(item.id)} aria-label="Xoá lịch sử">×</button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatHistoryDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}

function historySourceLabel(sourceType: string) {
  if (sourceType === 'scene_edit') return 'chỉnh hình';
  if (sourceType === 'ocr') return 'OCR';
  return 'đề bài';
}

function MobileRendererWarning({ dismissed, onDismiss }: { dismissed: boolean; onDismiss: () => void }) {
  if (dismissed) return null;
  return (
    <div className="mobile-renderer-warning" role="dialog" aria-modal="true" aria-labelledby="mobile-renderer-warning-title">
      <section className="mobile-renderer-warning-card">
        <h2 id="mobile-renderer-warning-title">Lưu ý khi dùng điện thoại</h2>
        <p>Math renderer chỉ hiển thị tốt trên các thiết bị desktop. Trên di động, màn hình render nằm bên dưới phần nhập đề.</p>
        <p>Hãy lướt xuống sau khi dựng hình để xem kết quả.</p>
        <button type="button" className="primary-button" onClick={onDismiss}>Bỏ qua và tiếp tục</button>
      </section>
    </div>
  );
}

function NotificationBanner({ notification, onDismiss }: { notification: Notification | null; onDismiss: () => void }) {
  if (!notification) return null;
  return (
    <div className="notification-stack" role="alert" aria-live="assertive">
      <section className={`notification-card ${notification.kind}`}>
        <div className="notification-header">
          <strong>{notification.title}</strong>
          <button type="button" className="notification-close" onClick={onDismiss} aria-label="Đóng thông báo">×</button>
        </div>
        <p>{notification.message}</p>
        {notification.details.length > 0 && (
          <details className="notification-details">
            <summary>Chi tiết fallback</summary>
            <ul>
              {notification.details.map((detail) => <li key={detail}>{detail}</li>)}
            </ul>
          </details>
        )}
      </section>
    </div>
  );
}

function toApiError(caught: unknown, fallback: string): ApiError {
  if (caught instanceof ApiError) return caught;
  if (caught instanceof Error) return new ApiError(caught.message || fallback);
  return new ApiError(fallback);
}

function friendlyMessage(message: string) {
  const text = message.trim();
  if (!text) return 'Có lỗi xảy ra. Hãy thử lại hoặc đổi cấu hình model.';
  if (/quota|rate limit|429/i.test(text)) return 'Model hoặc tài khoản đang bị giới hạn lượt gọi. Hãy chờ một lúc hoặc chọn model/provider khác.';
  if (/api key|unauthorized|401|403|forbidden/i.test(text)) return 'Provider chưa được cấu hình đúng hoặc API key không có quyền dùng model này.';
  if (/model.*not found|not found|404/i.test(text)) return 'Model đã chọn không khả dụng. Hãy quét lại danh sách model hoặc chọn model khác.';
  if (/timeout|timed out/i.test(text)) return 'Provider phản hồi quá lâu. Hãy thử lại hoặc đổi model nhẹ hơn.';
  if (/validation|field required|Input should/i.test(text)) return 'Dữ liệu hình chưa hợp lệ. Hãy thử dựng lại hoặc chỉnh hình đơn giản hơn.';
  return text.length > 220 ? `${text.slice(0, 217)}...` : text;
}

function friendlyDetails(details: string[]) {
  if (details.length === 0) return [];
  return details.map((detail) => friendlyDetail(detail)).filter(Boolean).slice(0, 6);
}

function friendlyDetail(detail: string) {
  const text = detail.trim();
  if (!text) return '';
  if (/mock extractor/i.test(text)) return 'AI provider hiện không sẵn sàng nên hệ thống dùng hình mẫu dự phòng.';
  if (/Đã thử:|provider|router9|openrouter|nvidia|ollama/i.test(text)) return text.replace(/RuntimeError:|Error:/g, '').slice(0, 240);
  if (/api key|unauthorized|401|403|forbidden/i.test(text)) return 'Kiểm tra API key hoặc quyền truy cập model trong phần Settings.';
  if (/quota|rate limit|429/i.test(text)) return 'Provider đang giới hạn lượt gọi; thử model/provider khác hoặc chờ quota hồi lại.';
  if (/not found|404/i.test(text)) return 'Model không còn khả dụng; hãy quét lại danh sách model.';
  return text.length > 240 ? `${text.slice(0, 237)}...` : text;
}

function mergeBackendDefaults(current: RuntimeSettings, defaults: SettingsDefaults): RuntimeSettings {
  const router9Allowed = mergeUnique(current.router9.allowed_model_ids, [defaults.router9.model ?? '', ...defaults.router9.allowed_model_ids]);
  const router9Model = current.router9.model || defaults.router9.model || router9Allowed[0] || '';
  const router9Scanned = mergeScannedModels(
    current.router9.scanned_models,
    router9Allowed.map((id) => ({ id, label: id, provider: 'router9' }))
  );

  return {
    ...current,
    default_provider: current.default_provider === 'auto' && defaults.default_provider ? defaults.default_provider : current.default_provider,
    router9: {
      ...current.router9,
      base_url: current.router9.base_url || defaults.router9.base_url || '',
      model: router9Model,
      only_mode: current.router9.only_mode || defaults.router9.only_mode,
      allowed_model_ids: router9Allowed,
      scanned_models: router9Scanned,
    },
    ocr: defaults.router9.api_key_configured || router9Allowed.length > 0
      ? { ...current.ocr, provider: 'router9', model: '' }
      : current.ocr,
  };
}

function mergeUnique(primary: string[], secondary: string[]) {
  return [...new Set([...primary, ...secondary].filter(Boolean))];
}

function mergeScannedModels(primary: RuntimeSettings['router9']['scanned_models'], secondary: RuntimeSettings['router9']['scanned_models']) {
  const byId = new Map(primary.map((model) => [model.id, model]));
  secondary.forEach((model) => {
    if (!byId.has(model.id)) byId.set(model.id, model);
  });
  return [...byId.values()];
}

function readMobileWarningDismissed() {
  try {
    return window.localStorage.getItem(MOBILE_WARNING_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function loadStoredSettings(saved: string): RuntimeSettings {
  const parsed = JSON.parse(saved) as { version?: number; settings?: Partial<RuntimeSettings> } & Partial<RuntimeSettings>;
  const next = mergeRuntimeSettingsShape(parsed.settings ?? parsed);

  if (parsed.version !== SETTINGS_STORAGE_VERSION) {
    dropLegacyDefaults(next);
  }
  dropLegacyOcrDefaults(next);

  return dropApiKeys(next);
}

function loadRemoteSettings(settings: Partial<RuntimeSettings>, current: RuntimeSettings): RuntimeSettings {
  return dropApiKeys(mergeRuntimeSettingsShape(settings, current));
}

function mergeRuntimeSettingsShape(rawSettings: Partial<RuntimeSettings>, base: RuntimeSettings = defaultRuntimeSettings): RuntimeSettings {
  return {
    ...base,
    ...rawSettings,
    openrouter: { ...base.openrouter, ...rawSettings.openrouter },
    nvidia: { ...base.nvidia, ...rawSettings.nvidia },
    ollama: { ...base.ollama, ...rawSettings.ollama },
    router9: { ...base.router9, ...rawSettings.router9 },
    ocr: { ...base.ocr, ...rawSettings.ocr },
  };
}

function sanitizeSettingsForStorage(settings: RuntimeSettings): RuntimeSettings {
  return {
    ...defaultRuntimeSettings,
    default_provider: settings.default_provider,
    openrouter: { ...defaultRuntimeSettings.openrouter, model: settings.openrouter.model },
    nvidia: { ...defaultRuntimeSettings.nvidia, model: settings.nvidia.model },
    ollama: { ...defaultRuntimeSettings.ollama, model: settings.ollama.model },
    router9: { ...defaultRuntimeSettings.router9, model: settings.router9.model },
    ocr: settings.ocr,
  };
}

function dropApiKeys(settings: RuntimeSettings): RuntimeSettings {
  return sanitizeSettingsForStorage(settings);
}

function dropLegacyDefaults(settings: RuntimeSettings) {
  const legacyProviderDefaults = {
    openrouter: { base_url: 'https://openrouter.ai/api/v1', model: 'openrouter/nvidia/nemotron-3-super-120b-a12b:free' },
    nvidia: { base_url: 'https://integrate.api.nvidia.com/v1', model: 'qwen/qwen3-coder-480b-a35b-instruct' },
    ollama: { base_url: 'https://ollama.com/v1', model: 'gpt-oss:120b' },
    router9: { base_url: 'http://localhost:20128/v1', model: '' },
  };

  for (const provider of ['openrouter', 'nvidia', 'ollama', 'router9'] as const) {
    if (settings[provider].base_url === legacyProviderDefaults[provider].base_url) {
      settings[provider].base_url = '';
    }
    if (settings[provider].model === legacyProviderDefaults[provider].model) {
      settings[provider].model = '';
    }
  }

  dropLegacyOcrDefaults(settings);
  if (settings.openrouter_x_title === 'Hinh Math Renderer') {
    settings.openrouter_x_title = '';
  }
}

function dropLegacyOcrDefaults(settings: RuntimeSettings) {
  if (settings.ocr.model === 'qwen/qwen2.5-vl-72b-instruct:free' || settings.ocr.model === 'google/gemma-4-26b-a4b-it:free') {
    settings.ocr.model = '';
  }
}

function hasSegment(scene: MathScene, start: string, end: string) {
  return scene.objects.some((obj) => {
    if (obj.type !== 'segment') return false;
    const [a, b] = obj.points;
    return (a === start && b === end) || (a === end && b === start);
  });
}

function findPoint(scene: MathScene, name: string): Vec3 | null {
  const point = scene.objects.find((obj) => (obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name);
  if (!point || (point.type !== 'point_2d' && point.type !== 'point_3d')) return null;
  return { x: point.x, y: point.y, z: point.type === 'point_3d' ? point.z : 0 };
}

function projectPointToSegment(point: Vec3, start: Vec3, end: Vec3): Vec3 {
  const direction = sub(end, start);
  const size = dot(direction, direction);
  if (size <= 1e-9) return start;
  const t = Math.max(0, Math.min(1, dot(sub(point, start), direction) / size));
  return add(start, scale(direction, t));
}

function nextPointName(scene: MathScene) {
  const used = new Set(scene.objects.map((obj) => ('name' in obj && typeof obj.name === 'string' ? obj.name : null)).filter(Boolean));
  for (const name of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
    if (!used.has(name)) return name;
  }
  let index = 1;
  while (used.has(`P${index}`)) index += 1;
  return `P${index}`;
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

function dot(a: Vec3, b: Vec3) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function round(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
      } else {
        reject(new Error('Không đọc được ảnh OCR.'));
      }
    };
    reader.onerror = () => reject(new Error('Không đọc được ảnh OCR.'));
    reader.readAsDataURL(file);
  });
}

function buildModelOptions(settings: RuntimeSettings, defaults?: SettingsDefaults | null): ModelOption[] {
  const providerOptions = (['openrouter', 'nvidia', 'ollama'] as const).flatMap((provider) => {
    const providerDefaults = defaults?.[provider];
    const allowedIds = providerDefaults?.allowed_model_ids ?? [];
    const scanned = providerDefaults?.scanned_models ?? [];
    const ids = allowedIds.length > 0 ? allowedIds : [providerDefaults?.model ?? settings[provider].model].filter(Boolean) as string[];
    return ids.map((modelId) => {
      const model = scanned.find((item) => item.id === modelId);
      return {
        key: `${provider}:${modelId}`,
        provider,
        modelId,
        label: `${providerLabel(provider)}: ${model?.label ?? modelId}`,
        description: `${providerLabel(provider)} model ${modelId}${model?.context_length ? ` — context ${model.context_length}` : ''}`,
      };
    });
  });

  const router9Defaults = defaults?.router9;
  const router9Ids = router9Defaults?.allowed_model_ids.length ? router9Defaults.allowed_model_ids : [router9Defaults?.model ?? settings.router9.model].filter(Boolean) as string[];
  const router9Options = router9Ids.map((modelId) => {
    const scanned = router9Defaults?.scanned_models.find((model) => model.id === modelId);
    return {
      key: `router9:${modelId}`,
      provider: 'router9',
      modelId,
      label: `9router: ${scanned?.label ?? modelId}`,
      description: `9router model ${modelId}`,
    };
  });

  if (defaults?.router9.only_mode) {
    return router9Options;
  }

  return [...staticModelOptions, ...providerOptions, ...router9Options];
}

function providerLabel(provider: 'openrouter' | 'nvidia' | 'ollama') {
  if (provider === 'openrouter') return 'OpenRouter';
  if (provider === 'nvidia') return 'NVIDIA';
  return 'Ollama';
}
