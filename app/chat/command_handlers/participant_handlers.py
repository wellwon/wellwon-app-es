# =============================================================================
# File: app/chat/command_handlers/participant_handlers.py
# Description: Command handlers for participant operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

from app.chat.commands import (
    AddParticipantCommand,
    RemoveParticipantCommand,
    ChangeParticipantRoleCommand,
    LeaveChatCommand,
)
from app.chat.aggregate import ChatAggregate
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.chat.handlers.participant")


@command_handler(AddParticipantCommand)
class AddParticipantHandler(BaseCommandHandler):
    """Handle AddParticipantCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: AddParticipantCommand) -> uuid.UUID:
        log.info(f"Adding participant {command.user_id} to chat {command.chat_id}")

        # Load aggregate
        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # Add participant
        chat_aggregate.add_participant(
            user_id=command.user_id,
            role=command.role,
            added_by=command.added_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Participant added: {command.user_id} to chat {command.chat_id}")
        return command.chat_id


@command_handler(RemoveParticipantCommand)
class RemoveParticipantHandler(BaseCommandHandler):
    """Handle RemoveParticipantCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: RemoveParticipantCommand) -> uuid.UUID:
        log.info(f"Removing participant {command.user_id} from chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.remove_participant(
            user_id=command.user_id,
            removed_by=command.removed_by,
            reason=command.reason,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Participant removed: {command.user_id} from chat {command.chat_id}")
        return command.chat_id


@command_handler(ChangeParticipantRoleCommand)
class ChangeParticipantRoleHandler(BaseCommandHandler):
    """Handle ChangeParticipantRoleCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: ChangeParticipantRoleCommand) -> uuid.UUID:
        log.info(f"Changing role for {command.user_id} in chat {command.chat_id} to {command.new_role}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.change_participant_role(
            user_id=command.user_id,
            new_role=command.new_role,
            changed_by=command.changed_by,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Role changed for {command.user_id} in chat {command.chat_id}")
        return command.chat_id


@command_handler(LeaveChatCommand)
class LeaveChatHandler(BaseCommandHandler):
    """Handle LeaveChatCommand"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LeaveChatCommand) -> uuid.UUID:
        log.info(f"User {command.user_id} leaving chat {command.chat_id}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.leave_chat(user_id=command.user_id)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"User {command.user_id} left chat {command.chat_id}")
        return command.chat_id
