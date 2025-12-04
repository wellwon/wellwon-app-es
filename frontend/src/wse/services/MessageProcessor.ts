// =============================================================================
// File: src/wse/services/MessageProcessor.ts
// Description: Message processing with full backend compatibility (COMPLETE)
// =============================================================================

import {
  WSMessage,
  QueuedMessage,
  MessagePriority,
  ConnectionQuality,
  ConnectionState,
  CircuitBreakerState
} from '@/wse';
import { useWSEStore } from '@/wse';
import { useMessageQueueStore } from '@/wse';
import { EventSequencer } from '@/wse';
import { CompressionManager } from '../protocols/compression';
import { logger } from '@/wse';
import { WS_CLIENT_VERSION, WS_PROTOCOL_VERSION } from '@/wse';

export class MessageProcessor {
  private sequencer: EventSequencer;
  private compression: CompressionManager;
  private messageHandlers: Map<string, (message: WSMessage) => void>;
  private batchTimer: NodeJS.Timeout | null = null;
  private processing = false;
  private connectionManager: any = null;
  private isReady = false;

  // Use promise-based queue for race condition prevention
  private batchPromise: Promise<void> | null = null;
  private destroyed = false;

  // Add server ready state management
  private serverReadyProcessed = false;
  private serverReadyDetails: any = null;

  constructor(
    private batchSize: number = 10,
    private batchTimeout: number = 100
  ) {
    this.sequencer = new EventSequencer();
    this.compression = new CompressionManager();
    this.messageHandlers = new Map();

    this.registerDefaultHandlers();
  }

  setConnectionManager(manager: any): void {
    this.connectionManager = manager;

    // Process pending server ready if we have it
    if (this.serverReadyProcessed && this.serverReadyDetails && manager) {
      logger.info('Processing pending server ready details');
      manager.handleServerReady(this.serverReadyDetails);
      this.serverReadyDetails = null; // Clear after processing
    }
  }

  setReady(ready: boolean): void {
    this.isReady = ready;
    if (ready) {
      logger.info('MessageProcessor is now ready to process messages');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Debug
  // ─────────────────────────────────────────────────────────────────────────

  private debugMessage(type: string, message: any, details?: any): void {
    // Only log in development or if debug mode is enabled
    if (process.env.NODE_ENV !== 'development' && !(window as any).WSE_DEBUG) {
      return;
    }

    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      type,
      message: {
        t: message?.t,
        id: message?.id,
        seq: message?.seq,
        hasPayload: !!message?.p,
        payloadType: typeof message?.p,
        payloadKeys: message?.p ? Object.keys(message.p) : [],
      },
      details,
      raw: message
    };

    // Store in session storage for debugging
    try {
      const debugLog = JSON.parse(sessionStorage.getItem('wse_debug_log') || '[]');
      debugLog.push(logEntry);
      // Keep only last 100 entries
      if (debugLog.length > 100) {
        debugLog.shift();
      }
      sessionStorage.setItem('wse_debug_log', JSON.stringify(debugLog));
    } catch (e) {
      // Ignore storage errors
    }

    // Log to console with color coding
    const color = type.includes('error') ? 'color: red' :
                  type.includes('warning') ? 'color: orange' :
                  'color: blue';

    console.log(`%c[WSE Debug] ${type}`, color, logEntry);
  }

  // Add this static method to enable/disable debug mode
  static enableDebugMode(enabled: boolean = true): void {
    (window as any).WSE_DEBUG = enabled;
    if (enabled) {
      logger.info('WSE Debug mode enabled. Messages will be logged to console and sessionStorage.');
      logger.info('View debug log with: JSON.parse(sessionStorage.getItem("wse_debug_log"))');
      logger.info('Clear debug log with: sessionStorage.removeItem("wse_debug_log")');
    } else {
      logger.info('WSE Debug mode disabled.');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Event Versioning
  // ─────────────────────────────────────────────────────────────────────────

  private handleEventVersion(message: WSMessage): void {
    // Client supports event versions 1-2
    const CLIENT_SUPPORTED_VERSION = 2;

    if (message.event_version && message.event_version > CLIENT_SUPPORTED_VERSION) {
      logger.warn(
        `Received event with version ${message.event_version} (type: ${message.t}), ` +
        `but client only supports up to version ${CLIENT_SUPPORTED_VERSION}. ` +
        `Some fields may not be handled correctly. Consider upgrading the client.`,
        { eventType: message.t, version: message.event_version }
      );
    }

    // Log version info for debugging (only once per event type)
    if (message.event_version) {
      const key = `${message.t}_v${message.event_version}`;
      if (!this.sequencer.isDuplicate(key)) {
        logger.debug(
          `Event type '${message.t}' using schema version ${message.event_version}`
        );
      }
    }
  }

  private logPerformanceMetrics(message: WSMessage): void {
    // Log performance metrics for observability and monitoring
    const metrics: string[] = [];

    if (message.latency_ms !== undefined) {
      metrics.push(`event_latency=${message.latency_ms}ms`);

      // Warn on high end-to-end latency
      if (message.latency_ms > 1000) {
        logger.warn(
          `High event latency detected: ${message.latency_ms}ms for event type '${message.t}'`,
          { eventType: message.t, latency: message.latency_ms }
        );
      }
    }

    if (message.wse_processing_ms !== undefined) {
      metrics.push(`wse_processing=${message.wse_processing_ms}ms`);

      // PERFORMANCE NOTE (Nov 11, 2025): wse_processing_ms is BACKEND processing time
      // Backend ReactiveEventBus takes 40-70ms for Redis operations (XADD + EXPIRE + PUBLISH)
      // After today's optimizations (async compression + pipelining), typical times:
      // - Small events: 40-60ms
      // - Large events (compressed): 60-90ms
      // - Complex events (server_ready, connection_state_change): 90-150ms
      // Threshold set to 150ms to avoid false positives
      if (message.wse_processing_ms > 150) {
        logger.warn(
          `High backend WSE processing time: ${message.wse_processing_ms}ms for event type '${message.t}'`,
          {
            eventType: message.t,
            backendWseProcessing: message.wse_processing_ms,
            note: 'This is backend ReactiveEventBus processing time (Redis XADD + EXPIRE + PUBLISH), not frontend processing'
          }
        );
      }
    }

    if (message.trace_id) {
      metrics.push(`trace_id=${message.trace_id}`);
    }

    // Log metrics if any are present
    if (metrics.length > 0) {
      logger.debug(`Event '${message.t}' metrics: ${metrics.join(', ')}`);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Message Processing
  // ─────────────────────────────────────────────────────────────────────────

  async processIncoming(data: string | ArrayBuffer): Promise<void> {
    if (this.destroyed) return;

    const store = useWSEStore.getState();
    store.incrementMetric('messagesReceived');

    try {
      let message: WSMessage | null;

      if (data instanceof ArrayBuffer) {
        message = await this.processBinaryMessage(data);
        store.incrementMetric('bytesReceived', data.byteLength);
      } else {
        message = this.processTextMessage(data);
        store.incrementMetric('bytesReceived', new Blob([data]).size);
      }

      if (!message) return;

      // Log every message for debugging
      logger.debug(`Received message type: ${message.t}`, message);

      // Check event version compatibility
      this.handleEventVersion(message);

      // Log performance metrics for observability
      this.logPerformanceMetrics(message);

      // Check for duplicate
      if (message.id && this.sequencer.isDuplicate(message.id)) {
        logger.debug(`Duplicate message ignored: ${message.id}`);
        return;
      }

      // Record sequence if present
      if (message.seq !== undefined) {
        this.sequencer.recordSequence(message.seq);
      }

      // Route message
      await this.routeMessage(message);

    } catch (error) {
      logger.error('Error processing message:', error);
      store.setLastError('Message processing error');
    }
  }

  private processTextMessage(data: string): WSMessage | null {
    // Handle special text messages from the backend

    // Plain text PING (backend sends this)
    if (data.toUpperCase().startsWith('PING')) {
      // We don't process incoming PINGs - backend doesn't send them
      return null;
    }

    // PONG response with timestamp
    if (data.startsWith('PONG:')) {
      const timestamp = parseInt(data.substring(5), 10);
      const latency = Date.now() - timestamp;

      const store = useWSEStore.getState();
      store.recordLatency(latency);

      logger.debug(`Latency: ${latency}ms`);
      return null; // Don't route PONG messages
    }

    try {
      // WSE Protocol v2: Messages have a category prefix before JSON
      // Wire format: {category}{json}
      // Categories:
      //   S  = Snapshot (full state dump for initial sync)
      //   U  = Update (incremental delta updates) - default
      //   WSE = System (protocol/system messages: ping, pong, errors, etc.)
      //
      // Examples:
      //   U{"t":"chat_created","p":{...}}
      //   S{"t":"broker_connection_snapshot","p":{...}}
      //   WSE{"t":"server_ready","p":{...}}

      let jsonData = data;
      let messageCategory: string | undefined;

      // Check for WSE prefix (3 chars)
      if (data.startsWith('WSE{')) {
        messageCategory = 'WSE';
        jsonData = data.substring(3);
      }
      // Check for single-letter prefix (S or U)
      else if (data.length > 1 && /^[SU]/.test(data[0]) && data[1] === '{') {
        messageCategory = data[0];
        jsonData = data.substring(1);
      }

      const message = JSON.parse(jsonData) as WSMessage;

      // Attach category to message for routing/logging purposes
      if (messageCategory) {
        message._category = messageCategory;
        logger.debug(`WSE Protocol v2: Category=${messageCategory}, Type=${message.t}`);
      }

      return message;
    } catch (error) {
      logger.error('Invalid JSON message:', error, { data: data.substring(0, 100) });
      return null;
    }
  }

  /**
   * Parse JSON string with WSE Protocol v2 category prefix handling.
   *
   * Wire format: {category}{json}
   * Categories:
   *   S   = Snapshot (full state dump for initial sync)
   *   U   = Update (incremental delta updates) - default
   *   WSE = System (protocol/system messages)
   */
  private parseWithCategory(text: string): WSMessage {
    let jsonData = text;
    let messageCategory: string | undefined;

    // Check for WSE prefix (3 chars)
    if (text.startsWith('WSE{')) {
      messageCategory = 'WSE';
      jsonData = text.substring(3);
    }
    // Check for single-letter prefix (S or U)
    else if (text.length > 1 && /^[SU]/.test(text[0]) && text[1] === '{') {
      messageCategory = text[0];
      jsonData = text.substring(1);
    }

    const message = JSON.parse(jsonData) as WSMessage;

    // Attach category to message for routing/logging purposes
    if (messageCategory) {
      message._category = messageCategory;
    }

    return message;
  }

  private async processBinaryMessage(data: ArrayBuffer): Promise<WSMessage | null> {
    const view = new Uint8Array(data);

    // AGGRESSIVE LOGGING FOR DEBUGGING
    console.log('=== BINARY MESSAGE RECEIVED ===');
    console.log('Size:', data.byteLength, 'bytes');
    console.log('First 10 bytes (hex):', Array.from(view.slice(0, 10)).map(b => b.toString(16).padStart(2, '0')).join(' '));
    console.log('First 2 chars:', view.length >= 2 ? String.fromCharCode(view[0], view[1]) : 'N/A');

    // Log the first few bytes for debugging
    logger.debug('Binary message received:', {
      length: data.byteLength,
      first10Bytes: Array.from(view.slice(0, 10)),
      first2Chars: view.length >= 2 ? String.fromCharCode(view[0], view[1]) : 'N/A',
      hexFirst10: Array.from(view.slice(0, 10)).map(b => b.toString(16).padStart(2, '0')).join(' ')
    });

    // CRITICAL FIX: Check for zlib magic bytes FIRST
    // Backend sends raw compressed data without prefix for messages > 1024 bytes
    // Zlib headers: 0x78 0x01 (no compression), 0x78 0x5E (fast), 0x78 0x9C (best), 0x78 0xDA (default)
    if (view.length > 2 && view[0] === 0x78) {
      const zlibCompressionMethods = [0x01, 0x5E, 0x9C, 0xDA];
      if (zlibCompressionMethods.includes(view[1])) {
        try {
          console.log('>>> Detected raw zlib compressed data (0x78 header)');
          const decompressed = this.compression.decompress(data);
          const text = new TextDecoder().decode(decompressed);

          // Parse with WSE Protocol v2 category prefix handling
          const parsed = this.parseWithCategory(text);

          console.log('=== DECOMPRESSED RAW ZLIB MESSAGE ===');
          console.log('Type:', parsed.t);
          console.log('Size:', data.byteLength, '->', decompressed.byteLength, 'bytes');

          logger.info('=== DECOMPRESSED RAW ZLIB MESSAGE ===');
          logger.info(`Type: ${parsed.t}`);
          logger.info(`Size: ${data.byteLength} -> ${decompressed.byteLength} bytes`);

          // Special logging for snapshots
          if (parsed.t === 'broker_connection_snapshot') {
            console.log('=== BROKER CONNECTION SNAPSHOT DECOMPRESSED ===');
            console.log('Connections found:', parsed.p?.connections?.length || 0);
            if (parsed.p?.connections?.length > 0) {
              console.log('First connection:', parsed.p.connections[0]);
            }
          } else if (parsed.t === 'broker_account_snapshot') {
            console.log('=== BROKER ACCOUNT SNAPSHOT DECOMPRESSED ===');
            console.log('Accounts found:', parsed.p?.accounts?.length || 0);
            if (parsed.p?.accounts?.length > 0) {
              console.log('First account:', parsed.p.accounts[0]);
            }
          } else if (parsed.t === 'broker_streaming_snapshot') {
            console.log('=== BROKER STREAMING SNAPSHOT DECOMPRESSED ===');
            console.log('Streaming statuses found:', parsed.p?.streaming_status?.length || 0);
            console.log('Full payload:', parsed.p);
            if (parsed.p?.streaming_status?.length > 0) {
              console.log('First status:', parsed.p.streaming_status[0]);
              console.log('Stream types available:', parsed.p.streaming_status.map((s: any) => s.stream_type));
            }
          }

          const store = useWSEStore.getState();
          store.incrementMetric('compressionHits');

          return parsed;
        } catch (error) {
          logger.error('Failed to decompress raw zlib data:', error);
          logger.error('Data info:', {
            length: data.byteLength,
            first20Hex: Array.from(view.slice(0, 20)).map(b => b.toString(16).padStart(2, '0')).join(' ')
          });
          // Don't return here - try other methods
        }
      }
    }

    // 1. Check compression header 'C':
    if (view.length >= 2 && view[0] === 67 && view[1] === 58) { // 'C:'
      const store = useWSEStore.getState();
      store.incrementMetric('compressionHits');

      try {
        const compressed = data.slice(2);
        const decompressed = this.compression.decompress(compressed);

        // Backend sends compressed JSON with WSE Protocol v2 category prefix
        const text = new TextDecoder().decode(decompressed);
        const parsed = this.parseWithCategory(text);

        logger.info('=== DECOMPRESSED MESSAGE WITH C: HEADER ===');
        logger.info('Type:', parsed.t, 'Category:', parsed._category);

        return parsed;
      } catch (error) {
        logger.error('Failed to process compressed message with C: header:', error);
        return null;
      }
    }

    // 2. Check MessagePack header 'M':
    if (view.length >= 2 && view[0] === 77 && view[1] === 58) { // 'M:'
      try {
        return this.compression.unpackMsgPack(data.slice(2));
      } catch (error) {
        logger.error('Failed to unpack MessagePack:', error);
        return null;
      }
    }

    // 3. Check encryption header 'E':
    if (view.length >= 2 && view[0] === 69 && view[1] === 58) { // 'E:'
      logger.warn('Encrypted message received but encryption not enabled');
      return null;
    }

    // 4. Try as JSON first (backend might be sending JSON without headers)
    try {
      const text = new TextDecoder().decode(data);

      // Check if it looks like JSON (with or without WSE category prefix)
      if (text.startsWith('{') || text.startsWith('[') ||
          text.startsWith('U{') || text.startsWith('S{') || text.startsWith('WSE{')) {
        const parsed = this.parseWithCategory(text);
        logger.debug('Parsed as plain JSON:', parsed.t, 'Category:', parsed._category);
        return parsed;
      }
    } catch {
      // Not JSON, continue to other methods
    }

    // 5. Try as raw MessagePack
    try {
      const unpacked = this.compression.unpackMsgPack(data);
      logger.debug('Parsed as raw MessagePack');
      return unpacked;
    } catch (error) {
      // Not MessagePack either
    }

    // 6. Last attempt - maybe it's some other format
    logger.error('Failed to parse binary message in any known format');
    logger.error('Message info:', {
      length: data.byteLength,
      first20Bytes: Array.from(view.slice(0, Math.min(20, view.length))),
      first20Hex: Array.from(view.slice(0, Math.min(20, view.length))).map(b => `0x${b.toString(16).padStart(2, '0')}`).join(' '),
      asText: (() => {
        try {
          const text = new TextDecoder().decode(data.slice(0, Math.min(100, data.byteLength)));
          return text.replace(/[^\x20-\x7E]/g, '.');
        } catch {
          return 'Not text data';
        }
      })()
    });

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Message Routing
  // ─────────────────────────────────────────────────────────────────────────

  private async routeMessage(message: WSMessage): Promise<void> {
    const type = message.t;

    // Debug level - only visible when debug mode enabled
    logger.debug(`Routing message: ${type}`);

    // For snapshot messages, log the structure
    if (type === 'broker_connection_snapshot') {
      logger.info('BROKER CONNECTION SNAPSHOT received in router');
      logger.info('Payload structure:', {
        hasConnections: 'connections' in (message.p || {}),
        connectionsLength: message.p?.connections?.length,
        trimArchived: message.p?.trim_archived,
        includeModuleDetails: message.p?.include_module_details
      });
      if (message.p?.connections?.length > 0) {
        logger.info('First connection in snapshot:', message.p.connections[0]);
      }
    } else if (type === 'broker_account_snapshot') {
      logger.info('BROKER ACCOUNT SNAPSHOT received in router');
      logger.info('Payload structure:', {
        hasAccounts: 'accounts' in (message.p || {}),
        accountsLength: message.p?.accounts?.length,
        includePositions: message.p?.include_positions
      });
    }

    // Check for a registered handler
    // DEBUG: Log all incoming messages for saga events
    if (type.includes('group_') || type.includes('saga') || type.includes('completion')) {
      console.log('[WSE DEBUG] Received saga-related event:', type, message);
    }

    const handler = this.messageHandlers.get(type);
    if (handler) {
      try {
        console.log('[WSE DEBUG] Calling handler for:', type);
        handler(message);
      } catch (error) {
        logger.error(`Error in handler for ${type}:`, error);
      }
      return;
    }

    // If no handler found
    logger.warn(`NO HANDLER FOUND for message type: ${type}`);
    logger.warn(`Registered handlers:`, Array.from(this.messageHandlers.keys()));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Message Handlers
  // ─────────────────────────────────────────────────────────────────────────

  private registerDefaultHandlers(): void {

    // System message handlers
    this.messageHandlers.set('server_ready', (msg) => this.handleServerReady(msg));
    this.messageHandlers.set('server_hello', (msg) => this.handleServerHello(msg));
    this.messageHandlers.set('subscription_update', (msg) => this.handleSubscriptionUpdate(msg));
    this.messageHandlers.set('error', (msg) => this.handleError(msg));
    this.messageHandlers.set('connection_state_change', (msg) => this.handleConnectionStateChange(msg));
    this.messageHandlers.set('health_check', (msg) => this.handleHealthCheck(msg));
    this.messageHandlers.set('health_check_response', (msg) => this.handleHealthCheckResponse(msg));
    this.messageHandlers.set('rate_limit_warning', (msg) => this.handleRateLimitWarning(msg));
    this.messageHandlers.set('connection_quality', (msg) => this.handleConnectionQuality(msg));
    this.messageHandlers.set('snapshot_complete', (msg) => this.handleSnapshotComplete(msg));
    this.messageHandlers.set('heartbeat', () => this.handleHeartbeat());
    this.messageHandlers.set('PONG', (msg) => this.handlePong(msg));

    // Debug handlers
    this.messageHandlers.set('debug_response', (msg) => this.handleDebugResponse(msg));
    this.messageHandlers.set('sequence_stats_response', (msg) => this.handleSequenceStatsResponse(msg));

    // Configuration handlers
    this.messageHandlers.set('config_response', (msg) => this.handleConfigResponse(msg));
    this.messageHandlers.set('config_update_response', (msg) => this.handleConfigUpdateResponse(msg));

    // Encryption handlers
    this.messageHandlers.set('encryption_response', (msg) => this.handleEncryptionResponse(msg));
    this.messageHandlers.set('key_rotation_response', (msg) => this.handleKeyRotationResponse(msg));

    // Batch handlers
    this.messageHandlers.set('batch', (msg) => this.handleBatchMessage(msg));
    this.messageHandlers.set('batch_message_result', (msg) => this.handleBatchMessageResult(msg));

    // Metrics handler
    this.messageHandlers.set('metrics_response', (msg) => this.handleMetricsResponse(msg));

    // Connection state handler
    this.messageHandlers.set('connection_state_response', (msg) => this.handleConnectionStateResponse(msg));

    // Sync request handler
    this.messageHandlers.set('sync_request', (msg) => {
      const store = useWSEStore.getState();
      this.queueOutgoing({
        t: 'sync_response',
        p: {
          client_version: WS_CLIENT_VERSION,
          protocol_version: WS_PROTOCOL_VERSION,
          sequence: this.sequencer.getCurrentSequence(),
          subscriptions: store.activeTopics,
          last_update: Date.now(),
        }
      }, MessagePriority.HIGH);
    });

    // Config update handler
    this.messageHandlers.set('config_update', (msg) => {
      const config = msg.p;
      const store = useWSEStore.getState();

      if (config.compression_enabled !== undefined) {
        store.updateConfig({ compressionEnabled: config.compression_enabled });
      }
      if (config.batching_enabled !== undefined) {
        store.updateConfig({ batchingEnabled: config.batching_enabled });
        if (config.batch_size) {
          this.batchSize = config.batch_size;
        }
        if (config.batch_timeout) {
          this.batchTimeout = config.batch_timeout;
        }
      }
      if (config.max_queue_size !== undefined) {
        const queueStore = useMessageQueueStore.getState();
        queueStore.setCapacity(config.max_queue_size);
      }

      logger.info('Configuration updated:', config);
    });

    // Metrics request handler
    this.messageHandlers.set('metrics_request', (msg) => {
      const store = useWSEStore.getState();
      const queueStore = useMessageQueueStore.getState();

      this.queueOutgoing({
        t: 'metrics_response',
        p: {
          client_version: WS_CLIENT_VERSION,
          connection_stats: store.metrics,
          queue_stats: queueStore.stats,
          diagnostics: store.diagnostics,
          circuit_breaker: store.circuitBreaker,
          security: store.security,
          subscriptions: {
            active: store.activeTopics,
            pending: store.subscriptions.pendingSubscriptions,
            failed: store.subscriptions.failedSubscriptions,
          },
          event_sequencer: this.sequencer.getStats(),
          timestamp: new Date().toISOString(),
        }
      }, MessagePriority.HIGH);
    });

    // Priority message handler
    this.messageHandlers.set('priority_message', (msg) => {
      const payload = msg.p;
      const priority = payload.priority || MessagePriority.NORMAL;

      logger.debug(`Priority message received with priority ${priority}:`, payload);

      // Could forward to specific handlers based on content
      if (payload.type && this.messageHandlers.has(payload.type)) {
        const handler = this.messageHandlers.get(payload.type);
        handler!({ ...msg, p: payload.content || payload });
      }
    });
  }

  // Updated handleServerReady method with proper state management
  private handleServerReady(message: WSMessage): void {
    const payload = message.p;
    logger.info('Server ready:', payload);

    const store = useWSEStore.getState();

    // CRITICAL: Set connection state to CONNECTED
    store.setConnectionState(ConnectionState.CONNECTED);
    store.updateMetrics({ connectedSince: Date.now() });

    // Store server ready details for later processing
    this.serverReadyDetails = payload.details || payload;
    this.serverReadyProcessed = true;

    // Process when connection manager is available
    if (this.connectionManager) {
      this.connectionManager.handleServerReady(this.serverReadyDetails);
      this.serverReadyDetails = null; // Clear after processing
    } else {
      logger.info('Connection manager not yet available, storing server ready details for later');
    }
  }

  // Add method to process pending server ready
  public processPendingServerReady(): void {
    if (this.serverReadyProcessed && this.serverReadyDetails && this.connectionManager) {
      this.connectionManager.handleServerReady(this.serverReadyDetails);
      this.serverReadyDetails = null; // Clear after processing
    }
  }

  // Reset the flag when connection is lost
  public resetServerReadyFlag(): void {
    this.serverReadyProcessed = false;
    this.serverReadyDetails = null;
  }

  private handleServerHello(message: WSMessage): void {
    const payload = message.p;
    logger.info('Server hello received:', payload);

    // Update capabilities based on server response
    const store = useWSEStore.getState();

    if (payload.features) {
      store.updateConfig({
        compressionEnabled: payload.features.compression ?? true,
        batchingEnabled: payload.features.batching ?? true,
        offlineModeEnabled: payload.features.offline_queue ?? true,
      });
    }

    if (payload.limits) {
      const queueStore = useMessageQueueStore.getState();
      if (payload.limits.max_queue_size) {
        queueStore.setCapacity(payload.limits.max_queue_size);
      }
    }
  }

  private handleConnectionStateChange(message: WSMessage): void {
    const payload = message.p;
    logger.info('Connection state change:', payload);

    const store = useWSEStore.getState();

    // Update connection state if provided
    if (payload.new_state) {
      // Map the state string to ConnectionState enum
      const stateMap: Record<string, ConnectionState> = {
        'pending': ConnectionState.PENDING,
        'connecting': ConnectionState.CONNECTING,
        'connected': ConnectionState.CONNECTED,
        'reconnecting': ConnectionState.RECONNECTING,
        'disconnected': ConnectionState.DISCONNECTED,
        'error': ConnectionState.ERROR,
        'degraded': ConnectionState.DEGRADED,
      };

      const newState = stateMap[payload.new_state.toLowerCase()];
      if (newState) {
        store.setConnectionState(newState);
      }
    }

    // Dispatch event for UI components that might need it
    window.dispatchEvent(new CustomEvent('connectionStateChange', {
      detail: {
        oldState: payload.old_state,
        newState: payload.new_state,
        connectionId: payload.connection_id,
        timestamp: payload.timestamp || new Date().toISOString(),
      }
    }));
  }

  private handleSubscriptionUpdate(message: WSMessage): void {
    const payload = message.p;
    const store = useWSEStore.getState();

    logger.info('=== SUBSCRIPTION UPDATE RECEIVED ===');
    logger.info('Payload:', payload);

    if (payload.success) {
      // Update confirmed subscriptions
      payload.success_topics?.forEach((topic: string) => {
        store.confirmSubscription(topic);
      });
    }

    if (payload.failed_topics) {
      payload.failed_topics.forEach((topic: string) => {
        store.failSubscription(topic);
      });
    }

    // Dispatch event for UI
    window.dispatchEvent(new CustomEvent('subscriptionUpdate', {
      detail: payload
    }));
  }

  private handleError(message: WSMessage): void {
    const store = useWSEStore.getState();

    // Log the full error for debugging
    logger.error('Server error received:', {
      type: message.t,
      payload: message.p,
      fullMessage: JSON.stringify(message, null, 2)
    });

    // Extract error data from payload
    const errorData = message.p || {};
    const errorMessage = errorData.message || 'Unknown error';
    const errorCode = errorData.code || 'UNKNOWN_ERROR';
    const recoverable = errorData.recoverable !== false;
    const details = errorData.details || {};

    // Log processed error
    logger.error(`Processed error - Code: ${errorCode}, Message: ${errorMessage}`, {
      errorData,
      recoverable,
      details
    });

    // Update store
    store.setLastError(errorMessage,
      typeof errorCode === 'number' ? errorCode :
      errorCode === 'AUTH_FAILED' ? 401 :
      errorCode === 'INIT_ERROR' ? 500 : 500
    );

    // Handle authentication errors
    if (errorCode === 'AUTH_FAILED') {
      logger.error('Authentication failed:', details);
      window.dispatchEvent(new CustomEvent('wseAuthFailed', {
        detail: {
          message: errorMessage,
          code: errorCode,
          details
        }
      }));
    }

    // Handle initialization errors
    if (errorCode === 'INIT_ERROR' && !recoverable) {
      logger.error('Critical initialization error:', details);
      window.dispatchEvent(new CustomEvent('wseInitializationError', {
        detail: {
          message: errorMessage,
          code: errorCode,
          recoverable: false,
          details
        }
      }));
    }

    // Handle server errors
    if (errorCode === 'SERVER_ERROR') {
      logger.error('Server error:', details);
      window.dispatchEvent(new CustomEvent('wseServerError', {
        detail: {
          message: errorMessage,
          code: errorCode,
          details
        }
      }));
    }

    // Handle circuit breaker errors
    if (errorCode === 'CIRCUIT_BREAKER_OPEN') {
      logger.error('Circuit breaker activated');
      store.updateCircuitBreaker({
        state: CircuitBreakerState.OPEN,
        lastFailureTime: Date.now()
      });
    }

    // Handle rate limiting
    if (errorCode === 'RATE_LIMIT_EXCEEDED' || errorMessage.includes('Rate limit')) {
      logger.warn('Rate limit exceeded');
      window.dispatchEvent(new CustomEvent('rateLimitExceeded', {
        detail: {
          message: errorMessage,
          retryAfter: errorData.retry_after || errorData.retryAfter,
          ...details
        }
      }));
    }

    // Handle subscription failures
    if (errorCode === 'SUBSCRIPTION_FAILED') {
      logger.warn('Subscription failed:', details);
      window.dispatchEvent(new CustomEvent('subscriptionFailed', {
        detail: {
          message: errorMessage,
          topics: errorData.topics || [],
          ...details
        }
      }));
    }

    // Dispatch generic error event for UI handling
    window.dispatchEvent(new CustomEvent('serverError', {
      detail: {
        message: errorMessage,
        code: errorCode,
        details: errorData,
        recoverable,
        timestamp: errorData.timestamp || new Date().toISOString(),
        severity: errorData.severity || 'error',
        context: {
          messageType: message.t,
          messageId: message.id,
          sequence: message.seq
        }
      }
    }));

    // If this is a critical error, we might need to reconnect
    if (!recoverable || errorCode === 'PROTOCOL_ERROR' || errorCode === 'INVALID_MESSAGE') {
      logger.error('Critical error detected, connection may need to be reset');

      window.dispatchEvent(new CustomEvent('criticalError', {
        detail: {
          code: errorCode,
          message: errorMessage,
          shouldReconnect: errorData.shouldReconnect !== false
        }
      }));
    }
  }

  private handleHealthCheck(message: WSMessage): void {
    const store = useWSEStore.getState();
    store.updateMetrics({ lastHealthCheck: Date.now() });

    // Respond to health check
    this.queueOutgoing({
      t: 'health_check_response',
      p: {
        client_version: WS_CLIENT_VERSION,
        stats: store.metrics,
        diagnostics: store.diagnostics,
        queue_size: useMessageQueueStore.getState().size,
      }
    }, MessagePriority.CRITICAL);
  }

  private handleHealthCheckResponse(message: WSMessage): void {
    const payload = message.p;
    logger.info('Health check response received:', payload);

    // Update diagnostics if provided
    if (payload.diagnostics) {
      const store = useWSEStore.getState();
      store.updateDiagnostics(payload.diagnostics);
    }
  }

  private handleRateLimitWarning(message: WSMessage): void {
    const warning = message.p;
    logger.warn('Rate limit warning:', warning);

    // Update store with rate limit info
    const store = useWSEStore.getState();
    store.setLastError(`Rate limit: ${warning.message}`, 429);

    // Could implement backoff logic here
    if (warning.retry_after) {
      logger.info(`Should retry after ${warning.retry_after} seconds`);
    }
  }

  private handleConnectionQuality(message: WSMessage): void {
    const payload = message.p;
    logger.info('Connection quality update:', payload);

    const store = useWSEStore.getState();

    // Update diagnostics with server suggestions
    if (payload.suggestions && payload.suggestions.length > 0) {
      // Get current diagnostics to merge with
      const currentDiagnostics = store.diagnostics || {
        quality: ConnectionQuality.UNKNOWN,
        stability: 100,
        jitter: 0,
        packetLoss: 0,
        roundTripTime: 0,
        suggestions: [],
        lastAnalysis: null,
      };

      // Update diagnostics with the proper NetworkDiagnostics structure
      store.updateDiagnostics({
        ...currentDiagnostics,
        suggestions: payload.suggestions,
        quality: payload.quality || currentDiagnostics.quality,
        lastAnalysis: Date.now(),
      });
    }

    // Apply recommended settings if provided
    if (payload.recommended_settings) {
      const settings = payload.recommended_settings;

      if (settings.compression !== undefined) {
        store.updateConfig({ compressionEnabled: settings.compression });
      }

      if (settings.batch_size !== undefined) {
        this.batchSize = settings.batch_size;
      }

      if (settings.batch_timeout !== undefined) {
        this.batchTimeout = settings.batch_timeout;
      }
    }
  }

  private handleSnapshotComplete(message: WSMessage): void {
    logger.info('Snapshot complete:', message.p);
    window.dispatchEvent(new CustomEvent('snapshotComplete', {
      detail: message.p
    }));
  }

  private handleHeartbeat(): void {
    const store = useWSEStore.getState();
    store.updateMetrics({ lastHealthCheck: Date.now() });
  }

  private handlePong(message: WSMessage): void {
    // JSON PONG format: {"t":"PONG","p":{"client_timestamp":123,"server_timestamp":456}}
    const payload = message.p || {};
    const clientTimestamp = payload.client_timestamp || payload.timestamp;

    if (clientTimestamp) {
      const latency = Date.now() - clientTimestamp;
      const store = useWSEStore.getState();
      store.recordLatency(latency);
      logger.debug(`PONG latency: ${latency}ms`);
    }
  }

  private handleDebugResponse(message: WSMessage): void {
    logger.info('Debug response received:', message.p);
    window.dispatchEvent(new CustomEvent('debugResponse', {
      detail: message.p
    }));
  }

  private handleSequenceStatsResponse(message: WSMessage): void {
    logger.info('Sequence stats received:', message.p);
    window.dispatchEvent(new CustomEvent('sequenceStatsResponse', {
      detail: message.p
    }));
  }

  private handleConfigResponse(message: WSMessage): void {
    logger.info('Configuration response:', message.p);
    window.dispatchEvent(new CustomEvent('configResponse', {
      detail: message.p
    }));
  }

  private handleConfigUpdateResponse(message: WSMessage): void {
    logger.info('Configuration update response:', message.p);
    window.dispatchEvent(new CustomEvent('configUpdateResponse', {
      detail: message.p
    }));
  }

  private handleEncryptionResponse(message: WSMessage): void {
    logger.info('Encryption response:', message.p);
    const store = useWSEStore.getState();

    if (message.p.enabled !== undefined) {
      store.updateSecurity({
        encryptionEnabled: message.p.enabled,
        encryptionAlgorithm: message.p.algorithms?.encryption || null
      });
    }

    window.dispatchEvent(new CustomEvent('encryptionResponse', {
      detail: message.p
    }));
  }

  private handleKeyRotationResponse(message: WSMessage): void {
    logger.info('Key rotation response:', message.p);
    const store = useWSEStore.getState();

    if (message.p.success) {
      store.updateSecurity({
        lastKeyRotation: Date.now()
      });
    }

    window.dispatchEvent(new CustomEvent('keyRotationResponse', {
      detail: message.p
    }));
  }

  private handleBatchMessage(message: WSMessage): void {
    const payload = message.p;
    logger.info(`Batch message received with ${payload.count} messages`);

    // Process each message in the batch
    if (payload.messages && Array.isArray(payload.messages)) {
      payload.messages.forEach(async (msg: WSMessage) => {
        await this.routeMessage(msg);
      });
    }
  }

  private handleBatchMessageResult(message: WSMessage): void {
    logger.info('Batch message result:', message.p);
    window.dispatchEvent(new CustomEvent('batchMessageResult', {
      detail: message.p
    }));
  }

  private handleMetricsResponse(message: WSMessage): void {
    logger.info('Metrics response received:', message.p);
    window.dispatchEvent(new CustomEvent('metricsResponse', {
      detail: message.p
    }));
  }

  private handleConnectionStateResponse(message: WSMessage): void {
    const payload = message.p;
    logger.info('Connection state response:', payload);

    const store = useWSEStore.getState();

    // Update metrics if provided
    if (payload.metrics) {
      store.updateMetrics(payload.metrics);
    }

    window.dispatchEvent(new CustomEvent('connectionStateResponse', {
      detail: payload
    }));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Outgoing Messages with Race Condition Fix
  // ─────────────────────────────────────────────────────────────────────────

  queueOutgoing(
    message: Partial<WSMessage>,
    priority: MessagePriority = MessagePriority.NORMAL
  ): boolean {
    if (this.destroyed) return false;

    const queueStore = useMessageQueueStore.getState();

    const queuedMessage: QueuedMessage = {
      id: message.id || crypto.randomUUID(),
      type: message.t || 'unknown',
      payload: message.p || {},
      priority,
      timestamp: Date.now(),
      retries: 0,
    };

    const queued = queueStore.enqueue(queuedMessage);

    if (queued) {
      this.scheduleBatch();
    }

    return queued;
  }

  // Use promise-based scheduling to prevent race conditions
  private scheduleBatch(): void {
    if (this.destroyed || this.batchPromise) return;

    this.batchPromise = new Promise((resolve) => {
      const timer = setTimeout(() => {
        if (this.destroyed) {
          resolve();
          return;
        }

        this.processBatchSafe()
          .then(resolve)
          .catch((error) => {
            logger.error('Batch processing error:', error);
            resolve();
          })
          .finally(() => {
            this.batchPromise = null;
          });
      }, this.batchTimeout);

      // Store timer for cleanup
      if (this.batchTimer) clearTimeout(this.batchTimer);
      this.batchTimer = timer;
    });
  }

  private async processBatchSafe(): Promise<void> {
    if (this.processing || this.destroyed) return;

    this.processing = true;
    try {
      await this.processBatch();
    } finally {
      this.processing = false;
    }
  }

  async processBatch(): Promise<WSMessage[]> {
    if (this.destroyed) return [];

    const queueStore = useMessageQueueStore.getState();
    queueStore.setProcessing(true);

    try {
      const messages = queueStore.dequeue(this.batchSize);

      if (messages.length === 0) {
        return [];
      }

      // Maintain order by timestamp for the same priority
      messages.sort((a, b) => {
        if (a.priority !== b.priority) {
          return b.priority - a.priority; // Higher priority first
        }
        return a.timestamp - b.timestamp; // Older first for the same priority
      });

      // Convert to WebSocket messages
      const wsMessages: WSMessage[] = messages.map(msg => ({
        id: msg.id,
        t: msg.type,
        p: msg.payload,
        v: WS_PROTOCOL_VERSION,
        seq: this.sequencer.getNextSequence(),
        ts: new Date().toISOString(),
        pri: msg.priority,
      }));

      const store = useWSEStore.getState();
      store.incrementMetric('messagesSent', wsMessages.length);

      return wsMessages;

    } finally {
      queueStore.setProcessing(false);

      // Schedule next batch if queue not empty
      if (queueStore.size > 0 && !this.destroyed) {
        this.scheduleBatch();
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────

  registerHandler(type: string, handler: (message: WSMessage) => void): void {
    // Silent registration - summary logged by caller
    this.messageHandlers.set(type, handler);
  }

  unregisterHandler(type: string): void {
    logger.info(`Unregistering handler for message type: ${type}`);
    this.messageHandlers.delete(type);
  }

  clearHandlers(): void {
    logger.info('Clearing all message handlers');
    this.messageHandlers.clear();
    this.registerDefaultHandlers();
  }

  getRegisteredHandlers(): string[] {
    return Array.from(this.messageHandlers.keys());
  }

  isHandlerRegistered(type: string): boolean {
    return this.messageHandlers.has(type);
  }

  waitForHandlers(requiredHandlers: string[], timeout: number = 5000): Promise<boolean> {
    return new Promise((resolve) => {
      const checkHandlers = () => {
        const allRegistered = requiredHandlers.every(h => this.isHandlerRegistered(h));
        if (allRegistered) {
          resolve(true);
          return;
        }
        return false;
      };

      // Check immediately
      if (checkHandlers()) return;

      // Set up polling
      const startTime = Date.now();
      const interval = setInterval(() => {
        if (checkHandlers() || Date.now() - startTime > timeout) {
          clearInterval(interval);
          resolve(this.isReady);
        }
      }, 100);
    });
  }

  destroy(): void {
    this.destroyed = true;

    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }

    this.batchPromise = null;
    this.clearHandlers();
    this.sequencer.destroy();

    // Clear server ready state
    this.serverReadyProcessed = false;
    this.serverReadyDetails = null;
  }
}