# =============================================================================
# File: app/customs/organization/commands.py
# Description: Domain commands for CommonOrganization aggregate
# =============================================================================

from __future__ import annotations

from pydantic import Field
from uuid import UUID
from typing import Optional, Dict, Any

from app.infra.cqrs.command_bus import Command
from app.customs.enums import OrganizationType
from app.utils.uuid_utils import generate_uuid


# =============================================================================
# Organization Lifecycle Commands
# =============================================================================

class CreateCommonOrgCommand(Command):
    """
    Command to create a new common organization.

    If INN is provided, will auto-fetch from EGRUL via Kontur (optional sync).
    User-provided fields override registry data.
    """
    org_id: UUID = Field(default_factory=generate_uuid)
    user_id: UUID
    org_name: str = Field(..., min_length=1, max_length=255)
    short_name: Optional[str] = Field(None, max_length=100)
    org_type: OrganizationType = OrganizationType.LEGAL_ENTITY
    inn: Optional[str] = Field(None, max_length=12)
    kpp: Optional[str] = Field(None, max_length=9)
    ogrn: Optional[str] = Field(None, max_length=15)
    is_foreign: bool = False
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None
    # If True, skip registry lookup
    skip_registry_lookup: bool = False


class UpdateCommonOrgCommand(Command):
    """Command to update organization details."""
    org_id: UUID
    user_id: UUID
    org_name: Optional[str] = Field(None, max_length=255)
    short_name: Optional[str] = Field(None, max_length=100)
    org_type: Optional[OrganizationType] = None
    kpp: Optional[str] = Field(None, max_length=9)
    legal_address: Optional[Dict[str, Any]] = None
    actual_address: Optional[Dict[str, Any]] = None


class SyncOrgFromRegistryCommand(Command):
    """
    Command to sync organization from EGRUL/EGRIP registry.

    Fetches latest data from registry and updates organization.
    """
    org_id: UUID
    user_id: UUID
    inn: str = Field(..., min_length=10, max_length=12)


class DeleteCommonOrgCommand(Command):
    """Command to delete organization."""
    org_id: UUID
    user_id: UUID
    reason: Optional[str] = None


class LinkOrgToKonturCommand(Command):
    """Command to link organization to Kontur (after creation in Kontur)."""
    org_id: UUID
    user_id: UUID
    kontur_org_id: str


# =============================================================================
# EOF
# =============================================================================
