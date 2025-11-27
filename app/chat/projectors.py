# =============================================================================
# File: app/chat/projectors.py
# Description: Chat domain event projectors for read model updates
# =============================================================================

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_store.sync_decorators import sync_projection, monitor_projection

if TYPE_CHECKING:
    from app.infra.read_repos.chat_read_repo import ChatReadRepo

log = logging.getLogger("wellwon.chat.projectors")


class ChatProjector:
    """
    Projects chat domain events to PostgreSQL read models.

    Handles all chat-related events and updates the corresponding
    read model tables (chats, chat_participants, messages, message_reads).
    """

    def __init__(self, chat_read_repo: 'ChatReadRepo'):
        self.chat_read_repo = chat_read_repo

    # =========================================================================
    # Chat Lifecycle Projections
    # =========================================================================

    @sync_projection("ChatCreated")
    @monitor_projection
    async def on_chat_created(self, envelope: EventEnvelope) -> None:
        """Project ChatCreated event to read model"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id

        log.info(f"Projecting ChatCreated: chat_id={chat_id}")

        await self.chat_read_repo.insert_chat(
            chat_id=chat_id,
            name=event_data.get('name'),
            chat_type=event_data['chat_type'],
            created_by=uuid.UUID(event_data['created_by']),
            company_id=uuid.UUID(event_data['company_id']) if event_data.get('company_id') else None,
            telegram_chat_id=event_data.get('telegram_chat_id'),
            telegram_topic_id=event_data.get('telegram_topic_id'),
            created_at=envelope.timestamp,
        )

    @sync_projection("ChatUpdated")
    async def on_chat_updated(self, envelope: EventEnvelope) -> None:
        """Project ChatUpdated event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id

        log.info(f"Projecting ChatUpdated: chat_id={chat_id}")

        await self.chat_read_repo.update_chat(
            chat_id=chat_id,
            name=event_data.get('name'),
            metadata=event_data.get('metadata'),
            updated_at=envelope.timestamp,
        )

    @sync_projection("ChatArchived")
    async def on_chat_archived(self, envelope: EventEnvelope) -> None:
        """Project ChatArchived event"""
        chat_id = envelope.aggregate_id

        log.info(f"Projecting ChatArchived: chat_id={chat_id}")

        await self.chat_read_repo.update_chat_status(
            chat_id=chat_id,
            is_active=False,
            updated_at=envelope.timestamp,
        )

    @sync_projection("ChatRestored")
    async def on_chat_restored(self, envelope: EventEnvelope) -> None:
        """Project ChatRestored event"""
        chat_id = envelope.aggregate_id

        log.info(f"Projecting ChatRestored: chat_id={chat_id}")

        await self.chat_read_repo.update_chat_status(
            chat_id=chat_id,
            is_active=True,
            updated_at=envelope.timestamp,
        )

    # =========================================================================
    # Participant Projections
    # =========================================================================

    @sync_projection("ParticipantAdded")
    @monitor_projection
    async def on_participant_added(self, envelope: EventEnvelope) -> None:
        """Project ParticipantAdded event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantAdded: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.insert_participant(
            chat_id=chat_id,
            user_id=user_id,
            role=event_data.get('role', 'member'),
            joined_at=datetime.fromisoformat(event_data['joined_at']) if event_data.get('joined_at') else envelope.timestamp,
        )

        # Update participant count on chat
        await self.chat_read_repo.increment_participant_count(chat_id)

    @sync_projection("ParticipantRemoved")
    async def on_participant_removed(self, envelope: EventEnvelope) -> None:
        """Project ParticipantRemoved event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantRemoved: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.deactivate_participant(
            chat_id=chat_id,
            user_id=user_id,
        )

        # Update participant count on chat
        await self.chat_read_repo.decrement_participant_count(chat_id)

    @sync_projection("ParticipantRoleChanged")
    async def on_participant_role_changed(self, envelope: EventEnvelope) -> None:
        """Project ParticipantRoleChanged event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantRoleChanged: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.update_participant_role(
            chat_id=chat_id,
            user_id=user_id,
            role=event_data['new_role'],
        )

    @sync_projection("ParticipantLeft")
    async def on_participant_left(self, envelope: EventEnvelope) -> None:
        """Project ParticipantLeft event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantLeft: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.deactivate_participant(
            chat_id=chat_id,
            user_id=user_id,
        )

        await self.chat_read_repo.decrement_participant_count(chat_id)

    # =========================================================================
    # Message Projections
    # =========================================================================

    @sync_projection("MessageSent")
    @monitor_projection
    async def on_message_sent(self, envelope: EventEnvelope) -> None:
        """Project MessageSent event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        message_id = uuid.UUID(event_data['message_id'])

        log.info(f"Projecting MessageSent: message_id={message_id}, chat_id={chat_id}")

        # sender_id can be None for external Telegram users
        sender_id = uuid.UUID(event_data['sender_id']) if event_data.get('sender_id') else None

        # Determine sync_direction based on source
        source = event_data.get('source', 'web')
        sync_direction = 'telegram_to_web' if source == 'telegram' else None

        await self.chat_read_repo.insert_message(
            message_id=message_id,
            chat_id=uuid.UUID(event_data['chat_id']),
            sender_id=sender_id,
            content=event_data['content'],
            message_type=event_data.get('message_type', 'text'),
            reply_to_id=uuid.UUID(event_data['reply_to_id']) if event_data.get('reply_to_id') else None,
            file_url=event_data.get('file_url'),
            file_name=event_data.get('file_name'),
            file_size=event_data.get('file_size'),
            file_type=event_data.get('file_type'),
            voice_duration=event_data.get('voice_duration'),
            source=source,
            telegram_message_id=event_data.get('telegram_message_id'),
            telegram_user_id=event_data.get('telegram_user_id'),
            telegram_user_data=event_data.get('telegram_user_data'),
            telegram_forward_data=event_data.get('telegram_forward_data'),
            telegram_topic_id=event_data.get('telegram_topic_id'),
            sync_direction=sync_direction,
            created_at=envelope.timestamp,
        )

        # Update chat's last message
        await self.chat_read_repo.update_chat_last_message(
            chat_id=uuid.UUID(event_data['chat_id']),
            last_message_at=envelope.timestamp,
            last_message_content=event_data['content'][:100],  # Truncate for preview
            last_message_sender_id=sender_id,
        )

    @sync_projection("MessageEdited")
    async def on_message_edited(self, envelope: EventEnvelope) -> None:
        """Project MessageEdited event"""
        event_data = envelope.event_data
        message_id = uuid.UUID(event_data['message_id'])

        log.info(f"Projecting MessageEdited: message_id={message_id}")

        await self.chat_read_repo.update_message_content(
            message_id=message_id,
            content=event_data['new_content'],
            is_edited=True,
            updated_at=envelope.timestamp,
        )

    @sync_projection("MessageDeleted")
    async def on_message_deleted(self, envelope: EventEnvelope) -> None:
        """Project MessageDeleted event (soft delete)"""
        event_data = envelope.event_data
        message_id = uuid.UUID(event_data['message_id'])

        log.info(f"Projecting MessageDeleted: message_id={message_id}")

        await self.chat_read_repo.soft_delete_message(
            message_id=message_id,
            updated_at=envelope.timestamp,
        )

    @sync_projection("MessageReadStatusUpdated")
    async def on_message_read_status_updated(self, envelope: EventEnvelope) -> None:
        """Project MessageReadStatusUpdated event"""
        event_data = envelope.event_data
        message_id = uuid.UUID(event_data['message_id'])
        user_id = uuid.UUID(event_data['user_id'])

        log.debug(f"Projecting MessageReadStatusUpdated: message={message_id}, user={user_id}")

        await self.chat_read_repo.insert_message_read(
            message_id=message_id,
            user_id=user_id,
            read_at=datetime.fromisoformat(event_data['read_at']) if event_data.get('read_at') else envelope.timestamp,
        )

    @sync_projection("MessagesMarkedAsRead")
    async def on_messages_marked_as_read(self, envelope: EventEnvelope) -> None:
        """Project MessagesMarkedAsRead event (batch read)"""
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        user_id = uuid.UUID(event_data['user_id'])
        last_read_message_id = uuid.UUID(event_data['last_read_message_id'])

        log.debug(f"Projecting MessagesMarkedAsRead: chat={chat_id}, user={user_id}")

        # Update participant's last read position
        await self.chat_read_repo.update_participant_last_read(
            chat_id=chat_id,
            user_id=user_id,
            last_read_message_id=last_read_message_id,
            last_read_at=envelope.timestamp,
        )

    # =========================================================================
    # Telegram Integration Projections
    # =========================================================================

    @sync_projection("TelegramChatLinked")
    async def on_telegram_chat_linked(self, envelope: EventEnvelope) -> None:
        """Project TelegramChatLinked event"""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id

        log.info(f"Projecting TelegramChatLinked: chat={chat_id}, telegram={event_data['telegram_chat_id']}")

        await self.chat_read_repo.update_chat_telegram(
            chat_id=chat_id,
            telegram_chat_id=event_data['telegram_chat_id'],
            telegram_topic_id=event_data.get('telegram_topic_id'),
        )

    @sync_projection("TelegramChatUnlinked")
    async def on_telegram_chat_unlinked(self, envelope: EventEnvelope) -> None:
        """Project TelegramChatUnlinked event"""
        chat_id = envelope.aggregate_id

        log.info(f"Projecting TelegramChatUnlinked: chat={chat_id}")

        await self.chat_read_repo.update_chat_telegram(
            chat_id=chat_id,
            telegram_chat_id=None,
            telegram_topic_id=None,
        )

    @sync_projection("TelegramMessageReceived")
    async def on_telegram_message_received(self, envelope: EventEnvelope) -> None:
        """
        Project TelegramMessageReceived event (DEPRECATED).

        This handler exists for backward compatibility with old events.
        New messages use unified MessageSent event with telegram_user_id field.
        """
        event_data = envelope.event_data
        message_id = uuid.UUID(event_data['message_id'])
        chat_id = uuid.UUID(event_data['chat_id'])

        log.warning(f"Projecting legacy TelegramMessageReceived: message={message_id}")

        # Insert message with telegram_user_id
        await self.chat_read_repo.insert_message(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=None,  # No mapped WellWon user
            content=event_data['content'],
            message_type=event_data.get('message_type', 'text'),
            source='telegram',
            telegram_message_id=event_data['telegram_message_id'],
            telegram_user_id=event_data.get('telegram_user_id'),
            sync_direction='telegram_to_web',
            created_at=envelope.timestamp,
        )

        # Update chat's last message
        await self.chat_read_repo.update_chat_last_message(
            chat_id=chat_id,
            last_message_at=envelope.timestamp,
            last_message_content=event_data['content'][:100],
            last_message_sender_id=None,
        )
