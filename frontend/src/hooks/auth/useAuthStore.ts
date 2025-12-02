// =============================================================================
// File: src/hooks/auth/useAuthStore.ts
// Description: Zustand store for auth token state (synchronous access for axios)
// Pattern: Zustand for synchronous state, React Query for server state
// =============================================================================

import { create } from 'zustand';
import { subscribeWithSelector, persist } from 'zustand/middleware';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

import type { Profile } from '@/types/auth';

interface AuthStorage {
  token: string | null;
  refresh_token: string | null;
  expires_at: number | null;
  token_type: string;
  session_id: string | null;
}

interface AuthStoreState {
  // Token state (persisted)
  token: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
  sessionId: string | null;

  // Profile cache (persisted) - for instant page refresh
  cachedProfile: Profile | null;
  cachedProfileUpdatedAt: number | null;

  // Derived state
  isAuthenticated: boolean;
  isTokenExpired: () => boolean;

  // Actions
  setTokens: (tokens: AuthStorage) => void;
  clearTokens: () => void;
  setCachedProfile: (profile: Profile) => void;

  // Helpers
  getAccessToken: () => string | null;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const useAuthStore = create<AuthStoreState>()(
  subscribeWithSelector(
    persist(
      (set, get) => ({
        // Initial state
        token: null,
        refreshToken: null,
        expiresAt: null,
        sessionId: null,
        cachedProfile: null,
        cachedProfileUpdatedAt: null,
        isAuthenticated: false,

        // Check if token is expired
        isTokenExpired: () => {
          const { expiresAt } = get();
          if (!expiresAt) return true;
          return Date.now() >= expiresAt;
        },

        // Set tokens after login/refresh
        setTokens: (tokens) => {
          set({
            token: tokens.token,
            refreshToken: tokens.refresh_token,
            expiresAt: tokens.expires_at,
            sessionId: tokens.session_id,
            isAuthenticated: !!tokens.token,
          });
        },

        // Clear tokens on logout
        clearTokens: () => {
          set({
            token: null,
            refreshToken: null,
            expiresAt: null,
            sessionId: null,
            cachedProfile: null,
            cachedProfileUpdatedAt: null,
            isAuthenticated: false,
          });
        },

        // Cache profile for instant page refresh
        setCachedProfile: (profile) => {
          set({
            cachedProfile: profile,
            cachedProfileUpdatedAt: Date.now(),
          });
        },

        // Get access token (for axios interceptor)
        getAccessToken: () => {
          const { token, isTokenExpired } = get();
          if (!token || isTokenExpired()) return null;
          return token;
        },
      }),
      {
        name: 'wellwon-auth',
        partialize: (state) => ({
          token: state.token,
          refreshToken: state.refreshToken,
          expiresAt: state.expiresAt,
          sessionId: state.sessionId,
          isAuthenticated: state.isAuthenticated,
          cachedProfile: state.cachedProfile,
          cachedProfileUpdatedAt: state.cachedProfileUpdatedAt,
        }),
      }
    )
  )
);

// -----------------------------------------------------------------------------
// Selectors
// -----------------------------------------------------------------------------

export const selectToken = (state: AuthStoreState) => state.token;
export const selectIsAuthenticated = (state: AuthStoreState) => state.isAuthenticated;
export const selectSessionId = (state: AuthStoreState) => state.sessionId;

// -----------------------------------------------------------------------------
// Helper: Get token synchronously (for axios interceptor)
// -----------------------------------------------------------------------------

export function getAuthToken(): string | null {
  return useAuthStore.getState().getAccessToken();
}

export function isAuthenticated(): boolean {
  const state = useAuthStore.getState();
  return state.isAuthenticated && !state.isTokenExpired();
}
