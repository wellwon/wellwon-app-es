// =============================================================================
// File: src/wse/handlers/EventHandlers.ts
// Description: Generic event handlers for WebSocket Event System (WSE)
// =============================================================================

import { WSMessage } from '@/wse';
import { useSystemStatusStore } from '@/stores/useSystemStatusStore';
import { logger } from '@/wse';
import { queryClient } from '@/lib/queryClient';
import type { Chat } from '@/types/realtime-chat';

// Interface for message processor registration
interface MessageProcessorRegistrar {
  registerHandler(type: string, handler: (message: WSMessage) => void): void;
}

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
      void queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });

      // Dispatch event for AuthContext
      window.dispatchEvent(new CustomEvent('userProfileUpdated', {
        detail: profileData
      }));
    } catch (error) {
      logger.error('Error handling user profile update:', error);
    }
  }

  static handleUserAdminStatusUpdated(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('User admin status updated event received:', data);

      const userId = data.user_id;
      const isActive = data.is_active;
      const isDeveloper = data.is_developer;
      const userType = data.user_type;
      const role = data.role;
      const adminUserId = data.admin_user_id;

      logger.info('Admin status update details:', {
        userId,
        isActive,
        isDeveloper,
        userType,
        role,
        adminUserId
      });

      // Invalidate React Query cache for user profile (forces re-fetch)
      void queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
      void queryClient.invalidateQueries({ queryKey: ['user', userId] });

      // Dispatch event for AuthContext to update local state immediately
      window.dispatchEvent(new CustomEvent('userAdminChange', {
        detail: {
          userId,
          isDeveloper,
          isActive,
          userType,
          role,
          changedFields: {
            ...(isDeveloper !== undefined && { is_developer: { new: isDeveloper } }),
            ...(isActive !== undefined && { is_active: { new: isActive } }),
            ...(userType !== undefined && { user_type: { new: userType } }),
            ...(role !== undefined && { role: { new: role } })
          },
          isCompensatingEvent: false,
          detectedBy: 'admin_panel',
          timestamp: data.timestamp || new Date().toISOString()
        }
      }));

      // Dispatch specific events for granular handling
      if (isDeveloper !== undefined) {
        window.dispatchEvent(new CustomEvent('developerStatusChanged', {
          detail: { userId, isDeveloper, newValue: isDeveloper }
        }));
        logger.info(`Admin panel: Developer status changed for user ${userId}: ${isDeveloper}`);
      }

      if (isActive !== undefined) {
        window.dispatchEvent(new CustomEvent('userStatusChanged', {
          detail: { userId, isActive, newValue: isActive }
        }));
        logger.info(`Admin panel: User status changed for user ${userId}: ${isActive}`);
      }

      if (userType !== undefined) {
        window.dispatchEvent(new CustomEvent('userTypeChanged', {
          detail: { userId, userType, newValue: userType }
        }));
        logger.info(`Admin panel: User type changed for user ${userId}: ${userType}`);
      }

      if (role !== undefined) {
        window.dispatchEvent(new CustomEvent('userRoleChanged', {
          detail: { userId, role, newValue: role }
        }));
        logger.info(`Admin panel: User role changed for user ${userId}: ${role}`);
      }

    } catch (error) {
      logger.error('Error handling user admin status update:', error);
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
      void queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
      void queryClient.invalidateQueries({ queryKey: ['user', userId] });

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

      // Do NOT invalidate here - useSupergroups hook handles its own cache via window events
      // Invalidating here would cause refetch with stale data (projection not yet complete)

      window.dispatchEvent(new CustomEvent('companyCreated', { detail: company }));
    } catch (error) {
      logger.error('Error handling company created:', error);
    }
  }

  static handleCompanyUpdated(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company updated:', company);

      // Only invalidate detail cache
      // Supergroups list is updated optimistically via setQueryData in useSupergroups hook
      void queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });

      window.dispatchEvent(new CustomEvent('companyUpdated', { detail: company }));
    } catch (error) {
      logger.error('Error handling company updated:', error);
    }
  }

  static handleCompanyArchived(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company archived:', company);

      // Only invalidate detail cache
      // Supergroups list is updated optimistically via setQueryData in useSupergroups hook
      void queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });

      window.dispatchEvent(new CustomEvent('companyArchived', { detail: company }));
    } catch (error) {
      logger.error('Error handling company archived:', error);
    }
  }

  static handleCompanyRestored(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company restored:', company);

      // Only invalidate detail cache
      // Supergroups list is updated optimistically via setQueryData in useSupergroups hook
      void queryClient.invalidateQueries({ queryKey: ['company', company.company_id] });

      window.dispatchEvent(new CustomEvent('companyRestored', { detail: company }));
    } catch (error) {
      logger.error('Error handling company restored:', error);
    }
  }

  static handleCompanyDeleted(message: WSMessage): void {
    try {
      const company = message.p;
      logger.info('Company deleted:', company);

      // Remove detail cache
      queryClient.removeQueries({ queryKey: ['company', company.company_id] });
      // Do NOT invalidate lists - they are updated optimistically via setQueryData in useSupergroups hook

      window.dispatchEvent(new CustomEvent('companyDeleted', { detail: company }));
    } catch (error) {
      logger.error('Error handling company deleted:', error);
    }
  }

  static handleCompanyMemberJoined(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member joined:', data);

      // Invalidate company lists so new company appears in sidebar
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
      void queryClient.invalidateQueries({ queryKey: ['my-companies'] });
      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

      window.dispatchEvent(new CustomEvent('companyMemberJoined', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member joined:', error);
    }
  }

  static handleCompanyMemberLeft(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member left:', data);

      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

      window.dispatchEvent(new CustomEvent('companyMemberLeft', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member left:', error);
    }
  }

  static handleCompanyMemberRoleChanged(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company member role changed:', data);

      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'users'] });

      window.dispatchEvent(new CustomEvent('companyMemberRoleChanged', { detail: data }));
    } catch (error) {
      logger.error('Error handling company member role changed:', error);
    }
  }

  static handleCompanyTelegramCreated(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group created:', data);

      // Only invalidate company-specific telegram cache
      // Do NOT invalidate supergroups lists - they are updated optimistically via setQueryData in useSupergroups hook
      // Invalidating would cause refetch that overwrites optimistic data with stale API response
      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramCreated', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram created:', error);
    }
  }

  static handleCompanyTelegramLinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group linked:', data);

      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramLinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram linked:', error);
    }
  }

  static handleCompanyTelegramUnlinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company Telegram group unlinked:', data);

      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'telegram'] });

      window.dispatchEvent(new CustomEvent('companyTelegramUnlinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling company telegram unlinked:', error);
    }
  }

  static handleCompanyBalanceUpdated(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Company balance updated:', data);

      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id, 'balance'] });
      void queryClient.invalidateQueries({ queryKey: ['company', data.company_id] });

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

      // Do NOT invalidate chats list - it's updated via setQueryData in useChatList hook
      // Invalidating would cause refetch that returns stale data (projection not yet complete)

      // Only invalidate counts (these are separate queries)
      void queryClient.invalidateQueries({ queryKey: ['supergroup-chat-counts'] });

      window.dispatchEvent(new CustomEvent('chatCreated', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat created:', error);
    }
  }

  static handleChatUpdated(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat updated:', chat);

      // Only invalidate detail cache, NOT the list!
      // The list is updated optimistically via setQueryData in useChatList hook
      // Invalidating list would cause refetch that overwrites optimistic update with stale data
      void queryClient.invalidateQueries({ queryKey: ['chat', chat.chat_id] });

      window.dispatchEvent(new CustomEvent('chatUpdated', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat updated:', error);
    }
  }

  static handleChatArchived(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat archived:', chat);

      // Only invalidate detail cache, NOT the list!
      // The list is updated optimistically via setQueryData in useChatList hook
      void queryClient.invalidateQueries({ queryKey: ['chat', chat.chat_id] });

      window.dispatchEvent(new CustomEvent('chatArchived', { detail: chat }));
    } catch (error) {
      logger.error('Error handling chat archived:', error);
    }
  }

  static handleChatDeleted(message: WSMessage): void {
    try {
      const chat = message.p;
      logger.info('Chat deleted:', chat);

      // Remove detail cache
      queryClient.removeQueries({ queryKey: ['chat', chat.chat_id] });
      // Do NOT invalidate list - it's updated optimistically via setQueryData in useChatList hook

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

      // NOTE: Do NOT invalidate messages query here!
      // The CustomEvent below triggers useRealtimeChat to add the message directly to state.
      // Invalidating would cause a full refetch, leading to duplicate messages.
      // This follows TkDodo's best practice: for frequent updates, directly update state.

      // Do NOT invalidate chat list here! This causes race condition:
      // - New chat added optimistically
      // - Message created triggers invalidation
      // - API returns stale data (projection not complete)
      // - Optimistic chat disappears
      // Instead, useChatList listens to messageCreated and updates last_message optimistically

      // Update unread count (this is a separate query, safe to invalidate)
      void queryClient.invalidateQueries({ queryKey: ['unread-count'] });

      // Dispatch event with full Telegram data
      // Normalize message_id to id for frontend consistency
      window.dispatchEvent(new CustomEvent('messageCreated', {
        detail: {
          ...msg,
          id: msg.message_id || msg.id,  // Backend sends message_id, frontend expects id
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

      // NOTE: Do NOT invalidate - CustomEvent triggers direct state update in useRealtimeChat
      // Normalize message_id to id for frontend consistency
      window.dispatchEvent(new CustomEvent('messageUpdated', {
        detail: {
          ...msg,
          id: msg.message_id || msg.id
        }
      }));
    } catch (error) {
      logger.error('Error handling message updated:', error);
    }
  }

  static handleMessageDeleted(message: WSMessage): void {
    try {
      const msg = message.p;
      logger.info('Message deleted:', msg);

      // NOTE: Do NOT invalidate - CustomEvent triggers direct state update in useRealtimeChat
      // Normalize message_id to id for frontend consistency
      window.dispatchEvent(new CustomEvent('messageDeleted', {
        detail: {
          ...msg,
          id: msg.message_id || msg.id
        }
      }));
    } catch (error) {
      logger.error('Error handling message deleted:', error);
    }
  }

  static handleParticipantJoined(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant joined chat:', data);

      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });
      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('participantJoined', { detail: data }));
    } catch (error) {
      logger.error('Error handling participant joined:', error);
    }
  }

  static handleParticipantLeft(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant left chat:', data);

      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });
      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      window.dispatchEvent(new CustomEvent('participantLeft', { detail: data }));
    } catch (error) {
      logger.error('Error handling participant left:', error);
    }
  }

  static handleParticipantRoleChanged(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Participant role changed:', data);

      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id, 'participants'] });

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
      logger.debug('Messages read (bidirectional):', {
        chat_id: data.chat_id,
        message_ids: data.message_ids,
        read_by: data.read_by,
        telegram_read_at: data.telegram_read_at,
        source: data.source,
      });

      // NOTE: Do NOT invalidate messages query here!
      // The CustomEvent below triggers useChatMessages to update read status via setQueryData.
      // Invalidating would cause a full refetch, disrupting the smooth checkmark animation.
      // This follows TkDodo's best practice: for frequent updates, directly update state.

      // Only invalidate unread count (separate aggregation query)
      void queryClient.invalidateQueries({ queryKey: ['unread-count'] });

      // Dispatch event for useChatMessages to update message read status directly
      window.dispatchEvent(new CustomEvent('messagesRead', { detail: data }));
    } catch (error) {
      logger.error('Error handling messages read:', error);
    }
  }

  static handleChatTelegramLinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Chat Telegram linked:', data);

      // Invalidate chat detail cache
      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

      // IMPORTANT: Use setQueryData to update the specific chat instead of invalidating
      // invalidateQueries would destroy optimistic entries before projection completes
      // This preserves any optimistically added chats while updating the linked one
      queryClient.setQueryData<Chat[] | undefined>(['chats'], (oldChats) => {
        if (!oldChats) return oldChats;
        return oldChats.map(chat =>
          chat.id === data.chat_id
            ? { ...chat, telegram_supergroup_id: data.telegram_supergroup_id }
            : chat
        );
      });

      // Safe to invalidate counts - these are separate aggregation queries
      void queryClient.invalidateQueries({ queryKey: ['supergroup-chat-counts'] });

      window.dispatchEvent(new CustomEvent('chatTelegramLinked', { detail: data }));
    } catch (error) {
      logger.error('Error handling chat telegram linked:', error);
    }
  }

  static handleChatTelegramUnlinked(message: WSMessage): void {
    try {
      const data = message.p;
      logger.info('Chat Telegram unlinked:', data);

      void queryClient.invalidateQueries({ queryKey: ['chat', data.chat_id] });

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

  static registerAll(messageProcessor: MessageProcessorRegistrar): void {
    try {
      // Define all handlers in a map for batch registration
      const handlers: Record<string, (message: WSMessage) => void> = {
        // User account events
        'user_account_update': this.handleUserAccountUpdate,
        'user_profile_updated': this.handleUserProfileUpdated,
        'user_admin_status_updated': this.handleUserAdminStatusUpdated,
        'user_admin_change': this.handleUserAdminChange,

        // Company domain events
        'company_created': this.handleCompanyCreated,
        'company_updated': this.handleCompanyUpdated,
        'company_archived': this.handleCompanyArchived,
        'company_restored': this.handleCompanyRestored,
        'company_deleted': this.handleCompanyDeleted,
        'company_member_joined': this.handleCompanyMemberJoined,
        'company_member_left': this.handleCompanyMemberLeft,
        'company_member_role_changed': this.handleCompanyMemberRoleChanged,
        'company_telegram_created': this.handleCompanyTelegramCreated,
        'company_telegram_linked': this.handleCompanyTelegramLinked,
        'company_telegram_unlinked': this.handleCompanyTelegramUnlinked,
        'company_balance_updated': this.handleCompanyBalanceUpdated,

        // Chat domain events
        'chat_created': this.handleChatCreated,
        'chat_updated': this.handleChatUpdated,
        'chat_archived': this.handleChatArchived,
        'chat_deleted': this.handleChatDeleted,
        'message_created': this.handleMessageCreated,
        'message_updated': this.handleMessageUpdated,
        'message_deleted': this.handleMessageDeleted,
        'participant_joined': this.handleParticipantJoined,
        'participant_left': this.handleParticipantLeft,
        'participant_role_changed': this.handleParticipantRoleChanged,
        'user_typing': this.handleUserTyping,
        'user_stopped_typing': this.handleUserStoppedTyping,
        'messages_read': this.handleMessagesRead,
        'chat_telegram_linked': this.handleChatTelegramLinked,
        'chat_telegram_unlinked': this.handleChatTelegramUnlinked,

        // Generic and system events
        'entity_update': this.handleEntityUpdate,
        'system_announcement': this.handleSystemAnnouncement,
        'system_status': this.handleSystemStatus,
        'system_health_update': this.handleSystemHealthUpdate,
        'component_health': this.handleComponentHealth,
        'performance_metrics': this.handlePerformanceMetrics,
        'notification': this.handleNotification,
      };

      // Batch register all handlers (no individual logging)
      const handlerNames = Object.keys(handlers);
      for (const [type, handler] of Object.entries(handlers)) {
        messageProcessor.registerHandler(type, handler);
      }

      logger.info(`Registered ${handlerNames.length} event handlers`);

    } catch (error) {
      logger.error('Error registering event handlers:', error);
      throw error;
    }
  }
}
