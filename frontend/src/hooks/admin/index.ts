// =============================================================================
// File: src/hooks/admin/index.ts
// Description: Admin hooks with React Query + WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi, type AdminUser, type AdminUserUpdate } from '@/api/admin';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const adminKeys = {
  all: ['admin'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  userList: (filters: Record<string, unknown>) => [...adminKeys.users(), filters] as const,
};

// -----------------------------------------------------------------------------
// useAdminUsers - All users for admin management with WSE
// -----------------------------------------------------------------------------

interface UseAdminUsersOptions {
  enabled?: boolean;
  includeInactive?: boolean;
  limit?: number;
}

export function useAdminUsers(options: UseAdminUsersOptions = {}) {
  const queryClient = useQueryClient();
  const { enabled = true, includeInactive = false, limit = 100 } = options;

  // WSE event handlers
  useEffect(() => {
    if (!enabled) return;

    const handleUserChange = () => {
      logger.debug('WSE: User change, invalidating admin users');
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    };

    // Listen for all user-related events
    window.addEventListener('userCreated', handleUserChange);
    window.addEventListener('userProfileUpdated', handleUserChange);
    window.addEventListener('userAdminChange', handleUserChange);
    window.addEventListener('userDeleted', handleUserChange);
    window.addEventListener('userActivated', handleUserChange);
    window.addEventListener('userDeactivated', handleUserChange);

    return () => {
      window.removeEventListener('userCreated', handleUserChange);
      window.removeEventListener('userProfileUpdated', handleUserChange);
      window.removeEventListener('userAdminChange', handleUserChange);
      window.removeEventListener('userDeleted', handleUserChange);
      window.removeEventListener('userActivated', handleUserChange);
      window.removeEventListener('userDeactivated', handleUserChange);
    };
  }, [enabled, queryClient]);

  const query = useQuery({
    queryKey: adminKeys.userList({ includeInactive, limit }),
    queryFn: async () => {
      const { data } = await adminApi.getUsers({ includeInactive, limit });
      return data;
    },
    enabled,
    staleTime: 2 * 60 * 1000, // 2 minutes
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
// useUpdateAdminUser - Update user status mutation
// -----------------------------------------------------------------------------

export function useUpdateAdminUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, data }: { userId: string; data: AdminUserUpdate }) => {
      const response = await adminApi.updateUser(userId, data);
      return response.data;
    },
    onMutate: async ({ userId, data }) => {
      // Cancel outgoing fetches
      await queryClient.cancelQueries({ queryKey: adminKeys.users() });

      // Snapshot previous value
      const previousUsers = queryClient.getQueryData(adminKeys.users());

      // Optimistically update
      queryClient.setQueriesData({ queryKey: adminKeys.users() }, (old: AdminUser[] | undefined) => {
        if (!old) return old;
        return old.map((user) =>
          user.user_id === userId ? { ...user, ...data } : user
        );
      });

      return { previousUsers };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousUsers) {
        queryClient.setQueriesData({ queryKey: adminKeys.users() }, context.previousUsers);
      }
      logger.error('Failed to update admin user', error);
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

// Re-export types
export type { AdminUser, AdminUserUpdate };
