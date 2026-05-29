import React, { useState, useEffect, useRef } from 'react';
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
  AdminPlanResponse,
  FeedbackStatus,
  ChatConversationResponse,
  ChatMessageResponse,
  ChatWsEvent
} from '../../api/client';
import { 
  getAdminSummary, 
  getAdminUsers,
  getAdminPlans,
  updateAdminPlan,
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
  getAdminDatabaseDiagnostics,
  getAdminChatConversations,
  getAdminChatConversation,
  sendAdminChatMessage,
  sendAdminChatImage,
  markAdminChatRead,
  closeAdminChatConversation,
  createChatWebSocket
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
  AdminAiTierProfilesForm,
  AdminAiPromptsForm,
} from './AdminForms';
import { distinctOptions, planLabel, providerLabels, rendererOptions, renderSourceOptions } from '../../utils/settingsOptions';
import type { SettingsDefaults } from '../../types/settings';
import adminLogoUrl from '../../../logo.svg';

type AdminToastKind = 'error' | 'warning' | 'info';

type AdminToast = (title: string, message: string, kind?: AdminToastKind) => void;
type AdminSection = 'overview' | 'users' | 'renders' | 'models' | 'plans' | 'settings' | 'feedback' | 'chat' | 'audit';

interface AdminConsoleProps {
  user: UserResponse;
  onBackToApp: () => void;
  onOpenRenderJobDetail: (detail: AdminRenderHistoryDetail) => void;
  onToast: AdminToast;
}

function AttachFileIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 12.2 13.9 4.3a4.2 4.2 0 0 1 5.9 5.9L10.9 19a5.8 5.8 0 0 1-8.2-8.2l9.7-9.7" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12 20 4l-5.4 16-3.1-6.5L4 12Z" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11.5 13.5 20 4" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
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
  const [activeSection, setActiveSection] = useState<AdminSection>('overview');
  const [summary, setSummary] = useState<AdminSummaryResponse | null>(null);
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [renderJobs, setRenderJobs] = useState<AdminRenderHistoryItem[]>([]);
  const [settings, setSettings] = useState<SystemSettingResponse[]>([]);
  const [plans, setPlans] = useState<AdminPlanResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [feedbackItems, setFeedbackItems] = useState<AdminFeedbackResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadedSections, setLoadedSections] = useState<Record<AdminSection, boolean>>({
    overview: false,
    users: false,
    renders: false,
    models: false,
    plans: false,
    settings: false,
    feedback: false,
    chat: false,
    audit: false,
  });

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

  // Chat inbox state
  const [chatConversations, setChatConversations] = useState<ChatConversationResponse[]>([]);
  const [selectedChatConversation, setSelectedChatConversation] = useState<ChatConversationResponse | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessageResponse[]>([]);
  const [chatFilters, setChatFilters] = useState<{ status?: string; q?: string }>({ status: 'open' });
  const [filteringChat, setFilteringChat] = useState(false);
  const [chatReply, setChatReply] = useState('');
  const [adminSelectedImage, setAdminSelectedImage] = useState<File | null>(null);
  const [adminSelectedImagePreview, setAdminSelectedImagePreview] = useState<string | null>(null);
  const [sendingChat, setSendingChat] = useState(false);
  const [chatConnected, setChatConnected] = useState(false);
  const [userTypingConversationId, setUserTypingConversationId] = useState<string | null>(null);
  const [chatSoundEnabled, setChatSoundEnabled] = useState(true);
  const selectedChatConversationRef = useRef<ChatConversationResponse | null>(null);
  const adminChatWsRef = useRef<WebSocket | null>(null);
  const userTypingTimeoutRef = useRef<number | null>(null);
  const adminTypingStopTimeoutRef = useRef<number | null>(null);
  const adminTypingSentRef = useRef(false);
  const adminReplyTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const adminFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    selectedChatConversationRef.current = selectedChatConversation;
  }, [selectedChatConversation]);

  useEffect(() => {
    resizeAdminReplyTextarea();
  }, [chatReply, selectedChatConversation?.id]);

  useEffect(() => {
    return () => {
      if (adminSelectedImagePreview) URL.revokeObjectURL(adminSelectedImagePreview);
    };
  }, [adminSelectedImagePreview]);

  // Audit log filters
  const [localAuditLogFilters, setLocalAuditLogFilters] = useState<AdminAuditLogFilters>({});
  const [filteringAuditLogs, setFilteringAuditLogs] = useState(false);

  async function withLoading(section: AdminSection, label: string, loader: () => Promise<void>, showSuccess = false) {
    setLoading(true);
    try {
      await loader();
      setLoadedSections((current) => ({ ...current, [section]: true }));
      if (showSuccess) onToast(label, 'Đã làm mới dữ liệu.', 'info');
    } catch (error) {
      onToast(label, getErrorMessage(error, 'Không thể tải dữ liệu.'), 'error');
    } finally {
      setLoading(false);
    }
  }

  const loadOverview = (showSuccess = false) => withLoading('overview', 'Tổng quan', async () => {
    const [s, r, diagnostics, a] = await Promise.all([
      getAdminSummary(),
      getAdminRenderJobs({}),
      getAdminDatabaseDiagnostics(),
      getAdminAuditLogs({}),
    ]);
    setSummary(s);
    setRenderJobs(r);
    setDatabaseDiagnostics(diagnostics);
    setAuditLogs(a);
  }, showSuccess);

  const loadUsers = (showSuccess = false) => withLoading('users', 'Người dùng', async () => {
    const [u, st] = await Promise.all([getAdminUsers({}), getAdminSystemSettings()]);
    setUsers(u);
    setSettings(st);
    setPlans(await loadAdminPlans(st));
  }, showSuccess);

  const loadRenders = (showSuccess = false) => withLoading('renders', 'Render jobs', async () => {
    const [r, u, st] = await Promise.all([getAdminRenderJobs({}), getAdminUsers({}), getAdminSystemSettings()]);
    setRenderJobs(r);
    setUsers(u);
    setSettings(st);
    const ai = st.find((item) => item.key === 'ai_settings');
    if (ai) setAiSettings(ai.value);
  }, showSuccess);

  const loadModels = (showSuccess = false) => withLoading('models', 'Model & AI', async () => {
    const [st, defaults] = await Promise.all([getAdminSystemSettings(), getSettingsDefaults()]);
    setSettings(st);
    setSettingsDefaults(defaults);
    const ai = st.find((item) => item.key === 'ai_settings');
    if (ai) setAiSettings(ai.value);
  }, showSuccess);

  const loadPlans = (showSuccess = false) => withLoading('plans', 'Gói người dùng', async () => {
    const st = await getAdminSystemSettings();
    setSettings(st);
    setPlans(await loadAdminPlans(st));
  }, showSuccess);

  const loadDatabase = (showSuccess = false) => withLoading('settings', 'Database', async () => {
    const [diagnostics, st] = await Promise.all([getAdminDatabaseDiagnostics(), getAdminSystemSettings()]);
    setDatabaseDiagnostics(diagnostics);
    setSettings(st);
  }, showSuccess);

  const loadFeedback = (showSuccess = false) => withLoading('feedback', 'Góp ý', async () => {
    const [f, u] = await Promise.all([getAdminFeedback({}), getAdminUsers({})]);
    setFeedbackItems(f);
    setUsers(u);
  }, showSuccess);

  const loadChat = (showSuccess = false) => withLoading('chat', 'Chat', async () => {
    const conversations = await getAdminChatConversations(chatFilters);
    setChatConversations(conversations);
    if (!selectedChatConversation && conversations[0]) void selectChatConversation(conversations[0]);
  }, showSuccess);

  const loadAudit = (showSuccess = false) => withLoading('audit', 'Nhật ký kiểm toán', async () => {
    const [a, u] = await Promise.all([getAdminAuditLogs({}), getAdminUsers({})]);
    setAuditLogs(a);
    setUsers(u);
  }, showSuccess);

  const refreshActiveSection = (showSuccess = false) => {
    const loaders: Record<AdminSection, (showSuccess?: boolean) => Promise<void>> = {
      overview: loadOverview,
      users: loadUsers,
      renders: loadRenders,
      models: loadModels,
      plans: loadPlans,
      settings: loadDatabase,
      feedback: loadFeedback,
      chat: loadChat,
      audit: loadAudit,
    };
    return loaders[activeSection](showSuccess);
  };

  useEffect(() => {
    if (!loadedSections[activeSection]) void refreshActiveSection(false);
  }, [activeSection]);

  useEffect(() => {
    let reconnectTimer: number | null = null;
    let closed = false;
    let ws: WebSocket | null = null;

    async function connect() {
      try {
        ws = await createChatWebSocket();
        adminChatWsRef.current = ws;
        ws.onopen = () => setChatConnected(true);
        ws.onclose = () => {
          setChatConnected(false);
          if (!closed) reconnectTimer = window.setTimeout(() => void connect(), 2500);
        };
        ws.onerror = () => setChatConnected(false);
        ws.onmessage = (event) => handleAdminChatEvent(event.data);
      } catch {
        setChatConnected(false);
        if (!closed) reconnectTimer = window.setTimeout(() => void connect(), 4000);
      }
    }

    void connect();
    return () => {
      closed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (userTypingTimeoutRef.current) window.clearTimeout(userTypingTimeoutRef.current);
      if (adminTypingStopTimeoutRef.current) window.clearTimeout(adminTypingStopTimeoutRef.current);
      ws?.close();
    };
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
      const updated = await updateAdminUser(u.id, patch);
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setLoadedSections((current) => ({ ...current, overview: false }));
      onToast('Người dùng', 'Đã cập nhật người dùng.', 'info');
    } catch (error) {
      onToast('Người dùng', getErrorMessage(error, 'Không thể cập nhật người dùng.'), 'error');
    }
  };

  const onToggleUserStatus = async (u: UserResponse) => {
    const nextStatus = u.status === 'active' ? 'disabled' : 'active';
    try {
      const updated = await updateAdminUser(u.id, { status: nextStatus });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setLoadedSections((current) => ({ ...current, overview: false }));
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
      const updated = await updateAdminSystemSetting('ai_settings', patch);
      setAiSettings(updated.value);
      setSettings((prev) =>
        prev.some((item) => item.key === 'ai_settings')
          ? prev.map((item) => (item.key === 'ai_settings' ? updated : item))
          : [...prev, updated]
      );
      setSettingsDefaults(await getSettingsDefaults());
    } catch (error) {
      throw error;
    } finally {
      setSavingAiSettings(false);
    }
  };

  const saveAdminSystemSetting = async (key: string, value: any) => {
    try {
      const updated = await updateAdminSystemSetting(key, value);
      setSettings((prev) =>
        prev.some((item) => item.key === key)
          ? prev.map((item) => (item.key === key ? updated : item))
          : [...prev, updated]
      );
      if (key === 'ai_settings') setAiSettings(updated.value);
      if (key === 'ai_settings' || key === 'ai_profiles' || key === 'ai_tier_profiles') setSettingsDefaults(await getSettingsDefaults());
    } catch (error) {
      throw error;
    }
  };

  const saveAdminPlan = async (planId: string, patch: Parameters<typeof updateAdminPlan>[1]) => {
    const updated = await updateAdminPlan(planId, patch);
    setPlans((current) => current.map((plan) => (plan.id === updated.id ? updated : plan)));
    setLoadedSections((current) => ({ ...current, users: false }));
    return updated;
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

  const onSearchChat = async (filters: { status?: string; q?: string }) => {
    setFilteringChat(true);
    try {
      const conversations = await getAdminChatConversations(filters);
      setChatConversations(conversations);
      if (selectedChatConversation && !conversations.some((item) => item.id === selectedChatConversation.id)) {
        setSelectedChatConversation(null);
        setChatMessages([]);
      }
    } catch (error) {
      onToast('Chat', getErrorMessage(error, 'Không thể lọc chat.'), 'error');
    } finally {
      setFilteringChat(false);
    }
  };

  const submitChatFilters = (event: React.FormEvent) => {
    event.preventDefault();
    void onSearchChat(chatFilters);
  };

  const selectChatConversation = async (conversation: ChatConversationResponse) => {
    try {
      const detail = await getAdminChatConversation(conversation.id);
      setSelectedChatConversation(detail.conversation);
      setChatMessages(detail.messages);
      await markAdminChatRead(conversation.id);
      setChatConversations((current) => current.map((item) => item.id === conversation.id ? { ...item, unread_count: 0, admin_last_read_at: new Date().toISOString() } : item));
    } catch (error) {
      onToast('Chat', getErrorMessage(error, 'Không thể mở cuộc trò chuyện.'), 'error');
    }
  };

  const sendChatReply = async () => {
    const body = chatReply.trim();
    if ((!body && !adminSelectedImage) || !selectedChatConversation || sendingChat) return;
    setSendingChat(true);
    try {
      const message = adminSelectedImage ? await sendAdminChatImage(selectedChatConversation.id, adminSelectedImage, body) : await sendAdminChatMessage(selectedChatConversation.id, body);
      setChatMessages((current) => current.some((item) => item.id === message.id) ? current : [...current, message]);
      setChatReply('');
      clearAdminSelectedImage();
      sendAdminTyping(false);
      window.requestAnimationFrame(resizeAdminReplyTextarea);
      setAuditLogs(await getAdminAuditLogs(localAuditLogFilters));
    } catch (error) {
      onToast('Chat', getErrorMessage(error, adminSelectedImage ? 'Không thể gửi ảnh.' : 'Không thể gửi phản hồi.'), 'error');
    } finally {
      setSendingChat(false);
    }
  };

  const closeChat = async () => {
    if (!selectedChatConversation || !window.confirm('Đóng cuộc trò chuyện này?')) return;
    try {
      const updated = await closeAdminChatConversation(selectedChatConversation.id);
      setSelectedChatConversation(updated);
      setChatConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      onToast('Chat', 'Đã đóng cuộc trò chuyện.', 'info');
    } catch (error) {
      onToast('Chat', getErrorMessage(error, 'Không thể đóng cuộc trò chuyện.'), 'error');
    }
  };

  function handleAdminChatEvent(data: string) {
    let event: ChatWsEvent;
    try {
      event = JSON.parse(data) as ChatWsEvent;
    } catch {
      return;
    }
    if (event.type === 'message.created') {
      const selected = selectedChatConversationRef.current;
      const isSelected = selected?.id === event.conversation_id;
      const nextConversation = isSelected ? { ...event.conversation, unread_count: 0 } : event.conversation;
      setChatConversations((current) => upsertConversation(current, nextConversation));
      setSelectedChatConversation((current) => current?.id === event.conversation_id ? nextConversation : current);
      setChatMessages((current) => {
        if (!isSelected) return current;
        return current.some((item) => item.id === event.message.id) ? current : [...current, event.message];
      });
      if (isSelected && event.message.sender_role === 'user') void markAdminChatRead(event.conversation_id).catch(() => undefined);
      if (event.message.sender_role === 'user') {
        if (chatSoundEnabled) playChatNotificationSound();
        if (!isSelected) onToast('Chat', `Tin nhắn mới từ ${event.conversation.user_email ?? 'người dùng'}.`, 'info');
      }
    }
    if (event.type === 'conversation.updated' || event.type === 'conversation.read') {
      setChatConversations((current) => upsertConversation(current, event.conversation));
      setSelectedChatConversation((current) => current?.id === event.conversation_id ? event.conversation : current);
    }
    if (event.type === 'typing' && event.role === 'user') {
      setUserTypingConversationId(event.is_typing ? event.conversation_id : null);
      if (userTypingTimeoutRef.current) window.clearTimeout(userTypingTimeoutRef.current);
      if (event.is_typing) userTypingTimeoutRef.current = window.setTimeout(() => setUserTypingConversationId(null), 2500);
    }
  }

  function sendAdminTyping(isTyping: boolean) {
    const conversation = selectedChatConversationRef.current;
    if (!conversation || adminChatWsRef.current?.readyState !== WebSocket.OPEN) return;
    if (adminTypingSentRef.current === isTyping) return;
    adminTypingSentRef.current = isTyping;
    adminChatWsRef.current.send(JSON.stringify({ type: 'typing', conversation_id: conversation.id, target_user_id: conversation.user_id, is_typing: isTyping }));
  }

  function handleChatReplyChange(value: string) {
    setChatReply(value);
    if (!value.trim()) {
      sendAdminTyping(false);
      return;
    }
    sendAdminTyping(true);
    if (adminTypingStopTimeoutRef.current) window.clearTimeout(adminTypingStopTimeoutRef.current);
    adminTypingStopTimeoutRef.current = window.setTimeout(() => sendAdminTyping(false), 1200);
  }

  function resizeAdminReplyTextarea() {
    const textarea = adminReplyTextareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`;
  }

  function handleAdminImageSelect(file: File | null) {
    if (adminSelectedImagePreview) URL.revokeObjectURL(adminSelectedImagePreview);
    setAdminSelectedImage(file);
    setAdminSelectedImagePreview(file ? URL.createObjectURL(file) : null);
  }

  function clearAdminSelectedImage() {
    handleAdminImageSelect(null);
    if (adminFileInputRef.current) adminFileInputRef.current.value = '';
  }

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
  const planOptions = plans.filter((plan) => plan.is_active).map((plan) => ({ id: plan.id, label: planLabel(plan.id) }));
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
  const chatUnreadCount = chatConversations.reduce((total, item) => total + (item.unread_count || 0), 0);
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
          <AdminNavButton active={activeSection === 'plans'} onClick={() => setActiveSection('plans')} icon="users" label="Gói người dùng" />
          <AdminNavButton active={activeSection === 'settings'} onClick={() => setActiveSection('settings')} icon="settings" label="Database" />
          <AdminNavButton active={activeSection === 'feedback'} onClick={() => setActiveSection('feedback')} icon="audit" label="Góp ý" />
          <AdminNavButton active={activeSection === 'chat'} onClick={() => setActiveSection('chat')} icon="chat" label="Chat" badge={chatUnreadCount} />
          <AdminNavButton active={activeSection === 'audit'} onClick={() => setActiveSection('audit')} icon="audit" label="Nhật ký kiểm toán" />
        </nav>
        <div className="admin-sidebar-footer"><small>{user.email}</small><button type="button" className="secondary-button admin-button-with-icon" onClick={onBackToApp}><AdminIcon name="back" />Trang người dùng</button></div>
      </aside>

      <main className="admin-main">
        {activeSection === 'overview' && (
          <>
            <header className="admin-topbar">
              <div><span className="home-eyebrow">Admin Dashboard</span><h2>Quản lý dự án AI Math Renderer</h2><p>Khu vực vận hành, phân tích, quản lý người dùng, model, cài đặt và nhật ký.</p></div>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
            <AdminAiSettingsForm value={adminAiSettingsValue(aiSettings, settingsDefaults)} defaults={settingsDefaults} saving={savingAiSettings} onSave={saveAiSettingsPatch} onToast={onToast} />
            <AdminAiProfilesForm value={adminAiProfilesValue(settings.find((item) => item.key === 'ai_profiles')?.value, settingsDefaults)} aiSettings={aiSettings} defaults={settingsDefaults} onSave={(value) => saveAdminSystemSetting('ai_profiles', value)} onToast={onToast} />
            <AdminAiTierProfilesForm value={adminAiTierProfilesValue(settings.find((item) => item.key === 'ai_tier_profiles')?.value, settingsDefaults)} aiSettings={aiSettings} defaults={settingsDefaults} onSave={(value) => saveAdminSystemSetting('ai_tier_profiles', value)} onToast={onToast} />
            <AdminAiPromptsForm value={settings.find((item) => item.key === 'ai_prompts')?.value ?? {}} onSave={(value) => saveAdminSystemSetting('ai_prompts', value)} onToast={onToast} />
          </section>
          </>
        )}

        {activeSection === 'plans' && (
          <>
            <header className="admin-page-header">
              <h2>Gói người dùng</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
              <AdminPlanSettingsForm plans={plans} onSavePlan={saveAdminPlan} />
              <AdminFeatureFlagsForm value={settings.find((item) => item.key === 'feature_flags')?.value ?? {}} onSave={(value) => saveAdminSystemSetting('feature_flags', value)} onToast={onToast} />
            </section>
          </>
        )}

        {activeSection === 'settings' && (
          <>
            <header className="admin-page-header">
              <h2>Database</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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

        {activeSection === 'chat' && (
          <>
            <header className="admin-page-header">
              <div>
                <h2>Chat hỗ trợ</h2>
                <p className={`field-hint chat-runtime-status ${chatConnected ? 'is-online' : 'is-connecting'}`}><i aria-hidden="true" />Realtime: {chatConnected ? 'đang kết nối' : 'đang kết nối lại'}</p>
              </div>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
            </header>
            <section className="admin-panel admin-panel-full">
              <form className="admin-toolbar admin-filter-grid" onSubmit={submitChatFilters}>
                <input value={chatFilters.q ?? ''} onChange={(event) => setChatFilters((current) => ({ ...current, q: event.target.value }))} placeholder="Tìm email, tên hoặc ID" />
                <select value={chatFilters.status ?? ''} onChange={(event) => setChatFilters((current) => ({ ...current, status: event.target.value }))}>
                  <option value="">Tất cả trạng thái</option>
                  <option value="open">open</option>
                  <option value="closed">closed</option>
                </select>
                <button type="submit" className="secondary-button" disabled={filteringChat}>{filteringChat ? 'Đang lọc...' : 'Lọc chat'}</button>
                <button type="button" className="secondary-button" onClick={() => { const next = { status: 'open' }; setChatFilters(next); void onSearchChat(next); }}>Xoá lọc</button>
                <button type="button" className="secondary-button" onClick={() => setChatSoundEnabled((value) => !value)}>{chatSoundEnabled ? 'Tắt âm báo' : 'Bật âm báo'}</button>
              </form>
              <div className="admin-chat-layout">
                <div className="admin-chat-list">
                  {chatConversations.map((conversation) => (
                    <button key={conversation.id} type="button" className={selectedChatConversation?.id === conversation.id ? 'active' : ''} onClick={() => void selectChatConversation(conversation)}>
                      <strong>{conversation.user_email ?? conversation.user_id}</strong>
                      <span>{latestChatPreview(conversation.latest_message)}</span>
                      <small>{conversation.status} · {formatHistoryDate(conversation.last_message_at)}</small>
                      {conversation.unread_count > 0 && <em>{conversation.unread_count}</em>}
                    </button>
                  ))}
                  {chatConversations.length === 0 && <p className="field-hint">Chưa có cuộc trò chuyện.</p>}
                </div>
                <div className="admin-chat-thread">
                  {selectedChatConversation ? (
                    <>
                      <div className="admin-chat-thread-header">
                        <div><strong>{selectedChatConversation.user_email ?? selectedChatConversation.user_id}</strong><span>{selectedChatConversation.status}</span></div>
                        <button type="button" className="secondary-button" disabled={selectedChatConversation.status === 'closed'} onClick={() => void closeChat()}>Đóng</button>
                      </div>
                      <div className="admin-chat-messages">
                        {chatMessages.map((message) => <div key={message.id} className={`admin-chat-message ${message.sender_role === 'admin' ? 'from-admin' : 'from-user'}`}><ChatMessageContent message={message} /><time>{formatHistoryDate(message.created_at)}</time></div>)}
                        {userTypingConversationId === selectedChatConversation.id && <div className="chat-typing-indicator admin-chat-typing">Người dùng đang nhập...</div>}
                      </div>
                      {selectedChatConversation.status === 'open' ? (
                        <form className="admin-chat-reply" onSubmit={(event) => { event.preventDefault(); void sendChatReply(); }}>
                          {adminSelectedImagePreview && (
                            <div className="chat-image-preview admin-chat-image-preview">
                              <img src={adminSelectedImagePreview} alt="Ảnh chuẩn bị gửi" />
                              <button type="button" onClick={clearAdminSelectedImage} aria-label="Bỏ ảnh">×</button>
                            </div>
                          )}
                          <input ref={adminFileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="sr-only" onChange={(event) => handleAdminImageSelect(event.target.files?.[0] ?? null)} />
                          <button type="button" className="chat-attach-button admin-chat-attach-button" onClick={() => adminFileInputRef.current?.click()} aria-label="Đính kèm ảnh"><AttachFileIcon /></button>
                          <textarea
                            ref={adminReplyTextareaRef}
                            value={chatReply}
                            onChange={(event) => handleChatReplyChange(event.target.value)}
                            onInput={resizeAdminReplyTextarea}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter' && !event.shiftKey) {
                                event.preventDefault();
                                void sendChatReply();
                              }
                            }}
                            placeholder="Trả lời người dùng..."
                            rows={1}
                            maxLength={2000}
                          />
                          <button type="submit" className="admin-chat-send-button" disabled={(!chatReply.trim() && !adminSelectedImage) || sendingChat} aria-label="Gửi phản hồi">
                            {sendingChat ? <span aria-hidden="true">...</span> : <SendIcon />}
                          </button>
                        </form>
                      ) : <p className="field-hint">Cuộc trò chuyện đã đóng.</p>}
                    </>
                  ) : <p className="field-hint">Chọn một cuộc trò chuyện để xem nội dung.</p>}
                </div>
              </div>
            </section>
          </>
        )}

        {activeSection === 'audit' && (
          <>
            <header className="admin-page-header">
              <h2>Nhật ký kiểm toán</h2>
              <AdminToolbarRefreshButton loading={loading} onClick={() => void refreshActiveSection(true)} />
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


function ChatMessageContent({ message }: { message: ChatMessageResponse }) {
  return (
    <>
      {message.image_url && (
        <a className="chat-message-image-link" href={message.image_url} target="_blank" rel="noopener noreferrer">
          <img className="chat-message-image" src={message.image_url} alt={message.image_original_name ?? 'Ảnh trong chat'} />
        </a>
      )}
      {message.body && <p>{message.body}</p>}
    </>
  );
}

function latestChatPreview(message?: ChatMessageResponse | null) {
  if (!message) return 'Chưa có tin nhắn';
  if (message.body) return message.body;
  return message.message_type === 'image' ? 'Ảnh' : 'Chưa có tin nhắn';
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function playChatNotificationSound() {
  const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return;
  const context = new AudioContextClass();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = 'sine';
  oscillator.frequency.setValueAtTime(720, context.currentTime);
  oscillator.frequency.exponentialRampToValueAtTime(920, context.currentTime + 0.12);
  gain.gain.setValueAtTime(0.0001, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.18);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.2);
}

function upsertConversation(current: ChatConversationResponse[], conversation: ChatConversationResponse) {
  const merged = current.some((item) => item.id === conversation.id)
    ? current.map((item) => item.id === conversation.id ? { ...item, ...conversation } : item)
    : [conversation, ...current];
  return [...merged].sort((a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime());
}

async function loadAdminPlans(settings: SystemSettingResponse[]): Promise<AdminPlanResponse[]> {
  try {
    return await getAdminPlans();
  } catch (error) {
    const legacy = settings.find((item) => item.key === 'plan_settings')?.value as Record<string, unknown> | undefined;
    const plansValue = legacy?.plans && typeof legacy.plans === 'object' ? legacy.plans as Record<string, unknown> : {};
    const ids = Object.keys(plansValue).length > 0 ? Object.keys(plansValue) : ['free', 'pro', 'pro_plus'];
    return ids.map((id, index) => {
      const data = plansValue[id] && typeof plansValue[id] === 'object' ? plansValue[id] as Record<string, unknown> : {};
      return {
        id,
        name: planLabel(id),
        daily_render_limit: typeof data.daily_render_limit === 'number' ? data.daily_render_limit : defaultPlanLimit(id),
        daily_ocr_limit: typeof data.daily_ocr_limit === 'number' ? data.daily_ocr_limit : defaultPlanLimit(id),
        sort_order: (index + 1) * 10,
        is_active: true,
        created_at: '',
        updated_at: '',
      };
    });
  }
}

function defaultPlanLimit(id: string) {
  if (id === 'free') return 20;
  if (id === 'pro') return 200;
  return null;
}

function adminAiSettingsValue(value: Record<string, unknown>, defaults: SettingsDefaults | null) {
  if (!defaults) return value;
  const next: Record<string, unknown> = { ...value, default_provider: defaults.default_provider, ocr: defaults.ocr };
  (['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const).forEach((provider) => {
    const current = value[provider] && typeof value[provider] === 'object' ? value[provider] as Record<string, unknown> : {};
    const providerDefaults = defaults[provider];
    next[provider] = {
      ...current,
      base_url: providerDefaults.base_url,
      model: providerDefaults.model ?? '',
      scanned_models: providerDefaults.scanned_models,
      allowed_model_ids: providerDefaults.allowed_model_ids,
      ...(provider === 'router9' ? { only_mode: defaults.router9.only_mode } : {}),
    };
  });
  return next;
}

function adminAiTierProfilesValue(value: unknown, defaults: SettingsDefaults | null) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  if (Object.keys(data).length > 0) {
    if ('tier1' in data || 'tier2' in data || 'tier3' in data) return data;
    const legacyRender = data.render && typeof data.render === 'object' ? data.render as Record<string, unknown> : {};
    return {
      version: 3,
      tier1: legacyTierValue(legacyRender.tier1, 'tier1'),
      tier2: legacyTierValue(legacyRender.tier2, 'tier2'),
      tier3: legacyTierValue(legacyRender.tier3, 'tier3'),
    };
  }
  const profiles = defaults?.registry_task_profiles ?? [];
  const byTask = Object.fromEntries(profiles.map((profile) => [profile.task, profile]));
  const result: Record<string, unknown> = { version: 3 };
  for (const tier of ['tier1', 'tier2', 'tier3']) {
    const profile = byTask[`render_${tier}`];
    result[tier] = profile
      ? { tier, default_model: formatAdminTierModelRef(profile.provider_id, profile.model_id), models: taskProfileModels(profile.provider_id, profile.model_id, profile.fallbacks) }
      : { tier, default_model: '', models: [] };
  }
  return result;
}

function legacyTierValue(value: unknown, tier: string) {
  const profile = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const provider = typeof profile.provider === 'string' ? profile.provider : 'auto';
  const model = typeof profile.model === 'string' ? profile.model : '';
  const defaultModel = formatAdminTierModelRef(provider, model);
  return { tier, default_model: defaultModel, models: defaultModel ? [defaultModel] : [] };
}

function taskProfileModels(provider: string, model: string, fallbacks: string[]) {
  const models: string[] = [];
  if (model) models.push(formatAdminTierModelRef(provider, model));
  for (const fallback of fallbacks) {
    const modelRef = formatAdminTierFallbackModelRef(provider, fallback);
    if (modelRef && !models.includes(modelRef)) models.push(modelRef);
  }
  return models;
}

function formatAdminTierModelRef(provider: string, model: string) {
  if (!model) return '';
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') {
    return model.startsWith(`${provider}/`) ? model : `${provider}/${model}`;
  }
  return model;
}

function formatAdminTierFallbackModelRef(provider: string, model: string) {
  if (!model) return '';
  return hasAdminTierProviderPrefix(model) ? model : formatAdminTierModelRef(provider, model);
}

function hasAdminTierProviderPrefix(model: string) {
  return ['openrouter/', 'nvidia/', 'ollama/', 'openai_compat/', 'openai-compat/', 'router9/'].some((prefix) => model.startsWith(prefix));
}

function adminAiProfilesValue(value: unknown, defaults: SettingsDefaults | null) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const profiles = defaults?.registry_task_profiles ?? [];
  const byTask = Object.fromEntries(profiles.map((profile) => [profile.task, profile]));
  const geometry = byTask.reasoning;
  const solver = byTask.solver_explanation;
  const ocr = byTask.ocr;
  if (Object.keys(data).length === 0) {
    if (profiles.length === 0) return data;
    return {
      version: 1,
      ...(geometry ? { geometry_reasoning: { provider: geometry.provider_id, model: geometry.model_id, fallbacks: geometry.fallbacks } } : {}),
      ...(solver ? { solver_explanation: { provider: solver.provider_id, model: solver.model_id, fallbacks: solver.fallbacks } } : {}),
      ...(ocr ? { ocr: { provider: ocr.provider_id, model: ocr.model_id, fallbacks: ocr.fallbacks } } : {}),
    };
  }
  return {
    ...data,
    ...(data.geometry_reasoning === undefined && geometry ? { geometry_reasoning: { provider: geometry.provider_id, model: geometry.model_id, fallbacks: geometry.fallbacks } } : {}),
    ...(data.solver_explanation === undefined && solver ? { solver_explanation: { provider: solver.provider_id, model: solver.model_id, fallbacks: solver.fallbacks } } : {}),
    ...(data.ocr === undefined && ocr ? { ocr: { provider: ocr.provider_id, model: ocr.model_id, fallbacks: ocr.fallbacks } } : {}),
  };
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
