# =============================================================================
# File: app/infra/telegram/mtproto_client.py
# Description: Telegram MTProto client using Telethon for user-level operations
# =============================================================================

from __future__ import annotations

import logging
import asyncio
import random
import time
from functools import wraps
from typing import Optional, List, Dict, Any, Callable, TypeVar, Tuple
from dataclasses import dataclass, field

from app.config.telegram_config import TelegramConfig

log = logging.getLogger("wellwon.telegram.mtproto_client")

# Type variable for generic return type
T = TypeVar('T')


def _calculate_backoff_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    multiplier: float,
    jitter: bool
) -> float:
    """Calculate exponential backoff delay with optional jitter."""
    delay = min(initial_delay * (multiplier ** attempt), max_delay)
    if jitter:
        # Full jitter: random between 0 and delay
        delay = random.uniform(0, delay)
    return delay


async def _retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    operation_name: str = "operation",
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Handles FloodWaitError by waiting the required time plus backoff.
    Other exceptions trigger standard backoff retries.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum retry attempts
        initial_delay: Initial backoff delay in seconds
        max_delay: Maximum backoff delay in seconds
        multiplier: Exponential multiplier
        jitter: Add random jitter to delays
        operation_name: Name for logging
        **kwargs: Keyword arguments for func

    Returns:
        Result of func if successful

    Raises:
        Last exception if all retries fail
    """
    # Import FloodWaitError lazily to avoid import issues
    try:
        from telethon.errors import FloodWaitError as TelethonFloodWaitError
    except ImportError:
        TelethonFloodWaitError = None

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Check if it's a FloodWaitError
            is_flood_error = TelethonFloodWaitError and isinstance(e, TelethonFloodWaitError)

            if is_flood_error:
                # FloodWaitError - must wait the specified time
                wait_time = e.seconds + 1  # Add 1 second buffer
                if attempt < max_retries:
                    log.warning(
                        f"[{operation_name}] FloodWaitError: waiting {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = e
                    continue
                else:
                    raise

            # Other exceptions - use exponential backoff
            last_exception = e
            if attempt < max_retries:
                delay = _calculate_backoff_delay(
                    attempt=attempt,
                    initial_delay=initial_delay,
                    max_delay=max_delay,
                    multiplier=multiplier,
                    jitter=jitter
                )
                log.warning(
                    f"[{operation_name}] Retry {attempt + 1}/{max_retries + 1} after {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception

# Lazy import telethon to avoid import errors when not installed
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import (
        CreateChannelRequest,
        EditAdminRequest,
        InviteToChannelRequest,
        EditTitleRequest,
        EditPhotoRequest,
        EditBannedRequest,
        ToggleForumRequest,
        GetParticipantsRequest,
    )
    from telethon.tl.types import ChannelParticipantsSearch
    from telethon.tl.functions.messages import (
        ExportChatInviteRequest,
        EditChatDefaultBannedRightsRequest,
        EditChatAboutRequest,
        CreateForumTopicRequest,
        EditForumTopicRequest,
        DeleteTopicHistoryRequest,
        GetForumTopicsRequest,
        UpdatePinnedForumTopicRequest,
    )
    from telethon.tl.functions.contacts import ResolveUsernameRequest
    from telethon.tl.types import ChatAdminRights, ChatBannedRights
    from telethon.errors import FloodWaitError, ChannelPrivateError, ChannelInvalidError
    TELETHON_AVAILABLE = True
except ImportError as e:
    TELETHON_AVAILABLE = False
    TelegramClient = None
    StringSession = None
    events = None
    log.warning(f"telethon not installed or import error: {e}. MTProto features will be disabled.")


# Emoji ID mapping for forum topics
EMOJI_MAP = {
    # Main organizational emojis
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
    "🌟": 5789419962516207617,
    "📱": 5787544865457888515,
    "💰": 5789739369064388643,
    "🎮": 5787846042074624042,
    "🏆": 5789953624849456207,
    "📈": 5787188704434982948,
    "🔔": 5789678837029509661,
    "💻": 5789419962516207618,
    "🎨": 5787544865457888516,
    "🎵": 5789739369064388644,
    # Status emojis
    "✅": 5789953624849456208,
    "❌": 5789953624849456209,
    "⚡️": 5787544865457888517,
    "🗄️": 5789678837029509662,
    "🔒": 5789678837029509663,
    "🔓": 5789678837029509664,
    "⏰": 5787544865457888518,
    "📅": 5787188704434982950,
    "🔍": 5789678837029509665,
    "📦": 5787188704434982951,
    "🏠": 5789953624849456211,
    "🌐": 5789419962516207619,
    "🔗": 5789678837029509666,
    "📬": 5787188704434982952,
    "📭": 5787188704434982953,
    "📋": 5787188704434982949,
}

# Default bot configuration for groups
DEFAULT_BOTS_CONFIG = [
    {
        "username": "WellWonAssist_bot",
        "title": "Assistant",
    },
    {
        "username": "wellwon_app_bot",
        "title": "Manager",
    }
]


@dataclass
class GroupInfo:
    """Information about a Telegram group"""
    group_id: int
    title: str
    access_hash: Optional[int] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    members_count: Optional[int] = None


@dataclass
class TopicInfo:
    """Information about a forum topic"""
    topic_id: int
    title: str
    emoji: Optional[str] = None
    emoji_id: Optional[int] = None
    pinned: bool = False


@dataclass
class OperationResult:
    """Generic result for MTProto operations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class MemberInfo:
    """Information about a group member"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: bool = False
    status: str = "member"  # creator, administrator, member, restricted, left, kicked


@dataclass
class IncomingMessage:
    """Incoming message from Telegram via MTProto"""
    message_id: int
    chat_id: int  # Full Telegram chat ID with -100 prefix
    topic_id: Optional[int]
    sender_id: int
    sender_username: Optional[str]
    sender_first_name: Optional[str]
    sender_last_name: Optional[str]
    sender_is_bot: bool
    text: Optional[str]
    date: Any  # datetime
    # File info
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None  # photo, document, voice, video, etc.
    voice_duration: Optional[int] = None


class TelegramMTProtoClient:
    """
    Telegram MTProto client for user-level operations.

    Uses Telethon for operations that are not available through Bot API:
    - Creating supergroups with forums
    - Managing forum topics (create, edit, delete)
    - Setting topic emojis
    - Adding bots as administrators
    - Setting group photos
    - Managing group permissions

    IMPORTANT: Incoming messages are received via polling, not push events.
    This is because Telethon's event system doesn't work reliably when the
    same session is used on multiple devices (phone, desktop, etc.).
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self._client: Optional['TelegramClient'] = None
        self._connected = False
        self._bots_config = DEFAULT_BOTS_CONFIG
        self._message_callback: Optional[callable] = None
        self._update_task: Optional[asyncio.Task] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._monitored_chats: Dict[int, int] = {}  # telegram_chat_id -> last_message_id
        self._polling_interval: float = 5.0  # Poll every 5 seconds for faster message detection

        # Entity cache for reducing API calls (Telethon best practice)
        self._entity_cache: Dict[int, Tuple[Any, float]] = {}  # id -> (entity, timestamp)
        self._entity_cache_populated = False

        # Reconnection state
        self._reconnect_attempts = 0
        self._last_disconnect_time: Optional[float] = None

    async def connect(self) -> bool:
        """Connect to Telegram MTProto servers"""
        if not TELETHON_AVAILABLE:
            log.error("telethon not installed. Cannot connect to MTProto.")
            return False

        if self._connected:
            return True

        try:
            # Create client with StringSession if available
            session_string = getattr(self.config, 'session_string', None)
            if session_string:
                log.debug("Using existing session string for MTProto")
                self._client = TelegramClient(
                    StringSession(session_string),
                    self.config.api_id,
                    self.config.api_hash
                )
            else:
                log.debug("Creating new session for MTProto")
                self._client = TelegramClient(
                    self.config.session_name,
                    self.config.api_id,
                    self.config.api_hash
                )

            # Set flood_sleep_threshold (Telethon best practice)
            # Auto-sleep for FloodWaitError if wait is below threshold
            flood_threshold = getattr(self.config, 'flood_sleep_threshold', 60)
            self._client.flood_sleep_threshold = flood_threshold
            log.info(f"MTProto flood_sleep_threshold set to {flood_threshold}s")

            await self._client.connect()

            # Validate session - check if session is authorized
            if not await self._client.is_user_authorized():
                if self.config.admin_phone:
                    log.info(f"Starting MTProto authorization for {self.config.admin_phone}")
                    await self._client.start(phone=self.config.admin_phone)
                else:
                    log.error("MTProto not authorized and no phone number provided")
                    return False

            # Session validation - verify we can get user info
            me = await self._client.get_me()
            if not me:
                log.error("MTProto session invalid - cannot get user info")
                return False

            log.info(f"MTProto connected as: {me.first_name} (ID: {me.id})")
            print(f"[MTPROTO] Connected as: {me.first_name} (ID: {me.id})")

            # Reset reconnection counter on successful connect
            self._reconnect_attempts = 0

            # Register incoming message handler
            @self._client.on(events.NewMessage(incoming=True))
            async def handle_new_message(event):
                await self._handle_new_message(event)

            log.info("MTProto message handler registered")
            print("[MTPROTO] Message handler registered")

            # Start the update loop in a background task
            # This is required for Telethon to actually receive new messages
            self._update_task = asyncio.create_task(self._run_update_loop())
            log.info("MTProto update loop started in background")
            print("[MTPROTO] Update loop started - ready to receive messages")

            # Pre-populate entity cache if configured (Telethon best practice)
            # This avoids ResolveUsernameRequest calls for entities in our dialogs
            cache_on_connect = getattr(self.config, 'cache_dialogs_on_connect', True)
            if cache_on_connect and not self._entity_cache_populated:
                asyncio.create_task(self._populate_entity_cache())

            self._connected = True
            return True

        except Exception as e:
            log.error(f"Failed to connect MTProto: {e}", exc_info=True)
            # Attempt reconnection if configured
            if getattr(self.config, 'auto_reconnect', True):
                asyncio.create_task(self._attempt_reconnect())
            return False

    async def _run_update_loop(self) -> None:
        """
        Run Telethon's update loop in the background.

        The key insight from Telethon's source code is that to receive updates,
        we must call GetStateRequest() to notify Telegram we want updates.
        This is what _run_until_disconnected() does internally.

        We implement our own version that:
        1. Requests updates from Telegram via GetStateRequest
        2. Waits for disconnection (which keeps the background tasks alive)
        3. Does NOT disconnect on cancellation (unlike run_until_disconnected)
        """
        try:
            log.info("MTProto update loop starting...")
            print("[MTPROTO] Update loop starting - requesting update state...")

            # Import the function to request updates
            from telethon.tl import functions

            # This is CRITICAL: Tell Telegram we want to receive updates
            # Without this call, Telegram won't send us any updates!
            await self._client(functions.updates.GetStateRequest())
            log.info("MTProto GetStateRequest sent - Telegram will now send updates")
            print("[MTPROTO] GetStateRequest sent - ready to receive updates!")

            # Now wait for disconnection - this keeps our event handlers active
            # The actual update processing happens in Telethon's background tasks
            await self._client.disconnected

            log.info("MTProto update loop ended (client disconnected)")
        except asyncio.CancelledError:
            log.info("MTProto update loop cancelled (server shutdown)")
            # Don't disconnect here - the server may restart the task
        except Exception as e:
            log.error(f"MTProto update loop error: {e}", exc_info=True)
            print(f"[MTPROTO] Update loop error: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Telegram"""
        if self._client and self._connected:
            self._last_disconnect_time = time.time()
            await self._client.disconnect()
            self._connected = False
            log.info("MTProto disconnected")

    async def _attempt_reconnect(self) -> bool:
        """
        Attempt to reconnect to Telegram with exponential backoff.

        This is called automatically when connection is lost and
        auto_reconnect is enabled in config.

        Returns:
            True if reconnection succeeded, False if max attempts reached
        """
        max_attempts = getattr(self.config, 'max_reconnect_attempts', 5)

        while self._reconnect_attempts < max_attempts:
            self._reconnect_attempts += 1

            # Calculate backoff delay
            delay = _calculate_backoff_delay(
                attempt=self._reconnect_attempts - 1,
                initial_delay=getattr(self.config, 'reconnect_delay', 5.0),
                max_delay=getattr(self.config, 'backoff_max_delay', 300.0),
                multiplier=getattr(self.config, 'backoff_multiplier', 2.0),
                jitter=getattr(self.config, 'backoff_jitter', True)
            )

            log.warning(
                f"MTProto connection lost. Attempting reconnect {self._reconnect_attempts}/{max_attempts} "
                f"in {delay:.1f}s"
            )
            await asyncio.sleep(delay)

            try:
                # Reset client state
                self._client = None
                self._connected = False

                # Attempt reconnection
                if await self.connect():
                    log.info(f"MTProto reconnected successfully after {self._reconnect_attempts} attempts")
                    return True
            except Exception as e:
                log.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")

        log.error(f"MTProto failed to reconnect after {max_attempts} attempts")
        return False

    async def _ensure_connected(self) -> bool:
        """Ensure client is connected"""
        if not self._connected:
            return await self.connect()
        return True

    def set_message_callback(self, callback: callable) -> None:
        """Set callback for incoming messages"""
        self._message_callback = callback
        log.info("MTProto message callback registered")

    def add_monitored_chat(self, telegram_chat_id: int, last_message_id: int = 0) -> None:
        """
        Add a Telegram chat to the polling monitor.

        Args:
            telegram_chat_id: Telegram chat ID (positive, without -100 prefix)
            last_message_id: Last known message ID (to avoid re-processing old messages)
        """
        self._monitored_chats[telegram_chat_id] = last_message_id
        log.info(f"Added chat {telegram_chat_id} to polling monitor (last_msg_id={last_message_id})")

    def remove_monitored_chat(self, telegram_chat_id: int) -> None:
        """Remove a Telegram chat from the polling monitor."""
        if telegram_chat_id in self._monitored_chats:
            del self._monitored_chats[telegram_chat_id]
            log.info(f"Removed chat {telegram_chat_id} from polling monitor")

    async def start_polling(self) -> None:
        """Start the message polling task."""
        if self._polling_task is None or self._polling_task.done():
            # Pre-populate entity cache by iterating dialogs once
            await self._populate_entity_cache()

            self._polling_task = asyncio.create_task(self._run_polling_loop())
            log.info("MTProto polling task started")
            print(f"[MTPROTO] Polling task started - will check for new messages every {int(self._polling_interval)} seconds")

    async def _populate_entity_cache(self) -> None:
        """
        Populate the entity cache by iterating through dialogs.

        This is a Telethon best practice to avoid ResolveUsernameRequest calls
        that can trigger rate limits. By caching all entities from dialogs,
        subsequent get_entity() calls will use the cached version.

        The cache is stored both in Telethon's internal session and in our
        own _entity_cache dict for TTL management.
        """
        if not self._connected or not self._client:
            return

        try:
            log.info("Populating entity cache from dialogs...")
            count = 0
            current_time = time.time()

            async for dialog in self._client.iter_dialogs():
                entity = dialog.entity
                if entity and hasattr(entity, 'id'):
                    # Cache in our local cache with timestamp
                    self._entity_cache[entity.id] = (entity, current_time)
                    count += 1

            self._entity_cache_populated = True
            log.info(f"Entity cache populated with {count} dialogs")
            print(f"[MTPROTO] Entity cache populated with {count} dialogs")

        except FloodWaitError as e:
            # Handle rate limit during cache population
            log.warning(f"FloodWaitError during entity cache population: {e.seconds}s wait required")
            # Don't mark as populated - will retry on next connect
        except Exception as e:
            log.warning(f"Failed to populate entity cache: {e}")

    async def _get_cached_entity(self, entity_id: int) -> Optional[Any]:
        """
        Get entity from cache if available and not expired.

        Args:
            entity_id: Telegram entity ID

        Returns:
            Cached entity or None if not found/expired
        """
        if entity_id not in self._entity_cache:
            return None

        entity, cached_time = self._entity_cache[entity_id]
        cache_ttl = getattr(self.config, 'entity_cache_ttl', 3600)

        if time.time() - cached_time > cache_ttl:
            # Cache expired
            del self._entity_cache[entity_id]
            return None

        return entity

    async def _get_entity_with_cache(self, entity_id: int) -> Optional[Any]:
        """
        Get entity, preferring cache over API call.

        This reduces API calls and avoids rate limiting.

        Args:
            entity_id: Telegram entity ID (can be positive user ID or negative chat ID)

        Returns:
            Entity object or None
        """
        # Try cache first
        cached = await self._get_cached_entity(abs(entity_id))
        if cached:
            return cached

        # Not in cache - fetch from Telegram
        if not self._connected or not self._client:
            return None

        try:
            entity = await self._client.get_entity(entity_id)
            if entity:
                # Add to cache
                self._entity_cache[abs(entity_id)] = (entity, time.time())
            return entity
        except FloodWaitError as e:
            log.warning(f"FloodWaitError getting entity {entity_id}: {e.seconds}s")
            # Auto-sleep handled by flood_sleep_threshold
            raise
        except Exception as e:
            log.debug(f"Failed to get entity {entity_id}: {e}")
            return None

    async def _run_polling_loop(self) -> None:
        """
        Poll monitored chats for new messages.

        This is a fallback mechanism for receiving messages when Telethon's
        event-based system doesn't work (e.g., due to session conflicts).
        """
        log.info("MTProto polling loop starting...")
        print("[MTPROTO] Polling loop started")

        while self._connected:
            try:
                monitored_count = len(self._monitored_chats)

                if monitored_count == 0:
                    pass  # No chats to monitor
                else:
                    for chat_id, last_msg_id in list(self._monitored_chats.items()):
                        await self._poll_chat(chat_id, last_msg_id)
            except Exception as e:
                log.error(f"Error in polling loop: {e}", exc_info=True)

            await asyncio.sleep(self._polling_interval)

        log.info("MTProto polling loop ended (client disconnected)")

    async def _poll_chat(self, chat_id: int, last_msg_id: int) -> None:
        """Poll a single chat for new messages."""
        if not self._connected or not self._client:
            return

        try:
            # Convert to Telegram peer ID format
            peer_id = self._to_telegram_peer_id(chat_id)

            # Try to get entity - may fail if not in cache
            try:
                entity = await self._client.get_entity(peer_id)
            except ValueError as e:
                # Entity not found in cache - try to resolve via dialogs
                if "Could not find the input entity" in str(e):
                    log.warning(f"Entity {peer_id} not in cache, trying to resolve via dialogs...")

                    # Iterate dialogs to populate entity cache
                    found = False
                    async for dialog in self._client.iter_dialogs():
                        if dialog.entity and hasattr(dialog.entity, 'id'):
                            entity_id = dialog.entity.id
                            # Check if this is our target (compare raw ID)
                            if entity_id == chat_id or entity_id == abs(peer_id) or int(f"-100{entity_id}") == peer_id:
                                entity = dialog.entity
                                found = True
                                log.info(f"Found entity {chat_id} via dialogs: {getattr(entity, 'title', 'N/A')}")
                                break

                    if not found:
                        # Still can't find - remove from monitoring to stop spam
                        log.error(f"Cannot resolve entity {chat_id} - removing from polling. "
                                  f"Ensure the MTProto account is a member of this chat.")
                        self.remove_monitored_chat(chat_id)
                        return
                else:
                    raise

            # Fetch messages newer than last_msg_id
            new_messages = []
            async for msg in self._client.iter_messages(entity, min_id=last_msg_id, limit=50):
                # Skip service/action messages (topic created, user joined, etc.)
                if hasattr(msg, 'action') and msg.action:
                    log.debug(f"Skipping service message: action={type(msg.action).__name__}")
                    continue

                # Skip empty messages (no text AND no media)
                has_text = bool(msg.text or msg.message)
                has_media = bool(msg.media)
                if not has_text and not has_media:
                    log.debug(f"Skipping empty message: id={msg.id}")
                    continue

                # Skip bot messages - use cached sender info to avoid extra API calls
                # Note: We DON'T filter out=True because the MTProto session owner
                # may send from their phone and we want those messages in WellWon
                if msg.sender_id:
                    sender = getattr(msg, '_sender', None)
                    if sender is None:
                        # Only fetch sender if not cached
                        try:
                            sender = await msg.get_sender()
                        except Exception:
                            sender = None
                    if sender and getattr(sender, 'bot', False):
                        continue
                else:
                    sender = None
                new_messages.append((msg, sender))

            if not new_messages:
                return

            # Process in chronological order (oldest first)
            new_messages.reverse()

            log.info(f"[POLLING] Found {len(new_messages)} new messages in chat {chat_id}")
            print(f"[MTPROTO] [POLLING] Found {len(new_messages)} new messages in chat {chat_id}")

            for msg, sender in new_messages:
                await self._process_polled_message(msg, sender, chat_id)
                # Update last_msg_id
                if msg.id > self._monitored_chats.get(chat_id, 0):
                    self._monitored_chats[chat_id] = msg.id

        except FloodWaitError as e:
            log.warning(f"[POLLING] Flood wait for chat {chat_id}: {e.seconds}s - will wait")
            await asyncio.sleep(e.seconds + 1)
        except (ChannelPrivateError, ChannelInvalidError) as e:
            # Channel was deleted, we were kicked, or don't have access anymore
            log.warning(f"Channel {chat_id} is no longer accessible, removing from polling: {e}")
            self.remove_monitored_chat(chat_id)
        except Exception as e:
            # Check for common access-related errors in the message
            error_msg = str(e).lower()
            if "private" in error_msg or "banned" in error_msg or "permission" in error_msg:
                log.warning(f"Channel {chat_id} access denied, removing from polling: {e}")
                self.remove_monitored_chat(chat_id)
            else:
                log.error(f"Error polling chat {chat_id}: {e}", exc_info=True)

    async def _process_polled_message(self, msg, sender, chat_id: int) -> None:
        """Process a message obtained via polling."""
        try:
            # Extract topic_id for forum messages
            topic_id = None
            if hasattr(msg, 'reply_to') and msg.reply_to:
                reply_to = msg.reply_to
                is_forum_topic = getattr(reply_to, 'forum_topic', False)
                if is_forum_topic:
                    topic_id = getattr(reply_to, 'reply_to_top_id', None) or getattr(reply_to, 'reply_to_msg_id', None)

            # Get sender info
            sender_id = sender.id if sender else None
            sender_username = getattr(sender, 'username', None)
            sender_first_name = getattr(sender, 'first_name', None)
            sender_last_name = getattr(sender, 'last_name', None)
            sender_is_bot = getattr(sender, 'bot', False) if sender else False

            # Get message text
            text = msg.text or msg.message

            # Get file info if present
            file_id = None
            file_name = None
            file_size = None
            file_type = None
            voice_duration = None

            if msg.media:
                if hasattr(msg.media, 'photo'):
                    file_type = 'photo'
                elif hasattr(msg.media, 'document'):
                    doc = msg.media.document
                    file_size = doc.size if hasattr(doc, 'size') else None
                    for attr in getattr(doc, 'attributes', []):
                        if hasattr(attr, 'file_name'):
                            file_name = attr.file_name
                        if hasattr(attr, 'voice') and attr.voice:
                            file_type = 'voice'
                            voice_duration = getattr(attr, 'duration', None)
                        elif hasattr(attr, 'video') and attr.video:
                            file_type = 'video'
                    if not file_type:
                        file_type = 'document'

            # Use full Telegram chat ID with -100 prefix for supergroups
            full_chat_id = self._to_telegram_peer_id(chat_id)

            incoming_msg = IncomingMessage(
                message_id=msg.id,
                chat_id=full_chat_id,
                topic_id=topic_id,
                sender_id=sender_id,
                sender_username=sender_username,
                sender_first_name=sender_first_name,
                sender_last_name=sender_last_name,
                sender_is_bot=sender_is_bot,
                text=text,
                date=msg.date,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                file_type=file_type,
                voice_duration=voice_duration,
            )

            log.info(
                f"[POLLING] Processing message: chat_id={full_chat_id}, topic_id={topic_id}, "
                f"from={sender_username or sender_id}, text={text[:50] if text else 'N/A'}..."
            )
            print(f"[MTPROTO] [POLLING] Message from {sender_username or sender_id}: {text[:30] if text else '[no text]'}...")

            # Forward to callback if registered
            if self._message_callback:
                await self._message_callback(incoming_msg)
            else:
                log.warning("No message callback registered, incoming message ignored")

        except Exception as e:
            log.error(f"[POLLING] Error processing message: {e}", exc_info=True)

    async def _handle_new_message(self, event) -> None:
        """
        Handle incoming message from Telegram.

        This is called by Telethon for every incoming message.
        We parse it and forward to the registered callback.
        """
        print(f"[MTPROTO] _handle_new_message called! event={type(event)}")
        log.info(f"MTProto _handle_new_message triggered for event: {type(event)}")
        try:
            message = event.message
            print(f"[MTPROTO] Message: id={message.id}, out={message.out}, chat_id={event.chat_id}")

            # Note: We DON'T filter out=True because the MTProto session owner
            # may send from their phone and we want those messages in WellWon

            # Get sender info early to check for bot
            sender = await event.get_sender()
            sender_is_bot = getattr(sender, 'bot', False)

            # Skip messages from bots (avoid echo from our own bot messages)
            if sender_is_bot:
                log.info(f"Skipping message from bot: {getattr(sender, 'username', 'unknown')}")
                return

            # Get chat ID
            chat_id = event.chat_id

            # Get topic ID (message_thread_id in Telegram API terms)
            # In forum groups, messages have reply_to with forum_topic=True
            # Reference: https://stackoverflow.com/questions/79712696
            #
            # Forum topic messages:
            # - reply_to.forum_topic = True
            # - If normal message in topic: topic_id = reply_to.reply_to_msg_id
            # - If reply to another message in topic: topic_id = reply_to.reply_to_top_id
            # - Use: reply_to_top_id OR reply_to_msg_id (whichever is set for the topic)
            topic_id = None
            if hasattr(message, 'reply_to') and message.reply_to:
                reply_to = message.reply_to
                is_forum_topic = getattr(reply_to, 'forum_topic', False)
                reply_to_msg_id = getattr(reply_to, 'reply_to_msg_id', None)
                reply_to_top_id = getattr(reply_to, 'reply_to_top_id', None)

                log.info(f"reply_to: forum_topic={is_forum_topic}, reply_to_msg_id={reply_to_msg_id}, reply_to_top_id={reply_to_top_id}")
                print(f"[MTPROTO] reply_to: forum_topic={is_forum_topic}, msg_id={reply_to_msg_id}, top_id={reply_to_top_id}")

                if is_forum_topic:
                    # For forum messages: use reply_to_top_id if it's a reply,
                    # otherwise use reply_to_msg_id (which is the topic's creation message ID)
                    topic_id = reply_to_top_id or reply_to_msg_id
                    log.info(f"Forum topic message: topic_id={topic_id}")
                    print(f"[MTPROTO] Forum topic detected: topic_id={topic_id}")
            else:
                log.info("Message has no reply_to attribute (likely General topic or non-forum message)")
                print(f"[MTPROTO] No reply_to attribute on message")

            # Get sender info (sender already fetched above for bot check)
            sender_id = sender.id if sender else None
            sender_username = getattr(sender, 'username', None)
            sender_first_name = getattr(sender, 'first_name', None)
            sender_last_name = getattr(sender, 'last_name', None)

            # Get message text
            text = message.text or message.message

            # Get file info if present
            file_id = None
            file_name = None
            file_size = None
            file_type = None
            voice_duration = None

            if message.media:
                if hasattr(message.media, 'photo'):
                    file_type = 'photo'
                elif hasattr(message.media, 'document'):
                    doc = message.media.document
                    file_size = doc.size if hasattr(doc, 'size') else None
                    # Check attributes for type
                    for attr in getattr(doc, 'attributes', []):
                        if hasattr(attr, 'file_name'):
                            file_name = attr.file_name
                        if hasattr(attr, 'voice') and attr.voice:
                            file_type = 'voice'
                            voice_duration = getattr(attr, 'duration', None)
                        elif hasattr(attr, 'video') and attr.video:
                            file_type = 'video'
                    if not file_type:
                        file_type = 'document'
                elif hasattr(message.media, 'voice'):
                    file_type = 'voice'

            incoming_msg = IncomingMessage(
                message_id=message.id,
                chat_id=chat_id,
                topic_id=topic_id,
                sender_id=sender_id,
                sender_username=sender_username,
                sender_first_name=sender_first_name,
                sender_last_name=sender_last_name,
                sender_is_bot=sender_is_bot,
                text=text,
                date=message.date,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                file_type=file_type,
                voice_duration=voice_duration,
            )

            log.info(
                f"MTProto incoming message: chat_id={chat_id}, topic_id={topic_id}, "
                f"from={sender_username or sender_id}, text={text[:50] if text else 'N/A'}..."
            )
            log.info(f"MTProto message details: has_reply_to={hasattr(message, 'reply_to') and message.reply_to is not None}")

            # Forward to callback if registered
            if self._message_callback:
                await self._message_callback(incoming_msg)
            else:
                log.warning("No message callback registered, incoming message ignored")

        except Exception as e:
            log.error(f"Error handling incoming message: {e}", exc_info=True)

    def _to_telegram_peer_id(self, group_id: int) -> int:
        """
        Convert a stored group ID to the full Telegram peer ID format.

        Telegram uses different ID formats:
        - Supergroups/Channels: -100{id} (e.g., -1003327943931)
        - Groups: negative numbers (e.g., -123456789)
        - Users: positive numbers (e.g., 123456789)

        Our database stores just the numeric ID without the -100 prefix.
        Telethon's get_entity() can work with negative IDs that include the prefix.

        Args:
            group_id: Group ID as stored in database (without -100 prefix)

        Returns:
            Full Telegram peer ID (with -100 prefix for supergroups)
        """
        # If already negative, assume it's already in the correct format
        if group_id < 0:
            return group_id

        # For positive IDs, assume they're supergroup IDs and add the -100 prefix
        # Supergroup IDs are typically large positive numbers
        if group_id > 1000000000:  # Supergroup IDs are large
            return -int(f"100{group_id}")

        # For smaller positive IDs, they might be user IDs - return as-is
        return group_id

    # =========================================================================
    # Group Management
    # =========================================================================

    async def create_supergroup(
        self,
        title: str,
        description: str = "",
        forum: bool = True
    ) -> Optional[GroupInfo]:
        """
        Create a new supergroup with optional forum support.

        Args:
            title: Group title
            description: Group description
            forum: Enable forum (topics) support

        Returns:
            GroupInfo if successful, None otherwise
        """
        if not await self._ensure_connected():
            return None

        try:
            # Check if group with this title already exists
            existing = await self._find_group_by_title(title)
            if existing:
                log.info(f"Group '{title}' already exists, returning existing")
                return GroupInfo(
                    group_id=existing.id,
                    title=existing.title,
                    access_hash=getattr(existing, 'access_hash', None)
                )

            result = await self._client(CreateChannelRequest(
                title=title,
                about=description,
                megagroup=True,
                forum=forum
            ))

            group = result.chats[0]
            log.info(f"Supergroup created: {title} (ID: {group.id})")

            return GroupInfo(
                group_id=group.id,
                title=group.title,
                access_hash=group.access_hash
            )

        except Exception as e:
            log.error(f"Failed to create supergroup: {e}", exc_info=True)
            return None

    async def _find_group_by_title(self, title: str):
        """Find existing group by title"""
        try:
            async for dialog in self._client.iter_dialogs():
                entity = dialog.entity
                if getattr(entity, 'megagroup', False) and getattr(entity, 'title', '') == title:
                    return entity
            return None
        except Exception:
            return None

    async def update_group_title(self, group_id: int, new_title: str) -> bool:
        """Update group title"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            await self._client(EditTitleRequest(channel=group, title=new_title))
            log.info(f"Group {group_id} title updated to: {new_title}")
            return True
        except Exception as e:
            log.error(f"Failed to update group title: {e}", exc_info=True)
            return False

    async def update_group_description(self, group_id: int, description: str) -> bool:
        """Update group description"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            await self._client(EditChatAboutRequest(peer=group, about=description))
            log.info(f"Group {group_id} description updated")
            return True
        except Exception as e:
            log.error(f"Failed to update group description: {e}", exc_info=True)
            return False

    async def set_group_photo(self, group_id: int, photo_url: str) -> bool:
        """Set group photo from URL"""
        if not await self._ensure_connected():
            return False

        try:
            import aiohttp
            import tempfile
            import os

            # Download photo
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url) as response:
                    if response.status != 200:
                        log.error(f"Failed to download photo: HTTP {response.status}")
                        return False
                    content = await response.read()

            # Save to temp file and upload
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name

            try:
                group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
                uploaded_file = await self._client.upload_file(tmp_file_path)
                await self._client(EditPhotoRequest(channel=group, photo=uploaded_file))
                log.info(f"Group {group_id} photo set")
                return True
            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

        except Exception as e:
            log.error(f"Failed to set group photo: {e}", exc_info=True)
            return False

    async def set_group_permissions(self, group_id: int) -> bool:
        """Set default group permissions (restrict regular members)"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))

            banned_rights = ChatBannedRights(
                until_date=None,
                view_messages=False,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False,
                send_polls=False,
                change_info=True,  # Restrict
                invite_users=False,
                pin_messages=True,  # Restrict
                manage_topics=False
            )

            await self._client(EditChatDefaultBannedRightsRequest(
                peer=group,
                banned_rights=banned_rights
            ))

            log.info(f"Group {group_id} permissions set")
            return True

        except Exception as e:
            # NOT_MODIFIED errors are normal - group already has these permissions
            if "NOT_MODIFIED" in str(e) or "wasn't modified" in str(e):
                log.debug(f"Group {group_id} permissions already set (no change needed)")
                return True
            log.error(f"Failed to set group permissions: {e}")
            return False

    async def get_invite_link(self, group_id: int) -> Optional[str]:
        """Get group invite link"""
        if not await self._ensure_connected():
            return None

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            invite = await self._client(ExportChatInviteRequest(group.id))
            return invite.link
        except Exception as e:
            log.error(f"Failed to get invite link: {e}", exc_info=True)
            return None

    async def get_group_info(self, group_id: int) -> Optional[GroupInfo]:
        """Get full group information"""
        if not await self._ensure_connected():
            return None

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            invite_link = await self.get_invite_link(group_id)

            return GroupInfo(
                group_id=group.id,
                title=group.title,
                access_hash=getattr(group, 'access_hash', None),
                description=getattr(group, 'about', ''),
                invite_link=invite_link,
                members_count=getattr(group, 'participants_count', 0)
            )
        except Exception as e:
            log.error(f"Failed to get group info: {e}", exc_info=True)
            return None

    # =========================================================================
    # Topic Management
    # =========================================================================

    async def create_forum_topic(
        self,
        group_id: int,
        title: str,
        icon_emoji: Optional[str] = None
    ) -> Optional[TopicInfo]:
        """
        Create a new forum topic.

        Args:
            group_id: Telegram group ID (as stored in DB, without -100 prefix)
            title: Topic title
            icon_emoji: Optional emoji character (will be converted to ID)

        Returns:
            TopicInfo if successful, None otherwise
        """
        if not await self._ensure_connected():
            return None

        try:
            # Convert stored ID to Telegram peer format
            peer_id = self._to_telegram_peer_id(group_id)
            log.debug(f"Converting group_id {group_id} to peer_id {peer_id}")
            group = await self._client.get_entity(peer_id)

            # Convert emoji to ID
            icon_emoji_id = EMOJI_MAP.get(icon_emoji) if icon_emoji else None

            import random
            result = await self._client(CreateForumTopicRequest(
                peer=group,
                title=title,
                icon_emoji_id=icon_emoji_id,
                send_as=None,
                random_id=random.randint(1, 2**63 - 1)
            ))

            # Extract topic_id from result
            topic_id = None
            if hasattr(result, 'updates'):
                for update in result.updates:
                    if hasattr(update, 'id'):
                        topic_id = update.id
                        break
                    elif hasattr(update, 'message') and hasattr(update.message, 'id'):
                        topic_id = update.message.id
                        break
            log.info(f"Topic '{title}' created with ID: {topic_id}")

            return TopicInfo(
                topic_id=topic_id,
                title=title,
                emoji=icon_emoji,
                emoji_id=icon_emoji_id
            )

        except Exception as e:
            log.error(f"Failed to create forum topic: {e}", exc_info=True)
            return None

    async def update_forum_topic(
        self,
        group_id: int,
        topic_id: int,
        new_title: Optional[str] = None,
        new_emoji: Optional[str] = None
    ) -> bool:
        """
        Update forum topic title and/or emoji.

        Args:
            group_id: Telegram group ID
            topic_id: Topic ID to update
            new_title: New title (optional)
            new_emoji: New emoji character (optional)

        Returns:
            True if successful, False otherwise
        """
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))

            # Convert emoji to ID
            icon_emoji_id = EMOJI_MAP.get(new_emoji) if new_emoji else None

            await self._client(EditForumTopicRequest(
                peer=group,
                topic_id=topic_id,
                title=new_title,
                icon_emoji_id=icon_emoji_id
            ))

            log.info(f"Topic {topic_id} updated")
            return True

        except Exception as e:
            # TOPIC_NOT_MODIFIED is normal - topic already has these settings
            if "NOT_MODIFIED" in str(e):
                log.debug(f"Topic {topic_id} already has requested settings (no change needed)")
                return True
            log.error(f"Failed to update forum topic: {e}")
            return False

    async def delete_forum_topic(self, group_id: int, topic_id: int) -> bool:
        """Delete a forum topic"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            await self._client(DeleteTopicHistoryRequest(
                peer=group,
                top_msg_id=topic_id
            ))
            log.info(f"Topic {topic_id} deleted from group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to delete forum topic: {e}", exc_info=True)
            return False

    async def pin_forum_topic(self, group_id: int, topic_id: int, pinned: bool = True) -> bool:
        """Pin or unpin a forum topic"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            await self._client(UpdatePinnedForumTopicRequest(
                peer=group,
                topic_id=topic_id,
                pinned=pinned
            ))
            log.info(f"Topic {topic_id} {'pinned' if pinned else 'unpinned'}")
            return True
        except Exception as e:
            # PINNED_TOPIC_NOT_MODIFIED is normal - topic already in requested state
            if "NOT_MODIFIED" in str(e):
                log.debug(f"Topic {topic_id} already {'pinned' if pinned else 'unpinned'} (no change needed)")
                return True
            log.error(f"Failed to pin/unpin topic: {e}")
            return False

    async def close_forum_topic(self, group_id: int, topic_id: int, closed: bool = True) -> bool:
        """
        Close or reopen a forum topic.

        Closing a topic hides it from the topic list but preserves all messages.
        Users can still find it via search or direct link.

        Args:
            group_id: Telegram group/supergroup ID
            topic_id: Forum topic ID
            closed: True to close, False to reopen

        Returns:
            True if successful
        """
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            await self._client(EditForumTopicRequest(
                peer=group,
                topic_id=topic_id,
                closed=closed
            ))
            log.info(f"Topic {topic_id} {'closed' if closed else 'reopened'} in group {group_id}")
            return True
        except Exception as e:
            # TOPIC_NOT_MODIFIED is normal - topic already in requested state
            if "NOT_MODIFIED" in str(e):
                log.debug(f"Topic {topic_id} already {'closed' if closed else 'open'} (no change needed)")
                return True
            log.error(f"Failed to close/reopen topic {topic_id}: {e}", exc_info=True)
            return False

    async def get_forum_topics(self, group_id: int) -> List[TopicInfo]:
        """Get list of all forum topics"""
        if not await self._ensure_connected():
            return []

        try:
            # Convert to proper channel ID format for Telethon
            # Supergroup IDs need -100 prefix for Telethon to recognize them as channels
            # If positive (e.g., 3327943931), convert to -1003327943931
            # If already negative with -100 prefix, use as-is
            if group_id > 0:
                channel_id = int(f"-100{group_id}")
            else:
                channel_id = group_id
            log.debug(f"get_forum_topics: Converting group_id {group_id} to channel_id {channel_id}")
            group = await self._client.get_entity(channel_id)

            result = await self._client(GetForumTopicsRequest(
                peer=group,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))

            topics = []
            for message in result.messages:
                if hasattr(message, 'action') and hasattr(message.action, 'title'):
                    action = message.action
                    topic_info = TopicInfo(
                        topic_id=message.id,
                        title=action.title,
                        emoji_id=getattr(action, 'icon_emoji_id', None),
                        pinned=getattr(message, 'pinned', False)
                    )
                    topics.append(topic_info)

            return topics

        except Exception as e:
            log.error(f"Failed to get forum topics: {e}", exc_info=True)
            return []

    # =========================================================================
    # Bot Management
    # =========================================================================

    async def add_bot_as_admin(
        self,
        group_id: int,
        bot_username: str,
        title: str = "Bot"
    ) -> bool:
        """
        Add a bot to the group as administrator.

        Args:
            group_id: Telegram group ID
            bot_username: Bot username (without @)
            title: Admin title for the bot

        Returns:
            True if successful, False otherwise
        """
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))

            # Resolve bot username
            resolved = await self._client(ResolveUsernameRequest(bot_username))
            bot_user = resolved.users[0]

            # Invite bot to group
            await self._client(InviteToChannelRequest(
                channel=group.id,
                users=[bot_user.id]
            ))

            await asyncio.sleep(1)  # Wait before promoting

            # Set admin rights
            rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True,
                manage_topics=True,
                post_stories=True,
                edit_stories=True,
                delete_stories=True
            )

            await self._client(EditAdminRequest(
                channel=group.id,
                user_id=bot_user.id,
                admin_rights=rights,
                rank=title
            ))

            log.info(f"Bot @{bot_username} added as admin to group {group_id}")
            return True

        except Exception as e:
            log.error(f"Failed to add bot as admin: {e}", exc_info=True)
            return False

    async def setup_group_bots(self, group_id: int) -> List[Dict[str, Any]]:
        """
        Add all configured bots to the group.

        Returns:
            List of results for each bot
        """
        results = []

        for bot_config in self._bots_config:
            try:
                success = await self.add_bot_as_admin(
                    group_id=group_id,
                    bot_username=bot_config["username"],
                    title=bot_config["title"]
                )
                results.append({
                    "username": bot_config["username"],
                    "title": bot_config["title"],
                    "status": "success" if success else "error"
                })
            except Exception as e:
                results.append({
                    "username": bot_config["username"],
                    "title": bot_config["title"],
                    "status": "error",
                    "reason": str(e)
                })

        return results

    # =========================================================================
    # User Management
    # =========================================================================

    async def invite_user(self, group_id: int, username: str) -> bool:
        """Invite a user to the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            user = await self._client.get_entity(username)
            await self._client(InviteToChannelRequest(channel=group, users=[user]))
            log.info(f"User @{username} invited to group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to invite user: {e}", exc_info=True)
            return False

    async def remove_user(self, group_id: int, username: str) -> bool:
        """Remove a user from the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            user = await self._client.get_entity(username)
            await self._client(EditBannedRequest(
                channel=group,
                participant=user,
                banned_rights=ChatBannedRights(until_date=None, view_messages=True)
            ))
            log.info(f"User @{username} removed from group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to remove user: {e}", exc_info=True)
            return False

    async def get_group_members(self, group_id: int, limit: int = 200) -> List['MemberInfo']:
        """Get all members of a group"""
        if not await self._ensure_connected():
            return []

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            result = await self._client(GetParticipantsRequest(
                channel=group,
                filter=ChannelParticipantsSearch(''),
                offset=0,
                limit=limit,
                hash=0
            ))

            members = []
            for participant in result.users:
                # Determine status from participant type
                status = "member"
                for p in result.participants:
                    if hasattr(p, 'user_id') and p.user_id == participant.id:
                        class_name = type(p).__name__
                        if 'Creator' in class_name:
                            status = "creator"
                        elif 'Admin' in class_name:
                            status = "administrator"
                        elif 'Banned' in class_name:
                            status = "restricted"
                        elif 'Left' in class_name:
                            status = "left"
                        break

                members.append(MemberInfo(
                    user_id=participant.id,
                    username=participant.username,
                    first_name=participant.first_name,
                    last_name=participant.last_name,
                    is_bot=participant.bot if hasattr(participant, 'bot') else False,
                    status=status,
                ))

            log.info(f"Retrieved {len(members)} members from group {group_id}")
            return members

        except Exception as e:
            log.error(f"Failed to get group members: {e}", exc_info=True)
            return []

    async def promote_user(self, group_id: int, user_id: int, admin: bool = True) -> bool:
        """Promote or demote a user in the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            user = await self._client.get_entity(user_id)

            if admin:
                # Promote to administrator
                admin_rights = ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    manage_topics=True,
                )
            else:
                # Demote to regular member (remove admin rights)
                admin_rights = ChatAdminRights()

            await self._client(EditAdminRequest(
                channel=group,
                user_id=user,
                admin_rights=admin_rights,
                rank="Admin" if admin else ""
            ))

            log.info(f"User {user_id} {'promoted' if admin else 'demoted'} in group {group_id}")
            return True

        except Exception as e:
            log.error(f"Failed to update user role: {e}", exc_info=True)
            return False

    async def restrict_user(self, group_id: int, user_id: int, restricted: bool = True) -> bool:
        """Restrict or unrestrict a user in the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(self._to_telegram_peer_id(group_id))
            user = await self._client.get_entity(user_id)

            if restricted:
                # Restrict user (can view but not send)
                banned_rights = ChatBannedRights(
                    until_date=None,
                    send_messages=True,
                    send_media=True,
                    send_stickers=True,
                    send_gifs=True,
                    send_games=True,
                    send_inline=True,
                )
            else:
                # Remove restrictions
                banned_rights = ChatBannedRights()

            await self._client(EditBannedRequest(
                channel=group,
                participant=user,
                banned_rights=banned_rights
            ))

            log.info(f"User {user_id} {'restricted' if restricted else 'unrestricted'} in group {group_id}")
            return True

        except Exception as e:
            log.error(f"Failed to update user restrictions: {e}", exc_info=True)
            return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def get_emoji_id(emoji: str) -> Optional[int]:
        """Get emoji ID from emoji character"""
        return EMOJI_MAP.get(emoji)

    @staticmethod
    def get_available_emojis() -> Dict[str, int]:
        """Get all available emojis with their IDs"""
        return EMOJI_MAP.copy()
