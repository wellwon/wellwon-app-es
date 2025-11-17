import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';
import type { Profile, SignUpMetadata, AuthResponse } from '@/types/auth';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
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
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Protection against state updates after unmounting and multiple profile loads
  const isMountedRef = React.useRef(true);
  const profileLoadingRef = React.useRef<string | null>(null);
  
  React.useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const fetchProfile = React.useCallback(async (userId: string) => {
    // Prevent multiple concurrent profile loads for the same user
    if (profileLoadingRef.current === userId) {
      logger.debug('Profile already loading for user', { userId, component: 'AuthContext' });
      return;
    }

    profileLoadingRef.current = userId;
    logger.debug('Starting profile load', { userId, component: 'AuthContext' });
    
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('user_id', userId)
        .single();

      logger.debug('Profile query result', { hasData: !!data, error: !!error, component: 'AuthContext' });

      if (error) {
        logger.error('Profile loading error', error, { userId, component: 'AuthContext' });
        return;
      }

      // Check if component is still mounted and we're loading the right user
      if (isMountedRef.current && profileLoadingRef.current === userId) {
        // Adapt database data to our interface
        const profileData: Profile = {
          id: data.id,
          user_id: data.user_id,
          first_name: data.first_name,
          last_name: data.last_name,
          avatar_url: data.avatar_url,
          bio: data.bio,
          phone: data.phone,
          active: data.active,
          is_developer: data.developer || false,
          user_number: data.user_number,
          created_at: data.created_at,
          updated_at: data.updated_at
        };
        
        logger.debug('Setting profile state', { isDeveloper: profileData.is_developer, component: 'AuthContext' });
        setProfile(profileData);
      }
    } catch (error) {
      logger.error('Critical error getting profile', error, { userId, component: 'AuthContext' });
    } finally {
      // Clear loading flag only if we're still handling this user
      if (profileLoadingRef.current === userId) {
        profileLoadingRef.current = null;
      }
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    let authStateProcessed = false;

    logger.debug('AuthContext useEffect mounted', { component: 'AuthContext' });

    // Set up auth state listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (!mounted || !isMountedRef.current) {
          logger.debug('Auth state change ignored - unmounted', { event, component: 'AuthContext' });
          return;
        }
        
        logger.debug('Auth state change processing', { event, hasSession: !!session, authStateProcessed, component: 'AuthContext' });
        
        // Always update session and user state immediately
        setSession(session);
        setUser(session?.user ?? null);
        
        if (session?.user) {
          // Load profile with slight delay to avoid race conditions
          const delay = authStateProcessed ? 100 : 50;
          setTimeout(() => {
            if (mounted && isMountedRef.current && session?.user) {
              fetchProfile(session.user.id);
            }
          }, delay);
        } else {
          // Clear profile and loading flag when user logs out
          setProfile(null);
          profileLoadingRef.current = null;
        }
        
        authStateProcessed = true;
        setLoading(false);
      }
    );

    // Check for existing session with improved error handling
    const initializeSession = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        
        if (!mounted || !isMountedRef.current) {
          logger.debug('Initial session check ignored - unmounted', { component: 'AuthContext' });
          return;
        }
        
        if (error) {
          logger.error('Error getting initial session', error, { component: 'AuthContext' });
          setLoading(false);
          return;
        }
        
        logger.debug('Initial session check completed', { hasSession: !!session, component: 'AuthContext' });
        
        setSession(session);
        setUser(session?.user ?? null);
        
        if (session?.user) {
          setTimeout(() => {
            if (mounted && isMountedRef.current && session?.user) {
              fetchProfile(session.user.id);
            }
          }, 50);
        }
        
        setLoading(false);
      } catch (error) {
        logger.error('Critical error in session initialization', error, { component: 'AuthContext' });
        if (mounted && isMountedRef.current) {
          setLoading(false);
        }
      }
    };

    initializeSession();

    return () => {
      logger.debug('AuthContext useEffect cleanup', { component: 'AuthContext' });
      mounted = false;
      subscription.unsubscribe();
    };
  }, [fetchProfile]);

  const signUp = async (email: string, password: string, metadata?: SignUpMetadata) => {
    const redirectUrl = `${window.location.origin}/platform`;
    
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectUrl,
        data: metadata,
      },
    });
    
    return { error };
  };

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    
    return { error };
  };

  const signInWithMagicLink = async (email: string) => {
    const redirectUrl = `${window.location.origin}/`;
    
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: redirectUrl,
      },
    });
    
    return { error };
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    
    if (!error) {
      // Clear profile loading state
      profileLoadingRef.current = null;
      // Clear local state immediately
      setSession(null);
      setUser(null);
      setProfile(null);
      
      logger.info('User signed out successfully', { component: 'AuthContext' });
    }
    
    return { error };
  };

  const updateProfile = async (updates: Partial<Profile>) => {
    if (!user) {
      return { error: new Error('Пользователь не авторизован') };
    }

    const { error } = await supabase
      .from('profiles')
      .update(updates)
      .eq('user_id', user.id);

    if (!error && isMountedRef.current) {
      // Обновляем локальное состояние профиля
      setProfile(prev => prev ? { ...prev, ...updates } : null);
    }

    return { error };
  };

  const updatePassword = async (currentPassword: string, newPassword: string) => {
    try {
      if (!user?.email) {
        return { error: new Error('Пользователь не авторизован') };
      }

      // Обновляем пароль
      const { error } = await supabase.auth.updateUser({
        password: newPassword
      });

      return { error };
    } catch (error) {
      logger.error('Ошибка обновления пароля', error, { component: 'AuthContext' });
      return { error };
    }
  };

  const quickLogin = async (email: string, password: string) => {
    const { error } = await signIn(email, password);
    return { error };
  };

  const value = {
    user,
    session,
    profile,
    loading,
    signUp,
    signIn,
    signInWithMagicLink,
    signOut,
    updateProfile,
    updatePassword,
    quickLogin,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};