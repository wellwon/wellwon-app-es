# Customs Domain Architecture Analysis

**WellWon Platform - Kontur Declarant API Integration**

**Date:** 2025-12-03
**Version:** 1.0
**Status:** Architectural Planning

---

## Executive Summary

Этот документ содержит полный анализ архитектуры доменов для интеграции Kontur Declarant API в WellWon Platform. На основе анализа 32 endpoints (8 категорий) Kontur API, изучения референсных гайдов и существующего кода предлагается **гибридная доменная архитектура** с одним основным доменом `customs` и несколькими агрегатами.

**Ключевые рекомендации:**
- ✅ **Один домен `customs`** с несколькими агрегатами внутри
- ✅ **CustomsDeclarationAggregate** (Docflow) - главный агрегат
- ✅ **CommonOrgAggregate** - управление организациями/контрагентами
- ✅ **Reference Data** - read-only (без агрегатов, только Query Handlers)
- ✅ **Documents** - как Value Objects внутри Declaration (не отдельный агрегат)
- ✅ **Event Enrichment** pattern для интеграции с Kontur

---

## Table of Contents

1. [Context & Analysis](#1-context--analysis)
2. [Kontur API Breakdown](#2-kontur-api-breakdown)
3. [Domain Architecture Options](#3-domain-architecture-options)
4. [Recommended Architecture](#4-recommended-architecture)
5. [Aggregate Design](#5-aggregate-design)
6. [Commands & Events](#6-commands--events)
7. [Integration Patterns](#7-integration-patterns)
8. [Reference Data Strategy](#8-reference-data-strategy)
9. [Saga Orchestration](#9-saga-orchestration)
10. [API Router Design](#10-api-router-design)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Open Questions](#12-open-questions)

---

## 1. Context & Analysis

### 1.1 Kontur Declarant API

**Purpose:** Российский сервис электронного декларирования для таможни (Russian customs declaration service).

**Capabilities:**
- Создание и управление таможенными декларациями (Docflows)
- Загрузка и управление документами
- Формы для ввода данных декларации (dynamic forms)
- Интеграция с ФТС (Federal Customs Service)
- Печать PDF для подачи в таможню
- Расчет платежей (для транспортных средств)

**Integration Status:**
- ✅ Adapter implemented (`app/infra/kontur/adapter.py`) - 32 endpoints
- ✅ Models defined (`app/infra/kontur/models.py`) - Pydantic BaseModel
- ✅ Configuration (`app/config/kontur_config.py`) - 26 env vars
- ✅ Documentation (`docs/mvp/infrastructure/KONTUR_ADAPTER.md`) - complete reference
- ✅ Reference DB (`wellwon_reference.sql`) - 7 customs tables
- ❌ Domain layer - **NOT YET IMPLEMENTED** (this is what we're designing)

### 1.2 Business Requirements

**User Stories:**
1. Пользователь создаёт новую таможенную декларацию (IM/EX/TR)
2. Пользователь заполняет форму декларации (ESADout form)
3. Пользователь прикрепляет документы (invoice, packing list, etc.)
4. Пользователь отправляет декларацию в таможню через Kontur
5. Система получает ответ от таможни (marks, messages)
6. Пользователь печатает PDF декларации для архива/подачи
7. Пользователь управляет организациями-контрагентами (Common Orgs)
8. Пользователь видит статус декларации (draft → sent → registered → released)

**Non-Functional Requirements:**
- Idempotency (Kontur API calls may retry)
- Event sourcing compliance (all state changes via events)
- Audit trail (full history of declaration changes)
- Performance (pagination for large datasets)
- Real-time updates (WSE integration for status changes)

---

## 2. Kontur API Breakdown

### 2.1 API Categories Analysis

| Category | Endpoints | Purpose | Domain Mapping |
|----------|-----------|---------|----------------|
| **Organizations** | 2 | Manage contractors (Common Orgs) | CommonOrgAggregate |
| **Docflows** | 7 | Main declarations (CRUD + lifecycle) | CustomsDeclarationAggregate |
| **Documents** | 5 | Attach documents to declarations | Value Objects in Declaration |
| **Forms** | 6 | Form data import/export (JSON/XML/Excel) | Application Services |
| **Templates** | 2 | Form templates/schemas | Reference Data (Query) |
| **Options** | 7 | Reference data (procedures, customs, etc.) | Reference Data (Query) |
| **Print** | 2 | Generate HTML/PDF | Application Services |
| **Payments** | 1 | Calculate customs payments | Application Services |

### 2.2 Core Business Entities

#### 1. Customs Declaration (Docflow)

**Kontur Model:** `DocflowDto`

**Key Fields:**
- `id` (UUID from Kontur)
- `name` (user-friendly name)
- `declaration_type` (IM/EX/TR)
- `procedure` (customs procedure code)
- `status` (0-200+ status codes)
- `gtd_number` (customs registration number - assigned by FTS)
- `customs` (customs office code)
- `organization_id`, `employee_id` (from Options API)

**Lifecycle:**
```
Draft → Sent → Registered → Released/Rejected
  0       1         2           3 / 4
```

**Business Rules:**
- One declaration per shipment/transaction
- Can be copied (template pattern)
- Status transitions controlled by Kontur/FTS
- Immutable once sent (can't edit, only create new version)

#### 2. Organization (CommonOrg)

**Kontur Model:** `CommonOrg`

**Key Fields:**
- `id` (UUID from Kontur)
- `org_name` (full name)
- `short_name` (short name)
- `type` (0=legal, 1=IP, 2=natural person)
- `inn`, `kpp`, `ogrn` (Russian tax IDs)
- `legal_address`, `actual_address`
- `is_foreign` (flag for foreign companies)

**Business Rules:**
- Can be created/updated by user
- Can be fetched by INN from Russian registries (auto-populate)
- Used as contractors in declarations (sender, recipient, etc.)

#### 3. Document

**Kontur Model:** `DocumentRowDto`

**Key Fields:**
- `id` (UUID from Kontur)
- `document_type_code` (INVOICE, PACKING_LIST, etc.)
- `document_number`
- `document_date`
- `attached_to_goods` (which goods this document applies to)

**Business Rules:**
- Multiple documents per declaration
- Documents can be attached to specific goods (1,2,3)
- Special document: DTS (customs value distribution) - calculated by Kontur

#### 4. Form Data

**Not a separate entity** - это данные, заполненные пользователем в динамической форме.

**Kontur Model:** Dynamic JSON (depends on `document_mode_id`)

**Storage:** JSONB in `form_data` field of CustomsDeclaration

**Business Rules:**
- Schema defined by form templates (dc_form_definitions)
- Validated by Kontur on import
- Can be exported as JSON/XML/Excel

---

## 3. Domain Architecture Options

### Option 1: Один большой домен `customs`

**Structure:**
```
app/customs/
├── aggregate.py (CustomsDeclarationAggregate - ~2000 lines)
├── commands.py (20+ commands)
├── events.py (20+ events)
├── command_handlers/
├── query_handlers/
├── projectors.py
├── read_models.py
└── queries.py
```

**Pros:**
- ✅ Simple to start
- ✅ All customs logic in one place
- ✅ Fewer cross-domain calls
- ✅ Easy to understand for new developers

**Cons:**
- ❌ Large aggregate (hard to maintain)
- ❌ Mixes responsibilities (declarations, orgs, documents)
- ❌ Violates Single Responsibility Principle
- ❌ Hard to scale (one aggregate for everything)

**Verdict:** ❌ Not recommended for long-term

---

### Option 2: Несколько независимых доменов

**Structure:**
```
app/customs_declaration/
├── aggregate.py (CustomsDeclarationAggregate)
├── commands.py
├── events.py
└── ...

app/customs_organization/
├── aggregate.py (CommonOrgAggregate)
├── commands.py
├── events.py
└── ...

app/customs_document/
├── aggregate.py (DocumentAggregate)
├── commands.py
├── events.py
└── ...
```

**Pros:**
- ✅ Clear separation of concerns
- ✅ Easy to test independently
- ✅ Scalable (each domain can scale separately)
- ✅ Follows DDD bounded context pattern

**Cons:**
- ❌ More code (3 domains)
- ❌ Sagas needed for coordination
- ❌ Complex for simple operations
- ❌ Over-engineering for MVP

**Verdict:** ❌ Too complex for current requirements

---

### Option 3: Гибридный подход (Recommended)

**Structure:**
```
app/customs/
├── __init__.py
├── aggregate.py (CustomsDeclarationAggregate - main)
├── commands.py (declaration commands)
├── events.py (declaration events)
├── value_objects.py (Document, GoodItem, etc.)
├── enums.py (DeclarationType, DocflowStatus, etc.)
├── exceptions.py
├── command_handlers/
│   ├── declaration_handlers.py (create, submit, copy)
│   ├── document_handlers.py (attach documents)
│   └── organization_handlers.py (CommonOrg CRUD)
├── query_handlers/
│   ├── declaration_query_handlers.py
│   ├── organization_query_handlers.py
│   └── reference_query_handlers.py (options, templates)
├── projectors.py
├── read_models.py
├── queries.py
├── organizations/
│   ├── aggregate.py (CommonOrgAggregate)
│   ├── commands.py
│   ├── events.py
│   └── ...
└── sagas/
    ├── declaration_submission_saga.py
    └── ...
```

**Pros:**
- ✅ Single domain (`customs`) - easier to navigate
- ✅ Multiple aggregates (CustomsDeclaration, CommonOrg)
- ✅ Sub-folders for organization (but still one domain)
- ✅ Documents as Value Objects (not full aggregates)
- ✅ Reference data in Query Handlers (no aggregates needed)
- ✅ Balanced complexity

**Cons:**
- 🟡 Slightly more complex than Option 1
- 🟡 Requires discipline to keep aggregates separate

**Verdict:** ✅ **RECOMMENDED** - best balance of simplicity and scalability

---

## 4. Recommended Architecture

### 4.1 Domain Structure

**Domain Name:** `customs`

**Aggregates:**
1. **CustomsDeclarationAggregate** (main)
2. **CommonOrgAggregate** (organizations/contractors)

**Value Objects:**
- `Document` (attached documents)
- `GoodItem` (товар в декларации)
- `Address`
- `Person`
- `IdentityCard`

**Application Services:**
- `KonturFormService` (form import/export)
- `KonturPrintService` (HTML/PDF generation)
- `KonturPaymentService` (calculate payments)

**Reference Data:**
- Query Handlers for templates, options, procedures, customs offices
- No aggregates (read-only from wellwon_reference DB)

### 4.2 Aggregate Boundaries

#### CustomsDeclarationAggregate

**Responsibilities:**
- Manage declaration lifecycle (draft → sent → registered → released)
- Store form data (JSONB)
- Track attached documents (list of Document value objects)
- Track goods (list of GoodItem value objects)
- Enforce business rules (can't edit after sent, etc.)
- Emit events for state changes

**NOT Responsible For:**
- Managing organizations (delegated to CommonOrgAggregate)
- Form validation (delegated to Kontur API)
- PDF generation (delegated to Application Services)
- Reference data queries (delegated to Query Handlers)

#### CommonOrgAggregate

**Responsibilities:**
- Create/update organizations (contractors)
- Validate INN/KPP/OGRN
- Store organization data (name, address, tax IDs)
- Link to declarations (as foreign key)
- Emit events for org changes

**NOT Responsible For:**
- Managing declarations (separate aggregate)

### 4.3 Data Flow Example

**Scenario:** User creates new customs declaration

```
1. Frontend POST /api/customs/declarations
   ↓
2. API Router (customs_router.py)
   - Extract user_id from JWT
   - Create CreateCustomsDeclarationCommand
   ↓
3. Command Handler (CreateCustomsDeclarationHandler)
   - Query reference data (customs offices, procedures) - ENRICH
   - Query organization data (if needed) - ENRICH
   - Create CustomsDeclarationAggregate
   - aggregate.create_declaration(...) - EMIT CustomsDeclarationCreated event
   - publish_and_commit_events()
   ↓
4. Event Store (Redpanda)
   - CustomsDeclarationCreated event published
   ↓
5. Projector (CustomsProjector)
   - @sync_projection CustomsDeclarationCreated
   - Insert into customs_declarations table (PostgreSQL)
   ↓
6. API Response
   - Return declaration_id to frontend
   ↓
7. WSE Publisher
   - Publish event to WebSocket (real-time update for frontend)
```

---

## 5. Aggregate Design

### 5.1 CustomsDeclarationAggregate

#### State Structure

```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from app.customs.enums import DeclarationType, DocflowStatus
from app.customs.value_objects import Document, GoodItem

class CustomsDeclarationAggregateState(BaseModel):
    """Internal state of CustomsDeclarationAggregate"""

    # Identity
    declaration_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    company_id: Optional[UUID] = None

    # Kontur Reference
    kontur_docflow_id: Optional[str] = None  # UUID from Kontur
    kontur_process_id: Optional[str] = None
    gtd_number: Optional[str] = None  # Assigned by FTS after registration

    # Declaration Details
    name: Optional[str] = None
    declaration_type: Optional[DeclarationType] = None  # IM/EX/TR
    procedure: Optional[str] = None  # Customs procedure code
    singularity: Optional[str] = None  # Declaration features
    customs_office_code: Optional[str] = None

    # Organization References (Foreign Keys to CommonOrg)
    organization_id: Optional[str] = None  # Kontur org ID
    employee_id: Optional[str] = None  # Kontur employee ID
    declarant_inn: Optional[str] = None  # For quick reference

    # Form Data (Dynamic)
    document_mode_id: Optional[str] = None  # Form template ID
    gf_code: Optional[str] = None  # Kontur internal code
    form_data: Dict[str, Any] = {}  # JSONB - user-filled form data

    # Attached Documents (Value Objects)
    documents: List[Document] = []

    # Goods (Value Objects)
    goods: List[GoodItem] = []

    # Status
    status: DocflowStatus = DocflowStatus.DRAFT
    status_text: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None  # When sent to Kontur/FTS
    registered_at: Optional[datetime] = None  # When FTS registered
    released_at: Optional[datetime] = None  # When customs cleared

    # Audit
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None


@dataclass
class CustomsDeclarationAggregate:
    """
    Aggregate root for Customs Declarations (Docflows).

    Manages declaration lifecycle with Kontur Declarant API integration.
    """

    # =========================================================================
    # IDENTITY
    # =========================================================================
    id: UUID  # WellWon internal ID

    # =========================================================================
    # STATE
    # =========================================================================
    state: CustomsDeclarationAggregateState = field(
        default_factory=CustomsDeclarationAggregateState
    )

    # =========================================================================
    # EVENT SOURCING INFRASTRUCTURE
    # =========================================================================
    version: int = 0
    uncommitted_events: List[BaseEvent] = field(default_factory=list)

    # =========================================================================
    # FACTORY METHODS
    # =========================================================================

    @staticmethod
    def create(
        declaration_id: UUID,
        user_id: UUID,
        company_id: UUID,
        name: str,
        declaration_type: DeclarationType,
        procedure: str,
        customs_office_code: str,
        organization_id: str,
        employee_id: str,
        document_mode_id: str,
        gf_code: str,
        form_data: Optional[Dict[str, Any]] = None,
        # Enrichment from handler
        customs_office_name: Optional[str] = None,
        procedure_name: Optional[str] = None,
        declarant_inn: Optional[str] = None,
    ) -> 'CustomsDeclarationAggregate':
        """
        Create new customs declaration.

        Business Rules:
        - User must own company
        - Organization/employee must exist in Kontur
        - Customs office must be valid
        - Procedure must match declaration type

        Args:
            declaration_id: WellWon internal UUID
            user_id: Owner user ID
            company_id: Company ID
            name: User-friendly name
            declaration_type: IM/EX/TR
            procedure: Customs procedure code
            customs_office_code: 8-digit customs office code
            organization_id: Kontur organization ID
            employee_id: Kontur employee ID
            document_mode_id: Form template ID
            gf_code: Kontur internal code
            form_data: Initial form data (optional)

            # Enrichment (from handler queries)
            customs_office_name: Enriched customs office name
            procedure_name: Enriched procedure name
            declarant_inn: Enriched declarant INN

        Returns:
            CustomsDeclarationAggregate with CustomsDeclarationCreated event
        """
        aggregate = CustomsDeclarationAggregate(id=declaration_id)

        # Emit creation event (ENRICHED)
        event = CustomsDeclarationCreated(
            declaration_id=declaration_id,
            user_id=user_id,
            company_id=company_id,
            name=name,
            declaration_type=declaration_type.value,
            procedure=procedure,
            customs_office_code=customs_office_code,
            organization_id=organization_id,
            employee_id=employee_id,
            document_mode_id=document_mode_id,
            gf_code=gf_code,
            form_data=form_data or {},
            # Enrichment
            customs_office_name=customs_office_name,
            procedure_name=procedure_name,
            declarant_inn=declarant_inn,
        )

        aggregate.apply(event)
        return aggregate

    # =========================================================================
    # COMMAND METHODS (Business Logic)
    # =========================================================================

    def update_form_data(
        self,
        form_data: Dict[str, Any],
        updated_by: UUID
    ) -> None:
        """
        Update form data (must be in DRAFT status).

        Business Rules:
        - Can only update in DRAFT status
        - Form data validated by Kontur API (not here)

        Raises:
            InvalidStatusError: If status != DRAFT
        """
        if self.state.status != DocflowStatus.DRAFT:
            raise InvalidStatusError(
                f"Cannot update form data in status {self.state.status}"
            )

        event = CustomsDeclarationFormDataUpdated(
            declaration_id=self.id,
            form_data=form_data,
            updated_by=updated_by
        )
        self.apply(event)

    def attach_document(
        self,
        kontur_document_id: str,
        document_type_code: str,
        document_number: str,
        document_date: str,
        attached_to_goods: Optional[str] = None,  # "1,2,3"
        # Enrichment
        document_type_name: Optional[str] = None
    ) -> None:
        """
        Attach document to declaration.

        Business Rules:
        - Can attach documents in DRAFT or SENT status
        - Document must be uploaded to Kontur first

        Args:
            kontur_document_id: Document ID from Kontur
            document_type_code: Document type (INVOICE, etc.)
            document_number: Document number
            document_date: Document date
            attached_to_goods: Goods numbers (e.g. "1,2,3")
            document_type_name: Enriched document type name

        Raises:
            InvalidStatusError: If status is REGISTERED or later
        """
        if self.state.status in [DocflowStatus.REGISTERED, DocflowStatus.RELEASED]:
            raise InvalidStatusError(
                f"Cannot attach documents in status {self.state.status}"
            )

        event = CustomsDeclarationDocumentAttached(
            declaration_id=self.id,
            kontur_document_id=kontur_document_id,
            document_type_code=document_type_code,
            document_number=document_number,
            document_date=document_date,
            attached_to_goods=attached_to_goods,
            # Enrichment
            document_type_name=document_type_name
        )
        self.apply(event)

    def submit_to_kontur(
        self,
        kontur_docflow_id: str,
        submitted_by: UUID
    ) -> None:
        """
        Submit declaration to Kontur/FTS.

        Business Rules:
        - Must be in DRAFT status
        - Form data must be complete (validated by Kontur)
        - After submission, declaration is immutable

        Args:
            kontur_docflow_id: Docflow ID from Kontur API
            submitted_by: User who submitted

        Raises:
            InvalidStatusError: If not DRAFT
        """
        if self.state.status != DocflowStatus.DRAFT:
            raise InvalidStatusError(
                f"Cannot submit declaration in status {self.state.status}"
            )

        event = CustomsDeclarationSubmitted(
            declaration_id=self.id,
            kontur_docflow_id=kontur_docflow_id,
            submitted_by=submitted_by
        )
        self.apply(event)

    def update_status_from_kontur(
        self,
        new_status: DocflowStatus,
        status_text: str,
        gtd_number: Optional[str] = None,
        registered_at: Optional[datetime] = None
    ) -> None:
        """
        Update status from Kontur API (webhook or polling).

        Business Rules:
        - Status transitions must be valid (can't go backwards)
        - GTD number assigned when REGISTERED

        Args:
            new_status: New status from Kontur
            status_text: Human-readable status
            gtd_number: GTD number (assigned by FTS)
            registered_at: Registration timestamp

        Raises:
            InvalidStatusTransitionError: If transition invalid
        """
        # Validate status transition
        if not self._is_valid_status_transition(self.state.status, new_status):
            raise InvalidStatusTransitionError(
                f"Invalid transition: {self.state.status} → {new_status}"
            )

        event = CustomsDeclarationStatusUpdated(
            declaration_id=self.id,
            old_status=self.state.status.value,
            new_status=new_status.value,
            status_text=status_text,
            gtd_number=gtd_number,
            registered_at=registered_at
        )
        self.apply(event)

    def mark_deleted(
        self,
        deleted_by: UUID,
        reason: str
    ) -> None:
        """
        Soft-delete declaration.

        Business Rules:
        - Can only delete DRAFT declarations
        - SENT/REGISTERED declarations cannot be deleted (archived only)
        """
        if self.state.status != DocflowStatus.DRAFT:
            raise InvalidOperationError(
                "Can only delete DRAFT declarations"
            )

        event = CustomsDeclarationDeleted(
            declaration_id=self.id,
            deleted_by=deleted_by,
            reason=reason
        )
        self.apply(event)

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    @staticmethod
    def _is_valid_status_transition(
        old_status: DocflowStatus,
        new_status: DocflowStatus
    ) -> bool:
        """
        Check if status transition is valid.

        Valid transitions:
        DRAFT → SENT
        SENT → REGISTERED or REJECTED
        REGISTERED → RELEASED
        """
        valid_transitions = {
            DocflowStatus.DRAFT: [DocflowStatus.SENT],
            DocflowStatus.SENT: [DocflowStatus.REGISTERED, DocflowStatus.REJECTED],
            DocflowStatus.REGISTERED: [DocflowStatus.RELEASED],
        }

        return new_status in valid_transitions.get(old_status, [])

    # =========================================================================
    # EVENT HANDLERS (State Mutation)
    # =========================================================================

    def _on_customs_declaration_created(self, event: CustomsDeclarationCreated):
        """Apply CustomsDeclarationCreated event"""
        self.state.declaration_id = event.declaration_id
        self.state.user_id = event.user_id
        self.state.company_id = event.company_id
        self.state.name = event.name
        self.state.declaration_type = DeclarationType(event.declaration_type)
        self.state.procedure = event.procedure
        self.state.customs_office_code = event.customs_office_code
        self.state.organization_id = event.organization_id
        self.state.employee_id = event.employee_id
        self.state.document_mode_id = event.document_mode_id
        self.state.gf_code = event.gf_code
        self.state.form_data = event.form_data
        self.state.declarant_inn = event.declarant_inn
        self.state.status = DocflowStatus.DRAFT
        self.state.created_at = event.timestamp

    def _on_customs_declaration_form_data_updated(
        self,
        event: CustomsDeclarationFormDataUpdated
    ):
        """Apply form data update"""
        self.state.form_data = event.form_data
        self.state.updated_at = event.timestamp

    def _on_customs_declaration_document_attached(
        self,
        event: CustomsDeclarationDocumentAttached
    ):
        """Apply document attachment"""
        document = Document(
            kontur_id=event.kontur_document_id,
            type_code=event.document_type_code,
            type_name=event.document_type_name,
            number=event.document_number,
            date=event.document_date,
            attached_to_goods=event.attached_to_goods
        )
        self.state.documents.append(document)
        self.state.updated_at = event.timestamp

    def _on_customs_declaration_submitted(
        self,
        event: CustomsDeclarationSubmitted
    ):
        """Apply submission"""
        self.state.kontur_docflow_id = event.kontur_docflow_id
        self.state.status = DocflowStatus.SENT
        self.state.submitted_at = event.timestamp

    def _on_customs_declaration_status_updated(
        self,
        event: CustomsDeclarationStatusUpdated
    ):
        """Apply status update"""
        self.state.status = DocflowStatus(event.new_status)
        self.state.status_text = event.status_text

        if event.gtd_number:
            self.state.gtd_number = event.gtd_number

        if event.registered_at:
            self.state.registered_at = event.registered_at

        if event.new_status == DocflowStatus.RELEASED.value:
            self.state.released_at = event.timestamp

    def _on_customs_declaration_deleted(
        self,
        event: CustomsDeclarationDeleted
    ):
        """Apply deletion"""
        self.state.is_deleted = True
        self.state.deleted_at = event.timestamp
```

### 5.2 CommonOrgAggregate

#### State Structure

```python
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.customs.enums import OrganizationType
from app.customs.value_objects import Address, Person, IdentityCard

class CommonOrgAggregateState(BaseModel):
    """Internal state of CommonOrgAggregate"""

    # Identity
    org_id: Optional[UUID] = None
    user_id: Optional[UUID] = None  # Owner (if created by user)
    company_id: Optional[UUID] = None

    # Kontur Reference
    kontur_org_id: Optional[str] = None  # UUID from Kontur

    # Organization Details
    org_name: str = ""
    short_name: str = ""
    type: OrganizationType = OrganizationType.LEGAL_ENTITY
    is_foreign: bool = False

    # Russian Tax IDs
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    okpo: Optional[str] = None
    okato: Optional[str] = None
    oktmo: Optional[str] = None

    # Addresses
    legal_address: Optional[Address] = None
    actual_address: Optional[Address] = None

    # Person (for natural persons)
    person: Optional[Person] = None
    identity_card: Optional[IdentityCard] = None

    # Additional
    branch_description: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None  # Last sync with Kontur

    # Audit
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None


@dataclass
class CommonOrgAggregate:
    """
    Aggregate root for Common Organizations (contractors).

    Manages organizations used in customs declarations.
    """

    id: UUID
    state: CommonOrgAggregateState = field(
        default_factory=CommonOrgAggregateState
    )
    version: int = 0
    uncommitted_events: List[BaseEvent] = field(default_factory=list)

    # Command methods: create, update, sync_from_kontur, delete
    # Event handlers: _on_common_org_created, _on_common_org_updated, etc.
```

---

## 6. Commands & Events

### 6.1 CustomsDeclaration Commands

```python
# app/customs/commands.py

from pydantic import Field
from uuid import UUID
from typing import Optional, Dict, Any
from app.infra.cqrs.command_bus import Command
from app.customs.enums import DeclarationType

class CreateCustomsDeclarationCommand(Command):
    """Create new customs declaration (docflow)"""
    declaration_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    company_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    declaration_type: DeclarationType
    procedure: str = Field(..., min_length=1, max_length=10)
    customs_office_code: str = Field(..., min_length=8, max_length=8)
    organization_id: str  # Kontur org ID
    employee_id: str  # Kontur employee ID
    document_mode_id: str  # Form template ID
    gf_code: str  # Kontur internal code
    form_data: Optional[Dict[str, Any]] = None


class UpdateCustomsDeclarationFormDataCommand(Command):
    """Update form data in DRAFT declaration"""
    declaration_id: UUID
    user_id: UUID
    form_data: Dict[str, Any]


class AttachDocumentToDeclarationCommand(Command):
    """Attach document to declaration"""
    declaration_id: UUID
    user_id: UUID
    kontur_document_id: str
    document_type_code: str
    document_number: str
    document_date: str
    attached_to_goods: Optional[str] = None  # "1,2,3"


class SubmitDeclarationToKonturCommand(Command):
    """Submit declaration to Kontur/FTS"""
    declaration_id: UUID
    user_id: UUID


class CopyDeclarationCommand(Command):
    """Copy existing declaration as template"""
    source_declaration_id: UUID
    user_id: UUID
    new_name: str


class UpdateDeclarationStatusFromKonturCommand(Command):
    """Update status from Kontur webhook/polling"""
    declaration_id: UUID
    new_status: int
    status_text: str
    gtd_number: Optional[str] = None


class DeleteCustomsDeclarationCommand(Command):
    """Soft-delete DRAFT declaration"""
    declaration_id: UUID
    user_id: UUID
    reason: str = "user_deleted"
```

### 6.2 CustomsDeclaration Events

```python
# app/customs/events.py

from typing import Literal, Optional, Dict, Any
from datetime import datetime, UTC
from uuid import UUID
from pydantic import Field
from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event

@domain_event(category="domain")
class CustomsDeclarationCreated(BaseEvent):
    """Customs declaration created"""
    event_type: Literal["CustomsDeclarationCreated"] = "CustomsDeclarationCreated"

    declaration_id: UUID
    user_id: UUID
    company_id: UUID
    name: str
    declaration_type: str  # "IM"/"EX"/"TR"
    procedure: str
    customs_office_code: str
    organization_id: str
    employee_id: str
    document_mode_id: str
    gf_code: str
    form_data: Dict[str, Any]

    # Enrichment (from handler queries)
    customs_office_name: Optional[str] = None
    procedure_name: Optional[str] = None
    declarant_inn: Optional[str] = None


@domain_event(category="domain")
class CustomsDeclarationFormDataUpdated(BaseEvent):
    """Form data updated"""
    event_type: Literal["CustomsDeclarationFormDataUpdated"] = "CustomsDeclarationFormDataUpdated"

    declaration_id: UUID
    form_data: Dict[str, Any]
    updated_by: UUID


@domain_event(category="domain")
class CustomsDeclarationDocumentAttached(BaseEvent):
    """Document attached to declaration"""
    event_type: Literal["CustomsDeclarationDocumentAttached"] = "CustomsDeclarationDocumentAttached"

    declaration_id: UUID
    kontur_document_id: str
    document_type_code: str
    document_number: str
    document_date: str
    attached_to_goods: Optional[str] = None

    # Enrichment
    document_type_name: Optional[str] = None


@domain_event(category="domain")
class CustomsDeclarationSubmitted(BaseEvent):
    """Declaration submitted to Kontur/FTS"""
    event_type: Literal["CustomsDeclarationSubmitted"] = "CustomsDeclarationSubmitted"

    declaration_id: UUID
    kontur_docflow_id: str
    submitted_by: UUID


@domain_event(category="domain")
class CustomsDeclarationStatusUpdated(BaseEvent):
    """Status updated from Kontur"""
    event_type: Literal["CustomsDeclarationStatusUpdated"] = "CustomsDeclarationStatusUpdated"

    declaration_id: UUID
    old_status: int
    new_status: int
    status_text: str
    gtd_number: Optional[str] = None
    registered_at: Optional[datetime] = None


@domain_event(category="domain")
class CustomsDeclarationDeleted(BaseEvent):
    """Declaration soft-deleted"""
    event_type: Literal["CustomsDeclarationDeleted"] = "CustomsDeclarationDeleted"

    declaration_id: UUID
    deleted_by: UUID
    reason: str
```

### 6.3 CommonOrg Commands & Events

```python
# app/customs/organizations/commands.py

class CreateCommonOrgCommand(Command):
    """Create organization/contractor"""
    org_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    company_id: UUID
    org_name: str
    short_name: str
    inn: str  # Required for Russian orgs
    # ... other fields


class SyncCommonOrgFromKonturCommand(Command):
    """Sync organization from Kontur by INN"""
    org_id: UUID
    user_id: UUID
    inn: str


# app/customs/organizations/events.py

@domain_event(category="domain")
class CommonOrgCreated(BaseEvent):
    """Organization created"""
    event_type: Literal["CommonOrgCreated"] = "CommonOrgCreated"

    org_id: UUID
    user_id: UUID
    company_id: UUID
    org_name: str
    inn: str
    # ... other fields


@domain_event(category="domain")
class CommonOrgSyncedFromKontur(BaseEvent):
    """Organization synced from Kontur registries"""
    event_type: Literal["CommonOrgSyncedFromKontur"] = "CommonOrgSyncedFromKontur"

    org_id: UUID
    kontur_org_id: str
    org_name: str
    inn: str
    # ... full org data from EGRUL/EGRIP
```

---

## 7. Integration Patterns

### 7.1 Kontur Adapter Usage in Command Handlers

**Pattern:** Command Handler → Kontur Adapter → Enrich Event

**Example:** Create Declaration

```python
# app/customs/command_handlers/declaration_handlers.py

from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.kontur.models import CreateDocflowRequest

@command_handler(CreateCustomsDeclarationCommand)
class CreateCustomsDeclarationHandler(BaseCommandHandler):
    """Create customs declaration with Kontur integration"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.customs-events",
            event_store=deps.event_store
        )
        self.query_bus = deps.query_bus
        self.kontur_adapter = get_kontur_adapter()

    async def handle(
        self,
        command: CreateCustomsDeclarationCommand
    ) -> UUID:
        log.info(f"Creating customs declaration: {command.name}")

        # 1. QUERY: Get reference data for enrichment
        customs_office = await self.query_bus.query(
            GetCustomsOfficeQuery(code=command.customs_office_code)
        )
        if not customs_office:
            raise ValueError(f"Invalid customs office: {command.customs_office_code}")

        procedure = await self.query_bus.query(
            GetCustomsProcedureQuery(code=command.procedure)
        )
        if not procedure:
            raise ValueError(f"Invalid procedure: {command.procedure}")

        declarant = await self.query_bus.query(
            GetKonturOrganizationQuery(org_id=command.organization_id)
        )

        # 2. Create docflow in Kontur (if needed immediately)
        # OR: Create draft locally, submit to Kontur later (better UX)
        # Let's use "create locally first" approach

        # 3. Create aggregate
        aggregate = CustomsDeclarationAggregate.create(
            declaration_id=command.declaration_id,
            user_id=command.user_id,
            company_id=command.company_id,
            name=command.name,
            declaration_type=command.declaration_type,
            procedure=command.procedure,
            customs_office_code=command.customs_office_code,
            organization_id=command.organization_id,
            employee_id=command.employee_id,
            document_mode_id=command.document_mode_id,
            gf_code=command.gf_code,
            form_data=command.form_data,
            # Enrichment
            customs_office_name=customs_office.name,
            procedure_name=procedure.name,
            declarant_inn=declarant.inn if declarant else None,
        )

        # 4. Publish events
        await self.publish_and_commit_events(
            aggregate=aggregate,
            aggregate_type="CustomsDeclaration",
            expected_version=None,
        )

        log.info(f"Customs declaration created: {command.declaration_id}")
        return command.declaration_id
```

**Example:** Submit Declaration to Kontur

```python
@command_handler(SubmitDeclarationToKonturCommand)
class SubmitDeclarationToKonturHandler(BaseCommandHandler):
    """Submit declaration to Kontur/FTS"""

    def __init__(self, deps: HandlerDependencies):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.customs-events",
            event_store=deps.event_store
        )
        self.kontur_adapter = get_kontur_adapter()
        self.aggregate_repository = deps.aggregate_repository

    async def handle(
        self,
        command: SubmitDeclarationToKonturCommand
    ) -> None:
        log.info(f"Submitting declaration to Kontur: {command.declaration_id}")

        # 1. Load aggregate from Event Store
        aggregate = await self.aggregate_repository.load(
            CustomsDeclarationAggregate,
            command.declaration_id
        )

        if aggregate.version == 0:
            raise ValueError("Declaration not found")

        # 2. Call Kontur API to create docflow
        kontur_request = CreateDocflowRequest(
            type=aggregate.state.declaration_type.value,
            procedure=aggregate.state.procedure,
            customs=aggregate.state.customs_office_code,
            organization_id=aggregate.state.organization_id,
            employee_id=aggregate.state.employee_id,
            name=aggregate.state.name,
            singularity=aggregate.state.singularity
        )

        try:
            docflow_result = await self.kontur_adapter.create_docflow(
                kontur_request
            )

            if not docflow_result:
                raise ValueError("Failed to create docflow in Kontur")

            kontur_docflow_id = docflow_result.id

        except httpx.HTTPStatusError as e:
            log.error(f"Kontur API error: {e}")
            raise

        # 3. Import form data to Kontur
        if aggregate.state.form_data:
            await self.kontur_adapter.import_form_json(
                docflow_id=kontur_docflow_id,
                form_id=aggregate.state.document_mode_id,
                data=aggregate.state.form_data
            )

        # 4. Update aggregate
        aggregate.submit_to_kontur(
            kontur_docflow_id=kontur_docflow_id,
            submitted_by=command.user_id
        )

        # 5. Publish events
        await self.publish_and_commit_events(
            aggregate=aggregate,
            aggregate_type="CustomsDeclaration",
            expected_version=aggregate.version,
        )

        log.info(f"Declaration submitted: {kontur_docflow_id}")
```

### 7.2 Status Sync Pattern (Webhook or Polling)

**Option 1: Webhook from Kontur**

Kontur can send webhooks when declaration status changes (if configured).

**Option 2: Polling (more reliable)**

Background job polls Kontur API every 5-10 minutes to check for status updates.

```python
# app/customs/services/kontur_status_sync_service.py

from app.infra.kontur.adapter import get_kontur_adapter

class KonturStatusSyncService:
    """
    Background service to sync declaration statuses from Kontur.

    Runs every 5 minutes, checks declarations in non-final statuses.
    """

    async def sync_active_declarations(self):
        """
        Sync all active declarations (SENT, REGISTERED).
        """
        # 1. Query active declarations from read model
        active_declarations = await self.query_bus.query(
            GetActiveDeclarationsQuery(
                statuses=["SENT", "REGISTERED"]
            )
        )

        kontur = get_kontur_adapter()

        for decl in active_declarations:
            try:
                # 2. Get latest status from Kontur
                docflow = await kontur.list_docflows(
                    # Filter by kontur_docflow_id (not supported by API)
                    # So we use search or get by GTD number
                )

                # Alternative: Get from Kontur by declaration number
                if decl.gtd_number:
                    search_result = await kontur.search_docflows(
                        SearchDocflowRequest(
                            document_number=decl.gtd_number
                        )
                    )
                    if search_result:
                        docflow = search_result[0]

                if not docflow:
                    continue

                # 3. Check if status changed
                if docflow.status != decl.kontur_status:
                    # Send command to update status
                    await self.command_bus.send(
                        UpdateDeclarationStatusFromKonturCommand(
                            declaration_id=decl.id,
                            new_status=docflow.status,
                            status_text=docflow.status_text,
                            gtd_number=docflow.gtd_number
                        )
                    )

                    log.info(
                        f"Status updated: {decl.id} "
                        f"{decl.status} → {docflow.status}"
                    )

            except Exception as e:
                log.error(f"Failed to sync {decl.id}: {e}")
                continue
```

---

## 8. Reference Data Strategy

### 8.1 Reference Tables (wellwon_reference DB)

**Tables:**
1. `dc_json_templates` - Form templates from Kontur
2. `dc_form_definitions` - Preprocessed form schemas
3. `dc_procedures` - Customs procedures
4. `dc_customs` - Customs offices
5. `dc_declaration_types` - Declaration types (IM/EX/TR)
6. `dc_document_types` - Document types
7. `dc_common_orgs` - Synced organizations from Kontur

**Access Pattern:**
- **Query Handlers** - read from wellwon_reference
- **Command Handlers** - enrich events using Query Handlers
- **NO Aggregates** - reference data is read-only

### 8.2 Query Handlers for Reference Data

```python
# app/customs/query_handlers/reference_query_handlers.py

@query_handler(GetCustomsOfficeQuery)
class GetCustomsOfficeHandler:
    """Get customs office by code"""

    def __init__(self, deps: HandlerDependencies):
        self.ref_db = deps.ref_db  # wellwon_reference connection

    async def handle(
        self,
        query: GetCustomsOfficeQuery
    ) -> Optional[CustomsOfficeOption]:
        result = await self.ref_db.fetch_one(
            "SELECT * FROM dc_customs WHERE code = $1",
            query.code
        )

        if not result:
            return None

        return CustomsOfficeOption(**result)


@query_handler(ListCustomsProceduresQuery)
class ListCustomsProceduresHandler:
    """List customs procedures for declaration type"""

    def __init__(self, deps: HandlerDependencies):
        self.ref_db = deps.ref_db

    async def handle(
        self,
        query: ListCustomsProceduresQuery
    ) -> List[CustomsProcedureOption]:
        results = await self.ref_db.fetch_all(
            """
            SELECT * FROM dc_procedures
            WHERE declaration_type = $1 AND is_active = true
            ORDER BY sort_order
            """,
            query.declaration_type
        )

        return [CustomsProcedureOption(**r) for r in results]


@query_handler(GetFormTemplateQuery)
class GetFormTemplateHandler:
    """Get form template by document_mode_id"""

    def __init__(self, deps: HandlerDependencies):
        self.ref_db = deps.ref_db

    async def handle(
        self,
        query: GetFormTemplateQuery
    ) -> Optional[FormTemplate]:
        result = await self.ref_db.fetch_one(
            """
            SELECT * FROM dc_form_definitions
            WHERE document_mode_id = $1 AND is_active = true
            """,
            query.document_mode_id
        )

        if not result:
            return None

        return FormTemplate(**result)
```

### 8.3 Sync Strategy for Reference Data

**Initial Sync (on deploy):**

```python
# app/customs/services/kontur_reference_sync_service.py

class KonturReferenceSyncService:
    """
    Sync reference data from Kontur API to wellwon_reference DB.

    Runs on deploy or manually via admin API.
    """

    async def sync_all_reference_data(self):
        """Full sync of all reference data"""
        await self.sync_templates()
        await self.sync_customs_offices()
        await self.sync_procedures()
        await self.sync_declaration_types()

    async def sync_templates(self):
        """Sync form templates from Kontur"""
        kontur = get_kontur_adapter()

        # Get all templates from Kontur
        templates = await kontur.list_templates()

        for template in templates:
            # Upsert to dc_json_templates
            await self.ref_db.execute(
                """
                INSERT INTO dc_json_templates (
                    gf_code, document_mode_id, type_name
                )
                VALUES ($1, $2, $3)
                ON CONFLICT (gf_code, document_mode_id, type_name)
                DO UPDATE SET updated_at = NOW()
                """,
                template.gf_code,
                template.document_mode_id,
                template.type_name
            )

        log.info(f"Synced {len(templates)} templates from Kontur")

    async def sync_customs_offices(self):
        """Sync customs offices from Kontur"""
        kontur = get_kontur_adapter()

        offices = await kontur.list_customs()

        for office in offices:
            await self.ref_db.execute(
                """
                INSERT INTO dc_customs (code, name, address)
                VALUES ($1, $2, $3)
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    address = EXCLUDED.address,
                    updated_at = NOW()
                """,
                office.code,
                office.name,
                office.address
            )

        log.info(f"Synced {len(offices)} customs offices")
```

---

## 9. Saga Orchestration

### 9.1 Declaration Submission Saga

**Purpose:** Orchestrate multi-step declaration submission to Kontur with compensation.

**Scenario:** User submits declaration → Create docflow in Kontur → Upload documents → Import form data → Final submission

**Steps:**

```python
# app/customs/sagas/declaration_submission_saga.py

from app.infra.saga.saga_manager import BaseSaga, SagaStep

class DeclarationSubmissionSaga(BaseSaga):
    """
    Orchestrate declaration submission to Kontur/FTS.

    TRUE SAGA: Event-driven orchestration using enriched events.
    """

    def get_saga_type(self) -> str:
        return "DeclarationSubmissionSaga"

    def get_timeout(self) -> timedelta:
        return timedelta(minutes=10)

    def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="create_kontur_docflow",
                handler=self._create_kontur_docflow,
                compensation=self._delete_kontur_docflow
            ),
            SagaStep(
                name="upload_documents",
                handler=self._upload_documents,
                compensation=None  # Documents can stay, no harm
            ),
            SagaStep(
                name="import_form_data",
                handler=self._import_form_data,
                compensation=None  # Idempotent, can retry
            ),
            SagaStep(
                name="final_submission",
                handler=self._final_submission,
                compensation=None  # Cannot compensate FTS submission
            ),
            SagaStep(
                name="publish_completion",
                handler=self._publish_completion,
                compensation=None
            ),
        ]

    # =========================================================================
    # STEP HANDLERS (TRUE SAGA - use enriched event data, NO queries!)
    # =========================================================================

    async def _create_kontur_docflow(self, **context) -> Dict[str, Any]:
        """Step 1: Create docflow in Kontur"""

        # Data from enriched event (NO queries!)
        declaration_id = context['declaration_id']
        declaration_type = context['declaration_type']
        procedure = context['procedure']
        customs_office_code = context['customs_office_code']
        organization_id = context['organization_id']
        employee_id = context['employee_id']
        name = context['name']

        kontur = get_kontur_adapter()

        # Call Kontur API
        request = CreateDocflowRequest(
            type=declaration_type,
            procedure=procedure,
            customs=customs_office_code,
            organization_id=organization_id,
            employee_id=employee_id,
            name=name
        )

        result = await kontur.create_docflow(request)

        if not result:
            raise SagaStepError("Failed to create docflow in Kontur")

        log.info(f"Created Kontur docflow: {result.id}")

        return {'kontur_docflow_id': result.id}

    async def _upload_documents(self, **context) -> Dict[str, Any]:
        """Step 2: Upload documents to Kontur"""

        kontur_docflow_id = context['kontur_docflow_id']
        documents = context['documents']  # From enriched event

        if not documents:
            log.info("No documents to upload, skipping")
            return {}

        kontur = get_kontur_adapter()

        for doc in documents:
            # Upload document file
            # (Assuming files stored in MinIO/S3, fetch and upload)
            file_bytes = await self.storage.get_file(doc['file_path'])

            await kontur.create_documents(
                docflow_id=kontur_docflow_id,
                documents=[
                    CreateDocumentRequest(
                        document_type_code=doc['type_code'],
                        document_number=doc['number'],
                        document_date=doc['date'],
                        file_content=file_bytes
                    )
                ]
            )

        log.info(f"Uploaded {len(documents)} documents")
        return {}

    async def _import_form_data(self, **context) -> Dict[str, Any]:
        """Step 3: Import form data to Kontur"""

        kontur_docflow_id = context['kontur_docflow_id']
        form_data = context['form_data']
        document_mode_id = context['document_mode_id']

        kontur = get_kontur_adapter()

        success = await kontur.import_form_json(
            docflow_id=kontur_docflow_id,
            form_id=document_mode_id,
            data=form_data
        )

        if not success:
            raise SagaStepError("Failed to import form data")

        log.info("Form data imported to Kontur")
        return {}

    async def _final_submission(self, **context) -> Dict[str, Any]:
        """Step 4: Final submission to FTS (via Kontur)"""

        kontur_docflow_id = context['kontur_docflow_id']

        # Kontur API: Mark docflow as ready for submission
        # (Actual FTS submission is handled by Kontur backend)

        kontur = get_kontur_adapter()

        # Placeholder: Kontur may have a "submit" endpoint
        # For now, just mark as opened (user viewed it)
        await kontur.set_opened_true(kontur_docflow_id)

        log.info(f"Declaration submitted to FTS: {kontur_docflow_id}")
        return {}

    async def _publish_completion(self, **context) -> Dict[str, Any]:
        """Step 5: Publish completion event"""

        declaration_id = context['declaration_id']
        kontur_docflow_id = context['kontur_docflow_id']

        # Send command to update aggregate
        await self.command_bus.send(
            UpdateDeclarationStatusFromKonturCommand(
                declaration_id=declaration_id,
                new_status=DocflowStatus.SENT.value,
                status_text="Отправлено в ФТС",
                saga_id=self.saga_id
            )
        )

        log.info(f"Declaration submission saga completed: {declaration_id}")
        return {}

    # =========================================================================
    # COMPENSATION (Rollback)
    # =========================================================================

    async def _delete_kontur_docflow(self, **context) -> None:
        """Compensation: Delete docflow from Kontur"""

        kontur_docflow_id = context.get('kontur_docflow_id')

        if not kontur_docflow_id:
            return  # Nothing to compensate

        # Kontur API doesn't have delete endpoint (!)
        # So we just log for manual cleanup
        log.warning(
            f"COMPENSATION: Kontur docflow {kontur_docflow_id} should be deleted manually"
        )
```

**Trigger:** CustomsDeclarationSubmitted event

```python
# Register saga trigger
saga_manager.register_trigger(
    event_type="CustomsDeclarationSubmitted",
    saga_class=DeclarationSubmissionSaga
)
```

---

## 10. API Router Design

### 10.1 Customs Declaration Router

```python
# app/api/routers/customs_router.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.api.models.customs_api_models import (
    CreateDeclarationRequest,
    DeclarationResponse,
    DeclarationListResponse,
    UpdateFormDataRequest,
    AttachDocumentRequest,
)
from app.security.jwt_auth import get_current_user
from app.customs.commands import (
    CreateCustomsDeclarationCommand,
    UpdateCustomsDeclarationFormDataCommand,
    SubmitDeclarationToKonturCommand,
    AttachDocumentToDeclarationCommand,
)
from app.customs.queries import (
    GetDeclarationByIdQuery,
    GetDeclarationsByCompanyQuery,
)

router = APIRouter()

@router.post("/declarations", status_code=status.HTTP_201_CREATED)
async def create_declaration(
    payload: CreateDeclarationRequest,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """
    Create new customs declaration (docflow).

    Creates declaration in DRAFT status. User can edit form data
    and attach documents before submission.
    """
    user_id = uuid.UUID(current_user_id)

    command = CreateCustomsDeclarationCommand(
        user_id=user_id,
        company_id=payload.company_id,
        name=payload.name,
        declaration_type=payload.declaration_type,
        procedure=payload.procedure,
        customs_office_code=payload.customs_office_code,
        organization_id=payload.organization_id,
        employee_id=payload.employee_id,
        document_mode_id=payload.document_mode_id,
        gf_code=payload.gf_code,
        form_data=payload.form_data
    )

    try:
        declaration_id = await command_bus.send(command)

        return {
            "declaration_id": str(declaration_id),
            "status": "created"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/declarations/{declaration_id}", response_model=DeclarationResponse)
async def get_declaration(
    declaration_id: str,
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    """Get declaration by ID"""
    user_id = uuid.UUID(current_user_id)
    decl_id = uuid.UUID(declaration_id)

    query = GetDeclarationByIdQuery(
        declaration_id=decl_id,
        user_id=user_id
    )

    declaration = await query_bus.query(query)

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found"
        )

    return DeclarationResponse.from_read_model(declaration)


@router.post("/declarations/{declaration_id}/submit")
async def submit_declaration(
    declaration_id: str,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """
    Submit declaration to Kontur/FTS.

    Triggers DeclarationSubmissionSaga which:
    1. Creates docflow in Kontur
    2. Uploads documents
    3. Imports form data
    4. Submits to FTS
    """
    user_id = uuid.UUID(current_user_id)
    decl_id = uuid.UUID(declaration_id)

    command = SubmitDeclarationToKonturCommand(
        declaration_id=decl_id,
        user_id=user_id
    )

    try:
        await command_bus.send(command)

        return {
            "status": "submitted",
            "message": "Declaration submitted to customs"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/declarations/{declaration_id}/form-data")
async def update_form_data(
    declaration_id: str,
    payload: UpdateFormDataRequest,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """Update form data (DRAFT only)"""
    user_id = uuid.UUID(current_user_id)
    decl_id = uuid.UUID(declaration_id)

    command = UpdateCustomsDeclarationFormDataCommand(
        declaration_id=decl_id,
        user_id=user_id,
        form_data=payload.form_data
    )

    try:
        await command_bus.send(command)

        return {"status": "updated"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/declarations/{declaration_id}/documents")
async def attach_document(
    declaration_id: str,
    payload: AttachDocumentRequest,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """Attach document to declaration"""
    user_id = uuid.UUID(current_user_id)
    decl_id = uuid.UUID(declaration_id)

    command = AttachDocumentToDeclarationCommand(
        declaration_id=decl_id,
        user_id=user_id,
        kontur_document_id=payload.kontur_document_id,
        document_type_code=payload.document_type_code,
        document_number=payload.document_number,
        document_date=payload.document_date,
        attached_to_goods=payload.attached_to_goods
    )

    try:
        await command_bus.send(command)

        return {"status": "attached"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
- [x] Kontur Adapter (DONE)
- [x] Kontur Config (DONE)
- [x] Kontur Models (DONE)
- [x] Reference DB Schema (DONE)
- [x] Documentation (DONE)

**Next:**
- [ ] Create `app/customs/` domain structure
- [ ] Implement CustomsDeclarationAggregate
- [ ] Implement CustomsDeclaration commands/events
- [ ] Implement CreateCustomsDeclarationHandler
- [ ] Implement CustomsProjector (@sync_projection for Created event)
- [ ] Test: Create declaration locally (no Kontur integration yet)

**Success Criteria:**
- User can create DRAFT declaration
- Declaration appears in read model
- Events stored in Event Store

### Phase 2: Core Operations (Week 3-4)

**Deliverables:**
- [ ] CommonOrgAggregate
- [ ] CommonOrg commands/events/handlers
- [ ] UpdateCustomsDeclarationHandler
- [ ] AttachDocumentHandler
- [ ] Query handlers for reference data
- [ ] API Router for declarations
- [ ] Frontend: Create declaration form

**Success Criteria:**
- User can create organizations
- User can create declarations with orgs
- User can update form data
- User can attach documents (metadata only)
- Frontend displays declarations list

### Phase 3: Kontur Integration (Week 5-6)

**Deliverables:**
- [ ] SubmitDeclarationToKonturHandler (with Kontur API)
- [ ] DeclarationSubmissionSaga
- [ ] KonturStatusSyncService (background job)
- [ ] UpdateDeclarationStatusHandler
- [ ] Frontend: Submit button + status display

**Success Criteria:**
- User can submit declaration to Kontur
- Saga creates docflow in Kontur
- Saga imports form data
- Status updates from Kontur (polling)
- Frontend shows real-time status

### Phase 4: Advanced Features (Week 7-8)

**Deliverables:**
- [ ] CopyDeclarationHandler (template pattern)
- [ ] Document upload (MinIO/S3 integration)
- [ ] Kontur document upload integration
- [ ] Print PDF feature
- [ ] Reference data sync service
- [ ] Frontend: Full form builder

**Success Criteria:**
- User can copy declarations
- User can upload document files
- Documents sent to Kontur
- User can print PDF from Kontur
- Reference data synced from Kontur

### Phase 5: Polish & Production (Week 9-10)

**Deliverables:**
- [ ] Error handling improvements
- [ ] Idempotency guards
- [ ] Performance optimization
- [ ] Monitoring/metrics
- [ ] Integration tests
- [ ] Load testing
- [ ] Documentation finalization

**Success Criteria:**
- 100% uptime during load test
- All edge cases handled
- Full test coverage (>80%)
- Production-ready

---

## 12. Open Questions

### 12.1 Kontur API Questions

**Q1:** Does Kontur have webhooks for status updates?
- **Impact:** If yes, no polling needed (simpler, more real-time)
- **Action:** Contact Kontur support to clarify

**Q2:** Can we delete/cancel docflows in Kontur?
- **Impact:** Affects compensation in saga
- **Action:** Test with sandbox account

**Q3:** What is the GTD number assignment process?
- **Impact:** When do we get GTD number (used as declaration identifier)
- **Action:** Test full submission flow in sandbox

### 12.2 Business Logic Questions

**Q4:** Can user edit declaration after submission?
- **Current assumption:** No (immutable after submission)
- **Action:** Confirm with business requirements

**Q5:** What happens when FTS rejects declaration?
- **Options:**
  a) User creates new declaration (copy pattern)
  b) User edits and resubmits (version pattern)
- **Action:** Confirm with business requirements

**Q6:** Do we need to support offline mode (work without Kontur)?
- **Current assumption:** No (always connected to Kontur)
- **Action:** Clarify with product team

### 12.3 Technical Questions

**Q7:** Should Documents be a separate aggregate?
- **Current recommendation:** No (value objects in Declaration)
- **Alternative:** Separate DocumentAggregate (if complex lifecycle)
- **Action:** Start with value objects, refactor if needed

**Q8:** How to handle large form data (>1MB)?
- **Options:**
  a) Store in JSONB (simple, but size limit)
  b) Store in MinIO/S3 (complex, but scalable)
- **Action:** Start with JSONB, monitor size

**Q9:** Do we need caching for Kontur API calls?
- **Recommendation:** Yes (for reference data: templates, options)
- **TTL:** 1 hour for options, 24 hours for templates
- **Action:** Implement in Kontur adapter (already has caching config)

---

## Conclusion

**Summary:**

Этот документ содержит полный анализ и архитектурный план для интеграции Kontur Declarant API в WellWon Platform.

**Ключевые решения:**
1. ✅ **Один домен `customs`** с двумя агрегатами (CustomsDeclaration, CommonOrg)
2. ✅ **Event Enrichment** pattern - handlers query reference data, enrich events
3. ✅ **Documents as Value Objects** - не отдельный aggregate
4. ✅ **Reference Data via Query Handlers** - no aggregates for read-only data
5. ✅ **DeclarationSubmissionSaga** - TRUE SAGA pattern for Kontur integration
6. ✅ **Status sync via polling** - background job every 5-10 minutes

**Next Steps:**
1. Начать с Phase 1: Create domain structure
2. Implement CustomsDeclarationAggregate
3. Implement CreateCustomsDeclarationHandler
4. Test locally (no Kontur yet)
5. Add Kontur integration in Phase 3

**Estimated Effort:**
- Phase 1 (Foundation): 2 weeks
- Phase 2 (Core Operations): 2 weeks
- Phase 3 (Kontur Integration): 2 weeks
- Phase 4 (Advanced Features): 2 weeks
- Phase 5 (Production Polish): 2 weeks
- **Total: 10 weeks** (2.5 months)

---

**Document Version:** 1.0
**Date:** 2025-12-03
**Status:** Draft for Review
**Next Review:** After Phase 1 completion
