# =============================================================================
# File: app/chat/projectors.py
# Description: Chat domain event projectors - Discord-style architecture
# =============================================================================
# Architecture (Discord Pattern):
#   ScyllaDB = PRIMARY for message content (trillions of messages)
#   PostgreSQL = METADATA only (chat list, participants, last_message preview)
#
# Message Flow:
#   Event → ScyllaDB (content) → PostgreSQL (metadata update) → WSE
#
# References:
#   - Discord: https://discord.com/blog/how-discord-stores-trillions-of-messages
#   - Level Infinite CQRS: ScyllaDB + Event Sourcing pattern
# =============================================================================

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.config.logging_config import get_logger
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.cqrs.projector_decorators import sync_projection, async_projection, monitor_projection
from app.common.exceptions.projection_exceptions import RetriableProjectionError

# ScyllaDB imports - REQUIRED for messaging
from app.infra.read_repos.message_scylla_repo import (
    MessageScyllaRepo,
    MessageData,
    MessageType,
    MessageSource,
    SyncDirection,
)

if TYPE_CHECKING:
    from app.infra.read_repos.chat_read_repo import ChatReadRepo

log = get_logger("wellwon.chat.projectors")


class ChatProjector:
    """
    Discord-style chat projector with ScyllaDB as PRIMARY message storage.

    Architecture:
        ScyllaDB (PRIMARY):
            - ALL message content
            - Reactions, pins, read positions
            - Telegram sync state
            - Partitioned by (channel_id, bucket) with Snowflake IDs

        PostgreSQL (METADATA ONLY):
            - chats table: name, type, last_message_* (preview)
            - chat_participants: roles, last_read_at
            - telegram_supergroups, telegram_users

    Projection Pattern:
        SYNC: TelegramMessageReceived (Telegram polling reliability)
        ASYNC: All others (optimistic UI + WSE notification)
    """

    def __init__(
        self,
        chat_read_repo: 'ChatReadRepo',
        message_scylla_repo: MessageScyllaRepo,
    ):
        """
        Initialize projector with both repositories.

        Args:
            chat_read_repo: PostgreSQL repository for chat metadata
            message_scylla_repo: ScyllaDB repository for message content (REQUIRED)
        """
        self.chat_read_repo = chat_read_repo
        self.message_scylla_repo = message_scylla_repo
        log.info("ChatProjector initialized with ScyllaDB PRIMARY architecture")

    # =========================================================================
    # Chat Lifecycle Projections (PostgreSQL)
    # =========================================================================

    @async_projection("ChatCreated")
    @monitor_projection
    async def on_chat_created(self, envelope: EventEnvelope) -> None:
        """Project ChatCreated to PostgreSQL. ASYNC - saga uses event data."""
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
            created_at=envelope.stored_at,
        )

    @async_projection("ChatUpdated")
    @monitor_projection
    async def on_chat_updated(self, envelope: EventEnvelope) -> None:
        """Project ChatUpdated to PostgreSQL. ASYNC."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id

        log.info(f"Projecting ChatUpdated: chat_id={chat_id}")

        await self.chat_read_repo.update_chat(
            chat_id=chat_id,
            name=event_data.get('name'),
            metadata=event_data.get('metadata'),
            updated_at=envelope.stored_at,
        )

    @async_projection("ChatArchived")
    @monitor_projection
    async def on_chat_archived(self, envelope: EventEnvelope) -> None:
        """Project ChatArchived to PostgreSQL. ASYNC."""
        chat_id = envelope.aggregate_id
        log.info(f"Projecting ChatArchived: chat_id={chat_id}")

        await self.chat_read_repo.update_chat_status(
            chat_id=chat_id,
            is_active=False,
            updated_at=envelope.stored_at,
        )

    @async_projection("ChatRestored")
    @monitor_projection
    async def on_chat_restored(self, envelope: EventEnvelope) -> None:
        """Project ChatRestored to PostgreSQL. ASYNC."""
        chat_id = envelope.aggregate_id
        log.info(f"Projecting ChatRestored: chat_id={chat_id}")

        await self.chat_read_repo.update_chat_status(
            chat_id=chat_id,
            is_active=True,
            updated_at=envelope.stored_at,
        )

    @async_projection("ChatHardDeleted")
    @monitor_projection
    async def on_chat_hard_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project ChatHardDeleted - ScyllaDB + PostgreSQL cleanup.

        ASYNC PROJECTION: Runs in EventProcessor worker (eventual consistency).
        Better for performance - doesn't block HTTP response.

        Order:
            1. ScyllaDB - delete ALL message data (messages, reactions, pins, etc.)
            2. PostgreSQL - delete chat metadata (CASCADE handles participants)

        This ensures complete cleanup when a chat is hard deleted via GroupDeletionSaga.
        """
        chat_id = envelope.aggregate_id
        log.info(f"Projecting ChatHardDeleted: chat_id={chat_id}")

        # -----------------------------------------------------------------
        # 1. ScyllaDB - delete ALL channel data (messages, reactions, etc.)
        # -----------------------------------------------------------------
        try:
            scylla_result = await self.message_scylla_repo.delete_all_channel_data(chat_id)
            log.info(
                f"ScyllaDB cleanup complete for chat {chat_id}: "
                f"messages={scylla_result.get('messages', 0)}, "
                f"reactions={scylla_result.get('reactions', 0)}, "
                f"pinned={scylla_result.get('pinned', 0)}, "
                f"read_positions={scylla_result.get('read_positions', 0)}, "
                f"telegram_mappings={scylla_result.get('telegram_mappings', 0)}"
            )
        except Exception as e:
            log.error(f"ScyllaDB cleanup failed for chat {chat_id}: {e}", exc_info=True)
            raise  # Fail loudly - don't leave orphaned data

        # -----------------------------------------------------------------
        # 2. PostgreSQL - delete chat metadata (CASCADE handles participants)
        # -----------------------------------------------------------------
        await self.chat_read_repo.hard_delete_chat(chat_id=chat_id)

    # =========================================================================
    # Participant Projections (PostgreSQL)
    # =========================================================================

    # ASYNC: Optimistic UI + WSE notification
    @async_projection("ParticipantAdded")
    @monitor_projection
    async def on_participant_added(self, envelope: EventEnvelope) -> None:
        """Project ParticipantAdded to PostgreSQL. ASYNC - optimistic UI."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantAdded: chat={chat_id}, user={user_id}")

        try:
            await self.chat_read_repo.insert_participant(
                chat_id=chat_id,
                user_id=user_id,
                role=event_data.get('role', 'member'),
                joined_at=datetime.fromisoformat(event_data['joined_at']) if event_data.get('joined_at') else envelope.stored_at,
            )
            await self.chat_read_repo.increment_participant_count(chat_id)
        except Exception as e:
            if 'foreign key' in str(e).lower():
                raise RetriableProjectionError(f"Chat {chat_id} not yet projected") from e
            raise

    @async_projection("ParticipantRemoved")
    @monitor_projection
    async def on_participant_removed(self, envelope: EventEnvelope) -> None:
        """Project ParticipantRemoved to PostgreSQL. ASYNC."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantRemoved: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.deactivate_participant(chat_id=chat_id, user_id=user_id)
        await self.chat_read_repo.decrement_participant_count(chat_id)

    @async_projection("ParticipantRoleChanged")
    @monitor_projection
    async def on_participant_role_changed(self, envelope: EventEnvelope) -> None:
        """Project ParticipantRoleChanged to PostgreSQL. ASYNC."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantRoleChanged: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.update_participant_role(
            chat_id=chat_id,
            user_id=user_id,
            role=event_data['new_role'],
        )

    @async_projection("ParticipantLeft")
    @monitor_projection
    async def on_participant_left(self, envelope: EventEnvelope) -> None:
        """Project ParticipantLeft to PostgreSQL. ASYNC."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id
        user_id = uuid.UUID(event_data['user_id'])

        log.info(f"Projecting ParticipantLeft: chat={chat_id}, user={user_id}")

        await self.chat_read_repo.deactivate_participant(chat_id=chat_id, user_id=user_id)
        await self.chat_read_repo.decrement_participant_count(chat_id)

    # =========================================================================
    # Message Projections (ScyllaDB PRIMARY)
    # =========================================================================

    # ASYNC: Optimistic UI shows message immediately, Worker confirms
    @async_projection("MessageSent")
    @monitor_projection
    async def on_message_sent(self, envelope: EventEnvelope) -> None:
        """
        Project MessageSent - ScyllaDB PRIMARY.

        ASYNC: Frontend uses optimistic UI, WSE confirms delivery.

        Flow:
            1. Write message content to ScyllaDB (primary storage)
            2. Update PostgreSQL chat.last_message_* (metadata preview)
        """
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        sender_id = uuid.UUID(event_data['sender_id']) if event_data.get('sender_id') else None
        source = event_data.get('source', 'web')

        # IDEMPOTENCY: Convert event's message_id UUID to deterministic Snowflake ID
        # This ensures both API server and Worker produce the same message_id
        message_uuid = uuid.UUID(event_data['message_id'])
        # Use first 8 bytes of UUID as int64, ensure positive
        deterministic_snowflake = int.from_bytes(message_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF

        log.info(f"Projecting MessageSent to ScyllaDB: chat_id={chat_id}, snowflake={deterministic_snowflake}")

        # -----------------------------------------------------------------
        # 1. ScyllaDB - PRIMARY message storage (IDEMPOTENT)
        # -----------------------------------------------------------------
        message = MessageData(
            channel_id=chat_id,
            message_id=deterministic_snowflake,  # Use deterministic ID for idempotency
            sender_id=sender_id,
            content=event_data['content'],
            message_type=MessageType(event_data.get('message_type', 'text')),
            source=MessageSource(source),
            reply_to_id=event_data.get('reply_to_snowflake_id'),
            file_url=event_data.get('file_url'),
            file_name=event_data.get('file_name'),
            file_size=event_data.get('file_size'),
            file_type=event_data.get('file_type'),
            voice_duration=event_data.get('voice_duration'),
            telegram_message_id=event_data.get('telegram_message_id'),
            telegram_chat_id=event_data.get('telegram_chat_id'),
            telegram_user_id=event_data.get('telegram_user_id'),
            telegram_user_data=json.dumps(event_data['telegram_user_data']) if event_data.get('telegram_user_data') else None,
            telegram_forward_data=json.dumps(event_data['telegram_forward_data']) if event_data.get('telegram_forward_data') else None,
            telegram_topic_id=event_data.get('telegram_topic_id'),
            sync_direction=SyncDirection.TELEGRAM_TO_WEB if source == 'telegram' else None,
            created_at=envelope.stored_at,
        )

        snowflake_id = await self.message_scylla_repo.insert_message(message)
        log.debug(f"ScyllaDB insert SUCCESS: snowflake_id={snowflake_id}")

        # -----------------------------------------------------------------
        # 2. PostgreSQL - metadata update (last message preview)
        # -----------------------------------------------------------------
        try:
            await self.chat_read_repo.update_chat_last_message(
                chat_id=chat_id,
                last_message_at=envelope.stored_at,
                last_message_content=event_data['content'][:100],
                last_message_sender_id=sender_id,
            )
        except Exception as e:
            if 'foreign key' in str(e).lower():
                raise RetriableProjectionError(f"Chat {chat_id} not yet projected") from e
            raise

    @async_projection("MessageEdited")
    @monitor_projection
    async def on_message_edited(self, envelope: EventEnvelope) -> None:
        """Project MessageEdited - ScyllaDB PRIMARY. ASYNC."""
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])

        # Get snowflake_id from event or compute from message_id UUID
        snowflake_id = event_data.get('snowflake_id')
        if not snowflake_id and event_data.get('message_id'):
            # Compute deterministic snowflake from message_id (same logic as MessageSent)
            message_uuid = uuid.UUID(event_data['message_id'])
            snowflake_id = int.from_bytes(message_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF

        if not snowflake_id:
            log.warning(f"MessageEdited missing both snowflake_id and message_id, skipping ScyllaDB update")
            return

        log.info(f"Projecting MessageEdited to ScyllaDB: snowflake_id={snowflake_id}")

        await self.message_scylla_repo.update_message_content(
            channel_id=chat_id,
            message_id=snowflake_id,
            new_content=event_data['new_content'],
        )

    @async_projection("MessageDeleted")
    @monitor_projection
    async def on_message_deleted(self, envelope: EventEnvelope) -> None:
        """Project MessageDeleted - ScyllaDB PRIMARY. ASYNC."""
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])

        # Get snowflake_id from event or compute from message_id UUID
        snowflake_id = event_data.get('snowflake_id')
        if not snowflake_id and event_data.get('message_id'):
            # Compute deterministic snowflake from message_id (same logic as MessageSent)
            message_uuid = uuid.UUID(event_data['message_id'])
            snowflake_id = int.from_bytes(message_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF

        if not snowflake_id:
            log.warning(f"MessageDeleted missing both snowflake_id and message_id, skipping ScyllaDB update")
            return

        log.info(f"Projecting MessageDeleted to ScyllaDB: snowflake_id={snowflake_id}")

        await self.message_scylla_repo.soft_delete_message(
            channel_id=chat_id,
            message_id=snowflake_id,
        )

    # =========================================================================
    # Read Status Projections (ScyllaDB)
    # =========================================================================

    @async_projection("MessagesMarkedAsRead")
    @monitor_projection
    async def on_messages_marked_as_read(self, envelope: EventEnvelope) -> None:
        """Project MessagesMarkedAsRead - ScyllaDB + PostgreSQL. ASYNC."""
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        user_id = uuid.UUID(event_data['user_id'])
        # last_read_message_id is now Snowflake ID (int)
        last_read_message_id = event_data.get('last_read_message_id')

        log.debug(f"Projecting MessagesMarkedAsRead: chat={chat_id}, user={user_id}, snowflake={last_read_message_id}")

        # ScyllaDB - read position (Snowflake ID)
        if last_read_message_id:
            await self.message_scylla_repo.update_read_position(
                channel_id=chat_id,
                user_id=user_id,
                last_read_message_id=last_read_message_id,
            )

        # PostgreSQL - participant last_read_at (store Snowflake as bigint)
        await self.chat_read_repo.update_participant_last_read(
            chat_id=chat_id,
            user_id=user_id,
            last_read_message_id=last_read_message_id,
            last_read_at=envelope.stored_at,
        )

    # =========================================================================
    # Telegram Delivery Confirmation (Bidirectional Read Receipts)
    # =========================================================================

    @async_projection("MessageSyncedToTelegram")
    @monitor_projection
    async def on_message_synced_to_telegram(self, envelope: EventEnvelope) -> None:
        """
        Project MessageSyncedToTelegram - ScyllaDB delivery confirmation.

        ASYNC: Updates message with Telegram delivery confirmation.

        This enables bidirectional delivery tracking:
        - Single checkmark: Message sent to WellWon server
        - Double checkmark: Message delivered to Telegram (this event)
        - Blue double checkmark: Message read on Telegram (MessagesMarkedAsRead)
        """
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        message_uuid = uuid.UUID(event_data['message_id'])
        telegram_message_id = event_data['telegram_message_id']
        telegram_chat_id = event_data['telegram_chat_id']

        # Compute deterministic snowflake from message_id (same logic as MessageSent)
        snowflake_id = int.from_bytes(message_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF

        log.info(
            f"Projecting MessageSyncedToTelegram: chat_id={chat_id}, "
            f"snowflake={snowflake_id}, telegram_message_id={telegram_message_id}"
        )

        # Update ScyllaDB message with Telegram delivery info
        await self.message_scylla_repo.update_message_telegram_sync(
            channel_id=chat_id,
            message_id=snowflake_id,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
            sync_direction=SyncDirection.WEB_TO_TELEGRAM,
        )

    @async_projection("MessagesReadOnTelegram")
    @monitor_projection
    async def on_messages_read_on_telegram(self, envelope: EventEnvelope) -> None:
        """
        Project MessagesReadOnTelegram - Blue checkmarks.

        When recipient reads messages on Telegram, update telegram_read_at
        to trigger blue checkmarks on frontend.
        """
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        last_read_message_id = uuid.UUID(event_data['last_read_message_id'])
        telegram_read_at = event_data.get('telegram_read_at')

        log.info(
            f"Projecting MessagesReadOnTelegram: chat={chat_id}, "
            f"last_read_message_id={last_read_message_id}, "
            f"telegram_read_at={telegram_read_at}"
        )

        # Update ScyllaDB - set telegram_read_at on messages up to last_read_message_id
        try:
            await self.message_scylla_repo.update_telegram_read_status(
                channel_id=chat_id,
                last_read_message_id=last_read_message_id,
                telegram_read_at=telegram_read_at,
            )
        except Exception as e:
            log.warning(f"Failed to update telegram_read_at in ScyllaDB: {e}")

    # =========================================================================
    # Company Link Projections (no read model changes needed)
    # =========================================================================

    @async_projection("ChatLinkedToCompany")
    async def on_chat_linked_to_company(self, envelope: EventEnvelope) -> None:
        """Acknowledge ChatLinkedToCompany - company link tracked on company side."""
        chat_id = envelope.aggregate_id
        company_id = envelope.event_data.get('company_id')
        log.debug(f"ChatLinkedToCompany acknowledged: chat={chat_id}, company={company_id}")

    @async_projection("ChatUnlinkedFromCompany")
    async def on_chat_unlinked_from_company(self, envelope: EventEnvelope) -> None:
        """Acknowledge ChatUnlinkedFromCompany - company link tracked on company side."""
        chat_id = envelope.aggregate_id
        log.debug(f"ChatUnlinkedFromCompany acknowledged: chat={chat_id}")

    # =========================================================================
    # Ephemeral Events (UI-only, no persistence needed)
    # =========================================================================

    @async_projection("TypingStarted")
    async def on_typing_started(self, envelope: EventEnvelope) -> None:
        """Acknowledge TypingStarted - ephemeral UI event, no persistence."""
        pass

    @async_projection("TypingStopped")
    async def on_typing_stopped(self, envelope: EventEnvelope) -> None:
        """Acknowledge TypingStopped - ephemeral UI event, no persistence."""
        pass

    @async_projection("MessageReadStatusUpdated")
    async def on_message_read_status_updated(self, envelope: EventEnvelope) -> None:
        """Acknowledge MessageReadStatusUpdated - handled by MessagesMarkedAsRead."""
        pass

    # =========================================================================
    # Telegram Integration Projections
    # =========================================================================

    @async_projection("TelegramChatLinked")
    @monitor_projection
    async def on_telegram_chat_linked(self, envelope: EventEnvelope) -> None:
        """Project TelegramChatLinked - PostgreSQL + ScyllaDB. ASYNC."""
        event_data = envelope.event_data
        chat_id = envelope.aggregate_id

        log.info(f"Projecting TelegramChatLinked: chat={chat_id}")

        # PostgreSQL - chat metadata
        await self.chat_read_repo.update_chat_telegram(
            chat_id=chat_id,
            telegram_chat_id=event_data['telegram_chat_id'],
            telegram_topic_id=event_data.get('telegram_topic_id'),
        )

        # ScyllaDB - sync state
        await self.message_scylla_repo.update_telegram_sync_state(
            channel_id=chat_id,
            telegram_chat_id=event_data['telegram_chat_id'],
            telegram_topic_id=event_data.get('telegram_topic_id'),
            sync_enabled=True,
        )

    @async_projection("TelegramChatUnlinked")
    @monitor_projection
    async def on_telegram_chat_unlinked(self, envelope: EventEnvelope) -> None:
        """Project TelegramChatUnlinked - PostgreSQL + ScyllaDB. ASYNC."""
        chat_id = envelope.aggregate_id

        log.info(f"Projecting TelegramChatUnlinked: chat={chat_id}")

        # PostgreSQL
        await self.chat_read_repo.update_chat_telegram(
            chat_id=chat_id,
            telegram_chat_id=None,
            telegram_topic_id=None,
        )

        # ScyllaDB - disable sync
        await self.message_scylla_repo.update_telegram_sync_state(
            channel_id=chat_id,
            telegram_chat_id=None,
            telegram_topic_id=None,
            sync_enabled=False,
        )

    # SYNC: User expects immediate Telegram message visibility
    @sync_projection("TelegramMessageReceived")
    @monitor_projection
    async def on_telegram_message_received(self, envelope: EventEnvelope) -> None:
        """
        Project TelegramMessageReceived - ScyllaDB PRIMARY.

        SYNC: User expects immediate Telegram message visibility in chat.
        """
        event_data = envelope.event_data
        chat_id = uuid.UUID(event_data['chat_id'])
        telegram_message_id = event_data['telegram_message_id']
        telegram_chat_id = event_data.get('telegram_chat_id', 0)

        # IDEMPOTENCY: Create deterministic Snowflake ID from Telegram IDs
        # Combine telegram_chat_id (high bits) + telegram_message_id (low bits)
        # This ensures both API server and Worker produce the same message_id
        deterministic_snowflake = ((abs(telegram_chat_id) & 0xFFFFFFFF) << 31) | (telegram_message_id & 0x7FFFFFFF)

        log.info(f"Projecting TelegramMessageReceived to ScyllaDB: chat_id={chat_id}, snowflake={deterministic_snowflake}")

        # -----------------------------------------------------------------
        # 1. ScyllaDB - PRIMARY message storage (IDEMPOTENT)
        # -----------------------------------------------------------------
        message = MessageData(
            channel_id=chat_id,
            message_id=deterministic_snowflake,  # Use deterministic ID for idempotency
            sender_id=None,  # No mapped WellWon user
            content=event_data['content'],
            message_type=MessageType(event_data.get('message_type', 'text')),
            source=MessageSource.TELEGRAM,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
            telegram_user_id=event_data.get('telegram_user_id'),
            telegram_user_data=event_data.get('telegram_user_data'),
            telegram_forward_data=event_data.get('telegram_forward_data'),
            telegram_topic_id=event_data.get('telegram_topic_id'),
            sync_direction=SyncDirection.TELEGRAM_TO_WEB,
            created_at=envelope.stored_at,
        )

        snowflake_id = await self.message_scylla_repo.insert_message(message)
        log.debug(f"ScyllaDB Telegram insert SUCCESS: snowflake_id={snowflake_id}")

        # -----------------------------------------------------------------
        # 2. PostgreSQL - metadata update
        # -----------------------------------------------------------------
        try:
            await self.chat_read_repo.update_chat_last_message(
                chat_id=chat_id,
                last_message_at=envelope.stored_at,
                last_message_content=event_data['content'][:100],
                last_message_sender_id=None,
            )
        except Exception as e:
            if 'foreign key' in str(e).lower():
                raise RetriableProjectionError(f"Chat {chat_id} not yet projected") from e
            raise
