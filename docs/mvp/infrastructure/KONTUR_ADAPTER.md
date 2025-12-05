# KONTUR ADAPTER REFERENCE
**Production-Ready Russian Customs Declarant API Integration**

**Version:** 1.0
**Date:** 2025-12-03
**Status:** Production Ready

---

## TABLE OF CONTENTS

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Architecture](#3-architecture)
4. [Configuration](#4-configuration)
5. [API Reference (32 Endpoints)](#5-api-reference-32-endpoints)
6. [Reliability & Error Handling](#6-reliability--error-handling)
7. [Usage Patterns](#7-usage-patterns)
8. [Testing](#8-testing)
9. [Troubleshooting](#9-troubleshooting)
10. [Appendix](#10-appendix)

---

## 1. OVERVIEW

### 1.1 What is Kontur?

**Kontur Declarant** is a Russian customs declaration system used by customs brokers for electronic submission of customs declarations to the Federal Customs Service (FTS). The Kontur API provides programmatic access to:

- Create and manage customs declarations (DT - Declaration for Transport)
- Submit declarations to customs electronically
- Attach supporting documents
- Track declaration status
- Generate official forms (PDF, XML)
- Query reference data (customs offices, procedures, forms)

**Official Website:** https://kontur.ru/customs
**API Documentation:** https://developer.kontur.ru/doc/customs

### 1.2 Adapter Features

The WellWon Kontur Adapter is a production-ready Python integration that provides:

**32 API Endpoints across 8 Categories:**
1. **Organizations (2)** - Create/query common organizations
2. **Docflows (7)** - Create/manage customs declarations
3. **Documents (5)** - Attach supporting documents
4. **Forms (6)** - Import/export form data
5. **Templates (2)** - Query form templates
6. **Options (7)** - List reference data (offices, procedures)
7. **Print (2)** - Generate HTML/PDF previews
8. **Payments (1)** - Calculate customs duties

**Full Reliability Stack:**
- Circuit Breaker (prevents cascade failures)
- Retry Logic (exponential backoff)
- Rate Limiting (token bucket algorithm)
- Bulkhead Pattern (concurrency limits)
- Response Caching (configurable TTL)

**Production Features:**
- Lazy initialization (resources created on demand)
- Singleton pattern (`get_kontur_adapter()`)
- HTTPS enforcement (security)
- Async/await support (asyncio)
- Type hints (Pydantic models)
- Comprehensive logging

### 1.3 Endpoint Categories

| Category | Endpoints | Purpose |
|----------|-----------|---------|
| Organizations | 2 | Manage common organizations (contractors) |
| Docflows | 7 | Create/manage customs declarations |
| Documents | 5 | Attach supporting documents |
| Forms | 6 | Import/export form data |
| Templates | 2 | Query form templates |
| Options | 7 | List reference data |
| Print | 2 | Generate HTML/PDF |
| Payments | 1 | Calculate customs duties |
| **TOTAL** | **32** | Complete API coverage |

### 1.4 Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                     KonturAdapter                           │
│                   (Main Facade - 32 endpoints)              │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐       ┌────▼────┐      ┌────▼────┐
    │ Orgs    │       │Docflows │      │Documents│
    │ Client  │       │ Client  │      │ Client  │
    └────┬────┘       └────┬────┘      └────┬────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │ BaseClient  │
                    │ (Reliability│
                    │   Stack)    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   httpx     │
                    │AsyncClient  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Kontur API  │
                    └─────────────┘
```

---

## 2. QUICK START

### 2.1 Installation

The Kontur adapter is already installed in the WellWon Platform:

```bash
# Dependencies already in requirements.txt
httpx>=0.27.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

### 2.2 Basic Configuration

**Minimum Configuration (.env):**

```bash
# Required
KONTUR_API_KEY=your_api_key_here

# Optional (defaults)
KONTUR_ENVIRONMENT=production  # or "test"
```

**Get API Key:**
1. Contact Kontur support: support@kontur.ru
2. Request API key for your organization
3. Specify environment: production or test (sandbox)

### 2.3 First API Call

**Example: List Organizations**

```python
from app.infra.kontur.adapter import get_kontur_adapter

# Get singleton adapter instance
adapter = get_kontur_adapter()

# List organizations (async)
organizations = await adapter.list_organizations()

for org in organizations:
    print(f"{org.name} (INN: {org.inn})")
```

**Expected Output:**
```
ООО "Моя Компания" (INN: 7707083893)
ИП Иванов Иван Иванович (INN: 123456789012)
```

### 2.4 Hello World: Create Organization

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.kontur.models import CommonOrg

adapter = get_kontur_adapter()

# Create organization
org = CommonOrg(
    full_name="ООО Ромашка",
    short_name="Ромашка",
    inn="7707083893",
    address="Москва, ул. Ленина, 1"
)

result = await adapter.create_or_update_org(org)

if result:
    print(f"Organization created with ID: {result.id}")
else:
    print("Error creating organization")
```

---

## 3. ARCHITECTURE

### 3.1 Component Diagram

```
KonturAdapter (Facade)
├── _get_http_client() → httpx.AsyncClient (lazy)
│
├── _organizations → OrganizationsClient (lazy)
│   └── create_or_update_org()
│   └── get_or_create_org_by_inn()
│
├── _docflows → DocflowsClient (lazy)
│   └── list_docflows()
│   └── create_docflow()
│   └── copy_docflow()
│   └── search_docflows()
│   └── get_declaration_marks()
│   └── get_messages()
│   └── set_opened_true()
│
├── _documents → DocumentsClient (lazy)
│   └── list_documents()
│   └── create_documents()
│   └── attach_document_to_goods()
│   └── create_dts_with_calculator()
│   └── copy_document_from_dt()
│
├── _forms → FormsClient (lazy)
│   └── get_form_json()
│   └── import_form_json()
│   └── import_goods_data()
│   └── upload_form_file()
│   └── get_form_xml()
│   └── set_form_contractor()
│
├── _templates → TemplatesClient (lazy)
│   └── list_templates()
│   └── get_template()
│
├── _options → OptionsClient (lazy)
│   └── list_organizations()
│   └── list_employees()
│   └── list_declaration_types()
│   └── list_procedures()
│   └── list_singularities()
│   └── list_customs()
│   └── list_common_orgs()
│
├── _print → PrintClient (lazy)
│   └── print_html()
│   └── print_pdf()
│
└── _payments → PaymentsClient (lazy)
    └── calculate_vehicle_payments()
```

### 3.2 Lazy Initialization Pattern

All components use lazy initialization for optimal resource usage:

```python
@property
def _docflows(self) -> DocflowsClient:
    """Get DocflowsClient (lazy initialization)."""
    if self._docflows_client is None:
        self._docflows_client = DocflowsClient(
            self._get_http_client(),
            self.config
        )
    return self._docflows_client
```

**Benefits:**
- HTTP client created only when first API call is made
- Sub-clients created only when their methods are called
- Lower memory footprint
- Faster startup time

### 3.3 Singleton Pattern

The adapter uses singleton pattern to ensure one instance per application:

```python
@lru_cache(maxsize=1)
def get_kontur_adapter() -> KonturAdapter:
    """Get Kontur adapter singleton."""
    global _kontur_adapter_instance
    if _kontur_adapter_instance is None:
        _kontur_adapter_instance = KonturAdapter()
    return _kontur_adapter_instance
```

**Usage:**
```python
# Always returns same instance
adapter1 = get_kontur_adapter()
adapter2 = get_kontur_adapter()
assert adapter1 is adapter2  # True
```

### 3.4 Reliability Stack Execution Order

Every API request flows through the reliability stack in BaseClient:

```
Request
   │
   ▼
1. Cache Check (if enabled)
   │ ← Cache Hit? Return cached response
   │ ← Cache Miss? Continue ↓
   ▼
2. Rate Limiter (token bucket)
   │ ← Tokens available? Continue ↓
   │ ← No tokens? Wait for refill
   ▼
3. Bulkhead (concurrency limit)
   │ ← Slot available? Continue ↓
   │ ← No slots? Queue request
   ▼
4. Circuit Breaker
   │ ← Closed? Continue ↓
   │ ← Open? Fail fast (CircuitBreakerOpenError)
   │ ← Half-Open? Test request
   ▼
5. Retry Logic (exponential backoff)
   │ ← Try request
   │ ← Transient error? Retry (max 3×)
   │ ← Success or business error? Continue ↓
   ▼
6. HTTP Request (httpx)
   │
   ▼
Response
```

---

## 4. CONFIGURATION

### 4.1 Authentication

#### KONTUR_API_KEY (Required)

**Type:** `SecretStr`
**Default:** `""` (empty - will log warning)
**Description:** API key from Kontur (X-Kontur-ApiKey header)

```bash
KONTUR_API_KEY=your_api_key_here
```

**Security:**
- Stored as `SecretStr` (Pydantic)
- Never logged in plain text
- Required for all API operations
- Different keys for production vs test environments

### 4.2 Environment

#### KONTUR_ENVIRONMENT

**Type:** `str`
**Default:** `"production"`
**Options:** `"production"`, `"test"`
**Description:** Environment to use

```bash
KONTUR_ENVIRONMENT=test  # Use sandbox
```

**Environments:**
- **production**: `https://api-d.kontur.ru`
- **test**: `https://api-d.testkontur.ru` (sandbox)

#### KONTUR_BASE_URL_PRODUCTION

**Type:** `str`
**Default:** `"https://api-d.kontur.ru"`
**Description:** Production base URL

#### KONTUR_BASE_URL_TEST

**Type:** `str`
**Default:** `"https://api-d.testkontur.ru"`
**Description:** Test base URL (sandbox)

### 4.3 Timeouts

#### KONTUR_TIMEOUT_SECONDS

**Type:** `int`
**Default:** `30`
**Range:** `1-600`
**Description:** Default request timeout (seconds)

```bash
KONTUR_TIMEOUT_SECONDS=60  # Increase for slow networks
```

#### KONTUR_LONG_TIMEOUT_SECONDS

**Type:** `int`
**Default:** `120`
**Range:** `1-600`
**Description:** Long operations timeout (PDF generation, docflow creation)

```bash
KONTUR_LONG_TIMEOUT_SECONDS=180
```

#### KONTUR_UPLOAD_TIMEOUT_SECONDS

**Type:** `int`
**Default:** `300`
**Range:** `1-600`
**Description:** File upload timeout

```bash
KONTUR_UPLOAD_TIMEOUT_SECONDS=600  # 10 minutes for large files
```

### 4.4 Rate Limiting

#### KONTUR_MAX_REQUESTS_PER_SECOND

**Type:** `float`
**Default:** `10.0`
**Description:** Global rate limit (requests/second)

```bash
KONTUR_MAX_REQUESTS_PER_SECOND=5.0  # More conservative
```

**Algorithm:** Token bucket
**Behavior:** Blocks request until tokens available

#### KONTUR_MAX_REQUESTS_PER_MINUTE

**Type:** `int`
**Default:** `500`
**Description:** Per-minute rate limit

```bash
KONTUR_MAX_REQUESTS_PER_MINUTE=1000  # Higher limit
```

### 4.5 Retry Configuration

#### KONTUR_MAX_RETRIES

**Type:** `int`
**Default:** `3`
**Range:** `0-10`
**Description:** Maximum retry attempts

```bash
KONTUR_MAX_RETRIES=5  # More retries
```

#### KONTUR_RETRY_INITIAL_DELAY_MS

**Type:** `int`
**Default:** `1000` (1 second)
**Range:** `100-30000`
**Description:** Initial retry delay (milliseconds)

```bash
KONTUR_RETRY_INITIAL_DELAY_MS=500  # Faster retries
```

#### KONTUR_RETRY_MAX_DELAY_MS

**Type:** `int`
**Default:** `30000` (30 seconds)
**Range:** `1000-60000`
**Description:** Maximum retry delay

```bash
KONTUR_RETRY_MAX_DELAY_MS=60000  # 1 minute max
```

**Backoff Formula:** `delay = min(initial_delay * (2 ** attempt), max_delay)`

**Example:**
- Attempt 1: 1s
- Attempt 2: 2s
- Attempt 3: 4s
- Attempt 4: 8s (capped at max_delay if exceeded)

### 4.6 Circuit Breaker

#### KONTUR_CIRCUIT_BREAKER_FAILURE_THRESHOLD

**Type:** `int`
**Default:** `5`
**Range:** `1-100`
**Description:** Consecutive failures before opening circuit

```bash
KONTUR_CIRCUIT_BREAKER_FAILURE_THRESHOLD=10  # More tolerant
```

#### KONTUR_CIRCUIT_BREAKER_RESET_TIMEOUT

**Type:** `int`
**Default:** `60` (seconds)
**Range:** `10-600`
**Description:** Time before attempting reset (half-open state)

```bash
KONTUR_CIRCUIT_BREAKER_RESET_TIMEOUT=120  # 2 minutes
```

**States:**
- **Closed:** Normal operation (all requests pass through)
- **Open:** Circuit breaker tripped (all requests fail fast)
- **Half-Open:** Testing if service recovered (single test request)

### 4.7 Caching

#### KONTUR_ENABLE_CACHE

**Type:** `bool`
**Default:** `true`
**Description:** Enable response caching

```bash
KONTUR_ENABLE_CACHE=false  # Disable caching
```

#### KONTUR_CACHE_TTL_OPTIONS

**Type:** `int`
**Default:** `3600` (1 hour)
**Range:** `60-86400`
**Description:** Cache TTL for options endpoints (seconds)

```bash
KONTUR_CACHE_TTL_OPTIONS=7200  # 2 hours
```

**Cached Endpoints:**
- `list_organizations()`
- `list_employees()`
- `list_declaration_types()`
- `list_procedures()`
- `list_singularities()`
- `list_customs()`
- `list_common_orgs()`

#### KONTUR_CACHE_TTL_DOCFLOWS

**Type:** `int`
**Default:** `300` (5 minutes)
**Range:** `60-3600`
**Description:** Cache TTL for docflows

```bash
KONTUR_CACHE_TTL_DOCFLOWS=600  # 10 minutes
```

**Cached Endpoints:**
- `list_docflows()`

#### KONTUR_CACHE_TTL_TEMPLATES

**Type:** `int`
**Default:** `86400` (24 hours)
**Range:** `3600-604800`
**Description:** Cache TTL for templates

```bash
KONTUR_CACHE_TTL_TEMPLATES=172800  # 48 hours
```

**Cached Endpoints:**
- `list_templates()`
- `get_template()`

### 4.8 Feature Flags

#### KONTUR_ENABLE_CIRCUIT_BREAKER

**Type:** `bool`
**Default:** `true`
**Description:** Enable circuit breaker pattern

```bash
KONTUR_ENABLE_CIRCUIT_BREAKER=false  # For testing only
```

#### KONTUR_ENABLE_RETRY

**Type:** `bool`
**Default:** `true`
**Description:** Enable retry logic

```bash
KONTUR_ENABLE_RETRY=false  # Disable retries
```

#### KONTUR_ENABLE_RATE_LIMITING

**Type:** `bool`
**Default:** `true`
**Description:** Enable rate limiting

```bash
KONTUR_ENABLE_RATE_LIMITING=false  # Disable rate limiting
```

#### KONTUR_ENABLE_BULKHEAD

**Type:** `bool`
**Default:** `true`
**Description:** Enable bulkhead pattern (concurrency limits)

```bash
KONTUR_ENABLE_BULKHEAD=false  # Disable bulkhead
```

#### KONTUR_ENABLE_FALLBACK

**Type:** `bool`
**Default:** `true`
**Description:** Enable fallback mechanisms

```bash
KONTUR_ENABLE_FALLBACK=false  # Disable fallback
```

### 4.9 KonturConfig Properties

```python
from app.config.kontur_config import get_kontur_config

config = get_kontur_config()

# Get base URL based on environment
config.base_url  # "https://api-d.kontur.ru" or "https://api-d.testkontur.ru"

# Get full API URL with version
config.api_url  # "https://api-d.kontur.ru/common/v1"

# Get API key as plain string
config.get_api_key()  # "your_api_key_here"

# Check if configured
config.is_configured()  # True if API key is set
```

### 4.10 Configuration Validation

**HTTPS Enforcement:**

All URLs must use HTTPS (enforced by `@model_validator`):

```python
@model_validator(mode='after')
def validate_https_urls(self) -> 'KonturConfig':
    """Enforce HTTPS for all URLs (security requirement)"""
    for url_field in ['base_url_production', 'base_url_test']:
        url = getattr(self, url_field)
        if url and not url.startswith('https://'):
            raise ValueError(
                f"{url_field} must use HTTPS protocol for security. "
                f"Got: {url}"
            )
    return self
```

**Result:** HTTP URLs will raise `ValueError` on startup

---

## 5. API REFERENCE (32 Endpoints)

### 5.1 Organizations API (2 endpoints)

#### 5.1.1 create_or_update_org()

```python
async def create_or_update_org(
    self,
    org: CommonOrg
) -> Optional[CommonOrg]
```

**Purpose:** Create or update organization in common organizations database

**Parameters:**
- `org: CommonOrg` - Organization data
  - `full_name: str` - Full legal name (required)
  - `short_name: str` - Short name (required)
  - `inn: str` - Russian INN (tax ID) (required)
  - `address: str` - Legal address (required)
  - `id: Optional[str]` - Kontur organization ID (auto-generated if None)

**Returns:** `Optional[CommonOrg]`
- `CommonOrg` with ID on success
- `None` on error

**Use Case:** Add contractor/supplier to common organizations for later use in declarations

**Example:**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.kontur.models import CommonOrg

adapter = get_kontur_adapter()

org = CommonOrg(
    full_name="ООО Ромашка",
    short_name="Ромашка",
    inn="7707083893",
    address="Москва, ул. Ленина, 1"
)

result = await adapter.create_or_update_org(org)

if result:
    print(f"Organization created with ID: {result.id}")
    print(f"Full name: {result.full_name}")
else:
    print("Error creating organization")
```

**Error Handling:**
- Returns `None` on HTTP errors (400, 404, 500, etc.)
- Retries on transient errors (network timeout, 5xx)
- Circuit breaker protection

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/organizations`
- Headers: `X-Kontur-ApiKey`, `Content-Type: application/json`
- Body: JSON serialized `CommonOrg`

---

#### 5.1.2 get_or_create_org_by_inn()

```python
async def get_or_create_org_by_inn(
    self,
    inn: str
) -> Optional[CommonOrg]
```

**Purpose:** Get or create organization by Russian INN (tax ID). Auto-fetches company data from Russian business registries (EGRUL/EGRIP).

**Parameters:**
- `inn: str` - Russian INN
  - 10 digits for legal entities (companies)
  - 12 digits for individual entrepreneurs

**Returns:** `Optional[CommonOrg]`
- `CommonOrg` with auto-populated company data
- `None` on error (invalid INN, not found, network error)

**Use Case:** Auto-populate contractor data without manual entry

**Example:**

```python
adapter = get_kontur_adapter()

# Sberbank INN (example)
org = await adapter.get_or_create_org_by_inn("7707083893")

if org:
    print(f"Company: {org.full_name}")  # "ПАО Сбербанк"
    print(f"Short name: {org.short_name}")  # "Сбербанк"
    print(f"Address: {org.address}")  # Auto-fetched from registry
    print(f"Kontur ID: {org.id}")  # Created in Kontur
else:
    print("Company not found or error occurred")
```

**Notes:**
- INN validation performed by Kontur API
- Company data fetched from EGRUL (legal entities) or EGRIP (entrepreneurs)
- Cached for 1 hour (via `KONTUR_CACHE_TTL_OPTIONS`)
- May fail if INN not found in registries

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/organizations/by-inn/{inn}`
- Caching: Yes (1 hour)

---

### 5.2 Docflows API (7 endpoints)

#### 5.2.1 list_docflows()

```python
async def list_docflows(
    self,
    take: int = 1000,
    changed_from: Optional[int] = None,
    changed_to: Optional[int] = None,
    status: Optional[int] = None,
    skip: int = 0
) -> List[DocflowDto]
```

**Purpose:** List docflows (customs declarations) with filtering and pagination

**Parameters:**
- `take: int` - Number of results (max 1000, default 1000)
- `changed_from: Optional[int]` - Unix timestamp (filter by modification date)
- `changed_to: Optional[int]` - Unix timestamp
- `status: Optional[int]` - Docflow status code (e.g., 10 = submitted)
- `skip: int` - Pagination offset (default 0)

**Returns:** `List[DocflowDto]`
- Empty list if no docflows found
- List of `DocflowDto` objects with metadata

**Use Case:**
- Sync docflows from Kontur
- Display user's declarations
- Monitor declaration status

**Example:**

```python
import time

adapter = get_kontur_adapter()

# Get docflows changed in last 24 hours
yesterday = int(time.time()) - 86400

docflows = await adapter.list_docflows(
    take=100,
    changed_from=yesterday,
    status=10  # Status: Submitted
)

for df in docflows:
    print(f"ID: {df.id}")
    print(f"Number: {df.declaration_number}")
    print(f"Created: {df.created_at}")
    print(f"Status: {df.status}")
    print("---")
```

**Status Codes:**
- `1` - Draft
- `10` - Submitted
- `20` - Registered with customs
- `30` - Released
- `40` - Rejected

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows?take={take}&skip={skip}&changedFrom={from}&changedTo={to}&status={status}`
- Caching: Yes (5 minutes)

---

#### 5.2.2 create_docflow()

```python
async def create_docflow(
    self,
    request: CreateDocflowRequest
) -> Optional[DocflowDto]
```

**Purpose:** Create new docflow (customs declaration)

**Parameters:**
- `request: CreateDocflowRequest`
  - `gf_code: str` - Form code (e.g., "18003" for import DT)
  - `document_mode_id: str` - Form version (e.g., "1006107E")
  - `form_data: dict` - Form data (JSON matching template schema)

**Returns:** `Optional[DocflowDto]`
- `DocflowDto` with ID and metadata on success
- `None` on error

**Use Case:** Submit new customs declaration to Kontur

**Example:**

```python
from app.infra.kontur.models import CreateDocflowRequest

adapter = get_kontur_adapter()

request = CreateDocflowRequest(
    gf_code="18003",
    document_mode_id="1006107E",
    form_data={
        "declarationType": "IM",  # Import
        "customsProcedure": "40",  # Release for domestic consumption
        "goods": [
            {
                "itemNumber": 1,
                "hsCode": "8471300000",
                "description": "Portable computers",
                "quantity": 10,
                "customsValue": 50000
            }
        ]
    }
)

docflow = await adapter.create_docflow(request)

if docflow:
    print(f"Docflow created: {docflow.id}")
    print(f"Status: {docflow.status}")
else:
    print("Error creating docflow")
```

**Notes:**
- Uses long timeout (120s via `KONTUR_LONG_TIMEOUT_SECONDS`)
- Form data validated by Kontur API
- Circuit breaker protects against repeated failures
- Retry on transient errors (3 attempts)

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows`
- Timeout: Long (120s)

---

#### 5.2.3 copy_docflow()

```python
async def copy_docflow(
    self,
    request: CopyDocflowRequest
) -> Optional[DocflowDto]
```

**Purpose:** Copy existing docflow (use as template)

**Parameters:**
- `request: CopyDocflowRequest`
  - `source_docflow_id: str` - Docflow ID to copy from

**Returns:** `Optional[DocflowDto]`
- New `DocflowDto` (copy) with new ID
- `None` on error

**Use Case:** Create similar declarations quickly (reuse goods list, contractor, etc.)

**Example:**

```python
from app.infra.kontur.models import CopyDocflowRequest

adapter = get_kontur_adapter()

request = CopyDocflowRequest(
    source_docflow_id="d1234567-89ab-cdef-0123-456789abcdef"
)

copy = await adapter.copy_docflow(request)

if copy:
    print(f"Copy created: {copy.id}")
    print(f"Original: {request.source_docflow_id}")
else:
    print("Error copying docflow")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/copy`

---

#### 5.2.4 search_docflows()

```python
async def search_docflows(
    self,
    request: SearchDocflowRequest,
    take: int = 50,
    skip: int = 0
) -> List[DocflowDto]
```

**Purpose:** Advanced search for docflows with multiple criteria

**Parameters:**
- `request: SearchDocflowRequest`
  - `declaration_number: Optional[str]` - Full or partial declaration number
  - `customs_office_code: Optional[str]` - Customs office code
  - `contractor_inn: Optional[str]` - Contractor INN
  - `date_from: Optional[datetime]` - Created after
  - `date_to: Optional[datetime]` - Created before
- `take: int` - Results per page (default 50)
- `skip: int` - Pagination offset (default 0)

**Returns:** `List[DocflowDto]`
- List of matching docflows
- Empty list if no matches

**Use Case:**
- Full-text search
- Filtering by multiple criteria
- User search functionality

**Example:**

```python
from app.infra.kontur.models import SearchDocflowRequest

adapter = get_kontur_adapter()

request = SearchDocflowRequest(
    declaration_number="10702010/010124/0000123",
    customs_office_code="10702010"
)

results = await adapter.search_docflows(request, take=20)

for df in results:
    print(f"Found: {df.declaration_number}")
    print(f"Status: {df.status}")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/search`

---

#### 5.2.5 get_declaration_marks()

```python
async def get_declaration_marks(
    self,
    docflow_id: str
) -> List[DeclarationMark]
```

**Purpose:** Get customs marks/stamps on declaration

**Parameters:**
- `docflow_id: str` - Docflow UUID

**Returns:** `List[DeclarationMark]`
- List of marks (chronological order)
- Empty list if no marks

**Mark Types:**
- `IM` - Import mark
- `EK` - Export mark
- `RL` - Release mark
- `RJ` - Rejection mark
- `DT` - Declaration mark

**Use Case:**
- Check customs office responses
- Track submission status
- Display mark history

**Example:**

```python
adapter = get_kontur_adapter()

marks = await adapter.get_declaration_marks(docflow_id)

for mark in marks:
    print(f"Type: {mark.mark_type}")
    print(f"Date: {mark.mark_date}")
    print(f"Office: {mark.customs_office_code}")
    print(f"Data: {mark.mark_data}")
    print("---")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/marks`

---

#### 5.2.6 get_messages()

```python
async def get_messages(
    self,
    docflow_id: str
) -> List[DocflowMessage]
```

**Purpose:** Get message journal (exchange log with FTS - Federal Customs Service)

**Parameters:**
- `docflow_id: str` - Docflow UUID

**Returns:** `List[DocflowMessage]`
- List of messages (chronological order)
- Empty list if no messages

**Use Case:**
- Audit trail
- Debug submission issues
- Monitor communication with customs

**Example:**

```python
adapter = get_kontur_adapter()

messages = await adapter.get_messages(docflow_id)

for msg in messages:
    print(f"Timestamp: {msg.timestamp}")
    print(f"Type: {msg.message_type}")
    print(f"Status: {msg.status}")
    print(f"Description: {msg.description}")
    print("---")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/messages`

---

#### 5.2.7 set_opened_true()

```python
async def set_opened_true(
    self,
    docflow_id: str
) -> bool
```

**Purpose:** Mark docflow as opened/viewed

**Parameters:**
- `docflow_id: str` - Docflow UUID

**Returns:** `bool`
- `True` on success
- `False` on error

**Use Case:** Track when user views declaration (UX feature)

**Example:**

```python
adapter = get_kontur_adapter()

success = await adapter.set_opened_true(docflow_id)

if success:
    print("Docflow marked as opened")
else:
    print("Error marking docflow as opened")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/set-opened`

---

### 5.3 Documents API (5 endpoints)

#### 5.3.1 list_documents()

```python
async def list_documents(
    self,
    docflow_id: str
) -> List[DocumentRowDto]
```

**Purpose:** List all documents attached to a docflow

**Parameters:**
- `docflow_id: str` - Docflow UUID

**Returns:** `List[DocumentRowDto]`
- List of documents
- Empty list if no documents

**Example:**

```python
adapter = get_kontur_adapter()

documents = await adapter.list_documents(docflow_id)

for doc in documents:
    print(f"ID: {doc.id}")
    print(f"Type: {doc.document_type_code}")
    print(f"Number: {doc.document_number}")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/documents`

---

#### 5.3.2 create_documents()

```python
async def create_documents(
    self,
    docflow_id: str,
    documents: List[CreateDocumentRequest]
) -> List[DocumentRowDto]
```

**Purpose:** Create multiple documents in a docflow

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `documents: List[CreateDocumentRequest]` - List of documents to create
  - `document_type_code: str` - Document type (e.g., "INVOICE")
  - `document_number: str` - Document number
  - `document_date: str` - Document date (YYYY-MM-DD)

**Returns:** `List[DocumentRowDto]`
- List of created documents with IDs
- Empty list on error

**Example:**

```python
from app.infra.kontur.models import CreateDocumentRequest

adapter = get_kontur_adapter()

docs = [
    CreateDocumentRequest(
        document_type_code="INVOICE",
        document_number="INV-2024-001",
        document_date="2024-01-15"
    ),
    CreateDocumentRequest(
        document_type_code="PACKING_LIST",
        document_number="PL-2024-001",
        document_date="2024-01-15"
    )
]

result = await adapter.create_documents(docflow_id, docs)

for doc in result:
    print(f"Created document: {doc.id}")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/documents`

---

#### 5.3.3 attach_document_to_goods()

```python
async def attach_document_to_goods(
    self,
    docflow_id: str,
    document_id: str,
    good_numbers: str
) -> bool
```

**Purpose:** Attach document to specific goods in declaration

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `document_id: str` - Document ID
- `good_numbers: str` - Comma-separated good numbers (e.g., "1,2,3")

**Returns:** `bool`
- `True` on success
- `False` on error

**Example:**

```python
adapter = get_kontur_adapter()

# Attach invoice to goods 1 and 2
success = await adapter.attach_document_to_goods(
    docflow_id,
    document_id,
    "1,2"
)

if success:
    print("Document attached to goods 1 and 2")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/documents/{doc_id}/attach`

---

#### 5.3.4 create_dts_with_calculator()

```python
async def create_dts_with_calculator(
    self,
    docflow_id: str,
    dts_type: int,
    items: List[DistributionItem]
) -> Optional[DocumentRowDto]
```

**Purpose:** Create DTS (customs value distribution) using calculator

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `dts_type: int` - DTS type code
- `items: List[DistributionItem]` - Distribution items

**Returns:** `Optional[DocumentRowDto]`
- Created DTS document
- `None` on error

**Use Case:** Distribute invoice costs (freight, insurance) across goods items

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/dts/calculate`

---

#### 5.3.5 copy_document_from_dt()

```python
async def copy_document_from_dt(
    self,
    docflow_id: str,
    document_id: str
) -> bool
```

**Purpose:** Copy document data from DT (customs declaration)

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `document_id: str` - Document ID

**Returns:** `bool`
- `True` on success
- `False` on error

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/documents/{doc_id}/copy-from-dt`

---

### 5.4 Forms API (6 endpoints)

#### 5.4.1 get_form_json()

```python
async def get_form_json(
    self,
    docflow_id: str,
    form_id: str
) -> Optional[Dict[str, Any]]
```

**Purpose:** Get form data as JSON

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID (e.g., "dt" for customs declaration)

**Returns:** `Optional[Dict[str, Any]]`
- Form data as dictionary
- `None` on error

**Example:**

```python
adapter = get_kontur_adapter()

form_data = await adapter.get_form_json(docflow_id, "dt")

if form_data:
    print(f"Declaration type: {form_data.get('declarationType')}")
    print(f"Goods count: {len(form_data.get('goods', []))}")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/json`

---

#### 5.4.2 import_form_json()

```python
async def import_form_json(
    self,
    docflow_id: str,
    form_id: str,
    data: Dict[str, Any]
) -> bool
```

**Purpose:** Import form data from JSON

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID
- `data: Dict[str, Any]` - Form data (matches template schema)

**Returns:** `bool`
- `True` on success
- `False` on error

**Example:**

```python
adapter = get_kontur_adapter()

form_data = {
    "declarationType": "IM",
    "customsProcedure": "40",
    "goods": [...]
}

success = await adapter.import_form_json(
    docflow_id,
    "dt",
    form_data
)

if success:
    print("Form data imported")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/import-json`

---

#### 5.4.3 import_goods_data()

```python
async def import_goods_data(
    self,
    docflow_id: str,
    form_id: str,
    goods: List[Dict[str, Any]],
    clear_before: bool = False,
    preserve_attached: bool = False
) -> bool
```

**Purpose:** Import goods data in bulk

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID
- `goods: List[Dict[str, Any]]` - List of goods
- `clear_before: bool` - Clear existing goods before import (default False)
- `preserve_attached: bool` - Preserve attached documents (default False)

**Returns:** `bool`
- `True` on success
- `False` on error

**Example:**

```python
adapter = get_kontur_adapter()

goods = [
    {
        "itemNumber": 1,
        "hsCode": "8471300000",
        "description": "Portable computers",
        "quantity": 10,
        "customsValue": 50000
    },
    {
        "itemNumber": 2,
        "hsCode": "8473309000",
        "description": "Parts for computers",
        "quantity": 5,
        "customsValue": 25000
    }
]

success = await adapter.import_goods_data(
    docflow_id,
    "dt",
    goods,
    clear_before=True  # Replace all goods
)

if success:
    print(f"Imported {len(goods)} goods")
```

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/import-goods`

---

#### 5.4.4 upload_form_file()

```python
async def upload_form_file(
    self,
    docflow_id: str,
    form_id: str,
    file_bytes: bytes,
    filename: str
) -> bool
```

**Purpose:** Upload form file (Excel, XML, etc.)

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID
- `file_bytes: bytes` - File content
- `filename: str` - File name (with extension)

**Returns:** `bool`
- `True` on success
- `False` on error

**Example:**

```python
adapter = get_kontur_adapter()

with open("declaration.xlsx", "rb") as f:
    file_bytes = f.read()

success = await adapter.upload_form_file(
    docflow_id,
    "dt",
    file_bytes,
    "declaration.xlsx"
)

if success:
    print("File uploaded")
```

**Notes:**
- Uses upload timeout (300s via `KONTUR_UPLOAD_TIMEOUT_SECONDS`)
- Supports Excel (.xlsx), XML (.xml), text files (.txt)
- Max file size depends on Kontur API limits

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/upload`
- Timeout: Upload (300s)

---

#### 5.4.5 get_form_xml()

```python
async def get_form_xml(
    self,
    docflow_id: str,
    form_id: str
) -> Optional[bytes]
```

**Purpose:** Export form as XML

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID

**Returns:** `Optional[bytes]`
- XML content as bytes
- `None` on error

**Example:**

```python
adapter = get_kontur_adapter()

xml_bytes = await adapter.get_form_xml(docflow_id, "dt")

if xml_bytes:
    with open("declaration.xml", "wb") as f:
        f.write(xml_bytes)
    print("XML exported")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/xml`

---

#### 5.4.6 set_form_contractor()

```python
async def set_form_contractor(
    self,
    docflow_id: str,
    form_id: str,
    org_id: str,
    graph_number: str
) -> bool
```

**Purpose:** Set organization from CommonOrgs to a specific field

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID
- `org_id: str` - Organization ID (from CommonOrgs)
- `graph_number: str` - Field number in declaration (e.g., "8" for consignor)

**Returns:** `bool`
- `True` on success
- `False` on error

**Use Case:** Link contractor from common organizations to declaration field

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/set-contractor`

---

### 5.5 Templates API (2 endpoints)

#### 5.5.1 list_templates()

```python
async def list_templates(self) -> List[JsonTemplate]
```

**Purpose:** List all available JSON templates

**Parameters:** None

**Returns:** `List[JsonTemplate]`
- List of available templates
- Empty list if none (unlikely)

**Example:**

```python
adapter = get_kontur_adapter()

templates = await adapter.list_templates()

for tmpl in templates:
    print(f"ID: {tmpl.document_mode_id}")
    print(f"Name: {tmpl.name}")
    print(f"Form: {tmpl.gf_code}")
    print("---")
```

**Common Templates:**
- `1006107E` - DT (import/export declaration)
- `1006109E` - Transit declaration
- `1006111E` - Temporary import declaration

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/templates`
- Caching: Yes (24 hours)

---

#### 5.5.2 get_template()

```python
async def get_template(
    self,
    document_mode_id: str
) -> Optional[Dict[str, Any]]
```

**Purpose:** Get specific template structure

**Parameters:**
- `document_mode_id: str` - Template ID (e.g., "1006107E")

**Returns:** `Optional[Dict[str, Any]]`
- Template structure (schema, fields, validation rules)
- `None` on error

**Example:**

```python
adapter = get_kontur_adapter()

template = await adapter.get_template("1006107E")

if template:
    print(f"Schema: {template['schema']}")
    print(f"Fields: {len(template['fields'])}")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/templates/{id}`
- Caching: Yes (24 hours)

---

### 5.6 Options API (7 endpoints)

#### 5.6.1 list_organizations()

```python
async def list_organizations(self) -> List[OrganizationOption]
```

**Purpose:** List organizations available to current user

**Parameters:** None

**Returns:** `List[OrganizationOption]`
- List of user's organizations
- Empty list if none

**Example:**

```python
adapter = get_kontur_adapter()

orgs = await adapter.list_organizations()

for org in orgs:
    print(f"ID: {org.id}")
    print(f"Name: {org.name}")
    print(f"INN: {org.inn}")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/organizations`
- Caching: Yes (1 hour)

---

#### 5.6.2 list_employees()

```python
async def list_employees(
    self,
    org_id: str
) -> List[EmployeeOption]
```

**Purpose:** List employees for specific organization

**Parameters:**
- `org_id: str` - Organization ID

**Returns:** `List[EmployeeOption]`
- List of employees
- Empty list if none

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/organizations/{id}/employees`
- Caching: Yes (1 hour)

---

#### 5.6.3 list_declaration_types()

```python
async def list_declaration_types(self) -> List[DeclarationTypeOption]
```

**Purpose:** List movement directions (declaration types)

**Parameters:** None

**Returns:** `List[DeclarationTypeOption]`
- `IM` - Import
- `EX` - Export
- `TR` - Transit
- `TI` - Temporary import
- `TE` - Temporary export

**Example:**

```python
adapter = get_kontur_adapter()

types = await adapter.list_declaration_types()

for dtype in types:
    print(f"Code: {dtype.code}")
    print(f"Name: {dtype.name}")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/declaration-types`
- Caching: Yes (1 hour)

---

#### 5.6.4 list_procedures()

```python
async def list_procedures(
    self,
    declaration_type: str
) -> List[Dict[str, Any]]
```

**Purpose:** List customs procedures for specific declaration type

**Parameters:**
- `declaration_type: str` - Declaration type code (e.g., "IM")

**Returns:** `List[Dict[str, Any]]`
- List of procedures
- Empty list if none

**Example:**

```python
adapter = get_kontur_adapter()

procedures = await adapter.list_procedures("IM")

for proc in procedures:
    print(f"Code: {proc['code']}")
    print(f"Name: {proc['name']}")
```

**Common Procedures:**
- `40` - Release for domestic consumption (import)
- `10` - Export
- `51` - Temporary import

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/procedures?declarationType={type}`
- Caching: Yes (1 hour)

---

#### 5.6.5 list_singularities()

```python
async def list_singularities(
    self,
    procedure: str
) -> List[Dict[str, Any]]
```

**Purpose:** List declaration singularities (special features) for procedure

**Parameters:**
- `procedure: str` - Procedure code (e.g., "40")

**Returns:** `List[Dict[str, Any]]`
- List of singularities
- Empty list if none

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/singularities?procedure={code}`
- Caching: Yes (1 hour)

---

#### 5.6.6 list_customs()

```python
async def list_customs(self) -> List[CustomsOption]
```

**Purpose:** List customs posts/offices

**Parameters:** None

**Returns:** `List[CustomsOption]`
- List of customs offices
- Empty list if none (unlikely)

**Example:**

```python
adapter = get_kontur_adapter()

customs = await adapter.list_customs()

for office in customs:
    print(f"Code: {office.code}")  # 8-digit code
    print(f"Name: {office.name}")
    print(f"Address: {office.address}")
```

**Example Codes:**
- `10702010` - Московская таможня (Moscow Customs)
- `10714000` - Шереметьевская таможня (Sheremetyevo Customs)

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/customs`
- Caching: Yes (1 hour)

---

#### 5.6.7 list_common_orgs()

```python
async def list_common_orgs(self) -> List[Dict[str, Any]]
```

**Purpose:** List common organizations (contractors)

**Parameters:** None

**Returns:** `List[Dict[str, Any]]`
- List of common organizations
- Empty list if none

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/options/common-orgs`
- Caching: Yes (1 hour)

---

### 5.7 Print API (2 endpoints)

#### 5.7.1 print_html()

```python
async def print_html(
    self,
    docflow_id: str,
    form_id: str
) -> Optional[str]
```

**Purpose:** Generate HTML preview of form

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID

**Returns:** `Optional[str]`
- HTML content as string
- `None` on error

**Use Case:**
- Web preview before submission
- Email notifications
- Print preview

**Example:**

```python
adapter = get_kontur_adapter()

html = await adapter.print_html(docflow_id, "dt")

if html:
    # Save to file
    with open("declaration.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Or display in browser
    # webbrowser.open("declaration.html")
```

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/print-html`

---

#### 5.7.2 print_pdf()

```python
async def print_pdf(
    self,
    docflow_id: str,
    form_id: str
) -> Optional[bytes]
```

**Purpose:** Generate PDF of form for printing or submission

**Parameters:**
- `docflow_id: str` - Docflow UUID
- `form_id: str` - Form ID

**Returns:** `Optional[bytes]`
- PDF content as bytes
- `None` on error

**Use Case:**
- Official format for paper customs submission
- Archive storage
- Email attachments

**Example:**

```python
adapter = get_kontur_adapter()

pdf_bytes = await adapter.print_pdf(docflow_id, "dt")

if pdf_bytes:
    with open("declaration.pdf", "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF generated ({len(pdf_bytes)} bytes)")
```

**Notes:**
- Uses long timeout (120s via `KONTUR_LONG_TIMEOUT_SECONDS`)
- PDF generation is slow (5-10 seconds on Kontur backend)
- Consider running asynchronously in background job
- Cache generated PDFs if declaration unchanged

**HTTP Request:**
- Method: `GET`
- Endpoint: `/common/v1/docflows/{id}/forms/{form_id}/print-pdf`
- Timeout: Long (120s)

---

### 5.8 Payments API (1 endpoint)

#### 5.8.1 calculate_vehicle_payments()

```python
async def calculate_vehicle_payments(
    self,
    request: VehiclePaymentRequest
) -> Optional[VehiclePaymentResult]
```

**Purpose:** Calculate customs payments for vehicle import

**Parameters:**
- `request: VehiclePaymentRequest`
  - Vehicle details (VIN, year, engine volume, etc.)

**Returns:** `Optional[VehiclePaymentResult]`
- Calculated customs duty, VAT, recycling fee
- `None` on error

**Use Case:** Import of cars, trucks, motorcycles

**HTTP Request:**
- Method: `POST`
- Endpoint: `/common/v1/payments/vehicle`

---

## 6. RELIABILITY & ERROR HANDLING

### 6.1 Reliability Stack Architecture

Every API request flows through a comprehensive reliability stack in `BaseClient`:

```python
# Execution Order (app/infra/kontur/clients/base_client.py)

1. Cache Check (if enabled)
   ├─ Cache Hit? → Return cached response
   └─ Cache Miss? → Continue to step 2

2. Rate Limiter (token bucket algorithm)
   ├─ Tokens available? → Consume token, continue
   └─ No tokens? → Wait for token refill

3. Bulkhead (concurrency limit)
   ├─ Slot available? → Acquire slot, continue
   └─ No slots? → Queue request (with timeout)

4. Circuit Breaker
   ├─ Closed? → Continue to step 5
   ├─ Open? → Fail fast (CircuitBreakerOpenError)
   └─ Half-Open? → Allow single test request

5. Retry Logic (exponential backoff)
   ├─ Try HTTP request
   ├─ Success? → Return response
   ├─ Transient error? → Retry (max 3 attempts)
   └─ Business error? → Raise exception

6. HTTP Request (httpx)
   └─ Execute actual API call
```

### 6.2 Circuit Breaker Pattern

**Purpose:** Prevent cascade failures when Kontur API is down

**Configuration:**
- Failure threshold: 5 consecutive failures (configurable)
- Reset timeout: 60 seconds (configurable)
- States: Closed → Open → Half-Open → Closed

**State Machine:**

```
┌─────────┐
│ CLOSED  │ (Normal operation)
└────┬────┘
     │
     │ 5 consecutive failures
     ▼
┌─────────┐
│  OPEN   │ (All requests fail fast)
└────┬────┘
     │
     │ 60 seconds elapsed
     ▼
┌──────────┐
│HALF-OPEN │ (Test with single request)
└────┬─────┘
     │
     ├─ Success? → Return to CLOSED
     └─ Failure? → Return to OPEN
```

**Behavior by State:**

**Closed:**
- All requests pass through
- Failures increment counter
- After 5 failures → transition to Open

**Open:**
- All requests fail immediately (`CircuitBreakerOpenError`)
- No HTTP calls made
- After 60s → transition to Half-Open

**Half-Open:**
- Single test request allowed
- Success → transition to Closed (counter reset)
- Failure → transition to Open (extend timeout)

**Example:**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.reliability.circuit_breaker import CircuitBreakerOpenError

adapter = get_kontur_adapter()

# Circuit breaker opens after 5 consecutive failures
for i in range(10):
    try:
        result = await adapter.create_docflow(...)
        print(f"Attempt {i+1}: Success")
    except CircuitBreakerOpenError:
        print(f"Attempt {i+1}: Circuit breaker open - Kontur API down")
        break
    except Exception as e:
        print(f"Attempt {i+1}: Error - {e}")
```

### 6.3 Retry Logic

**Purpose:** Handle transient errors (network timeouts, server errors)

**Configuration:**
- Max retries: 3 attempts (configurable)
- Initial delay: 1000ms (configurable)
- Max delay: 30000ms (configurable)
- Backoff: Exponential

**Backoff Formula:**
```python
delay = min(initial_delay * (2 ** attempt), max_delay)
```

**Example Delays:**
- Attempt 1: 1s
- Attempt 2: 2s
- Attempt 3: 4s
- Attempt 4: 8s (capped at max_delay if > 30s)

**Retry Conditions:**

**Retried Errors:**
- Network errors (connection timeout, DNS failure)
- HTTP 5xx errors (500, 502, 503, 504)
- Timeout errors (`httpx.TimeoutError`)

**Not Retried:**
- HTTP 4xx errors (400, 401, 403, 404)
- Business validation errors
- Circuit breaker open errors

**Example:**

```python
# Automatic retry on transient errors (transparent to caller)
adapter = get_kontur_adapter()

try:
    result = await adapter.create_docflow(...)
    # If network error: retry 1s → 2s → 4s → fail
except httpx.TimeoutError:
    # All retries exhausted
    print("Kontur API timeout after 3 retries")
```

### 6.4 Rate Limiting

**Purpose:** Avoid HTTP 429 (Too Many Requests) from Kontur API

**Configuration:**
- Global limit: 10 requests/second (configurable)
- Per-minute limit: 500 requests/minute (configurable)
- Algorithm: Token bucket

**Token Bucket Algorithm:**

```python
class TokenBucket:
    capacity: int = 10        # Max tokens
    refill_rate: float = 10   # Tokens per second

    def consume(self, tokens: int = 1) -> bool:
        if self.current_tokens >= tokens:
            self.current_tokens -= tokens
            return True
        else:
            # Wait for refill
            wait_time = (tokens - self.current_tokens) / self.refill_rate
            await asyncio.sleep(wait_time)
            return self.consume(tokens)
```

**Behavior:**
- Requests consume 1 token
- Tokens refill at configured rate (10/s by default)
- Exceeding limit blocks request until tokens available
- No exceptions raised (transparent wait)

**Example:**

```python
# Rate limiting is transparent
adapter = get_kontur_adapter()

# 100 requests will be automatically rate-limited
for i in range(100):
    result = await adapter.list_docflows(take=10)
    # Automatically throttled to 10 req/s
```

### 6.5 Bulkhead Pattern

**Purpose:** Limit concurrent requests to prevent resource exhaustion

**Configuration:**
- Max concurrent requests: Configurable per client (default varies)
- Queue: Requests queued when limit reached
- Timeout: Queued requests timeout if not processed

**Behavior:**
```python
# Max 5 concurrent requests
semaphore = asyncio.Semaphore(5)

async def request():
    async with semaphore:
        # Only 5 requests execute concurrently
        # Others wait in queue
        return await http_client.get(...)
```

**Benefits:**
- Prevents overwhelming Kontur API
- Protects against resource exhaustion (memory, connections)
- Fair queuing (FIFO)

### 6.6 Caching Strategy

**Purpose:** Reduce API calls for static/slow-changing data

**Cache Levels:**

| Data Type | TTL | Endpoint(s) |
|-----------|-----|-------------|
| Templates | 24 hours | `list_templates()`, `get_template()` |
| Options | 1 hour | `list_organizations()`, `list_customs()`, etc. |
| Docflows | 5 minutes | `list_docflows()` |

**Cache Key Format:**

```python
# Template
"kontur:template:{document_mode_id}"

# Organizations
"kontur:organizations:{user_id}"

# Docflows
"kontur:docflows:{company_id}:{filters_hash}"
```

**Cache Implementation:**

```python
# Automatic caching in BaseClient
async def _request(self, method, endpoint, cache_ttl=None):
    if cache_ttl and self.config.enable_cache:
        cache_key = f"kontur:{endpoint}"

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Make request
        response = await self._http_request(method, endpoint)

        # Cache response
        await self.cache.setex(
            cache_key,
            cache_ttl,
            json.dumps(response)
        )

        return response
```

### 6.7 Error Types and Handling

#### 6.7.1 Transient Errors (Retried)

**Definition:** Temporary errors that may succeed on retry

**Examples:**
- Network timeout (`httpx.TimeoutError`)
- Connection refused (`httpx.ConnectError`)
- HTTP 500 (Internal Server Error)
- HTTP 502 (Bad Gateway)
- HTTP 503 (Service Unavailable)
- HTTP 504 (Gateway Timeout)

**Handling:**

```python
try:
    result = await adapter.create_docflow(...)
except httpx.TimeoutError:
    # Automatic retry (3 attempts with exponential backoff)
    # If all retries fail, exception raised
    log.error("Kontur API timeout after retries")
except httpx.ConnectError:
    # Automatic retry
    log.error("Cannot connect to Kontur API")
```

**Retry Behavior:**
- Attempt 1: Immediate
- Attempt 2: Wait 1s
- Attempt 3: Wait 2s
- Attempt 4: Wait 4s
- If all fail: Raise exception

---

#### 6.7.2 Business Errors (Not Retried)

**Definition:** Errors requiring user action (invalid data, auth failure)

**Examples:**
- HTTP 400 (Bad Request) - Invalid form data
- HTTP 401 (Unauthorized) - Invalid API key
- HTTP 403 (Forbidden) - No permission
- HTTP 404 (Not Found) - Resource doesn't exist
- HTTP 422 (Unprocessable Entity) - Validation error

**Handling:**

```python
try:
    result = await adapter.create_docflow(request)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 400:
        # Validation error - user must fix data
        errors = e.response.json()
        log.error(f"Invalid form data: {errors}")
        # Show errors to user

    elif e.response.status_code == 401:
        # Auth error - check API key
        log.critical("Kontur authentication failed - check KONTUR_API_KEY")
        # Alert admin

    elif e.response.status_code == 404:
        # Resource not found
        log.warning(f"Docflow not found: {docflow_id}")
        # Show "not found" message

    elif e.response.status_code == 422:
        # Validation error
        errors = e.response.json()
        log.error(f"Validation errors: {errors}")
        # Show validation errors to user
```

**No Retry:** Business errors will NOT be retried automatically

---

#### 6.7.3 Rate Limit Errors

**Example:**
- HTTP 429 (Too Many Requests)

**Handling:**

```python
# Rate limiter prevents this preemptively
# If encountered despite rate limiting:

try:
    result = await adapter.create_docflow(...)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        # Rate limit exceeded
        retry_after = e.response.headers.get("Retry-After", "60")
        log.warning(f"Rate limit exceeded - retry after {retry_after}s")

        # Exponential backoff (same as transient errors)
        await asyncio.sleep(int(retry_after))
        # Retry automatically
```

**Prevention:** Token bucket rate limiter prevents this in most cases

---

#### 6.7.4 Circuit Breaker Errors

**Example:**

```python
from app.infra.reliability.circuit_breaker import CircuitBreakerOpenError

try:
    result = await adapter.create_docflow(...)
except CircuitBreakerOpenError:
    log.error("Circuit breaker open - Kontur API unavailable")
    # Show user-friendly error message
    # "Customs service temporarily unavailable. Please try again in 1 minute."

    # Optional: Fallback logic
    # - Return cached data
    # - Queue request for later
    # - Use alternative service
```

**Behavior:**
- Circuit opens after 5 consecutive failures
- All requests fail immediately (no HTTP calls)
- Circuit resets after 60 seconds (half-open state)

---

## 7. USAGE PATTERNS

### 7.1 Pattern 1: In Command Handlers (Recommended)

**Use Case:** Write operations (submit declaration, create docflow, attach documents)

**Purpose:** Command handlers are the appropriate place for external API calls in Event Sourcing architecture (Phase 1, before Sagas)

**Example: Submit Declaration to Customs**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.kontur.models import CreateDocflowRequest
from app.customs.commands import SubmitDeclarationToCustomsCommand
import httpx

class SubmitDeclarationToCustomsHandler:
    """Command handler for submitting customs declaration to Kontur API"""

    def __init__(self, query_bus, aggregate_repository, event_publisher):
        self.query_bus = query_bus
        self.aggregate_repository = aggregate_repository
        self.event_publisher = event_publisher

    async def handle(self, command: SubmitDeclarationToCustomsCommand):
        # 1. Query reference data (form template, customs office)
        form_template = await self.query_bus.query(
            GetFormTemplateQuery(
                document_mode_id=command.document_mode_id
            )
        )

        customs_office = await self.query_bus.query(
            GetCustomsOfficeQuery(
                office_code=command.customs_office_code
            )
        )

        # 2. Load aggregate from event store
        aggregate = await self.aggregate_repository.load(
            command.declaration_id
        )

        # 3. Call Kontur API
        adapter = get_kontur_adapter()

        try:
            docflow_result = await adapter.create_docflow(
                CreateDocflowRequest(
                    gf_code=aggregate.state.gf_code,
                    document_mode_id=aggregate.state.document_mode_id,
                    form_data=aggregate.state.form_data
                )
            )
        except httpx.HTTPStatusError as e:
            # Handle error (emit error event)
            if e.response.status_code == 400:
                # Validation error
                aggregate.submission_failed(
                    error_type="validation_error",
                    error_code=e.response.status_code,
                    error_message=e.response.text
                )
            else:
                # Other error
                aggregate.submission_failed(
                    error_type="kontur_api_error",
                    error_code=e.response.status_code,
                    error_message=str(e)
                )

            # Publish events
            await self.event_publisher.publish_events(aggregate.uncommitted_events)
            return

        # 4. Emit event with Kontur data (event enrichment pattern)
        aggregate.submit_to_customs(
            kontur_docflow_id=docflow_result.id,
            submission_date=docflow_result.created_at,
            customs_office_code=command.customs_office_code,
            customs_office_name=customs_office.name  # Enrichment from reference data
        )

        # 5. Publish events to event store and event bus
        await self.event_publisher.publish_events(aggregate.uncommitted_events)
```

**Why This Pattern:**
- Command handlers are responsible for orchestrating write operations
- Kontur API is called synchronously (Phase 1, before Saga implementation)
- Events are enriched with Kontur response data (event enrichment pattern)
- Error handling emits error events (audit trail)
- Saga-ready design (easy to extract Kontur logic to Saga later)

---

### 7.2 Pattern 2: In Query Handlers (Read Operations)

**Use Case:** Fetch reference data (forms, templates, customs offices, procedures)

**Purpose:** Query handlers for read-only operations, especially reference data

**Example: List Available Forms**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.customs.queries import ListAvailableFormsQuery
from app.customs.read_models import FormTemplateDto

class ListAvailableFormsQueryHandler:
    """Query handler for listing available customs forms"""

    async def handle(self, query: ListAvailableFormsQuery):
        adapter = get_kontur_adapter()

        # Cached for 24 hours (KONTUR_CACHE_TTL_TEMPLATES)
        templates = await adapter.list_templates()

        return [
            FormTemplateDto(
                document_mode_id=t.document_mode_id,
                name=t.name,
                gf_code=t.gf_code,
                description=t.description
            )
            for t in templates
        ]
```

**Example: Get Customs Offices**

```python
from app.infra.kontur.adapter import get_kontur_adapter

class ListCustomsOfficesQueryHandler:
    """Query handler for listing customs offices"""

    async def handle(self, query: ListCustomsOfficesQuery):
        adapter = get_kontur_adapter()

        # Cached for 1 hour (KONTUR_CACHE_TTL_OPTIONS)
        customs = await adapter.list_customs()

        # Filter by region if specified
        if query.region:
            customs = [
                c for c in customs
                if c.code.startswith(query.region)
            ]

        return customs
```

**Why This Pattern:**
- Query handlers for read-only operations
- Caching reduces API calls (24h for templates, 1h for options)
- No side effects
- No events emitted

---

### 7.3 Pattern 3: In Application Services

**Use Case:** Cross-cutting operations, background jobs, data synchronization

**Purpose:** Services for batch operations and scheduled jobs

**Example: Sync Common Organizations from Kontur**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.persistence.postgres_connection import get_reference_db

class KonturSyncService:
    """Background service to sync reference data from Kontur API"""

    def __init__(self):
        self.adapter = get_kontur_adapter()
        self.ref_db = get_reference_db()

    async def sync_common_organizations(self):
        """Sync common organizations from Kontur to reference DB"""

        # 1. Fetch from Kontur API
        kontur_orgs = await self.adapter.list_common_orgs()

        # 2. Update reference DB (wellwon_reference)
        for org in kontur_orgs:
            await self.ref_db.execute(
                """
                INSERT INTO dc_common_orgs (
                    kontur_id, full_name, short_name, inn, address
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (kontur_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    short_name = EXCLUDED.short_name,
                    address = EXCLUDED.address,
                    updated_at = NOW()
                """,
                org["id"],
                org["full_name"],
                org["short_name"],
                org["inn"],
                org["address"]
            )

        print(f"Synced {len(kontur_orgs)} common organizations from Kontur")

    async def sync_customs_offices(self):
        """Sync customs offices from Kontur to reference DB"""

        # 1. Fetch from Kontur API
        customs = await self.adapter.list_customs()

        # 2. Update reference DB
        for office in customs:
            await self.ref_db.execute(
                """
                INSERT INTO dc_customs (
                    code, name, address, is_active
                )
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    address = EXCLUDED.address,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                """,
                office.code,
                office.name,
                office.address,
                True
            )

        print(f"Synced {len(customs)} customs offices from Kontur")
```

**Scheduled Execution:**

```python
# In background worker or cron job
from app.services.kontur_sync_service import KonturSyncService

sync_service = KonturSyncService()

# Run weekly
await sync_service.sync_common_organizations()
await sync_service.sync_customs_offices()
```

**Why This Pattern:**
- Services for batch operations
- Scheduled jobs (cron, background workers)
- Data synchronization
- No domain events (infrastructure concern)

---

### 7.4 Pattern 4: In Sagas (Future Implementation)

**Use Case:** Multi-step workflows with compensation logic

**Purpose:** Sagas orchestrate complex workflows across multiple aggregates/services

**Example: Declaration Submission Saga (Future)**

```python
from app.infra.kontur.adapter import get_kontur_adapter
from app.infra.saga.saga_base import SagaBase

class DeclarationSubmissionSaga(SagaBase):
    """
    Saga for orchestrating customs declaration submission workflow.

    Steps:
    1. Create docflow in Kontur
    2. Upload documents to Kontur
    3. Submit declaration to customs
    4. Poll for customs marks

    Compensation:
    - Delete docflow if any step fails
    """

    async def on_declaration_created(self, event: DeclarationCreated):
        """React to DeclarationCreated event"""
        adapter = get_kontur_adapter()

        # Step 1: Create docflow
        try:
            docflow = await adapter.create_docflow(
                CreateDocflowRequest(
                    gf_code=event.gf_code,
                    document_mode_id=event.document_mode_id,
                    form_data=event.form_data
                )
            )

            # Store docflow ID for compensation
            self.saga_data["docflow_id"] = docflow.id

        except Exception as e:
            # Emit failure event
            await self.emit_event(DeclarationSubmissionFailed(
                declaration_id=event.declaration_id,
                error_message=str(e)
            ))
            return

        # Step 2: Upload documents
        for doc_id in event.document_ids:
            try:
                # Upload document logic
                await adapter.create_documents(
                    docflow.id,
                    [CreateDocumentRequest(...)]
                )
            except Exception as e:
                # Compensation: Delete docflow
                await self.compensate_create_docflow(docflow.id)

                await self.emit_event(DeclarationSubmissionFailed(
                    declaration_id=event.declaration_id,
                    error_message=f"Document upload failed: {str(e)}"
                ))
                return

        # Step 3: Submit to customs (mark as submitted in Kontur)
        # ...

        # Emit success event
        await self.emit_event(DeclarationSubmittedToCustoms(
            declaration_id=event.declaration_id,
            kontur_docflow_id=docflow.id,
            submission_date=docflow.created_at
        ))

    async def compensate_create_docflow(self, docflow_id: str):
        """Compensation: Delete docflow on failure"""
        adapter = get_kontur_adapter()

        try:
            # Note: Kontur adapter doesn't have delete_docflow() yet
            # Would need to add this endpoint
            # await adapter.delete_docflow(docflow_id)
            pass
        except Exception as e:
            log.error(f"Compensation failed for docflow {docflow_id}: {e}")
```

**Why This Pattern (Future):**
- Sagas for complex multi-step workflows
- Compensation logic for failures
- Distributed transactions
- Currently NOT implemented (Phase 2 feature)
- Handler pattern (7.1) is simpler for Phase 1

---

## 8. TESTING

### 8.1 Test Environment Setup

**Configuration (.env.test):**

```bash
# Test environment (Kontur sandbox)
KONTUR_ENVIRONMENT=test
KONTUR_API_KEY=test_api_key_from_kontur_support
KONTUR_BASE_URL_TEST=https://api-d.testkontur.ru

# Optional: Disable reliability features for faster tests
KONTUR_ENABLE_CIRCUIT_BREAKER=false
KONTUR_ENABLE_RETRY=false
KONTUR_ENABLE_RATE_LIMITING=false
KONTUR_ENABLE_CACHE=false
```

**Kontur Sandbox:**
- Test environment: `https://api-d.testkontur.ru`
- Separate API key (request from Kontur support)
- Isolated test data (won't affect production)
- Same API as production

**Request Sandbox Access:**
1. Contact: support@kontur.ru
2. Subject: "API Sandbox Access Request"
3. Provide: Company name, INN, developer contact

---

### 8.2 Unit Testing (Mock Adapter)

**Purpose:** Test business logic without external API calls

**Example: Mock create_docflow()**

```python
import pytest
from unittest.mock import AsyncMock
from app.infra.kontur.adapter import KonturAdapter
from app.infra.kontur.models import DocflowDto, CreateDocflowRequest
from datetime import datetime

@pytest.fixture
def mock_adapter():
    """Create mocked Kontur adapter"""
    adapter = KonturAdapter()

    # Mock _docflows client
    adapter._docflows_client = AsyncMock()
    adapter._docflows_client.create = AsyncMock(
        return_value=DocflowDto(
            id="mock-docflow-123",
            declaration_number=None,
            created_at=datetime.now(),
            status=1  # Draft
        )
    )

    return adapter

async def test_submit_declaration(mock_adapter):
    """Test declaration submission with mocked adapter"""

    # Create test request
    request = CreateDocflowRequest(
        gf_code="18003",
        document_mode_id="1006107E",
        form_data={"declarationType": "IM"}
    )

    # Call adapter
    result = await mock_adapter.create_docflow(request)

    # Assertions
    assert result is not None
    assert result.id == "mock-docflow-123"
    assert result.status == 1

    # Verify mock was called
    mock_adapter._docflows_client.create.assert_called_once_with(request)
```

**Example: Test Error Handling**

```python
import pytest
from unittest.mock import AsyncMock
import httpx

async def test_create_docflow_error_handling(mock_adapter):
    """Test error handling when Kontur API returns 400"""

    # Mock API error
    mock_adapter._docflows_client.create = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Bad Request",
            request=...,
            response=httpx.Response(
                400,
                json={"errors": ["Invalid form data"]}
            )
        )
    )

    # Call adapter
    request = CreateDocflowRequest(...)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await mock_adapter.create_docflow(request)

    assert exc_info.value.response.status_code == 400
```

---

### 8.3 Integration Testing (Kontur Sandbox)

**Purpose:** Test actual integration with Kontur API (sandbox environment)

**Prerequisites:**
- Kontur sandbox API key
- KONTUR_ENVIRONMENT=test
- Network access to api-d.testkontur.ru

**Example: Test list_organizations()**

```python
import pytest
from app.infra.kontur.adapter import get_kontur_adapter
from app.config.kontur_config import get_kontur_config

@pytest.mark.integration
async def test_kontur_list_organizations():
    """Integration test: List organizations in sandbox"""

    # Verify test environment
    config = get_kontur_config()
    assert config.environment == "test"
    assert config.base_url == "https://api-d.testkontur.ru"

    # Get adapter
    adapter = get_kontur_adapter()

    # Call API
    orgs = await adapter.list_organizations()

    # Assertions
    assert isinstance(orgs, list)
    assert len(orgs) > 0  # Sandbox should have test data

    # Verify structure
    first_org = orgs[0]
    assert hasattr(first_org, "id")
    assert hasattr(first_org, "name")
    assert hasattr(first_org, "inn")
```

**Example: Test list_templates()**

```python
@pytest.mark.integration
async def test_kontur_list_templates():
    """Integration test: List form templates"""

    adapter = get_kontur_adapter()

    # Call API (cached for 24h)
    templates = await adapter.list_templates()

    # Assertions
    assert isinstance(templates, list)
    assert len(templates) > 0

    # Verify common templates exist
    template_ids = [t.document_mode_id for t in templates]
    assert "1006107E" in template_ids  # DT template

    # Verify structure
    first_template = templates[0]
    assert hasattr(first_template, "document_mode_id")
    assert hasattr(first_template, "name")
    assert hasattr(first_template, "gf_code")
```

**Example: Test get_template()**

```python
@pytest.mark.integration
async def test_kontur_get_template():
    """Integration test: Get specific template"""

    adapter = get_kontur_adapter()

    # Get DT template
    template = await adapter.get_template("1006107E")

    # Assertions
    assert template is not None
    assert isinstance(template, dict)
    assert "schema" in template
    assert "fields" in template
```

**Running Integration Tests:**

```bash
# Run only integration tests
pytest -m integration tests/integration/

# Skip integration tests
pytest -m "not integration" tests/
```

---

### 8.4 Error Handling Tests

**Example: Test Invalid API Key**

```python
@pytest.mark.integration
async def test_invalid_api_key():
    """Test behavior with invalid API key"""
    from app.infra.kontur.adapter import KonturAdapter
    from app.config.kontur_config import KonturConfig

    # Create adapter with invalid key
    config = KonturConfig(api_key="invalid_key_12345")
    adapter = KonturAdapter(config=config)

    # Should raise 401
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await adapter.list_organizations()

    assert exc_info.value.response.status_code == 401
```

**Example: Test Circuit Breaker**

```python
@pytest.mark.integration
async def test_circuit_breaker_opens():
    """Test circuit breaker opens after failures"""
    from app.infra.reliability.circuit_breaker import CircuitBreakerOpenError

    adapter = get_kontur_adapter()

    # Cause 5 consecutive failures
    for i in range(5):
        try:
            # Invalid docflow ID → 404
            await adapter.get_declaration_marks("invalid-id-123")
        except httpx.HTTPStatusError:
            pass

    # Circuit should be open now
    with pytest.raises(CircuitBreakerOpenError):
        await adapter.get_declaration_marks("another-invalid-id")
```

**Example: Test Retry Logic**

```python
@pytest.mark.integration
async def test_retry_on_timeout(monkeypatch):
    """Test retry logic on timeout"""
    import httpx
    from unittest.mock import AsyncMock

    adapter = get_kontur_adapter()

    # Mock HTTP client to raise timeout
    original_request = adapter._http_client.request
    call_count = 0

    async def mock_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("Timeout")
        return await original_request(*args, **kwargs)

    adapter._http_client.request = mock_request

    # Should retry 3 times, then succeed
    result = await adapter.list_templates()

    assert call_count == 3
    assert result is not None
```

---

## 9. TROUBLESHOOTING

### 9.1 Issue: "Kontur not configured"

**Symptom:**

```
WARNING: Kontur API key not configured. Kontur features will not work.
```

**Cause:** Missing `KONTUR_API_KEY` environment variable

**Solution:**

1. Check `.env` file:
   ```bash
   cat .env | grep KONTUR_API_KEY
   ```

2. Add API key:
   ```bash
   echo "KONTUR_API_KEY=your_api_key_here" >> .env
   ```

3. Restart application

**Verification:**

```python
from app.config.kontur_config import is_kontur_configured

assert is_kontur_configured() == True
```

---

### 9.2 Issue: "Authentication failed" (HTTP 401)

**Symptom:**

```
httpx.HTTPStatusError: 401 Unauthorized
```

**Cause:**
- Invalid API key
- Expired API key
- Wrong environment (production key in test environment)

**Solution:**

1. Check API key in `.env`:
   ```bash
   echo $KONTUR_API_KEY
   ```

2. Verify environment:
   ```python
   from app.config.kontur_config import get_kontur_config
   config = get_kontur_config()
   print(f"Environment: {config.environment}")
   print(f"Base URL: {config.base_url}")
   ```

3. Contact Kontur support:
   - Email: support@kontur.ru
   - Request: API key verification
   - Provide: Company name, INN

4. Check environment matching:
   - Production key → `KONTUR_ENVIRONMENT=production`
   - Test key → `KONTUR_ENVIRONMENT=test`

---

### 9.3 Issue: "Circuit breaker open"

**Symptom:**

```
CircuitBreakerOpenError: Circuit breaker is open
```

**Cause:** Too many consecutive failures (5+ by default)

**Solution:**

1. **Wait for reset** (60 seconds by default):
   ```python
   import asyncio
   await asyncio.sleep(60)
   # Try again
   ```

2. **Check Kontur service status:**
   - Website: https://status.kontur.ru
   - Check for outages or maintenance

3. **Review logs for root cause:**
   ```bash
   tail -f logs/wellwon.log | grep "kontur"
   ```

4. **Disable circuit breaker temporarily** (testing only):
   ```bash
   echo "KONTUR_ENABLE_CIRCUIT_BREAKER=false" >> .env.test
   ```

5. **Adjust threshold** (if too sensitive):
   ```bash
   # Increase tolerance
   echo "KONTUR_CIRCUIT_BREAKER_FAILURE_THRESHOLD=10" >> .env
   ```

---

### 9.4 Issue: "Rate limit exceeded" (HTTP 429)

**Symptom:**

```
httpx.HTTPStatusError: 429 Too Many Requests
```

**Cause:** Exceeded rate limits (10 req/s or 500 req/min by default)

**Solution:**

1. **Reduce request frequency:**
   ```python
   # Add delay between requests
   await asyncio.sleep(0.2)  # 5 req/s
   ```

2. **Lower rate limits:**
   ```bash
   echo "KONTUR_MAX_REQUESTS_PER_SECOND=5.0" >> .env
   ```

3. **Implement request batching:**
   ```python
   # Batch 100 requests
   results = []
   for batch in chunks(requests, 10):
       batch_results = await asyncio.gather(*[
           adapter.some_method(req) for req in batch
       ])
       results.extend(batch_results)
       await asyncio.sleep(1)  # Pause between batches
   ```

4. **Contact Kontur support for higher limits:**
   - Email: support@kontur.ru
   - Subject: "Rate Limit Increase Request"
   - Provide: Company name, use case, expected volume

---

### 9.5 Issue: Slow PDF generation

**Symptom:** `print_pdf()` takes 10+ seconds

**Cause:** PDF generation is inherently slow on Kontur backend (5-10s typical)

**Solution:**

1. **Already uses long timeout:**
   - Default: 120s (`KONTUR_LONG_TIMEOUT_SECONDS`)
   - No action needed

2. **Run asynchronously in background job:**
   ```python
   # FastAPI background task
   from fastapi import BackgroundTasks

   async def generate_pdf_task(docflow_id: str):
       adapter = get_kontur_adapter()
       pdf_bytes = await adapter.print_pdf(docflow_id, "dt")
       # Save to MinIO/S3
       await save_pdf_to_storage(docflow_id, pdf_bytes)

   @app.post("/declarations/{id}/generate-pdf")
   async def generate_pdf(id: str, background_tasks: BackgroundTasks):
       background_tasks.add_task(generate_pdf_task, id)
       return {"status": "generating", "message": "PDF will be ready in 1-2 minutes"}
   ```

3. **Cache generated PDFs:**
   ```python
   # Check if PDF already generated
   cached_pdf = await storage.get_pdf(docflow_id)
   if cached_pdf:
       return cached_pdf

   # Generate and cache
   pdf_bytes = await adapter.print_pdf(docflow_id, "dt")
   await storage.save_pdf(docflow_id, pdf_bytes)
   return pdf_bytes
   ```

---

### 9.6 Issue: "Timeout error"

**Symptom:**

```
httpx.TimeoutException: Request timeout
```

**Cause:**
- Kontur API slow
- Network issues
- Large request/response

**Solution:**

1. **Check network connectivity:**
   ```bash
   ping api-d.kontur.ru
   curl -I https://api-d.kontur.ru
   ```

2. **Increase timeout:**
   ```bash
   # For all requests
   echo "KONTUR_TIMEOUT_SECONDS=60" >> .env

   # For long operations only
   echo "KONTUR_LONG_TIMEOUT_SECONDS=180" >> .env
   ```

3. **Retry logic handles transient timeouts automatically:**
   ```python
   # Automatic retry (3 attempts)
   result = await adapter.create_docflow(...)
   # No manual retry needed
   ```

4. **Use long timeout for specific operations:**
   ```python
   # PDF generation, docflow creation already use long timeout
   # No action needed for these endpoints
   ```

---

### 9.7 Issue: "SSL Certificate Error"

**Symptom:**

```
httpx.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Cause:**
- Missing CA certificates
- Corporate proxy/firewall
- System time incorrect

**Solution:**

1. **Update CA certificates:**
   ```bash
   # macOS
   brew install ca-certificates

   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install ca-certificates

   # CentOS/RHEL
   sudo yum install ca-certificates
   ```

2. **Check system time:**
   ```bash
   date
   # Should match current time
   ```

3. **Corporate proxy:**
   ```bash
   # If behind corporate proxy
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

4. **Disable SSL verification** (NOT recommended for production):
   ```python
   # ONLY for testing/debugging
   import httpx
   client = httpx.AsyncClient(verify=False)
   ```

---

## 10. APPENDIX

### 10.1 HTTP Headers

**Request Headers (All Endpoints):**

```http
X-Kontur-ApiKey: {api_key}
Content-Type: application/json
Accept: application/json
```

**Important:** Kontur uses **custom `X-Kontur-ApiKey` header**, NOT `Authorization: Bearer`

**Example:**

```python
headers = {
    "X-Kontur-ApiKey": "your_api_key_here",
    "Content-Type": "application/json"
}
```

---

### 10.2 Response Types

**1. JSON (Default)**

Most endpoints return JSON:

```python
result = await adapter.list_organizations()
# Returns: List[OrganizationOption] (parsed from JSON)
```

**2. Text (HTML)**

`print_html()` returns HTML as string:

```python
html = await adapter.print_html(docflow_id, "dt")
# Returns: str (HTML content)
```

**3. Bytes (PDF, XML)**

Binary content returned as bytes:

```python
pdf_bytes = await adapter.print_pdf(docflow_id, "dt")
# Returns: bytes (PDF content)

xml_bytes = await adapter.get_form_xml(docflow_id, "dt")
# Returns: bytes (XML content)
```

---

### 10.3 API URL Structure

**Production:**

```
Base URL:  https://api-d.kontur.ru
API URL:   https://api-d.kontur.ru/common/v1
```

**Test (Sandbox):**

```
Base URL:  https://api-d.testkontur.ru
API URL:   https://api-d.testkontur.ru/common/v1
```

**Endpoint Examples:**

```
Organizations:  {api_url}/organizations
Docflows:       {api_url}/docflows
Documents:      {api_url}/docflows/{id}/documents
Forms:          {api_url}/docflows/{id}/forms/{form_id}
Templates:      {api_url}/templates
Options:        {api_url}/options/organizations
Print:          {api_url}/docflows/{id}/forms/{form_id}/print-pdf
Payments:       {api_url}/payments/vehicle
```

---

### 10.4 Source Code Reference

**Main Files:**

| File | Lines | Purpose |
|------|-------|---------|
| `/app/infra/kontur/adapter.py` | 469 | Main adapter facade (32 endpoints) |
| `/app/config/kontur_config.py` | 125 | Configuration (26 env vars) |
| `/app/infra/kontur/clients/base_client.py` | ~400 | Reliability stack (circuit breaker, retry, etc.) |
| `/app/core/startup/adapters.py` | 69 | Initialization at startup |
| `/app/infra/kontur/models.py` | ~500 | Pydantic models for API requests/responses |

**Client Files:**

| File | Endpoints | Purpose |
|------|-----------|---------|
| `/app/infra/kontur/clients/organizations_client.py` | 2 | Organizations API |
| `/app/infra/kontur/clients/docflows_client.py` | 7 | Docflows API |
| `/app/infra/kontur/clients/documents_client.py` | 5 | Documents API |
| `/app/infra/kontur/clients/forms_client.py` | 6 | Forms API |
| `/app/infra/kontur/clients/templates_client.py` | 2 | Templates API |
| `/app/infra/kontur/clients/options_client.py` | 7 | Options API |
| `/app/infra/kontur/clients/print_client.py` | 2 | Print API |
| `/app/infra/kontur/clients/payments_client.py` | 1 | Payments API |

---

### 10.5 Official Documentation

**Kontur Resources:**

- **API Documentation:** https://developer.kontur.ru/doc/customs
- **Status Page:** https://status.kontur.ru
- **Support Email:** support@kontur.ru
- **Phone:** +7 (495) 785-08-00
- **Developer Portal:** https://developer.kontur.ru

**WellWon Resources:**

- **Architecture:** `/docs/mvp/architecture/`
- **Dual Database:** `/docs/mvp/architecture/MULTI_DATABASE_SETUP.md`
- **Customs Domain:** `/docs/mvp/domains/CUSTOMS_ARCHITECTURE.md` (future)
- **Event Sourcing:** `/docs/reference/infrastructure/`
- **Saga Patterns:** `/docs/reference/sagas/`

---

### 10.6 Model Definitions

**Key Pydantic Models:**

```python
# Organizations
class CommonOrg(BaseModel):
    id: Optional[str] = None
    full_name: str
    short_name: str
    inn: str
    address: str

# Docflows
class DocflowDto(BaseModel):
    id: str
    declaration_number: Optional[str] = None
    created_at: datetime
    status: int

class CreateDocflowRequest(BaseModel):
    gf_code: str
    document_mode_id: str
    form_data: dict

class CopyDocflowRequest(BaseModel):
    source_docflow_id: str

class SearchDocflowRequest(BaseModel):
    declaration_number: Optional[str] = None
    customs_office_code: Optional[str] = None
    contractor_inn: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

# Documents
class CreateDocumentRequest(BaseModel):
    document_type_code: str
    document_number: str
    document_date: str  # YYYY-MM-DD

class DocumentRowDto(BaseModel):
    id: str
    document_type_code: str
    document_number: str

# Templates
class JsonTemplate(BaseModel):
    document_mode_id: str
    name: str
    gf_code: str
    description: Optional[str] = None

# Options
class OrganizationOption(BaseModel):
    id: str
    name: str
    inn: str

class CustomsOption(BaseModel):
    code: str  # 8-digit code
    name: str
    address: Optional[str] = None

class DeclarationTypeOption(BaseModel):
    code: str  # IM, EX, TR, TI, TE
    name: str

# Marks
class DeclarationMark(BaseModel):
    mark_id: str
    mark_type: str  # IM, EK, RL, RJ, DT
    mark_date: datetime
    customs_office_code: str
    mark_data: dict

# Messages
class DocflowMessage(BaseModel):
    timestamp: datetime
    message_type: str
    status: str
    description: str
```

---

### 10.7 Environment Variable Summary

**Quick Reference (26 Environment Variables):**

| Variable | Default | Type | Purpose |
|----------|---------|------|---------|
| `KONTUR_API_KEY` | `""` | `SecretStr` | **Required** API key |
| `KONTUR_ENVIRONMENT` | `production` | `str` | Environment (production/test) |
| `KONTUR_BASE_URL_PRODUCTION` | `https://api-d.kontur.ru` | `str` | Production URL |
| `KONTUR_BASE_URL_TEST` | `https://api-d.testkontur.ru` | `str` | Test URL |
| `KONTUR_TIMEOUT_SECONDS` | `30` | `int` | Default timeout |
| `KONTUR_LONG_TIMEOUT_SECONDS` | `120` | `int` | Long operations timeout |
| `KONTUR_UPLOAD_TIMEOUT_SECONDS` | `300` | `int` | Upload timeout |
| `KONTUR_MAX_REQUESTS_PER_SECOND` | `10.0` | `float` | Rate limit (req/s) |
| `KONTUR_MAX_REQUESTS_PER_MINUTE` | `500` | `int` | Rate limit (req/min) |
| `KONTUR_MAX_RETRIES` | `3` | `int` | Max retry attempts |
| `KONTUR_RETRY_INITIAL_DELAY_MS` | `1000` | `int` | Initial retry delay |
| `KONTUR_RETRY_MAX_DELAY_MS` | `30000` | `int` | Max retry delay |
| `KONTUR_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | `int` | Failures before open |
| `KONTUR_CIRCUIT_BREAKER_RESET_TIMEOUT` | `60` | `int` | Reset timeout (s) |
| `KONTUR_ENABLE_CACHE` | `true` | `bool` | Enable caching |
| `KONTUR_CACHE_TTL_OPTIONS` | `3600` | `int` | Options cache TTL (s) |
| `KONTUR_CACHE_TTL_DOCFLOWS` | `300` | `int` | Docflows cache TTL (s) |
| `KONTUR_CACHE_TTL_TEMPLATES` | `86400` | `int` | Templates cache TTL (s) |
| `KONTUR_ENABLE_CIRCUIT_BREAKER` | `true` | `bool` | Feature flag |
| `KONTUR_ENABLE_RETRY` | `true` | `bool` | Feature flag |
| `KONTUR_ENABLE_RATE_LIMITING` | `true` | `bool` | Feature flag |
| `KONTUR_ENABLE_BULKHEAD` | `true` | `bool` | Feature flag |
| `KONTUR_ENABLE_FALLBACK` | `true` | `bool` | Feature flag |

---

### 10.8 Common Status Codes

**Kontur API HTTP Status Codes:**

| Code | Meaning | Retry? | Action |
|------|---------|--------|--------|
| 200 | OK | - | Success |
| 400 | Bad Request | No | Fix data |
| 401 | Unauthorized | No | Check API key |
| 403 | Forbidden | No | Check permissions |
| 404 | Not Found | No | Check resource ID |
| 422 | Unprocessable Entity | No | Fix validation errors |
| 429 | Too Many Requests | Yes | Reduce frequency |
| 500 | Internal Server Error | Yes | Retry |
| 502 | Bad Gateway | Yes | Retry |
| 503 | Service Unavailable | Yes | Retry |
| 504 | Gateway Timeout | Yes | Retry |

---

## END OF DOCUMENTATION

**Document Version:** 1.0
**Date:** 2025-12-03
**Author:** WellWon Platform Team
**Status:** Production Ready

**Feedback:** For documentation feedback or corrections, please contact the development team or submit an issue.

---

**Copyright © 2025 WellWon Platform. All rights reserved.**
