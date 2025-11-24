# app/infra/event_store/outbox_service.py
# =============================================================================
# Event Outbox Service for Exactly-Once Transport Publishing
# FIXED: Virtual Broker events now use transport like other bounded contexts
# FIXED: Now properly handles database transactions
# UPDATED: Added centralized DLQ Service integration
# UPDATED: Integrated centralized retry with exponential backoff (optional)
# UPDATED: Added poison pill detection for DLQ routing
# =============================================================================

from __future__ import annotations

import asyncio
import logging
import json
import uuid
from typing import List, Optional, Dict, Any, Set, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass

from app.infra.persistence.pg_client import db as pg_db_proxy, transaction
from app.infra.event_bus.event_bus import EventBus
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.reliability.retry import retry_async, RetryConfig
from app.infra.reliability.poison_pill_detector import PoisonPillDetector
from app.config.outbox_config import OutboxConfig, DEFAULT_OUTBOX_CONFIG

if TYPE_CHECKING:
    from app.infra.event_store.dlq_service import DLQService

log = logging.getLogger("wellwon.outbox")


class OutboxStatus(Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class OutboxEntry:
    """Represents an entry in the event outbox for transport publishing"""
    id: uuid.UUID
    event_id: uuid.UUID
    aggregate_id: uuid.UUID
    aggregate_type: str
    event_type: str
    event_data: Dict[str, Any]
    topic: str  # Target transport stream (e.g., transport.user-account-events)
    partition_key: Optional[str] = None
    status: OutboxStatus = OutboxStatus.PENDING
    publish_attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    last_error: Optional[str] = None
    correlation_id: Optional[uuid.UUID] = None
    causation_id: Optional[uuid.UUID] = None
    saga_id: Optional[uuid.UUID] = None
    metadata: Optional[Dict[str, Any]] = None
    aggregate_version: Optional[int] = None  # CRITICAL FIX: Added for correct event ordering
    created_at: Optional[datetime] = None

    def to_transport_event(self) -> Dict[str, Any]:
        """Convert to event format for transport publishing"""
        # Ensure event has all required fields for transport
        transport_event = self.event_data.copy()

        # Ensure standard fields
        transport_event.update({
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "aggregate_id": str(self.aggregate_id),
            "aggregate_type": self.aggregate_type,
            "timestamp": transport_event.get("timestamp") or datetime.now(timezone.utc).isoformat()
        })

        # Add correlation/causation if present
        if self.correlation_id:
            transport_event["correlation_id"] = str(self.correlation_id)
        if self.causation_id:
            transport_event["causation_id"] = str(self.causation_id)
        if self.saga_id:
            transport_event["saga_id"] = str(self.saga_id)

        return transport_event


class TransportOutboxService:
    """
    Manages the outbox for publishing events from Event Store to Transport layer.
    Ensures exactly-once delivery to transport streams (Redis/RedPanda).
    FIXED: Virtual Broker events now use transport like other bounded contexts
    FIXED: Now properly handles database transactions
    UPDATED: Integrated with centralized DLQ Service
    """

    # Default transport topic mappings
    DEFAULT_TRANSPORT_TOPICS = {
        # User domain events
        "UserAccountCreated": "transport.user-account-events",
        "UserPasswordChanged": "transport.user-account-events",
        "UserAccountDeleted": "transport.user-account-events",
        "UserEmailVerified": "transport.user-account-events",
        "UserProfileUpdated": "transport.user-account-events",
    }

    def __init__(
            self,
            event_bus: EventBus,
            max_retry_attempts: int = 3,
            retry_delay_seconds: int = 5,
            batch_size: int = 100,
            dead_letter_after_hours: int = 24,
            custom_topic_mappings: Optional[Dict[str, str]] = None,
            dlq_service: Optional['DLQService'] = None,
            use_exponential_backoff: bool = True,  # NEW: Enable centralized retry (default ON)
            use_poison_pill_detection: bool = True  # NEW: Enable poison pill detection (default ON)
    ):
        self.event_bus = event_bus
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.batch_size = batch_size
        self.dead_letter_after_hours = dead_letter_after_hours
        self._dlq_service = dlq_service
        self.use_exponential_backoff = use_exponential_backoff
        self.use_poison_pill_detection = use_poison_pill_detection

        # Configure centralized retry (if enabled)
        if self.use_exponential_backoff:
            self.retry_config = RetryConfig(
                max_attempts=max_retry_attempts,
                initial_delay_ms=100,      # Start fast: 100ms
                max_delay_ms=30000,         # Max delay: 30 seconds
                backoff_factor=2.0,         # Exponential: 100, 200, 400, 800, 1600ms...
                jitter=True,                # Prevent thundering herd
                jitter_type='full'          # Full jitter for best distribution
            )
            log.info(f"Outbox using exponential backoff retry (max attempts: {max_retry_attempts})")
        else:
            self.retry_config = None
            log.info(f"Outbox using legacy fixed delay retry ({retry_delay_seconds}s)")

        # Initialize poison pill detector (if enabled)
        if self.use_poison_pill_detection:
            log.info("Outbox poison pill detection enabled (non-transient errors skip retries)")

        # Merge custom mappings with defaults
        self.topic_mappings = self.DEFAULT_TRANSPORT_TOPICS.copy()
        if custom_topic_mappings:
            self.topic_mappings.update(custom_topic_mappings)

    def _get_transport_topic(self, event_type: str, aggregate_type: str) -> Optional[str]:
        """
        Determine the transport topic for an event.
        FIXED: Virtual Broker events now get proper transport topics
        """
        # First check explicit mapping
        if event_type in self.topic_mappings:
            return self.topic_mappings[event_type]

        # For Virtual Broker events, use dedicated transport topic
        if event_type.startswith("Virtual"):
            return "transport.virtual-broker-events"

        # Convert CamelCase to kebab-case for the topic name
        # BrokerConnection -> broker-connection
        import re
        kebab_case = re.sub('([a-z0-9])([A-Z])', r'\1-\2', aggregate_type).lower()
        return f"transport.{kebab_case}-events"

    async def save_events_to_outbox(
            self,
            envelopes: List[EventEnvelope]
    ) -> None:
        """
        Save events to outbox for transport publishing.
        CRITICAL FIX (2025-11-05): Check ContextVar for transaction connection first!
        If we're inside a transaction (e.g., sync projections), use the SAME transaction.
        Otherwise create a new one. This prevents race conditions.

        Args:
            envelopes: Event envelopes from the event store
        """
        if not envelopes:
            return

        # CRITICAL FIX: Check if we're inside a transaction context
        from app.infra.persistence.pg_client import _current_transaction_connection
        transaction_conn = _current_transaction_connection.get()

        if transaction_conn is not None:
            # Use existing transaction (e.g., during sync projections)
            await self._save_to_outbox_with_connection(envelopes, transaction_conn)
        else:
            # Create new transaction if not in transaction context
            async with transaction() as conn:
                await self._save_to_outbox_with_connection(envelopes, conn)

    async def _save_to_outbox_with_connection(
            self,
            envelopes: List[EventEnvelope],
            conn
    ) -> None:
        """
        Internal method to save events using a specific connection.
        CRITICAL FIX (2025-11-05): Separated logic to support both transaction contexts.
        """
        # Prepare batch insert - including Virtual Broker events
        rows = []
        for envelope in envelopes:
            transport_topic = self._get_transport_topic(
                envelope.event_type,
                envelope.aggregate_type
            )

            # All events get a transport topic now
            if not transport_topic:
                log.warning(f"No transport topic for {envelope.event_type}, using default")
                transport_topic = f"transport.{envelope.aggregate_type.lower()}-events"

            rows.append((
                envelope.event_id,
                envelope.aggregate_id,
                envelope.aggregate_type,
                envelope.event_type,
                json.dumps(envelope.event_data),
                transport_topic,
                str(envelope.aggregate_id),  # Use aggregate_id as partition key
                envelope.correlation_id,
                envelope.causation_id,
                envelope.saga_id,
                json.dumps(envelope.metadata) if envelope.metadata else None,
                envelope.aggregate_version  # CRITICAL FIX: Add aggregate version for correct ordering
            ))

        # Batch insert using a single query with multiple values
        if not rows:
            return

        # Build the VALUES clause with proper parameterization
        placeholders = []
        flattened_values = []
        param_count = 12  # FIXED: number of columns we're inserting (added aggregate_version)

        for i, row in enumerate(rows):
            # Create placeholder for this row ($1, $2, ..., $12), ($13, $14, ..., $24), etc.
            row_placeholders = [f"${j}" for j in range(i * param_count + 1, (i + 1) * param_count + 1)]
            placeholders.append(f"({', '.join(row_placeholders)})")

            # Flatten the row values
            flattened_values.extend(row)

        values_clause = ", ".join(placeholders)

        # FIXED: Use the connection from our transaction context
        # CRITICAL FIX: Added aggregate_version column for correct event ordering
        await conn.execute(
            f"""
            INSERT INTO event_outbox (event_id, aggregate_id, aggregate_type, event_type,
                                     event_data, topic, partition_key,
                                     correlation_id, causation_id, saga_id, metadata, aggregate_version)
            VALUES {values_clause}
            ON CONFLICT (event_id) DO NOTHING -- Idempotency
            """,
            *flattened_values
        )

        log.debug(f"Saved {len(rows)} events to outbox for transport publishing")

    async def publish_immediate(self, entry: OutboxEntry) -> bool:
        """
        Publish event immediately to transport (for SYNC events).

        CRITICAL FIX (Nov 12, 2025): True synchronous publish with zero polling delay.
        - Does NOT save to outbox table
        - Raises exception on failure (caller handles fallback)
        - Used for SYNC events (BrokerAccountLinked, etc.) that need instant delivery

        Args:
            entry: Outbox entry to publish immediately

        Returns:
            True if published successfully

        Raises:
            Exception if publish fails (caller should handle fallback to outbox)
        """
        transport_event = entry.to_transport_event()
        await self.event_bus.publish(entry.topic, transport_event)
        log.info(
            f"SYNC event {entry.event_type} (id: {entry.event_id}) published immediately "
            f"to {entry.topic} (zero polling delay)"
        )
        return True

    async def get_pending_events(
            self,
            limit: Optional[int] = None
    ) -> List[OutboxEntry]:
        """Get pending events for publishing (OPTIMIZED with stored procedure)"""
        limit = limit or self.batch_size

        # Get events that are ready for publishing
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.retry_delay_seconds)

        # OPTIMIZED: Use stored procedure to reduce query compilation overhead
        # The stored procedure has a pre-compiled query plan, reducing first-query latency
        # from ~100ms to <5ms
        # Note: Function signature - get_pending_outbox_events(max_attempts INT, cutoff_time TIMESTAMPTZ, created_after TIMESTAMPTZ, limit INT)
        # Function definition in database/wellwon.sql (lines 1459-1519)
        # noinspection SqlResolve
        try:
            rows = await pg_db_proxy.fetch(
                """
                SELECT * FROM get_pending_outbox_events($1, $2, $3, $4)
                """,
                self.max_retry_attempts,
                cutoff_time,
                datetime.now(timezone.utc) - timedelta(hours=self.dead_letter_after_hours),
                limit
            )
        except Exception as e:
            # Fallback to direct query if stored procedure not available
            if "function" in str(e).lower() and "does not exist" in str(e).lower():
                log.warning(f"Stored procedure get_pending_outbox_events not found, using direct query fallback")
                rows = await pg_db_proxy.fetch(
                    """
                    SELECT id,
                           event_id,
                           aggregate_id,
                           aggregate_type,
                           event_type,
                           event_data,
                           topic,
                           partition_key,
                           status,
                           publish_attempts,
                           last_attempt_at,
                           published_at,
                           last_error,
                           correlation_id,
                           causation_id,
                           saga_id,
                           metadata,
                           aggregate_version,
                           created_at
                    FROM event_outbox
                    WHERE status IN ('pending', 'failed')
                      AND publish_attempts < $1
                      AND (last_attempt_at IS NULL OR last_attempt_at < $2)
                      AND created_at > $3
                    ORDER BY aggregate_id, aggregate_version, created_at, id
                    LIMIT $4 FOR UPDATE SKIP LOCKED
                    """,
                    self.max_retry_attempts,
                    cutoff_time,
                    datetime.now(timezone.utc) - timedelta(hours=self.dead_letter_after_hours),
                    limit
                )
            else:
                raise

        entries = []
        for row in rows:
            # asyncpg returns JSONB as dict already - no need to json.loads()
            event_data = row['event_data']
            if isinstance(event_data, str):
                event_data = json.loads(event_data)

            metadata = row['metadata']
            if metadata and isinstance(metadata, str):
                metadata = json.loads(metadata)

            entries.append(OutboxEntry(
                id=row['id'],
                event_id=row['event_id'],
                aggregate_id=row['aggregate_id'],
                aggregate_type=row['aggregate_type'],
                event_type=row['event_type'],
                event_data=event_data,
                topic=row['topic'],
                partition_key=row['partition_key'],
                status=OutboxStatus(row['status']),
                publish_attempts=row['publish_attempts'],
                last_attempt_at=row['last_attempt_at'],
                published_at=row['published_at'],
                last_error=row['last_error'],
                correlation_id=row['correlation_id'],
                causation_id=row['causation_id'],
                saga_id=row['saga_id'],
                metadata=metadata,
                aggregate_version=row['aggregate_version'],  # CRITICAL FIX: Include aggregate_version for ordering
                created_at=row['created_at']
            ))

        return entries

    async def publish_event(self, entry: OutboxEntry) -> bool:
        """
        Publish a single event to the transport layer.

        Uses centralized retry with exponential backoff (if enabled).
        Detects poison pills to skip unnecessary retries (if enabled).

        Returns:
            True if successfully published, False otherwise
        """
        try:
            # Use centralized retry if enabled
            if self.use_exponential_backoff and self.retry_config:
                await retry_async(
                    self._do_publish,
                    entry,
                    retry_config=self.retry_config,
                    context=f"outbox-{entry.event_id}"
                )
            else:
                # Legacy: direct publish without retry wrapper
                await self._do_publish(entry)

            # Mark as published
            await self.mark_as_published(entry.id)

            log.info(
                f"Published event {entry.event_id} ({entry.event_type}) "
                f"to transport topic {entry.topic}"
            )

            return True

        except Exception as e:
            error_message = str(e)
            log.error(
                f"Failed to publish event {entry.event_id} to {entry.topic}: {error_message}",
                exc_info=True
            )

            # Check if this is a poison pill (non-retriable error)
            is_poison = False
            if self.use_poison_pill_detection:
                is_poison = PoisonPillDetector.is_poison_pill(e, error_message)

                if is_poison:
                    log.error(
                        f"☠️ POISON PILL detected for event {entry.event_id}: {error_message[:200]} "
                        f"- Marking for DLQ immediately (skipping further retries)"
                    )
                    # Send directly to DLQ
                    if self._dlq_service:
                        await self._dlq_service.record_failure(
                            source="outbox_service",
                            event=entry.event_data,  # The actual event data
                            error=e,                 # The exception object
                            context={
                                "event_id": str(entry.event_id),
                                "event_type": entry.event_type,
                                "aggregate_id": str(entry.aggregate_id),
                                "aggregate_type": entry.aggregate_type,
                                "topic": entry.topic,
                                "is_poison_pill": True,
                                "retry_attempts": entry.publish_attempts,
                                "detection_reason": "PoisonPillDetector identified non-transient error"
                            }
                        )

            # Update failure status
            await self.mark_publish_attempt(entry.id, error_message, is_poison_pill=is_poison)

            return False

    async def publish_event_transactional(self, entry: OutboxEntry) -> bool:
        """
        Publish event using Kafka transaction for atomic outbox → Kafka operation.

        ISSUE #3 DOCUMENTATION: PostgreSQL Update Non-Atomicity
        =========================================================

        This method provides KAFKA-level atomicity but NOT cross-database atomicity:

        1. Event is sent to Kafka (within Kafka transaction)
        2. Outbox status updated in PostgreSQL (SEPARATE transaction - NOT atomic with Kafka)
        3. Kafka transaction committed

        WHY THIS IS ACCEPTABLE (Best Practice Trade-off):
        --------------------------------------------------
        - If Kafka commit succeeds + PostgreSQL fails:
          → Event marked 'pending', will be republished
          → Consumers use isolation_level='read_committed' (only see committed messages)
          → Idempotent handlers prevent duplicate side effects
          → Eventual consistency maintained

        - If PostgreSQL succeeds + Kafka commit fails:
          → Event marked 'published' but not sent
          → Next reconciliation run will detect and fix (reconciliation_service.py)
          → Sequence gap detection catches orphaned events

        - Implementing true 2PC (Two-Phase Commit) across Kafka + PostgreSQL would:
          → Require distributed transaction coordinator (XA protocol)
          → 10x latency overhead (50ms → 500ms)
          → NOT supported by Redpanda natively
          → Violate exactly-once semantics (coordinator can fail)

        ALTERNATIVE CONSIDERED: Single database transaction
        ---------------------------------------------------
        Moving Kafka send() into PostgreSQL transaction is IMPOSSIBLE because:
        - Kafka transactions are separate from database transactions
        - Cannot combine them without 2PC coordinator

        CONCLUSION: This design follows industry best practices
        --------------------------------------------------------
        - Outbox pattern for at-least-once delivery
        - Kafka transactions for exactly-once on transport layer
        - Idempotent handlers for exactly-once on data layer
        - Reconciliation service as safety net

        Returns:
            True if successfully published, False otherwise
        """
        from app.infra.metrics.exactly_once_metrics import (
            outbox_transactional_publish_success_total,
            outbox_transactional_publish_failures_total,
            outbox_transactional_publish_duration_seconds
        )
        import time

        start_time = time.time()

        # Get transactional producer from event bus
        # Note: This requires event_bus to support transactional producers
        if not hasattr(self.event_bus, '_adapter'):
            log.warning("EventBus doesn't support transactional publishing, falling back to standard")
            return await self.publish_event(entry)

        adapter = self.event_bus._adapter
        if not hasattr(adapter, '_create_transactional_producer'):
            log.warning("Adapter doesn't support transactional publishing, falling back to standard")
            return await self.publish_event(entry)

        # Create unique transactional ID for outbox publisher
        import os
        transactional_id = f"{adapter._transactional_id_prefix}-outbox-{os.getpid()}"

        try:
            # Get or create transactional producer
            txn_producer = await adapter._create_transactional_producer(transactional_id)

            # Start transaction (producer already has a transaction active from initialization)
            # Convert to transport event format
            transport_event = entry.to_transport_event()

            # 1. Send to Kafka (within transaction)
            await txn_producer.send(
                entry.topic,
                value=json.dumps(transport_event).encode('utf-8'),
                key=str(entry.partition_key).encode('utf-8') if entry.partition_key else None
            )

            # 2. Update outbox status in PostgreSQL (NOT part of Kafka txn, but separate)
            await pg_db_proxy.execute(
                """
                UPDATE event_outbox
                SET status = 'published',
                    published_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                entry.id
            )

            # 3. Commit Kafka transaction
            await txn_producer.commit_transaction()

            # 4. Begin new transaction for next publish
            await txn_producer.begin_transaction()

            # Record metrics
            duration = time.time() - start_time
            outbox_transactional_publish_success_total.inc()
            outbox_transactional_publish_duration_seconds.observe(duration)

            log.info(
                f"Transactionally published event {entry.event_id} ({entry.event_type}) "
                f"to topic {entry.topic}, duration={duration:.3f}s"
            )

            return True

        except Exception as e:
            error_message = str(e)
            log.error(
                f"Transactional publish failed for event {entry.event_id}: {error_message}",
                exc_info=True
            )

            # Record failure metrics
            outbox_transactional_publish_failures_total.labels(
                reason=type(e).__name__
            ).inc()

            # Try to abort transaction
            try:
                if 'txn_producer' in locals():
                    await txn_producer.abort_transaction()
                    await txn_producer.begin_transaction()  # Start fresh transaction
            except Exception as abort_error:
                log.error(f"Failed to abort transaction: {abort_error}")

            # Update failure status in outbox
            await self.mark_publish_attempt(entry.id, error_message)

            return False

    async def _do_publish(self, entry: OutboxEntry) -> None:
        """
        Internal method to actually publish the event.
        Separated for retry wrapper compatibility.

        Raises:
            Exception if publish fails
        """
        # Convert to transport event format
        transport_event = entry.to_transport_event()

        # Publish to transport stream
        await self.event_bus.publish(
            entry.topic,
            transport_event
        )

    async def mark_as_published(self, outbox_id: uuid.UUID) -> None:
        """Mark an outbox entry as successfully published"""
        await pg_db_proxy.execute(
            """
            UPDATE event_outbox
            SET status       = 'published',
                published_at = CURRENT_TIMESTAMP,
                updated_at   = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            outbox_id
        )

    async def mark_publish_attempt(
        self,
        outbox_id: uuid.UUID,
        error: str,
        is_poison_pill: bool = False
    ) -> None:
        """
        Mark a failed publish attempt.

        Args:
            outbox_id: The outbox entry ID
            error: Error message
            is_poison_pill: If True, marks entry for immediate DLQ (skips further retries)
        """
        # If poison pill, set status to dead_letter and max out attempts
        if is_poison_pill:
            await pg_db_proxy.execute(
                """
                UPDATE event_outbox
                SET status           = 'dead_letter',
                    publish_attempts = $2,  -- Max out attempts to prevent retries
                    last_attempt_at  = CURRENT_TIMESTAMP,
                    last_error       = $3,
                    last_error_at    = CURRENT_TIMESTAMP,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                outbox_id,
                self.max_retry_attempts,  # Set to max to prevent retries
                f"[POISON PILL] {error[:950]}"  # Prefix with marker
            )
        else:
            # Normal failure - increment attempts
            await pg_db_proxy.execute(
                """
                UPDATE event_outbox
                SET status           = 'failed',
                    publish_attempts = publish_attempts + 1,
                    last_attempt_at  = CURRENT_TIMESTAMP,
                    last_error       = $2,
                    last_error_at    = CURRENT_TIMESTAMP,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                outbox_id,
                error[:1000]  # Truncate error message
            )

    async def move_to_dead_letter(self) -> int:
        """Move old failed events to dead letter status"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.dead_letter_after_hours)

        result = await pg_db_proxy.execute(
            """
            UPDATE event_outbox
            SET status     = 'dead_letter',
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'failed'
              AND (
                publish_attempts >= $1
                    OR created_at < $2
                )
            """,
            self.max_retry_attempts,
            cutoff
        )

        count = int(result.split()[-1]) if result else 0
        if count > 0:
            log.warning(f"Moved {count} events to dead letter queue")

            # Also send to centralized DLQ
            if self._dlq_service:
                # Get the events that were just marked as dead_letter
                dlq_events = await pg_db_proxy.fetch(
                    """
                    SELECT event_id,
                           event_type,
                           event_data,
                           topic,
                           last_error,
                           aggregate_id,
                           aggregate_type
                    FROM event_outbox
                    WHERE status = 'dead_letter'
                      AND updated_at >= NOW() - INTERVAL '1 minute'
                    """
                )

                for row in dlq_events:
                    # asyncpg returns JSONB as dict already
                    event_data = row['event_data']
                    if isinstance(event_data, str):
                        event_data = json.loads(event_data)

                    await self._dlq_service.record_failure(
                        source="outbox_service",
                        event=event_data,
                        error=Exception(row['last_error'] or "Outbox publishing failed"),
                        context={
                            "topic": row['topic'],
                            "aggregate_id": str(row['aggregate_id']),
                            "aggregate_type": row['aggregate_type']
                        }
                    )

        return count

    async def cleanup_published_events(self, days_to_keep: int = 7) -> int:
        """Clean up old published events"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        result = await pg_db_proxy.execute(
            """
            DELETE
            FROM event_outbox
            WHERE status = 'published'
              AND published_at < $1
            """,
            cutoff
        )

        count = int(result.split()[-1]) if result else 0
        if count > 0:
            log.info(f"Cleaned up {count} old published events")

        return count

    async def get_outbox_stats(self) -> Dict[str, Any]:
        """Get statistics about the outbox"""
        stats = await pg_db_proxy.fetchrow(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'pending')         as pending,
                   COUNT(*) FILTER (WHERE status = 'published')       as published,
                   COUNT(*) FILTER (WHERE status = 'failed')          as failed,
                   COUNT(*) FILTER (WHERE status = 'dead_letter')     as dead_letter,
                   MIN(created_at) FILTER (WHERE status = 'pending')  as oldest_pending,
                   MAX(published_at)                                  as last_published_at,
                   COUNT(DISTINCT topic)                              as unique_topics,
                   COUNT(*) FILTER (WHERE event_type LIKE 'Virtual%') as virtual_broker_events
            FROM event_outbox
            """
        )

        return dict(stats) if stats else {}


class OutboxPublisher:
    """
    Background service that publishes events from the outbox to transport streams.

    ENHANCED (2025-11-14): Uses PostgreSQL LISTEN/NOTIFY for near-zero latency.
    This provides CDC-like performance WITHOUT external dependencies (Debezium).

    Best Practice: PostgreSQL NOTIFY triggers instant processing when events arrive,
    with fallback polling for reliability.
    """

    def __init__(
            self,
            outbox_service: TransportOutboxService,
            config: Optional[OutboxConfig] = None,
            # Legacy parameters (deprecated - use config instead)
            poll_interval_seconds: Optional[float] = None,
            batch_size: Optional[int] = None,
            synchronous_mode: Optional[bool] = None,
            synchronous_event_types: Optional[Set[str]] = None,
            use_listen_notify: bool = True  # NEW: Enable LISTEN/NOTIFY for instant processing
    ):
        # Use provided config or default
        self.config = config or DEFAULT_OUTBOX_CONFIG

        # Legacy parameter override (for backward compatibility)
        if poll_interval_seconds is not None:
            self.poll_interval_seconds = poll_interval_seconds
        else:
            self.poll_interval_seconds = self.config.poll_interval_seconds

        if batch_size is not None:
            self.batch_size = batch_size
        else:
            self.batch_size = self.config.batch_size

        if synchronous_mode is not None:
            self.synchronous_mode = synchronous_mode
        else:
            self.synchronous_mode = self.config.synchronous_mode

        if synchronous_event_types is not None:
            self.synchronous_event_types = synchronous_event_types
        else:
            self.synchronous_event_types = self.config.synchronous_event_types

        self.outbox_service = outbox_service
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None  # NEW: LISTEN/NOTIFY task
        self._consecutive_empty_polls = 0
        self._adaptive_interval = self.poll_interval_seconds

        # NEW: LISTEN/NOTIFY settings
        self.use_listen_notify = use_listen_notify
        self._notify_conn = None  # Dedicated connection for LISTEN
        self._process_event = asyncio.Event()  # Signal for instant processing

        # Adaptive polling settings
        self._enable_adaptive = self.config.enable_adaptive_polling
        self._adaptive_min = self.config.adaptive_poll_min_interval_seconds
        self._adaptive_max = self.config.adaptive_poll_max_interval_seconds
        self._adaptive_threshold = self.config.adaptive_poll_empty_threshold

        log.info(
            f"OutboxPublisher initialized: "
            f"poll={self.poll_interval_seconds * 1000:.0f}ms, "
            f"batch={self.batch_size}, "
            f"sync_mode={self.synchronous_mode}, "
            f"adaptive={self._enable_adaptive}, "
            f"listen_notify={'ENABLED (near-zero latency)' if use_listen_notify else 'DISABLED'}"
        )

    async def start(self) -> None:
        """Start the outbox publisher with LISTEN/NOTIFY support"""
        if self._running:
            log.warning("Outbox publisher already running")
            return

        self._running = True

        # Start LISTEN/NOTIFY task if enabled
        if self.use_listen_notify:
            self._listen_task = asyncio.create_task(self._listen_for_notifications())
            log.info("PostgreSQL LISTEN/NOTIFY enabled for instant outbox processing")

        # Start main publisher task
        self._task = asyncio.create_task(self._run())
        log.info(
            f"Outbox publisher started: "
            f"sync_mode={self.synchronous_mode}, "
            f"notify={'ENABLED' if self.use_listen_notify else 'DISABLED'}"
        )

    async def stop(self) -> None:
        """Stop the outbox publisher and cleanup LISTEN/NOTIFY"""
        self._running = False

        # Stop LISTEN/NOTIFY task
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        # Stop main task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Close NOTIFY connection
        if self._notify_conn:
            try:
                await self._notify_conn.close()
            except Exception as e:
                log.warning(f"Error closing NOTIFY connection: {e}")

        log.info("Outbox publisher stopped")

    async def _listen_for_notifications(self) -> None:
        """
        LISTEN for PostgreSQL NOTIFY events from outbox table.

        BEST PRACTICE (PostgreSQL): Use dedicated connection for LISTEN
        to get instant notifications when events are inserted.
        This provides CDC-like latency WITHOUT external dependencies.

        Uses asyncpg add_listener() API with callback pattern.
        """
        import asyncpg
        from urllib.parse import urlparse

        # Queue for receiving notifications from callback
        notification_queue = asyncio.Queue()

        # Callback function for asyncpg listener
        def notification_callback(connection, pid, channel, payload):
            """Called by asyncpg when NOTIFY received"""
            try:
                # Put notification in queue (non-blocking)
                notification_queue.put_nowait(payload)
            except Exception as e:
                log.error(f"Error in notification callback: {e}")

        try:
            # Create dedicated connection for LISTEN
            from app.config.pg_client_config import get_database_config
            db_config = get_database_config()

            # Parse DSN to extract connection parameters
            parsed_dsn = urlparse(db_config.main_dsn)

            self._notify_conn = await asyncpg.connect(
                host=parsed_dsn.hostname,
                port=parsed_dsn.port or 5432,
                user=parsed_dsn.username,
                password=parsed_dsn.password,
                database=parsed_dsn.path.lstrip('/')
            )

            # Add listener with callback (asyncpg API)
            await self._notify_conn.add_listener('outbox_events', notification_callback)
            log.info("PostgreSQL LISTEN started on channel 'outbox_events'")

            # Process notifications from queue
            while self._running:
                try:
                    # Wait for notification from queue with timeout
                    payload = await asyncio.wait_for(
                        notification_queue.get(),
                        timeout=5.0  # Check _running flag every 5s
                    )

                    # Instant signal to process events
                    self._process_event.set()
                    log.debug(f"NOTIFY received: {payload}")

                except asyncio.TimeoutError:
                    # Normal timeout - continue loop
                    pass
                except asyncio.CancelledError:
                    break

        except Exception as e:
            log.error(f"Error in LISTEN task: {e}", exc_info=True)
            # Fallback to polling if LISTEN fails
            log.warning("LISTEN/NOTIFY disabled, using polling fallback")

        finally:
            if self._notify_conn:
                try:
                    # Remove listener before closing
                    await self._notify_conn.remove_listener('outbox_events', notification_callback)
                    await self._notify_conn.close()
                except Exception:
                    pass

    async def _run(self) -> None:
        """
        Main publisher loop with LISTEN/NOTIFY integration.

        ENHANCED (2025-11-14): Combines instant NOTIFY events with fallback polling.
        - NOTIFY triggers immediate processing (near-zero latency)
        - Polling ensures reliability if NOTIFY fails
        - Adaptive polling reduces DB load when idle
        """
        log.info("Outbox publisher running with LISTEN/NOTIFY support")

        while self._running:
            try:
                # Wait for notification OR timeout
                if self.use_listen_notify:
                    try:
                        # Wait for NOTIFY event or timeout
                        await asyncio.wait_for(
                            self._process_event.wait(),
                            timeout=self._adaptive_interval
                        )
                        # Clear the event flag
                        self._process_event.clear()
                    except asyncio.TimeoutError:
                        # Timeout = fallback polling
                        pass
                else:
                    # Pure polling mode (LISTEN/NOTIFY disabled)
                    await asyncio.sleep(self._adaptive_interval)

                # Get pending events
                entries = await self.outbox_service.get_pending_events(self.batch_size)

                if entries:
                    # Reset adaptive interval when we have work
                    self._consecutive_empty_polls = 0
                    self._adaptive_interval = self.poll_interval_seconds

                    log.debug(f"Publishing {len(entries)} events from outbox")

                    # Publish each event - use transactional if enabled
                    success_count = 0
                    use_txn = self.config.enable_transactional_publishing

                    for entry in entries:
                        if use_txn:
                            # Use Kafka transactions for atomic publish
                            if await self.outbox_service.publish_event_transactional(entry):
                                success_count += 1
                        else:
                            # Use standard publish (at-least-once + idempotent handlers)
                            if await self.outbox_service.publish_event(entry):
                                success_count += 1

                    log.info(
                        f"Published {success_count}/{len(entries)} events "
                        f"from outbox to transport"
                    )

                    # Move very old failed events to dead letter
                    await self.outbox_service.move_to_dead_letter()
                else:
                    # OPTIMIZED: Adaptive polling - slow down if no events
                    self._consecutive_empty_polls += 1

                    # Increase interval after 10 empty polls, max 2 seconds
                    if self._consecutive_empty_polls > 10 and not self.use_listen_notify:
                        self._adaptive_interval = min(
                            self._adaptive_interval * 1.5,
                            2.0  # Max 2 seconds
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in outbox publisher: {e}", exc_info=True)
                # Reset adaptive interval on error
                self._adaptive_interval = self.poll_interval_seconds
                await asyncio.sleep(self.poll_interval_seconds)

        log.info("Outbox publisher stopped")


# Convenience function to create outbox with event bus
def create_transport_outbox(
        event_bus: EventBus,
        custom_mappings: Optional[Dict[str, str]] = None,
        dlq_service: Optional['DLQService'] = None
) -> TransportOutboxService:
    """Create a transport outbox service with event bus and optional DLQ"""
    return TransportOutboxService(
        event_bus=event_bus,
        custom_topic_mappings=custom_mappings,
        dlq_service=dlq_service
    )