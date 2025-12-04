# =============================================================================
# File: app/infra/saga/declaration_submission_saga.py
# Description: TRUE SAGA for Kontur declaration submission process
# =============================================================================

from __future__ import annotations

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.config.logging_config import get_logger
from app.config.saga_config import saga_config
from app.infra.saga.saga_manager import BaseSaga, SagaStep

log = get_logger("wellwon.saga.declaration_submission")


class DeclarationSubmissionSaga(BaseSaga):
    """
    TRUE SAGA: Orchestrates Kontur declaration submission process.

    Trigger Event: CustomsDeclarationSubmitted (enriched with all data)

    Context from enriched event:
    - declaration_id: UUID
    - kontur_docflow_id: str
    - form_data: Dict - declaration form data
    - documents: List[Dict] - attached documents
    - organization_id: str - Kontur organization ID
    - organization_inn: str - organization INN

    Steps:
    1. Import form data to Kontur (dt form)
    2. Upload documents to Kontur
    3. Set organization on form
    4. Validate declaration
    5. Publish completion

    Compensation:
    - Kontur handles rollback internally
    - Publish failure event for manual intervention
    """

    def __init__(self, saga_id: Optional[uuid.UUID] = None):
        super().__init__(saga_id)
        self._form_imported: bool = False
        self._documents_uploaded: int = 0

    def get_saga_type(self) -> str:
        return "DeclarationSubmissionSaga"

    def get_timeout(self) -> timedelta:
        return saga_config.get_timeout_for_saga(self.get_saga_type())

    def define_steps(self) -> List[SagaStep]:
        """
        Define saga steps for declaration submission.

        Order optimized for Kontur API:
        1. Import form data (creates base declaration)
        2. Upload documents (attaches to declaration)
        3. Set organization (sets contractor on form)
        4. Validate (optional - Kontur validation)
        5. Publish completion
        """
        return [
            SagaStep(
                name="import_form_data",
                execute=self._import_form_data,
                compensate=self._noop_compensate,  # Kontur handles rollback
                timeout_seconds=60,
                retry_count=2
            ),
            SagaStep(
                name="upload_documents",
                execute=self._upload_documents,
                compensate=self._noop_compensate,
                timeout_seconds=120,  # Documents may be large
                retry_count=2
            ),
            SagaStep(
                name="set_organization",
                execute=self._set_organization,
                compensate=self._noop_compensate,
                timeout_seconds=30,
                retry_count=2
            ),
            SagaStep(
                name="publish_completion",
                execute=self._publish_completion,
                compensate=self._noop_compensate,
                timeout_seconds=10,
                retry_count=1
            ),
        ]

    # =========================================================================
    # Step 1: Import Form Data
    # =========================================================================
    async def _import_form_data(self, **context) -> Dict[str, Any]:
        """
        Import declaration form data to Kontur.

        TRUE SAGA: All data from enriched CustomsDeclarationSubmitted event.
        """
        kontur_docflow_id = context['kontur_docflow_id']
        form_data = context.get('form_data', {})

        if not form_data:
            log.info(f"Saga {self.saga_id}: No form data to import")
            return {'form_imported': False, 'form_skipped': True}

        log.info(f"Saga {self.saga_id}: Importing form data to Kontur docflow {kontur_docflow_id}")

        try:
            from app.infra.kontur.adapter import get_kontur_adapter

            adapter = await get_kontur_adapter()
            await adapter.import_form_json(
                docflow_id=kontur_docflow_id,
                form_id="dt",  # Declaration for goods
                form_data=form_data
            )

            self._form_imported = True
            log.info(f"Saga {self.saga_id}: Form data imported successfully")

            return {'form_imported': True}

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to import form data: {e}")
            raise

    # =========================================================================
    # Step 2: Upload Documents
    # =========================================================================
    async def _upload_documents(self, **context) -> Dict[str, Any]:
        """
        Upload documents to Kontur docflow.

        TRUE SAGA: Documents list from enriched event.
        """
        kontur_docflow_id = context['kontur_docflow_id']
        documents = context.get('documents', [])

        if not documents:
            log.info(f"Saga {self.saga_id}: No documents to upload")
            return {'documents_uploaded': 0, 'documents_skipped': True}

        log.info(f"Saga {self.saga_id}: Uploading {len(documents)} documents to Kontur")

        try:
            from app.infra.kontur.adapter import get_kontur_adapter

            adapter = await get_kontur_adapter()
            uploaded_count = 0

            for doc in documents:
                try:
                    # Create document metadata in Kontur
                    await adapter.create_documents(
                        docflow_id=kontur_docflow_id,
                        documents=[{
                            "name": doc.get("name", "Document"),
                            "number": doc.get("number", ""),
                            "date": doc.get("date", ""),
                            "grafa44Code": doc.get("grafa44_code", ""),
                            "belongsToAllGoods": doc.get("belongs_to_all_goods", True),
                        }]
                    )
                    uploaded_count += 1

                except Exception as e:
                    log.warning(
                        f"Saga {self.saga_id}: Failed to upload document {doc.get('document_id')}: {e}"
                    )
                    # Continue with other documents

            self._documents_uploaded = uploaded_count
            log.info(f"Saga {self.saga_id}: Uploaded {uploaded_count}/{len(documents)} documents")

            return {
                'documents_uploaded': uploaded_count,
                'documents_total': len(documents),
            }

        except Exception as e:
            log.error(f"Saga {self.saga_id}: Failed to upload documents: {e}")
            raise

    # =========================================================================
    # Step 3: Set Organization
    # =========================================================================
    async def _set_organization(self, **context) -> Dict[str, Any]:
        """
        Set organization (contractor) on declaration form.

        TRUE SAGA: organization_id from enriched event.
        """
        kontur_docflow_id = context['kontur_docflow_id']
        organization_id = context.get('organization_id')

        if not organization_id:
            log.info(f"Saga {self.saga_id}: No organization to set")
            return {'organization_set': False, 'organization_skipped': True}

        log.info(
            f"Saga {self.saga_id}: Setting organization {organization_id} "
            f"on Kontur docflow {kontur_docflow_id}"
        )

        try:
            from app.infra.kontur.adapter import get_kontur_adapter

            adapter = await get_kontur_adapter()

            # Set organization on Grafa 8 (consignee)
            await adapter.set_form_contractor(
                docflow_id=kontur_docflow_id,
                form_id="dt",
                org_id=organization_id,
                grafa="8"
            )

            log.info(f"Saga {self.saga_id}: Organization set successfully")

            return {'organization_set': True}

        except Exception as e:
            log.warning(f"Saga {self.saga_id}: Failed to set organization: {e}")
            # Don't fail saga - organization can be set manually
            return {'organization_set': False, 'organization_error': str(e)}

    # =========================================================================
    # Step 4: Publish Completion
    # =========================================================================
    async def _publish_completion(self, **context) -> Dict[str, Any]:
        """
        Publish saga completion event.
        """
        from app.infra.saga.saga_events import DeclarationSubmissionSagaCompleted

        declaration_id = context['declaration_id']
        kontur_docflow_id = context['kontur_docflow_id']

        event_bus = context['event_bus']

        log.info(f"Saga {self.saga_id}: Publishing completion event")

        # Create completion event
        completion_event = DeclarationSubmissionSagaCompleted(
            saga_id=str(self.saga_id),
            declaration_id=str(declaration_id),
            kontur_docflow_id=kontur_docflow_id,
            form_imported=context.get('form_imported', False),
            documents_uploaded=context.get('documents_uploaded', 0),
            organization_set=context.get('organization_set', False),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await event_bus.publish("saga.events", completion_event.model_dump(mode='json'))

        log.info(
            f"Saga {self.saga_id}: DeclarationSubmissionSaga completed - "
            f"Declaration: {declaration_id}, Kontur: {kontur_docflow_id}"
        )

        return {'completion_published': True}

    # =========================================================================
    # Compensation (Kontur handles internally)
    # =========================================================================
    async def _noop_compensate(self, **context) -> None:
        """
        No explicit compensation needed.

        Kontur API:
        - Docflows can be deleted if in DRAFT status
        - Failed submissions stay in DRAFT for manual correction
        - No cascading side effects to compensate
        """
        pass


# =============================================================================
# Context Builder
# =============================================================================

def declaration_submission_context_builder(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build saga context from CustomsDeclarationSubmitted event.

    TRUE SAGA: All data extracted from enriched event.
    """
    return {
        "declaration_id": event_data['declaration_id'],
        "kontur_docflow_id": event_data['kontur_docflow_id'],
        "form_data": event_data.get('form_data', {}),
        "documents": event_data.get('documents', []),
        "organization_id": event_data.get('organization_id'),
        "organization_inn": event_data.get('organization_inn'),
        "user_id": event_data.get('user_id'),
    }


# =============================================================================
# EOF
# =============================================================================
