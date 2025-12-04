# =============================================================================
# File: app/customs/declaration/events.py
# Description: Domain events for CustomsDeclaration aggregate
# =============================================================================

from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List
from pydantic import Field
import uuid
from datetime import datetime, timezone

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event


# =============================================================================
# SECTION: Declaration Lifecycle Events
# =============================================================================

@domain_event(category="customs")
class CustomsDeclarationCreated(BaseEvent):
    """Emitted when a new customs declaration is created."""
    event_type: Literal["CustomsDeclarationCreated"] = "CustomsDeclarationCreated"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    name: str
    declaration_type: str  # "IM", "EX", "TR"
    procedure: str  # e.g., "4000"
    customs_code: str
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CustomsDeclarationDeleted(BaseEvent):
    """Emitted when a customs declaration is deleted."""
    event_type: Literal["CustomsDeclarationDeleted"] = "CustomsDeclarationDeleted"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    reason: Optional[str] = None
    deleted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class CustomsDeclarationCopied(BaseEvent):
    """Emitted when a declaration is created as a copy from another."""
    event_type: Literal["CustomsDeclarationCopied"] = "CustomsDeclarationCopied"
    declaration_id: uuid.UUID
    source_declaration_id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    name: str
    # Copied data
    declaration_type: str
    procedure: str
    customs_code: str
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    form_data: Dict[str, Any] = Field(default_factory=dict)
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# SECTION: Form Data Events
# =============================================================================

@domain_event(category="customs")
class FormDataUpdated(BaseEvent):
    """Emitted when declaration form data is updated."""
    event_type: Literal["FormDataUpdated"] = "FormDataUpdated"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    form_data: Dict[str, Any]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class GoodsImported(BaseEvent):
    """Emitted when goods are imported into the declaration."""
    event_type: Literal["GoodsImported"] = "GoodsImported"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    goods: List[Dict[str, Any]]
    import_source: str  # "manual", "xml", "excel"
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# SECTION: Document Events
# =============================================================================

@domain_event(category="customs")
class DocumentAttached(BaseEvent):
    """Emitted when a document is attached to the declaration."""
    event_type: Literal["DocumentAttached"] = "DocumentAttached"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    document_id: str
    form_id: str
    name: str
    number: str
    date: str
    grafa44_code: str
    belongs_to_all_goods: bool = True
    file_id: Optional[str] = None
    attached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class DocumentRemoved(BaseEvent):
    """Emitted when a document is removed from the declaration."""
    event_type: Literal["DocumentRemoved"] = "DocumentRemoved"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    document_id: str
    removed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class DtsDocumentCreated(BaseEvent):
    """Emitted when a DTS (customs value) document is created."""
    event_type: Literal["DtsDocumentCreated"] = "DtsDocumentCreated"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    document_id: str
    dts_type: int  # 1=transport, 2=insurance, 3=loading
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# SECTION: Kontur Integration Events
# =============================================================================

@domain_event(category="customs")
class CustomsDeclarationSubmitted(BaseEvent):
    """
    Emitted when a declaration is submitted to Kontur.
    TRUE SAGA Pattern: Contains all enriched data needed by saga.
    """
    event_type: Literal["CustomsDeclarationSubmitted"] = "CustomsDeclarationSubmitted"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    kontur_docflow_id: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Enriched data for TRUE SAGA pattern (no queries in saga)
    form_data: Dict[str, Any] = Field(default_factory=dict)
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    organization_id: Optional[str] = None
    organization_inn: Optional[str] = None


@domain_event(category="customs")
class StatusUpdatedFromKontur(BaseEvent):
    """Emitted when declaration status is synced from Kontur."""
    event_type: Literal["StatusUpdatedFromKontur"] = "StatusUpdatedFromKontur"
    declaration_id: uuid.UUID
    kontur_docflow_id: str
    old_status: int
    new_status: int
    gtd_number: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class DeclarationRegistered(BaseEvent):
    """Emitted when customs assigns GTD number (registered status)."""
    event_type: Literal["DeclarationRegistered"] = "DeclarationRegistered"
    declaration_id: uuid.UUID
    kontur_docflow_id: str
    gtd_number: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class DeclarationReleased(BaseEvent):
    """Emitted when goods are released by customs."""
    event_type: Literal["DeclarationReleased"] = "DeclarationReleased"
    declaration_id: uuid.UUID
    kontur_docflow_id: str
    gtd_number: str
    released_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class DeclarationRejected(BaseEvent):
    """Emitted when declaration is rejected by customs."""
    event_type: Literal["DeclarationRejected"] = "DeclarationRejected"
    declaration_id: uuid.UUID
    kontur_docflow_id: str
    rejection_reason: Optional[str] = None
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class KonturSyncFailed(BaseEvent):
    """Emitted when Kontur synchronization fails."""
    event_type: Literal["KonturSyncFailed"] = "KonturSyncFailed"
    declaration_id: uuid.UUID
    kontur_docflow_id: Optional[str] = None
    error_message: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# SECTION: Organization Events
# =============================================================================

@domain_event(category="customs")
class OrganizationSet(BaseEvent):
    """Emitted when organization is set on declaration."""
    event_type: Literal["OrganizationSet"] = "OrganizationSet"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    organization_id: str
    grafa: str  # Field number (e.g., "8" for consignee)
    set_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@domain_event(category="customs")
class EmployeeSet(BaseEvent):
    """Emitted when employee (declarant) is set on declaration."""
    event_type: Literal["EmployeeSet"] = "EmployeeSet"
    declaration_id: uuid.UUID
    user_id: uuid.UUID
    employee_id: str
    set_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Event Type Registry (for deserialization)
# =============================================================================

DECLARATION_EVENT_TYPES = {
    "CustomsDeclarationCreated": CustomsDeclarationCreated,
    "CustomsDeclarationDeleted": CustomsDeclarationDeleted,
    "CustomsDeclarationCopied": CustomsDeclarationCopied,
    "FormDataUpdated": FormDataUpdated,
    "GoodsImported": GoodsImported,
    "DocumentAttached": DocumentAttached,
    "DocumentRemoved": DocumentRemoved,
    "DtsDocumentCreated": DtsDocumentCreated,
    "CustomsDeclarationSubmitted": CustomsDeclarationSubmitted,
    "StatusUpdatedFromKontur": StatusUpdatedFromKontur,
    "DeclarationRegistered": DeclarationRegistered,
    "DeclarationReleased": DeclarationReleased,
    "DeclarationRejected": DeclarationRejected,
    "KonturSyncFailed": KonturSyncFailed,
    "OrganizationSet": OrganizationSet,
    "EmployeeSet": EmployeeSet,
}

# =============================================================================
# EOF
# =============================================================================
