# =============================================================================
# File: app/chat/command_handlers/telegram_handlers.py
# Description: Command handlers for Telegram integration
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

from app.chat.commands import (
    LinkTelegramChatCommand,
    LinkChatToTelegramCommand,
    UnlinkTelegramChatCommand,
    ProcessTelegramMessageCommand,
)
from app.chat.aggregate import ChatAggregate
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.chat.handlers.telegram")


@command_handler(LinkTelegramChatCommand)
class LinkTelegramChatHandler(BaseCommandHandler):
    """Handle LinkTelegramChatCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LinkTelegramChatCommand) -> uuid.UUID:
        log.info(f"Linking Telegram chat {command.telegram_chat_id} to chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.link_telegram_chat(
            telegram_chat_id=command.telegram_chat_id,
            telegram_topic_id=command.telegram_topic_id,
            linked_by=command.linked_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Telegram chat {command.telegram_chat_id} linked to {command.chat_id}")
        return command.chat_id


@command_handler(UnlinkTelegramChatCommand)
class UnlinkTelegramChatHandler(BaseCommandHandler):
    """Handle UnlinkTelegramChatCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UnlinkTelegramChatCommand) -> uuid.UUID:
        log.info(f"Unlinking Telegram chat from {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.unlink_telegram_chat(unlinked_by=command.unlinked_by)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Telegram chat unlinked from {command.chat_id}")
        return command.chat_id


@command_handler(ProcessTelegramMessageCommand)
class ProcessTelegramMessageHandler(BaseCommandHandler):
    """
    Handle ProcessTelegramMessageCommand.

    This handler processes incoming messages from Telegram webhook.
    ALL messages go through the ChatAggregate to maintain DDD integrity.

    For mapped WellWon users: uses send_message() (requires participant check)
    For external Telegram users: uses receive_external_message() (no participant check)
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self._chat_read_repo = None

    async def _bootstrap_aggregate_from_read_model(
        self,
        aggregate: ChatAggregate,
        chat_id: uuid.UUID
    ) -> None:
        """
        Bootstrap aggregate state from read model for legacy/migrated chats.

        This creates a ChatCreated event to properly initialize the aggregate state.
        This event will be stored in Event Store so subsequent replays work correctly.

        This is a migration support feature for chats that were created
        before Event Sourcing was implemented.
        """
        try:
            from app.infra.read_repos.chat_read_repo import ChatReadRepo
            chat = await ChatReadRepo.get_chat_by_id(chat_id)

            if chat:
                log.info(
                    f"Bootstrapping aggregate from read model: {chat_id}, "
                    f"name={chat.name}, type={chat.chat_type}, "
                    f"telegram_chat_id={chat.telegram_chat_id}, telegram_topic_id={chat.telegram_topic_id}"
                )
                # Create the chat event to establish proper aggregate state
                # This will be stored in Event Store for future replays
                aggregate.create_chat(
                    name=chat.name,
                    chat_type=chat.chat_type,
                    created_by=chat.created_by,
                    company_id=chat.company_id,
                    telegram_chat_id=chat.telegram_chat_id,
                    telegram_topic_id=chat.telegram_topic_id,
                )
                log.info(f"Created ChatCreated event for bootstrapped chat: {chat_id}, state.telegram_chat_id={aggregate.state.telegram_chat_id}")
        except Exception as e:
            log.warning(f"Failed to bootstrap aggregate from read model: {e}")

    async def handle(self, command: ProcessTelegramMessageCommand) -> uuid.UUID:
        log.error(
            f"=== ProcessTelegramMessageHandler START === "
            f"msg_id={command.telegram_message_id} chat_id={command.chat_id}"
        )

        events = await self.event_store.get_events(command.chat_id, "Chat")
        log.error(f"EVENTS: Got {len(events)} events from event store for chat {command.chat_id}")

        if events:
            for i, e in enumerate(events):
                # Log event details including telegram_chat_id if present
                event_data = e.event_data if hasattr(e, 'event_data') else {}
                tg_chat_id = event_data.get('telegram_chat_id', 'N/A') if isinstance(event_data, dict) else 'N/A'
                log.info(f"  Event {i}: type={e.event_type}, telegram_chat_id={tg_chat_id}")
        else:
            log.info("  No events found - will bootstrap from read model")

        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)
        log.info(
            f"AGGREGATE STATE after replay: "
            f"version={chat_aggregate.version}, "
            f"is_active={chat_aggregate.state.is_active}, "
            f"telegram_chat_id={chat_aggregate.state.telegram_chat_id}, "
            f"telegram_topic_id={chat_aggregate.state.telegram_topic_id}"
        )

        # Track if this is a bootstrapped aggregate (no event history)
        is_bootstrapped = not events

        # MIGRATION SUPPORT: If no events exist, check if chat exists in read model
        # and bootstrap the aggregate state from it
        if is_bootstrapped:
            await self._bootstrap_aggregate_from_read_model(chat_aggregate, command.chat_id)

        if command.sender_id:
            # Mapped WellWon user - use regular message flow (requires participant)
            chat_aggregate.send_message(
                message_id=command.message_id,
                sender_id=command.sender_id,
                content=command.content,
                message_type=command.message_type,
                file_url=command.file_url,
                file_name=command.file_name,
                file_size=command.file_size,
                file_type=command.file_type,
                voice_duration=command.voice_duration,
                source="telegram",
                telegram_message_id=command.telegram_message_id,
                telegram_user_id=command.telegram_user_id,
                telegram_user_data=command.telegram_user_data,
                telegram_forward_data=command.telegram_forward_data,
                telegram_topic_id=command.telegram_topic_id,
            )
        else:
            # External Telegram user - use receive_external_message (no participant check)
            # This is for new clients contacting via general topic
            chat_aggregate.receive_external_message(
                message_id=command.message_id,
                content=command.content,
                message_type=command.message_type,
                source="telegram",
                telegram_message_id=command.telegram_message_id,
                telegram_user_id=command.telegram_user_id,
                telegram_user_data=command.telegram_user_data,
                telegram_forward_data=command.telegram_forward_data,
                telegram_topic_id=command.telegram_topic_id,
                file_url=command.file_url,
                file_name=command.file_name,
                file_size=command.file_size,
                file_type=command.file_type,
                voice_duration=command.voice_duration,
            )

        # Both paths go through aggregate - publish events uniformly
        # For bootstrapped aggregates, use expected_version=None (new stream)
        if is_bootstrapped:
            # Bootstrapped from read model - create new event stream
            await self.publish_and_commit_events(
                aggregate=chat_aggregate,
                aggregate_type="Chat",
                expected_version=None,  # New stream
            )
        else:
            # Normal flow - use version tracking
            await self.publish_events(
                aggregate=chat_aggregate,
                aggregate_id=command.chat_id,
                command=command
            )

        log.info(f"Telegram message processed: {command.message_id}")
        return command.message_id


@command_handler(LinkChatToTelegramCommand)
class LinkChatToTelegramHandler(BaseCommandHandler):
    """
    Handle LinkChatToTelegramCommand.

    Used by GroupCreationSaga to link an existing chat to Telegram.
    Creates a Telegram topic in the supergroup and updates the chat.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter = deps.telegram_adapter

    async def handle(self, command: LinkChatToTelegramCommand) -> uuid.UUID:
        log.info(
            f"Linking chat {command.chat_id} to Telegram supergroup {command.telegram_supergroup_id}"
        )

        # Load chat aggregate
        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        if not chat_aggregate.state.is_active:
            raise ValueError(f"Chat {command.chat_id} is not active")

        # Create Telegram topic for this chat
        chat_name = chat_aggregate.state.name or "Чат компании"
        telegram_topic_id = None

        log.info(f"Creating Telegram topic '{chat_name}' in supergroup {command.telegram_supergroup_id}")

        try:
            if not self.telegram_adapter:
                log.warning("TelegramAdapter not available, skipping topic creation")
            else:
                # Use TelegramAdapter.create_chat_topic() which returns TopicInfo
                topic_info = await self.telegram_adapter.create_chat_topic(
                    group_id=command.telegram_supergroup_id,
                    topic_name=chat_name,
                    emoji="📝",  # Default emoji for chat topics
                )

                if topic_info:
                    telegram_topic_id = topic_info.topic_id
                    log.info(f"Telegram topic created: id={telegram_topic_id}, name={chat_name}")
                else:
                    log.warning("Topic creation returned no info, continuing without topic")

        except Exception as e:
            # IMPORTANT: Don't fail the command - still link the chat to supergroup
            # This allows chats to be associated with the group even if topic creation fails
            # (e.g., when Telegram Premium is required for topic creation)
            log.warning(f"Failed to create Telegram topic, continuing without topic: {e}")

        # Update chat aggregate with Telegram info (supergroup_id is always set)
        chat_aggregate.link_telegram_chat(
            telegram_chat_id=command.telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,  # May be None if topic creation failed
            linked_by=command.linked_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(
            f"Chat {command.chat_id} linked to Telegram: "
            f"supergroup={command.telegram_supergroup_id}, topic={telegram_topic_id}"
        )
        return command.chat_id
