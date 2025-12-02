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

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

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

        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

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

    async def handle(self, command: ProcessTelegramMessageCommand) -> uuid.UUID:
        log.debug(f"Processing Telegram message {command.telegram_message_id} for chat {command.chat_id}")

        # Load aggregate from event store (proper Event Sourcing)
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # If aggregate has no state (no events), this is an unmigrated chat
        if not chat_aggregate.state.is_active and chat_aggregate.version == 0:
            log.warning(f"Chat {command.chat_id} has no events in Event Store. Run migration first.")
            raise ValueError(f"Chat {command.chat_id} not found in Event Store. Migration required.")

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

        # Publish events via standard Event Sourcing flow
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
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

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
            telegram_supergroup_id=command.telegram_supergroup_id,  # For frontend filtering
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
