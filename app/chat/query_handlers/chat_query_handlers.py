# =============================================================================
# File: app/chat/query_handlers/chat_query_handlers.py
# Description: Query handlers for chat operations
# =============================================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from app.infra.cqrs.cqrs_decorators import query_handler, cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.chat.queries import (
    GetChatByIdQuery,
    GetChatsByUserQuery,
    GetChatsByCompanyQuery,
    GetChatByTelegramIdQuery,
    GetLinkedTelegramChatsQuery,
    SearchChatsQuery,
    GetChatParticipantsQuery,
    GetUserParticipationQuery,
    ChatDetail,
    ChatSummary,
    ParticipantInfo,
    UserParticipation,
    LinkedTelegramChat,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.read_repos.chat_read_repo import ChatReadRepo

log = logging.getLogger("wellwon.chat.query_handlers")


@cached_query_handler(GetChatByIdQuery, ttl=60)
class GetChatByIdQueryHandler(BaseQueryHandler[GetChatByIdQuery, Optional[ChatDetail]]):
    """Get chat details by ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatByIdQuery) -> Optional[ChatDetail]:
        """Fetch chat from read model"""
        chat = await self.chat_read_repo.get_chat_by_id(query.chat_id)

        if not chat:
            return None

        return ChatDetail(
            id=chat.id,
            name=chat.name,
            chat_type=chat.chat_type,
            created_by=chat.created_by,
            company_id=chat.company_id,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            is_active=chat.is_active,
            participant_count=chat.participant_count,
            last_message_at=chat.last_message_at,
            telegram_chat_id=chat.telegram_chat_id,
            telegram_supergroup_id=chat.telegram_chat_id,  # Same value for compatibility
            telegram_topic_id=chat.telegram_topic_id,
            last_message_content=chat.last_message_content,
            last_message_sender_id=chat.last_message_sender_id,
        )


@query_handler(GetChatsByUserQuery)
class GetChatsByUserQueryHandler(BaseQueryHandler[GetChatsByUserQuery, List[ChatSummary]]):
    """Get all chats for a user"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatsByUserQuery) -> List[ChatSummary]:
        """Fetch user's chats from read model"""
        chats = await self.chat_read_repo.get_chats_by_user(
            user_id=query.user_id,
            include_archived=query.include_archived,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            ChatSummary(
                id=chat.id,
                name=chat.name,
                chat_type=chat.chat_type,
                participant_count=chat.participant_count,
                last_message_at=chat.last_message_at,
                last_message_content=chat.last_message_content,
                unread_count=getattr(chat, 'unread_count', 0),
                is_active=chat.is_active,
                company_id=getattr(chat, 'company_id', None),
                telegram_supergroup_id=getattr(chat, 'telegram_supergroup_id', None),
                telegram_topic_id=getattr(chat, 'telegram_topic_id', None),
                other_participant_name=getattr(chat, 'other_participant_name', None),
            )
            for chat in chats
        ]


@query_handler(GetChatsByCompanyQuery)
class GetChatsByCompanyQueryHandler(BaseQueryHandler[GetChatsByCompanyQuery, List[ChatSummary]]):
    """Get all chats for a company"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatsByCompanyQuery) -> List[ChatSummary]:
        """Fetch company's chats from read model"""
        chats = await self.chat_read_repo.get_chats_by_company(
            company_id=query.company_id,
            include_archived=query.include_archived,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            ChatSummary(
                id=chat.id,
                name=chat.name,
                chat_type=chat.chat_type,
                participant_count=chat.participant_count,
                last_message_at=chat.last_message_at,
                last_message_content=chat.last_message_content,
                is_active=chat.is_active,
            )
            for chat in chats
        ]


@cached_query_handler(GetChatByTelegramIdQuery, ttl=300)
class GetChatByTelegramIdQueryHandler(BaseQueryHandler[GetChatByTelegramIdQuery, Optional[ChatDetail]]):
    """Get chat by Telegram chat ID"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatByTelegramIdQuery) -> Optional[ChatDetail]:
        """Fetch chat by Telegram ID from read model"""
        chat = await self.chat_read_repo.get_chat_by_telegram_id(
            telegram_chat_id=query.telegram_chat_id,
            telegram_topic_id=query.telegram_topic_id,
        )

        if not chat:
            return None

        return ChatDetail(
            id=chat.id,
            name=chat.name,
            chat_type=chat.chat_type,
            created_by=chat.created_by,
            company_id=chat.company_id,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            is_active=chat.is_active,
            participant_count=chat.participant_count,
            last_message_at=chat.last_message_at,
            telegram_chat_id=chat.telegram_chat_id,
            telegram_supergroup_id=chat.telegram_chat_id,  # Same value for compatibility
            telegram_topic_id=chat.telegram_topic_id,
        )


@query_handler(SearchChatsQuery)
class SearchChatsQueryHandler(BaseQueryHandler[SearchChatsQuery, List[ChatSummary]]):
    """Search chats by name"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: SearchChatsQuery) -> List[ChatSummary]:
        """Search chats by name"""
        chats = await self.chat_read_repo.search_chats(
            user_id=query.user_id,
            search_term=query.search_term,
            limit=query.limit,
        )

        return [
            ChatSummary(
                id=chat.id,
                name=chat.name,
                chat_type=chat.chat_type,
                participant_count=chat.participant_count,
                last_message_at=chat.last_message_at,
                is_active=chat.is_active,
            )
            for chat in chats
        ]


@query_handler(GetChatParticipantsQuery)
class GetChatParticipantsQueryHandler(BaseQueryHandler[GetChatParticipantsQuery, List[ParticipantInfo]]):
    """Get participants of a chat"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetChatParticipantsQuery) -> List[ParticipantInfo]:
        """Fetch participants from read model with user details"""
        participants = await self.chat_read_repo.get_chat_participants(
            chat_id=query.chat_id,
            include_inactive=query.include_inactive,
        )

        return [
            ParticipantInfo(
                user_id=p.user_id,
                role=p.role,
                joined_at=p.joined_at,
                is_active=p.is_active,
                last_read_at=p.last_read_at,
                user_name=getattr(p, 'user_name', None),
                user_email=getattr(p, 'user_email', None),
                user_avatar_url=getattr(p, 'user_avatar_url', None),
            )
            for p in participants
        ]


@cached_query_handler(GetUserParticipationQuery, ttl=60)
class GetUserParticipationQueryHandler(BaseQueryHandler[GetUserParticipationQuery, UserParticipation]):
    """Check if user is participant in chat"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetUserParticipationQuery) -> UserParticipation:
        """Check user participation status"""
        participation = await self.chat_read_repo.get_user_participation(
            chat_id=query.chat_id,
            user_id=query.user_id,
        )

        if not participation:
            return UserParticipation(
                chat_id=query.chat_id,
                user_id=query.user_id,
                is_participant=False,
            )

        return UserParticipation(
            chat_id=query.chat_id,
            user_id=query.user_id,
            is_participant=participation.is_active,
            role=participation.role,
            joined_at=participation.joined_at,
        )


@query_handler(GetLinkedTelegramChatsQuery)
class GetLinkedTelegramChatsQueryHandler(BaseQueryHandler[GetLinkedTelegramChatsQuery, List[LinkedTelegramChat]]):
    """Get all chats linked to Telegram supergroups for polling"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo: 'ChatReadRepo' = deps.chat_read_repo

    async def handle(self, query: GetLinkedTelegramChatsQuery) -> List[LinkedTelegramChat]:
        """Fetch linked Telegram chats from read model"""
        chats = await self.chat_read_repo.get_linked_telegram_chats(
            active_only=query.active_only,
        )

        return [
            LinkedTelegramChat(
                chat_id=chat['chat_id'],
                telegram_supergroup_id=chat['telegram_supergroup_id'],
                telegram_topic_id=chat.get('telegram_topic_id'),
                name=chat.get('name'),
                last_telegram_message_id=0,  # TODO: Track last processed message per chat
            )
            for chat in chats
        ]
