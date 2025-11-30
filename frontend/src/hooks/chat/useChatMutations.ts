// =============================================================================
// File: src/hooks/chat/useChatMutations.ts
// Description: React Query mutations for chat operations with optimistic updates
// Pattern: TkDodo's useMutation with onMutate/onError/onSettled
// =============================================================================

import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { Message, SendMessageRequest } from '@/api/chat';
import { chatKeys, addOptimisticMessage, removeMessageFromCache } from './useChatMessages';
import { logger } from '@/utils/logger';
import { useAuth } from '@/contexts/AuthContext';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface SendMessageParams {
  chatId: string;
  content: string;
  messageType?: string;
  replyToId?: string;
  fileUrl?: string;
  fileName?: string;
  fileSize?: number;
  fileType?: string;
  voiceDuration?: number;
}

interface EditMessageParams {
  chatId: string;
  messageId: string;
  content: string;
}

interface DeleteMessageParams {
  chatId: string;
  messageId: string;
}

// -----------------------------------------------------------------------------
// useSendMessage - Mutation with optimistic update
// -----------------------------------------------------------------------------

export function useSendMessage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (params: SendMessageParams) => {
      const messageId = crypto.randomUUID();

      const request: SendMessageRequest = {
        message_id: messageId,
        content: params.content,
        message_type: params.messageType || 'text',
        reply_to_id: params.replyToId,
        file_url: params.fileUrl,
        file_name: params.fileName,
        file_size: params.fileSize,
        file_type: params.fileType,
        voice_duration: params.voiceDuration,
      };

      await chatApi.sendMessage(params.chatId, request);

      return { messageId, chatId: params.chatId };
    },

    onMutate: async (params) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: chatKeys.messages(params.chatId) });

      // Snapshot previous value
      const previousMessages = queryClient.getQueryData(chatKeys.messages(params.chatId));

      // Create optimistic message with client-generated UUID
      const messageId = crypto.randomUUID();
      const optimisticMessage: Message = {
        id: messageId,
        chat_id: params.chatId,
        sender_id: user?.id || null,
        content: params.content,
        message_type: params.messageType || 'text',
        reply_to_id: params.replyToId || null,
        file_url: params.fileUrl || null,
        file_name: params.fileName || null,
        file_size: params.fileSize || null,
        file_type: params.fileType || null,
        voice_duration: params.voiceDuration || null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        is_edited: false,
        is_deleted: false,
        source: 'web',
        telegram_message_id: null,
        sender_name: user?.user_metadata?.first_name || 'You',
        sender_avatar_url: user?.user_metadata?.avatar_url || null,
        reply_to_content: null,
        reply_to_sender_name: null,
      };

      // Optimistically add message to cache
      addOptimisticMessage(queryClient, params.chatId, optimisticMessage);

      logger.debug('Optimistic message added', { messageId, chatId: params.chatId });

      // Return context for rollback
      return { previousMessages, optimisticMessageId: messageId };
    },

    onError: (error, params, context) => {
      logger.error('Failed to send message, rolling back', { error, chatId: params.chatId });

      // Rollback to previous state
      if (context?.previousMessages) {
        queryClient.setQueryData(
          chatKeys.messages(params.chatId),
          context.previousMessages
        );
      }
    },

    onSuccess: (data, params) => {
      logger.debug('Message sent successfully', { messageId: data.messageId, chatId: params.chatId });

      // Invalidate chat list to update last_message
      queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
    },

    // Don't refetch on settle - WSE will update the cache
    onSettled: () => {
      // No invalidation needed - WSE handles real-time updates
    },
  });
}

// -----------------------------------------------------------------------------
// useEditMessage - Mutation with optimistic update
// -----------------------------------------------------------------------------

export function useEditMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: EditMessageParams) => {
      await chatApi.editMessage(params.chatId, params.messageId, {
        content: params.content,
      });
      return params;
    },

    onMutate: async (params) => {
      await queryClient.cancelQueries({ queryKey: chatKeys.messages(params.chatId) });

      const previousMessages = queryClient.getQueryData(chatKeys.messages(params.chatId));

      // Optimistically update message
      queryClient.setQueryData(
        chatKeys.messages(params.chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) =>
              m.id === params.messageId
                ? { ...m, content: params.content, is_edited: true, updated_at: new Date().toISOString() }
                : m
            ),
          }));

          return { ...oldData, pages: newPages };
        }
      );

      return { previousMessages };
    },

    onError: (error, params, context) => {
      logger.error('Failed to edit message, rolling back', { error, messageId: params.messageId });

      if (context?.previousMessages) {
        queryClient.setQueryData(
          chatKeys.messages(params.chatId),
          context.previousMessages
        );
      }
    },
  });
}

// -----------------------------------------------------------------------------
// useDeleteMessage - Mutation with optimistic update
// -----------------------------------------------------------------------------

export function useDeleteMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: DeleteMessageParams) => {
      await chatApi.deleteMessage(params.chatId, params.messageId);
      return params;
    },

    onMutate: async (params) => {
      await queryClient.cancelQueries({ queryKey: chatKeys.messages(params.chatId) });

      const previousMessages = queryClient.getQueryData(chatKeys.messages(params.chatId));

      // Optimistically remove message
      removeMessageFromCache(queryClient, params.chatId, params.messageId);

      logger.debug('Optimistically deleted message', { messageId: params.messageId });

      return { previousMessages };
    },

    onError: (error, params, context) => {
      logger.error('Failed to delete message, rolling back', { error, messageId: params.messageId });

      if (context?.previousMessages) {
        queryClient.setQueryData(
          chatKeys.messages(params.chatId),
          context.previousMessages
        );
      }
    },

    onSuccess: (data, params) => {
      logger.debug('Message deleted successfully', { messageId: params.messageId });

      // Invalidate chat list to update last_message
      queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
    },
  });
}

// -----------------------------------------------------------------------------
// useMarkAsRead - Mutation (no optimistic update needed)
// -----------------------------------------------------------------------------

export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: { chatId: string; messageId: string }) => {
      await chatApi.markAsRead(params.chatId, { last_read_message_id: params.messageId });
      return params;
    },

    onSuccess: () => {
      // Invalidate unread count
      queryClient.invalidateQueries({ queryKey: ['unread-count'] });
    },
  });
}

// -----------------------------------------------------------------------------
// useUploadFile - File upload mutation
// -----------------------------------------------------------------------------

export function useUploadFile() {
  return useMutation({
    mutationFn: async (params: { chatId: string; file: File }) => {
      const result = await chatApi.uploadChatFile(params.chatId, params.file);

      if (!result.success || !result.file_url) {
        throw new Error(result.error || 'File upload failed');
      }

      return result;
    },
  });
}

// -----------------------------------------------------------------------------
// useUploadVoice - Voice upload mutation
// -----------------------------------------------------------------------------

export function useUploadVoice() {
  return useMutation({
    mutationFn: async (params: { chatId: string; audioBlob: Blob; duration: number }) => {
      const result = await chatApi.uploadVoiceMessage(
        params.chatId,
        params.audioBlob,
        params.duration
      );

      if (!result.success || !result.file_url) {
        throw new Error(result.error || 'Voice upload failed');
      }

      return result;
    },
  });
}
