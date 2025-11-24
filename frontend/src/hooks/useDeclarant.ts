// =============================================================================
// useDeclarant Hook
// =============================================================================
// Combined hook that provides both server state (React Query) and UI state (Zustand)
// for the Declarant module

import { useQuery } from '@tanstack/react-query';
import { useDeclarantStore } from '@/stores/useDeclarantStore';
import { getDeclarantBatches, getDeclarantStats } from '@/api/declarant';
import type { DeclarantBatch, DeclarantStats } from '@/types/declarant';

/**
 * Main hook for Declarant data and UI state
 *
 * Returns:
 * - Server state: batches, stats, loading states
 * - UI state: filters, selections, preferences
 * - Actions: toggle filters, select batches, etc.
 */
export function useDeclarant() {
  // ============================================================================
  // Server State (React Query)
  // ============================================================================

  // Fetch batches
  const {
    data: batches = [],
    isLoading: batchesLoading,
    error: batchesError,
    refetch: refetchBatches,
  } = useQuery<DeclarantBatch[]>({
    queryKey: ['declarant', 'batches'],
    queryFn: getDeclarantBatches,
    staleTime: 30 * 1000, // 30 seconds
    // TODO: Add WSE invalidation when backend ready
    // Will auto-refetch when 'declarant_batch_updated' event received
  });

  // Fetch stats
  const {
    data: stats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useQuery<DeclarantStats>({
    queryKey: ['declarant', 'stats'],
    queryFn: getDeclarantStats,
    staleTime: 60 * 1000, // 1 minute
    // TODO: Add WSE invalidation when backend ready
  });

  // ============================================================================
  // UI State (Zustand)
  // ============================================================================

  const {
    // State
    tableView,
    sortOrder,
    selectedFilters,
    selectedBatchIds,
    draftBatch,

    // Actions
    setTableView,
    setSortOrder,
    toggleFilter,
    toggleBatchSelection,
    selectAllBatches,
    clearSelection,
    setDraftBatch,
  } = useDeclarantStore();

  // ============================================================================
  // Computed Values
  // ============================================================================

  // Filter batches by selected filters
  const filteredBatches = batches.filter((batch) => {
    if (selectedFilters.length === 0) return true;
    return selectedFilters.includes(batch.status);
  });

  // Sort batches
  const sortedBatches = [...filteredBatches].sort((a, b) => {
    const dateA = new Date(a.created_at).getTime();
    const dateB = new Date(b.created_at).getTime();
    return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  // Get selected batches
  const selectedBatches = sortedBatches.filter((batch) =>
    selectedBatchIds.includes(batch.id)
  );

  // Overall loading state
  const isLoading = batchesLoading || statsLoading;

  // ============================================================================
  // Actions
  // ============================================================================

  const handleSelectAll = () => {
    if (selectedBatchIds.length === sortedBatches.length) {
      // Deselect all
      clearSelection();
    } else {
      // Select all visible batches
      selectAllBatches(sortedBatches.map((b) => b.id));
    }
  };

  const handleRefresh = async () => {
    await Promise.all([refetchBatches(), refetchStats()]);
  };

  // ============================================================================
  // Return Value
  // ============================================================================

  return {
    // Server data
    batches: sortedBatches,
    stats,
    isLoading,
    batchesError,

    // UI state
    tableView,
    sortOrder,
    selectedFilters,
    selectedBatchIds,
    selectedBatches,
    draftBatch,

    // Actions
    setTableView,
    setSortOrder,
    toggleFilter,
    toggleBatchSelection,
    handleSelectAll,
    clearSelection,
    setDraftBatch,
    handleRefresh,

    // Helpers
    isAllSelected: selectedBatchIds.length === sortedBatches.length && sortedBatches.length > 0,
  };
}
