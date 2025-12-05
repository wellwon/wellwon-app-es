# =============================================================================
# File: app/infra/read_repos/user_account_read_repo.py
# Description: Read repository for User projections in 
# - Handles direct database access (PostgreSQL for auth, uses CacheManager for runtime)
#   for querying user information.
# - Used by API layer for GET requests and by Projectors to update read models.
# - Supports immediate or grace-period deletion via ENV var USER_DELETION_GRACE_SECONDS
# UPDATED: Clean domain boundaries - no cross-domain database queries
# =============================================================================

from __future__ import annotations

import logging
import os
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

# Database clients
from app.infra.persistence.pg_client import (
    execute as pg_execute,
    fetchrow as pg_fetchrow,
    fetchrow_with_app_context,
)
from app.infra.persistence.cache_manager import CacheManager, get_cache_manager

# Import Pydantic models for User Read Models
from app.user_account.read_models import (
    UserAccountReadModel,
    UserAuthDataReadModel,
    UserRuntimeStateReadModel,
    UserSummaryReadModel
)

log = logging.getLogger("wellwon.infra.user_read_repo")

# Grace period (seconds) before hard deleting a user
GRACE_SECONDS = int(os.getenv("USER_DELETION_GRACE_SECONDS", "0"))


class UserAccountReadRepo:
    """
    Repository for accessing User read models (projections).
    Interacts with PostgreSQL for user auth data and CacheManager for runtime user state.
    Clean CQRS implementation - only handles reads and projections.
    CLEAN DOMAIN BOUNDARIES - no cross-domain database queries.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """Initialize with optional cache manager injection"""
        if cache_manager:
            self.cache = cache_manager
        else:
            # Try to get global cache manager, but don't fail if Redis not initialized
            try:
                self.cache = get_cache_manager()
            except Exception as e:
                log.warning(f"Cache manager not available: {e}. Cache operations will be skipped.")
                self.cache = None

    # ==========================================================================
    # PostgreSQL (Auth Data) Methods - CREATE/UPDATE for Projectors
    # ==========================================================================

    @staticmethod
    async def insert_user_account_projection(
            user_id: UUID,
            username: str,
            email: str,
            hashed_password: str,
            hashed_secret: str,
            role: str,
            is_active: bool = True,
            email_verified: bool = False,
            first_name: str = None,
            last_name: str = None
    ) -> bool:
        """
        Inserts a new user record into the users projection table (PostgreSQL).
        Called by the UserProjector on UserAccountCreated event.
        """
        sql = """
              INSERT INTO user_accounts (id, username, email, hashed_password, hashed_secret,
                                         role, is_active, email_verified, first_name, last_name, created_at)
              VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
              ON CONFLICT (id) DO NOTHING
              RETURNING id;
              """

        try:
            result = await pg_fetchrow(
                sql, user_id, username, email,
                hashed_password, hashed_secret, role,
                is_active, email_verified, first_name, last_name
            )

            if result:
                log.info(f"User projection created for username: {username}, id: {user_id}")
                return True
            else:
                log.warning(f"User projection already exists for id: {user_id}")
                return False

        except Exception as e:
            log.error(f"Failed to insert user projection: {e}")
            raise

    @staticmethod
    async def update_user_password_projection(user_id: UUID, new_hashed_password: str) -> None:
        """Updates the hashed password in the user projection table."""
        sql = """
              UPDATE user_accounts
              SET hashed_password      = $1,
                  last_password_change = CURRENT_TIMESTAMP,
                  updated_at           = CURRENT_TIMESTAMP
              WHERE id = $2 \
              """

        try:
            await pg_execute(sql, new_hashed_password, user_id)
            log.info(f"User password projection updated for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to update password projection: {e}")
            raise

    @staticmethod
    async def mark_user_inactive_projection(user_id: UUID) -> None:
        """Marks a user as inactive in the projection table (soft-delete)."""
        sql = """
              UPDATE user_accounts
              SET is_active  = FALSE,
                  updated_at = CURRENT_TIMESTAMP
              WHERE id = $1 \
              """

        try:
            await pg_execute(sql, user_id)
            log.info(f"User projection marked as inactive for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to mark user inactive: {e}")
            raise

    @staticmethod
    async def delete_user_account_projection(user_id: UUID) -> None:
        """Performs hard delete of a user from the projection table."""
        try:
            await pg_execute("DELETE FROM user_accounts WHERE id = $1", user_id)
            log.info(f"User projection hard-deleted for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to delete user projection: {e}")
            raise

    @staticmethod
    async def process_user_account_deletion(user_id: UUID, grace_period: Optional[int] = None) -> None:
        """
        Applies deletion strategy based on grace_period:
        - grace_period == 0 or None: hard delete
        - Otherwise: soft delete (mark inactive)
        """
        effective_grace = grace_period if grace_period is not None else GRACE_SECONDS

        if effective_grace == 0:
            await UserAccountReadRepo.delete_user_account_projection(user_id)
        else:
            await UserAccountReadRepo.mark_user_inactive_projection(user_id)

    @staticmethod
    async def verify_user_email_projection(user_id: UUID) -> None:
        """Marks a user's email as verified in the projection table."""
        sql = """
              UPDATE user_accounts
              SET email_verified = TRUE,
                  updated_at     = CURRENT_TIMESTAMP
              WHERE id = $1 \
              """

        try:
            await pg_execute(sql, user_id)
            log.info(f"User email projection marked as verified for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to verify email projection: {e}")
            raise

    @staticmethod
    async def update_last_login(user_id: UUID) -> None:
        """Updates the user's last login timestamp."""
        sql = """
              UPDATE user_accounts
              SET last_login = CURRENT_TIMESTAMP,
                  updated_at = CURRENT_TIMESTAMP
              WHERE id = $1 \
              """

        try:
            await pg_execute(sql, user_id)
            log.info(f"Updated last login for user_id: {user_id}")
        except Exception as e:
            # Log the error but don't raise it - login should still succeed
            log.error(f"Failed to update last login for user_id {user_id}: {e}")

    @staticmethod
    async def update_user_profile(user_id: UUID, **kwargs) -> None:
        """
        Updates user profile fields dynamically.

        Args:
            user_id: The UUID of the user to update
            **kwargs: Fields to update (email, mfa_enabled, security_alerts_enabled,
                     first_name, last_name, avatar_url, bio, phone)
        """
        # Filter out None values
        updates = {k: v for k, v in kwargs.items() if v is not None}

        if not updates:
            return

        # Build SET clause
        set_clauses = []
        params = []
        param_count = 1

        for field, value in updates.items():
            set_clauses.append(f"{field} = ${param_count}")
            params.append(value)
            param_count += 1

        # Always update the updated_at timestamp
        set_clauses.append(f"updated_at = CURRENT_TIMESTAMP")

        # Add user_id as the last parameter
        params.append(user_id)

        sql = f"""
            UPDATE user_accounts
            SET {', '.join(set_clauses)}
            WHERE id = ${param_count}
        """

        try:
            await pg_execute(sql, *params)
            log.info(f"Updated user profile for user_id: {user_id}, fields: {list(updates.keys())}")
        except Exception as e:
            log.error(f"Failed to update user profile for user_id {user_id}: {e}")
            raise

    @staticmethod
    async def update_user_profile_projection(
            user_id: UUID,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            avatar_url: Optional[str] = None,
            bio: Optional[str] = None,
            phone: Optional[str] = None,
            user_type: Optional[str] = None,
            is_developer: Optional[bool] = None
    ) -> None:
        """
        Updates WellWon platform profile fields (called by projector).
        Alias for update_user_profile with typed parameters.
        """
        await UserAccountReadRepo.update_user_profile(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
            bio=bio,
            phone=phone,
            user_type=user_type,
            is_developer=is_developer
        )

    # ==========================================================================
    # PostgreSQL Query Methods - READ operations
    # ==========================================================================

    @staticmethod
    async def get_user_auth_details_by_username(username: str) -> Optional[UserAuthDataReadModel]:
        """Fetches auth details by username."""
        sql = """
              SELECT id, \
                     username, \
                     email, \
                     hashed_password, \
                     hashed_secret, \
                     role,
                     is_active, \
                     created_at, \
                     updated_at, \
                     last_login,
                     email_verified, \
                     mfa_enabled, \
                     security_alerts_enabled,
                     last_password_change
              FROM user_accounts
              WHERE username = $1 \
              """

        row = await pg_fetchrow(sql, username)
        if row:
            return UserAuthDataReadModel(
                user_id=row["id"],
                username=row["username"],
                email=row["email"],
                hashed_password=row["hashed_password"],
                hashed_secret=row.get("hashed_secret"),
                role=row["role"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                last_login=row.get("last_login"),
                email_verified=row.get("email_verified", False),
                mfa_enabled=row.get("mfa_enabled", False),
                security_alerts_enabled=row.get("security_alerts_enabled", True),
                last_password_change=row.get("last_password_change")
            )
        return None

    @staticmethod
    async def get_user_auth_details_by_email(email: str) -> Optional[UserAuthDataReadModel]:
        """Fetches auth details by email address."""
        sql = """
              SELECT id, \
                     username, \
                     email, \
                     hashed_password, \
                     hashed_secret, \
                     role,
                     is_active, \
                     created_at, \
                     updated_at, \
                     last_login,
                     email_verified, \
                     mfa_enabled, \
                     security_alerts_enabled,
                     last_password_change
              FROM user_accounts
              WHERE email = $1 \
              """

        row = await pg_fetchrow(sql, email)
        if row:
            return UserAuthDataReadModel(
                user_id=row["id"],
                username=row["username"],
                email=row["email"],
                hashed_password=row["hashed_password"],
                hashed_secret=row.get("hashed_secret"),
                role=row["role"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                last_login=row.get("last_login"),
                email_verified=row.get("email_verified", False),
                mfa_enabled=row.get("mfa_enabled", False),
                security_alerts_enabled=row.get("security_alerts_enabled", True),
                last_password_change=row.get("last_password_change")
            )
        return None

    @staticmethod
    async def get_user_profile_by_user_id(user_id: UUID) -> Optional[UserAccountReadModel]:
        """Fetches user profile data by user ID for API responses."""
        sql = """
              SELECT id, \
                     username, \
                     email, \
                     role, \
                     is_active,
                     email_verified, \
                     last_login, \
                     created_at, \
                     updated_at,
                     mfa_enabled, \
                     security_alerts_enabled, \
                     last_password_change,
                     first_name, \
                     last_name, \
                     avatar_url, \
                     bio, \
                     phone, \
                     is_developer, \
                     user_number
              FROM user_accounts
              WHERE id = $1 \
              """

        row = await pg_fetchrow(sql, user_id)
        if row:
            return UserAccountReadModel(
                id=row["id"],
                user_id_str=str(row["id"]),
                username=row["username"],
                email=row["email"],
                role=row["role"],
                is_active=row["is_active"],
                email_verified=row["email_verified"],
                last_login=row.get("last_login"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                mfa_enabled=row.get("mfa_enabled", False),
                security_alerts_enabled=row.get("security_alerts_enabled", True),
                last_password_change=row.get("last_password_change"),
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                avatar_url=row.get("avatar_url"),
                bio=row.get("bio"),
                phone=row.get("phone"),
                is_developer=row.get("is_developer", False),
                user_number=row.get("user_number")
            )
        return None

    @staticmethod
    async def get_connected_brokers(user_id: UUID) -> List[str]:
        """
        Gets list of connected brokers for a user from cache only.
        User domain tracks broker relationships in its own cache, not by querying other domains.
        """
        cache_manager = get_cache_manager()

        # Get from user domain's cache only
        cache_data = await cache_manager.get_json(
            cache_manager._make_key('user', 'connected_brokers', str(user_id))
        )

        if cache_data and isinstance(cache_data, list):
            # Extract unique broker IDs
            unique_brokers = set()
            for broker_env in cache_data:
                if ':' in broker_env:
                    broker_id = broker_env.split(':')[0]
                    unique_brokers.add(broker_id)
                else:
                    unique_brokers.add(broker_env)
            return sorted(list(unique_brokers))

        log.debug(f"No cached broker connections found for user {user_id}")
        return []

    # ==========================================================================
    # Cache (Runtime User Data) Methods - Using CacheManager
    # ==========================================================================

    async def get_user_broker_account_mapping(self, user_id: UUID, asset_type: str) -> Optional[str]:
        """Gets a specific asset_type→account_id mapping from cache."""
        cache_key = self.cache._make_key('user', 'account_mapping', str(user_id), asset_type)
        return await self.cache.get(cache_key)

    async def set_user_broker_account_mapping(self, user_id: UUID, asset_type: str, account_id: UUID) -> None:
        """Sets an asset_type→account_id mapping in cache."""
        cache_key = self.cache._make_key('user', 'account_mapping', str(user_id), asset_type)
        ttl = self.cache.get_module_ttl('user', 'account_mapping', default=3600)

        try:
            await self.cache.set(cache_key, str(account_id), ttl)
            log.info(f"Mapping set for user {user_id}, asset '{asset_type}': {account_id}")
        except Exception as e:
            log.error(f"Failed to set account mapping: {e}")

    @staticmethod
    async def get_user_connected_brokers(user_id: UUID) -> List[str]:
        """Gets a list of connected brokers for a user from cache."""
        cache_manager = get_cache_manager()

        # Get all broker connections from cache
        cache_data = await cache_manager.get_json(
            cache_manager._make_key('user', 'connected_brokers', str(user_id))
        )

        if cache_data and isinstance(cache_data, list):
            return cache_data

        log.debug(f"No cached broker connections found for user {user_id}")
        return []

    async def add_user_connected_broker(self, user_id: UUID, broker_id: str, environment: str) -> None:
        """Adds a broker connection identifier to cache."""
        # Get current list
        current_brokers = await self.get_user_connected_brokers(user_id)
        member = f"{broker_id}:{environment}"

        # Add if not already present
        if member not in current_brokers:
            current_brokers.append(member)

        # Save back to cache
        cache_key = self.cache._make_key('user', 'connected_brokers', str(user_id))
        ttl = self.cache.get_module_ttl('user', 'connected_brokers', default=86400)  # 24 hours

        try:
            await self.cache.set_json(cache_key, current_brokers, ttl)
            log.info(f"Broker added for user {user_id}: {member}")
        except Exception as e:
            log.error(f"Failed to add connected broker: {e}")

    async def remove_user_connected_broker(self, user_id: UUID, broker_id: str, environment: str) -> None:
        """Removes a broker connection identifier from cache."""
        # Get current list
        current_brokers = await self.get_user_connected_brokers(user_id)
        member = f"{broker_id}:{environment}"

        # Remove if present
        if member in current_brokers:
            current_brokers.remove(member)

        # Save back to cache (or delete if empty)
        cache_key = self.cache._make_key('user', 'connected_brokers', str(user_id))

        try:
            if current_brokers:
                ttl = self.cache.get_module_ttl('user', 'connected_brokers', default=86400)
                await self.cache.set_json(cache_key, current_brokers, ttl)
            else:
                await self.cache.delete(cache_key)
            log.info(f"Broker removed for user {user_id}: {member}")
        except Exception as e:
            log.error(f"Failed to remove connected broker: {e}")

    async def mark_user_broker_disconnected_projection(self, user_id: UUID) -> None:
        """Clears all connected brokers for a user in cache."""
        cache_key = self.cache._make_key('user', 'connected_brokers', str(user_id))
        try:
            await self.cache.delete(cache_key)
            log.info(f"All connected brokers cleared for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to clear connected brokers: {e}")

    async def mark_user_broker_accounts_purged_projection(self, user_id: UUID) -> None:
        """Removes all account mapping entries for a user in cache."""
        pattern = self.cache._make_key('user', 'account_mapping', str(user_id), '*')
        try:
            deleted = await self.cache.delete_pattern(pattern)
            if deleted > 0:
                log.info(f"Cleared {deleted} account mappings for user_id: {user_id}")
        except Exception as e:
            log.error(f"Failed to purge account mappings: {e}")

    async def get_account_mapping(self, user_id: UUID, asset_type: str) -> Optional[str]:
        """Gets a specific account mapping for an asset type."""
        return await self.get_user_broker_account_mapping(user_id, asset_type)

    async def get_account_mappings(self, user_id: UUID) -> Dict[str, str]:
        """
        Gets all account mappings for a user.
        Note: This is a simplified implementation - in production,
        you might want to track asset types in a separate list.
        """
        mappings = {}
        # Check common asset types
        asset_types = ['stocks', 'options', 'crypto', 'forex', 'futures', 'multi']

        for asset_type in asset_types:
            mapping = await self.get_account_mapping(user_id, asset_type)
            if mapping:
                mappings[asset_type] = mapping

        return mappings

    # ==========================================================================
    # Composite Read Methods (combining DB and cache data)
    # ==========================================================================

    async def get_user_runtime_state(self, user_id: UUID) -> UserRuntimeStateReadModel:
        """
        Gets complete runtime state for a user (cache data).
        """
        # Get account mappings
        account_mappings = await self.get_account_mappings(user_id)

        # Get connected brokers
        connected_brokers = await self.get_user_connected_brokers(user_id)

        return UserRuntimeStateReadModel(
            user_id=user_id,
            account_mappings=account_mappings,
            connected_brokers=connected_brokers
        )

    async def get_user_summary(self, user_id: UUID) -> Optional[UserSummaryReadModel]:
        """
        Gets lightweight user summary.
        """
        sql = """
              SELECT id, username, email, role, is_active, created_at
              FROM user_accounts
              WHERE id = $1 \
              """

        row = await pg_fetchrow(sql, user_id)
        if row:
            return UserSummaryReadModel(
                id=row["id"],
                username=row["username"],
                email=row["email"],
                role=row["role"],
                is_active=row["is_active"],
                created_at=row["created_at"]
            )
        return None

    @staticmethod
    async def get_all_users_for_admin(
            include_inactive: bool = True,
            limit: int = 100,
            offset: int = 0
    ) -> List[UserAccountReadModel]:
        """
        Gets all users for admin management panel.

        Args:
            include_inactive: Whether to include inactive users
            limit: Maximum number of users to return
            offset: Number of users to skip

        Returns:
            List of UserAccountReadModel
        """
        from app.infra.persistence.pg_client import fetch as pg_fetch

        where_clause = "" if include_inactive else "WHERE is_active = TRUE"

        sql = f"""
            SELECT
                id,
                username,
                email,
                role,
                is_active,
                email_verified,
                last_login,
                created_at,
                updated_at,
                mfa_enabled,
                security_alerts_enabled,
                last_password_change,
                first_name,
                last_name,
                avatar_url,
                bio,
                phone,
                is_developer,
                user_number
            FROM user_accounts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """

        rows = await pg_fetch(sql, limit, offset)

        return [
            UserAccountReadModel(
                id=row["id"],
                user_id_str=str(row["id"]),
                username=row["username"],
                email=row["email"],
                role=row["role"],
                is_active=row["is_active"],
                email_verified=row.get("email_verified", False),
                last_login=row.get("last_login"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                mfa_enabled=row.get("mfa_enabled", False),
                security_alerts_enabled=row.get("security_alerts_enabled", True),
                last_password_change=row.get("last_password_change"),
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                avatar_url=row.get("avatar_url"),
                bio=row.get("bio"),
                phone=row.get("phone"),
                is_developer=row.get("is_developer", False),
                user_number=row.get("user_number")
            )
            for row in rows
        ]

    @staticmethod
    async def update_user_admin_status(
            user_id: UUID,
            is_active: Optional[bool] = None,
            is_developer: Optional[bool] = None,
            user_type: Optional[str] = None,
            role: Optional[str] = None
    ) -> Optional[UserAccountReadModel]:
        """
        Updates user admin status (active, developer, user_type, role).
        Called by projector on admin status change events.

        Args:
            user_id: The UUID of the user to update
            is_active: New active status (optional)
            is_developer: New developer status (optional)
            user_type: New user type (optional)
            role: New role (optional)

        Returns:
            Updated UserAccountReadModel or None if not found
        """
        updates = {}
        if is_active is not None:
            updates['is_active'] = is_active
        if is_developer is not None:
            updates['is_developer'] = is_developer
        if user_type is not None:
            updates['user_type'] = user_type
        if role is not None:
            updates['role'] = role

        if not updates:
            return None

        # Build SET clause
        set_clauses = []
        params = []
        param_count = 1

        for field, value in updates.items():
            set_clauses.append(f"{field} = ${param_count}")
            params.append(value)
            param_count += 1

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)

        sql = f"""
            UPDATE user_accounts
            SET {', '.join(set_clauses)}
            WHERE id = ${param_count}
            RETURNING
                id,
                username,
                email,
                role,
                is_active,
                email_verified,
                last_login,
                created_at,
                updated_at,
                first_name,
                last_name,
                is_developer
        """

        try:
            # Use fetchrow_with_app_context to bypass CES triggers
            # This prevents duplicate events when updating via normal app flow
            row = await fetchrow_with_app_context(sql, *params)

            if not row:
                log.warning(f"User not found for admin status update: {user_id}")
                return None

            log.info(f"Updated admin status for user {user_id}: {updates}")

            return UserAccountReadModel(
                id=row["id"],
                user_id_str=str(row["id"]),
                username=row["username"],
                email=row["email"],
                role=row["role"],
                is_active=row["is_active"],
                email_verified=row.get("email_verified", False),
                last_login=row.get("last_login"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                is_developer=row.get("is_developer", False),
            )

        except Exception as e:
            log.error(f"Failed to update admin status for user {user_id}: {e}")
            raise

    @staticmethod
    async def get_profiles_with_telegram() -> List[Dict[str, Any]]:
        """
        Gets user profiles that have telegram_user_id linked.
        Used for mentions feature in chat.

        Returns:
            List of dicts with user_id, first_name, last_name, avatar_url, role, telegram_user_id
        """
        sql = """
            SELECT
                id as user_id,
                first_name,
                last_name,
                avatar_url,
                role as role_label,
                telegram_user_id
            FROM user_accounts
            WHERE is_active = TRUE
            ORDER BY
                CASE WHEN telegram_user_id IS NOT NULL THEN 0 ELSE 1 END,
                first_name, last_name
        """

        from app.infra.persistence.pg_client import fetch as pg_fetch

        rows = await pg_fetch(sql)
        return [
            {
                "user_id": str(row["user_id"]),
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "avatar_url": row["avatar_url"],
                "role_label": row["role_label"],
                "telegram_user_id": row["telegram_user_id"],
            }
            for row in rows
        ]

    @staticmethod
    async def update_telegram_user_id(user_id: UUID, telegram_user_id: int) -> bool:
        """
        Links a WellWon user account to a Telegram user ID.

        Args:
            user_id: WellWon user UUID
            telegram_user_id: Telegram user ID (bigint)

        Returns:
            True if updated, False otherwise
        """
        sql = """
            UPDATE user_accounts
            SET telegram_user_id = $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """

        try:
            await pg_execute(sql, telegram_user_id, user_id)
            log.info(f"Linked user {user_id} to Telegram user {telegram_user_id}")
            return True
        except Exception as e:
            log.error(f"Failed to link user {user_id} to Telegram: {e}")
            return False

    @staticmethod
    async def get_user_by_telegram_id(telegram_user_id: int) -> Optional[UUID]:
        """
        Find WellWon user ID by Telegram user ID.

        Args:
            telegram_user_id: Telegram user ID (bigint)

        Returns:
            WellWon user UUID if found, None otherwise
        """
        sql = """
            SELECT id FROM user_accounts
            WHERE telegram_user_id = $1 AND is_active = TRUE
        """

        try:
            row = await pg_fetchrow(sql, telegram_user_id)
            if row:
                log.debug(f"Found WellWon user {row['id']} for Telegram user {telegram_user_id}")
                return row['id']
            return None
        except Exception as e:
            log.error(f"Failed to lookup user by Telegram ID {telegram_user_id}: {e}")
            return None

    @staticmethod
    async def get_user_by_external_id(provider: str, external_id: str) -> Optional[UUID]:
        """
        Find WellWon user ID by external provider ID.
        Supports 'telegram' provider via telegram_user_id column.

        Args:
            provider: Provider name ('telegram', 'google', etc.)
            external_id: External user ID

        Returns:
            WellWon user UUID if found, None otherwise
        """
        if provider == 'telegram':
            try:
                telegram_id = int(external_id)
                return await UserAccountReadRepo.get_user_by_telegram_id(telegram_id)
            except ValueError:
                log.warning(f"Invalid Telegram user ID format: {external_id}")
                return None

        # For future providers, check user_external_identities table
        sql = """
            SELECT user_id FROM user_external_identities
            WHERE provider = $1 AND external_id = $2
        """

        try:
            row = await pg_fetchrow(sql, provider, external_id)
            if row:
                return row['user_id']
            return None
        except Exception as e:
            # Table might not exist yet
            log.debug(f"External identity lookup failed: {e}")
            return None


# =============================================================================
# Singleton instance for backward compatibility
# =============================================================================

_default_repo: Optional[UserAccountReadRepo] = None


def get_user_account_read_repo() -> UserAccountReadRepo:
    """Get singleton instance of UserAccountReadRepo"""
    global _default_repo
    if _default_repo is None:
        _default_repo = UserAccountReadRepo()
    return _default_repo

# =============================================================================
# EOF
# =============================================================================