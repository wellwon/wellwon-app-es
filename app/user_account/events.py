# =============================================================================
# File: app/user_account/events.py 
# Description: Domain events for User operations in TradeCore.
# =============================================================================

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

from app.infra.event_bus.event_decorators import domain_event

# =============================================================================
# SECTION: Base Event Contract (shared for all events)
# =============================================================================

class BaseEvent(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str  # Each subclass sets its Literal value
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    model_config = {"from_attributes": True}

# =============================================================================
# SECTION: User Lifecycle and Authentication Events
# =============================================================================

@domain_event(category="domain")
class UserAccountCreated(BaseEvent):
    event_type: Literal["UserAccountCreated"] = "UserAccountCreated"
    user_id: uuid.UUID
    username: str
    email: str
    role: str
    hashed_password: str
    hashed_secret: str

@domain_event(category="domain")
class UserPasswordChanged(BaseEvent):
    event_type: Literal["UserPasswordChanged"] = "UserPasswordChanged"
    user_id: uuid.UUID
    new_hashed_password: str

@domain_event(category="domain")
class UserPasswordResetViaSecret(BaseEvent):
    event_type: Literal["UserPasswordResetViaSecret"] = "UserPasswordResetViaSecret"
    user_id: uuid.UUID
    new_hashed_password: str

@domain_event(category="domain")
class UserAuthenticationSucceeded(BaseEvent):
    event_type: Literal["UserAuthenticationSucceeded"] = "UserAuthenticationSucceeded"
    user_id: uuid.UUID
    username: str
    role: str
    login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@domain_event(category="domain")
class UserLoggedOut(BaseEvent):
    event_type: Literal["UserLoggedOut"] = "UserLoggedOut"
    user_id: uuid.UUID
    session_id: Optional[str] = None
    logout_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@domain_event(category="domain")
class UserAuthenticationFailed(BaseEvent):
    event_type: Literal["UserAuthenticationFailed"] = "UserAuthenticationFailed"
    username_attempted: str
    reason: str
    attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@domain_event(category="domain")
class UserAccountDeleted(BaseEvent):
    event_type: Literal["UserAccountDeleted"] = "UserAccountDeleted"
    user_id: uuid.UUID
    reason: Optional[str] = Field(default=None, description="Reason for deletion")
    grace_period: Optional[int] = Field(default=0, description="Grace period in seconds before hard-delete")
    has_virtual_broker: bool = Field(default=False, description="Whether user has virtual broker connections")
    # TRUE SAGA Pattern: Enriched event data (eliminates query_bus dependency in saga)
    owned_connection_ids: list[uuid.UUID] = Field(default_factory=list, description="Broker connection IDs owned by this user")
    owned_account_ids: list[uuid.UUID] = Field(default_factory=list, description="Broker account IDs owned by this user")
    owned_automation_ids: list[uuid.UUID] = Field(default_factory=list, description="Automation IDs owned by this user")

@domain_event(category="domain")
class UserEmailVerified(BaseEvent):
    event_type: Literal["UserEmailVerified"] = "UserEmailVerified"
    user_id: uuid.UUID

# =============================================================================
# SECTION: User Runtime State Events
# =============================================================================

@domain_event(category="domain")
class UserBrokerAccountMappingSet(BaseEvent):
    event_type: Literal["UserBrokerAccountMappingSet"] = "UserBrokerAccountMappingSet"
    user_id: uuid.UUID
    asset_type: str
    account_id: str

@domain_event(category="domain")
class UserConnectedBrokerAdded(BaseEvent):
    event_type: Literal["UserConnectedBrokerAdded"] = "UserConnectedBrokerAdded"
    user_id: uuid.UUID
    broker_id: str
    environment: str

@domain_event(category="domain")
class UserConnectedBrokerRemoved(BaseEvent):
    event_type: Literal["UserConnectedBrokerRemoved"] = "UserConnectedBrokerRemoved"
    user_id: uuid.UUID
    broker_id: str
    environment: str

# =============================================================================
# EOF
# =============================================================================