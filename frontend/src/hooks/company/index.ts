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
// -----------------------------------------------------------------------------

export function useMyCompanies(options?: { includeArchived?: boolean }) {
  const queryClient = useQueryClient();
  const includeArchived = options?.includeArchived ?? false;

  // WSE event handlers
  useEffect(() => {
    const handleCompanyChange = () => {
      logger.debug('WSE: Company change, invalidating my companies');
      queryClient.invalidateQueries({ queryKey: companyKeys.myCompanies() });
    };

    window.addEventListener('companyCreated', handleCompanyChange);
    window.addEventListener('companyUpdated', handleCompanyChange);
    window.addEventListener('companyArchived', handleCompanyChange);
    window.addEventListener('companyRestored', handleCompanyChange);
    window.addEventListener('companyUserAdded', handleCompanyChange);
    window.addEventListener('companyUserRemoved', handleCompanyChange);

    return () => {
      window.removeEventListener('companyCreated', handleCompanyChange);
      window.removeEventListener('companyUpdated', handleCompanyChange);
      window.removeEventListener('companyArchived', handleCompanyChange);
      window.removeEventListener('companyRestored', handleCompanyChange);
      window.removeEventListener('companyUserAdded', handleCompanyChange);
      window.removeEventListener('companyUserRemoved', handleCompanyChange);
    };
  }, [queryClient]);

  const query = useQuery({
    queryKey: [...companyKeys.myCompanies(), { includeArchived }],
    queryFn: () => companyApi.getMyCompanies(includeArchived),
    staleTime: 5 * 60 * 1000,
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
// -----------------------------------------------------------------------------

export function useCompanies(options?: { includeArchived?: boolean; limit?: number }) {
  const queryClient = useQueryClient();
  const includeArchived = options?.includeArchived ?? false;
  const limit = options?.limit ?? 50;

  useEffect(() => {
    const handleCompanyChange = () => {
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
    };

    window.addEventListener('companyCreated', handleCompanyChange);
    window.addEventListener('companyUpdated', handleCompanyChange);
    window.addEventListener('companyArchived', handleCompanyChange);
    window.addEventListener('companyRestored', handleCompanyChange);

    return () => {
      window.removeEventListener('companyCreated', handleCompanyChange);
      window.removeEventListener('companyUpdated', handleCompanyChange);
      window.removeEventListener('companyArchived', handleCompanyChange);
      window.removeEventListener('companyRestored', handleCompanyChange);
    };
  }, [queryClient]);

  const query = useQuery({
    queryKey: companyKeys.list({ includeArchived, limit }),
    queryFn: () => companyApi.getCompanies(includeArchived, limit),
    staleTime: 5 * 60 * 1000,
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
// -----------------------------------------------------------------------------

export function useCreateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: companyApi.createCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
      queryClient.invalidateQueries({ queryKey: companyKeys.myCompanies() });
    },
  });
}

export function useUpdateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, data }: { companyId: string; data: companyApi.UpdateCompanyRequest }) =>
      companyApi.updateCompany(companyId, data),
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
    },
  });
}

export function useArchiveCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, reason }: { companyId: string; reason?: string }) =>
      companyApi.archiveCompany(companyId, reason),
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(companyId) });
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
      queryClient.invalidateQueries({ queryKey: companyKeys.myCompanies() });
    },
  });
}

// Re-export types
export type { CompanyDetail, CompanySummary, UserCompanyInfo };
