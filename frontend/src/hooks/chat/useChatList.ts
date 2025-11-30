// =============================================================================
// File: src/hooks/chat/useChatList.ts
// Description: React Query hook for chat list with WSE integration
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { ChatListItem, ChatDetail } from '@/api/chat';
import { chatKeys } from './useChatMessages';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// useChatList - Fetch all user's chats
// -----------------------------------------------------------------------------

interface UseChatListOptions {
  includeArchived?: boolean;
  limit?: number;
  enabled?: boolean;
}

export function useChatList(options: UseChatListOptions = {}) {
  const queryClient = useQueryClient();
  const { includeArchived = false, limit = 100, enabled = true } = options;

  const query = useQuery({
    queryKey: chatKeys.list({ includeArchived, limit }),
    queryFn: async () => {
      const chats = await chatApi.getChats(includeArchived, limit, 0);
      return chats;
    },
    enabled,
  });

  // WSE event handlers
  useEffect(() => {
    const handleChatCreated = async (event: CustomEvent) => {
      const newChatData = event.detail;
      const chatId = newChatData.chat_id || newChatData.id;

      logger.debug('WSE: Chat created', { chatId });

      // Delay to allow projector to update read model (eventual consistency)
      await new Promise(resolve => setTimeout(resolve, 500));

      // Fetch full chat data and add to cache
      try {
        const fullChat = await chatApi.getChatById(chatId);

        queryClient.setQueryData(
          chatKeys.list({ includeArchived, limit }),
          (oldData: ChatListItem[] | undefined) => {
            if (!oldData) return [fullChat];

            // Check if already exists
            if (oldData.some((c) => c.id === chatId)) {
              return oldData;
            }

            // Add at beginning (newest first)
            return [fullChat, ...oldData];
          }
        );
      } catch (error) {
        logger.error('Failed to fetch new chat details', { error, chatId });
        // Fallback: invalidate to refetch after another delay
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
        }, 500);
      }
    };

    const handleChatUpdated = (event: CustomEvent) => {
      const updatedChat = event.detail;
      const chatId = updatedChat.chat_id || updatedChat.id;

      logger.debug('WSE: Chat updated', { chatId });

      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;

          return oldData.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  name: updatedChat.name ?? chat.name,
                  last_message_at: updatedChat.last_message_at ?? chat.last_message_at,
                  last_message_content: updatedChat.last_message_content ?? chat.last_message_content,
                  unread_count: updatedChat.unread_count ?? chat.unread_count,
                }
              : chat
          );
        }
      );
    };

    const handleChatArchived = (event: CustomEvent) => {
      const archivedChat = event.detail;
      const chatId = archivedChat.chat_id || archivedChat.id;

      logger.debug('WSE: Chat archived', { chatId });

      if (!includeArchived) {
        // Remove from list if not showing archived
        queryClient.setQueryData(
          chatKeys.list({ includeArchived, limit }),
          (oldData: ChatListItem[] | undefined) => {
            if (!oldData) return oldData;
            return oldData.filter((chat) => chat.id !== chatId);
          }
        );
      } else {
        // Update is_active flag
        queryClient.setQueryData(
          chatKeys.list({ includeArchived, limit }),
          (oldData: ChatListItem[] | undefined) => {
            if (!oldData) return oldData;
            return oldData.map((chat) =>
              chat.id === chatId ? { ...chat, is_active: false } : chat
            );
          }
        );
      }
    };

    const handleChatDeleted = (event: CustomEvent) => {
      const deletedChat = event.detail;
      const chatId = deletedChat.chat_id || deletedChat.id;

      logger.debug('WSE: Chat deleted', { chatId });

      // Remove from cache
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((chat) => chat.id !== chatId);
        }
      );

      // Also remove detail cache
      queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });
    };

    // Subscribe to WSE events
    window.addEventListener('chatCreated', handleChatCreated as EventListener);
    window.addEventListener('chatUpdated', handleChatUpdated as EventListener);
    window.addEventListener('chatArchived', handleChatArchived as EventListener);
    window.addEventListener('chatDeleted', handleChatDeleted as EventListener);

    return () => {
      window.removeEventListener('chatCreated', handleChatCreated as EventListener);
      window.removeEventListener('chatUpdated', handleChatUpdated as EventListener);
      window.removeEventListener('chatArchived', handleChatArchived as EventListener);
      window.removeEventListener('chatDeleted', handleChatDeleted as EventListener);
    };
  }, [queryClient, includeArchived, limit]);

  return {
    chats: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useChatDetail - Fetch single chat details
// -----------------------------------------------------------------------------

export function useChatDetail(chatId: string | null) {
  return useQuery({
    queryKey: chatId ? chatKeys.detail(chatId) : ['disabled'],
    queryFn: async () => {
      if (!chatId) return null;
      return await chatApi.getChatById(chatId);
    },
    enabled: !!chatId,
  });
}

// -----------------------------------------------------------------------------
// useChatParticipants - Fetch chat participants
// -----------------------------------------------------------------------------

export function useChatParticipants(chatId: string | null, includeInactive = false) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: chatId ? chatKeys.participants(chatId) : ['disabled'],
    queryFn: async () => {
      if (!chatId) return [];
      return await chatApi.getParticipants(chatId, includeInactive);
    },
    enabled: !!chatId,
  });

  // WSE event handlers for participants
  useEffect(() => {
    if (!chatId) return;

    const handleParticipantJoined = (event: CustomEvent) => {
      if (event.detail.chat_id !== chatId) return;
      queryClient.invalidateQueries({ queryKey: chatKeys.participants(chatId) });
    };

    const handleParticipantLeft = (event: CustomEvent) => {
      if (event.detail.chat_id !== chatId) return;
      queryClient.invalidateQueries({ queryKey: chatKeys.participants(chatId) });
    };

    window.addEventListener('participantJoined', handleParticipantJoined as EventListener);
    window.addEventListener('participantLeft', handleParticipantLeft as EventListener);

    return () => {
      window.removeEventListener('participantJoined', handleParticipantJoined as EventListener);
      window.removeEventListener('participantLeft', handleParticipantLeft as EventListener);
    };
  }, [chatId, queryClient]);

  return {
    participants: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useUnreadCount - Fetch unread count
// -----------------------------------------------------------------------------

export function useUnreadCount() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['unread-count'],
    queryFn: chatApi.getUnreadCount,
  });

  // Update on messages read event
  useEffect(() => {
    const handleMessagesRead = () => {
      queryClient.invalidateQueries({ queryKey: ['unread-count'] });
    };

    window.addEventListener('messagesRead', handleMessagesRead);
    return () => window.removeEventListener('messagesRead', handleMessagesRead);
  }, [queryClient]);

  return {
    totalUnread: query.data?.total_unread ?? 0,
    unreadChats: query.data?.unread_chats ?? 0,
    isLoading: query.isLoading,
    refetch: query.refetch,
  };
}
