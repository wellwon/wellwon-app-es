# app/user_account/projectors.py
# =============================================================================
# File: app/user_account/projectors.py
# Description: User Account Projector with sync projection decorators
# FIXED: Correct usage of read repository methods (static vs instance)
# =============================================================================

import logging
import os
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

log = logging.getLogger("wellwon.user_account.projectors")

# Grace period (seconds) before hard deleting a user
GRACE_SECONDS = int(os.getenv("USER_DELETION_GRACE_SECONDS", "0"))


class UserAccountProjector:
    """
    Handles User domain events to update read models (projections).
    Uses sync projection decorators for immediate consistency.
    FIXED: Properly uses UserAccountReadRepo static methods.
    """

    def __init__(self, user_read_repo: UserAccountReadRepo):
        self.user_read_repo = user_read_repo
        # For backward compatibility with static methods
        self.UserAccountReadRepo = UserAccountReadRepo

    # -------------------------------------------------------------------------
    # Synchronous Projection Handlers
    # -------------------------------------------------------------------------

    @sync_projection("UserAccountCreated")
    @monitor_projection
    async def on_user_created(self, envelope: EventEnvelope) -> None:
        """Project UserAccountCreated event"""
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserAccountCreated for user_id={user_id}")
        log.info(f"DEBUG PROJECTOR: hashed_password from event starts with: {event_data['hashed_password'][:20]}")
        log.info(f"DEBUG PROJECTOR: hashed_secret from event starts with: {event_data['hashed_secret'][:20]}")

        # Use static method
        await UserAccountReadRepo.insert_user_account_projection(
            user_id=user_id,
            username=event_data['username'],
            email=event_data.get('email', ''),
            hashed_password=event_data['hashed_password'],
            hashed_secret=event_data['hashed_secret'],
            role=event_data['role'],
            first_name=event_data.get('first_name'),
            last_name=event_data.get('last_name'),
        )

    @sync_projection("UserCreated")  # Legacy support
    async def on_user_created_legacy(self, envelope: EventEnvelope) -> None:
        """Handle legacy UserCreated event"""
        await self.on_user_created(envelope)

    async def on_user_password_changed(self, envelope: EventEnvelope) -> None:
        """Project UserPasswordChanged event

        ASYNC: Password already validated/changed in command handler
        Performance: Does not block password change operation
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserPasswordChanged for user_id={user_id}")

        # Use static method
        await UserAccountReadRepo.update_user_password_projection(
            user_id, event_data['new_hashed_password']
        )

    async def on_user_password_reset(self, envelope: EventEnvelope) -> None:
        """Project UserPasswordResetViaSecret event

        ASYNC: Password already reset in command handler
        Performance: Does not block password reset operation
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserPasswordResetViaSecret for user_id={user_id}")

        # Use static method
        await UserAccountReadRepo.update_user_password_projection(
            user_id, event_data['new_hashed_password']
        )

    @sync_projection("UserAccountDeleted", priority=1, timeout=3.0)
    async def on_user_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project UserAccountDeleted event with high priority.
        CRITICAL: Includes immediate cache invalidation to prevent deleted user from accessing system.
        UPDATED: If user has virtual broker, delay hard delete until saga completes VB cleanup.
        """
        log.info(f"DEBUG: on_user_deleted CALLED for envelope: event_type={envelope.event_type}, aggregate_id={envelope.aggregate_id}")

        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserAccountDeleted for user_id={user_id}")

        # Use grace period from event or environment default
        grace_period = event_data.get('grace_period', GRACE_SECONDS)
        has_virtual_broker = event_data.get('has_virtual_broker', False)

        if grace_period == 0:
            # CRITICAL FIX: If user has virtual broker, delay hard delete
            # Saga will handle VB account deletion first, then trigger hard delete
            if has_virtual_broker:
                log.info(
                    f"User {user_id} has virtual broker - soft delete only, "
                    f"saga will trigger hard delete after VB cleanup"
                )
                await UserAccountReadRepo.mark_user_inactive_projection(user_id)
            else:
                # Immediate hard delete - use static method
                await UserAccountReadRepo.delete_user_account_projection(user_id)
                log.info(f"User {user_id} hard deleted from database")
        else:
            # Soft delete - use static method
            await UserAccountReadRepo.mark_user_inactive_projection(user_id)
            log.info(f"User {user_id} soft deleted with grace period {grace_period}s")

        # CRITICAL: Clear all caches immediately to prevent deleted user from accessing system
        await self._clear_user_caches(user_id)

    @sync_projection("UserDeleted", priority=1, timeout=3.0)  # Legacy support
    async def on_user_deleted_legacy(self, envelope: EventEnvelope) -> None:
        """Handle legacy UserDeleted event"""
        await self.on_user_deleted(envelope)

    @sync_projection("UserHardDeleted", priority=1, timeout=3.0)
    async def on_user_hard_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project UserHardDeleted event - final hard delete after saga completion.
        This event is published by UserDeletionSaga after VB cleanup is complete.
        """
        event_data = envelope.event_data
        user_id_str = event_data.get('user_id')

        if not user_id_str:
            log.error("UserHardDeleted event missing user_id")
            return

        user_id = uuid.UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str

        log.info(f"Projecting UserHardDeleted for user_id={user_id} - final hard delete from saga")

        # Hard delete user from database
        await UserAccountReadRepo.delete_user_account_projection(user_id)
        log.info(f"User {user_id} hard deleted from database after saga completion")

        # Clear caches again to ensure no stale data
        await self._clear_user_caches(user_id)

    async def on_user_email_verified(self, envelope: EventEnvelope) -> None:
        """Project UserEmailVerified event

        ASYNC: Email verification is not auth-critical
        Performance: Does not block email verification flow
        """
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserEmailVerified for user_id={user_id}")

        # Use static method
        await UserAccountReadRepo.verify_user_email_projection(user_id)

    async def on_user_account_mapping_set(self, envelope: EventEnvelope) -> None:
        """Project UserBrokerAccountMappingSet event

        ASYNC: Cache update - eventual consistency OK
        Performance: Does not block account mapping operation
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserBrokerAccountMappingSet for user_id={user_id}")

        # Use instance method for cache operations
        await self.user_read_repo.set_user_broker_account_mapping(
            user_id,
            event_data['asset_type'],
            uuid.UUID(event_data['account_id'])
        )

    async def on_user_account_mapping_set_legacy(self, envelope: EventEnvelope) -> None:
        """Handle legacy UserAccountMappingSet event

        ASYNC: Cache update - eventual consistency OK
        Performance: Does not block account mapping operation
        """
        await self.on_user_account_mapping_set(envelope)

    async def on_user_connected_broker_added(self, envelope: EventEnvelope) -> None:
        """Project UserConnectedBrokerAdded event

        ASYNC: Broker list update - not queried immediately
        Performance: Does not block broker connection operation
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserConnectedBrokerAdded for user_id={user_id}")

        # Use instance method for cache operations
        await self.user_read_repo.add_user_connected_broker(
            user_id,
            event_data['broker_id'],
            event_data['environment']
        )

    async def on_user_connected_broker_removed(self, envelope: EventEnvelope) -> None:
        """Project UserConnectedBrokerRemoved event

        ASYNC: Broker list update - not queried immediately
        Performance: Does not block broker disconnection operation
        """
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserConnectedBrokerRemoved for user_id={user_id}")

        # Use instance method for cache operations
        await self.user_read_repo.remove_user_connected_broker(
            user_id,
            event_data['broker_id'],
            event_data['environment']
        )

    async def on_user_authentication_succeeded(self, envelope: EventEnvelope) -> None:
        """Project UserAuthenticationSucceeded event - updates last login

        ASYNC: Last login timestamp update - eventual consistency OK
        """
        event_data = envelope.event_data

        # Get user_id from event_data
        user_id_str = event_data.get('user_id')

        if not user_id_str:
            log.error(f"UserAuthenticationSucceeded event missing user_id: {event_data}")
            return

        # Convert string to UUID
        try:
            user_id = uuid.UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        except (ValueError, TypeError) as e:
            log.error(f"Invalid user_id format in UserAuthenticationSucceeded: {user_id_str}, error: {e}")
            return

        log.info(f"User authentication succeeded for {event_data.get('username', 'unknown')}, updating last login")

        # Update last login timestamp - use static method
        await UserAccountReadRepo.update_last_login(user_id)

    async def on_user_authentication_failed(self, envelope: EventEnvelope) -> None:
        """Project UserAuthenticationFailed event

        ASYNC: Security monitoring/audit - eventual consistency OK
        """
        event_data = envelope.event_data

        log.warning(
            f"User authentication failed for {event_data['username_attempted']}: "
            f"{event_data['reason']}"
        )

        # Track failed attempts for security monitoring
        await self._track_failed_login_attempt(
            event_data['username_attempted'],
            event_data.get('ip_address'),
            event_data['reason']
        )

    async def on_user_logged_out(self, envelope: EventEnvelope) -> None:
        """
        Project UserLoggedOut event - minimal handler for event acknowledgment.

        FIX (Nov 11, 2025): Added to prevent unhandled event errors.
        This event is primarily handled by StreamingLifecycleManager for broker cleanup.
        No database projection needed - logout is stateless (JWT invalidation only).
        """
        event_data = envelope.event_data
        user_id_str = event_data.get('user_id')
        session_id = event_data.get('session_id')

        log.debug(f"User logged out: {user_id_str}, session: {session_id}")
        # No projection needed - event acknowledged for worker processing

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    async def _track_failed_login_attempt(
            self,
            username: str,
            ip_address: Optional[str],
            reason: str
    ) -> None:
        """Track failed login attempts for security monitoring"""
        # This could be extended to:
        # - Store in a separate security_events table
        # - Implement rate limiting
        # - Trigger alerts after N failures
        # - Implement temporary account lockouts

        log.info(
            f"Failed login attempt tracked: username={username}, "
            f"ip={ip_address}, reason={reason}"
        )

    async def _clear_user_caches(self, user_id: uuid.UUID) -> None:
        """
        Clear all user-related caches immediately.
        CRITICAL for preventing deleted/modified users from using stale cached data.
        """
        cache_cleared_count = 0

        # 1. Clear Redis caches
        try:
            from app.infra.persistence.cache_manager import get_cache_manager
            cache_manager = get_cache_manager()

            redis_keys = [
                f"user:profile:{user_id}",
                f"user:auth:{user_id}",
                f"user:sessions:{user_id}",
                f"user:brokers:{user_id}",
                f"user:mappings:{user_id}",
                f"user:accounts:{user_id}",
                f"user:connections:{user_id}",
                f"user:query:{user_id}",
            ]

            for key in redis_keys:
                try:
                    await cache_manager.delete(key)
                    cache_cleared_count += 1
                except Exception as e:
                    log.warning(f"Failed to clear Redis cache key {key}: {e}")

            log.info(f"Cleared {cache_cleared_count} Redis cache entries for user {user_id}")

        except Exception as e:
            log.warning(f"Failed to clear Redis caches for user {user_id}: {e}")

        # Note: QueryBus in-memory cache will expire naturally with TTL (60s default)
        # or will be cleared by the saga's comprehensive cleanup step

        log.info(f"Cache invalidation completed for user {user_id}")

    # -------------------------------------------------------------------------
    # WellWon Platform Projection Handlers
    # -------------------------------------------------------------------------

    @sync_projection("UserProfileUpdated")
    @monitor_projection
    async def on_user_profile_updated(self, envelope: EventEnvelope) -> None:
        """Project UserProfileUpdated event for WellWon platform"""
        event_data = envelope.event_data
        user_id = envelope.aggregate_id

        log.info(f"Projecting UserProfileUpdated for user_id={user_id}")

        # Use static method to update profile fields
        await UserAccountReadRepo.update_user_profile_projection(
            user_id=user_id,
            first_name=event_data.get('first_name'),
            last_name=event_data.get('last_name'),
            avatar_url=event_data.get('avatar_url'),
            bio=event_data.get('bio'),
            phone=event_data.get('phone')
        )

        # Invalidate cache
        try:
            from app.infra.persistence.cache_manager import get_cache_manager
            cache_manager = get_cache_manager()
            await cache_manager.delete(f"user:profile:{user_id}")
            log.info(f"Cleared profile cache for user {user_id}")
        except Exception as e:
            log.warning(f"Failed to clear profile cache: {e}")

    def get_stats(self) -> dict:
        """Get projector statistics"""
        return {
            "projector": "UserAccountProjector",
            "handlers": 14,  # Number of sync projection handlers
            "sync_events": [
                "UserAccountCreated", "UserCreated",
                "UserAccountDeleted", "UserDeleted",
                "UserPasswordChanged", "UserPasswordResetViaSecret",
                "UserEmailVerified", "UserBrokerAccountMappingSet",
                "UserAccountMappingSet", "UserConnectedBrokerAdded",
                "UserConnectedBrokerRemoved", "UserAuthenticationSucceeded",
                "UserAuthenticationFailed", "UserProfileUpdated"
            ]
        }

# =============================================================================
# EOF
# =============================================================================