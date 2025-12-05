// =============================================================================
// File: src/hooks/chat/useChatMutations.ts
// Description: React Query mutations for chat operations with optimistic updates
// Pattern: TkDodo's useMutation with onMutate/onError/onSettled
// =============================================================================

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { v7 as uuidv7 } from 'uuid';  // UUIDv7: time-sortable, RFC 9562
import * as chatApi from '@/api/chat';
import type { Message, SendMessageRequest, SendMessageResponse } from '@/api/chat';
import { chatKeys, addOptimisticMessage, removeMessageFromCache, reconcileMessageId } from './useChatMessages';
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
  // Client temp ID for optimistic UI (Industry Standard - Discord/Slack pattern)
  // Format: "temp_<uuid>" - easy to identify as temporary
  _clientTempId?: string;
  // Idempotency key for exactly-once delivery (prevents duplicates on retry)
  _idempotencyKey?: string;
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

  const mutation = useMutation({
    mutationFn: async (params: SendMessageParams): Promise<SendMessageResponse & { chatId: string; clientTempId: string }> => {
      // Use the pre-generated client temp ID and idempotency key from params (set by wrapper below)
      const clientTempId = params._clientTempId!;
      const idempotencyKey = params._idempotencyKey!;

      const request: SendMessageRequest = {
        client_temp_id: clientTempId,
        idempotency_key: idempotencyKey,  // For exactly-once delivery
        content: params.content,
        message_type: params.messageType || 'text',
        reply_to_id: params.replyToId,
        file_url: params.fileUrl,
        file_name: params.fileName,
        file_size: params.fileSize,
        file_type: params.fileType,
        voice_duration: params.voiceDuration,
      };

      const response = await chatApi.sendMessage(params.chatId, request);

      // Return server's Snowflake ID + client temp ID for reconciliation
      return { ...response, chatId: params.chatId, clientTempId };
    },

    onMutate: async (params) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: chatKeys.messages(params.chatId) });

      // Snapshot previous value
      const previousMessages = queryClient.getQueryData(chatKeys.messages(params.chatId));

      // Use client temp ID for optimistic message (will be reconciled with Snowflake on success)
      const clientTempId = params._clientTempId!;
      const optimisticMessage: Message = {
        id: clientTempId,  // Temp ID (starts with "temp_")
        _stableKey: clientTempId,  // Stable key for React - persists through reconciliation (Discord/Slack pattern)
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

      logger.debug('Optimistic message added', { clientTempId, chatId: params.chatId });

      // Return context for rollback
      return { previousMessages, clientTempId };
    },

    onError: (error: any, params, context) => {
      logger.error('Failed to send message', { error, chatId: params.chatId });

      // DON'T rollback - keep message visible but mark as FAILED
      // User can see error state and retry
      if (context?.clientTempId) {
        const errorMessage = error?.response?.data?.message ||
                            error?.message ||
                            'Failed to send';

        queryClient.setQueryData(
          chatKeys.messages(params.chatId),
          (oldData: any) => {
            if (!oldData?.pages) return oldData;

            return {
              ...oldData,
              pages: oldData.pages.map((page: any) => ({
                ...page,
                messages: page.messages.map((msg: Message) => {
                  if (msg.id === context.clientTempId || (msg as any)._stableKey === context.clientTempId) {
                    return {
                      ...msg,
                      _failed: true,
                      _error: errorMessage,
                      _idempotencyKey: params._idempotencyKey, // Keep for retry
                    };
                  }
                  return msg;
                }),
              })),
            };
          }
        );

        logger.info('Message marked as failed, user can retry', {
          clientTempId: context.clientTempId,
          error: errorMessage,
        });
      }
    },

    onSuccess: (data, params, context) => {
      // Reconcile: replace temp ID with server's Snowflake ID
      // This ensures React Query cache has the permanent ID for future operations
      if (context?.clientTempId && data.id) {
        reconcileMessageId(queryClient, params.chatId, context.clientTempId, data.id);
        logger.debug('Message ID reconciled', {
          clientTempId: context.clientTempId,
          snowflakeId: data.id,
          chatId: params.chatId,
        });
      }

      // DON'T invalidate chat lists - WSE handles real-time updates via handleMessageCreated
    },

    // Don't refetch on settle - WSE will update the cache
    onSettled: () => {
      // No invalidation needed - WSE handles real-time updates
    },
  });

  // Retry a failed message - uses the same idempotency key for deduplication
  const retryMessage = (chatId: string, clientTempId: string) => {
    // Find the failed message in cache
    const data = queryClient.getQueryData(chatKeys.messages(chatId)) as any;
    if (!data?.pages) return;

    let failedMessage: any = null;
    for (const page of data.pages) {
      for (const msg of page.messages) {
        if (msg.id === clientTempId || msg._stableKey === clientTempId) {
          failedMessage = msg;
          break;
        }
      }
      if (failedMessage) break;
    }

    if (!failedMessage || !failedMessage._failed) {
      logger.warn('Message not found or not failed', { clientTempId });
      return;
    }

    // Clear failed state
    queryClient.setQueryData(
      chatKeys.messages(chatId),
      (oldData: any) => {
        if (!oldData?.pages) return oldData;
        return {
          ...oldData,
          pages: oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((msg: Message) => {
              if (msg.id === clientTempId || (msg as any)._stableKey === clientTempId) {
                const { _failed, _error, ...rest } = msg as any;
                return rest;
              }
              return msg;
            }),
          })),
        };
      }
    );

    // Retry with same idempotency key (server will dedupe if already processed)
    mutation.mutate({
      chatId,
      content: failedMessage.content,
      messageType: failedMessage.message_type,
      replyToId: failedMessage.reply_to_id,
      fileUrl: failedMessage.file_url,
      fileName: failedMessage.file_name,
      fileSize: failedMessage.file_size,
      fileType: failedMessage.file_type,
      voiceDuration: failedMessage.voice_duration,
      _clientTempId: clientTempId,
      _idempotencyKey: failedMessage._idempotencyKey || crypto.randomUUID(),
    });

    logger.info('Retrying failed message', { clientTempId });
  };

  // Discard a failed message
  const discardMessage = (chatId: string, clientTempId: string) => {
    removeMessageFromCache(queryClient, chatId, clientTempId);
    logger.info('Discarded failed message', { clientTempId });
  };

  // Wrapper that generates client temp ID and idempotency key ONCE before mutation
  // Format: "temp_<uuid>" - easy to identify as temporary
  // UUIDv7 for idempotency: time-sortable (RFC 9562), better for debugging and tracing
  return {
    ...mutation,
    mutate: (params: Omit<SendMessageParams, '_clientTempId' | '_idempotencyKey'>) => {
      const clientTempId = `temp_${uuidv7()}`;
      const idempotencyKey = uuidv7();  // UUIDv7: time-ordered, sortable
      mutation.mutate({ ...params, _clientTempId: clientTempId, _idempotencyKey: idempotencyKey });
    },
    mutateAsync: async (params: Omit<SendMessageParams, '_clientTempId' | '_idempotencyKey'>) => {
      const clientTempId = `temp_${uuidv7()}`;
      const idempotencyKey = uuidv7();  // UUIDv7: time-ordered, sortable
      return mutation.mutateAsync({ ...params, _clientTempId: clientTempId, _idempotencyKey: idempotencyKey });
    },
    retryMessage,
    discardMessage,
  };
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

      // DON'T invalidate chat lists - WSE handles real-time updates
      // queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
    },
  });
}

// -----------------------------------------------------------------------------
// useMarkAsRead - Mutation with throttling and deduplication to prevent flood
// -----------------------------------------------------------------------------

// Module-level tracking to prevent flood (persists across hook instances)
const lastMarkedRead: Map<string, { messageId: string; timestamp: number }> = new Map();
const MARK_AS_READ_THROTTLE_MS = 5000; // 5 seconds minimum between calls per chat

export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: { chatId: string; messageId: string }) => {
      const now = Date.now();
      const key = params.chatId;
      const lastMark = lastMarkedRead.get(key);

      // Skip if same message was marked recently (within throttle window)
      if (lastMark) {
        const timeSinceLastMark = now - lastMark.timestamp;

        // If same message, always skip
        if (lastMark.messageId === params.messageId) {
          logger.debug('MarkAsRead skipped: same message already marked', {
            chatId: params.chatId,
            messageId: params.messageId,
          });
          return params; // Return early, don't call API
        }

        // If different message but within throttle window, skip
        if (timeSinceLastMark < MARK_AS_READ_THROTTLE_MS) {
          logger.debug('MarkAsRead skipped: throttled', {
            chatId: params.chatId,
            messageId: params.messageId,
            timeSinceLastMark,
          });
          return params; // Return early, don't call API
        }
      }

      // Update tracking BEFORE API call
      lastMarkedRead.set(key, { messageId: params.messageId, timestamp: now });

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
