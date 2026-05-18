import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { ApiError, createChatWebSocket, getChatConversation, markChatRead, sendChatMessage, type ChatConversationResponse, type ChatMessageResponse, type ChatWsEvent, type UserResponse } from '../api/client';

type LocalChatMessage = ChatMessageResponse & { local_status?: 'sending' | 'sent' | 'error'; retry_body?: string };

interface ChatBubbleProps {
  user: UserResponse | null;
  onToast: (title: string, message: string, kind?: 'error' | 'info' | 'warning') => void;
}

export function ChatBubble({ user, onToast }: ChatBubbleProps) {
  const [open, setOpen] = useState(false);
  const [conversation, setConversation] = useState<ChatConversationResponse | null>(null);
  const [messages, setMessages] = useState<LocalChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [adminTyping, setAdminTyping] = useState(false);
  const [unread, setUnread] = useState(0);
  const [bubbleBottom, setBubbleBottom] = useState(92);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const openRef = useRef(open);
  const conversationRef = useRef(conversation);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const dragRef = useRef<{ pointerId: number; startY: number; startBottom: number; moved: boolean } | null>(null);
  const typingTimeoutRef = useRef<number | null>(null);
  const stopTypingTimeoutRef = useRef<number | null>(null);
  const sentTypingRef = useRef(false);

  useEffect(() => { openRef.current = open; }, [open]);
  useEffect(() => { conversationRef.current = conversation; }, [conversation]);

  useEffect(() => {
    if (!user || user.role === 'admin') return;
    void connectWs();
    return () => {
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
      if (typingTimeoutRef.current) window.clearTimeout(typingTimeoutRef.current);
      if (stopTypingTimeoutRef.current) window.clearTimeout(stopTypingTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [user?.id, user?.role]);

  useEffect(() => {
    if (!open) return;
    void ensureConversation();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, open]);

  useEffect(() => {
    resizeTextarea();
  }, [input, open]);

  async function ensureConversation() {
    if (!user) {
      onToast('Chat admin', 'Bạn cần đăng nhập để chat với quản trị viên.', 'info');
      return;
    }
    if (user.role === 'admin') {
      onToast('Chat admin', 'Tài khoản admin hãy dùng mục Chat trong Admin Dashboard.', 'info');
      return;
    }
    if (conversation || loading) return;
    setLoading(true);
    try {
      const detail = await getChatConversation();
      setConversation(detail.conversation);
      setMessages(detail.messages);
      setUnread(0);
      void markChatRead(detail.conversation.id).catch(() => undefined);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : 'Không thể tải cuộc trò chuyện.';
      onToast('Chat admin', message, 'error');
    } finally {
      setLoading(false);
    }
  }

  async function connectWs() {
    try {
      const ws = await createChatWebSocket();
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        reconnectRef.current = window.setTimeout(() => void connectWs(), 2500);
      };
      ws.onerror = () => undefined;
      ws.onmessage = (event) => handleWsMessage(event.data);
    } catch {
      setConnected(false);
      reconnectRef.current = window.setTimeout(() => void connectWs(), 4000);
    }
  }

  function handleWsMessage(data: string) {
    let event: ChatWsEvent;
    try {
      event = JSON.parse(data) as ChatWsEvent;
    } catch {
      return;
    }
    if (event.type === 'message.created') {
      if (conversationRef.current && event.conversation_id !== conversationRef.current.id) return;
      setConversation(event.conversation);
      setMessages((current) => current.some((item) => item.id === event.message.id) ? current : [...current, event.message]);
      if (event.message.sender_role === 'admin') {
        if (openRef.current) {
          void markChatRead(event.conversation_id).catch(() => undefined);
        } else {
          setUnread((value) => value + 1);
          onToast('Tin nhắn từ admin', event.message.body.slice(0, 120), 'info');
        }
      }
    }
    if (event.type === 'conversation.updated' || event.type === 'conversation.read') {
      if (!conversationRef.current || event.conversation_id === conversationRef.current.id) setConversation(event.conversation);
    }
    if (event.type === 'typing' && event.role === 'admin') {
      if (conversationRef.current && event.conversation_id !== conversationRef.current.id) return;
      setAdminTyping(event.is_typing);
      if (typingTimeoutRef.current) window.clearTimeout(typingTimeoutRef.current);
      if (event.is_typing) typingTimeoutRef.current = window.setTimeout(() => setAdminTyping(false), 2500);
    }
  }

  async function handleSend() {
    if (!user || user.role === 'admin') {
      await ensureConversation();
      return;
    }
    const body = input.trim();
    if (!body || sending) return;
    const activeConversation = conversation ?? (await getChatConversation()).conversation;
    setConversation(activeConversation);
    const localId = `local-${Date.now()}`;
    const pending: LocalChatMessage = { id: localId, conversation_id: activeConversation.id, sender_user_id: user.id, sender_role: 'user', body, created_at: new Date().toISOString(), local_status: 'sending', retry_body: body };
    setMessages((current) => [...current, pending]);
    setSending(true);
    try {
      const message = await sendChatMessage(activeConversation.id, body);
      setMessages((current) => current.map((item) => item.id === localId ? { ...message, local_status: 'sent' } : item));
      setInput('');
      sendTyping(false);
      window.requestAnimationFrame(resizeTextarea);
    } catch (caught) {
      setMessages((current) => current.map((item) => item.id === localId ? { ...item, local_status: 'error' } : item));
      const message = caught instanceof ApiError ? caught.message : 'Không thể gửi tin nhắn.';
      onToast('Chat admin', message, 'error');
    } finally {
      setSending(false);
    }
  }

  async function retryMessage(message: LocalChatMessage) {
    if (!message.retry_body || sending) return;
    setMessages((current) => current.filter((item) => item.id !== message.id));
    setInput(message.retry_body);
    window.setTimeout(() => void handleSend(), 0);
  }

  function toggleOpen() {
    if (dragRef.current?.moved) return;
    setOpen((value) => {
      const next = !value;
      if (next) setUnread(0);
      if (next && conversationRef.current) void markChatRead(conversationRef.current.id).catch(() => undefined);
      return next;
    });
  }

  function handleBubblePointerDown(event: PointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, startY: event.clientY, startBottom: bubbleBottom, moved: false };
  }

  function handleBubblePointerMove(event: PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const delta = drag.startY - event.clientY;
    if (Math.abs(delta) > 4) drag.moved = true;
    setBubbleBottom(clamp(drag.startBottom + delta, 18, window.innerHeight - 96));
  }

  function handleBubblePointerUp(event: PointerEvent<HTMLButtonElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    window.setTimeout(() => {
      dragRef.current = null;
    }, 0);
  }

  function resizeTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 118)}px`;
  }

  function sendTyping(isTyping: boolean) {
    if (!conversationRef.current || wsRef.current?.readyState !== WebSocket.OPEN) return;
    if (sentTypingRef.current === isTyping) return;
    sentTypingRef.current = isTyping;
    wsRef.current.send(JSON.stringify({ type: 'typing', conversation_id: conversationRef.current.id, is_typing: isTyping }));
  }

  function handleInputChange(value: string) {
    setInput(value);
    if (!value.trim()) {
      sendTyping(false);
      return;
    }
    sendTyping(true);
    if (stopTypingTimeoutRef.current) window.clearTimeout(stopTypingTimeoutRef.current);
    stopTypingTimeoutRef.current = window.setTimeout(() => sendTyping(false), 1200);
  }

  return (
    <div className={`chat-bubble ${open ? 'is-open' : ''}`} style={{ bottom: bubbleBottom }}>
      {open && (
        <section className="chat-panel" aria-label="Chat với admin">
          <header className="chat-panel-header">
            <div>
              <strong>Chat với admin</strong>
              <span className={`chat-runtime-status ${connected ? 'is-online' : 'is-connecting'}`}><i aria-hidden="true" />{connected ? 'Realtime đã kết nối' : 'Đang kết nối realtime...'}</span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Đóng chat">×</button>
          </header>
          <div className="chat-messages">
            {loading && <p className="chat-empty">Đang tải cuộc trò chuyện...</p>}
            {!loading && messages.length === 0 && <p className="chat-empty">Gửi câu hỏi cho admin. Bạn sẽ nhận phản hồi tại đây.</p>}
            {messages.map((message) => (
              <div key={message.id} className={`chat-message ${message.sender_role === 'admin' ? 'from-admin' : 'from-user'}`}>
                <p>{message.body}</p>
                <time>{message.local_status ? sendStatusText(message.local_status) : formatChatTime(message.created_at)}</time>
                {message.local_status === 'error' && <button type="button" className="chat-retry-button" onClick={() => void retryMessage(message)}>Gửi lại</button>}
              </div>
            ))}
            {adminTyping && <div className="chat-typing-indicator">Admin đang nhập...</div>}
            <div ref={messagesEndRef} />
          </div>
          {conversation?.status === 'closed' ? (
            <div className="chat-closed">Cuộc trò chuyện đã đóng.</div>
          ) : (
            <form className="chat-input-row" onSubmit={(event) => { event.preventDefault(); void handleSend(); }}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(event) => handleInputChange(event.target.value)}
                onInput={resizeTextarea}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                maxLength={2000}
                placeholder="Nhập tin nhắn..."
                rows={1}
              />
              <button type="submit" className="chat-send-button" disabled={!input.trim() || sending} aria-label="Gửi tin nhắn">
                {sending ? <span aria-hidden="true">...</span> : <SendIcon />}
              </button>
            </form>
          )}
        </section>
      )}
      <button
        type="button"
        className="chat-bubble-button"
        onPointerDown={handleBubblePointerDown}
        onPointerMove={handleBubblePointerMove}
        onPointerUp={handleBubblePointerUp}
        onClick={toggleOpen}
        aria-label="Chat với admin"
      >
        <svg viewBox="0 0 1024 940" aria-hidden="true">
          <g fill="#ffffff" stroke="#000000" strokeWidth="28" strokeLinecap="round" strokeLinejoin="round">
            <path d="M760 325C902 350 1008 468 1008 610C1008 698 966 776 901 826L1007 925L842 846C803 864 760 874 714 874C594 874 491 804 449 704C419 632 422 550 457 481C507 380 626 302 760 325Z" />
            <path d="M410 14C630 14 809 191 809 409C809 627 630 804 410 804C348 804 289 791 236 766L14 880L117 646C51 578 14 494 14 409C14 191 190 14 410 14Z" />
          </g>
          <g fill="none" stroke="#000000" strokeWidth="24" strokeLinecap="round">
            <line x1="214" y1="284" x2="610" y2="284" />
            <line x1="130" y1="414" x2="696" y2="414" />
            <line x1="214" y1="542" x2="610" y2="542" />
            <line x1="807" y1="519" x2="858" y2="519" />
            <line x1="775" y1="617" x2="926" y2="617" />
            <line x1="721" y1="715" x2="858" y2="715" />
          </g>
        </svg>
        {unread > 0 && <span className="chat-unread-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatChatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

function sendStatusText(status: NonNullable<LocalChatMessage['local_status']>) {
  if (status === 'sending') return 'Đang gửi...';
  if (status === 'error') return 'Gửi lỗi';
  return 'Đã gửi';
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12 20 4l-5.4 16-3.1-6.5L4 12Z" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11.5 13.5 20 4" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}
