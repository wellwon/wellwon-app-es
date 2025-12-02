// =============================================================================
// File: src/hooks/chat/useChatMessages.ts
// Description: React Query hook for chat messages with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query" + Zustand persistence
// =============================================================================

import { useEffect, useCallback, useRef } from 'react';
import { useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { Message } from '@/api/chat';
import { logger } from '@/utils/logger';
import { useMessagesStore } from '@/stores/useMessagesStore';

const MESSAGES_PER_PAGE = 30; // Increased for smoother scrolling
const PREFETCH_THRESHOLD = 10; // Prefetch when 10 messages from top

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const chatKeys = {
  all: ['chats'] as const,
  lists: () => [...chatKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...chatKeys.lists(), filters] as const,
  details: () => [...chatKeys.all, 'detail'] as const,
  detail: (id: string) => [...chatKeys.details(), id] as const,
  messages: (chatId: string) => [...chatKeys.detail(chatId), 'messages'] as const,
  participants: (chatId: string) => [...chatKeys.detail(chatId), 'participants'] as const,
};

// -----------------------------------------------------------------------------
// Normalizer - ensures consistent 'id' field
// -----------------------------------------------------------------------------

function normalizeMessage(msg: any): Message {
  const normalizedId = msg.id || msg.message_id;
  const { message_id, ...rest } = msg;
  return { ...rest, id: normalizedId } as Message;
}

// -----------------------------------------------------------------------------
// useChatMessages - Infinite scroll with WSE integration + persistence
// -----------------------------------------------------------------------------

interface UseChatMessagesOptions {
  enabled?: boolean;
}

export function useChatMessages(chatId: string | null, options: UseChatMessagesOptions = {}) {
  const queryClient = useQueryClient();
  const { enabled = true } = options;

  // Zustand cache for instant page refresh
  const getChatMessages = useMessagesStore((s) => s.getChatMessages);
  const setChatMessages = useMessagesStore((s) => s.setChatMessages);

  // Get cached data for this chat
  const cachedData = chatId ? getChatMessages(chatId) : null;

  // Track if we're prefetching to avoid duplicate calls
  const isPrefetchingRef = useRef(false);

  // Infinite query for paginated messages
  const query = useInfiniteQuery({
    queryKey: chatId ? chatKeys.messages(chatId) : ['disabled'],
    queryFn: async ({ pageParam = 0 }) => {
      if (!chatId) return { messages: [], nextOffset: null };

      const messages = await chatApi.getMessages(chatId, {
        limit: MESSAGES_PER_PAGE,
        offset: pageParam,
      });

      return {
        messages: messages.map(normalizeMessage),
        nextOffset: messages.length === MESSAGES_PER_PAGE ? pageParam + MESSAGES_PER_PAGE : null,
      };
    },
    getNextPageParam: (lastPage) => lastPage.nextOffset,
    initialPageParam: 0,
    enabled: enabled && !!chatId,

    // TkDodo: staleTime: Infinity when WSE handles all updates
    staleTime: Infinity,

    // TkDodo: initialData from Zustand cache for instant render
    // IMPORTANT: Only use if cache has actual pages, otherwise let React Query fetch
    initialData: cachedData?.pages?.length ? {
      pages: cachedData.pages,
      pageParams: cachedData.pageParams,
    } : undefined,
    initialDataUpdatedAt: cachedData?.pages?.length ? cachedData.updatedAt : undefined,

    // Messages sorted newest first from API, we reverse for display
    select: (data) => ({
      pages: data.pages,
      pageParams: data.pageParams,
      // Flatten all pages into single array, reversed for chronological order
      messages: data.pages
        .flatMap((page) => page.messages)
        .reverse(),
    }),

    // Keep only recent pages in memory for performance
    maxPages: 5,
  });

  // Sync React Query cache to Zustand for persistence
  useEffect(() => {
    if (chatId && query.data?.pages?.length) {
      setChatMessages(
        chatId,
        query.data.pages,
        query.data.pageParams as number[]
      );
    }
  }, [chatId, query.data?.pages, query.data?.pageParams, setChatMessages]);

  // WSE event handlers - update React Query cache directly
  useEffect(() => {
    if (!chatId) return;

    const handleMessageCreated = (event: CustomEvent) => {
      const messageData = event.detail;
      if (messageData.chat_id !== chatId) return;

      const newMessage = normalizeMessage(messageData);

      logger.debug('WSE: Adding message to React Query cache', {
        messageId: newMessage.id,
        chatId,
      });

      // Add message to cache using setQueryData (TkDodo pattern)
      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          // Check for duplicates using first page (most recent)
          const allMessages = oldData.pages.flatMap((p: any) => p.messages);
          if (allMessages.some((m: Message) => m.id === newMessage.id)) {
            logger.debug('WSE: Message already exists, skipping', { messageId: newMessage.id });
            return oldData;
          }

          // Add to first page (newest messages)
          const newPages = [...oldData.pages];
          if (newPages.length > 0) {
            newPages[0] = {
              ...newPages[0],
              messages: [newMessage, ...newPages[0].messages],
            };
          }

          return { ...oldData, pages: newPages };
        }
      );
    };

    const handleMessageUpdated = (event: CustomEvent) => {
      const messageData = event.detail;
      if (messageData.chat_id !== chatId) return;

      const updatedMessage = normalizeMessage(messageData);

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) =>
              m.id === updatedMessage.id ? { ...m, ...updatedMessage } : m
            ),
          }));

          return { ...oldData, pages: newPages };
        }
      );
    };

    const handleMessageDeleted = (event: CustomEvent) => {
      const messageData = event.detail;
      if (messageData.chat_id !== chatId) return;

      const deletedId = messageData.id || messageData.message_id;

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.filter((m: Message) => m.id !== deletedId),
          }));

          return { ...oldData, pages: newPages };
        }
      );
    };

    // Handle message synced to Telegram - delivery confirmation (double gray checkmark)
    const handleMessageSyncedToTelegram = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId) return;

      const messageId = data.id || data.message_id;
      const telegramMessageId = data.telegram_message_id;

      logger.debug('WSE: Message synced to Telegram (delivered)', {
        chatId,
        messageId,
        telegramMessageId,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              if (m.id === messageId) {
                return {
                  ...m,
                  telegram_message_id: telegramMessageId,
                };
              }
              return m;
            }),
          }));

          return { ...oldData, pages: newPages };
        }
      );
    };

    // Handle messages read - bidirectional (Web ↔ Telegram)
    const handleMessagesRead = (event: CustomEvent) => {
      const data = event.detail;
      // Compare as strings since chatId from hook is string, data might have UUID
      if (String(data.chat_id) !== String(chatId)) return;

      logger.debug('WSE: Messages read event received', {
        chatId,
        data,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          // Extract data - handle both formats:
          // Backend sends: user_id, last_read_message_id, read_at
          // Also support: read_by object, telegram_read_at
          const readUserId = data.user_id;
          const lastReadMessageId = data.last_read_message_id;
          const readAt = data.read_at || new Date().toISOString();
          const telegramReadAt = data.telegram_read_at;

          // Build read_by entry from user_id if not provided directly
          const readByEntry = data.read_by || (readUserId ? {
            user_id: readUserId,
            read_at: readAt,
          } : null);

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              // Mark as read if:
              // 1. Message ID matches last_read_message_id
              // 2. Or message was created before/at the read time
              const messageId = String(m.id);
              const isLastReadMessage = lastReadMessageId && messageId === String(lastReadMessageId);
              const isBeforeLastRead = lastReadMessageId &&
                new Date(m.created_at) <= new Date(readAt);

              if (!isLastReadMessage && !isBeforeLastRead) return m;

              // Update read status
              const updatedMessage = { ...m };

              // Add read_by entry (WellWon user read)
              if (readByEntry && readByEntry.user_id) {
                const existingReadBy = m.read_by || [];
                const alreadyRead = existingReadBy.some(
                  (r: any) => String(r.user_id) === String(readByEntry.user_id)
                );
                if (!alreadyRead) {
                  updatedMessage.read_by = [...existingReadBy, readByEntry];
                }
              }

              // Update telegram_read_at if provided (Telegram read)
              if (telegramReadAt) {
                updatedMessage.telegram_read_at = telegramReadAt;
              }

              return updatedMessage;
            }),
          }));

          return { ...oldData, pages: newPages };
        }
      );
    };

    // Handle messages read on Telegram - blue checkmarks from Telegram read receipts
    const handleMessagesReadOnTelegram = (event: CustomEvent) => {
      const data = event.detail;
      if (String(data.chat_id) !== String(chatId)) return;

      const telegramReadAt = data.telegram_read_at;

      logger.debug('WSE: Messages read on Telegram (blue checkmarks)', {
        chatId,
        telegramReadAt,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          // Update all messages that have telegram_message_id but no telegram_read_at
          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              // Only update messages that were delivered to Telegram
              if (m.telegram_message_id && !m.telegram_read_at) {
                return {
                  ...m,
                  telegram_read_at: telegramReadAt,
                };
              }
              return m;
            }),
          }));

          return { ...oldData, pages: newPages };
        }
      );
    };

    // Subscribe to WSE events
    window.addEventListener('messageCreated', handleMessageCreated as EventListener);
    window.addEventListener('messageUpdated', handleMessageUpdated as EventListener);
    window.addEventListener('messageDeleted', handleMessageDeleted as EventListener);
    window.addEventListener('messageSyncedToTelegram', handleMessageSyncedToTelegram as EventListener);
    window.addEventListener('messagesRead', handleMessagesRead as EventListener);
    window.addEventListener('messagesReadOnTelegram', handleMessagesReadOnTelegram as EventListener);

    return () => {
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('messageUpdated', handleMessageUpdated as EventListener);
      window.removeEventListener('messageDeleted', handleMessageDeleted as EventListener);
      window.removeEventListener('messageSyncedToTelegram', handleMessageSyncedToTelegram as EventListener);
      window.removeEventListener('messagesRead', handleMessagesRead as EventListener);
      window.removeEventListener('messagesReadOnTelegram', handleMessagesReadOnTelegram as EventListener);
    };
  }, [chatId, queryClient]);

  // Seamless prefetch - load next page before user reaches top
  const prefetchNextPage = useCallback(() => {
    if (
      query.hasNextPage &&
      !query.isFetchingNextPage &&
      !query.isFetching &&
      !isPrefetchingRef.current
    ) {
      isPrefetchingRef.current = true;
      query.fetchNextPage().finally(() => {
        isPrefetchingRef.current = false;
      });
    }
  }, [query]);

  // Check if should prefetch based on scroll position (called by consumer)
  const checkPrefetch = useCallback((visibleMessageIndex: number) => {
    // If user is near the top (old messages), prefetch more
    if (visibleMessageIndex < PREFETCH_THRESHOLD && query.hasNextPage) {
      prefetchNextPage();
    }
  }, [prefetchNextPage, query.hasNextPage]);

  return {
    messages: query.data?.messages ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    hasNextPage: query.hasNextPage,
    isFetchingNextPage: query.isFetchingNextPage,
    isFetching: query.isFetching,
    fetchNextPage: query.fetchNextPage,
    prefetchNextPage,
    checkPrefetch,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// Utility: Add optimistic message to cache
// -----------------------------------------------------------------------------

export function addOptimisticMessage(
  queryClient: ReturnType<typeof useQueryClient>,
  chatId: string,
  message: Message
) {
  queryClient.setQueryData(
    chatKeys.messages(chatId),
    (oldData: any) => {
      if (!oldData) {
        return {
          pages: [{ messages: [message], nextOffset: null }],
          pageParams: [0],
        };
      }

      const newPages = [...oldData.pages];
      if (newPages.length > 0) {
        newPages[0] = {
          ...newPages[0],
          messages: [message, ...newPages[0].messages],
        };
      }

      return { ...oldData, pages: newPages };
    }
  );
}

// -----------------------------------------------------------------------------
// Utility: Remove message from cache
// -----------------------------------------------------------------------------

export function removeMessageFromCache(
  queryClient: ReturnType<typeof useQueryClient>,
  chatId: string,
  messageId: string
) {
  queryClient.setQueryData(
    chatKeys.messages(chatId),
    (oldData: any) => {
      if (!oldData) return oldData;

      const newPages = oldData.pages.map((page: any) => ({
        ...page,
        messages: page.messages.filter((m: Message) => m.id !== messageId),
      }));

      return { ...oldData, pages: newPages };
    }
  );
}
