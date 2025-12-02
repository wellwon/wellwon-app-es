// =============================================================================
// File: src/hooks/useSupergroups.ts
// Description: React Query hooks for Telegram supergroups with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query" + proper cleanup
// =============================================================================

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useCallback } from 'react';
import * as telegramApi from '@/api/telegram';
import * as companyApi from '@/api/company';
import type { TelegramSupergroup } from '@/types/chat';
import { logger } from '@/utils/logger';
import { useSupergroupsStore } from '@/stores/useSupergroupsStore';

// Query keys - centralized for consistency
export const supergroupKeys = {
  all: ['supergroups'] as const,
  active: ['supergroups', 'active'] as const,
  archived: ['supergroups', 'archived'] as const,
  chatCounts: ['supergroups', 'chat-counts'] as const,
  balances: ['supergroups', 'balances'] as const,
};

/**
 * Hook for fetching active supergroups with WSE real-time updates
 *
 * TkDodo Pattern: Optimistic updates via setQueryData + invalidation for sync
 * + Zustand cache for instant page refresh (no "Loading..." on refresh)
 * https://tkdodo.eu/blog/using-web-sockets-with-react-query
 */
export function useActiveSupergroups() {
  const queryClient = useQueryClient();

  // Zustand cache for instant page refresh
  const cachedActiveSupergroups = useSupergroupsStore((s) => s.cachedActiveSupergroups);
  const cachedUpdatedAt = useSupergroupsStore((s) => s.cachedUpdatedAt);
  const setCachedActiveSupergroups = useSupergroupsStore((s) => s.setCachedActiveSupergroups);

  // Track pending timeouts for cleanup
  const pendingTimeoutsRef = useRef<Set<NodeJS.Timeout>>(new Set());

  // Helper to sync Zustand after cache updates
  const syncZustandCache = useCallback(() => {
    const currentData = queryClient.getQueryData<TelegramSupergroup[]>(supergroupKeys.active);
    if (currentData) {
      setCachedActiveSupergroups(currentData);
    }
  }, [queryClient, setCachedActiveSupergroups]);

  useEffect(() => {
    // Optimistic delete - immediately remove from cache
    const handleDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company deleted, removing from cache', { companyId });

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      syncZustandCache();
    };

    // Optimistic archive - remove from active list
    const handleArchived = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company archived, removing from active', { companyId });

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      syncZustandCache();
    };

    // OPTIMISTIC CREATE: Immediately add new company to cache
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Company created, adding to cache optimistically', {
        companyId: data.company_id || data.id,
        name: data.name || data.company_name,
      });

      // Create optimistic supergroup entry from event data
      // _isOptimistic: true marks this as not yet confirmed by API
      const newSupergroup: TelegramSupergroup = {
        id: 0,  // Placeholder until Telegram group created
        telegram_group_id: data.telegram_group_id || 0,
        title: data.name || data.company_name || 'New Company',
        username: null,
        description: data.description || null,
        invite_link: data.telegram_invite_link || null,
        is_forum: true,
        created_at: data.created_at || new Date().toISOString(),
        company_id: data.company_id || data.id,
        company_logo: data.logo_url || null,
        group_type: data.company_type || 'company',
        member_count: 1,
        is_active: true,
        bot_is_admin: false,
        _isOptimistic: true,  // CRITICAL: Mark as optimistic entry
      };

      // Add to active cache immediately
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return [newSupergroup];
          // Avoid duplicates (idempotent)
          const exists = oldData.some((g) => g.company_id === newSupergroup.company_id);
          if (exists) return oldData;
          return [newSupergroup, ...oldData];
        }
      );
      syncZustandCache();
    };

    // OPTIMISTIC TELEGRAM LINKED: Update with real telegram data
    const handleTelegramCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Telegram supergroup created, updating cache', {
        companyId: data.company_id,
        telegramGroupId: data.telegram_group_id,
      });

      const companyId = data.company_id;
      const telegramGroupId = data.telegram_group_id;

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((group) =>
            group.company_id === companyId
              ? {
                  ...group,
                  telegram_group_id: telegramGroupId,
                  invite_link: data.invite_link || group.invite_link,
                  bot_is_admin: true,
                }
              : group
          );
        }
      );
      syncZustandCache();
    };

    // For restore/update - delay refetch to allow projection (with cleanup)
    const handleNeedsRefetchDelayed = () => {
      logger.debug('WSE: Supergroup needs refetch (delayed 300ms)');
      const timeout = setTimeout(() => {
        pendingTimeoutsRef.current.delete(timeout);
        queryClient.invalidateQueries({ queryKey: supergroupKeys.active });
      }, 300);
      pendingTimeoutsRef.current.add(timeout);
    };

    // Handle telegram supergroup deletion (from saga)
    const handleTelegramDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id;
      logger.debug('WSE: Telegram supergroup deleted, removing from cache', { companyId });

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      syncZustandCache();
    };

    // Handle group deletion saga completion - final cleanup
    const handleGroupDeletionCompleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id;
      logger.debug('WSE: Group deletion saga completed, ensuring cleanup', { companyId });

      // Final cleanup - remove from all caches
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );

      // Also remove from balances cache
      queryClient.setQueryData(
        supergroupKeys.balances,
        (oldData: Record<string, unknown> | undefined) => {
          if (!oldData) return oldData;
          const newData = { ...oldData };
          delete newData[companyId];
          return newData;
        }
      );

      syncZustandCache();
    };

    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyArchived', handleArchived as EventListener);
    window.addEventListener('companyCreated', handleCreated as EventListener);
    window.addEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
    window.addEventListener('companyTelegramDeleted', handleTelegramDeleted as EventListener);
    window.addEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);
    window.addEventListener('companyRestored', handleNeedsRefetchDelayed);
    window.addEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyArchived', handleArchived as EventListener);
      window.removeEventListener('companyCreated', handleCreated as EventListener);
      window.removeEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
      window.removeEventListener('companyTelegramDeleted', handleTelegramDeleted as EventListener);
      window.removeEventListener('groupDeletionCompleted', handleGroupDeletionCompleted as EventListener);
      window.removeEventListener('companyRestored', handleNeedsRefetchDelayed);
      window.removeEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

      // Cleanup pending timeouts on unmount
      pendingTimeoutsRef.current.forEach(clearTimeout);
      pendingTimeoutsRef.current.clear();
    };
  }, [queryClient, syncZustandCache]);

  return useQuery({
    queryKey: supergroupKeys.active,
    queryFn: async () => {
      const apiData = await telegramApi.getAllSupergroups(true);

      // CRITICAL: Preserve optimistic entries that were added via WSE events
      // These have _isOptimistic: true - not yet confirmed by API/projection
      const existingData = queryClient.getQueryData<TelegramSupergroup[]>(supergroupKeys.active);
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter(e => e._isOptimistic === true);
        if (optimisticEntries.length > 0) {
          logger.info('Preserving optimistic entries during fetch', {
            optimisticCount: optimisticEntries.length,
            apiCount: apiData.length,
            optimisticIds: optimisticEntries.map(e => e.company_id),
          });
          // Merge: Keep optimistic entries that aren't in API yet
          const apiCompanyIds = new Set(apiData.map(a => a.company_id));
          const uniqueOptimistic = optimisticEntries.filter(o => !apiCompanyIds.has(o.company_id));

          // API entries don't have _isOptimistic (or it's false)
          const result = [...uniqueOptimistic, ...apiData];
          // Persist to Zustand for instant load on refresh
          setCachedActiveSupergroups(result);
          return result;
        }
      }

      // Persist to Zustand for instant load on refresh
      setCachedActiveSupergroups(apiData);
      return apiData;
    },
    staleTime: Infinity, // WSE handles updates

    // Use cached data as initial data (instant render on page refresh!)
    // IMPORTANT: Only use non-empty cache, otherwise React Query won't fetch
    initialData: cachedActiveSupergroups?.length ? cachedActiveSupergroups : undefined,
    initialDataUpdatedAt: cachedActiveSupergroups?.length ? (cachedUpdatedAt ?? 0) : undefined,
  });
}

/**
 * Hook for fetching archived supergroups
 * + Zustand cache for instant page refresh (no "Loading..." on refresh)
 */
export function useArchivedSupergroups() {
  const queryClient = useQueryClient();

  // Zustand cache for instant page refresh
  const cachedArchivedSupergroups = useSupergroupsStore((s) => s.cachedArchivedSupergroups);
  const cachedUpdatedAt = useSupergroupsStore((s) => s.cachedUpdatedAt);
  const setCachedArchivedSupergroups = useSupergroupsStore((s) => s.setCachedArchivedSupergroups);

  useEffect(() => {
    // Optimistic delete - immediately remove from cache
    const handleDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company deleted, removing from archived cache', { companyId });

      queryClient.setQueryData(
        supergroupKeys.archived,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
    };

    // Optimistic restore - remove from archived list
    const handleRestored = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company restored, removing from archived', { companyId });

      queryClient.setQueryData(
        supergroupKeys.archived,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
    };

    // For archive - delay refetch to allow projection (eventual consistency)
    const handleNeedsRefetchDelayed = () => {
      logger.debug('WSE: Archived supergroups need refetch (delayed 500ms)');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: supergroupKeys.archived });
      }, 500);
    };

    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyRestored', handleRestored as EventListener);
    window.addEventListener('companyArchived', handleNeedsRefetchDelayed);
    window.addEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyRestored', handleRestored as EventListener);
      window.removeEventListener('companyArchived', handleNeedsRefetchDelayed);
      window.removeEventListener('supergroupUpdated', handleNeedsRefetchDelayed);
    };
  }, [queryClient]);

  return useQuery({
    queryKey: supergroupKeys.archived,
    queryFn: async () => {
      const apiData = await telegramApi.getAllSupergroups(false);
      // Persist to Zustand for instant load on refresh
      setCachedArchivedSupergroups(apiData);
      return apiData;
    },
    staleTime: Infinity,

    // Use cached data as initial data (instant render on page refresh!)
    // IMPORTANT: Only use non-empty cache, otherwise React Query won't fetch
    initialData: cachedArchivedSupergroups?.length ? cachedArchivedSupergroups : undefined,
    initialDataUpdatedAt: cachedArchivedSupergroups?.length ? (cachedUpdatedAt ?? 0) : undefined,
  });
}

/**
 * Hook for fetching supergroup chat counts
 */
export function useSupergroupChatCounts() {
  return useQuery({
    queryKey: supergroupKeys.chatCounts,
    queryFn: telegramApi.getSupergroupChatCounts,
    staleTime: 30000, // 30 seconds - chat counts change more frequently
  });
}

/**
 * Combined hook for all supergroups data (active + archived + counts + balances)
 * Single hook to replace multiple useState + useEffect patterns
 *
 * TkDodo Pattern: Optimistic updates via setQueryData for delete/archive/restore
 * + Zustand cache for instant page refresh (no "Loading..." on refresh)
 */
export function useSupergroups() {
  const queryClient = useQueryClient();

  // Zustand cache for instant page refresh
  const cachedActiveSupergroups = useSupergroupsStore((s) => s.cachedActiveSupergroups);
  const cachedArchivedSupergroups = useSupergroupsStore((s) => s.cachedArchivedSupergroups);
  const cachedUpdatedAt = useSupergroupsStore((s) => s.cachedUpdatedAt);
  const setCachedActiveSupergroups = useSupergroupsStore((s) => s.setCachedActiveSupergroups);
  const setCachedArchivedSupergroups = useSupergroupsStore((s) => s.setCachedArchivedSupergroups);

  // Track pending timeouts for cleanup
  const pendingTimeoutsRef = useRef<Set<NodeJS.Timeout>>(new Set());

  // Helper to sync Zustand after cache updates
  const syncZustandCaches = useCallback(() => {
    const activeData = queryClient.getQueryData<TelegramSupergroup[]>(supergroupKeys.active);
    const archivedData = queryClient.getQueryData<TelegramSupergroup[]>(supergroupKeys.archived);
    if (activeData) setCachedActiveSupergroups(activeData);
    if (archivedData) setCachedArchivedSupergroups(archivedData);
  }, [queryClient, setCachedActiveSupergroups, setCachedArchivedSupergroups]);

  // Listen for WSE events with optimistic updates
  useEffect(() => {
    // Optimistic delete - immediately remove from both caches
    const handleDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.info('WSE: Company deleted, removing from all caches', { companyId });

      // Remove from active
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      // Remove from archived
      queryClient.setQueryData(
        supergroupKeys.archived,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      // Remove from balances
      queryClient.setQueryData(
        supergroupKeys.balances,
        (oldData: Record<string, number> | undefined) => {
          if (!oldData) return oldData;
          const { [companyId]: _, ...rest } = oldData;
          return rest;
        }
      );
      syncZustandCaches();
    };

    // Optimistic archive - move from active to archived (remove from active, invalidate archived)
    const handleArchived = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.info('WSE: Company archived', { companyId });

      // Remove from active immediately
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      syncZustandCaches();
      // Invalidate archived to refetch with new item (with delay for projection)
      const timeout = setTimeout(() => {
        pendingTimeoutsRef.current.delete(timeout);
        queryClient.invalidateQueries({ queryKey: supergroupKeys.archived });
      }, 300);
      pendingTimeoutsRef.current.add(timeout);
    };

    // Optimistic restore - move from archived to active (remove from archived, invalidate active)
    const handleRestored = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.info('WSE: Company restored', { companyId });

      // Remove from archived immediately
      queryClient.setQueryData(
        supergroupKeys.archived,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.filter((group) => group.company_id !== companyId);
        }
      );
      syncZustandCaches();
      // Invalidate active to refetch with restored item (with delay for projection)
      const timeout = setTimeout(() => {
        pendingTimeoutsRef.current.delete(timeout);
        queryClient.invalidateQueries({ queryKey: supergroupKeys.active });
      }, 300);
      pendingTimeoutsRef.current.add(timeout);
    };

    // Optimistic update - immediately update name/data in cache
    const handleUpdated = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.info('WSE: Company updated, updating cache', { companyId });

      // Update in active cache
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((group) =>
            group.company_id === companyId
              ? { ...group, name: data.name ?? group.name, title: data.name ?? group.title }
              : group
          );
        }
      );
      // Update in archived cache
      queryClient.setQueryData(
        supergroupKeys.archived,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((group) =>
            group.company_id === companyId
              ? { ...group, name: data.name ?? group.name, title: data.name ?? group.title }
              : group
          );
        }
      );
      syncZustandCaches();
    };

    // OPTIMISTIC CREATE: Immediately add new company to cache
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Company created, adding to active cache optimistically', {
        companyId: data.company_id || data.id,
        name: data.name || data.company_name,
      });

      // _isOptimistic: true marks this as not yet confirmed by API
      const newSupergroup: TelegramSupergroup = {
        id: 0,  // Placeholder until Telegram group created
        telegram_group_id: data.telegram_group_id || 0,
        title: data.name || data.company_name || 'New Company',
        username: null,
        description: data.description || null,
        invite_link: data.telegram_invite_link || null,
        is_forum: true,
        created_at: data.created_at || new Date().toISOString(),
        company_id: data.company_id || data.id,
        company_logo: data.logo_url || null,
        group_type: data.company_type || 'company',
        member_count: 1,
        is_active: true,
        bot_is_admin: false,
        _isOptimistic: true,  // CRITICAL: Mark as optimistic entry
      };

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return [newSupergroup];
          // Avoid duplicates (idempotent)
          const exists = oldData.some((g) => g.company_id === newSupergroup.company_id);
          if (exists) return oldData;
          return [newSupergroup, ...oldData];
        }
      );
      syncZustandCaches();
    };

    // OPTIMISTIC TELEGRAM LINKED: Update with real telegram data
    const handleTelegramCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Telegram supergroup created, updating active cache', {
        companyId: data.company_id,
        telegramGroupId: data.telegram_group_id,
      });

      const companyId = data.company_id;
      const telegramGroupId = data.telegram_group_id;

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return oldData;
          return oldData.map((group) =>
            group.company_id === companyId
              ? {
                  ...group,
                  telegram_group_id: telegramGroupId,
                  invite_link: data.invite_link || group.invite_link,
                  bot_is_admin: true,
                }
              : group
          );
        }
      );
      syncZustandCaches();
    };

    // For restore/update - delay refetch (with cleanup)
    const handleNeedsRefetchDelayed = () => {
      logger.debug('WSE: Supergroups need refetch (delayed 300ms)');
      const timeout = setTimeout(() => {
        pendingTimeoutsRef.current.delete(timeout);
        queryClient.invalidateQueries({ queryKey: supergroupKeys.all });
      }, 300);
      pendingTimeoutsRef.current.add(timeout);
    };

    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyArchived', handleArchived as EventListener);
    window.addEventListener('companyRestored', handleRestored as EventListener);
    window.addEventListener('companyUpdated', handleUpdated as EventListener);
    window.addEventListener('companyCreated', handleCreated as EventListener);
    window.addEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
    window.addEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyArchived', handleArchived as EventListener);
      window.removeEventListener('companyRestored', handleRestored as EventListener);
      window.removeEventListener('companyUpdated', handleUpdated as EventListener);
      window.removeEventListener('companyCreated', handleCreated as EventListener);
      window.removeEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
      window.removeEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

      // Cleanup pending timeouts on unmount
      pendingTimeoutsRef.current.forEach(clearTimeout);
      pendingTimeoutsRef.current.clear();
    };
  }, [queryClient, syncZustandCaches]);

  // Fetch active supergroups
  const activeQuery = useQuery({
    queryKey: supergroupKeys.active,
    queryFn: async () => {
      const apiData = await telegramApi.getAllSupergroups(true);

      // CRITICAL: Preserve optimistic entries that were added via WSE events
      // These have _isOptimistic: true - not yet confirmed by API/projection
      const existingData = queryClient.getQueryData<TelegramSupergroup[]>(supergroupKeys.active);
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter(e => e._isOptimistic === true);
        if (optimisticEntries.length > 0) {
          logger.info('useSupergroups: Preserving optimistic entries', {
            optimisticCount: optimisticEntries.length,
            apiCount: apiData.length,
            optimisticIds: optimisticEntries.map(e => e.company_id),
          });
          // Keep optimistic entries that aren't in API yet
          const apiCompanyIds = new Set(apiData.map(a => a.company_id));
          const uniqueOptimistic = optimisticEntries.filter(o => !apiCompanyIds.has(o.company_id));
          const result = [...uniqueOptimistic, ...apiData];
          // Persist to Zustand for instant load on refresh
          setCachedActiveSupergroups(result);
          return result;
        }
      }

      // Persist to Zustand for instant load on refresh
      setCachedActiveSupergroups(apiData);
      return apiData;
    },
    staleTime: Infinity,

    // Use cached data as initial data (instant render on page refresh!)
    // IMPORTANT: Only use non-empty cache, otherwise React Query won't fetch
    initialData: cachedActiveSupergroups?.length ? cachedActiveSupergroups : undefined,
    initialDataUpdatedAt: cachedActiveSupergroups?.length ? (cachedUpdatedAt ?? 0) : undefined,
  });

  // Fetch archived supergroups
  const archivedQuery = useQuery({
    queryKey: supergroupKeys.archived,
    queryFn: async () => {
      const apiData = await telegramApi.getAllSupergroups(false);
      // Persist to Zustand for instant load on refresh
      setCachedArchivedSupergroups(apiData);
      return apiData;
    },
    staleTime: Infinity,

    // Use cached data as initial data (instant render on page refresh!)
    // IMPORTANT: Only use non-empty cache, otherwise React Query won't fetch
    initialData: cachedArchivedSupergroups?.length ? cachedArchivedSupergroups : undefined,
    initialDataUpdatedAt: cachedArchivedSupergroups?.length ? (cachedUpdatedAt ?? 0) : undefined,
  });

  // Fetch chat counts
  const chatCountsQuery = useQuery({
    queryKey: supergroupKeys.chatCounts,
    queryFn: telegramApi.getSupergroupChatCounts,
    staleTime: 30000,
  });

  // Fetch company balances for all supergroups
  const balancesQuery = useQuery({
    queryKey: supergroupKeys.balances,
    queryFn: async () => {
      const allSupergroups = [
        ...(activeQuery.data || []),
        ...(archivedQuery.data || []),
      ];

      const companyIds = allSupergroups
        .filter((group): group is TelegramSupergroup & { company_id: string } => !!group.company_id)
        .map(group => group.company_id);

      if (companyIds.length === 0) return {};

      const balances: Record<string, number> = {};
      await Promise.all(
        companyIds.map(async (companyId) => {
          try {
            const balance = await companyApi.getCompanyBalance(companyId);
            if (balance) {
              balances[companyId] = parseFloat(balance.balance) || 0;
            }
          } catch (err) {
            logger.warn('Failed to load company balance', { companyId });
            balances[companyId] = 0;
          }
        })
      );
      return balances;
    },
    enabled: !activeQuery.isLoading && !archivedQuery.isLoading,
    staleTime: 60000, // 1 minute
  });

  return {
    activeSupergroups: activeQuery.data || [],
    archivedSupergroups: archivedQuery.data || [],
    chatCounts: chatCountsQuery.data || {},
    companyBalances: balancesQuery.data || {},
    isLoading: activeQuery.isLoading || archivedQuery.isLoading,
    isError: activeQuery.isError || archivedQuery.isError,
    error: activeQuery.error || archivedQuery.error,
    refetch: () => {
      activeQuery.refetch();
      archivedQuery.refetch();
      chatCountsQuery.refetch();
      balancesQuery.refetch();
    },
  };
}

/**
 * Hook to manually trigger supergroup invalidation
 */
export function useInvalidateSupergroups() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: supergroupKeys.all });
  };
}
