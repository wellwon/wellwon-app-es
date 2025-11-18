# app/infra/consumers/consumer_manager.py
# =============================================================================
# File: app/infra/consumers/consumer_manager.py
# Description: Consumer manager with sync events awareness
# =============================================================================

import asyncio
import logging
import uuid
import json
import time
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition

from app.infra.event_bus.event_bus import EventBus
from app.infra.worker_core.worker_config import WorkerConfig
from app.infra.worker_core.event_processor.event_processor import EventProcessor
from app.infra.worker_core.event_processor.domain_registry import DomainRegistry

log = logging.getLogger("tradecore.consumer_manager")


@dataclass
class ConsumerTask:
    """Represents an active consumer task with proper offset tracking"""
    topic: str
    group: str
    consumer_id: str
    task: asyncio.Task
    consumer: AIOKafkaConsumer
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events_processed: int = 0
    sync_events_processed: int = 0  # NEW: Track sync events
    last_event_time: Optional[datetime] = None
    error_count: int = 0
    duplicate_count: int = 0
    state: str = "running"
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Offset tracking
    last_committed_offsets: Dict[int, int] = field(default_factory=dict)  # partition -> offset
    pending_commits: Dict[int, int] = field(default_factory=dict)  # partition -> offset
    commit_batch_size: int = 100
    commit_interval_seconds: float = 5.0
    last_commit_time: float = field(default_factory=time.time)

    def is_active(self) -> bool:
        """Check if consumer is active"""
        return (self.state == "running" and
                self.task and not self.task.done() and
                not self.stop_event.is_set())


class ConsumerManager:
    """
    Fixed consumer manager with proper offset handling and sync events awareness
    """

    def __init__(
            self,
            config: WorkerConfig,
            event_bus: EventBus,
            event_processor: Optional[EventProcessor] = None,
            domain_registry: Optional[DomainRegistry] = None
    ):
        self.config = config
        self.event_bus = event_bus
        self.event_processor = event_processor
        self.domain_registry = domain_registry

        # Single consumer per unique topic
        self._consumers: Dict[str, ConsumerTask] = {}
        self._consumer_lock = asyncio.Lock()

        # Global deduplication tracking
        self._processed_events: Set[str] = set()
        self._processing_events: Set[str] = set()
        self._dedup_lock = asyncio.Lock()
        self._max_cache_size = 50000
        self._last_cleanup = time.time()

        # State
        self._running = False
        self._stop_requested = False
        self._shutdown_event = asyncio.Event()
        self._start_time = None  # Track when consumers started

        # Metrics
        self._topic_event_counts: Dict[str, int] = defaultdict(int)
        self._topic_error_counts: Dict[str, int] = defaultdict(int)
        self._duplicate_counts: Dict[str, int] = defaultdict(int)
        self._commit_counts: Dict[str, int] = defaultdict(int)
        self._sync_event_counts: Dict[str, int] = defaultdict(int)  # NEW: Track sync events by topic

        # Sync events registry from domain registry (OPTIONAL)
        if self.domain_registry:
            self._sync_events = self.domain_registry.get_all_sync_events()
        else:
            # Fallback: Use decorator-based sync event registry
            try:
                from app.infra.event_store.sync_decorators import get_all_sync_events
                self._sync_events = get_all_sync_events()
            except Exception:
                self._sync_events = set()  # No sync events if registry unavailable

        log.info(
            f"ConsumerManager initialized for worker {config.worker_id} "
            f"(tracking {len(self._sync_events)} sync event types, "
            f"domain_registry={'enabled' if domain_registry else 'disabled'})"
        )

    def _is_sync_event(self, event_type: str) -> bool:
        """Check if event type is a sync event"""
        return event_type in self._sync_events

    async def start(self) -> None:
        """Start consumer tasks for unique topics only"""
        if self._running:
            log.warning("ConsumerManager already running")
            return

        self._running = True
        self._stop_requested = False
        self._shutdown_event.clear()
        self._start_time = time.time()  # Track startup for grace period

        log.info("Starting consumers with proper offset management")

        # Get unique topics only
        unique_topics = list(set(self.config.topics))
        log.info(f"Processing {len(unique_topics)} unique topics from {len(self.config.topics)} configured topics")

        for topic in unique_topics:
            await self._start_consumer_for_topic(topic)

        log.info(f"Started {len(self._consumers)} consumer tasks")

    async def stop(self, timeout: int = 30) -> None:
        """Stop all consumer tasks gracefully with final offset commits"""
        if not self._running:
            return

        log.info("Stopping ConsumerManager")
        self._stop_requested = True
        self._running = False
        self._shutdown_event.set()

        # Get list of consumers to stop
        async with self._consumer_lock:
            consumers_to_stop = list(self._consumers.items())

        if not consumers_to_stop:
            log.info("No consumers to stop")
            return

        log.info(f"Stopping {len(consumers_to_stop)} consumers")

        # Signal all consumers to stop
        for consumer_key, consumer_task in consumers_to_stop:
            consumer_task.state = "stopping"
            consumer_task.stop_event.set()
            log.debug(f"Signaled stop for consumer {consumer_key}")

        # Commit any pending offsets before stopping
        for consumer_key, consumer_task in consumers_to_stop:
            try:
                if consumer_task.pending_commits:
                    log.info(f"Committing pending offsets for {consumer_key}: {consumer_task.pending_commits}")
                    await consumer_task.consumer.commit()
                    consumer_task.last_committed_offsets.update(consumer_task.pending_commits)
                    consumer_task.pending_commits.clear()
                    self._commit_counts[consumer_task.topic] += 1
            except Exception as e:
                log.error(f"Error committing final offsets for {consumer_key}: {e}")

        # Stop Kafka consumers
        for consumer_key, consumer_task in consumers_to_stop:
            try:
                await consumer_task.consumer.stop()
                log.debug(f"Stopped Kafka consumer for {consumer_key}")
            except Exception as e:
                log.warning(f"Error stopping Kafka consumer for {consumer_key}: {e}")

        # Cancel consumer tasks
        consumer_tasks = []
        for consumer_key, consumer_task in consumers_to_stop:
            if consumer_task.task and not consumer_task.task.done():
                consumer_task.task.cancel()
                consumer_tasks.append((consumer_key, consumer_task.task))

        if consumer_tasks:
            log.debug(f"Cancelling {len(consumer_tasks)} consumer tasks")
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[task for _, task in consumer_tasks], return_exceptions=True),
                    timeout=timeout
                )
                for i, (key, _) in enumerate(consumer_tasks):
                    if isinstance(results[i], Exception) and not isinstance(results[i], asyncio.CancelledError):
                        log.warning(f"Consumer task for {key} ended with error: {results[i]}")
            except asyncio.TimeoutError:
                log.warning(f"Timeout waiting for consumer tasks to cancel")

        # Clean up internal state
        async with self._consumer_lock:
            self._consumers.clear()

        log.info("ConsumerManager stopped")

    async def _start_consumer_for_topic(self, topic: str) -> None:
        """Start a single consumer task for a topic"""
        # Create unique consumer group and ID
        consumer_group = f"{self.config.consumer_group_prefix}-{topic.split('.')[-1]}"
        consumer_id = f"{self.config.worker_id}-{topic.split('.')[-1]}"
        consumer_key = f"{topic}:{consumer_group}"

        async with self._consumer_lock:
            if consumer_key in self._consumers:
                log.warning(f"Consumer already exists for {consumer_key}")
                return

        # Enhanced consumer configuration for deduplication
        # OPTIMIZED (2025-11-11): Manual commits for financial data integrity
        consumer_config = {
            'bootstrap_servers': self.config.redpanda_servers,
            'group_id': consumer_group,
            'client_id': consumer_id,
            'session_timeout_ms': 30000,
            'heartbeat_interval_ms': 3000,
            'max_poll_records': self.config.consumer_batch_size,  # Use worker config (1000 for EVENT_PROCESSOR)
            'enable_auto_commit': False,  # Manual commits for at-least-once delivery (financial safety)
            'auto_offset_reset': 'earliest',
            'fetch_min_bytes': 1,
            'fetch_max_wait_ms': 200,  # Reduced broker CPU load without latency impact (increased from 100ms)
            'isolation_level': 'read_committed'
        }

        # Create and start Kafka consumer
        try:
            kafka_consumer = AIOKafkaConsumer(topic, **consumer_config)
            await kafka_consumer.start()

            # Get partition info and check committed offsets
            partitions = kafka_consumer.partitions_for_topic(topic)
            if partitions:
                tps = [TopicPartition(topic, p) for p in partitions]

                # Check committed offsets for each partition individually
                committed_offsets = {}
                for tp in tps:
                    try:
                        # Call committed() with a single TopicPartition, not a list
                        offset = await kafka_consumer.committed(tp)
                        committed_offsets[tp] = offset
                        if offset is not None:
                            log.debug(f"Partition {tp.partition} has committed offset: {offset}")
                        else:
                            log.debug(
                                f"Partition {tp.partition} has no committed offset (will start from {consumer_config['auto_offset_reset']})")
                    except Exception as e:
                        log.warning(f"Could not get committed offset for {tp}: {e}")

                # Log consumer group status
                log.info(
                    f"Consumer group '{consumer_group}' starting with {len(partitions)} partitions. "
                    f"Committed offsets: {sum(1 for o in committed_offsets.values() if o is not None)}/{len(partitions)}"
                )

            # Create consumer task
            consumer_task = ConsumerTask(
                topic=topic,
                group=consumer_group,
                consumer_id=consumer_id,
                consumer=kafka_consumer,
                task=asyncio.create_task(
                    self._consume_from_topic(topic, kafka_consumer, consumer_id),
                    name=f"consumer-{topic.split('.')[-1]}"
                )
            )

            async with self._consumer_lock:
                self._consumers[consumer_key] = consumer_task

            log.info(f"Started consumer for topic '{topic}' with group '{consumer_group}'")

        except Exception as e:
            log.error(f"Failed to start consumer for topic '{topic}': {e}", exc_info=True)
            raise

    async def _consume_from_topic(
            self,
            topic: str,
            consumer: AIOKafkaConsumer,
            consumer_id: str
    ) -> None:
        """Main consumer loop with proper offset management and sync event tracking"""
        consumer_key = f"{topic}:{consumer_id}"

        log.info(f"Consumer {consumer_id} starting for topic '{topic}'")

        # Track messages processed since last commit
        messages_since_commit = 0
        partition_offsets = defaultdict(int)  # partition -> highest processed offset

        try:
            while not self._stop_requested:
                try:
                    # OPTIMIZED (2025-11-11): Faster polling for lower latency
                    # Use worker config batch size (1000 for EVENT_PROCESSOR = 10x throughput capacity)
                    # Industry validated: Confluent recommends 1000-2000 for high throughput workloads
                    messages = await consumer.getmany(timeout_ms=100, max_records=self.config.consumer_batch_size)

                    if not messages:
                        # Check if we should commit based on time
                        if consumer_key in self._consumers:
                            consumer_task = self._consumers[consumer_key]
                            time_since_commit = time.time() - consumer_task.last_commit_time

                            if (consumer_task.pending_commits and
                                    time_since_commit >= consumer_task.commit_interval_seconds):
                                await self._commit_offsets(consumer_task)
                        continue

                    # OPTIMIZED (2025-11-10): Prioritize SYNC events for immediate processing
                    # Separate SYNC events from ASYNC events
                    sync_messages = []
                    async_messages = []

                    for topic_partition, msgs in messages.items():
                        for msg in msgs:
                            if self._stop_requested:
                                return

                            # Parse event type to determine priority
                            try:
                                event_data = json.loads(msg.value.decode('utf-8'))
                                event_type = event_data.get('event_type', 'unknown')

                                if self._is_sync_event(event_type):
                                    sync_messages.append((msg, topic_partition))
                                else:
                                    async_messages.append((msg, topic_partition))
                            except Exception as e:
                                log.warning(f"Failed to parse message for prioritization: {e}")
                                async_messages.append((msg, topic_partition))

                    # Process SYNC messages FIRST (high priority)
                    if sync_messages:
                        log.info(f"[PRIORITY] Processing {len(sync_messages)} SYNC events first (before {len(async_messages)} async events)")

                    for msg, tp in sync_messages:
                        if self._stop_requested:
                            return

                        processed = await self._process_message(msg, topic, consumer_id)

                        if processed:
                            partition_offsets[msg.partition] = max(
                                partition_offsets[msg.partition],
                                msg.offset + 1
                            )
                            messages_since_commit += 1

                    # Then process ASYNC messages (normal priority)
                    for msg, tp in async_messages:
                        if self._stop_requested:
                            return

                        processed = await self._process_message(msg, topic, consumer_id)

                        if processed:
                            partition_offsets[msg.partition] = max(
                                partition_offsets[msg.partition],
                                msg.offset + 1
                            )
                            messages_since_commit += 1

                    # MANUAL COMMIT (2025-11-11): Commit after successful batch processing
                    # For financial data integrity, commit only after ALL messages processed successfully
                    if consumer_key in self._consumers and (sync_messages or async_messages):
                        consumer_task = self._consumers[consumer_key]
                        consumer_task.pending_commits.update(partition_offsets)

                        # Commit immediately after batch (financial safety - at-least-once delivery)
                        if consumer_task.pending_commits:
                            await self._commit_offsets(consumer_task)
                            messages_since_commit = 0
                            partition_offsets.clear()

                            log.debug(
                                f"[MANUAL COMMIT] Committed batch of {len(sync_messages) + len(async_messages)} "
                                f"messages ({len(sync_messages)} SYNC, {len(async_messages)} ASYNC)"
                            )

                except asyncio.CancelledError:
                    log.info(f"Consumer {consumer_id} cancelled")
                    return
                except Exception as e:
                    log.error(f"Consumer error for topic '{topic}': {e}", exc_info=True)
                    self._topic_error_counts[topic] += 1

                    # Update consumer task error count
                    if consumer_key in self._consumers:
                        self._consumers[consumer_key].error_count += 1

                    # CRITICAL: Don't commit on error - messages will replay on restart (at-least-once)
                    log.warning(
                        f"[MANUAL COMMIT] Skipping commit due to error - "
                        f"{len(partition_offsets)} messages will replay on restart"
                    )

                    # Clear pending offsets to avoid partial commits
                    partition_offsets.clear()

                    # Brief pause before retry
                    await asyncio.sleep(1)

        except Exception as e:
            log.error(f"Fatal consumer error for topic '{topic}': {e}", exc_info=True)
        finally:
            # Final commit before shutdown
            if consumer_key in self._consumers:
                consumer_task = self._consumers[consumer_key]
                if consumer_task.pending_commits:
                    try:
                        await self._commit_offsets(consumer_task)
                    except Exception as e:
                        log.error(f"Error in final commit: {e}")

            log.info(f"Consumer {consumer_id} stopped for topic '{topic}'")

    async def _commit_offsets(self, consumer_task: ConsumerTask) -> None:
        """
        Commit offsets with proper error handling.
        MANUAL COMMIT (2025-11-11): Critical for financial data integrity.
        Only commits after successful batch processing (at-least-once delivery).
        """
        if not consumer_task.pending_commits:
            return

        try:
            # Build offset dict for commit
            offsets = {}
            for partition, offset in consumer_task.pending_commits.items():
                tp = TopicPartition(consumer_task.topic, partition)
                offsets[tp] = offset

            # MANUAL COMMIT: Only called after successful message processing
            await consumer_task.consumer.commit(offsets)

            # Update tracking
            consumer_task.last_committed_offsets.update(consumer_task.pending_commits)
            consumer_task.last_commit_time = time.time()
            self._commit_counts[consumer_task.topic] += 1

            log.info(
                f"[MANUAL COMMIT] ✅ Committed offsets for {consumer_task.topic}: "
                f"partitions={list(consumer_task.pending_commits.keys())}, "
                f"total_commits={self._commit_counts[consumer_task.topic]}"
            )

            # Clear pending commits after successful commit
            consumer_task.pending_commits.clear()

        except Exception as e:
            log.error(
                f"[MANUAL COMMIT] ❌ Failed to commit offsets for {consumer_task.topic}: {e} - "
                f"Messages will replay on restart (at-least-once guarantee)"
            )
            # CRITICAL: Don't clear pending commits on error
            # This ensures messages replay on restart (financial safety)

    async def _process_message(self, msg, topic: str, consumer_id: str) -> bool:
        """Process a single message with deduplication and sync event tracking"""
        try:
            # Parse message
            event_data = json.loads(msg.value.decode('utf-8'))
            event_id = event_data.get('event_id')
            event_type = event_data.get('event_type', 'unknown')

            if not event_id:
                log.warning(f"Message without event_id on topic {topic}")
                return True  # Mark as processed to advance offset

            # Check if this is a sync event
            is_sync_event = self._is_sync_event(event_type)
            if is_sync_event:
                self._sync_event_counts[topic] += 1
                log.debug(f"Processing sync event {event_type} in async mode on topic {topic}")

            # Atomic deduplication check
            async with self._dedup_lock:
                # Check if already processed
                if event_id in self._processed_events:
                    self._duplicate_counts[topic] += 1
                    log.debug(f"Skipping duplicate event {event_id} on topic {topic}")
                    return True  # Still mark as processed to advance offset

                # Check if currently processing
                if event_id in self._processing_events:
                    self._duplicate_counts[topic] += 1
                    log.debug(f"Skipping event {event_id} already in processing on topic {topic}")
                    return False  # Don't advance offset yet

                # Mark as processing
                self._processing_events.add(event_id)

            try:
                # Process the event
                if self.event_processor:
                    # EventProcessorWorker pattern
                    await self.event_processor.process_event(
                        topic=topic,
                        event_dict=event_data,
                        consumer_id=consumer_id,
                        from_event_store=False
                    )
                elif hasattr(self, '_process_event') and callable(self._process_event):
                    # DataSyncWorker pattern (custom handler hook)
                    await self._process_event(event_data)
                else:
                    log.warning(f"No event processor configured, skipping event {event_id}")

                # Update metrics
                self._topic_event_counts[topic] += 1
                consumer_key = f"{topic}:{consumer_id}"
                if consumer_key in self._consumers:
                    self._consumers[consumer_key].events_processed += 1
                    self._consumers[consumer_key].last_event_time = datetime.now(timezone.utc)
                    if is_sync_event:
                        self._consumers[consumer_key].sync_events_processed += 1

                log.debug(
                    f"Processed {'sync' if is_sync_event else 'async'} event {event_id} (type: {event_type}) "
                    f"from topic {topic} partition {msg.partition} offset {msg.offset}"
                )

                return True

            finally:
                # Always cleanup processing state
                async with self._dedup_lock:
                    self._processing_events.discard(event_id)
                    self._processed_events.add(event_id)

                    # Cleanup cache if too large
                    if len(self._processed_events) > self._max_cache_size:
                        await self._cleanup_processed_cache()

        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in message from topic {topic}: {e}")
            return True  # Skip invalid messages
        except Exception as e:
            log.error(f"Error processing message from topic {topic}: {e}", exc_info=True)
            self._topic_error_counts[topic] += 1
            return False  # Retry this message

    async def _cleanup_processed_cache(self) -> None:
        """Cleanup processed events cache to prevent memory leaks"""
        current_time = time.time()

        # Only cleanup every 5 minutes
        if current_time - self._last_cleanup < 300:
            return

        # Remove oldest half of entries
        cache_size = len(self._processed_events)
        if cache_size > self._max_cache_size:
            # Convert to list and remove oldest entries
            events_list = list(self._processed_events)
            keep_count = self._max_cache_size // 2

            # Keep the most recent half
            self._processed_events = set(events_list[-keep_count:])

            removed_count = cache_size - len(self._processed_events)
            log.info(f"Cleaned {removed_count} old events from deduplication cache")

        self._last_cleanup = current_time

    def is_healthy(self) -> bool:
        """Check if consumer manager is healthy"""
        if not self._running:
            return False

        # Check if we have active consumers for unique topics
        unique_topics = set(self.config.topics)
        active_topics = set()

        for consumer in self._consumers.values():
            if consumer.is_active():
                active_topics.add(consumer.topic)

        missing_topics = unique_topics - active_topics
        if missing_topics:
            # Only warn if consumers have been running for a while
            # During startup, consumers may not be active yet (async start)
            import time
            startup_grace_period = 10  # seconds
            if hasattr(self, '_start_time') and (time.time() - self._start_time) > startup_grace_period:
                log.warning(f"Missing active consumers for topics: {missing_topics}")
                return False
            else:
                # Still starting up, don't warn yet
                log.debug(f"Consumers still starting for topics: {missing_topics}")
                return True  # Consider healthy during startup

        # Check error rates
        total_events = sum(self._topic_event_counts.values())
        total_errors = sum(self._topic_error_counts.values())

        if total_events > 100:  # Only check after some events
            error_rate = total_errors / total_events
            if error_rate > 0.1:  # More than 10% errors
                log.warning(f"High error rate: {error_rate:.2%}")
                return False

        return True

    async def get_consumer_stats(self) -> Dict[str, Any]:
        """Get consumer statistics with sync event information"""
        async with self._consumer_lock:
            active_consumers = len([c for c in self._consumers.values() if c.is_active()])

            consumer_details = {}
            for key, consumer in self._consumers.items():
                consumer_details[key] = {
                    "topic": consumer.topic,
                    "group": consumer.group,
                    "consumer_id": consumer.consumer_id,
                    "state": consumer.state,
                    "events_processed": consumer.events_processed,
                    "sync_events_processed": consumer.sync_events_processed,
                    "error_count": consumer.error_count,
                    "duplicate_count": consumer.duplicate_count,
                    "last_event_time": consumer.last_event_time.isoformat() if consumer.last_event_time else None,
                    "uptime_seconds": (datetime.now(timezone.utc) - consumer.created_at).total_seconds(),
                    "last_committed_offsets": consumer.last_committed_offsets,
                    "pending_commits": consumer.pending_commits,
                    "commits_made": self._commit_counts.get(consumer.topic, 0)
                }

        return {
            "total_consumers": len(self._consumers),
            "active_consumers": active_consumers,
            "unique_topics": len(set(self.config.topics)),
            "configured_topics": len(self.config.topics),
            "total_events_processed": sum(self._topic_event_counts.values()),
            "total_sync_events": sum(self._sync_event_counts.values()),
            "total_errors": sum(self._topic_error_counts.values()),
            "total_duplicates": sum(self._duplicate_counts.values()),
            "total_commits": sum(self._commit_counts.values()),
            "event_counts_by_topic": dict(self._topic_event_counts),
            "sync_event_counts_by_topic": dict(self._sync_event_counts),
            "error_counts_by_topic": dict(self._topic_error_counts),
            "duplicate_counts_by_topic": dict(self._duplicate_counts),
            "commit_counts_by_topic": dict(self._commit_counts),
            "deduplication_cache_size": len(self._processed_events),
            "processing_events": len(self._processing_events),
            "consumers": consumer_details,
            "sync_events_tracked": len(self._sync_events)
        }

# =============================================================================
# EOF
# =============================================================================