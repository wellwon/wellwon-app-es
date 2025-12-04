# =============================================================================
# File: app/customs/organization/events.py
# Description: Domain events for CommonOrganization aggregate
# =============================================================================

from __future__ import annotations

from typing import Literal, Optional, Dict, Any
from pydantic import Field
import uuid
from datetime import datetime, timezone

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event


# =============================================================================
# Organization Lifecycle Events
# =============================================================================

@domain_event(category="customs")
class CommonOrgCreated(BaseEvent):
    """Emitted when a new common organization is created."""
    event_type: Literal["CommonOrgCreated"] = "CommonOrgCreated"
    org_id: uuid.UUID
    user_id: uuid.UUID
    org_name: str
    short_name: Optional[str] = None
    org_type: int  # OrganizationType value
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    kontur_org_id: Optional[str] = None
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    from_registry: bool = False  # True if created with EGRUL data
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CommonOrgUpdated(BaseEvent):
    """Emitted when organization details are updated."""
    event_type: Literal["CommonOrgUpdated"] = "CommonOrgUpdated"
    org_id: uuid.UUID
    user_id: uuid.UUID
    org_name: Optional[str] = None
    short_name: Optional[str] = None
    org_type: Optional[int] = None
    kpp: Optional[str] = None
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CommonOrgSyncedFromRegistry(BaseEvent):
    """Emitted when organization is synced from EGRUL/EGRIP registry."""
    event_type: Literal["CommonOrgSyncedFromRegistry"] = "CommonOrgSyncedFromRegistry"
    org_id: uuid.UUID
    inn: str
    org_name: str
    short_name: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    kontur_org_id: Optional[str] = None
    legal_address: Optional[Dict[str, Any]] = None
    synced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CommonOrgDeleted(BaseEvent):
    """Emitted when organization is deleted."""
    event_type: Literal["CommonOrgDeleted"] = "CommonOrgDeleted"
    org_id: uuid.UUID
    user_id: uuid.UUID
    reason: Optional[str] = None
    deleted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CommonOrgLinkedToKontur(BaseEvent):
    """Emitted when organization is linked to Kontur."""
    event_type: Literal["CommonOrgLinkedToKontur"] = "CommonOrgLinkedToKontur"
    org_id: uuid.UUID
    kontur_org_id: str
    linked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Event Type Registry (for deserialization)
# =============================================================================

ORGANIZATION_EVENT_TYPES = {
    "CommonOrgCreated": CommonOrgCreated,
    "CommonOrgUpdated": CommonOrgUpdated,
    "CommonOrgSyncedFromRegistry": CommonOrgSyncedFromRegistry,
    "CommonOrgDeleted": CommonOrgDeleted,
    "CommonOrgLinkedToKontur": CommonOrgLinkedToKontur,
}

# =============================================================================
# EOF
# =============================================================================
