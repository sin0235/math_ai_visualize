import { useEffect, useMemo, useRef, useState } from 'react';
import { AdminConsole } from './components/admin/AdminConsole';
import { ApiError, changePassword, deleteRenderHistory, forgotPassword, getCurrentUser, getHealth, getRenderHistory, getRenderHistoryDetail, getSessions, getSettingsDefaults, getUserSettings, login, loginWithGoogle, logout, ocrImage, register, renderEditedScene, renderProblem, resendVerification, resetPassword, revokeOtherSessions, revokeSession, saveUserSettings, updateProfile, verifyEmail, type AdminRenderHistoryDetail, type RenderHistoryItem, type SessionResponse, type UserResponse } from './api/client';
import { defaultAdvancedSettings, ProblemInput, type ModelOption } from './components/ProblemInput';
import { GeneralSettingsPanel } from './components/GeneralSettingsPanel';
import { AccountPage } from './components/AccountPage';
import { FeedbackPage } from './components/FeedbackPage';
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
import { ExportMenuItems } from './components/ExportMenu';
import { ProblemVariantTool } from './components/DiagramTools';
import { normalizeMineruBaseUrl } from './api/mineru';
import { getDefaultParamValues, patchGeogebraCommandsForScene, recomputeSceneWithParameters, recomputeThreeScene } from './utils/sceneParameters';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, SETTINGS_STORAGE_VERSION, type OcrProvider, type RuntimeSettings, type SettingsDefaults, type UserBasicSettings } from './types/settings';
import { inferOcrProviderFromModelId } from './utils/settingsOptions';
import logoUrl from '../img.svg';
import './styles.css';

const SETTINGS_STORAGE_KEY = 'hinh-runtime-settings';
const MOBILE_WARNING_STORAGE_KEY = 'hinh-mobile-warning-dismissed';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 900px)';
const DEVELOPER_GITHUB_URL = 'https://github.com/sin0235';
const CONTACT_EMAIL = 'support@sin-studio.tech';
const PDF_WORD_ENABLED = parseEnvFlag(import.meta.env.VITE_PDF_WORD_ENABLED);
const MINERU_API_BASE_URL = normalizeMineruBaseUrl(import.meta.env.VITE_MINERU_API_BASE_URL);

type AppView = 'home' | 'render' | 'analyzer' | 'analyzer-guide' | 'simulation' | 'geogebra-lab' | 'pdf-to-word' | 'history' | 'guide' | 'about' | 'privacy-policy' | 'terms' | 'login' | 'settings' | 'admin' | 'account' | 'feedback' | 'reset-password' | 'verify-email';
type EditTool = 'move' | 'connect' | 'project_to_segment' | 'add_point';
type Vec3 = { x: number; y: number; z: number };
type Notification = {
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
  settings: '/settings',
  admin: '/admin',
  account: '/account',
  feedback: '/feedback',
  'reset-password': '/reset-password',
  'verify-email': '/verify-email',
};

function pathToView(pathname: string): AppView {
  const normalized = pathname.replace(/\/+$/, '') || '/';
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
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsDefaults | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'checking' });
  const [notifications, setNotifications] = useState<Notification[]>([]);
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
  const [remoteSettingsHydrated, setRemoteSettingsHydrated] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [toolsMenuOpen, setToolsMenuOpen] = useState(false);
  const resultAnchorRef = useRef<HTMLDivElement | null>(null);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);
  const toolsMenuRef = useRef<HTMLDivElement | null>(null);
  const renderToolsMenuRef = useRef<HTMLDivElement | null>(null);
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
    try {
      const saved = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (!saved) return;
      setRuntimeSettings(loadStoredSettings(saved));
    } catch {
      // Keep defaults when local storage is invalid.
    }
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
    if (!settingsDefaults || !remoteSettingsHydrated) return;
    setRuntimeSettings((current) => mergeBackendDefaults(current, settingsDefaults));
  }, [settingsDefaults, remoteSettingsHydrated]);

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
      saveUserSettings(toUserBasicSettings(runtimeSettings)).catch(() => undefined);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [runtimeSettings, user, remoteSettingsHydrated]);

  useEffect(() => {
    if (notifications.length === 0) return;
    const timers = notifications.map((item) => window.setTimeout(() => dismissNotification(item.id), 10000));
    return () => timers.forEach(window.clearTimeout);
  }, [notifications]);

  useEffect(() => {
    setEditorButtonTop(clamp(window.innerHeight * 0.55, 84, window.innerHeight - 88));
  }, []);

  useEffect(() => {
    if (sidebarTool !== 'solver') setHighlightedObjects([]);
  }, [sidebarTool]);

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
    preferredAiProvider?: string,
    preferredAiModel?: string,
    advancedSettings?: AdvancedRenderSettings,
    preferredRenderer?: Renderer,
    mode: 'problem' | 'diagram' = 'problem',
  ) {
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

    setOcrLoading(true);
    try {
      const imageDataUrl = await fileToDataUrl(file);
      const response = await ocrImage(imageDataUrl, runtimeSettings, mode);
      const nextProblemText = response.text.trim();
      setProblemText(nextProblemText);
      if (nextProblemText) {
        await handleSubmit(nextProblemText, preferredAiProvider, preferredAiModel, advancedSettings, preferredRenderer);
      }
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

  function clearSessionState() {
    setUser(null);
    setHistoryItems([]);
    setHistoryOpen(false);
    setAccountMenuOpen(false);
    setRemoteSettingsHydrated(true);
  }

  async function applyAuthenticatedUser(nextUser: UserResponse) {
    setRemoteSettingsHydrated(false);
    setUser(nextUser);
    await loadRemoteWorkspace(nextUser);
  }

  function applyAuthenticatedUserInBackground(nextUser: UserResponse) {
    setRemoteSettingsHydrated(false);
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
    try {
      const [remoteSettings] = await Promise.all([
        getUserSettings().catch(() => null),
        refreshHistory(),
      ]);
      const savedSettings = remoteSettings?.settings;
      if (savedSettings) {
        setRuntimeSettings((current) => loadRemoteSettings(savedSettings, current));
      } else {
        await saveUserSettings(toUserBasicSettings(runtimeSettings));
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
        { type: 'segment', points: [start, end], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
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
        { type: 'segment', points: [pointToSegmentSource, newName], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
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
                  if (PDF_WORD_ENABLED) {
                    navigateTo('pdf-to-word');
                    return;
                  }
                  showNotification(
                    'PDF → Word chuẩn đề trắc nghiệm',
                    'Chức năng này đang tắt bằng feature flag. Bật VITE_PDF_WORD_ENABLED và cấu hình VITE_MINERU_API_BASE_URL để dùng demo.',
                    ['Khi chưa bật demo, hãy gửi mail để được hỗ trợ cài đặt miễn phí.', CONTACT_EMAIL],
                    'info',
                    { label: 'Chuyển tới Mail', href: `mailto:${CONTACT_EMAIL}?subject=Hỗ trợ cài đặt PDF sang Word&body=Em/chào bạn,%0D%0A%0D%0AMình cần hỗ trợ cài đặt chức năng PDF sang Word chuẩn cấu trúc đề trắc nghiệm.%0D%0A%0D%0AThông tin liên hệ:%0D%0A- Zalo:%0D%0A- Email/Facebook:%0D%0A%0D%0AXin cảm ơn.` },
                  );
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
              <button type="button" className={`account-menu-trigger ${activeView === 'history' || activeView === 'settings' || activeView === 'account' || activeView === 'feedback' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen((open) => !open)}>
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
                      navigateTo('settings');
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10.91 3H11a2 2 0 1 1 4 0h.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0A1.65 1.65 0 0 0 21 10.91V11a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                      Cài đặt chung
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
      {activeView === 'render' && <MobileRendererWarning dismissed={mobileWarningDismissed} onDismiss={dismissMobileWarning} />}

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
                    modelOptions={modelOptions}
                    router9Only={settingsDefaults?.router9.only_mode ?? false}
                    onProblemTextChange={setProblemText}
                    onOcrImage={handleOcrImage}
                    onOcrClipboardImage={handleOcrClipboardImage}
                    onOpenRouter9Settings={() => navigateTo(user?.role === 'admin' ? 'admin' : 'settings')}
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
                <RendererPanel result={effectiveResult} threeInteraction={threeInteraction} onGeoGebraPointChange={handlePointDragEnd} highlightedObjects={highlightedObjects} saving={editorSaving} onThreeImageCaptureReady={(capture) => setThreeImageCapture(() => capture)} />
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
            {/* Lựa chọn 1: Khảo sát hàm số (chỉ khi có function_graph) */}
            {effectiveResult?.scene && effectiveResult.scene.topic === 'function_graph' && (
              <div className="result-area">
                <FunctionAnalyzerPanel
                  initialExpression={
                    (() => {
                      const fg = effectiveResult.scene.objects.find((o: { type: string }) => o.type === 'function_graph') as { expression?: string } | undefined;
                      return fg?.expression ?? '';
                    })()
                  }
                  onOpenGuide={() => navigateTo('analyzer-guide')}
                />
              </div>
            )}
          </section>
        )}
        {activeView === 'analyzer' && (
          <div className="analyzer-standalone-wrap">
            <FunctionAnalyzerPanel onOpenGuide={() => navigateTo('analyzer-guide')} />
          </div>
        )}
        {activeView === 'simulation' && <CalculusSimulationPage />}
        {activeView === 'geogebra-lab' && <GeoGebraLabPage />}
        {activeView === 'pdf-to-word' && (
          <PdfToWordPage
            enabled={PDF_WORD_ENABLED}
            apiBaseUrl={MINERU_API_BASE_URL}
            modelOptions={modelOptions}
            runtimeSettings={runtimeSettings}
            router9Only={settingsDefaults?.router9.only_mode ?? false}
            onOpenSettings={() => navigateTo(user?.role === 'admin' ? 'admin' : 'settings')}
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
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                  </FooterNavIcon>
                }
              >
                Góp ý
              </FooterNavButton>
              <FooterNavButton
                onClick={() => showNotification('Báo lỗi', 'Kênh GitHub issue sẽ được bổ sung khi repository public.', [], 'info')}
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

function AccessDeniedPage({ user, onHome, onLogin }: { user: UserResponse | null; onHome: () => void; onLogin: () => void }) {
  return (
    <section className="product-page-card">
      <span className="home-eyebrow">Không thể mở trang</span>
      <h2>Bạn không có quyền truy cập khu vực này.</h2>
      <p>{user ? 'Tài khoản hiện tại không có quyền sử dụng trang này.' : 'Vui lòng đăng nhập bằng tài khoản được cấp quyền để tiếp tục.'}</p>
      <div className="home-actions">
        <button type="button" onClick={onHome}>Về trang chủ</button>
        {!user && <button type="button" className="secondary-button" onClick={onLogin}>Đăng nhập</button>}
      </div>
    </section>
  );
}

function GuidePage({ onOpenAnalyzerGuide }: { onOpenAnalyzerGuide: () => void }) {
  const guideSteps = [
    { title: 'Nhập đề bài', text: 'Gõ đề hình học tiếng Việt, dán dữ liệu tọa độ hoặc kéo thả ảnh đề bài vào khu vực OCR.' },
    { title: 'Chọn cách hiển thị', text: 'Dùng GeoGebra cho Oxy, đồ thị hàm số; dùng Three.js cho hình học không gian hoặc mô hình 3D.' },
    { title: 'Dựng hình', text: 'Hệ thống chuyển đề bài thành hình có cấu trúc để bạn kiểm tra trực quan.' },
    { title: 'Tinh chỉnh', text: 'Kéo điểm, chỉnh scene hoặc dựng lại bằng mô tả rõ hơn khi hình chưa đúng ý.' },
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
          <h3>Thử nhanh với ví dụ này</h3>
          <p>Trong mặt phẳng Oxy, cho A(0,0), B(4,0), C(1,3). Dựng tam giác ABC, vẽ đường cao từ C xuống AB và ghi tên chân đường cao H.</p>
        </section>
        <section>
          <h3>Mẹo viết đề bài</h3>
          <ul>
            {promptTips.map((tip) => <li key={tip}>{tip}</li>)}
          </ul>
        </section>
        <section className="guide-renderer-section">
          <h3>Khi nào dùng renderer nào?</h3>
          <div className="guide-renderer-grid">
            <article>
              <h4>GeoGebra 2D</h4>
              <p>Phù hợp cho bài toán trên mặt phẳng Oxy: đồ thị hàm số, đường thẳng, đường tròn, tam giác, tứ giác và các quan hệ đồng quy - song song - vuông góc.</p>
              <ul>
                <li>Dùng khi đề chỉ có tọa độ 2D hoặc ký hiệu nằm trên mặt phẳng.</li>
                <li>Thích hợp để khảo sát hàm số, xem giao điểm, cực trị và tiệm cận.</li>
                <li>Nên chọn nếu bạn cần hình rõ, nhanh và dễ chỉnh các điểm phẳng.</li>
              </ul>
            </article>
            <article>
              <h4>GeoGebra 3D / Three.js</h4>
              <p>Phù hợp cho bài toán không gian Oxyz: khối đa diện, mặt phẳng, đường thẳng chéo nhau, giao tuyến, khoảng cách và góc trong không gian.</p>
              <ul>
                <li>Dùng khi đề có tọa độ 3D, mặt phẳng (P), đường thẳng d hoặc hình chóp/lăng trụ.</li>
                <li>Hữu ích khi cần xoay góc nhìn để kiểm tra quan hệ hình học khó thấy ở 2D.</li>
                <li>Nên chọn Three.js khi muốn thao tác trực quan mạnh hơn với mô hình 3D.</li>
              </ul>
            </article>
          </div>
          <button type="button" className="guide-analyzer-label" onClick={onOpenAnalyzerGuide}>
            <span>Hướng dẫn khảo sát hàm số</span>
            <span className="guide-analyzer-label-arrow" aria-hidden="true">→</span>
          </button>
        </section>
      </div>
    </section>
  );
}

function AnalyzerGuidePage({ onOpenGeneralGuide }: { onOpenGeneralGuide: () => void }) {
  const formulaGroups = [
    {
      title: 'Toán tử cơ bản',
      rows: [
        { raw: '2*x, x*(x-1)', tex: '2x,\\; x(x-1)', note: 'Dùng * để nhân tường minh.' },
        { raw: '(x^2-1)/(x-2)', tex: '\\frac{x^2-1}{x-2}' },
        { raw: 'x^3 - 3*x + 2', tex: 'x^3-3x+2', note: 'Lũy thừa dùng dấu ^.' },
        { raw: 'pi, E', tex: '\\pi,\\; e' },
      ],
    },
    {
      title: 'Hàm thường gặp',
      rows: [
        { raw: 'sqrt(x^2+1), abs(x)', tex: '\\sqrt{x^2+1},\\; |x|' },
        { raw: 'exp(x), ln(x), log(x)', tex: 'e^x,\\; \\ln(x),\\; \\ln(x)' },
        { raw: 'log(x,2), log(x,10)', tex: '\\log_2(x),\\; \\log_{10}(x)', note: 'Log cơ số bất kỳ: log(x,a).' },
        { raw: 'sin(x), cos(x), tan(x)', tex: '\\sin(x),\\; \\cos(x),\\; \\tan(x)' },
        { raw: 'asin(x), acos(x), atan(x)', tex: '\\arcsin(x),\\; \\arccos(x),\\; \\arctan(x)' },
        { raw: 'sinh(x), cosh(x), tanh(x)', tex: '\\sinh(x),\\; \\cosh(x),\\; \\tanh(x)' },
      ],
    },
    {
      title: 'Hàm hỗ trợ',
      rows: [
        { raw: 'floor(x), ceil(x)', tex: '\\lfloor x \\rfloor,\\; \\lceil x \\rceil' },
        { raw: 'sign(x), Min(a,b), Max(a,b)', tex: '\\operatorname{sign}(x),\\; \\min(a,b),\\; \\max(a,b)' },
        { raw: 'Piecewise((x^2, x<0), (x, x>=0))', tex: '\\begin{cases}x^2,&x<0\\\\x,&x\\ge 0\\end{cases}' },
      ],
    },
  ];

  return (
    <section className="analyzer-guide-page">
      <div className="analyzer-guide-hero">
        <div className="analyzer-guide-hero-head">
          <h2>Hướng dẫn chi tiết cách nhập công thức và dùng OCR</h2>
          <button type="button" className="analyzer-guide-label" onClick={onOpenGeneralGuide}>
            <span>Hướng dẫn vẽ hình</span>
            <span className="analyzer-guide-label-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <div className="analyzer-guide-grid">
        {formulaGroups.map((group) => (
          <article key={group.title} className="analyzer-guide-card">
            <h3>{group.title}</h3>
            <div className="analyzer-guide-table">
              {group.rows.map((row) => (
                <div key={row.raw} className="analyzer-guide-row">
                  <code>{row.raw}</code>
                  <KatexSpan tex={row.tex} className="analyzer-guide-katex" />
                  {row.note && <p>{row.note}</p>}
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="analyzer-guide-ocr">
        <article>
          <h3>OCR từ clipboard (dán ảnh)</h3>
          <ol>
            <li>Chụp/copy ảnh đề vào clipboard.</li>
            <li>Tại ô nhập hàm, bấm chuột phải để kích hoạt đọc ảnh từ clipboard.</li>
            <li>Nếu không có ảnh trong clipboard, hệ thống tự mở hộp chọn tệp ảnh.</li>
          </ol>
        </article>
        <article>
          <h3>OCR từ tệp ảnh</h3>
          <ol>
            <li>Bấm nút đính kèm ảnh (icon kẹp giấy) cạnh ô nhập.</li>
            <li>Chọn ảnh từ máy hoặc camera điện thoại.</li>
            <li>Kiểm tra lại biểu thức sau OCR rồi bấm “Phân tích”.</li>
          </ol>
        </article>
      </div>
    </section>
  );
}


function AboutPage({ onStart, onGuide }: { onStart: () => void; onGuide: () => void }) {
  const features = [
    { title: 'Kiến trúc Phân tích & Suy luận', text: 'Quy trình xử lý đa tầng: Hệ thống phân tích giả thiết (Reasoning) trước khi thực thi lệnh vẽ, giúp tối ưu hóa độ chính xác và giảm thiểu sai sót hình học.' },
    { title: 'Tương tác Đồ họa Đa nền tảng', text: 'Kết hợp sức mạnh của GeoGebra cho toán học phẳng và Three.js cho mô phỏng không gian 3D, mang lại trải nghiệm tương tác mượt mà và trực quan.' },
    { title: 'Cấu trúc Scene JSON Linh hoạt', text: 'Hình vẽ không chỉ là ảnh tĩnh mà là một thực thể có cấu trúc (Scene-as-Code), cho phép người dùng can thiệp, kéo thả và tinh chỉnh từng đối tượng.' },
  ];

  return (
    <section className="about-page">
      <div className="about-hero">
        <span className="home-eyebrow">Về dự án</span>
        <h2>Số hóa hình học với độ chính xác tuyệt đối.</h2>
        <p>AI Math Renderer là một nền tảng tiên phong kết hợp giữa Trí tuệ nhân tạo và các công cụ tính toán hình học (CAS). Chúng tôi hướng tới việc đơn giản hóa quy trình xây dựng học liệu toán học, giúp giáo viên và học sinh tiết kiệm hàng giờ làm việc thủ công.</p>
        <div className="home-actions">
          <button type="button" onClick={onStart}>Truy cập Workspace</button>
          <button type="button" className="secondary-button" onClick={onGuide}>Tài liệu hướng dẫn</button>
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
          <span>Triết lý phát triển</span>
          <h3>Trợ lý kỹ thuật đắc lực, không chỉ là công cụ vẽ hình.</h3>
        </div>
        <p>Áp dụng tư duy <strong>"Infrastructure as Code"</strong> vào toán học, chúng tôi biến các đề bài trừu tượng thành dữ liệu có cấu trúc. AI đóng vai trò là một cộng tác viên thông minh, giúp bạn hiện thực hóa các ý tưởng hình học, khảo sát đồ thị phức tạp và kiểm chứng các giả thiết toán học một cách khoa học nhất.</p>
      </section>
    </section>
  );
}


function HistoryPage({ user, items, loading, openingId, onOpen, onDelete, onLogin, onWorkspace }: { user: UserResponse | null; items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void; onLogin: () => void; onWorkspace: () => void }) {
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
          <span className="home-eyebrow">Lịch sử workspace</span>
          <h2>Lịch sử dựng hình của bạn</h2>
          <p>Mở lại đề bài, scene và renderer đã lưu từ các lần render trước.</p>
        </div>
        <button type="button" onClick={onWorkspace}>Dựng hình mới</button>
      </div>
      <HistoryPanel items={items} loading={loading} openingId={openingId} onOpen={onOpen} onDelete={onDelete} />
    </section>
  );
}


function MetricCard({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <article className="admin-metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString('vi-VN')}{suffix}</strong>
    </article>
  );
}

function HistoryPanel({ items, loading, openingId, onOpen, onDelete }: { items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  return (
    <section className="history-panel">
      <div className="history-panel-header">
        <strong>Lịch sử dựng hình</strong>
        <span>{loading ? 'Đang tải...' : `${items.length} mục`}</span>
      </div>
      {items.length === 0 ? (
        <p>Các lượt render mới sau khi đăng nhập sẽ được lưu vào hệ thống.</p>
      ) : (
        <div className="history-list">
          {items.map((item) => {
            const opening = openingId === item.id;
            return (
              <article className={`history-item${opening ? ' opening' : ''}`} key={item.id}>
                <button type="button" onClick={() => onOpen(item.id)} disabled={opening} aria-busy={opening}>
                  <span className="history-item-copy">
                    <strong>{item.problem_text}</strong>
                    <span>{formatHistoryDate(item.created_at)} · {historySourceLabel(item.source_type)}{item.renderer ? ` · ${item.renderer}` : ''}{item.model ? ` · ${item.model}` : ''}</span>
                  </span>
                  {opening && <span className="history-opening-indicator" aria-hidden="true"><span className="sp-spinner" /></span>}
                </button>
                <button type="button" className="history-delete" onClick={() => onDelete(item.id)} disabled={opening} aria-label="Xoá lịch sử">×</button>
              </article>
            );
          })}
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
    <aside className="mobile-renderer-warning" role="status" aria-live="polite">
      <strong>Lưu ý khi dùng điện thoại</strong>
      <span>Math renderer hiển thị tốt nhất trên desktop. Trên di động, hãy lướt xuống sau khi dựng hình để xem kết quả.</span>
      <button type="button" onClick={onDismiss}>Bỏ qua</button>
    </aside>
  );
}

function NotificationStack({ notifications, onDismiss }: { notifications: Notification[]; onDismiss: (id: number) => void }) {
  if (notifications.length === 0) return null;
  return (
    <div className="notification-stack" role="region" aria-label="Thông báo" aria-live="polite">
      {notifications.map((notification) => (
        <section className={`notification-card ${notification.kind}`} key={notification.id} role="status">
          <div className="notification-header">
            <strong>{notification.title}</strong>
            <button type="button" className="notification-close" onClick={() => onDismiss(notification.id)} aria-label="Đóng thông báo">×</button>
          </div>
          <p>{notification.message}</p>
          {notification.action && (
            notification.action.href ? (
              <a className="notification-action" href={notification.action.href}>{notification.action.label}</a>
            ) : (
              <button type="button" className="notification-action" onClick={notification.action.onClick}>{notification.action.label}</button>
            )
          )}
          {notification.details.length > 0 && (
            <details className="notification-details">
              <summary>Chi tiết và hướng dẫn</summary>
              <ul>
                {notification.details.map((detail) => <li key={detail}>{detail}</li>)}
              </ul>
            </details>
          )}
        </section>
      ))}
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

function mergeBackendDefaults(current: RuntimeSettings, defaults: SettingsDefaults): RuntimeSettings {
  const openrouter = mergeProviderDefaults(current.openrouter, defaults.openrouter, 'openrouter');
  const nvidia = mergeProviderDefaults(current.nvidia, defaults.nvidia, 'nvidia');
  const ollama = mergeProviderDefaults(current.ollama, defaults.ollama, 'ollama');
  const openai_compat = mergeProviderDefaults(current.openai_compat, defaults.openai_compat, 'openai_compat');
  const router9 = mergeProviderDefaults(current.router9, defaults.router9, 'router9');
  const userWantsSystemOcrProvider = !String(current.ocr.provider ?? '').trim();
  const ocrProviderFromChoice = (current.ocr.provider || defaults.ocr.provider || 'openrouter') as OcrProvider;
  const ocrModel =
    current.ocr.model ||
    defaultOcrModelFromMergedDefaults(ocrProviderFromChoice, defaults, { openrouter, nvidia, ollama, openai_compat, router9 });
  const inferred = inferOcrProviderFromModelId(ocrModel);
  const rawModel = ocrModel.trim();
  const ocrProviderEffective =
    ocrProviderFromChoice === 'openrouter' && inferred === 'router9' && !rawModel.startsWith('openrouter/')
      ? 'router9'
      : ocrProviderFromChoice === 'router9' && inferred === 'openrouter'
        ? 'openrouter'
        : ocrProviderFromChoice;
  const ocrProviderStored = userWantsSystemOcrProvider ? '' : ocrProviderEffective;

  return {
    ...current,
    default_provider: current.default_provider === 'auto' && defaults.default_provider ? defaults.default_provider : current.default_provider,
    openrouter,
    nvidia,
    ollama,
    openai_compat,
    router9: {
      ...router9,
      only_mode: current.router9.only_mode || defaults.router9.only_mode,
    },
    ocr: {
      ...current.ocr,
      provider: ocrProviderStored,
      model: ocrModel,
      max_image_mb: current.ocr.max_image_mb || defaults.ocr.max_image_mb,
    },
  };
}

function defaultOcrModelFromMergedDefaults(
  provider: OcrProvider,
  defaults: SettingsDefaults,
  merged: Pick<RuntimeSettings, 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat' | 'router9'>,
): string {
  if (defaults.ocr.provider === provider && defaults.ocr.model) return defaults.ocr.model;
  if (provider === 'openrouter') return defaults.openrouter.vision_model || merged.openrouter.model || '';
  return merged[provider].model || defaults[provider].allowed_model_ids[0] || defaults[provider].scanned_models[0]?.id || '';
}

function mergeProviderDefaults<Provider extends 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat' | 'router9'>(
  current: RuntimeSettings[Provider],
  defaults: SettingsDefaults[Provider],
  provider: Provider,
): RuntimeSettings[Provider] {
  const allowlist = defaults.allowed_model_ids.length > 0 ? defaults.allowed_model_ids : [defaults.model ?? ''].filter(Boolean);
  const allowed_model_ids = allowlist;
  const defaultModel = defaults.model && (!allowed_model_ids.length || allowed_model_ids.includes(defaults.model))
    ? defaults.model
    : allowed_model_ids[0] || '';
  const model = current.model && (!allowed_model_ids.length || allowed_model_ids.includes(current.model))
    ? current.model
    : defaultModel;
  const scanned_models = mergeScannedModels(
    defaults.scanned_models.filter((item) => !allowed_model_ids.length || allowed_model_ids.includes(item.id)),
    allowed_model_ids.map((id) => ({ id, label: id, provider }))
  );

  return {
    ...current,
    base_url: current.base_url || defaults.base_url || '',
    model,
    allowed_model_ids,
    scanned_models,
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

function parseEnvFlag(value: string | boolean | undefined) {
  if (typeof value === 'boolean') return value;
  const normalized = (value ?? '').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(normalized);
}

function loadStoredSettings(saved: string): RuntimeSettings {
  const parsed = JSON.parse(saved) as { version?: number; settings?: Partial<RuntimeSettings> } & Partial<RuntimeSettings>;
  const next = mergeRuntimeSettingsShape(parsed.settings ?? parsed);

  if ((parsed.version ?? 0) < 5 && next.ocr.provider === 'openrouter' && !next.ocr.model.trim()) {
    next.ocr.provider = '';
  }

  if (parsed.version !== SETTINGS_STORAGE_VERSION) {
    dropLegacyDefaults(next);
  }
  dropLegacyOcrDefaults(next);

  return dropApiKeys(next);
}

function loadRemoteSettings(settings: UserBasicSettings, current: RuntimeSettings): RuntimeSettings {
  const next = { ...current, default_provider: settings.default_provider, ocr: { ...current.ocr, ...settings.ocr } };
  const provider = settings.default_provider;
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') {
    return dropApiKeys({ ...next, [provider]: { ...next[provider], model: settings.default_model } });
  }
  return dropApiKeys(next);
}

function toUserBasicSettings(settings: RuntimeSettings): UserBasicSettings {
  return {
    version: 2,
    default_provider: settings.default_provider,
    default_model: currentProviderModel(settings),
    ocr: settings.ocr,
  };
}

function currentProviderModel(settings: RuntimeSettings) {
  const provider = settings.default_provider;
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') return settings[provider].model;
  return '';
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
    openrouter: { ...defaultRuntimeSettings.openrouter, model: settings.openrouter.model, allowed_model_ids: settings.openrouter.allowed_model_ids },
    nvidia: { ...defaultRuntimeSettings.nvidia, model: settings.nvidia.model, allowed_model_ids: settings.nvidia.allowed_model_ids },
    ollama: { ...defaultRuntimeSettings.ollama, model: settings.ollama.model, allowed_model_ids: settings.ollama.allowed_model_ids },
    openai_compat: { ...defaultRuntimeSettings.openai_compat, model: settings.openai_compat.model, allowed_model_ids: settings.openai_compat.allowed_model_ids },
    router9: { ...defaultRuntimeSettings.router9, model: settings.router9.model, allowed_model_ids: settings.router9.allowed_model_ids },
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
  const providerOptions = (['openrouter', 'nvidia', 'ollama', 'openai_compat'] as const).flatMap((provider) => {
    const providerDefaults = defaults?.[provider];
    const ids = modelIdsForProvider(providerDefaults, settings[provider].model, defaults, provider);
    return ids.map((modelId) => {
      const model = providerDefaults?.scanned_models.find((item) => item.id === modelId);
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
  const router9Ids = modelIdsForProvider(router9Defaults, settings.router9.model, defaults, 'router9');
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

  return [{ key: 'provider:auto', provider: 'auto', label: 'Tự động chọn mô hình phù hợp', description: 'Tự động dùng provider/model do admin cấu hình.' }, ...providerOptions, ...router9Options];
}

function modelIdsForProvider(providerDefaults: SettingsDefaults['openrouter'] | SettingsDefaults['nvidia'] | SettingsDefaults['ollama'] | SettingsDefaults['openai_compat'] | SettingsDefaults['router9'] | undefined, currentModel: string, defaults: SettingsDefaults | null | undefined, providerId: string) {
  const registryModels = defaults?.registry_models?.filter((model) => model.provider_id === providerId && model.enabled) ?? [];
  if (registryModels.length > 0) {
    const visibleModels = registryModels.some((model) => model.allowed) ? registryModels.filter((model) => model.allowed) : registryModels;
    return visibleModels.map((model) => model.id);
  }
  if (!providerDefaults) return [currentModel].filter(Boolean) as string[];
  if (providerDefaults.allowed_model_ids.length > 0) return providerDefaults.allowed_model_ids;
  return [providerDefaults.model].filter(Boolean) as string[];
}

function providerLabel(provider: 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat') {
  if (provider === 'openrouter') return 'OpenRouter';
  if (provider === 'nvidia') return 'NVIDIA';
  if (provider === 'openai_compat') return 'OpenAI-Compatible';
  return 'Ollama';
}
