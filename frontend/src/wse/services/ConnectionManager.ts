// =============================================================================
// File: src/wse/services/ConnectionManager.ts
// Description: WebSocket connection management with industrial-standard token handling
// =============================================================================

import {
  ConnectionState,
  WSMessage,
  ReconnectionStrategy,
  MessagePriority,
  MessageCategory,
  WSE_SYSTEM_EVENT_TYPES,
} from '@/wse';
import { useWSEStore } from '@/wse';
import { logger } from '@/wse';
import { RateLimiter } from './RateLimiter';
import { ConnectionPool } from './ConnectionPool';
import { CircuitBreaker } from '@/wse';
import { WS_PROTOCOL_VERSION, WS_CLIENT_VERSION, FEATURES } from '@/wse';
import { refreshToken as refreshAuthToken } from '@/api/user_account';
import { queryClient } from '@/lib/queryClient';
import { AdaptiveQualityManager } from './AdaptiveQualityManager';

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 10;
const MAX_TOKEN_REFRESH_ATTEMPTS = 3;

export class ConnectionManager {
  private ws: WebSocket | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private token: string | null = null;
  private rateLimiter: RateLimiter;
  private serverReady = false;
  private clientHelloSent = false;
  private connectionId: string | null = null;

  // Token management
  private tokenRefreshTimer: NodeJS.Timeout | null = null;
  private tokenExpiresAt: number | null = null;
  private tokenRefreshAttempts = 0;

  // Connection pool
  private connectionPool: ConnectionPool;
  private currentEndpoint: string | null = null;

  // State tracking
  private isDestroyed = false;
  private isConnecting = false;
  private lastConnectionAttempt = 0;
  private consecutiveFailures = 0;

  // Circuit breaker for connection attempts
  private connectionCircuitBreaker: CircuitBreaker;

  // Adaptive quality management
  private adaptiveQuality: AdaptiveQualityManager;

  // Store server ready details temporarily
  private serverReadyDetails: any = null;
  private serverReadyProcessed = false;

  constructor(
    private endpoints: string[],
    private reconnectionStrategy: ReconnectionStrategy,
    private onMessage: (data: string | ArrayBuffer) => void,
    private onStateChange: (state: ConnectionState) => void,
    private onServerReady?: (details: any) => void
  ) {
    this.rateLimiter = new RateLimiter(1000, 100, 1000);

    // FIXED: Initialize the connection pool with only 1 connection per endpoint
    this.connectionPool = new ConnectionPool({
      endpoints: this.endpoints,
      maxPerEndpoint: 1, // Changed from 3 to prevent multiple connections
      healthCheckInterval: 30000,
      loadBalancingStrategy: 'weighted-random',
    });

    // Initialize circuit breaker
    this.connectionCircuitBreaker = new CircuitBreaker({
      failureThreshold: 5,
      resetTimeout: 60000, // 1 minute
      successThreshold: 3,
    });

    // Initialize adaptive quality manager
    this.adaptiveQuality = new AdaptiveQualityManager(queryClient);

    // Log initialization
    logger.info('[ConnectionManager] Initialized with endpoints:', this.endpoints);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Connection Management - Industrial Standard Token Handling
  // ─────────────────────────────────────────────────────────────────────────

  async connect(token: string, topics: string[] = []): Promise<void> {
    // Industrial standard: Only check token existence, no validation
    if (!token) {
      logger.error('[ConnectionManager] No token provided');
      throw new Error('Authentication token required');
    }

    if (this.isDestroyed) {
      throw new Error('ConnectionManager has been destroyed');
    }

    // Prevent concurrent connection attempts
    if (this.isConnecting) {
      logger.warn('[ConnectionManager] Connection already in progress');
      return;
    }

    // If already connected with same token, just return
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.token === token) {
      logger.info('[ConnectionManager] Already connected with this token');
      return;
    }

    // If different token, disconnect first
    if (this.token && this.token !== token && this.ws) {
      logger.info('[ConnectionManager] New token detected, disconnecting existing connection');
      this.disconnect();
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // Rate limit connection attempts
    const now = Date.now();
    const timeSinceLastAttempt = now - this.lastConnectionAttempt;
    const minDelay = this.calculateMinConnectionDelay();

    if (timeSinceLastAttempt < minDelay) {
      const waitTime = minDelay - timeSinceLastAttempt;
      logger.info(`[ConnectionManager] Rate limiting connection attempt, waiting ${waitTime}ms`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }

    this.token = token;
    this.serverReady = false;
    this.clientHelloSent = false;
    this.tokenRefreshAttempts = 0;
    this.lastConnectionAttempt = Date.now();

    // Setup token refresh
    await this.setupTokenRefresh();

    // Use circuit breaker for connection attempts
    try {
      await this.connectionCircuitBreaker.execute(async () => {
        const endpoint = this.selectBestEndpoint();

        if (!endpoint) {
          throw new Error('No available endpoints');
        }

        await this.connectToEndpoint(endpoint, topics);
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage === 'Circuit breaker is OPEN') {
        logger.error('[ConnectionManager] Connection circuit breaker is OPEN - too many failures');
        this.onStateChange(ConnectionState.ERROR);
        const store = useWSEStore.getState();
        store.setLastError('Connection circuit breaker open - too many failures');
      }
      throw error;
    }
  }

  private calculateMinConnectionDelay(): number {
    // Exponential backoff based on consecutive failures
    if (this.consecutiveFailures === 0) return 0;

    const baseDelay = 1000; // 1 second
    const maxDelay = 60000; // 60 seconds
    const delay = Math.min(baseDelay * Math.pow(2, this.consecutiveFailures - 1), maxDelay);

    return delay;
  }

  private async connectToEndpoint(endpoint: string, topics: string[]): Promise<void> {
    if (this.isDestroyed) return;

    // FIXED: Add detailed logging
    logger.info(`[ConnectionManager] Connecting to endpoint: ${endpoint}`);
    logger.info(`[ConnectionManager] Topics: ${topics.join(', ')}`);

    // Set connecting flag
    this.isConnecting = true;

    const store = useWSEStore.getState();

    try {
      // Check if already connected
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        logger.info('[ConnectionManager] WebSocket already open, skipping connection');
        this.isConnecting = false;
        return;
      }

      // FIXED: Close any existing connection properly
      if (this.ws) {
        logger.info('[ConnectionManager] Closing existing WebSocket connection');
        this.ws.close();
        this.ws = null;
        // Wait for close to complete
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      // Update state
      this.onStateChange(ConnectionState.CONNECTING);
      this.currentEndpoint = endpoint;

      // Build URL - Pass token as opaque string (Industrial Standard)
      const url = new URL(endpoint);
      url.searchParams.set('token', this.token || '');
      if (topics.length > 0) {
        url.searchParams.set('topics', topics.join(','));
      }
      url.searchParams.set('client_version', WS_CLIENT_VERSION);
      url.searchParams.set('protocol_version', String(WS_PROTOCOL_VERSION));
      url.searchParams.set('compression', String(FEATURES.COMPRESSION));
      url.searchParams.set('encryption', String(FEATURES.ENCRYPTION));

      // FIXED: Log the full URL for debugging (without token for security)
      const debugUrl = new URL(url);
      debugUrl.searchParams.set('token', '[REDACTED]');
      logger.info(`[ConnectionManager] WebSocket URL: ${debugUrl.toString()}`);

      const connectionStart = Date.now();
      const ws = new WebSocket(url.toString());
      ws.binaryType = 'arraybuffer';

      this.ws = ws;
      this.setupWebSocketHandlers(ws, endpoint);

      // Wait for connection with error handling
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 10000);

        const handleOpen = () => {
          clearTimeout(timeout);
          ws.removeEventListener('open', handleOpen);
          ws.removeEventListener('error', handleError);
          ws.removeEventListener('close', handleClose);
          resolve();
        };

        const handleError = (event: Event) => {
          clearTimeout(timeout);
          ws.removeEventListener('open', handleOpen);
          ws.removeEventListener('error', handleError);
          ws.removeEventListener('close', handleClose);
          reject(new Error('Connection failed'));
        };

        // Listen for immediate close (auth failures from backend)
        const handleClose = (event: CloseEvent) => {
          clearTimeout(timeout);
          ws.removeEventListener('open', handleOpen);
          ws.removeEventListener('error', handleError);
          ws.removeEventListener('close', handleClose);

          // Backend auth validation response codes
          if (event.code === 4401 || event.code === 4403 || event.code === 1008) {
            reject(new Error(`Authentication failed: ${event.reason || 'Invalid token'}`));
          } else {
            reject(new Error(`Connection closed: ${event.reason || 'Unknown reason'}`));
          }
        };

        ws.addEventListener('open', handleOpen);
        ws.addEventListener('error', handleError);
        ws.addEventListener('close', handleClose);
      });

      const connectionTime = Date.now() - connectionStart;

      // Connection successful
      this.onStateChange(ConnectionState.CONNECTED);
      store.setConnectionState(ConnectionState.CONNECTED);
      store.updateMetrics({ connectedSince: Date.now() });

      // FIXED: Don't add multiple connections to the pool
      // The pool should manage this internally
      this.connectionPool.recordSuccess(endpoint, connectionTime);
      this.connectionPool.setActiveEndpoint(endpoint);
      this.connectionCircuitBreaker.recordSuccess();

      // Reset failure tracking
      this.reconnectAttempts = 0;
      this.consecutiveFailures = 0;

      // Start heartbeat
      this.startHeartbeat();

      logger.info(`[ConnectionManager] Connected successfully to ${endpoint} in ${connectionTime}ms`);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('[ConnectionManager] Connection failed:', errorMessage);

      // Record failures
      this.consecutiveFailures++;
      this.connectionPool.recordFailure(endpoint);
      this.connectionCircuitBreaker.recordFailure();

      // Clean up failed connection
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }

      // Handle auth failures from backend
      if (errorMessage.includes('Authentication failed')) {
        this.token = null;
        store.setLastError('Authentication failed', 401);
        store.incrementMetric('authFailures');

        // Dispatch auth failure event
        window.dispatchEvent(new CustomEvent('wseAuthFailed', {
          detail: { reason: 'Backend rejected token' }
        }));
      }

      throw error;
    } finally {
      this.isConnecting = false;
    }
  }

  disconnect(): void {
    logger.info('[ConnectionManager] Disconnect called');

    // Mark as disconnecting to prevent new operations
    this.serverReady = false;
    this.clientHelloSent = false;
    this.connectionId = null;
    this.isConnecting = false;
    this.serverReadyProcessed = false;
    this.serverReadyDetails = null;

    // Reset adaptive quality to conservative mode
    this.adaptiveQuality.reset();

    // Clear all timers
    this.clearAllTimers();

    // FIXED: Remove from connection pool if exists
    if (this.ws && this.currentEndpoint) {
      try {
        this.connectionPool.removeConnection(this.currentEndpoint, this.ws);
      } catch (e) {
        logger.error('[ConnectionManager] Error removing from connection pool:', e);
      }
    }

    // Close connection
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        logger.info('[ConnectionManager] Closing WebSocket connection');
        this.ws.close(1000, 'Client disconnect');
      }
      this.ws = null;
    }

    this.currentEndpoint = null;
    this.onStateChange(ConnectionState.DISCONNECTED);

    logger.info('[ConnectionManager] Disconnected');
  }

  private clearAllTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
      this.tokenRefreshTimer = null;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Token Management - Industrial Standard
  // ─────────────────────────────────────────────────────────────────────────

  private async setupTokenRefresh(): Promise<void> {
    if (this.isDestroyed) return;

    // Clear existing timer
    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
      this.tokenRefreshTimer = null;
    }

    try {
      // Industrial standard: Get expiry from localStorage, not parsing JWT
      const auth = JSON.parse(localStorage.getItem('auth') || '{}');
      if (auth.expires_at) {
        this.tokenExpiresAt = auth.expires_at;

        const now = Date.now();
        if (!this.tokenExpiresAt) {
          logger.warn('[ConnectionManager] Token expiry time is null');
          return;
        }

        const expiresIn = this.tokenExpiresAt - now;

        logger.info(`[ConnectionManager] Token expires in ${Math.floor(expiresIn / 1000)} seconds`);

        // If token expires in less than 30 seconds, refresh immediately
        if (expiresIn < 30000) {
          logger.info('[ConnectionManager] Token expiring soon, refreshing immediately');
          await this.refreshTokenWithRetry();
          return;
        }

        // Schedule refresh 5 minutes before expiry
        const refreshIn = Math.max(0, expiresIn - 5 * 60 * 1000);

        if (refreshIn > 0) {
          this.tokenRefreshTimer = setTimeout(() => {
            this.refreshTokenWithRetry().catch(error => {
              logger.error('[ConnectionManager] Token refresh with retry failed:', error);
            });
          }, refreshIn);

          logger.info(`[ConnectionManager] Token refresh scheduled in ${Math.floor(refreshIn / 1000)}s`);
        }
      }
    } catch (error) {
      logger.error('[ConnectionManager] Error setting up token refresh:', error);
    }
  }

  private async refreshTokenWithRetry(): Promise<void> {
    if (this.isDestroyed) return;

    if (this.tokenRefreshAttempts >= MAX_TOKEN_REFRESH_ATTEMPTS) {
      logger.error('[ConnectionManager] Max token refresh attempts exceeded');
      this.disconnect();
      window.dispatchEvent(new CustomEvent('authTokenExpired', {
        detail: {
          error: 'Max token refresh attempts exceeded',
          attempts: this.tokenRefreshAttempts
        }
      }));
      return;
    }

    for (let attempt = 0; attempt < MAX_TOKEN_REFRESH_ATTEMPTS; attempt++) {
      try {
        await this.refreshToken();
        this.tokenRefreshAttempts = 0;
        return;
      } catch (error) {
        this.tokenRefreshAttempts++;
        const errorMessage = error instanceof Error ? error.message : String(error);
        logger.warn(`[ConnectionManager] Token refresh attempt ${attempt + 1}/${MAX_TOKEN_REFRESH_ATTEMPTS} failed:`, errorMessage);

        if (attempt < MAX_TOKEN_REFRESH_ATTEMPTS - 1) {
          // Exponential backoff for retry
          const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    // All attempts failed
    logger.error('[ConnectionManager] All token refresh attempts failed');
    this.disconnect();
    window.dispatchEvent(new CustomEvent('authTokenExpired', {
      detail: {
        error: 'Token refresh failed after all attempts',
        attempts: this.tokenRefreshAttempts
      }
    }));
  }

  private async refreshToken(): Promise<void> {
      if (this.isDestroyed) return;

      try {
          logger.info('[ConnectionManager] Refreshing WebSocket connection token');

          // Get the stored auth to get refresh token
          const auth = JSON.parse(localStorage.getItem('auth') || '{}');
          if (!auth.refresh_token) {
              throw new Error('No refresh token available');
          }

          // Use the API to refresh token
          const response = await refreshAuthToken(auth.refresh_token);

          if (!response.access_token) {
              throw new Error('Failed to refresh token - no access token returned');
          }

          // Update our token reference
          this.token = response.access_token;

          // Update token expiry from the response
          if (response.expires_in) {
              this.tokenExpiresAt = Date.now() + (response.expires_in * 1000);
          }

          // Update localStorage with new tokens
          const newAuth = {
              ...auth,
              token: response.access_token,
              refresh_token: response.refresh_token || auth.refresh_token,
              expires_at: this.tokenExpiresAt,
          };
          localStorage.setItem('auth', JSON.stringify(newAuth));

          // If connected, reconnect with new token
          if (this.isConnected()) {
              logger.info('[ConnectionManager] Token refreshed, reconnecting with new token');
              await this.reconnectWithNewToken();
          } else {
              logger.info('[ConnectionManager] Token refreshed, will use on next connection');
          }

          // Schedule next refresh
          await this.setupTokenRefresh();

      } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          logger.error('[ConnectionManager] Token refresh failed:', errorMessage);

          // Notify about auth failure
          this.onStateChange(ConnectionState.ERROR);
          const store = useWSEStore.getState();
          store.setLastError('Authentication token refresh failed', 401);

          throw error;
      }
  }

  private async reconnectWithNewToken(): Promise<void> {
    if (this.isDestroyed) return;

    logger.info('[ConnectionManager] Reconnecting with new token');

    // Store current topics
    const store = useWSEStore.getState();
    const topics = store.activeTopics;

    // Disconnect current connection gracefully
    if (this.ws) {
      this.ws.close(1000, 'Token refresh');
      this.ws = null;
    }

    // Wait a bit for clean disconnection
    await new Promise(resolve => setTimeout(resolve, 100));

    // Reset failure counters for token refresh reconnect
    this.consecutiveFailures = 0;
    this.reconnectAttempts = 0;

    // Reconnect with new token
    if (this.token) {
      try {
        await this.connect(this.token, topics);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        logger.error('[ConnectionManager] Failed to reconnect after token refresh:', errorMessage);
        throw error;
      }
    } else {
      const error = new Error('No valid token available for reconnection');
      logger.error('[ConnectionManager]', error.message);
      throw error;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Reconnection with Circuit Breaker
  // ─────────────────────────────────────────────────────────────────────────

  private async reconnect(): Promise<void> {
    if (this.isDestroyed) return;

    const store = useWSEStore.getState();

    const maxAttempts = this.reconnectionStrategy.maxAttempts === -1
      ? DEFAULT_MAX_RECONNECT_ATTEMPTS
      : this.reconnectionStrategy.maxAttempts;

    // Check if we should reconnect
    if (!store.canReconnect()) {
      logger.warn('[ConnectionManager] Cannot reconnect - circuit breaker open or max attempts reached');
      return;
    }

    // Check max attempts
    if (this.reconnectAttempts >= maxAttempts) {
      logger.error('[ConnectionManager] Max reconnection attempts reached');
      this.onStateChange(ConnectionState.ERROR);
      store.setLastError('Max reconnection attempts reached');
      return;
    }

    // Check circuit breaker
    if (!this.connectionCircuitBreaker.canExecute()) {
      logger.warn('[ConnectionManager] Connection circuit breaker is OPEN, skipping reconnect');
      this.onStateChange(ConnectionState.ERROR);
      store.setLastError('Connection circuit breaker open');
      return;
    }

    try {
      if (!this.token) {
        throw new Error('No token available for reconnection');
      }

      const endpoint = this.selectBestEndpoint();
      if (!endpoint) {
        throw new Error('No available endpoints for reconnection');
      }

      await this.connectToEndpoint(endpoint, store.activeTopics);
      store.incrementMetric('reconnectCount');

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('[ConnectionManager] Reconnection failed:', errorMessage);

      if (this.reconnectAttempts < maxAttempts && !this.isDestroyed) {
        this.scheduleReconnect();
      } else {
        this.onStateChange(ConnectionState.ERROR);
        store.setLastError('Max reconnection attempts reached');
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.isDestroyed) return;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    // Calculate delay with exponential backoff
    const baseDelay = this.calculateReconnectDelay();
    const minDelay = this.calculateMinConnectionDelay();
    const delay = Math.max(baseDelay, minDelay);

    // Cap at 5 minutes
    const finalDelay = Math.min(delay, 300000);

    logger.info(`[ConnectionManager] Scheduling reconnect in ${finalDelay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      if (!this.isDestroyed) {
        this.reconnectAttempts++;
        this.lastConnectionAttempt = Date.now();
        this.reconnect().catch(error => {
          const errorMessage = error instanceof Error ? error.message : String(error);
          logger.error('[ConnectionManager] Reconnect failed:', errorMessage);
        });
      }
    }, finalDelay);
  }

  private calculateReconnectDelay(): number {
    const { mode, baseDelay, maxDelay, factor, jitter } = this.reconnectionStrategy;
    let delay: number;

    switch (mode) {
      case 'exponential':
        delay = Math.min(maxDelay, baseDelay * Math.pow(factor, this.reconnectAttempts));
        break;

      case 'linear':
        delay = Math.min(maxDelay, baseDelay + (this.reconnectAttempts * 1000));
        break;

      case 'fibonacci': {
        const fib = (n: number): number => n <= 1 ? n : fib(n - 1) + fib(n - 2);
        delay = Math.min(maxDelay, baseDelay * fib(Math.min(this.reconnectAttempts, 10)));
        break;
      }

      case 'adaptive':
      default:
        delay = Math.min(maxDelay, baseDelay * Math.pow(1.5, this.reconnectAttempts));
        break;
    }

    // Add jitter if enabled
    if (jitter) {
      const jitterAmount = delay * 0.2 * (Math.random() - 0.5);
      delay = Math.max(0, delay + jitterAmount);
    }

    return delay;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Message Handling
  // ─────────────────────────────────────────────────────────────────────────

  send(message: WSMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || this.isDestroyed) {
      logger.debug('[ConnectionManager] Cannot send - WebSocket not open');
      return false;
    }

    // Allow critical messages with just serverReady
    const isCriticalMessage = ['subscription_update', 'sync_request', 'client_hello'].includes(message.t);

    if (isCriticalMessage) {
      if (!this.serverReady) {
        logger.debug(`[ConnectionManager] Cannot send critical message ${message.t} - server not ready yet`);
        return false;
      }
    } else {
      // For non-critical messages, require full readiness
      if (!this.isReady()) {
        logger.debug(`[ConnectionManager] Cannot send non-critical message ${message.t} - not fully ready`);
        return false;
      }
    }

    // Check rate limit
    if (!this.rateLimiter.canSend()) {
      logger.warn('[ConnectionManager] Rate limit exceeded');
      const store = useWSEStore.getState();
      store.incrementMetric('messagesDropped');

      const retryAfter = this.rateLimiter.getRetryAfter();
      logger.info(`[ConnectionManager] Rate limited. Retry after ${retryAfter}s`);

      // Dispatch event for UI to handle
      window.dispatchEvent(new CustomEvent('clientRateLimitExceeded', {
        detail: {
          retryAfter,
          stats: this.rateLimiter.getStats(),
        }
      }));

      return false;
    }

    try {
      // Determine message category prefix (Protocol v2)
      // S = Snapshot, U = Update, WSE = System
      let msgCat: string;
      const msgType = message.t || '';
      if (msgType.toLowerCase().includes('snapshot')) {
        msgCat = MessageCategory.SNAPSHOT; // "S"
      } else if (WSE_SYSTEM_EVENT_TYPES.has(msgType)) {
        msgCat = MessageCategory.SYSTEM; // "WSE"
      } else {
        msgCat = MessageCategory.UPDATE; // "U"
      }

      // Serialize with prefix: {category}{json}
      const jsonData = JSON.stringify(message);
      const data = `${msgCat}${jsonData}`;
      this.ws.send(data);

      const store = useWSEStore.getState();
      store.incrementMetric('messagesSent');
      store.incrementMetric('bytesSent', new Blob([data]).size);

      logger.debug(`[ConnectionManager] ✓ Sent [${msgCat}] ${isCriticalMessage ? 'critical' : ''} message: ${message.t}`);
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('[ConnectionManager] Failed to send message:', errorMessage);
      return false;
    }
  }

  sendRaw(data: string | ArrayBuffer): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || this.isDestroyed) {
      return false;
    }

    // Rate limiting for raw messages too
    if (!this.rateLimiter.canSend()) {
      logger.warn('[ConnectionManager] Rate limit exceeded for raw message');
      return false;
    }

    try {
      this.ws.send(data);

      const store = useWSEStore.getState();
      store.incrementMetric('messagesSent');

      if (typeof data === 'string') {
        store.incrementMetric('bytesSent', new Blob([data]).size);
      } else {
        store.incrementMetric('bytesSent', data.byteLength);
      }

      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('[ConnectionManager] Failed to send raw message:', errorMessage);
      return false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Server Ready and Client Hello
  // ─────────────────────────────────────────────────────────────────────────

  handleServerReady(details: any): void {
    this.serverReady = true;
    this.connectionId = details.connection_id || null;
    this.serverReadyProcessed = true;
    this.serverReadyDetails = details;

    logger.info('[ConnectionManager] Server ready received:', details);

    // Send client hello first
    if (!this.clientHelloSent) {
      this.sendClientHello();
    }

    // Notify callback
    if (this.onServerReady && !this.isDestroyed) {
      logger.info('[ConnectionManager] Notifying onServerReady callback');
      this.onServerReady(details);
    }
  }

  processPendingServerReady(): void {
    if (this.serverReadyProcessed && this.serverReadyDetails && !this.isDestroyed) {
      this.handleServerReady(this.serverReadyDetails);
    }
  }

  resetServerReadyFlag(): void {
    this.serverReadyProcessed = false;
    this.serverReadyDetails = null;
  }

  private sendClientHello(): void {
    if (this.clientHelloSent || this.isDestroyed) {
      return;
    }

    const message: WSMessage = {
      t: 'client_hello',
      p: {
        client_version: WS_CLIENT_VERSION,
        protocol_version: WS_PROTOCOL_VERSION,
        features: {
          compression: FEATURES.COMPRESSION,
          encryption: FEATURES.ENCRYPTION,
          batching: FEATURES.BATCHING,
          priority_queue: FEATURES.PRIORITY_QUEUE,
          circuit_breaker: FEATURES.CIRCUIT_BREAKER,
          offline_queue: FEATURES.OFFLINE_QUEUE,
          message_signing: FEATURES.MESSAGE_SIGNING,
          rate_limiting: FEATURES.RATE_LIMITING,
          health_check: FEATURES.HEALTH_CHECK,
          metrics: FEATURES.METRICS,
        },
        connection_id: this.connectionId,
      },
      id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      v: WS_PROTOCOL_VERSION,
      pri: MessagePriority.CRITICAL,
    };

    const sent = this.send(message);
    if (sent) {
      this.clientHelloSent = true;
      logger.info('[ConnectionManager] Client hello sent successfully');
    } else if (!this.isDestroyed) {
      // Retry client hello after a delay
      logger.warn('[ConnectionManager] Failed to send client hello, retrying in 1s');
      setTimeout(() => this.sendClientHello(), 1000);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // WebSocket Event Handlers
  // ─────────────────────────────────────────────────────────────────────────

  private setupWebSocketHandlers(ws: WebSocket, endpoint: string): void {
    ws.onopen = () => {
      logger.info('[ConnectionManager] WebSocket connection opened');
      this.onStateChange(ConnectionState.CONNECTED);

      // Update store metrics
      const store = useWSEStore.getState();
      store.updateMetrics({ connectedSince: Date.now() });

      // Record success in connection pool
      this.connectionPool.recordSuccess(endpoint);
    };

    ws.onmessage = (event) => {
      if (this.isDestroyed) return;

      // Record latency for PONG messages
      if (typeof event.data === 'string' && event.data.startsWith('PONG:')) {
        try {
          const timestamp = parseInt(event.data.substring(5), 10);
          const latency = Date.now() - timestamp;
          this.connectionPool.recordSuccess(endpoint, latency);

          // Update adaptive quality based on latency (industry thresholds)
          let quality: 'excellent' | 'good' | 'fair' | 'poor';
          if (latency < 100) quality = 'excellent';
          else if (latency < 300) quality = 'good';
          else if (latency < 1000) quality = 'fair';
          else quality = 'poor';

          this.adaptiveQuality.updateQuality(quality, { latency });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          logger.warn('[ConnectionManager] Failed to parse PONG timestamp:', errorMessage);
        }
      }

      // Pass all messages to the message processor
      this.onMessage(event.data);
    };

    ws.onerror = (error) => {
      if (this.isDestroyed) return;

      logger.error(`[ConnectionManager] WebSocket error on ${endpoint}:`, error);
      const store = useWSEStore.getState();
      store.recordCircuitBreakerFailure();
      this.connectionPool.recordFailure(endpoint);
    };

    ws.onclose = (event) => {
      if (this.isDestroyed) return;

      logger.info(`[ConnectionManager] WebSocket closed on ${endpoint}: code=${event.code}, reason=${event.reason}`);

      this.ws = null;
      this.serverReady = false;
      this.clientHelloSent = false;
      this.serverReadyProcessed = false;

      const store = useWSEStore.getState();

      // FIXED: Safely remove from connection pool
      if (this.currentEndpoint) {
        try {
          this.connectionPool.removeConnection(this.currentEndpoint, ws);
        } catch (e) {
          logger.error('[ConnectionManager] Error removing from pool on close:', e);
        }
      }

      // Handle different close codes from backend
      if (event.code === 1000 || event.code === 1001) {
        // Normal closure
        this.onStateChange(ConnectionState.DISCONNECTED);
      } else if (event.code === 4401 || event.code === 4403) {
        // Auth failure from backend - Industrial standard response
        this.onStateChange(ConnectionState.ERROR);
        store.setLastError('Authentication failed', event.code);
        store.incrementMetric('authFailures');

        // Clear token
        this.token = null;

        // Notify about auth failure
        window.dispatchEvent(new CustomEvent('wseAuthFailed', {
          detail: {
            code: event.code,
            reason: event.reason || 'Backend authentication failed'
          }
        }));

        // Attempt token refresh
        this.refreshTokenWithRetry().catch(error => {
          const errorMessage = error instanceof Error ? error.message : String(error);
          logger.error('[ConnectionManager] Token refresh after auth failure failed:', errorMessage);
        });
      } else if (event.code === 4429) {
        // Rate limit from backend
        this.onStateChange(ConnectionState.ERROR);
        store.setLastError('Rate limit exceeded', event.code);
      } else if (!this.isDestroyed) {
        // Abnormal closure - attempt reconnect
        this.onStateChange(ConnectionState.RECONNECTING);
        this.scheduleReconnect();
      }
    };
  }

  private selectBestEndpoint(): string | null {
    return this.connectionPool.getBestEndpoint();
  }

  private startHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.heartbeatInterval = setInterval(() => {
      if (this.isDestroyed) {
        if (this.heartbeatInterval) {
          clearInterval(this.heartbeatInterval);
          this.heartbeatInterval = null;
        }
        return;
      }

      // Send PING with WSE prefix (Protocol v2 format)
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          const pingMessage = {
            t: 'PING',
            p: { timestamp: Date.now() },
            v: WS_PROTOCOL_VERSION,
          };
          const data = `${MessageCategory.SYSTEM}${JSON.stringify(pingMessage)}`;
          this.ws.send(data);
          const store = useWSEStore.getState();
          store.incrementMetric('messagesSent');
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          logger.error('[ConnectionManager] Failed to send ping:', errorMessage);
        }
      }
    }, 15000); // 15 seconds matching backend HEARTBEAT_INTERVAL
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public Methods
  // ─────────────────────────────────────────────────────────────────────────

  changeEndpoint(endpoint: string): void {
    if (this.isDestroyed) return;

    logger.info(`[ConnectionManager] Changing endpoint to: ${endpoint}`);

    this.connectionPool.setPreferredEndpoint(endpoint);
    this.connectionPool.addEndpoint(endpoint);

    this.disconnect();
    this.reconnectAttempts = 0;
    this.consecutiveFailures = 0;

    if (this.token) {
      const store = useWSEStore.getState();
      this.connect(this.token, store.activeTopics).catch(error => {
        const errorMessage = error instanceof Error ? error.message : String(error);
        logger.error('[ConnectionManager] Failed to change endpoint:', errorMessage);
      });
    } else {
      logger.warn('[ConnectionManager] Cannot change endpoint: no token available');
    }
  }

  isConnected(): boolean {
    return !this.isDestroyed && this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  isReady(): boolean {
    return this.isConnected() && this.serverReady;
  }

  isFullyReady(): boolean {
    return this.isConnected() && this.serverReady && this.clientHelloSent;
  }

  getConnectionId(): string | null {
    return this.connectionId;
  }

  getRateLimiterStats(): any {
    return this.rateLimiter.getStats();
  }

  getConnectionPoolStats(): any {
    return this.connectionPool.getDetailedStats();
  }

  setLoadBalancingStrategy(strategy: 'weighted-random' | 'least-connections' | 'round-robin'): void {
    this.connectionPool.setLoadBalancingStrategy(strategy);
  }

  getHealthScores(): Record<string, number> {
    return this.connectionPool.getHealthScores();
  }

  getConnectionPool(): ConnectionPool {
    return this.connectionPool;
  }

  getAdaptiveQuality(): { quality: string | null; strategy: string } {
    return {
      quality: this.adaptiveQuality.getCurrentQuality(),
      strategy: this.adaptiveQuality.getCurrentStrategyName(),
    };
  }

  // Cleanup method
  destroy(): void {
    logger.info('[ConnectionManager] Destroy called');

    this.isDestroyed = true;

    // Force close WebSocket immediately
    if (this.ws) {
      try {
        // Remove all event listeners first
        this.ws.onopen = null;
        this.ws.onmessage = null;
        this.ws.onerror = null;
        this.ws.onclose = null;

        // Force close if still open
        if (this.ws.readyState === WebSocket.OPEN ||
            this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close(1000, 'Destroying connection manager');
        }
      } catch (e) {
        logger.error('[ConnectionManager] Error closing WebSocket:', e);
      }
      this.ws = null;
    }

    // Clear all timers
    this.clearAllTimers();

    // Destroy connection pool
    try {
      this.connectionPool.destroy();
    } catch (e) {
      logger.error('[ConnectionManager] Error destroying connection pool:', e);
    }

    this.connectionCircuitBreaker.reset();

    logger.info('[ConnectionManager] Destroyed');
  }}