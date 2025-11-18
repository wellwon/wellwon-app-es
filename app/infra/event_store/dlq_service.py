# app/infra/event_store/dlq_service.py
"""
Dead Letter Queue Service - Part of Event Store Infrastructure

Handles failed events from all system components with:
- Non-blocking async queue
- Batch processing for efficiency
- Multiple storage backends
- Automatic error categorization
- Comprehensive metrics
- UPDATED: Poison pill detection for non-transient errors
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from asyncio import Queue, QueueFull
import traceback

from app.infra.persistence.pg_client import db as pg_db_proxy, transaction
from app.infra.event_bus.event_bus import EventBus
from app.config.dlq_config import (
    DLQConfig, DLQStorageMode, DLQSourceSystem,
    DLQCategory, DLQReason, get_dlq_config
)
from app.infra.metrics.dlq_metrics import get_dlq_metrics, DLQMetricsCollector
from app.infra.reliability.poison_pill_detector import PoisonPillDetector, ErrorCategory

log = logging.getLogger("wellwon.event_store.dlq")


@dataclass
class DLQMetrics:
    """DLQ service metrics"""
    received: int = 0
    processed: int = 0
    dropped: int = 0
    errors: int = 0
    kafka_sent: int = 0
    db_persisted: int = 0
    emergency_persists: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_reason: Dict[str, int] = field(default_factory=dict)
    queue_high_watermark: int = 0
    last_flush_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    average_batch_size: float = 0.0
    total_batches: int = 0
    poison_pills_detected: int = 0  # NEW: Track poison pills
    transient_errors: int = 0        # NEW: Track transient errors


class DLQService:
    """
    Dead Letter Queue Service for Event Store

    Features:
    - Fire-and-forget API (non-blocking)
    - Async queue with configurable size
    - Batch processing for DB efficiency
    - Kafka forwarding for real-time monitoring
    - Automatic error categorization
    - Comprehensive metrics with external collector
    - Emergency persist when queue is full
    """

    def __init__(
            self,
            config: Optional[DLQConfig] = None,
            event_bus: Optional[EventBus] = None,
            metrics_collector: Optional[DLQMetricsCollector] = None
    ):
        """
        Initialize DLQ Service

        Args:
            config: DLQ configuration (uses default if not provided)
            event_bus: EventBus instance for Kafka forwarding
            metrics_collector: Optional metrics collector (uses global if not provided)
        """
        self.config = config or get_dlq_config()
        self.event_bus = event_bus
        self.metrics_collector = metrics_collector or get_dlq_metrics()

        # Async queue for non-blocking operations
        self._queue: Queue[Dict[str, Any]] = Queue(maxsize=self.config.queue_size)
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        self._initialized = False

        # Internal metrics (kept for backward compatibility)
        self._metrics = DLQMetrics()

        # Batch processing state
        self._current_batch: List[Dict[str, Any]] = []
        self._last_flush_time = asyncio.get_event_loop().time()

        log.info(f"DLQ Service created with config: {self.config.to_dict()}")

    async def initialize(self) -> None:
        """
        Initialize the DLQ service

        This method performs any necessary async initialization and starts
        the background processor if the service is enabled.
        """
        if self._initialized:
            log.warning("DLQ Service already initialized")
            return

        log.info("Initializing DLQ Service...")

        try:
            # Perform any async initialization here
            # For example, verify database connectivity, create tables if needed, etc.

            # Verify database table exists (optional)
            if self._should_persist_to_db():
                await self._verify_database_table()

            # Verify Kafka connectivity if enabled
            if self._should_forward_to_kafka() and self.event_bus:
                log.info("Verifying Kafka connectivity for DLQ forwarding...")
                # You could add a health check here if needed

            # Initialize metrics collector if needed
            if self.metrics_collector and hasattr(self.metrics_collector, 'initialize'):
                await self.metrics_collector.initialize()

            # Start the background processor
            await self.start()

            self._initialized = True
            log.info("DLQ Service initialized successfully")

        except Exception as e:
            log.error(f"Failed to initialize DLQ Service: {e}", exc_info=True)
            raise

    async def _verify_database_table(self) -> None:
        """Verify the DLQ database table exists"""
        try:
            # Check if table exists
            result = await pg_db_proxy.fetchval(
                """
                SELECT EXISTS (SELECT
                               FROM information_schema.tables
                               WHERE table_schema = 'public'
                                 AND table_name = $1)
                """,
                self.config.table_name
            )

            if result:
                log.info(f"DLQ table '{self.config.table_name}' verified")
            else:
                log.warning(f"DLQ table '{self.config.table_name}' does not exist")
                # You could create the table here if needed

        except Exception as e:
            log.error(f"Error verifying DLQ table: {e}")
            # Don't fail initialization on table check error

    async def start(self) -> None:
        """Start the background processor"""
        if self._running:
            log.debug("DLQ Service already running")
            return

        if not self.config.enabled:
            log.info("DLQ Service is disabled in configuration")
            return

        self._running = True
        self._processor_task = asyncio.create_task(
            self._process_queue(),
            name="dlq-processor"
        )
        log.info("DLQ Service started")

    async def stop(self) -> None:
        """Gracefully stop the service"""
        if not self._running:
            return

        log.info("Stopping DLQ Service...")
        self._running = False

        # Process remaining items
        if self._current_batch:
            await self._flush_batch(self._current_batch)

        # Cancel processor task
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        self._initialized = False
        log.info(f"DLQ Service stopped. Final metrics: {self.get_metrics()}")

    async def record_failure(
            self,
            source: str,
            event: Dict[str, Any],
            error: Exception,
            context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a failed event to DLQ (non-blocking)

        Args:
            source: Source system (event_processor, outbox, etc.)
            event: The failed event data
            error: The exception that caused the failure
            context: Additional context (topic, consumer, etc.)
        """
        if not self.config.enabled:
            return

        # Ensure service is initialized
        if not self._initialized:
            log.warning("DLQ Service not initialized, attempting to initialize...")
            try:
                await self.initialize()
            except Exception as e:
                log.error(f"Failed to initialize DLQ Service: {e}")
                return

        self._metrics.received += 1

        # Create DLQ entry
        dlq_entry = self._create_dlq_entry(source, event, error, context)

        # Update metrics
        self._update_metrics(dlq_entry)

        # Update external metrics collector
        category = dlq_entry.get("dlq_category", "unknown")
        self.metrics_collector.record_event_received(source, category)

        try:
            # Non-blocking - just put in queue
            self._queue.put_nowait(dlq_entry)

            # Track high watermark
            current_size = self._queue.qsize()
            if current_size > self._metrics.queue_high_watermark:
                self._metrics.queue_high_watermark = current_size
                self.metrics_collector.update_queue_high_watermark(current_size)

            # Check if we need emergency persist
            if current_size >= self.config.emergency_persist_threshold:
                asyncio.create_task(self._emergency_persist())

        except QueueFull:
            self._metrics.dropped += 1
            self.metrics_collector.record_event_dropped()

            if self.config.log_dropped_events:
                log.warning(
                    f"DLQ queue full! Dropped event from {source}. "
                    f"Total dropped: {self._metrics.dropped}"
                )

            # Emergency persist for critical events
            if self._is_critical_event(dlq_entry):
                await self._emergency_persist_single(dlq_entry)

            # Alert if threshold exceeded
            if self._metrics.dropped >= self.config.dropped_events_threshold:
                log.error(
                    f"DLQ dropped events threshold exceeded: {self._metrics.dropped}"
                )

    async def _process_queue(self) -> None:
        """Background task to process the queue"""
        log.info("DLQ processor started")

        while self._running:
            try:
                # Wait for event or timeout
                timeout = self.config.flush_interval_seconds

                try:
                    entry = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=timeout
                    )
                    self._current_batch.append(entry)
                except asyncio.TimeoutError:
                    # Timeout - check if we need to flush
                    pass

                # Check flush conditions
                should_flush = self._should_flush_batch()

                if should_flush and self._current_batch:
                    batch_start_time = asyncio.get_event_loop().time()
                    await self._flush_batch(self._current_batch)

                    # Record batch metrics
                    batch_time_ms = (asyncio.get_event_loop().time() - batch_start_time) * 1000
                    self.metrics_collector.record_batch_processed(
                        len(self._current_batch),
                        batch_time_ms
                    )

                    self._current_batch = []
                    self._last_flush_time = asyncio.get_event_loop().time()

            except asyncio.CancelledError:
                log.info("DLQ processor cancelled")
                break
            except Exception as e:
                self._metrics.errors += 1
                self._metrics.last_error_time = datetime.now(timezone.utc)
                self.metrics_collector.record_error()
                log.error(f"Error in DLQ processor: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause on error

        # Final flush on shutdown
        if self._current_batch:
            await self._flush_batch(self._current_batch)

        log.info("DLQ processor stopped")

    def _should_flush_batch(self) -> bool:
        """Check if batch should be flushed"""
        if not self._current_batch:
            return False

        # Size-based flush
        if len(self._current_batch) >= self.config.batch_size:
            return True

        # Time-based flush
        elapsed = asyncio.get_event_loop().time() - self._last_flush_time
        if elapsed >= self.config.flush_interval_seconds:
            return True

        # Max wait time exceeded
        if elapsed >= self.config.max_batch_wait_seconds:
            return True

        return False

    async def _flush_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Process and persist a batch of DLQ entries"""
        if not batch:
            return

        batch_size = len(batch)
        log.debug(f"Flushing DLQ batch of {batch_size} entries")

        # 1. Forward to Kafka (if enabled)
        if self._should_forward_to_kafka():
            await self._forward_batch_to_kafka(batch)

        # 2. Persist to database
        if self._should_persist_to_db():
            await self._persist_batch_to_db(batch)

        # Update metrics
        self._metrics.processed += batch_size
        self._metrics.total_batches += 1
        self._metrics.average_batch_size = (
                (self._metrics.average_batch_size * (self._metrics.total_batches - 1) + batch_size) /
                self._metrics.total_batches
        )
        self._metrics.last_flush_time = datetime.now(timezone.utc)

        # Update external metrics
        for _ in range(batch_size):
            self.metrics_collector.record_event_processed()

    async def _forward_batch_to_kafka(self, batch: List[Dict[str, Any]]) -> None:
        """Forward batch to Kafka for real-time monitoring"""
        if not self.event_bus:
            return

        for entry in batch:
            try:
                # Prepare event for Kafka
                kafka_event = self._prepare_kafka_event(entry)

                # Send to DLQ topic
                await self.event_bus.publish(
                    self.config.kafka_topic,
                    kafka_event
                )

                self._metrics.kafka_sent += 1

            except Exception as e:
                log.error(f"Failed to forward DLQ event to Kafka: {e}")
                self._metrics.errors += 1
                self.metrics_collector.record_kafka_error()

    async def _persist_batch_to_db(self, batch: List[Dict[str, Any]]) -> None:
        """Persist batch to database efficiently"""
        if not batch:
            return

        try:
            async with transaction():
                # Build batch insert query
                await self._execute_batch_insert(batch)
                self._metrics.db_persisted += len(batch)

        except Exception as e:
            log.error(f"Failed to persist DLQ batch to database: {e}", exc_info=True)
            self._metrics.errors += 1
            self.metrics_collector.record_db_error()

            # Try individual inserts as fallback
            for entry in batch:
                try:
                    await self._persist_single_entry(entry)
                    self._metrics.db_persisted += 1
                except Exception as entry_error:
                    log.error(f"Failed to persist individual DLQ entry: {entry_error}")

    async def _execute_batch_insert(self, batch: List[Dict[str, Any]]) -> None:
        """Execute batch insert query"""
        # Prepare values for batch insert
        values = []
        placeholders = []

        for i, entry in enumerate(batch):
            base_idx = i * 20  # 20 parameters per row

            # Create placeholders for this row
            row_placeholders = [f"${j}" for j in range(base_idx + 1, base_idx + 21)]
            placeholders.append(f"({', '.join(row_placeholders)})")

            # Extract values in correct order
            values.extend([
                self._safe_uuid(entry.get("original_event_id")),
                entry.get("event_type"),
                entry.get("topic_name"),
                json.dumps(entry.get("raw_payload", {})),
                entry.get("error_message"),
                entry.get("error_type"),
                entry.get("consumer_name"),
                entry.get("retry_count", 0),
                entry.get("dlq_reason"),
                entry.get("dlq_category"),
                entry.get("recoverable", True),
                entry.get("source_system"),
                entry.get("original_topic"),
                self._safe_uuid(entry.get("saga_id")),
                self._safe_uuid(entry.get("correlation_id")),
                self._safe_uuid(entry.get("causation_id")),
                self._safe_uuid(entry.get("aggregate_id")),
                entry.get("aggregate_type"),
                entry.get("sequence_number"),
                len(json.dumps(entry.get("raw_payload", {})))
            ])

        # Build and execute query
        query = f"""
            INSERT INTO {self.config.table_name} (
                original_event_id, event_type, topic_name,
                raw_payload, error_message, error_type,
                consumer_name, retry_count, dlq_reason,
                dlq_category, recoverable, source_system,
                original_topic, saga_id, correlation_id,
                causation_id, aggregate_id, aggregate_type,
                sequence_number, payload_size
            ) VALUES {', '.join(placeholders)}
        """

        await pg_db_proxy.execute(query, *values)

    async def _persist_single_entry(self, entry: Dict[str, Any]) -> None:
        """Persist single DLQ entry"""
        await pg_db_proxy.execute(
            f"""
            INSERT INTO {self.config.table_name} (
                original_event_id, event_type, topic_name,
                raw_payload, error_message, error_type,
                consumer_name, retry_count, dlq_reason,
                dlq_category, recoverable, source_system,
                original_topic
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            self._safe_uuid(entry.get("original_event_id")),
            entry.get("event_type"),
            entry.get("topic_name"),
            json.dumps(entry.get("raw_payload", {})),
            entry.get("error_message"),
            entry.get("error_type"),
            entry.get("consumer_name"),
            entry.get("retry_count", 0),
            entry.get("dlq_reason"),
            entry.get("dlq_category"),
            entry.get("recoverable", True),
            entry.get("source_system"),
            entry.get("original_topic")
        )

    async def _emergency_persist(self) -> None:
        """Emergency persist when queue is nearly full"""
        log.warning("DLQ emergency persist triggered")
        self._metrics.emergency_persists += 1
        self.metrics_collector.record_emergency_persist()

        # Drain up to batch_size items immediately
        emergency_batch = []

        for _ in range(self.config.batch_size):
            try:
                item = self._queue.get_nowait()
                emergency_batch.append(item)
            except asyncio.QueueEmpty:
                break

        if emergency_batch:
            await self._flush_batch(emergency_batch)
            log.info(f"Emergency persisted {len(emergency_batch)} DLQ entries")

    async def _emergency_persist_single(self, entry: Dict[str, Any]) -> None:
        """Emergency persist for critical single entry"""
        try:
            await self._persist_single_entry(entry)
            self._metrics.emergency_persists += 1
            self.metrics_collector.record_emergency_persist()
            log.warning("Emergency persisted critical DLQ entry")
        except Exception as e:
            log.error(f"Failed to emergency persist critical entry: {e}")

    def _create_dlq_entry(
            self,
            source: str,
            event: Dict[str, Any],
            error: Exception,
            context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a DLQ entry from failure information with poison pill detection"""
        context = context or {}

        # Extract error details
        error_traceback = None
        if log.isEnabledFor(logging.DEBUG):
            error_traceback = traceback.format_exc()

        # Detect if this is a poison pill (non-retriable error)
        error_category, detection_reason = PoisonPillDetector.detect(
            exception=error,
            error_message=str(error)
        )

        is_poison_pill = (error_category == ErrorCategory.POISON_PILL)
        is_transient = (error_category == ErrorCategory.TRANSIENT)

        # Override from context if explicitly set
        if "is_poison_pill" in context:
            is_poison_pill = context["is_poison_pill"]

        # Update internal metrics
        if is_poison_pill:
            self._metrics.poison_pills_detected += 1
        elif is_transient:
            self._metrics.transient_errors += 1

        # Determine recommended action
        if is_poison_pill:
            recommended_action = f"SKIP_RETRY (poison pill: {detection_reason})"
        elif is_transient:
            recommended_action = f"RETRY_WITH_BACKOFF (transient: {detection_reason})"
        else:
            recommended_action = f"RETRY_CAUTIOUSLY (unknown: {detection_reason})"

        # CRITICAL FIX (Nov 9, 2025): Convert UUIDs to strings for JSON serialization
        # Previously UUIDs were stored as objects, causing "Object of type UUID is not JSON serializable" error
        # Now convert all UUIDs to strings immediately to prevent serialization failures
        def uuid_to_str(uuid_val: Optional[uuid.UUID]) -> Optional[str]:
            """Convert UUID to string, return None if None"""
            return str(uuid_val) if uuid_val is not None else None

        # Build DLQ entry
        dlq_entry = {
            "id": str(uuid.uuid4()),
            "source_system": source,
            "original_event_id": uuid_to_str(self._extract_event_id(event)),  # FIX: Convert UUID to str
            "event_type": event.get("event_type", "unknown"),
            "topic_name": context.get("topic", event.get("topic")),
            "raw_payload": event,
            "error_message": str(error)[:1000],  # Truncate to fit DB
            "error_type": type(error).__name__,
            "error_traceback": error_traceback,
            "consumer_name": context.get("consumer_name", context.get("consumer")),
            "retry_count": context.get("retry_count", 0),
            "dlq_reason": self._determine_reason(error, context),
            "dlq_category": self._categorize_error(error),
            "recoverable": self._is_recoverable(error),
            "saga_id": uuid_to_str(self._extract_uuid_field(event, "saga_id")),  # FIX: Convert UUID to str
            "correlation_id": uuid_to_str(self._extract_uuid_field(event, "correlation_id")),  # FIX: Convert UUID to str
            "causation_id": uuid_to_str(self._extract_uuid_field(event, "causation_id")),  # FIX: Convert UUID to str
            "aggregate_id": uuid_to_str(self._extract_uuid_field(event, "aggregate_id")),  # FIX: Convert UUID to str
            "aggregate_type": event.get("aggregate_type"),
            "sequence_number": event.get("sequence_number"),
            "original_topic": context.get("original_topic", context.get("topic")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            # NEW: Poison pill detection fields
            "is_poison_pill": is_poison_pill,
            "is_transient": is_transient,
            "error_category": error_category.value,
            "detection_reason": detection_reason,
            "recommended_action": recommended_action
        }

        # Log poison pill detection
        if is_poison_pill:
            log.warning(
                f"☠️ Poison pill detected in DLQ: {event.get('event_type', 'unknown')} "
                f"- Reason: {detection_reason} - Action: {recommended_action}"
            )

        return dlq_entry

    def _extract_event_id(self, event: Dict[str, Any]) -> Optional[uuid.UUID]:
        """Extract event ID, handling various formats"""
        event_id = event.get("event_id") or event.get("id")
        return self._safe_uuid(event_id)

    def _extract_uuid_field(self, event: Dict[str, Any], field_name: str) -> Optional[uuid.UUID]:
        """Extract UUID field from event"""
        value = event.get(field_name)
        return self._safe_uuid(value)

    def _safe_uuid(self, value: Any) -> Optional[uuid.UUID]:
        """Safely convert value to UUID"""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None

    def _categorize_error(self, error: Exception) -> str:
        """Categorize error for analysis"""
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Timeout errors
        if "timeout" in error_type.lower() or "timeout" in error_msg:
            return DLQCategory.TIMEOUT.value

        # Connection errors
        if any(term in error_type.lower() for term in ["connection", "network"]):
            return DLQCategory.CONNECTION.value
        if any(term in error_msg for term in ["connection", "network", "refused"]):
            return DLQCategory.CONNECTION.value

        # Validation errors
        if any(term in error_type.lower() for term in ["validation", "invalid", "schema"]):
            return DLQCategory.VALIDATION.value
        if any(term in error_msg for term in ["invalid", "validation", "required"]):
            return DLQCategory.VALIDATION.value

        # Authorization errors
        if any(term in error_type.lower() for term in ["permission", "auth", "forbidden"]):
            return DLQCategory.AUTHORIZATION.value
        if any(term in error_msg for term in ["permission", "unauthorized", "forbidden"]):
            return DLQCategory.AUTHORIZATION.value

        # Database errors
        if any(term in error_type.lower() for term in ["database", "sql"]):
            return DLQCategory.DATABASE.value
        if any(term in error_msg for term in ["database", "sql", "constraint"]):
            return DLQCategory.DATABASE.value

        # Serialization errors
        if any(term in error_type.lower() for term in ["json", "serialization", "encode"]):
            return DLQCategory.SERIALIZATION.value

        # External service errors
        if any(term in error_msg for term in ["external", "api", "service"]):
            return DLQCategory.EXTERNAL_SERVICE.value

        # Business logic errors
        if any(term in error_type for term in ["Business", "Domain", "Application"]):
            return DLQCategory.BUSINESS_LOGIC.value

        return DLQCategory.UNKNOWN.value

    def _is_recoverable(self, error: Exception) -> bool:
        """Determine if error is potentially recoverable"""
        # Non-recoverable error types
        non_recoverable_types = {
            "ValidationError", "ValueError", "TypeError",
            "PermissionError", "AuthorizationError",
            "InvalidEventError", "SchemaError",
            "NotImplementedError", "AssertionError"
        }

        error_type = type(error).__name__

        # Check exact type
        if error_type in non_recoverable_types:
            return False

        # Check error message for non-recoverable indicators
        error_msg = str(error).lower()
        non_recoverable_keywords = [
            "invalid", "validation", "permission denied",
            "not authorized", "forbidden", "schema"
        ]

        for keyword in non_recoverable_keywords:
            if keyword in error_msg:
                return False

        # Default to recoverable
        return True

    def _determine_reason(self, error: Exception, context: Optional[Dict[str, Any]]) -> str:
        """Determine DLQ reason"""
        context = context or {}

        # Check context for specific reasons
        if context.get("circuit_breaker_open"):
            return DLQReason.CIRCUIT_BREAKER_OPEN.value

        if context.get("rate_limited"):
            return DLQReason.RATE_LIMIT_EXCEEDED.value

        if context.get("max_retries_exceeded"):
            return DLQReason.MAX_RETRIES_EXCEEDED.value

        # Check error type
        error_type = type(error).__name__

        if "Timeout" in error_type:
            return DLQReason.TIMEOUT_EXCEEDED.value

        if "Validation" in error_type:
            return DLQReason.VALIDATION_FAILED.value

        if "NotFound" in error_type or "Handler" in error_type:
            return DLQReason.HANDLER_NOT_FOUND.value

        # Check error message
        error_msg = str(error).lower()

        if "dependency" in error_msg or "service unavailable" in error_msg:
            return DLQReason.DEPENDENCY_FAILURE.value

        # Default reason
        return DLQReason.PROCESSING_FAILED.value

    def _is_critical_event(self, entry: Dict[str, Any]) -> bool:
        """Check if event is critical and should be emergency persisted"""
        # Saga events are critical
        if entry.get("saga_id"):
            return True

        # Financial events are critical
        event_type = entry.get("event_type", "").lower()
        critical_patterns = ["order", "trade", "payment", "withdrawal", "deposit"]

        for pattern in critical_patterns:
            if pattern in event_type:
                return True

        return False

    def _should_forward_to_kafka(self) -> bool:
        """Check if should forward to Kafka"""
        if self.config.storage_mode == DLQStorageMode.DATABASE_ONLY:
            return False
        return self.config.enable_kafka_forward and self.event_bus is not None

    def _should_persist_to_db(self) -> bool:
        """Check if should persist to database"""
        return self.config.storage_mode != DLQStorageMode.KAFKA_ONLY

    def _prepare_kafka_event(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare DLQ entry for Kafka"""
        # Remove fields that don't need to go to Kafka
        kafka_event = entry.copy()
        kafka_event.pop("error_traceback", None)
        kafka_event.pop("context", None)

        # Ensure event_id
        if "event_id" not in kafka_event:
            kafka_event["event_id"] = kafka_event.get("id", str(uuid.uuid4()))

        # Add event type for routing
        kafka_event["event_type"] = "DLQEvent"

        return kafka_event

    def _update_metrics(self, entry: Dict[str, Any]) -> None:
        """Update internal metrics"""
        # By source
        source = entry.get("source_system", "unknown")
        self._metrics.by_source[source] = self._metrics.by_source.get(source, 0) + 1

        # By category
        category = entry.get("dlq_category", "unknown")
        self._metrics.by_category[category] = self._metrics.by_category.get(category, 0) + 1

        # By reason
        reason = entry.get("dlq_reason", "unknown")
        self._metrics.by_reason[reason] = self._metrics.by_reason.get(reason, 0) + 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics from both internal and external collectors"""
        # Get external metrics
        external_metrics = self.metrics_collector.get_metrics()

        # Combine with internal metrics
        return {
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "received": self._metrics.received,
            "processed": self._metrics.processed,
            "dropped": self._metrics.dropped,
            "errors": self._metrics.errors,
            "kafka_sent": self._metrics.kafka_sent,
            "db_persisted": self._metrics.db_persisted,
            "emergency_persists": self._metrics.emergency_persists,
            "queue_size": self._queue.qsize(),
            "queue_capacity": self.config.queue_size,
            "queue_usage_percent": (self._queue.qsize() / self.config.queue_size) * 100,
            "queue_high_watermark": self._metrics.queue_high_watermark,
            "by_source": dict(self._metrics.by_source),
            "by_category": dict(self._metrics.by_category),
            "by_reason": dict(self._metrics.by_reason),
            "average_batch_size": round(self._metrics.average_batch_size, 2),
            "total_batches": self._metrics.total_batches,
            "last_flush_time": self._metrics.last_flush_time.isoformat() if self._metrics.last_flush_time else None,
            "last_error_time": self._metrics.last_error_time.isoformat() if self._metrics.last_error_time else None,
            "storage_mode": self.config.storage_mode.value,
            # External metrics
            "external_metrics": external_metrics
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of DLQ service"""
        # Get external health status
        external_health = self.metrics_collector.get_health_status()

        metrics = self.get_metrics()

        # Determine health
        is_healthy = external_health["healthy"]
        issues = external_health["alerts"]

        # Check if service is initialized
        if self.config.enabled and not self._initialized:
            is_healthy = False
            issues.append({
                "level": "critical",
                "message": "Service enabled but not initialized"
            })

        # Check queue usage
        if metrics["queue_usage_percent"] > 80:
            issues.append({
                "level": "warning",
                "message": f"Queue usage high: {metrics['queue_usage_percent']:.1f}%",
                "threshold": "80%"
            })
            if metrics["queue_usage_percent"] > 95:
                is_healthy = False

        # Check if service is running
        if self.config.enabled and self._initialized and not self._running:
            is_healthy = False
            issues.append({
                "level": "critical",
                "message": "Service initialized but not running"
            })

        return {
            "healthy": is_healthy,
            "initialized": self._initialized,
            "running": self._running,
            "issues": issues,
            "metrics": metrics
        }


# Factory function for creating DLQ service
def create_dlq_service(
        profile: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        metrics_collector: Optional[DLQMetricsCollector] = None
) -> DLQService:
    """
    Create DLQ service with specified profile

    Args:
        profile: Configuration profile name
        event_bus: EventBus instance for Kafka forwarding
        metrics_collector: Optional metrics collector
    """
    config = get_dlq_config(profile)
    return DLQService(
        config=config,
        event_bus=event_bus,
        metrics_collector=metrics_collector
    )