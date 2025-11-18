# =============================================================================
# File: app/infra/event_bus/transport_adapter.py
# Description: Abstract adapter interface for Redpanda/Kafka durable streams
#              SIMPLIFIED (Nov 13, 2025): PUBSUB mode removed
# =============================================================================
"""
Abstract async transport adapter for EventBus durable stream delivery.

Uses Redpanda/Kafka for event sourcing with:
- Durable streams with offset commits (exactly-once delivery)
- Consumer groups for load balancing
- Manual offset management for reliability

NOTE: Redis Pub/Sub for WebSocket coordination is handled separately
by PubSubBus (app/wse/core/pubsub_bus.py), not by this adapter.
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Awaitable, AsyncIterator, Optional, List, NamedTuple


class HealthCheck(NamedTuple):
    """Health check information for transport adapters"""
    is_healthy: bool
    details: Dict[str, Any]


class TransportAdapter(ABC):
    """
    Abstract base transport adapter for Redpanda/Kafka event delivery.

    SIMPLIFIED (Nov 13, 2025): Removed PUBSUB mode - all events use durable streams.
    Redis Pub/Sub for WebSocket coordination is handled by separate PubSubBus.

    IMPORTANT: The stream_consume() method should block until the consumer
    is explicitly cancelled. This allows proper lifecycle management by the caller.
    """

    @abstractmethod
    async def publish(
            self,
            channel: str,
            event: Dict[str, Any]
    ) -> None:
        """
        Publish a single event to a durable stream (Redpanda/Kafka topic).
        Consumers in a consumer group can process events reliably with offset commits.
        """

    @abstractmethod
    async def publish_batch(
            self,
            channel: str,
            events: List[Dict[str, Any]],
            partition_key: Optional[str] = None
    ) -> None:
        """
        Publish a batch of events to a durable stream.
        Uses Kafka batching for optimal throughput.
        """

    @abstractmethod
    async def stream_consume(
            self,
            channel: str,
            handler: Callable[[Dict[str, Any]], Awaitable[None]],
            group: str,
            consumer: str,
            batch_size: int = 10,
            block_ms=int(os.getenv("TRANSPORT_ADAPTER_BLOCK_MS", "5000"))
    ) -> None:
        """
        Consume events from a durable stream in a consumer group.
        - `group`: name of the consumer group.
        - `consumer`: unique consumer name.
        - `batch_size`: max events to fetch per iteration.
        - `block_ms`: block timeout in milliseconds.

        IMPORTANT: This method should block until the consumer is cancelled.
        The implementation should handle the consumer loop internally and only
        return when explicitly stopped or an error occurs.
        """

    @abstractmethod
    async def stream(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Raw async generator for reading events from a durable stream.
        Yields one event payload at a time.
        """

    @abstractmethod
    async def close(self) -> None:
        """
        Gracefully shut down the adapter, closing any connections or background tasks.
        """

    async def health_check(self) -> HealthCheck:
        """
        Check the health of the underlying transport connections.
        Returns a HealthCheck object with is_healthy property and details.
        Default implementation assumes health if no override.
        """
        return HealthCheck(is_healthy=True, details={"status": "default implementation"})

    async def ping(self) -> bool:
        """
        Simple connectivity check to the underlying transport.
        Returns True if connected, False otherwise.
        The default implementation assumes connected if no override.
        """
        return True

# =============================================================================
# EOF
# =============================================================================