# =============================================================================
# File: app/chat/aggregate.py
# Description: Chat domain aggregate with Event Sourcing
# =============================================================================

from __future__ import annotations

from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import logging

from app.common.base.base_model import BaseEvent
from app.chat.events import (
    ChatCreated,
    ChatUpdated,
    ChatArchived,
    ChatRestored,
    ChatHardDeleted,
    ChatLinkedToCompany,
    ChatUnlinkedFromCompany,
    ParticipantAdded,
    ParticipantRemoved,
    ParticipantRoleChanged,
    ParticipantLeft,
    MessageSent,
    MessageEdited,
    MessageDeleted,
    MessageReadStatusUpdated,
    MessagesMarkedAsRead,
    TelegramChatLinked,
    TelegramChatUnlinked,
)
from app.chat.exceptions import (
    ChatAlreadyExistsError,
    ChatInactiveError,
    UserNotParticipantError,
    UserAlreadyParticipantError,
    InsufficientPermissionsError,
)
from app.chat.enums import ParticipantRole

log = logging.getLogger("wellwon.chat.aggregate")


# =============================================================================
# Participant State (embedded in aggregate state)
# =============================================================================

class ParticipantState(BaseModel):
    """State of a chat participant"""
    user_id: uuid.UUID
    role: str = "member"
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    last_read_message_id: Optional[int] = None  # Snowflake ID for idempotency


# =============================================================================
# Message State (for tracking in aggregate - lightweight)
# =============================================================================

class MessageState(BaseModel):
    """Lightweight message state in aggregate"""
    message_id: int  # Server-generated Snowflake ID (int64)
    sender_id: Optional[uuid.UUID] = None  # None for external Telegram users
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Chat Aggregate State
# =============================================================================

class ChatAggregateState(BaseModel):
    """In-memory state for Chat aggregate"""
    chat_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    chat_type: str = "direct"  # direct, group, company
    company_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True
    is_deleted: bool = False

    # Participants (user_id -> ParticipantState)
    participants: Dict[str, ParticipantState] = Field(default_factory=dict)

    # Message tracking (message_id -> MessageState) - keep limited for memory
    recent_messages: Dict[str, MessageState] = Field(default_factory=dict)
    message_count: int = 0
    last_message_at: Optional[datetime] = None

    # Telegram integration
    telegram_chat_id: Optional[int] = None
    telegram_topic_id: Optional[int] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Chat Aggregate
# =============================================================================

class ChatAggregate:
    """
    Chat Aggregate Root for Event Sourcing.

    Responsibilities:
    - Validate business rules for chat operations
    - Emit domain events
    - Maintain aggregate state from events
    """

    # Maximum recent messages to track in aggregate state (for memory efficiency)
    MAX_RECENT_MESSAGES = 100

    def __init__(self, chat_id: uuid.UUID):
        self.id: uuid.UUID = chat_id
        self.version: int = 0
        self.state: ChatAggregateState = ChatAggregateState(chat_id=chat_id)
        self._uncommitted_events: List[BaseEvent] = []

    # =========================================================================
    # Event Management
    # =========================================================================

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Get events that haven't been committed to event store"""
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        """Mark all events as committed"""
        self._uncommitted_events.clear()

    def _apply_and_record(self, event: BaseEvent) -> None:
        """Apply event to state and record for commit"""
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    # =========================================================================
    # Chat Lifecycle Methods
    # =========================================================================

    def create_chat(
        self,
        name: Optional[str],
        chat_type: str,
        created_by: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_supergroup_id: Optional[int] = None,
        telegram_topic_id: Optional[int] = None,
    ) -> None:
        """Create a new chat"""
        if self.version > 0:
            raise ChatAlreadyExistsError(str(self.id))

        # Use telegram_supergroup_id as primary, fallback to telegram_chat_id for compat
        supergroup_id = telegram_supergroup_id or telegram_chat_id

        event = ChatCreated(
            chat_id=self.id,
            name=name,
            chat_type=chat_type,
            created_by=created_by,
            company_id=company_id,
            telegram_chat_id=supergroup_id,  # Legacy field
            telegram_supergroup_id=supergroup_id,  # New field
            telegram_topic_id=telegram_topic_id,
        )
        self._apply_and_record(event)

    def update_chat(
        self,
        name: Optional[str],
        updated_by: uuid.UUID,
    ) -> None:
        """Update chat details"""
        self._ensure_active()
        self._ensure_participant(updated_by)

        event = ChatUpdated(
            chat_id=self.id,
            name=name,
            updated_by=updated_by,
        )
        self._apply_and_record(event)

    def archive_chat(
        self,
        archived_by: uuid.UUID,
        telegram_supergroup_id: Optional[int] = None,
        telegram_topic_id: Optional[int] = None,
    ) -> None:
        """Archive the chat"""
        self._ensure_active()
        self._ensure_admin(archived_by)

        event = ChatArchived(
            chat_id=self.id,
            archived_by=archived_by,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )
        self._apply_and_record(event)

    def restore_chat(self, restored_by: uuid.UUID) -> None:
        """Restore an archived chat"""
        if self.state.is_active:
            raise ChatInactiveError(str(self.id))  # Already active

        event = ChatRestored(
            chat_id=self.id,
            restored_by=restored_by,
        )
        self._apply_and_record(event)

    def hard_delete_chat(
        self,
        deleted_by: uuid.UUID,
        reason: Optional[str] = None,
        telegram_supergroup_id: Optional[int] = None,
        telegram_topic_id: Optional[int] = None,
    ) -> None:
        """Permanently delete the chat (hard delete)"""
        # Prevent double deletion
        if self.state.is_deleted:
            log.warning(f"Chat {self.id} is already deleted, skipping")
            return

        event = ChatHardDeleted(
            chat_id=self.id,
            deleted_by=deleted_by,
            reason=reason,
            telegram_supergroup_id=telegram_supergroup_id,
            telegram_topic_id=telegram_topic_id,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Participant Methods
    # =========================================================================

    def add_participant(
        self,
        user_id: uuid.UUID,
        role: str = "member",
        added_by: Optional[uuid.UUID] = None,
    ) -> None:
        """Add a participant to the chat"""
        self._ensure_active()

        user_key = str(user_id)
        if user_key in self.state.participants and self.state.participants[user_key].is_active:
            raise UserAlreadyParticipantError(str(self.id), str(user_id))

        event = ParticipantAdded(
            chat_id=self.id,
            user_id=user_id,
            role=role,
            added_by=added_by,
        )
        self._apply_and_record(event)

    def remove_participant(
        self,
        user_id: uuid.UUID,
        removed_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> None:
        """Remove a participant from the chat"""
        self._ensure_active()
        self._ensure_participant(user_id)

        # Only admin can remove others
        if user_id != removed_by:
            self._ensure_admin(removed_by)

        event = ParticipantRemoved(
            chat_id=self.id,
            user_id=user_id,
            removed_by=removed_by,
            reason=reason,
        )
        self._apply_and_record(event)

    def change_participant_role(
        self,
        user_id: uuid.UUID,
        new_role: str,
        changed_by: uuid.UUID,
    ) -> None:
        """Change a participant's role"""
        self._ensure_active()
        self._ensure_participant(user_id)
        self._ensure_admin(changed_by)

        user_key = str(user_id)
        old_role = self.state.participants[user_key].role

        if old_role == new_role:
            return  # No change needed

        event = ParticipantRoleChanged(
            chat_id=self.id,
            user_id=user_id,
            old_role=old_role,
            new_role=new_role,
            changed_by=changed_by,
        )
        self._apply_and_record(event)

    def leave_chat(self, user_id: uuid.UUID) -> None:
        """Participant leaves the chat voluntarily"""
        self._ensure_active()
        self._ensure_participant(user_id)

        event = ParticipantLeft(
            chat_id=self.id,
            user_id=user_id,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Message Methods
    # =========================================================================

    def send_message(
        self,
        message_id: int,  # Server-generated Snowflake ID (int64)
        sender_id: uuid.UUID,
        content: str,
        message_type: str = "text",
        reply_to_id: Optional[int] = None,  # Snowflake ID of replied message
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
        voice_duration: Optional[int] = None,
        source: str = "web",
        telegram_message_id: Optional[int] = None,
        telegram_user_id: Optional[int] = None,
        telegram_user_data: Optional[Dict[str, Any]] = None,
        telegram_forward_data: Optional[Dict[str, Any]] = None,
        telegram_topic_id: Optional[int] = None,
        client_temp_id: Optional[str] = None,  # For frontend reconciliation
    ) -> None:
        """
        Send a message to the chat.

        Args:
            message_id: Server-generated Snowflake ID (int64) - permanent ID
            client_temp_id: Optional client temp ID for optimistic UI reconciliation
        """
        self._ensure_active()
        self._ensure_participant(sender_id)

        # Get all active participant IDs for real-time routing
        participant_ids = [
            uuid.UUID(uid) for uid, p in self.state.participants.items()
            if p.is_active
        ]

        event = MessageSent(
            message_id=message_id,  # Snowflake ID (int64)
            chat_id=self.id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            voice_duration=voice_duration,
            source=source,
            participant_ids=participant_ids,
            telegram_message_id=telegram_message_id,
            telegram_user_id=telegram_user_id,
            telegram_user_data=telegram_user_data,
            telegram_forward_data=telegram_forward_data,
            telegram_topic_id=telegram_topic_id,
            client_temp_id=client_temp_id,  # Echo for frontend reconciliation
        )
        self._apply_and_record(event)

    def receive_external_message(
        self,
        message_id: int,  # Server-generated Snowflake ID (int64)
        content: str,
        message_type: str = "text",
        source: str = "telegram",
        telegram_message_id: Optional[int] = None,
        telegram_user_id: Optional[int] = None,
        telegram_user_data: Optional[Dict[str, Any]] = None,
        telegram_forward_data: Optional[Dict[str, Any]] = None,
        telegram_topic_id: Optional[int] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
        voice_duration: Optional[int] = None,
    ) -> None:
        """
        Receive message from external source (e.g., Telegram).

        This method is used for messages from users who are NOT WellWon participants.
        It does NOT require sender to be a chat participant.

        Business context:
        - New clients contact via Telegram general topic
        - Messages distributed to available managers
        - No WellWon account required for external sender

        Note: We don't call _ensure_telegram_linked() here because:
        1. The message is coming FROM Telegram, proving the link exists
        2. The webhook already validated the chat via query before calling this
        3. Legacy chats may not have telegram_chat_id in their event history
        """
        self._ensure_active()
        # Note: telegram_linked check removed - message source proves linkage

        # Get all active participant IDs for real-time routing
        participant_ids = [
            uuid.UUID(uid) for uid, p in self.state.participants.items()
            if p.is_active
        ]

        event = MessageSent(
            message_id=message_id,
            chat_id=self.id,
            sender_id=None,  # External user has no WellWon ID
            content=content,
            message_type=message_type,
            source=source,
            participant_ids=participant_ids,
            telegram_message_id=telegram_message_id,
            telegram_user_id=telegram_user_id,
            telegram_user_data=telegram_user_data,
            telegram_forward_data=telegram_forward_data,
            telegram_topic_id=telegram_topic_id,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            voice_duration=voice_duration,
        )
        self._apply_and_record(event)

    def edit_message(
        self,
        message_id: uuid.UUID,
        edited_by: uuid.UUID,
        new_content: str,
    ) -> None:
        """Edit an existing message"""
        self._ensure_active()
        self._ensure_participant(edited_by)

        msg_key = str(message_id)
        if msg_key not in self.state.recent_messages:
            # Message not in recent cache - allow edit (projector will validate)
            pass
        else:
            msg = self.state.recent_messages[msg_key]
            if msg.sender_id != edited_by:
                raise InsufficientPermissionsError(str(edited_by), "edit this message")
            if msg.is_deleted:
                raise InsufficientPermissionsError(str(edited_by), "edit deleted message")

        # Note: old_content will be filled by handler from read model
        event = MessageEdited(
            message_id=message_id,
            chat_id=self.id,
            edited_by=edited_by,
            old_content="",  # Handler will fill this
            new_content=new_content,
        )
        self._apply_and_record(event)

    def delete_message(
        self,
        message_id: uuid.UUID,
        deleted_by: uuid.UUID,
        telegram_message_id: Optional[int] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> None:
        """Soft-delete a message"""
        self._ensure_active()
        self._ensure_participant(deleted_by)

        msg_key = str(message_id)
        if msg_key in self.state.recent_messages:
            msg = self.state.recent_messages[msg_key]
            # Only sender or admin can delete
            if msg.sender_id != deleted_by:
                self._ensure_admin(deleted_by)

        event = MessageDeleted(
            message_id=message_id,
            chat_id=self.id,
            deleted_by=deleted_by,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )
        self._apply_and_record(event)

    def mark_message_as_read(
        self,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Mark a message as read"""
        self._ensure_participant(user_id)

        event = MessageReadStatusUpdated(
            message_id=message_id,
            chat_id=self.id,
            user_id=user_id,
        )
        self._apply_and_record(event)

    def mark_messages_as_read(
        self,
        user_id: uuid.UUID,
        last_read_message_id: int,  # Snowflake ID (bigint)
        read_count: int,
        source: str = "web",
        telegram_message_id: Optional[int] = None,  # For bidirectional sync
    ) -> None:
        """Mark all messages up to a point as read.

        Args:
            user_id: User who read the messages
            last_read_message_id: Snowflake ID of the last read message (bigint)
            read_count: Number of messages marked as read
            source: Origin of read event ('web', 'telegram') - prevents sync loops
            telegram_message_id: Telegram message ID for syncing (enriched by command)
        """
        # Soft check - don't fail if participant not in aggregate state
        # (may happen with snapshot loading issues or legacy data)
        if not self.is_participant(user_id):
            log.warning(
                f"mark_messages_as_read: user {user_id} not found in aggregate participants, "
                f"skipping (chat: {self.id}, participants: {len(self.state.participants)})"
            )
            return

        # IDEMPOTENCY: Check if already marked as read up to this message
        user_key = str(user_id)
        participant = self.state.participants.get(user_key)
        if participant and participant.last_read_message_id == last_read_message_id:
            log.debug(
                f"mark_messages_as_read: already at message {last_read_message_id}, skipping"
            )
            return  # No-op, already at this read position

        # Include Telegram data from aggregate state for listener to use
        event = MessagesMarkedAsRead(
            chat_id=self.id,
            user_id=user_id,
            last_read_message_id=last_read_message_id,
            read_count=read_count,
            source=source,
            # Telegram sync data - listener will use this instead of querying
            telegram_message_id=telegram_message_id,
            telegram_chat_id=self.state.telegram_chat_id,
            telegram_topic_id=self.state.telegram_topic_id,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Telegram Integration Methods
    # =========================================================================

    def link_telegram_chat(
        self,
        telegram_chat_id: int,
        linked_by: uuid.UUID,
        telegram_topic_id: Optional[int] = None,
        telegram_supergroup_id: Optional[int] = None,
    ) -> None:
        """Link a Telegram chat"""
        self._ensure_active()
        self._ensure_admin(linked_by)

        event = TelegramChatLinked(
            chat_id=self.id,
            telegram_chat_id=telegram_chat_id,
            telegram_supergroup_id=telegram_supergroup_id or telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            linked_by=linked_by,
        )
        self._apply_and_record(event)

    def unlink_telegram_chat(self, unlinked_by: uuid.UUID) -> None:
        """Unlink Telegram chat"""
        self._ensure_active()
        self._ensure_admin(unlinked_by)

        if not self.state.telegram_chat_id:
            return  # Already unlinked

        event = TelegramChatUnlinked(
            chat_id=self.id,
            telegram_chat_id=self.state.telegram_chat_id,
            unlinked_by=unlinked_by,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Company Linking Methods (used by Saga orchestration)
    # =========================================================================

    def link_to_company(
        self,
        company_id: uuid.UUID,
        linked_by: uuid.UUID,
        telegram_supergroup_id: Optional[int] = None,
    ) -> None:
        """
        Link chat to a company.
        Used by CompanyCreationSaga to link existing chats to newly created companies.
        """
        self._ensure_active()

        from app.chat.events import ChatLinkedToCompany

        event = ChatLinkedToCompany(
            chat_id=self.id,
            company_id=company_id,
            telegram_supergroup_id=telegram_supergroup_id,
            linked_by=linked_by,
        )
        self._apply_and_record(event)

    def unlink_from_company(
        self,
        unlinked_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Unlink chat from its company.
        Used by Saga compensation when company creation fails.
        """
        self._ensure_active()

        if not self.state.company_id:
            return  # Already unlinked

        from app.chat.events import ChatUnlinkedFromCompany

        event = ChatUnlinkedFromCompany(
            chat_id=self.id,
            previous_company_id=self.state.company_id,
            unlinked_by=unlinked_by,
            reason=reason,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def _ensure_active(self) -> None:
        """Ensure chat is active"""
        if not self.state.is_active:
            raise ChatInactiveError(str(self.id))

    def _ensure_participant(self, user_id: uuid.UUID) -> None:
        """Ensure user is an active participant"""
        user_key = str(user_id)
        if user_key not in self.state.participants:
            raise UserNotParticipantError(str(self.id), str(user_id))
        if not self.state.participants[user_key].is_active:
            raise UserNotParticipantError(str(self.id), str(user_id))

    def _ensure_admin(self, user_id: uuid.UUID) -> None:
        """Ensure user is an admin"""
        user_key = str(user_id)
        self._ensure_participant(user_id)
        if self.state.participants[user_key].role != ParticipantRole.ADMIN.value:
            raise InsufficientPermissionsError(str(user_id), "perform admin action")

    def _ensure_telegram_linked(self) -> None:
        """Ensure chat has Telegram integration enabled"""
        if not self.state.telegram_chat_id:
            raise ChatInactiveError(f"Chat {self.id} is not linked to Telegram")

    def is_participant(self, user_id: uuid.UUID) -> bool:
        """Check if user is an active participant"""
        user_key = str(user_id)
        if user_key not in self.state.participants:
            return False
        return self.state.participants[user_key].is_active

    def get_participant_count(self) -> int:
        """Get count of active participants"""
        return sum(1 for p in self.state.participants.values() if p.is_active)

    # =========================================================================
    # Event Application (State Updates)
    # =========================================================================

    def _apply(self, event: BaseEvent) -> None:
        """Route event to appropriate handler"""
        handlers = {
            ChatCreated: self._on_chat_created,
            ChatUpdated: self._on_chat_updated,
            ChatArchived: self._on_chat_archived,
            ChatRestored: self._on_chat_restored,
            ChatHardDeleted: self._on_chat_hard_deleted,
            ChatLinkedToCompany: self._on_chat_linked_to_company,
            ChatUnlinkedFromCompany: self._on_chat_unlinked_from_company,
            ParticipantAdded: self._on_participant_added,
            ParticipantRemoved: self._on_participant_removed,
            ParticipantRoleChanged: self._on_participant_role_changed,
            ParticipantLeft: self._on_participant_left,
            MessageSent: self._on_message_sent,
            MessageEdited: self._on_message_edited,
            MessageDeleted: self._on_message_deleted,
            MessagesMarkedAsRead: self._on_messages_marked_as_read,
            TelegramChatLinked: self._on_telegram_chat_linked,
            TelegramChatUnlinked: self._on_telegram_chat_unlinked,
        }

        handler = handlers.get(type(event))
        if handler:
            handler(event)

    def _on_chat_created(self, event: ChatCreated) -> None:
        self.state.chat_id = event.chat_id
        self.state.name = event.name
        self.state.chat_type = event.chat_type
        self.state.created_by = event.created_by
        self.state.company_id = event.company_id
        self.state.created_at = event.timestamp
        self.state.is_active = True
        self.state.telegram_chat_id = event.telegram_chat_id
        self.state.telegram_topic_id = event.telegram_topic_id

    def _on_chat_updated(self, event: ChatUpdated) -> None:
        if event.name is not None:
            self.state.name = event.name
        self.state.updated_at = event.timestamp
        if event.metadata:
            self.state.metadata.update(event.metadata)

    def _on_chat_archived(self, event: ChatArchived) -> None:
        self.state.is_active = False
        self.state.updated_at = event.timestamp

    def _on_chat_restored(self, event: ChatRestored) -> None:
        self.state.is_active = True
        self.state.updated_at = event.timestamp

    def _on_chat_hard_deleted(self, event: ChatHardDeleted) -> None:
        self.state.is_deleted = True
        self.state.is_active = False
        self.state.updated_at = event.timestamp

    def _on_chat_linked_to_company(self, event: ChatLinkedToCompany) -> None:
        self.state.company_id = event.company_id
        if event.telegram_supergroup_id:
            self.state.telegram_chat_id = event.telegram_supergroup_id
        self.state.updated_at = event.timestamp

    def _on_chat_unlinked_from_company(self, event: ChatUnlinkedFromCompany) -> None:
        self.state.company_id = None
        self.state.updated_at = event.timestamp

    def _on_participant_added(self, event: ParticipantAdded) -> None:
        user_key = str(event.user_id)
        self.state.participants[user_key] = ParticipantState(
            user_id=event.user_id,
            role=event.role,
            joined_at=event.joined_at,
            is_active=True,
        )

    def _on_participant_removed(self, event: ParticipantRemoved) -> None:
        user_key = str(event.user_id)
        if user_key in self.state.participants:
            self.state.participants[user_key].is_active = False

    def _on_participant_role_changed(self, event: ParticipantRoleChanged) -> None:
        user_key = str(event.user_id)
        if user_key in self.state.participants:
            self.state.participants[user_key].role = event.new_role

    def _on_participant_left(self, event: ParticipantLeft) -> None:
        user_key = str(event.user_id)
        if user_key in self.state.participants:
            self.state.participants[user_key].is_active = False

    def _on_message_sent(self, event: MessageSent) -> None:
        msg_key = str(event.message_id)
        self.state.recent_messages[msg_key] = MessageState(
            message_id=event.message_id,
            sender_id=event.sender_id,
            is_deleted=False,
            created_at=event.timestamp,
        )
        self.state.message_count += 1
        self.state.last_message_at = event.timestamp

        # Prune old messages from aggregate state
        self._prune_recent_messages()

    def _on_message_edited(self, event: MessageEdited) -> None:
        # No state change needed in aggregate
        pass

    def _on_message_deleted(self, event: MessageDeleted) -> None:
        msg_key = str(event.message_id)
        if msg_key in self.state.recent_messages:
            self.state.recent_messages[msg_key].is_deleted = True

    def _on_messages_marked_as_read(self, event: MessagesMarkedAsRead) -> None:
        """Update participant's last read position for idempotency"""
        user_key = str(event.user_id)
        if user_key in self.state.participants:
            self.state.participants[user_key].last_read_message_id = event.last_read_message_id

    def _on_telegram_chat_linked(self, event: TelegramChatLinked) -> None:
        self.state.telegram_chat_id = event.telegram_chat_id
        self.state.telegram_topic_id = event.telegram_topic_id

    def _on_telegram_chat_unlinked(self, event: TelegramChatUnlinked) -> None:
        self.state.telegram_chat_id = None
        self.state.telegram_topic_id = None

    def _prune_recent_messages(self) -> None:
        """Keep only most recent messages in aggregate state"""
        if len(self.state.recent_messages) > self.MAX_RECENT_MESSAGES:
            # Sort by created_at and keep only MAX_RECENT_MESSAGES
            sorted_msgs = sorted(
                self.state.recent_messages.items(),
                key=lambda x: x[1].created_at,
                reverse=True
            )
            self.state.recent_messages = dict(sorted_msgs[:self.MAX_RECENT_MESSAGES])

    # =========================================================================
    # Snapshot Support
    # =========================================================================

    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state for persistence"""
        return {
            "chat_id": str(self.state.chat_id) if self.state.chat_id else None,
            "name": self.state.name,
            "chat_type": self.state.chat_type,
            "company_id": str(self.state.company_id) if self.state.company_id else None,
            "created_by": str(self.state.created_by) if self.state.created_by else None,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "updated_at": self.state.updated_at.isoformat() if self.state.updated_at else None,
            "is_active": self.state.is_active,
            "participants": {
                k: {
                    "user_id": str(v.user_id),
                    "role": v.role,
                    "joined_at": v.joined_at.isoformat(),
                    "is_active": v.is_active,
                    "last_read_message_id": v.last_read_message_id,  # Snowflake ID (int), keep as-is
                }
                for k, v in self.state.participants.items()
            },
            "message_count": self.state.message_count,
            "last_message_at": self.state.last_message_at.isoformat() if self.state.last_message_at else None,
            "telegram_chat_id": self.state.telegram_chat_id,
            "telegram_topic_id": self.state.telegram_topic_id,
            "metadata": self.state.metadata,
            "version": self.version,
        }

    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore state from a snapshot"""
        self.state.chat_id = uuid.UUID(snapshot_data["chat_id"]) if snapshot_data.get("chat_id") else None
        self.state.name = snapshot_data.get("name")
        self.state.chat_type = snapshot_data.get("chat_type", "direct")
        self.state.company_id = uuid.UUID(snapshot_data["company_id"]) if snapshot_data.get("company_id") else None
        self.state.created_by = uuid.UUID(snapshot_data["created_by"]) if snapshot_data.get("created_by") else None
        self.state.is_active = snapshot_data.get("is_active", True)
        self.state.message_count = snapshot_data.get("message_count", 0)
        self.state.telegram_chat_id = snapshot_data.get("telegram_chat_id")
        self.state.telegram_topic_id = snapshot_data.get("telegram_topic_id")
        self.state.metadata = snapshot_data.get("metadata", {})

        if snapshot_data.get("created_at"):
            self.state.created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if snapshot_data.get("updated_at"):
            self.state.updated_at = datetime.fromisoformat(snapshot_data["updated_at"])
        if snapshot_data.get("last_message_at"):
            self.state.last_message_at = datetime.fromisoformat(snapshot_data["last_message_at"])

        # Restore participants
        self.state.participants = {}
        for k, v in snapshot_data.get("participants", {}).items():
            last_read = v.get("last_read_message_id")
            # Handle last_read_message_id migration (UUID -> Snowflake ID)
            last_read_snowflake = None
            if last_read is not None:
                if isinstance(last_read, int):
                    # Already a Snowflake ID (new format)
                    last_read_snowflake = last_read
                elif isinstance(last_read, str):
                    # Could be UUID string or numeric string
                    if len(last_read) == 36 and last_read.count('-') == 4:
                        # Old UUID format - convert to Snowflake using same formula
                        try:
                            msg_uuid = uuid.UUID(last_read)
                            last_read_snowflake = int.from_bytes(msg_uuid.bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF
                        except ValueError:
                            last_read_snowflake = None
                    else:
                        # Numeric string
                        try:
                            last_read_snowflake = int(last_read)
                        except ValueError:
                            last_read_snowflake = None
            self.state.participants[k] = ParticipantState(
                user_id=uuid.UUID(v["user_id"]),
                role=v["role"],
                joined_at=datetime.fromisoformat(v["joined_at"]),
                is_active=v["is_active"],
                last_read_message_id=last_read_snowflake,
            )

        self.version = snapshot_data.get("version", 0)

    @classmethod
    def replay_from_events(
        cls,
        chat_id: uuid.UUID,
        events: List[BaseEvent],
        snapshot: Optional[Any] = None
    ) -> 'ChatAggregate':
        """
        Reconstruct aggregate from event history.

        Handles both BaseEvent objects and EventEnvelope objects (from KurrentDB).
        EventEnvelopes are converted to domain events using the event registry.

        Args:
            chat_id: The aggregate ID
            events: Events to replay (should be events AFTER snapshot if snapshot provided)
            snapshot: Optional AggregateSnapshot to restore from first
        """
        from app.infra.event_store.event_envelope import EventEnvelope
        from app.chat.events import CHAT_EVENT_TYPES

        agg = cls(chat_id)

        # Restore from snapshot first if provided
        if snapshot is not None:
            log.info(
                f"Restoring chat {chat_id} from snapshot v{snapshot.version}, "
                f"snapshot has {len(snapshot.state.get('participants', {}))} participants"
            )
            agg.restore_from_snapshot(snapshot.state)
            agg.version = snapshot.version
            log.info(
                f"After restore: chat {chat_id} v{agg.version}, "
                f"participants: {list(agg.state.participants.keys())}"
            )

        for evt in events:
            # Handle EventEnvelope from KurrentDB
            if isinstance(evt, EventEnvelope):
                # Try to convert envelope to domain event object
                event_obj = evt.to_event_object()
                if event_obj is None:
                    # Fallback: use CHAT_EVENT_TYPES registry
                    event_class = CHAT_EVENT_TYPES.get(evt.event_type)
                    if event_class:
                        try:
                            event_obj = event_class(**evt.event_data)
                        except Exception as e:
                            log.warning(f"Failed to deserialize {evt.event_type}: {e}")
                            continue
                    else:
                        log.warning(f"Unknown event type in replay: {evt.event_type}")
                        continue
                agg._apply(event_obj)
                # Use version from envelope (handles snapshot case correctly)
                if evt.aggregate_version:
                    agg.version = evt.aggregate_version
                else:
                    agg.version += 1
            else:
                # Direct BaseEvent object
                agg._apply(evt)
                agg.version += 1
        agg.mark_events_committed()
        return agg
