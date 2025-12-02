// =============================================================================
// File: src/stores/usePlatformStore.ts
// Description: Zustand store for platform UI state (persisted)
// Pattern: TkDodo - Zustand for client state, atomic selectors, actions namespace
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface SelectedCompany {
  id: string;
  name: string;
  company_type: string;
}

interface PlatformActions {
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleTheme: () => void;
  setIsLightTheme: (light: boolean) => void;
  setSelectedCompany: (company: SelectedCompany | null) => void;
  clearCompany: () => void;
}

interface PlatformState {
  // Persisted UI state
  sidebarCollapsed: boolean;
  isLightTheme: boolean;
  selectedCompany: SelectedCompany | null;

  // Actions namespace (TkDodo pattern)
  actions: PlatformActions;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const usePlatformStore = create<PlatformState>()(
  persist(
    (set) => ({
      // Initial state
      sidebarCollapsed: false,
      isLightTheme: false,
      selectedCompany: null,

      // Actions namespace
      actions: {
        toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
        setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
        toggleTheme: () => set((s) => ({ isLightTheme: !s.isLightTheme })),
        setIsLightTheme: (light) => set({ isLightTheme: light }),
        setSelectedCompany: (company) => set({
          selectedCompany: company ? {
            id: company.id,
            name: company.name,
            company_type: company.company_type,
          } : null,
        }),
        clearCompany: () => set({ selectedCompany: null }),
      },
    }),
    {
      name: 'wellwon-platform',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        isLightTheme: state.isLightTheme,
        selectedCompany: state.selectedCompany,
      }),
    }
  )
);

// -----------------------------------------------------------------------------
// Atomic Selectors (TkDodo pattern - return single values)
// -----------------------------------------------------------------------------

export const useSidebarCollapsed = () => usePlatformStore((s) => s.sidebarCollapsed);
export const useIsLightTheme = () => usePlatformStore((s) => s.isLightTheme);
export const useSelectedCompany = () => usePlatformStore((s) => s.selectedCompany);
export const usePlatformActions = () => usePlatformStore((s) => s.actions);

// -----------------------------------------------------------------------------
// Helper: Get state outside React (for non-component code)
// -----------------------------------------------------------------------------

export function getPlatformState() {
  return usePlatformStore.getState();
}

export function isSidebarCollapsed(): boolean {
  return usePlatformStore.getState().sidebarCollapsed;
}
