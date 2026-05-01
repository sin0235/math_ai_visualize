import { useEffect, useRef, useState } from 'react';

import { ApiError, deleteAdminRenderJob, deleteRenderHistory, getAdminAuditLogs, getAdminRenderJobs, getAdminSummary, getAdminSystemSettings, getAdminUsers, getCurrentUser, getHealth, getRenderHistory, getRenderHistoryDetail, getSettingsDefaults, getUserSettings, login, logout, ocrImage, register, renderEditedScene, renderProblem, saveUserSettings, updateAdminUser, type AdminRenderHistoryItem, type AdminSummaryResponse, type AuditLogResponse, type RenderHistoryItem, type SystemSettingResponse, type UserResponse } from './api/client';
import { defaultAdvancedSettings, ProblemInput, staticModelOptions, type ModelOption } from './components/ProblemInput';
import { GeneralSettingsPanel } from './components/GeneralSettingsPanel';
import { HomePage } from './components/HomePage';
import { LoginPage } from './components/LoginPage';
import { RendererPanel } from './components/RendererPanel';
import { Router9SettingsPanel } from './components/Router9SettingsPanel';
import { SceneEditorPanel, type PointPlacementPlane } from './components/SceneEditorPanel';
import { SceneJsonPanel } from './components/SceneJsonPanel';
import { SettingsPanel } from './components/SettingsPanel';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, SETTINGS_STORAGE_VERSION, type RuntimeSettings, type SettingsDefaults } from './types/settings';
import logoUrl from '../img.svg';
import './styles.css';

const SETTINGS_STORAGE_KEY = 'hinh-runtime-settings';
const MOBILE_WARNING_STORAGE_KEY = 'hinh-mobile-warning-dismissed';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 900px)';

type AppView = 'home' | 'render' | 'history' | 'login' | 'settings' | 'admin';
type SettingsTab = 'general' | 'providers' | 'router9';
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

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('home');
  const [activeSettingsTab, setActiveSettingsTab] = useState<SettingsTab>('general');
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
  const [historyItems, setHistoryItems] = useState<RenderHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [remoteSettingsHydrated, setRemoteSettingsHydrated] = useState(false);
  const [adminSummary, setAdminSummary] = useState<AdminSummaryResponse | null>(null);
  const [adminUsers, setAdminUsers] = useState<UserResponse[]>([]);
  const [adminRenderJobs, setAdminRenderJobs] = useState<AdminRenderHistoryItem[]>([]);
  const [adminSettings, setAdminSettings] = useState<SystemSettingResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [adminLoading, setAdminLoading] = useState(false);
  const resultAnchorRef = useRef<HTMLDivElement | null>(null);
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
    let cancelled = false;
    getCurrentUser()
      .then(async ({ user }) => {
        if (cancelled) return;
        setUser(user);
        await loadRemoteWorkspace(user);
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

  const modelOptions = buildModelOptions(runtimeSettings);
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
    if (runtimeSettings.router9.only_mode && !runtimeSettings.router9.model.trim() && runtimeSettings.router9.allowed_model_ids.length === 0) {
      const message = '9router-only đang bật. Hãy quét/chọn model 9router trước khi OCR.';
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

  function forgetApiKeys() {
    setRuntimeSettings((current) => dropApiKeys(current));
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
      setActiveView('render');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleRegister(email: string, password: string) {
    setAuthLoading(true);
    try {
      setRemoteSettingsHydrated(false);
      const response = await register(email, password);
      setUser(response.user);
      await saveUserSettings(sanitizeSettingsForStorage(runtimeSettings));
      await refreshHistory();
      setRemoteSettingsHydrated(true);
      setActiveView('render');
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
    } finally {
      setAuthLoading(false);
    }
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
    if (user?.role !== 'admin') {
      showNotification('Không có quyền quản trị', 'Tài khoản hiện tại không có quyền truy cập trang quản trị.');
      setActiveView('render');
      return;
    }
    setAdminLoading(true);
    try {
      const [summary, users, jobs, settings, logs] = await Promise.all([
        getAdminSummary(),
        getAdminUsers(),
        getAdminRenderJobs(),
        getAdminSystemSettings(),
        getAdminAuditLogs(),
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

  async function toggleUserStatus(target: UserResponse) {
    try {
      const nextStatus = target.status === 'active' ? 'disabled' : 'active';
      const updated = await updateAdminUser(target.id, { status: nextStatus });
      setAdminUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      void loadAdminWorkspace();
    } catch (caught) {
      const apiError = toApiError(caught, 'Không thể cập nhật người dùng.');
      showApiError('Không thể cập nhật user', apiError, 'Hãy thử lại hoặc kiểm tra quyền admin.');
    }
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
          {user && (
            <button type="button" className={`nav-item ${activeView === 'history' ? 'active' : ''}`} onClick={() => {
              setActiveView('history');
              void refreshHistory();
            }}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 3v6h6"></path><path d="M12 7v5l3 2"></path></svg>
              Lịch sử
            </button>
          )}
          {user?.role === 'admin' && (
            <button type="button" className={`nav-item ${activeView === 'admin' ? 'active' : ''}`} onClick={() => {
              setActiveView('admin');
              void loadAdminWorkspace();
            }}>
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
              Admin
            </button>
          )}
          <button type="button" className={`nav-item ${activeView === 'login' ? 'active' : ''}`} onClick={() => setActiveView('login')}>
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><path d="M10 17l5-5-5-5"></path><path d="M15 12H3"></path></svg>
            {user ? user.email : 'Đăng nhập'}
          </button>
          <button type="button" className={`nav-item ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}>
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10.91 3H11a2 2 0 1 1 4 0h.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0A1.65 1.65 0 0 0 21 10.91V11a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Setting
          </button>
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
            <ProblemInput
              loading={loading}
              ocrLoading={ocrLoading}
              ocrError={null}
              problemText={problemText}
              modelOptions={modelOptions}
              router9Only={runtimeSettings.router9.only_mode}
              onProblemTextChange={setProblemText}
              onOcrImage={handleOcrImage}
              onOcrClipboardImage={handleOcrClipboardImage}
              onOpenRouter9Settings={() => {
                setActiveView('settings');
                setActiveSettingsTab('router9');
              }}
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
              <SceneJsonPanel result={result} />
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
        {activeView === 'admin' && (
          <AdminConsole
            user={user}
            summary={adminSummary}
            users={adminUsers}
            renderJobs={adminRenderJobs}
            settings={adminSettings}
            auditLogs={auditLogs}
            loading={adminLoading}
            onRefresh={loadAdminWorkspace}
            onToggleUserStatus={toggleUserStatus}
            onDeleteRenderJob={removeAdminRenderJob}
            onBackToApp={() => setActiveView('render')}
          />
        )}
        {activeView === 'login' && (
          <LoginPage
            logoUrl={logoUrl}
            user={user}
            authLoading={authLoading}
            onBackHome={() => setActiveView('home')}
            onContinueAsGuest={() => setActiveView('render')}
            onLogin={handleLogin}
            onRegister={handleRegister}
            onLogout={handleLogout}
          />
        )}
        {activeView === 'settings' && (
          <section className="settings-page">
            <div className="settings-tabs">
              <button type="button" className={`settings-tab ${activeSettingsTab === 'general' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('general')}>General</button>
              <button type="button" className={`settings-tab ${activeSettingsTab === 'providers' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('providers')}>Provider</button>
              <button type="button" className={`settings-tab ${activeSettingsTab === 'router9' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('router9')}>9router</button>
            </div>
            {activeSettingsTab === 'general' ? (
              <GeneralSettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onReset={resetSettings} />
            ) : activeSettingsTab === 'providers' ? (
              <SettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onReset={resetSettings} onForgetApiKeys={forgetApiKeys} />
            ) : (
              <Router9SettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onForgetApiKeys={forgetApiKeys} />
            )}
          </section>
        )}
      </main>
      <footer className="app-footer">
        <span className="footer-line" />
        <span className="footer-credit">Developed by <strong>Sin Tran</strong></span>
        <span className="footer-line" />
      </footer>
    </>
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

function AdminConsole({ user, summary, users, renderJobs, settings, auditLogs, loading, onRefresh, onToggleUserStatus, onDeleteRenderJob, onBackToApp }: { user: UserResponse | null; summary: AdminSummaryResponse | null; users: UserResponse[]; renderJobs: AdminRenderHistoryItem[]; settings: SystemSettingResponse[]; auditLogs: AuditLogResponse[]; loading: boolean; onRefresh: () => void; onToggleUserStatus: (user: UserResponse) => void; onDeleteRenderJob: (id: string) => void; onBackToApp: () => void }) {
  if (user?.role !== 'admin') {
    return (
      <section className="product-page-card">
        <span className="home-eyebrow">Admin console</span>
        <h2>Bạn không có quyền truy cập trang quản trị.</h2>
        <p>Trang này chỉ dành cho tài khoản admin đang hoạt động.</p>
        <button type="button" onClick={onBackToApp}>Quay lại workspace</button>
      </section>
    );
  }

  return (
    <section className="admin-console">
      <div className="page-title-row">
        <div>
          <span className="home-eyebrow">Admin console</span>
          <h2>Quản trị AI Math Renderer</h2>
          <p>Theo dõi người dùng, render jobs, cấu hình hệ thống và audit logs.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? 'Đang tải...' : 'Làm mới'}</button>
      </div>

      <div className="admin-metric-grid">
        <MetricCard label="Người dùng" value={summary?.users ?? 0} />
        <MetricCard label="Đang hoạt động" value={summary?.active_users ?? 0} />
        <MetricCard label="Admin" value={summary?.admins ?? 0} />
        <MetricCard label="Render jobs" value={summary?.render_jobs ?? 0} />
      </div>

      <div className="admin-grid">
        <section className="admin-panel">
          <h3>Người dùng</h3>
          <div className="admin-table">
            {users.map((item) => (
              <article className="admin-row" key={item.id}>
                <div>
                  <strong>{item.display_name || item.email}</strong>
                  <span>{item.email} · {item.role} · {item.status} · {item.plan}</span>
                </div>
                <button type="button" className="secondary-button" onClick={() => onToggleUserStatus(item)}>{item.status === 'active' ? 'Vô hiệu hoá' : 'Kích hoạt'}</button>
              </article>
            ))}
          </div>
        </section>

        <section className="admin-panel">
          <h3>Render jobs gần đây</h3>
          <div className="admin-table">
            {renderJobs.map((job) => (
              <article className="admin-row" key={job.id}>
                <div>
                  <strong>{job.problem_text}</strong>
                  <span>{formatHistoryDate(job.created_at)} · {job.user_id || 'guest'} · {job.renderer || 'auto'} · {job.model || 'default'}</span>
                </div>
                <button type="button" className="history-delete" onClick={() => onDeleteRenderJob(job.id)} aria-label="Xoá render job">×</button>
              </article>
            ))}
          </div>
        </section>

        <section className="admin-panel">
          <h3>Cấu hình hệ thống</h3>
          {settings.length === 0 ? <p>Chưa có cấu hình non-secret nào được lưu.</p> : settings.map((item) => (
            <article className="admin-row" key={item.key}>
              <div>
                <strong>{item.key}</strong>
                <span>Cập nhật {formatHistoryDate(item.updated_at)}</span>
              </div>
            </article>
          ))}
        </section>

        <section className="admin-panel">
          <h3>Audit logs</h3>
          <div className="admin-table">
            {auditLogs.map((log) => (
              <article className="admin-row" key={log.id}>
                <div>
                  <strong>{log.action}</strong>
                  <span>{formatHistoryDate(log.created_at)} · {log.actor_user_id || 'system'} · {log.target_type}{log.target_id ? `/${log.target_id}` : ''}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <article className="admin-metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString('vi-VN')}</strong>
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
    ocr: current.ocr.provider === 'router9' && !current.ocr.model && router9Model
      ? { ...current.ocr, model: router9Model }
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
  return dropApiKeys(settings);
}

function dropApiKeys(settings: RuntimeSettings): RuntimeSettings {
  return {
    ...settings,
    openrouter: { ...settings.openrouter, api_key: '' },
    nvidia: { ...settings.nvidia, api_key: '' },
    ollama: { ...settings.ollama, api_key: '' },
    router9: { ...settings.router9, api_key: '' },
  };
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

function buildModelOptions(settings: RuntimeSettings): ModelOption[] {
  const scannedProviderOptions = (['openrouter', 'nvidia', 'ollama'] as const).flatMap((provider) =>
    settings[provider].scanned_models.map((model) => ({
      key: `${provider}:${model.id}`,
      provider,
      modelId: model.id,
      label: `${providerLabel(provider)}: ${model.label}`,
      description: `${providerLabel(provider)} model ${model.id}${model.context_length ? ` — context ${model.context_length}` : ''}`,
    }))
  );

  const router9Options = settings.router9.allowed_model_ids.map((modelId) => {
    const scanned = settings.router9.scanned_models.find((model) => model.id === modelId);
    return {
      key: `router9:${modelId}`,
      provider: 'router9',
      modelId,
      label: `9router: ${scanned?.label ?? modelId}`,
      description: `9router model ${modelId}`,
    };
  });

  if (settings.router9.only_mode) {
    return router9Options;
  }

  return [...staticModelOptions, ...scannedProviderOptions, ...router9Options];
}

function providerLabel(provider: 'openrouter' | 'nvidia' | 'ollama') {
  if (provider === 'openrouter') return 'OpenRouter';
  if (provider === 'nvidia') return 'NVIDIA';
  return 'Ollama';
}
