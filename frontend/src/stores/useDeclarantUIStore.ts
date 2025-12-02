// =============================================================================
// File: src/stores/useDeclarantUIStore.ts
// Description: Zustand store for Declarant UI state (persisted)
// Pattern: TkDodo - Zustand for client state, atomic selectors
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface DeclarantUIState {
  // Persisted UI state
  isDark: boolean;
  sidebarCollapsed: boolean;
  rowsPerPage: string;

  // Actions
  setIsDark: (dark: boolean) => void;
  toggleTheme: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setRowsPerPage: (rows: string) => void;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const useDeclarantUIStore = create<DeclarantUIState>()(
  persist(
    (set) => ({
      // Initial state
      isDark: true, // Default dark theme
      sidebarCollapsed: false,
      rowsPerPage: '10',

      // Actions
      setIsDark: (dark) => set({ isDark: dark }),
      toggleTheme: () => set((s) => ({ isDark: !s.isDark })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setRowsPerPage: (rows) => set({ rowsPerPage: rows }),
    }),
    {
      name: 'wellwon-declarant-ui',
      partialize: (state) => ({
        isDark: state.isDark,
        sidebarCollapsed: state.sidebarCollapsed,
        rowsPerPage: state.rowsPerPage,
      }),
    }
  )
);

// -----------------------------------------------------------------------------
// Atomic Selectors (TkDodo pattern - return single values)
// -----------------------------------------------------------------------------

export const useDeclarantIsDark = () => useDeclarantUIStore((s) => s.isDark);
export const useDeclarantSidebarCollapsed = () => useDeclarantUIStore((s) => s.sidebarCollapsed);
export const useDeclarantRowsPerPage = () => useDeclarantUIStore((s) => s.rowsPerPage);
