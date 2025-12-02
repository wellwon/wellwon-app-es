# =============================================================================
# File: app/infra/telegram/listener.py
# Description: Event listener that syncs Chat Domain events to Telegram
# =============================================================================
# Architecture:
#   - Subscribes to Chat Domain events via EventBus (RedPanda)
#   - Uses QueryBus for CQRS-compliant data lookups
#   - Uses Message Queue for reliable delivery with retries
#   - Circuit Breaker protects against Telegram API failures
#   - Metrics for observability
# =============================================================================

from __future__ import annotations

import asyncio
from typing import Optional, Any, TYPE_CHECKING
from uuid import UUID

from app.config.logging_config import get_logger
from app.config.reliability_config import CircuitBreakerConfig, RetryConfig
from app.infra.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    get_circuit_breaker,
)
from app.infra.reliability.retry import retry_async, is_permanent, mark_permanent
from app.infra.telegram.adapter import TelegramAdapter, get_telegram_adapter
from app.infra.telegram.message_queue import (
    OutgoingMessage,
    MessagePriority,
    TelegramMessageQueue,
    get_message_queue,
)

# Metrics import (optional)
try:
    from app.infra.metrics.telegram_metrics import (
        telegram_messages_sent_total,
        telegram_group_operations_total,
        record_message_sent,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

if TYPE_CHECKING:
    from app.infra.cqrs.query_bus import QueryBus

log = get_logger("wellwon.telegram.listener")


class TelegramEventListener:
    """
    Listens to Chat Domain events and syncs to Telegram.

    This listener subscribes to domain events and translates them
    to Telegram API calls via the TelegramAdapter.

    Events handled:
    - MessageSent: Web message -> Telegram
    - ChatCreated: Create Telegram topic if configured
    - ChatUpdated: Update topic name/emoji
    - ChatDeleted: (Optional) Archive/close topic

    Architecture:
    - Receives events from EventBus (RedPanda)
    - Uses QueryBus to lookup data (CQRS compliance)
    - Uses Message Queue for reliable delivery
    - Circuit Breaker protects against Telegram failures
    - Retry with exponential backoff for transient errors

    Pattern follows WSEDomainPublisher for consistency.
    """

    # Circuit breaker configuration for Telegram operations
    CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
        name="telegram_listener",
        failure_threshold=5,
        reset_timeout_seconds=60,
        half_open_max_calls=3,
        success_threshold=2,
    )

    # Retry configuration for transient errors
    RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        initial_delay_ms=1000,
        max_delay_ms=10000,
        backoff_factor=2.0,
        jitter=True,
    )

    def __init__(
        self,
        event_bus: Any,
        query_bus: 'QueryBus',
        telegram_adapter: Optional[TelegramAdapter] = None,
        redis_client: Optional[Any] = None,
        use_message_queue: bool = True,
    ):
        """
        Initialize the Telegram Event Listener.

        Args:
            event_bus: EventBus for subscribing to domain events
            query_bus: QueryBus for CQRS-compliant data lookups
            telegram_adapter: Optional pre-configured adapter
            redis_client: Redis client for message queue (optional)
            use_message_queue: Whether to use queue for message delivery
        """
        self._event_bus = event_bus
        self._query_bus = query_bus
        self._telegram: Optional[TelegramAdapter] = telegram_adapter
        self._redis_client = redis_client
        self._use_message_queue = use_message_queue
        self._message_queue: Optional[TelegramMessageQueue] = None

        self._initialized = False
        self._running = False
        self._subscriptions: dict = {}
        self._pending_tasks: set = set()

        # Circuit breaker for Telegram operations
        self._circuit_breaker = get_circuit_breaker(
            self.CIRCUIT_BREAKER_CONFIG.name,
            self.CIRCUIT_BREAKER_CONFIG
        )

    async def start(self) -> None:
        """Start the Telegram Event Listener - subscribe to chat domain events"""
        if self._running:
            log.warning("TelegramEventListener already running")
            return

        log.info("Starting TelegramEventListener...")

        # Initialize telegram adapter if not provided
        if self._telegram is None:
            self._telegram = await get_telegram_adapter()

        # Initialize message queue if Redis is available
        if self._use_message_queue and self._redis_client:
            try:
                self._message_queue = await get_message_queue(self._redis_client)
                log.info("Message queue initialized for reliable delivery")
            except Exception as e:
                log.warning(f"Message queue not available, using direct send: {e}")
                self._message_queue = None

        self._initialized = True
        self._running = True

        try:
            await self._subscribe_to_chat_events()
            log.info(
                f"TelegramEventListener ready - "
                f"{len(self._subscriptions)} subscriptions active, "
                f"queue={'enabled' if self._message_queue else 'disabled'}, "
                f"circuit_breaker={self._circuit_breaker.get_state_sync()}"
            )
        except Exception as e:
            log.error(f"Failed to start TelegramEventListener: {e}", exc_info=True)
            self._running = False
            raise

    async def _subscribe_to_chat_events(self) -> None:
        """Subscribe to chat domain events for Telegram forwarding"""
        if not self._running:
            return

        import os
        topic = "transport.chat-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_chat_event,
                group="telegram-event-listener",
                consumer=f"telegram-listener-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::telegram-event-listener"
            log.info(f"Subscribed to {topic} for Telegram forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _handle_chat_event(self, event: dict) -> None:
        """Route chat domain events to appropriate handlers"""
        event_type = event.get("event_type", "")

        handler_map = {
            "MessageSent": self.on_message_sent,
            "MessageDeleted": self.on_message_deleted,
            "MessagesMarkedAsRead": self.on_messages_marked_as_read,  # Web -> Telegram read sync
            "ChatCreated": self.on_chat_created,
            "ChatUpdated": self.on_chat_updated,
            "ChatArchived": self.on_chat_archived,
            "ChatHardDeleted": self.on_chat_deleted,  # Hard delete with Telegram topic removal
        }

        handler = handler_map.get(event_type)
        if handler:
            await handler(event)
        else:
            log.debug(f"No Telegram handler for event type: {event_type}")

    async def stop(self) -> None:
        """Stop the Telegram Event Listener gracefully"""
        if not self._running:
            return

        log.info("Stopping TelegramEventListener...")
        self._running = False

        # Wait for pending tasks to complete (with timeout)
        if self._pending_tasks:
            log.info(f"Waiting for {len(self._pending_tasks)} pending tasks...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._pending_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                log.warning("Timeout waiting for pending tasks, cancelling...")
                for task in self._pending_tasks:
                    task.cancel()

        self._subscriptions.clear()
        self._pending_tasks.clear()

        # Log circuit breaker state on shutdown
        cb_state = await self._circuit_breaker.get_state()
        log.info(
            f"TelegramEventListener stopped. "
            f"Circuit breaker final state: {cb_state}"
        )

    # =========================================================================
    # Reliable Send Methods (Circuit Breaker + Queue + Retry)
    # =========================================================================

    async def _send_message_reliable(
        self,
        telegram_chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        file_url: Optional[str] = None,
        file_type: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """
        Send message to Telegram with reliability features.

        Uses:
        1. Message Queue (if available) for persistence
        2. Circuit Breaker to prevent cascade failures
        3. Retry with exponential backoff for transient errors

        Args:
            telegram_chat_id: Target chat ID
            text: Message text (HTML formatted)
            topic_id: Forum topic ID (optional)
            file_url: File URL for media messages (optional)
            file_type: File type (photo, document, voice)
            priority: Message priority for queue ordering
            correlation_id: Tracing correlation ID

        Returns:
            True if message was sent or queued successfully
        """
        # If message queue is available, enqueue for reliable delivery
        if self._message_queue:
            return await self._enqueue_message(
                telegram_chat_id=telegram_chat_id,
                text=text,
                topic_id=topic_id,
                file_url=file_url,
                file_type=file_type,
                priority=priority,
                correlation_id=correlation_id,
            )

        # Otherwise, send directly with circuit breaker and retry
        return await self._send_direct_with_protection(
            telegram_chat_id=telegram_chat_id,
            text=text,
            topic_id=topic_id,
            file_url=file_url,
            file_type=file_type,
        )

    async def _enqueue_message(
        self,
        telegram_chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        file_url: Optional[str] = None,
        file_type: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Enqueue message for reliable async delivery."""
        message = OutgoingMessage(
            chat_id=telegram_chat_id,
            topic_id=topic_id,
            text=text,
            file_url=file_url,
            file_type=file_type,
            priority=priority,
            correlation_id=correlation_id,
            source_domain="chat",
        )

        try:
            success = await self._message_queue.enqueue(message)
            if success:
                log.debug(f"Message {message.message_id} enqueued for delivery")
            return success
        except Exception as e:
            log.error(f"Failed to enqueue message: {e}")
            # Fallback to direct send
            return await self._send_direct_with_protection(
                telegram_chat_id=telegram_chat_id,
                text=text,
                topic_id=topic_id,
                file_url=file_url,
                file_type=file_type,
            )

    async def _send_direct_with_protection(
        self,
        telegram_chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        file_url: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> bool:
        """
        Send message directly with circuit breaker and retry.

        Used when message queue is not available or as fallback.
        """
        # Check circuit breaker before attempting
        if not self._circuit_breaker.can_execute():
            log.warning(
                f"Circuit breaker OPEN, skipping message to chat {telegram_chat_id}"
            )
            if METRICS_AVAILABLE:
                record_message_sent(file_type or "text", success=False)
            return False

        try:
            # Execute with retry
            result = await retry_async(
                self._do_send,
                telegram_chat_id,
                text,
                topic_id,
                file_url,
                file_type,
                retry_config=self.RETRY_CONFIG,
                context=f"telegram_send_{telegram_chat_id}",
            )

            # Record success
            self._circuit_breaker.record_success()
            if METRICS_AVAILABLE:
                record_message_sent(file_type or "text", success=True)

            return result

        except CircuitBreakerOpenError:
            log.warning(f"Circuit breaker tripped for chat {telegram_chat_id}")
            if METRICS_AVAILABLE:
                record_message_sent(file_type or "text", success=False)
            return False

        except Exception as e:
            # Record failure for circuit breaker
            self._circuit_breaker.record_failure(str(e))
            if METRICS_AVAILABLE:
                record_message_sent(file_type or "text", success=False)

            # Check if permanent error (shouldn't retry)
            if self._is_permanent_error(e):
                log.error(f"Permanent error sending to {telegram_chat_id}: {e}")
            else:
                log.warning(f"Transient error sending to {telegram_chat_id}: {e}")

            return False

    async def _do_send(
        self,
        telegram_chat_id: int,
        text: str,
        topic_id: Optional[int],
        file_url: Optional[str],
        file_type: Optional[str],
    ) -> bool:
        """Actually send the message via adapter."""
        if not self._telegram:
            raise RuntimeError("Telegram adapter not available")

        if file_url and file_type in ("photo", "image"):
            result = await self._telegram.send_file(
                chat_id=telegram_chat_id,
                file_url=file_url,
                caption=text if text else None,
                topic_id=topic_id
            )
        elif file_url and file_type == "voice":
            result = await self._telegram.send_voice(
                chat_id=telegram_chat_id,
                voice_url=file_url,
                caption=text if text else None,
                topic_id=topic_id
            )
        elif file_url:
            result = await self._telegram.send_file(
                chat_id=telegram_chat_id,
                file_url=file_url,
                caption=text if text else None,
                topic_id=topic_id
            )
        else:
            result = await self._telegram.send_message(
                chat_id=telegram_chat_id,
                text=text,
                topic_id=topic_id
            )

        if not result.success:
            # Check if permanent error
            if result.error and self._is_permanent_error_str(result.error):
                raise mark_permanent(RuntimeError(result.error))
            raise RuntimeError(result.error or "Unknown send error")

        return True

    def _is_permanent_error(self, error: Exception) -> bool:
        """Check if error is permanent (should not retry)."""
        if is_permanent(error):
            return True
        return self._is_permanent_error_str(str(error))

    def _is_permanent_error_str(self, error_str: str) -> bool:
        """Check if error string indicates permanent failure."""
        error_lower = error_str.lower()
        permanent_indicators = [
            "chat not found",
            "bot was blocked",
            "user is deactivated",
            "chat_write_forbidden",
            "need administrator rights",
            "message is too long",
            "wrong file identifier",
            "topic_closed",
            "topic_deleted",
        ]
        return any(ind in error_lower for ind in permanent_indicators)

    async def _execute_mtproto_with_protection(
        self,
        operation_name: str,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute MTProto operation with circuit breaker and retry protection.

        Args:
            operation_name: Name for logging and metrics
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result of the function or None on failure
        """
        if not self._circuit_breaker.can_execute():
            log.warning(f"Circuit breaker OPEN, skipping {operation_name}")
            if METRICS_AVAILABLE:
                telegram_group_operations_total.labels(
                    operation=operation_name, status="circuit_open"
                ).inc()
            return None

        try:
            result = await retry_async(
                func,
                *args,
                retry_config=self.RETRY_CONFIG,
                context=operation_name,
                **kwargs,
            )

            self._circuit_breaker.record_success()
            if METRICS_AVAILABLE:
                telegram_group_operations_total.labels(
                    operation=operation_name, status="success"
                ).inc()

            return result

        except Exception as e:
            self._circuit_breaker.record_failure(str(e))
            if METRICS_AVAILABLE:
                telegram_group_operations_total.labels(
                    operation=operation_name, status="error"
                ).inc()

            log.error(f"MTProto operation {operation_name} failed: {e}")
            return None

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def on_message_sent(self, event: dict) -> None:
        """
        Handle MessageSent event - send message to Telegram.

        Event payload:
        {
            "chat_id": UUID,
            "message_id": UUID,
            "sender_id": UUID,
            "content": str,
            "message_type": str,  # text, photo, document, voice
            "file_url": Optional[str],
            "source": str,  # web, telegram, api
            "metadata": dict
        }
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        # Skip messages that came FROM Telegram (avoid echo)
        # Also skip messages from web - SendMessageHandler already syncs those to Telegram
        source = event.get("source", "web")
        if source == "telegram":
            log.debug(f"Skipping message {event.get('message_id')} - already from Telegram")
            return
        if source == "web":
            log.debug(f"Skipping message {event.get('message_id')} - web messages synced by SendMessageHandler")
            return

        try:
            chat_id = event.get("chat_id")
            content = event.get("content", "")
            file_url = event.get("file_url")
            message_type = event.get("message_type", "text")
            sender_id = event.get("sender_id")

            # Lookup sender name via QueryBus (CQRS compliant)
            sender_name = "Unknown"
            if sender_id:
                try:
                    from app.user_account.queries import GetUserProfileQuery
                    user = await self._query_bus.query(
                        GetUserProfileQuery(
                            user_id=UUID(sender_id) if isinstance(sender_id, str) else sender_id,
                            include_preferences=False,
                            include_security_settings=False
                        )
                    )
                    if user:
                        first = getattr(user, 'first_name', '') or ''
                        last = getattr(user, 'last_name', '') or ''
                        username = getattr(user, 'username', '') or ''
                        sender_name = f"{first} {last}".strip() or username or "Unknown"
                except Exception as e:
                    log.warning(f"Failed to lookup sender {sender_id}: {e}")

            # Get chat configuration via QueryBus (CQRS compliant)
            from app.chat.queries import GetChatByIdQuery
            chat = await self._query_bus.query(
                GetChatByIdQuery(
                    chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                )
            )

            if not chat:
                log.debug(f"Chat {chat_id} not found")
                return

            # Check if chat has Telegram integration
            telegram_chat_id = getattr(chat, 'telegram_chat_id', None)
            if not telegram_chat_id:
                log.debug(f"Chat {chat_id} has no Telegram integration")
                return

            # Get Telegram identifiers
            topic_id = getattr(chat, 'telegram_topic_id', None)

            # Format message with sender name
            formatted_content = f"<b>{sender_name}</b>\n{content}"

            # Determine file type for reliable send
            file_type = None
            if file_url:
                if message_type in ("photo", "image"):
                    file_type = "photo"
                elif message_type == "voice":
                    file_type = "voice"
                else:
                    file_type = "document"

            # Send via reliable method (with queue, circuit breaker, retry)
            success = await self._send_message_reliable(
                telegram_chat_id=telegram_chat_id,
                text=formatted_content,
                topic_id=topic_id,
                file_url=file_url,
                file_type=file_type,
                priority=MessagePriority.NORMAL,
                correlation_id=str(event.get("message_id", "")),
            )

            if success:
                log.debug(f"Message {event.get('message_id')} sent/queued for Telegram")
            else:
                log.warning(f"Message {event.get('message_id')} failed to send to Telegram")

        except Exception as e:
            log.error(f"Error handling MessageSent event: {e}", exc_info=True)

    async def on_message_deleted(self, event: dict) -> None:
        """
        Handle MessageDeleted event - delete message in Telegram.

        Event payload:
        {
            "message_id": UUID,
            "chat_id": UUID,
            "deleted_by": UUID,
            "telegram_message_id": Optional[int],
            "telegram_chat_id": Optional[int]
        }
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        try:
            telegram_message_id = event.get("telegram_message_id")
            telegram_chat_id = event.get("telegram_chat_id")

            # If telegram IDs are not in the event, try to look up from chat/message
            if not telegram_message_id or not telegram_chat_id:
                message_id = event.get("message_id")
                chat_id = event.get("chat_id")

                # Lookup chat to get telegram_chat_id
                if chat_id and not telegram_chat_id:
                    from app.chat.queries import GetChatByIdQuery
                    chat = await self._query_bus.query(
                        GetChatByIdQuery(
                            chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                        )
                    )
                    if chat:
                        telegram_chat_id = getattr(chat, 'telegram_chat_id', None) or getattr(chat, 'telegram_supergroup_id', None)

                # Without telegram_message_id, we cannot delete the message in Telegram
                if not telegram_message_id:
                    log.debug(
                        f"No telegram_message_id for message {message_id}, cannot sync deletion to Telegram"
                    )
                    return

            if not telegram_chat_id:
                log.debug(f"No telegram_chat_id available, cannot sync deletion to Telegram")
                return

            # Delete message in Telegram
            success = await self._telegram.delete_message(
                chat_id=telegram_chat_id,
                message_id=telegram_message_id
            )

            if success:
                log.info(
                    f"Deleted Telegram message {telegram_message_id} in chat {telegram_chat_id}"
                )
            else:
                log.warning(
                    f"Failed to delete Telegram message {telegram_message_id} in chat {telegram_chat_id}"
                )

        except Exception as e:
            log.error(f"Error handling MessageDeleted event: {e}", exc_info=True)

    async def on_messages_marked_as_read(self, event: dict) -> None:
        """
        Handle MessagesMarkedAsRead event - sync read status to Telegram.

        When user reads messages on WellWon (web), we mark them as read on Telegram too.
        This enables bidirectional read sync:
        - WellWon -> Telegram: This handler
        - Telegram -> WellWon: incoming_handler.handle_read_event

        Event payload (now includes Telegram data from aggregate):
        {
            "chat_id": UUID,
            "user_id": UUID,
            "last_read_message_id": int (Snowflake ID),
            "read_count": int,
            "read_at": datetime,
            "source": str,  # 'web' or 'telegram'
            "telegram_message_id": int | None,  # For sync (from command)
            "telegram_chat_id": int | None,     # From aggregate state
            "telegram_topic_id": int | None,    # From aggregate state
        }
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping read sync")
            return

        # CRITICAL: Only sync reads from WEB to Telegram
        # If source is 'telegram', the read already came from Telegram - don't loop back
        source = event.get("source", "web")
        if source == "telegram":
            log.debug("Skipping read sync - already from Telegram")
            return

        try:
            chat_id = event.get("chat_id")
            if not chat_id:
                log.debug("No chat_id in MessagesMarkedAsRead event")
                return

            # Get Telegram data directly from event (no query needed!)
            telegram_chat_id = event.get("telegram_chat_id")
            telegram_topic_id = event.get("telegram_topic_id")
            telegram_message_id = event.get("telegram_message_id")

            if not telegram_chat_id:
                log.debug(f"Chat {chat_id} not linked to Telegram, skipping read sync")
                return

            if not telegram_message_id:
                log.debug(f"No telegram_message_id in event, skipping Telegram sync")
                return

            log.info(
                f"Syncing read status to Telegram: chat_id={telegram_chat_id}, "
                f"topic_id={telegram_topic_id}, max_id={telegram_message_id}"
            )

            if telegram_topic_id:
                # Forum topic - use topic-specific read method
                success = await self._telegram.mark_topic_messages_read(
                    group_id=telegram_chat_id,
                    topic_id=telegram_topic_id,
                    max_id=telegram_message_id
                )
            else:
                # Regular chat/group
                success = await self._telegram.mark_messages_read(
                    chat_id=telegram_chat_id,
                    max_id=telegram_message_id
                )

            if success:
                log.info(
                    f"Synced read status to Telegram: chat={telegram_chat_id}, "
                    f"topic={telegram_topic_id}, max_id={telegram_message_id}"
                )
            else:
                log.warning(
                    f"Failed to sync read status to Telegram: chat={telegram_chat_id}"
                )

        except Exception as e:
            log.error(f"Error handling MessagesMarkedAsRead event: {e}", exc_info=True)

    async def _get_telegram_message_id(
        self,
        chat_id: UUID,
        message_id: int,  # Snowflake ID
    ) -> Optional[int]:
        """
        Look up the telegram_message_id via QueryBus.

        Args:
            chat_id: WellWon chat UUID
            message_id: Snowflake ID of the message

        Returns:
            Telegram message ID if found, None otherwise
        """
        try:
            from app.chat.queries import GetMessageByIdQuery

            message = await self._query_bus.query(
                GetMessageByIdQuery(chat_id=chat_id, snowflake_id=message_id)
            )

            if message:
                return getattr(message, 'telegram_message_id', None)

            return None

        except Exception as e:
            log.debug(f"Could not lookup telegram_message_id: {e}")
            return None

    async def on_chat_created(self, event: dict) -> None:
        """
        Handle ChatCreated event - optionally create Telegram topic.

        Event payload:
        {
            "chat_id": UUID,
            "chat_name": str,
            "company_id": UUID,
            "create_telegram_topic": bool,
            "telegram_group_id": Optional[int],
            "topic_emoji": Optional[str]
        }
        """
        if not self._initialized or not self._telegram:
            return

        try:
            # Check if we should create a Telegram topic
            if not event.get("create_telegram_topic"):
                return

            telegram_group_id = event.get("telegram_group_id")
            if not telegram_group_id:
                log.warning("No telegram_group_id provided for topic creation")
                return

            chat_name = event.get("chat_name", "New Chat")
            topic_emoji = event.get("topic_emoji")

            # Create topic in Telegram with circuit breaker protection
            topic = await self._execute_mtproto_with_protection(
                "create_topic",
                self._telegram.create_chat_topic,
                group_id=telegram_group_id,
                topic_name=chat_name,
                emoji=topic_emoji
            )

            if topic:
                log.info(f"Created Telegram topic {topic.topic_id} for chat {event.get('chat_id')}")

                # TODO: Update chat with external_topic_id via Command Bus
                # command = UpdateChatExternalChannelCommand(
                #     chat_id=event["chat_id"],
                #     external_channel_type="telegram",
                #     external_channel_id=str(telegram_group_id),
                #     external_topic_id=str(topic.topic_id)
                # )
                # await command_bus.dispatch(command)
            else:
                log.error(f"Failed to create Telegram topic for chat {event.get('chat_id')}")

        except Exception as e:
            log.error(f"Error handling ChatCreated event: {e}", exc_info=True)

    async def on_chat_updated(self, event: dict) -> None:
        """
        Handle ChatUpdated event - update Telegram topic if needed.

        Event payload:
        {
            "chat_id": UUID,
            "name": Optional[str],
            "updated_by": UUID
        }
        """
        if not self._initialized or not self._telegram:
            return

        try:
            chat_id = event.get("chat_id")
            new_name = event.get("name")

            if not new_name:
                log.debug(f"ChatUpdated event has no name change, skipping Telegram sync")
                return

            # Fetch chat details to get Telegram integration info
            from app.chat.queries import GetChatByIdQuery
            chat = await self._query_bus.query(
                GetChatByIdQuery(
                    chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                )
            )

            if not chat:
                log.debug(f"Chat {chat_id} not found")
                return

            # Check if chat has Telegram integration
            telegram_chat_id = getattr(chat, 'telegram_chat_id', None)
            telegram_topic_id = getattr(chat, 'telegram_topic_id', None)

            if not telegram_chat_id or not telegram_topic_id:
                log.debug(f"Chat {chat_id} has no Telegram topic integration")
                return

            # Topic ID 1 (General) cannot be renamed
            if telegram_topic_id == 1:
                log.info("Cannot rename General topic (ID 1), skipping Telegram sync")
                return

            log.info(f"Syncing chat name to Telegram: chat_id={chat_id}, name={new_name}, topic_id={telegram_topic_id}")

            # Update topic with circuit breaker protection
            success = await self._execute_mtproto_with_protection(
                "update_topic",
                self._telegram.update_chat_topic,
                group_id=telegram_chat_id,
                topic_id=telegram_topic_id,
                new_name=new_name,
                new_emoji=None
            )

            if success:
                log.info(f"Updated Telegram topic {telegram_topic_id} with name '{new_name}'")
            else:
                log.error(f"Failed to update Telegram topic {telegram_topic_id}")

        except Exception as e:
            log.error(f"Error handling ChatUpdated event: {e}", exc_info=True)

    async def on_chat_archived(self, event: dict) -> None:
        """
        Handle ChatArchived event - close/archive Telegram topic.

        Event payload:
        {
            "chat_id": UUID,
            "archived_by": UUID,
            "telegram_supergroup_id": Optional[int],
            "telegram_topic_id": Optional[int]
        }

        Note: Telegram topics cannot be truly deleted, only closed.
        Closing a topic hides it from the topic list but preserves messages.
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        try:
            telegram_supergroup_id = event.get("telegram_supergroup_id")
            telegram_topic_id = event.get("telegram_topic_id")

            if not telegram_supergroup_id or not telegram_topic_id:
                log.debug(
                    f"Chat {event.get('chat_id')} has no Telegram integration, skipping archive sync"
                )
                return

            # Topic ID 1 (General) cannot be closed
            if telegram_topic_id == 1:
                log.info("Cannot close General topic (ID 1), skipping Telegram sync")
                return

            # Close the topic in Telegram with circuit breaker protection
            if self._telegram.mtproto_client:
                success = await self._execute_mtproto_with_protection(
                    "close_topic",
                    self._telegram.close_topic,
                    group_id=telegram_supergroup_id,
                    topic_id=telegram_topic_id,
                    closed=True
                )

                if success:
                    log.info(
                        f"Closed Telegram topic {telegram_topic_id} in group {telegram_supergroup_id}"
                    )
                else:
                    log.warning(
                        f"Failed to close Telegram topic {telegram_topic_id}"
                    )
            else:
                log.debug("MTProto client not available for topic close")

        except Exception as e:
            log.error(f"Error handling ChatArchived event: {e}", exc_info=True)

    async def on_chat_deleted(self, event: dict) -> None:
        """
        Handle ChatHardDeleted event - delete Telegram topic.

        Event payload from ChatHardDeleted:
        {
            "chat_id": UUID,
            "deleted_by": UUID,
            "reason": Optional[str],
            "telegram_supergroup_id": Optional[int],
            "telegram_topic_id": Optional[int]
        }

        Note: This actually deletes the topic and its message history.
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping chat delete event")
            return

        try:
            telegram_supergroup_id = event.get("telegram_supergroup_id")
            telegram_topic_id = event.get("telegram_topic_id")

            if not telegram_supergroup_id or not telegram_topic_id:
                log.debug(
                    f"Chat {event.get('chat_id')} has no Telegram integration, skipping delete sync"
                )
                return

            # Topic ID 1 (General) cannot be deleted
            if telegram_topic_id == 1:
                log.info("Cannot delete General topic (ID 1), skipping Telegram sync")
                return

            # Delete the topic and its history with circuit breaker protection
            if self._telegram.mtproto_client:
                success = await self._execute_mtproto_with_protection(
                    "delete_topic",
                    self._telegram.delete_chat_topic,
                    group_id=telegram_supergroup_id,
                    topic_id=telegram_topic_id
                )

                if success:
                    log.info(
                        f"Deleted Telegram topic {telegram_topic_id} in group {telegram_supergroup_id}"
                    )
                else:
                    log.warning(f"Failed to delete Telegram topic {telegram_topic_id}")
            else:
                log.debug("MTProto client not available for topic deletion")

        except Exception as e:
            log.error(f"Error handling ChatDeleted event: {e}", exc_info=True)


# =============================================================================
# Factory Function for Startup
# =============================================================================

async def create_telegram_event_listener(
    event_bus: Any,
    query_bus: 'QueryBus',
    redis_client: Optional[Any] = None,
    use_message_queue: bool = True,
) -> TelegramEventListener:
    """
    Factory function to create and start a TelegramEventListener.

    This creates a production-ready listener with:
    - Message Queue for reliable delivery (if Redis available)
    - Circuit Breaker for failure protection
    - Retry with exponential backoff
    - Metrics for observability

    Usage in startup:
        listener = await create_telegram_event_listener(
            event_bus=app.state.event_bus,
            query_bus=app.state.query_bus,
            redis_client=app.state.redis,
            use_message_queue=True,
        )
        app.state.telegram_event_listener = listener

    Args:
        event_bus: EventBus for subscribing to domain events
        query_bus: QueryBus for CQRS-compliant data lookups
        redis_client: Redis client for message queue (optional)
        use_message_queue: Whether to use queue for reliable delivery

    Returns:
        Started TelegramEventListener instance
    """
    listener = TelegramEventListener(
        event_bus=event_bus,
        query_bus=query_bus,
        redis_client=redis_client,
        use_message_queue=use_message_queue,
    )
    await listener.start()
    return listener
