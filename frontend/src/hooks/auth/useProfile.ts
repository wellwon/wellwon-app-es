// =============================================================================
// File: src/hooks/auth/useProfile.ts
// Description: React Query hook for user profile with WSE integration
// Pattern: TkDodo's "Using WebSockets with React Query"
// =============================================================================

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMe } from '@/api/user_account';
import { useAuthStore } from './useAuthStore';
import { logger } from '@/utils/logger';
import type { Profile } from '@/types/auth';

// -----------------------------------------------------------------------------
// Query Keys
// -----------------------------------------------------------------------------

export const authKeys = {
  all: ['auth'] as const,
  profile: () => [...authKeys.all, 'profile'] as const,
  sessions: () => [...authKeys.all, 'sessions'] as const,
};

// -----------------------------------------------------------------------------
// Profile mapping
// -----------------------------------------------------------------------------

function mapToProfile(data: any): Profile {
  return {
    id: data.user_id,
    user_id: data.user_id,
    username: data.username,
    email: data.email,
    role: data.role,
    first_name: data.first_name || null,
    last_name: data.last_name || null,
    avatar_url: data.avatar_url || null,
    bio: data.bio || null,
    phone: data.phone || null,
    active: data.is_active,
    is_active: data.is_active,
    is_developer: data.is_developer ?? false,
    email_verified: data.email_verified,
    mfa_enabled: data.mfa_enabled,
    created_at: data.created_at,
    updated_at: data.created_at,
    last_login: data.last_login,
    last_password_change: data.last_password_change,
    security_alerts_enabled: data.security_alerts_enabled,
    active_sessions_count: data.active_sessions_count,
    user_type: data.user_type,
    user_number: data.user_number,
  };
}

// -----------------------------------------------------------------------------
// useProfile - React Query hook with WSE integration
// -----------------------------------------------------------------------------

export function useProfile() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isTokenExpired = useAuthStore((state) => state.isTokenExpired);

  // Profile query - only runs when authenticated
  const query = useQuery({
    queryKey: authKeys.profile(),
    queryFn: async () => {
      const data = await fetchMe();
      return mapToProfile(data);
    },
    enabled: isAuthenticated && !isTokenExpired(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
    retry: (failureCount, error: any) => {
      // Don't retry on 401 (will trigger logout)
      if (error?.response?.status === 401) return false;
      return failureCount < 2;
    },
  });

  // WSE event handlers - update React Query cache directly
  useEffect(() => {
    if (!isAuthenticated) return;

    const handleProfileUpdate = (event: CustomEvent) => {
      logger.debug('WSE: Profile update event received', { detail: event.detail });

      // Invalidate profile query to refetch
      queryClient.invalidateQueries({ queryKey: authKeys.profile() });
    };

    const handleAdminChange = (event: CustomEvent) => {
      const detail = event.detail;
      logger.debug('WSE: Admin change event received', { detail });

      // Update profile in cache directly for responsive UI
      queryClient.setQueryData(authKeys.profile(), (oldData: Profile | undefined) => {
        if (!oldData) return oldData;

        // Only update if this event is for the current user
        if (detail?.userId && detail.userId !== oldData.user_id) {
          return oldData;
        }

        return {
          ...oldData,
          is_developer: detail.isDeveloper ?? oldData.is_developer,
          role: detail.role ?? oldData.role,
          is_active: detail.isActive ?? oldData.is_active,
          active: detail.isActive ?? oldData.active,
          email_verified: detail.emailVerified ?? oldData.email_verified,
          user_type: detail.userType ?? oldData.user_type,
        };
      });
    };

    window.addEventListener('userProfileUpdated', handleProfileUpdate as EventListener);
    window.addEventListener('userAdminChange', handleAdminChange as EventListener);

    return () => {
      window.removeEventListener('userProfileUpdated', handleProfileUpdate as EventListener);
      window.removeEventListener('userAdminChange', handleAdminChange as EventListener);
    };
  }, [isAuthenticated, queryClient]);

  return {
    profile: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

// -----------------------------------------------------------------------------
// Helper: Create user object from profile
// -----------------------------------------------------------------------------

export interface User {
  id: string;
  user_id: string;
  username: string;
  email: string;
  role: string;
  user_metadata?: {
    first_name?: string;
    last_name?: string;
    avatar_url?: string;
  };
}

export function profileToUser(profile: Profile | null): User | null {
  if (!profile) return null;

  return {
    id: profile.user_id,
    user_id: profile.user_id,
    username: profile.username,
    email: profile.email,
    role: profile.role,
    user_metadata: {
      first_name: profile.first_name ?? undefined,
      last_name: profile.last_name ?? undefined,
      avatar_url: profile.avatar_url ?? undefined,
    },
  };
}
