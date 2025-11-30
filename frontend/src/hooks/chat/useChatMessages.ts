// =============================================================================
// File: src/hooks/chat/useChatMessages.ts
// Description: React Query hook for chat messages with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect, useCallback } from 'react';
import { useQuery, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { Message } from '@/api/chat';
import { logger } from '@/utils/logger';

const MESSAGES_PER_PAGE = 20;

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
// useChatMessages - Infinite scroll with WSE integration
// -----------------------------------------------------------------------------

interface UseChatMessagesOptions {
  enabled?: boolean;
}

export function useChatMessages(chatId: string | null, options: UseChatMessagesOptions = {}) {
  const queryClient = useQueryClient();
  const { enabled = true } = options;

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
    enabled: enabled && !!chatId,
    // Messages are sorted newest first from API, we reverse for display
    select: (data) => ({
      pages: data.pages,
      pageParams: data.pageParams,
      // Flatten all pages into single array, reversed for chronological order
      messages: data.pages
        .flatMap((page) => page.messages)
        .reverse(),
    }),
  });

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

    // Subscribe to WSE events
    window.addEventListener('messageCreated', handleMessageCreated as EventListener);
    window.addEventListener('messageUpdated', handleMessageUpdated as EventListener);
    window.addEventListener('messageDeleted', handleMessageDeleted as EventListener);

    return () => {
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('messageUpdated', handleMessageUpdated as EventListener);
      window.removeEventListener('messageDeleted', handleMessageDeleted as EventListener);
    };
  }, [chatId, queryClient]);

  // Prefetch next page for smooth infinite scroll
  const prefetchNextPage = useCallback(() => {
    if (query.hasNextPage && !query.isFetchingNextPage) {
      query.fetchNextPage();
    }
  }, [query]);

  return {
    messages: query.data?.messages ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    hasNextPage: query.hasNextPage,
    isFetchingNextPage: query.isFetchingNextPage,
    fetchNextPage: query.fetchNextPage,
    prefetchNextPage,
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
