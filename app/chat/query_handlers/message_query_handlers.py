# =============================================================================
# File: app/chat/query_handlers/message_query_handlers.py
# Description: Query handlers for message operations
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from app.infra.cqrs.decorators import query_handler, cached_query_handler
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
    from app.infra.read_repos.chat_read_repo import ChatReadRepo

log = logging.getLogger("wellwon.chat.query_handlers.message")


@query_handler(GetChatMessagesQuery)
class GetChatMessagesQueryHandler(BaseQueryHandler[GetChatMessagesQuery, List[MessageDetail]]):
    """Get messages from a chat (paginated)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatMessagesQuery) -> List[MessageDetail]:
        """Fetch messages from read model with sender info"""
        messages = await self.chat_read_repo.get_chat_messages(
            chat_id=query.chat_id,
            limit=query.limit,
            offset=query.offset,
            before_id=query.before_id,
            after_id=query.after_id,
        )

        return [
            MessageDetail(
                id=m.id,
                chat_id=m.chat_id,
                sender_id=m.sender_id,
                content=m.content,
                message_type=m.message_type,
                reply_to_id=m.reply_to_id,
                file_url=m.file_url,
                file_name=m.file_name,
                file_size=m.file_size,
                file_type=m.file_type,
                voice_duration=m.voice_duration,
                created_at=m.created_at,
                updated_at=m.updated_at,
                is_edited=m.is_edited,
                is_deleted=m.is_deleted,
                read_by_count=getattr(m, 'read_by_count', 0),
                source=m.source,
                # Telegram fields
                telegram_message_id=m.telegram_message_id,
                telegram_user_id=getattr(m, 'telegram_user_id', None),
                telegram_user_data=getattr(m, 'telegram_user_data', None),
                telegram_forward_data=getattr(m, 'telegram_forward_data', None),
                telegram_topic_id=getattr(m, 'telegram_topic_id', None),
                sync_direction=getattr(m, 'sync_direction', None),
                # Joined sender info
                sender_name=getattr(m, 'sender_name', None),
                sender_avatar_url=getattr(m, 'sender_avatar_url', None),
                reply_to_content=getattr(m, 'reply_to_content', None),
                reply_to_sender_name=getattr(m, 'reply_to_sender_name', None),
            )
            for m in messages
        ]


@cached_query_handler(GetMessageByIdQuery, ttl=60)
class GetMessageByIdQueryHandler(BaseQueryHandler[GetMessageByIdQuery, Optional[MessageDetail]]):
    """Get a single message by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetMessageByIdQuery) -> Optional[MessageDetail]:
        """Fetch single message from read model"""
        message = await self.chat_read_repo.get_message_by_id(query.message_id)

        if not message:
            return None

        return MessageDetail(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            content=message.content,
            message_type=message.message_type,
            reply_to_id=message.reply_to_id,
            file_url=message.file_url,
            file_name=message.file_name,
            file_size=message.file_size,
            file_type=message.file_type,
            voice_duration=message.voice_duration,
            created_at=message.created_at,
            updated_at=message.updated_at,
            is_edited=message.is_edited,
            is_deleted=message.is_deleted,
            source=message.source,
            # Telegram fields
            telegram_message_id=message.telegram_message_id,
            telegram_user_id=message.telegram_user_id,
            telegram_user_data=message.telegram_user_data,
            telegram_forward_data=message.telegram_forward_data,
            telegram_topic_id=message.telegram_topic_id,
            sync_direction=message.sync_direction,
        )


@query_handler(GetUnreadMessagesCountQuery)
class GetUnreadMessagesCountQueryHandler(BaseQueryHandler[GetUnreadMessagesCountQuery, UnreadCount]):
    """Get count of unread messages for user in chat"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetUnreadMessagesCountQuery) -> UnreadCount:
        """Get unread count from read model"""
        count = await self.chat_read_repo.get_unread_messages_count(
            chat_id=query.chat_id,
            user_id=query.user_id,
        )

        return UnreadCount(
            chat_id=query.chat_id,
            count=count,
        )


@query_handler(GetUnreadChatsCountQuery)
class GetUnreadChatsCountQueryHandler(BaseQueryHandler[GetUnreadChatsCountQuery, int]):
    """Get count of chats with unread messages for user"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetUnreadChatsCountQuery) -> int:
        """Get count of chats with unread messages"""
        return await self.chat_read_repo.get_unread_chats_count(user_id=query.user_id)


@query_handler(SearchMessagesQuery)
class SearchMessagesQueryHandler(BaseQueryHandler[SearchMessagesQuery, List[MessageDetail]]):
    """Search messages in chat"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: SearchMessagesQuery) -> List[MessageDetail]:
        """Search messages by content"""
        messages = await self.chat_read_repo.search_messages(
            chat_id=query.chat_id,
            search_term=query.search_term,
            limit=query.limit,
        )

        return [
            MessageDetail(
                id=m.id,
                chat_id=m.chat_id,
                sender_id=m.sender_id,
                content=m.content,
                message_type=m.message_type,
                created_at=m.created_at,
                is_deleted=m.is_deleted,
                source=m.source,
                # Telegram fields
                telegram_message_id=m.telegram_message_id,
                telegram_user_id=m.telegram_user_id,
                telegram_user_data=m.telegram_user_data,
                telegram_forward_data=m.telegram_forward_data,
                telegram_topic_id=m.telegram_topic_id,
                sync_direction=m.sync_direction,
            )
            for m in messages
        ]
