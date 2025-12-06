# =============================================================================
# File: app/customs/organization/command_handlers/org_handlers.py
# Description: Command handlers for CommonOrganization aggregate
# =============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, Any
import uuid

from app.config.logging_config import get_logger
from app.customs.organization.commands import (
    CreateCommonOrgCommand,
    UpdateCommonOrgCommand,
    SyncOrgFromRegistryCommand,
    DeleteCommonOrgCommand,
    LinkOrgToKonturCommand,
)
from app.customs.organization.aggregate import CommonOrgAggregate
from app.customs.exceptions import OrganizationNotFoundError, KonturSyncError
from app.infra.cqrs.cqrs_decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies
    from app.customs.ports.kontur_declarant_port import KonturDeclarantPort

log = get_logger("wellwon.customs.organization.handlers")

CUSTOMS_TRANSPORT_TOPIC = "transport.customs-events"


# -----------------------------------------------------------------------------
# CreateCommonOrgHandler - with optional EGRUL auto-sync
# -----------------------------------------------------------------------------
@command_handler(CreateCommonOrgCommand)
class CreateCommonOrgHandler(BaseCommandHandler):
    """
    Handles CreateCommonOrgCommand.

    Industry Standard Pattern:
    1. If INN provided and skip_registry_lookup=False -> auto-fetch from EGRUL via Kontur
    2. Pre-fill fields from registry
    3. User-provided fields override registry data
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: CreateCommonOrgCommand) -> uuid.UUID:
        log.info(f"Creating organization: {command.org_name} (INN: {command.inn})")

        # Try to fetch from EGRUL if INN provided
        registry_data: Optional[Dict[str, Any]] = None
        if command.inn and not command.skip_registry_lookup:
            registry_data = await self._fetch_from_registry(command.inn)

        # Merge: command fields override registry data
        final_data = self._merge_data(command, registry_data)

        # Create new aggregate
        org = CommonOrgAggregate(org_id=command.org_id)

        # Call aggregate command method
        org.create_organization(
            user_id=command.user_id,
            org_name=final_data["org_name"],
            org_type=command.org_type,
            short_name=final_data.get("short_name"),
            inn=command.inn,
            kpp=final_data.get("kpp"),
            ogrn=final_data.get("ogrn"),
            is_foreign=command.is_foreign,
            kontur_org_id=final_data.get("kontur_org_id"),
            legal_address=final_data.get("legal_address"),
            actual_address=command.actual_address,
            from_registry=registry_data is not None,
        )

        # Publish events
        await self.publish_events(
            aggregate=org,
            aggregate_id=command.org_id,
            command=command,
            aggregate_type="CommonOrg"
        )

        log.info(
            f"Organization created: {command.org_id} "
            f"(from_registry={registry_data is not None})"
        )
        return command.org_id

    async def _fetch_from_registry(self, inn: str) -> Optional[Dict[str, Any]]:
        """Fetch organization data from EGRUL via Kontur port."""
        try:
            kontur_org = await self._kontur.get_or_create_org_by_inn(inn)

            if kontur_org:
                return {
                    "org_name": kontur_org.org_name or "",
                    "short_name": kontur_org.short_name,
                    "kpp": kontur_org.kpp,
                    "ogrn": kontur_org.ogrn,
                    "kontur_org_id": kontur_org.id,
                    "legal_address": kontur_org.legal_address.model_dump() if kontur_org.legal_address else None,
                }

        except Exception as e:
            log.warning(f"Registry lookup failed for INN {inn}: {e}")

        return None

    def _merge_data(
        self,
        command: CreateCommonOrgCommand,
        registry_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge command data with registry data (command takes precedence)."""
        base = registry_data or {}
        return {
            "org_name": command.org_name or base.get("org_name", ""),
            "short_name": command.short_name or base.get("short_name"),
            "kpp": command.kpp or base.get("kpp"),
            "ogrn": command.ogrn or base.get("ogrn"),
            "kontur_org_id": base.get("kontur_org_id"),
            "legal_address": command.legal_address or base.get("legal_address"),
        }


# -----------------------------------------------------------------------------
# UpdateCommonOrgHandler
# -----------------------------------------------------------------------------
@command_handler(UpdateCommonOrgCommand)
class UpdateCommonOrgHandler(BaseCommandHandler):
    """Handles UpdateCommonOrgCommand."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: UpdateCommonOrgCommand) -> uuid.UUID:
        log.info(f"Updating organization: {command.org_id}")

        org = await self.load_aggregate(
            command.org_id,
            "CommonOrg",
            CommonOrgAggregate
        )

        if org.version == 0:
            raise OrganizationNotFoundError(f"Organization {command.org_id} not found")

        org.update_organization(
            user_id=command.user_id,
            org_name=command.org_name,
            short_name=command.short_name,
            org_type=command.org_type,
            kpp=command.kpp,
            legal_address=command.legal_address,
            actual_address=command.actual_address,
        )

        await self.publish_events(
            aggregate=org,
            aggregate_id=command.org_id,
            command=command,
            aggregate_type="CommonOrg"
        )

        log.info(f"Organization updated: {command.org_id}")
        return command.org_id


# -----------------------------------------------------------------------------
# SyncOrgFromRegistryHandler
# -----------------------------------------------------------------------------
@command_handler(SyncOrgFromRegistryCommand)
class SyncOrgFromRegistryHandler(BaseCommandHandler):
    """
    Handles SyncOrgFromRegistryCommand.

    Re-syncs organization from EGRUL/EGRIP registry (manual refresh).
    """

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )
        # Port injection: kontur_adapter implements KonturDeclarantPort
        self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter

    async def handle(self, command: SyncOrgFromRegistryCommand) -> uuid.UUID:
        log.info(f"Syncing organization {command.org_id} from registry (INN: {command.inn})")

        org = await self.load_aggregate(
            command.org_id,
            "CommonOrg",
            CommonOrgAggregate
        )

        if org.version == 0:
            raise OrganizationNotFoundError(f"Organization {command.org_id} not found")

        # Fetch from registry via port
        try:
            kontur_org = await self._kontur.get_or_create_common_org_by_inn(command.inn)

            if not kontur_org:
                raise KonturSyncError(f"Organization with INN {command.inn} not found in registry")

            org.sync_from_registry(
                inn=command.inn,
                org_name=kontur_org.org_name or "",
                short_name=kontur_org.short_name,
                kpp=kontur_org.kpp,
                ogrn=kontur_org.ogrn,
                kontur_org_id=kontur_org.id,
                legal_address=kontur_org.legal_address.model_dump() if kontur_org.legal_address else None,
            )

        except Exception as e:
            log.error(f"Failed to sync organization {command.org_id}: {e}")
            raise KonturSyncError(f"Failed to sync from registry: {e}")

        await self.publish_events(
            aggregate=org,
            aggregate_id=command.org_id,
            command=command,
            aggregate_type="CommonOrg"
        )

        log.info(f"Organization synced from registry: {command.org_id}")
        return command.org_id


# -----------------------------------------------------------------------------
# DeleteCommonOrgHandler
# -----------------------------------------------------------------------------
@command_handler(DeleteCommonOrgCommand)
class DeleteCommonOrgHandler(BaseCommandHandler):
    """Handles DeleteCommonOrgCommand."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: DeleteCommonOrgCommand) -> uuid.UUID:
        log.info(f"Deleting organization: {command.org_id}")

        org = await self.load_aggregate(
            command.org_id,
            "CommonOrg",
            CommonOrgAggregate
        )

        if org.version == 0:
            raise OrganizationNotFoundError(f"Organization {command.org_id} not found")

        org.delete_organization(
            user_id=command.user_id,
            reason=command.reason,
        )

        await self.publish_events(
            aggregate=org,
            aggregate_id=command.org_id,
            command=command,
            aggregate_type="CommonOrg"
        )

        log.info(f"Organization deleted: {command.org_id}")
        return command.org_id


# -----------------------------------------------------------------------------
# LinkOrgToKonturHandler
# -----------------------------------------------------------------------------
@command_handler(LinkOrgToKonturCommand)
class LinkOrgToKonturHandler(BaseCommandHandler):
    """Handles LinkOrgToKonturCommand."""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic=CUSTOMS_TRANSPORT_TOPIC,
            event_store=deps.event_store
        )

    async def handle(self, command: LinkOrgToKonturCommand) -> uuid.UUID:
        log.info(f"Linking organization {command.org_id} to Kontur: {command.kontur_org_id}")

        org = await self.load_aggregate(
            command.org_id,
            "CommonOrg",
            CommonOrgAggregate
        )

        if org.version == 0:
            raise OrganizationNotFoundError(f"Organization {command.org_id} not found")

        org.link_to_kontur(kontur_org_id=command.kontur_org_id)

        await self.publish_events(
            aggregate=org,
            aggregate_id=command.org_id,
            command=command,
            aggregate_type="CommonOrg"
        )

        log.info(f"Organization linked to Kontur: {command.org_id}")
        return command.org_id


# =============================================================================
# EOF
# =============================================================================
