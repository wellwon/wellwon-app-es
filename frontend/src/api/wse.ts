/**
 * WebSocket Engine (WSE) API Layer
 *
 * Provides clean, typed interface for WebSocket operations.
 * Extracted from business logic hooks for better separation of concerns.
 *
 * Architecture:
 * - Component → Hook (business logic) → WSE API (this file) → useWSE (transport)
 * - Mirrors REST API pattern in /api/broker_connection.ts, /api/broker_account.ts
 *
 * @module api/wse
 * @since 2025-11-10 - Architectural refactor
 */

import { useCallback, useMemo } from 'react';
import { useWSEContext } from '@/providers';
import { MessagePriority, ConnectionState, NetworkDiagnostics } from '@/wse/types';
import { logger } from '@/wse/utils/logger';

// ============================================================================
// Type Definitions
// ============================================================================

export interface MessageOptions {
  priority?: MessagePriority;
  requiresAck?: boolean;
  timeout?: number;
}

export interface ConnectionStatus {
  status: 'connected' | 'connecting' | 'disconnected' | 'error';
  health: ConnectionState;
  diagnostics: NetworkDiagnostics | null;
}

export interface SnapshotRequestOptions {
  /** Filter by broker ID (e.g., 'alpaca', 'tradestation', 'virtual') */
  brokerId?: string;
  /** Filter by environment ('paper' | 'live') */
  environment?: string;
  /** Include additional details (slower, more data) */
  includeDetails?: boolean;
}

// ============================================================================
// WSE API Interface
// ============================================================================

export interface WSEApi {
  // ──────────────────────────────────────────────────────────────────────
  // Snapshot Requests
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Request broker connections snapshot
   *
   * Triggers backend to send `broker_connection_snapshot` event with all broker connections.
   *
   * Use cases:
   * - Initial page load verification
   * - Manual refresh button
   * - Drift detection recovery
   *
   * @param options Optional filters
   * @returns void (response arrives via WebSocket event)
   *
   * @example
   * ```ts
   * // Request all brokers
   * wseApi.requestBrokerSnapshot();
   *
   * // Request specific broker
   * wseApi.requestBrokerSnapshot({ brokerId: 'alpaca', environment: 'paper' });
   * ```
   */
  requestBrokerSnapshot: (options?: SnapshotRequestOptions) => void;

  /**
   * Request broker accounts snapshot
   *
   * Triggers backend to send `broker_account_snapshot` event with all accounts.
   *
   * Use cases:
   * - Initial page load
   * - Manual refresh
   * - After broker connection established
   *
   * @param options Optional filters
   * @returns void (response arrives via WebSocket event)
   *
   * @example
   * ```ts
   * // Request all accounts
   * wseApi.requestAccountSnapshot();
   *
   * // Request accounts for specific broker
   * wseApi.requestAccountSnapshot({ brokerId: 'alpaca', environment: 'paper' });
   * ```
   */
  requestAccountSnapshot: (options?: SnapshotRequestOptions) => void;

  /**
   * Request automation/strategies snapshot
   *
   * Triggers backend to send `automation_snapshot` event.
   */
  requestAutomationSnapshot: () => void;

  /**
   * Request order snapshot
   *
   * Triggers backend to send `order_snapshot` event with all orders.
   *
   * Use cases:
   * - Initial page load
   * - Manual refresh
   * - After order placement/cancellation
   *
   * @param options Optional filters
   * @returns void (response arrives via WebSocket event)
   *
   * @example
   * ```ts
   * // Request all orders
   * wseApi.requestOrderSnapshot();
   *
   * // Request orders for specific account
   * wseApi.requestOrderSnapshot({ accountId: 'acc-123' });
   * ```
   */
  requestOrderSnapshot: (options?: { accountId?: string }) => void;

  /**
   * Request all snapshots (broker + accounts + automation)
   *
   * Convenient shorthand for full state refresh.
   *
   * @param options Optional filters applied to all requests
   */
  requestAllSnapshots: (options?: SnapshotRequestOptions) => void;

  // ──────────────────────────────────────────────────────────────────────
  // Topic Subscriptions
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Subscribe to event topics
   *
   * @param topics Array of topic names to subscribe
   *
   * Available topics:
   * - 'broker_connection_events' - Broker connect/disconnect/status
   * - 'broker_account_events' - Account balance/equity/positions
   * - 'automation_events' - Automation strategy updates
   * - 'order_events' - Order fills/cancellations
   * - 'position_events' - Position updates
   * - 'market_data_events' - Real-time quotes/trades
   * - 'system_events' - System health/announcements
   *
   * @example
   * ```ts
   * wseApi.subscribe(['broker_connection_events', 'broker_account_events']);
   * ```
   */
  subscribe: (topics: string[]) => void;

  /**
   * Unsubscribe from event topics
   *
   * @param topics Array of topic names to unsubscribe
   */
  unsubscribe: (topics: string[]) => void;

  // ──────────────────────────────────────────────────────────────────────
  // Direct Messaging
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Send generic WebSocket message
   *
   * Low-level API for custom message types.
   * Prefer typed methods above when available.
   *
   * @param type Message type (e.g., 'request_broker_snapshot')
   * @param payload Message payload
   * @param options Message options (priority, ACK, timeout)
   *
   * @example
   * ```ts
   * wseApi.sendMessage('custom_request', { key: 'value' }, {
   *   priority: MessagePriority.HIGH,
   *   requiresAck: true,
   *   timeout: 5000
   * });
   * ```
   */
  sendMessage: (type: string, payload: any, options?: MessageOptions) => void;

  // ──────────────────────────────────────────────────────────────────────
  // Connection Control
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Force WebSocket reconnection
   *
   * Closes current connection and initiates new connection.
   * Useful for recovering from error states.
   *
   * @example
   * ```ts
   * // Recover from connection error
   * if (wseApi.getConnectionStatus().status === 'error') {
   *   wseApi.forceReconnect();
   * }
   * ```
   */
  forceReconnect: () => void;

  // Note: forceDisconnect not available in current WSE implementation
  // Use forceReconnect if connection recovery needed

  // ──────────────────────────────────────────────────────────────────────
  // Status & Diagnostics
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Check if WebSocket is connected
   *
   * @returns true if connection status is 'connected'
   *
   * @example
   * ```ts
   * if (wseApi.isConnected()) {
   *   wseApi.requestAccountSnapshot();
   * } else {
   *   console.warn('WebSocket not connected, skipping snapshot request');
   * }
   * ```
   */
  isConnected: () => boolean;

  /**
   * Get detailed connection status
   *
   * @returns Connection status with latency, heartbeat, reconnect attempts
   *
   * @example
   * ```ts
   * const status = wseApi.getConnectionStatus();
   * console.log(`Status: ${status.status}, Latency: ${status.latency}ms`);
   * ```
   */
  getConnectionStatus: () => ConnectionStatus;

  /**
   * Export diagnostics data to JSON file
   *
   * Downloads comprehensive diagnostics including:
   * - Connection state and health
   * - Message queue stats
   * - Circuit breaker state
   * - Event handler registration
   * - Network metrics
   * - Error history
   *
   * @example
   * ```ts
   * // User clicks "Export Diagnostics" button
   * wseApi.downloadDiagnostics();
   * ```
   */
  downloadDiagnostics: () => void;
}

// ============================================================================
// WSE API Implementation
// ============================================================================

/**
 * Create WSE API instance
 *
 * Factory function that wraps useWSE hook with clean interface.
 * Should not be called directly - use `useWSEApi()` hook instead.
 *
 * @param wse WSE context from useWSEContext()
 * @returns WSE API interface
 * @internal
 */
export const createWSEApi = (wse: ReturnType<typeof useWSEContext>): WSEApi => {
  // Validate WSE context
  if (!wse || typeof wse.sendMessage !== 'function') {
    logger.error('Invalid WSE context provided to createWSEApi');
    throw new Error('WSE context not available. Ensure component is wrapped in <WSEProvider>.');
  }

  return {
    // ────────────────────────────────────────────────────────────────────
    // Snapshot Requests
    // ────────────────────────────────────────────────────────────────────

    requestBrokerSnapshot: (options?: SnapshotRequestOptions) => {
      logger.info('[WSE API] Requesting broker snapshot', options);

      wse.sendMessage(
        'request_broker_snapshot',
        {
          broker_id: options?.brokerId,
          environment: options?.environment,
          include_details: options?.includeDetails ?? false,
        },
        { priority: MessagePriority.HIGH }
      );
    },

    requestAccountSnapshot: (options?: SnapshotRequestOptions) => {
      logger.info('[WSE API] Requesting account snapshot', options);

      wse.sendMessage(
        'request_account_snapshot',
        {
          broker_id: options?.brokerId,
          environment: options?.environment,
          include_details: options?.includeDetails ?? false,
        },
        { priority: MessagePriority.HIGH }
      );
    },

    requestAutomationSnapshot: () => {
      logger.info('[WSE API] Requesting automation snapshot');

      wse.sendMessage(
        'request_automation_snapshot',
        {},
        { priority: MessagePriority.HIGH }
      );
    },

    requestOrderSnapshot: (options?: { accountId?: string }) => {
      logger.info('[WSE API] Requesting order snapshot', options);

      wse.sendMessage(
        'request_order_snapshot',
        {
          account_id: options?.accountId,
        },
        { priority: MessagePriority.HIGH }
      );
    },

    requestAllSnapshots: (options?: SnapshotRequestOptions) => {
      logger.info('[WSE API] Requesting all snapshots', options);

      // Send all snapshot requests in parallel
      wse.sendMessage('request_broker_snapshot', {
        broker_id: options?.brokerId,
        environment: options?.environment,
        include_details: options?.includeDetails ?? false,
      }, { priority: MessagePriority.HIGH });

      wse.sendMessage('request_account_snapshot', {
        broker_id: options?.brokerId,
        environment: options?.environment,
        include_details: options?.includeDetails ?? false,
      }, { priority: MessagePriority.HIGH });

      wse.sendMessage('request_automation_snapshot', {}, { priority: MessagePriority.HIGH });
    },

    // ────────────────────────────────────────────────────────────────────
    // Topic Subscriptions
    // ────────────────────────────────────────────────────────────────────

    subscribe: (topics: string[]) => {
      logger.info('[WSE API] Subscribing to topics', topics);

      wse.sendMessage(
        'subscription_update',
        {
          action: 'subscribe',
          topics,
        },
        { priority: MessagePriority.HIGH }
      );
    },

    unsubscribe: (topics: string[]) => {
      logger.info('[WSE API] Unsubscribing from topics', topics);

      wse.sendMessage(
        'subscription_update',
        {
          action: 'unsubscribe',
          topics,
        },
        { priority: MessagePriority.NORMAL }
      );
    },

    // ────────────────────────────────────────────────────────────────────
    // Direct Messaging
    // ────────────────────────────────────────────────────────────────────

    sendMessage: (type: string, payload: any, options?: MessageOptions) => {
      logger.debug('[WSE API] Sending message', { type, payload, options });

      wse.sendMessage(type, payload, options);
    },

    // ────────────────────────────────────────────────────────────────────
    // Connection Control
    // ────────────────────────────────────────────────────────────────────

    forceReconnect: () => {
      logger.info('[WSE API] Force reconnect requested');

      if (typeof wse.forceReconnect === 'function') {
        wse.forceReconnect();
      } else {
        logger.error('[WSE API] forceReconnect not available in WSE context');
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Status & Diagnostics
    // ────────────────────────────────────────────────────────────────────

    isConnected: () => {
      return wse.isConnected;
    },

    getConnectionStatus: () => {
      return {
        status: wse.isConnected ? 'connected' : 'disconnected',
        health: wse.connectionHealth,
        diagnostics: wse.diagnostics,
      };
    },

    downloadDiagnostics: () => {
      logger.info('[WSE API] Downloading diagnostics');

      if (typeof wse.downloadDiagnostics === 'function') {
        wse.downloadDiagnostics();
      } else {
        logger.error('[WSE API] downloadDiagnostics not available in WSE context');
      }
    },
  };
};

// ============================================================================
// React Hook
// ============================================================================

/**
 * Hook for accessing WSE API
 *
 * Provides clean, typed interface for WebSocket operations.
 * Memoized to prevent unnecessary re-creations.
 *
 * @returns WSE API interface
 * @throws Error if not wrapped in <WSEProvider>
 *
 * @example
 * ```tsx
 * const MyComponent = () => {
 *   const wseApi = useWSEApi();
 *
 *   useEffect(() => {
 *     // Request initial snapshot on mount
 *     if (wseApi.isConnected()) {
 *       wseApi.requestBrokerSnapshot();
 *     }
 *   }, [wseApi]);
 *
 *   const handleRefresh = () => {
 *     wseApi.requestAllSnapshots();
 *   };
 *
 *   return (
 *     <button onClick={handleRefresh}>
 *       Refresh
 *     </button>
 *   );
 * };
 * ```
 */
export const useWSEApi = (): WSEApi => {
  const wse = useWSEContext();

  // Memoize API instance to prevent re-creation on every render
  const api = useMemo(() => {
    try {
      return createWSEApi(wse);
    } catch (error) {
      logger.error('[useWSEApi] Failed to create WSE API', error);
      throw error;
    }
  }, [wse]);

  return api;
};

// ============================================================================
// Future: Convenience Hooks (Coming Soon)
// ============================================================================

// TODO: Add convenience hooks for auto-requesting snapshots
// export const useRequestBrokerSnapshot = (options?, deps?) => { ... }
// export const useRequestAccountSnapshot = (options?, deps?) => { ... }

// ============================================================================
// Exports
// ============================================================================

export default useWSEApi;

/**
 * Re-export MessagePriority for convenience
 */
export { MessagePriority };
