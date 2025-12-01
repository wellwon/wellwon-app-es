# WSE Message Protocol Reference

## Overview

WebSocket Engine (WSE) использует стандартизированный протокол сообщений версии 2 для real-time коммуникации между сервером и клиентами. Этот документ описывает все конвенции именования и форматы сообщений для использования в других проектах.

---

## 1. Структура JSON сообщения

### Базовый формат (Protocol v2)

```json
{
    "t": "broker_account_update",
    "p": { ... },
    "id": "evt_abc123",
    "ts": "2025-01-13T10:30:00.000Z",
    "seq": 1234,
    "_msg_cat": "U",
    "v": 2
}
```

### Полная структура со всеми полями

| Поле | Алиас | Тип | Обязательно | Описание |
|------|-------|-----|-------------|----------|
| `t` | `type`, `event_type` | string | Да | Тип события |
| `p` | `payload` | object | Да | Данные события |
| `id` | - | string | Да | Уникальный ID события |
| `ts` | `timestamp` | string | Да | ISO 8601 timestamp |
| `seq` | `sequence` | int | Нет | Порядковый номер для ordering |
| `_msg_cat` | - | string | Нет | Категория сообщения: `S`, `U`, `WSE` |
| `cid` | `correlation_id` | string | Нет | ID для связывания запрос-ответ |
| `pri` | `priority` | int | Нет | Приоритет 1-10 |
| `cmp` | `compressed` | bool | Нет | Флаг сжатия (zlib) |
| `enc` | `encrypted` | bool | Нет | Флаг шифрования |
| `event_version` | - | int | Нет | Версия схемы payload |
| `trace_id` | - | string | Нет | ID для distributed tracing |
| `latency_ms` | - | int | Нет | Время обработки в мс |
| `v` | `version` | int | Да | Версия протокола (всегда `2`) |

---

## 2. Категории сообщений (`_msg_cat`)

### Три типа категорий

| Префикс | Название | Назначение |
|---------|----------|------------|
| **`S`** | Snapshot | Полный дамп состояния (initial sync) |
| **`U`** | Update | Инкрементальное обновление (delta) |
| **`WSE`** | System | Служебные сообщения протокола |

### Правила автоматического определения

```python
def determine_message_category(event_type: str) -> str:
    # Snapshot - полное состояние
    if "snapshot" in event_type.lower():
        return "S"

    # System - служебные сообщения WSE
    system_types = [
        'server_ready', 'snapshot_complete', 'client_hello_ack',
        'connection_state_change', 'error', 'pong', 'ping',
        'heartbeat', 'subscription_update'
    ]
    if event_type.lower() in system_types:
        return "WSE"

    # Default - инкрементальное обновление
    return "U"
```

---

## 3. Именование Event Types

### Snapshot Types (категория `S`)

Используются при initial sync или reconnect для передачи полного состояния:

```
{domain}_snapshot
```

**Примеры:**
- `broker_connection_snapshot` - все подключения к брокерам
- `broker_account_snapshot` - все аккаунты
- `order_snapshot` - все активные ордера
- `position_snapshot` - все позиции
- `portfolio_snapshot` - агрегированный портфель

### Update Types (категория `U`)

Инкрементальные обновления для конкретных изменений:

```
{domain}_{entity}_update
```

**Примеры:**
- `broker_account_update` - изменение аккаунта
- `broker_account_balance_update` - изменение баланса
- `broker_connection_update` - изменение статуса подключения
- `broker_health_update` - результат health check
- `order_update` - изменение ордера
- `position_update` - изменение позиции
- `market_data_update` - котировки/сделки

### System Types (категория `WSE`)

Служебные сообщения протокола:

| Type | Направление | Описание |
|------|-------------|----------|
| `ping` / `PING` | Client → Server | Запрос проверки latency |
| `PONG` | Server → Client | Ответ на ping |
| `client_hello` | Client → Server | Инициация handshake |
| `server_hello` | Server → Client | Подтверждение handshake |
| `server_ready` | Server → Client | Сервер готов к работе |
| `subscription_update` | Server → Client | Подтверждение подписки |
| `snapshot_complete` | Server → Client | Initial sync завершен |
| `connection_state_change` | Server → Client | Изменение состояния соединения |
| `heartbeat` | Both | Keep-alive |
| `error` | Server → Client | Ошибка |

---

## 4. Topic/Channel Naming

### User-scoped Topics

Все пользовательские топики следуют паттерну:

```
user:{user_id}:{topic_type}
```

### Стандартные Topic Types

| Topic Type | Содержимое |
|------------|------------|
| `broker_connection_events` | Lifecycle подключений к брокерам |
| `broker_account_events` | События аккаунтов |
| `broker_health` | Health check результаты |
| `broker_streaming` | Статус WebSocket стримов |
| `order_events` | События ордеров |
| `position_events` | События позиций |
| `portfolio_events` | Агрегированный портфель |
| `market_data` | Котировки, сделки, бары |
| `automation_events` | Стратегии и автоматизация |
| `events` | Общие события пользователя |
| `monitoring` | Системный мониторинг |
| `sync_progress` | Прогресс фоновой синхронизации |

### Системные Topics

```
system:announcements           # Broadcast всем пользователям
priority:{user_id}:messages    # Приоритетная очередь
```

### Redis Namespace

Все топики в Redis автоматически получают префикс `wse:`:

```
wse:user:abc123:order_events
wse:system:announcements
```

---

## 5. Priority Levels

### Числовые приоритеты (поле `pri`)

| Уровень | Значение | Использование |
|---------|----------|---------------|
| CRITICAL | 10 | Ордера, сделки, критичные изменения аккаунта |
| HIGH | 8 | Health checks, изменения состояния |
| NORMAL | 5 | Стандартные domain events (default) |
| LOW | 3 | Market data, мониторинг |
| BACKGROUND | 1 | Метрики, логи |

### Пример использования

```json
{
    "t": "order_update",
    "p": { "status": "filled" },
    "pri": 10,
    "v": 2
}
```

---

## 6. Connection States

### Состояния WebSocket соединения

```
PENDING → CONNECTING → CONNECTED
                ↓           ↓
            ERROR      RECONNECTING
                ↓           ↓
           DISCONNECTED ←───┘
                ↓
            DEGRADED (опционально)
```

| State | Описание |
|-------|----------|
| `pending` | Начальное состояние |
| `connecting` | Handshake в процессе |
| `connected` | Готов к обмену сообщениями |
| `reconnecting` | Автоматическое переподключение |
| `disconnected` | Соединение закрыто |
| `error` | Ошибка соединения |
| `degraded` | Работает с ограничениями (high latency) |

---

## 7. Примеры сообщений

### Broker Account Update (Incremental)

```json
{
    "t": "broker_account_update",
    "p": {
        "broker_account_id": "acc_123",
        "broker_id": "alpaca",
        "account_number": "PA1234567",
        "status": "active",
        "buying_power": 50000.00,
        "cash": 25000.00
    },
    "id": "evt_acc_001",
    "ts": "2025-11-25T10:00:00.000Z",
    "seq": 1,
    "_msg_cat": "U",
    "pri": 8,
    "v": 2
}
```

### Broker Account Snapshot (Initial Sync)

```json
{
    "t": "broker_account_snapshot",
    "p": {
        "accounts": [
            {
                "broker_account_id": "acc_123",
                "broker_id": "alpaca",
                "account_number": "PA1234567",
                "status": "active"
            },
            {
                "broker_account_id": "acc_456",
                "broker_id": "tradestation",
                "account_number": "TS9876543",
                "status": "active"
            }
        ],
        "count": 2,
        "sync_complete": true
    },
    "id": "evt_snap_001",
    "ts": "2025-11-25T10:00:00.000Z",
    "seq": 1,
    "_msg_cat": "S",
    "v": 2
}
```

### Order Update

```json
{
    "t": "order_update",
    "p": {
        "order_id": "ord_1",
        "symbol": "AAPL",
        "status": "filled",
        "filled_qty": 100,
        "avg_price": 150.25
    },
    "id": "evt_upd_042",
    "ts": "2025-11-25T10:05:30.500Z",
    "seq": 42,
    "_msg_cat": "U",
    "pri": 10,
    "v": 2
}
```

### System Message (PONG)

```json
{
    "t": "PONG",
    "p": {
        "client_timestamp": 1700000000000,
        "server_timestamp": 1700000000050,
        "latency_ms": 50
    },
    "id": "evt_pong_001",
    "ts": "2025-11-25T10:05:31.000Z",
    "_msg_cat": "WSE",
    "v": 2
}
```

### Error Message

```json
{
    "t": "error",
    "p": {
        "code": "SUBSCRIPTION_FAILED",
        "message": "Invalid topic format",
        "details": {
            "topic": "invalid-topic",
            "reason": "Topic must follow pattern user:{id}:{type}"
        }
    },
    "id": "evt_err_001",
    "ts": "2025-11-25T10:05:32.000Z",
    "_msg_cat": "WSE",
    "pri": 10,
    "v": 2
}
```

---

## 8. Event Transformation

### Маппинг внутренних событий → WebSocket types

При трансформации domain events в WebSocket сообщения:

1. Внутренний тип (`BrokerAccountLinked`) → WebSocket тип (`broker_account_update`)
2. Оригинальный тип сохраняется в `original_event_type` внутри payload

```json
{
    "t": "broker_account_update",
    "p": {
        "original_event_type": "BrokerAccountLinked",
        "broker_account_id": "acc_123",
        "status": "linked"
    },
    "v": 2
}
```

### Типичные маппинги

| Internal Event | WebSocket Type |
|----------------|----------------|
| `BrokerAccountLinked` | `broker_account_update` |
| `BrokerAccountUpdated` | `broker_account_update` |
| `BrokerAccountBalanceUpdated` | `broker_account_balance_update` |
| `BrokerConnectionInitiated` | `broker_connection_update` |
| `BrokerConnectionEstablished` | `broker_connection_update` |
| `BrokerConnectionDisconnected` | `broker_connection_update` |
| `OrderPlacedEvent` | `order_update` |
| `OrderFilledEvent` | `order_update` |
| `PositionOpenedEvent` | `position_update` |

---

## 9. Compression

### Правила сжатия

- **Порог:** Сообщения > 1024 байт сжимаются автоматически
- **Алгоритм:** zlib
- **Флаг:** `"cmp": true`

```json
{
    "t": "portfolio_snapshot",
    "p": "eJzLSM3JyVcozy/KSQEAGgsEHQ==",
    "cmp": true,
    "v": 2
}
```

---

## 10. Deduplication

### Механизмы дедупликации

1. **Event ID** - уникальный идентификатор каждого сообщения
2. **Sequence Number** - для ordering и gap detection
3. **Client-side tracking** - хранение последних N message IDs

### Рекомендации

- Хранить последние 1000 `id` на клиенте
- Игнорировать сообщения с уже виденными `id`
- Использовать `seq` для обнаружения пропущенных сообщений

---

## 11. Checklist для имплементации

### Server-side

- [ ] Все сообщения имеют обязательные поля: `t`, `p`, `id`, `ts`, `v`
- [ ] `_msg_cat` устанавливается автоматически по правилам
- [ ] Snapshot сообщения отправляются при подключении
- [ ] Priority устанавливается для критичных событий
- [ ] Сжатие применяется к большим сообщениям

### Client-side

- [ ] Поддержка алиасов полей (`t`/`type`, `p`/`payload`)
- [ ] Обработка всех трех категорий: `S`, `U`, `WSE`
- [ ] Дедупликация по `id`
- [ ] Ordering по `seq` (если используется)
- [ ] Декомпрессия при `cmp: true`

### Topics

- [ ] Формат: `user:{user_id}:{topic_type}`
- [ ] Redis namespace: `wse:` prefix
- [ ] Subscription по конкретным типам событий

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-11 | Current protocol version |
| 1.0 | 2025-01 | Initial implementation |
