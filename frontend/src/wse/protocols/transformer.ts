// =============================================================================
// File: src/wse/protocols/transformer.ts
// Description: Event transformation between internal and WebSocket formats
// =============================================================================

import { WSMessage } from '@/wse';

// Event type mappings
const INTERNAL_TO_WS_EVENT_TYPE_MAP: Record<string, string> = {
  // User account events
  'UserAccountUpdated': 'user_account_update',
  'UserAccountDeleted': 'user_account_remove',
  'UserProfileUpdated': 'user_profile_updated',

  // Generic entity events
  'EntityUpdated': 'entity_update',
  'EntityCreated': 'entity_create',
  'EntityDeleted': 'entity_remove',

  // System events
  'SystemAnnouncement': 'system_announcement',
  'SystemHealthUpdate': 'system_health_update',
  'ComponentHealthUpdate': 'component_health',
  'PerformanceMetricsUpdate': 'performance_metrics',

  // Notification events
  'NotificationCreated': 'notification',
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
      case 'user_account_update':
        return this.transformUserAccount(event);

      case 'system_health_update':
      case 'component_health':
      case 'performance_metrics':
        return this.transformSystemMetrics(event);

      default:
        return this.extractGenericPayload(event);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Specific Transformations
  // ─────────────────────────────────────────────────────────────────────────

  private transformUserAccount(event: any): any {
    return {
      user_id: String(event.user_id || event.id || ''),
      username: event.username,
      email: event.email,
      role: event.role,
      is_active: event.is_active ?? true,
      email_verified: event.email_verified ?? false,
      mfa_enabled: event.mfa_enabled ?? false,
      created_at: event.created_at || new Date().toISOString(),
      updated_at: event.updated_at,
      metadata: event.metadata,
    };
  }

  private transformSystemMetrics(event: any): any {
    return {
      component: event.component,
      status: event.status,
      message: event.message,
      metrics: event.metrics,
      cpu_usage: event.cpu_usage,
      memory_usage: event.memory_usage,
      event_queue_size: event.event_queue_size,
      active_connections: event.active_connections,
      uptime: event.uptime,
      timestamp: event.timestamp || new Date().toISOString(),
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
