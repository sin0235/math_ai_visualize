import { useEffect, useRef, useState } from 'react';
import { ApiError, createChatWebSocket, getChatConversation, markChatRead, sendChatMessage, type ChatConversationResponse, type ChatMessageResponse, type ChatWsEvent, type UserResponse } from '../api/client';

interface ChatBubbleProps {
  user: UserResponse | null;
  onToast: (title: string, message: string, kind?: 'error' | 'info' | 'warning') => void;
}

export function ChatBubble({ user, onToast }: ChatBubbleProps) {
  const [open, setOpen] = useState(false);
  const [conversation, setConversation] = useState<ChatConversationResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [unread, setUnread] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const openRef = useRef(open);
  const conversationRef = useRef(conversation);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => { openRef.current = open; }, [open]);
  useEffect(() => { conversationRef.current = conversation; }, [conversation]);

  useEffect(() => {
    if (!user || user.role === 'admin') return;
    void connectWs();
    return () => {
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
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
        setConnected(false);
        reconnectRef.current = window.setTimeout(() => void connectWs(), 2500);
      };
      ws.onerror = () => setConnected(false);
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
    setSending(true);
    try {
      const message = await sendChatMessage(activeConversation.id, body);
      setMessages((current) => current.some((item) => item.id === message.id) ? current : [...current, message]);
      setInput('');
      window.requestAnimationFrame(resizeTextarea);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : 'Không thể gửi tin nhắn.';
      onToast('Chat admin', message, 'error');
    } finally {
      setSending(false);
    }
  }

  function toggleOpen() {
    setOpen((value) => {
      const next = !value;
      if (next) setUnread(0);
      if (next && conversationRef.current) void markChatRead(conversationRef.current.id).catch(() => undefined);
      return next;
    });
  }

  function resizeTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 118)}px`;
  }

  return (
    <div className={`chat-bubble ${open ? 'is-open' : ''}`}>
      {open && (
        <section className="chat-panel" aria-label="Chat với admin">
          <header className="chat-panel-header">
            <div>
              <strong>Chat với admin</strong>
              <span>{connected ? 'Đang kết nối realtime' : 'Mất kết nối realtime'}</span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Đóng chat">×</button>
          </header>
          <div className="chat-messages">
            {loading && <p className="chat-empty">Đang tải cuộc trò chuyện...</p>}
            {!loading && messages.length === 0 && <p className="chat-empty">Gửi câu hỏi cho admin. Bạn sẽ nhận phản hồi tại đây.</p>}
            {messages.map((message) => (
              <div key={message.id} className={`chat-message ${message.sender_role === 'admin' ? 'from-admin' : 'from-user'}`}>
                <p>{message.body}</p>
                <time>{formatChatTime(message.created_at)}</time>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          {conversation?.status === 'closed' ? (
            <div className="chat-closed">Cuộc trò chuyện đã đóng.</div>
          ) : (
            <form className="chat-input-row" onSubmit={(event) => { event.preventDefault(); void handleSend(); }}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
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
      <button type="button" className="chat-bubble-button" onClick={toggleOpen} aria-label="Chat với admin">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2h9A3.5 3.5 0 0 1 20 5.5v7A3.5 3.5 0 0 1 16.5 16H11l-5.2 4.2A.8.8 0 0 1 4.5 19.6V16A3.5 3.5 0 0 1 1 12.5v-7Z" fill="currentColor" /></svg>
        {unread > 0 && <span className="chat-unread-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
    </div>
  );
}

function formatChatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12 20 4l-5.4 16-3.1-6.5L4 12Z" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11.5 13.5 20 4" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}
