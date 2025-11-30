// =============================================================================
// File: src/hooks/auth/index.ts
// Description: Auth hooks barrel export
// Architecture: Zustand (token storage) + React Query (profile) + WSE (real-time)
// =============================================================================

// Zustand store for token (synchronous access for axios)
export {
  useAuthStore,
  getAuthToken,
  isAuthenticated,
  selectToken,
  selectIsAuthenticated,
  selectSessionId,
} from './useAuthStore';

// React Query hooks for profile
export { useProfile, authKeys, profileToUser, type User } from './useProfile';

// Mutations for auth operations
export {
  useLogin,
  useLogout,
  useRegister,
  useUpdateProfile,
  useChangePassword,
  useRefreshToken,
} from './useAuthMutations';

// Re-export types
export type { Profile } from '@/types/auth';
