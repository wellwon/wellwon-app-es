// =============================================================================
// File: src/wse/handlers/EventHandlers.ts
// Description: Generic event handlers for WebSocket Event System (WSE)
// =============================================================================

import { WSMessage } from '@/wse';
import { useSystemStatusStore } from '@/stores/useSystemStatusStore';
import { logger } from '@/wse';
import { queryClient } from '@/lib/queryClient';

export class EventHandlers {

  // ─────────────────────────────────────────────────────────────────────────
  // User Account Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleUserAccountUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      logger.info('User account update received:', update);

      // Dispatch event for UI components
      window.dispatchEvent(new CustomEvent('userAccountUpdated', {
        detail: update
      }));
    } catch (error) {
      logger.error('Error handling user account update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Generic Entity Update Handler
  // ─────────────────────────────────────────────────────────────────────────

  static handleEntityUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      const entityType = update.entity_type || 'unknown';

      logger.info(`Entity update received for ${entityType}:`, update);

      // Dispatch generic entity event
      window.dispatchEvent(new CustomEvent('entityUpdated', {
        detail: {
          entityType,
          data: update
        }
      }));
    } catch (error) {
      logger.error('Error handling entity update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // System Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleSystemAnnouncement(message: WSMessage): void {
    try {
      const announcement = message.p;

      logger.info('System announcement:', announcement);

      window.dispatchEvent(new CustomEvent('systemAnnouncement', {
        detail: {
          id: announcement.id || crypto.randomUUID(),
          type: announcement.type || 'info',
          title: announcement.title,
          message: announcement.message,
          timestamp: announcement.timestamp || new Date().toISOString(),
          priority: announcement.priority || 'normal',
          dismissible: announcement.dismissible ?? true,
          action: announcement.action,
          expires_at: announcement.expires_at,
        }
      }));

      switch (announcement.type) {
        case 'maintenance':
          logger.warn(`Scheduled maintenance: ${announcement.message}`);
          break;
        case 'error':
          logger.error(`System error announcement: ${announcement.message}`);
          break;
        case 'warning':
          logger.warn(`System warning: ${announcement.message}`);
          break;
      }
    } catch (error) {
      logger.error('Error handling system announcement:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // System Status Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleSystemStatus(message: WSMessage): void {
    try {
      const status = message.p;
      const systemStatusStore = useSystemStatusStore.getState();

      logger.info('System status update received:', status);

      systemStatusStore.setStatus(status);

      window.dispatchEvent(new CustomEvent('systemStatus', {
        detail: status
      }));
    } catch (error) {
      logger.error('Error handling system status:', error);
    }
  }

  static handleSystemHealthUpdate(message: WSMessage): void {
    try {
      const healthData = message.p;
      const systemStatusStore = useSystemStatusStore.getState();

      logger.info('System health update received:', healthData);

      const systemStatus = {
        api: healthData.api_status || healthData.api || 'unknown',
        api_status: healthData.api_status || 'unknown',
        datafeed_status: healthData.datafeed_status || 'unknown',
        redis: healthData.redis_status || healthData.redis || 'unknown',
        event_bus: healthData.event_bus_status || healthData.event_bus || 'unknown',
        cpu_usage: healthData.cpu_usage,
        memory_usage: healthData.memory_usage,
        lastBackup: healthData.last_backup || healthData.lastBackup,
        active_connections: healthData.active_connections,
        event_queue_size: healthData.event_queue_size,
        adapter_statuses: healthData.adapter_statuses,
        module_statuses: healthData.module_statuses,
        circuit_breakers: healthData.circuit_breakers,
        uptime: healthData.uptime,
      };

      systemStatusStore.setStatus(systemStatus);

      window.dispatchEvent(new CustomEvent('systemStatus', {
        detail: systemStatus
      }));
    } catch (error) {
      logger.error('Error handling system health update:', error);
    }
  }

  static handleComponentHealth(message: WSMessage): void {
    try {
      const healthUpdate = message.p;

      logger.info('Component health update received:', healthUpdate);

      if (healthUpdate.component && healthUpdate.status) {
        window.dispatchEvent(new CustomEvent('componentHealth', {
          detail: {
            component: healthUpdate.component,
            status: healthUpdate.status,
            message: healthUpdate.message,
            timestamp: healthUpdate.timestamp || new Date().toISOString(),
          }
        }));
      } else if (healthUpdate.components) {
        Object.entries(healthUpdate.components).forEach(([component, status]) => {
          window.dispatchEvent(new CustomEvent('componentHealth', {
            detail: {
              component,
              status,
              timestamp: healthUpdate.timestamp || new Date().toISOString(),
            }
          }));
        });
      }
    } catch (error) {
      logger.error('Error handling component health:', error);
    }
  }

  static handlePerformanceMetrics(message: WSMessage): void {
    try {
      const metrics = message.p;

      logger.debug('Performance metrics received:', metrics);

      window.dispatchEvent(new CustomEvent('performanceMetrics', {
        detail: {
          cpu_usage: metrics.cpu_usage,
          memory_usage: metrics.memory_usage,
          event_queue_size: metrics.event_queue_size,
          active_connections: metrics.active_connections,
          uptime: metrics.uptime,
          timestamp: metrics.timestamp || new Date().toISOString(),
        }
      }));
    } catch (error) {
      logger.error('Error handling performance metrics:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Notification Handler
  // ─────────────────────────────────────────────────────────────────────────

  static handleNotification(message: WSMessage): void {
    try {
      const notification = message.p;

      logger.info('Notification received:', notification);

      window.dispatchEvent(new CustomEvent('notification', {
        detail: {
          id: notification.id || crypto.randomUUID(),
          type: notification.type || 'info',
          title: notification.title,
          message: notification.message,
          timestamp: notification.timestamp || new Date().toISOString(),
          priority: notification.priority || 'normal',
          dismissible: notification.dismissible ?? true,
          action: notification.action,
        }
      }));
    } catch (error) {
      logger.error('Error handling notification:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Register All Handlers
  // ─────────────────────────────────────────────────────────────────────────

  static registerAll(messageProcessor: any): void {
    logger.info('=== REGISTERING GENERIC EVENT HANDLERS ===');

    try {
      // User account events
      messageProcessor.registerHandler('user_account_update', this.handleUserAccountUpdate);

      // Generic entity events
      messageProcessor.registerHandler('entity_update', this.handleEntityUpdate);

      // System events
      messageProcessor.registerHandler('system_announcement', this.handleSystemAnnouncement);
      messageProcessor.registerHandler('system_status', this.handleSystemStatus);
      messageProcessor.registerHandler('system_health_update', this.handleSystemHealthUpdate);
      messageProcessor.registerHandler('component_health', this.handleComponentHealth);
      messageProcessor.registerHandler('performance_metrics', this.handlePerformanceMetrics);

      // Notification events
      messageProcessor.registerHandler('notification', this.handleNotification);

      logger.info('All generic event handlers registered successfully');

      // Log the registered handlers for debugging
      const registeredHandlers = messageProcessor.getRegisteredHandlers();
      logger.info('Registered handlers:', registeredHandlers);

    } catch (error) {
      logger.error('Error registering event handlers:', error);
      throw error;
    }
  }
}
