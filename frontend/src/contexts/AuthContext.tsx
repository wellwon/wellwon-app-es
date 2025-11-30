// =============================================================================
// File: src/contexts/AuthContext.tsx
// Description: Auth context using React Query + Zustand (TkDodo pattern)
// =============================================================================

import React, { createContext, useContext, useCallback, useMemo, useEffect, useRef } from 'react';
import { logger } from '@/utils/logger';
import type { Profile, SignUpMetadata, AuthResponse } from '@/types/auth';

// React Query + Zustand hooks
import {
  useAuthStore,
  useProfile,
  useLogin,
  useLogout,
  useRegister,
  useUpdateProfile,
  useChangePassword,
  useRefreshToken,
  profileToUser,
  type User,
} from '@/hooks/auth';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface AuthContextType {
  user: User | null;
  profile: Profile | null;
  loading: boolean;
  token: string | null;
  signUp: (email: string, password: string, metadata?: SignUpMetadata) => Promise<AuthResponse>;
  signIn: (email: string, password: string) => Promise<AuthResponse>;
  signInWithMagicLink: (email: string) => Promise<AuthResponse>;
  signOut: () => Promise<AuthResponse>;
  updateProfile: (updates: Partial<Profile>) => Promise<AuthResponse>;
  updatePassword: (currentPassword: string, newPassword: string) => Promise<AuthResponse>;
  quickLogin: (email: string, password: string) => Promise<AuthResponse>;
}

// -----------------------------------------------------------------------------
// Context
// -----------------------------------------------------------------------------

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// -----------------------------------------------------------------------------
// Provider
// -----------------------------------------------------------------------------

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Zustand: Token state
  const token = useAuthStore((state) => state.token);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const expiresAt = useAuthStore((state) => state.expiresAt);

  // React Query: Profile
  const { profile, isLoading: isLoadingProfile } = useProfile();

  // Mutations
  const loginMutation = useLogin();
  const logoutMutation = useLogout();
  const registerMutation = useRegister();
  const updateProfileMutation = useUpdateProfile();
  const changePasswordMutation = useChangePassword();
  const refreshTokenMutation = useRefreshToken();

  // Token refresh timer
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Schedule token refresh
  useEffect(() => {
    if (!isAuthenticated || !expiresAt || !refreshToken) {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      return;
    }

    const scheduleRefresh = () => {
      const now = Date.now();
      const timeUntilExpiry = expiresAt - now;

      // Refresh 1 minute before expiry
      const refreshTime = expiresAt - 60000;
      const delayMs = refreshTime - now;

      if (delayMs <= 0) {
        // Token already expired or expiring soon - refresh immediately!
        logger.debug('Token expired or expiring soon, refreshing immediately');
        refreshTokenMutation.mutate();
        return;
      }

      logger.debug('Scheduling token refresh', { inSeconds: Math.round(delayMs / 1000) });

      refreshTimerRef.current = setTimeout(() => {
        refreshTokenMutation.mutate();
      }, delayMs);
    };

    scheduleRefresh();

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [isAuthenticated, expiresAt, refreshToken, refreshTokenMutation]);

  // Derive user from profile
  const user = useMemo(() => profileToUser(profile), [profile]);

  // Loading state
  const loading = useMemo(() => {
    // Initial load: checking stored auth
    if (isAuthenticated && !profile && isLoadingProfile) {
      return true;
    }
    return false;
  }, [isAuthenticated, profile, isLoadingProfile]);

  // -----------------------------------------------------------------------------
  // Actions (maintain same interface as before)
  // -----------------------------------------------------------------------------

  const signUp = useCallback(async (
    email: string,
    password: string,
    metadata?: SignUpMetadata
  ): Promise<AuthResponse> => {
    try {
      await registerMutation.mutateAsync({ email, password, metadata });
      return { error: null };
    } catch (error: any) {
      logger.error('Registration error', error);
      return { error: error?.response?.data || error };
    }
  }, [registerMutation]);

  const signIn = useCallback(async (
    email: string,
    password: string
  ): Promise<AuthResponse> => {
    try {
      await loginMutation.mutateAsync({ email, password });
      return { error: null };
    } catch (error: any) {
      logger.error('Login error', error);
      return { error: error?.response?.data || error };
    }
  }, [loginMutation]);

  const signInWithMagicLink = useCallback(async (_email: string): Promise<AuthResponse> => {
    logger.warn('Magic link not implemented yet');
    return { error: new Error('Magic link not implemented') };
  }, []);

  const signOut = useCallback(async (): Promise<AuthResponse> => {
    try {
      await logoutMutation.mutateAsync();
      return { error: null };
    } catch (error: any) {
      logger.error('Logout error', error);
      return { error };
    }
  }, [logoutMutation]);

  const updateProfileAction = useCallback(async (
    updates: Partial<Profile>
  ): Promise<AuthResponse> => {
    try {
      await updateProfileMutation.mutateAsync(updates as any);
      return { error: null };
    } catch (error: any) {
      logger.error('Profile update error', error);
      return { error: error?.response?.data || error };
    }
  }, [updateProfileMutation]);

  const updatePassword = useCallback(async (
    currentPassword: string,
    newPassword: string
  ): Promise<AuthResponse> => {
    try {
      await changePasswordMutation.mutateAsync({ currentPassword, newPassword });
      return { error: null };
    } catch (error: any) {
      logger.error('Password update error', error);
      return { error: error?.response?.data || error };
    }
  }, [changePasswordMutation]);

  const quickLogin = useCallback(async (
    email: string,
    password: string
  ): Promise<AuthResponse> => {
    return signIn(email, password);
  }, [signIn]);

  // -----------------------------------------------------------------------------
  // Context Value
  // -----------------------------------------------------------------------------

  const value: AuthContextType = useMemo(() => ({
    user,
    profile,
    loading,
    token,
    signUp,
    signIn,
    signInWithMagicLink,
    signOut,
    updateProfile: updateProfileAction,
    updatePassword,
    quickLogin,
  }), [
    user,
    profile,
    loading,
    token,
    signUp,
    signIn,
    signInWithMagicLink,
    signOut,
    updateProfileAction,
    updatePassword,
    quickLogin,
  ]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
