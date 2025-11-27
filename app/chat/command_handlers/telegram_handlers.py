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
        log.info(
            f"Processing Telegram message {command.telegram_message_id} "
            f"from user {command.telegram_user_id} in chat {command.chat_id}"
        )

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

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
        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Telegram message processed: {command.message_id}")
        return command.message_id
