import { API_BASE_URL, cleanText, queryString, requestJson } from './core';

export type ChatStatus = 'open' | 'closed';
export type ChatSenderRole = 'user' | 'admin' | 'system';
export type ChatMessageType = 'text' | 'image';

export interface ChatMessageResponse {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_role: ChatSenderRole;
  body: string;
  created_at: string;
  message_type: ChatMessageType;
  image_url?: string | null;
  image_public_id?: string | null;
  image_width?: number | null;
  image_height?: number | null;
  image_bytes?: number | null;
  image_format?: string | null;
  image_original_name?: string | null;
}

export interface ChatConversationResponse {
  id: string;
  user_id: string;
  status: ChatStatus;
  assigned_admin_id?: string | null;
  last_message_at: string;
  user_last_read_at?: string | null;
  admin_last_read_at?: string | null;
  created_at: string;
  updated_at: string;
  user_email?: string | null;
  user_display_name?: string | null;
  unread_count: number;
  latest_message?: ChatMessageResponse | null;
}

export interface ChatConversationDetailResponse {
  conversation: ChatConversationResponse;
  messages: ChatMessageResponse[];
}

export interface ChatWsTicketResponse {
  ticket: string;
  expires_at: string;
}

export interface AdminChatConversationFilters {
  status?: string;
  q?: string;
}

export type ChatWsEvent =
  | { type: 'connected'; user_id: string; role: 'user' | 'admin' }
  | { type: 'message.created'; conversation_id: string; message: ChatMessageResponse; conversation: ChatConversationResponse }
  | { type: 'conversation.updated'; conversation_id: string; conversation: ChatConversationResponse }
  | { type: 'conversation.read'; conversation_id: string; reader_role: 'user' | 'admin'; conversation: ChatConversationResponse }
  | { type: 'typing'; conversation_id: string; user_id: string; role: 'user' | 'admin'; is_typing: boolean }
  | { type: 'pong' };

export async function getChatConversation(): Promise<ChatConversationDetailResponse> {
  return requestJson('/api/chat/conversation', { credentials: 'include' }, 'Không thể tải cuộc trò chuyện.');
}

export async function getChatMessages(conversationId: string, before?: string): Promise<ChatMessageResponse[]> {
  return requestJson(`/api/chat/conversations/${encodeURIComponent(conversationId)}/messages${queryString({ before })}`, { credentials: 'include' }, 'Không thể tải tin nhắn.');
}

export async function sendChatMessage(conversationId: string, body: string): Promise<ChatMessageResponse> {
  return requestJson(`/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ body: cleanText(body) ?? '' }),
  }, 'Không thể gửi tin nhắn.');
}

export async function sendChatImage(conversationId: string, file: File, caption?: string): Promise<ChatMessageResponse> {
  const formData = new FormData();
  formData.set('file', file);
  const cleanCaption = cleanText(caption ?? '');
  if (cleanCaption) formData.set('caption', cleanCaption);
  return requestJson(`/api/chat/conversations/${encodeURIComponent(conversationId)}/messages/image`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  }, 'Không thể gửi ảnh.');
}

export async function markChatRead(conversationId: string): Promise<ChatConversationResponse> {
  return requestJson(`/api/chat/conversations/${encodeURIComponent(conversationId)}/read`, { method: 'POST', credentials: 'include' }, 'Không thể đánh dấu đã đọc.');
}

export async function createChatWsTicket(): Promise<ChatWsTicketResponse> {
  return requestJson('/api/chat/ws-ticket', { method: 'POST', credentials: 'include' }, 'Không thể tạo kết nối chat realtime.');
}

export async function getAdminChatConversations(filters: AdminChatConversationFilters = {}): Promise<ChatConversationResponse[]> {
  return requestJson(`/api/admin/chat/conversations${queryString(filters)}`, { credentials: 'include' }, 'Không thể tải inbox chat.');
}

export async function getAdminChatConversation(conversationId: string): Promise<ChatConversationDetailResponse> {
  return requestJson(`/api/admin/chat/conversations/${encodeURIComponent(conversationId)}`, { credentials: 'include' }, 'Không thể tải cuộc trò chuyện.');
}

export async function sendAdminChatMessage(conversationId: string, body: string): Promise<ChatMessageResponse> {
  return requestJson(`/api/admin/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ body: cleanText(body) ?? '' }),
  }, 'Không thể gửi tin nhắn admin.');
}

export async function sendAdminChatImage(conversationId: string, file: File, caption?: string): Promise<ChatMessageResponse> {
  const formData = new FormData();
  formData.set('file', file);
  const cleanCaption = cleanText(caption ?? '');
  if (cleanCaption) formData.set('caption', cleanCaption);
  return requestJson(`/api/admin/chat/conversations/${encodeURIComponent(conversationId)}/messages/image`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  }, 'Không thể gửi ảnh admin.');
}

export async function markAdminChatRead(conversationId: string): Promise<ChatConversationResponse> {
  return requestJson(`/api/admin/chat/conversations/${encodeURIComponent(conversationId)}/read`, { method: 'POST', credentials: 'include' }, 'Không thể đánh dấu chat đã đọc.');
}

export async function closeAdminChatConversation(conversationId: string): Promise<ChatConversationResponse> {
  return requestJson(`/api/admin/chat/conversations/${encodeURIComponent(conversationId)}/close`, { method: 'POST', credentials: 'include' }, 'Không thể đóng cuộc trò chuyện.');
}

export async function createChatWebSocket(): Promise<WebSocket> {
  const { ticket } = await createChatWsTicket();
  return new WebSocket(`${chatWsBaseUrl()}/ws/chat?ticket=${encodeURIComponent(ticket)}`);
}

function chatWsBaseUrl() {
  const explicitWsUrl = import.meta.env.VITE_WS_BASE_URL?.trim().replace(/\/$/, '');
  if (explicitWsUrl) return explicitWsUrl;
  if (API_BASE_URL.startsWith('http://')) return API_BASE_URL.replace(/^http:/, 'ws:');
  if (API_BASE_URL.startsWith('https://')) return API_BASE_URL.replace(/^https:/, 'wss:');
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${API_BASE_URL}`;
}
