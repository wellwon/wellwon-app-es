# =============================================================================
# File: app/infra/telegram/message_queue.py
# Description: Outgoing message queue for Telegram with retry and DLQ
# =============================================================================
# Best practice: Queue outgoing messages instead of sending directly.
# This provides:
#   - Reliability (messages survive crashes)
#   - Rate limiting compliance
#   - Retry with exponential backoff
#   - Dead letter queue for failures
#   - Metrics and monitoring
# =============================================================================

from __future__ import annotations

import asyncio
import json
import time
from uuid import UUID
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable

from app.config.logging_config import get_logger
from app.config.telegram_config import get_telegram_config
from app.utils.uuid_utils import generate_uuid_str

log = get_logger("wellwon.telegram.message_queue")


class MessagePriority(str, Enum):
    """Message priority levels"""
    HIGH = "high"      # System messages, errors
    NORMAL = "normal"  # Regular messages
    LOW = "low"        # Bulk, notifications


class MessageStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    DLQ = "dlq"  # Dead letter queue


@dataclass
class OutgoingMessage:
    """
    Outgoing Telegram message envelope.

    Contains all information needed to send a message to Telegram.
    """
    # Message identification
    message_id: str = field(default_factory=generate_uuid_str)
    created_at: float = field(default_factory=time.time)

    # Telegram destination
    chat_id: int = 0
    topic_id: Optional[int] = None

    # Message content
    text: str = ""
    parse_mode: Optional[str] = "HTML"

    # File attachment (optional)
    file_url: Optional[str] = None
    file_type: Optional[str] = None  # photo, document, voice, video

    # Reply (optional)
    reply_to_message_id: Optional[int] = None

    # Queue metadata
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    last_attempt_at: Optional[float] = None
    last_error: Optional[str] = None
    next_retry_at: Optional[float] = None

    # Tracking
    source_domain: Optional[str] = None  # chat, notification, etc.
    correlation_id: Optional[str] = None  # For tracing

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutgoingMessage':
        """Create from dictionary."""
        # Convert enums from strings
        if 'priority' in data and isinstance(data['priority'], str):
            data['priority'] = MessagePriority(data['priority'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = MessageStatus(data['status'])
        return cls(**data)

    def calculate_next_retry(self, base_delay: float = 1.0, max_delay: float = 300.0) -> float:
        """Calculate next retry time with exponential backoff."""
        delay = min(base_delay * (2 ** self.attempts), max_delay)
        # Add jitter (0-25% of delay)
        import random
        jitter = random.uniform(0, delay * 0.25)
        return time.time() + delay + jitter


class TelegramMessageQueue:
    """
    Redis-backed message queue for outgoing Telegram messages.

    Features:
    - Priority queues (high/normal/low)
    - Retry with exponential backoff
    - Dead letter queue for permanent failures
    - Rate limiting awareness
    - Metrics integration

    Usage:
        queue = TelegramMessageQueue(redis_client)
        await queue.enqueue(OutgoingMessage(chat_id=123, text="Hello"))

        # In worker:
        async for message in queue.dequeue():
            result = await send_to_telegram(message)
            if result.success:
                await queue.ack(message)
            else:
                await queue.nack(message, error=result.error)
    """

    # Redis key prefixes
    QUEUE_PREFIX = "tg:outbox"
    DLQ_PREFIX = "tg:dlq"
    PROCESSING_PREFIX = "tg:processing"
    STATS_PREFIX = "tg:stats"

    def __init__(
        self,
        redis_client,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 300.0,
        processing_timeout: int = 60,
    ):
        """
        Initialize message queue.

        Args:
            redis_client: Async Redis client
            max_retries: Maximum retry attempts before DLQ
            base_retry_delay: Initial retry delay (seconds)
            max_retry_delay: Maximum retry delay (seconds)
            processing_timeout: Timeout for processing a message (seconds)
        """
        self._redis = redis_client
        self._max_retries = max_retries
        self._base_retry_delay = base_retry_delay
        self._max_retry_delay = max_retry_delay
        self._processing_timeout = processing_timeout

    def _queue_key(self, priority: MessagePriority) -> str:
        """Get Redis key for priority queue."""
        return f"{self.QUEUE_PREFIX}:{priority.value}"

    def _processing_key(self, message_id: str) -> str:
        """Get Redis key for processing message."""
        return f"{self.PROCESSING_PREFIX}:{message_id}"

    def _dlq_key(self) -> str:
        """Get Redis key for dead letter queue."""
        return self.DLQ_PREFIX

    async def enqueue(self, message: OutgoingMessage) -> bool:
        """
        Add message to the outgoing queue.

        Args:
            message: OutgoingMessage to send

        Returns:
            True if enqueued successfully
        """
        try:
            message.status = MessageStatus.PENDING
            queue_key = self._queue_key(message.priority)

            # Use sorted set with score = created_at for ordering
            score = message.created_at
            await self._redis.zadd(
                queue_key,
                {json.dumps(message.to_dict()): score}
            )

            # Update stats
            await self._redis.hincrby(f"{self.STATS_PREFIX}:enqueued", message.priority.value, 1)

            log.debug(f"Enqueued message {message.message_id} to {queue_key}")
            return True

        except Exception as e:
            log.error(f"Failed to enqueue message: {e}")
            return False

    async def dequeue(
        self,
        priorities: Optional[List[MessagePriority]] = None,
        batch_size: int = 1
    ) -> List[OutgoingMessage]:
        """
        Dequeue messages for processing.

        Args:
            priorities: Priority order to check (default: HIGH, NORMAL, LOW)
            batch_size: Number of messages to dequeue

        Returns:
            List of OutgoingMessage to process
        """
        if priorities is None:
            priorities = [MessagePriority.HIGH, MessagePriority.NORMAL, MessagePriority.LOW]

        messages = []
        now = time.time()

        for priority in priorities:
            if len(messages) >= batch_size:
                break

            queue_key = self._queue_key(priority)

            # Get oldest messages (lowest score)
            remaining = batch_size - len(messages)
            items = await self._redis.zrange(
                queue_key, 0, remaining - 1,
                withscores=True
            )

            for item, score in items:
                try:
                    data = json.loads(item)
                    msg = OutgoingMessage.from_dict(data)

                    # Check if message is ready for retry
                    if msg.next_retry_at and msg.next_retry_at > now:
                        continue

                    # Move to processing
                    await self._redis.zrem(queue_key, item)
                    msg.status = MessageStatus.PROCESSING
                    msg.last_attempt_at = now
                    msg.attempts += 1

                    # Store in processing set with timeout
                    await self._redis.setex(
                        self._processing_key(msg.message_id),
                        self._processing_timeout,
                        json.dumps(msg.to_dict())
                    )

                    messages.append(msg)

                except Exception as e:
                    log.error(f"Error parsing queued message: {e}")
                    # Remove corrupted message
                    await self._redis.zrem(queue_key, item)

        return messages

    async def ack(self, message: OutgoingMessage) -> None:
        """
        Acknowledge successful message delivery.

        Args:
            message: Successfully sent message
        """
        # Remove from processing
        await self._redis.delete(self._processing_key(message.message_id))

        # Update stats
        await self._redis.hincrby(f"{self.STATS_PREFIX}:sent", message.priority.value, 1)

        log.debug(f"Acked message {message.message_id}")

    async def nack(
        self,
        message: OutgoingMessage,
        error: str,
        permanent: bool = False
    ) -> None:
        """
        Negative acknowledge - message delivery failed.

        Args:
            message: Failed message
            error: Error description
            permanent: If True, send directly to DLQ without retry
        """
        # Remove from processing
        await self._redis.delete(self._processing_key(message.message_id))

        message.last_error = error
        message.status = MessageStatus.FAILED

        # Check if should retry
        if not permanent and message.attempts < self._max_retries:
            # Calculate next retry time
            message.next_retry_at = message.calculate_next_retry(
                self._base_retry_delay,
                self._max_retry_delay
            )
            message.status = MessageStatus.PENDING

            # Re-queue with delay
            queue_key = self._queue_key(message.priority)
            await self._redis.zadd(
                queue_key,
                {json.dumps(message.to_dict()): message.next_retry_at}
            )

            log.warning(
                f"Message {message.message_id} failed (attempt {message.attempts}), "
                f"retry at {datetime.fromtimestamp(message.next_retry_at)}: {error}"
            )
        else:
            # Move to DLQ
            await self._move_to_dlq(message)

    async def _move_to_dlq(self, message: OutgoingMessage) -> None:
        """Move message to dead letter queue."""
        message.status = MessageStatus.DLQ

        await self._redis.lpush(
            self._dlq_key(),
            json.dumps(message.to_dict())
        )

        # Update stats
        await self._redis.hincrby(f"{self.STATS_PREFIX}:dlq", message.priority.value, 1)

        log.error(
            f"Message {message.message_id} moved to DLQ after {message.attempts} attempts: "
            f"{message.last_error}"
        )

    async def get_dlq_messages(self, limit: int = 100) -> List[OutgoingMessage]:
        """Get messages from dead letter queue."""
        items = await self._redis.lrange(self._dlq_key(), 0, limit - 1)
        messages = []
        for item in items:
            try:
                data = json.loads(item)
                messages.append(OutgoingMessage.from_dict(data))
            except Exception as e:
                log.error(f"Error parsing DLQ message: {e}")
        return messages

    async def replay_dlq_message(self, message_id: str) -> bool:
        """
        Replay a message from DLQ back to the main queue.

        Args:
            message_id: ID of message to replay

        Returns:
            True if replayed successfully
        """
        # Find message in DLQ
        items = await self._redis.lrange(self._dlq_key(), 0, -1)

        for i, item in enumerate(items):
            try:
                data = json.loads(item)
                if data.get('message_id') == message_id:
                    msg = OutgoingMessage.from_dict(data)

                    # Reset retry state
                    msg.attempts = 0
                    msg.status = MessageStatus.PENDING
                    msg.last_error = None
                    msg.next_retry_at = None

                    # Remove from DLQ
                    await self._redis.lrem(self._dlq_key(), 1, item)

                    # Re-queue
                    return await self.enqueue(msg)

            except Exception as e:
                log.error(f"Error replaying DLQ message: {e}")

        return False

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {
            "queues": {},
            "dlq_size": 0,
            "processing": 0,
            "totals": {},
        }

        # Queue sizes
        for priority in MessagePriority:
            queue_key = self._queue_key(priority)
            size = await self._redis.zcard(queue_key)
            stats["queues"][priority.value] = size

        # DLQ size
        stats["dlq_size"] = await self._redis.llen(self._dlq_key())

        # Processing count
        keys = await self._redis.keys(f"{self.PROCESSING_PREFIX}:*")
        stats["processing"] = len(keys) if keys else 0

        # Totals from stats hash
        for stat_type in ["enqueued", "sent", "dlq"]:
            totals = await self._redis.hgetall(f"{self.STATS_PREFIX}:{stat_type}")
            stats["totals"][stat_type] = {
                k.decode() if isinstance(k, bytes) else k:
                int(v.decode() if isinstance(v, bytes) else v)
                for k, v in totals.items()
            } if totals else {}

        return stats

    async def clear_queue(self, priority: Optional[MessagePriority] = None) -> int:
        """
        Clear messages from queue.

        Args:
            priority: Specific priority to clear, or all if None

        Returns:
            Number of messages cleared
        """
        count = 0

        if priority:
            priorities = [priority]
        else:
            priorities = list(MessagePriority)

        for p in priorities:
            queue_key = self._queue_key(p)
            size = await self._redis.zcard(queue_key)
            await self._redis.delete(queue_key)
            count += size

        return count


class TelegramMessageQueueWorker:
    """
    Worker that processes the outgoing message queue.

    Runs in a background task, dequeuing messages and sending them
    to Telegram via the adapter.

    Usage:
        worker = TelegramMessageQueueWorker(queue, adapter)
        await worker.start()
        # ... later ...
        await worker.stop()
    """

    def __init__(
        self,
        queue: TelegramMessageQueue,
        send_func: Callable[[OutgoingMessage], Awaitable[bool]],
        batch_size: int = 10,
        poll_interval: float = 0.5,
        rate_limit_delay: float = 0.05,  # 20 msg/s max
    ):
        """
        Initialize worker.

        Args:
            queue: Message queue to process
            send_func: Async function to send message (returns success bool)
            batch_size: Messages to process per batch
            poll_interval: Seconds between queue polls
            rate_limit_delay: Minimum delay between sends (rate limiting)
        """
        self._queue = queue
        self._send_func = send_func
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._rate_limit_delay = rate_limit_delay

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the worker."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info("Telegram message queue worker started")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Telegram message queue worker stopped")

    async def _run(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                # Dequeue batch
                messages = await self._queue.dequeue(batch_size=self._batch_size)

                if not messages:
                    # No messages, wait before next poll
                    await asyncio.sleep(self._poll_interval)
                    continue

                # Process messages
                for message in messages:
                    if not self._running:
                        break

                    try:
                        success = await self._send_func(message)

                        if success:
                            await self._queue.ack(message)
                        else:
                            await self._queue.nack(message, "Send returned false")

                    except Exception as e:
                        error_msg = f"{type(e).__name__}: {str(e)}"

                        # Check if permanent error
                        permanent = self._is_permanent_error(e)
                        await self._queue.nack(message, error_msg, permanent=permanent)

                    # Rate limiting delay
                    await asyncio.sleep(self._rate_limit_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(1)

    def _is_permanent_error(self, error: Exception) -> bool:
        """Check if error is permanent (no retry)."""
        error_str = str(error).lower()

        # Permanent errors - don't retry
        permanent_indicators = [
            "chat not found",
            "bot was blocked",
            "user is deactivated",
            "chat_write_forbidden",
            "need administrator rights",
            "message is too long",
            "wrong file identifier",
        ]

        return any(indicator in error_str for indicator in permanent_indicators)


# =============================================================================
# Factory Functions
# =============================================================================

_message_queue: Optional[TelegramMessageQueue] = None
_queue_worker: Optional[TelegramMessageQueueWorker] = None


async def get_message_queue(redis_client) -> TelegramMessageQueue:
    """Get or create message queue singleton."""
    global _message_queue
    if _message_queue is None:
        config = get_telegram_config()
        _message_queue = TelegramMessageQueue(
            redis_client=redis_client,
            max_retries=config.max_retries,
            base_retry_delay=config.retry_delay_seconds,
        )
    return _message_queue


async def start_queue_worker(
    redis_client,
    send_func: Callable[[OutgoingMessage], Awaitable[bool]]
) -> TelegramMessageQueueWorker:
    """Start the message queue worker."""
    global _queue_worker

    queue = await get_message_queue(redis_client)
    _queue_worker = TelegramMessageQueueWorker(queue, send_func)
    await _queue_worker.start()
    return _queue_worker


async def stop_queue_worker() -> None:
    """Stop the message queue worker."""
    global _queue_worker
    if _queue_worker:
        await _queue_worker.stop()
        _queue_worker = None
