# User Account Domain

**Version:** 1.0.0
**Last Updated:** 2025-12-01
**Status:** Production Ready

## Overview

The User Account domain handles all user-related functionality in WellWon:
- Authentication (register, login, logout)
- Profile management
- Password management
- Session management
- Admin operations
- External change detection (CES)

## Domain Structure

```
app/user_account/
├── aggregate.py              # UserAccountAggregate
├── commands.py               # Domain commands
├── events.py                 # Domain events
├── queries.py                # Domain queries
├── read_models.py            # Pydantic read models
├── projectors.py             # Event projectors (23 methods)
├── command_handlers/
│   ├── auth_handlers.py      # Register, login, logout
│   ├── password_handlers.py  # Password change, reset
│   ├── profile_handlers.py   # Profile updates
│   └── admin_handlers.py     # Admin operations
└── query_handlers/
    ├── auth_query_handlers.py
    ├── profile_query_handlers.py
    ├── session_query_handlers.py
    └── monitoring_query_handlers.py
```

## Events

### Authentication

| Event | Projection | Description |
|-------|------------|-------------|
| `UserAccountCreated` | SYNC | New user registered |
| `UserCreated` | SYNC | Legacy event (backward compat) |
| `UserAuthenticationSucceeded` | ASYNC | Login success |
| `UserAuthenticationFailed` | ASYNC | Login failure (audit) |
| `UserLoggedOut` | ASYNC | User logout |

### Profile

| Event | Projection | Description |
|-------|------------|-------------|
| `UserProfileUpdated` | SYNC | Profile data updated |
| `UserEmailVerified` | ASYNC | Email verified |

### Password

| Event | Projection | Description |
|-------|------------|-------------|
| `UserPasswordChanged` | ASYNC | Password changed |
| `UserPasswordResetViaSecret` | ASYNC | Password reset |

### Account Lifecycle

| Event | Projection | Description |
|-------|------------|-------------|
| `UserAccountDeleted` | SYNC | Account soft-deleted |
| `UserDeleted` | SYNC | Legacy soft-delete |
| `UserHardDeleted` | SYNC | Account permanently deleted |

### CES (Compensating Event System)

| Event | Projection | Description |
|-------|------------|-------------|
| `UserRoleChangedExternally` | SYNC | Role changed via admin panel |
| `UserStatusChangedExternally` | SYNC | Status changed externally |
| `UserTypeChangedExternally` | ASYNC | User type changed |
| `UserEmailVerifiedExternally` | ASYNC | Email verified externally |
| `UserDeveloperStatusChangedExternally` | ASYNC | Developer flag changed |
| `UserAdminFieldsChangedExternally` | ASYNC | Admin fields changed |

## Projector

```python
# app/user_account/projectors.py

class UserAccountProjector:
    def __init__(self, user_account_read_repo: UserAccountReadRepo):
        self.user_account_read_repo = user_account_read_repo

    # SYNC: User must exist immediately after registration
    @sync_projection("UserAccountCreated", priority=1, timeout=2.0)
    @monitor_projection
    async def on_user_created(self, envelope: EventEnvelope) -> None:
        await self.user_account_read_repo.insert_user(...)

    # SYNC: Profile updates must be visible immediately
    @sync_projection("UserProfileUpdated", priority=5)
    async def on_user_profile_updated(self, envelope: EventEnvelope) -> None:
        await self.user_account_read_repo.update_profile(...)

    # ASYNC: Login tracking doesn't need immediate consistency
    @async_projection("UserAuthenticationSucceeded")
    async def on_user_authentication_succeeded(self, envelope: EventEnvelope) -> None:
        await self.user_account_read_repo.update_last_login(...)

    # SYNC: CES role changes must be reflected immediately
    @sync_projection("UserRoleChangedExternally", priority=1)
    async def on_user_role_changed_externally(self, envelope: EventEnvelope) -> None:
        # Already changed in DB by trigger, just log
        log.info(f"User {envelope.aggregate_id} role changed externally")
```

## Read Model

### PostgreSQL Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),

    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    avatar_url TEXT,

    -- Telegram
    telegram_id BIGINT,
    telegram_username VARCHAR(100),

    -- Status
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    user_type VARCHAR(50) DEFAULT 'standard',

    -- Flags
    email_verified BOOLEAN DEFAULT FALSE,
    is_developer BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_status ON users(status);
```

## API Endpoints

```
# Authentication
POST   /api/auth/register           # Register new user
POST   /api/auth/login              # Login
POST   /api/auth/logout             # Logout
POST   /api/auth/refresh            # Refresh JWT token

# Profile
GET    /api/auth/me                 # Get current user
PATCH  /api/auth/profile            # Update profile
POST   /api/auth/avatar             # Upload avatar

# Password
POST   /api/auth/change-password    # Change password
POST   /api/auth/forgot-password    # Request reset
POST   /api/auth/reset-password     # Reset with token

# Admin (admin role required)
GET    /api/admin/users             # List users
PATCH  /api/admin/users/{id}/role   # Change role
PATCH  /api/admin/users/{id}/status # Change status
```

## JWT Authentication

### Token Structure

```python
{
    "sub": "user_uuid",
    "email": "user@example.com",
    "role": "user",
    "exp": 1234567890,
    "iat": 1234567800,
    "jti": "token_uuid",
    "fingerprint_hash": "sha256_hash"  # Device binding
}
```

### Token Flow

```
1. Login Request (email + password + fingerprint)
         ↓
2. Validate credentials
         ↓
3. Generate JWT with fingerprint_hash
         ↓
4. Store refresh token in Redis
         ↓
5. Return { access_token, refresh_token }
```

## CES (Compensating Event System)

CES handles external database changes (e.g., admin panel edits) by:

1. PostgreSQL trigger detects change
2. Trigger inserts into `external_changes` table
3. CES listener picks up change
4. Emits compensating event (e.g., `UserRoleChangedExternally`)
5. Event processed through normal projection flow

```sql
-- Trigger example
CREATE TRIGGER user_role_changed_trigger
AFTER UPDATE OF role ON users
FOR EACH ROW
WHEN (OLD.role IS DISTINCT FROM NEW.role)
EXECUTE FUNCTION emit_external_change('UserRoleChangedExternally');
```

## Statistics

| Metric | Count |
|--------|-------|
| SYNC projections | 8 |
| ASYNC projections | 15 |
| Total projections | 23 |
| Commands | 12 |
| Queries | 10 |
| Events | 20 |

## Security Considerations

1. **Password hashing**: bcrypt with cost factor 12
2. **JWT expiration**: Access 15min, Refresh 7 days
3. **Device fingerprinting**: Prevents token theft
4. **Rate limiting**: Login attempts limited
5. **Audit logging**: All auth events logged

## Related Documentation

- [PROJECTION_ARCHITECTURE.md](../architecture/PROJECTION_ARCHITECTURE.md)
- [CES_INTEGRATION_GUIDE.md](../../CES/CES_INTEGRATION_GUIDE.md)
- [JWT_FINGERPRINT_MIGRATION_GUIDE.md](../../reference/JWT_FINGERPRINT_MIGRATION_GUIDE.md)
