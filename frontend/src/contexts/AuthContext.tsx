import React, { createContext, useContext, useEffect, useState } from 'react';
import { logger } from '@/utils/logger';
import type { Profile, SignUpMetadata, AuthResponse } from '@/types/auth';
import { login as apiLogin, register as apiRegister, getProfile as apiGetProfile } from '@/api/user_account';
import { API } from '@/api/core';

// Simplified User type (no Supabase dependency)
interface User {
  user_id: string;
  username: string;
  email: string;
  role: string;
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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  // Protection against state updates after unmounting
  const isMountedRef = React.useRef(true);
  const profileLoadingRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    return () => {
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
        setProfile(profileData);
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
            user_id: profileData.user_id,
            username: profileData.username,
            email: profileData.email,
            role: profileData.role || 'user'
          };

          setUser(userObj);
          setProfile(profileData);
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

  const signUp = async (email: string, password: string, metadata?: SignUpMetadata) => {
    try {
      // Call new backend register API
      await apiRegister({
        username: email.split('@')[0], // Use email prefix as username
        email,
        password,
        secret: metadata?.secret || 'default',  // TODO: Add secret to form
        terms_accepted: true
      });

      // Auto-login after registration
      return await signIn(email, password);
    } catch (error: any) {
      logger.error('Registration error', error, { component: 'AuthContext' });
      return { error: error?.response?.data || error };
    }
  };

  const signIn = async (email: string, password: string) => {
    try {
      // Call new backend login API
      const authResponse = await apiLogin(email, password);

      // Store JWT tokens
      localStorage.setItem('auth', JSON.stringify({
        token: authResponse.access_token,
        refresh_token: authResponse.refresh_token
      }));

      setToken(authResponse.access_token);

      // Load profile
      const profileData = await apiGetProfile();

      if (isMountedRef.current) {
        const userObj: User = {
          user_id: profileData.user_id,
          username: profileData.username,
          email: profileData.email,
          role: profileData.role || 'user'
        };

        setUser(userObj);
        setProfile(profileData);
      }

      logger.info('User logged in successfully', { component: 'AuthContext' });
      return { error: null };
    } catch (error: any) {
      logger.error('Login error', error, { component: 'AuthContext' });
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
      // Call new backend PATCH /api/auth/profile
      await API.patch('/api/auth/profile', updates);

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

      // Call new backend POST /api/auth/change-password
      await API.post('/api/auth/change-password', {
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
