// =============================================================================
// File: src/hooks/chat/useChatList.ts
// Description: React Query hook for chat list with WSE integration
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { ChatListItem } from '@/api/chat';
import { chatKeys } from './useChatMessages';
import { logger } from '@/utils/logger';
import { useChatsStore } from '@/stores/useChatsStore';

// -----------------------------------------------------------------------------
// useChatList - Fetch all user's chats
// -----------------------------------------------------------------------------

interface UseChatListOptions {
  includeArchived?: boolean;
  limit?: number;
  enabled?: boolean;
}

// Extended type with optimistic marker
type OptimisticChatListItem = ChatListItem & { _isOptimistic?: boolean };

export function useChatList(options: UseChatListOptions = {}) {
  const queryClient = useQueryClient();
  const { includeArchived = false, limit = 100, enabled = true } = options;

  // Zustand cache for instant page refresh (TkDodo pattern)
  const cachedChats = useChatsStore((s) => s.cachedChats);
  const cachedUpdatedAt = useChatsStore((s) => s.cachedUpdatedAt);
  const setCachedChats = useChatsStore((s) => s.setCachedChats);

  const query = useQuery({
    queryKey: chatKeys.list({ includeArchived, limit }),
    queryFn: async () => {
      const apiChats = await chatApi.getChats(includeArchived, limit, 0);

      // CRITICAL: Preserve optimistic entries that were added via WSE events
      const existingData = queryClient.getQueryData<OptimisticChatListItem[]>(chatKeys.list({ includeArchived, limit }));
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter(e => e._isOptimistic);
        if (optimisticEntries.length > 0) {
          logger.info('useChatList: Preserving optimistic entries', {
            optimisticCount: optimisticEntries.length,
            apiCount: apiChats.length
          });
          // Merge: keep optimistic entries that aren't in API response yet
          const apiIds = new Set(apiChats.map(c => c.id));
          const uniqueOptimistic = optimisticEntries.filter(o => !apiIds.has(o.id));
          const result = [...uniqueOptimistic, ...apiChats];
          setCachedChats(result); // Save to Zustand for instant refresh
          return result;
        }
      }

      setCachedChats(apiChats); // Save to Zustand for instant refresh
      return apiChats;
    },
    enabled,
    // TkDodo: staleTime: Infinity when WSE handles all updates
    staleTime: Infinity,
    // TkDodo: initialData from Zustand cache for instant render on page refresh
    // IMPORTANT: Only use non-empty cache, otherwise React Query won't fetch
    initialData: cachedChats?.length ? cachedChats : undefined,
    initialDataUpdatedAt: cachedChats?.length ? (cachedUpdatedAt ?? 0) : undefined,
  });

  // WSE event handlers
  useEffect(() => {
    // OPTIMISTIC CREATE: Immediately add chat to cache from WSE event data
    const handleChatCreated = async (event: CustomEvent) => {
      const newChatData = event.detail;
      const chatId = newChatData.chat_id || newChatData.id;

      logger.info('WSE: Chat created, adding optimistically', { chatId, newChatData });

      // TanStack best practice: Cancel any in-flight refetches to prevent race conditions
      await queryClient.cancelQueries({
        queryKey: chatKeys.list({ includeArchived, limit })
      });

      // Create optimistic chat entry from WSE event data
      // Mark as optimistic so queryFn can preserve it during race conditions
      const optimisticChat: OptimisticChatListItem = {
        id: chatId,
        name: newChatData.name || newChatData.chat_name || 'New Chat',
        chat_type: newChatData.chat_type || 'company',
        is_active: true,
        created_at: newChatData.created_at || new Date().toISOString(),
        company_id: newChatData.company_id || null,
        telegram_chat_id: newChatData.telegram_chat_id || null,
        telegram_supergroup_id: newChatData.telegram_supergroup_id || null, // Important for filtering
        telegram_topic_id: newChatData.telegram_topic_id || null,
        last_message_at: newChatData.created_at || new Date().toISOString(),
        last_message_content: null,
        last_message_sender_id: null,
        unread_count: 0,
        participant_count: 1,
        other_participant_name: null,
        _isOptimistic: true, // Marker for queryFn to preserve during fetch
      };

      // Add to cache IMMEDIATELY (optimistic)
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return [optimisticChat];

          // Check if already exists
          if (oldData.some((c) => c.id === chatId)) {
            return oldData;
          }

          // Add at beginning (newest first)
          return [optimisticChat, ...oldData];
        }
      );

      // Also update Zustand cache immediately
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) {
        setCachedChats(currentChats);
      }

      // Retry logic with exponential backoff (TkDodo pattern for projection delays)
      const fetchWithRetry = async (attempts = 3, baseDelay = 1000) => {
        for (let i = 0; i < attempts; i++) {
          const delay = baseDelay * Math.pow(2, i); // 1s, 2s, 4s
          await new Promise(r => setTimeout(r, delay));

          try {
            const fullChat = await chatApi.getChatById(chatId);
            if (fullChat) {
              queryClient.setQueryData(
                chatKeys.list({ includeArchived, limit }),
                (oldData: ChatListItem[] | undefined) => {
                  if (!oldData) return [fullChat];
                  const updated = oldData.map((c) =>
                    c.id === chatId ? { ...fullChat, _isOptimistic: false } : c
                  );
                  setCachedChats(updated); // Sync Zustand cache
                  return updated;
                }
              );
              logger.info('WSE: Full chat fetched after retry', { chatId, attempt: i + 1 });
              return;
            }
          } catch (error) {
            if (i === attempts - 1) {
              logger.warn('WSE: Failed to fetch full chat after all retries, keeping optimistic', {
                chatId,
                attempts,
                error
              });
            } else {
              logger.debug('WSE: Chat fetch attempt failed, retrying...', { chatId, attempt: i + 1 });
            }
          }
        }
      };

      fetchWithRetry();
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

      // Sync Zustand cache after update
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) setCachedChats(currentChats);
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

      // Sync Zustand cache
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) setCachedChats(currentChats);
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

      // Sync Zustand cache
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) setCachedChats(currentChats);
    };

    // OPTIMISTIC UPDATE: Update last_message when message is created
    const handleMessageCreated = (event: CustomEvent) => {
      const message = event.detail;
      const chatId = message.chat_id;

      if (!chatId) return;

      logger.debug('WSE: Message created, updating chat last_message', { chatId });

      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  last_message_at: message.created_at || new Date().toISOString(),
                  last_message_content: message.content || message.text || null,
                  last_message_sender_id: message.sender_id || null,
                }
              : chat
          );
        }
      );

      // Sync Zustand cache
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) setCachedChats(currentChats);
    };

    // CRITICAL: Update telegram_supergroup_id when chat is linked to telegram
    // This enables the chat to appear in the correct supergroup filter
    const handleChatTelegramLinked = (event: CustomEvent) => {
      const data = event.detail;
      const chatId = data.chat_id || data.id;
      const telegramSupergroupId = data.telegram_supergroup_id;

      logger.info('WSE: Chat telegram linked, updating telegram_supergroup_id', {
        chatId,
        telegramSupergroupId
      });

      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  telegram_supergroup_id: telegramSupergroupId,
                  telegram_chat_id: data.telegram_chat_id || chat.telegram_chat_id,
                  _isOptimistic: false, // No longer optimistic after linking
                }
              : chat
          );
        }
      );

      // Sync Zustand cache
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );
      if (currentChats) setCachedChats(currentChats);
    };

    // Subscribe to WSE events
    window.addEventListener('chatCreated', handleChatCreated as EventListener);
    window.addEventListener('chatUpdated', handleChatUpdated as EventListener);
    window.addEventListener('chatArchived', handleChatArchived as EventListener);
    window.addEventListener('chatDeleted', handleChatDeleted as EventListener);
    window.addEventListener('messageCreated', handleMessageCreated as EventListener);
    window.addEventListener('chatTelegramLinked', handleChatTelegramLinked as EventListener);

    return () => {
      window.removeEventListener('chatCreated', handleChatCreated as EventListener);
      window.removeEventListener('chatUpdated', handleChatUpdated as EventListener);
      window.removeEventListener('chatArchived', handleChatArchived as EventListener);
      window.removeEventListener('chatDeleted', handleChatDeleted as EventListener);
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('chatTelegramLinked', handleChatTelegramLinked as EventListener);
    };
  }, [queryClient, includeArchived, limit, setCachedChats]);

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
