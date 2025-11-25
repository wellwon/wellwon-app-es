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
    UnlinkTelegramChatCommand,
    ProcessTelegramMessageCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.events import TelegramMessageReceived
from app.infra.cqrs.decorators import command_handler
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

        events = await self.event_store.get_events(command.chat_id, "chat")
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

        events = await self.event_store.get_events(command.chat_id, "chat")
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
    It creates a MessageSent event (via aggregate) or TelegramMessageReceived
    if the sender cannot be mapped to a WellWon user.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ProcessTelegramMessageCommand) -> uuid.UUID:
        log.info(
            f"Processing Telegram message {command.telegram_message_id} "
            f"from user {command.telegram_user_id} in chat {command.chat_id}"
        )

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        if command.sender_id:
            # Mapped WellWon user - use regular message flow
            chat_aggregate.send_message(
                message_id=command.message_id,
                sender_id=command.sender_id,
                content=command.content,
                message_type=command.message_type,
                file_url=command.file_url,
                file_name=command.file_name,
                source="telegram",
                telegram_message_id=command.telegram_message_id,
            )

            await self.publish_events(
                aggregate=chat_aggregate,
                aggregate_id=command.chat_id,
                command=command
            )
        else:
            # Unknown Telegram user - emit special event
            event = TelegramMessageReceived(
                message_id=command.message_id,
                chat_id=command.chat_id,
                telegram_message_id=command.telegram_message_id,
                telegram_user_id=command.telegram_user_id,
                sender_id=None,
                content=command.content,
                message_type=command.message_type,
                file_url=command.file_url,
                file_name=command.file_name,
            )

            # Store event and publish
            await self.event_store.append_events(
                aggregate_id=command.chat_id,
                aggregate_type="chat",
                events=[event],
                expected_version=chat_aggregate.version,
            )
            await self.event_bus.publish(event, topic=self.transport_topic)

        log.info(f"Telegram message processed: {command.message_id}")
        return command.message_id
