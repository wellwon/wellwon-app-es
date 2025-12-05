// =============================================================================
// File: src/stores/useMessagesStore.ts
// Description: Zustand store for messages cache persistence (TkDodo pattern)
// Purpose: Instant page refresh - messages appear immediately from cache
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface MessagePage {
  messages: any[];
  // Cursor-based pagination (2025 pattern)
  oldestMessageId: string | null;
  hasMore: boolean;
  // Legacy field for backwards compatibility
  nextOffset?: number | null;
}

interface ChatMessagesCache {
  pages: MessagePage[];
  // Cursor-based: string | null (message IDs), legacy: number[]
  pageParams: (string | number | null)[];
  updatedAt: number;
}

interface MessagesStoreState {
  // Cache per chat - keyed by chatId
  messagesCache: Record<string, ChatMessagesCache>;

  // Active chat for quick access
  activeChatId: string | null;

  // Actions
  setChatMessages: (chatId: string, pages: MessagePage[], pageParams: (string | number | null)[]) => void;
  getChatMessages: (chatId: string) => ChatMessagesCache | null;
  setActiveChatId: (chatId: string | null) => void;
  clearChatCache: (chatId: string) => void;
  clearAllCache: () => void;
}

// Max chats to cache (LRU-style cleanup)
const MAX_CACHED_CHATS = 10;
// Max age before considering stale (30 minutes)
const MAX_CACHE_AGE_MS = 30 * 60 * 1000;

export const useMessagesStore = create<MessagesStoreState>()(
  persist(
    (set, get) => ({
      messagesCache: {},
      activeChatId: null,

      setChatMessages: (chatId, pages, pageParams) => {
        set((state) => {
          const newCache = { ...state.messagesCache };

          // Add/update cache for this chat
          newCache[chatId] = {
            pages,
            pageParams,
            updatedAt: Date.now(),
          };

          // LRU cleanup - keep only MAX_CACHED_CHATS most recent
          const chatIds = Object.keys(newCache);
          if (chatIds.length > MAX_CACHED_CHATS) {
            // Sort by updatedAt, remove oldest
            const sortedIds = chatIds.sort(
              (a, b) => (newCache[b]?.updatedAt || 0) - (newCache[a]?.updatedAt || 0)
            );
            sortedIds.slice(MAX_CACHED_CHATS).forEach((id) => {
              delete newCache[id];
            });
          }

          return { messagesCache: newCache };
        });
      },

      getChatMessages: (chatId) => {
        const cache = get().messagesCache[chatId];
        if (!cache) return null;

        // Check if cache is stale
        if (Date.now() - cache.updatedAt > MAX_CACHE_AGE_MS) {
          return null;
        }

        return cache;
      },

      setActiveChatId: (chatId) => {
        set({ activeChatId: chatId });
      },

      clearChatCache: (chatId) => {
        set((state) => {
          const newCache = { ...state.messagesCache };
          delete newCache[chatId];
          return { messagesCache: newCache };
        });
      },

      clearAllCache: () => {
        set({ messagesCache: {}, activeChatId: null });
      },
    }),
    {
      name: 'wellwon-messages',
      partialize: (state) => ({
        messagesCache: state.messagesCache,
        activeChatId: state.activeChatId,
      }),
    }
  )
);

// Expose store globally for logout to access
if (typeof window !== 'undefined') {
  (window as any).__MESSAGES_STORE__ = useMessagesStore;
}
