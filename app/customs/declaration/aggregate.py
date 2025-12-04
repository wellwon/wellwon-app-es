# =============================================================================
# File: app/customs/declaration/aggregate.py
# Description: CustomsDeclaration Aggregate Root
# Responsibilities:
#  - Maintain internal state for customs declaration entities via event sourcing.
#  - Validate commands and generate corresponding Domain Events.
#  - Apply events to mutate aggregate state and track uncommitted events.
#  - Support snapshot creation and restoration for event store optimization.
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.config.logging_config import get_logger
from app.customs.enums import DeclarationType, DocflowStatus
from app.customs.exceptions import (
    InvalidDeclarationStatusError,
    DeclarationAlreadySubmittedError,
    DeclarationNotSubmittedError,
)
from app.customs.declaration.events import (
    BaseEvent,
    CustomsDeclarationCreated,
    CustomsDeclarationDeleted,
    CustomsDeclarationCopied,
    FormDataUpdated,
    GoodsImported,
    DocumentAttached,
    DocumentRemoved,
    DtsDocumentCreated,
    CustomsDeclarationSubmitted,
    StatusUpdatedFromKontur,
    DeclarationRegistered,
    DeclarationReleased,
    DeclarationRejected,
    KonturSyncFailed,
    OrganizationSet,
    EmployeeSet,
    DECLARATION_EVENT_TYPES,
)

log = get_logger("wellwon.customs.declaration.aggregate")


class CustomsDeclarationAggregateState(BaseModel):
    """
    Represents the in-memory state of a CustomsDeclarationAggregate.
    Fields correspond to properties maintained in the write model.
    """
    declaration_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None

    # Kontur integration
    kontur_docflow_id: Optional[str] = None
    gtd_number: Optional[str] = None

    # Declaration details
    name: str = ""
    declaration_type: DeclarationType = DeclarationType.IMPORT
    procedure: str = "4000"
    customs_code: str = ""
    status: DocflowStatus = DocflowStatus.DRAFT

    # Organization references (by ID - Reference by ID pattern)
    organization_id: Optional[str] = None
    employee_id: Optional[str] = None
    declarant_inn: Optional[str] = None

    # Form data (JSONB in read model)
    form_data: Dict[str, Any] = Field(default_factory=dict)

    # Documents (Value Objects stored as dicts)
    documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Goods items
    goods: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # Soft delete flag
    is_deleted: bool = False


class CustomsDeclarationAggregate:
    """
    Aggregate root for CustomsDeclaration entity.
    - Commands mutate state by emitting events.
    - Events are applied to update internal state.
    - Supports snapshots for event store optimization.
    """

    def __init__(self, declaration_id: uuid.UUID):
        self.id: uuid.UUID = declaration_id
        self.version: int = 0
        self.state: CustomsDeclarationAggregateState = CustomsDeclarationAggregateState(
            declaration_id=declaration_id
        )
        self._uncommitted_events: List[BaseEvent] = []

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Return events not yet persisted to the event store."""
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        """Clear the list of uncommitted events after they are persisted."""
        self._uncommitted_events.clear()

    # -------------------------------------------------------------------------
    # Command Handlers - Lifecycle
    # -------------------------------------------------------------------------
    def create_declaration(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        name: str,
        declaration_type: DeclarationType,
        procedure: str,
        customs_code: str,
        organization_id: Optional[str] = None,
        employee_id: Optional[str] = None,
    ) -> None:
        """
        Handle CreateCustomsDeclarationCommand.
        Validate that aggregate is new (version == 0).
        Emit CustomsDeclarationCreated event.
        """
        if self.version > 0:
            raise ValueError("Declaration already exists.")

        if not name:
            raise ValueError("Declaration name is required.")

        if not customs_code:
            raise ValueError("Customs code is required.")

        event = CustomsDeclarationCreated(
            declaration_id=self.id,
            user_id=user_id,
            company_id=company_id,
            name=name,
            declaration_type=declaration_type.value,
            procedure=procedure,
            customs_code=customs_code,
            organization_id=organization_id,
            employee_id=employee_id,
        )
        self._apply_and_record(event)

    def delete_declaration(self, user_id: uuid.UUID, reason: Optional[str] = None) -> None:
        """
        Handle DeleteCustomsDeclarationCommand.
        Cannot delete if already submitted or released.
        """
        if self.state.is_deleted:
            return  # Idempotent

        if self.state.status in (DocflowStatus.SENT, DocflowStatus.REGISTERED, DocflowStatus.RELEASED):
            raise InvalidDeclarationStatusError(
                f"Cannot delete declaration in status {self.state.status.name}"
            )

        event = CustomsDeclarationDeleted(
            declaration_id=self.id,
            user_id=user_id,
            reason=reason,
        )
        self._apply_and_record(event)

    def create_as_copy(
        self,
        source_declaration_id: uuid.UUID,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        name: str,
        declaration_type: DeclarationType,
        procedure: str,
        customs_code: str,
        organization_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        form_data: Optional[Dict[str, Any]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Handle CopyCustomsDeclarationCommand.
        Create declaration as a copy from source.
        """
        if self.version > 0:
            raise ValueError("Declaration already exists.")

        event = CustomsDeclarationCopied(
            declaration_id=self.id,
            source_declaration_id=source_declaration_id,
            user_id=user_id,
            company_id=company_id,
            name=name,
            declaration_type=declaration_type.value,
            procedure=procedure,
            customs_code=customs_code,
            organization_id=organization_id,
            employee_id=employee_id,
            form_data=form_data or {},
            documents=documents or [],
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Command Handlers - Form Data
    # -------------------------------------------------------------------------
    def update_form_data(self, user_id: uuid.UUID, form_data: Dict[str, Any]) -> None:
        """
        Handle UpdateFormDataCommand.
        Cannot update if already submitted.
        """
        self._validate_can_modify()

        event = FormDataUpdated(
            declaration_id=self.id,
            user_id=user_id,
            form_data=form_data,
        )
        self._apply_and_record(event)

    def import_goods(
        self,
        user_id: uuid.UUID,
        goods: List[Dict[str, Any]],
        import_source: str,
        replace_existing: bool = False,
    ) -> None:
        """
        Handle ImportGoodsCommand.
        Import goods items into declaration.
        """
        self._validate_can_modify()

        event = GoodsImported(
            declaration_id=self.id,
            user_id=user_id,
            goods=goods,
            import_source=import_source,
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Command Handlers - Documents
    # -------------------------------------------------------------------------
    def attach_document(
        self,
        user_id: uuid.UUID,
        document_id: str,
        form_id: str,
        name: str,
        number: str,
        date: str,
        grafa44_code: str,
        belongs_to_all_goods: bool = True,
        file_id: Optional[str] = None,
    ) -> None:
        """
        Handle AttachDocumentCommand.
        Attach a document to the declaration.
        """
        self._validate_can_modify()

        event = DocumentAttached(
            declaration_id=self.id,
            user_id=user_id,
            document_id=document_id,
            form_id=form_id,
            name=name,
            number=number,
            date=date,
            grafa44_code=grafa44_code,
            belongs_to_all_goods=belongs_to_all_goods,
            file_id=file_id,
        )
        self._apply_and_record(event)

    def remove_document(self, user_id: uuid.UUID, document_id: str) -> None:
        """
        Handle RemoveDocumentCommand.
        Remove a document from the declaration.
        """
        self._validate_can_modify()

        # Verify document exists
        doc_exists = any(d.get("document_id") == document_id for d in self.state.documents)
        if not doc_exists:
            raise ValueError(f"Document {document_id} not found in declaration")

        event = DocumentRemoved(
            declaration_id=self.id,
            user_id=user_id,
            document_id=document_id,
        )
        self._apply_and_record(event)

    def attach_dts_document(
        self,
        user_id: uuid.UUID,
        document_id: str,
        dts_type: int,
    ) -> None:
        """
        Handle CreateDtsCommand result.
        Attach DTS document created via Kontur calculator.
        """
        self._validate_is_submitted()

        event = DtsDocumentCreated(
            declaration_id=self.id,
            user_id=user_id,
            document_id=document_id,
            dts_type=dts_type,
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Command Handlers - Kontur Integration
    # -------------------------------------------------------------------------
    def submit_to_kontur(
        self,
        user_id: uuid.UUID,
        kontur_docflow_id: str,
        form_data: Optional[Dict[str, Any]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        organization_id: Optional[str] = None,
        organization_inn: Optional[str] = None,
    ) -> None:
        """
        Handle SubmitToKonturCommand.
        Submit declaration to Kontur and emit enriched event for saga.
        TRUE SAGA Pattern: Event contains all data needed by saga.
        """
        if self.state.kontur_docflow_id:
            raise DeclarationAlreadySubmittedError(
                f"Declaration already submitted with docflow ID: {self.state.kontur_docflow_id}"
            )

        event = CustomsDeclarationSubmitted(
            declaration_id=self.id,
            user_id=user_id,
            kontur_docflow_id=kontur_docflow_id,
            form_data=form_data or self.state.form_data,
            documents=documents or self.state.documents,
            organization_id=organization_id or self.state.organization_id,
            organization_inn=organization_inn,
        )
        self._apply_and_record(event)

    def update_status_from_kontur(
        self,
        kontur_docflow_id: str,
        new_status: DocflowStatus,
        gtd_number: Optional[str] = None,
    ) -> None:
        """
        Handle SyncStatusFromKonturCommand.
        Update status based on Kontur sync.
        """
        self._validate_is_submitted()

        if self.state.status == new_status:
            return  # Idempotent

        old_status = self.state.status

        event = StatusUpdatedFromKontur(
            declaration_id=self.id,
            kontur_docflow_id=kontur_docflow_id,
            old_status=old_status.value,
            new_status=new_status.value,
            gtd_number=gtd_number,
        )
        self._apply_and_record(event)

        # Emit specific events for important status changes
        if new_status == DocflowStatus.REGISTERED and gtd_number:
            reg_event = DeclarationRegistered(
                declaration_id=self.id,
                kontur_docflow_id=kontur_docflow_id,
                gtd_number=gtd_number,
            )
            self._apply_and_record(reg_event)

        elif new_status == DocflowStatus.RELEASED:
            rel_event = DeclarationReleased(
                declaration_id=self.id,
                kontur_docflow_id=kontur_docflow_id,
                gtd_number=gtd_number or self.state.gtd_number or "",
            )
            self._apply_and_record(rel_event)

        elif new_status == DocflowStatus.REJECTED:
            rej_event = DeclarationRejected(
                declaration_id=self.id,
                kontur_docflow_id=kontur_docflow_id,
            )
            self._apply_and_record(rej_event)

    def mark_sync_failed(
        self,
        error_message: str,
        kontur_docflow_id: Optional[str] = None,
    ) -> None:
        """
        Record Kontur sync failure for audit/debugging.
        """
        event = KonturSyncFailed(
            declaration_id=self.id,
            kontur_docflow_id=kontur_docflow_id or self.state.kontur_docflow_id,
            error_message=error_message,
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Command Handlers - Organization
    # -------------------------------------------------------------------------
    def set_organization(
        self,
        user_id: uuid.UUID,
        organization_id: str,
        grafa: str = "8",
    ) -> None:
        """
        Handle SetOrganizationCommand.
        Set organization on declaration form.
        """
        self._validate_can_modify()

        event = OrganizationSet(
            declaration_id=self.id,
            user_id=user_id,
            organization_id=organization_id,
            grafa=grafa,
        )
        self._apply_and_record(event)

    def set_employee(self, user_id: uuid.UUID, employee_id: str) -> None:
        """
        Handle SetEmployeeCommand.
        Set employee (declarant) on declaration.
        """
        self._validate_can_modify()

        event = EmployeeSet(
            declaration_id=self.id,
            user_id=user_id,
            employee_id=employee_id,
        )
        self._apply_and_record(event)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------
    def _validate_can_modify(self) -> None:
        """Validate that declaration can be modified."""
        if self.state.is_deleted:
            raise InvalidDeclarationStatusError("Cannot modify deleted declaration")

        if self.state.status != DocflowStatus.DRAFT:
            raise InvalidDeclarationStatusError(
                f"Cannot modify declaration in status {self.state.status.name}. "
                f"Only DRAFT declarations can be modified."
            )

    def _validate_is_submitted(self) -> None:
        """Validate that declaration is submitted to Kontur."""
        if not self.state.kontur_docflow_id:
            raise DeclarationNotSubmittedError(
                "Declaration has not been submitted to Kontur yet"
            )

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
        if isinstance(event, CustomsDeclarationCreated):
            self._on_declaration_created(event)
        elif isinstance(event, CustomsDeclarationDeleted):
            self._on_declaration_deleted(event)
        elif isinstance(event, CustomsDeclarationCopied):
            self._on_declaration_copied(event)
        elif isinstance(event, FormDataUpdated):
            self._on_form_data_updated(event)
        elif isinstance(event, GoodsImported):
            self._on_goods_imported(event)
        elif isinstance(event, DocumentAttached):
            self._on_document_attached(event)
        elif isinstance(event, DocumentRemoved):
            self._on_document_removed(event)
        elif isinstance(event, DtsDocumentCreated):
            self._on_dts_document_created(event)
        elif isinstance(event, CustomsDeclarationSubmitted):
            self._on_declaration_submitted(event)
        elif isinstance(event, StatusUpdatedFromKontur):
            self._on_status_updated(event)
        elif isinstance(event, DeclarationRegistered):
            self._on_declaration_registered(event)
        elif isinstance(event, DeclarationReleased):
            self._on_declaration_released(event)
        elif isinstance(event, DeclarationRejected):
            self._on_declaration_rejected(event)
        elif isinstance(event, OrganizationSet):
            self._on_organization_set(event)
        elif isinstance(event, EmployeeSet):
            self._on_employee_set(event)
        # KonturSyncFailed doesn't change state, just recorded for audit

    # -------------------------------------------------------------------------
    # State Update Methods
    # -------------------------------------------------------------------------
    def _on_declaration_created(self, event: CustomsDeclarationCreated) -> None:
        self.state.declaration_id = event.declaration_id
        self.state.user_id = event.user_id
        self.state.company_id = event.company_id
        self.state.name = event.name
        self.state.declaration_type = DeclarationType(event.declaration_type)
        self.state.procedure = event.procedure
        self.state.customs_code = event.customs_code
        self.state.organization_id = event.organization_id
        self.state.employee_id = event.employee_id
        self.state.status = DocflowStatus.DRAFT
        self.state.created_at = event.created_at
        self.state.updated_at = event.created_at

    def _on_declaration_deleted(self, event: CustomsDeclarationDeleted) -> None:
        self.state.is_deleted = True
        self.state.deleted_at = event.deleted_at
        self.state.updated_at = event.deleted_at

    def _on_declaration_copied(self, event: CustomsDeclarationCopied) -> None:
        self.state.declaration_id = event.declaration_id
        self.state.user_id = event.user_id
        self.state.company_id = event.company_id
        self.state.name = event.name
        self.state.declaration_type = DeclarationType(event.declaration_type)
        self.state.procedure = event.procedure
        self.state.customs_code = event.customs_code
        self.state.organization_id = event.organization_id
        self.state.employee_id = event.employee_id
        self.state.form_data = event.form_data
        self.state.documents = event.documents
        self.state.status = DocflowStatus.DRAFT
        self.state.created_at = event.created_at
        self.state.updated_at = event.created_at

    def _on_form_data_updated(self, event: FormDataUpdated) -> None:
        # Merge form data
        self.state.form_data.update(event.form_data)
        self.state.updated_at = event.updated_at

    def _on_goods_imported(self, event: GoodsImported) -> None:
        # Append goods (replace logic handled in command handler if needed)
        self.state.goods.extend(event.goods)
        self.state.updated_at = event.imported_at

    def _on_document_attached(self, event: DocumentAttached) -> None:
        doc = {
            "document_id": event.document_id,
            "form_id": event.form_id,
            "name": event.name,
            "number": event.number,
            "date": event.date,
            "grafa44_code": event.grafa44_code,
            "belongs_to_all_goods": event.belongs_to_all_goods,
            "file_id": event.file_id,
        }
        self.state.documents.append(doc)
        self.state.updated_at = event.attached_at

    def _on_document_removed(self, event: DocumentRemoved) -> None:
        self.state.documents = [
            d for d in self.state.documents
            if d.get("document_id") != event.document_id
        ]
        self.state.updated_at = event.removed_at

    def _on_dts_document_created(self, event: DtsDocumentCreated) -> None:
        doc = {
            "document_id": event.document_id,
            "form_id": "dts",
            "name": f"DTS Type {event.dts_type}",
            "dts_type": event.dts_type,
        }
        self.state.documents.append(doc)
        self.state.updated_at = event.created_at

    def _on_declaration_submitted(self, event: CustomsDeclarationSubmitted) -> None:
        self.state.kontur_docflow_id = event.kontur_docflow_id
        self.state.status = DocflowStatus.SENT
        self.state.submitted_at = event.submitted_at
        self.state.updated_at = event.submitted_at

    def _on_status_updated(self, event: StatusUpdatedFromKontur) -> None:
        self.state.status = DocflowStatus(event.new_status)
        if event.gtd_number:
            self.state.gtd_number = event.gtd_number
        self.state.updated_at = event.updated_at

    def _on_declaration_registered(self, event: DeclarationRegistered) -> None:
        self.state.gtd_number = event.gtd_number
        self.state.status = DocflowStatus.REGISTERED
        self.state.updated_at = event.registered_at

    def _on_declaration_released(self, event: DeclarationReleased) -> None:
        self.state.status = DocflowStatus.RELEASED
        self.state.updated_at = event.released_at

    def _on_declaration_rejected(self, event: DeclarationRejected) -> None:
        self.state.status = DocflowStatus.REJECTED
        self.state.updated_at = event.rejected_at

    def _on_organization_set(self, event: OrganizationSet) -> None:
        self.state.organization_id = event.organization_id
        self.state.updated_at = event.set_at

    def _on_employee_set(self, event: EmployeeSet) -> None:
        self.state.employee_id = event.employee_id
        self.state.updated_at = event.set_at

    # -------------------------------------------------------------------------
    # Snapshot Support for Event Store
    # -------------------------------------------------------------------------
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state for event store optimization."""
        return {
            "declaration_id": str(self.state.declaration_id) if self.state.declaration_id else None,
            "user_id": str(self.state.user_id) if self.state.user_id else None,
            "company_id": str(self.state.company_id) if self.state.company_id else None,
            "kontur_docflow_id": self.state.kontur_docflow_id,
            "gtd_number": self.state.gtd_number,
            "name": self.state.name,
            "declaration_type": self.state.declaration_type.value,
            "procedure": self.state.procedure,
            "customs_code": self.state.customs_code,
            "status": self.state.status.value,
            "organization_id": self.state.organization_id,
            "employee_id": self.state.employee_id,
            "declarant_inn": self.state.declarant_inn,
            "form_data": self.state.form_data,
            "documents": self.state.documents,
            "goods": self.state.goods,
            "created_at": self.state.created_at.isoformat() if self.state.created_at else None,
            "updated_at": self.state.updated_at.isoformat() if self.state.updated_at else None,
            "submitted_at": self.state.submitted_at.isoformat() if self.state.submitted_at else None,
            "deleted_at": self.state.deleted_at.isoformat() if self.state.deleted_at else None,
            "is_deleted": self.state.is_deleted,
            "version": self.version,
        }

    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore aggregate state from a snapshot."""
        self.state.declaration_id = uuid.UUID(snapshot_data["declaration_id"]) if snapshot_data.get("declaration_id") else None
        self.state.user_id = uuid.UUID(snapshot_data["user_id"]) if snapshot_data.get("user_id") else None
        self.state.company_id = uuid.UUID(snapshot_data["company_id"]) if snapshot_data.get("company_id") else None
        self.state.kontur_docflow_id = snapshot_data.get("kontur_docflow_id")
        self.state.gtd_number = snapshot_data.get("gtd_number")
        self.state.name = snapshot_data.get("name", "")
        self.state.declaration_type = DeclarationType(snapshot_data.get("declaration_type", "IM"))
        self.state.procedure = snapshot_data.get("procedure", "4000")
        self.state.customs_code = snapshot_data.get("customs_code", "")
        self.state.status = DocflowStatus(snapshot_data.get("status", 0))
        self.state.organization_id = snapshot_data.get("organization_id")
        self.state.employee_id = snapshot_data.get("employee_id")
        self.state.declarant_inn = snapshot_data.get("declarant_inn")
        self.state.form_data = snapshot_data.get("form_data", {})
        self.state.documents = snapshot_data.get("documents", [])
        self.state.goods = snapshot_data.get("goods", [])
        self.state.is_deleted = snapshot_data.get("is_deleted", False)

        if snapshot_data.get("created_at"):
            self.state.created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if snapshot_data.get("updated_at"):
            self.state.updated_at = datetime.fromisoformat(snapshot_data["updated_at"])
        if snapshot_data.get("submitted_at"):
            self.state.submitted_at = datetime.fromisoformat(snapshot_data["submitted_at"])
        if snapshot_data.get("deleted_at"):
            self.state.deleted_at = datetime.fromisoformat(snapshot_data["deleted_at"])

        self.version = snapshot_data.get("version", 0)

    # -------------------------------------------------------------------------
    # Replay from History
    # -------------------------------------------------------------------------
    @classmethod
    def replay_from_events(
        cls,
        declaration_id: uuid.UUID,
        events: List[BaseEvent],
        snapshot: Optional[Any] = None
    ) -> CustomsDeclarationAggregate:
        """
        Reconstruct an aggregate by applying past events in order.

        Handles both BaseEvent objects and EventEnvelope objects (from KurrentDB).
        EventEnvelopes are converted to domain events using the event registry.

        Args:
            declaration_id: The aggregate ID
            events: Events to replay (should be events AFTER snapshot if snapshot provided)
            snapshot: Optional AggregateSnapshot to restore from first
        """
        from app.infra.event_store.event_envelope import EventEnvelope

        agg = cls(declaration_id)

        # Restore from snapshot first if provided
        if snapshot is not None:
            agg.restore_from_snapshot(snapshot.state)
            agg.version = snapshot.version
            log.debug(f"Restored declaration {declaration_id} from snapshot at version {snapshot.version}")

        for evt in events:
            # Handle EventEnvelope from KurrentDB
            if isinstance(evt, EventEnvelope):
                # Try to convert envelope to domain event object
                event_obj = evt.to_event_object()
                if event_obj is None:
                    # Fallback: use DECLARATION_EVENT_TYPES registry
                    event_class = DECLARATION_EVENT_TYPES.get(evt.event_type)
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


# =============================================================================
# EOF
# =============================================================================
