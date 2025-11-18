// src/hooks/useUserAccount.ts

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import * as authAPI from "@/api/user_account";

export interface User {
  user_id: string;
  username: string;
  email: string;
  role: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  sessionReady: boolean;
  loading: boolean;
  error: string | null;
  requiresMFA: boolean;
  sessionId: string | null;
  tokenExpiresAt: number | null;
  isRefreshing: boolean;
}

export const AuthEvents = {
  AUTH_STATE_CHANGED: 'authStateChanged',
  AUTH_TOKEN_REFRESHED: 'authTokenRefreshed',
  AUTH_TOKEN_EXPIRING: 'authTokenExpiring',
  AUTH_SUCCESS: 'authSuccess',
  AUTH_FAILED: 'authFailed',
  AUTH_LOGOUT: 'authLogout',
} as const;

// Initialize with sessionReady as true to prevent multiple updates
const createInitialState = (): AuthState => ({
  user: null,
  isAuthenticated: false,
  sessionReady: true,
  loading: false,
  error: null,
  requiresMFA: false,
  sessionId: null,
  tokenExpiresAt: null,
  isRefreshing: false,
});

export function useUserAccount() {
  const [state, setState] = useState<AuthState>(() => {
    const auth = authAPI.getStoredAuth();
    const userData = localStorage.getItem('auth_user');

    if (auth?.token && userData && !authAPI.isTokenExpired()) {
      return {
        ...createInitialState(),
        sessionReady: false,
      };
    }

    return createInitialState();
  });

  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  const expiryWarningTimerRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // Event Dispatcher
  const dispatchAuthEvent = useCallback((type: string, detail: any) => {
    console.log(`[useAuth] Dispatching ${type}:`, detail);
    window.dispatchEvent(new CustomEvent(type, { detail }));
  }, []);

  // Token Management
  const storeAuthData = useCallback((response: authAPI.AuthResponse, username?: string) => {
    const authStorage: authAPI.AuthStorage = {
      token: response.access_token,
      refresh_token: response.refresh_token,
      expires_at: Date.now() + (response.expires_in * 1000),
      token_type: response.token_type || 'Bearer',
      session_id: response.session_id,
    };

    authAPI.setStoredAuth(authStorage);

    const userData = {
      username: username || 'user',
      session_id: response.session_id,
    };
    localStorage.setItem('auth_user', JSON.stringify(userData));

    window.dispatchEvent(new StorageEvent('storage', {
      key: 'auth',
      newValue: JSON.stringify(authStorage),
      url: window.location.href,
      storageArea: localStorage
    }));

    return authStorage;
  }, []);

  // Token Refresh - Fixed version
  const performTokenRefresh = useCallback(async (): Promise<void> => {
    if (!mountedRef.current || state.isRefreshing) return;

    const auth = authAPI.getStoredAuth();
    if (!auth?.refresh_token) {
      console.error('[useAuth] No refresh token available');
      return;
    }

    setState(prev => ({ ...prev, isRefreshing: true }));

    try {
      console.log('[useAuth] Refreshing token...');
      const response = await authAPI.refreshToken(auth.refresh_token);

      if (!response.access_token) {
        throw new Error('No access token in refresh response');
      }

      // Update stored auth
      const newAuth: authAPI.AuthStorage = {
        token: response.access_token,
        refresh_token: response.refresh_token || auth.refresh_token,
        expires_at: Date.now() + (response.expires_in * 1000),
        token_type: response.token_type || 'Bearer',
        session_id: auth.session_id,
      };

      authAPI.setStoredAuth(newAuth);

      window.dispatchEvent(new StorageEvent('storage', {
        key: 'auth',
        newValue: JSON.stringify(newAuth),
        url: window.location.href,
        storageArea: localStorage
      }));

      setState(prev => ({
        ...prev,
        tokenExpiresAt: newAuth.expires_at,
        isRefreshing: false,
      }));

      dispatchAuthEvent(AuthEvents.AUTH_TOKEN_REFRESHED, {
        token: response.access_token,
        expiresAt: newAuth.expires_at,
      });

      // Schedule next refresh
      scheduleTokenRefresh();

      console.log('[useAuth] Token refreshed successfully');
    } catch (error) {
      console.error('[useAuth] Token refresh failed:', error);
      setState(prev => ({ ...prev, isRefreshing: false }));

      authAPI.clearStoredAuth();
      localStorage.removeItem('auth_user');
      setState(createInitialState());

      dispatchAuthEvent(AuthEvents.AUTH_FAILED, {
        error: 'Token refresh failed',
        code: 'TOKEN_REFRESH_FAILED'
      });
    }
  }, [state.isRefreshing, dispatchAuthEvent]);

  // Create a stable ref for the refresh function
  const performTokenRefreshRef = useRef<typeof performTokenRefresh>(null);
  performTokenRefreshRef.current = performTokenRefresh;

  // Schedule Token Refresh - Fixed
  const scheduleTokenRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (expiryWarningTimerRef.current) {
      clearTimeout(expiryWarningTimerRef.current);
      expiryWarningTimerRef.current = null;
    }

    const auth = authAPI.getStoredAuth();
    if (!auth?.expires_at || !auth.refresh_token) return;

    const now = Date.now();
    const timeUntilExpiry = auth.expires_at - now;

    if (timeUntilExpiry <= 60000) {
      console.log('[useAuth] Token expired or expiring soon, not scheduling refresh');
      return;
    }

    // Schedule warning 2 minutes before expiry
    const warnTime = auth.expires_at - 120000;
    if (warnTime > now) {
      expiryWarningTimerRef.current = setTimeout(() => {
        if (mountedRef.current) {
          dispatchAuthEvent(AuthEvents.AUTH_TOKEN_EXPIRING, {
            expiresIn: 120,
            tokenExpiresAt: auth.expires_at
          });
        }
      }, warnTime - now);
    }

    // Schedule refresh 1 minute before expiry
    const refreshTime = auth.expires_at - 60000;
    refreshTimerRef.current = setTimeout(() => {
      if (mountedRef.current && performTokenRefreshRef.current) {
        // Call the current version of the function
        performTokenRefreshRef.current();
      }
    }, refreshTime - now);

    console.log('[useAuth] Token refresh scheduled in', Math.round((refreshTime - now) / 1000), 'seconds');
  }, [dispatchAuthEvent]);

  // Session Restoration
  useEffect(() => {
    let isMounted = true;

    const restoreSession = async () => {
      if (state.sessionReady) {
        return;
      }

      console.log('[useAuth] Attempting session restoration');

      const auth = authAPI.getStoredAuth();
      const userData = localStorage.getItem('auth_user');

      if (!auth?.token || !userData) {
        console.log('[useAuth] No stored session');
        if (isMounted) {
          setState(createInitialState());
        }
        return;
      }

      if (authAPI.isTokenExpired()) {
        console.log('[useAuth] Stored token expired, clearing session');

        authAPI.clearStoredAuth();
        localStorage.removeItem('auth_user');

        if (isMounted) {
          setState(createInitialState());
        }
        return;
      }

      try {
        const userInfo = JSON.parse(userData);

        let user: User;
        try {
          const profile = await authAPI.fetchMe();
          user = {
            user_id: profile.user_id,
            username: profile.username,
            email: profile.email,
            role: profile.role,
          };

          localStorage.setItem('auth_user', JSON.stringify({
            ...user,
            session_id: auth.session_id,
          }));
        } catch (error) {
          console.warn('[useAuth] Failed to fetch profile, using stored data');
          user = {
            user_id: userInfo.user_id || '',
            username: userInfo.username || '',
            email: userInfo.email || '',
            role: userInfo.role || 'user',
          };
        }

        if (isMounted) {
          setState({
            user,
            isAuthenticated: true,
            sessionReady: true,
            loading: false,
            error: null,
            requiresMFA: false,
            sessionId: auth.session_id,
            tokenExpiresAt: auth.expires_at,
            isRefreshing: false,
          });

          scheduleTokenRefresh();
        }

        console.log('[useAuth] Session restored successfully');
      } catch (error) {
        console.error('[useAuth] Session restoration error:', error);

        authAPI.clearStoredAuth();
        localStorage.removeItem('auth_user');

        if (isMounted) {
          setState(createInitialState());
        }
      }
    };

    restoreSession();

    return () => {
      isMounted = false;
      mountedRef.current = false;
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
      if (expiryWarningTimerRef.current) clearTimeout(expiryWarningTimerRef.current);
    };
  }, [state.sessionReady, scheduleTokenRefresh]);

  // Login
  const login = useCallback(async (
    username: string,
    password: string,
    rememberMe: boolean = false
  ): Promise<User | null> => {
    console.log('[useAuth] Login attempt for:', username);

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      // Fix: authAPI.login expects these exact parameters
      const response = await authAPI.login(
        username,
        password,
        undefined,    // mfa_code
        undefined,    // device_info
        rememberMe    // remember_me
      );

      if (response.requires_mfa) {
        setState(prev => ({
          ...prev,
          loading: false,
          requiresMFA: true,
          error: "MFA code required",
        }));
        return null;
      }

      const authStorage = storeAuthData(response, username);

      let user: User;
      try {
        const profile = await authAPI.fetchMe();
        user = {
          user_id: profile.user_id,
          username: profile.username,
          email: profile.email,
          role: profile.role,
        };

        localStorage.setItem('auth_user', JSON.stringify({
          ...user,
          session_id: response.session_id,
        }));
      } catch (error) {
        console.warn('[useAuth] Failed to fetch profile, using basic user data');
        user = {
          user_id: username,
          username: username,
          email: '',
          role: 'user',
        };
      }

      setState({
        user,
        isAuthenticated: true,
        sessionReady: true,
        loading: false,
        error: null,
        requiresMFA: false,
        sessionId: response.session_id,
        tokenExpiresAt: authStorage.expires_at,
        isRefreshing: false,
      });

      dispatchAuthEvent(AuthEvents.AUTH_SUCCESS, {
        user,
        token: response.access_token,
        expiresAt: authStorage.expires_at,
        sessionId: response.session_id
      });

      scheduleTokenRefresh();

      // Data will load via React Query and WSE after navigation
      console.log('[useAuth] Login successful');
      return user;
    } catch (error: any) {
      // Handle Pydantic validation errors (array) or string errors
      let errorMessage = "Invalid credentials";
      if (error?.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          // Pydantic validation errors - extract messages and clean "Value error, " prefix
          errorMessage = error.response.data.detail
            .map((err: any) => err.msg.replace(/^Value error,\s*/i, ''))
            .join('. ');
        } else if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail.replace(/^Value error,\s*/i, '');
        }
      } else if (error?.message) {
        errorMessage = error.message;
      }

      console.error('[useAuth] Login failed:', errorMessage);

      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
        isAuthenticated: false,
        sessionReady: true,
      }));

      dispatchAuthEvent(AuthEvents.AUTH_FAILED, {
        error: errorMessage,
        code: error?.response?.status || 'LOGIN_FAILED'
      });

      return null;
    }
  }, [storeAuthData, scheduleTokenRefresh, dispatchAuthEvent]);

  // Logout
  const logout = useCallback(async () => {
    console.log('[useAuth] Logout initiated');

    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    if (expiryWarningTimerRef.current) clearTimeout(expiryWarningTimerRef.current);

    dispatchAuthEvent(AuthEvents.AUTH_LOGOUT, {
      user: state.user,
      timestamp: Date.now()
    });

    setState(prev => ({ ...prev, loading: true }));

    try {
      await authAPI.logout();
      console.log('[useAuth] Logout API successful');
    } catch (error) {
      console.warn('[useAuth] Logout API error:', error);
    }

    authAPI.clearStoredAuth();
    localStorage.removeItem('auth_user');

    window.dispatchEvent(new StorageEvent('storage', {
      key: 'auth',
      newValue: null,
      oldValue: localStorage.getItem('auth'),
      url: window.location.href,
      storageArea: localStorage
    }));

    setState(createInitialState());

    console.log('[useAuth] Logout complete');
  }, [state.user, dispatchAuthEvent]);

  // Helpers
  const getAccessToken = useCallback((): string | null => {
    return authAPI.getStoredToken();
  }, []);

  // FIXED: Compute isAuthenticated value directly, not as a function
  const isAuthenticated = useMemo(() => {
    return state.isAuthenticated && !authAPI.isTokenExpired();
  }, [state.isAuthenticated]);

  // Public API
  const tokenStatus = useMemo(() => {
    if (!state.tokenExpiresAt) return null;

    const now = Date.now();
    const timeUntilExpiry = state.tokenExpiresAt - now;

    return {
      expiresAt: state.tokenExpiresAt,
      expiresIn: Math.max(0, Math.floor(timeUntilExpiry / 1000)),
      isExpired: timeUntilExpiry <= 0,
      isExpiringSoon: timeUntilExpiry > 0 && timeUntilExpiry < 120000,
    };
  }, [state.tokenExpiresAt]);

  return {
    // State
    user: state.user,
    isAuthenticated,  // Now this is a boolean value, not a function
    sessionReady: state.sessionReady,
    loading: state.loading,
    error: state.error,
    requiresMFA: state.requiresMFA,
    sessionId: state.sessionId,
    isRefreshing: state.isRefreshing,
    tokenStatus,

    // Actions
    login,
    logout,
    refreshToken: performTokenRefresh,

    // Helpers
    getAccessToken,
  };
}