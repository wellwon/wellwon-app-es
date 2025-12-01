# app/infra/consumers/event_processor.py
# =============================================================================
# File: app/infra/consumers/event_processor.py
# Description: Event processor with CQRS buses and sync projections awareness
# UPDATED: Enhanced race condition protection for broker connections
# FIXED: Better handling of sync events and improved deduplication
# =============================================================================

import asyncio
import logging
import time
import uuid
import json
from typing import Dict, Any, Optional, Set, TYPE_CHECKING, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from app.infra.event_bus.event_bus import EventBus
from app.infra.event_store.sequence_tracker import EventSequenceTracker, OutOfOrderEventError, DuplicateEventError
from app.infra.persistence.pg_client import db as pg_db_proxy, transaction
from app.infra.persistence.redis_client import redis_client, safe_get, safe_set
from app.infra.worker_core.event_processor.domain_registry import DomainRegistry
from app.infra.worker_core.worker_config import (
    MAX_RETRIES, RETRY_DELAY_BASE_S, DLQ_TOPIC,
    PROCESSED_EVENTS_TABLE, WORKER_INSTANCE_ID
)

# CQRS imports
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus

# Type checking imports
if TYPE_CHECKING:
    from app.infra.event_store.dlq_service import DLQService

log = logging.getLogger("wellwon.worker.event_processor")


class EventProcessingMetrics:
    """Enhanced metrics for event processing"""

    def __init__(self):
        self.processed_events = 0
        self.failed_events = 0
        self.retry_events = 0
        self.dlq_events = 0
        self.out_of_order_events = 0
        self.events_from_outbox = 0
        self.events_from_rebuild = 0
        self.filtered_duplicates = 0
        self.filtered_disconnected = 0
        self.recovery_triggers = 0
        self.sync_events_skipped = 0
        self.last_event_time = None
        self.event_type_counters = defaultdict(int)
        self.topic_counters = defaultdict(int)
        self.error_counters = defaultdict(int)
        self.rebuild_events_by_projection = defaultdict(int)
        self.processing_times = defaultdict(list)
        self.sync_event_warnings = defaultdict(int)
        self.repeated_event_counts = defaultdict(int)
        # NEW: Race condition metrics
        self.race_conditions_detected = 0
        self.connection_state_conflicts = 0
        self.events_reordered = 0

    def record_processed(self, event_type: str, topic: str, processing_time_ms: float = 0):
        """Record successful event processing with timing"""
        self.processed_events += 1
        self.last_event_time = time.time()
        self.event_type_counters[event_type] += 1
        self.topic_counters[topic] += 1

        if processing_time_ms > 0:
            self.processing_times[event_type].append(processing_time_ms)
            if len(self.processing_times[event_type]) > 100:
                self.processing_times[event_type] = self.processing_times[event_type][-100:]

    def record_failed(self, event_type: str, error_type: str):
        """Record failed event processing"""
        self.failed_events += 1
        self.error_counters[error_type] += 1

    def record_rebuild_event(self, projection_name: str):
        """Record rebuild event processing"""
        self.events_from_rebuild += 1
        self.rebuild_events_by_projection[projection_name] += 1

    def record_filtered_duplicate(self):
        """Record filtered duplicate event"""
        self.filtered_duplicates += 1

    def record_filtered_disconnected(self):
        """Record filtered event for disconnected broker"""
        self.filtered_disconnected += 1

    def record_recovery_triggered(self):
        """Record account recovery trigger"""
        self.recovery_triggers += 1

    def record_sync_event_skipped(self, event_type: str):
        """Record when a sync event is skipped in async mode"""
        self.sync_events_skipped += 1
        self.sync_event_warnings[event_type] += 1

    def record_repeated_event(self, event_type: str, aggregate_id: str):
        """Record repeated event processing"""
        key = f"{event_type}:{aggregate_id}"
        self.repeated_event_counts[key] += 1

    def record_race_condition(self):
        """Record detected race condition"""
        self.race_conditions_detected += 1

    def record_connection_conflict(self):
        """Record connection state conflict"""
        self.connection_state_conflicts += 1

    def record_event_reordered(self):
        """Record event reordering"""
        self.events_reordered += 1

    def get_average_processing_time(self, event_type: str) -> float:
        """Get average processing time for an event type"""
        times = self.processing_times.get(event_type, [])
        return sum(times) / len(times) if times else 0.0


class EventProcessor:
    """
    Event processor with CQRS buses integration and sync projections awareness.
    Enhanced with race condition protection for broker connections.

    Args:
        skip_sync_events: If True, skip events marked for sync projection.
                         Should be False for workers (they need to process all events).
                         Only set to True in special cases where you want to skip sync events.
    """

    def __init__(
            self,
            domain_registry: DomainRegistry,
            event_bus: EventBus,
            command_bus: Optional[CommandBus] = None,
            query_bus: Optional[QueryBus] = None,
            saga_manager: Optional[Any] = None,
            sequence_tracker: Optional[EventSequenceTracker] = None,
            metrics: Optional[EventProcessingMetrics] = None,
            sync_events_registry: Optional[Set[str]] = None,
            dlq_service: Optional['DLQService'] = None,
            skip_sync_events: bool = False
    ):
        self.domain_registry = domain_registry
        self.event_bus = event_bus
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.sequence_tracker = sequence_tracker
        self.metrics = metrics or EventProcessingMetrics()
        self.sync_events_registry = sync_events_registry or set()
        self.dlq_service = dlq_service
        self.skip_sync_events = skip_sync_events
        self._stop_requested = False

        # Enhanced deduplication tracking
        self._processed_event_ids: Set[str] = set()
        self._processing_event_ids: Set[str] = set()
        self._event_lock = asyncio.Lock()
        self._max_cache_size = 10000

        # Track duplicate attempts for analysis
        self._duplicate_attempts = defaultdict(lambda: {
            'count': 0,
            'reasons': set(),
            'first_seen': time.time(),
            'last_seen': time.time(),
            'event_type': 'unknown',
            'aggregate_id': None
        })
        self._last_cleanup = time.time()

        # Cache for disconnected broker connections
        self._disconnected_brokers: Set[str] = set()
        self._disconnected_cache_ttl = 300  # 5 minutes

        # Track projection errors by broker connection
        self._projection_errors_by_connection: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._projection_error_threshold = 10

        # Track repeated disconnection events
        self._disconnection_event_cache: Dict[str, float] = {}
        self._disconnection_cooldown = 60  # seconds

        # NEW: Connection state tracking for race detection
        self._connection_states: Dict[str, Dict[str, Any]] = {}
        self._recent_connection_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._race_window_seconds = 2.0  # Configurable window

        # NEW: Pending events for out-of-order handling
        self._pending_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        if saga_manager is not None:
            log.warning("Saga manager provided to worker event processor - ignoring (sagas run in server context)")

        log.info(
            f"EventProcessor initialized with CQRS buses and {len(self.sync_events_registry)} sync events registered"
            f" (skip_sync_events={self.skip_sync_events} - workers should process sync events)"
        )

    def register_sync_events(self, sync_events: Set[str]) -> None:
        """Register sync events that should be processed synchronously in server"""
        self.sync_events_registry.update(sync_events)
        log.info(f"Registered {len(sync_events)} sync events, total: {len(self.sync_events_registry)}")

    def request_stop(self):
        """Request the processor to stop processing"""
        self._stop_requested = True

    def _is_sync_event(self, event_type: str) -> bool:
        """Check if event type should be processed synchronously"""
        return event_type in self.sync_events_registry

    def _extract_broker_connection_id(self, event_dict: Dict[str, Any]) -> Optional[str]:
        """Extract broker connection ID from event"""
        broker_id = (
                event_dict.get("broker_connection_id") or
                event_dict.get("broker_id") or
                event_dict.get("connection_id") or
                (event_dict.get("aggregate_id") if event_dict.get("aggregate_type") == "BrokerConnection" else None)
        )
        return str(broker_id) if broker_id else None

    def _extract_user_id(self, event_dict: Dict[str, Any]) -> Optional[str]:
        """Extract user ID from event"""
        user_id = event_dict.get("user_id")
        return str(user_id) if user_id else None

    async def _is_connection_race_condition(self, event_dict: Dict[str, Any]) -> bool:
        """
        NEW: Detect race conditions in connection state transitions
        """
        event_type = event_dict.get("event_type")
        if event_type not in ["BrokerConnectionEstablished", "BrokerDisconnected"]:
            return False

        connection_id = self._extract_broker_connection_id(event_dict)
        if not connection_id:
            return False

        # Get event timestamp
        event_timestamp = event_dict.get("timestamp") or event_dict.get("stored_at")
        if event_timestamp:
            if isinstance(event_timestamp, str):
                from app.utils.datetime_utils import parse_timestamp_robust
                event_timestamp = parse_timestamp_robust(event_timestamp)
        else:
            event_timestamp = datetime.now(timezone.utc)

        # Track this event
        self._track_connection_event(connection_id, event_type, event_timestamp, event_dict.get("aggregate_version", 0))

        # Check for opposite event within time window
        opposite_event = (
            "BrokerDisconnected" if event_type == "BrokerConnectionEstablished"
            else "BrokerConnectionEstablished"
        )

        recent_events = self._recent_connection_events.get(connection_id, [])

        for recent in recent_events:
            if recent["event_type"] == opposite_event:
                time_diff = abs((event_timestamp - recent["timestamp"]).total_seconds())

                if time_diff < self._race_window_seconds:
                    # Check version to determine which event is newer
                    if event_dict.get("aggregate_version", 0) < recent.get("version", 0):
                        log.warning(
                            f"Race condition detected: {event_type} v{event_dict.get('aggregate_version', 0)} "
                            f"is older than {opposite_event} v{recent.get('version', 0)} "
                            f"(time diff: {time_diff:.2f}s)"
                        )
                        self.metrics.record_race_condition()
                        return True

        # Also check Redis for distributed race detection
        race_key = f"connection_race:{connection_id}:{opposite_event}"
        race_data = await safe_get(race_key)

        if race_data:
            try:
                race_info = json.loads(race_data)
                race_time = datetime.fromisoformat(race_info["timestamp"])
                time_since_race = abs((event_timestamp - race_time).total_seconds())

                if time_since_race < self._race_window_seconds:
                    # Check version
                    if event_dict.get("aggregate_version", 0) < race_info.get("version", 0):
                        log.warning(
                            f"Distributed race detection: {event_type} v{event_dict.get('aggregate_version', 0)} "
                            f"within {time_since_race:.2f}s of {opposite_event} v{race_info.get('version', 0)}"
                        )
                        self.metrics.record_race_condition()
                        return True
            except Exception as e:
                log.debug(f"Error parsing race detection data: {e}")

        # Record this event for future race detection
        await safe_set(
            f"connection_race:{connection_id}:{event_type}",
            json.dumps({
                "event_id": str(event_dict.get("event_id", "")),
                "timestamp": event_timestamp.isoformat(),
                "version": event_dict.get("aggregate_version", 0)
            }),
            ttl_seconds=10  # Short TTL for race detection
        )

        return False

    def _track_connection_event(self, connection_id: str, event_type: str, timestamp: datetime, version: int):
        """Track connection event for race detection"""
        self._recent_connection_events[connection_id].append({
            "event_type": event_type,
            "timestamp": timestamp,
            "version": version
        })

        # Keep only recent events (last 10 or within 5 minutes)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        self._recent_connection_events[connection_id] = [
            e for e in self._recent_connection_events[connection_id][-10:]
            if e["timestamp"] > cutoff_time
        ]

    def _update_connection_state(self, event_dict: Dict[str, Any]):
        """Update internal connection state tracking"""
        connection_id = self._extract_broker_connection_id(event_dict)
        if not connection_id:
            return

        event_type = event_dict.get("event_type")
        timestamp = datetime.now(timezone.utc)

        if event_type == "BrokerConnectionEstablished":
            self._connection_states[connection_id] = {
                "state": "connected",
                "since": timestamp,
                "version": event_dict.get("aggregate_version", 0)
            }
            # Remove from disconnected cache
            self._disconnected_brokers.discard(connection_id)

        elif event_type == "BrokerDisconnected":
            self._connection_states[connection_id] = {
                "state": "disconnected",
                "since": timestamp,
                "version": event_dict.get("aggregate_version", 0)
            }
            # Add to disconnected cache
            self._disconnected_brokers.add(connection_id)

        elif event_type == "BrokerConnectionPurged":
            self._connection_states.pop(connection_id, None)
            self._disconnected_brokers.discard(connection_id)

    async def _trigger_projection_rebuild(
            self,
            domain_name: str,
            broker_connection_id: str,
            error_count: int,
            reason: str
    ) -> None:
        """
        CQRS/ES COMPLIANT: Request projection rebuild from Event Store.

        This is NOT account recovery (that's handled by DataIntegrityMonitor).
        This is projection recovery - replaying events from Event Store to fix broken projections.

        ProjectionRebuilderService will handle the actual rebuild by:
        1. Finding the last successful checkpoint
        2. Replaying events from Event Store
        3. Rebuilding projection state in PostgreSQL
        """
        try:
            rebuild_event = {
                "event_type": "ProjectionRebuildRequested",
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "domain": domain_name,
                "aggregate_filter": {
                    "broker_connection_id": broker_connection_id
                },
                "reason": reason,
                "error_count": error_count,
                "triggered_by": f"event_processor:{WORKER_INSTANCE_ID}",
                "worker_id": WORKER_INSTANCE_ID,
                "priority": "HIGH",
                "rebuild_strategy": "replay_from_checkpoint"
            }

            await self.event_bus.publish("system.projection-rebuilds", rebuild_event)
            self.metrics.record_recovery_triggered()

            log.info(
                f"Requested projection rebuild for domain '{domain_name}' "
                f"(connection: {broker_connection_id}, errors: {error_count}). "
                f"ProjectionRebuilderService will replay events from Event Store."
            )

        except Exception as e:
            log.error(f"Failed to request projection rebuild: {e}")

    async def _should_skip_event(
            self,
            event_dict: Dict[str, Any],
            event_uuid: uuid.UUID,
            topic: str
    ) -> bool:
        """
        Enhanced filtering logic with sync event awareness
        """
        event_id_str = str(event_uuid)
        event_type = event_dict.get("event_type", "")
        skip_reasons = []

        # 1. Check if already in processing (prevents race conditions)
        if event_id_str in self._processing_event_ids:
            skip_reasons.append("currently_processing")

        # 2. Check if already processed (cached check)
        if event_id_str in self._processed_event_ids:
            skip_reasons.append("already_processed_cache")

        # 3. Database check for processed events (only if not in cache)
        if not skip_reasons:
            try:
                is_processed = await self._is_event_already_processed(event_uuid)
                if is_processed:
                    skip_reasons.append("already_processed_db")
                    self._processed_event_ids.add(event_id_str)
            except Exception as e:
                log.warning(f"Error checking processed status for {event_uuid}: {e}")

        # 4. Check if this is a sync event and we're configured to skip them
        if self.skip_sync_events and self._is_sync_event(event_type):
            skip_reasons.append("sync_event_skipped")
            self.metrics.record_sync_event_skipped(event_type)

            if self.metrics.sync_event_warnings[event_type] == 1:
                log.warning(
                    f"Sync event '{event_type}' being skipped. "
                    "This is unusual - workers typically process all events."
                )

        # 5. Check for special event markers
        if event_dict.get("_skip_worker_processing", False):
            skip_reasons.append("marked_for_skip")

        # 6. Filter system events that don't need processing
        skip_event_types = {
            "WorkerProcessingFailed", "WorkerHeartbeat", "WorkerStarted", "WorkerStopped"
        }

        virtual_broker_events = {
            "VirtualBrokerReadyForDiscovery",
            "VirtualBrokerUserConnected",
            "BrokerConnectionStatusReset"
        }

        if event_type in skip_event_types:
            skip_reasons.append("system_event")

        # 7. Enhanced filtering for repeated disconnection events
        if event_type == "BrokerDisconnected":
            broker_connection_id = self._extract_broker_connection_id(event_dict)
            if broker_connection_id:
                current_time = time.time()
                last_processed = self._disconnection_event_cache.get(broker_connection_id, 0)

                if current_time - last_processed < self._disconnection_cooldown:
                    skip_reasons.append("disconnection_cooldown")
                    log.debug(
                        f"Skipping repeated BrokerDisconnected for {broker_connection_id} "
                        f"(cooldown: {self._disconnection_cooldown}s)"
                    )
                else:
                    self._disconnection_event_cache[broker_connection_id] = current_time

        # 8. Comprehensive filtering for disconnected broker events
        broker_connection_id = event_dict.get("broker_connection_id")

        broker_event_types = {
            'BrokerConnectionHealthChecked',
            'BrokerConnectionHealthUpdated',
            'BrokerConnectionModuleHealthChanged',
            'BrokerConnectionMetricsUpdated',
            'BrokerConnectionStatusUpdate',
            'BrokerConnectionAttemptFailed',
            'BrokerTokensSuccessfullyRefreshed',
            'BrokerApiEndpointConfigured'
        }

        if (event_type in broker_event_types and
                broker_connection_id and
                event_type not in virtual_broker_events):

            if str(broker_connection_id) in self._disconnected_brokers:
                skip_reasons.append("disconnected_broker_event")
                self.metrics.record_filtered_disconnected()
                log.debug(f"Skipping {event_type} for disconnected broker {broker_connection_id}")

            else:
                is_connected = event_dict.get('connected', True)
                is_healthy = event_dict.get('is_healthy', True)
                status = str(event_dict.get('new_status', event_dict.get('status', ''))).upper()
                health_status = str(event_dict.get('health_status', '')).lower()
                last_connection_status = str(event_dict.get('last_connection_status', '')).upper()

                is_disconnected = (
                        not is_connected or
                        status == 'DISCONNECTED' or
                        last_connection_status == 'DISCONNECTED' or
                        (
                                    event_type == 'BrokerConnectionHealthChecked' and not is_healthy and 'disconnect' in health_status)
                )

                if is_disconnected:
                    skip_reasons.append("disconnected_broker_indicator")
                    self.metrics.record_filtered_disconnected()
                    log.debug(
                        f"Skipping {event_type} for broker {broker_connection_id} with disconnection indicators: "
                        f"connected={is_connected}, status={status}, health_status={health_status}"
                    )
                    self._disconnected_brokers.add(str(broker_connection_id))

        # Track duplicate attempts for analysis
        if skip_reasons:
            aggregate_id = event_dict.get("aggregate_id")
            self._duplicate_attempts[event_id_str]['count'] += 1
            self._duplicate_attempts[event_id_str]['reasons'].update(skip_reasons)
            self._duplicate_attempts[event_id_str]['event_type'] = event_type
            self._duplicate_attempts[event_id_str]['aggregate_id'] = aggregate_id
            self._duplicate_attempts[event_id_str]['last_seen'] = time.time()

            if self._duplicate_attempts[event_id_str]['count'] > 3 and "sync_event_skipped" not in skip_reasons:
                log.warning(
                    f"Event {event_id_str} attempted {self._duplicate_attempts[event_id_str]['count']} times. "
                    f"Reasons: {skip_reasons}, Type: {event_type}"
                )

            if aggregate_id:
                self.metrics.record_repeated_event(event_type, str(aggregate_id))

            self.metrics.record_filtered_duplicate()
            log.debug(f"Skipping event {event_id_str}: {skip_reasons}")
            return True

        # Track special event types
        if event_dict.get("_from_outbox", False):
            self.metrics.events_from_outbox += 1
            log.debug(f"Processing outbox event {event_uuid}")

        if event_dict.get("_from_projection_rebuild", False):
            projection_name = event_dict.get("_rebuild_projection", "unknown")
            self.metrics.record_rebuild_event(projection_name)
            log.debug(f"Processing rebuild event {event_uuid} from projection: {projection_name}")

        return False

    async def _update_disconnected_brokers_cache(self, event_dict: Dict[str, Any]) -> None:
        """Update the disconnected brokers cache based on events"""
        event_type = event_dict.get("event_type", "")
        broker_connection_id = self._extract_broker_connection_id(event_dict)

        if not broker_connection_id:
            return

        broker_connection_id_str = str(broker_connection_id)

        if event_type == "BrokerDisconnected":
            self._disconnected_brokers.add(broker_connection_id_str)
            log.info(f"Added broker {broker_connection_id} to disconnected cache")
            await self._clear_broker_subscriptions(broker_connection_id_str)

        elif event_type == "BrokerConnectionEstablished":
            if broker_connection_id_str in self._disconnected_brokers:
                self._disconnected_brokers.discard(broker_connection_id_str)
                log.info(f"Removed broker {broker_connection_id} from disconnected cache (connection established)")

        elif event_type == "BrokerConnectionHealthUpdated":
            new_status = event_dict.get("new_status")
            # Status values in DB are lowercase
            if new_status and str(new_status).lower() == "connected":
                if broker_connection_id_str in self._disconnected_brokers:
                    self._disconnected_brokers.discard(broker_connection_id_str)
                    log.info(
                        f"Removed broker {broker_connection_id} from disconnected cache (health update shows connected)")
            elif new_status and str(new_status).lower() == "disconnected":
                self._disconnected_brokers.add(broker_connection_id_str)
                log.info(
                    f"Added broker {broker_connection_id} to disconnected cache (health update shows disconnected)")

        elif event_type == "VirtualBrokerUserConnected":
            if broker_connection_id_str in self._disconnected_brokers:
                self._disconnected_brokers.discard(broker_connection_id_str)
                log.info(f"Removed virtual broker {broker_connection_id} from disconnected cache")

        elif event_type == "BrokerConnectionStatusReset":
            if broker_connection_id_str in self._disconnected_brokers:
                self._disconnected_brokers.discard(broker_connection_id_str)
                log.info(f"Removed broker {broker_connection_id} from disconnected cache (status reset)")

    async def _clear_broker_subscriptions(self, broker_connection_id: str) -> None:
        """Clear any pending events for a disconnected broker"""
        log.debug(f"Clearing pending events for disconnected broker {broker_connection_id}")

    async def _queue_pending_event(self, event_dict: Dict[str, Any], domain_name: str):
        """Queue out-of-order event for later processing"""
        key = f"{domain_name}:{event_dict.get('aggregate_id', 'unknown')}"
        self._pending_events[key].append(event_dict)

        # Limit pending events
        if len(self._pending_events[key]) > 100:
            oldest = self._pending_events[key].pop(0)
            log.warning(f"Dropping old pending event {oldest.get('event_id')}")

    async def _check_pending_events(self, domain_name: str):
        """Check if any pending events can now be processed"""
        keys_to_check = [k for k in self._pending_events.keys() if k.startswith(f"{domain_name}:")]

        for key in keys_to_check:
            pending = self._pending_events.get(key, [])
            if not pending:
                continue

            # Sort by version/sequence
            pending.sort(key=lambda e: e.get("sequence_number", e.get("aggregate_version", 0)))

            processed = []
            for event in pending[:]:
                try:
                    # Create a fresh context for processing
                    await self.process_event(
                        event.get("topic", "unknown"),
                        event,
                        event.get("consumer_id", "unknown"),
                        from_event_store=event.get("from_event_store", False)
                    )
                    processed.append(event)
                except Exception as e:
                    log.debug(f"Pending event still cannot be processed: {e}")
                    break

            # Remove processed events
            for event in processed:
                pending.remove(event)

            if not pending:
                del self._pending_events[key]

    async def process_event(
            self,
            topic: str,
            event_dict: Dict[str, Any],
            consumer_id: str,
            from_event_store: bool = False
    ) -> None:
        """
        Process event with proper deduplication and SINGLE domain processing.
        Enhanced with race condition protection.
        """
        if self._stop_requested:
            log.info("Event processing stopped by request")
            return

        processing_start = time.time()

        # Validate event
        event_id_str = str(event_dict.get("event_id", ""))
        event_type = str(event_dict.get("event_type", "unknown"))

        if not event_id_str:
            log.error(f"Event missing 'event_id'. Topic: {topic}. Sending to DLQ.")
            # Send malformed event to DLQ (FIX 2025-11-14)
            await self._send_malformed_event_to_dlq(
                event_dict=event_dict,
                topic=topic,
                consumer_id=consumer_id,
                error_reason="Missing event_id field"
            )
            return

        try:
            event_uuid = uuid.UUID(event_id_str)
        except ValueError:
            log.error(f"Invalid event ID '{event_id_str}'. Expected UUID format. Sending to DLQ.")
            # Send malformed event to DLQ (FIX 2025-11-14)
            await self._send_malformed_event_to_dlq(
                event_dict=event_dict,
                topic=topic,
                consumer_id=consumer_id,
                error_reason=f"Invalid event_id format: '{event_id_str}' (expected UUID)"
            )
            return

        # Update connection state tracking
        self._update_connection_state(event_dict)

        # Update disconnected brokers cache
        await self._update_disconnected_brokers_cache(event_dict)

        # NEW: Check for connection race conditions
        if await self._is_connection_race_condition(event_dict):
            log.warning(f"Skipping event {event_uuid} due to connection race condition")
            self.metrics.record_connection_conflict()
            await self._mark_event_as_processed(
                event_uuid, consumer_id, event_type, topic, "race_condition_skipped"
            )
            return

        # Enhanced filtering with proper locking
        if await self._should_skip_event(event_dict, event_uuid, topic):
            return

        # Atomic check-and-set for processing
        async with self._event_lock:
            if event_id_str in self._processing_event_ids:
                log.debug(f"Event {event_id_str} already being processed by another task")
                return

            if event_id_str in self._processed_event_ids:
                log.debug(f"Event {event_id_str} already processed (cache hit)")
                return

            # Mark as processing
            self._processing_event_ids.add(event_id_str)

        try:
            # Check if this is a sync event that was not skipped (for logging)
            if self._is_sync_event(event_type) and not self.skip_sync_events:
                log.debug(f"Processing sync event {event_type} in async mode (skip_sync_events=False)")

            log.debug(f"Processing event {event_uuid} (type: {event_type}, topic: {topic})")

            # Get domains for this topic
            domains = self.domain_registry.get_domains_for_topic(topic)

            if not domains:
                log.debug(f"No domains registered for topic '{topic}'")
                await self._mark_event_as_processed(
                    event_uuid, consumer_id, event_type, topic, "no_domains"
                )
                return

            # Process for the FIRST matching domain only to prevent duplicates
            processed_successfully = False
            processing_errors = []

            for domain in domains:
                # Check if this domain handles this event type
                if event_type not in domain.event_models:
                    log.debug(f"Domain '{domain.name}' doesn't handle event type '{event_type}'")
                    continue

                # CRITICAL FIX: Allow None event models for acknowledgment-only domains (like saga_notifications)
                # These domains use handle_event() to acknowledge/log events without full projection
                # Don't skip - let the domain's handle_event process it
                if domain.event_models.get(event_type) is None:
                    log.debug(f"Domain '{domain.name}' has None/placeholder for event type '{event_type}' - will use handle_event for acknowledgment")
                    # Don't continue - allow processing with handle_event below

                if not domain.projector_instance:
                    log.warning(f"No projector instance for domain '{domain.name}'")
                    continue

                # Process with ONLY ONE domain to prevent duplicates
                try:
                    log.debug(f"Processing {event_type} for domain '{domain.name}' from topic '{topic}'")

                    # Check sequence if enabled
                    if self.sequence_tracker and domain.enable_sequence_tracking:
                        aggregate_id = uuid.UUID(event_dict.get("aggregate_id", str(event_uuid)))
                        sequence = event_dict.get("sequence_number") or event_dict.get("aggregate_version", 1)

                        try:
                            should_process = await self.sequence_tracker.check_and_update_sequence(
                                aggregate_id=aggregate_id,
                                projection_name=f"{domain.name}_{event_type}",
                                event_sequence=sequence,
                                event_id=event_uuid,
                                allow_replay=False
                            )

                            if not should_process:
                                log.debug(f"Sequence check failed for {event_type} in domain {domain.name}")
                                continue

                        except OutOfOrderEventError as e:
                            log.warning(f"Out of order event: {e}")
                            self.metrics.out_of_order_events += 1

                            # NEW: Queue for later processing
                            event_dict["topic"] = topic
                            event_dict["consumer_id"] = consumer_id
                            event_dict["from_event_store"] = from_event_store
                            await self._queue_pending_event(event_dict, domain.name)
                            self.metrics.record_event_reordered()
                            continue

                        except DuplicateEventError as e:
                            log.debug(f"Duplicate event: {e}")
                            self.metrics.record_filtered_duplicate()
                            continue

                    # Check if projector uses sync decorators or handle_event
                    has_sync_decorators = False

                    for attr_name in dir(domain.projector_instance):
                        try:
                            attr = getattr(domain.projector_instance, attr_name)
                            if hasattr(attr, '_is_sync_projection'):
                                has_sync_decorators = True
                                break
                        except:
                            continue

                    if has_sync_decorators:
                        # Use projection decorators (SYNC and ASYNC)
                        from app.infra.event_store.event_envelope import EventEnvelope
                        from app.infra.cqrs.projector_decorators import (
                            execute_sync_projections,
                            execute_async_projections,
                            has_sync_handler,
                            has_async_handler
                        )

                        # Create EventEnvelope from event_dict
                        envelope = EventEnvelope.from_partial_data(event_dict)

                        # Collect ALL projector instances for cross-domain events
                        projector_instances = {}
                        for d in self.domain_registry.get_enabled_domains():
                            if d.has_projector() and event_type in d.event_models:
                                projector_instances[d.name] = d.projector_instance
                                log.debug(
                                    f"Added projector instance for domain '{d.name}' to handle {event_type}"
                                )

                        if not projector_instances:
                            log.warning(
                                f"No projector instances found for {event_type}. "
                                f"Enabled domains: {[d.name for d in self.domain_registry.get_enabled_domains()]}"
                            )

                        # Try SYNC projections first (immediate consistency)
                        result = await execute_sync_projections(envelope, projector_instances)

                        # Check if any SYNC handlers were executed
                        if result.get('handlers_executed', 0) == 0:
                            # No sync handlers - try ASYNC projections (eventual consistency)
                            async_result = await execute_async_projections(envelope, projector_instances)

                            if async_result.get('handlers_executed', 0) == 0:
                                # No handlers - event has no projection (check decorators)
                                log.warning(
                                    f"No projection handlers for {event_type} in domain {domain.name}. "
                                    f"Ensure @sync_projection or @async_projection decorator is applied."
                                )
                            else:
                                log.debug(
                                    f"ASYNC projection executed for {event_type}: "
                                    f"{async_result.get('handlers_executed', 0)} handlers"
                                )
                    else:
                        # No decorators found - this should not happen with current architecture
                        log.error(
                            f"Domain {domain.name} projector missing decorators for {event_type}. "
                            f"All projections must use @sync_projection or @async_projection."
                        )
                        continue

                    # Calculate processing time
                    processing_time_ms = (time.time() - processing_start) * 1000

                    # Mark as processed
                    await self._mark_event_as_processed(
                        event_uuid, consumer_id, event_type, topic,
                        f"domain_{domain.name}", processing_time_ms
                    )

                    # Update metrics
                    self.metrics.record_processed(event_type, topic, processing_time_ms)

                    # Track rebuild events separately
                    if event_dict.get("_from_projection_rebuild"):
                        projection_name = event_dict.get("_rebuild_projection", "unknown")
                        self.metrics.record_rebuild_event(projection_name)

                    log.debug(
                        f"Successfully processed event {event_uuid} for domain '{domain.name}' "
                        f"in {processing_time_ms:.2f}ms"
                    )

                    processed_successfully = True

                    # NEW: Check pending events after successful processing
                    await self._check_pending_events(domain.name)

                    break  # Stop after first successful processing

                except Exception as exc:
                    # Check for retriable errors (FK violations, dependencies not ready)
                    from app.common.exceptions.projection_exceptions import RetriableProjectionError

                    if isinstance(exc, RetriableProjectionError):
                        log.warning(
                            f"Retriable error for {event_type} in domain '{domain.name}': {exc}. "
                            f"Queueing for retry."
                        )
                        # Queue for later processing instead of failing
                        event_dict["topic"] = topic
                        event_dict["consumer_id"] = consumer_id
                        event_dict["from_event_store"] = from_event_store
                        await self._queue_pending_event(event_dict, domain.name)
                        self.metrics.record_event_reordered()
                        # Mark as processed - event was handled, just deferred
                        processed_successfully = True
                        break  # Event queued for retry, don't try other domains

                    error_msg = f"Failed to process event {event_uuid} for domain '{domain.name}': {exc}"
                    log.error(error_msg, exc_info=True)
                    processing_errors.append(error_msg)
                    self.metrics.record_failed(event_type, f"domain_{domain.name}_failure")

                    # Track projection errors by broker connection
                    broker_connection_id = self._extract_broker_connection_id(event_dict)

                    if broker_connection_id and domain.name == "broker_account":
                        self._projection_errors_by_connection[broker_connection_id][domain.name] += 1
                        error_count = self._projection_errors_by_connection[broker_connection_id][domain.name]

                        if error_count >= self._projection_error_threshold:
                            await self._trigger_projection_rebuild(
                                domain.name,
                                broker_connection_id,
                                error_count,
                                f"Projection error threshold exceeded: {error_count} consecutive errors in {domain.name}"
                            )
                            # Reset counter after requesting rebuild
                            self._projection_errors_by_connection[broker_connection_id][domain.name] = 0

            if not processed_successfully:
                # No domain could process the event
                error_msg = f"No domain could process event type '{event_type}' from topic '{topic}'"
                if processing_errors:
                    error_msg += f". Errors: {'; '.join(processing_errors)}"

                await self._send_to_dlq(
                    Exception(error_msg),
                    event_uuid, topic, event_dict, consumer_id, event_type
                )

        finally:
            # Always clean up processing state
            async with self._event_lock:
                self._processing_event_ids.discard(event_id_str)
                self._processed_event_ids.add(event_id_str)

                # Cleanup cache if too large
                if len(self._processed_event_ids) > self._max_cache_size:
                    await self._cleanup_cache()

    async def _is_event_already_processed(self, event_id: uuid.UUID) -> bool:
        """Check if event has been processed"""
        try:
            return await pg_db_proxy.fetchval(
                f"SELECT EXISTS (SELECT 1 FROM {PROCESSED_EVENTS_TABLE} WHERE event_id = $1)",
                event_id
            )
        except Exception as e:
            log.error(f"Error checking processed status: {e}")
            return False

    async def _mark_event_as_processed(
            self,
            event_id: uuid.UUID,
            consumer_id: str,
            event_type: str,
            topic: str,
            processing_result: str,
            processing_time_ms: float = 0.0
    ) -> None:
        """Mark event as processed with enhanced metadata"""
        try:
            # Add sync event info
            is_sync_event = self._is_sync_event(event_type)

            await pg_db_proxy.execute(
                f"INSERT INTO {PROCESSED_EVENTS_TABLE} "
                "(event_id, consumer_name, event_type, event_topic, processing_result, "
                "processing_time_ms, processed_at, worker_instance, is_sync_event) "
                "VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8) "
                "ON CONFLICT (event_id) DO NOTHING",
                event_id, consumer_id, event_type, topic, processing_result,
                processing_time_ms, WORKER_INSTANCE_ID, is_sync_event
            )
        except Exception as e:
            log.error(f"Error marking event processed: {e}")

    async def _send_to_dlq(
            self,
            exc: Exception,
            event_id: uuid.UUID,
            topic: str,
            event_dict: Dict[str, Any],
            consumer_id: str,
            event_type: str
    ) -> None:
        """Send failed event to DLQ with enhanced metadata"""
        log.error(f"Final processing failed for event {event_id}: {exc}", exc_info=True)

        self.metrics.record_failed(event_type, type(exc).__name__)
        self.metrics.dlq_events += 1

        # Use centralized DLQ if available
        if self.dlq_service:
            await self.dlq_service.record_failure(
                source="event_processor",
                event=event_dict,
                error=exc,
                context={
                    "topic": topic,
                    "consumer_id": consumer_id,
                    "worker_instance": WORKER_INSTANCE_ID,
                    "was_rebuild_event": event_dict.get("_from_projection_rebuild", False),
                    "rebuild_projection": event_dict.get("_rebuild_projection"),
                    "processing_attempt_count": MAX_RETRIES,
                    "was_sync_event": self._is_sync_event(event_type),
                    "aggregate_id": event_dict.get("aggregate_id"),
                    "sequence_number": event_dict.get("sequence_number"),
                    "race_condition_detected": event_dict.get("aggregate_id") in self._recent_connection_events
                }
            )
        else:
            # Fallback to old method
            dlq_payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "WorkerProcessingFailed",
                "original_event_id": str(event_id),
                "original_event_type": event_type,
                "original_payload_preview": str(event_dict)[:1024],
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "topic": topic,
                "failed_by_consumer": consumer_id,
                "worker_instance": WORKER_INSTANCE_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "was_rebuild_event": event_dict.get("_from_projection_rebuild", False),
                "rebuild_projection": event_dict.get("_rebuild_projection"),
                "processing_attempt_count": MAX_RETRIES,
                "original_aggregate_id": event_dict.get("aggregate_id"),
                "original_sequence_number": event_dict.get("sequence_number"),
                "was_sync_event": self._is_sync_event(event_type)
            }

            try:
                await self.event_bus.publish(DLQ_TOPIC, dlq_payload)
                log.info(f"Event {event_id} sent to DLQ topic")
            except Exception as dlq_e:
                log.error(f"Failed to send to DLQ: {dlq_e}")

        # Mark as processed anyway to prevent infinite retry
        await self._mark_event_as_processed(
            event_id, consumer_id, event_type, topic, "failed_to_dlq"
        )

    async def _send_malformed_event_to_dlq(
            self,
            event_dict: Dict[str, Any],
            topic: str,
            consumer_id: str,
            error_reason: str
    ) -> None:
        """
        Send malformed event to DLQ (events with missing/invalid event_id).
        FIX (2025-11-14): Prevent data loss from silently skipped malformed events.
        """
        self.metrics.dlq_events += 1

        # Use centralized DLQ if available
        if self.dlq_service:
            await self.dlq_service.record_failure(
                source="event_processor",
                event=event_dict,
                error=ValueError(error_reason),
                context={
                    "topic": topic,
                    "consumer_id": consumer_id,
                    "worker_instance": WORKER_INSTANCE_ID,
                    "validation_error": error_reason,
                    "malformed_event": True
                }
            )
        else:
            # Fallback to old method
            dlq_payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "MalformedEventRejected",
                "original_event_id": event_dict.get("event_id", "MISSING"),
                "original_event_type": event_dict.get("event_type", "unknown"),
                "original_payload_preview": str(event_dict)[:1024],
                "error_type": "ValidationError",
                "error_message": error_reason,
                "topic": topic,
                "failed_by_consumer": consumer_id,
                "worker_instance": WORKER_INSTANCE_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "malformed_event": True
            }

            try:
                await self.event_bus.publish(DLQ_TOPIC, dlq_payload)
                log.info(f"Malformed event sent to DLQ: {error_reason}")
            except Exception as dlq_e:
                log.error(f"Failed to send malformed event to DLQ: {dlq_e}")

    async def _cleanup_cache(self) -> None:
        """Periodic cleanup of processed event cache and tracking data"""
        current_time = time.time()

        # Cleanup processed event cache (keep half)
        if len(self._processed_event_ids) > self._max_cache_size:
            events_to_remove = len(self._processed_event_ids) - (self._max_cache_size // 2)
            sorted_events = sorted(self._processed_event_ids)
            for event_id in sorted_events[:events_to_remove]:
                self._processed_event_ids.discard(event_id)

            log.info(f"Cleaned {events_to_remove} events from processed cache")

        # Cleanup duplicate attempts tracking (older than 1 hour)
        if current_time - self._last_cleanup > 3600:
            old_attempts = [
                event_id for event_id, data in self._duplicate_attempts.items()
                if current_time - data['first_seen'] > 3600
            ]
            for event_id in old_attempts:
                del self._duplicate_attempts[event_id]

            if old_attempts:
                log.info(f"Cleaned {len(old_attempts)} old duplicate attempt records")

            # Clean disconnection event cache
            old_disconnections = [
                broker_id for broker_id, last_time in self._disconnection_event_cache.items()
                if current_time - last_time > self._disconnection_cooldown * 2
            ]
            for broker_id in old_disconnections:
                del self._disconnection_event_cache[broker_id]

            # Clean disconnected brokers cache periodically
            if len(self._disconnected_brokers) > 100:
                self._disconnected_brokers = set(list(self._disconnected_brokers)[-50:])
                log.info(f"Cleaned disconnected brokers cache, kept 50 most recent")

            # NEW: Clean old connection events
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            for connection_id in list(self._recent_connection_events.keys()):
                self._recent_connection_events[connection_id] = [
                    e for e in self._recent_connection_events[connection_id]
                    if e["timestamp"] > cutoff_time
                ]
                if not self._recent_connection_events[connection_id]:
                    del self._recent_connection_events[connection_id]

            self._last_cleanup = current_time

    def get_projection_metrics(self) -> Dict[str, Any]:
        """Get metrics about projection health"""
        errors_by_projection = {}

        for conn_id, projections in self._projection_errors_by_connection.items():
            for projection_name, error_count in projections.items():
                if projection_name not in errors_by_projection:
                    errors_by_projection[projection_name] = 0
                errors_by_projection[projection_name] += error_count

        return {
            "errors_by_projection": errors_by_projection,
            "total_processed": self.metrics.processed_events,
            "total_errors": self.metrics.failed_events,
            "events_from_outbox": self.metrics.events_from_outbox,
            "recovery_triggers": self.metrics.recovery_triggers,
            "sync_events_skipped": self.metrics.sync_events_skipped,
            "sync_event_warnings": dict(self.metrics.sync_event_warnings),
            "repeated_event_counts": dict(self.metrics.repeated_event_counts),
            "race_conditions_detected": self.metrics.race_conditions_detected,
            "connection_state_conflicts": self.metrics.connection_state_conflicts,
            "events_reordered": self.metrics.events_reordered,
            "pending_events": sum(len(events) for events in self._pending_events.values())
        }

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        total_duplicates = sum(data['count'] for data in self._duplicate_attempts.values())

        return {
            "processed_events": self.metrics.processed_events,
            "failed_events": self.metrics.failed_events,
            "retry_events": self.metrics.retry_events,
            "system.dlq.events": self.metrics.dlq_events,
            "out_of_order_events": self.metrics.out_of_order_events,
            "events_from_outbox": self.metrics.events_from_outbox,
            "events_from_rebuild": self.metrics.events_from_rebuild,
            "filtered_duplicates": self.metrics.filtered_duplicates,
            "filtered_disconnected": self.metrics.filtered_disconnected,
            "recovery_triggers": self.metrics.recovery_triggers,
            "sync_events_skipped": self.metrics.sync_events_skipped,
            "sync_event_warnings": dict(self.metrics.sync_event_warnings),
            "last_event_time": self.metrics.last_event_time,
            "event_type_counters": dict(self.metrics.event_type_counters),
            "topic_counters": dict(self.metrics.topic_counters),
            "error_counters": dict(self.metrics.error_counters),
            "rebuild_events_by_projection": dict(self.metrics.rebuild_events_by_projection),
            "processed_events_cache": len(self._processed_event_ids),
            "currently_processing": len(self._processing_event_ids),
            "disconnected_brokers_cached": len(self._disconnected_brokers),
            "disconnection_events_cached": len(self._disconnection_event_cache),
            "duplicate_attempts_tracked": len(self._duplicate_attempts),
            "total_duplicate_attempts": total_duplicates,
            "top_duplicate_reasons": self._get_top_duplicate_reasons(),
            "top_repeated_events": self._get_top_repeated_events(),
            "sync_events_registered": len(self.sync_events_registry),
            "skip_sync_events": self.skip_sync_events,
            "worker_instance": WORKER_INSTANCE_ID,
            "race_conditions_detected": self.metrics.race_conditions_detected,
            "connection_state_conflicts": self.metrics.connection_state_conflicts,
            "events_reordered": self.metrics.events_reordered,
            "connection_states_tracked": len(self._connection_states),
            "recent_connection_events": sum(len(events) for events in self._recent_connection_events.values()),
            "pending_events_queued": sum(len(events) for events in self._pending_events.values())
        }

    def _get_top_duplicate_reasons(self) -> Dict[str, int]:
        """Get top reasons for duplicate processing attempts"""
        reason_counts = defaultdict(int)
        for data in self._duplicate_attempts.values():
            for reason in data['reasons']:
                reason_counts[reason] += data['count']
        return dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5])

    def _get_top_repeated_events(self) -> List[Dict[str, Any]]:
        """Get top repeated events by type and aggregate"""
        repeated_events = []
        for key, count in sorted(self.metrics.repeated_event_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            event_type, aggregate_id = key.split(':', 1)
            repeated_events.append({
                "event_type": event_type,
                "aggregate_id": aggregate_id,
                "count": count
            })
        return repeated_events

    def reset_metrics(self) -> None:
        """Reset processing metrics"""
        log.info("Resetting event processing metrics")
        self.metrics = EventProcessingMetrics()
        self._processed_event_ids.clear()
        self._duplicate_attempts.clear()
        self._disconnected_brokers.clear()
        self._disconnection_event_cache.clear()
        self._projection_errors_by_connection.clear()
        self._connection_states.clear()
        self._recent_connection_events.clear()
        self._pending_events.clear()

# =============================================================================
# EOF
# =============================================================================