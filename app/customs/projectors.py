# =============================================================================
# File: app/customs/projectors.py
# Description: Projectors for Customs domain events
# =============================================================================

import uuid

from app.config.logging_config import get_logger
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.cqrs.projector_decorators import sync_projection, async_projection, monitor_projection
from app.infra.read_repos.customs_read_repo import CustomsDeclarationReadRepo, CommonOrganizationReadRepo

log = get_logger("wellwon.customs.projectors")


class CustomsProjector:
    """
    Handles Customs domain events to update read models (projections).

    Uses sync projections for:
    - Declaration creation (saga may follow)
    - Status updates (user needs immediate feedback)
    - Organization creation (user needs immediate confirmation)

    Uses async projections for:
    - Form data updates (eventual consistency OK)
    - Document changes (not immediately queried)
    - Organization updates (eventual consistency OK)
    """

    def __init__(
        self,
        declaration_read_repo: CustomsDeclarationReadRepo,
        organization_read_repo: CommonOrganizationReadRepo,
    ):
        self.declaration_read_repo = declaration_read_repo
        self.organization_read_repo = organization_read_repo

    # -------------------------------------------------------------------------
    # Declaration Lifecycle Projections
    # -------------------------------------------------------------------------

    @sync_projection("CustomsDeclarationCreated", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_created(self, envelope: EventEnvelope) -> None:
        """
        Project CustomsDeclarationCreated event.
        SYNC: Saga may follow, user needs immediate confirmation.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(f"Projecting CustomsDeclarationCreated for declaration_id={declaration_id}")

        await self.declaration_read_repo.insert_declaration(
            declaration_id=declaration_id,
            user_id=uuid.UUID(event_data['user_id']) if isinstance(event_data['user_id'], str) else event_data['user_id'],
            company_id=uuid.UUID(event_data['company_id']) if isinstance(event_data['company_id'], str) else event_data['company_id'],
            name=event_data['name'],
            declaration_type=event_data['declaration_type'],
            procedure=event_data['procedure'],
            customs_code=event_data['customs_code'],
            organization_id=event_data.get('organization_id'),
            employee_id=event_data.get('employee_id'),
            created_at=event_data.get('created_at'),
        )

    @sync_projection("CustomsDeclarationDeleted", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project CustomsDeclarationDeleted event.
        SYNC: User needs immediate feedback.
        """
        declaration_id = envelope.aggregate_id
        event_data = envelope.event_data

        log.info(f"Projecting CustomsDeclarationDeleted for declaration_id={declaration_id}")

        await self.declaration_read_repo.mark_declaration_deleted(
            declaration_id=declaration_id,
            deleted_at=event_data.get('deleted_at'),
        )

    @sync_projection("CustomsDeclarationCopied", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_copied(self, envelope: EventEnvelope) -> None:
        """
        Project CustomsDeclarationCopied event.
        SYNC: User needs immediate confirmation of copy.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting CustomsDeclarationCopied for declaration_id={declaration_id} "
            f"(source: {event_data['source_declaration_id']})"
        )

        await self.declaration_read_repo.insert_declaration(
            declaration_id=declaration_id,
            user_id=uuid.UUID(event_data['user_id']) if isinstance(event_data['user_id'], str) else event_data['user_id'],
            company_id=uuid.UUID(event_data['company_id']) if isinstance(event_data['company_id'], str) else event_data['company_id'],
            name=event_data['name'],
            declaration_type=event_data['declaration_type'],
            procedure=event_data['procedure'],
            customs_code=event_data['customs_code'],
            organization_id=event_data.get('organization_id'),
            employee_id=event_data.get('employee_id'),
            form_data=event_data.get('form_data', {}),
            documents=event_data.get('documents', []),
            created_at=event_data.get('created_at'),
        )

    # -------------------------------------------------------------------------
    # Form Data Projections
    # -------------------------------------------------------------------------

    @async_projection("FormDataUpdated")
    async def on_form_data_updated(self, envelope: EventEnvelope) -> None:
        """
        Project FormDataUpdated event.
        ASYNC: Eventual consistency OK for form edits.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(f"Projecting FormDataUpdated for declaration_id={declaration_id}")

        await self.declaration_read_repo.update_form_data(
            declaration_id=declaration_id,
            form_data=event_data['form_data'],
            updated_at=event_data.get('updated_at'),
        )

    @async_projection("GoodsImported")
    async def on_goods_imported(self, envelope: EventEnvelope) -> None:
        """
        Project GoodsImported event.
        ASYNC: Eventual consistency OK for goods import.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting GoodsImported for declaration_id={declaration_id} "
            f"({len(event_data['goods'])} goods from {event_data['import_source']})"
        )

        await self.declaration_read_repo.add_goods(
            declaration_id=declaration_id,
            goods=event_data['goods'],
            updated_at=event_data.get('imported_at'),
        )

    # -------------------------------------------------------------------------
    # Document Projections
    # -------------------------------------------------------------------------

    @async_projection("DocumentAttached")
    async def on_document_attached(self, envelope: EventEnvelope) -> None:
        """
        Project DocumentAttached event.
        ASYNC: Eventual consistency OK for document attachments.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting DocumentAttached for declaration_id={declaration_id} "
            f"(document: {event_data['document_id']})"
        )

        await self.declaration_read_repo.add_document(
            declaration_id=declaration_id,
            document={
                "document_id": event_data['document_id'],
                "form_id": event_data['form_id'],
                "name": event_data['name'],
                "number": event_data['number'],
                "date": event_data['date'],
                "grafa44_code": event_data['grafa44_code'],
                "belongs_to_all_goods": event_data['belongs_to_all_goods'],
                "file_id": event_data.get('file_id'),
            },
            updated_at=event_data.get('attached_at'),
        )

    @async_projection("DocumentRemoved")
    async def on_document_removed(self, envelope: EventEnvelope) -> None:
        """
        Project DocumentRemoved event.
        ASYNC: Eventual consistency OK for document removal.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting DocumentRemoved for declaration_id={declaration_id} "
            f"(document: {event_data['document_id']})"
        )

        await self.declaration_read_repo.remove_document(
            declaration_id=declaration_id,
            document_id=event_data['document_id'],
            updated_at=event_data.get('removed_at'),
        )

    @async_projection("DtsDocumentCreated")
    async def on_dts_document_created(self, envelope: EventEnvelope) -> None:
        """
        Project DtsDocumentCreated event.
        ASYNC: Eventual consistency OK for DTS document creation.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting DtsDocumentCreated for declaration_id={declaration_id} "
            f"(dts_type: {event_data['dts_type']})"
        )

        await self.declaration_read_repo.add_document(
            declaration_id=declaration_id,
            document={
                "document_id": event_data['document_id'],
                "form_id": "dts",
                "name": f"DTS Type {event_data['dts_type']}",
                "dts_type": event_data['dts_type'],
            },
            updated_at=event_data.get('created_at'),
        )

    # -------------------------------------------------------------------------
    # Kontur Integration Projections
    # -------------------------------------------------------------------------

    @sync_projection("CustomsDeclarationSubmitted", priority=1, timeout=3.0)
    @monitor_projection
    async def on_declaration_submitted(self, envelope: EventEnvelope) -> None:
        """
        Project CustomsDeclarationSubmitted event.
        SYNC: User needs immediate feedback that submission started.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting CustomsDeclarationSubmitted for declaration_id={declaration_id} "
            f"(kontur_docflow_id: {event_data['kontur_docflow_id']})"
        )

        await self.declaration_read_repo.update_submission_status(
            declaration_id=declaration_id,
            kontur_docflow_id=event_data['kontur_docflow_id'],
            status=1,  # SENT
            submitted_at=event_data.get('submitted_at'),
        )

    @sync_projection("StatusUpdatedFromKontur", priority=1, timeout=2.0)
    @monitor_projection
    async def on_status_updated_from_kontur(self, envelope: EventEnvelope) -> None:
        """
        Project StatusUpdatedFromKontur event.
        SYNC: User needs immediate feedback on status changes.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting StatusUpdatedFromKontur for declaration_id={declaration_id} "
            f"(status: {event_data['old_status']} -> {event_data['new_status']})"
        )

        await self.declaration_read_repo.update_status(
            declaration_id=declaration_id,
            status=event_data['new_status'],
            gtd_number=event_data.get('gtd_number'),
            updated_at=event_data.get('updated_at'),
        )

    @sync_projection("DeclarationRegistered", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_registered(self, envelope: EventEnvelope) -> None:
        """
        Project DeclarationRegistered event.
        SYNC: GTD number assignment is critical information.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting DeclarationRegistered for declaration_id={declaration_id} "
            f"(gtd_number: {event_data['gtd_number']})"
        )

        await self.declaration_read_repo.update_status(
            declaration_id=declaration_id,
            status=2,  # REGISTERED
            gtd_number=event_data['gtd_number'],
            updated_at=event_data.get('registered_at'),
        )

    @sync_projection("DeclarationReleased", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_released(self, envelope: EventEnvelope) -> None:
        """
        Project DeclarationReleased event.
        SYNC: Goods release is critical business event.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting DeclarationReleased for declaration_id={declaration_id} "
            f"(gtd_number: {event_data['gtd_number']})"
        )

        await self.declaration_read_repo.update_status(
            declaration_id=declaration_id,
            status=3,  # RELEASED
            updated_at=event_data.get('released_at'),
        )

    @sync_projection("DeclarationRejected", priority=1, timeout=2.0)
    @monitor_projection
    async def on_declaration_rejected(self, envelope: EventEnvelope) -> None:
        """
        Project DeclarationRejected event.
        SYNC: Rejection needs immediate attention.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(f"Projecting DeclarationRejected for declaration_id={declaration_id}")

        await self.declaration_read_repo.update_status(
            declaration_id=declaration_id,
            status=4,  # REJECTED
            rejection_reason=event_data.get('rejection_reason'),
            updated_at=event_data.get('rejected_at'),
        )

    @async_projection("KonturSyncFailed")
    async def on_kontur_sync_failed(self, envelope: EventEnvelope) -> None:
        """
        Project KonturSyncFailed event.
        ASYNC: Audit/logging only, doesn't affect user flow.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.warning(
            f"Projecting KonturSyncFailed for declaration_id={declaration_id}: "
            f"{event_data['error_message']}"
        )

        # Store sync failure for audit
        await self.declaration_read_repo.record_sync_failure(
            declaration_id=declaration_id,
            error_message=event_data['error_message'],
            failed_at=event_data.get('failed_at'),
        )

    # -------------------------------------------------------------------------
    # Organization Projections
    # -------------------------------------------------------------------------

    @async_projection("OrganizationSet")
    async def on_organization_set(self, envelope: EventEnvelope) -> None:
        """
        Project OrganizationSet event.
        ASYNC: Eventual consistency OK.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting OrganizationSet for declaration_id={declaration_id} "
            f"(organization: {event_data['organization_id']}, grafa: {event_data['grafa']})"
        )

        await self.declaration_read_repo.update_organization(
            declaration_id=declaration_id,
            organization_id=event_data['organization_id'],
            updated_at=event_data.get('set_at'),
        )

    @async_projection("EmployeeSet")
    async def on_employee_set(self, envelope: EventEnvelope) -> None:
        """
        Project EmployeeSet event.
        ASYNC: Eventual consistency OK.
        """
        event_data = envelope.event_data
        declaration_id = envelope.aggregate_id

        log.info(
            f"Projecting EmployeeSet for declaration_id={declaration_id} "
            f"(employee: {event_data['employee_id']})"
        )

        await self.declaration_read_repo.update_employee(
            declaration_id=declaration_id,
            employee_id=event_data['employee_id'],
            updated_at=event_data.get('set_at'),
        )

    # -------------------------------------------------------------------------
    # CommonOrg (Organization) Aggregate Projections
    # -------------------------------------------------------------------------

    @sync_projection("CommonOrgCreated", priority=1, timeout=2.0)
    @monitor_projection
    async def on_common_org_created(self, envelope: EventEnvelope) -> None:
        """
        Project CommonOrgCreated event.
        SYNC: User needs immediate confirmation of creation.
        """
        event_data = envelope.event_data
        org_id = envelope.aggregate_id

        log.info(f"Projecting CommonOrgCreated for org_id={org_id}")

        await self.organization_read_repo.insert_organization(
            org_id=org_id,
            kontur_org_id=event_data.get('kontur_org_id'),
            org_name=event_data['org_name'],
            short_name=event_data.get('short_name'),
            org_type=event_data['org_type'],
            inn=event_data.get('inn'),
            kpp=event_data.get('kpp'),
            ogrn=event_data.get('ogrn'),
            is_foreign=event_data.get('is_foreign', False),
            legal_address=event_data.get('legal_address'),
            actual_address=event_data.get('actual_address'),
            created_at=event_data.get('created_at'),
        )

    @async_projection("CommonOrgUpdated")
    async def on_common_org_updated(self, envelope: EventEnvelope) -> None:
        """
        Project CommonOrgUpdated event.
        ASYNC: Eventual consistency OK for updates.
        """
        event_data = envelope.event_data
        org_id = envelope.aggregate_id

        log.info(f"Projecting CommonOrgUpdated for org_id={org_id}")

        await self.organization_read_repo.update_organization(
            org_id=org_id,
            org_name=event_data.get('org_name'),
            short_name=event_data.get('short_name'),
            org_type=event_data.get('org_type'),
            kpp=event_data.get('kpp'),
            legal_address=event_data.get('legal_address'),
            actual_address=event_data.get('actual_address'),
            updated_at=event_data.get('updated_at'),
        )

    @sync_projection("CommonOrgSyncedFromRegistry", priority=1, timeout=3.0)
    @monitor_projection
    async def on_common_org_synced_from_registry(self, envelope: EventEnvelope) -> None:
        """
        Project CommonOrgSyncedFromRegistry event.
        SYNC: User triggered registry sync, needs immediate feedback.
        """
        event_data = envelope.event_data
        org_id = envelope.aggregate_id

        log.info(
            f"Projecting CommonOrgSyncedFromRegistry for org_id={org_id} "
            f"(INN: {event_data.get('inn')})"
        )

        await self.organization_read_repo.sync_from_registry(
            org_id=org_id,
            inn=event_data.get('inn'),
            org_name=event_data.get('org_name'),
            short_name=event_data.get('short_name'),
            kpp=event_data.get('kpp'),
            ogrn=event_data.get('ogrn'),
            kontur_org_id=event_data.get('kontur_org_id'),
            legal_address=event_data.get('legal_address'),
            synced_at=event_data.get('synced_at'),
        )

    @sync_projection("CommonOrgDeleted", priority=1, timeout=2.0)
    @monitor_projection
    async def on_common_org_deleted(self, envelope: EventEnvelope) -> None:
        """
        Project CommonOrgDeleted event.
        SYNC: User needs immediate feedback.
        """
        event_data = envelope.event_data
        org_id = envelope.aggregate_id

        log.info(f"Projecting CommonOrgDeleted for org_id={org_id}")

        await self.organization_read_repo.mark_deleted(
            org_id=org_id,
            deleted_at=event_data.get('deleted_at'),
        )

    @async_projection("CommonOrgLinkedToKontur")
    async def on_common_org_linked_to_kontur(self, envelope: EventEnvelope) -> None:
        """
        Project CommonOrgLinkedToKontur event.
        ASYNC: Eventual consistency OK for Kontur linking.
        """
        event_data = envelope.event_data
        org_id = envelope.aggregate_id

        log.info(
            f"Projecting CommonOrgLinkedToKontur for org_id={org_id} "
            f"(kontur_org_id: {event_data['kontur_org_id']})"
        )

        await self.organization_read_repo.link_to_kontur(
            org_id=org_id,
            kontur_org_id=event_data['kontur_org_id'],
            linked_at=event_data.get('linked_at'),
        )

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get projector statistics"""
        return {
            "projector": "CustomsProjector",
            "handlers": 21,
            "sync_events": [
                "CustomsDeclarationCreated",
                "CustomsDeclarationDeleted",
                "CustomsDeclarationCopied",
                "CustomsDeclarationSubmitted",
                "StatusUpdatedFromKontur",
                "DeclarationRegistered",
                "DeclarationReleased",
                "DeclarationRejected",
                "CommonOrgCreated",
                "CommonOrgSyncedFromRegistry",
                "CommonOrgDeleted",
            ],
            "async_events": [
                "FormDataUpdated",
                "GoodsImported",
                "DocumentAttached",
                "DocumentRemoved",
                "DtsDocumentCreated",
                "KonturSyncFailed",
                "OrganizationSet",
                "EmployeeSet",
                "CommonOrgUpdated",
                "CommonOrgLinkedToKontur",
            ]
        }


# =============================================================================
# EOF
# =============================================================================
