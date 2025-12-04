# =============================================================================
# File: app/customs/organization/aggregate.py
# Description: CommonOrganization Aggregate Root
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.config.logging_config import get_logger
from app.customs.enums import OrganizationType
from app.customs.exceptions import OrganizationNotFoundError
from app.customs.organization.events import (
    BaseEvent,
    CommonOrgCreated,
    CommonOrgUpdated,
    CommonOrgSyncedFromRegistry,
    CommonOrgDeleted,
    CommonOrgLinkedToKontur,
    ORGANIZATION_EVENT_TYPES,
)

log = get_logger("wellwon.customs.organization.aggregate")


class CommonOrgAggregateState(BaseModel):
    """
    Represents the in-memory state of a CommonOrgAggregate.
    """
    org_id: Optional[uuid.UUID] = None
    kontur_org_id: Optional[str] = None
    org_name: str = ""
    short_name: Optional[str] = None
    org_type: OrganizationType = OrganizationType.LEGAL_ENTITY
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    is_foreign: bool = False
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None


class CommonOrgAggregate:
    """
    Aggregate root for CommonOrganization entity.
    """

    def __init__(self, org_id: uuid.UUID):
        self.id: uuid.UUID = org_id
        self.version: int = 0
        self.state: CommonOrgAggregateState = CommonOrgAggregateState(org_id=org_id)
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
    def create_organization(
        self,
        user_id: uuid.UUID,
        org_name: str,
        org_type: OrganizationType,
        short_name: Optional[str] = None,
        inn: Optional[str] = None,
        kpp: Optional[str] = None,
        ogrn: Optional[str] = None,
        is_foreign: bool = False,
        kontur_org_id: Optional[str] = None,
        legal_address: Optional[Dict[str, Any]] = None,
        actual_address: Optional[Dict[str, Any]] = None,
        from_registry: bool = False,
    ) -> None:
        """Create a new organization."""
        if self.version > 0:
            raise ValueError("Organization already exists.")

        if not org_name:
            raise ValueError("Organization name is required.")

        event = CommonOrgCreated(
            org_id=self.id,
            user_id=user_id,
            org_name=org_name,
            short_name=short_name,
            org_type=org_type.value,
            inn=inn,
            kpp=kpp,
            ogrn=ogrn,
            is_foreign=is_foreign,
            kontur_org_id=kontur_org_id,
            legal_address=legal_address,
            actual_address=actual_address,
            from_registry=from_registry,
        )
        self._apply_and_record(event)

    def update_organization(
        self,
        user_id: uuid.UUID,
        org_name: Optional[str] = None,
        short_name: Optional[str] = None,
        org_type: Optional[OrganizationType] = None,
        kpp: Optional[str] = None,
        legal_address: Optional[Dict[str, Any]] = None,
        actual_address: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update organization details."""
        if self.state.is_deleted:
            raise ValueError("Cannot update deleted organization.")

        event = CommonOrgUpdated(
            org_id=self.id,
            user_id=user_id,
            org_name=org_name,
            short_name=short_name,
            org_type=org_type.value if org_type else None,
            kpp=kpp,
            legal_address=legal_address,
            actual_address=actual_address,
        )
        self._apply_and_record(event)

    def sync_from_registry(
        self,
        inn: str,
        org_name: str,
        short_name: Optional[str] = None,
        kpp: Optional[str] = None,
        ogrn: Optional[str] = None,
        kontur_org_id: Optional[str] = None,
        legal_address: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Sync organization data from EGRUL/EGRIP registry."""
        if self.state.is_deleted:
            raise ValueError("Cannot sync deleted organization.")

        event = CommonOrgSyncedFromRegistry(
            org_id=self.id,
            inn=inn,
            org_name=org_name,
            short_name=short_name,
            kpp=kpp,
            ogrn=ogrn,
            kontur_org_id=kontur_org_id,
            legal_address=legal_address,
        )
        self._apply_and_record(event)

    def delete_organization(
        self,
        user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> None:
        """Delete organization (soft delete)."""
        if self.state.is_deleted:
            return  # Idempotent

        event = CommonOrgDeleted(
            org_id=self.id,
            user_id=user_id,
            reason=reason,
        )
        self._apply_and_record(event)

    def link_to_kontur(self, kontur_org_id: str) -> None:
        """Link organization to Kontur after creation."""
        if self.state.is_deleted:
            raise ValueError("Cannot link deleted organization.")

        event = CommonOrgLinkedToKontur(
            org_id=self.id,
            kontur_org_id=kontur_org_id,
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Internal Event Application
    # -------------------------------------------------------------------------
    def _apply_and_record(self, event: BaseEvent) -> None:
        """Apply event to state and record it for later persistence."""
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    def _apply(self, event: BaseEvent) -> None:
        """Dispatch event to the appropriate state update method."""
        if isinstance(event, CommonOrgCreated):
            self._on_org_created(event)
        elif isinstance(event, CommonOrgUpdated):
            self._on_org_updated(event)
        elif isinstance(event, CommonOrgSyncedFromRegistry):
            self._on_org_synced(event)
        elif isinstance(event, CommonOrgDeleted):
            self._on_org_deleted(event)
        elif isinstance(event, CommonOrgLinkedToKontur):
            self._on_org_linked(event)

    def _on_org_created(self, event: CommonOrgCreated) -> None:
        self.state.org_id = event.org_id
        self.state.org_name = event.org_name
        self.state.short_name = event.short_name
        self.state.org_type = OrganizationType(event.org_type)
        self.state.inn = event.inn
        self.state.kpp = event.kpp
        self.state.ogrn = event.ogrn
        self.state.is_foreign = event.is_foreign
        self.state.kontur_org_id = event.kontur_org_id
        self.state.legal_address = event.legal_address
        self.state.actual_address = event.actual_address
        self.state.created_at = event.created_at
        self.state.updated_at = event.created_at

    def _on_org_updated(self, event: CommonOrgUpdated) -> None:
        if event.org_name is not None:
            self.state.org_name = event.org_name
        if event.short_name is not None:
            self.state.short_name = event.short_name
        if event.org_type is not None:
            self.state.org_type = OrganizationType(event.org_type)
        if event.kpp is not None:
            self.state.kpp = event.kpp
        if event.legal_address is not None:
            self.state.legal_address = event.legal_address
        if event.actual_address is not None:
            self.state.actual_address = event.actual_address
        self.state.updated_at = event.updated_at

    def _on_org_synced(self, event: CommonOrgSyncedFromRegistry) -> None:
        self.state.inn = event.inn
        self.state.org_name = event.org_name
        if event.short_name:
            self.state.short_name = event.short_name
        if event.kpp:
            self.state.kpp = event.kpp
        if event.ogrn:
            self.state.ogrn = event.ogrn
        if event.kontur_org_id:
            self.state.kontur_org_id = event.kontur_org_id
        if event.legal_address:
            self.state.legal_address = event.legal_address
        self.state.synced_at = event.synced_at
        self.state.updated_at = event.synced_at

    def _on_org_deleted(self, event: CommonOrgDeleted) -> None:
        self.state.is_deleted = True
        self.state.deleted_at = event.deleted_at
        self.state.updated_at = event.deleted_at

    def _on_org_linked(self, event: CommonOrgLinkedToKontur) -> None:
        self.state.kontur_org_id = event.kontur_org_id
        self.state.updated_at = event.linked_at

    # -------------------------------------------------------------------------
    # Snapshot Support
    # -------------------------------------------------------------------------
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state."""
        return {
            "org_id": str(self.state.org_id) if self.state.org_id else None,
            "kontur_org_id": self.state.kontur_org_id,
            "org_name": self.state.org_name,
            "short_name": self.state.short_name,
            "org_type": self.state.org_type.value,
            "inn": self.state.inn,
            "kpp": self.state.kpp,
            "ogrn": self.state.ogrn,
            "is_foreign": self.state.is_foreign,
            "legal_address": self.state.legal_address,
            "actual_address": self.state.actual_address,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "updated_at": self.state.updated_at.isoformat() if self.state.updated_at else None,
            "synced_at": self.state.synced_at.isoformat() if self.state.synced_at else None,
            "is_deleted": self.state.is_deleted,
            "deleted_at": self.state.deleted_at.isoformat() if self.state.deleted_at else None,
            "version": self.version,
        }

    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore aggregate state from a snapshot."""
        self.state.org_id = uuid.UUID(snapshot_data["org_id"]) if snapshot_data.get("org_id") else None
        self.state.kontur_org_id = snapshot_data.get("kontur_org_id")
        self.state.org_name = snapshot_data.get("org_name", "")
        self.state.short_name = snapshot_data.get("short_name")
        self.state.org_type = OrganizationType(snapshot_data.get("org_type", 0))
        self.state.inn = snapshot_data.get("inn")
        self.state.kpp = snapshot_data.get("kpp")
        self.state.ogrn = snapshot_data.get("ogrn")
        self.state.is_foreign = snapshot_data.get("is_foreign", False)
        self.state.legal_address = snapshot_data.get("legal_address")
        self.state.actual_address = snapshot_data.get("actual_address")
        self.state.is_deleted = snapshot_data.get("is_deleted", False)

        if snapshot_data.get("created_at"):
            self.state.created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if snapshot_data.get("updated_at"):
            self.state.updated_at = datetime.fromisoformat(snapshot_data["updated_at"])
        if snapshot_data.get("synced_at"):
            self.state.synced_at = datetime.fromisoformat(snapshot_data["synced_at"])
        if snapshot_data.get("deleted_at"):
            self.state.deleted_at = datetime.fromisoformat(snapshot_data["deleted_at"])

        self.version = snapshot_data.get("version", 0)

    @classmethod
    def replay_from_events(
        cls,
        org_id: uuid.UUID,
        events: List[BaseEvent],
        snapshot: Optional[Any] = None
    ) -> CommonOrgAggregate:
        """Reconstruct an aggregate by applying past events."""
        from app.infra.event_store.event_envelope import EventEnvelope

        agg = cls(org_id)

        if snapshot is not None:
            agg.restore_from_snapshot(snapshot.state)
            agg.version = snapshot.version
            log.debug(f"Restored org {org_id} from snapshot at version {snapshot.version}")

        for evt in events:
            if isinstance(evt, EventEnvelope):
                event_obj = evt.to_event_object()
                if event_obj is None:
                    event_class = ORGANIZATION_EVENT_TYPES.get(evt.event_type)
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
                if evt.aggregate_version:
                    agg.version = evt.aggregate_version
                else:
                    agg.version += 1
            else:
                agg._apply(evt)
                agg.version += 1

        agg.mark_events_committed()
        return agg


# =============================================================================
# EOF
# =============================================================================
