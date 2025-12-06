# =============================================================================
# File: app/chat/command_handlers/invitation_handlers.py
# Description: Command handlers for client invitation to Telegram groups
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING, Optional

from app.chat.commands import InviteClientCommand
from app.chat.aggregate import ChatAggregate
from app.chat.events import ClientInvited, ClientInvitationFailed
from app.chat.value_objects import TelegramContact
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.telegram.adapter import TelegramAdapter

log = logging.getLogger("wellwon.chat.handlers.invitation")


@command_handler(InviteClientCommand)
class InviteClientHandler(BaseCommandHandler):
    """
    Handle InviteClientCommand - auto-add client to Telegram group.

    Flow:
    1. Load chat aggregate to get telegram_supergroup_id
    2. Parse contact (phone or @username)
    3. Resolve to telegram_user_id via MTProto
    4. Invite to group via MTProto
    5. Record ClientInvited or ClientInvitationFailed event
    6. Projector updates telegram_group_members table

    Note: This handler uses TelegramAdapter for infrastructure operations,
    which is allowed in CQRS (not a query - it's an external system call).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: InviteClientCommand) -> uuid.UUID:
        log.info(f"Inviting client '{command.contact}' to chat {command.chat_id}")

        # Load chat aggregate to get telegram_supergroup_id
        chat_aggregate = await self.load_aggregate(command.chat_id, "Chat", ChatAggregate)

        # Verify chat has Telegram supergroup linked
        telegram_supergroup_id = chat_aggregate.state.telegram_chat_id
        if not telegram_supergroup_id:
            log.error(f"Chat {command.chat_id} not linked to Telegram supergroup")
            raise ValueError("Chat not linked to Telegram group. Cannot invite client.")

        # Check if Telegram adapter is available
        if not self.telegram_adapter:
            log.error("TelegramAdapter not available")
            raise ValueError("Telegram integration not available")

        # Parse contact to value object
        contact = TelegramContact.from_string(command.contact)
        log.info(f"Parsed contact: type={contact.contact_type.value}, value={contact.value}")

        # Resolve and invite via MTProto
        success, telegram_user_id, status = await self.telegram_adapter.resolve_and_invite_by_contact(
            group_id=telegram_supergroup_id,
            contact=command.contact,
            client_name=command.client_name
        )

        if success:
            # Record success event
            event = ClientInvited(
                chat_id=command.chat_id,
                contact_type=contact.contact_type.value,
                contact_value=contact.value,
                telegram_user_id=telegram_user_id,
                client_name=command.client_name,
                invited_by=command.invited_by,
                status=status,  # 'success' or 'already_member'
            )
            chat_aggregate._apply(event)
            log.info(f"Client invited successfully: telegram_user_id={telegram_user_id}, status={status}")
        else:
            # Record failure event
            event = ClientInvitationFailed(
                chat_id=command.chat_id,
                contact_value=contact.value,
                reason=status,  # 'user_not_found', 'privacy_restricted', 'rate_limit', etc.
                invited_by=command.invited_by,
            )
            chat_aggregate._apply(event)
            log.warning(f"Client invitation failed: contact={contact.value}, reason={status}")

        # Publish events
        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Raise exception for failed invitations so API can return appropriate error
        if not success:
            raise ValueError(f"Failed to invite client: {status}")

        return command.chat_id
