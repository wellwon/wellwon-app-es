// =============================================================================
// File: src/hooks/chat/useChatList.ts
// Description: React Query hook for chat list with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query" + proper cleanup
// =============================================================================

import { useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { ChatListItem } from '@/api/chat';
import { chatKeys } from './useChatMessages';
import { logger } from '@/utils/logger';
import { useChatsStore } from '@/stores/useChatsStore';
import { useMessagesStore } from '@/stores/useMessagesStore';
import { useChatUIStore } from './useChatUIStore';

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

  // Track pending retries for cleanup (prevents stale writes after unmount)
  const pendingRetriesRef = useRef<Map<string, AbortController>>(new Map());

  // Cleanup function for pending retries
  const cancelPendingRetry = useCallback((chatId: string) => {
    const controller = pendingRetriesRef.current.get(chatId);
    if (controller) {
      controller.abort();
      pendingRetriesRef.current.delete(chatId);
    }
  }, []);

  // Zustand clearCache for when all chats are removed
  const clearCache = useChatsStore((s) => s.clearCache);

  // Helper to sync Zustand after any cache update
  const syncZustandCache = useCallback(() => {
    const currentChats = queryClient.getQueryData<ChatListItem[]>(
      chatKeys.list({ includeArchived, limit })
    );
    if (currentChats && currentChats.length > 0) {
      setCachedChats(currentChats);
    } else if (currentChats && currentChats.length === 0) {
      // CRITICAL: Clear Zustand cache when all chats are removed
      // This prevents deleted chats from reappearing on page refresh
      clearCache();
    }
  }, [queryClient, includeArchived, limit, setCachedChats, clearCache]);

  const query = useQuery({
    queryKey: chatKeys.list({ includeArchived, limit }),
    queryFn: async () => {
      const apiChats = await chatApi.getChats(includeArchived, limit, 0);

      // CRITICAL: Preserve optimistic entries and their telegram_supergroup_id
      const existingData = queryClient.getQueryData<OptimisticChatListItem[]>(chatKeys.list({ includeArchived, limit }));
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter(e => e._isOptimistic);
        if (optimisticEntries.length > 0) {
          logger.info('useChatList: Preserving optimistic entries', {
            optimisticCount: optimisticEntries.length,
            apiCount: apiChats.length
          });

          // Build a map of optimistic entries for quick lookup
          const optimisticMap = new Map(optimisticEntries.map(o => [o.id, o]));

          // Placeholder names that should NOT overwrite real names
          // NOTE: "Чат компании" is the REAL name for company chats, not a placeholder!
          const PLACEHOLDER_NAMES = ['Chat Company', 'General', 'Новый чат', 'New chat', ''];

          // Merge API data with optimistic entries, preserving telegram_supergroup_id and real names
          const mergedApiChats = apiChats.map(apiChat => {
            const optimistic = optimisticMap.get(apiChat.id);
            if (!optimistic) return apiChat;

            // Preserve telegram_supergroup_id if API doesn't have it yet
            const preservedSupergroupId = apiChat.telegram_supergroup_id || optimistic.telegram_supergroup_id;

            // STABILIZATION: Don't let API placeholder name overwrite optimistic real name
            const optimisticNameIsReal = optimistic.name && !PLACEHOLDER_NAMES.includes(optimistic.name);
            const apiNameIsPlaceholder = !apiChat.name || PLACEHOLDER_NAMES.includes(apiChat.name);
            const finalName = (optimisticNameIsReal && apiNameIsPlaceholder)
              ? optimistic.name
              : apiChat.name;

            return {
              ...apiChat,
              name: finalName,
              telegram_supergroup_id: preservedSupergroupId,
            };
          });

          // Keep optimistic entries that aren't in API response yet
          const apiIds = new Set(apiChats.map(c => c.id));
          const uniqueOptimistic = optimisticEntries.filter(o => !apiIds.has(o.id));
          const result = [...uniqueOptimistic, ...mergedApiChats];
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

      // Cancel any existing retry for this chat (idempotent handling)
      cancelPendingRetry(chatId);

      // Get current chat scope to inherit telegram_supergroup_id if not in event
      // This fixes the issue where chat_created fires before chat_telegram_linked
      const chatScope = useChatUIStore.getState().chatScope;
      const selectedSupergroupId = useChatUIStore.getState().selectedSupergroupId;

      // Determine the best telegram_supergroup_id to use:
      // 1. Use event data if available
      // 2. Fall back to current chatScope.supergroupId (user is creating within a supergroup)
      // 3. Fall back to selectedSupergroupId (user has a supergroup selected)
      const telegram_supergroup_id =
        newChatData.telegram_supergroup_id ||
        (chatScope.type === 'supergroup' ? chatScope.supergroupId : null) ||
        selectedSupergroupId ||
        null;

      logger.info('WSE: Chat created, adding optimistically', {
        chatId,
        inheritedSupergroupId: telegram_supergroup_id,
      });

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
        company_id: newChatData.company_id || chatScope.companyId || null,
        telegram_chat_id: newChatData.telegram_chat_id || null,
        telegram_supergroup_id: telegram_supergroup_id, // Important for filtering - inherits from scope if not in event
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

          // Check if already exists (idempotent)
          if (oldData.some((c) => c.id === chatId)) {
            return oldData;
          }

          // Add at beginning (newest first)
          return [optimisticChat, ...oldData];
        }
      );

      // Sync Zustand immediately
      syncZustandCache();

      // Create AbortController for this retry sequence
      const abortController = new AbortController();
      pendingRetriesRef.current.set(chatId, abortController);

      // Retry logic with exponential backoff and proper cancellation
      const fetchWithRetry = async (attempts = 3, baseDelay = 1000) => {
        for (let i = 0; i < attempts; i++) {
          // Check if aborted before waiting
          if (abortController.signal.aborted) {
            logger.debug('WSE: Retry cancelled for chat', { chatId });
            return;
          }

          const delay = baseDelay * Math.pow(2, i); // 1s, 2s, 4s
          await new Promise((resolve, reject) => {
            const timeout = setTimeout(resolve, delay);
            abortController.signal.addEventListener('abort', () => {
              clearTimeout(timeout);
              reject(new Error('Aborted'));
            }, { once: true });
          }).catch(() => {
            // Aborted during wait
            return;
          });

          // Check again after wait
          if (abortController.signal.aborted) {
            return;
          }

          try {
            const fullChat = await chatApi.getChatById(chatId);
            if (fullChat && !abortController.signal.aborted) {
              // Placeholder names that should NOT overwrite real names
              // NOTE: "Чат компании" is the REAL name for company chats, not a placeholder!
              const PLACEHOLDER_NAMES = ['Chat Company', 'General', 'Новый чат', 'New chat', ''];

              queryClient.setQueryData(
                chatKeys.list({ includeArchived, limit }),
                (oldData: ChatListItem[] | undefined) => {
                  if (!oldData) return [fullChat];
                  return oldData.map((c) => {
                    if (c.id !== chatId) return c;

                    // CRITICAL: Preserve telegram_supergroup_id from optimistic entry
                    // if API doesn't have it yet (TelegramChatLinked event hasn't fired)
                    // This prevents the chat from disappearing from filtered view
                    const preservedSupergroupId = fullChat.telegram_supergroup_id ||
                      (c as OptimisticChatListItem).telegram_supergroup_id;

                    // STABILIZATION: Don't let API placeholder name overwrite real name
                    const currentNameIsReal = c.name && !PLACEHOLDER_NAMES.includes(c.name);
                    const apiNameIsPlaceholder = !fullChat.name || PLACEHOLDER_NAMES.includes(fullChat.name);
                    const finalName = (currentNameIsReal && apiNameIsPlaceholder)
                      ? c.name
                      : fullChat.name;

                    return {
                      ...fullChat,
                      name: finalName,
                      telegram_supergroup_id: preservedSupergroupId,
                      _isOptimistic: false,
                    };
                  });
                }
              );
              syncZustandCache();
              logger.info('WSE: Full chat fetched after retry', { chatId, attempt: i + 1 });
              pendingRetriesRef.current.delete(chatId);
              return;
            }
          } catch (error) {
            if (abortController.signal.aborted) return;
            if (i === attempts - 1) {
              logger.warn('WSE: Failed to fetch full chat after all retries, keeping optimistic', {
                chatId,
                attempts,
              });
              // IMPORTANT: Still sync Zustand to persist optimistic entry
              syncZustandCache();
            } else {
              logger.debug('WSE: Chat fetch attempt failed, retrying...', { chatId, attempt: i + 1 });
            }
          }
        }
        pendingRetriesRef.current.delete(chatId);
      };

      // Fire and track (not truly fire-and-forget anymore)
      fetchWithRetry();
    };

    const handleChatUpdated = (event: CustomEvent) => {
      const updatedChat = event.detail;
      const chatId = updatedChat.chat_id || updatedChat.id;

      logger.debug('WSE: Chat updated', { chatId, newName: updatedChat.name });

      // Placeholder names that should NOT overwrite real names
      // NOTE: "Чат компании" is the REAL name for company chats, not a placeholder!
      const PLACEHOLDER_NAMES = ['Chat Company', 'General', 'Новый чат', 'New chat', ''];

      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;

          return oldData.map((chat) => {
            if (chat.id !== chatId) return chat;

            // STABILIZATION: Don't let placeholder names overwrite real names
            // Once a chat has a "real" name, keep it unless a new "real" name comes
            const currentNameIsReal = chat.name && !PLACEHOLDER_NAMES.includes(chat.name);
            const newNameIsPlaceholder = !updatedChat.name || PLACEHOLDER_NAMES.includes(updatedChat.name);

            const finalName = (currentNameIsReal && newNameIsPlaceholder)
              ? chat.name  // Keep current real name
              : (updatedChat.name ?? chat.name);  // Use new name

            if (currentNameIsReal && newNameIsPlaceholder) {
              logger.debug('WSE: Ignoring placeholder name update', {
                chatId,
                currentName: chat.name,
                rejectedName: updatedChat.name
              });
            }

            return {
              ...chat,
              name: finalName,
              last_message_at: updatedChat.last_message_at ?? chat.last_message_at,
              last_message_content: updatedChat.last_message_content ?? chat.last_message_content,
              unread_count: updatedChat.unread_count ?? chat.unread_count,
            };
          });
        }
      );

      syncZustandCache();
    };

    const handleChatArchived = (event: CustomEvent) => {
      const archivedChat = event.detail;
      const chatId = archivedChat.chat_id || archivedChat.id;

      logger.debug('WSE: Chat archived', { chatId });

      // Cancel any pending retries for this chat
      cancelPendingRetry(chatId);

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

      syncZustandCache();
    };

    const handleChatDeleted = (event: CustomEvent) => {
      const deletedChat = event.detail;
      const chatId = deletedChat.chat_id || deletedChat.id;

      logger.debug('WSE: Chat deleted, clearing all caches', { chatId });

      // Cancel any pending retries for this chat
      cancelPendingRetry(chatId);

      // Remove from list cache
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((chat) => chat.id !== chatId);
        }
      );

      // Remove all related React Query caches
      queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });
      queryClient.removeQueries({ queryKey: chatKeys.messages(chatId) });
      queryClient.removeQueries({ queryKey: chatKeys.participants(chatId) });

      // CRITICAL: Clear Zustand persistent cache for this chat's messages
      // This prevents deleted chat messages from appearing on page refresh
      const { clearChatCache } = useMessagesStore.getState();
      clearChatCache(chatId);

      syncZustandCache();
      logger.info('WSE: Chat deleted, all caches cleared', { chatId });
    };

    // OPTIMISTIC UPDATE: Update last_message and unread_count when message is created
    const handleMessageCreated = (event: CustomEvent) => {
      const message = event.detail;
      const chatId = message.chat_id;
      const senderId = message.sender_id;

      if (!chatId) return;

      // Get active chat from Zustand to know if user is viewing this chat
      const activeChatId = useChatUIStore.getState().activeChatId;
      const isViewingChat = activeChatId === chatId;

      logger.debug('WSE: Message created, updating chat', { chatId, isViewingChat, senderId });

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
                  last_message_sender_id: senderId || null,
                  // Increment unread_count if:
                  // 1. User is NOT viewing this chat
                  // 2. Message is NOT from current user (senderId check happens on backend)
                  unread_count: isViewingChat
                    ? (chat.unread_count || 0)  // Don't increment if viewing
                    : (chat.unread_count || 0) + 1,  // Increment if not viewing
                }
              : chat
          );
        }
      );

      syncZustandCache();
    };

    // Handle messages marked as read - reset unread_count
    // IMPORTANT: Only reset if current user is viewing this chat or event is from current user
    const handleMessagesRead = (event: CustomEvent) => {
      const data = event.detail;
      const chatId = data.chat_id;
      const readByUserId = data.user_id; // Who marked as read

      if (!chatId) return;

      // Get current user and active chat
      const activeChatId = useChatUIStore.getState().activeChatId;
      const isViewingChat = activeChatId === chatId;

      // If event has user_id and it's NOT from someone else reading,
      // OR if user is currently viewing this chat - then reset unread
      // If no user_id in event (local optimistic), always reset
      const shouldResetUnread = isViewingChat || !readByUserId;

      if (!shouldResetUnread) {
        logger.debug('WSE: Ignoring messagesRead from other user', { chatId, readByUserId });
        return;
      }

      logger.debug('WSE: Messages marked as read, resetting unread_count', { chatId, isViewingChat });

      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((chat) =>
            chat.id === chatId
              ? { ...chat, unread_count: 0 }
              : chat
          );
        }
      );

      syncZustandCache();
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

      // Cancel pending retry - we have the real data now
      cancelPendingRetry(chatId);

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

      syncZustandCache();
    };

    // Handle group deletion saga completion - remove all chats for the deleted company
    const handleGroupDeletionCompleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id;

      logger.info('WSE: Group deletion completed, clearing all caches for company', { companyId });

      // Cancel any pending retries for chats being deleted
      pendingRetriesRef.current.forEach((controller) => {
        controller.abort();
      });
      pendingRetriesRef.current.clear();

      // Get current chats to identify which ones to clean up
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );

      // Find all chat IDs belonging to this company
      const chatsToDelete = currentChats?.filter(chat => chat.company_id === companyId) || [];

      // CRITICAL: Clear ALL related caches for each deleted chat
      const { clearChatCache, clearAllCache } = useMessagesStore.getState();

      chatsToDelete.forEach(chat => {
        const chatId = chat.id;

        // Remove React Query caches
        queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });
        queryClient.removeQueries({ queryKey: chatKeys.messages(chatId) });
        queryClient.removeQueries({ queryKey: chatKeys.participants(chatId) });

        // Clear Zustand persistent messages cache
        clearChatCache(chatId);

        logger.debug('WSE: Cleared caches for deleted chat', { chatId, companyId });
      });

      // Remove all chats belonging to this company from list
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((chat) => chat.company_id !== companyId);
        }
      );

      syncZustandCache();
      logger.info('WSE: Group deletion cleanup complete', {
        companyId,
        chatsDeleted: chatsToDelete.length
      });
    };

    // CRITICAL: Handle company deletion - remove all chats for the deleted company
    // This is dispatched from GroupsPanel when user deletes a group
    const handleCompanyDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;

      if (!companyId) {
        logger.warn('WSE: companyDeleted missing company_id', { data });
        return;
      }

      logger.info('WSE: Company deleted, clearing all caches for company', { companyId });

      // Cancel any pending retries for chats being deleted
      pendingRetriesRef.current.forEach((controller) => {
        controller.abort();
      });
      pendingRetriesRef.current.clear();

      // Get current chats to identify which ones to clean up
      const currentChats = queryClient.getQueryData<ChatListItem[]>(
        chatKeys.list({ includeArchived, limit })
      );

      // Find all chat IDs belonging to this company
      const chatsToDelete = currentChats?.filter(chat => chat.company_id === companyId) || [];

      // CRITICAL: Clear ALL related caches for each deleted chat
      const { clearChatCache } = useMessagesStore.getState();

      chatsToDelete.forEach(chat => {
        const chatId = chat.id;

        // Remove React Query caches
        queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });
        queryClient.removeQueries({ queryKey: chatKeys.messages(chatId) });
        queryClient.removeQueries({ queryKey: chatKeys.participants(chatId) });

        // Clear Zustand persistent messages cache
        clearChatCache(chatId);

        logger.debug('WSE: Cleared caches for deleted chat', { chatId, companyId });
      });

      // Remove all chats belonging to this company from list
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((chat) => chat.company_id !== companyId);
        }
      );

      syncZustandCache();
      logger.info('WSE: Company deletion cleanup complete', {
        companyId,
        chatsDeleted: chatsToDelete.length
      });
    };

    // CRITICAL: Handle group creation saga completion - add the chat that was created
    const handleGroupCreationCompleted = async (event: CustomEvent) => {
      const data = event.detail;
      const chatId = data.chat_id;
      const companyId = data.company_id;
      const telegramGroupId = data.telegram_group_id;

      console.log('[OPTIMISTIC DEBUG] handleGroupCreationCompleted received:', {
        chatId,
        companyId,
        telegramGroupId,
        fullData: data
      });

      if (!chatId) {
        logger.warn('WSE: groupCreationCompleted missing chat_id', { data });
        return;
      }

      logger.info('WSE: Group creation completed, adding chat', {
        chatId,
        companyId,
        telegramGroupId
      });

      // Cancel any in-flight refetches
      await queryClient.cancelQueries({
        queryKey: chatKeys.list({ includeArchived, limit })
      });

      // Create chat entry from saga completion data
      // CRITICAL: Keep _isOptimistic: true until the chat appears in API response
      // Otherwise queryFn will drop it on refetch since it only preserves _isOptimistic entries
      // NOTE: Chat name is ALWAYS "Чат компании" - NOT the company name!
      const newChat: OptimisticChatListItem = {
        id: chatId,
        name: 'Чат компании',
        chat_type: 'company',
        is_active: true,
        created_at: data.timestamp || new Date().toISOString(),
        company_id: companyId,
        telegram_chat_id: null,
        telegram_supergroup_id: telegramGroupId,
        telegram_topic_id: 1, // General topic
        last_message_at: data.timestamp || new Date().toISOString(),
        last_message_content: null,
        last_message_sender_id: null,
        unread_count: 0,
        participant_count: 1,
        other_participant_name: null,
        _isOptimistic: true, // IMPORTANT: Keep as true until API confirms!
      };

      // Add to cache
      queryClient.setQueryData(
        chatKeys.list({ includeArchived, limit }),
        (oldData: ChatListItem[] | undefined) => {
          if (!oldData) return [newChat];

          // Remove any optimistic entries for this company and add the real chat
          const filtered = oldData.filter(c => {
            // Remove optimistic chats with matching company_id
            if ((c as any)._isOptimistic && c.company_id === companyId) {
              return false;
            }
            // Remove if same chat_id already exists
            if (c.id === chatId) {
              return false;
            }
            return true;
          });

          return [newChat, ...filtered];
        }
      );

      syncZustandCache();

      console.log('[OPTIMISTIC DEBUG] Chat added to cache:', {
        chatId: newChat.id,
        telegram_supergroup_id: newChat.telegram_supergroup_id,
        company_id: newChat.company_id,
        cacheKeyUsed: chatKeys.list({ includeArchived, limit })
      });

      // Also dispatch chatCreated event for any other listeners
      window.dispatchEvent(new CustomEvent('chatCreated', { detail: newChat }));
    };

    // Subscribe to WSE events
    window.addEventListener('chatCreated', handleChatCreated as EventListener);
    window.addEventListener('chatUpdated', handleChatUpdated as EventListener);
    window.addEventListener('chatArchived', handleChatArchived as EventListener);
    window.addEventListener('chatDeleted', handleChatDeleted as EventListener);
    window.addEventListener('messageCreated', handleMessageCreated as EventListener);
    window.addEventListener('messagesRead', handleMessagesRead as EventListener);
    window.addEventListener('chatTelegramLinked', handleChatTelegramLinked as EventListener);
    window.addEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);
    window.addEventListener('groupCreationCompleted', handleGroupCreationCompleted as EventListener);
    window.addEventListener('companyDeleted', handleCompanyDeleted as EventListener);

    return () => {
      // Cleanup event listeners
      window.removeEventListener('chatCreated', handleChatCreated as EventListener);
      window.removeEventListener('chatUpdated', handleChatUpdated as EventListener);
      window.removeEventListener('chatArchived', handleChatArchived as EventListener);
      window.removeEventListener('chatDeleted', handleChatDeleted as EventListener);
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('messagesRead', handleMessagesRead as EventListener);
      window.removeEventListener('chatTelegramLinked', handleChatTelegramLinked as EventListener);
      window.removeEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);
      window.removeEventListener('groupCreationCompleted', handleGroupCreationCompleted as EventListener);
      window.removeEventListener('companyDeleted', handleCompanyDeleted as EventListener);

      // CRITICAL: Cancel all pending retries on unmount to prevent stale writes
      pendingRetriesRef.current.forEach((controller) => {
        controller.abort();
      });
      pendingRetriesRef.current.clear();
    };
  }, [queryClient, includeArchived, limit, syncZustandCache, cancelPendingRetry]);

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
