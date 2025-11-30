# =============================================================================
# File: app/wse/core/event_mappings.py
# Description: Event Type Mappings (Internal Events -> WebSocket Events)
# =============================================================================

"""
Event Type Mappings for WSE

Maps internal domain event types to WebSocket-friendly event types.

Usage:
    ```python
    from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

    internal_event = "UserAccountCreated"
    ws_event_type = INTERNAL_TO_WS_EVENT_TYPE_MAP.get(internal_event)
    # Result: "user_account_update"
    ```

Domains covered:
- User Account events
- System events
"""

# -----------------------------------------------------------------------------
# Internal Event Type -> WebSocket Event Type Mapping
# -----------------------------------------------------------------------------

INTERNAL_TO_WS_EVENT_TYPE_MAP = {
    # =========================================================================
    # USER ACCOUNT DOMAIN EVENTS
    # =========================================================================
    'UserAccountCreated': 'user_account_update',
    'UserAuthenticated': 'user_account_update',
    'UserPasswordChanged': 'user_account_update',
    'UserPasswordReset': 'user_account_update',
    'UserPasswordResetViaSecret': 'user_account_update',
    'UserProfileUpdated': 'user_profile_updated',
    'UserEmailVerified': 'user_account_update',
    'UserAccountDeleted': 'user_account_remove',
    'UserAccountDeactivated': 'user_account_update',
    'UserAccountReactivated': 'user_account_update',
    'UserAdminStatusUpdated': 'user_admin_status_updated',  # Admin panel status changes

    # =========================================================================
    # CES EVENTS (Compensating Event System - External Change Detection)
    # Pattern: Greg Young's Compensating Events via PostgreSQL triggers
    # These notify frontend when admin changes user data directly in SQL
    # =========================================================================
    'UserRoleChangedExternally': 'user_admin_change',
    'UserStatusChangedExternally': 'user_admin_change',
    'UserTypeChangedExternally': 'user_admin_change',
    'UserEmailVerifiedExternally': 'user_admin_change',
    'UserDeveloperStatusChangedExternally': 'user_admin_change',
    'UserAdminFieldsChangedExternally': 'user_admin_change',

    # =========================================================================
    # COMPANY DOMAIN EVENTS
    # =========================================================================
    'CompanyCreated': 'company_created',
    'CompanyUpdated': 'company_updated',
    'CompanyArchived': 'company_archived',
    'CompanyRestored': 'company_restored',
    'CompanyDeleted': 'company_deleted',
    'UserAddedToCompany': 'company_member_joined',
    'UserRemovedFromCompany': 'company_member_left',
    'UserCompanyRoleChanged': 'company_member_role_changed',
    'TelegramSupergroupCreated': 'company_telegram_created',
    'TelegramSupergroupLinked': 'company_telegram_linked',
    'TelegramSupergroupUnlinked': 'company_telegram_unlinked',
    'TelegramSupergroupUpdated': 'company_telegram_updated',
    'CompanyBalanceUpdated': 'company_balance_updated',

    # =========================================================================
    # CHAT DOMAIN EVENTS
    # =========================================================================
    'ChatCreated': 'chat_created',
    'ChatUpdated': 'chat_updated',
    'ChatArchived': 'chat_archived',
    'ChatDeleted': 'chat_deleted',
    'MessageSent': 'message_created',
    'MessageEdited': 'message_updated',
    'MessageDeleted': 'message_deleted',
    'ParticipantAdded': 'participant_joined',
    'ParticipantRemoved': 'participant_left',
    'ParticipantRoleChanged': 'participant_role_changed',
    'UserStartedTyping': 'user_typing',
    'UserStoppedTyping': 'user_stopped_typing',
    'MessagesRead': 'messages_read',
    'TelegramChatLinked': 'chat_telegram_linked',
    'TelegramChatUnlinked': 'chat_telegram_unlinked',
    'TelegramMessageReceived': 'message_created',  # Telegram message → same as regular message

    # =========================================================================
    # SYSTEM EVENTS
    # =========================================================================
    'SystemAnnouncement': 'system_announcement',
    'SystemMaintenanceScheduled': 'system_announcement',
    'SystemHealthUpdate': 'system_health_update',
    'ComponentHealthUpdate': 'component_health',
    'PerformanceMetrics': 'performance_metrics',

    # =========================================================================
    # SNAPSHOT EVENTS (Category: S - Full state sync)
    # Used for initial sync on connect/reconnect
    # =========================================================================
    'UserSnapshot': 'user_snapshot',
    'CompanySnapshot': 'company_snapshot',
    'ChatSnapshot': 'chat_snapshot',
    'ChatsListSnapshot': 'chats_list_snapshot',
    'MessagesSnapshot': 'messages_snapshot',
    'CompanyMembersSnapshot': 'company_members_snapshot',
}


# =============================================================================
# EOF
# =============================================================================
