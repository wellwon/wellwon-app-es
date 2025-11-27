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

  static handleUserProfileUpdated(message: WSMessage): void {
    try {
      const profileData = message.p;
      logger.info('User profile updated event received:', profileData);

      // Invalidate React Query cache for profile
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });

      // Dispatch event for AuthContext
      window.dispatchEvent(new CustomEvent('userProfileUpdated', {
        detail: profileData
      }));
    } catch (error) {
      logger.error('Error handling user profile update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CES Events (Compensating Event System - External Admin Changes)
  // Pattern: Greg Young's Compensating Events via PostgreSQL triggers
  // These notify frontend when admin changes user data directly in SQL
  // ─────────────────────────────────────────────────────────────────────────

  static handleUserAdminChange(message: WSMessage): void {
    try {
      const data = message.p?.data || message.p;
      logger.info('CES: User admin change detected:', data);

      // Extract key fields from the CES event
      const changedFields = data.changed_fields || {};
      const userId = data.user_id;
      const isDeveloper = data.is_developer;
      const role = data.role;
      const userType = data.user_type;
      const isActive = data.is_active;
      const emailVerified = data.email_verified;
      const isCompensatingEvent = data.compensating_event || false;
      const detectedBy = data.detected_by;

      logger.info('CES Event Details:', {
        userId,
        isDeveloper,
        role,
        userType,
        isActive,
        emailVerified,
        changedFields: Object.keys(changedFields),
        isCompensatingEvent,
        detectedBy
      });

      // Invalidate React Query cache for user profile (forces re-fetch)
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
      queryClient.invalidateQueries({ queryKey: ['user', userId] });

      // Dispatch event for AuthContext to update local state
      window.dispatchEvent(new CustomEvent('userAdminChange', {
        detail: {
          userId,
          isDeveloper,
          role,
          userType,
          isActive,
          emailVerified,
          changedFields,
          isCompensatingEvent,
          detectedBy,
          timestamp: data.timestamp || new Date().toISOString()
        }
      }));

      // If developer status changed, dispatch specific event
      if ('is_developer' in changedFields) {
        window.dispatchEvent(new CustomEvent('developerStatusChanged', {
          detail: {
            userId,
            isDeveloper,
            oldValue: changedFields.is_developer?.old,
            newValue: changedFields.is_developer?.new
          }
        }));
        logger.info(`CES: Developer status changed for user ${userId}: ${changedFields.is_developer?.old} -> ${changedFields.is_developer?.new}`);
      }

      // If role changed, dispatch specific event (security-critical)
      if ('role' in changedFields) {
        window.dispatchEvent(new CustomEvent('userRoleChanged', {
          detail: {
            userId,
            role,
            oldValue: changedFields.role?.old,
            newValue: changedFields.role?.new
          }
        }));
        logger.warn(`CES: User role changed for user ${userId}: ${changedFields.role?.old} -> ${changedFields.role?.new}`);
      }

      // If account status changed (ban/unban)
      if ('is_active' in changedFields) {
        window.dispatchEvent(new CustomEvent('userStatusChanged', {
          detail: {
            userId,
            isActive,
            oldValue: changedFields.is_active?.old,
            newValue: changedFields.is_active?.new
          }
        }));
        logger.warn(`CES: User status changed for user ${userId}: ${changedFields.is_active?.old} -> ${changedFields.is_active?.new}`);
      }

    } catch (error) {
      logger.error('Error handling CES user admin change:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Company Domain Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleCompanyCreated(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company created:', company);

      // Invalidate company list queries
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      queryClient.invalidateQueries({ queryKey: ['my-companies'] });

      window.dispatchEvent(new CustomEvent('companyCreated', { detail: company }));
    } catch (error) {
      logger.error('Error handling company created:', error);
    }
  }

  static handleCompanyUpdated(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company updated:', company);

      // Invalidate specific company and list queries
      queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });

      window.dispatchEvent(new CustomEvent('companyUpdated', { detail: company }));
    } catch (error) {
      logger.error('Error handling company updated:', error);
    }
  }

  static handleCompanyArchived(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company archived:', company);

      queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      queryClient.invalidateQueries({ queryKey: ['my-companies'] });

      window.dispatchEvent(new CustomEvent('companyArchived', { detail: company }));
    } catch (error) {
      logger.error('Error handling company archived:', error);
    }
  }

  static handleCompanyRestored(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company restored:', company);

      queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });

      window.dispatchEvent(new CustomEvent('companyRestored', { detail: company }));
    } catch (error) {
      logger.error('Error handling company restored:', error);
    }
  }

  static handleCompanyDeleted(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company deleted:', company);

      queryClient.removeQueries({ queryKey: ['company', company.company_id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      queryClient.invalidateQueries({ queryKey: ['my-companies'] });

      window.dispatchEvent(new CustomEvent('companyDeleted', { detail: company }));
    } catch (error) {
      logger.error('Error handling company deleted:', error);
    }
  }

  static handleCompanyMemberJoined(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member joined:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });
      queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

      window.dispatchEvent(new CustomEvent('companyMemberJoined', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member joined:', error);
    }
  }

  static handleCompanyMemberLeft(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member left:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });
      queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

      window.dispatchEvent(new CustomEvent('companyMemberLeft', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member left:', error);
    }
  }

  static handleCompanyMemberRoleChanged(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member role changed:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });

      window.dispatchEvent(new CustomEvent('companyMemberRoleChanged', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member role changed:', error);
    }
  }

  static handleCompanyTelegramCreated(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group created:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramCreated', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram created:', error);
    }
  }

  static handleCompanyTelegramLinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group linked:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramLinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram linked:', error);
    }
  }

  static handleCompanyTelegramUnlinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group unlinked:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramUnlinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram unlinked:', error);
    }
  }

  static handleCompanyBalanceUpdated(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company balance updated:', data);

      queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'balance'] });
      queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

      window.dispatchEvent(new CustomEvent('companyBalanceUpdated', { detail: data }));
    } catch (error) {
      logger.error('Error handling company balance updated:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Chat Domain Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleChatCreated(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat created:', chat);

      queryClient.invalidateQueries({ queryKey: ['chats'] });

      window.dispatchEvent(new CustomEvent('chatCreated', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat created:', error);
    }
  }

  static handleChatUpdated(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat updated:', chat);

      queryClient.invalidateQueries({ queryKey: ['chat', chat.chat_id] });
      queryClient.invalidateQueries({ queryKey: ['chats'] });

      window.dispatchEvent(new CustomEvent('chatUpdated', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat updated:', error);
    }
  }

  static handleChatArchived(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat archived:', chat);

      queryClient.invalidateQueries({ queryKey: ['chat', chat.chat_id] });
      queryClient.invalidateQueries({ queryKey: ['chats'] });

      window.dispatchEvent(new CustomEvent('chatArchived', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat archived:', error);
    }
  }

  static handleChatDeleted(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat deleted:', chat);

      queryClient.removeQueries({ queryKey: ['chat', chat.chat_id] });
      queryClient.invalidateQueries({ queryKey: ['chats'] });

      window.dispatchEvent(new CustomEvent('chatDeleted', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat deleted:', error);
    }
  }

  static handleMessageCreated(message: WSMessage): void {
    try {
      const msg = message.p;

      // Log with source info for debugging Telegram integration
      const source = msg.source || 'web';
      const isTelegram = source === 'telegram' || !!msg.telegram_user_id;
      logger.info('Message created:', {
        message_id: msg.message_id,
        chat_id: msg.chat_id,
        source,
        isTelegram,
        sender_id: msg.sender_id,
        telegram_user_id: msg.telegram_user_id,
        has_telegram_user_data: !!msg.telegram_user_data
      });

      // Invalidate messages for the chat
      queryClient.invalidateQueries({ queryKey: ['chat', msg.chat_id, 'messages'] });
      // Update chat list (for last message preview)
      queryClient.invalidateQueries({ queryKey: ['chats'] });
      // Update unread count
      queryClient.invalidateQueries({ queryKey: ['unread-count'] });

      // Dispatch event with full Telegram data
      window.dispatchEvent(new CustomEvent('messageCreated', {
        detail: {
          ...msg,
          source,
          isTelegram
        }
      }));
    } catch (error) {
      logger.error('Error handling message created:', error);
    }
  }

  static handleMessageUpdated(message: WSMessage): void {
    try {
      const msg = message.p;
      logger.info('Message updated:', msg);

      queryClient.invalidateQueries({ queryKey: ['chat', msg.chat_id, 'messages'] });

      window.dispatchEvent(new CustomEvent('messageUpdated', { detail: msg }));
    } catch (error) {
      logger.error('Error handling message updated:', error);
    }
  }

  static handleMessageDeleted(message: WSMessage): void {
    try {
      const msg = message.p;
      logger.info('Message deleted:', msg);

      queryClient.invalidateQueries({ queryKey: ['chat', msg.chat_id, 'messages'] });

      window.dispatchEvent(new CustomEvent('messageDeleted', { detail: msg }));
    } catch (error) {
      logger.error('Error handling message deleted:', error);
    }
  }

  static handleParticipantJoined(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant joined chat:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });
      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('participantJoined', { detail: data }));
    } catch (error) {
      logger.error('Error handling participant joined:', error);
    }
  }

  static handleParticipantLeft(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant left chat:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });
      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('participantLeft', { detail: data }));
    } catch (error) {
      logger.error('Error handling participant left:', error);
    }
  }

  static handleParticipantRoleChanged(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant role changed:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });

      window.dispatchEvent(new CustomEvent('participantRoleChanged', { detail: data }));
    } catch (error) {
      logger.error('Error handling participant role changed:', error);
    }
  }

  static handleUserTyping(message: WSMessage): void {
    try {
      const data = message.p;
      logger.debug('User typing:', data);

      window.dispatchEvent(new CustomEvent('userTyping', { detail: data }));
    } catch (error) {
      logger.error('Error handling user typing:', error);
    }
  }

  static handleUserStoppedTyping(message: WSMessage): void {
    try {
      const data = message.p;
      logger.debug('User stopped typing:', data);

      window.dispatchEvent(new CustomEvent('userStoppedTyping', { detail: data }));
    } catch (error) {
      logger.error('Error handling user stopped typing:', error);
    }
  }

  static handleMessagesRead(message: WSMessage): void {
    try {
      const data = message.p;
      logger.debug('Messages read:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'messages'] });
      queryClient.invalidateQueries({ queryKey: ['unread-count'] });

      window.dispatchEvent(new CustomEvent('messagesRead', { detail: data }));
    } catch (error) {
      logger.error('Error handling messages read:', error);
    }
  }

  static handleChatTelegramLinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Chat Telegram linked:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('chatTelegramLinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling chat telegram linked:', error);
    }
  }

  static handleChatTelegramUnlinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Chat Telegram unlinked:', data);

      queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('chatTelegramUnlinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling chat telegram unlinked:', error);
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
    logger.info('=== REGISTERING EVENT HANDLERS ===');

    try {
      // User account events
      messageProcessor.registerHandler('user_account_update', this.handleUserAccountUpdate);
      messageProcessor.registerHandler('user_profile_updated', this.handleUserProfileUpdated);

      // CES Events (Compensating Event System - External Admin Changes)
      messageProcessor.registerHandler('user_admin_change', this.handleUserAdminChange);

      // ─────────────────────────────────────────────────────────────────────────
      // Company Domain Events
      // ─────────────────────────────────────────────────────────────────────────
      messageProcessor.registerHandler('company_created', this.handleCompanyCreated);
      messageProcessor.registerHandler('company_updated', this.handleCompanyUpdated);
      messageProcessor.registerHandler('company_archived', this.handleCompanyArchived);
      messageProcessor.registerHandler('company_restored', this.handleCompanyRestored);
      messageProcessor.registerHandler('company_deleted', this.handleCompanyDeleted);
      messageProcessor.registerHandler('company_member_joined', this.handleCompanyMemberJoined);
      messageProcessor.registerHandler('company_member_left', this.handleCompanyMemberLeft);
      messageProcessor.registerHandler('company_member_role_changed', this.handleCompanyMemberRoleChanged);
      messageProcessor.registerHandler('company_telegram_created', this.handleCompanyTelegramCreated);
      messageProcessor.registerHandler('company_telegram_linked', this.handleCompanyTelegramLinked);
      messageProcessor.registerHandler('company_telegram_unlinked', this.handleCompanyTelegramUnlinked);
      messageProcessor.registerHandler('company_balance_updated', this.handleCompanyBalanceUpdated);

      // ─────────────────────────────────────────────────────────────────────────
      // Chat Domain Events
      // ─────────────────────────────────────────────────────────────────────────
      messageProcessor.registerHandler('chat_created', this.handleChatCreated);
      messageProcessor.registerHandler('chat_updated', this.handleChatUpdated);
      messageProcessor.registerHandler('chat_archived', this.handleChatArchived);
      messageProcessor.registerHandler('chat_deleted', this.handleChatDeleted);
      messageProcessor.registerHandler('message_created', this.handleMessageCreated);
      messageProcessor.registerHandler('message_updated', this.handleMessageUpdated);
      messageProcessor.registerHandler('message_deleted', this.handleMessageDeleted);
      messageProcessor.registerHandler('participant_joined', this.handleParticipantJoined);
      messageProcessor.registerHandler('participant_left', this.handleParticipantLeft);
      messageProcessor.registerHandler('participant_role_changed', this.handleParticipantRoleChanged);
      messageProcessor.registerHandler('user_typing', this.handleUserTyping);
      messageProcessor.registerHandler('user_stopped_typing', this.handleUserStoppedTyping);
      messageProcessor.registerHandler('messages_read', this.handleMessagesRead);
      messageProcessor.registerHandler('chat_telegram_linked', this.handleChatTelegramLinked);
      messageProcessor.registerHandler('chat_telegram_unlinked', this.handleChatTelegramUnlinked);

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

      logger.info('All event handlers registered successfully');

      // Log the registered handlers for debugging
      const registeredHandlers = messageProcessor.getRegisteredHandlers();
      logger.info('Registered handlers:', registeredHandlers);

    } catch (error) {
      logger.error('Error registering event handlers:', error);
      throw error;
    }
  }
}
