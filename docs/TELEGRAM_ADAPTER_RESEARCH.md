# TELEGRAM ADAPTER - ИССЛЕДОВАНИЕ И РЕКОМЕНДАЦИИ

**Дата:** 2025-11-25
**Статус:** Исследование завершено
**Цель:** Определить лучшее решение для высоконагруженного Telegram адаптера

---

## 1. АНАЛИЗ ТЕКУЩЕЙ РЕАЛИЗАЦИИ (Supabase)

### Что было в старой системе:

**1. Edge Functions (Deno) - Bot API:**
- `telegram-webhook` - прием сообщений (прямой HTTP к api.telegram.org)
- `telegram-send` - отправка сообщений (прямой HTTP)
- Никакого фреймворка, просто `fetch()`

**2. Отдельный микросервис (telegram-manage.onrender.com) - MTProto:**
- FastAPI + Telethon
- Создание супергрупп с форумами
- Управление топиками (create, rename, delete, emoji)
- Добавление ботов как админов
- Установка фото группы
- User-level операции, недоступные Bot API

### Почему две системы:

| Операция | Bot API | MTProto (Telethon) |
|----------|---------|-------------------|
| Отправка сообщений | ✅ | ✅ |
| Прием webhook | ✅ | ❌ (нет webhook) |
| Создание супергруппы | ❌ | ✅ |
| Создание форума | ❌ | ✅ |
| Создание топиков | ✅ (ограничено) | ✅ (полный контроль) |
| Emoji для топиков | ❌ | ✅ |
| Файлы до 50MB | ✅ | - |
| Файлы до 2GB | ❌ | ✅ |
| Несколько инстансов | ❌ | ✅ |

---

## 2. СРАВНЕНИЕ PYTHON БИБЛИОТЕК

### 2.1 Bot API библиотеки

| Библиотека | Async | Активность | Webhook | FSM | Рекомендация |
|------------|-------|------------|---------|-----|--------------|
| **aiogram 3.x** | ✅ | Активна | ✅ | ✅ | **РЕКОМЕНДУЮ** |
| python-telegram-bot | ✅ (v20+) | Активна | ✅ | ✅ | Альтернатива |
| pyTelegramBotAPI | ✅ | Активна | ✅ | ✅ | Проще, но слабее |

**Вывод:** aiogram 3.x - лучший выбор для Bot API:
- Полностью асинхронный (asyncio)
- Отличная интеграция с FastAPI
- Большое русскоязычное комьюнити
- Middleware, FSM, фильтры из коробки

### 2.2 MTProto библиотеки

| Библиотека | Статус | Производительность | Документация |
|------------|--------|-------------------|--------------|
| **Telethon** | ✅ Активна | Отлично | Отлично |
| Pyrogram | ⚠️ Заброшена | Отлично (TgCrypto) | Хорошо |
| Pyrogram (форки) | ✅ Активны | Отлично | Хорошо |

**Вывод:** Telethon - безопасный выбор:
- Активно поддерживается
- Отличная документация (docs.telethon.dev)
- Уже используется в текущей системе
- Pure Python, легко интегрировать

### 2.3 MTProto vs Bot API

**Преимущества MTProto:**
- Прямое соединение с серверами Telegram (нет HTTP overhead)
- Работает даже если Bot API endpoint упал
- Полный доступ к API (не ограничен публичным Bot API)
- Файлы до 2GB (Bot API: 50MB upload, 20MB download)
- Несколько сессий одновременно
- User-level операции

**Недостатки MTProto:**
- Нет webhook (нужен polling или постоянное соединение)
- Сложнее в настройке
- Требует session string (безопасность)
- Rate limits строже для user accounts

---

## 3. АРХИТЕКТУРА ДЛЯ HIGH-LOAD

### 3.1 Проблемы масштабирования

1. **Rate Limits Telegram:**
   - 30 сообщений/сек в один чат
   - 1 сообщение/сек в один чат (для ботов без Telegram Business)
   - Глобальные лимиты на API вызовы

2. **Long Polling vs Webhook:**
   - Long polling: только один инстанс бота
   - Webhook: можно балансировать, но нужен публичный endpoint

3. **State Management:**
   - При нескольких инстансах нужен shared state (Redis)

### 3.2 Best Practices для High-Load

```
┌─────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER                            │
│                    (nginx / traefik / k8s)                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                     WEBHOOK RECEIVERS                            │
│              (Multiple FastAPI instances)                        │
│                                                                  │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│   │ Pod 1   │  │ Pod 2   │  │ Pod 3   │  │ Pod N   │           │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
└────────┼────────────┼────────────┼────────────┼─────────────────┘
         │            │            │            │
         └────────────┴─────┬──────┴────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      MESSAGE QUEUE                               │
│                   (Redis / RabbitMQ)                             │
│                                                                  │
│   ┌──────────────────┐  ┌──────────────────┐                    │
│   │ incoming_queue   │  │ outgoing_queue   │                    │
│   └────────┬─────────┘  └────────▲─────────┘                    │
└────────────┼─────────────────────┼──────────────────────────────┘
             │                     │
┌────────────▼─────────────────────┴──────────────────────────────┐
│                       WORKERS                                    │
│                                                                  │
│   ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│   │  Message Processor      │  │  Telegram Sender            │  │
│   │  (Chat Domain commands) │  │  (Rate-limited, queued)     │  │
│   └─────────────────────────┘  └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Ключевые принципы:

1. **Webhook для приема** - scalable, event-driven
2. **Queue для отправки** - rate limiting, retry, ordering
3. **Redis для state** - typing indicators, session data
4. **Workers для обработки** - отделить прием от логики

---

## 4. РЕКОМЕНДУЕМОЕ РЕШЕНИЕ

### 4.1 Двухуровневая архитектура

```python
# app/infra/telegram/
├── __init__.py
├── bot_client.py       # aiogram 3.x - Bot API операции
├── mtproto_client.py   # Telethon - User-level операции
├── adapter.py          # TelegramAdapter - единый интерфейс
├── webhook.py          # FastAPI webhook endpoint
├── listener.py         # Слушает события Chat Domain
├── models.py           # Telegram-специфичные модели
├── rate_limiter.py     # Rate limiting для отправки
└── session_manager.py  # Управление Telethon сессиями
```

### 4.2 Bot API Client (aiogram)

```python
# app/infra/telegram/bot_client.py
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

class TelegramBotClient:
    """Bot API клиент для повседневных операций"""

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()

    async def send_message(
        self,
        chat_id: int,
        text: str,
        message_thread_id: int | None = None,
        reply_to_message_id: int | None = None,
        parse_mode: str = "HTML"
    ) -> Message:
        """Отправка текстового сообщения"""
        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=message_thread_id,
            reply_to_message_id=reply_to_message_id,
            parse_mode=parse_mode
        )

    async def send_photo(
        self,
        chat_id: int,
        photo: str | bytes,
        caption: str | None = None,
        message_thread_id: int | None = None
    ) -> Message:
        """Отправка фото"""
        return await self.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            message_thread_id=message_thread_id
        )

    async def send_document(
        self,
        chat_id: int,
        document: str | bytes,
        filename: str | None = None,
        caption: str | None = None,
        message_thread_id: int | None = None
    ) -> Message:
        """Отправка документа"""
        return await self.bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            message_thread_id=message_thread_id
        )

    async def get_file(self, file_id: str) -> bytes:
        """Скачивание файла"""
        file = await self.bot.get_file(file_id)
        return await self.bot.download_file(file.file_path)

    async def close(self):
        await self.bot.session.close()
```

### 4.3 MTProto Client (Telethon)

```python
# app/infra/telegram/mtproto_client.py
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    CreateForumTopicRequest,
    EditForumTopicRequest,
    DeleteTopicHistoryRequest,
    EditAdminRequest,
    InviteToChannelRequest,
)
from telethon.tl.types import ChatAdminRights

class TelegramMTProtoClient:
    """MTProto клиент для user-level операций"""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str
    ):
        self.client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )
        self._connected = False

    async def connect(self):
        if not self._connected:
            await self.client.connect()
            self._connected = True

    async def disconnect(self):
        if self._connected:
            await self.client.disconnect()
            self._connected = False

    async def create_supergroup(
        self,
        title: str,
        description: str = "",
        forum: bool = True
    ) -> dict:
        """Создание супергруппы с форумом"""
        await self.connect()

        result = await self.client(CreateChannelRequest(
            title=title,
            about=description,
            megagroup=True,
            forum=forum
        ))

        group = result.chats[0]
        return {
            "group_id": group.id,
            "title": group.title,
            "access_hash": group.access_hash
        }

    async def create_forum_topic(
        self,
        group_id: int,
        title: str,
        icon_emoji_id: int | None = None
    ) -> dict:
        """Создание топика в форуме"""
        await self.connect()

        group = await self.client.get_entity(group_id)

        result = await self.client(CreateForumTopicRequest(
            channel=group,
            title=title,
            icon_emoji_id=icon_emoji_id
        ))

        topic_id = result.updates[0].message.id
        return {
            "topic_id": topic_id,
            "title": title
        }

    async def update_forum_topic(
        self,
        group_id: int,
        topic_id: int,
        title: str | None = None,
        icon_emoji_id: int | None = None
    ) -> bool:
        """Обновление топика"""
        await self.connect()

        group = await self.client.get_entity(group_id)

        await self.client(EditForumTopicRequest(
            channel=group,
            topic_id=topic_id,
            title=title,
            icon_emoji_id=icon_emoji_id
        ))
        return True

    async def delete_forum_topic(
        self,
        group_id: int,
        topic_id: int
    ) -> bool:
        """Удаление топика"""
        await self.connect()

        group = await self.client.get_entity(group_id)

        await self.client(DeleteTopicHistoryRequest(
            channel=group,
            top_msg_id=topic_id
        ))
        return True

    async def add_bot_as_admin(
        self,
        group_id: int,
        bot_username: str,
        title: str = "Bot"
    ) -> bool:
        """Добавление бота как админа"""
        await self.connect()

        group = await self.client.get_entity(group_id)
        bot = await self.client.get_entity(bot_username)

        # Сначала приглашаем
        await self.client(InviteToChannelRequest(
            channel=group,
            users=[bot]
        ))

        # Потом назначаем админом
        rights = ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            manage_topics=True,
            manage_call=True,
            other=True
        )

        await self.client(EditAdminRequest(
            channel=group,
            user_id=bot,
            admin_rights=rights,
            rank=title
        ))
        return True
```

### 4.4 TelegramAdapter (unified interface)

```python
# app/infra/telegram/adapter.py
from typing import Protocol
from uuid import UUID

class TelegramAdapter:
    """Адаптер к Telegram для Chat Domain (Hexagonal Architecture)"""

    def __init__(
        self,
        bot_client: TelegramBotClient,
        mtproto_client: TelegramMTProtoClient
    ):
        self.bot = bot_client
        self.mtproto = mtproto_client

    # === MESSAGING (Bot API) ===

    async def send_message(
        self,
        chat_id: int,
        text: str,
        topic_id: int | None = None,
        reply_to: int | None = None
    ) -> int:
        """Отправка сообщения, возвращает telegram_message_id"""
        msg = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=topic_id,
            reply_to_message_id=reply_to
        )
        return msg.message_id

    async def send_file(
        self,
        chat_id: int,
        file_url: str,
        file_type: str,
        caption: str | None = None,
        topic_id: int | None = None
    ) -> int:
        """Отправка файла"""
        if file_type == "photo":
            msg = await self.bot.send_photo(
                chat_id=chat_id,
                photo=file_url,
                caption=caption,
                message_thread_id=topic_id
            )
        else:
            msg = await self.bot.send_document(
                chat_id=chat_id,
                document=file_url,
                caption=caption,
                message_thread_id=topic_id
            )
        return msg.message_id

    async def download_file(self, file_id: str) -> bytes:
        """Скачивание файла из Telegram"""
        return await self.bot.get_file(file_id)

    # === GROUP MANAGEMENT (MTProto) ===

    async def create_company_group(
        self,
        company_name: str,
        description: str = ""
    ) -> dict:
        """Создание группы для компании"""
        return await self.mtproto.create_supergroup(
            title=company_name,
            description=description,
            forum=True
        )

    async def create_chat_topic(
        self,
        group_id: int,
        topic_name: str,
        emoji: str | None = None
    ) -> dict:
        """Создание топика для чата"""
        emoji_id = self._get_emoji_id(emoji) if emoji else None
        return await self.mtproto.create_forum_topic(
            group_id=group_id,
            title=topic_name,
            icon_emoji_id=emoji_id
        )

    async def setup_group_bots(self, group_id: int) -> list[dict]:
        """Настройка ботов в группе"""
        results = []

        for bot_config in self._bot_configs:
            try:
                await self.mtproto.add_bot_as_admin(
                    group_id=group_id,
                    bot_username=bot_config["username"],
                    title=bot_config["title"]
                )
                results.append({"bot": bot_config["username"], "status": "ok"})
            except Exception as e:
                results.append({"bot": bot_config["username"], "status": "error", "error": str(e)})

        return results

    # === HELPERS ===

    @staticmethod
    def normalize_chat_id(telegram_id: int) -> str:
        """Нормализация Telegram ID для хранения"""
        if telegram_id > 0:
            return str(telegram_id)
        return str(telegram_id * -1 - 1000000000000)

    @staticmethod
    def denormalize_chat_id(normalized_id: str) -> int:
        """Денормализация для отправки в Telegram"""
        id_int = int(normalized_id)
        if id_int > 0:
            return id_int
        return (id_int + 1000000000000) * -1

    _EMOJI_MAP = {
        "🎯": 5789953624849456205,
        "📝": 5787188704434982946,
        "💼": 5789678837029509659,
        # ... остальные emoji из старого кода
    }

    def _get_emoji_id(self, emoji: str) -> int | None:
        return self._EMOJI_MAP.get(emoji)
```

### 4.5 Webhook Handler

```python
# app/infra/telegram/webhook.py
from fastapi import APIRouter, Request, HTTPException
from aiogram.types import Update

router = APIRouter(prefix="/telegram", tags=["telegram"])

@router.post("/webhook/{bot_token}")
async def telegram_webhook(
    bot_token: str,
    request: Request,
    telegram: TelegramAdapter = Depends(get_telegram_adapter),
    command_bus: CommandBus = Depends(get_command_bus)
):
    """Webhook endpoint для Telegram Bot"""

    # Валидация токена
    if bot_token != settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    # Парсим update
    update_data = await request.json()
    update = Update(**update_data)

    # Обрабатываем сообщение
    if update.message:
        await _handle_message(update.message, telegram_service, command_bus)
    elif update.edited_message:
        await _handle_edited_message(update.edited_message, command_bus)

    return {"ok": True}


async def _handle_message(
    msg: Message,
    telegram: TelegramAdapter,
    command_bus: CommandBus
):
    """Обработка входящего сообщения"""

    # Нормализуем chat_id
    normalized_chat_id = telegram.normalize_chat_id(msg.chat.id)
    topic_id = str(msg.message_thread_id) if msg.message_thread_id else None

    # Ищем чат в нашей системе
    chat = await chat_repo.find_by_external_channel(
        channel_type="telegram",
        channel_id=normalized_chat_id,
        topic_id=topic_id
    )

    if not chat or not chat.sync_enabled:
        return  # Игнорируем

    # Скачиваем файл если есть
    file_url = None
    if msg.photo or msg.document or msg.voice:
        file_id = _get_file_id(msg)
        file_data = await telegram.download_file(file_id)
        file_url = await file_storage.upload(file_data, _get_filename(msg))

    # Отправляем команду в Chat Domain
    command = ReceiveExternalMessageCommand(
        chat_id=chat.chat_id,
        external_sender_id=str(msg.from_user.id),
        external_sender_name=_get_sender_name(msg.from_user),
        content=msg.text or msg.caption or "",
        message_type=_detect_message_type(msg),
        file_url=file_url,
        external_message_id=str(msg.message_id)
    )

    await command_bus.dispatch(command)
```

### 4.6 Event Listener

```python
# app/infra/telegram/listener.py
class TelegramEventListener:
    """Слушает события Chat Domain и отправляет в Telegram"""

    def __init__(
        self,
        telegram: TelegramAdapter,
        chat_repo: ChatReadRepository
    ):
        self.telegram = telegram
        self.chat_repo = chat_repo

    @subscribe_to("MessageSent")
    async def on_message_sent(self, event: MessageSent):
        """Web → Telegram"""
        chat = await self.chat_repo.get_by_id(event.chat_id)

        if not chat.sync_enabled or chat.external_channel_type != "telegram":
            return

        telegram_chat_id = self.telegram.denormalize_chat_id(chat.external_channel_id)
        topic_id = int(chat.external_topic_id) if chat.external_topic_id else None

        if event.file_url:
            await self.telegram.send_file(
                chat_id=telegram_chat_id,
                file_url=event.file_url,
                file_type=event.message_type,
                caption=event.content,
                topic_id=topic_id
            )
        else:
            await self.telegram.send_message(
                chat_id=telegram_chat_id,
                text=event.content,
                topic_id=topic_id
            )

    @subscribe_to("ChatCreated")
    async def on_chat_created(self, event: ChatCreated):
        """Создание топика при создании чата (если нужно)"""
        # Логика создания топика в Telegram группе
        pass
```

---

## 5. ЗАВИСИМОСТИ

```toml
# pyproject.toml

[tool.poetry.dependencies]
# Bot API
aiogram = "^3.17.0"

# MTProto
telethon = "^1.37.0"

# Async HTTP (уже есть)
httpx = "^0.27.0"
aiohttp = "^3.9.0"

# Rate limiting
aiolimiter = "^1.1.0"
```

---

## 6. КОНФИГУРАЦИЯ

```python
# app/config/telegram_config.py
from pydantic_settings import BaseSettings

class TelegramSettings(BaseSettings):
    # Bot API
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str | None = None
    TELEGRAM_WEBHOOK_URL: str | None = None

    # MTProto (для user-level операций)
    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str
    TELEGRAM_SESSION_STRING: str
    TELEGRAM_PHONE: str | None = None  # Для первичной авторизации

    # Bots to add to groups
    TELEGRAM_BOT_USERNAMES: list[str] = ["WellWonAssist_bot", "wellwon_app_bot"]

    # Rate limits
    TELEGRAM_RATE_LIMIT_MESSAGES_PER_SECOND: int = 30
    TELEGRAM_RATE_LIMIT_MESSAGES_PER_CHAT: int = 1

    class Config:
        env_file = ".env"
```

---

## 7. ИТОГОВАЯ РЕКОМЕНДАЦИЯ

### Использовать:

| Компонент | Библиотека | Причина |
|-----------|------------|---------|
| Bot API | **aiogram 3.x** | Async, FastAPI интеграция, FSM, активно |
| MTProto | **Telethon** | Стабильный, документация, уже используется |
| Queue | **Redis** | Уже есть в инфраструктуре |
| Rate Limiter | **aiolimiter** | Простой, async |

### НЕ делать:
- ❌ Свой MTProto клиент (слишком сложно, ~50k строк)
- ❌ Pyrogram (оригинальный заброшен)
- ❌ Telepot (мёртв)
- ❌ Прямые HTTP вызовы без фреймворка (aiogram лучше)

### Преимущества:
1. **Разделение ответственности** - Bot API для сообщений, MTProto для управления
2. **Высокая нагрузка** - Webhook + Queue + Workers
3. **Чистая архитектура** - TelegramService скрывает детали от Chat Domain
4. **Надёжность** - Rate limiting, retry, error handling
5. **Масштабируемость** - Горизонтальное масштабирование через K8s

---

## 8. ПЛАН РЕАЛИЗАЦИИ

1. [ ] Установить aiogram + telethon
2. [ ] Создать `app/infra/telegram/` структуру
3. [ ] Реализовать TelegramBotClient (aiogram)
4. [ ] Реализовать TelegramMTProtoClient (telethon)
5. [ ] Реализовать TelegramService (unified)
6. [ ] Настроить webhook endpoint
7. [ ] Реализовать event listener
8. [ ] Перенести session string из старого сервиса
9. [ ] Тестирование

---

## ИСТОЧНИКИ

- [Telethon: Bot API vs MTProto](https://docs.telethon.dev/en/stable/concepts/botapi-vs-mtproto.html)
- [Pyrogram: MTProto vs Bot API](https://docs.pyrogram.org/topics/mtproto-vs-botapi)
- [aiogram Documentation](https://docs.aiogram.dev/)
- [Scaling Telegram Bots](https://grammy.dev/advanced/scaling)
- [Stack Overflow: Telethon vs Aiogram](https://stackoverflow.com/questions/75488871/telethon-or-aiogram-pros-and-cons-which-is-better)
- [High Load Bot Architecture](https://www.nextstruggle.com/how-to-scale-your-telegram-bot-for-high-traffic-best-practices-strategies/askdushyant/)
- [aiogram + FastAPI Integration](https://github.com/QuvonchbekBobojonov/aiogram-webhook-template)
