# =============================================================================
# File: app/chat/command_handlers/chat_handlers.py
# Description: Command handlers for chat lifecycle operations
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING, List, Optional

from app.chat.commands import (
    CreateChatCommand,
    UpdateChatCommand,
    ArchiveChatCommand,
    RestoreChatCommand,
    DeleteChatCommand,
    LinkChatToCompanyCommand,
    UnlinkChatFromCompanyCommand,
)
from app.chat.aggregate import ChatAggregate
from app.chat.enums import ParticipantRole
from app.company.queries import GetCompanyByIdQuery, GetCompanyByTelegramGroupQuery
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.infra.telegram.adapter import TelegramAdapter

log = logging.getLogger("wellwon.chat.handlers.chat")


@command_handler(CreateChatCommand)
class CreateChatHandler(BaseCommandHandler):
    """
    Handle CreateChatCommand using Event Sourcing with bidirectional Telegram sync.

    Creates a new chat and optionally adds initial participants.
    The creator is automatically added as admin.

    If the chat belongs to a company with a Telegram supergroup and no topic_id is provided,
    a new Telegram topic will be created for the chat.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: CreateChatCommand) -> uuid.UUID:
        log.info(f"Creating {command.chat_type} chat by user {command.created_by}")

        # Determine Telegram IDs - either from command or create new topic
        telegram_supergroup_id = command.telegram_supergroup_id
        telegram_topic_id = command.telegram_topic_id
        company_id = command.company_id

        # If supergroup is provided but no company_id, lookup company from supergroup
        if telegram_supergroup_id and not company_id:
            company_id = await self._get_company_from_supergroup(telegram_supergroup_id)
            if company_id:
                log.info(f"Found company {company_id} for supergroup {telegram_supergroup_id}")

        # If we have a supergroup and no topic_id yet, create a Telegram topic
        if telegram_supergroup_id and not telegram_topic_id:
            telegram_supergroup_id, telegram_topic_id = await self._ensure_telegram_topic(
                company_id,
                command.name or "Новый чат",
                telegram_supergroup_id
            )

        # Create new aggregate
        chat_aggregate = ChatAggregate(chat_id=command.chat_id)

        # Create the chat (use resolved company_id if we found one from supergroup)
        chat_aggregate.create_chat(
            name=command.name,
            chat_type=command.chat_type,
            created_by=command.created_by,
            company_id=company_id,  # Use resolved company_id (could be from command or from supergroup lookup)
            telegram_chat_id=telegram_supergroup_id,  # Map to aggregate's telegram_chat_id
            telegram_topic_id=telegram_topic_id,
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

        log.info(f"Chat created: {command.chat_id} with {len(command.participant_ids) + 1} participants, telegram_topic_id={telegram_topic_id}")
        return command.chat_id

    async def _get_company_from_supergroup(self, telegram_supergroup_id: int) -> Optional[uuid.UUID]:
        """
        Lookup company by Telegram supergroup ID.

        Returns:
            Company ID if found, None otherwise
        """
        try:
            company = await self.query_bus.query(
                GetCompanyByTelegramGroupQuery(telegram_group_id=telegram_supergroup_id)
            )
            if company:
                return company.id
            return None
        except Exception as e:
            log.warning(f"Failed to lookup company for supergroup {telegram_supergroup_id}: {e}")
            return None

    async def _ensure_telegram_topic(
        self,
        company_id: Optional[uuid.UUID],
        chat_name: str,
        provided_supergroup_id: Optional[int]
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Ensure a Telegram topic exists for the chat.

        Creates a new topic in the specified supergroup.
        If company_id is provided, will lookup the supergroup from company if not provided.

        Returns:
            Tuple of (telegram_supergroup_id, telegram_topic_id)
        """
        if not self.telegram_adapter:
            log.debug("Telegram adapter not available, skipping topic creation")
            return provided_supergroup_id, None

        try:
            telegram_supergroup_id = provided_supergroup_id

            # If no supergroup provided but we have company, try to get supergroup from company
            if not telegram_supergroup_id and company_id:
                company = await self.query_bus.query(GetCompanyByIdQuery(company_id=company_id))
                if company:
                    telegram_supergroup_id = getattr(company, 'telegram_group_id', None)

            if not telegram_supergroup_id:
                log.debug("No Telegram supergroup available for topic creation")
                return None, None

            # Create topic in Telegram
            log.info(f"Creating Telegram topic '{chat_name}' in supergroup {telegram_supergroup_id}")

            topic_info = await self.telegram_adapter.create_chat_topic(
                group_id=telegram_supergroup_id,
                topic_name=chat_name,
            )

            if topic_info:
                log.info(f"Telegram topic created: id={topic_info.topic_id}, name={topic_info.title}")
                return telegram_supergroup_id, topic_info.topic_id
            else:
                log.warning(f"Failed to create Telegram topic for chat '{chat_name}'")
                return telegram_supergroup_id, None

        except Exception as e:
            # Don't fail chat creation if Telegram sync fails
            log.error(f"Error creating Telegram topic: {e}", exc_info=True)
            return provided_supergroup_id, None


@command_handler(UpdateChatCommand)
class UpdateChatHandler(BaseCommandHandler):
    """Handle UpdateChatCommand - Telegram sync via TelegramEventListener"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: UpdateChatCommand) -> uuid.UUID:
        log.info(f"Updating chat {command.chat_id}")

        # Load aggregate from event store
        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        log.info(f"Chat state: company_id={chat_aggregate.state.company_id}, participants={list(chat_aggregate.state.participants.keys())}, event_count={len(events)}")

        # Auto-enroll user as participant if they're not yet a participant
        # For company chats, we allow any authenticated user to manage (they should be company members)
        if not chat_aggregate.is_participant(command.updated_by):
            log.info(f"User {command.updated_by} is not a participant, auto-enrolling as admin")
            chat_aggregate.add_participant(
                user_id=command.updated_by,
                role=ParticipantRole.ADMIN.value,
                added_by=command.updated_by,
            )

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

        # Telegram sync (topic rename) handled by TelegramEventListener via EventBus (CQRS pattern)
        log.info(f"Chat updated: {command.chat_id}")
        return command.chat_id

    async def _is_company_member(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        """Check if user is a member of the company"""
        try:
            from app.company.queries import GetUserCompanyRelationshipQuery
            relationship = await self.query_bus.query(GetUserCompanyRelationshipQuery(
                company_id=company_id,
                user_id=user_id,
            ))
            return relationship is not None and relationship.is_member
        except Exception as e:
            log.warning(f"Failed to check company membership: {e}")
            # Fall back to allowing the operation for company chats
            return True


@command_handler(ArchiveChatCommand)
class ArchiveChatHandler(BaseCommandHandler):
    """Handle ArchiveChatCommand (soft delete) with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus

    async def handle(self, command: ArchiveChatCommand) -> uuid.UUID:
        log.info(f"Archiving chat {command.chat_id}")

        # Lookup telegram IDs for syncing archive to Telegram
        telegram_supergroup_id: Optional[int] = None
        telegram_topic_id: Optional[int] = None

        try:
            from app.chat.queries import GetChatByIdQuery
            chat = await self.query_bus.query(
                GetChatByIdQuery(chat_id=command.chat_id)
            )
            if chat:
                telegram_supergroup_id = getattr(chat, 'telegram_supergroup_id', None) or getattr(chat, 'telegram_chat_id', None)
                telegram_topic_id = getattr(chat, 'telegram_topic_id', None)
        except Exception as e:
            log.warning(f"Failed to lookup telegram IDs for chat archive: {e}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        log.info(f"Chat state for archive: company_id={chat_aggregate.state.company_id}, participants={list(chat_aggregate.state.participants.keys())}, event_count={len(events)}")

        # Auto-enroll user as admin if they're not yet a participant
        if not chat_aggregate.is_participant(command.archived_by):
            log.info(f"User {command.archived_by} is not a participant, auto-enrolling as admin for archive")
            chat_aggregate.add_participant(
                user_id=command.archived_by,
                role=ParticipantRole.ADMIN.value,
                added_by=command.archived_by,
            )

        chat_aggregate.archive_chat(
            archived_by=command.archived_by,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        # Telegram sync handled by TelegramEventListener via EventBus (CQRS pattern)
        # Archive → close_forum_topic() in Telegram (preserves messages)
        log.info(f"Chat archived: {command.chat_id}, telegram_topic_id={telegram_topic_id}")
        return command.chat_id

    async def _is_company_member(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        """Check if user is a member of the company"""
        try:
            from app.company.queries import GetUserCompanyRelationshipQuery
            relationship = await self.query_bus.query(GetUserCompanyRelationshipQuery(
                company_id=company_id,
                user_id=user_id,
            ))
            return relationship is not None and relationship.is_member
        except Exception as e:
            log.warning(f"Failed to check company membership: {e}")
            # Fall back to allowing the operation for company chats
            return True


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

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.restore_chat(restored_by=command.restored_by)

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat restored: {command.chat_id}")
        return command.chat_id


@command_handler(DeleteChatCommand)
class DeleteChatHandler(BaseCommandHandler):
    """Handle DeleteChatCommand (hard delete) with bidirectional Telegram sync"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.telegram_adapter: Optional['TelegramAdapter'] = getattr(deps, 'telegram_adapter', None)

    async def handle(self, command: DeleteChatCommand) -> uuid.UUID:
        log.info(f"Hard deleting chat {command.chat_id}")

        # Lookup telegram IDs for syncing delete to Telegram
        telegram_supergroup_id: Optional[int] = None
        telegram_topic_id: Optional[int] = None

        try:
            from app.chat.queries import GetChatByIdQuery
            chat = await self.query_bus.query(
                GetChatByIdQuery(chat_id=command.chat_id)
            )
            if chat:
                telegram_supergroup_id = getattr(chat, 'telegram_supergroup_id', None) or getattr(chat, 'telegram_chat_id', None)
                telegram_topic_id = getattr(chat, 'telegram_topic_id', None)
        except Exception as e:
            log.warning(f"Failed to lookup telegram IDs for chat delete: {e}")

        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        chat_aggregate.hard_delete_chat(
            deleted_by=command.deleted_by,
            reason=command.reason,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )

        # Check if any events were generated
        has_new_events = len(chat_aggregate.get_uncommitted_events()) > 0

        if has_new_events:
            await self.publish_events(
                aggregate=chat_aggregate,
                aggregate_id=command.chat_id,
                command=command
            )
        else:
            # Already deleted in EventStore but maybe not in read model (previous projection failure)
            # Force cleanup of read model
            log.info(f"Chat {command.chat_id} already deleted in EventStore, ensuring read model cleanup")
            from app.infra.read_repos.chat_read_repo import ChatReadRepo
            try:
                await ChatReadRepo.hard_delete_chat(chat_id=command.chat_id)
            except Exception as e:
                log.warning(f"Read model cleanup failed (may already be deleted): {e}")

        # Telegram sync handled by TelegramEventListener via EventBus (CQRS pattern)
        # Delete → delete_forum_topic() in Telegram (removes messages)
        log.info(f"Chat hard deleted: {command.chat_id}, telegram_topic_id={telegram_topic_id}")
        return command.chat_id


# =============================================================================
# Company Linking Handlers (used by CompanyCreationSaga)
# =============================================================================

@command_handler(LinkChatToCompanyCommand)
class LinkChatToCompanyHandler(BaseCommandHandler):
    """
    Handle LinkChatToCompanyCommand.
    Used by CompanyCreationSaga to link existing chats to newly created companies.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: LinkChatToCompanyCommand) -> uuid.UUID:
        log.info(f"Linking chat {command.chat_id} to company {command.company_id}")

        # Load aggregate from event store
        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # Link to company
        chat_aggregate.link_to_company(
            company_id=command.company_id,
            linked_by=command.linked_by,
            telegram_supergroup_id=command.telegram_supergroup_id,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat {command.chat_id} linked to company {command.company_id}")
        return command.chat_id


@command_handler(UnlinkChatFromCompanyCommand)
class UnlinkChatFromCompanyHandler(BaseCommandHandler):
    """
    Handle UnlinkChatFromCompanyCommand.
    Used by saga compensation when company creation fails.
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.chat-events",
            event_store=deps.event_store
        )

    async def handle(self, command: UnlinkChatFromCompanyCommand) -> uuid.UUID:
        log.info(f"Unlinking chat {command.chat_id} from company")

        # Load aggregate from event store
        events = await self.event_store.get_events(command.chat_id, "Chat")
        chat_aggregate = ChatAggregate.replay_from_events(command.chat_id, events)

        # Unlink from company
        chat_aggregate.unlink_from_company(
            unlinked_by=command.unlinked_by,
            reason=command.reason,
        )

        await self.publish_events(
            aggregate=chat_aggregate,
            aggregate_id=command.chat_id,
            command=command
        )

        log.info(f"Chat {command.chat_id} unlinked from company")
        return command.chat_id
