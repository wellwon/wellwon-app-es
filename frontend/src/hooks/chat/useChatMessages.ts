// =============================================================================
// File: src/hooks/chat/useChatMessages.ts
// Description: React Query hook for chat messages with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query" + Zustand persistence
// =============================================================================

import { useEffect, useCallback, useRef, useMemo } from 'react';
import { useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { Message } from '@/api/chat';
import { logger } from '@/utils/logger';
import { useMessagesStore } from '@/stores/useMessagesStore';

const MESSAGES_PER_PAGE = 30; // Increased for smoother scrolling
const PREFETCH_THRESHOLD = 10; // Prefetch when 10 messages from top

// -----------------------------------------------------------------------------
// Message ID Set - O(1) deduplication helper
// -----------------------------------------------------------------------------

function buildMessageIdSet(pages: any[]): Set<string> {
  const idSet = new Set<string>();
  for (const page of pages) {
    for (const msg of page.messages) {
      idSet.add(String(msg.id));
    }
  }
  return idSet;
}

function hasMessage(pages: any[], messageId: string): boolean {
  // O(n) with early exit - fine for small page sizes (30 msgs)
  // Building a Set would also be O(n) so no benefit
  const id = String(messageId);
  for (const page of pages) {
    for (const msg of page.messages) {
      if (String(msg.id) === id) return true;
    }
  }
  return false;
}

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
  const rawCachedData = chatId ? getChatMessages(chatId) : null;
  const clearChatCache = useMessagesStore((s) => s.clearChatCache);

  // IMPORTANT: Only use cache if it actually has messages, not just empty page structure
  // Also migrate legacy cache format (nextOffset → oldestMessageId)
  const cachedData = useMemo(() => {
    if (!rawCachedData?.pages?.length) return null;

    // Count total messages across all pages
    let totalMessages = 0;
    for (const page of rawCachedData.pages) {
      totalMessages += page.messages?.length || 0;
    }

    // If cache is essentially empty (no actual messages), don't use it
    if (totalMessages === 0) {
      console.log('[CACHE] Cache has pages but no messages - ignoring cache');
      return null;
    }

    // Migrate legacy cache format: ensure each page has oldestMessageId and hasMore
    const migratedPages = rawCachedData.pages.map((page: any) => {
      // If already has new format, use as-is
      if (page.oldestMessageId !== undefined && page.hasMore !== undefined) {
        return page;
      }

      // Migrate: derive oldestMessageId from last message in page
      const messages = page.messages || [];
      const oldestMessage = messages[messages.length - 1];
      const oldestMessageId = oldestMessage?.id || null;

      // Default hasMore to true for cached pages (will be corrected on fresh fetch)
      const hasMore = page.hasMore ?? (messages.length >= 10);

      return {
        ...page,
        oldestMessageId,
        hasMore,
      };
    });

    return {
      ...rawCachedData,
      pages: migratedPages,
    };
  }, [rawCachedData]);

  // Clean up corrupted cache (empty page structures)
  useEffect(() => {
    if (chatId && rawCachedData?.pages?.length && !cachedData) {
      console.log('[CACHE] Cleaning up corrupted cache for chat:', chatId);
      clearChatCache(chatId);
    }
  }, [chatId, rawCachedData, cachedData, clearChatCache]);

  // Debug: log cache state
  useEffect(() => {
    if (chatId) {
      const msgCount = cachedData?.pages?.reduce((acc, p) => acc + (p.messages?.length || 0), 0) || 0;
      console.log('[CACHE] Chat:', chatId, 'Cached pages:', cachedData?.pages?.length || 0, 'Messages:', msgCount);
    }
  }, [chatId, cachedData?.pages?.length]);

  // Track if we're prefetching to avoid duplicate calls
  const isPrefetchingRef = useRef(false);

  // Debug: log query state
  useEffect(() => {
    console.log('[QUERY-DEBUG] ============================');
    console.log('[QUERY-DEBUG] chatId:', chatId);
    console.log('[QUERY-DEBUG] enabled prop:', enabled);
    console.log('[QUERY-DEBUG] Query will be enabled:', enabled && !!chatId);
    if (enabled && chatId) {
      console.log('[QUERY-DEBUG] ✓ Query SHOULD fire and fetch from backend!');
    } else {
      console.log('[QUERY-DEBUG] ✗ Query DISABLED - chatId or enabled is falsy');
    }
  }, [enabled, chatId]);

  // -----------------------------------------------------------------------------
  // Infinite Query with CURSOR-BASED pagination (Industry Standard)
  // - Uses before_id to load OLDER messages (scroll up)
  // - More reliable than offset (no issues when new messages shift positions)
  // - Discord/Telegram pattern
  // -----------------------------------------------------------------------------
  const query = useInfiniteQuery({
    queryKey: chatId ? chatKeys.messages(chatId) : ['disabled'],
    queryFn: async ({ pageParam }) => {
      console.log('[QUERY-FN] >>>>>> queryFn CALLED! chatId:', chatId, 'cursor:', pageParam);

      if (!chatId) {
        console.log('[QUERY-FN] No chatId, returning empty');
        return { messages: [], oldestMessageId: null, hasMore: false };
      }

      console.log('[QUERY-FN] Fetching messages from BACKEND for chat:', chatId, 'cursor:', pageParam, 'limit:', MESSAGES_PER_PAGE);

      // pageParam is the cursor (oldest message ID from previous page)
      // null = first page (newest messages)
      const messages = await chatApi.getMessages(chatId, {
        limit: MESSAGES_PER_PAGE,
        before_id: pageParam || undefined, // Load messages BEFORE this ID (older)
      });

      console.log('[QUERY] Got', messages.length, 'messages from API');
      const normalizedMessages = messages.map(normalizeMessage);

      // Get the oldest message ID for next page cursor
      const oldestMessage = normalizedMessages[normalizedMessages.length - 1];
      const oldestMessageId = oldestMessage?.id || null;

      return {
        messages: normalizedMessages,
        // Cursor for loading older messages (scroll up)
        oldestMessageId,
        // Has more if we got a full page
        hasMore: messages.length === MESSAGES_PER_PAGE,
      };
    },

    // Cursor-based pagination: return oldest message ID or undefined to stop
    // IMPORTANT: Default hasMore to true for cached pages that might not have this field
    // This ensures pagination works when loading from localStorage cache
    getNextPageParam: (lastPage) => {
      // If hasMore is explicitly false, stop pagination
      if (lastPage.hasMore === false) return undefined;
      // If no oldestMessageId, stop pagination
      if (!lastPage.oldestMessageId) return undefined;
      // Otherwise assume more pages (Discord/Telegram pattern)
      return lastPage.oldestMessageId;
    },

    // First page has no cursor (get newest messages)
    initialPageParam: null as string | null,
    enabled: enabled && !!chatId,

    // TkDodo pattern: Show cached data instantly, fetch fresh in background
    // placeholderData shows Zustand cache while fetching (instant page refresh)
    placeholderData: cachedData ? {
      pages: cachedData.pages,
      pageParams: cachedData.pageParams,
    } : undefined,

    // Fresh fetch in background - ensures consistency with ScyllaDB
    staleTime: 0, // Data is immediately stale - fetch fresh in background
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes for navigation
    refetchOnMount: true, // Fetch fresh data but show placeholder while loading

    // Transform data for display
    select: (data) => {
      // Deduplicate using Map for O(1) lookup, preserving order
      const messageMap = new Map<string, Message>();
      for (const page of data.pages) {
        for (const msg of page.messages) {
          const id = String(msg.id);
          if (!messageMap.has(id)) {
            messageMap.set(id, msg);
          }
        }
      }

      // API returns newest first per page, pages are oldest to newest
      // We need chronological order: oldest first, newest last
      const messages = Array.from(messageMap.values()).reverse();

      return {
        pages: data.pages,
        pageParams: data.pageParams,
        messages,
        hasMore: data.pages[data.pages.length - 1]?.hasMore ?? false,
      };
    },

    // Limit cache to prevent memory bloat (TanStack Query v5)
    maxPages: 10,
  });

  // Debug: log query state after definition
  useEffect(() => {
    console.log('[QUERY-STATE] isLoading:', query.isLoading, 'isFetching:', query.isFetching, 'isError:', query.isError);
    console.log('[QUERY-STATE] data pages:', query.data?.pages?.length || 0, 'messages:', query.data?.messages?.length || 0);
    console.log('[QUERY-STATE] hasNextPage:', query.hasNextPage, 'isFetchingNextPage:', query.isFetchingNextPage);
    // Debug: check last page structure
    if (query.data?.pages?.length) {
      const lastPage = query.data.pages[query.data.pages.length - 1];
      console.log('[QUERY-STATE] Last page hasMore:', lastPage?.hasMore, 'oldestMessageId:', lastPage?.oldestMessageId);
    }
    if (query.isError) {
      console.error('[QUERY-STATE] ERROR:', query.error);
    }
  }, [query.isLoading, query.isFetching, query.isError, query.data?.pages?.length, query.data?.messages?.length, query.error, query.hasNextPage, query.isFetchingNextPage]);

  // Sync React Query cache to Zustand for persistence
  useEffect(() => {
    if (chatId && query.data?.pages?.length) {
      setChatMessages(
        chatId,
        query.data.pages,
        query.data.pageParams as (string | number | null)[]
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

      logger.debug('WSE: Processing message_created', {
        messageId: newMessage.id,
        chatId,
      });

      // Add message to cache using setQueryData (TkDodo pattern)
      // Simple logic: only add if message doesn't exist (by snowflake_id)
      // Optimistic messages have temp_xxx IDs, server messages have snowflake IDs
      // HTTP response handles reconciliation (temp_xxx → snowflake)
      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          // Check if message already exists by ID (snowflake_id)
          if (hasMessage(oldData.pages, newMessage.id)) {
            logger.debug('WSE: Message already exists, skipping', { messageId: newMessage.id });
            return oldData;
          }

          // Check if there's an optimistic message with temp ID that needs reconciliation
          // Look for temp_xxx IDs that should be replaced with this snowflake
          const clientTempId = messageData.client_temp_id;
          if (clientTempId) {
            let found = false;
            const newPages = oldData.pages.map((page: any) => ({
              ...page,
              messages: page.messages.map((m: Message) => {
                if (String(m.id) === clientTempId) {
                  found = true;
                  // Preserve _stableKey to prevent React remount/re-animation
                  return { ...newMessage, _stableKey: m._stableKey || clientTempId };
                }
                return m;
              }),
            }));
            if (found) {
              logger.debug('WSE: Reconciled optimistic message', { tempId: clientTempId, snowflakeId: newMessage.id });
              return { ...oldData, pages: newPages };
            }
            // client_temp_id provided but temp not found - HTTP already reconciled, skip
            logger.debug('WSE: client_temp_id provided but temp not found, skipping', { clientTempId });
            return oldData;
          }

          // No client_temp_id - check if this is our optimistic message by looking for temp_ prefix
          // If any temp_ message exists with same sender, it's likely ours - wait for HTTP reconcile
          const hasPendingOptimistic = oldData.pages.some((page: any) =>
            page.messages.some((m: Message) =>
              String(m.id).startsWith('temp_') && m.sender_id === newMessage.sender_id
            )
          );
          if (hasPendingOptimistic) {
            logger.debug('WSE: Has pending optimistic from same sender, skipping', { messageId: newMessage.id });
            return oldData;
          }

          // Truly new message from other user - add to cache
          logger.debug('WSE: Adding new message', { messageId: newMessage.id });
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
      // Compare as strings (chatId is string, data.chat_id may be UUID)
      if (String(data.chat_id) !== String(chatId)) return;

      const messageId = String(data.id || data.message_id);
      const telegramMessageId = data.telegram_message_id;

      logger.info('WSE: Message synced to Telegram (delivered) - double gray checkmarks', {
        chatId,
        messageId,
        telegramMessageId,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          let updated = false;
          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              // Compare as strings (m.id is string, messageId is stringified Snowflake)
              if (String(m.id) === messageId) {
                updated = true;
                return {
                  ...m,
                  telegram_message_id: telegramMessageId,
                };
              }
              return m;
            }),
          }));

          if (updated) {
            logger.info(`Updated message ${messageId} with telegram_message_id=${telegramMessageId}`);
          } else {
            logger.warn(`Message ${messageId} not found in cache for telegram sync update`);
          }

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

      logger.info('[READ-DEBUG] WSE: Messages read on Telegram (blue checkmarks)', {
        chatId,
        telegramReadAt,
        lastReadMessageId: data.last_read_message_id,
        lastReadTelegramMessageId: data.last_read_telegram_message_id,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          let updatedCount = 0;

          // Update all messages that have telegram_message_id but no telegram_read_at
          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              // Only update messages that were delivered to Telegram
              if (m.telegram_message_id && !m.telegram_read_at) {
                updatedCount++;
                return {
                  ...m,
                  telegram_read_at: telegramReadAt,
                };
              }
              return m;
            }),
          }));

          logger.info(`[READ-DEBUG] Updated ${updatedCount} messages with telegram_read_at (blue checkmarks)`);

          return { ...oldData, pages: newPages };
        }
      );
    };

    // Handle message file URL updated - async file processing complete
    // This updates the message with permanent MinIO URL after background upload
    const handleMessageFileUrlUpdated = (event: CustomEvent) => {
      const data = event.detail;
      if (String(data.chat_id) !== String(chatId)) return;

      const messageId = String(data.message_id);

      logger.debug('WSE: Message file URL updated (async upload complete)', {
        chatId,
        messageId,
        newFileUrl: data.new_file_url,
      });

      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          if (!oldData) return oldData;

          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              if (String(m.id) === messageId) {
                return {
                  ...m,
                  file_url: data.new_file_url,
                  file_name: data.file_name ?? m.file_name,
                  file_size: data.file_size ?? m.file_size,
                  file_type: data.file_type ?? m.file_type,
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
    window.addEventListener('messageFileUrlUpdated', handleMessageFileUrlUpdated as EventListener);

    return () => {
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('messageUpdated', handleMessageUpdated as EventListener);
      window.removeEventListener('messageDeleted', handleMessageDeleted as EventListener);
      window.removeEventListener('messageSyncedToTelegram', handleMessageSyncedToTelegram as EventListener);
      window.removeEventListener('messagesRead', handleMessagesRead as EventListener);
      window.removeEventListener('messagesReadOnTelegram', handleMessagesReadOnTelegram as EventListener);
      window.removeEventListener('messageFileUrlUpdated', handleMessageFileUrlUpdated as EventListener);
    };
  }, [chatId, queryClient]);

  // -----------------------------------------------------------------------------
  // Catch-up mechanism: fetch new messages on mount, tab return, or WSE reconnect
  // TkDodo best practice: "Always refetch after reconnect to ensure consistency"
  // Discord/Telegram pattern: sync missed messages when coming back online
  //
  // IMPORTANT: For infinite queries, we DON'T use query.refetch() because:
  // 1. It refetches ALL cached pages (slow, wasteful)
  // 2. Offset-based pagination breaks when new messages shift offsets
  //
  // Instead, we fetch ONLY the first page (newest messages) and merge with cache.
  // The `select` function deduplicates by message ID automatically.
  // -----------------------------------------------------------------------------

  // Track if initial catch-up was done for this chat
  const initialCatchUpDoneRef = useRef<string | null>(null);

  // Fetch newest messages and merge with existing cache (cursor-based)
  const fetchNewestMessages = useCallback(async () => {
    if (!chatId) return;

    try {
      console.log('[CATCH-UP] Fetching newest messages for chat:', chatId);
      logger.info('[CATCH-UP] Fetching newest messages', { chatId });

      // Fetch newest messages (no cursor = get latest)
      const messages = await chatApi.getMessages(chatId, {
        limit: MESSAGES_PER_PAGE,
      });

      console.log('[CATCH-UP] API returned messages:', messages.length);
      const normalizedMessages = messages.map(normalizeMessage);

      // Get oldest message ID for cursor
      const oldestMessage = normalizedMessages[normalizedMessages.length - 1];
      const oldestMessageId = oldestMessage?.id || null;

      // Merge with existing cache - add new messages to first page
      queryClient.setQueryData(
        chatKeys.messages(chatId),
        (oldData: any) => {
          console.log('[CATCH-UP] Existing cache pages:', oldData?.pages?.length || 0);

          if (!oldData?.pages?.length) {
            // No existing data, create fresh structure (cursor-based)
            console.log('[CATCH-UP] No cache, creating fresh with', normalizedMessages.length, 'messages');
            return {
              pages: [{
                messages: normalizedMessages,
                oldestMessageId,
                hasMore: messages.length === MESSAGES_PER_PAGE,
              }],
              pageParams: [null], // First page has null cursor
            };
          }

          // Build map of fresh messages for O(1) lookup
          const freshMessageMap = new Map<string, Message>();
          for (const msg of normalizedMessages) {
            freshMessageMap.set(String(msg.id), msg);
          }
          console.log('[CATCH-UP] Fresh messages from API:', freshMessageMap.size);

          // Build set of existing message IDs for O(1) lookup
          const existingIds = buildMessageIdSet(oldData.pages);
          console.log('[CATCH-UP] Existing message IDs count:', existingIds.size);

          // Find new messages that aren't in cache
          const newMessages = normalizedMessages.filter(
            (msg) => !existingIds.has(String(msg.id))
          );

          // IMPORTANT: Update existing messages with fresh data (telegram_read_at, etc.)
          // This ensures blue checkmarks persist after page refresh
          let updatedCount = 0;
          const newPages = oldData.pages.map((page: any) => ({
            ...page,
            messages: page.messages.map((m: Message) => {
              const freshMsg = freshMessageMap.get(String(m.id));
              if (freshMsg) {
                // Merge fresh data into existing message (preserves _stableKey)
                const hasChanges =
                  freshMsg.telegram_read_at !== m.telegram_read_at ||
                  freshMsg.telegram_message_id !== m.telegram_message_id;
                if (hasChanges) {
                  updatedCount++;
                }
                return { ...m, ...freshMsg, _stableKey: m._stableKey };
              }
              return m;
            }),
          }));

          if (updatedCount > 0) {
            console.log('[CATCH-UP] Updated', updatedCount, 'existing messages with fresh data (telegram_read_at, etc.)');
          }

          if (newMessages.length === 0 && updatedCount === 0) {
            console.log('[CATCH-UP] No new messages and no updates needed');
            logger.debug('[CATCH-UP] No changes needed');
            return oldData;
          }

          console.log('[CATCH-UP] Found', newMessages.length, 'new messages to add');
          logger.info('[CATCH-UP] Catch-up complete', { newMessages: newMessages.length, updated: updatedCount });

          // Add new messages to front of first page (newest messages)
          if (newMessages.length > 0) {
            newPages[0] = {
              ...newPages[0],
              messages: [...newMessages, ...newPages[0].messages],
            };
          }

          return { ...oldData, pages: newPages };
        }
      );
    } catch (error) {
      console.error('[CATCH-UP] Failed to fetch:', error);
      logger.error('[CATCH-UP] Failed to fetch newest messages', { error, chatId });
    }
  }, [chatId, queryClient]);

  // Initial mount catch-up: fetch new messages ONLY if we have cached data
  // If no cached data, let React Query do its natural initial fetch
  // This prevents conflicts between setQueryData and initial query fetch
  useEffect(() => {
    if (!chatId) return;

    // Skip if we already did catch-up for this chat
    if (initialCatchUpDoneRef.current === chatId) return;

    // IMPORTANT: Only run catch-up if there's cached data
    // If no cache (fresh login), let React Query fetch naturally
    if (!cachedData?.pages?.length) {
      console.log('[CATCH-UP] No cached data, letting React Query fetch naturally');
      initialCatchUpDoneRef.current = chatId;
      return;
    }

    initialCatchUpDoneRef.current = chatId;

    // Has cached data - fetch newest to merge any missed messages
    console.log('[CATCH-UP] Has cached data, fetching newest messages');
    const timeoutId = setTimeout(() => {
      fetchNewestMessages();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [chatId, cachedData?.pages?.length, fetchNewestMessages]);

  // Reset catch-up flag when chat changes
  useEffect(() => {
    if (chatId !== initialCatchUpDoneRef.current) {
      initialCatchUpDoneRef.current = null;
    }
  }, [chatId]);

  useEffect(() => {
    if (!chatId) return;

    let lastVisibleTime = Date.now();
    const REFETCH_THRESHOLD_MS = 10000; // 10 seconds - refetch if away longer

    // Visibility change handler - fetch new messages when returning to tab
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const awayTime = Date.now() - lastVisibleTime;

        // Only fetch if user was away for more than threshold
        if (awayTime > REFETCH_THRESHOLD_MS) {
          logger.info('[CATCH-UP] Tab became visible after being away', {
            chatId,
            awayTimeMs: awayTime,
          });
          fetchNewestMessages();
        }
      } else {
        lastVisibleTime = Date.now();
      }
    };

    // WSE reconnection handler - fetch new messages when WebSocket reconnects
    const handleWSEReconnected = () => {
      logger.info('[CATCH-UP] WSE reconnected, fetching new messages', { chatId });
      setTimeout(() => fetchNewestMessages(), 500);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('wse:reconnected', handleWSEReconnected);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('wse:reconnected', handleWSEReconnected);
    };
  }, [chatId, fetchNewestMessages]);

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

// -----------------------------------------------------------------------------
// Utility: Reconcile temp ID with server's Snowflake ID (Industry Standard)
// -----------------------------------------------------------------------------

/**
 * Replaces a temporary client ID with the server-generated Snowflake ID.
 * This is called after the server confirms the message was saved.
 *
 * Pattern: Discord/Slack optimistic UI reconciliation
 * 1. Client sends message with temp ID ("temp_<uuid>")
 * 2. Server generates Snowflake ID, echoes back temp ID
 * 3. Client replaces temp ID with Snowflake in cache
 *
 * IMPORTANT: Preserves _stableKey to prevent React remount/re-animation
 * The _stableKey is set to the original tempId and never changes.
 */
export function reconcileMessageId(
  queryClient: ReturnType<typeof useQueryClient>,
  chatId: string,
  tempId: string,
  snowflakeId: string
) {
  queryClient.setQueryData(
    chatKeys.messages(chatId),
    (oldData: any) => {
      if (!oldData) return oldData;

      const newPages = oldData.pages.map((page: any) => ({
        ...page,
        messages: page.messages.map((m: Message) =>
          m.id === tempId
            ? { ...m, id: snowflakeId, _stableKey: m._stableKey || tempId }
            : m
        ),
      }));

      return { ...oldData, pages: newPages };
    }
  );
}
