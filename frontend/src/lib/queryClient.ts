// =============================================================================
// File: src/lib/queryClient.ts
// Description: Shared QueryClient instance with WSE integration for reactive UI
// =============================================================================

import { QueryClient } from '@tanstack/react-query';

// Dynamic staleTime based on WebSocket connection
// TkDodo Best Practice: "If you update all your data via websockets, set staleTime: Infinity"
// https://tkdodo.eu/blog/using-web-sockets-with-react-query
//
// Pattern:
// - WebSocket CONNECTED: staleTime = Infinity (WSE handles all updates, no polling needed)
// - WebSocket DISCONNECTED: staleTime = 5s (REST API fallback mode)
//
// Benefits:
// - Reduced server load (no redundant refetches when WSE active)
// - Real-time updates via WSE cache invalidation
// - Automatic fallback to polling when WSE disconnects

/**
 * Get dynamic staleTime based on WSE connection state
 * Returns Infinity when connected (WSE invalidates cache), 5000ms when disconnected
 */
export function getDynamicStaleTime(_query?: unknown): number {
  const wseStore = (window as any).__WSE_STORE__;
  const connectionState = wseStore?.getState?.()?.connectionState;
  const isConnected = connectionState === 'connected';

  return isConnected ? Infinity : 5000;
}

/**
 * Get dynamic refetchInterval based on WSE connection state
 * Returns false when connected (no polling), 30000ms when disconnected
 */
export function getDynamicRefetchInterval(_query?: unknown): number | false {
  const wseStore = (window as any).__WSE_STORE__;
  const connectionState = wseStore?.getState?.()?.connectionState;
  const isConnected = connectionState === 'connected';

  return isConnected ? false : 30000;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Dynamic staleTime - Infinity when WSE connected, 5s when disconnected
      staleTime: getDynamicStaleTime,

      // Dynamic refetchInterval - false when WSE connected, 30s when disconnected
      refetchInterval: getDynamicRefetchInterval,

      // Best practices for WSE integration:
      // - refetchOnWindowFocus: false (WSE keeps data fresh)
      // - refetchOnReconnect: true (ensure consistency after network outage)
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,

      // Retry failed queries with exponential backoff
      // BUT: Don't retry 404/410 errors - resource was deleted or doesn't exist
      retry: (failureCount, error) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const status = (error as any)?.response?.status;
        // Don't retry 404 (Not Found) or 410 (Gone) - resource deleted
        if (status === 404 || status === 410) {
          return false;
        }
        // Don't retry 401/403 - auth issues won't be fixed by retry
        if (status === 401 || status === 403) {
          return false;
        }
        // Default: retry up to 3 times
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
      retryDelay: 1000,
    },
  },
});
