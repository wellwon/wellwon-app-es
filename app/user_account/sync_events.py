# =============================================================================
# File: app/user_account/sync_events.py
# Description: Synchronous event configuration for UserAccount domain
# THIS IS THE MOST IMPORTANT FILE FOR PERFORMANCE
# =============================================================================

"""
User Account Synchronous Events

WellWon Platform (Nov 2025):
================================
Events requiring immediate consistency for cross-domain queries and critical user actions.

SYNC PHILOSOPHY:
- Only events that OTHER domains query immediately
- Critical user-facing state changes (registration, deletion, profile)
- Security-critical operations (deletion, email verification)

ASYNC PHILOSOPHY:
- High-frequency operations (authentication attempts, password changes)
- Audit/logging events (login success/failure)
- Background operations (session cleanup)
"""

# Events requiring synchronous projection (blocking - wait for DB update)
SYNC_EVENTS = {
    # === CRITICAL - USER LIFECYCLE ===
    "UserAccountCreated",       # Must block - needed for immediate login after registration
    "UserAccountDeleted",       # Must block - security (prevent deleted user access)
    "UserHardDeleted",          # Must block - security (permanent deletion)

    # === CRITICAL - PROFILE UPDATES ===
    "UserProfileUpdated",       # Must block - UI consistency (profile displays immediately)

    # === CRITICAL - EMAIL VERIFICATION ===
    "UserEmailVerified",        # Must block - may unlock features immediately
}

# Events that are intentionally async (eventual consistency OK)
ASYNC_EVENTS = {
    # === HIGH-FREQUENCY - NO BLOCKING ===
    "UserPasswordChanged",           # Already validated in handler, no cross-domain queries
    "UserPasswordResetViaSecret",    # Already validated in handler

    # === AUDIT/LOGGING - NO BLOCKING ===
    "UserAuthenticationSucceeded",   # Audit trail only, updates last_login_at
    "UserAuthenticationFailed",      # Security monitoring, no blocking needed
    "UserLoggedOut",                 # Stateless cleanup, no critical queries
}

# Configuration for specific sync events
EVENT_CONFIG = {
    "UserAccountCreated": {
        "priority": 1,
        "timeout": 5.0,
        "description": "Must create user projection before returning from registration API"
    },
    "UserAccountDeleted": {
        "priority": 1,
        "timeout": 3.0,
        "description": "Security - must invalidate caches and prevent access immediately"
    },
    "UserHardDeleted": {
        "priority": 1,
        "timeout": 3.0,
        "description": "Security - permanent deletion must complete before response"
    },
    "UserProfileUpdated": {
        "priority": 2,
        "timeout": 2.0,
        "description": "UI consistency - profile must update before API response"
    },
    "UserEmailVerified": {
        "priority": 2,
        "timeout": 2.0,
        "description": "May unlock features - must complete immediately"
    },
}

# Auto-registration with decorator system
def register_domain_events():
    """Register this domain's sync events with the decorator system"""
    try:
        from app.infra.event_store.sync_decorators import register_domain_sync_events
        register_domain_sync_events("user_account", SYNC_EVENTS)
    except ImportError:
        pass

# Auto-register on import
register_domain_events()

# =============================================================================
# PERFORMANCE NOTES:
#
# SYNC Rate: 5 SYNC / 10 total = 50%
# - Higher than ideal (target 20-30%) but justified for user domain
# - User operations are relatively low-frequency (registration, profile updates)
# - Security and consistency requirements outweigh performance concerns
#
# High-frequency async events:
# - UserAuthenticationSucceeded: ~100-1000x per day (async = no bottleneck)
# - UserPasswordChanged: ~1-10x per user per year (low frequency)
#
# Trade-off accepted: Prioritize security and consistency over raw throughput
# =============================================================================
# EOF
# =============================================================================
