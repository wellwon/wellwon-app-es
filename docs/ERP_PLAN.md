# WellWon Custom ERP: Полная инструкция разработки

> **Цель документа:** Пошаговое руководство для Claude Opus 4.5 по созданию Custom ERP модулей с защитой данных и best practices.

---

## ЧАСТЬ 1: ФИЛОСОФИЯ И АРХИТЕКТУРА

### 1.1 Почему Custom ERP для WellWon

| Фактор | Решение |
|--------|---------|
| Инфраструктура | 70% уже готово (ES, CQRS, Saga) |
| Гибкость | Полный контроль над кодом |
| Единый стек | PostgreSQL везде (не MariaDB) |
| Аудит | Event Sourcing = полная история |
| Скорость UI | React native, без API overhead |

### 1.2 Архитектурный принцип: Modular Monolith

```
app/
├── erp/                      # ERP Core (ОДИН сервис!)
│   ├── items/                # Номенклатура
│   ├── partners/             # Контрагенты
│   ├── inventory/            # Склад
│   ├── orders/               # Заказы
│   ├── finance/              # Финансы
│   └── common/               # Общие справочники
├── ww_declarant/             # Декларант (отдельный bounded context)
├── chat/                     # Чаты (уже есть)
├── company/                  # Компании (уже есть)
└── user_account/             # Пользователи (уже есть)
```

**Почему Modular Monolith, а не микросервисы для ERP:**
- ERP модули тесно связаны (заказ → склад → финансы)
- Транзакционная целостность критична
- Проще разрабатывать и деплоить
- Можно выделить в микросервис позже при необходимости

---

## ЧАСТЬ 2: ИСТОЧНИКИ BEST PRACTICES

### 2.1 Где подсматривать логику

| Область | Источник | Что брать |
|---------|----------|-----------|
| **Складской учёт** | ERPNext (tabBin, tabStock Ledger Entry) | actual_qty, reserved_qty, projected_qty |
| **Документооборот** | ERPNext (Sales Order → Invoice) | Цепочки документов |
| **Финансы** | ERPNext (GL Entry pattern) | Двойная запись |
| **Event Sourcing** | Существующий WellWon код | Паттерны aggregate, events |
| **CQRS** | app/company/, app/chat/ | Command/Query handlers |

### 2.2 Ключевые паттерны из ERPNext для адаптации

**Stock Balance (из ERPNext):**
```python
# Концепция tabBin - баланс по складу
stock_fields = {
    'actual_qty': 'Фактическое количество',
    'reserved_qty': 'Зарезервировано',
    'ordered_qty': 'Заказано (в пути)',
    'projected_qty': 'Прогнозное = actual - reserved + ordered',
    'valuation_rate': 'Себестоимость единицы',
}
```

**Document Chain:**
```
Quotation → Sales Order → Delivery Note → Sales Invoice → Payment Entry
                ↓
         Stock Reservation → Stock Entry (при отгрузке)
```

---

## ЧАСТЬ 3: СТРУКТУРА ERP МОДУЛЯ

### 3.1 Шаблон структуры (на примере Items)

```
app/erp/items/
├── __init__.py
├── enums.py                  # ItemType, ItemStatus
├── exceptions.py             # ItemNotFoundError, etc.
├── events.py                 # ItemCreated, ItemUpdated, etc.
├── commands.py               # CreateItemCommand, etc.
├── queries.py                # GetItemByIdQuery, etc.
├── aggregate.py              # ItemAggregate (Event Sourcing)
├── read_models.py            # Pydantic models для PostgreSQL
├── projectors.py             # Events → Read Models
├── command_handlers/
│   ├── __init__.py
│   └── item_handlers.py
├── query_handlers/
│   ├── __init__.py
│   └── item_query_handlers.py
└── migrations/
    └── 001_create_items.sql
```

### 3.2 Порядок создания файлов

```
1. enums.py           → Типы и статусы
2. exceptions.py      → Исключения домена
3. events.py          → Доменные события (ВАЖНО: версионировать!)
4. commands.py        → CQRS команды
5. queries.py         → CQRS запросы
6. aggregate.py       → Event Sourcing aggregate
7. read_models.py     → Pydantic модели
8. migrations/*.sql   → DDL для PostgreSQL
9. projectors.py      → Проекции событий
10. command_handlers/ → Обработчики команд
11. query_handlers/   → Обработчики запросов
12. API router        → REST endpoints
```

### 3.3 Паттерны именования

```python
# События
{Entity}Created, {Entity}Updated, {Entity}Deleted, {Entity}Archived
ItemCreated, StockMovementRecorded, InvoicePaid

# Команды
Create{Entity}Command, Update{Entity}Command, Delete{Entity}Command
CreateItemCommand, RecordStockMovementCommand, PayInvoiceCommand

# Запросы
Get{Entity}ByIdQuery, Get{Entities}Query, Get{Entity}By{Filter}Query
GetItemByIdQuery, GetItemsByCompanyQuery, GetLowStockItemsQuery

# Обработчики
{Action}{Entity}Handler
CreateItemHandler, RecordStockMovementHandler

# Исключения
{Entity}NotFoundError, {Entity}AlreadyExistsError, Insufficient{Resource}Error
ItemNotFoundError, InsufficientStockError
```

---

## ЧАСТЬ 4: ЗАЩИТА ДАННЫХ И БЕЗОПАСНАЯ РАЗРАБОТКА

### 4.1 Event Sourcing = Главная защита

```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT STORE (KurrentDB)                  │
│                      IMMUTABLE!                             │
│                                                             │
│  ItemCreated → StockAdded → StockReserved → ...            │
│                                                             │
│  Никогда не удаляем, никогда не меняем                     │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼ Projection (можно пересоздать!)
┌─────────────────────────────────────────────────────────────┐
│                  READ MODELS (PostgreSQL)                   │
│                                                             │
│  items, stock_balances, invoices — генерируются из событий │
└─────────────────────────────────────────────────────────────┘
```

**Правило:** События = факты. Read Models = интерпретация. Факты неизменны.

### 4.2 Версионирование событий

```python
# app/erp/items/events.py

@domain_event(category="domain")
class ItemCreated(BaseEvent):
    """Версия события в __version__"""
    __version__ = 1

    event_type: Literal["ItemCreated"] = "ItemCreated"
    item_id: uuid.UUID
    sku: str
    name: str
    # V1 поля

# Когда нужно добавить поле:
@domain_event(category="domain")
class ItemCreatedV2(BaseEvent):
    __version__ = 2

    event_type: Literal["ItemCreated"] = "ItemCreated"  # Тот же тип!
    item_id: uuid.UUID
    sku: str
    name: str
    category_id: uuid.UUID | None = None  # Новое поле, optional!

# Upcaster для миграции старых событий
class ItemEventUpcaster:
    def upcast(self, event_data: dict, version: int) -> dict:
        if version == 1:
            event_data['category_id'] = None
        return event_data
```

### 4.3 Безопасные миграции БД

**Золотое правило: Additive-only**

```sql
-- ✅ БЕЗОПАСНО
ALTER TABLE items ADD COLUMN category_id UUID NULL;
CREATE INDEX CONCURRENTLY idx_items_category ON items(category_id);
CREATE TABLE new_table (...);

-- ❌ ОПАСНО (требует особой процедуры)
ALTER TABLE items DROP COLUMN old_field;
DROP TABLE old_table;
UPDATE items SET field = value;  -- массовый update
```

**Паттерн Expand-Contract:**

```
Релиз 1: EXPAND
- Добавляем new_column (nullable)
- Код пишет в old_column И new_column
- Код читает из old_column

Релиз 2: MIGRATE
- Backfill: UPDATE ... SET new_column = old_column WHERE new_column IS NULL
- Код читает из new_column
- Код всё ещё пишет в оба

Релиз 3: CONTRACT (через 2-3 релиза!)
- Убираем запись в old_column
- DROP COLUMN old_column (если уверены)
```

### 4.4 Feature Flags

```python
# app/config/features.py

from enum import Enum

class FeatureFlag(str, Enum):
    NEW_STOCK_ALGORITHM = "new_stock_algorithm"
    MULTI_WAREHOUSE = "multi_warehouse"
    BATCH_TRACKING = "batch_tracking"

# Redis-based feature flags
class FeatureFlagService:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_enabled(self, flag: FeatureFlag, company_id: str = None) -> bool:
        # Глобальный флаг
        global_key = f"feature:{flag.value}"
        if await self.redis.get(global_key) == "1":
            return True

        # Per-company флаг (для постепенного rollout)
        if company_id:
            company_key = f"feature:{flag.value}:company:{company_id}"
            return await self.redis.get(company_key) == "1"

        return False

# Использование
if await feature_flags.is_enabled(FeatureFlag.NEW_STOCK_ALGORITHM):
    result = await new_stock_calculation(item_id)
else:
    result = await old_stock_calculation(item_id)
```

### 4.5 Чеклист перед каждым релизом

```markdown
## Pre-Release Checklist

### Код
- [ ] Все новые поля в событиях optional или с default
- [ ] Event upcasters написаны для новых версий событий
- [ ] Feature flag для новой бизнес-логики
- [ ] Тесты покрывают новый функционал
- [ ] Rollback сценарий документирован

### База данных
- [ ] Миграции идемпотентны (можно запустить повторно)
- [ ] Все ALTER TABLE ADD COLUMN с NULL или DEFAULT
- [ ] Индексы создаются CONCURRENTLY
- [ ] Нет DROP COLUMN/TABLE без отдельного approval

### Деплой
- [ ] Backup production DB сделан
- [ ] Staging протестирован с prod-like данными
- [ ] Dry-run миграций выполнен
- [ ] Мониторинг алертов настроен
- [ ] План отката готов
```

---

## ЧАСТЬ 5: ПЛАН РАЗРАБОТКИ ERP

### Фаза 1: Справочники (Неделя 1-2)

**Модуль: app/erp/common/**
```
Currencies (валюты)
- CurrencyCreated, CurrencyRateUpdated
- Поля: code, name, symbol, rate_to_base

UoM (единицы измерения)
- UoMCreated
- Поля: code, name, base_uom_id, conversion_factor

ItemCategories (категории товаров)
- ItemCategoryCreated, ItemCategoryUpdated
- Поля: id, name, parent_id (иерархия)
```

**Модуль: app/erp/items/**
```
Items (номенклатура)
- ItemCreated, ItemUpdated, ItemArchived
- Поля: sku, name, category_id, default_uom,
        item_type (goods/service), is_stock_item
```

**Модуль: app/erp/partners/**
```
Partners (контрагенты)
- PartnerCreated, PartnerUpdated, PartnerArchived
- Поля: name, inn, kpp, partner_type (customer/supplier/both),
        addresses[], contacts[], payment_terms
```

### Фаза 2: Склад (Неделя 3-4)

**Модуль: app/erp/inventory/**
```
Warehouses (склады)
- WarehouseCreated, WarehouseUpdated
- Поля: code, name, address, is_active

StockBalance (проекция - не aggregate!)
- Пересчитывается из StockMovement событий
- Поля: item_id, warehouse_id, actual_qty, reserved_qty,
        projected_qty, valuation_rate, last_movement_date

StockMovement (движения по складу)
- StockMovementRecorded
- Поля: item_id, warehouse_id, qty (+ или -),
        movement_type (receipt/shipment/adjustment/transfer),
        reference_doc_type, reference_doc_id, cost_price
```

**Ключевая логика склада (из ERPNext):**
```python
# Projected Qty = Actual - Reserved + Ordered
projected_qty = actual_qty - reserved_qty + ordered_qty

# При создании Sales Order → резервируем
# При отгрузке (Delivery) → списываем actual, снимаем reserve
# При приёмке (Receipt) → увеличиваем actual
```

### Фаза 3: Заказы (Неделя 5-6)

**Модуль: app/erp/orders/**
```
SalesOrder (заказ клиента)
- SalesOrderCreated, SalesOrderLineAdded,
  SalesOrderConfirmed, SalesOrderShipped, SalesOrderCancelled
- Поля: customer_id, order_date, lines[], status,
        total_amount, currency

PurchaseOrder (заказ поставщику)
- PurchaseOrderCreated, PurchaseOrderSent,
  PurchaseOrderReceived, PurchaseOrderCancelled
- Поля: supplier_id, order_date, lines[], status,
        expected_date, total_amount
```

**Saga: OrderFulfillmentSaga**
```
1. SalesOrderConfirmed
   → ReserveStockCommand (inventory)
   → Если нет на складе: CreatePurchaseOrderCommand

2. StockReceived (от поставщика)
   → CheckPendingOrdersCommand
   → Если есть ожидающие: ReserveStockCommand

3. ShipOrderCommand
   → DeductStockCommand
   → CreateInvoiceCommand (finance)
```

### Фаза 4: Финансы - базовые (Неделя 7-8)

**Модуль: app/erp/finance/**
```
Invoice (счета)
- InvoiceCreated, InvoiceLineAdded, InvoiceSent,
  InvoicePaid, InvoiceCancelled
- Поля: number, partner_id, invoice_type (in/out),
        lines[], total, paid_amount, status

Payment (платежи)
- PaymentRecorded
- Поля: partner_id, amount, payment_date,
        invoices[] (к каким счетам)
```

### Фаза 5: Декларант (параллельно с Фазой 3-4)

**Модуль: app/ww_declarant/**
```
Declaration (декларация)
- DeclarationCreated, DeclarationItemAdded,
  DeclarationSubmitted, DeclarationAccepted, DeclarationRejected
- Поля: number, declaration_type, customs_code,
        items[], documents[], status

Интеграции:
- FTS API клиент (подача деклараций)
- STM/XML генератор
- Связь с items из ERP (товары)
- Связь с partners (отправитель/получатель)
```

---

## ЧАСТЬ 6: ВОПРОСЫ ДЛЯ ЧЕЛОВЕКА

### 6.1 Обязательные вопросы перед началом модуля

```markdown
## Чеклист вопросов перед разработкой модуля

### Бизнес-логика
1. Какие статусы/жизненный цикл у сущности?
2. Кто может создавать/редактировать/удалять?
3. Какие поля обязательны, какие опциональны?
4. Есть ли связи с другими модулями?
5. Нужны ли уведомления при изменениях?

### Данные
6. Есть ли существующие данные для миграции?
7. Какой ожидаемый объём данных?
8. Нужна ли история изменений (audit)?

### UI
9. Какие экраны нужны (список, карточка, формы)?
10. Нужны ли фильтры, сортировка, поиск?
11. Какие действия на UI (кнопки)?

### Интеграции
12. Нужна ли интеграция с внешними системами?
13. Нужен ли экспорт/импорт?
```

### 6.2 Решения только для человека

```markdown
## Решения требующие человеческого approval

### Архитектура
- [ ] Добавление нового bounded context
- [ ] Изменение структуры событий (breaking change)
- [ ] Выделение модуля в отдельный сервис

### Данные
- [ ] DROP TABLE / DROP COLUMN
- [ ] Массовый UPDATE существующих данных
- [ ] Изменение типа данных колонки
- [ ] Удаление/архивация событий из Event Store

### Безопасность
- [ ] Изменение прав доступа
- [ ] Новые API endpoints без авторизации
- [ ] Хранение чувствительных данных

### Бизнес
- [ ] Изменение расчёта стоимости/цен
- [ ] Изменение логики резервирования
- [ ] Новые статусы документов
```

---

## ЧАСТЬ 7: ПРОЦЕСС РАЗРАБОТКИ

### 7.1 Workflow для каждого модуля

```
1. ПЛАНИРОВАНИЕ
   └── Задать вопросы из чеклиста 6.1
   └── Получить approval на архитектуру
   └── Создать TODO список

2. РАЗРАБОТКА (порядок важен!)
   └── enums.py, exceptions.py
   └── events.py (с версионированием!)
   └── commands.py, queries.py
   └── aggregate.py
   └── migrations/*.sql
   └── read_models.py
   └── projectors.py
   └── command_handlers/
   └── query_handlers/
   └── API router
   └── Тесты

3. РЕВЬЮ
   └── Проверить чеклист 4.5
   └── Убедиться в feature flags
   └── Проверить миграции

4. ДЕПЛОЙ
   └── Staging → тестирование
   └── Production (с backup!)
```

### 7.2 Команды для разработки

```bash
# Запуск dev окружения
cd /Users/macbookpro/PycharmProjects/WellWon
source .venv/bin/activate

# Backend
python -m app.server  # или через granian

# Frontend
cd frontend && npm run dev

# Миграции (вручную пока)
psql -h localhost -U wellwon -d wellwon -f database/migrations/XXX.sql

# Тесты
pytest tests/ -v
```

---

## ЧАСТЬ 8: КРИТИЧЕСКИЕ ФАЙЛЫ

### 8.1 Файлы для изучения перед началом

```
# Паттерны модулей
app/company/aggregate.py          # Пример Aggregate
app/company/events.py             # Пример Events
app/company/commands.py           # Пример Commands
app/company/command_handlers/     # Пример Handlers

# Инфраструктура
app/infra/cqrs/command_bus.py     # Как работает Command Bus
app/infra/cqrs/query_bus.py       # Как работает Query Bus
app/infra/event_store/            # Event Store интеграция
app/infra/saga/saga_manager.py    # Saga для сложных операций

# Конфигурация
app/core/routes.py                # Регистрация роутеров
app/core/startup/                 # Инициализация приложения
app/config/                       # Настройки

# База данных
database/wellwon.sql              # Текущая схема
```

### 8.2 Файлы для изменения при добавлении модуля

```
# Обязательно
app/core/routes.py                # Добавить router
app/core/startup/cqrs.py          # Импорт handlers

# При необходимости
app/infra/event_bus/event_registry.py  # Регистрация событий
.env                              # Новые настройки
```

---

## ЧАСТЬ 9: МОНИТОРИНГ И ОТЛАДКА

### 9.1 Логирование

```python
from app.config.logging_config import get_logger

log = get_logger("wellwon.erp.items")

# Уровни
log.debug("Детали для отладки")
log.info("Важные операции: Item created: {item_id}")
log.warning("Предупреждения: Low stock for item {item_id}")
log.error("Ошибки: Failed to create item", exc_info=True)
```

### 9.2 Метрики (Prometheus)

```python
# Уже настроено в app/api/routers/metrics_router.py
# Добавлять свои метрики:

from prometheus_client import Counter, Histogram

erp_commands_total = Counter(
    'erp_commands_total',
    'Total ERP commands processed',
    ['command_type', 'status']
)

erp_command_duration = Histogram(
    'erp_command_duration_seconds',
    'ERP command processing duration',
    ['command_type']
)
```

### 9.3 Проекция rebuild

```python
# Если read model повреждена - пересоздаём из событий
# POST /api/projections/{projection_name}/rebuild

# Это безопасно! События не трогаем.
```

---

## ЧАСТЬ 10: ПРИМЕРЫ КОДА

### 10.1 Пример Events (на основе существующих паттернов WellWon)

```python
# app/erp/items/events.py
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import domain_event

@domain_event(category="domain")
class ItemCreated(BaseEvent):
    """Событие: товар создан"""
    __version__ = 1

    event_type: Literal["ItemCreated"] = "ItemCreated"
    item_id: uuid.UUID
    company_id: uuid.UUID
    sku: str
    name: str
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    default_uom: str = "pcs"
    item_type: str = "goods"  # goods, service
    is_stock_item: bool = True
    created_by: uuid.UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@domain_event(category="domain")
class ItemUpdated(BaseEvent):
    """Событие: товар обновлён"""
    __version__ = 1

    event_type: Literal["ItemUpdated"] = "ItemUpdated"
    item_id: uuid.UUID
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    updated_by: uuid.UUID

@domain_event(category="domain")
class ItemArchived(BaseEvent):
    """Событие: товар архивирован"""
    __version__ = 1

    event_type: Literal["ItemArchived"] = "ItemArchived"
    item_id: uuid.UUID
    reason: Optional[str] = None
    archived_by: uuid.UUID

# Реестр событий для регистрации
ITEM_EVENT_TYPES = {
    "ItemCreated": ItemCreated,
    "ItemUpdated": ItemUpdated,
    "ItemArchived": ItemArchived,
}
```

### 10.2 Пример Aggregate

```python
# app/erp/items/aggregate.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
from datetime import datetime

from app.common.base.base_model import BaseEvent
from app.erp.items.events import ItemCreated, ItemUpdated, ItemArchived
from app.erp.items.exceptions import ItemNotFoundError, ItemAlreadyExistsError

class ItemAggregateState(BaseModel):
    item_id: Optional[uuid.UUID] = None
    company_id: Optional[uuid.UUID] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    default_uom: str = "pcs"
    item_type: str = "goods"
    is_stock_item: bool = True
    is_archived: bool = False
    created_by: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None

class ItemAggregate:
    """Item Aggregate Root for Event Sourcing"""

    def __init__(self, item_id: uuid.UUID):
        self.id = item_id
        self.version = 0
        self.state = ItemAggregateState(item_id=item_id)
        self._uncommitted_events: List[BaseEvent] = []

    # =========================================================================
    # Event Management
    # =========================================================================

    def get_uncommitted_events(self) -> List[BaseEvent]:
        return self._uncommitted_events

    def mark_events_committed(self) -> None:
        self._uncommitted_events.clear()

    def _apply_and_record(self, event: BaseEvent) -> None:
        self._apply(event)
        self._uncommitted_events.append(event)
        self.version += 1

    # =========================================================================
    # Commands
    # =========================================================================

    def create_item(
        self,
        company_id: uuid.UUID,
        sku: str,
        name: str,
        created_by: uuid.UUID,
        description: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        default_uom: str = "pcs",
        item_type: str = "goods",
        is_stock_item: bool = True,
    ) -> None:
        if self.version > 0:
            raise ItemAlreadyExistsError(str(self.id))

        event = ItemCreated(
            item_id=self.id,
            company_id=company_id,
            sku=sku,
            name=name,
            description=description,
            category_id=category_id,
            default_uom=default_uom,
            item_type=item_type,
            is_stock_item=is_stock_item,
            created_by=created_by,
        )
        self._apply_and_record(event)

    def update_item(
        self,
        updated_by: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
    ) -> None:
        if self.state.is_archived:
            raise ValueError("Cannot update archived item")

        event = ItemUpdated(
            item_id=self.id,
            name=name,
            description=description,
            category_id=category_id,
            updated_by=updated_by,
        )
        self._apply_and_record(event)

    def archive_item(self, archived_by: uuid.UUID, reason: Optional[str] = None) -> None:
        if self.state.is_archived:
            return  # Idempotent

        event = ItemArchived(
            item_id=self.id,
            reason=reason,
            archived_by=archived_by,
        )
        self._apply_and_record(event)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _apply(self, event: BaseEvent) -> None:
        handlers = {
            ItemCreated: self._on_item_created,
            ItemUpdated: self._on_item_updated,
            ItemArchived: self._on_item_archived,
        }
        handler = handlers.get(type(event))
        if handler:
            handler(event)

    def _on_item_created(self, event: ItemCreated) -> None:
        self.state.item_id = event.item_id
        self.state.company_id = event.company_id
        self.state.sku = event.sku
        self.state.name = event.name
        self.state.description = event.description
        self.state.category_id = event.category_id
        self.state.default_uom = event.default_uom
        self.state.item_type = event.item_type
        self.state.is_stock_item = event.is_stock_item
        self.state.created_by = event.created_by
        self.state.created_at = event.timestamp

    def _on_item_updated(self, event: ItemUpdated) -> None:
        if event.name is not None:
            self.state.name = event.name
        if event.description is not None:
            self.state.description = event.description
        if event.category_id is not None:
            self.state.category_id = event.category_id

    def _on_item_archived(self, event: ItemArchived) -> None:
        self.state.is_archived = True

    # =========================================================================
    # Replay
    # =========================================================================

    @classmethod
    def replay_from_events(cls, item_id: uuid.UUID, events: List[BaseEvent]) -> 'ItemAggregate':
        agg = cls(item_id)
        for evt in events:
            agg._apply(evt)
            agg.version += 1
        agg.mark_events_committed()
        return agg
```

### 10.3 Пример Command Handler

```python
# app/erp/items/command_handlers/item_handlers.py
from __future__ import annotations
import uuid
from typing import TYPE_CHECKING

from app.config.logging_config import get_logger
from app.erp.items.commands import CreateItemCommand, UpdateItemCommand, ArchiveItemCommand
from app.erp.items.aggregate import ItemAggregate
from app.infra.cqrs.decorators import command_handler
from app.common.base.base_command_handler import BaseCommandHandler

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = get_logger("wellwon.erp.items.handlers")

@command_handler(CreateItemCommand)
class CreateItemHandler(BaseCommandHandler):
    """Обработчик создания товара"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__(
            event_bus=deps.event_bus,
            transport_topic="transport.erp-events",
            event_store=deps.event_store
        )

    async def handle(self, command: CreateItemCommand) -> uuid.UUID:
        log.info(f"Creating item: {command.sku}")

        item = ItemAggregate(item_id=command.item_id)

        item.create_item(
            company_id=command.company_id,
            sku=command.sku,
            name=command.name,
            created_by=command.created_by,
            description=command.description,
            category_id=command.category_id,
            default_uom=command.default_uom,
            item_type=command.item_type,
            is_stock_item=command.is_stock_item,
        )

        await self.publish_and_commit_events(
            aggregate=item,
            aggregate_type="Item",
            expected_version=None,
        )

        log.info(f"Item created: {command.item_id}")
        return command.item_id
```

---

## РЕЗЮМЕ

### Ключевые принципы

1. **Event Sourcing = страховка** — события immutable, данные не потеряются
2. **Additive-only миграции** — не удаляем, только добавляем
3. **Feature Flags** — новая логика за флагом
4. **Версионирование событий** — upcasters для обратной совместимости
5. **Вопросы человеку** — архитектурные решения требуют approval

### Порядок разработки

```
Фаза 1: Справочники (items, partners, currencies, uom)
Фаза 2: Склад (warehouses, stock movements, balances)
Фаза 3: Заказы (sales orders, purchase orders)
Фаза 4: Финансы (invoices, payments)
Фаза 5: Декларант (параллельно)
```

### Готовность к старту

- [x] Инфраструктура Event Sourcing готова
- [x] CQRS Command/Query Bus готов
- [x] Saga Manager для сложных транзакций готов
- [x] PostgreSQL, Redis, Kafka настроены
- [x] React frontend готов
- [ ] Начать с модуля Items (Фаза 1)
