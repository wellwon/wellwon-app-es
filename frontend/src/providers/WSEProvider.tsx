// src/providers/WSEProvider.tsx
import React, { ReactNode, useMemo, useRef, useEffect, useReducer, createContext, useContext } from 'react';
import { useWSE } from '@/wse/hooks/useWSE';
import { useUserAccount } from '@/hooks/useUserAccount';
import { getStoredToken } from '@/api/user_account';
import { WSEConfig, UseWSEReturn } from '@/wse/types';
import { Logger } from '@/wse';

// Create a logger instance for this module
const logger = new Logger('WSEProvider');

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface ExtendedWSEReturn extends UseWSEReturn {
  isInitialized: boolean;
  isConnected: boolean;
  authError: string | null;
}

export interface WSEProviderProps {
  children: ReactNode;
  config?: Partial<WSEConfig>;
  initialTopics?: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────────────────────────

const WSEContext = createContext<ExtendedWSEReturn | null>(null);

// ─────────────────────────────────────────────────────────────────────────────
// Hook to use WSE context
// ─────────────────────────────────────────────────────────────────────────────

export function useWSEContext(): ExtendedWSEReturn {
  const context = useContext(WSEContext);
  if (!context) {
    throw new Error('useWSEContext must be used within a WSEProvider');
  }
  return context;
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider Component - Use this ONCE at the root of your app
// ─────────────────────────────────────────────────────────────────────────────

export function WSEProvider({
  children,
  config,
  initialTopics = ['broker_connection_events', 'broker_account_events', 'system_events']
}: WSEProviderProps) {
  const userAccountHook = useUserAccount();
  const { isAuthenticated, sessionReady, user } = userAccountHook;
  const previousTokenRef = useRef<string | undefined>(undefined);
  const [updateCounter, forceUpdate] = useReducer((x: number) => x + 1, 0);

  // Listen for auth changes via storage events for cross-component reactivity
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth') {
        logger.info('[WSEProvider] Auth storage changed, forcing update');
        forceUpdate();
      }
    };

    // Also listen for custom auth events
    const handleAuthSuccess = () => {
      logger.info('[WSEProvider] Auth success event received');
      forceUpdate();
    };

    const handleAuthLogout = () => {
      logger.info('[WSEProvider] Auth logout event received');
      forceUpdate();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('authSuccess', handleAuthSuccess);
    window.addEventListener('authLogout', handleAuthLogout);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('authSuccess', handleAuthSuccess);
      window.removeEventListener('authLogout', handleAuthLogout);
    };
  }, []);

  // FIXED: isAuthenticated is now a boolean value, not a function
  const isAuth = isAuthenticated;

  // Token retrieval - directly check localStorage for immediate updates
  const accessToken = useMemo(() => {
    // Force dependency on updateCounter to ensure re-evaluation
    const _ = updateCounter;

    logger.info('[WSEProvider] Token check:', {
      isAuthenticated: isAuth,
      sessionReady,
      hasUser: !!user,
      updateCounter
    });

    // Direct localStorage check for immediate token availability
    try {
      const token = getStoredToken();

      if (!token) {
        logger.debug('[WSEProvider] No valid token in storage');
        return undefined;
      }

      // Additional validation: check if we have user data
      const authData = localStorage.getItem('auth_user');
      if (!authData) {
        logger.debug('[WSEProvider] No user data found');
        return undefined;
      }

      // Only log if token actually changed
      if (previousTokenRef.current !== token) {
        logger.info(`[WSEProvider] Token changed from ${previousTokenRef.current ? 'exists' : 'none'} to ${token ? 'exists' : 'none'}`);
        previousTokenRef.current = token;
      }

      return token;
    } catch (error) {
      logger.debug('[WSEProvider] Failed to get access token:', error);
      return undefined;
    }
  }, [isAuth, sessionReady, user, updateCounter]); // Include updateCounter as dependency

  // Use the WSE hook - it handles all the complexity
  const wseHook = useWSE(accessToken, initialTopics, config);

  // Create a context value with minimal additions
  const contextValue = useMemo<ExtendedWSEReturn>(() => ({
    ...wseHook,
    isInitialized: !!accessToken && wseHook.connectionHealth !== 'pending',
    isConnected: wseHook.connectionHealth === 'connected',
    authError: !accessToken && isAuth && sessionReady ? 'No valid access token available' : null,
  }), [wseHook, accessToken, isAuth, sessionReady]);

  // Debug logging for connection state changes
  useEffect(() => {
    if (accessToken && wseHook.connectionHealth === 'pending') {
      logger.info('[WSEProvider] Token available, waiting for WSE connection...');
    } else if (accessToken && wseHook.connectionHealth === 'connected') {
      logger.info('[WSEProvider] WSE connected successfully');
    } else if (!accessToken) {
      logger.info('[WSEProvider] No token available for WSE connection');
    }
  }, [accessToken, wseHook.connectionHealth]);

  return (
    <WSEContext.Provider value={contextValue}>
      {children}
    </WSEContext.Provider>
  );
}