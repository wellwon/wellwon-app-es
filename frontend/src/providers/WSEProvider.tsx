// src/providers/WSEProvider.tsx
import React, { ReactNode, useMemo, useRef, useEffect, useReducer, createContext, useContext } from 'react';
import { useWSE } from '@/wse/hooks/useWSE';
import { useAuthStore, getAuthToken } from '@/hooks/auth';
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
  initialTopics = ['user_account_events', 'system_events']
}: WSEProviderProps) {
  // Zustand auth store (synchronous)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const token = useAuthStore((state) => state.token);

  const previousTokenRef = useRef<string | undefined>(undefined);
  const [updateCounter, forceUpdate] = useReducer((x: number) => x + 1, 0);

  // Listen for auth changes via custom events
  useEffect(() => {
    const handleAuthSuccess = () => {
      logger.info('[WSEProvider] Auth success event received');
      forceUpdate();
    };

    const handleAuthLogout = () => {
      logger.info('[WSEProvider] Auth logout event received');
      forceUpdate();
    };

    window.addEventListener('authSuccess', handleAuthSuccess);
    window.addEventListener('authLogout', handleAuthLogout);

    return () => {
      window.removeEventListener('authSuccess', handleAuthSuccess);
      window.removeEventListener('authLogout', handleAuthLogout);
    };
  }, []);

  // Token retrieval - use Zustand store directly
  const accessToken = useMemo(() => {
    // Force dependency on updateCounter to ensure re-evaluation
    const _ = updateCounter;

    logger.info('[WSEProvider] Token check:', {
      isAuthenticated,
      hasToken: !!token,
      updateCounter
    });

    // Get token from Zustand store (already validated)
    const currentToken = getAuthToken();

    if (!currentToken) {
      logger.debug('[WSEProvider] No valid token in store');
      return undefined;
    }

    // Only log if token actually changed
    if (previousTokenRef.current !== currentToken) {
      logger.info(`[WSEProvider] Token changed from ${previousTokenRef.current ? 'exists' : 'none'} to ${currentToken ? 'exists' : 'none'}`);
      previousTokenRef.current = currentToken;
    }

    return currentToken;
  }, [isAuthenticated, token, updateCounter]);

  // Use the WSE hook - it handles all the complexity
  const wseHook = useWSE(accessToken, initialTopics, config);

  // Create a context value with minimal additions
  const contextValue = useMemo<ExtendedWSEReturn>(() => ({
    ...wseHook,
    isInitialized: !!accessToken && wseHook.connectionHealth !== 'pending',
    isConnected: wseHook.connectionHealth === 'connected',
    authError: !accessToken && isAuthenticated ? 'No valid access token available' : null,
  }), [wseHook, accessToken, isAuthenticated]);

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