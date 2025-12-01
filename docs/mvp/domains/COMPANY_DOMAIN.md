# Company Domain Implementation

**Status:** Complete
**Last Updated:** 2025-11-25

## Overview

The Company Domain manages all company-related operations in the WellWon platform, including company lifecycle, user-company relationships, Telegram supergroup integration, and balance management.

## Architecture

```
app/company/
├── __init__.py              # Domain marker
├── enums.py                 # Domain enumerations
├── events.py                # Domain events (13 events)
├── commands.py              # Commands (12 commands)
├── aggregate.py             # CompanyAggregate with Event Sourcing
├── exceptions.py            # Domain-specific exceptions
├── read_models.py           # Read models for PostgreSQL
├── queries.py               # CQRS queries and result types
├── projectors.py            # Event projectors
├── command_handlers/        # Command handler modules
│   └── __init__.py
└── query_handlers/          # Query handler modules
    └── __init__.py
```

## Enumerations

### CompanyType
```python
class CompanyType(str, Enum):
    COMPANY = "company"      # Standard company
    PROJECT = "project"      # Project-based entity
    INDIVIDUAL = "individual" # Individual entrepreneur
```

### UserCompanyRelationship
```python
class UserCompanyRelationship(str, Enum):
    OWNER = "owner"          # Company owner (full permissions)
    PARTICIPANT = "participant" # General participant
    DECLARANT = "declarant"  # Customs declarant
    ACCOUNTANT = "accountant" # Financial role
    MANAGER = "manager"      # Operational manager
```

### CompanyStatus
```python
class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
```

## Domain Events

### Company Lifecycle Events

| Event | Description | Key Fields |
|-------|-------------|------------|
| `CompanyCreated` | New company created | company_id, name, company_type, created_by, legal info, contacts |
| `CompanyUpdated` | Company details updated | company_id, updated_by, changed fields |
| `CompanyArchived` | Company soft-deleted | company_id, archived_by, reason |
| `CompanyRestored` | Archived company restored | company_id, restored_by |
| `CompanyDeleted` | Company hard-deleted | company_id, deleted_by |

### User-Company Relationship Events

| Event | Description | Key Fields |
|-------|-------------|------------|
| `UserAddedToCompany` | User associated with company | company_id, user_id, relationship_type, added_by |
| `UserRemovedFromCompany` | User removed from company | company_id, user_id, removed_by, reason |
| `UserCompanyRoleChanged` | User role updated | company_id, user_id, old/new relationship_type, changed_by |

### Telegram Integration Events

| Event | Description | Key Fields |
|-------|-------------|------------|
| `TelegramSupergroupCreated` | New supergroup created for company | company_id, telegram_group_id, title, invite_link, is_forum |
| `TelegramSupergroupLinked` | Existing supergroup linked | company_id, telegram_group_id, linked_by |
| `TelegramSupergroupUnlinked` | Supergroup unlinked | company_id, telegram_group_id, unlinked_by |
| `TelegramSupergroupUpdated` | Supergroup info updated | company_id, telegram_group_id, title, description |

### Balance Events

| Event | Description | Key Fields |
|-------|-------------|------------|
| `CompanyBalanceUpdated` | Balance changed | company_id, old_balance, new_balance, change_amount, reason, reference_id |

## Commands

### Company Lifecycle Commands

```python
# Create new company
CreateCompanyCommand(
    company_id: UUID,        # Optional, auto-generated
    name: str,               # Required
    company_type: str,       # "company", "project", "individual"
    created_by: UUID,        # Required
    # Legal info (Russian business)
    vat: str,                # INN
    ogrn: str,
    kpp: str,
    # Address
    postal_code: str,
    country_id: int,         # Default: 190 (Russia)
    city: str,
    street: str,
    # Contacts
    director: str,
    email: str,
    phone: str,
    # Telegram contacts
    tg_dir: str,
    tg_accountant: str,
    tg_manager_1: str,
    tg_manager_2: str,
    tg_manager_3: str,
    tg_support: str,
)

# Update company
UpdateCompanyCommand(company_id, updated_by, **changed_fields)

# Archive/Restore/Delete
ArchiveCompanyCommand(company_id, archived_by, reason)
RestoreCompanyCommand(company_id, restored_by)
DeleteCompanyCommand(company_id, deleted_by)
```

### User-Company Commands

```python
# Add user to company
AddUserToCompanyCommand(
    company_id: UUID,
    user_id: UUID,
    relationship_type: str,  # "owner", "participant", "declarant", etc.
    added_by: UUID,
)

# Remove user from company
RemoveUserFromCompanyCommand(company_id, user_id, removed_by, reason)

# Change user role
ChangeUserCompanyRoleCommand(company_id, user_id, new_relationship_type, changed_by)
```

### Telegram Commands

```python
# Create supergroup
CreateTelegramSupergroupCommand(
    company_id: UUID,
    telegram_group_id: int,
    title: str,
    username: str,
    description: str,
    invite_link: str,
    is_forum: bool,
    created_by: UUID,
)

# Link/Unlink existing supergroup
LinkTelegramSupergroupCommand(company_id, telegram_group_id, linked_by)
UnlinkTelegramSupergroupCommand(company_id, telegram_group_id, unlinked_by)

# Update supergroup info
UpdateTelegramSupergroupCommand(company_id, telegram_group_id, title, description, invite_link)
```

### Balance Commands

```python
# Update balance
UpdateCompanyBalanceCommand(
    company_id: UUID,
    change_amount: Decimal,  # Positive to add, negative to subtract
    reason: str,
    reference_id: str,       # Order ID, transaction ID, etc.
    updated_by: UUID,
)
```

## Aggregate

### CompanyAggregate

The aggregate enforces all business rules:

```python
class CompanyAggregate:
    """Company Aggregate Root for Event Sourcing"""

    def __init__(self, company_id: UUID):
        self.id = company_id
        self.version = 0
        self.state = CompanyAggregateState(company_id=company_id)
        self._uncommitted_events = []
```

### Business Rules Enforced

1. **Company Lifecycle**
   - Cannot create duplicate companies
   - Cannot modify archived/deleted companies
   - Only owners can archive/delete companies

2. **User Relationships**
   - Cannot add user already in company
   - Cannot remove user not in company
   - Cannot remove company owner
   - Only owners can change user roles

3. **Telegram Integration**
   - Cannot link already-linked supergroup
   - Cannot unlink non-existent supergroup

4. **Balance Management**
   - Cannot have negative balance
   - All changes tracked with reason and reference

### State Management

```python
class CompanyAggregateState:
    company_id: UUID
    name: str
    company_type: str
    is_active: bool
    is_deleted: bool

    # Legal info
    vat: str              # INN
    ogrn: str
    kpp: str

    # Address
    postal_code: str
    country_id: int
    city: str
    street: str

    # Balance
    balance: Decimal

    # Relationships
    users: Dict[str, UserCompanyState]
    telegram_supergroups: Dict[str, TelegramSupergroupState]
```

### Snapshot Support

The aggregate supports snapshots for efficient replay:

```python
# Create snapshot
snapshot = aggregate.create_snapshot()

# Restore from snapshot
aggregate.restore_from_snapshot(snapshot_data)

# Replay from events
aggregate = CompanyAggregate.replay_from_events(company_id, events)
```

## Read Models

### CompanyReadModel
Full company details for PostgreSQL `companies` table.

### UserCompanyReadModel
User-company relationships for `user_companies` table.

### TelegramSupergroupReadModel
Telegram supergroups for `telegram_supergroups` table.

### BalanceTransactionReadModel
Balance transaction history for `company_balance_transactions` table.

### Composite Models
- `CompanyWithUsersReadModel` - Company with all users
- `CompanyWithTelegramReadModel` - Company with supergroups
- `CompanyListItemReadModel` - For list views
- `UserCompanyListItemReadModel` - User's companies list

## Queries

```python
# Company queries
GetCompanyByIdQuery(company_id)
GetCompaniesQuery(include_archived, include_deleted, limit, offset)
GetCompaniesByUserQuery(user_id, include_archived, limit, offset)
SearchCompaniesQuery(search_term, limit)
GetCompanyByVatQuery(vat)

# User-company queries
GetCompanyUsersQuery(company_id, include_inactive)
GetUserCompanyRelationshipQuery(company_id, user_id)

# Telegram queries
GetCompanyTelegramSupergroupsQuery(company_id)
GetCompanyByTelegramGroupQuery(telegram_group_id)

# Balance queries
GetCompanyBalanceQuery(company_id)
GetCompanyBalanceHistoryQuery(company_id, limit, offset)
```

## Projectors

The `CompanyProjector` handles all domain events and updates read models:

```python
class CompanyProjector:
    def __init__(self, company_read_repo: CompanyReadRepo):
        self.company_read_repo = company_read_repo

    @sync_projection("CompanyCreated")
    @monitor_projection
    async def on_company_created(self, envelope: EventEnvelope) -> None:
        # Insert company into read model
        ...

    @sync_projection("UserAddedToCompany")
    @monitor_projection
    async def on_user_added_to_company(self, envelope: EventEnvelope) -> None:
        # Insert user-company relationship
        # Increment user count
        ...
```

## Exceptions

| Exception | Description |
|-----------|-------------|
| `CompanyError` | Base exception for Company domain |
| `CompanyNotFoundError` | Company not found |
| `CompanyAlreadyExistsError` | Company already exists |
| `CompanyInactiveError` | Company is not active |
| `UserNotInCompanyError` | User not associated with company |
| `UserAlreadyInCompanyError` | User already in company |
| `InsufficientCompanyPermissionsError` | Permission denied |
| `TelegramSupergroupNotFoundError` | Supergroup not found |
| `TelegramSupergroupAlreadyLinkedError` | Supergroup already linked |
| `InsufficientBalanceError` | Insufficient balance |
| `CannotRemoveOwnerError` | Cannot remove owner from company |

## Russian Business Entity Support

The domain fully supports Russian business requirements:

| Field | Russian Term | Description |
|-------|--------------|-------------|
| `vat` | INN | Tax Identification Number |
| `ogrn` | OGRN | Primary State Registration Number |
| `kpp` | KPP | Tax Registration Reason Code |

## Integration with Other Domains

### Chat Domain
- Company ID links chats to companies
- Telegram supergroups create chat topics

### User Account Domain
- Users are linked to companies via relationships
- User permissions derived from relationship type

### Payment Domain (Future)
- Company balance for financial operations
- Transaction references link to payments

## Next Steps

1. Create command handlers in `command_handlers/`
2. Create query handlers in `query_handlers/`
3. Create `CompanyReadRepo` in `app/infra/read_repos/`
4. Create API router in `app/api/routers/company_router.py`
5. Register domain in `domain_registry.py`
6. Create database migrations
