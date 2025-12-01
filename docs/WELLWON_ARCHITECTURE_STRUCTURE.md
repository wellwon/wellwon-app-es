# WELLWON ARCHITECTURE STRUCTURE

**Дата:** 2025-11-25
**Архитектура:** Event Sourcing + CQRS + DDD + Hexagonal

---

## ПОЛНАЯ СТРУКТУРА ПРОЕКТА

```
app/
├── api/                              # API Layer (FastAPI)
│   ├── dependencies/                 # Dependency Injection
│   │   ├── __init__.py
│   │   ├── auth.py                  # get_current_user, require_auth
│   │   ├── bus.py                   # get_command_bus, get_query_bus
│   │   ├── telegram.py              # get_telegram_adapter
│   │   └── repositories.py          # get_*_repository
│   │
│   ├── models/                       # Pydantic API Models
│   │   ├── __init__.py
│   │   ├── user_account_api_models.py
│   │   ├── company_api_models.py
│   │   ├── chat_api_models.py
│   │   └── common_api_models.py
│   │
│   └── routers/                      # FastAPI Routers
│       ├── __init__.py
│       ├── user_account_router.py   # /api/user/*
│       ├── company_router.py        # /api/companies/*
│       ├── chat_router.py           # /api/chats/*
│       ├── message_router.py        # /api/messages/*
│       └── health_router.py         # /health, /ready
│
├── common/                           # Shared Code
│   ├── base/
│   │   ├── aggregate.py             # BaseAggregate
│   │   ├── command.py               # BaseCommand
│   │   ├── event.py                 # BaseDomainEvent
│   │   ├── query.py                 # BaseQuery
│   │   └── value_object.py          # BaseValueObject
│   │
│   ├── enums/
│   │   ├── chat_enums.py            # ChatType, MessageType, SyncDirection
│   │   ├── company_enums.py         # CompanyType, MemberRole
│   │   └── user_enums.py            # UserRole, UserStatus
│   │
│   └── exceptions/
│       ├── domain_exceptions.py
│       └── infrastructure_exceptions.py
│
├── config/                           # Configuration
│   ├── settings.py                  # Pydantic Settings
│   ├── telegram_config.py           # Telegram-specific settings
│   ├── database_config.py
│   ├── redis_config.py
│   └── logging_config.py
│
│
│ ═══════════════════════════════════════════════════════════════
│                        DOMAIN LAYER
│ ═══════════════════════════════════════════════════════════════
│
├── user_account/                     # USER ACCOUNT DOMAIN (READY)
│   ├── __init__.py
│   ├── aggregate.py                 # UserAccountAggregate
│   ├── commands.py                  # CreateUserAccount, Authenticate, etc.
│   ├── events.py                    # UserCreated, UserAuthenticated, etc.
│   ├── queries.py                   # GetUserById, GetUserByEmail
│   ├── read_models.py               # UserReadModel
│   ├── projectors.py                # UserAccountProjector
│   │
│   ├── command_handlers/
│   │   ├── __init__.py
│   │   ├── auth_handlers.py
│   │   ├── password_handlers.py
│   │   └── profile_handlers.py
│   │
│   └── query_handlers/
│       ├── __init__.py
│       └── user_query_handlers.py
│
├── company/                          # COMPANY DOMAIN (TO CREATE)
│   ├── __init__.py
│   ├── aggregate.py                 # CompanyAggregate
│   ├── commands.py
│   │   # CreateCompanyCommand
│   │   # UpdateCompanyCommand
│   │   # AddCompanyMemberCommand
│   │   # RemoveCompanyMemberCommand
│   │   # LookupCompanyByInnCommand
│   │
│   ├── events.py
│   │   # CompanyCreated
│   │   # CompanyUpdated
│   │   # CompanyMemberAdded
│   │   # CompanyMemberRemoved
│   │
│   ├── queries.py
│   │   # GetCompanyByIdQuery
│   │   # GetUserCompaniesQuery
│   │   # GetCompanyMembersQuery
│   │   # SearchCompanyByInnQuery
│   │
│   ├── read_models.py
│   │   # CompanyReadModel
│   │   # CompanyMemberReadModel
│   │   # CompanySummaryReadModel
│   │
│   ├── projectors.py                # CompanyProjector
│   ├── value_objects.py             # Address, ContactInfo
│   │
│   ├── command_handlers/
│   │   ├── __init__.py
│   │   ├── company_handlers.py
│   │   └── member_handlers.py
│   │
│   └── query_handlers/
│       ├── __init__.py
│       └── company_query_handlers.py
│
├── chat/                             # CHAT DOMAIN (TO CREATE)
│   ├── __init__.py
│   │
│   ├── aggregates/
│   │   ├── __init__.py
│   │   ├── chat_aggregate.py        # ChatAggregate
│   │   ├── message_aggregate.py     # MessageAggregate
│   │   └── participant_aggregate.py # ChatParticipantAggregate
│   │
│   ├── commands.py
│   │   # Chat Management
│   │   # CreateChatCommand
│   │   # UpdateChatCommand
│   │   # ArchiveChatCommand
│   │   # BindExternalChannelCommand
│   │   # UnbindExternalChannelCommand
│   │   #
│   │   # Participants
│   │   # AddParticipantCommand
│   │   # RemoveParticipantCommand
│   │   # UpdateParticipantRoleCommand
│   │   #
│   │   # Messaging
│   │   # SendMessageCommand
│   │   # ReceiveExternalMessageCommand
│   │   # EditMessageCommand
│   │   # DeleteMessageCommand
│   │   #
│   │   # Read Receipts
│   │   # MarkMessagesAsReadCommand
│   │
│   ├── events.py
│   │   # ChatCreated, ChatUpdated, ChatArchived
│   │   # ExternalChannelBound, ExternalChannelUnbound
│   │   # ParticipantAdded, ParticipantRemoved
│   │   # MessageSent, ExternalMessageReceived
│   │   # MessageEdited, MessageDeleted
│   │   # MessagesMarkedAsRead
│   │
│   ├── queries.py
│   │   # GetChatByIdQuery
│   │   # GetUserChatsQuery
│   │   # GetCompanyChatsQuery
│   │   # GetChatMessagesQuery (cursor pagination)
│   │   # GetUnreadCountQuery
│   │   # SearchMessagesQuery
│   │   # GetChatParticipantsQuery
│   │
│   ├── read_models.py
│   │   # ChatReadModel
│   │   # ChatListItemReadModel (with last_message, unread_count)
│   │   # MessageReadModel
│   │   # ParticipantReadModel
│   │
│   ├── projectors.py                # ChatProjector, MessageProjector
│   ├── value_objects.py             # MessageContent, FileMeta
│   │
│   ├── command_handlers/
│   │   ├── __init__.py
│   │   ├── chat_handlers.py
│   │   ├── message_handlers.py
│   │   └── participant_handlers.py
│   │
│   └── query_handlers/
│       ├── __init__.py
│       ├── chat_query_handlers.py
│       └── message_query_handlers.py
│
│
│ ═══════════════════════════════════════════════════════════════
│                     INFRASTRUCTURE LAYER
│ ═══════════════════════════════════════════════════════════════
│
├── infra/
│   │
│   ├── cqrs/                         # Command/Query Bus
│   │   ├── __init__.py
│   │   ├── command_bus.py
│   │   ├── query_bus.py
│   │   └── handler_registry.py
│   │
│   ├── event_store/                  # KurrentDB Event Store
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── repository.py            # EventStoreRepository
│   │   └── serialization.py
│   │
│   ├── event_bus/                    # RedPanda/Kafka Event Bus
│   │   ├── __init__.py
│   │   ├── producer.py
│   │   ├── consumer.py
│   │   └── topics.py
│   │
│   ├── persistence/                  # PostgreSQL + Redis
│   │   ├── __init__.py
│   │   ├── postgres/
│   │   │   ├── connection.py
│   │   │   └── migrations/
│   │   └── redis/
│   │       ├── client.py
│   │       ├── cache.py
│   │       └── pubsub.py
│   │
│   ├── read_repos/                   # Read Model Repositories
│   │   ├── __init__.py
│   │   ├── user_read_repo.py
│   │   ├── company_read_repo.py
│   │   ├── chat_read_repo.py
│   │   └── message_read_repo.py
│   │
│   ├── reliability/                  # Reliability Patterns
│   │   ├── circuit_breaker.py
│   │   ├── retry.py
│   │   └── distributed_lock.py
│   │
│   ├── saga/                         # Saga Orchestration
│   │   ├── __init__.py
│   │   ├── saga_manager.py
│   │   ├── saga_store.py
│   │   └── compensation.py
│   │
│   ├── worker_core/                  # Worker Infrastructure
│   │   ├── data_sync/
│   │   └── event_processor/
│   │       ├── domain_registry.py   # Register domain projectors
│   │       └── processor.py
│   │
│   │
│   │ ─────────────────────────────────────────────────────────
│   │                    ADAPTERS (External Systems)
│   │ ─────────────────────────────────────────────────────────
│   │
│   ├── telegram/                     # TELEGRAM ADAPTER
│   │   ├── __init__.py
│   │   │   # from .adapter import TelegramAdapter
│   │   │   # from .bot_client import TelegramBotClient
│   │   │   # from .mtproto_client import TelegramMTProtoClient
│   │   │
│   │   ├── adapter.py               # TelegramAdapter (main interface)
│   │   │   # class TelegramAdapter:
│   │   │   #     def __init__(bot_client, mtproto_client)
│   │   │   #     async def send_message(chat_id, text, topic_id)
│   │   │   #     async def send_file(chat_id, file_url, file_type)
│   │   │   #     async def download_file(file_id)
│   │   │   #     async def create_company_group(company_name)
│   │   │   #     async def create_chat_topic(group_id, topic_name)
│   │   │   #     @staticmethod normalize_chat_id(telegram_id)
│   │   │   #     @staticmethod denormalize_chat_id(normalized_id)
│   │   │
│   │   ├── bot_client.py            # aiogram 3.x Bot API
│   │   │   # class TelegramBotClient:
│   │   │   #     async def send_message()
│   │   │   #     async def send_photo()
│   │   │   #     async def send_document()
│   │   │   #     async def get_file()
│   │   │
│   │   ├── mtproto_client.py        # Telethon MTProto
│   │   │   # class TelegramMTProtoClient:
│   │   │   #     async def create_supergroup()
│   │   │   #     async def create_forum_topic()
│   │   │   #     async def update_forum_topic()
│   │   │   #     async def delete_forum_topic()
│   │   │   #     async def add_bot_as_admin()
│   │   │
│   │   ├── webhook.py               # FastAPI webhook endpoint
│   │   │   # router = APIRouter(prefix="/telegram")
│   │   │   # @router.post("/webhook/{bot_token}")
│   │   │
│   │   ├── listener.py              # Event listener (Chat Domain -> Telegram)
│   │   │   # class TelegramEventListener:
│   │   │   #     @subscribe_to("MessageSent")
│   │   │   #     @subscribe_to("ChatCreated")
│   │   │
│   │   ├── models.py                # Telegram-specific Pydantic models
│   │   │   # TelegramUpdate, TelegramMessage, TelegramUser
│   │   │
│   │   ├── rate_limiter.py          # Rate limiting for Telegram API
│   │   │   # class TelegramRateLimiter
│   │   │
│   │   └── session_manager.py       # Telethon session management
│   │       # class TelegramSessionManager
│   │
│   ├── dadata/                       # DADATA ADAPTER (Company lookup)
│   │   ├── __init__.py
│   │   ├── adapter.py               # DaDataAdapter
│   │   │   # async def find_company_by_inn(inn: str)
│   │   │   # async def suggest_company(query: str)
│   │   └── models.py
│   │
│   ├── file_storage/                 # FILE STORAGE ADAPTER (MinIO/S3)
│   │   ├── __init__.py
│   │   ├── adapter.py               # FileStorageAdapter
│   │   │   # async def upload(file_data, path)
│   │   │   # async def download(path)
│   │   │   # async def get_url(path)
│   │   │   # async def delete(path)
│   │   └── config.py
│   │
│   └── services/                     # Shared Infrastructure Services
│       ├── typing_service.py        # Ephemeral typing indicators (Redis)
│       │   # class TypingService:
│       │   #     async def start_typing(chat_id, user_id)
│       │   #     async def stop_typing(chat_id, user_id)
│       │   #     async def get_typing_users(chat_id)
│       │
│       └── presence_service.py      # Online/offline status
│
│
│ ═══════════════════════════════════════════════════════════════
│                        WSE (WebSocket Engine)
│ ═══════════════════════════════════════════════════════════════
│
├── wse/
│   ├── __init__.py
│   ├── core/
│   │   ├── manager.py               # WSE Connection Manager
│   │   └── protocol.py              # WSE Protocol
│   │
│   ├── publishers/                   # Domain Event -> WSE
│   │   ├── __init__.py
│   │   ├── domain_publisher.py      # Maps domain events to WSE events
│   │   │   # EVENT_MAPPING = {
│   │   │   #     'MessageSent': 'chat.message.new',
│   │   │   #     'ExternalMessageReceived': 'chat.message.new',
│   │   │   #     'MessageEdited': 'chat.message.edited',
│   │   │   #     'MessageDeleted': 'chat.message.deleted',
│   │   │   #     'MessagesMarkedAsRead': 'chat.read',
│   │   │   #     'CompanyCreated': 'company.created',
│   │   │   #     'CompanyMemberAdded': 'company.member.added',
│   │   │   # }
│   │   └── chat_publisher.py
│   │
│   ├── services/
│   │   └── subscription_service.py
│   │
│   └── websocket/
│       ├── router.py                # /ws endpoint
│       └── handlers.py
│
│
│ ═══════════════════════════════════════════════════════════════
│                           WORKERS
│ ═══════════════════════════════════════════════════════════════
│
├── workers/
│   ├── event_processor_worker.py    # Processes events from EventBus
│   ├── data_sync_worker.py          # Syncs read models
│   └── telegram_worker.py           # Background Telegram operations
│
│
│ ═══════════════════════════════════════════════════════════════
│                        APPLICATION CORE
│ ═══════════════════════════════════════════════════════════════
│
├── core/
│   ├── __init__.py
│   ├── app_state.py                 # Application state
│   ├── lifespan.py                  # Startup/shutdown
│   ├── middleware.py                # FastAPI middleware
│   ├── routes.py                    # Route setup
│   └── exceptions.py                # Exception handlers
│
├── security/
│   ├── jwt_auth.py
│   └── permissions.py
│
└── server.py                         # FastAPI entry point
```

---

## API ROUTES SUMMARY

| Route | Method | Handler | Description |
|-------|--------|---------|-------------|
| **User Account** |
| `/api/user/register` | POST | user_account_router | Register new user |
| `/api/user/login` | POST | user_account_router | Authenticate user |
| `/api/user/logout` | POST | user_account_router | Logout |
| `/api/user/me` | GET | user_account_router | Get current user profile |
| `/api/user/profile` | PATCH | user_account_router | Update profile |
| `/api/user/change-password` | POST | user_account_router | Change password |
| **Company** |
| `/api/companies` | GET | company_router | List user's companies |
| `/api/companies` | POST | company_router | Create company |
| `/api/companies/{id}` | GET | company_router | Get company by ID |
| `/api/companies/{id}` | PATCH | company_router | Update company |
| `/api/companies/{id}/members` | GET | company_router | List members |
| `/api/companies/{id}/members` | POST | company_router | Add member |
| `/api/companies/{id}/members/{user_id}` | DELETE | company_router | Remove member |
| `/api/companies/lookup/inn/{inn}` | GET | company_router | Lookup by INN (DaData) |
| **Chat** |
| `/api/chats` | GET | chat_router | List user's chats |
| `/api/chats` | POST | chat_router | Create chat |
| `/api/chats/{id}` | GET | chat_router | Get chat by ID |
| `/api/chats/{id}` | PATCH | chat_router | Update chat |
| `/api/chats/{id}/archive` | POST | chat_router | Archive chat |
| `/api/chats/{id}/participants` | GET | chat_router | List participants |
| `/api/chats/{id}/participants` | POST | chat_router | Add participant |
| `/api/chats/{id}/bind-telegram` | POST | chat_router | Bind to Telegram |
| **Messages** |
| `/api/chats/{chat_id}/messages` | GET | message_router | Get messages (paginated) |
| `/api/chats/{chat_id}/messages` | POST | message_router | Send message |
| `/api/messages/{id}` | PATCH | message_router | Edit message |
| `/api/messages/{id}` | DELETE | message_router | Delete message |
| `/api/chats/{chat_id}/read` | POST | message_router | Mark as read |
| `/api/chats/{chat_id}/typing` | POST | message_router | Typing indicator |
| **Telegram** |
| `/api/telegram/webhook/{token}` | POST | telegram/webhook | Telegram webhook |
| **WebSocket** |
| `/ws` | WS | wse/router | WebSocket connection |
| **Health** |
| `/health` | GET | health_router | Health check |
| `/ready` | GET | health_router | Readiness check |

---

## DATA FLOW DIAGRAMS

### 1. Send Message (Web -> Telegram)

```
Frontend                API                    Domain                   Infra
   │                     │                       │                        │
   │ POST /messages      │                       │                        │
   │────────────────────>│                       │                        │
   │                     │ SendMessageCommand    │                        │
   │                     │──────────────────────>│                        │
   │                     │                       │ MessageSent event      │
   │                     │                       │───────────────────────>│ EventBus
   │                     │                       │                        │
   │                     │                       │                        │──> TelegramEventListener
   │                     │                       │                        │    │
   │                     │                       │                        │    │ TelegramAdapter.send_message()
   │                     │                       │                        │    │──────────────────────────────>
   │                     │                       │                        │                              Telegram
   │                     │                       │                        │
   │                     │                       │                        │──> WSE Publisher
   │<────────────────────────────────────────────────────────────────────────── chat.message.new
   │                     │                       │                        │
```

### 2. Receive Message (Telegram -> Web)

```
Telegram              Webhook                  Domain                   Frontend
   │                     │                       │                        │
   │ POST /webhook       │                       │                        │
   │────────────────────>│                       │                        │
   │                     │ ReceiveExternalMessageCommand                  │
   │                     │──────────────────────>│                        │
   │                     │                       │ ExternalMessageReceived│
   │                     │                       │───────────────────────>│ EventBus
   │                     │                       │                        │
   │                     │                       │                        │──> WSE Publisher
   │                     │                       │                        │    │
   │                     │                       │                        │<───┘ chat.message.new
   │                     │                       │                        │────────────────────────────────>
   │                     │                       │                        │
```

### 3. Create Company with Telegram Group

```
Frontend              API                    Domain                   Telegram
   │                   │                       │                        │
   │ POST /companies   │                       │                        │
   │──────────────────>│                       │                        │
   │                   │ CreateCompanyCommand  │                        │
   │                   │──────────────────────>│                        │
   │                   │                       │ CompanyCreated event   │
   │                   │                       │───────────────────────>│ Saga
   │                   │                       │                        │
   │                   │                       │       CreateTelegramGroupStep
   │                   │                       │                        │──────────────────>
   │                   │                       │                        │  TelegramAdapter
   │                   │                       │                        │  .create_company_group()
   │                   │                       │                        │
   │                   │                       │       BindGroupToCompanyStep
   │                   │                       │<───────────────────────│
   │                   │                       │                        │
   │<──────────────────────────────────────────│                        │
   │  { company_id, telegram_group_id }        │                        │
```

---

## DEPENDENCIES BETWEEN COMPONENTS

```
                    ┌─────────────────┐
                    │   API Routers   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │   User     │  │  Company   │  │    Chat    │
     │  Account   │  │   Domain   │  │   Domain   │
     │   Domain   │  │            │  │            │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │     CQRS Bus           │
              │  (Command + Query)     │
              └───────────┬────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Event Store  │ │   Event Bus   │ │  Read Repos   │
│  (KurrentDB)  │ │  (RedPanda)   │ │  (PostgreSQL) │
└───────────────┘ └───────┬───────┘ └───────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Projectors  │ │  WSE Publisher│ │   Telegram    │
│               │ │               │ │   Listener    │
└───────────────┘ └───────┬───────┘ └───────┬───────┘
                          │                 │
                          ▼                 ▼
                  ┌───────────────┐ ┌───────────────┐
                  │   Frontend    │ │   Telegram    │
                  │  (WebSocket)  │ │   Adapter     │
                  └───────────────┘ └───────────────┘
```

---

## DOMAIN TO WSE EVENT MAPPING

```python
# app/wse/publishers/domain_publisher.py

EVENT_MAPPING = {
    # Chat Domain
    'ChatCreated': 'chat.created',
    'ChatUpdated': 'chat.updated',
    'ChatArchived': 'chat.archived',
    'MessageSent': 'chat.message.new',
    'ExternalMessageReceived': 'chat.message.new',
    'MessageEdited': 'chat.message.edited',
    'MessageDeleted': 'chat.message.deleted',
    'MessagesMarkedAsRead': 'chat.read',
    'ParticipantAdded': 'chat.participant.added',
    'ParticipantRemoved': 'chat.participant.removed',

    # Company Domain
    'CompanyCreated': 'company.created',
    'CompanyUpdated': 'company.updated',
    'CompanyMemberAdded': 'company.member.added',
    'CompanyMemberRemoved': 'company.member.removed',

    # User Account Domain
    'UserProfileUpdated': 'user.profile.updated',
}
```

---

## NEXT STEPS

1. [ ] Create `app/company/` domain
2. [ ] Create `app/chat/` domain
3. [ ] Create `app/infra/telegram/` adapter
4. [ ] Register domains in `domain_registry.py`
5. [ ] Create API routers
6. [ ] Create database migrations
7. [ ] Update frontend to use WSE
