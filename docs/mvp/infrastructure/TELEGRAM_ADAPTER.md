# Telegram Adapter Infrastructure

**Status:** Complete
**Last Updated:** 2025-11-25

## Overview

The Telegram Adapter provides a unified interface for all Telegram operations following Hexagonal Architecture (Ports & Adapters) pattern. It abstracts away the complexity of dual-API integration (Bot API + MTProto).

## Architecture

```
app/infra/telegram/
├── __init__.py           # Package exports
├── config.py             # TelegramConfig with env vars
├── adapter.py            # TelegramAdapter (unified interface)
├── bot_client.py         # TelegramBotClient (aiogram 3.x)
├── mtproto_client.py     # TelegramMTProtoClient (Telethon)
└── listener.py           # Event listener (optional)
```

### Dual API Strategy

| Feature | Bot API (aiogram) | MTProto (Telethon) |
|---------|-------------------|---------------------|
| Send messages | Yes | No |
| Receive webhooks | Yes | No |
| File transfers | Yes | Limited |
| Create supergroups | No | Yes |
| Create forum topics | No | Yes |
| Manage topic emojis | No | Yes |
| Add bots as admin | No | Yes |
| Set group permissions | No | Yes |

## Configuration

### Environment Variables

```bash
# Bot API (aiogram)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...        # From @BotFather
TELEGRAM_WEBHOOK_URL=https://api.wellwon.com # Public URL for webhooks
TELEGRAM_WEBHOOK_SECRET=your-secret-token    # Webhook verification

# MTProto (Telethon)
TELEGRAM_API_ID=12345678                     # From my.telegram.org
TELEGRAM_API_HASH=abc123def456...            # From my.telegram.org
TELEGRAM_SESSION_STRING=1BVtsOK...           # Pre-generated session
TELEGRAM_SESSION_NAME=wellwon_telegram       # Fallback session file
TELEGRAM_ADMIN_PHONE=+79991234567            # For new sessions

# Bots to add to groups
TELEGRAM_BOT_USERNAMES=WellWonAssist_bot,wellwon_app_bot

# Feature flags
TELEGRAM_ENABLE_WEBHOOK=true                 # Enable Bot API webhook
TELEGRAM_ENABLE_MTPROTO=false               # Enable MTProto client
```

### TelegramConfig Class

```python
@dataclass
class TelegramConfig:
    # Bot API
    bot_token: str
    webhook_url: Optional[str]
    webhook_secret: str
    webhook_path: str = "/api/telegram/webhook"

    # MTProto
    api_id: int
    api_hash: str
    session_string: Optional[str]
    session_name: str
    admin_phone: Optional[str]

    # Bots to add to groups
    bot_usernames: List[str]

    # Rate limiting
    messages_per_second: float = 30.0
    messages_per_chat_per_minute: int = 20

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    @property
    def bot_api_available(self) -> bool:
        return bool(self.bot_token)

    @property
    def mtproto_available(self) -> bool:
        return bool(self.api_id and self.api_hash and (self.session_string or self.admin_phone))
```

## TelegramAdapter (Unified Interface)

### Initialization

```python
from app.infra.telegram.adapter import TelegramAdapter, get_telegram_adapter

# Using singleton
adapter = await get_telegram_adapter()

# Or manually
adapter = TelegramAdapter()
await adapter.initialize()
```

### Messaging (Bot API)

```python
# Send text message
result = await adapter.send_message(
    chat_id=-1001234567890,
    text="Hello, world!",
    topic_id=123,              # Forum topic ID
    reply_to=456,              # Reply to message
    parse_mode="HTML"          # HTML, Markdown, MarkdownV2
)

# Send file
result = await adapter.send_file(
    chat_id=-1001234567890,
    file_url="https://example.com/doc.pdf",
    file_name="document.pdf",
    caption="Check this out",
    topic_id=123
)

# Send voice
result = await adapter.send_voice(
    chat_id=-1001234567890,
    voice_url="https://example.com/voice.ogg",
    duration=30,               # seconds
    topic_id=123
)

# Edit message
result = await adapter.edit_message(
    chat_id=-1001234567890,
    message_id=789,
    text="Updated text"
)

# Delete message
success = await adapter.delete_message(chat_id=-1001234567890, message_id=789)

# Get file download URL
url = await adapter.get_file_url(file_id="AgACAgIAAxk...")
```

### Webhook Handling (Bot API)

```python
# Setup webhook
await adapter.setup_webhook()

# Remove webhook
await adapter.remove_webhook()

# Process incoming update (from FastAPI endpoint)
telegram_message = await adapter.process_webhook_update(update_data)
```

### Group Management (MTProto)

```python
# Create company group with forum, bots, and permissions
result = await adapter.create_company_group(
    company_name="Acme Corp",
    description="Company group for Acme Corp",
    photo_url="https://example.com/logo.png",
    setup_bots=True
)
# Result: CompanyGroupResult(success=True, group_id=..., invite_link=...)

# Get group info
info = await adapter.get_group_info(group_id)
# Returns: GroupInfo(group_id, title, description, invite_link, members_count)

# Update group
await adapter.update_group(group_id, title="New Title", description="New desc")
```

### Topic Management (MTProto)

```python
# Create topic with emoji
topic = await adapter.create_chat_topic(
    group_id=-1001234567890,
    topic_name="Orders",
    emoji="📦"
)
# Returns: TopicInfo(topic_id, title, emoji, emoji_id)

# Update topic
await adapter.update_chat_topic(
    group_id=-1001234567890,
    topic_id=123,
    new_name="Active Orders",
    new_emoji="🔥"
)

# Delete topic
await adapter.delete_chat_topic(group_id, topic_id)

# Get all topics
topics = await adapter.get_group_topics(group_id)
```

### User Management (MTProto)

```python
# Invite user to group
await adapter.invite_user_to_group(group_id, username="john_doe")

# Remove user from group
await adapter.remove_user_from_group(group_id, username="john_doe")
```

### Utility Methods

```python
# Normalize chat ID for storage (remove -100 prefix)
normalized = TelegramAdapter.normalize_chat_id(-1001234567890)
# Returns: "1234567890"

# Denormalize for Telegram API
telegram_id = TelegramAdapter.denormalize_chat_id("1234567890")
# Returns: -1001234567890

# Get available emojis for topics
emojis = TelegramAdapter.get_available_emojis()
# Returns: {"🎯": 5789953624849456205, "📝": 5787188704434982946, ...}
```

## Bot Client (aiogram 3.x)

### TelegramBotClient

Low-level Bot API client with rate limiting.

```python
from app.infra.telegram.bot_client import TelegramBotClient

client = TelegramBotClient(config)
await client.initialize()

# All messaging operations
result = await client.send_message(...)
result = await client.send_file(...)
result = await client.send_voice(...)
result = await client.edit_message(...)
success = await client.delete_message(...)
result = await client.forward_message(...)

# File handling
url = await client.get_file_url(file_id)

# Chat info
info = await client.get_chat_info(chat_id)
```

### TelegramMessage Model

```python
@dataclass
class TelegramMessage:
    message_id: int
    chat_id: int
    topic_id: Optional[int]
    from_user_id: Optional[int]
    from_username: Optional[str]
    text: Optional[str]
    date: Optional[datetime]
    reply_to_message_id: Optional[int]
    # File info
    file_id: Optional[str]
    file_url: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    file_type: Optional[str]  # photo, document, audio, voice, video
    voice_duration: Optional[int]
```

### SendMessageResult Model

```python
@dataclass
class SendMessageResult:
    success: bool
    message_id: Optional[int]
    error: Optional[str]
```

## MTProto Client (Telethon)

### TelegramMTProtoClient

Low-level MTProto client for user-level operations.

```python
from app.infra.telegram.mtproto_client import TelegramMTProtoClient

client = TelegramMTProtoClient(config)
await client.connect()

# Group operations
group = await client.create_supergroup(title, description, forum=True)
await client.update_group_title(group_id, new_title)
await client.update_group_description(group_id, description)
await client.set_group_photo(group_id, photo_url)
await client.set_group_permissions(group_id)
link = await client.get_invite_link(group_id)
info = await client.get_group_info(group_id)

# Topic operations
topic = await client.create_forum_topic(group_id, title, icon_emoji)
await client.update_forum_topic(group_id, topic_id, new_title, new_emoji)
await client.delete_forum_topic(group_id, topic_id)
await client.pin_forum_topic(group_id, topic_id, pinned=True)
topics = await client.get_forum_topics(group_id)

# Bot management
await client.add_bot_as_admin(group_id, bot_username, title)
results = await client.setup_group_bots(group_id)

# User management
await client.invite_user(group_id, username)
await client.remove_user(group_id, username)
```

### Available Emojis

```python
EMOJI_MAP = {
    # Main organizational
    "🎯": 5789953624849456205,
    "📝": 5787188704434982946,
    "💼": 5789678837029509659,
    "🔥": 5789419962516207616,
    "⚡": 5787544865457888514,
    "🚀": 5789739369064388642,
    "💡": 5787846042074624041,
    "🎉": 5789953624849456206,
    "📊": 5787188704434982947,
    "🔧": 5789678837029509660,
    # ... more emojis
}
```

### GroupInfo Model

```python
@dataclass
class GroupInfo:
    group_id: int
    title: str
    access_hash: Optional[int]
    description: Optional[str]
    invite_link: Optional[str]
    members_count: Optional[int]
```

### TopicInfo Model

```python
@dataclass
class TopicInfo:
    topic_id: int
    title: str
    emoji: Optional[str]
    emoji_id: Optional[int]
    pinned: bool
```

## Rate Limiting

The Bot Client implements per-chat rate limiting:

```python
# Configuration
messages_per_second: float = 30.0         # Global Telegram limit
messages_per_chat_per_minute: int = 20    # Per-chat limit

# Automatic tracking
async def _check_rate_limit(self, chat_id: int) -> bool:
    # Returns False if limit exceeded
    ...
```

## Error Handling

### Bot API Errors

```python
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

try:
    result = await adapter.send_message(...)
except TelegramRetryAfter as e:
    # Rate limited - retry after e.retry_after seconds
    pass
```

### MTProto Errors

MTProto errors are caught internally and return `None` or `False`:

```python
topic = await adapter.create_chat_topic(...)
if topic is None:
    # Operation failed - check logs for details
    pass
```

## Integration with Chat Domain

### Creating Company Group

```python
# In Chat command handler
result = await telegram_adapter.create_company_group(
    company_name=company.name,
    description=f"Official group for {company.name}",
    setup_bots=True
)

if result.success:
    # Emit TelegramSupergroupCreated event
    event = TelegramSupergroupCreated(
        company_id=company.id,
        telegram_group_id=result.group_id,
        title=result.group_title,
        invite_link=result.invite_link,
        is_forum=True,
        created_by=user_id,
    )
```

### Creating Chat Topic

```python
# When creating a new chat linked to Telegram
topic = await telegram_adapter.create_chat_topic(
    group_id=company.telegram_group_id,
    topic_name=chat.name,
    emoji="💬"
)

if topic:
    # Link chat to topic
    chat.telegram_topic_id = topic.topic_id
```

### Processing Webhook Messages

```python
# In FastAPI endpoint
@router.post("/webhook")
async def telegram_webhook(request: Request):
    update_data = await request.json()
    message = await telegram_adapter.process_webhook_update(update_data)

    if message:
        # Create ProcessTelegramMessageCommand
        await command_bus.dispatch(ProcessTelegramMessageCommand(
            chat_id=find_chat_by_telegram_id(message.chat_id),
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user_id,
            content=message.text,
            ...
        ))
```

## Session Management

### Generating Session String

For production, pre-generate the Telethon session string:

```python
# scripts/generate_telegram_session.py
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = 12345678
    api_hash = "your-api-hash"

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("Session string:")
        print(client.session.save())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Then set `TELEGRAM_SESSION_STRING` environment variable.

## Lifecycle Management

### Application Startup

```python
# In app startup
from app.infra.telegram.adapter import get_telegram_adapter

async def startup():
    adapter = await get_telegram_adapter()
    # Adapter is now ready to use
```

### Application Shutdown

```python
# In app shutdown
from app.infra.telegram.adapter import close_telegram_adapter

async def shutdown():
    await close_telegram_adapter()
```

## Dependencies

```
aiogram>=3.0.0        # Bot API client
telethon>=1.34.0      # MTProto client
aiohttp>=3.9.0        # HTTP client (for file downloads)
```

## Next Steps

1. Create `listener.py` for real-time event handling
2. Add message queuing for high-volume scenarios
3. Implement file storage integration
4. Add Telegram user mapping to WellWon users
5. Create admin dashboard for Telegram management
