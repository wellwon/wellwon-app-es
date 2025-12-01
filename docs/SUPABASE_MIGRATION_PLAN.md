# ПЛАН МИГРАЦИИ SUPABASE → EVENT SOURCING

**Дата создания:** 2025-11-25
**Статус:** В разработке
**Философия:** Толстый бэкенд (CQRS/ES/DDD) + Тонкий фронтенд

---

## СОДЕРЖАНИЕ

1. [Обзор текущего состояния](#1-обзор-текущего-состояния)
2. [Анализ Supabase схемы](#2-анализ-supabase-схемы)
3. [Анализ Edge Functions](#3-анализ-edge-functions)
4. [Необходимые домены](#4-необходимые-домены)
5. [План миграции по фазам](#5-план-миграции-по-фазам)
6. [Технические решения](#6-технические-решения)

---

## 1. ОБЗОР ТЕКУЩЕГО СОСТОЯНИЯ

### Что есть в WellWon (Event Sourcing)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| User Account Domain | ✅ 100% | Полностью готов |
| Event Store (KurrentDB) | ✅ Готов | 10 лет хранения событий |
| CQRS Bus | ✅ Готов | Command/Query Bus |
| Event Bus (RedPanda) | ✅ Готов | Kafka-совместимый |
| WSE (WebSocket Engine) | ✅ Готов | Real-time через Redis PubSub |
| Saga Pattern | ✅ Готов | Распределённые транзакции |
| Projectors | ✅ Готов | Sync/Async проекции |

### Что было в Supabase (прототип)

- **158 миграций** - SQL схема
- **11 Edge Functions** - Serverless функции
- **15 таблиц** - Основные данные
- **Supabase Realtime** - Real-time подписки
- **RLS Policies** - Row Level Security

---

## 2. АНАЛИЗ SUPABASE СХЕМЫ

### 2.1 Таблицы по доменам

#### USER DOMAIN (уже мигрирован)
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `profiles` | ✅ Мигрирован | → UserAccountAggregate |
| `user_companies` | ⏳ Частично | Связь user↔company |

#### COMPANY DOMAIN (нужен новый домен)
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `companies` | ❌ Не мигрирован | Основная сущность |
| `user_companies` | ❌ Не мигрирован | M2M связь |

**Поля companies:**
- id, name, vat, ogrn, kpp, director
- street, city, postal_code, country
- email, phone, balance, status
- company_type ('company' | 'project')
- tg_dir, tg_accountant, tg_manager_1/2/3, tg_support
- orders_count, turnover, rating, successful_deliveries

#### CHAT DOMAIN (нужен новый домен)
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `chats` | ❌ Не мигрирован | Чаты (direct/group/company) |
| `chat_participants` | ❌ Не мигрирован | Участники чата |
| `messages` | ❌ Не мигрирован | Сообщения |
| `message_reads` | ❌ Не мигрирован | Прочтения |
| `typing_indicators` | ❌ Не мигрирован | Индикаторы набора |
| `message_templates` | ❌ Не мигрирован | Шаблоны сообщений |

**Поля messages:**
- id, chat_id, sender_id, content, message_type
- reply_to_id, file_url, file_name, file_size, file_type
- voice_duration, is_edited, is_deleted
- telegram_message_id, telegram_user_id, telegram_user_data
- telegram_topic_id, telegram_forward_data, sync_direction

#### TELEGRAM DOMAIN (нужен новый домен)
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `telegram_supergroups` | ❌ Не мигрирован | Telegram группы |
| `telegram_group_members` | ❌ Не мигрирован | Участники групп |
| `tg_users` | ❌ Не мигрирован | Telegram пользователи |

#### CONTENT DOMAIN (низкий приоритет)
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `news` | ❌ Не мигрирован | Новости/объявления |
| `currencies` | ❌ Не мигрирован | Курсы валют |

#### SYSTEM
| Таблица | Статус | Примечание |
|---------|--------|------------|
| `system_logs` | ⏳ Есть аналог | Используем logging |

---

## 3. АНАЛИЗ EDGE FUNCTIONS

### 3.1 Функции для миграции

| Функция | Приоритет | Целевой домен | Описание |
|---------|-----------|---------------|----------|
| `telegram-webhook` | 🔴 HIGH | Telegram | Приём сообщений из Telegram (852 строки) |
| `telegram-send` | 🔴 HIGH | Chat | Отправка в Telegram |
| `telegram-group-create` | 🟡 MEDIUM | Company | Создание Telegram группы |
| `telegram-verify-topics` | 🟡 MEDIUM | Telegram | Верификация топиков |
| `telegram-backfill-media` | 🟢 LOW | Chat | Бэкфил медиа файлов |
| `telegram-file-proxy` | 🟢 LOW | Infra | Прокси для файлов |
| `telegram-health` | 🟢 LOW | Infra | Health check |
| `dadata-api-inn` | 🟡 MEDIUM | Company | Поиск компании по ИНН |
| `quick-login` | ✅ Удалить | - | Заменён на AuthenticateUserCommand |
| `storage-make-public` | ✅ Удалить | - | Одноразовая настройка |

### 3.2 Критическая логика в Edge Functions

**telegram-webhook (852 строки):**
1. Нормализация Telegram ID: `id * -1 - 1000000000000`
2. Создание/обновление supergroup
3. Обработка forum топиков (General = topicId 1)
4. Загрузка файлов → Supabase Storage
5. Сохранение сообщений с дедупликацией
6. Обработка replies и forwards

**telegram-send:**
1. Валидация чата и топика
2. Отправка text/photo/document/voice
3. Retry при "topic not found" → отправка в General
4. Сохранение telegram_message_id

---

## 4. НЕОБХОДИМЫЕ ДОМЕНЫ

### 4.1 Архитектурное решение: Hexagonal Architecture

**Правильное разделение по слоям:**

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│   /api/chat/*          /api/telegram/webhook                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    DOMAIN LAYER (бизнес-логика)                 │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │  Chat Domain    │    │ Company Domain  │                   │
│   │  - ChatAggregate│    │ - CompanyAggr.  │                   │
│   │  - MessageAggr. │    │ - Events        │                   │
│   │  - Events       │    │ - Commands      │                   │
│   └────────┬────────┘    └─────────────────┘                   │
│            │                                                    │
└────────────┼────────────────────────────────────────────────────┘
             │ Events: MessageSent, ChatCreated, etc.
             │
┌────────────▼────────────────────────────────────────────────────┐
│                INFRASTRUCTURE LAYER (адаптеры)                  │
│                                                                 │
│   ┌───────────────────┐  ┌───────────────────┐                 │
│   │ WSE Publisher     │  │ Telegram Adapter  │                 │
│   │ (Real-time → Web) │  │ (External API)    │                 │
│   └───────────────────┘  └─────────┬─────────┘                 │
│                                    │                            │
│   ┌───────────────────┐  ┌─────────▼─────────┐                 │
│   │ File Storage      │  │ Telegram Bot API  │                 │
│   │ (MinIO/S3)        │  │ (External Service)│                 │
│   └───────────────────┘  └───────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

**Принцип:**
- **Chat Domain** - чистая бизнес-логика, НЕ знает про Telegram
- **Telegram** - Infrastructure service (адаптер к внешнему API)
- Связь через Events: Domain публикует → Adapter слушает и отправляет

### 4.2 Список компонентов

| # | Компонент | Тип | Приоритет | Описание |
|---|-----------|-----|-----------|----------|
| 1 | **Company** | Domain | 🔴 HIGH | Компании, сотрудники |
| 2 | **Chat** | Domain | 🔴 HIGH | Чаты, сообщения, участники |
| 3 | **Telegram Adapter** | Infrastructure | 🔴 HIGH | Клиент Telegram API + Webhook |
| 4 | **File Storage** | Infrastructure | 🟡 MED | Хранение файлов |
| 5 | **News** | Domain | 🟢 LOW | Новости |
| 6 | **Currency** | Domain | 🟢 LOW | Курсы валют |

### 4.3 Детальная структура доменов

---

### DOMAIN 1: COMPANY

**Папка:** `app/company/`

**Aggregate:** `CompanyAggregate`
- company_id, name, vat, ogrn, kpp
- director, address (value object)
- contacts (email, phone, telegram contacts)
- balance, status, metrics

**Commands:**
```
CreateCompanyCommand
UpdateCompanyCommand
AddCompanyMemberCommand (owner/manager/assigned_admin)
RemoveCompanyMemberCommand
UpdateCompanyBalanceCommand
LookupCompanyByInnCommand (DaData integration)
```

**Events:**
```
CompanyCreated
CompanyUpdated
CompanyMemberAdded
CompanyMemberRemoved
CompanyBalanceUpdated
```

**Queries:**
```
GetCompanyByIdQuery
GetUserCompaniesQuery
GetCompanyMembersQuery
SearchCompanyByInnQuery
```

**Read Models:**
```
CompanyReadModel
CompanyMemberReadModel
CompanySummaryReadModel
```

**External Services:**
- DaData API (поиск по ИНН)

---

### DOMAIN 2: CHAT (чистая бизнес-логика)

**Папка:** `app/chat/`

**ВАЖНО: Hexagonal Architecture**
- Chat Domain НЕ знает про Telegram
- Chat работает с абстрактными external_channel_id, external_message_id
- Telegram - это один из возможных адаптеров (может быть WhatsApp, Email и т.д.)

#### Aggregates:

**1. ChatAggregate** (чат/канал)
```python
class ChatAggregate:
    chat_id: UUID
    company_id: UUID
    name: str
    chat_type: ChatType  # direct, group, company_channel

    # External channel binding (abstract - может быть Telegram, WhatsApp, etc.)
    external_channel_id: Optional[str]  # e.g. Telegram supergroup_id
    external_topic_id: Optional[str]    # e.g. Telegram topic_id
    sync_enabled: bool
    sync_direction: SyncDirection  # inbound, outbound, bidirectional

    is_active: bool
    created_at: datetime
```

**2. MessageAggregate** (сообщения)
```python
class MessageAggregate:
    message_id: UUID
    chat_id: UUID

    # Sender - либо наш user, либо external
    sender_id: Optional[UUID]           # WellWon user_id
    external_sender_id: Optional[str]   # e.g. Telegram user_id
    external_sender_name: Optional[str] # Display name from external

    content: str
    message_type: MessageType  # text, photo, document, voice, video

    # File attachments
    file_url: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    file_type: Optional[str]

    # Reply/Forward
    reply_to_id: Optional[UUID]
    forward_from: Optional[dict]  # JSON с данными пересылки

    # External sync
    external_message_id: Optional[str]  # e.g. Telegram message_id
    sync_direction: SyncDirection

    # State
    is_edited: bool
    is_deleted: bool
    created_at: datetime
```

**3. ChatParticipantAggregate** (участники)
```python
class ChatParticipantAggregate:
    chat_id: UUID
    user_id: UUID
    role: ParticipantRole  # owner, admin, member
    joined_at: datetime
    last_read_message_id: Optional[UUID]
    last_read_at: Optional[datetime]
```

#### Commands:
```python
# Chat Management
CreateChatCommand(company_id, name, chat_type, participants)
UpdateChatCommand(chat_id, name, ...)
ArchiveChatCommand(chat_id)
BindExternalChannelCommand(chat_id, channel_type, channel_id, topic_id)
UnbindExternalChannelCommand(chat_id)

# Participants
AddParticipantCommand(chat_id, user_id, role)
RemoveParticipantCommand(chat_id, user_id)
UpdateParticipantRoleCommand(chat_id, user_id, new_role)

# Messaging
SendMessageCommand(chat_id, sender_id, content, message_type, file_*, reply_to_id)
ReceiveExternalMessageCommand(chat_id, external_sender_id, content, external_message_id)
EditMessageCommand(message_id, new_content)
DeleteMessageCommand(message_id)

# Read Receipts
MarkMessagesAsReadCommand(chat_id, user_id, last_read_message_id)
```

#### Events:
```python
# Chat
ChatCreated(chat_id, company_id, name, chat_type)
ChatUpdated(chat_id, changes)
ChatArchived(chat_id)
ExternalChannelBound(chat_id, channel_type, channel_id, topic_id)
ExternalChannelUnbound(chat_id)

# Participants
ParticipantAdded(chat_id, user_id, role)
ParticipantRemoved(chat_id, user_id)
ParticipantRoleUpdated(chat_id, user_id, new_role)

# Messages
MessageSent(message_id, chat_id, sender_id, content, ...)
ExternalMessageReceived(message_id, chat_id, external_sender_id, content, ...)
MessageEdited(message_id, new_content)
MessageDeleted(message_id)

# Read Receipts
MessagesMarkedAsRead(chat_id, user_id, last_read_message_id)
```

#### Queries:
```python
GetChatByIdQuery(chat_id) -> ChatReadModel
GetUserChatsQuery(user_id, company_id?) -> List[ChatListItemReadModel]
GetCompanyChatsQuery(company_id) -> List[ChatReadModel]

GetChatMessagesQuery(chat_id, cursor?, limit, direction) -> List[MessageReadModel]
GetUnreadCountQuery(chat_id, user_id) -> int
SearchMessagesQuery(chat_id, query, limit) -> List[MessageReadModel]

GetChatParticipantsQuery(chat_id) -> List[ParticipantReadModel]
```

#### Read Models:
```python
ChatReadModel:
    chat_id, company_id, name, chat_type
    external_channel_type, external_channel_id, sync_enabled
    participant_count, is_active, created_at

ChatListItemReadModel:
    chat_id, name, chat_type
    last_message: MessageSummary
    unread_count: int
    last_activity_at: datetime

MessageReadModel:
    message_id, chat_id
    sender_id, sender_name, sender_avatar
    external_sender_id, external_sender_name
    content, message_type, file_*
    reply_to: MessageSummary?
    is_edited, is_deleted, created_at

ParticipantReadModel:
    user_id, username, avatar_url
    role, joined_at, is_online
```

#### WSE Events (Real-time):
```python
chat.message.new        # Новое сообщение
chat.message.edited     # Редактирование
chat.message.deleted    # Удаление
chat.typing.start       # Начал печатать
chat.typing.stop        # Перестал печатать
chat.read               # Прочтение
chat.updated            # Обновление чата
chat.participant.added  # Новый участник
```

---

### INFRASTRUCTURE: TELEGRAM ADAPTER

**Папка:** `app/infra/telegram/`

**Это НЕ домен, а инфраструктурный адаптер!**
- Получает события от Chat Domain
- Отправляет в Telegram Bot API
- Принимает webhook от Telegram
- Трансформирует в команды Chat Domain

#### Структура файлов:
```
app/infra/telegram/
├── __init__.py
├── client.py           # HTTP клиент к Telegram Bot API
├── webhook_handler.py  # Обработка входящих webhook
├── event_listener.py   # Слушает события Chat Domain
├── models.py           # Telegram-специфичные модели
├── file_service.py     # Загрузка/скачивание файлов
└── id_normalizer.py    # Нормализация Telegram ID
```

#### Telegram Client (HTTP API):
```python
# app/infra/telegram/client.py
class TelegramBotClient:
    """HTTP клиент к Telegram Bot API"""

    def __init__(self, bot_token: str):
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        message_thread_id: int | None = None,
        reply_to_message_id: int | None = None,
        parse_mode: str = "HTML"
    ) -> TelegramMessage:
        ...

    async def send_photo(self, chat_id: int, photo: bytes | str, caption: str = None) -> TelegramMessage:
        ...

    async def send_document(self, chat_id: int, document: bytes | str, filename: str) -> TelegramMessage:
        ...

    async def get_file(self, file_id: str) -> TelegramFile:
        ...

    async def download_file(self, file_path: str) -> bytes:
        ...
```

#### Webhook Handler (входящие сообщения):
```python
# app/infra/telegram/webhook_handler.py
class TelegramWebhookHandler:
    """Обрабатывает входящие webhook от Telegram"""

    def __init__(self, command_bus: CommandBus, chat_repo: ChatReadRepository):
        self.command_bus = command_bus
        self.chat_repo = chat_repo

    async def handle_update(self, update: TelegramUpdate) -> None:
        """Преобразует Telegram Update в команду Chat Domain"""

        if update.message:
            await self._handle_message(update.message)
        elif update.edited_message:
            await self._handle_edited_message(update.edited_message)

    async def _handle_message(self, msg: TelegramMessage) -> None:
        # 1. Найти чат по external_channel_id
        chat = await self.chat_repo.find_by_external_channel(
            channel_type="telegram",
            channel_id=self._normalize_chat_id(msg.chat.id),
            topic_id=str(msg.message_thread_id) if msg.message_thread_id else None
        )

        if not chat or not chat.sync_enabled:
            return  # Игнорируем, если чат не привязан

        # 2. Создать команду Chat Domain
        command = ReceiveExternalMessageCommand(
            chat_id=chat.chat_id,
            external_sender_id=str(msg.from_user.id),
            external_sender_name=msg.from_user.first_name,
            content=msg.text or msg.caption or "",
            message_type=self._detect_message_type(msg),
            file_url=await self._download_file_if_exists(msg),
            external_message_id=str(msg.message_id)
        )

        # 3. Отправить в Command Bus
        await self.command_bus.dispatch(command)

    def _normalize_chat_id(self, telegram_id: int) -> str:
        """Нормализация Telegram ID: id * -1 - 1000000000000"""
        if telegram_id > 0:
            return str(telegram_id)
        return str(telegram_id * -1 - 1000000000000)
```

#### Event Listener (исходящие сообщения):
```python
# app/infra/telegram/event_listener.py
class TelegramEventListener:
    """Слушает события Chat Domain и отправляет в Telegram"""

    def __init__(self, telegram_client: TelegramBotClient, chat_repo: ChatReadRepository):
        self.client = telegram_client
        self.chat_repo = chat_repo

    @subscribe_to("MessageSent")
    async def on_message_sent(self, event: MessageSent) -> None:
        """Когда пользователь отправил сообщение через web → отправить в Telegram"""

        # 1. Получить чат с external binding
        chat = await self.chat_repo.get_by_id(event.chat_id)

        if not chat.sync_enabled or chat.external_channel_type != "telegram":
            return  # Не синхронизируем

        # 2. Отправить в Telegram
        telegram_chat_id = self._denormalize_chat_id(chat.external_channel_id)
        topic_id = int(chat.external_topic_id) if chat.external_topic_id else None

        result = await self.client.send_message(
            chat_id=telegram_chat_id,
            text=event.content,
            message_thread_id=topic_id
        )

        # 3. Сохранить external_message_id (опционально, через команду)
        # await self.command_bus.dispatch(
        #     UpdateMessageExternalIdCommand(event.message_id, str(result.message_id))
        # )

    def _denormalize_chat_id(self, normalized_id: str) -> int:
        """Обратная нормализация для отправки"""
        id_int = int(normalized_id)
        if id_int > 0:
            return id_int
        return (id_int + 1000000000000) * -1
```

#### API Router (webhook endpoint):
```python
# app/api/routers/telegram_webhook_router.py
from fastapi import APIRouter, Request, HTTPException
from app.infra.telegram.webhook_handler import TelegramWebhookHandler

router = APIRouter(prefix="/telegram", tags=["telegram"])

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    handler: TelegramWebhookHandler = Depends(get_telegram_handler)
):
    """Endpoint для Telegram Bot webhook"""
    try:
        update = await request.json()
        await handler.handle_update(TelegramUpdate(**update))
        return {"ok": True}
    except Exception as e:
        log.error(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### Telegram Group Management Service:
```python
# app/infra/telegram/group_service.py
class TelegramGroupService:
    """Управление Telegram группами через внешний микросервис"""

    def __init__(self, manage_service_url: str):
        self.manage_url = manage_service_url  # telegram-manage.onrender.com

    async def create_group(
        self,
        title: str,
        description: str,
        photo_url: str | None = None
    ) -> dict:
        """Создать новую Telegram группу"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.manage_url}/create-group",
                json={"title": title, "description": description, "photo_url": photo_url}
            )
            return response.json()
```

#### Typing Indicators (ephemeral, Redis - не Event Sourcing):
```python
# app/infra/services/typing_service.py
class TypingService:
    """Ephemeral state - не храним в Event Store"""

    def __init__(self, redis: Redis, pubsub: RedisPubSub):
        self.redis = redis
        self.pubsub = pubsub

    async def start_typing(self, chat_id: UUID, user_id: UUID) -> None:
        key = f"typing:{chat_id}:{user_id}"
        await self.redis.setex(key, 10, "1")  # TTL 10 секунд
        await self.pubsub.publish(f"chat:{chat_id}", {
            "type": "chat.typing.start",
            "user_id": str(user_id)
        })

    async def stop_typing(self, chat_id: UUID, user_id: UUID) -> None:
        key = f"typing:{chat_id}:{user_id}"
        await self.redis.delete(key)
        await self.pubsub.publish(f"chat:{chat_id}", {
            "type": "chat.typing.stop",
            "user_id": str(user_id)
        })

    async def get_typing_users(self, chat_id: UUID) -> list[UUID]:
        pattern = f"typing:{chat_id}:*"
        keys = await self.redis.keys(pattern)
        return [UUID(k.split(":")[-1]) for k in keys]
```

---

### DOMAIN 3: NEWS (низкий приоритет)

**Папка:** `app/news/`

**Commands:** CreateNews, UpdateNews, PublishNews, UnpublishNews
**Events:** NewsCreated, NewsUpdated, NewsPublished
**Queries:** GetNewsById, GetPublishedNews, GetNewsByCategory

---

### DOMAIN 5: CURRENCY (низкий приоритет)

**Папка:** `app/currency/`

**Commands:** UpdateExchangeRates
**Events:** ExchangeRatesUpdated
**Queries:** GetCurrentRates, GetRatesHistory

---

## 5. ПЛАН МИГРАЦИИ ПО ФАЗАМ

### ФАЗА 1: Company Domain

**Цель:** Базовое управление компаниями

**Задачи:**
1. [ ] Создать структуру `app/company/`
2. [ ] Реализовать CompanyAggregate
3. [ ] Команды: Create, Update, AddMember
4. [ ] Проекторы в PostgreSQL
5. [ ] API endpoints: `/api/companies/*`
6. [ ] Миграция данных из Supabase
7. [ ] Интеграция с DaData (поиск по ИНН)

**Миграция данных:**
```sql
-- Из Supabase companies → WellWon
INSERT INTO wellwon.companies
SELECT * FROM supabase.companies;

-- Из user_companies → связи
INSERT INTO wellwon.company_members
SELECT * FROM supabase.user_companies;
```

---

### ФАЗА 2: Chat Domain

**Цель:** Полноценный чат (без внешних интеграций)

**Задачи:**
1. [ ] Создать структуру `app/chat/`
2. [ ] ChatAggregate + MessageAggregate + ParticipantAggregate
3. [ ] Все команды для сообщений
4. [ ] WSE publishers для real-time
5. [ ] Typing indicators через Redis
6. [ ] Read receipts
7. [ ] API endpoints: `/api/chats/*`, `/api/messages/*`
8. [ ] Обновить фронтенд (убрать Supabase Realtime)

**WSE Integration:**
```python
# В domain_publisher.py добавить:
'MessageSent': 'chat.message.new',
'ExternalMessageReceived': 'chat.message.new',
'MessageEdited': 'chat.message.edited',
'MessageDeleted': 'chat.message.deleted',
'MessagesMarkedAsRead': 'chat.read',
```

**Frontend изменения:**
- `RealtimeChatService` → `ChatAPI` + `useWSEQuery`
- Supabase Realtime → WSE subscriptions

---

### ФАЗА 3: Telegram Adapter (Infrastructure)

**Цель:** Bi-directional Telegram sync

**Задачи:**
1. [ ] Создать структуру `app/infra/telegram/`
2. [ ] TelegramBotClient (HTTP клиент)
3. [ ] TelegramWebhookHandler
4. [ ] TelegramEventListener (слушает Chat Domain events)
5. [ ] TelegramFileService (загрузка/скачивание файлов)
6. [ ] TelegramGroupService (создание групп)
7. [ ] API endpoint: `/api/telegram/webhook`
8. [ ] Миграция supergroups/members из Supabase

**Telegram Flow (входящие):**
```
Telegram Bot API
       │
       ▼ (POST /webhook)
┌──────────────────────────────────┐
│  TelegramWebhookHandler          │
│  (app/infra/telegram/)           │
│  - Парсит Update                 │
│  - Нормализует ID                │
│  - Находит chat по external_id   │
└──────────────┬───────────────────┘
               │
               ▼ (Command)
┌──────────────────────────────────┐
│  Chat Domain (app/chat/)         │
│  - ReceiveExternalMessageCommand │
│  - MessageAggregate              │
│  - ExternalMessageReceived event │
└──────────────┬───────────────────┘
               │
               ▼ (Event Bus)
┌──────────────────────────────────┐
│  WSE Publisher                   │
│  - chat.message.new              │
│  - WebSocket → Frontend          │
└──────────────────────────────────┘
```

**Telegram Flow (исходящие):**
```
Frontend → POST /api/messages
               │
               ▼ (Command)
┌──────────────────────────────────┐
│  Chat Domain (app/chat/)         │
│  - SendMessageCommand            │
│  - MessageAggregate              │
│  - MessageSent event             │
└──────────────┬───────────────────┘
               │
               ▼ (Event Bus)
┌──────────────────────────────────┐
│  TelegramEventListener           │
│  (app/infra/telegram/)           │
│  - Слушает MessageSent           │
│  - Проверяет sync_enabled        │
│  - Отправляет в Telegram API     │
└──────────────────────────────────┘
```

---

### ФАЗА 4: Cleanup & Optimization

**Задачи:**
1. [ ] Удалить Supabase зависимости из фронтенда
2. [ ] Удалить Edge Functions (или архивировать)
3. [ ] Performance testing
4. [ ] Документация API

---

## 6. ТЕХНИЧЕСКИЕ РЕШЕНИЯ

### 6.1 File Storage

**Решение:** MinIO (S3-совместимый) или AWS S3

**Структура путей:**
```
/chat-files/
  /{company_id}/
    /{chat_id}/
      /{year}/{month}/
        {message_id}_{filename}
```

**Service:**
```python
# app/infra/services/file_storage_service.py
class FileStorageService:
    async def upload_file(file: bytes, path: str) -> str
    async def get_file_url(path: str) -> str
    async def delete_file(path: str) -> None
```

### 6.2 Telegram Integration

**Решение:** Отдельный сервис

```python
# app/infra/services/telegram_api_service.py
class TelegramApiService:
    async def send_message(chat_id: int, text: str, ...) -> int
    async def send_photo(chat_id: int, photo: bytes, ...) -> int
    async def get_file(file_id: str) -> bytes
    async def download_file(file_path: str) -> bytes
```

### 6.3 Typing Indicators

**Решение:** Redis с TTL (не Event Sourcing)

```python
# Ephemeral state - не нужно хранить в event store
class TypingService:
    async def start_typing(chat_id: UUID, user_id: UUID):
        await redis.setex(f"typing:{chat_id}:{user_id}", 10, "1")
        await pubsub.publish(f"chat:{chat_id}", {"type": "typing", "user_id": user_id})

    async def stop_typing(chat_id: UUID, user_id: UUID):
        await redis.delete(f"typing:{chat_id}:{user_id}")
```

### 6.4 Message Pagination

**Решение:** Cursor-based pagination

```python
class GetChatMessagesQuery(Query):
    chat_id: UUID
    cursor: Optional[datetime] = None  # created_at of last message
    limit: int = 50
    direction: Literal["older", "newer"] = "older"
```

### 6.5 Unread Count

**Решение:** Materialized в read model

```python
class ChatListItemReadModel:
    chat_id: UUID
    name: str
    last_message: Optional[MessageSummary]
    unread_count: int  # Вычисляется проектором
    last_read_at: datetime
```

**Projector:**
```python
@sync_projection("MessageMarkedAsRead")
async def on_message_read(self, envelope):
    # Пересчитать unread_count для участника
    await self.recalculate_unread_count(
        chat_id=envelope.aggregate_id,
        user_id=envelope.event_data['user_id']
    )
```

---

## ИТОГОВАЯ СТАТИСТИКА

### Объём работы

| Компонент | Тип | Файлов | Строк кода (оценка) |
|-----------|-----|--------|---------------------|
| Company | Domain | ~15 | ~2,000 |
| Chat | Domain | ~20 | ~4,000 |
| Telegram | Infrastructure | ~8 | ~1,500 |
| News | Domain | ~10 | ~800 |
| Currency | Domain | ~8 | ~500 |
| **ИТОГО** | | ~61 | ~8,800 |

### Архитектура компонентов

```
┌────────────────────────────────────────────────────────────────┐
│                        API Layer                                │
│  /api/user/*  /api/companies/*  /api/chats/*  /api/telegram/*  │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│                     DOMAIN LAYER                                │
│                                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│   │ User Account │  │   Company    │  │     Chat     │        │
│   │   (готов)    │  │   Domain     │  │    Domain    │        │
│   └──────────────┘  └──────────────┘  └──────┬───────┘        │
│                                              │                 │
│   ┌──────────────┐  ┌──────────────┐         │                │
│   │    News      │  │   Currency   │         │                │
│   │   Domain     │  │    Domain    │         │                │
│   └──────────────┘  └──────────────┘         │                │
└──────────────────────────────────────────────┼─────────────────┘
                                               │ Events
┌──────────────────────────────────────────────▼─────────────────┐
│                   INFRASTRUCTURE LAYER                          │
│                                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│   │     WSE      │  │   Telegram   │  │ File Storage │        │
│   │  Publisher   │  │   Adapter    │  │   (MinIO)    │        │
│   └──────────────┘  └──────────────┘  └──────────────┘        │
│                            │                                    │
│                            ▼                                    │
│                    Telegram Bot API                             │
└─────────────────────────────────────────────────────────────────┘
```

### Зависимости

```
User Account (готов)
      │
      ▼
   Company Domain
      │
      ▼
   Chat Domain ◄───────── Telegram Adapter (infra)
      │                          │
      │                          ▼
      │                   Telegram Bot API
      ▼
   [News, Currency - независимые]
```

### Приоритеты

1. 🔴 **Company Domain** - без него нельзя делать Chat
2. 🔴 **Chat Domain** - основной функционал платформы
3. 🔴 **Telegram Adapter** - интеграция с внешним миром
4. 🟢 **News/Currency** - можно отложить

---

## СЛЕДУЮЩИЕ ШАГИ

1. **Начать с Company domain** - это фундамент
2. **Создать миграции БД** для read models
3. **Обновить фронтенд** по мере готовности доменов
4. **Тестировать каждую фазу** перед следующей

---

*Документ создан автоматически на основе анализа reference/supabase и текущей кодовой базы WellWon*
