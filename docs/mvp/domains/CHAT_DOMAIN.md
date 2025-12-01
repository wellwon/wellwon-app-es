# Chat Domain

**Version:** 1.0.0
**Last Updated:** 2025-12-01
**Status:** Production Ready

## Overview

The Chat domain handles all messaging functionality in WellWon, including:
- Chat rooms (company chats, direct messages)
- Messages (send, edit, delete)
- Participants (add, remove, roles)
- Telegram integration (bridge to Telegram supergroups)

## Architecture

### Storage Strategy (Discord Pattern)

| Data Type | Primary Storage | Secondary Storage |
|-----------|----------------|-------------------|
| **Messages** | ScyllaDB | - |
| **Chat Metadata** | PostgreSQL | - |
| **Participants** | PostgreSQL | - |
| **Read Status** | ScyllaDB | - |

**Why ScyllaDB for Messages:**
- High write throughput (millions of messages/day)
- Time-series optimized (messages ordered by timestamp)
- Horizontal scaling
- Low latency reads

## Domain Structure

```
app/chat/
├── aggregate.py              # ChatAggregate
├── commands.py               # Domain commands
├── events.py                 # Domain events
├── queries.py                # Domain queries
├── read_models.py            # Pydantic read models
├── projectors.py             # Event projectors
├── command_handlers/
│   ├── chat_handlers.py      # Chat lifecycle
│   ├── message_handlers.py   # Message operations
│   ├── participant_handlers.py # Participant management
│   └── telegram_handlers.py  # Telegram bridge
└── query_handlers/
    ├── chat_query_handlers.py
    ├── message_query_handlers.py
    └── template_query_handlers.py
```

## Events

### Chat Lifecycle

| Event | Projection | Description |
|-------|------------|-------------|
| `ChatCreated` | SYNC | New chat created |
| `ChatUpdated` | ASYNC | Chat metadata updated |
| `ChatArchived` | ASYNC | Chat archived |
| `ChatRestored` | ASYNC | Chat restored from archive |
| `ChatHardDeleted` | ASYNC | Chat permanently deleted |

### Messages

| Event | Projection | Description |
|-------|------------|-------------|
| `MessageSent` | SYNC | New message sent |
| `MessageEdited` | ASYNC | Message content edited |
| `MessageDeleted` | ASYNC | Message deleted |
| `MessagesMarkedAsRead` | ASYNC | Read receipts updated |

### Participants

| Event | Projection | Description |
|-------|------------|-------------|
| `ParticipantAdded` | SYNC | User added to chat |
| `ParticipantRemoved` | ASYNC | User removed from chat |
| `ParticipantRoleChanged` | ASYNC | User role changed |
| `ParticipantLeft` | ASYNC | User left chat |

### Telegram Integration

| Event | Projection | Description |
|-------|------------|-------------|
| `TelegramChatLinked` | ASYNC | Chat linked to Telegram |
| `TelegramChatUnlinked` | ASYNC | Chat unlinked from Telegram |
| `TelegramMessageReceived` | SYNC | Message from Telegram |

## Projector

```python
# app/chat/projectors.py

class ChatProjector:
    def __init__(self, chat_read_repo: ChatReadRepo, message_scylla_repo: MessageScyllaRepo):
        self.chat_read_repo = chat_read_repo
        self.message_scylla_repo = message_scylla_repo

    # SYNC: Chat must be visible immediately
    @sync_projection("ChatCreated")
    @monitor_projection
    async def on_chat_created(self, envelope: EventEnvelope) -> None:
        await self.chat_read_repo.insert_chat(...)

    # SYNC: Message must appear instantly
    @sync_projection("MessageSent")
    @monitor_projection
    async def on_message_sent(self, envelope: EventEnvelope) -> None:
        # Insert to ScyllaDB (primary)
        await self.message_scylla_repo.insert_message(...)
        # Update chat last_message_at (PostgreSQL)
        await self.chat_read_repo.update_chat_last_message(...)

    # ASYNC: Edits can be eventual
    @async_projection("MessageEdited")
    async def on_message_edited(self, envelope: EventEnvelope) -> None:
        await self.message_scylla_repo.update_message_content(...)

    # SYNC: Telegram messages need immediate visibility
    @sync_projection("TelegramMessageReceived")
    @monitor_projection
    async def on_telegram_message_received(self, envelope: EventEnvelope) -> None:
        await self.message_scylla_repo.insert_message(...)
```

## Read Models

### PostgreSQL Tables

```sql
-- Chat metadata
CREATE TABLE chats (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    chat_type VARCHAR(50),
    company_id UUID REFERENCES companies(id),
    created_by UUID REFERENCES users(id),
    last_message_at TIMESTAMPTZ,
    participant_count INTEGER DEFAULT 0,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat participants
CREATE TABLE chat_participants (
    id UUID PRIMARY KEY,
    chat_id UUID REFERENCES chats(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(chat_id, user_id)
);

-- Telegram bridge
CREATE TABLE chat_telegram_links (
    chat_id UUID PRIMARY KEY REFERENCES chats(id),
    telegram_chat_id BIGINT NOT NULL,
    linked_at TIMESTAMPTZ DEFAULT NOW()
);
```

### ScyllaDB Tables

```cql
-- Messages (primary storage)
CREATE TABLE messages (
    chat_id UUID,
    message_id TIMEUUID,
    sender_id UUID,
    content TEXT,
    message_type TEXT,
    reply_to_id TIMEUUID,
    is_edited BOOLEAN,
    is_deleted BOOLEAN,
    created_at TIMESTAMP,
    PRIMARY KEY (chat_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- Read status per user
CREATE TABLE message_read_status (
    chat_id UUID,
    user_id UUID,
    last_read_message_id TIMEUUID,
    read_at TIMESTAMP,
    PRIMARY KEY ((chat_id, user_id))
);
```

## API Endpoints

```
POST   /api/chats                    # Create chat
GET    /api/chats                    # List user's chats
GET    /api/chats/{id}               # Get chat details
PATCH  /api/chats/{id}               # Update chat
DELETE /api/chats/{id}               # Archive/delete chat

POST   /api/chats/{id}/messages      # Send message
GET    /api/chats/{id}/messages      # Get messages (paginated)
PATCH  /api/chats/{id}/messages/{mid}  # Edit message
DELETE /api/chats/{id}/messages/{mid}  # Delete message

POST   /api/chats/{id}/participants  # Add participant
DELETE /api/chats/{id}/participants/{uid}  # Remove participant
PATCH  /api/chats/{id}/participants/{uid}  # Change role

POST   /api/chats/{id}/telegram/link    # Link to Telegram
DELETE /api/chats/{id}/telegram/link    # Unlink from Telegram
```

## Real-time Updates (WSE)

Chat events are published to WebSocket clients via WSE:

```typescript
// Frontend subscription
useWSEQuery(['chat', chatId], fetchChat, 'chat_updated', {
  invalidateOn: (event) => event.p.chat_id === chatId
});

// Message subscription
useWSEQuery(['messages', chatId], fetchMessages, 'message_sent', {
  invalidateOn: (event) => event.p.chat_id === chatId,
  appendTo: 'messages'  // Optimistic append
});
```

## Telegram Bridge

### Flow: WellWon → Telegram

```
User sends message in WellWon
         ↓
MessageSent event
         ↓
TelegramAdapter.send_message()
         ↓
MTProto Client → Telegram API
         ↓
Message appears in Telegram supergroup
```

### Flow: Telegram → WellWon

```
User sends message in Telegram
         ↓
TelegramListener receives update
         ↓
Dispatch TelegramMessageReceivedCommand
         ↓
TelegramMessageReceived event
         ↓
@sync_projection → ScyllaDB
         ↓
WSE publishes to WebSocket
         ↓
Message appears in WellWon UI
```

## Statistics

| Metric | Count |
|--------|-------|
| SYNC projections | 4 |
| ASYNC projections | 12 |
| Total projections | 16 |
| Commands | 15 |
| Queries | 8 |
| Events | 16 |

## Related Documentation

- [PROJECTION_ARCHITECTURE.md](../architecture/PROJECTION_ARCHITECTURE.md)
- [SCYLLADB.md](../infrastructure/SCYLLADB.md)
- [TELEGRAM_ADAPTER.md](../infrastructure/TELEGRAM_ADAPTER.md)
