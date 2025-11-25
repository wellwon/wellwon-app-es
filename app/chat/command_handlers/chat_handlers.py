# =============================================================================
# File: app/chat/command_handlers/chat_handlers.py
# Description: Command handlers for chat lifecycle operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING, List

from app.chat.commands import (
    CreateChatCommand,
    UpdateChatCommand,
    ArchiveChatCommand,
    RestoreChatCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.enums import ParticipantRole
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.chat.handlers.chat")


@command_handler(CreateChatCommand)
class CreateChatHandler(BaseCommandHandler):
    """
    Handle CreateChatCommand using Event Sourcing.

    Creates a new chat and optionally adds initial participants.
    The creator is automatically added as admin.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: CreateChatCommand) -> uuid.UUID:
        log.info(f"Creating {command.chat_type} chat by user {command.created_by}")

        # Create new aggregate
        chat_aggregate = ChatAggregate(chat_id=command.chat_id)

        # Create the chat
        chat_aggregate.create_chat(
            name=command.name,
            chat_type=command.chat_type,
            created_by=command.created_by,
            company_id=command.company_id,
            telegram_chat_id=command.telegram_chat_id,
            telegram_topic_id=command.telegram_topic_id,
        )

        # Add creator as admin
        chat_aggregate.add_participant(
            user_id=command.created_by,
            role=ParticipantRole.ADMIN.value,
            added_by=command.created_by,
        )

        # Add other participants as members
        for participant_id in command.participant_ids:
            if participant_id != command.created_by:
                chat_aggregate.add_participant(
                    user_id=participant_id,
                    role=ParticipantRole.MEMBER.value,
                    added_by=command.created_by,
                )

        # Publish all events
        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat created: {command.chat_id} with {len(command.participant_ids) + 1} participants")
        return command.chat_id


@command_handler(UpdateChatCommand)
class UpdateChatHandler(BaseCommandHandler):
    """Handle UpdateChatCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateChatCommand) -> uuid.UUID:
        log.info(f"Updating chat {command.chat_id}")

        # Load aggregate from event store
        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # Update chat
        chat_aggregate.update_chat(
            name=command.name,
            updated_by=command.updated_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat updated: {command.chat_id}")
        return command.chat_id


@command_handler(ArchiveChatCommand)
class ArchiveChatHandler(BaseCommandHandler):
    """Handle ArchiveChatCommand (soft delete)"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ArchiveChatCommand) -> uuid.UUID:
        log.info(f"Archiving chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.archive_chat(archived_by=command.archived_by)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat archived: {command.chat_id}")
        return command.chat_id


@command_handler(RestoreChatCommand)
class RestoreChatHandler(BaseCommandHandler):
    """Handle RestoreChatCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: RestoreChatCommand) -> uuid.UUID:
        log.info(f"Restoring chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.restore_chat(restored_by=command.restored_by)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat restored: {command.chat_id}")
        return command.chat_id
