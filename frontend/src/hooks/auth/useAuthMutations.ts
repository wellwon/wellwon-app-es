// =============================================================================
// File: src/hooks/auth/useAuthMutations.ts
// Description: React Query mutations for auth operations
// Pattern: TkDodo's mutation pattern with side effects
// =============================================================================

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from './useAuthStore';
import { authKeys } from './useProfile';
import * as authApi from '@/api/user_account';
import { API } from '@/api/core';
import { logger } from '@/utils/logger';
import type { SignUpMetadata } from '@/types/auth';

// -----------------------------------------------------------------------------
// useLogin
// -----------------------------------------------------------------------------

interface LoginParams {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export function useLogin() {
  const queryClient = useQueryClient();
  const setTokens = useAuthStore((state) => state.setTokens);

  return useMutation({
    mutationFn: async ({ email, password, rememberMe }: LoginParams) => {
      const response = await authApi.login(email, password, undefined, undefined, rememberMe);

      if (response.requires_mfa) {
        throw new Error('MFA_REQUIRED');
      }

      return response;
    },
    onSuccess: (response) => {
      // Store tokens in Zustand (persisted)
      setTokens({
        token: response.access_token,
        refresh_token: response.refresh_token,
        expires_at: Date.now() + (response.expires_in * 1000),
        token_type: response.token_type || 'Bearer',
        session_id: response.session_id,
      });

      // Invalidate profile to trigger fetch
      queryClient.invalidateQueries({ queryKey: authKeys.profile() });

      // Dispatch event for WSE reconnection
      window.dispatchEvent(new Event('authSuccess'));

      logger.info('Login successful');
    },
    onError: (error: any) => {
      logger.error('Login failed', error);
    },
  });
}

// -----------------------------------------------------------------------------
// useLogout
// -----------------------------------------------------------------------------

export function useLogout() {
  const queryClient = useQueryClient();
  const clearTokens = useAuthStore((state) => state.clearTokens);

  return useMutation({
    mutationFn: async () => {
      try {
        await authApi.logout();
      } catch (error) {
        // Log but don't fail - still need to clear local state
        logger.warn('Backend logout failed, clearing local state anyway');
      }
    },
    onSuccess: () => {
      // Clear tokens (also clears cached profile via Zustand)
      clearTokens();

      // Clear all auth-related queries
      queryClient.removeQueries({ queryKey: authKeys.all });

      // Clear all other queries (user data is now invalid)
      queryClient.clear();

      // Clear persisted messages cache from Zustand
      // This ensures fresh data on next login (no stale messages)
      const messagesStore = (window as any).__MESSAGES_STORE__;
      if (messagesStore?.getState?.()?.clearAllCache) {
        messagesStore.getState().clearAllCache();
        logger.info('Cleared messages cache on logout');
      }

      // Also clear from localStorage directly (fallback)
      try {
        localStorage.removeItem('wellwon-messages');
      } catch (e) {
        // Ignore localStorage errors
      }

      logger.info('Logout successful');
    },
  });
}

// -----------------------------------------------------------------------------
// useRegister
// -----------------------------------------------------------------------------

interface RegisterParams {
  email: string;
  password: string;
  metadata?: SignUpMetadata;
}

export function useRegister() {
  return useMutation({
    mutationFn: async ({ email, password, metadata }: RegisterParams) => {
      await authApi.register(
        email, // username = email
        email,
        password,
        undefined, // secret
        true, // terms_accepted
        false, // marketing_consent
        undefined, // referral_code
        metadata?.first_name,
        metadata?.last_name
      );
    },
    onSuccess: () => {
      logger.info('Registration successful');
    },
    onError: (error: any) => {
      logger.error('Registration failed', error);
    },
  });
}

// -----------------------------------------------------------------------------
// useUpdateProfile
// -----------------------------------------------------------------------------

interface UpdateProfileParams {
  first_name?: string;
  last_name?: string;
  avatar_url?: string;
  bio?: string;
  phone?: string;
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (updates: UpdateProfileParams) => {
      await API.patch('/user/profile', updates);
      return updates;
    },
    onMutate: async (updates) => {
      // Cancel outgoing fetches
      await queryClient.cancelQueries({ queryKey: authKeys.profile() });

      // Snapshot previous value
      const previousProfile = queryClient.getQueryData(authKeys.profile());

      // Optimistically update
      queryClient.setQueryData(authKeys.profile(), (old: any) => ({
        ...old,
        ...updates,
      }));

      return { previousProfile };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousProfile) {
        queryClient.setQueryData(authKeys.profile(), context.previousProfile);
      }
      logger.error('Profile update failed', error);
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: authKeys.profile() });
    },
  });
}

// -----------------------------------------------------------------------------
// useChangePassword
// -----------------------------------------------------------------------------

interface ChangePasswordParams {
  currentPassword: string;
  newPassword: string;
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async ({ currentPassword, newPassword }: ChangePasswordParams) => {
      await API.post('/user/change-password', {
        old_password: currentPassword,
        new_password: newPassword,
      });
    },
    onSuccess: () => {
      logger.info('Password changed successfully');
    },
    onError: (error: any) => {
      logger.error('Password change failed', error);
    },
  });
}

// -----------------------------------------------------------------------------
// useRefreshToken
// -----------------------------------------------------------------------------

export function useRefreshToken() {
  const setTokens = useAuthStore((state) => state.setTokens);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const sessionId = useAuthStore((state) => state.sessionId);

  return useMutation({
    mutationFn: async () => {
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await authApi.refreshToken(refreshToken);
      return response;
    },
    onSuccess: (response) => {
      setTokens({
        token: response.access_token,
        refresh_token: response.refresh_token || refreshToken,
        expires_at: Date.now() + (response.expires_in * 1000),
        token_type: response.token_type || 'Bearer',
        session_id: sessionId,
      });

      logger.debug('Token refreshed successfully');
    },
    onError: (error: any) => {
      logger.error('Token refresh failed', error);
      // Token refresh failed - will trigger logout via 401 interceptor
    },
  });
}
