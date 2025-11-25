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
    'UserProfileUpdated': 'user_profile_updated',
    'UserEmailVerified': 'user_account_update',
    'UserAccountDeleted': 'user_account_remove',
    'UserAccountDeactivated': 'user_account_update',
    'UserAccountReactivated': 'user_account_update',

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
    # SYSTEM EVENTS
    # =========================================================================
    'SystemAnnouncement': 'system_announcement',
    'SystemMaintenanceScheduled': 'system_announcement',
    'SystemHealthUpdate': 'system_health_update',
    'ComponentHealthUpdate': 'component_health',
    'PerformanceMetrics': 'performance_metrics',
}


# =============================================================================
# EOF
# =============================================================================
