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
    MessageReadModel,
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
        """Insert a new chat record"""
        await pg_client.execute(
            """
            INSERT INTO chats (
                id, name, chat_type, created_by, company_id,
                telegram_chat_id, telegram_topic_id, created_at,
                is_active, participant_count, version
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true, 0, 1)
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

        updates.append(f"version = version + 1")

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
            SET is_active = $1, updated_at = $2, version = version + 1
            WHERE id = $3
            """,
            is_active, updated_at or datetime.utcnow(), chat_id
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
        """Update Telegram integration fields"""
        await pg_client.execute(
            """
            UPDATE chats
            SET telegram_chat_id = $1, telegram_topic_id = $2, updated_at = NOW()
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
            "SELECT * FROM chats WHERE id = $1",
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
        """Get chat by Telegram chat ID"""
        if telegram_topic_id:
            row = await pg_client.fetchrow(
                """
                SELECT * FROM chats
                WHERE telegram_chat_id = $1 AND telegram_topic_id = $2
                """,
                telegram_chat_id, telegram_topic_id
            )
        else:
            row = await pg_client.fetchrow(
                """
                SELECT * FROM chats
                WHERE telegram_chat_id = $1 AND telegram_topic_id IS NULL
                """,
                telegram_chat_id
            )
        if not row:
            return None
        return ChatReadModel(**dict(row))

    @staticmethod
    async def get_chats_by_user(
        user_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatListItemReadModel]:
        """Get all chats for a user with unread counts"""
        active_filter = "" if include_archived else "AND c.is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT
                c.id, c.name, c.chat_type, c.participant_count,
                c.last_message_at, c.last_message_content, c.is_active,
                COALESCE(unread.count, 0) as unread_count,
                CASE
                    WHEN c.chat_type = 'direct' THEN other_user.full_name
                    ELSE NULL
                END as other_participant_name
            FROM chats c
            INNER JOIN chat_participants cp ON c.id = cp.chat_id AND cp.user_id = $1 AND cp.is_active = true
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as count
                FROM messages m
                WHERE m.chat_id = c.id
                  AND m.created_at > COALESCE(cp.last_read_at, '1970-01-01'::timestamp)
                  AND m.sender_id != $1
                  AND m.is_deleted = false
            ) unread ON true
            LEFT JOIN LATERAL (
                SELECT u.full_name
                FROM chat_participants cp2
                INNER JOIN users u ON cp2.user_id = u.id
                WHERE cp2.chat_id = c.id AND cp2.user_id != $1 AND cp2.is_active = true
                LIMIT 1
            ) other_user ON c.chat_type = 'direct'
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
        """Get all chats for a company"""
        active_filter = "" if include_archived else "AND is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT * FROM chats
            WHERE company_id = $1 {active_filter}
            ORDER BY last_message_at DESC NULLS LAST
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
            SELECT c.* FROM chats c
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
        last_read_message_id: uuid.UUID,
        last_read_at: datetime,
    ) -> None:
        """Update participant's last read position"""
        await pg_client.execute(
            """
            UPDATE chat_participants
            SET last_read_at = $1, last_read_message_id = $2
            WHERE chat_id = $3 AND user_id = $4
            """,
            last_read_at, last_read_message_id, chat_id, user_id
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
                u.full_name as user_name,
                u.email as user_email,
                u.avatar_url as user_avatar_url
            FROM chat_participants cp
            LEFT JOIN users u ON cp.user_id = u.id
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
    # Message Operations
    # =========================================================================

    @staticmethod
    async def insert_message(
        message_id: uuid.UUID,
        chat_id: uuid.UUID,
        sender_id: Optional[uuid.UUID],
        content: str,
        message_type: str = "text",
        reply_to_id: Optional[uuid.UUID] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
        voice_duration: Optional[int] = None,
        source: str = "web",
        telegram_message_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        """Insert a new message"""
        await pg_client.execute(
            """
            INSERT INTO messages (
                id, chat_id, sender_id, content, message_type,
                reply_to_id, file_url, file_name, file_size, file_type,
                voice_duration, source, telegram_message_id, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (id) DO NOTHING
            """,
            message_id, chat_id, sender_id, content, message_type,
            reply_to_id, file_url, file_name, file_size, file_type,
            voice_duration, source, telegram_message_id,
            metadata or {}, created_at or datetime.utcnow()
        )

    @staticmethod
    async def update_message_content(
        message_id: uuid.UUID,
        content: str,
        is_edited: bool = True,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update message content"""
        await pg_client.execute(
            """
            UPDATE messages
            SET content = $1, is_edited = $2, updated_at = $3
            WHERE id = $4
            """,
            content, is_edited, updated_at or datetime.utcnow(), message_id
        )

    @staticmethod
    async def soft_delete_message(
        message_id: uuid.UUID,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Soft delete a message"""
        await pg_client.execute(
            """
            UPDATE messages SET is_deleted = true, updated_at = $1
            WHERE id = $2
            """,
            updated_at or datetime.utcnow(), message_id
        )

    @staticmethod
    async def get_message_by_id(message_id: uuid.UUID) -> Optional[MessageReadModel]:
        """Get message by ID"""
        row = await pg_client.fetchrow(
            "SELECT * FROM messages WHERE id = $1",
            message_id
        )
        if not row:
            return None
        return MessageReadModel(**dict(row))

    @staticmethod
    async def get_chat_messages(
        chat_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        before_id: Optional[uuid.UUID] = None,
        after_id: Optional[uuid.UUID] = None,
    ) -> List[MessageReadModel]:
        """Get messages from a chat with pagination"""
        if before_id:
            rows = await pg_client.fetch(
                """
                SELECT m.*,
                    u.full_name as sender_name,
                    u.avatar_url as sender_avatar_url,
                    rm.content as reply_to_content,
                    ru.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages rm ON m.reply_to_id = rm.id
                LEFT JOIN users ru ON rm.sender_id = ru.id
                WHERE m.chat_id = $1 AND m.created_at < (SELECT created_at FROM messages WHERE id = $2)
                ORDER BY m.created_at DESC
                LIMIT $3
                """,
                chat_id, before_id, limit
            )
        elif after_id:
            rows = await pg_client.fetch(
                """
                SELECT m.*,
                    u.full_name as sender_name,
                    u.avatar_url as sender_avatar_url,
                    rm.content as reply_to_content,
                    ru.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages rm ON m.reply_to_id = rm.id
                LEFT JOIN users ru ON rm.sender_id = ru.id
                WHERE m.chat_id = $1 AND m.created_at > (SELECT created_at FROM messages WHERE id = $2)
                ORDER BY m.created_at ASC
                LIMIT $3
                """,
                chat_id, after_id, limit
            )
        else:
            rows = await pg_client.fetch(
                """
                SELECT m.*,
                    u.full_name as sender_name,
                    u.avatar_url as sender_avatar_url,
                    rm.content as reply_to_content,
                    ru.full_name as reply_to_sender_name
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN messages rm ON m.reply_to_id = rm.id
                LEFT JOIN users ru ON rm.sender_id = ru.id
                WHERE m.chat_id = $1
                ORDER BY m.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                chat_id, limit, offset
            )

        return [MessageReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def search_messages(
        chat_id: uuid.UUID,
        search_term: str,
        limit: int = 20,
    ) -> List[MessageReadModel]:
        """Search messages in chat by content"""
        rows = await pg_client.fetch(
            """
            SELECT * FROM messages
            WHERE chat_id = $1 AND content ILIKE $2 AND is_deleted = false
            ORDER BY created_at DESC
            LIMIT $3
            """,
            chat_id, f"%{search_term}%", limit
        )

        return [MessageReadModel(**dict(row)) for row in rows]

    # =========================================================================
    # Message Read Status Operations
    # =========================================================================

    @staticmethod
    async def insert_message_read(
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        read_at: datetime,
    ) -> None:
        """Insert message read status"""
        await pg_client.execute(
            """
            INSERT INTO message_reads (id, message_id, user_id, read_at)
            VALUES (gen_random_uuid(), $1, $2, $3)
            ON CONFLICT (message_id, user_id) DO UPDATE SET read_at = $3
            """,
            message_id, user_id, read_at
        )

    @staticmethod
    async def get_unread_messages_count(
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Get count of unread messages for user in chat"""
        result = await pg_client.fetchval(
            """
            SELECT COUNT(*) FROM messages m
            LEFT JOIN chat_participants cp ON cp.chat_id = m.chat_id AND cp.user_id = $2
            WHERE m.chat_id = $1
              AND m.sender_id != $2
              AND m.is_deleted = false
              AND m.created_at > COALESCE(cp.last_read_at, '1970-01-01'::timestamp)
            """,
            chat_id, user_id
        )
        return result or 0

    @staticmethod
    async def get_unread_chats_count(user_id: uuid.UUID) -> int:
        """Get count of chats with unread messages"""
        result = await pg_client.fetchval(
            """
            SELECT COUNT(DISTINCT c.id) FROM chats c
            INNER JOIN chat_participants cp ON c.id = cp.chat_id AND cp.user_id = $1 AND cp.is_active = true
            WHERE EXISTS (
                SELECT 1 FROM messages m
                WHERE m.chat_id = c.id
                  AND m.sender_id != $1
                  AND m.is_deleted = false
                  AND m.created_at > COALESCE(cp.last_read_at, '1970-01-01'::timestamp)
            )
            """,
            user_id
        )
        return result or 0

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
