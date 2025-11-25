# =============================================================================
# File: app/chat/command_handlers/message_handlers.py
# Description: Command handlers for message operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

from app.chat.commands import (
    SendMessageCommand,
    EditMessageCommand,
    DeleteMessageCommand,
    MarkMessageAsReadCommand,
    MarkMessagesAsReadCommand,
    StartTypingCommand,
    StopTypingCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.events import TypingStarted, TypingStopped
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.chat.handlers.message")


@command_handler(SendMessageCommand)
class SendMessageHandler(BaseCommandHandler):
    """Handle SendMessageCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: SendMessageCommand) -> uuid.UUID:
        log.info(f"Sending message to chat {command.chat_id} from {command.sender_id}")

        # Load aggregate
        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # Send message
        chat_aggregate.send_message(
            message_id=command.message_id,
            sender_id=command.sender_id,
            content=command.content,
            message_type=command.message_type,
            reply_to_id=command.reply_to_id,
            file_url=command.file_url,
            file_name=command.file_name,
            file_size=command.file_size,
            file_type=command.file_type,
            voice_duration=command.voice_duration,
            source=command.source,
            telegram_message_id=command.telegram_message_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Message sent: {command.message_id} to chat {command.chat_id}")
        return command.message_id


@command_handler(EditMessageCommand)
class EditMessageHandler(BaseCommandHandler):
    """Handle EditMessageCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: EditMessageCommand) -> uuid.UUID:
        log.info(f"Editing message {command.message_id} in chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.edit_message(
            message_id=command.message_id,
            edited_by=command.edited_by,
            new_content=command.new_content,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Message edited: {command.message_id}")
        return command.message_id


@command_handler(DeleteMessageCommand)
class DeleteMessageHandler(BaseCommandHandler):
    """Handle DeleteMessageCommand (soft delete)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteMessageCommand) -> uuid.UUID:
        log.info(f"Deleting message {command.message_id} in chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.delete_message(
            message_id=command.message_id,
            deleted_by=command.deleted_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Message deleted: {command.message_id}")
        return command.message_id


@command_handler(MarkMessageAsReadCommand)
class MarkMessageAsReadHandler(BaseCommandHandler):
    """Handle MarkMessageAsReadCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: MarkMessageAsReadCommand) -> uuid.UUID:
        log.debug(f"Marking message {command.message_id} as read by {command.user_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.mark_message_as_read(
            message_id=command.message_id,
            user_id=command.user_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        return command.message_id


@command_handler(MarkMessagesAsReadCommand)
class MarkMessagesAsReadHandler(BaseCommandHandler):
    """Handle MarkMessagesAsReadCommand (batch read)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: MarkMessagesAsReadCommand) -> uuid.UUID:
        log.debug(f"Marking messages as read in chat {command.chat_id} by {command.user_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # TODO: Get actual count from read model
        # For now, use 0 as placeholder - projector will calculate actual count
        read_count = 0

        chat_aggregate.mark_messages_as_read(
            user_id=command.user_id,
            last_read_message_id=command.last_read_message_id,
            read_count=read_count,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        return command.last_read_message_id


@command_handler(StartTypingCommand)
class StartTypingHandler(BaseCommandHandler):
    """
    Handle StartTypingCommand.

    Note: Typing events are ephemeral and NOT stored in event store.
    They are only published to the transport for real-time delivery.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=None  # Don't store ephemeral events
        )

    async def handle(self, command: StartTypingCommand) -> uuid.UUID:
        log.debug(f"User {command.user_id} started typing in chat {command.chat_id}")

        # Create ephemeral event (not stored)
        event = TypingStarted(
            chat_id=command.chat_id,
            user_id=command.user_id,
        )

        # Publish directly to transport (no event store)
        await self.event_bus.publish(event, topic=self.transport_topic)

        return command.chat_id


@command_handler(StopTypingCommand)
class StopTypingHandler(BaseCommandHandler):
    """Handle StopTypingCommand (ephemeral)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=None  # Don't store ephemeral events
        )

    async def handle(self, command: StopTypingCommand) -> uuid.UUID:
        log.debug(f"User {command.user_id} stopped typing in chat {command.chat_id}")

        event = TypingStopped(
            chat_id=command.chat_id,
            user_id=command.user_id,
        )

        await self.event_bus.publish(event, topic=self.transport_topic)

        return command.chat_id
