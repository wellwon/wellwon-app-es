/**
 * Chat domain React Query hooks
 * Replaces MessageTemplateService and chat-related services
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import { queryKeys } from '@/lib/queryKeys';

// Re-export types
export type { MessageTemplate, TemplateData } from '@/api/chat';

// =============================================================================
// Template Queries
// =============================================================================

/**
 * Fetch all templates
 */
export function useTemplates(activeOnly: boolean = true) {
  return useQuery({
    queryKey: queryKeys.templates.lists(),
    queryFn: () => chatApi.getAllTemplates(activeOnly),
  });
}

/**
 * Fetch templates grouped by category
 */
export function useTemplatesByCategory(activeOnly: boolean = true) {
  return useQuery({
    queryKey: queryKeys.templates.list({ category: 'all' }),
    queryFn: () => chatApi.getTemplatesByCategory(activeOnly),
  });
}

/**
 * Fetch single template by ID
 */
export function useTemplate(templateId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.templates.detail(templateId || ''),
    queryFn: () => chatApi.getTemplateById(templateId!),
    enabled: !!templateId,
  });
}

// =============================================================================
// Chat Queries
// =============================================================================

/**
 * Fetch user's chats
 */
export function useChats(options?: {
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: queryKeys.chats.lists(),
    queryFn: () => chatApi.getChats(
      options?.includeArchived ?? false,
      options?.limit ?? 50,
      options?.offset ?? 0
    ),
  });
}

/**
 * Fetch chats for a company
 */
export function useCompanyChats(companyId: string | undefined, options?: {
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: queryKeys.chats.byCompany(companyId || ''),
    queryFn: () => chatApi.getCompanyChats(
      companyId!,
      options?.includeArchived ?? false,
      options?.limit ?? 50,
      options?.offset ?? 0
    ),
    enabled: !!companyId,
  });
}

/**
 * Fetch single chat by ID
 */
export function useChat(chatId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.chats.detail(chatId || ''),
    queryFn: () => chatApi.getChatById(chatId!),
    enabled: !!chatId,
  });
}

/**
 * Fetch messages for a chat
 */
export function useMessages(chatId: string | undefined, options?: {
  limit?: number;
  offset?: number;
  before_id?: string;
  after_id?: string;
}) {
  return useQuery({
    queryKey: queryKeys.chats.messages(chatId || '', options),
    queryFn: () => chatApi.getMessages(chatId!, options),
    enabled: !!chatId,
  });
}

/**
 * Fetch participants for a chat
 */
export function useParticipants(chatId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.chats.participants(chatId || ''),
    queryFn: () => chatApi.getParticipants(chatId!, false),
    enabled: !!chatId,
  });
}

/**
 * Fetch unread count
 */
export function useUnreadCount() {
  return useQuery({
    queryKey: queryKeys.chats.unreadCount(),
    queryFn: () => chatApi.getUnreadCount(),
  });
}

// =============================================================================
// Chat Mutations
// =============================================================================

/**
 * Create a new chat
 */
export function useCreateChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: chatApi.createChat,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.all });
    },
  });
}

/**
 * Update a chat
 */
export function useUpdateChat(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: chatApi.UpdateChatRequest) =>
      chatApi.updateChat(chatId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.detail(chatId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.lists() });
    },
  });
}

/**
 * Archive a chat
 */
export function useArchiveChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: chatApi.archiveChat,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.all });
    },
  });
}

/**
 * Send a message
 */
export function useSendMessage(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: chatApi.SendMessageRequest) =>
      chatApi.sendMessage(chatId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.messages(chatId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.detail(chatId) });
    },
  });
}

/**
 * Edit a message
 */
export function useEditMessage(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      chatApi.editMessage(chatId, messageId, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.messages(chatId) });
    },
  });
}

/**
 * Delete a message
 */
export function useDeleteMessage(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (messageId: string) =>
      chatApi.deleteMessage(chatId, messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.messages(chatId) });
    },
  });
}

/**
 * Mark messages as read
 */
export function useMarkAsRead(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (messageIds: string[]) =>
      chatApi.markAsRead(chatId, { message_ids: messageIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.unreadCount() });
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.unreadCount(chatId) });
    },
  });
}

/**
 * Add participant to chat
 */
export function useAddParticipant(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: chatApi.AddParticipantRequest) =>
      chatApi.addParticipant(chatId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.participants(chatId) });
    },
  });
}

/**
 * Remove participant from chat
 */
export function useRemoveParticipant(chatId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) =>
      chatApi.removeParticipant(chatId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chats.participants(chatId) });
    },
  });
}

/**
 * Upload file to chat
 */
export function useUploadChatFile(chatId: string) {
  return useMutation({
    mutationFn: (file: File) => chatApi.uploadChatFile(chatId, file),
  });
}

/**
 * Upload voice message
 */
export function useUploadVoiceMessage(chatId: string) {
  return useMutation({
    mutationFn: ({ audioBlob, duration }: { audioBlob: Blob; duration: number }) =>
      chatApi.uploadVoiceMessage(chatId, audioBlob, duration),
  });
}
