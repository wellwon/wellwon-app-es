// =============================================================================
// Declarant Zustand Store
// =============================================================================
// Local UI state management for Declarant module
// Server state managed by React Query (see hooks/useDeclarant.ts)

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { DeclarantUIState, TableView, SortOrder } from '@/types/declarant';

export const useDeclarantStore = create<DeclarantUIState>()(
  persist(
    (set) => ({
      // View preferences (persisted to localStorage)
      tableView: 'list',
      sortOrder: 'desc',
      selectedFilters: [],

      // Temporary state (not persisted)
      selectedBatchIds: [],
      draftBatch: null,

      // Actions
      setTableView: (view: TableView) =>
        set({ tableView: view }),

      setSortOrder: (order: SortOrder) =>
        set({ sortOrder: order }),

      toggleFilter: (filter: string) =>
        set((state) => ({
          selectedFilters: state.selectedFilters.includes(filter)
            ? state.selectedFilters.filter((f) => f !== filter)
            : [...state.selectedFilters, filter],
        })),

      toggleBatchSelection: (id: string) =>
        set((state) => ({
          selectedBatchIds: state.selectedBatchIds.includes(id)
            ? state.selectedBatchIds.filter((batchId) => batchId !== id)
            : [...state.selectedBatchIds, id],
        })),

      selectAllBatches: (ids: string[]) =>
        set({ selectedBatchIds: ids }),

      clearSelection: () =>
        set({ selectedBatchIds: [] }),

      setDraftBatch: (draft) =>
        set({ draftBatch: draft }),
    }),
    {
      name: 'declarant-ui-preferences', // localStorage key
      partialize: (state) => ({
        // Only persist these fields
        tableView: state.tableView,
        sortOrder: state.sortOrder,
        selectedFilters: state.selectedFilters,
        // Do NOT persist: selectedBatchIds, draftBatch (temporary)
      }),
    }
  )
);
