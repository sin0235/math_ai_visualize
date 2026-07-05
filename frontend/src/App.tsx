import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, changePassword, deleteRenderHistory, forgotPassword, getCurrentUser, getHealth, getLearningProfile, getRenderHistory, getRenderHistoryDetail, getSessions, getSettingsDefaults, login, loginWithGoogle, logout, ocrImageByUploadId, patchRenderHistory, register, renderEditedScene, renderProblem, resendVerification, resetPassword, revokeOtherSessions, revokeSession, updateLearningProfile, updateProfile, uploadOcrImage, verifyEmail, type AdminRenderHistoryDetail, type RenderHistoryItem, type SessionResponse, type UserLearningProfileResponse, type UserLearningProfileUpdateRequest, type UserResponse } from './api/client';
import { defaultAdvancedSettings, ProblemInput, type TierKey } from './components/ProblemInput';
import { AccountPage } from './components/AccountPage';
import { SettingsPage } from './components/SettingsPage';
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
import { AboutPage, AccessDeniedPage, AnalyzerGuidePage, GuidePage, HistoryPage, HistoryPanel, MobileRendererWarning, isGeometryMobileWarningView } from './components/AppPages';
import { NotificationStack } from './components/NotificationStack';
import { useNotifications } from './hooks/useNotifications';
import { ExportMenuItems } from './components/ExportMenu';
import { ProblemVariantTool } from './components/DiagramTools';
import { normalizeMineruBaseUrl } from './api/mineru';
import { getDefaultParamValues, patchGeogebraCommandsForScene, recomputeSceneWithParameters, recomputeThreeScene } from './utils/sceneParameters';
import { clamp, findPoint, hasSegment, nextPointName, projectPointToLine, round, type Vec3 } from './utils/sceneEditing';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, type RuntimeSettings, type SettingsDefaults } from './types/settings';
import logoUrl from '../img.svg';
import './styles.css';

const AdminConsole = lazy(() => import('./components/admin/AdminConsole').then((module) => ({ default: module.AdminConsole })));
const FunctionAnalyzerPanel = lazy(() => import('./components/FunctionAnalyzerPanel').then((module) => ({ default: module.FunctionAnalyzerPanel })));
const AlgebraSolverPage = lazy(() => import('./components/AlgebraSolverPage').then((module) => ({ default: module.AlgebraSolverPage })));
const CalculusSimulationPage = lazy(() => import('./components/CalculusSimulationPage').then((module) => ({ default: module.CalculusSimulationPage })));
const GeoGebraLabPage = lazy(() => import('./components/GeoGebraLabPage').then((module) => ({ default: module.GeoGebraLabPage })));
const PdfToWordPage = lazy(() => import('./components/PdfToWordPage').then((module) => ({ default: module.PdfToWordPage })));

const MOBILE_WARNING_STORAGE_KEY = 'hinh-mobile-warning-dismissed';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 900px)';
const DEVELOPER_GITHUB_URL = 'https://github.com/sin0235';
const CONTACT_EMAIL = 'support@sin-studio.tech';
const CONTACT_ZALO_PHONE = '0347952503';
const CONTACT_ZALO_URL = `https://zalo.me/${CONTACT_ZALO_PHONE}`;
const MINERU_API_BASE_URL = normalizeMineruBaseUrl(import.meta.env.VITE_MINERU_API_BASE_URL);

type AppView = 'home' | 'render' | 'analyzer' | 'algebra-solver' | 'analyzer-guide' | 'simulation' | 'geogebra-lab' | 'pdf-to-word' | 'history' | 'guide' | 'about' | 'privacy-policy' | 'terms' | 'login' | 'admin' | 'account' | 'settings' | 'feedback' | 'reset-password' | 'verify-email';
type EditTool = 'move' | 'connect' | 'project_to_segment' | 'add_point';
type BackendStatus = {
  state: 'checking' | 'online' | 'offline';
  appName?: string;
};

type ConfirmationState = {
  fallback_confirmed: boolean;
  assumptions_confirmed: boolean;
  repair_confirmed: boolean;
};

const defaultConfirmation: ConfirmationState = {
  fallback_confirmed: false,
  assumptions_confirmed: false,
  repair_confirmed: false,
};

const viewPaths: Record<AppView, string> = {
  home: '/',
  render: '/render',
  analyzer: '/analyzer',
  'algebra-solver': '/algebra-solver',
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
  settings: '/settings',
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
  const [activeScene, setActiveScene] = useState<MathScene | null>(null);
  const [activeRevision, setActiveRevision] = useState(0);
  const [confirmation, setConfirmation] = useState<ConfirmationState>(defaultConfirmation);
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
  const [learningProfile, setLearningProfile] = useState<UserLearningProfileResponse | null>(null);
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
  const editSaveSeqRef = useRef(0);
  const renderToolsMenuTop = Math.min(Math.max(editorButtonTop - 8, 72), Math.max(72, window.innerHeight - 430));

  function applyRenderResponse(response: RenderResponse, nextConfirmation: ConfirmationState = defaultConfirmation) {
    setResult(response);
    setActiveScene(response.scene);
    setActiveRevision(response.scene.revision ?? 1);
    setConfirmation(nextConfirmation);
  }

  function applyLocalSceneEdit(scene: MathScene) {
    setActiveScene(scene);
    setActiveRevision(scene.revision ?? 1);
    setResult((current) => {
      if (!current) return current;
      let payload = current.payload;
      if (payload.three_scene) {
        payload = { ...payload, three_scene: recomputeThreeScene(payload.three_scene, scene) };
      }
      if (payload.geogebra_commands && payload.geogebra_commands.length > 0) {
        payload = { ...payload, geogebra_commands: patchGeogebraCommandsForScene(payload.geogebra_commands, scene) };
      }
      return { ...current, scene, payload, user_confirmed: false };
    });
  }

  function confirmCurrentScene() {
    setConfirmation({ fallback_confirmed: true, assumptions_confirmed: true, repair_confirmed: true });
  }

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
    renderToolsMenuRef.current?.style.setProperty('--render-tools-floating-top', `${editorButtonTop}px`);
    renderToolsMenuRef.current?.style.setProperty('--render-tools-menu-top', `${renderToolsMenuTop}px`);
  }, [editorButtonTop, renderToolsMenuTop, activeScene]);

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
    setParamValues(getDefaultParamValues(activeScene?.parameters));
  }, [activeScene]);

  // Tạo result đã được recompute theo paramValues. Khi không có parameters, trả result gốc.
  const effectiveResult = useMemo<RenderResponse | null>(() => {
    if (!result || !activeScene) return null;
    const params = activeScene.parameters;
    const baseScene = params && params.length > 0 ? recomputeSceneWithParameters(activeScene, paramValues) : activeScene;
    let payload = result.payload;
    if (payload.three_scene) {
      payload = { ...payload, three_scene: recomputeThreeScene(payload.three_scene, baseScene) };
    }
    if (payload.geogebra_commands && payload.geogebra_commands.length > 0) {
      payload = { ...payload, geogebra_commands: patchGeogebraCommandsForScene(payload.geogebra_commands, baseScene) };
    }
    return { ...result, scene: baseScene, payload, user_confirmed: confirmation.fallback_confirmed && confirmation.assumptions_confirmed && confirmation.repair_confirmed };
  }, [result, activeScene, paramValues, confirmation]);

  const threeInteraction = sceneEditorOpen && effectiveResult?.scene.renderer === 'threejs_3d'
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
        saving: false,
      }
    : undefined;

  // Khi thao tác workspace (render/OCR) thất bại, request có thể fail ở tầng mạng khiến
  // không nhận được response 503 MAINTENANCE_MODE. Endpoint settings/defaults không bị
  // enforce_enabled chặn nên vẫn cho biết trạng thái bảo trì thực tế để báo đúng cho người dùng.
  async function reportWorkspaceError(title: string, apiError: ApiError, fallbackSuggestion: string) {
    try {
      const fresh = await getSettingsDefaults();
      if (fresh.feature_flags?.maintenance_mode) {
        setSettingsDefaults(fresh);
        showNotification(
          'Hệ thống đang bảo trì',
          fresh.feature_flags.maintenance_message || 'Hệ thống đang tạm bảo trì, vui lòng quay lại sau.',
          [],
          'warning',
        );
        return;
      }
    } catch {
      // Không lấy được trạng thái bảo trì thì giữ nguyên thông báo lỗi gốc bên dưới.
    }
    showApiError(title, apiError, fallbackSuggestion);
  }

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
      await reportWorkspaceError('OCR thất bại', apiError, 'Hãy kiểm tra ảnh có rõ chữ không hoặc liên hệ admin kiểm tra cấu hình OCR hệ thống.');
    }
  }

  async function handleOcrImage(file: File) {
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
      const uploaded = await uploadOcrImage(file);
      const response = await ocrImageByUploadId(uploaded.file_id);
      setProblemText(response.text.trim());
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể OCR ảnh đề bài.');
      await reportWorkspaceError('OCR thất bại', apiError, 'Hãy kiểm tra ảnh có rõ chữ không hoặc liên hệ admin kiểm tra cấu hình OCR hệ thống.');
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
      const response = await renderProblem(problemText, tier, advancedSettings, preferredRenderer, runtimeSettings);
      applyRenderResponse(response);
      if (user) void refreshHistory();
      scrollToResultOnMobile();
      if (!shouldShowConfirmationPrompt(response)) showWarnings(response.warnings);
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể dựng hình từ đề bài này.');
      await reportWorkspaceError('Dựng hình thất bại', apiError, 'Hãy thử mức độ chất lượng khác hoặc viết đề bài rõ hơn.');
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
    setLearningProfile(null);
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

  async function handleLogin(email: string, password: string, turnstileToken?: string) {
    setAuthLoading(true);
    try {
      const response = await login(email, password, turnstileToken);
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

  async function handleRegister(email: string, password: string, displayName: string | undefined, acceptPrivacyPolicy: boolean, acceptTerms: boolean, turnstileToken?: string) {
    setAuthLoading(true);
    try {
      const response = await register(email, password, displayName, acceptPrivacyPolicy, acceptTerms, turnstileToken);
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

  async function handleForgotPassword(email: string, turnstileToken?: string) {
    const response = await forgotPassword(email, turnstileToken);
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

  async function handleUpdateLearningProfile(patch: UserLearningProfileUpdateRequest) {
    setLearningProfile(await updateLearningProfile(patch));
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
    await Promise.all([
      refreshHistory(),
      getLearningProfile().then(setLearningProfile).catch(() => setLearningProfile(null)),
    ]);
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
    applyRenderResponse(detail.response ?? buildLegacyHistoryResponse(detail));
    navigateTo('render');
    scrollToResultOnMobile();
  }

  async function openHistoryItem(id: string) {
    setOpeningHistoryId(id);
    try {
      const detail = await getRenderHistoryDetail(id);
      setProblemText(detail.problem_text);
      applyRenderResponse(detail.response ?? buildLegacyHistoryResponse(detail));
      setLastAdvancedSettings(advancedSettingsFromHistory(detail.advanced_settings));
      setRuntimeSettings((current) => runtimeSettingsFromHistory(detail.runtime_settings, current));
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

  async function updateHistoryItem(id: string, patch: Parameters<typeof patchRenderHistory>[1]) {
    try {
      const updated = await patchRenderHistory(id, patch);
      setHistoryItems((current) => current.map((item) => item.id === id ? { ...item, ...updated } : item));
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể cập nhật lịch sử dựng hình.');
      showApiError('Không thể cập nhật lịch sử', apiError, 'Hãy thử lại sau.');
    }
  }

  async function handleSceneEdit(scene: MathScene, options: { optimistic?: boolean } = {}) {
    const saveSeq = editSaveSeqRef.current + 1;
    editSaveSeqRef.current = saveSeq;
    if (options.optimistic) applyLocalSceneEdit(scene);
    setEditorSaving(true);
    try {
      const response = await renderEditedScene(scene, lastAdvancedSettings, effectiveResult);
      if (editSaveSeqRef.current !== saveSeq) return;
      applyRenderResponse(response);
      if (user) void refreshHistory();
      showWarnings(response.warnings);
    } catch (caught) {
      if (editSaveSeqRef.current !== saveSeq) return;
      const apiError = toApiError(caught, 'Không thể lưu chỉnh sửa hình.');
      showApiError('Không thể lưu chỉnh sửa', apiError, 'Hình đã được chỉnh cục bộ. Hãy thử lưu/chỉnh lại nếu cần đồng bộ server.');
    } finally {
      if (editSaveSeqRef.current === saveSeq) setEditorSaving(false);
    }
  }

  async function handlePointDragEnd(name: string, point: Vec3) {
    const scene = effectiveResult?.scene ?? activeScene;
    if (!scene) return;
    const target = scene.objects.find((obj) => (obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name);
    if (target?.locked) {
      showNotification('Không thể sửa điểm', `Điểm ${name} đang bị khóa theo dữ kiện đề bài.`, [], 'warning');
      return;
    }
    const editedScene: MathScene = {
      ...scene,
      revision: (scene.revision ?? activeRevision) + 1,
      objects: scene.objects.map((obj) => {
        if ((obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name) {
          // Khi user tự kéo điểm, xoá biểu thức tham số (nếu có) cho điểm đó
          // vì giá trị mới do user đặt thủ công, không còn phụ thuộc tham số.
          if (obj.type === 'point_3d') {
            return { ...obj, x: round(point.x), y: round(point.y), z: round(point.z), x_expr: null, y_expr: null, z_expr: null, source: 'user_edited' as const, user_edited: true };
          }
          return { ...obj, x: round(point.x), y: round(point.y), x_expr: null, y_expr: null, source: 'user_edited' as const, user_edited: true };
        }
        return obj;
      }),
    };
    void handleSceneEdit(editedScene, { optimistic: true });
  }

  async function handleConnectPoints(start: string, end: string) {
    const scene = effectiveResult?.scene ?? activeScene;
    if (!scene || editorSaving) return;
    if (start === end) {
      const message = 'Chọn hai điểm khác nhau để nối đoạn.';
      showNotification('Không thể nối đoạn', message);
      return;
    }
    if (hasSegment(scene, start, end)) {
      const message = `Đoạn ${start}${end} đã tồn tại.`;
      showNotification('Không thể nối đoạn', message);
      return;
    }
    const editedScene: MathScene = {
      ...scene,
      revision: (scene.revision ?? activeRevision) + 1,
      objects: [
        ...scene.objects,
        { type: 'segment', points: [start, end], hidden: false, color: '#111111', line_width: 3, style: 'solid', source: 'construction' },
      ],
    };
    await handleSceneEdit(editedScene, { optimistic: true });
  }

  async function handlePointToSegmentClick(segmentPoints: [string, string]) {
    const scene = effectiveResult?.scene ?? activeScene;
    if (editorSaving) return;
    if (!scene || !pointToSegmentSource || editTool !== 'project_to_segment') {
      const message = 'Chọn công cụ tạo chân nối, chọn một điểm nguồn, rồi click vào đoạn đích.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }
    if (segmentPoints.includes(pointToSegmentSource)) {
      const message = 'Điểm nguồn đang nằm trên đoạn đích. Hãy chọn đoạn khác nếu muốn nối thêm.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }

    const source = findPoint(scene, pointToSegmentSource);
    const start = findPoint(scene, segmentPoints[0]);
    const end = findPoint(scene, segmentPoints[1]);
    if (!source || !start || !end) {
      const message = 'Không tìm thấy điểm nguồn hoặc đoạn đích trong scene.';
      showNotification('Không thể tạo chân nối', message);
      return;
    }

    const newPoint = projectPointToLine(source, start, end);
    const newName = nextPointName(scene);
    const sourceSegment = `${pointToSegmentSource}-${newName}`;
    const targetSegment = `${segmentPoints[0]}-${segmentPoints[1]}`;
    const constructionMetadata = {
      constructed_by: 'project_to_segment',
      source_point: pointToSegmentSource,
      target_segment: segmentPoints,
      projection: 'orthogonal_to_line',
      t: newPoint.t,
      outside_segment: newPoint.outside,
    };
    const editedScene: MathScene = {
      ...scene,
      revision: (scene.revision ?? activeRevision) + 1,
      objects: [
        ...scene.objects,
        { type: 'point_3d', name: newName, x: round(newPoint.x), y: round(newPoint.y), z: round(newPoint.z), source: 'construction', metadata: constructionMetadata },
        { type: 'segment', points: [pointToSegmentSource, newName], hidden: false, color: '#111111', line_width: 3, style: 'solid', source: 'construction', metadata: constructionMetadata },
      ],
      relations: [
        ...(scene.relations ?? []),
        { type: 'perpendicular', object_1: sourceSegment, object_2: targetSegment, source: 'construction', args: { source_point: pointToSegmentSource, foot_point: newName, target_segment: segmentPoints }, metadata: { ...constructionMetadata, confidence: 'unverified' } },
        { type: 'on_line', object_1: newName, object_2: targetSegment, source: 'construction', args: { source_point: pointToSegmentSource, target_segment: segmentPoints, t: newPoint.t }, metadata: { ...constructionMetadata, confidence: 'unverified' } },
      ],
    };

    setPointToSegmentSource(null);
    await handleSceneEdit(editedScene, { optimistic: true });
  }

  function handleAddPointBlockedClick(name: string) {
    showNotification('Không thể thêm điểm', `Vị trí ${name} đã có điểm. Hãy click vào vùng trống trên hình.`, [], 'warning');
  }

  async function handleCanvasClickToAddPoint(clickedPoint: Vec3) {
    const scene = effectiveResult?.scene ?? activeScene;
    if (!scene || editorSaving) return;

    const dim = scene.view.dimension;
    const name = nextPointName(scene);
    const point = dim === '3d'
      ? { type: 'point_3d' as const, name, x: round(clickedPoint.x), y: round(clickedPoint.y), z: round(clickedPoint.z), source: 'user_created' as const, user_edited: true }
      : { type: 'point_2d' as const, name, x: round(clickedPoint.x), y: round(clickedPoint.y), source: 'user_created' as const, user_edited: true };

    const editedScene: MathScene = {
      ...scene,
      revision: (scene.revision ?? activeRevision) + 1,
      objects: [...scene.objects, point],
    };
    await handleSceneEdit(editedScene, { optimistic: true });
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
          <Suspense fallback={<PageLoadingFallback />}>
            <AdminConsole
              user={user}
              onBackToApp={() => navigateTo('home')}
              onOpenRenderJobDetail={openAdminRenderJobDetail}
              onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            />
          </Suspense>
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
            <button type="button" className={`nav-item ${activeView === 'render' || activeView === 'analyzer' || activeView === 'algebra-solver' || activeView === 'analyzer-guide' || activeView === 'simulation' || activeView === 'geogebra-lab' || activeView === 'pdf-to-word' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={toolsMenuOpen ? 'true' : 'false'} onClick={() => setToolsMenuOpen((open) => !open)}>
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
                <button type="button" role="menuitem" className={activeView === 'algebra-solver' ? 'active' : ''} onClick={() => {
                  setToolsMenuOpen(false);
                  navigateTo('algebra-solver');
                }}>
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 7h16"></path><path d="M4 12h10"></path><path d="M4 17h16"></path><path d="M17 10l3 3-3 3"></path></svg>
                  <span>
                    <strong>
                      Solver đại số
                      <em className="tools-beta-badge" title="Đang trong quá trình phát triển, có thể chưa đầy đủ chức năng hoặc phát sinh lỗi." aria-label="Beta: đang trong quá trình phát triển, có thể chưa đầy đủ chức năng hoặc phát sinh lỗi.">Beta</em>
                    </strong>
                    <small>Phương trình, bất phương trình có kiểm chứng</small>
                  </span>
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
              <button type="button" className={`account-menu-trigger ${activeView === 'history' || activeView === 'account' || activeView === 'settings' || activeView === 'feedback' ? 'active' : ''}`} aria-haspopup="menu" aria-expanded={accountMenuOpen ? 'true' : 'false'} onClick={() => setAccountMenuOpen((open) => !open)}>
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
                      Tài khoản
                    </button>
                    <button type="button" role="menuitem" onClick={() => {
                      setAccountMenuOpen(false);
                      navigateTo('settings');
                    }}>
                      <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 8.92 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.36.64.98 1 1.6 1h.09a2 2 0 1 1 0 4H21c-.62 0-1.24.36-1.6 1Z"></path></svg>
                      Cài đặt
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
                <button type="button" className={sidebarTool === 'input' ? 'active' : ''} onClick={() => setSidebarTool('input')} role="tab" aria-selected={sidebarTool === 'input' ? 'true' : 'false'}>
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
                  aria-selected={sidebarTool === 'solver' ? 'true' : 'false'}
                  aria-disabled={result?.scene ? undefined : 'true'}
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
                      {historyOpen && <HistoryPanel items={historyItems} loading={historyLoading} openingId={openingHistoryId} onOpen={openHistoryItem} onDelete={removeHistoryItem} onPatch={updateHistoryItem} />}
                    </div>
                  )}
                </>
              ) : effectiveResult?.scene && user ? (
                <SolverPanel scene={effectiveResult.scene} response={effectiveResult} runtimeSettings={runtimeSettings} onHighlight={setHighlightedObjects} />
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
                {effectiveResult && shouldShowConfirmationPrompt(effectiveResult) && (
                  <aside className="render-review-chip" role="status" aria-live="polite">
                    <span className="render-review-dot" aria-hidden="true" />
                    <span className="render-review-copy">
                      <strong>Cần kiểm tra hình</strong>
                      <small>Hình có fallback hoặc giả định. Xác nhận sau khi đối chiếu với đề bài.</small>
                    </span>
                    <button type="button" className="secondary-button" onClick={confirmCurrentScene}>Đã kiểm tra</button>
                  </aside>
                )}
                {effectiveResult?.scene && (
                  <div ref={renderToolsMenuRef} className="render-tools-floating">
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
                      aria-expanded={renderToolsOpen ? 'true' : 'false'}
                      title="Công cụ hình"
                    >
                      <ToolboxIcon />
                    </button>
                    {renderToolsOpen && (
                      <div
                        className="render-tools-menu"
                        role="menu"
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
                          aria-expanded={renderToolsPanel === 'export' ? 'true' : 'false'}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M14 3v5h5M9 15h6M9 18h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
                          <span><strong>Xuất hình</strong><small>PNG, JPG, SVG, HTML KaTeX, TikZ, PDF, GGB.</small></span>
                        </button>
                        {renderToolsPanel === 'export' && (
                          <div className="render-tools-submenu render-tools-export-submenu">
                            <ExportMenuItems
                              scene={effectiveResult.scene}
                              advancedSettings={lastAdvancedSettings}
                              captureCurrentView={threeImageCapture}
                              preferCurrentViewCapture={Boolean(effectiveResult.payload.three_scene)}
                              response={effectiveResult}
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
                          aria-expanded={renderToolsPanel === 'variants' ? 'true' : 'false'}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12M6 12h12M6 17h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><path d="M16 15l2 2 3-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
                          <span><strong>Sinh đề</strong><small>Chọn số lượng đề biến thể.</small></span>
                        </button>
                        {renderToolsPanel === 'variants' && (
                          <div className="render-tools-submenu">
                            <ProblemVariantTool scene={effectiveResult.scene} response={effectiveResult} originalProblem={problemText} runtimeSettings={runtimeSettings} onError={(msg) => showNotification('Công cụ hình', msg, [], 'info')} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                {sceneEditorOpen && effectiveResult?.scene && (
                  <div className="scene-editor-layer" role="presentation" onMouseDown={() => setSceneEditorOpen(false)}>
                    <aside className="scene-editor-drawer" role="dialog" aria-modal="true" aria-label="Sửa hình học" onMouseDown={(event) => event.stopPropagation()}>
                      <div className="scene-editor-popover-header">
                        <div className="scene-editor-heading">
                          <strong>Sửa hình học</strong>
                          <span>{editorSaving ? 'Đang đồng bộ thay đổi' : 'Chỉnh hình trực tiếp trên canvas'}</span>
                        </div>
                        <button type="button" className="scene-editor-close" onClick={() => setSceneEditorOpen(false)} aria-label="Đóng sửa hình học"><CloseIcon /></button>
                      </div>
                      <SceneEditorPanel
                        scene={effectiveResult.scene}
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
                        onChange={(scene) => { void handleSceneEdit(scene, { optimistic: true }); }}
                        parameters={effectiveResult.scene.parameters}
                        parameterValues={paramValues}
                        onParameterValuesChange={setParamValues}
                        onParameterReset={() => setParamValues(getDefaultParamValues(effectiveResult.scene.parameters))}
                        onHighlightObjects={setHighlightedObjects}
                      />
                    </aside>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
        {activeView === 'analyzer' && (
          <Suspense fallback={<PageLoadingFallback />}>
            <div className="analyzer-standalone-wrap">
              <FunctionAnalyzerPanel onOpenGuide={() => navigateTo('analyzer-guide')} onWarnings={showAnalyzerWarnings} />
            </div>
          </Suspense>
        )}
        {activeView === 'algebra-solver' && <Suspense fallback={<PageLoadingFallback />}><AlgebraSolverPage /></Suspense>}
        {activeView === 'simulation' && <Suspense fallback={<PageLoadingFallback />}><CalculusSimulationPage /></Suspense>}
        {activeView === 'geogebra-lab' && <Suspense fallback={<PageLoadingFallback />}><GeoGebraLabPage /></Suspense>}
        {activeView === 'pdf-to-word' && (
          <Suspense fallback={<PageLoadingFallback />}>
            <PdfToWordPage apiBaseUrl={MINERU_API_BASE_URL} />
          </Suspense>
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
            onPatch={updateHistoryItem}
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
            turnstileEnabled={settingsDefaults?.feature_flags?.turnstile_enabled ?? false}
            turnstileSiteKey={settingsDefaults?.feature_flags?.turnstile_site_key ?? null}
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
            onOpenSettings={() => navigateTo('settings')}
            onLogout={handleLogout}
            onResendVerification={handleResendVerification}
            onUpdateProfile={handleUpdateProfile}
            learningProfile={learningProfile}
            onUpdateLearningProfile={handleUpdateLearningProfile}
            onChangePassword={handleChangePassword}
            onLoadSessions={handleLoadSessions}
            onRevokeSession={handleRevokeSession}
            onRevokeOtherSessions={handleRevokeOtherSessions}
          />
        )}
        {activeView === 'settings' && user && (
          <SettingsPage
            onToast={(title, message, kind = 'info') => showNotification(title, message, [], kind)}
            onBackWorkspace={() => navigateTo('render')}
            onOpenAccount={() => navigateTo('account')}
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

function PageLoadingFallback() {
  return (
    <section className="product-page-card page-loading-fallback" aria-live="polite">
      <div className="tool-loading-orb" aria-hidden="true">
        <span />
      </div>
      <div className="tool-loading-copy">
        <strong>Đang tải công cụ</strong>
        <span>Chuẩn bị module, canvas và dữ liệu cần thiết.</span>
      </div>
      <div className="tool-loading-skeleton" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
    </section>
  );
}

function shouldShowConfirmationPrompt(response: RenderResponse) {
  const hasAssumptions = Boolean(response.scene.interpretation?.assumptions?.length || response.scene.interpretation?.missing_data?.length);
  return !response.user_confirmed && (
    response.status === 'fallback'
    || response.status === 'needs_confirmation'
    || response.requires_user_confirmation
    || response.source.fallback_used
    || response.repair_report.requires_confirmation
    || hasAssumptions
  );
}

function buildLegacyHistoryResponse(detail: AdminRenderHistoryDetail): RenderResponse {
  return {
    status: detail.fallback_source && detail.fallback_source !== 'none' ? 'fallback' : 'partially_verified',
    source: {
      kind: detail.ai_source === 'byok' ? 'byok' : detail.fallback_source === 'mock' ? 'mock' : 'ai',
      provider: detail.provider,
      model: detail.model,
      fallback_used: Boolean(detail.degraded || (detail.fallback_source && detail.fallback_source !== 'none')),
      fallback_reason: detail.fallback_source && detail.fallback_source !== 'none' ? detail.fallback_source : null,
      candidate_attempts: [],
    },
    scene: detail.scene,
    payload: detail.payload,
    warnings: detail.warnings,
    validation_report: { status: 'passed', items: [] },
    verification_report: { status: 'partial', relations: [], summary: { verified: 0, failed: 0, unsupported: 0, unverifiable: 0, error: 0 } },
    repair_report: { status: 'none', changes: [], requires_confirmation: false, warnings: [] },
    renderer_compatibility: { status: 'requires_confirmation', renderer: detail.scene.renderer, dimension: detail.scene.view.dimension, messages: ['Lịch sử này không có full metadata render v2.'], unsupported_objects: [], unsupported_relations: [] },
    requires_user_confirmation: true,
    cas_issues: detail.scene.cas_issues ?? [],
    advisory: null,
    degraded: detail.degraded,
    fallback_source: detail.fallback_source ?? 'none',
    ai_source: detail.ai_source ?? 'none',
  };
}

function advancedSettingsFromHistory(value: Record<string, unknown> | null | undefined): AdvancedRenderSettings {
  if (!value) return defaultAdvancedSettings;
  return { ...defaultAdvancedSettings, ...value } as AdvancedRenderSettings;
}

function runtimeSettingsFromHistory(value: Record<string, unknown> | null | undefined, fallback: RuntimeSettings): RuntimeSettings {
  if (!value) return fallback;
  return { ...fallback, ...value } as RuntimeSettings;
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
    model: defaults.model ?? '',
    scanned_models: defaults.scanned_models,
    allowed_model_ids: defaults.allowed_model_ids,
    last_scanned_at: '',
  };
}
