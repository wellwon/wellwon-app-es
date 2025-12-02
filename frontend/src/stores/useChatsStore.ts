// =============================================================================
// File: src/stores/useChatsStore.ts — Zustand store for chat list caching
// =============================================================================
// Purpose: Provides persistent cache for chat list to enable instant render
// on page refresh while React Query fetches fresh data.
// Pattern: Same as useSupergroupsStore.ts (proven to work)
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatListItem } from '@/api/chat';

interface ChatsStoreState {
  // Cached chat list for instant render on page load
  cachedChats: ChatListItem[] | null;
  // Timestamp of last cache update (for initialDataUpdatedAt)
  cachedUpdatedAt: number | null;

  // Actions
  setCachedChats: (chats: ChatListItem[]) => void;
  clearCache: () => void;
}

export const useChatsStore = create<ChatsStoreState>()(
  persist(
    (set) => ({
      cachedChats: null,
      cachedUpdatedAt: null,

      setCachedChats: (chats) => set({
        cachedChats: chats,
        cachedUpdatedAt: Date.now(),
      }),

      clearCache: () => set({
        cachedChats: null,
        cachedUpdatedAt: null,
      }),
    }),
    {
      name: 'wellwon-chats',
      partialize: (state) => ({
        cachedChats: state.cachedChats,
        cachedUpdatedAt: state.cachedUpdatedAt,
      }),
    }
  )
);
