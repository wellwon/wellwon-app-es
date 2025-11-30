// =============================================================================
// File: src/hooks/useSupergroups.ts
// Description: React Query hooks for Telegram supergroups with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import * as telegramApi from '@/api/telegram';
import * as companyApi from '@/api/company';
import type { TelegramSupergroup } from '@/types/chat';
import { logger } from '@/utils/logger';

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
 * https://tkdodo.eu/blog/using-web-sockets-with-react-query
 */
export function useActiveSupergroups() {
  const queryClient = useQueryClient();

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
    };

    // OPTIMISTIC CREATE: Immediately add new company to cache
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Company created, adding to cache optimistically', { data });

      // Create optimistic supergroup entry from event data
      const newSupergroup: TelegramSupergroup = {
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
      };

      // Add to active cache immediately
      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return [newSupergroup];
          // Avoid duplicates
          const exists = oldData.some((g) => g.company_id === newSupergroup.company_id);
          if (exists) return oldData;
          return [newSupergroup, ...oldData];
        }
      );
    };

    // OPTIMISTIC TELEGRAM LINKED: Update with real telegram data
    const handleTelegramCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Telegram supergroup created, updating cache', { data });

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
    };

    // For restore/update - delay refetch to allow projection
    const handleNeedsRefetchDelayed = () => {
      logger.debug('WSE: Supergroup needs refetch (delayed 300ms)');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: supergroupKeys.active });
      }, 300);
    };

    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyArchived', handleArchived as EventListener);
    window.addEventListener('companyCreated', handleCreated as EventListener);
    window.addEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
    window.addEventListener('companyRestored', handleNeedsRefetchDelayed);
    window.addEventListener('supergroupUpdated', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyArchived', handleArchived as EventListener);
      window.removeEventListener('companyCreated', handleCreated as EventListener);
      window.removeEventListener('companyTelegramCreated', handleTelegramCreated as EventListener);
      window.removeEventListener('companyRestored', handleNeedsRefetchDelayed);
      window.removeEventListener('supergroupUpdated', handleNeedsRefetchDelayed);
    };
  }, [queryClient]);

  return useQuery({
    queryKey: supergroupKeys.active,
    queryFn: () => telegramApi.getAllSupergroups(true),
    staleTime: Infinity, // WSE handles updates
  });
}

/**
 * Hook for fetching archived supergroups
 */
export function useArchivedSupergroups() {
  const queryClient = useQueryClient();

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
    queryFn: () => telegramApi.getAllSupergroups(false),
    staleTime: Infinity,
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
 */
export function useSupergroups() {
  const queryClient = useQueryClient();

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
      // Invalidate archived to refetch with new item
      queryClient.invalidateQueries({ queryKey: supergroupKeys.archived });
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
      // Invalidate active to refetch with restored item
      queryClient.invalidateQueries({ queryKey: supergroupKeys.active });
    };

    // Optimistic update - immediately update name/data in cache
    const handleUpdated = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.info('WSE: Company updated, updating cache', { companyId, data });

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
    };

    // OPTIMISTIC CREATE: Immediately add new company to cache
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Company created, adding to active cache optimistically', { data });

      const newSupergroup: TelegramSupergroup = {
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
      };

      queryClient.setQueryData(
        supergroupKeys.active,
        (oldData: TelegramSupergroup[] | undefined) => {
          if (!oldData) return [newSupergroup];
          const exists = oldData.some((g) => g.company_id === newSupergroup.company_id);
          if (exists) return oldData;
          return [newSupergroup, ...oldData];
        }
      );
    };

    // OPTIMISTIC TELEGRAM LINKED: Update with real telegram data
    const handleTelegramCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Telegram supergroup created, updating active cache', { data });

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
    };

    // For restore/update - delay refetch
    const handleNeedsRefetchDelayed = () => {
      logger.debug('WSE: Supergroups need refetch (delayed 300ms)');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: supergroupKeys.all });
      }, 300);
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
    };
  }, [queryClient]);

  // Fetch active supergroups
  const activeQuery = useQuery({
    queryKey: supergroupKeys.active,
    queryFn: () => telegramApi.getAllSupergroups(true),
    staleTime: Infinity,
  });

  // Fetch archived supergroups
  const archivedQuery = useQuery({
    queryKey: supergroupKeys.archived,
    queryFn: () => telegramApi.getAllSupergroups(false),
    staleTime: Infinity,
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
