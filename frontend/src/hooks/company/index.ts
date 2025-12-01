// =============================================================================
// File: src/hooks/company/index.ts
// Description: Company hooks with React Query + WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as companyApi from '@/api/company';
import type { CompanyDetail, CompanySummary, UserCompanyInfo } from '@/api/company';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const companyKeys = {
  all: ['companies'] as const,
  lists: () => [...companyKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...companyKeys.lists(), filters] as const,
  details: () => [...companyKeys.all, 'detail'] as const,
  detail: (id: string) => [...companyKeys.details(), id] as const,
  myCompanies: () => [...companyKeys.all, 'my'] as const,
  users: (companyId: string) => [...companyKeys.detail(companyId), 'users'] as const,
  balance: (companyId: string) => [...companyKeys.detail(companyId), 'balance'] as const,
};

// -----------------------------------------------------------------------------
// useCompany - Single company detail with WSE
// -----------------------------------------------------------------------------

export function useCompany(companyId: string | null) {
  const queryClient = useQueryClient();

  // WSE event handlers
  useEffect(() => {
    if (!companyId) return;

    const handleCompanyUpdate = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail?.companyId === companyId || detail?.company_id === companyId) {
        logger.debug('WSE: Company update, invalidating', { companyId });
        queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
      }
    };

    window.addEventListener('companyUpdated', handleCompanyUpdate as EventListener);
    window.addEventListener('companyArchived', handleCompanyUpdate as EventListener);
    window.addEventListener('companyRestored', handleCompanyUpdate as EventListener);

    return () => {
      window.removeEventListener('companyUpdated', handleCompanyUpdate as EventListener);
      window.removeEventListener('companyArchived', handleCompanyUpdate as EventListener);
      window.removeEventListener('companyRestored', handleCompanyUpdate as EventListener);
    };
  }, [companyId, queryClient]);

  const query = useQuery({
    queryKey: companyId ? companyKeys.detail(companyId) : ['disabled'],
    queryFn: () => companyApi.getCompanyById(companyId!),
    enabled: !!companyId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    company: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useMyCompanies - Current user's companies with WSE
// PATTERN: Optimistic updates via setQueryData, NOT invalidateQueries
// -----------------------------------------------------------------------------

export function useMyCompanies(options?: { includeArchived?: boolean }) {
  const queryClient = useQueryClient();
  const includeArchived = options?.includeArchived ?? false;

  // WSE event handlers with optimistic updates
  useEffect(() => {
    const queryKey = [...companyKeys.myCompanies(), { includeArchived }];

    // OPTIMISTIC CREATE: Add new company to cache immediately
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.info('WSE: Company created, adding optimistically to my companies', { data });

      const newCompany: CompanySummary = {
        id: data.company_id || data.id,
        name: data.name || 'New Company',
        company_type: data.company_type || 'company',
        is_active: true,
        user_count: 1,
        created_at: data.created_at || new Date().toISOString(),
        logo_url: data.logo_url || null,
        _isOptimistic: true, // Mark as optimistic
      };

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return [newCompany];
        // Avoid duplicates
        const exists = oldData.some((c) => c.id === newCompany.id);
        if (exists) return oldData;
        return [newCompany, ...oldData];
      });
    };

    // OPTIMISTIC UPDATE: Update company in cache
    const handleUpdated = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company updated, updating in my companies', { companyId });

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.map((c) =>
          c.id === companyId ? { ...c, name: data.name ?? c.name } : c
        );
      });
    };

    // OPTIMISTIC DELETE: Remove from cache
    const handleDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company deleted, removing from my companies', { companyId });

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((c) => c.id !== companyId);
      });
    };

    // OPTIMISTIC ARCHIVE: Remove from active list (if not includeArchived)
    const handleArchived = (event: CustomEvent) => {
      if (includeArchived) return; // Keep archived companies if includeArchived
      const data = event.detail;
      const companyId = data.company_id || data.id;
      logger.debug('WSE: Company archived, removing from my companies', { companyId });

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((c) => c.id !== companyId);
      });
    };

    // For restore/user changes - delay invalidate to allow projection
    const handleNeedsRefetchDelayed = () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: companyKeys.myCompanies() });
      }, 300);
    };

    window.addEventListener('companyCreated', handleCreated as EventListener);
    window.addEventListener('companyUpdated', handleUpdated as EventListener);
    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyArchived', handleArchived as EventListener);
    window.addEventListener('companyRestored', handleNeedsRefetchDelayed);
    window.addEventListener('companyUserAdded', handleNeedsRefetchDelayed);
    window.addEventListener('companyUserRemoved', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyCreated', handleCreated as EventListener);
      window.removeEventListener('companyUpdated', handleUpdated as EventListener);
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyArchived', handleArchived as EventListener);
      window.removeEventListener('companyRestored', handleNeedsRefetchDelayed);
      window.removeEventListener('companyUserAdded', handleNeedsRefetchDelayed);
      window.removeEventListener('companyUserRemoved', handleNeedsRefetchDelayed);
    };
  }, [queryClient, includeArchived]);

  const query = useQuery({
    queryKey: [...companyKeys.myCompanies(), { includeArchived }],
    queryFn: async () => {
      const apiData = await companyApi.getMyCompanies(includeArchived);

      // CRITICAL: Preserve optimistic entries during refetch
      const existingData = queryClient.getQueryData<CompanySummary[]>(
        [...companyKeys.myCompanies(), { includeArchived }]
      );
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter((c: any) => c._isOptimistic);
        if (optimisticEntries.length > 0) {
          logger.info('useMyCompanies: Preserving optimistic entries', {
            optimisticCount: optimisticEntries.length,
            apiCount: apiData.length,
          });
          const apiIds = new Set(apiData.map((a) => a.id));
          const uniqueOptimistic = optimisticEntries.filter((o) => !apiIds.has(o.id));
          return [...uniqueOptimistic, ...apiData];
        }
      }
      return apiData;
    },
    staleTime: Infinity, // WSE handles updates
  });

  return {
    companies: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useCompanies - All companies list with WSE
// PATTERN: Optimistic updates via setQueryData (TkDodo best practice)
// -----------------------------------------------------------------------------

export function useCompanies(options?: { includeArchived?: boolean; limit?: number }) {
  const queryClient = useQueryClient();
  const includeArchived = options?.includeArchived ?? false;
  const limit = options?.limit ?? 50;

  useEffect(() => {
    const queryKey = companyKeys.list({ includeArchived, limit });

    // OPTIMISTIC CREATE
    const handleCreated = (event: CustomEvent) => {
      const data = event.detail;
      logger.debug('WSE: Company created, adding to companies list', { data });

      const newCompany: CompanySummary = {
        id: data.company_id || data.id,
        name: data.name || 'New Company',
        company_type: data.company_type || 'company',
        is_active: true,
        user_count: 1,
        created_at: data.created_at || new Date().toISOString(),
        logo_url: data.logo_url || null,
        _isOptimistic: true,
      };

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return [newCompany];
        const exists = oldData.some((c) => c.id === newCompany.id);
        if (exists) return oldData;
        return [newCompany, ...oldData];
      });
    };

    // OPTIMISTIC UPDATE
    const handleUpdated = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.map((c) =>
          c.id === companyId ? { ...c, name: data.name ?? c.name } : c
        );
      });
    };

    // OPTIMISTIC DELETE
    const handleDeleted = (event: CustomEvent) => {
      const data = event.detail;
      const companyId = data.company_id || data.id;

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((c) => c.id !== companyId);
      });
    };

    // OPTIMISTIC ARCHIVE
    const handleArchived = (event: CustomEvent) => {
      if (includeArchived) return;
      const data = event.detail;
      const companyId = data.company_id || data.id;

      queryClient.setQueryData(queryKey, (oldData: CompanySummary[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((c) => c.id !== companyId);
      });
    };

    // For restore - delay to allow projection
    const handleNeedsRefetchDelayed = () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
      }, 300);
    };

    window.addEventListener('companyCreated', handleCreated as EventListener);
    window.addEventListener('companyUpdated', handleUpdated as EventListener);
    window.addEventListener('companyDeleted', handleDeleted as EventListener);
    window.addEventListener('companyArchived', handleArchived as EventListener);
    window.addEventListener('companyRestored', handleNeedsRefetchDelayed);

    return () => {
      window.removeEventListener('companyCreated', handleCreated as EventListener);
      window.removeEventListener('companyUpdated', handleUpdated as EventListener);
      window.removeEventListener('companyDeleted', handleDeleted as EventListener);
      window.removeEventListener('companyArchived', handleArchived as EventListener);
      window.removeEventListener('companyRestored', handleNeedsRefetchDelayed);
    };
  }, [queryClient, includeArchived, limit]);

  const query = useQuery({
    queryKey: companyKeys.list({ includeArchived, limit }),
    queryFn: async () => {
      const apiData = await companyApi.getCompanies(includeArchived, limit);

      // Preserve optimistic entries during refetch
      const existingData = queryClient.getQueryData<CompanySummary[]>(
        companyKeys.list({ includeArchived, limit })
      );
      if (existingData && Array.isArray(existingData)) {
        const optimisticEntries = existingData.filter((c: any) => c._isOptimistic);
        if (optimisticEntries.length > 0) {
          const apiIds = new Set(apiData.map((a) => a.id));
          const uniqueOptimistic = optimisticEntries.filter((o) => !apiIds.has(o.id));
          return [...uniqueOptimistic, ...apiData];
        }
      }
      return apiData;
    },
    staleTime: Infinity, // WSE handles updates
  });

  return {
    companies: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useCompanyUsers - Company users list
// -----------------------------------------------------------------------------

export function useCompanyUsers(companyId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!companyId) return;

    const handleUserChange = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail?.companyId === companyId || detail?.company_id === companyId) {
        queryClient.invalidateQueries({ queryKey: companyKeys.users(companyId) });
      }
    };

    window.addEventListener('companyUserAdded', handleUserChange as EventListener);
    window.addEventListener('companyUserRemoved', handleUserChange as EventListener);
    window.addEventListener('companyUserRoleChanged', handleUserChange as EventListener);

    return () => {
      window.removeEventListener('companyUserAdded', handleUserChange as EventListener);
      window.removeEventListener('companyUserRemoved', handleUserChange as EventListener);
      window.removeEventListener('companyUserRoleChanged', handleUserChange as EventListener);
    };
  }, [companyId, queryClient]);

  const query = useQuery({
    queryKey: companyId ? companyKeys.users(companyId) : ['disabled'],
    queryFn: () => companyApi.getCompanyUsers(companyId!),
    enabled: !!companyId,
    staleTime: 5 * 60 * 1000,
  });

  return {
    users: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// useCompanyBalance - Company balance
// -----------------------------------------------------------------------------

export function useCompanyBalance(companyId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!companyId) return;

    const handleBalanceChange = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail?.companyId === companyId || detail?.company_id === companyId) {
        queryClient.invalidateQueries({ queryKey: companyKeys.balance(companyId) });
      }
    };

    window.addEventListener('companyBalanceUpdated', handleBalanceChange as EventListener);

    return () => {
      window.removeEventListener('companyBalanceUpdated', handleBalanceChange as EventListener);
    };
  }, [companyId, queryClient]);

  const query = useQuery({
    queryKey: companyId ? companyKeys.balance(companyId) : ['disabled'],
    queryFn: () => companyApi.getCompanyBalance(companyId!),
    enabled: !!companyId,
    staleTime: 60 * 1000, // 1 minute
  });

  return {
    balance: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// Mutations
// PATTERN: TkDodo - Don't invalidate on success, WSE handles cache updates
// https://tkdodo.eu/blog/using-web-sockets-with-react-query
// -----------------------------------------------------------------------------

export function useCreateCompany() {
  // NOTE: Do NOT invalidate queries on success!
  // WSE sends company_created event which triggers:
  // 1. EventHandlers.handleCompanyCreated -> dispatches 'companyCreated' CustomEvent
  // 2. useMyCompanies/useCompanies listen to event and add company via setQueryData
  // 3. useSupergroups also listens and adds to supergroups cache
  // Invalidating would cause a refetch that returns stale data (projection not yet complete)

  return useMutation({
    mutationFn: companyApi.createCompany,
    // onSuccess intentionally empty - WSE handles cache updates
  });
}

export function useUpdateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, data }: { companyId: string; data: companyApi.UpdateCompanyRequest }) =>
      companyApi.updateCompany(companyId, data),
    onSuccess: (_, { companyId }) => {
      // Only invalidate detail cache - lists are updated via WSE events
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
    },
  });
}

export function useArchiveCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, reason }: { companyId: string; reason?: string }) =>
      companyApi.archiveCompany(companyId, reason),
    onSuccess: (_, { companyId }) => {
      // Only invalidate detail cache - lists are updated via WSE events
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
    },
  });
}

export function useDeleteCompany() {
  return useMutation({
    mutationFn: (companyId: string) => companyApi.deleteCompany(companyId),
    // WSE sends company_deleted event which updates caches optimistically
  });
}

export function useRestoreCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (companyId: string) => companyApi.restoreCompany(companyId),
    onSuccess: (_, companyId) => {
      // Only invalidate detail cache - lists are updated via WSE events
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
    },
  });
}

// Re-export types
export type { CompanyDetail, CompanySummary, UserCompanyInfo };
