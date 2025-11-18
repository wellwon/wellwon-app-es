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
    UserBrokerAccountMappingSet,
    UserConnectedBrokerAdded,
    UserConnectedBrokerRemoved,
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
    account_mappings: Dict[str, str] = Field(default_factory=dict)
    connected_brokers: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    # TRUE SAGA Pattern: Track owned resources for event enrichment
    owned_connection_ids: List[uuid.UUID] = Field(default_factory=list)
    owned_account_ids: List[uuid.UUID] = Field(default_factory=list)
    owned_automation_ids: List[uuid.UUID] = Field(default_factory=list)


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

    def set_account_mapping(self, asset_type: str, account_id: str) -> None:
        """
        Handle SetUserAccountMappingCommand:
        - Map asset_type to account_id.
        """
        if not self.state.is_active:
            raise ValueError("Cannot modify mappings for inactive user.")

        if not asset_type or not account_id:
            raise ValueError("Asset type and account ID are required.")

        # Check if mapping already exists and is the same
        if self.state.account_mappings.get(asset_type) == account_id:
            return  # No change, idempotent

        event = UserBrokerAccountMappingSet(
            user_id=self.id,
            asset_type=asset_type,
            account_id=account_id
        )
        self._apply_and_record(event)

    def add_connected_broker(self, broker_id: str, environment: str) -> None:
        """
        Handle AddUserConnectedBrokerCommand:
        - Add broker session identifier to state.
        """
        if not self.state.is_active:
            raise ValueError("Cannot add brokers for inactive user.")

        if not broker_id or not environment:
            raise ValueError("Broker ID and environment are required.")

        key = f"{broker_id}:{environment}"
        if key in self.state.connected_brokers:
            return  # Already connected, idempotent

        event = UserConnectedBrokerAdded(
            user_id=self.id,
            broker_id=broker_id,
            environment=environment
        )
        self._apply_and_record(event)

    def remove_connected_broker(self, broker_id: str, environment: str) -> None:
        """
        Handle RemoveUserConnectedBrokerCommand:
        - Remove broker session identifier from the state.
        """
        if not broker_id or not environment:
            raise ValueError("Broker ID and environment are required.")

        key = f"{broker_id}:{environment}"
        if key not in self.state.connected_brokers:
            return  # Not connected, idempotent

        event = UserConnectedBrokerRemoved(
            user_id=self.id,
            broker_id=broker_id,
            environment=environment
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
        elif isinstance(event, UserBrokerAccountMappingSet):
            self._on_account_mapping_set(event)
        elif isinstance(event, UserConnectedBrokerAdded):
            self._on_broker_added(event)
        elif isinstance(event, UserConnectedBrokerRemoved):
            self._on_broker_removed(event)

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

    def _on_account_mapping_set(self, event: UserBrokerAccountMappingSet) -> None:
        self.state.account_mappings[event.asset_type] = event.account_id

    def _on_broker_added(self, event: UserConnectedBrokerAdded) -> None:
        key = f"{event.broker_id}:{event.environment}"
        if key not in self.state.connected_brokers:
            self.state.connected_brokers.append(key)

    def _on_broker_removed(self, event: UserConnectedBrokerRemoved) -> None:
        key = f"{event.broker_id}:{event.environment}"
        if key in self.state.connected_brokers:
            self.state.connected_brokers.remove(key)

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
            "account_mappings": self.state.account_mappings,
            "connected_brokers": self.state.connected_brokers,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "last_password_change": self.state.last_password_change.isoformat() if self.state.last_password_change else None,
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
        self.state.account_mappings = snapshot_data.get("account_mappings", {})
        self.state.connected_brokers = snapshot_data.get("connected_brokers", [])

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