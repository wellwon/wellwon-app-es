// =============================================================================
// File: src/wse/hooks/useWSE.ts
// Description: WebSocket Event System hook with industrial-standard token handling
// =============================================================================

import { useEffect, useRef, useCallback, useMemo } from 'react';
import {
  UseWSEReturn,
  WSEConfig,
  MessageOptions,
  MessagePriority,
  ConnectionState,
  WSMessage,
  CircuitBreakerState,
} from '@/wse';
import {
  getEndpoints,
  getSavedSubscriptions,
  saveSubscriptions,
} from '@/wse';
import { useWSEStore } from '@/wse';
import { useMessageQueueStore } from '@/wse';
import { ConnectionManager } from '../services/ConnectionManager';
import { MessageProcessor } from '../services/MessageProcessor';
import { NetworkMonitor } from '../services/NetworkMonitor';
import { OfflineQueue } from '../services/OfflineQueue';
import { EventHandlers } from '../handlers/EventHandlers';
import { logger } from '@/wse';

// Default configuration matching backend expectations
const DEFAULT_CONFIG: Partial<WSEConfig> = {
  endpoints: [],
  reconnection: {
    mode: 'adaptive',
    baseDelay: 1000,
    maxDelay: 30000,
    maxAttempts: 10,
    factor: 1.5,
    jitter: true,
  },
  security: {
    encryptionEnabled: false,
    messageSignature: false,
  },
  performance: {
    batchSize: 10,
    batchTimeout: 100,
    compressionThreshold: 1024,
    maxQueueSize: 10000,
    memoryLimit: 50 * 1024 * 1024,
  },
  offline: {
    enabled: true,
    maxSize: 1000,
    maxAge: 3600000,
    persistToStorage: true,
  },
  diagnostics: {
    enabled: true,
    sampleRate: 0.1,
    metricsInterval: 60000,
    healthCheckInterval: 30000,
  },
};

const CRITICAL_HANDLERS = [
  'user_account_update',
  'entity_update',
  'system_announcement',
  'system_status'
];

const SNAPSHOT_DEBOUNCE_TIME = 2000; // 2 seconds
let lastSnapshotTime = 0;

// Global instance management with proper cleanup tracking
interface GlobalWSEInstance {
  token: string;
  connectionManager: ConnectionManager | null;
  messageProcessor: MessageProcessor | null;
  networkMonitor: NetworkMonitor | null;
  offlineQueue: OfflineQueue | null;
  initPromise: Promise<void> | null;
  cleanupFunction: (() => void) | null;
  destroyed: boolean;
}

let globalWSEInstance: GlobalWSEInstance | null = null;

// Cleanup tracking
const activeCleanups = new WeakMap<object, () => void>();

// Circuit breaker check interval
let circuitBreakerCheckInterval: NodeJS.Timeout | null = null;

// Event deduplication at the module level
const processedEvents = new Map<string, number>();
const EVENT_CACHE_TIME = 60 * 1000; // 1 minute
const MAX_CACHED_EVENTS = 100;

// Cleanup old processed events
function cleanupProcessedEvents() {
  const now = Date.now();
  const entriesToDelete: string[] = [];

  for (const [eventId, timestamp] of processedEvents.entries()) {
    if (now - timestamp > EVENT_CACHE_TIME) {
      entriesToDelete.push(eventId);
    }
  }

  entriesToDelete.forEach(id => processedEvents.delete(id));

  if (processedEvents.size > MAX_CACHED_EVENTS) {
    const entries = Array.from(processedEvents.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_CACHED_EVENTS);

    processedEvents.clear();
    entries.forEach(([id, timestamp]) => processedEvents.set(id, timestamp));
  }
}

// Run cleanup every 30 seconds
const cleanupInterval = setInterval(cleanupProcessedEvents, 30000);

// Cleanup on module unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    clearInterval(cleanupInterval);

    // Force cleanup of global instance
    if (globalWSEInstance && !globalWSEInstance.destroyed) {
      logger.info('[useWSE] Window unload - cleaning up global instance');
      destroyGlobalInstance();
    }
  });
}

// Global connection start time tracking
declare global {
  interface Window {
    __wseConnectionStartTime?: number;
    __wseAuthEvents?: Set<string>;
    __wseLastStates?: Record<string, any>;
    __pendingBrokerDisconnects?: Set<string>;
  }
}

// Helper function to destroy global instance
function destroyGlobalInstance(): void {
  if (!globalWSEInstance) return;

  logger.info('[useWSE] Destroying global WSE instance');

  globalWSEInstance.destroyed = true;

  // Call cleanup function if exists
  if (globalWSEInstance.cleanupFunction) {
    try {
      globalWSEInstance.cleanupFunction();
    } catch (e) {
      logger.error('[useWSE] Error calling cleanup function:', e);
    }
  }

  // Destroy services
  try {
    if (globalWSEInstance.connectionManager) {
      globalWSEInstance.connectionManager.destroy();
      globalWSEInstance.connectionManager = null;
    }
  } catch (e) {
    logger.error('[useWSE] Error destroying connection manager:', e);
  }

  try {
    if (globalWSEInstance.messageProcessor) {
      globalWSEInstance.messageProcessor.destroy();
      globalWSEInstance.messageProcessor = null;
    }
  } catch (e) {
    logger.error('[useWSE] Error destroying message processor:', e);
  }

  try {
    if (globalWSEInstance.networkMonitor) {
      globalWSEInstance.networkMonitor.destroy();
      globalWSEInstance.networkMonitor = null;
    }
  } catch (e) {
    logger.error('[useWSE] Error destroying network monitor:', e);
  }

  try {
    if (globalWSEInstance.offlineQueue) {
      globalWSEInstance.offlineQueue.destroy();
      globalWSEInstance.offlineQueue = null;
    }
  } catch (e) {
    logger.error('[useWSE] Error destroying offline queue:', e);
  }

  globalWSEInstance = null;
}

export function useWSE(
  token?: string,
  initialTopics?: string[],
  config?: Partial<WSEConfig>
): UseWSEReturn {
  // Industrial standard: Only check token existence, no validation
  const validToken = useMemo(() => {
    if (!token || token.trim() === '') {
      logger.debug('WSE: No token provided');
      return undefined;
    }

    logger.debug('WSE: Token provided, length:', token.length);
    return token;
  }, [token]);

  // Stores
  const store = useWSEStore();
  const queueStore = useMessageQueueStore();

  // Services refs
  const connectionManagerRef = useRef<ConnectionManager | null>(null);
  const messageProcessorRef = useRef<MessageProcessor | null>(null);
  const networkMonitorRef = useRef<NetworkMonitor | null>(null);
  const offlineQueueRef = useRef<OfflineQueue | null>(null);

  // Track initialization and subscription state
  const initializedRef = useRef(false);
  const processingBatchRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const subscriptionsConfirmedRef = useRef(false);
  const snapshotRequestedRef = useRef(false);
  const handlersReadyRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const initialSyncSentRef = useRef(false);

  // Track received snapshots to prevent duplicates
  const snapshotsReceivedRef = useRef({
    broker: false,
    account: false,
  });

  // Track current token to detect changes
  const currentTokenRef = useRef<string | undefined>(null);
  const instanceKeyRef = useRef<symbol>(Symbol('wse-instance'));

  // Add timestamp tracking for rate limiting
  const lastEventTimestampRef = useRef<Map<string, number>>(new Map());
  const EVENT_THROTTLE_MS = 500; // Throttle events to 2 per second per type

  // Memoize config with stable reference
  const finalConfig = useMemo<WSEConfig>(() => {
    const endpoints = config?.endpoints || getEndpoints();
    return {
      endpoints: endpoints.length > 0 ? endpoints : ['ws://localhost:5002/wse'],
      reconnection: {
        ...DEFAULT_CONFIG.reconnection!,
        ...config?.reconnection,
        maxAttempts: config?.reconnection?.maxAttempts === -1
          ? 10
          : (config?.reconnection?.maxAttempts || DEFAULT_CONFIG.reconnection!.maxAttempts!)
      },
      security: { ...DEFAULT_CONFIG.security!, ...config?.security },
      performance: { ...DEFAULT_CONFIG.performance!, ...config?.performance },
      offline: { ...DEFAULT_CONFIG.offline!, ...config?.offline },
      diagnostics: { ...DEFAULT_CONFIG.diagnostics!, ...config?.diagnostics },
    };
  }, [config?.endpoints?.join(','), config?.reconnection, config?.security, config?.performance, config?.offline, config?.diagnostics]);

  // Stable callback refs
  const stableCallbacks = useRef({
    onMessage: null as ((data: string | ArrayBuffer) => void) | null,
    onStateChange: null as ((state: ConnectionState) => void) | null,
    onServerReady: null as ((details: any) => void) | null,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Circuit Breaker Management
  // ─────────────────────────────────────────────────────────────────────────

  const startCircuitBreakerCheck = useCallback(() => {
    if (circuitBreakerCheckInterval) return;

    circuitBreakerCheckInterval = setInterval(() => {
      store.checkCircuitBreakerTimeout();

      // Check if we can reconnect after circuit breaker timeout
      if (store.canReconnect() && store.connectionState === ConnectionState.ERROR) {
        const manager = connectionManagerRef.current;
        if (manager && validToken) {
          logger.info('Circuit breaker timeout reached, attempting reconnection');
          manager.connect(validToken, store.activeTopics).catch(error => {
            logger.error('Auto-reconnection after circuit breaker timeout failed:', error);
          });
        }
      }
    }, 5000); // Check every 5 seconds
  }, [store, validToken]);

  const stopCircuitBreakerCheck = useCallback(() => {
    if (circuitBreakerCheckInterval) {
      clearInterval(circuitBreakerCheckInterval);
      circuitBreakerCheckInterval = null;
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Handler Registration Helper
  // ─────────────────────────────────────────────────────────────────────────

  const ensureHandlersRegistered = useCallback(async (retries = 3): Promise<boolean> => {
    const processor = messageProcessorRef.current;
    if (!processor) {
      logger.error('Message processor not available');
      return false;
    }

    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        // Check if all critical handlers are registered
        const registeredHandlers = processor.getRegisteredHandlers();
        const missingHandlers = CRITICAL_HANDLERS.filter(h => !registeredHandlers.includes(h));

        if (missingHandlers.length === 0) {
          handlersReadyRef.current = true;
          processor.setReady(true);
          logger.info('All critical handlers are registered and ready');
          return true;
        }

        logger.warn(`Attempt ${attempt + 1}: Missing handlers:`, missingHandlers);

        // Re-register all handlers
        EventHandlers.registerAll(processor);

        // Wait a bit before checking again
        await new Promise(resolve => setTimeout(resolve, 100 * (attempt + 1)));

      } catch (error) {
        logger.error(`Handler registration attempt ${attempt + 1} failed:`, error);
      }
    }

    logger.error('Failed to register all critical handlers after retries');
    return false;
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Queue Processing
  // ─────────────────────────────────────────────────────────────────────────

  const processOfflineQueue = useCallback(async () => {
    const offlineQueue = offlineQueueRef.current;
    const connection = connectionManagerRef.current;

    if (!offlineQueue || !connection || !connection.isReady()) return;

    try {
      const messages = await offlineQueue.getAll();
      logger.info(`Processing ${messages.length} offline messages`);

      for (const message of messages) {
        const sent = connection.send(message);
        if (!sent) {
          await offlineQueue.enqueue(message);
          break;
        }
      }

      await offlineQueue.clear();
    } catch (error) {
      logger.error('Error processing offline queue:', error);
    }
  }, []);

  const processBatch = useCallback(async () => {
    if (processingBatchRef.current) return;
    processingBatchRef.current = true;

    try {
      const processor = messageProcessorRef.current;
      const connection = connectionManagerRef.current;
      const offlineQueue = offlineQueueRef.current;

      if (!processor || !connection) return;

      const messages = await processor.processBatch();
      for (const message of messages) {
        const sent = connection.send(message);
        if (!sent && offlineQueue) {
          await offlineQueue.enqueue(message);
        }
      }
    } catch (error) {
      logger.error('Error processing batch:', error);
    } finally {
      processingBatchRef.current = false;
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────

  const sendMessage = useCallback((
    type: string,
    payload: any,
    options: MessageOptions = {}
  ) => {
    // Create the message first
    const message: WSMessage = {
      t: type,
      p: payload,
      id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      v: 2,
    };

    if (options.priority) message.pri = options.priority;
    if (options.correlation_id) message.cid = options.correlation_id;
    if (options.encrypted) message.enc = true;

    // Check if we're fully initialized
    if (!initializedRef.current || !messageProcessorRef.current || !connectionManagerRef.current) {
      logger.debug('WSE not fully initialized, queueing message for later');

      // Queue the message with a retry mechanism
      const retryCount = 5;
      let attempts = 0;

      const tryToSend = () => {
        attempts++;

        if (attempts > retryCount) {
          logger.error(`Failed to send queued message after retries:`, {
            messageType: type,
            payload: payload,
            attempts: attempts
          });
          return;
        }

        const processor = messageProcessorRef.current;
        const connection = connectionManagerRef.current;


        if (processor && connection && connection.isReady()) {
          // Try to send even if not fully ready for critical messages
          const isCriticalMessage = ['subscription_update', 'sync_request', 'client_hello'].includes(type);

          if (connection.isConnected() && (connection.isReady() || isCriticalMessage)) {
            // We're ready now, send it
            try {
              logger.debug(`Attempting to send queued message ${type} (attempt ${attempts})`);
              const sent = connection.send(message);
              if (!sent) {
                // If send returns false, queue it for processing
                processor.queueOutgoing(message, options.priority || MessagePriority.NORMAL);
              }
              logger.info(`Queued message ${type} sent successfully after ${attempts} attempts`);
              return; // Success, exit retry loop
            } catch (error) {
              logger.error(`Error sending queued message ${type}:`, error);
              // Continue to retry logic below
            }
          } else {
            logger.debug(`Connection not ready for ${type}, isConnected: ${connection.isConnected()}, isReady: ${connection.isReady()}`);
          }
        }

        // Still not ready or failed, try again
        const delay = Math.min(100 * Math.pow(2, attempts - 1), 2000);
        logger.debug(`Retrying ${type} in ${delay}ms (attempt ${attempts}/${retryCount})`);
        setTimeout(tryToSend, delay);
      };

      // Start the retry process
      setTimeout(tryToSend, 100);
      return;
    }

    // Normal send logic for when already initialized
    const processor = messageProcessorRef.current;
    const connection = connectionManagerRef.current;
    const offlineQueue = offlineQueueRef.current;

    // Try to send immediately if connected
    if (connection?.isReady()) {
      try {
        const sent = connection.send(message);
        if (!sent) {
          processor.queueOutgoing(message, options.priority || MessagePriority.NORMAL);
        }
      } catch (error) {
        logger.error('Error sending message:', error);
        // Queue for later delivery
        processor.queueOutgoing(message, options.priority || MessagePriority.NORMAL);
      }
    } else if (options.offline && offlineQueue) {
      // Queue offline
      offlineQueue.enqueue(message).catch(error => {
        logger.error('Failed to enqueue offline message:', error);
      });
    } else {
      // Queue for later delivery
      processor.queueOutgoing(message, options.priority || MessagePriority.NORMAL);
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Message Handling Callbacks with Enhanced Deduplication
  // ─────────────────────────────────────────────────────────────────────────

  const handleIncomingMessage = useCallback((data: string | ArrayBuffer) => {
    const processor = messageProcessorRef.current;
    const monitor = networkMonitorRef.current;

    if (!processor || !monitor) return;

    // Pre-parse to check for duplicates and throttling
    try {
      let parsed: any;

      if (typeof data === 'string') {
        // Skip PING/PONG messages
        if (data.toUpperCase().startsWith('PING') || data.startsWith('PONG:')) {
          processor.processIncoming(data).catch(error => {
            logger.error('Failed to process ping/pong:', error);
          });
          return;
        }

        parsed = JSON.parse(data);
      } else {
        // For binary data, we need to parse it first
        const view = new Uint8Array(data);

        // Check compression header 'C':
        if (view.length >= 2 && view[0] === 67 && view[1] === 58) {
          // This is compressed, we can't easily check without decompressing
          // Let the processor handle it
          processor.processIncoming(data).catch(error => {
            logger.error('Failed to process compressed message:', error);
          });
          return;
        }

        // Try to parse as JSON
        try {
          const text = new TextDecoder().decode(data);
          parsed = JSON.parse(text);
        } catch {
          // Can't parse, let processor handle it
          processor.processIncoming(data).catch(error => {
            logger.error('Failed to process binary message:', error);
          });
          return;
        }
      }

      // Age filtering
      if (parsed && parsed.ts) {
        const eventTime = new Date(parsed.ts).getTime();
        const now = Date.now();
        const age = now - eventTime;
        const eventType = parsed.t;

        // Define what's considered "old" based on event type and connection state
        const connectionTime = Date.now() - (window.__wseConnectionStartTime || Date.now());
        const isNewConnection = connectionTime < 5000; // First 5 seconds

        // During new connection, be very strict about old events
        if (isNewConnection) {
          // Snapshots are always allowed
          if (eventType && eventType.includes('snapshot')) {
            logger.debug(`Accepting ${eventType} snapshot during new connection`);
          } else if (age > 1000) { // Only accept events < 1 second old
            logger.debug(`Rejecting old ${eventType} event during new connection (${Math.round(age / 1000)}s old)`);
            return;
          }
        } else {
          // After connection established, normal filtering
          // NOTE: Health and connection updates can be delayed by backend processing
          // Allow longer age window to prevent rejecting valid incremental updates
          const maxAge = eventType && (
            eventType.includes('snapshot') ||
            eventType.includes('health_update') ||
            eventType.includes('connection_update')
          ) ? 60000 : 5000;
          if (age > maxAge) {
            logger.debug(`Rejecting old ${eventType} event (${Math.round(age / 1000)}s old)`);
            return;
          }
        }
      }

      // Check event ID for deduplication
      if (parsed && parsed.id) {
        // Check size BEFORE adding
        if (processedEvents.size >= MAX_CACHED_EVENTS) {
          // Remove oldest immediately
          const oldestKey = processedEvents.keys().next().value;
          if (oldestKey) processedEvents.delete(oldestKey);
        }

        // Global deduplication
        if (processedEvents.has(parsed.id)) {
          logger.debug(`Skipping globally duplicate event: ${parsed.id}`);
          return;
        }
        processedEvents.set(parsed.id, Date.now());
      }

      // Check event type throttling
      if (parsed && parsed.t) {
        const eventType = parsed.t;
        const now = Date.now();
        const lastTimestamp = lastEventTimestampRef.current.get(eventType) || 0;

        // Smart throttling based on event type and state
        let throttleMs = EVENT_THROTTLE_MS;

        // Less aggressive throttling to ensure real-time updates
        if (eventType === 'heartbeat') {
          throttleMs = 5000; // 5 seconds for heartbeats
        } else if (eventType === 'market_data_update') {
          throttleMs = 100; // 100ms for market data
        } else if (eventType.includes('snapshot')) {
          throttleMs = 0; // No throttling for snapshots
        } else if (eventType === 'health_check' || eventType === 'health_check_response') {
          throttleMs = 10000; // 10 seconds for health checks
        } else if (eventType === 'performance_metrics' || eventType === 'metrics_response') {
          throttleMs = 60000; // 1 minute for metrics
        }

        if (throttleMs > 0 && (now - lastTimestamp) < throttleMs) {
          logger.debug(`Throttling ${eventType} event (last: ${now - lastTimestamp}ms ago)`);
          return;
        }

        lastEventTimestampRef.current.set(eventType, now);
      }

      // Special handling for broker connection updates during startup
      if (parsed && parsed.t === 'broker_connection_update' && !subscriptionsConfirmedRef.current) {
        // During startup, only process the first update per broker connection
        const connectionId = parsed.p?.broker_connection_id;
        if (connectionId) {
          const processedKey = `startup_broker_${connectionId}`;
          if (processedEvents.has(processedKey)) {
            logger.debug(`Skipping duplicate startup broker update for ${connectionId}`);
            return;
          }
          processedEvents.set(processedKey, Date.now());
        }
      }

      // Additional deduplication for account updates
      if (parsed && parsed.t === 'account_update') {
        const accountId = parsed.p?.id || parsed.p?.account_id;
        if (accountId) {
          const accountKey = `account_${accountId}_update`;
          const lastAccountUpdate = lastEventTimestampRef.current.get(accountKey) || 0;
          const now = Date.now();

          // Throttle account updates to once per 5 seconds per account
          if (now - lastAccountUpdate < 5000) {
            logger.debug(`Throttling account update for ${accountId}`);
            return;
          }

          lastEventTimestampRef.current.set(accountKey, now);
        }
      }

    } catch (e) {
      // If we can't parse for deduplication, still process the message
      logger.debug('Could not pre-parse message for deduplication:', e);
    }

    // Record metrics
    monitor.recordPacketReceived();
    if (data instanceof ArrayBuffer) {
      monitor.recordBytes(data.byteLength);
    } else {
      monitor.recordBytes(new Blob([data]).size);
    }

    // Process the message
    processor.processIncoming(data).catch(error => {
      logger.error('Failed to process incoming message:', error);
    });
  }, []);

  const handleStateChange = useCallback((state: ConnectionState) => {
    store.setConnectionState(state);

    if (state === ConnectionState.CONNECTED) {
      reconnectAttemptsRef.current = 0;
      store.resetCircuitBreaker();

      ensureHandlersRegistered().then((ready) => {
        if (ready) {
          processOfflineQueue();
        }
      });
    } else if (state === ConnectionState.ERROR) {
      startCircuitBreakerCheck();
    }
  }, [store, processOfflineQueue, ensureHandlersRegistered, startCircuitBreakerCheck]);

  const requestInitialSnapshot = useCallback(async (retries = 3, delay = 1000) => {
    if (snapshotRequestedRef.current) {
      logger.info('Snapshot already requested, skipping duplicate');
      return;
    }

    const handlersReady = await ensureHandlersRegistered();
    if (!handlersReady) {
      logger.error('Cannot request snapshot - handlers not ready');
      return;
    }

    for (let i = 0; i < retries; i++) {
      try {
        if (i > 0) {
          const waitTime = delay * Math.pow(2, i - 1);
          logger.info(`Waiting ${waitTime}ms before retry ${i + 1}/${retries}`);
          await new Promise(resolve => setTimeout(resolve, waitTime));
        }

        logger.info(`=== REQUESTING INITIAL SNAPSHOTS (Attempt ${i + 1}/${retries}) ===`);
        logger.info('Topics for snapshot:', ['user_account_events', 'system_events']);

        // Request snapshot without historical events
        sendMessage('sync_request', {
          topics: ['user_account_events', 'system_events'],
          include_snapshots: true,
          include_history: false, // Don't include historical events
          last_sequence: 0,
        }, { priority: MessagePriority.HIGH });

        snapshotRequestedRef.current = true;
        break;
      } catch (error) {
        logger.warn(`Snapshot request attempt ${i + 1} failed:`, error);
        if (i === retries - 1) {
          logger.error('All snapshot request attempts failed');
        }
      }
    }
  }, [sendMessage, ensureHandlersRegistered]);

  const handleServerReady = useCallback((details: any) => {
    logger.info('=== SERVER READY RECEIVED ===');
    logger.info('Server ready details:', details);

    // Clear processed events on new connection
    processedEvents.clear();
    lastEventTimestampRef.current.clear();

    // CRITICAL FIX: Reset the flag on new connection
    initialSyncSentRef.current = false;

    snapshotRequestedRef.current = false;
    snapshotsReceivedRef.current = {
      broker: false,
      account: false,
    };

    const savedTopics = store.activeTopics.length > 0
      ? store.activeTopics
      : (initialTopics || getSavedSubscriptions());

    const topics = [...new Set([...savedTopics, 'user_account_events', 'system_events'])];

    logger.info('Subscribing to topics:', topics);

    // CRITICAL FIX: Only send once
    if (!initialSyncSentRef.current) {
      initialSyncSentRef.current = true;

      setTimeout(() => {
        // Send subscription update
        sendMessage('subscription_update', {
          action: 'subscribe',
          topics,
        }, { priority: MessagePriority.HIGH });

        // CRITICAL FIX (Nov 10, 2025): Request initial snapshot immediately after subscription
        // Backend now auto-sends snapshots after subscription, but this provides redundancy
        // Reduces snapshot delay from 30-60s to <1-2s
        setTimeout(() => {
          logger.info('Requesting initial snapshot after subscription');
          requestInitialSnapshot(3, 1000);
        }, 500); // Small delay to let subscription complete
      }, 200);
    }

    store.setActiveTopics(topics);
    saveSubscriptions(topics);
  }, [store, initialTopics, sendMessage]);

  // Update stable callbacks
  useEffect(() => {
    stableCallbacks.current = {
      onMessage: handleIncomingMessage,
      onStateChange: handleStateChange,
      onServerReady: handleServerReady,
    };
  });

  // Add event listeners for snapshot tracking
  useEffect(() => {
    const handleUserSnapshot = () => {
      snapshotsReceivedRef.current.broker = true; // Reuse existing flag
      subscriptionsConfirmedRef.current = true;
    };

    const handleSystemSnapshot = () => {
      snapshotsReceivedRef.current.account = true; // Reuse existing flag
      subscriptionsConfirmedRef.current = true;
    };

    window.addEventListener('userSnapshotReceived', handleUserSnapshot);
    window.addEventListener('systemSnapshotReceived', handleSystemSnapshot);

    return () => {
      window.removeEventListener('userSnapshotReceived', handleUserSnapshot);
      window.removeEventListener('systemSnapshotReceived', handleSystemSnapshot);
    };
  }, []);

  // Add subscription confirmation handler
  useEffect(() => {
    const handleSubscriptionUpdate = (event: CustomEvent) => {
      const { success, topics } = event.detail;
      if (success && topics?.includes('user_account_events')) {
        logger.info('Subscription confirmed for user_account_events');
        subscriptionsConfirmedRef.current = true;
      }
    };

    window.addEventListener('subscriptionUpdate', handleSubscriptionUpdate as EventListener);
    return () => {
      window.removeEventListener('subscriptionUpdate', handleSubscriptionUpdate as EventListener);
    };
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Main Initialization Effect - FIXED WITH PROPER CLEANUP
  // ─────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    // Track if token changed
    const tokenChanged = currentTokenRef.current !== validToken;

    if (tokenChanged) {
      logger.info('WSE: Token state changed', {
        hadToken: !!currentTokenRef.current,
        hasToken: !!validToken,
        tokenChanged: true
      });

      // CRITICAL: Clean up old instance before proceeding
      if (currentTokenRef.current && globalWSEInstance && globalWSEInstance.token === currentTokenRef.current) {
        logger.info('WSE: Token changed - destroying old global instance');
        destroyGlobalInstance();
      }

      currentTokenRef.current = validToken;
    }

    // No token - cleanup and return
    if (!validToken) {
      if (initializedRef.current && cleanupRef.current) {
        logger.info('WSE: Token removed, cleaning up');
        cleanupRef.current();
        cleanupRef.current = null;
        initializedRef.current = false;

        // Clear global instance if it was ours
        if (globalWSEInstance && !globalWSEInstance.token) {
          destroyGlobalInstance();
        }
      }
      return;
    }

    // Token exists but not changed and already initialized - do nothing
    if (!tokenChanged && initializedRef.current) {
      logger.debug('WSE: Token unchanged and already initialized');
      return;
    }

    // Check if we can reuse existing global instance
    if (globalWSEInstance && globalWSEInstance.token === validToken && !globalWSEInstance.destroyed) {
      logger.info('WSE: Reusing existing global instance');

      // Wait for any pending initialization
      if (globalWSEInstance.initPromise) {
        logger.info('WSE: Waiting for pending initialization');
        globalWSEInstance.initPromise.then(() => {
          if (globalWSEInstance && globalWSEInstance.token === validToken && !globalWSEInstance.destroyed) {
            connectionManagerRef.current = globalWSEInstance.connectionManager;
            messageProcessorRef.current = globalWSEInstance.messageProcessor;
            networkMonitorRef.current = globalWSEInstance.networkMonitor;
            offlineQueueRef.current = globalWSEInstance.offlineQueue;
            initializedRef.current = true;
          }
        });
        return;
      }

      connectionManagerRef.current = globalWSEInstance.connectionManager;
      messageProcessorRef.current = globalWSEInstance.messageProcessor;
      networkMonitorRef.current = globalWSEInstance.networkMonitor;
      offlineQueueRef.current = globalWSEInstance.offlineQueue;
      initializedRef.current = true;
      return;
    }

    // Need to initialize new instance
    logger.info('=== INITIALIZING NEW WSE INSTANCE ===');
    logger.info('Token changed:', tokenChanged);
    logger.info('Previous initialization:', initializedRef.current);

    // Reset all state for new connection
    initializedRef.current = false;
    subscriptionsConfirmedRef.current = false;
    snapshotRequestedRef.current = false;
    handlersReadyRef.current = false;
    reconnectAttemptsRef.current = 0;
    snapshotsReceivedRef.current = { broker: false, account: false };
    initialSyncSentRef.current = false;

    let mounted = true;
    let connectionManager: ConnectionManager | null = null;
    let messageProcessor: MessageProcessor | null = null;
    let networkMonitor: NetworkMonitor | null = null;
    let offlineQueue: OfflineQueue | null = null;
    let batchInterval: NodeJS.Timeout | null = null;
    let diagnosticsInterval: NodeJS.Timeout | null = null;

    const cleanup = () => {
      logger.info('WSE: Cleaning up instance');
      mounted = false;
      initializedRef.current = false;
      subscriptionsConfirmedRef.current = false;
      snapshotRequestedRef.current = false;
      handlersReadyRef.current = false;
      reconnectAttemptsRef.current = 0;
      snapshotsReceivedRef.current = { broker: false, account: false };
      initialSyncSentRef.current = false;

      // Reset connection start time
      delete window.__wseConnectionStartTime;

      stopCircuitBreakerCheck();

      if (batchInterval) {
        clearInterval(batchInterval);
        batchInterval = null;
      }
      if (diagnosticsInterval) {
        clearInterval(diagnosticsInterval);
        diagnosticsInterval = null;
      }

      // Don't destroy services here - they're managed by global instance
      connectionManagerRef.current = null;
      messageProcessorRef.current = null;
      networkMonitorRef.current = null;
      offlineQueueRef.current = null;

      // Clear stores
      store.reset();
      queueStore.clearQueue();

      logger.info('WSE: Cleanup complete');
    };

    const initializeServices = async () => {
      try {
        // Track connection start time
        window.__wseConnectionStartTime = Date.now();

        // Initialize message processor FIRST
        messageProcessor = new MessageProcessor(
          finalConfig.performance.batchSize,
          finalConfig.performance.batchTimeout
        );

        messageProcessorRef.current = messageProcessor;

        // Register all event handlers BEFORE creating connection manager
        EventHandlers.registerAll(messageProcessor);
        logger.info('=== EVENT HANDLERS REGISTERED ===');

        // Verify critical handlers are registered
        try {
          const handlersReady = await messageProcessor.waitForHandlers(CRITICAL_HANDLERS, 5000);
          if (!handlersReady) {
            throw new Error('Failed to register critical handlers within timeout');
          }
        } catch (handlerError) {
          logger.error('Handler registration failed:', handlerError);
          throw new Error(`Failed to register critical handlers: ${(handlerError as Error).message}`);
        }

        handlersReadyRef.current = true;
        messageProcessor.setReady(true);

        const registeredHandlers = messageProcessor.getRegisteredHandlers();
        logger.info('Registered handlers:', registeredHandlers);

        const missingHandlers: string[] = [];
        CRITICAL_HANDLERS.forEach(handler => {
          if (!registeredHandlers.includes(handler)) {
            logger.error(`CRITICAL: ${handler} handler not registered!`);
            missingHandlers.push(handler);
          } else {
            logger.info(`${handler} handler registered successfully`);
          }
        });

        if (missingHandlers.length > 0) {
          throw new Error(`Missing critical handlers: ${missingHandlers.join(', ')}`);
        }

        // Create connection manager with handlers already set up
        connectionManager = new ConnectionManager(
          finalConfig.endpoints,
          finalConfig.reconnection,
          (data) => stableCallbacks.current.onMessage?.(data),
          (state) => {
            handleStateChange(state);
          },
          (details) => stableCallbacks.current.onServerReady?.(details)
        );

        messageProcessor.setConnectionManager(connectionManager);

        networkMonitor = new NetworkMonitor();
        offlineQueue = new OfflineQueue(finalConfig.offline);

        connectionManagerRef.current = connectionManager;
        networkMonitorRef.current = networkMonitor;
        offlineQueueRef.current = offlineQueue;

        // Mark as initialized
        initializedRef.current = true;

        try {
          await offlineQueue.initialize();
          logger.info('Offline queue initialized');
        } catch (offlineError) {
          logger.warn('Offline queue initialization failed:', offlineError);
        }

        const savedTopics = initialTopics || getSavedSubscriptions();
        const topics = [...new Set([...savedTopics, 'user_account_events', 'system_events'])];
        store.setActiveTopics(topics);

        if (!mounted) {
          logger.info('Component unmounted during initialization');
          return;
        }

        // Start circuit breaker check
        startCircuitBreakerCheck();

        logger.info('=== STARTING CONNECTION ===');
        logger.info('Endpoints:', finalConfig.endpoints);
        logger.info('Topics:', topics);

        try {
          await connectionManager.connect(validToken, topics);
        } catch (connectError) {
          logger.error('Connection failed:', connectError);
          // Don't throw here, let the connection manager handle retries
          store.setConnectionState(ConnectionState.ERROR);
          store.setLastError(`Failed to establish WebSocket connection: ${(connectError as Error).message}`);
        }

        if (!mounted) {
          logger.info('Component unmounted after connection');
          return;
        }

        batchInterval = setInterval(() => {
          if (processingBatchRef.current || !mounted) return;
          void processBatch().catch(error => {
            logger.error('Batch processing error:', error);
          });
        }, finalConfig.performance.batchTimeout);

        if (finalConfig.diagnostics.enabled) {
          diagnosticsInterval = setInterval(() => {
            if (!mounted || !networkMonitor) return;
            try {
              const diagnostics = networkMonitor.analyze();
              store.updateDiagnostics(diagnostics);
            } catch (diagError) {
              logger.error('Diagnostics update error:', diagError);
            }
          }, finalConfig.diagnostics.metricsInterval);
        }

        logger.info('=== WSE INITIALIZATION COMPLETE ===');

        // Store cleanup function in global instance
        cleanupRef.current = cleanup;

        // Update global instance after successful initialization
        if (globalWSEInstance && globalWSEInstance.token === validToken) {
          globalWSEInstance.connectionManager = connectionManager;
          globalWSEInstance.messageProcessor = messageProcessor;
          globalWSEInstance.networkMonitor = networkMonitor;
          globalWSEInstance.offlineQueue = offlineQueue;
          globalWSEInstance.cleanupFunction = cleanup;
          globalWSEInstance.initPromise = null;
        }

      } catch (error) {
        logger.error('Failed to initialize WSE:', error);
        initializedRef.current = false;
        store.setConnectionState(ConnectionState.ERROR);
        store.setLastError(error instanceof Error ? error.message : 'Initialization failed');

        // Cleanup any partially initialized services
        try {
          if (connectionManager) connectionManager.destroy();
          if (messageProcessor) messageProcessor.destroy();
          if (networkMonitor) networkMonitor.destroy();
          if (offlineQueue) offlineQueue.destroy();
        } catch (cleanupError) {
          logger.error('Error during cleanup:', cleanupError);
        }

        connectionManagerRef.current = null;
        messageProcessorRef.current = null;
        networkMonitorRef.current = null;
        offlineQueueRef.current = null;

        // Destroy failed global instance
        if (globalWSEInstance?.token === validToken) {
          destroyGlobalInstance();
        }

        throw error;
      }
    };

    // Create initialization promise and set global instance
    const initPromise = initializeServices().catch(error => {
      logger.error('WSE initialization failed:', error);
      cleanup();
    });

    // Set global instance with initialization promise
    globalWSEInstance = {
      token: validToken,
      connectionManager: null,
      messageProcessor: null,
      networkMonitor: null,
      offlineQueue: null,
      initPromise,
      cleanupFunction: null,
      destroyed: false,
    };

    // Cleanup function for this effect
    return () => {
      logger.info('useWSE effect cleanup triggered');

      // If this instance owns the global instance, clean it up
      if (cleanupRef.current && globalWSEInstance && globalWSEInstance.token === validToken) {
        // Check if component is being unmounted due to token change
        if (currentTokenRef.current !== validToken) {
          // Token is changing, destroy immediately
          logger.info('Token changing, destroying global instance immediately');
          destroyGlobalInstance();
        } else {
          // Normal unmount, keep instance alive for potential reuse
          logger.info('Component unmounting, keeping global instance for reuse');
        }
      }

      // Always clean up local references
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, [validToken]); // ONLY depend on validToken

  // ─────────────────────────────────────────────────────────────────────────
  // Public API Implementation
  // ─────────────────────────────────────────────────────────────────────────

  const subscribe = useCallback((topics: string[]) => {
    if (!topics.length) return;

    const currentTopics = store.activeTopics;
    const newTopics = [...new Set([...currentTopics, ...topics])];

    store.setActiveTopics(newTopics);
    saveSubscriptions(newTopics);

    sendMessage('subscription_update', {
      action: 'subscribe',
      topics,
    }, { priority: MessagePriority.HIGH });
  }, [store, sendMessage]);

  const unsubscribe = useCallback((topics: string[]) => {
    if (!topics.length) return;

    const currentTopics = store.activeTopics;
    const newTopics = currentTopics.filter(t => !topics.includes(t));

    store.setActiveTopics(newTopics);
    saveSubscriptions(newTopics);

    sendMessage('subscription_update', {
      action: 'unsubscribe',
      topics,
    }, { priority: MessagePriority.HIGH });
  }, [store, sendMessage]);

  const sendBatch = useCallback((messages: Array<{ type: string; payload: any }>) => {
    messages.forEach(({ type, payload }) => {
      sendMessage(type, payload);
    });
  }, [sendMessage]);

  const forceReconnect = useCallback(() => {
    const manager = connectionManagerRef.current;
    if (manager && validToken) {
      subscriptionsConfirmedRef.current = false;
      snapshotRequestedRef.current = false;
      handlersReadyRef.current = false;
      reconnectAttemptsRef.current = 0;
      snapshotsReceivedRef.current = { broker: false, account: false };
      initialSyncSentRef.current = false;

      // Clear processed events on reconnect
      processedEvents.clear();
      lastEventTimestampRef.current.clear();

      store.resetCircuitBreaker();
      store.updateMetrics({ reconnectCount: 0 });

      manager.disconnect();
      setTimeout(() => {
        manager.connect(validToken, store.activeTopics).catch(error => {
          logger.error('Force reconnection failed:', error);
        });
      }, 100);
    }
  }, [validToken, store]);

  const changeEndpoint = useCallback((endpoint: string) => {
    const manager = connectionManagerRef.current;
    if (manager) {
      subscriptionsConfirmedRef.current = false;
      snapshotRequestedRef.current = false;
      handlersReadyRef.current = false;
      reconnectAttemptsRef.current = 0;
      snapshotsReceivedRef.current = { broker: false, account: false };
      initialSyncSentRef.current = false;

      store.resetCircuitBreaker();
      manager.changeEndpoint(endpoint);
    }
  }, [store]);

  const setEncryption = useCallback((enabled: boolean) => {
    store.updateConfig({ compressionEnabled: enabled });
    logger.info(`Encryption ${enabled ? 'enabled' : 'disabled'}`);
  }, [store]);

  const downloadDiagnostics = useCallback(() => {
    const connection = connectionManagerRef.current;
    const processor = messageProcessorRef.current;
    const diagnostics = {
      timestamp: new Date().toISOString(),
      connection: {
        state: store.connectionState,
        endpoints: store.endpoints,
        activeEndpoint: store.activeEndpoint,
        connectionId: connection?.getConnectionId() || null,
        isReady: connection?.isReady() || false,
        rateLimiter: connection?.getRateLimiterStats() || null,
        connectionPool: connection?.getConnectionPoolStats() || null,
        healthScores: connection?.getHealthScores() || null,
      },
      metrics: store.metrics,
      diagnostics: store.diagnostics,
      circuitBreaker: store.circuitBreaker,
      queue: {
        message: queueStore.stats,
        offline: offlineQueueRef.current?.getStats() || null,
      },
      activeTopics: store.activeTopics,
      errorHistory: store.errorHistory,
      config: finalConfig,
      network: {
        monitor: networkMonitorRef.current?.getLatencyStats() || null,
        lastDiagnostics: networkMonitorRef.current?.getLastDiagnostics() || null,
      },
      handlers: {
        registered: processor?.getRegisteredHandlers() || [],
        subscriptionsConfirmed: subscriptionsConfirmedRef.current,
        snapshotRequested: snapshotRequestedRef.current,
        handlersReady: handlersReadyRef.current,
        snapshotsReceived: snapshotsReceivedRef.current,
        initialSyncSent: initialSyncSentRef.current,
      },
      reconnectAttempts: reconnectAttemptsRef.current,
      deduplication: {
        processedEventsCount: processedEvents.size,
        eventThrottleCounts: Object.fromEntries(lastEventTimestampRef.current),
      },
    };

    const blob = new Blob([JSON.stringify(diagnostics, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `wse-diagnostics-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [store, queueStore, finalConfig]);

  const clearOfflineQueue = useCallback(async () => {
    const offlineQueue = offlineQueueRef.current;
    if (offlineQueue) {
      await offlineQueue.clear();
      logger.info('Offline queue cleared');
    }
  }, []);

  const getQueueSize = useCallback(() => {
    return queueStore.size + (offlineQueueRef.current?.getStats().size || 0);
  }, [queueStore.size]);

  const requestBrokerSnapshot = useCallback(() => {
    logger.info('=== MANUALLY REQUESTING BROKER SNAPSHOT ===');
    snapshotRequestedRef.current = false;
    snapshotsReceivedRef.current.broker = false;
    requestInitialSnapshot(1, 0);
  }, [requestInitialSnapshot]);

  const debugHandlers = useCallback(() => {
    const processor = messageProcessorRef.current;
    if (processor) {
      const handlers = processor.getRegisteredHandlers();
      logger.info('=== CURRENT REGISTERED HANDLERS ===');
      logger.info('Total handlers:', handlers.length);
      logger.info('Handlers:', handlers);

      CRITICAL_HANDLERS.forEach(handler => {
        if (handlers.includes(handler)) {
          logger.info(`${handler} is registered`);
        } else {
          logger.error(`ERROR: ${handler} is NOT registered`);
        }
      });

      logger.info('Subscriptions confirmed:', subscriptionsConfirmedRef.current);
      logger.info('Snapshot requested:', snapshotRequestedRef.current);
      logger.info('Handlers ready:', handlersReadyRef.current);
      logger.info('Snapshots received:', snapshotsReceivedRef.current);
      logger.info('Initial sync sent:', initialSyncSentRef.current);
      logger.info('Circuit breaker:', store.circuitBreaker);
      logger.info('Can reconnect:', store.canReconnect());
      logger.info('Processed events count:', processedEvents.size);
      logger.info('Event throttle states:', Object.fromEntries(lastEventTimestampRef.current));
    } else {
      logger.error('Message processor not initialized');
    }
  }, [store]);

  // ─────────────────────────────────────────────────────────────────────────
  // Return API
  // ─────────────────────────────────────────────────────────────────────────

  return {
    // Connection management
    subscribe,
    unsubscribe,
    forceReconnect,
    changeEndpoint,

    // Messaging
    sendMessage,
    sendBatch,

    // Status & monitoring
    stats: store.metrics,
    activeTopics: store.activeTopics,
    connectionHealth: store.connectionState,
    diagnostics: store.diagnostics,

    // Advanced features
    setEncryption,
    downloadDiagnostics,
    clearOfflineQueue,
    getQueueSize,

    // Broker-specific features
    requestBrokerSnapshot,

    // Debug features
    debugHandlers,
  };
}

// Add debug utilities to window for development
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  (window as any).WSE = {
    getStore: () => useWSEStore.getState(),
    getQueueStore: () => useMessageQueueStore.getState(),
    resetCircuitBreaker: () => {
      const store = useWSEStore.getState();
      store.resetCircuitBreaker();
    },
    forceReconnect: () => {
      const store = useWSEStore.getState();
      store.resetCircuitBreaker();
      window.dispatchEvent(new CustomEvent('wseForceReconnect'));
    },
    forceDisconnect: () => {
      logger.info('[WSE Debug] Force disconnect called');
      if (globalWSEInstance) {
        destroyGlobalInstance();
      }
    },
    enableDebug: () => MessageProcessor.enableDebugMode(true),
    disableDebug: () => MessageProcessor.enableDebugMode(false),
    getDebugLog: () => JSON.parse(sessionStorage.getItem('wse_debug_log') || '[]'),
    clearDebugLog: () => sessionStorage.removeItem('wse_debug_log'),
    checkCanReconnect: () => {
      const store = useWSEStore.getState();
      return store.canReconnect();
    },
    getCircuitBreaker: () => {
      const store = useWSEStore.getState();
      return store.circuitBreaker;
    },
    getProcessedEvents: () => processedEvents,
    clearProcessedEvents: () => processedEvents.clear(),
    getGlobalInstance: () => globalWSEInstance,
    destroyGlobalInstance: () => destroyGlobalInstance(),
  };

  logger.info('WSE debug utilities available at window.WSE');
}