# =============================================================================
# File: app/infra/read_repos/chat_read_repo.py
# Description: Read repository for Chat domain
# =============================================================================

from __future__ import annotations

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.infra.persistence import pg_client
from app.chat.read_models import (
    ChatReadModel,
    ChatParticipantReadModel,
    ChatListItemReadModel,
)

log = logging.getLogger("wellwon.chat.read_repo")


class ChatReadRepo:
    """
    Read repository for Chat domain.

    Provides read operations for chat-related data from PostgreSQL read models.
    All methods are static for ease of use from projectors and query handlers.
    """

    # =========================================================================
    # Chat Operations
    # =========================================================================

    @staticmethod
    async def insert_chat(
        chat_id: uuid.UUID,
        name: Optional[str],
        chat_type: str,
        created_by: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_topic_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        """
        Insert a new chat record.

        Note: Parameter is telegram_chat_id but DB column is telegram_supergroup_id.
        """
        await pg_client.execute(
            """
            INSERT INTO chats (
                id, name, type, created_by, company_id,
                telegram_supergroup_id, telegram_topic_id, created_at,
                is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)
            ON CONFLICT (id) DO NOTHING
            """,
            chat_id, name, chat_type, created_by, company_id,
            telegram_chat_id, telegram_topic_id, created_at or datetime.utcnow(),
        )

    @staticmethod
    async def update_chat(
        chat_id: uuid.UUID,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update chat details"""
        updates = []
        params = []
        param_idx = 1

        if name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(name)
            param_idx += 1

        if metadata is not None:
            updates.append(f"metadata = metadata || ${param_idx}::jsonb")
            params.append(metadata)
            param_idx += 1

        updates.append(f"updated_at = ${param_idx}")
        params.append(updated_at or datetime.utcnow())
        param_idx += 1

        # Note: version column removed - event store handles versioning

        params.append(chat_id)

        await pg_client.execute(
            f"UPDATE chats SET {', '.join(updates)} WHERE id = ${param_idx}",
            *params
        )

    @staticmethod
    async def update_chat_status(
        chat_id: uuid.UUID,
        is_active: bool,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update chat active status"""
        await pg_client.execute(
            """
            UPDATE chats
            SET is_active = $1, updated_at = $2
            WHERE id = $3
            """,
            is_active, updated_at or datetime.utcnow(), chat_id
        )

    @staticmethod
    async def hard_delete_chat(chat_id: uuid.UUID) -> None:
        """
        Hard delete a chat and all related PostgreSQL data.

        Deletes:
        - Chat participants (includes read status via last_read_at/last_read_message_id)
        - The chat itself

        Note: Messages are stored in ScyllaDB (Discord pattern) and require
        separate cleanup via MessageScyllaRepo or TTL expiration.
        """
        # Delete in correct order to avoid FK constraint violations
        await pg_client.execute(
            "DELETE FROM chat_participants WHERE chat_id = $1",
            chat_id
        )
        await pg_client.execute(
            "DELETE FROM chats WHERE id = $1",
            chat_id
        )

    @staticmethod
    async def update_chat_last_message(
        chat_id: uuid.UUID,
        last_message_at: datetime,
        last_message_content: Optional[str] = None,
        last_message_sender_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Update chat's last message info"""
        await pg_client.execute(
            """
            UPDATE chats
            SET last_message_at = $1,
                last_message_content = $2,
                last_message_sender_id = $3,
                updated_at = NOW()
            WHERE id = $4
            """,
            last_message_at, last_message_content, last_message_sender_id, chat_id
        )

    @staticmethod
    async def update_chat_telegram(
        chat_id: uuid.UUID,
        telegram_chat_id: Optional[int],
        telegram_topic_id: Optional[int] = None,
    ) -> None:
        """
        Update Telegram integration fields.

        Note: Parameter is telegram_chat_id but DB column is telegram_supergroup_id.
        """
        await pg_client.execute(
            """
            UPDATE chats
            SET telegram_supergroup_id = $1, telegram_topic_id = $2, updated_at = NOW()
            WHERE id = $3
            """,
            telegram_chat_id, telegram_topic_id, chat_id
        )

    @staticmethod
    async def increment_participant_count(chat_id: uuid.UUID) -> None:
        """Increment participant count"""
        await pg_client.execute(
            "UPDATE chats SET participant_count = participant_count + 1 WHERE id = $1",
            chat_id
        )

    @staticmethod
    async def decrement_participant_count(chat_id: uuid.UUID) -> None:
        """Decrement participant count"""
        await pg_client.execute(
            "UPDATE chats SET participant_count = GREATEST(0, participant_count - 1) WHERE id = $1",
            chat_id
        )

    @staticmethod
    async def get_chat_by_id(chat_id: uuid.UUID) -> Optional[ChatReadModel]:
        """Get chat by ID"""
        row = await pg_client.fetchrow(
            """
            SELECT
                c.id, c.name, c.type as chat_type, c.company_id, c.created_by,
                c.created_at, c.updated_at, c.is_active, c.metadata,
                c.telegram_supergroup_id as telegram_chat_id,
                c.telegram_topic_id,
                0 as participant_count, 0 as version,
                NULL::timestamp as last_message_at,
                NULL::text as last_message_content,
                NULL::uuid as last_message_sender_id
            FROM chats c
            WHERE c.id = $1
            """,
            chat_id
        )
        if not row:
            return None
        return ChatReadModel(**dict(row))

    @staticmethod
    async def get_chat_by_telegram_id(
        telegram_chat_id: int,
        telegram_topic_id: Optional[int] = None,
    ) -> Optional[ChatReadModel]:
        """
        Get chat by Telegram supergroup ID.

        Note: Parameter is telegram_chat_id but DB column is telegram_supergroup_id.
        """
        log.info(f"[LOOKUP] Searching chat: tg_chat_id={telegram_chat_id}, tg_topic_id={telegram_topic_id}")
        if telegram_topic_id:
            row = await pg_client.fetchrow(
                """
                SELECT
                    c.id, c.name, c.type as chat_type, c.company_id, c.created_by,
                    c.created_at, c.updated_at, c.is_active, c.metadata,
                    c.telegram_supergroup_id as telegram_chat_id,
                    c.telegram_topic_id,
                    0 as participant_count, 0 as version,
                    NULL::timestamp as last_message_at,
                    NULL::text as last_message_content,
                    NULL::uuid as last_message_sender_id
                FROM chats c
                WHERE c.telegram_supergroup_id = $1 AND c.telegram_topic_id = $2
                """,
                telegram_chat_id, telegram_topic_id
            )
        else:
            # First try exact match: topic_id IS NULL
            row = await pg_client.fetchrow(
                """
                SELECT
                    c.id, c.name, c.type as chat_type, c.company_id, c.created_by,
                    c.created_at, c.updated_at, c.is_active, c.metadata,
                    c.telegram_supergroup_id as telegram_chat_id,
                    c.telegram_topic_id,
                    0 as participant_count, 0 as version,
                    NULL::timestamp as last_message_at,
                    NULL::text as last_message_content,
                    NULL::uuid as last_message_sender_id
                FROM chats c
                WHERE c.telegram_supergroup_id = $1 AND c.telegram_topic_id IS NULL
                """,
                telegram_chat_id
            )
            # Fallback: find ANY chat linked to this supergroup (for General topic messages)
            if not row:
                row = await pg_client.fetchrow(
                    """
                    SELECT
                        c.id, c.name, c.type as chat_type, c.company_id, c.created_by,
                        c.created_at, c.updated_at, c.is_active, c.metadata,
                        c.telegram_supergroup_id as telegram_chat_id,
                        c.telegram_topic_id,
                        0 as participant_count, 0 as version,
                        NULL::timestamp as last_message_at,
                        NULL::text as last_message_content,
                        NULL::uuid as last_message_sender_id
                    FROM chats c
                    WHERE c.telegram_supergroup_id = $1 AND c.is_active = true
                    ORDER BY c.created_at ASC
                    LIMIT 1
                    """,
                    telegram_chat_id
                )
        if not row:
            log.warning(f"[LOOKUP] No chat found for tg_chat_id={telegram_chat_id}, tg_topic_id={telegram_topic_id}")
            return None
        model = ChatReadModel(**dict(row))
        log.info(f"[LOOKUP] Found chat: id={model.id}, name={model.name}, db_topic={model.telegram_topic_id}")
        return model

    @staticmethod
    async def get_chats_by_user(
        user_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatListItemReadModel]:
        """
        Get all chats for a user.

        Discord Pattern: Messages are in ScyllaDB, not PostgreSQL.
        Unread counts are tracked in ScyllaDB's message_read_positions table
        and should be fetched separately via MessageScyllaRepo.
        """
        active_filter = "" if include_archived else "AND c.is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT
                c.id, c.name, c.type as chat_type, c.participant_count,
                c.last_message_at, c.last_message_content, c.is_active,
                c.telegram_supergroup_id, c.telegram_topic_id, c.company_id,
                COALESCE(cp.unread_count, 0) as unread_count,
                CASE
                    WHEN c.type = 'direct' THEN other_user.full_name
                    ELSE NULL
                END as other_participant_name
            FROM chats c
            INNER JOIN chat_participants cp ON c.id = cp.chat_id AND cp.user_id = $1 AND cp.is_active = true
            LEFT JOIN LATERAL (
                SELECT COALESCE(u.first_name || ' ' || u.last_name, u.first_name, u.last_name, 'Unknown') as full_name
                FROM chat_participants cp2
                INNER JOIN user_accounts u ON cp2.user_id = u.id
                WHERE cp2.chat_id = c.id AND cp2.user_id != $1 AND cp2.is_active = true
                LIMIT 1
            ) other_user ON c.type = 'direct'
            WHERE 1=1 {active_filter}
            ORDER BY c.last_message_at DESC NULLS LAST
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )

        return [ChatListItemReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_chats_by_company(
        company_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatReadModel]:
        """
        Get all chats for a company.

        Finds chats by:
        1. Direct company_id link (chats.company_id = company_id)
        2. Telegram link (chats.telegram_supergroup_id belongs to company)

        This handles cases where chats were created via Telegram sync and may
        not have company_id set directly, or where company was re-linked.
        """
        active_filter = "" if include_archived else "AND c.is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT DISTINCT
                c.id, c.name, c.type as chat_type, c.company_id, c.created_by, c.created_at,
                c.updated_at, c.is_active, c.participant_count, c.last_message_at,
                c.last_message_content, c.last_message_sender_id,
                c.telegram_supergroup_id as telegram_chat_id, c.telegram_topic_id,
                c.metadata, c.version
            FROM chats c
            LEFT JOIN telegram_supergroups ts ON c.telegram_supergroup_id = ts.id
            WHERE (c.company_id = $1 OR ts.company_id = $1) {active_filter}
            ORDER BY c.last_message_at DESC NULLS LAST
            LIMIT $2 OFFSET $3
            """,
            company_id, limit, offset
        )

        return [ChatReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def search_chats(
        user_id: uuid.UUID,
        search_term: str,
        limit: int = 20,
    ) -> List[ChatReadModel]:
        """Search chats by name"""
        rows = await pg_client.fetch(
            """
            SELECT
                c.id, c.name, c.type as chat_type, c.company_id, c.created_by, c.created_at,
                c.updated_at, c.is_active, c.participant_count, c.last_message_at,
                c.last_message_content, c.last_message_sender_id,
                c.telegram_supergroup_id as telegram_chat_id, c.telegram_topic_id,
                c.metadata, c.version
            FROM chats c
            INNER JOIN chat_participants cp ON c.id = cp.chat_id
              AND cp.user_id = $1 AND cp.is_active = true
            WHERE c.name ILIKE $2 AND c.is_active = true
            ORDER BY c.last_message_at DESC NULLS LAST
            LIMIT $3
            """,
            user_id, f"%{search_term}%", limit
        )

        return [ChatReadModel(**dict(row)) for row in rows]

    # =========================================================================
    # Participant Operations
    # =========================================================================

    @staticmethod
    async def insert_participant(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = "member",
        joined_at: Optional[datetime] = None,
    ) -> None:
        """Insert a new participant"""
        await pg_client.execute(
            """
            INSERT INTO chat_participants (id, chat_id, user_id, role, joined_at, is_active)
            VALUES (gen_random_uuid(), $1, $2, $3, $4, true)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET is_active = true, role = $3
            """,
            chat_id, user_id, role, joined_at or datetime.utcnow()
        )

    @staticmethod
    async def deactivate_participant(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Deactivate a participant (soft delete)"""
        await pg_client.execute(
            """
            UPDATE chat_participants SET is_active = false
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id, user_id
        )

    @staticmethod
    async def update_participant_role(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> None:
        """Update participant's role"""
        await pg_client.execute(
            """
            UPDATE chat_participants SET role = $1
            WHERE chat_id = $2 AND user_id = $3
            """,
            role, chat_id, user_id
        )

    @staticmethod
    async def update_participant_last_read(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        last_read_message_id: Optional[int],  # Snowflake ID (unused in PG, tracked in ScyllaDB)
        last_read_at: datetime,
    ) -> None:
        """Update participant's last read timestamp.

        Note: The actual read position (last_read_message_id as Snowflake) is
        stored in ScyllaDB's message_read_positions table. PostgreSQL only
        tracks the timestamp for chat list sorting/metadata.
        """
        await pg_client.execute(
            """
            UPDATE chat_participants
            SET last_read_at = $1
            WHERE chat_id = $2 AND user_id = $3
            """,
            last_read_at, chat_id, user_id
        )

    @staticmethod
    async def get_chat_participants(
        chat_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> List[ChatParticipantReadModel]:
        """Get participants of a chat with user details"""
        active_filter = "" if include_inactive else "AND cp.is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT
                cp.*,
                COALESCE(u.first_name || ' ' || u.last_name, u.first_name, u.last_name, 'Unknown') as user_name,
                u.email as user_email,
                u.avatar_url as user_avatar_url
            FROM chat_participants cp
            LEFT JOIN user_accounts u ON cp.user_id = u.id
            WHERE cp.chat_id = $1 {active_filter}
            ORDER BY cp.joined_at
            """,
            chat_id
        )

        return [ChatParticipantReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_user_participation(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[ChatParticipantReadModel]:
        """Get user's participation status in chat"""
        row = await pg_client.fetchrow(
            """
            SELECT * FROM chat_participants
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id, user_id
        )
        if not row:
            return None
        return ChatParticipantReadModel(**dict(row))

    # =========================================================================
    # Message Templates Operations (Read Model)
    # =========================================================================

    @staticmethod
    async def get_all_templates(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all message templates"""
        sql = """
            SELECT
                id, name, description, category, template_data,
                image_url, created_by, is_active, created_at, updated_at
            FROM message_templates
        """
        if active_only:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY category, name"

        rows = await pg_client.fetch(sql)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_template_by_id(template_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get message template by ID"""
        row = await pg_client.fetchrow(
            """
            SELECT
                id, name, description, category, template_data,
                image_url, created_by, is_active, created_at, updated_at
            FROM message_templates
            WHERE id = $1
            """,
            template_id
        )
        if not row:
            return None
        return dict(row)

    @staticmethod
    async def get_templates_by_category(
        category: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get message templates by category"""
        sql = """
            SELECT
                id, name, description, category, template_data,
                image_url, created_by, is_active, created_at, updated_at
            FROM message_templates
            WHERE category = $1
        """
        if active_only:
            sql += " AND is_active = TRUE"
        sql += " ORDER BY name"

        rows = await pg_client.fetch(sql, category)
        return [dict(row) for row in rows]

    # =========================================================================
    # Telegram Integration Operations
    # =========================================================================

    @staticmethod
    async def get_linked_telegram_chats(
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all chats that have a linked Telegram supergroup.

        Used by the Telegram polling mechanism to know which supergroups to monitor.
        """
        active_filter = "AND is_active = true" if active_only else ""

        rows = await pg_client.fetch(
            f"""
            SELECT
                id as chat_id,
                telegram_supergroup_id,
                telegram_topic_id,
                name
            FROM chats
            WHERE telegram_supergroup_id IS NOT NULL
            {active_filter}
            ORDER BY updated_at DESC NULLS LAST
            """,
        )

        return [dict(row) for row in rows]

    # =========================================================================
    # Telegram Group Members Operations
    # =========================================================================

    @staticmethod
    async def upsert_telegram_group_member(
        supergroup_id: int,
        telegram_user_id: int,
        first_name: str,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        status: str = "member",
        joined_at: Optional[datetime] = None,
    ) -> None:
        """
        Upsert a Telegram group member.

        Used when clients are invited to groups via InviteClientCommand.
        Also used by incoming_handler when users join via invite link.

        Args:
            supergroup_id: Telegram supergroup ID (BIGINT)
            telegram_user_id: User's Telegram ID (BIGINT)
            first_name: User's first name
            last_name: User's last name (optional)
            username: User's @username (optional)
            status: member, administrator, creator, left, kicked
            joined_at: When user joined (defaults to now)
        """
        await pg_client.execute(
            """
            INSERT INTO telegram_group_members (
                supergroup_id, telegram_user_id, first_name, last_name,
                username, status, joined_at, is_active, last_seen
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, true, NOW())
            ON CONFLICT (supergroup_id, telegram_user_id) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                username = COALESCE(EXCLUDED.username, telegram_group_members.username),
                status = EXCLUDED.status,
                is_active = true,
                last_seen = NOW()
            """,
            supergroup_id, telegram_user_id, first_name, last_name,
            username, status, joined_at or datetime.utcnow()
        )

    @staticmethod
    async def get_telegram_group_members(
        supergroup_id: int,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all members of a Telegram supergroup"""
        active_filter = "AND is_active = true" if active_only else ""

        rows = await pg_client.fetch(
            f"""
            SELECT
                telegram_user_id,
                first_name,
                last_name,
                username,
                status,
                joined_at,
                last_seen,
                is_active
            FROM telegram_group_members
            WHERE supergroup_id = $1 {active_filter}
            ORDER BY joined_at DESC
            """,
            supergroup_id
        )

        return [dict(row) for row in rows]

    # =========================================================================
    # Unread Count Operations
    # =========================================================================

    @staticmethod
    async def get_unread_chats_count(user_id: uuid.UUID) -> int:
        """
        Get count of chats with unread messages for a user.

        Used by:
        - GET /chats/unread-count endpoint
        - GetUnreadChatsCountQuery handler

        Returns count of chats where unread_count > 0 for this user.
        """
        result = await pg_client.fetchval(
            """
            SELECT COUNT(*)
            FROM chats c
            INNER JOIN chat_participants cp ON c.id = cp.chat_id
            WHERE cp.user_id = $1
              AND cp.is_active = true
              AND cp.unread_count > 0
              AND c.is_active = true
            """,
            user_id
        )
        return result or 0

    @staticmethod
    async def increment_unread_count(
        chat_id: uuid.UUID,
        exclude_user_id: uuid.UUID,
    ) -> None:
        """
        Increment unread_count for all participants EXCEPT the sender.

        Called by MessageSent projector to mark message as unread
        for all other participants in the chat.

        Args:
            chat_id: Chat where message was sent
            exclude_user_id: User who sent the message (don't increment for them)
        """
        await pg_client.execute(
            """
            UPDATE chat_participants
            SET unread_count = unread_count + 1
            WHERE chat_id = $1
              AND user_id != $2
              AND is_active = true
            """,
            chat_id, exclude_user_id
        )

    @staticmethod
    async def reset_unread_count(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Reset unread_count to 0 when user reads messages.

        Called by MessagesMarkedAsRead projector.

        Args:
            chat_id: Chat where messages were read
            user_id: User who read the messages
        """
        await pg_client.execute(
            """
            UPDATE chat_participants
            SET unread_count = 0, last_read_at = NOW()
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id, user_id
        )

    @staticmethod
    async def get_participant_unread_count(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """
        Get unread count for a specific participant in a chat.

        Args:
            chat_id: Chat ID
            user_id: User ID

        Returns:
            Number of unread messages for this user in this chat
        """
        result = await pg_client.fetchval(
            """
            SELECT COALESCE(unread_count, 0)
            FROM chat_participants
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id, user_id
        )
        return result or 0
