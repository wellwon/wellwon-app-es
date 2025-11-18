// =============================================================================
// File: src/wse/protocols/transformer.ts
// Description: Event transformation between internal and WebSocket formats
// =============================================================================

import {
  WSMessage,
  BrokerConnectionUpdate,
  AccountUpdate,
} from '@/wse';

// Event type mappings - UPDATED Nov 13, 2025
const INTERNAL_TO_WS_EVENT_TYPE_MAP: Record<string, string> = {
  // =========================================================================
  // DOMAIN EVENTS → broker_connection_events topic
  // =========================================================================
  // Broker connection lifecycle (OAuth, credentials, saga completion)
  'BrokerConnectionInitiated': 'broker_connection_update',
  'BrokerConnectionEstablished': 'broker_connection_update',
  'BrokerConnectionEstablishedSagaCompleted': 'broker_connection_update',
  'BrokerConnectionRestored': 'broker_connection_update',
  'BrokerConnectionAttemptFailed': 'broker_connection_update',
  'BrokerDisconnected': 'broker_connection_update',
  'BrokerTokensSuccessfullyStored': 'broker_connection_update',
  'BrokerTokensSuccessfullyRefreshed': 'broker_connection_update',
  'BrokerOAuthClientCredentialsStored': 'broker_connection_update',
  'BrokerApiEndpointConfigured': 'broker_connection_update',
  'BrokerApiCredentialsStored': 'broker_connection_update',
  'BrokerConnectionPurged': 'broker_status_remove',

  // =========================================================================
  // MONITORING EVENTS → broker_health topic (NEW! Nov 13, 2025)
  // =========================================================================
  // REST API health checks and module health
  'BrokerConnectionHealthUpdated': 'broker_health_update',
  'BrokerConnectionHealthChecked': 'broker_health_update',
  'BrokerConnectionModuleHealthChanged': 'broker_health_update',

  // =========================================================================
  // MONITORING EVENTS → broker_streaming topic (Nov 13, 2025)
  // =========================================================================
  // WebSocket/HTTP Chunked streaming lifecycle
  'streaming_connection_status': 'broker_streaming_update',
  'streaming_subscription_started': 'broker_streaming_update',
  'streaming_subscription_stopped': 'broker_streaming_update',
  'streaming_error': 'broker_streaming_update',

  // =========================================================================
  // REAL-TIME DATA → market_data topic (Nov 13, 2025)
  // =========================================================================
  // Market data streams (quotes, trades, bars, orderbook)
  'quote_update': 'quote_update',
  'trade_update': 'trade_update',
  'bar_update': 'bar_update',
  'orderbook_update': 'orderbook_update',

  // Account events
  'AccountDataFromBrokerUpdated': 'account_update',
  'BrokerAccountLinked': 'account_update',
  'UserSetAccountDetailsChanged': 'account_update',
  'UserAccountMarkedDeleted': 'account_remove',
  'BrokerAccountDeleted': 'account_remove',
  'BrokerAccountsDeleted': 'accounts_bulk_remove',
  'BrokerAccountBatchDeleted': 'accounts_bulk_remove',
  'BrokerAccountRecovered': 'account_update',
  'AccountDeleted': 'account_remove',

  // Trading events
  'PositionUpdated': 'position_update',
  'OrderExecuted': 'order_update',
  'OrderStatusChanged': 'order_update',
  'OrderRejected': 'order_update',
  'OrderCancelled': 'order_update',
  'OrderPartiallyFilled': 'order_update',

  // Strategy events
  'AutomationUpdated': 'automation_update',
  'AutomationExecutionStarted': 'automation_update',
  'AutomationExecutionCompleted': 'automation_update',

  // System events
  'SystemAnnouncement': 'system_announcement',
  'MarketDataUpdate': 'market_data_update',
};

export class EventTransformer {
  // ─────────────────────────────────────────────────────────────────────────
  // Main Transformation
  // ─────────────────────────────────────────────────────────────────────────

  transformForWS(event: any, sequence: number = 0): WSMessage {
    const eventType = event.event_type || event.type;

    // Map internal event type to WebSocket event type
    const wsEventType = INTERNAL_TO_WS_EVENT_TYPE_MAP[eventType] || eventType?.toLowerCase() || 'unknown';

    // Extract metadata
    const metadata = event._metadata || {};

    const payload = this.transformPayload(wsEventType, event);

    // Build WebSocket-compatible event
    const wsEvent: WSMessage = {
      v: 2, // Protocol version
      id: metadata.event_id || event.event_id || crypto.randomUUID(),
      t: wsEventType,
      ts: metadata.timestamp || event.timestamp || new Date().toISOString(),
      seq: sequence,
      p: payload,
    };

    return wsEvent;
  }

  private transformPayload(wsEventType: string, event: any): any {
    switch (wsEventType) {
      case 'broker_connection_update':
        return this.transformBrokerConnection(event);

      case 'broker_health_update':
        return this.transformBrokerHealth(event);

      case 'broker_module_health_update':
        return this.transformModuleHealth(event);

      case 'broker_streaming_update':
        return this.transformBrokerStreaming(event);

      case 'account_update':
        return this.transformAccount(event);

      case 'position_update':
        return this.transformPosition(event);

      case 'order_update':
        return this.transformOrder(event);

      default:
        return this.extractGenericPayload(event);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Specific Transformations
  // ─────────────────────────────────────────────────────────────────────────

  transformBrokerConnection(event: any): BrokerConnectionUpdate {
    return {
      broker_connection_id: String(event.broker_connection_id || ''),
      broker_id: event.broker_id,
      environment: event.environment || 'paper',
      status: event.new_status || event.status || 'UNKNOWN',
      reauth_required: event.reauth_required || false,
      message: event.reason || event.status_message,
      last_connected_at: event.last_connected_at,
      last_heartbeat_at: event.last_heartbeat_at,
      api_endpoint: event.api_endpoint,
      modules: event.module_health,
    };
  }

  private transformBrokerHealth(event: any): any {
    return {
      broker_connection_id: String(event.broker_connection_id || ''),
      broker_id: event.broker_id,
      environment: event.environment,
      is_healthy: event.is_healthy ?? true,
      health_status: event.health_status || (event.is_healthy ? 'healthy' : 'unhealthy'),
      response_time_ms: event.response_time_ms,
      message: event.message,
      modules: event.modules || event.module_health,
      last_checked: event.checked_at || event.last_checked || new Date().toISOString(),
    };
  }

  private transformBrokerStreaming(event: any): any {
    return {
      broker_connection_id: String(event.broker_connection_id || ''),
      broker_id: event.broker_id,
      environment: event.environment,
      stream_type: event.stream_type,
      status: event.status,
      message: event.message,
      timestamp: event.timestamp || new Date().toISOString(),
    };
  }

  private transformModuleHealth(event: any): any {
    const moduleName = event.module_name || 'unknown';

    return {
      broker_connection_id: String(event.broker_connection_id || ''),
      module_updates: {
        [moduleName]: {
          module_id: moduleName,
          module_type: moduleName,
          is_healthy: event.is_healthy || false,
          status: event.is_healthy ? 'healthy' : 'unhealthy',
          message: event.message,
          details: event.error_details,
          last_checked: new Date().toISOString(),
        }
      }
    };
  }

  transformAccount(event: any): AccountUpdate {
    return {
      id: String(event.account_id || event.id || ''),
      broker_connection_id: event.broker_connection_id ? String(event.broker_connection_id) : undefined,
      broker_id: event.broker_id || 'unknown',
      environment: event.environment || 'paper',
      asset_type: event.asset_type || 'UNKNOWN',
      broker_account_id: event.broker_account_id || '',
      account_name: event.account_name,
      balance: String(event.balance || 0),
      currency: event.currency || 'USD',
      equity: event.equity !== undefined ? String(event.equity) : undefined,
      buying_power: event.buying_power !== undefined ? String(event.buying_power) : undefined,
      status: event.status,
      account_type: event.account_type,
      metadata: event.metadata,
      deleted: event.deleted || false,
      archived: event.archived,
      last_synced_at: event.last_synced_at,
      created_at: event.created_at || new Date().toISOString(),
      updated_at: event.updated_at,
      positions: this.transformPositions(event.positions),
      open_orders_count: event.open_orders_count,
      daily_pnl: event.daily_pnl !== undefined ? String(event.daily_pnl) : undefined,
      daily_pnl_percent: event.daily_pnl_percent !== undefined ? String(event.daily_pnl_percent) : undefined,
    };
  }

  private transformPositions(positions: any[]): any[] | undefined {
    if (!positions || !Array.isArray(positions)) return undefined;

    return positions.map(pos => ({
      symbol: pos.symbol || '',
      quantity: String(pos.quantity || 0),
      side: pos.side || 'long',
      market_value: pos.market_value !== undefined ? String(pos.market_value) : undefined,
      avg_cost: pos.avg_cost !== undefined ? String(pos.avg_cost) : undefined,
      unrealized_pnl: pos.unrealized_pnl !== undefined ? String(pos.unrealized_pnl) : undefined,
      unrealized_pnl_percent: pos.unrealized_pnl_percent !== undefined ? String(pos.unrealized_pnl_percent) : undefined,
      asset_class: pos.asset_class,
    }));
  }

  private transformPosition(event: any): any {
    return {
      symbol: event.symbol || '',
      quantity: String(event.quantity || 0),
      side: event.side || 'long',
      market_value: event.market_value !== undefined ? String(event.market_value) : undefined,
      avg_cost: event.avg_cost !== undefined ? String(event.avg_cost) : undefined,
      unrealized_pnl: event.unrealized_pnl !== undefined ? String(event.unrealized_pnl) : undefined,
      unrealized_pnl_percent: event.unrealized_pnl_percent !== undefined ? String(event.unrealized_pnl_percent) : undefined,
      asset_class: event.asset_class,
    };
  }

  private transformOrder(event: any): any {
    return {
      order_id: String(event.order_id || ''),
      client_order_id: event.client_order_id,
      account_id: String(event.account_id || ''),
      symbol: event.symbol || '',
      side: event.side || '',
      quantity: String(event.quantity || 0),
      order_type: event.order_type || '',
      status: event.status || '',
      filled_quantity: event.filled_quantity !== undefined ? String(event.filled_quantity) : undefined,
      avg_fill_price: event.avg_fill_price !== undefined ? String(event.avg_fill_price) : undefined,
      limit_price: event.limit_price !== undefined ? String(event.limit_price) : undefined,
      stop_price: event.stop_price !== undefined ? String(event.stop_price) : undefined,
      time_in_force: event.time_in_force,
      created_at: event.created_at || new Date().toISOString(),
      updated_at: event.updated_at,
    };
  }

  private extractGenericPayload(event: any): any {
    // Remove metadata and extract actual payload
    const payload = event.payload || event;

    if ('_metadata' in payload) {
      const { _metadata, ...rest } = payload;
      return rest;
    }

    // Ensure event_type is set if a type is provided
    if ('type' in payload && !('event_type' in payload)) {
      payload.event_type = payload.type;
    }

    return payload;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Reverse Transformation (WS to Internal)
  // ─────────────────────────────────────────────────────────────────────────

  transformFromWS(wsMessage: WSMessage): any {
    const internalEvent: any = {
      event_type: this.mapWSEventTypeToInternal(wsMessage.t),
      timestamp: wsMessage.ts,
      event_id: wsMessage.id,
      sequence: wsMessage.seq,
      ...wsMessage.p,
    };

    return internalEvent;
  }

  private mapWSEventTypeToInternal(wsType: string): string {
    // Reverse mapping
    for (const [internal, ws] of Object.entries(INTERNAL_TO_WS_EVENT_TYPE_MAP)) {
      if (ws === wsType) {
        return internal;
      }
    }

    // Default: capitalize the first letter
    return wsType.charAt(0).toUpperCase() + wsType.slice(1);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Utilities
  // ─────────────────────────────────────────────────────────────────────────

  isKnownEventType(eventType: string): boolean {
    return eventType in INTERNAL_TO_WS_EVENT_TYPE_MAP;
  }

  getWSEventType(internalType: string): string {
    return INTERNAL_TO_WS_EVENT_TYPE_MAP[internalType] || internalType.toLowerCase();
  }
}

// Singleton instance
export const eventTransformer = new EventTransformer();