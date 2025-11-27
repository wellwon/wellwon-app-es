// =============================================================================
// File: src/api/chat.ts — Chat Domain API Client
// =============================================================================

import { API } from "./core";

// -----------------------------------------------------------------------------
// Types (matching backend chat queries and API models)
// -----------------------------------------------------------------------------

export interface ChatDetail {
  id: string;
  name: string | null;
  chat_type: string;
  created_by: string;
  company_id: string | null;
  created_at: string;
  updated_at: string | null;
  is_active: boolean;
  participant_count: number;
  // Last message info
  last_message_at: string | null;
  last_message_content: string | null;
  last_message_sender_id: string | null;
  // Telegram integration
  telegram_chat_id: number | null;
  telegram_topic_id: number | null;
}

export interface ChatListItem {
  id: string;
  name: string | null;
  chat_type: string;
  participant_count: number;
  last_message_at: string | null;
  last_message_content: string | null;
  is_active: boolean;
  unread_count: number;
  other_participant_name: string | null;
}

export interface Message {
  id: string;
  chat_id: string;
  sender_id: string | null;
  content: string;
  message_type: string;
  reply_to_id: string | null;
  created_at: string;
  updated_at: string | null;
  is_edited: boolean;
  is_deleted: boolean;
  // File info
  file_url: string | null;
  file_name: string | null;
  file_size: number | null;
  file_type: string | null;
  voice_duration: number | null;
  // Source
  source: string;
  telegram_message_id: number | null;
  // Sender info (joined)
  sender_name: string | null;
  sender_avatar_url: string | null;
  // Reply info (joined)
  reply_to_content: string | null;
  reply_to_sender_name: string | null;
}

export interface ChatParticipant {
  id: string;
  chat_id: string;
  user_id: string;
  role: string;
  joined_at: string;
  is_active: boolean;
  last_read_at: string | null;
  last_read_message_id: string | null;
  // User info (joined)
  user_name: string | null;
  user_email: string | null;
  user_avatar_url: string | null;
}

export interface UnreadCount {
  total_unread: number;
  unread_chats: number;
}

// Request types
export interface CreateChatRequest {
  name?: string;
  chat_type: string;
  company_id?: string;
  participant_ids?: string[];
}

export interface UpdateChatRequest {
  name?: string;
}

export interface SendMessageRequest {
  content: string;
  message_type?: string;
  reply_to_id?: string;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  voice_duration?: number;
}

export interface EditMessageRequest {
  content: string;
}

export interface AddParticipantRequest {
  user_id: string;
  role?: string;
}

export interface LinkTelegramRequest {
  telegram_group_id: number;
  telegram_topic_id?: number;
}

export interface MarkAsReadRequest {
  message_ids: string[];
}

// Response wrapper for command results
export interface CommandResponse {
  id: string;
  status: string;
  message?: string;
}

// -----------------------------------------------------------------------------
// Chat CRUD Operations
// -----------------------------------------------------------------------------

export async function getChats(
  includeArchived: boolean = false,
  limit: number = 50,
  offset: number = 0
): Promise<ChatListItem[]> {
  const { data } = await API.get<ChatListItem[]>("/chats", {
    params: {
      include_archived: includeArchived,
      limit,
      offset,
    },
  });
  return data;
}

export async function getChatById(chatId: string): Promise<ChatDetail> {
  const { data } = await API.get<ChatDetail>(`/chats/${chatId}`);
  return data;
}

export async function createChat(request: CreateChatRequest): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>("/chats", request);
  return data;
}

export async function updateChat(
  chatId: string,
  request: UpdateChatRequest
): Promise<CommandResponse> {
  const { data } = await API.patch<CommandResponse>(`/chats/${chatId}`, request);
  return data;
}

export async function archiveChat(chatId: string): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/archive`);
  return data;
}

export async function deleteChat(chatId: string): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/chats/${chatId}`);
  return data;
}

export async function searchChats(
  searchTerm: string,
  limit: number = 20
): Promise<ChatDetail[]> {
  const { data } = await API.get<ChatDetail[]>("/chats/search", {
    params: { q: searchTerm, limit },
  });
  return data;
}

export async function getUnreadCount(): Promise<UnreadCount> {
  const { data } = await API.get<UnreadCount>("/chats/unread-count");
  return data;
}

// -----------------------------------------------------------------------------
// Message Operations
// -----------------------------------------------------------------------------

export async function getMessages(
  chatId: string,
  options?: {
    limit?: number;
    offset?: number;
    before_id?: string;
    after_id?: string;
  }
): Promise<Message[]> {
  const { data } = await API.get<Message[]>(`/chats/${chatId}/messages`, {
    params: options,
  });
  return data;
}

export async function sendMessage(
  chatId: string,
  request: SendMessageRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/messages`, request);
  return data;
}

export async function editMessage(
  chatId: string,
  messageId: string,
  request: EditMessageRequest
): Promise<CommandResponse> {
  const { data } = await API.patch<CommandResponse>(
    `/chats/${chatId}/messages/${messageId}`,
    request
  );
  return data;
}

export async function deleteMessage(
  chatId: string,
  messageId: string
): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/chats/${chatId}/messages/${messageId}`);
  return data;
}

export async function markAsRead(
  chatId: string,
  request: MarkAsReadRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/read`, request);
  return data;
}

export async function searchMessages(
  chatId: string,
  searchTerm: string,
  limit: number = 20
): Promise<Message[]> {
  const { data } = await API.get<Message[]>(`/chats/${chatId}/messages/search`, {
    params: { q: searchTerm, limit },
  });
  return data;
}

// -----------------------------------------------------------------------------
// Participant Operations
// -----------------------------------------------------------------------------

export async function getParticipants(
  chatId: string,
  includeInactive: boolean = false
): Promise<ChatParticipant[]> {
  const { data } = await API.get<ChatParticipant[]>(`/chats/${chatId}/participants`, {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function addParticipant(
  chatId: string,
  request: AddParticipantRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/participants`, request);
  return data;
}

export async function removeParticipant(
  chatId: string,
  userId: string
): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/chats/${chatId}/participants/${userId}`);
  return data;
}

export async function leaveChat(chatId: string): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/leave`);
  return data;
}

export async function changeParticipantRole(
  chatId: string,
  userId: string,
  role: string
): Promise<CommandResponse> {
  const { data } = await API.patch<CommandResponse>(`/chats/${chatId}/participants/${userId}`, {
    role,
  });
  return data;
}

// -----------------------------------------------------------------------------
// Typing Indicators
// -----------------------------------------------------------------------------

export async function startTyping(chatId: string): Promise<void> {
  await API.post(`/chats/${chatId}/typing/start`);
}

export async function stopTyping(chatId: string): Promise<void> {
  await API.post(`/chats/${chatId}/typing/stop`);
}

// -----------------------------------------------------------------------------
// Telegram Integration
// -----------------------------------------------------------------------------

export async function linkTelegramChat(
  chatId: string,
  request: LinkTelegramRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/chats/${chatId}/telegram/link`, request);
  return data;
}

export async function unlinkTelegramChat(chatId: string): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/chats/${chatId}/telegram/link`);
  return data;
}

// -----------------------------------------------------------------------------
// Company Chats
// -----------------------------------------------------------------------------

export async function getCompanyChats(
  companyId: string,
  includeArchived: boolean = false,
  limit: number = 50,
  offset: number = 0
): Promise<ChatDetail[]> {
  const { data } = await API.get<ChatDetail[]>(`/companies/${companyId}/chats`, {
    params: {
      include_archived: includeArchived,
      limit,
      offset,
    },
  });
  return data;
}

// -----------------------------------------------------------------------------
// Direct Chat Helpers
// -----------------------------------------------------------------------------

export async function getOrCreateDirectChat(userId: string): Promise<ChatDetail> {
  const { data } = await API.post<ChatDetail>("/chats/direct", { user_id: userId });
  return data;
}

// -----------------------------------------------------------------------------
// Message Templates
// -----------------------------------------------------------------------------

export interface TemplateData {
  type: string;
  title: string;
  description: string;
  image_url?: string;
  image_position?: 'left' | 'right';
  buttons: Array<{
    text: string;
    action: string;
    style?: string;
  }>;
}

export interface MessageTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string;
  template_data: TemplateData;
  image_url: string | null;
  created_by: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface TemplatesByCategoryResponse {
  categories: Record<string, MessageTemplate[]>;
}

export async function getAllTemplates(activeOnly: boolean = true): Promise<MessageTemplate[]> {
  const { data } = await API.get<MessageTemplate[]>("/chats/templates", {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function getTemplatesByCategory(
  activeOnly: boolean = true
): Promise<Record<string, MessageTemplate[]>> {
  const { data } = await API.get<TemplatesByCategoryResponse>("/chats/templates/by-category", {
    params: { active_only: activeOnly },
  });
  return data.categories;
}

export async function getTemplateById(templateId: string): Promise<MessageTemplate | null> {
  try {
    const { data } = await API.get<MessageTemplate>(`/chats/templates/${templateId}`);
    return data;
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------------
// File Upload Operations
// -----------------------------------------------------------------------------

export interface FileUploadResponse {
  success: boolean;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  error?: string;
}

export interface VoiceUploadResponse {
  success: boolean;
  file_url?: string;
  duration?: number;
  error?: string;
}

export async function uploadChatFile(
  chatId: string,
  file: File
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await API.post<FileUploadResponse>(
    `/chats/${chatId}/upload/file`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return data;
}

export async function uploadVoiceMessage(
  chatId: string,
  audioBlob: Blob,
  duration: number
): Promise<VoiceUploadResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, "voice-message.webm");

  const { data } = await API.post<VoiceUploadResponse>(
    `/chats/${chatId}/upload/voice`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      params: { duration },
    }
  );
  return data;
}
