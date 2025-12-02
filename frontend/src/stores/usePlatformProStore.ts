// =============================================================================
// File: src/stores/usePlatformProStore.ts
// Description: Zustand store for Platform Pro UI state (persisted)
// Pattern: TkDodo - Zustand for client state, atomic selectors
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface PlatformProState {
  // Persisted UI state
  sidebarCollapsed: boolean;
  isDark: boolean;

  // Actions
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setIsDark: (dark: boolean) => void;
  toggleTheme: () => void;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const usePlatformProStore = create<PlatformProState>()(
  persist(
    (set) => ({
      // Initial state
      sidebarCollapsed: false,
      isDark: true, // Default dark theme

      // Actions
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setIsDark: (dark) => set({ isDark: dark }),
      toggleTheme: () => set((s) => ({ isDark: !s.isDark })),
    }),
    {
      name: 'wellwon-platform-pro',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        isDark: state.isDark,
      }),
    }
  )
);

// -----------------------------------------------------------------------------
// Atomic Selectors (TkDodo pattern - return single values)
// -----------------------------------------------------------------------------

export const usePlatformProSidebarCollapsed = () => usePlatformProStore((s) => s.sidebarCollapsed);
export const usePlatformProIsDark = () => usePlatformProStore((s) => s.isDark);
