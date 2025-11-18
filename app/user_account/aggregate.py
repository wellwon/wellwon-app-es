# =============================================================================
# File: app/user_account/aggregate.py
# Description: User Aggregate Root for 
# Responsibilities:
#  - Maintain internal state for user entities via event sourcing.
#  - Validate commands and generate corresponding Domain Events.
#  - Apply events to mutate aggregate state and track uncommitted events.
#  - Support snapshot creation and restoration for event store optimization.
# =============================================================================

from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

# Domain Events
from app.user_account.events import (
    BaseEvent,
    UserAccountCreated,
    UserPasswordChanged,
    UserPasswordResetViaSecret,
    UserAccountDeleted,
    UserEmailVerified,
    UserProfileUpdated,
)


class UserAccountAggregateState(BaseModel):
    """
    Represents the in-memory state of a UserAggregate.
    Fields correspond to properties maintained in the 'users' write model.
    """
    user_id: Optional[uuid.UUID] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    email_verified: bool = False
    secret_hash: Optional[str] = None
    password_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    last_password_change: Optional[datetime] = None

    # WellWon Platform fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    user_type: str = "entrepreneur"  # ww_admin, ww_manager, entrepreneur, investor
    user_number: Optional[int] = None  # Auto-increment user number


class UserAccountAggregate:
    """
    Aggregate root for User entity.
    - Commands mutate state by emitting events.
    - Events are applied to update internal state.
    - Supports snapshots for event store optimization.
    """

    def __init__(self, user_id: uuid.UUID):
        self.id: uuid.UUID = user_id
        self.version: int = 0
        self.state: UserAccountAggregateState = UserAccountAggregateState(user_id=user_id)
        self._uncommitted_events: List[BaseEvent] = []

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Return events not yet persisted to the event store."""
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        """Clear the list of uncommitted events after they are persisted."""
        self._uncommitted_events.clear()

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------
    def create_new_user(
            self,
            username: str,
            email: str,
            role: str,
            hashed_password: str,
            hashed_secret: str,
    ) -> None:
        """
        Handle CreateUserCommand:
        - Validate that aggregate is new (version == 0).
        - Emit UserAccountCreated event.
        """
        if self.version > 0:
            raise ValueError("User already exists.")

        if not username or not email:
            raise ValueError("Username and email are required.")

        event = UserAccountCreated(
            user_id=self.id,
            username=username.lower(),
            email=email.lower(),
            role=role,
            hashed_password=hashed_password,
            hashed_secret=hashed_secret,
        )
        self._apply_and_record(event)

    def change_password(self, new_hashed_password: str) -> None:
        """
        Handle ChangeUserPasswordCommand:
        - Must be active user.
        - Emit UserPasswordChanged event.
        """
        if not self.state.is_active:
            raise ValueError("Cannot change password for inactive user.")

        if not new_hashed_password:
            raise ValueError("New password hash is required.")

        event = UserPasswordChanged(
            user_id=self.id,
            new_hashed_password=new_hashed_password
        )
        self._apply_and_record(event)

    def reset_password_with_secret(self, new_hashed_password: str) -> None:
        """
        Handle ResetUserPasswordWithSecretCommand:
        - Must be active user.
        - Emit UserPasswordResetViaSecret event.
        """
        if not self.state.is_active:
            raise ValueError("Cannot reset password for inactive user.")

        if not new_hashed_password:
            raise ValueError("New password hash is required.")

        event = UserPasswordResetViaSecret(
            user_id=self.id,
            new_hashed_password=new_hashed_password
        )
        self._apply_and_record(event)

    def delete(self, reason: str = "self_delete", grace_period: int = 0) -> None:
        """
        Handle DeleteUserCommand:
        - Emit UserAccountDeleted event (marks user as inactive).
        """
        if not self.state.is_active:
            return  # Already deleted, idempotent

        event = UserAccountDeleted(
            user_id=self.id,
            reason=reason,
            grace_period=grace_period
        )
        self._apply_and_record(event)

    def verify_email(self) -> None:
        """
        Handle email verification:
        - Emit UserEmailVerified event if not already verified.
        """
        if self.state.email_verified:
            return  # Already verified, idempotent

        event = UserEmailVerified(user_id=self.id)
        self._apply_and_record(event)

    def update_profile(
            self,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            avatar_url: Optional[str] = None,
            bio: Optional[str] = None,
            phone: Optional[str] = None
    ) -> None:
        """
        Handle UpdateUserProfileCommand:
        - Update user profile information.
        - Emit UserProfileUpdated event.
        """
        if not self.state.is_active:
            raise ValueError("Cannot update profile for inactive user.")

        event = UserProfileUpdated(
            user_id=self.id,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
            bio=bio,
            phone=phone
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Internal Event Application
    # -------------------------------------------------------------------------
    def _apply_and_record(self, event: BaseEvent) -> None:
        """
        Apply event to state and record it for later persistence.
        """
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    def _apply(self, event: BaseEvent) -> None:
        """
        Dispatch event to the appropriate state update method using isinstance checks.
        """
        if isinstance(event, UserAccountCreated):
            self._on_user_created(event)
        elif isinstance(event, UserPasswordChanged):
            self._on_password_changed(event)
        elif isinstance(event, UserPasswordResetViaSecret):
            self._on_password_reset(event)
        elif isinstance(event, UserAccountDeleted):
            self._on_user_deleted(event)
        elif isinstance(event, UserEmailVerified):
            self._on_email_verified(event)
        elif isinstance(event, UserProfileUpdated):
            self._on_profile_updated(event)

    # -------------------------------------------------------------------------
    # State Update Methods
    # -------------------------------------------------------------------------
    def _on_user_created(self, event: UserAccountCreated) -> None:
        self.state.user_id = event.user_id
        self.state.username = event.username
        self.state.email = event.email
        self.state.role = event.role
        self.state.is_active = True
        self.state.email_verified = False
        self.state.password_hash = event.hashed_password
        self.state.secret_hash = event.hashed_secret
        self.state.account_mappings.clear()
        self.state.connected_brokers.clear()
        self.state.created_at = event.timestamp

    def _on_password_changed(self, event: UserPasswordChanged) -> None:
        self.state.password_hash = event.new_hashed_password
        self.state.last_password_change = event.timestamp

    def _on_password_reset(self, event: UserPasswordResetViaSecret) -> None:
        self.state.password_hash = event.new_hashed_password
        self.state.last_password_change = event.timestamp

    def _on_user_deleted(self, event: UserAccountDeleted) -> None:
        self.state.is_active = False

    def _on_email_verified(self, event: UserEmailVerified) -> None:
        self.state.email_verified = True

    def _on_profile_updated(self, event) -> None:
        """Apply UserProfileUpdated event to state"""
        if event.first_name is not None:
            self.state.first_name = event.first_name
        if event.last_name is not None:
            self.state.last_name = event.last_name
        if event.avatar_url is not None:
            self.state.avatar_url = event.avatar_url
        if event.bio is not None:
            self.state.bio = event.bio
        if event.phone is not None:
            self.state.phone = event.phone

    # -------------------------------------------------------------------------
    # Snapshot Support for Event Store
    # -------------------------------------------------------------------------
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state for event store optimization"""
        return {
            "user_id": str(self.state.user_id) if self.state.user_id else None,
            "username": self.state.username,
            "email": self.state.email,
            "role": self.state.role,
            "is_active": self.state.is_active,
            "email_verified": self.state.email_verified,
            "secret_hash": self.state.secret_hash,
            "password_hash": self.state.password_hash,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "last_password_change": self.state.last_password_change.isoformat() if self.state.last_password_change else None,
            # WellWon fields
            "first_name": self.state.first_name,
            "last_name": self.state.last_name,
            "avatar_url": self.state.avatar_url,
            "bio": self.state.bio,
            "phone": self.state.phone,
            "user_type": self.state.user_type,
            "user_number": self.state.user_number,
            "version": self.version
        }

    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore aggregate state from a snapshot"""
        self.state.user_id = uuid.UUID(snapshot_data["user_id"]) if snapshot_data.get("user_id") else None
        self.state.username = snapshot_data.get("username")
        self.state.email = snapshot_data.get("email")
        self.state.role = snapshot_data.get("role", "user")
        self.state.is_active = snapshot_data.get("is_active", True)
        self.state.email_verified = snapshot_data.get("email_verified", False)
        self.state.secret_hash = snapshot_data.get("secret_hash")
        self.state.password_hash = snapshot_data.get("password_hash")

        # WellWon fields
        self.state.first_name = snapshot_data.get("first_name")
        self.state.last_name = snapshot_data.get("last_name")
        self.state.avatar_url = snapshot_data.get("avatar_url")
        self.state.bio = snapshot_data.get("bio")
        self.state.phone = snapshot_data.get("phone")
        self.state.user_type = snapshot_data.get("user_type", "entrepreneur")
        self.state.user_number = snapshot_data.get("user_number")

        if snapshot_data.get("created_at"):
            self.state.created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if snapshot_data.get("last_password_change"):
            self.state.last_password_change = datetime.fromisoformat(snapshot_data["last_password_change"])

        self.version = snapshot_data.get("version", 0)

    # -------------------------------------------------------------------------
    # Replay from History
    # -------------------------------------------------------------------------
    @classmethod
    def replay_from_events(cls, user_id: uuid.UUID, events: List[BaseEvent]) -> UserAccountAggregate:
        """
        Reconstruct an aggregate by applying past events in order.
        """
        agg = cls(user_id)
        for evt in events:
            agg._apply(evt)
            agg.version += 1
        agg.mark_events_committed()
        return agg

# =============================================================================
# EOF
# =============================================================================