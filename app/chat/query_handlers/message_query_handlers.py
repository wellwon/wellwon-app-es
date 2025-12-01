# =============================================================================
# File: app/chat/query_handlers/message_query_handlers.py
# Description: Query handlers for messages - ScyllaDB PRIMARY
# =============================================================================
# Architecture (Discord Pattern):
#   ScyllaDB = PRIMARY for message content
#   PostgreSQL = METADATA only (unread counts via chat_participants)
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.config.logging_config import get_logger
from app.infra.cqrs.cqrs_decorators import query_handler, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.chat.queries import (
    GetChatMessagesQuery,
    GetMessageByIdQuery,
    GetUnreadMessagesCountQuery,
    GetUnreadChatsCountQuery,
    SearchMessagesQuery,
    MessageDetail,
    UnreadCount,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.chat.query_handlers.message")


@query_handler(GetChatMessagesQuery)
class GetChatMessagesQueryHandler(BaseQueryHandler[GetChatMessagesQuery, List[MessageDetail]]):
    """
    Get messages from ScyllaDB (PRIMARY storage).

    Uses Discord-style partitioning: (channel_id, bucket) with Snowflake IDs.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.message_scylla_repo = deps.message_scylla_repo

    async def handle(self, query: GetChatMessagesQuery) -> List[MessageDetail]:
        """Fetch messages from ScyllaDB with pagination."""
        messages = await self.message_scylla_repo.get_messages(
            channel_id=query.chat_id,
            limit=query.limit,
            before_id=query.before_id,  # Snowflake ID
            after_id=query.after_id,    # Snowflake ID
        )

        return [
            MessageDetail(
                id=None,  # PostgreSQL UUID not used
                message_id=m.get('message_id'),  # Snowflake ID
                chat_id=m.get('channel_id'),
                sender_id=m.get('sender_id'),
                content=m.get('content'),
                message_type=m.get('message_type', 'text'),
                reply_to_id=m.get('reply_to_id'),
                file_url=m.get('file_url'),
                file_name=m.get('file_name'),
                file_size=m.get('file_size'),
                file_type=m.get('file_type'),
                voice_duration=m.get('voice_duration'),
                created_at=m.get('created_at'),
                updated_at=m.get('updated_at'),
                is_edited=m.get('is_edited', False),
                is_deleted=m.get('is_deleted', False),
                source=m.get('source', 'web'),
                # Telegram fields
                telegram_message_id=m.get('telegram_message_id'),
                telegram_user_id=m.get('telegram_user_id'),
                telegram_user_data=m.get('telegram_user_data'),
                telegram_forward_data=m.get('telegram_forward_data'),
                telegram_topic_id=m.get('telegram_topic_id'),
                sync_direction=m.get('sync_direction'),
            )
            for m in messages
        ]


@cached_query_handler(GetMessageByIdQuery, ttl=60)
class GetMessageByIdQueryHandler(BaseQueryHandler[GetMessageByIdQuery, Optional[MessageDetail]]):
    """Get single message from ScyllaDB by Snowflake ID."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.message_scylla_repo = deps.message_scylla_repo

    async def handle(self, query: GetMessageByIdQuery) -> Optional[MessageDetail]:
        """Fetch single message from ScyllaDB."""
        # Query requires channel_id and snowflake_id
        if not query.snowflake_id or not query.chat_id:
            return None

        message = await self.message_scylla_repo.get_message(
            channel_id=query.chat_id,
            message_id=query.snowflake_id,
        )

        if not message:
            return None

        return MessageDetail(
            id=None,
            message_id=message.get('message_id'),
            chat_id=message.get('channel_id'),
            sender_id=message.get('sender_id'),
            content=message.get('content'),
            message_type=message.get('message_type', 'text'),
            reply_to_id=message.get('reply_to_id'),
            file_url=message.get('file_url'),
            file_name=message.get('file_name'),
            file_size=message.get('file_size'),
            file_type=message.get('file_type'),
            voice_duration=message.get('voice_duration'),
            created_at=message.get('created_at'),
            updated_at=message.get('updated_at'),
            is_edited=message.get('is_edited', False),
            is_deleted=message.get('is_deleted', False),
            source=message.get('source', 'web'),
            telegram_message_id=message.get('telegram_message_id'),
            telegram_user_id=message.get('telegram_user_id'),
            telegram_user_data=message.get('telegram_user_data'),
            telegram_forward_data=message.get('telegram_forward_data'),
            telegram_topic_id=message.get('telegram_topic_id'),
            sync_direction=message.get('sync_direction'),
        )


@query_handler(GetUnreadMessagesCountQuery)
class GetUnreadMessagesCountQueryHandler(BaseQueryHandler[GetUnreadMessagesCountQuery, UnreadCount]):
    """
    Get unread count from ScyllaDB read positions.

    Uses message_read_positions table to calculate unread.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.message_scylla_repo = deps.message_scylla_repo

    async def handle(self, query: GetUnreadMessagesCountQuery) -> UnreadCount:
        """Get unread count from ScyllaDB."""
        count = await self.message_scylla_repo.get_unread_count(
            channel_id=query.chat_id,
            user_id=query.user_id,
        )

        return UnreadCount(
            chat_id=query.chat_id,
            count=count,
        )


@query_handler(GetUnreadChatsCountQuery)
class GetUnreadChatsCountQueryHandler(BaseQueryHandler[GetUnreadChatsCountQuery, int]):
    """Get count of chats with unread messages (PostgreSQL metadata)."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo = deps.chat_read_repo

    async def handle(self, query: GetUnreadChatsCountQuery) -> int:
        """Get count of chats with unread from PostgreSQL."""
        return await self.chat_read_repo.get_unread_chats_count(user_id=query.user_id)


@query_handler(SearchMessagesQuery)
class SearchMessagesQueryHandler(BaseQueryHandler[SearchMessagesQuery, List[MessageDetail]]):
    """
    Search messages - ScyllaDB content scan.

    Note: For production, consider Elasticsearch/Meilisearch for full-text search.
    ScyllaDB scan is acceptable for small result sets.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.message_scylla_repo = deps.message_scylla_repo

    async def handle(self, query: SearchMessagesQuery) -> List[MessageDetail]:
        """Search messages in ScyllaDB (limited scan)."""
        # Get recent messages and filter client-side
        # For production: use dedicated search service
        messages = await self.message_scylla_repo.get_messages(
            channel_id=query.chat_id,
            limit=query.limit * 10,  # Fetch more for filtering
        )

        # Filter by search term
        search_term = query.search_term.lower()
        filtered = [
            m for m in messages
            if search_term in (m.get('content') or '').lower()
        ][:query.limit]

        return [
            MessageDetail(
                id=None,
                message_id=m.get('message_id'),
                chat_id=m.get('channel_id'),
                sender_id=m.get('sender_id'),
                content=m.get('content'),
                message_type=m.get('message_type', 'text'),
                created_at=m.get('created_at'),
                is_deleted=m.get('is_deleted', False),
                source=m.get('source', 'web'),
                telegram_message_id=m.get('telegram_message_id'),
                telegram_user_id=m.get('telegram_user_id'),
                telegram_user_data=m.get('telegram_user_data'),
                telegram_forward_data=m.get('telegram_forward_data'),
                telegram_topic_id=m.get('telegram_topic_id'),
                sync_direction=m.get('sync_direction'),
            )
            for m in filtered
        ]
