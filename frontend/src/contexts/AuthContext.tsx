import React, { createContext, useContext, useEffect, useState } from 'react';
import { logger } from '@/utils/logger';
import type { Profile, SignUpMetadata, AuthResponse } from '@/types/auth';
import { login as apiLogin, register as apiRegister, fetchMe as apiGetProfile, logout as apiLogout } from '@/api/user_account';
import { API } from '@/api/core';

// Simplified User type (no Supabase dependency)
interface User {
  id: string;  // Alias for user_id (for compatibility)
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

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Hook moved to separate export for better HMR compatibility
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  // Protection against state updates after unmounting
  const isMountedRef = React.useRef(true);
  const profileLoadingRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    // Reset to true on mount (important for React StrictMode)
    console.log('[AuthContext] Component mounted, isMountedRef set to true');
    isMountedRef.current = true;
    return () => {
      console.log('[AuthContext] Component unmounting, isMountedRef set to false');
      isMountedRef.current = false;
    };
  }, []);

  const fetchProfile = React.useCallback(async (userId: string) => {
    // Prevent multiple concurrent profile loads
    if (profileLoadingRef.current === userId) {
      logger.debug('Profile already loading for user', { userId, component: 'AuthContext' });
      return;
    }

    profileLoadingRef.current = userId;
    logger.debug('Starting profile load', { userId, component: 'AuthContext' });

    try {
      // Call new backend API
      const profileData = await apiGetProfile();

      logger.debug('Profile loaded successfully', { component: 'AuthContext' });

      if (isMountedRef.current && profileLoadingRef.current === userId) {
        // Map API response to Profile type
        const mappedProfile: Profile = {
          id: profileData.user_id,
          user_id: profileData.user_id,
          username: profileData.username,
          email: profileData.email,
          role: profileData.role,
          first_name: profileData.first_name || null,
          last_name: profileData.last_name || null,
          avatar_url: profileData.avatar_url || null,
          bio: profileData.bio || null,
          phone: profileData.phone || null,
          active: profileData.is_active,
          is_active: profileData.is_active,
          is_developer: false,
          email_verified: profileData.email_verified,
          mfa_enabled: profileData.mfa_enabled,
          created_at: profileData.created_at,
          updated_at: profileData.created_at,
          last_login: profileData.last_login,
          last_password_change: profileData.last_password_change,
          security_alerts_enabled: profileData.security_alerts_enabled,
          active_sessions_count: profileData.active_sessions_count,
          user_type: profileData.user_type,
          user_number: profileData.user_number,
        };
        setProfile(mappedProfile);
      }
    } catch (error) {
      logger.error('Profile loading error', error, { userId, component: 'AuthContext' });
    } finally {
      if (profileLoadingRef.current === userId) {
        profileLoadingRef.current = null;
      }
    }
  }, []);

  // Initialize session from localStorage
  useEffect(() => {
    let mounted = true;

    logger.debug('AuthContext initializing', { component: 'AuthContext' });

    const initializeAuth = async () => {
      try {
        // Check for stored auth
        const stored = localStorage.getItem('auth');
        if (!stored) {
          logger.debug('No stored auth found', { component: 'AuthContext' });
          setLoading(false);
          return;
        }

        const auth = JSON.parse(stored);
        if (!auth.token) {
          logger.debug('No token in stored auth', { component: 'AuthContext' });
          localStorage.removeItem('auth');
          setLoading(false);
          return;
        }

        logger.debug('Found stored token, loading profile', { component: 'AuthContext' });
        setToken(auth.token);

        // Try to load profile
        const profileData = await apiGetProfile();

        if (mounted && isMountedRef.current) {
          // Create user object from profile
          const userObj: User = {
            id: profileData.user_id,
            user_id: profileData.user_id,
            username: profileData.username,
            email: profileData.email,
            role: profileData.role || 'user'
          };

          // Map API response to Profile type
          const mappedProfile: Profile = {
            id: profileData.user_id,
            user_id: profileData.user_id,
            username: profileData.username,
            email: profileData.email,
            role: profileData.role,
            first_name: profileData.first_name || null,
            last_name: profileData.last_name || null,
            avatar_url: profileData.avatar_url || null,
            bio: profileData.bio || null,
            phone: profileData.phone || null,
            active: profileData.is_active,
            is_active: profileData.is_active,
            is_developer: false,
            email_verified: profileData.email_verified,
            mfa_enabled: profileData.mfa_enabled,
            created_at: profileData.created_at,
            updated_at: profileData.created_at,
            last_login: profileData.last_login,
            last_password_change: profileData.last_password_change,
            security_alerts_enabled: profileData.security_alerts_enabled,
            active_sessions_count: profileData.active_sessions_count,
            user_type: profileData.user_type,
            user_number: profileData.user_number,
          };

          setUser(userObj);
          setProfile(mappedProfile);
          logger.info('User session restored from localStorage', { component: 'AuthContext' });
        }

        setLoading(false);
      } catch (error) {
        logger.error('Failed to restore session', error, { component: 'AuthContext' });
        // Clear invalid auth
        localStorage.removeItem('auth');
        setToken(null);
        setUser(null);
        setProfile(null);
        setLoading(false);
      }
    };

    initializeAuth();

    return () => {
      logger.debug('AuthContext cleanup', { component: 'AuthContext' });
      mounted = false;
    };
  }, []);

  // Listen for WSE profile update events
  useEffect(() => {
    const handleProfileUpdate = async (event: CustomEvent) => {
      try {
        logger.info('Profile update event received via WSE', { component: 'AuthContext' });

        // Refetch profile from backend to get latest data
        if (profile?.user_id) {
          await fetchProfile(profile.user_id);
        }
      } catch (error) {
        logger.error('Failed to handle profile update event', error, { component: 'AuthContext' });
      }
    };

    window.addEventListener('userProfileUpdated', handleProfileUpdate as EventListener);

    return () => {
      window.removeEventListener('userProfileUpdated', handleProfileUpdate as EventListener);
    };
  }, [profile?.user_id, fetchProfile]);

  const signUp = async (email: string, password: string, metadata?: SignUpMetadata) => {
    try {
      // Call new backend register API
      // Use email as username (simplest approach, OAuth-ready)
      await apiRegister(
        email, // username = email
        email,
        password,
        undefined, // secret - optional, uses default on backend
        true, // terms_accepted
        false, // marketing_consent
        undefined, // referral_code
        metadata?.first_name, // WellWon profile field
        metadata?.last_name   // WellWon profile field
      );

      // Don't auto-login - let event projector process first
      // User will be redirected to login page
      logger.info('Registration successful, please login', { component: 'AuthContext' });
      return { error: null };
    } catch (error: any) {
      logger.error('Registration error', error, { component: 'AuthContext' });
      return { error: error?.response?.data || error };
    }
  };

  const signIn = async (email: string, password: string) => {
    try {
      // Call new backend login API
      console.log('[AuthContext] signIn: calling apiLogin...');
      const authResponse = await apiLogin(email, password);
      console.log('[AuthContext] signIn: login successful, storing tokens...');

      // Store JWT tokens with expiration
      localStorage.setItem('auth', JSON.stringify({
        token: authResponse.access_token,
        refresh_token: authResponse.refresh_token,
        expires_at: Date.now() + (authResponse.expires_in * 1000),
        token_type: authResponse.token_type,
        session_id: authResponse.session_id
      }));

      setToken(authResponse.access_token);

      // Load profile
      console.log('[AuthContext] signIn: loading profile...');
      const profileData = await apiGetProfile();
      console.log('[AuthContext] signIn: profile loaded:', profileData);

      const userObj: User = {
        id: profileData.user_id,
        user_id: profileData.user_id,
        username: profileData.username,
        email: profileData.email,
        role: profileData.role || 'user'
      };

      // Map API response to Profile type
      const mappedProfile: Profile = {
        id: profileData.user_id,
        user_id: profileData.user_id,
        username: profileData.username,
        email: profileData.email,
        role: profileData.role,
        first_name: profileData.first_name || null,
        last_name: profileData.last_name || null,
        avatar_url: profileData.avatar_url || null,
        bio: profileData.bio || null,
        phone: profileData.phone || null,
        active: profileData.is_active,
        is_active: profileData.is_active,
        is_developer: false,
        email_verified: profileData.email_verified,
        mfa_enabled: profileData.mfa_enabled,
        created_at: profileData.created_at,
        updated_at: profileData.created_at,
        last_login: profileData.last_login,
        last_password_change: profileData.last_password_change,
        security_alerts_enabled: profileData.security_alerts_enabled,
        active_sessions_count: profileData.active_sessions_count,
        user_type: profileData.user_type,
        user_number: profileData.user_number,
      };

      console.log('[AuthContext] signIn: setting user and profile state...');
      setUser(userObj);
      setProfile(mappedProfile);
      console.log('[AuthContext] signIn: state update called, userObj:', userObj);

      // Dispatch custom event to trigger WSE reconnection
      console.log('[AuthContext] signIn: dispatching authSuccess event for WSE');
      window.dispatchEvent(new Event('authSuccess'));

      logger.info('User logged in successfully', { component: 'AuthContext' });
      console.log('[AuthContext] signIn: returning success');
      return { error: null };
    } catch (error: any) {
      logger.error('Login error', error, { component: 'AuthContext' });
      console.error('[AuthContext] signIn: error:', error);
      return { error: error?.response?.data || error };
    }
  };

  const signInWithMagicLink = async (email: string) => {
    // TODO: Implement magic link with new backend
    logger.warn('Magic link not implemented yet', { component: 'AuthContext' });
    return { error: new Error('Magic link not implemented') };
  };

  const signOut = async () => {
    try {
      // Call backend logout to invalidate server session
      await apiLogout();
    } catch (error) {
      // Log but don't fail - still need to clear local state
      logger.warn('Backend logout failed, clearing local state anyway', { component: 'AuthContext' });
    }

    try {
      // Clear localStorage
      localStorage.removeItem('auth');
      setToken(null);
      setUser(null);
      setProfile(null);
      profileLoadingRef.current = null;

      logger.info('User signed out successfully', { component: 'AuthContext' });
      return { error: null };
    } catch (error) {
      logger.error('Logout error', error, { component: 'AuthContext' });
      return { error };
    }
  };

  const updateProfile = async (updates: Partial<Profile>) => {
    if (!user) {
      return { error: new Error('Пользователь не авторизован') };
    }

    try {
      // Call backend PATCH /user/profile
      await API.patch('/user/profile', updates);

      // Update local state
      if (isMountedRef.current) {
        setProfile(prev => prev ? { ...prev, ...updates } : null);
      }

      logger.info('Profile updated successfully', { component: 'AuthContext' });
      return { error: null };
    } catch (error: any) {
      logger.error('Profile update error', error, { component: 'AuthContext' });
      return { error: error?.response?.data || error };
    }
  };

  const updatePassword = async (currentPassword: string, newPassword: string) => {
    try {
      if (!user?.email) {
        return { error: new Error('Пользователь не авторизован') };
      }

      // Call backend POST /user/change-password
      await API.post('/user/change-password', {
        old_password: currentPassword,
        new_password: newPassword
      });

      logger.info('Password updated successfully', { component: 'AuthContext' });
      return { error: null };
    } catch (error: any) {
      logger.error('Password update error', error, { component: 'AuthContext' });
      return { error: error?.response?.data || error };
    }
  };

  const quickLogin = async (email: string, password: string) => {
    return await signIn(email, password);
  };

  const value = {
    user,
    profile,
    loading,
    token,
    signUp,
    signIn,
    signInWithMagicLink,
    signOut,
    updateProfile,
    updatePassword,
    quickLogin,
    // Remove session (not used with JWT)
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
