// =============================================================================
// File: src/stores/useSupergroupsStore.ts
// Description: Zustand store for supergroups cache (persisted)
// Pattern: TkDodo - Zustand for client cache, React Query for server state
// Purpose: Instant page refresh - no "Loading..." on refresh
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TelegramSupergroup } from '@/types/chat';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface SupergroupsStoreState {
  // Cached data (persisted) - for instant page refresh
  cachedActiveSupergroups: TelegramSupergroup[] | null;
  cachedArchivedSupergroups: TelegramSupergroup[] | null;
  cachedUpdatedAt: number | null;

  // Actions
  setCachedActiveSupergroups: (supergroups: TelegramSupergroup[]) => void;
  setCachedArchivedSupergroups: (supergroups: TelegramSupergroup[]) => void;
  clearCache: () => void;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const useSupergroupsStore = create<SupergroupsStoreState>()(
  persist(
    (set) => ({
      // Initial state
      cachedActiveSupergroups: null,
      cachedArchivedSupergroups: null,
      cachedUpdatedAt: null,

      // Actions
      setCachedActiveSupergroups: (supergroups) => {
        set({
          cachedActiveSupergroups: supergroups,
          cachedUpdatedAt: Date.now(),
        });
      },

      setCachedArchivedSupergroups: (supergroups) => {
        set({
          cachedArchivedSupergroups: supergroups,
          cachedUpdatedAt: Date.now(),
        });
      },

      clearCache: () => {
        set({
          cachedActiveSupergroups: null,
          cachedArchivedSupergroups: null,
          cachedUpdatedAt: null,
        });
      },
    }),
    {
      name: 'wellwon-supergroups',
      partialize: (state) => ({
        cachedActiveSupergroups: state.cachedActiveSupergroups,
        cachedArchivedSupergroups: state.cachedArchivedSupergroups,
        cachedUpdatedAt: state.cachedUpdatedAt,
      }),
    }
  )
);

// -----------------------------------------------------------------------------
// Atomic Selectors (TkDodo pattern - return single values)
// -----------------------------------------------------------------------------

export const useCachedActiveSupergroups = () =>
  useSupergroupsStore((s) => s.cachedActiveSupergroups);
export const useCachedArchivedSupergroups = () =>
  useSupergroupsStore((s) => s.cachedArchivedSupergroups);
export const useCachedSupergroupsUpdatedAt = () =>
  useSupergroupsStore((s) => s.cachedUpdatedAt);
