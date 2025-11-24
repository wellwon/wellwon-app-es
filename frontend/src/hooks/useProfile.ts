import { useWSEQuery } from '@/wse/hooks/useWSEQuery';
import { useAuth } from '@/contexts/AuthContext';
import axios from '@/api/core';

/**
 * Hook for fetching user profile with real-time WSE updates
 *
 * Automatically invalidates React Query cache when 'user_profile_updated'
 * event is received via WebSocket, ensuring UI updates without logout/login.
 *
 * @returns Profile data and query state
 */
export function useProfile() {
  const { profile: authProfile } = useAuth();

  const { data: profile, ...queryState } = useWSEQuery(
    ['user', 'profile', authProfile?.user_id],
    async () => {
      if (!authProfile?.user_id) {
        return null;
      }
      const response = await axios.get('/api/auth/me');
      return response.data;
    },
    'user_profile_updated',
    {
      enabled: !!authProfile?.user_id,
      invalidateOn: (event) => {
        // Invalidate cache when profile update event matches current user
        return event.p?.user_id === authProfile?.user_id;
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
    }
  );

  return {
    profile: profile ?? authProfile,
    ...queryState,
  };
}
