import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AdminConsole } from './components/admin/AdminConsole';
import { ApiError, changePassword, deleteRenderHistory, forgotPassword, getCurrentUser, getHealth, getRenderHistory, getRenderHistoryDetail, getSessions, getSettingsDefaults, login, loginWithGoogle, logout, ocrImage, register, renderEditedScene, renderProblem, resendVerification, resetPassword, revokeOtherSessions, revokeSession, updateProfile, verifyEmail, type AdminRenderHistoryDetail, type RenderHistoryItem, type SessionResponse, type UserResponse } from './api/client';
import { defaultAdvancedSettings, ProblemInput, type ModelOption, type TierKey } from './components/ProblemInput';
import { AccountPage } from './components/AccountPage';
import { FeedbackPage } from './components/FeedbackPage';
import { ChatBubble } from './components/ChatBubble';
import { HomePage } from './components/HomePage';
import { LoginPage } from './components/LoginPage';
import { ResetPasswordPage } from './components/ResetPasswordPage';
import { VerifyEmailPage } from './components/VerifyEmailPage';
import { RendererPanel } from './components/RendererPanel';
import type { ThreeSceneImageCapture } from './components/ThreeGeometryView';
import { SceneEditorPanel, type PointPlacementPlane } from './components/SceneEditorPanel';
import { PrivacyPolicyPage, TermsPage } from './components/LegalPages';
import { SolverPanel } from './components/SolverPanel';
import { FunctionAnalyzerPanel } from './components/FunctionAnalyzerPanel';
import { CalculusSimulationPage } from './components/CalculusSimulationPage';
import { GeoGebraLabPage } from './components/GeoGebraLabPage';
import { PdfToWordPage } from './components/PdfToWordPage';
import { KatexSpan } from './components/KatexSpan';
import { AboutPage, AccessDeniedPage, AnalyzerGuidePage, GuidePage, HistoryPage, HistoryPanel, MobileRendererWarning, isGeometryMobileWarningView } from './components/AppPages';
import { NotificationStack } from './components/NotificationStack';
import { useNotifications } from './hooks/useNotifications';
import { ExportMenuItems } from './components/ExportMenu';
import { ProblemVariantTool } from './components/DiagramTools';
import { normalizeMineruBaseUrl } from './api/mineru';
import { getDefaultParamValues, patchGeogebraCommandsForScene, recomputeSceneWithParameters, recomputeThreeScene } from './utils/sceneParameters';
import { clamp, findPoint, hasSegment, nextPointName, projectPointToSegment, round, type Vec3 } from './utils/sceneEditing';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, type RuntimeSettings, type SettingsDefaults } from './types/settings';
import logoUrl from '../img.svg';
import './styles.css';

const MOBILE_WARNING_STORAGE_KEY = 'hinh-mobile-warning-dismissed';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 900px)';
const DEVELOPER_GITHUB_URL = 'https://github.com/sin0235';
const CONTACT_EMAIL = 'support@sin-studio.tech';
const CONTACT_ZALO_PHONE = '0347952503';
const CONTACT_ZALO_URL = `https://zalo.me/${CONTACT_ZALO_PHONE}`;
const MINERU_API_BASE_URL = normalizeMineruBaseUrl(import.meta.env.VITE_MINERU_API_BASE_URL);

type AppView = 'home' | 'render' | 'analyzer' | 'analyzer-guide' | 'simulation' | 'geogebra-lab' | 'pdf-to-word' | 'history' | 'guide' | 'about' | 'privacy-policy' | 'terms' | 'login' | 'admin' | 'account' | 'feedback' | 'reset-password' | 'verify-email';
type EditTool = 'move' | 'connect' | 'project_to_segment' | 'add_point';
type BackendStatus = {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
};

const viewPaths: Record<AppView, string> = {
  home: '/',
  render: '/render',
  analyzer: '/analyzer',
  'analyzer-guide': '/analyzer/guide',
  simulation: '/simulation',
  'geogebra-lab': '/geogebra-lab',
  'pdf-to-word': '/pdf-to-word',
  history: '/history',
  guide: '/guide',
  about: '/about',
  'privacy-policy': '/privacy-policy',
  terms: '/terms',
  login: '/login',
  admin: '/admin',
  account: '/account',
  feedback: '/feedback',
  'reset-password': '/reset-password',
  'verify-email': '/verify-email',
};

function pathToView(pathname: string): AppView {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  if (normalized === '/settings') return 'render';
  const match = Object.entries(viewPaths).find(([, path]) => path === normalized);
  return match ? match[0] as AppView : 'home';
}

function FooterNavIcon({ children }: { children: React.ReactNode }) {
  return (
    <svg className="footer-nav-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

function ZaloIcon() {
  return (
    <svg className="footer-nav-icon footer-nav-icon--zalo" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="14 12 44 42" aria-hidden="true">
      <path
        d="M18 20C18 16.7 20.7 14 24 14H48C51.3 14 54 16.7 54 20V36C54 39.3 51.3 42 48 42H33L24 50L26 42H24C20.7 42 18 39.3 18 36Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.8"
        strokeLinejoin="round"
      />
      <text x="36" y="32" textAnchor="middle" fontFamily="Arial, Helvetica, sans-serif" fontSize="11" fontWeight="700" letterSpacing="0.5" fill="currentColor">
        Zalo
      </text>
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

function ToolboxIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M7 12h10M9 17h6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><circle cx="9" cy="7" r="2" fill="currentColor" /><circle cx="15" cy="12" r="2" fill="currentColor" /><circle cx="12" cy="17" r="2" fill="currentColor" /></svg>;
}

function GeometryEditIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17 11 6l8 12H5Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M11 6v12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><circle cx="5" cy="17" r="1.8" fill="currentColor" /><circle cx="11" cy="6" r="1.8" fill="currentColor" /><circle cx="19" cy="18" r="1.8" fill="currentColor" /></svg>;
}

function CloseIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>;
}

function FooterNavLink({
  href,
  title,
  target,
  rel,
  children,
  icon,
}: {
  href: string;
  title?: string;
  target?: string;
  rel?: string;
  children: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <a href={href} className="footer-nav-link" title={title} target={target} rel={rel}>
      {icon}
      <span className="footer-nav-label">{children}</span>
    </a>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState<AppView>(() => pathToView(window.location.pathname));
  const [result, setResult] = useState<RenderResponse | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [problemText, setProblemText] = useState('');
  const [lastAdvancedSettings, setLastAdvancedSettings] = useState<AdvancedRenderSettings>(defaultAdvancedSettings);
  const [editTool, setEditTool] = useState<EditTool>('move');
  const [pointToSegmentSource, setPointToSegmentSource] = useState<string | null>(null);
  const [pointPlacementPlane, setPointPlacementPlane] = useState<PointPlacementPlane>('xy');
  const [pointPlacementDepth, setPointPlacementDepth] = useState('0');
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettings>(defaultRuntimeSettings);
  const [renderTier, setRenderTier] = useState<TierKey>('tier1');
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsDefaults | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'checking' });
  const { notifications, showNotification, dismissNotification, showApiError, showWarnings, showAnalyzerWarnings } = useNotifications();
  const [mobileWarningDismissed, setMobileWarningDismissed] = useState(readMobileWarningDismissed);
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false);
  const [renderToolsOpen, setRenderToolsOpen] = useState(false);
  const [renderToolsPanel, setRenderToolsPanel] = useState<'export' | 'variants' | null>(null);
  const [sidebarTool, setSidebarTool] = useState<'input' | 'solver'>('input');
  const [highlightedObjects, setHighlightedObjects] = useState<string[]>([]);
  const [threeImageCapture, setThreeImageCapture] = useState<ThreeSceneImageCapture | null>(null);
  const [editorButtonTop, setEditorButtonTop] = useState(220);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authToken, setAuthToken] = useState('');
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState('');
  const [historyItems, setHistoryItems] = useState<RenderHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [openingHistoryId, setOpeningHistoryId] = useState<string | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [toolsMenuOpen, setToolsMenuOpen] = useState(false);
  const resultAnchorRef = useRef<HTMLDivElement | null>(null);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);
  const toolsMenuRef = useRef<HTMLDivElement | null>(null);
  const renderToolsMenuRef = useRef<HTMLDivElement | null>(null);
  const ocrInFlightRef = useRef(false);
  const editorButtonDragRef = useRef<{ pointerId: number; startY: number; startTop: number; moved: boolean } | null>(null);

  function navigateTo(view: AppView, replace = false) {
    setActiveView(view);
    const nextPath = viewPaths[view];
    if (window.location.pathname === nextPath && !window.location.search) return;
    const method = replace ? 'replaceState' : 'pushState';
    window.history[method]({}, document.title, nextPath);
  }

  useEffect(() => {
    function handlePopState() {
      setActiveView(pathToView(window.location.pathname));
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (!accountMenuOpen && !toolsMenuOpen && !renderToolsOpen) return;
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (!accountMenuRef.current?.contains(target)) setAccountMenuOpen(false);
      if (!toolsMenuRef.current?.contains(target)) setToolsMenuOpen(false);
      if (!renderToolsMenuRef.current?.contains(target)) {
        setRenderToolsOpen(false);
        setRenderToolsPanel(null);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setAccountMenuOpen(false);
        setToolsMenuOpen(false);
        setRenderToolsOpen(false);
        setRenderToolsPanel(null);
      }
    }
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [accountMenuOpen, toolsMenuOpen, renderToolsOpen]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([getHealth(), getSettingsDefaults()])
      .then(([health, defaults]) => {
        if (cancelled) return;
        setBackendStatus({ state: 'online', appName: health.app });
        setSettingsDefaults(defaults);
        setRuntimeSettings(runtimeSettingsFromAdminDefaults(defaults));
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
    if (!settingsDefaults) return;
    setRuntimeSettings(runtimeSettingsFromAdminDefaults(settingsDefaults));
  }, [settingsDefaults]);

  useEffect(() => {
    if (window.location.pathname.replace(/\/+$/, '') === '/settings') {
      navigateTo('render', true);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('auth');
    const authError = params.get('auth_error');
    const token = params.get('token');
    if (action === 'google-success') {
      navigateTo('render', true);
      showNotification('Đăng nhập Google', 'Đăng nhập Google thành công. Workspace của bạn đã được đồng bộ.', [], 'info');
      return;
    }
    if (authError) {
      navigateTo('login', true);
      const message = authError === 'google_unverified_email'
        ? 'Email Google này chưa được xác minh nên chưa thể đăng nhập.'
        : 'Không thể hoàn tất đăng nhập Google. Hãy thử lại hoặc dùng email/mật khẩu.';
      showNotification('Đăng nhập Google', message, [], 'error');
      return;
    }
    if (token) {
      setAuthToken(token);
      const targetView = action === 'verify-email' || window.location.pathname === viewPaths['verify-email']
        ? 'verify-email'
        : action === 'reset-password' || window.location.pathname === viewPaths['reset-password']
          ? 'reset-password'
          : null;
      if (targetView) navigateTo(targetView, true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then(({ user }) => {
        if (cancelled) return;
        applyAuthenticatedUserInBackground(user);
        if (user.role === 'admin' && pathToView(window.location.pathname) === 'home') {
          navigateTo('admin', true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setEditorButtonTop(clamp(window.innerHeight * 0.55, 84, window.innerHeight - 88));
  }, []);

  useEffect(() => {
    if (sidebarTool !== 'solver') setHighlightedObjects([]);
  }, [sidebarTool]);

  const handleThreeImageCaptureReady = useCallback((capture: ThreeSceneImageCapture | null) => {
    setThreeImageCapture(() => capture);
  }, []);

  // Reset slider values khi scene mới được dựng
  useEffect(() => {
    setParamValues(getDefaultParamValues(result?.scene.parameters));
  }, [result?.scene]);

  // Tạo result đã được recompute theo paramValues. Khi không có parameters, trả result gốc.
  const effectiveResult = useMemo<RenderResponse | null>(() => {
    if (!result) return null;
    const params = result.scene.parameters;
    if (!params || params.length === 0) return result;
    const recomputedScene = recomputeSceneWithParameters(result.scene, paramValues);
    let payload = result.payload;
    if (payload.three_scene) {
      payload = { ...payload, three_scene: recomputeThreeScene(payload.three_scene, recomputedScene) };
    }
    if (payload.geogebra_commands && payload.geogebra_commands.length > 0) {
      payload = { ...payload, geogebra_commands: patchGeogebraCommandsForScene(payload.geogebra_commands, recomputedScene) };
    }
    return { ...result, scene: recomputedScene, payload };
  }, [result, paramValues]);

  const modelOptions = buildModelOptions(runtimeSettings, settingsDefaults);
  const threeInteraction = effectiveResult?.scene.renderer === 'threejs_3d'
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
        onBlockedPointClick: handleAddPointBlockedClick,
        saving: editorSaving,
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

  async function handleOcrImage(
    file: File,
    mode: 'problem' | 'diagram' = 'problem',
  ) {
    if (ocrInFlightRef.current) return;
    if (!user) {
      showNotification('Cần đăng nhập', 'Vui lòng đăng nhập trước khi dùng OCR.', [], 'warning');
      navigateTo('login');
      return;
    }
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

    ocrInFlightRef.current = true;
    setOcrLoading(true);
    try {
      const imageDataUrl = await fileToDataUrl(file);
      const response = await ocrImage(imageDataUrl, runtimeSettings, mode);
      setProblemText(response.text.trim());
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể OCR ảnh đề bài.');
      showApiError('OCR thất bại', apiError, 'Hãy kiểm tra ảnh có rõ chữ không, model OCR đã chọn có hỗ trợ ảnh không, hoặc thử provider/model khác.');
    } finally {
      ocrInFlightRef.current = false;
      setOcrLoading(false);
    }
  }

  async function handleSubmit(
    problemText: string,
    tier: TierKey,
    advancedSettings?: AdvancedRenderSettings,
    preferredRenderer?: Renderer,
  ) {
    if (!user) {
      showNotification('Cần đăng nhập', 'Vui lòng đăng nhập trước khi dựng hình.', [], 'warning');
      navigateTo('login');
      return;
    }
    setLoading(true);
    setPointToSegmentSource(null);
    setEditTool('move');
    setLastAdvancedSettings(advancedSettings ?? defaultAdvancedSettings);
    try {
      const response = await renderProblem(problemText, tier, advancedSettings, preferredRenderer);
      setResult(response);
      if (user) void refreshHistory();
      scrollToResultOnMobile();
      showWarnings(response.warnings);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể dựng hình từ đề bài này.');
      showApiError('Dựng hình thất bại', apiError, 'Hãy thử mức độ chất lượng khác hoặc viết đề bài rõ hơn.');
    } finally {
      setLoading(false);
    }
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

  function clearSessionState() {
    setUser(null);
    setHistoryItems([]);
    setHistoryOpen(false);
    setAccountMenuOpen(false);
  }

  async function applyAuthenticatedUser(nextUser: UserResponse) {
    setUser(nextUser);
    await loadRemoteWorkspace(nextUser);
  }

  function applyAuthenticatedUserInBackground(nextUser: UserResponse) {
    setUser(nextUser);
    void loadRemoteWorkspace(nextUser);
  }

  async function handleLogin(email: string, password: string) {
    setAuthLoading(true);
    try {
      const response = await login(email, password);
      applyAuthenticatedUserInBackground(response.user);
      setPendingVerificationEmail('');
      navigateTo(response.user.role === 'admin' ? 'admin' : 'render');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleGoogleLogin() {
    setAuthLoading(true);
    try {
      const response = await loginWithGoogle();
      applyAuthenticatedUserInBackground(response.user);
      navigateTo(response.user.role === 'admin' ? 'admin' : 'render');
      showNotification('Đăng nhập Google', 'Đăng nhập Google thành công. Workspace của bạn đã được đồng bộ.', [], 'info');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleRegister(email: string, password: string, displayName: string | undefined, acceptPrivacyPolicy: boolean, acceptTerms: boolean) {
    setAuthLoading(true);
    try {
      const response = await register(email, password, displayName, acceptPrivacyPolicy, acceptTerms);
      if (response.user.email_verified_at) {
        await applyAuthenticatedUser(response.user);
        navigateTo('render');
      } else {
        await logout().catch(() => undefined);
        clearSessionState();
        setPendingVerificationEmail(email);
        navigateTo('verify-email');
        showNotification('Xác minh email', 'Tài khoản đã tạo. Nhập mã OTP trong email để kích hoạt workspace.', [], 'info');
      }
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    setAuthLoading(true);
    try {
      await logout();
    } finally {
      clearSessionState();
      navigateTo('login');
      setAuthLoading(false);
    }
  }

  async function handleForgotPassword(email: string) {
    const response = await forgotPassword(email);
    return response.message;
  }

  async function handleResetPassword(token: string, password: string) {
    const response = await resetPassword(token, password);
    clearSessionState();
    setAuthToken('');
    navigateTo('login');
    showNotification('Đặt lại mật khẩu', `${response.message} Hãy đăng nhập để mở workspace.`, [], 'info');
    return response.message;
  }

  async function handleVerifyEmail(token: string, otp: string) {
    const response = await verifyEmail(token, otp);
    await applyAuthenticatedUser(response.user);
    setAuthToken('');
    setPendingVerificationEmail('');
    navigateTo(response.user.role === 'admin' ? 'admin' : 'render');
    showNotification('Xác minh email', 'Email đã xác minh. Workspace của bạn đã sẵn sàng.', [], 'info');
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
    await refreshHistory();
  }

  async function refreshHistory() {
    setHistoryLoading(true);
    try {
      setHistoryItems(await getRenderHistory());
    } finally {
      setHistoryLoading(false);
    }
  }

  function openAdminRenderJobDetail(detail: AdminRenderHistoryDetail) {
    setProblemText(detail.problem_text);
    setResult({ scene: detail.scene, payload: detail.payload, warnings: detail.warnings });
    navigateTo('render');
    scrollToResultOnMobile();
  }

  async function openHistoryItem(id: string) {
    setOpeningHistoryId(id);
    try {
      const detail = await getRenderHistoryDetail(id);
      setProblemText(detail.problem_text);
      setResult({ scene: detail.scene, payload: detail.payload, warnings: detail.warnings });
      navigateTo('render');
      scrollToResultOnMobile();
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể mở lịch sử dựng hình.');
      showApiError('Không thể mở lịch sử', apiError, 'Hãy đăng nhập lại hoặc thử tải lại trang.');
    } finally {
      setOpeningHistoryId(null);
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
    if (!result?.scene || editorSaving) return;
    const editedScene: MathScene = {
      ...result.scene,
      objects: result.scene.objects.map((obj) => {
        if ((obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name) {
          // Khi user tự kéo điểm, xoá biểu thức tham số (nếu có) cho điểm đó
          // vì giá trị mới do user đặt thủ công, không còn phụ thuộc tham số.
          if (obj.type === 'point_3d') {
            return { ...obj, x: round(point.x), y: round(point.y), z: round(point.z), x_expr: null, y_expr: null, z_expr: null };
          }
          return { ...obj, x: round(point.x), y: round(point.y), x_expr: null, y_expr: null };
        }
        return obj;
      }),
    };
    await handleSceneEdit(editedScene);
  }

  async function handleConnectPoints(start: string, end: string) {
    if (!result?.scene || editorSaving) return;
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
        { type: 'segment', points: [start, end], hidden: false, color: '#111111', line_width: 3, style: 'solid' },
      ],
    };
    await handleSceneEdit(editedScene);
  }

  async function handlePointToSegmentClick(segmentPoints: [string, string], clickedPoint: Vec3) {
    if (editorSaving) return;
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
        { type: 'segment', points: [pointToSegmentSource, newName], hidden: false, color: '#111111', line_width: 3, style: 'solid' },
      ],
    };

    setPointToSegmentSource(null);
    await handleSceneEdit(editedScene);
  }

  function handleAddPointBlockedClick(name: string) {
    showNotification('Không thể thêm điểm', `Vị trí ${name} đã có điểm. Hãy click vào vùng trống trên hình.`, [], 'warning');
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
    if (user?.role === 'admin') {
      return (
        <>
          <NotificationStack notifications={notifications} onDismiss={dismissNotification} />
          <AdminConsole
            user={user}
            onBackToApp={() => navigateTo('home')}
            onOpenRenderJobDetail={openAdminRenderJobDetail}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
          />
        </>
      );
    }

    return (
      <>
        <NotificationStack notifications={notifications} onDismiss={dismissNotification} />
        <AccessDeniedPage user={user} onHome={() => navigateTo('home')} onLogin={() => navigateTo('login')} />
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
          onClick={() => navigateTo('home')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              navigateTo('home');
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
          <div className="tools-menu" ref={toolsMenuRef}>
            <button type="button" className={`nav-item ${activeView === 'render' || activeView === 'analyzer' || activeView === 'analyzer-guide' || activeView === 'simulation' || activeView === 'geogebra-lab' || activeView === 'pdf-to-word' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={toolsMenuOpen} onClick={() => setToolsMenuOpen((open) => !open)}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v18"></path><path d="M3 12h18"></path><path d="M5 5l14 14"></path><path d="M19 5L5 19"></path></svg>
              Công cụ
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>
            </button>
            {toolsMenuOpen && (
              <div className="tools-dropdown" role="menu">
                <button type="button" role="menuitem" className={activeView === 'render' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('render');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="12" x2="14" y2="12"></line><line x1="4" y1="18" x2="18" y2="18"></line></svg>
                  <span><strong>Dựng hình</strong><small>Vẽ hình học từ đề bài</small></span>
                </button>
                <button type="button" role="menuitem" className={activeView === 'analyzer' || activeView === 'analyzer-guide' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('analyzer');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                  <span><strong>Khảo sát hàm</strong><small>Đồ thị, đạo hàm, cực trị</small></span>
                </button>
                <button type="button" role="menuitem" className={activeView === 'simulation' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('simulation');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
                  <span><strong>Mô phỏng</strong><small>Tích phân, lượng giác, animation học toán</small></span>
                </button>
                <button type="button" role="menuitem" className={activeView === 'geogebra-lab' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('geogebra-lab');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M3 9h18"></path><path d="M9 21V9"></path><circle cx="16" cy="15" r="2"></circle></svg>
                  <span><strong>GeoGebra Lab</strong><small>Graphing, Geometry, 3D, Probability</small></span>
                </button>
                <button type="button" role="menuitem" className={activeView === 'pdf-to-word' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('pdf-to-word');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6"></path><path d="M8 13h8"></path><path d="M8 17h5"></path></svg>
                  <span><strong>PDF → Word</strong><small>Chuẩn cấu trúc đề trắc nghiệm</small></span>
                </button>
              </div>
            )}
          </div>
          {user?.role === 'admin' && (
            <button type="button" className="nav-item" onClick={() => {
              navigateTo('admin');
            }}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
              Admin
            </button>
          )}
          {user ? (
            <div className="account-menu" ref={accountMenuRef}>
              <button type="button" className={`account-menu-trigger ${activeView === 'history' || activeView === 'account' || activeView === 'feedback' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen((open) => !open)}>
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
                      navigateTo('history');
                      void refreshHistory();
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 3v6h6"></path><path d="M12 7v5l3 2"></path></svg>
                      Lịch sử
                    </button>
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      navigateTo('feedback');
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                      Góp ý
                    </button>
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      navigateTo('account');
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
            <button type="button" className={`nav-item ${activeView === 'login' ? 'active' : ''}`} onClick={() => navigateTo('login')}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><path d="M10 17l5-5-5-5"></path><path d="M15 12H3"></path></svg>
              Đăng nhập
            </button>
          )}
        </nav>
      </header>

      <NotificationStack notifications={notifications} onDismiss={dismissNotification} />
      {user?.role !== 'admin' && <ChatBubble user={user} onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)} />}
      {isGeometryMobileWarningView(activeView) && <MobileRendererWarning dismissed={mobileWarningDismissed} onDismiss={dismissMobileWarning} />}

      <main className="app-shell">
        {activeView === 'home' && (
          <HomePage
            logoUrl={logoUrl}
            backendStatus={{ ...backendStatus, settingsDefaults }}
            onOpenLogin={() => navigateTo('login')}
          />
        )}
        {activeView === 'render' && (
          <section className="workspace">
            <div className="workspace-sidebar">
              <div className="workspace-sidebar-tabs" role="tablist" aria-label="Workspace tools">
                <button type="button" className={sidebarTool === 'input' ? 'active' : ''} onClick={() => setSidebarTool('input')} role="tab" aria-selected={sidebarTool === 'input'}>
                  Mô tả hình
                </button>
                <button
                  type="button"
                  className={sidebarTool === 'solver' ? 'active' : ''}
                  onClick={() => {
                    if (!result?.scene) return;
                    setSidebarTool('solver');
                  }}
                  role="tab"
                  aria-selected={sidebarTool === 'solver'}
                  aria-disabled={!result?.scene}
                  title={!result?.scene ? 'Dựng hình trước để giải từng bước các câu hỏi' : undefined}
                >
                  Giải từng bước
                </button>
              </div>
              {sidebarTool === 'input' ? (
                <>
                  <ProblemInput
                    loading={loading}
                    ocrLoading={ocrLoading}
                    ocrError={null}
                    problemText={problemText}
                    tier={renderTier}
                    onProblemTextChange={setProblemText}
                    onTierChange={setRenderTier}
                    onOcrImage={handleOcrImage}
                    onOcrClipboardImage={handleOcrClipboardImage}
                    onSubmit={handleSubmit}
                  />
                  {user && (
                    <div className="history-drawer-wrap">
                      <button type="button" className="secondary-button history-toggle" onClick={() => setHistoryOpen((open) => !open)}>
                        {historyOpen ? 'Ẩn lịch sử' : `Lịch sử (${historyItems.length})`}
                      </button>
                      {historyOpen && <HistoryPanel items={historyItems} loading={historyLoading} openingId={openingHistoryId} onOpen={openHistoryItem} onDelete={removeHistoryItem} />}
                    </div>
                  )}
                </>
              ) : effectiveResult?.scene && user ? (
                <SolverPanel scene={effectiveResult.scene} runtimeSettings={runtimeSettings} onHighlight={setHighlightedObjects} />
              ) : (
                <div className="solver-disabled-state">
                  <strong>Chưa thể giải từng bước</strong>
                  <p>{!user ? 'Vui lòng đăng nhập để dùng giải từng bước.' : 'Hãy dựng hình xong trước, sau đó mở tab Giải từng bước.'}</p>
                </div>
              )}
            </div>
            {result && <button type="button" className="mobile-scroll-notice" onClick={scrollToResult}>↓ Xem hình vừa dựng</button>}
            <div className="result-area" ref={resultAnchorRef}>
              <div className="render-stage">
                <RendererPanel result={effectiveResult} threeInteraction={threeInteraction} onGeoGebraPointChange={handlePointDragEnd} highlightedObjects={highlightedObjects} saving={editorSaving} onThreeImageCaptureReady={handleThreeImageCaptureReady} />
                {effectiveResult?.scene && (
                  <div ref={renderToolsMenuRef} className="render-tools-floating" style={{ top: editorButtonTop }}>
                    <button
                      type="button"
                      className="render-editor-trigger"
                      onPointerDown={handleEditorButtonPointerDown}
                      onPointerMove={handleEditorButtonPointerMove}
                      onPointerUp={handleEditorButtonPointerUp}
                      onPointerCancel={handleEditorButtonPointerUp}
                      onClick={() => {
                        if (editorButtonDragRef.current?.moved) return;
                        setRenderToolsOpen((open) => {
                          const nextOpen = !open;
                          if (!nextOpen) setRenderToolsPanel(null);
                          return nextOpen;
                        });
                      }}
                      aria-label="Mở công cụ hình"
                      aria-haspopup="menu"
                      aria-expanded={renderToolsOpen}
                      title="Công cụ hình"
                    >
                      <ToolboxIcon />
                    </button>
                    {renderToolsOpen && (
                      <div
                        className="render-tools-menu"
                        role="menu"
                        style={{ top: Math.min(Math.max(editorButtonTop - 8, 72), Math.max(72, window.innerHeight - 430)) }}
                      >
                        <button
                          type="button"
                          role="menuitem"
                          className="render-tools-menu-item"
                          onClick={() => {
                            setRenderToolsOpen(false);
                            setSceneEditorOpen(true);
                          }}
                        >
                          <GeometryEditIcon />
                          <span><strong>Sửa hình học</strong><small>Kéo điểm, thêm quan hệ, chỉnh tham số.</small></span>
                        </button>
                        <button
                          type="button"
                          role="menuitem"
                          className="render-tools-menu-item"
                          onClick={() => setRenderToolsPanel((panel) => panel === 'export' ? null : 'export')}
                          aria-expanded={renderToolsPanel === 'export'}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M14 3v5h5M9 15h6M9 18h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
                          <span><strong>Xuất hình</strong><small>PNG, JPG, SVG, HTML KaTeX, TikZ.</small></span>
                        </button>
                        {renderToolsPanel === 'export' && (
                          <div className="render-tools-submenu render-tools-export-submenu">
                            <ExportMenuItems
                              scene={effectiveResult.scene}
                              advancedSettings={lastAdvancedSettings}
                              captureCurrentView={threeImageCapture}
                              preferCurrentViewCapture={Boolean(effectiveResult.payload.three_scene)}
                              onError={(msg) => showNotification('Xuất hình thất bại', msg, [], 'error')}
                              onAfterDownload={() => {
                                setRenderToolsOpen(false);
                                setRenderToolsPanel(null);
                              }}
                              itemClassName="render-tools-menu-item render-tools-submenu-item"
                            />
                          </div>
                        )}
                        <button
                          type="button"
                          role="menuitem"
                          className="render-tools-menu-item"
                          onClick={() => setRenderToolsPanel((panel) => panel === 'variants' ? null : 'variants')}
                          aria-expanded={renderToolsPanel === 'variants'}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12M6 12h12M6 17h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><path d="M16 15l2 2 3-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
                          <span><strong>Sinh đề</strong><small>Chọn số lượng đề biến thể.</small></span>
                        </button>
                        {renderToolsPanel === 'variants' && (
                          <div className="render-tools-submenu">
                            <ProblemVariantTool scene={effectiveResult.scene} originalProblem={problemText} runtimeSettings={runtimeSettings} onError={(msg) => showNotification('Công cụ hình', msg, [], 'info')} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                {sceneEditorOpen && result?.scene && (
                  <div className="scene-editor-layer" role="presentation" onMouseDown={() => setSceneEditorOpen(false)}>
                    <div className="scene-editor-popover" role="dialog" aria-modal="true" aria-label="Sửa hình học" onMouseDown={(event) => event.stopPropagation()}>
                      <div className="scene-editor-popover-header">
                        <strong>Sửa hình học</strong>
                        <button type="button" className="scene-editor-close" onClick={() => setSceneEditorOpen(false)} aria-label="Đóng sửa hình học"><CloseIcon /></button>
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
                        parameters={result.scene.parameters}
                        parameterValues={paramValues}
                        onParameterValuesChange={setParamValues}
                        onParameterReset={() => setParamValues(getDefaultParamValues(result.scene.parameters))}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
        {activeView === 'analyzer' && (
          <div className="analyzer-standalone-wrap">
            <FunctionAnalyzerPanel onOpenGuide={() => navigateTo('analyzer-guide')} onWarnings={showAnalyzerWarnings} />
          </div>
        )}
        {activeView === 'simulation' && <CalculusSimulationPage />}
        {activeView === 'geogebra-lab' && <GeoGebraLabPage />}
        {activeView === 'pdf-to-word' && (
          <PdfToWordPage
            apiBaseUrl={MINERU_API_BASE_URL}
            modelOptions={modelOptions}
            runtimeSettings={runtimeSettings}
            router9Only={settingsDefaults?.router9.only_mode ?? false}
            onOpenSettings={() => navigateTo(user?.role === 'admin' ? 'admin' : 'render')}
          />
        )}
        {activeView === 'analyzer-guide' && <AnalyzerGuidePage onOpenGeneralGuide={() => navigateTo('guide')} />}
        {activeView === 'history' && (
          <HistoryPage
            user={user}
            items={historyItems}
            loading={historyLoading}
            openingId={openingHistoryId}
            onOpen={openHistoryItem}
            onDelete={removeHistoryItem}
            onLogin={() => navigateTo('login')}
            onWorkspace={() => navigateTo('render')}
          />
        )}
        {activeView === 'guide' && <GuidePage onOpenAnalyzerGuide={() => navigateTo('analyzer-guide')} />}
        {activeView === 'about' && <AboutPage onStart={() => navigateTo('render')} onGuide={() => navigateTo('guide')} />}
        {activeView === 'privacy-policy' && <PrivacyPolicyPage />}
        {activeView === 'terms' && <TermsPage />}
        {activeView === 'login' && (
          <LoginPage
            logoUrl={logoUrl}
            user={user}
            authLoading={authLoading}
            onOpenWorkspace={() => navigateTo('render')}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            onLogin={handleLogin}
            onGoogleLogin={handleGoogleLogin}
            onRegister={handleRegister}
            onForgotPassword={handleForgotPassword}
            onLogout={handleLogout}
            onOpenAccount={() => navigateTo('account')}
            onOpenPrivacyPolicy={() => navigateTo('privacy-policy')}
            onOpenTerms={() => navigateTo('terms')}
          />
        )}
        {activeView === 'feedback' && (
          <FeedbackPage
            user={user}
            onLogin={() => navigateTo('login')}
            onBackWorkspace={() => navigateTo('render')}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
          />
        )}
        {activeView === 'account' && user && (
          <AccountPage
            user={user}
            authLoading={authLoading}
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            onBackWorkspace={() => navigateTo('render')}
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
          <ResetPasswordPage token={authToken} onResetPassword={handleResetPassword} onBackLogin={() => navigateTo('login')} onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)} />
        )}
        {activeView === 'verify-email' && (
          <VerifyEmailPage token={authToken} email={pendingVerificationEmail} onVerifyEmail={handleVerifyEmail} onBackWorkspace={() => navigateTo('render')} onBackLogin={() => navigateTo('login')} onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)} />
        )}
      </main>
      <footer className="app-footer">
        <div className="footer-top">
          <div className="footer-brand-block">
            <div className="footer-brand">
              <img src={logoUrl} alt="AI Math Renderer" />
              <strong>AI Math Renderer</strong>
            </div>
            <p>Hệ sinh thái AI Toán học: Dựng hình GeoGebra/Three.js từ ngôn ngữ tự nhiên, khảo sát hàm số, mô phỏng 2D/3D, và thực hành GeoGebra Lab đa năng.</p>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <div>
              <strong>Sản phẩm</strong>
              <FooterNavButton
                onClick={() => navigateTo('render')}
                icon={
                  <FooterNavIcon>
                    <path d="M4 4h16v16H4z" />
                    <path d="M8 16 16 8M8 8h8v8" />
                  </FooterNavIcon>
                }
              >
                Không gian làm việc
              </FooterNavButton>
              <FooterNavButton
                onClick={() => navigateTo('guide')}
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
                onClick={() => navigateTo('about')}
                icon={
                  <FooterNavIcon>
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4" />
                    <path d="M12 8h.01" />
                  </FooterNavIcon>
                }
              >
                Giới thiệu
              </FooterNavButton>
            </div>
            <div>
              <strong>Hỗ trợ</strong>
              <FooterNavButton
                onClick={() => navigateTo('feedback')}
                icon={
                  <FooterNavIcon>
                    <rect x="5" y="3" width="14" height="18" rx="2.5" />
                    <path d="M9 7h6" />
                    <path d="M8 11h8" />
                    <path d="M8 15h5" />
                    <path d="m14.5 17 1.5 1.5 3-3" />
                  </FooterNavIcon>
                }
              >
                Góp ý
              </FooterNavButton>
              <FooterNavLink
                href={CONTACT_ZALO_URL}
                title={`Zalo ${CONTACT_ZALO_PHONE}`}
                target="_blank"
                rel="noreferrer"
                icon={<ZaloIcon />}
              >
                Zalo
              </FooterNavLink>
              <FooterNavLink
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
              </FooterNavLink>
            </div>
            <div>
              <strong>Pháp lý</strong>
              <FooterNavButton
                onClick={() => navigateTo('privacy-policy')}
                icon={
                  <FooterNavIcon>
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
                  </FooterNavIcon>
                }
              >
                Chính sách bảo mật
              </FooterNavButton>
              <FooterNavButton
                onClick={() => navigateTo('terms')}
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
            © 2026 AI Math Renderer by{' '}
            <a href={DEVELOPER_GITHUB_URL} target="_blank" rel="noopener noreferrer" className="footer-developer-link">
              <strong>Sin Studio</strong>
            </a>
          </span>
        </div>
      </footer>
    </>
  );
}

function toApiError(caught: unknown, fallback: string): ApiError {
  if (caught instanceof ApiError) return caught;
  if (caught instanceof Error) return new ApiError(caught.message || fallback);
  return new ApiError(fallback);
}

function readMobileWarningDismissed() {
  try {
    return window.localStorage.getItem(MOBILE_WARNING_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function runtimeSettingsFromAdminDefaults(defaults: SettingsDefaults): RuntimeSettings {
  return {
    ...defaultRuntimeSettings,
    default_provider: defaults.default_provider,
    openrouter: providerSettingsFromAdminDefaults(defaults.openrouter),
    nvidia: providerSettingsFromAdminDefaults(defaults.nvidia),
    ollama: providerSettingsFromAdminDefaults(defaults.ollama),
    openai_compat: providerSettingsFromAdminDefaults(defaults.openai_compat),
    router9: {
      ...providerSettingsFromAdminDefaults(defaults.router9),
      only_mode: defaults.router9.only_mode,
    },
    ocr: { ...defaults.ocr },
    openrouter_http_referer: defaults.openrouter.http_referer ?? '',
    openrouter_x_title: defaults.openrouter.x_title,
    openrouter_reasoning_enabled: defaults.openrouter.reasoning_enabled,
  };
}

function providerSettingsFromAdminDefaults(defaults: SettingsDefaults['openrouter'] | SettingsDefaults['nvidia'] | SettingsDefaults['ollama'] | SettingsDefaults['openai_compat'] | SettingsDefaults['router9']) {
  return {
    ...defaultRuntimeSettings.openrouter,
    base_url: defaults.base_url,
    model: defaults.model ?? '',
    scanned_models: defaults.scanned_models,
    allowed_model_ids: defaults.allowed_model_ids,
    last_scanned_at: '',
  };
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
  const providerOrder = orderRenderProviders(settings.default_provider);
  const providerOptions = providerOrder.flatMap((provider) => {
    const providerDefaults = defaults?.[provider];
    const ids = modelIdsForProvider(providerDefaults, settings[provider].model, defaults, provider);
    const exactModelOptions = ids.map((modelId) => {
      const model = providerDefaults?.scanned_models.find((item) => item.id === modelId);
      return {
        key: `model:${provider}:${modelId}`,
        provider,
        modelId,
        label: `${renderProviderLabel(provider)}: ${model?.label ?? modelId}`,
        description: `${renderProviderLabel(provider)} model ${modelId}${model?.context_length ? ` — context ${model.context_length}` : ''}`,
      };
    });
    const canUseProviderDefault = Boolean(providerDefaults?.model || providerDefaults?.allowed_model_ids.length || providerDefaults?.scanned_models.length || settings[provider].model);
    const defaultOption = canUseProviderDefault
      ? [{
          key: `default:${provider}`,
          provider,
          label: `${renderProviderLabel(provider)} mặc định`,
          description: `Dùng provider ${renderProviderLabel(provider)} với model mặc định do admin cấu hình.`,
        }]
      : [];
    return [...defaultOption, ...exactModelOptions];
  });

  if (defaults?.router9.only_mode) {
    const router9Options = providerOptions.filter((option) => option.provider === 'router9');
    return router9Options.length > 0
      ? [
          { key: 'default:auto', provider: 'auto', label: 'Mặc định hệ thống (9router)', description: '9router-only đang bật, backend tự chọn model 9router được phép.' },
          ...router9Options,
        ]
      : [];
  }

  return [
    { key: 'default:auto', provider: 'auto', label: 'Mặc định hệ thống', description: 'Tự động dùng provider/model và fallback do admin cấu hình.' },
    ...providerOptions,
  ];
}

type RenderProviderKey = 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat' | 'router9';

function orderRenderProviders(defaultProvider: RuntimeSettings['default_provider']): RenderProviderKey[] {
  const providers = ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const;
  const normalized = normalizeRenderProvider(defaultProvider);
  if (!normalized) {
    return [...providers];
  }
  return [normalized, ...providers.filter((provider) => provider !== normalized)];
}

function normalizeRenderProvider(provider: RuntimeSettings['default_provider']): RenderProviderKey | null {
  if (!provider || provider === 'auto' || provider === 'mock' || provider === 'openrouter_gpt_oss' || provider === 'opencode_nemotron') return null;
  if (provider === 'ollama_gpt_oss') return 'ollama';
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') return provider;
  return null;
}

function modelIdsForProvider(providerDefaults: SettingsDefaults['openrouter'] | SettingsDefaults['nvidia'] | SettingsDefaults['ollama'] | SettingsDefaults['openai_compat'] | SettingsDefaults['router9'] | undefined, currentModel: string, defaults: SettingsDefaults | null | undefined, providerId: string) {
  const ids: string[] = [];
  const add = (modelId: string | null | undefined) => {
    const id = String(modelId ?? '').trim();
    if (id && !ids.includes(id)) ids.push(id);
  };
  const registryModels = defaults?.registry_models?.filter((model) => model.provider_id === providerId && model.enabled) ?? [];
  if (registryModels.length > 0) {
    const visibleModels = registryModels.some((model) => model.allowed) ? registryModels.filter((model) => model.allowed) : registryModels;
    visibleModels.forEach((model) => add(model.id));
    providerDefaults?.allowed_model_ids.forEach(add);
    add(providerDefaults?.model);
    add(currentModel);
    return ids;
  }
  if (!providerDefaults) {
    add(currentModel);
    return ids;
  }
  if (providerDefaults.allowed_model_ids.length > 0) providerDefaults.allowed_model_ids.forEach(add);
  else add(providerDefaults.model);
  add(currentModel);
  return ids;
}

function providerLabel(provider: 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat') {
  if (provider === 'openrouter') return 'OpenRouter';
  if (provider === 'nvidia') return 'NVIDIA';
  if (provider === 'openai_compat') return 'OpenAI-Compatible';
  return 'Ollama';
}

function renderProviderLabel(provider: RenderProviderKey) {
  if (provider === 'router9') return '9router';
  return providerLabel(provider);
}
