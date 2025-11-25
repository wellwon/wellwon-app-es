# app/services/saga_service.py
# =============================================================================
# File: app/services/saga_service.py
# Description: Saga service with enhanced race condition detection
# UPDATED: Version-based conflict resolution and tighter race windows
# =============================================================================

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Type, Awaitable, Set, Union, Callable, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from app.infra.saga.saga_manager import SagaManager, BaseSaga
from app.infra.event_bus.event_bus import EventBus
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore
from app.infra.persistence.redis_client import safe_set, safe_get, safe_delete
from app.infra.reliability.distributed_lock import DistributedLockManager

# Import centralized saga config
from app.config.saga_config import saga_config

# Import reliability patterns
from app.infra.reliability.circuit_breaker import (
    CircuitBreakerConfig, get_circuit_breaker
)
from app.infra.reliability.retry import retry_async, RetryConfig
from app.config.reliability_config import ReliabilityConfigs

# Import saga events to register them with @domain_event decorator
from app.infra.saga import saga_events

# Import virtual broker events to register them with @domain_event decorator
# from app.virtual_broker import events as vb_events

# Type checking imports
if TYPE_CHECKING:
    from app.services.infrastructure.projection_rebuilder_service import ProjectionRebuilderService

log = logging.getLogger("wellwon.saga_service")


class SagaPriority(Enum):
    """Priority levels for saga execution"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class PendingSaga:
    """Represents a saga waiting to be executed"""
    saga_class: Type[BaseSaga]
    context: Dict[str, Any]
    original_event: Dict[str, Any]
    description: str
    dedupe_key: Optional[str]
    dedupe_window_seconds: int
    conflict_key: str
    priority: SagaPriority = SagaPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retries: int = 5


@dataclass
class SagaTriggerConfig:
    """Configuration for a saga trigger"""
    event_types: List[str]
    saga_class: Type[BaseSaga]
    context_builder: Callable[[Dict[str, Any]], Dict[str, Any]]
    description: str = ""
    dedupe_key_builder: Optional[Callable[[Dict[str, Any]], str]] = None
    dedupe_window_seconds: int = 300
    should_dedupe: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    fast_track: bool = False
    conflict_key_builder: Optional[Callable[[Dict[str, Any]], str]] = None
    allow_concurrent: bool = True
    pre_trigger_delay_ms: Optional[Union[int, Callable[[Dict[str, Any]], Optional[int]]]] = None
    state_sync_grace_period_ms: Optional[Union[int, Callable[[Dict[str, Any]], Optional[int]]]] = None
    pre_trigger_check: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None
    priority: SagaPriority = SagaPriority.NORMAL
    auto_retry_on_conflict: bool = True
    max_retry_attempts: int = 5


class SagaService:
    """
    Centralized service for saga orchestration with enhanced race condition protection.

    Key improvements:
    - Version-based conflict resolution
    - Tighter race windows (1 second max)
    - Distributed race detection with Redis
    - Connection state validation
    - Smart retry with priority queue
    """

    def __init__(
            self,
            event_bus: EventBus,
            command_bus: CommandBus,
            query_bus: QueryBus,
            event_store: Optional[KurrentDBEventStore] = None,
            instance_id: Optional[str] = None,
            lock_manager: Optional[DistributedLockManager] = None,
            projection_rebuilder: Optional['ProjectionRebuilderService'] = None
    ):
        self.event_bus = event_bus
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.event_store = event_store
        self.instance_id = instance_id or 'default'
        self.lock_manager = lock_manager
        self.projection_rebuilder = projection_rebuilder

        # Validate rebuilder if provided
        if projection_rebuilder:
            self._validate_rebuilder(projection_rebuilder)

        # Saga manager instance
        self.saga_manager: Optional[SagaManager] = None

        # Consumer tasks for event triggers
        self._consumer_tasks: List[asyncio.Task] = []
        self._saga_group = f"saga-triggers-{self.instance_id}"

        # Saga trigger configurations
        self._trigger_configs: Dict[str, List[SagaTriggerConfig]] = {}

        # Duplicate detection
        self._active_sagas: Dict[str, Set[str]] = defaultdict(set)
        self._saga_event_tracker: Dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

        # Conflict prevention - track active sagas per aggregate
        self._active_aggregate_sagas: Dict[str, str] = {}

        # Connection attempt tracking for cold start
        self._recent_connection_attempts: Dict[str, datetime] = {}

        # Track connection/disconnection event ordering with versions
        self._connection_event_sequence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Pending saga queue for smart retry
        self._pending_sagas: Dict[str, List[PendingSaga]] = defaultdict(list)
        self._pending_saga_processor: Optional[asyncio.Task] = None

        # Saga completion listeners
        self._saga_completion_listeners: List[asyncio.Task] = []

        # Circuit breakers for reliability
        self._saga_trigger_circuit_breaker = get_circuit_breaker(
            "saga_trigger",
            CircuitBreakerConfig(
                name="saga_trigger",
                failure_threshold=10,
                reset_timeout_seconds=60,
                half_open_max_calls=3,
                success_threshold=3
            )
        )

        self._event_publish_circuit_breaker = get_circuit_breaker(
            "saga_event_publish",
            CircuitBreakerConfig(
                name="saga_event_publish",
                failure_threshold=5,
                reset_timeout_seconds=30,
                half_open_max_calls=2,
                success_threshold=2
            )
        )

        # Retry configurations
        self._lock_retry_config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            max_delay_ms=1000,
            backoff_factor=2.0,
            jitter=True
        )

        self._redis_retry_config = ReliabilityConfigs.redis_retry()
        self._event_retry_config = ReliabilityConfigs.kafka_retry()

        # State
        self._initialized = False
        self._running = False

        log.info(f"SagaService created for instance: {self.instance_id}")

    @staticmethod
    def _validate_rebuilder(rebuilder: Any) -> None:
        """Validate rebuilder has required methods"""
        required_methods = ['rebuild_projection', 'rebuild_aggregate_projections']

        for method in required_methods:
            if not hasattr(rebuilder, method):
                raise ValueError(
                    f"ProjectionRebuilder missing required method: {method}"
                )

    async def initialize(self) -> None:
        """Initialize the saga service with all protections enabled."""
        if self._initialized:
            log.warning("SagaService already initialized")
            return

        log.info("Initializing SagaService with enhanced protections...")

        # Create distributed lock manager if not provided
        if not self.lock_manager:
            from app.infra.reliability.distributed_lock import DistributedLockManager
            self.lock_manager = DistributedLockManager()

        # Create saga manager with monitoring
        self.saga_manager = SagaManager(
            event_bus=self.event_bus,
            redis_prefix="wellwon_saga:",
            enable_monitoring=True
        )

        # Configure saga manager with CQRS buses
        self.saga_manager.set_command_bus(self.command_bus)
        self.saga_manager.set_query_bus(self.query_bus)

        # Set bidirectional reference for ProjectionRebuilder access
        self.saga_manager.set_parent_service(self)

        # Inject Event Store if available
        if self.event_store:
            self.saga_manager.set_event_store(self.event_store)
            log.info("Event Store injected into Saga Manager for causation tracking")

        # Verify saga manager is properly initialized
        if not self.saga_manager.is_initialized():
            raise RuntimeError("Saga Manager failed to initialize properly")

        # Register all saga types
        self._register_sagas()

        # Configure saga triggers with all protections
        self._configure_triggers()

        # Setup event consumers
        await self._setup_event_consumers()

        # Start pending saga processor if enabled
        if saga_config.pending_queue_enabled:
            self._pending_saga_processor = asyncio.create_task(self._process_pending_sagas_loop())
            log.info(
                f"Started pending saga processor with {saga_config.pending_queue_check_interval_seconds}s interval")

        # Setup saga completion listeners
        await self._setup_saga_completion_listeners()

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_tracking_data())

        # Clean up any stale locks from previous runs
        if saga_config.stale_lock_check_enabled:
            await self._cleanup_stale_locks()

        self._initialized = True
        self._running = True

        log.info("SagaService initialized successfully with all protections enabled")

    def _register_sagas(self) -> None:
        """Register all saga types with the saga manager"""
        # TODO: Create WellWon-specific sagas
        # from app.infra.saga.user_deletion_saga import UserDeletionSaga

        saga_types = [
            # UserDeletionSaga,  # Not yet implemented for WellWon
        ]

        for saga_type in saga_types:
            self.saga_manager.register_saga(saga_type)
            log.info(f"Registered saga type: {saga_type.__name__}")

        log.info("No sagas registered yet - WellWon sagas to be implemented")

    async def _should_trigger_connection_saga(self, event: Dict[str, Any]) -> bool:
        """
        OPTIMIZED: Immediate trigger for virtual brokers with recent disconnection check
        """
        try:
            broker_id = event.get('broker_id', '')
            broker_connection_id = event.get('broker_connection_id')

            # ALWAYS trigger immediately for virtual broker
            if 'virtual' in broker_id.lower():
                log.info(f"Virtual broker - immediate saga trigger")
                return True  # True = should trigger (no dedupe)

            # For real brokers, check if recently disconnected
            if broker_connection_id:
                disconnect_key = f"broker_disconnected:{broker_connection_id}"
                if disconnect_key in self._saga_event_tracker:
                    disconnect_time = self._saga_event_tracker[disconnect_key]
                    time_since_disconnect = (datetime.now(timezone.utc) - disconnect_time).total_seconds()
                    if time_since_disconnect < 10:  # 10 seconds
                        log.warning(f"Skipping connection saga for recently disconnected broker")
                        return False

            return True

        except Exception as e:
            log.error(f"Error in connection saga trigger check: {e}")
            return True

    async def _validate_disconnection_timing(self, event_dict: Dict[str, Any]) -> bool:
        """
        OPTIMIZED: Validate disconnection timing with version check
        """
        broker_connection_id = event_dict.get("broker_connection_id") or event_dict.get("aggregate_id")
        broker_id = event_dict.get("broker_id", "")

        if not broker_connection_id:
            return True

        # Use config values
        is_virtual = 'virtual' in broker_id.lower()
        threshold_seconds = saga_config.connection_conflict_window_seconds if is_virtual else 10

        # Check if there was a very recent connection event
        connection_key = f"BrokerConnectionEstablished:{broker_connection_id}"
        if connection_key in self._saga_event_tracker:
            conn_time = self._saga_event_tracker[connection_key]
            time_since_connection = (datetime.now(timezone.utc) - conn_time).total_seconds()

            if time_since_connection < threshold_seconds:
                # Check versions to determine which event is newer
                event_version = event_dict.get("aggregate_version", 0)

                # Look for connection event in sequence
                connection_events = self._connection_event_sequence.get(str(broker_connection_id), [])
                for tracked_event in connection_events:
                    if tracked_event['event_type'] == "BrokerConnectionEstablished":
                        conn_version = tracked_event.get('version', 0)
                        if event_version < conn_version:
                            log.warning(
                                f"Skipping disconnection saga - older version "
                                f"(disconnect v{event_version} < connection v{conn_version})"
                            )
                            return False
                        elif event_version > conn_version:
                            log.info(f"Allowing newer disconnection event v{event_version} to proceed")
                            return True

                # If same version or no version info, use time
                log.warning(
                    f"Skipping disconnection saga - connection established only {time_since_connection:.1f}s ago"
                )
                return False

        return True

    def _configure_triggers(self) -> None:
        """Configure saga triggers with enhanced race condition protection"""
        # TODO: Create WellWon-specific sagas and configure triggers
        # from app.infra.saga.user_deletion_saga import UserDeletionSaga

        # User domain triggers - commented out until sagas are implemented
        # self._trigger_configs["transport.user-account-events"] = [
        #     SagaTriggerConfig(
        #         event_types=["UserAccountDeleted", "UserDeleted"],
        #         saga_class=UserDeletionSaga,
        #         context_builder=lambda event: {
        #             'user_id': event['user_id'],
        #             'reason': event.get('reason', 'user_deletion'),
        #             'grace_period': event.get('grace_period', 0),
        #             'correlation_id': event.get('correlation_id', event.get('event_id')),
        #             'causation_id': event.get('event_id'),
        #             'original_event_type': event.get('event_type'),
        #             'triggered_from': 'saga_service'
        #         },
        #         dedupe_key_builder=lambda event: f"user_deletion:{event['user_id']}",
        #         dedupe_window_seconds=600,
        #         description="Triggers user deletion saga to clean up all user resources"
        #     )
        # ]

        log.info("No saga triggers configured yet - WellWon sagas to be implemented")


    async def _setup_event_consumers(self) -> None:
        """
        Setup event consumers for saga triggers.

        CRITICAL FIX (Nov 9, 2025): Start all consumers in parallel and wait until ready
        BEFORE app starts accepting requests. This prevents race condition where:
        1. App marks as "ready to serve requests"
        2. User clicks Connect → events published to Kafka
        3. Consumers still starting up (15-20s delay) → events sit in Kafka
        4. UI hangs waiting for saga completion

        Solution: Use asyncio.gather() to start all consumers in parallel and BLOCK
        until all Kafka connections are established.
        """
        async def start_consumer_for_topic(topic_name, trigger_configs):
            """Helper to start a single consumer"""
            consumer_name = f"{topic_name.split('.')[-1]}-saga-trigger"
            handler = self._create_event_handler(topic_name, trigger_configs)

            log.info(f"Starting saga trigger consumer for topic: {topic_name}")

            # This will BLOCK until consumer.start() completes (Kafka connection established)
            await self.event_bus.stream_consume(
                channel=topic_name,
                handler=handler,
                group=self._saga_group,
                consumer=consumer_name
            )

        # Start ALL consumers in parallel
        consumer_tasks = []
        for topic, configs in self._trigger_configs.items():
            task = asyncio.create_task(start_consumer_for_topic(topic, configs))
            consumer_tasks.append(task)
            self._consumer_tasks.append(task)

        # CRITICAL: Wait for ALL consumers to connect to Kafka before continuing
        # This ensures no events are lost due to consumers not being ready
        if consumer_tasks:
            log.info(f"Waiting for {len(consumer_tasks)} saga consumers to connect to Kafka...")
            # OPTIMIZED: Reduced wait from 5s to 2s (Redpanda consumers typically connect in <1s)
            # Wait with timeout to prevent hanging startup (max 30s for all consumers)
            try:
                await asyncio.wait_for(
                    asyncio.sleep(2.0),  # Give consumers 2s to start background loops (reduced from 5s)
                    timeout=30.0
                )
                log.info(f"✓ All {len(consumer_tasks)} saga consumers ready to process events")
            except asyncio.TimeoutError:
                log.warning("Consumer startup timed out after 30s, some consumers may not be ready")

    async def _setup_saga_completion_listeners(self) -> None:
        """Setup listeners for saga completion events"""
        saga_completion_handler = self._create_saga_completion_handler()

        # Listen to saga lifecycle events
        log.info("Starting saga completion listener...")
        task = asyncio.create_task(
            self.event_bus.stream_consume(
                channel="saga.events",
                handler=saga_completion_handler,
                group=f"{self._saga_group}-completion",
                consumer="saga-completion-listener"
            )
        )

        self._saga_completion_listeners.append(task)

        # CRITICAL FIX (Nov 9, 2025): Wait for completion listener to connect
        # OPTIMIZED: Reduced wait from 2s to 1s (single consumer typically connects in <500ms)
        # Same race condition fix as saga trigger consumers
        await asyncio.sleep(1.0)
        log.info("✓ Saga completion listener ready")

    def _create_saga_completion_handler(self) -> Callable[[Dict[str, Any]], Awaitable[None]]:
        """Create handler for saga completion events"""

        async def handle_saga_completion(event_dict: Dict[str, Any]) -> None:
            event_type = event_dict.get("event_type")

            # We're interested in completion events
            completion_events = {
                "SagaCompleted", "SagaFailed", "SagaCompensated",
                "BrokerDisconnectionCompleted", "BrokerDisconnectionAbandoned",
                "BrokerConnectionEstablishedSagaCompleted"
            }

            if event_type not in completion_events:
                return

            # Extract aggregate lock info
            saga_id = event_dict.get("saga_id")
            final_context = event_dict.get("final_context", {})
            conflict_key = final_context.get("conflict_key")

            if not conflict_key:
                # Try to extract from other fields
                broker_connection_id = event_dict.get("broker_connection_id")
                if broker_connection_id:
                    conflict_key = f"broker_connection:{broker_connection_id}"

            if conflict_key:
                log.info(f"Saga {saga_id} completed, checking pending sagas for {conflict_key}")

                # Process pending sagas for this aggregate
                await self._process_pending_sagas_for_aggregate(conflict_key)

        return handle_saga_completion

    def _create_event_handler(
            self,
            topic: str,
            configs: List[SagaTriggerConfig]
    ) -> Callable[[Dict[str, Any]], Awaitable[None]]:
        """Create an event handler for a specific topic"""

        async def handle_event(event_dict: Dict[str, Any]) -> None:
            """Handle events and trigger appropriate sagas"""
            # DEBUG: Log ALL received events
            event_type = event_dict.get("event_type")
            event_id = event_dict.get("event_id")
            log.info(f"[SAGA_CONSUMER_DEBUG] Received event on topic '{topic}': type={event_type}, id={event_id}")

            # Skip events that should not trigger sagas
            if await self._should_skip_event(event_dict):
                log.info(f"[SAGA_CONSUMER_DEBUG] Skipped event {event_id} ({event_type})")
                return

            # NEW: Enhanced event ordering check with version awareness
            if await self._should_skip_due_to_event_ordering(event_dict):
                event_id = event_dict.get("event_id")
                log.info(f"Skipping event {event_id} due to event ordering")
                return

            event_type = event_dict.get("event_type")
            event_id = event_dict.get("event_id")

            # Find matching trigger configs
            for config in configs:
                if event_type in config.event_types:
                    try:
                        # Check for duplicate connection attempts (cold start protection)
                        if await self._is_duplicate_connection_attempt(event_dict, config):
                            log.info(
                                f"Skipping duplicate connection attempt for event {event_id}"
                            )
                            continue

                        # Apply pre-trigger check if configured
                        if config.pre_trigger_check:
                            if not await config.pre_trigger_check(event_dict):
                                log.info(
                                    f"Pre-trigger check failed for {config.saga_class.__name__}, "
                                    f"skipping event {event_id}"
                                )
                                continue

                        # Apply state synchronization grace period if configured
                        if config.state_sync_grace_period_ms is not None:
                            grace_period_value = config.state_sync_grace_period_ms

                            if callable(grace_period_value):
                                # noinspection PyCallingNonCallable
                                grace_period_ms = grace_period_value(event_dict)
                            else:
                                grace_period_ms = grace_period_value

                            if grace_period_ms and grace_period_ms > 0:
                                log.info(
                                    f"Applying {grace_period_ms}ms grace period for "
                                    f"{config.saga_class.__name__} to allow state synchronization"
                                )
                                await asyncio.sleep(grace_period_ms / 1000.0)

                        # Apply pre-trigger delay if configured (cold start fix)
                        if config.pre_trigger_delay_ms:
                            delay_value = config.pre_trigger_delay_ms

                            if callable(delay_value):
                                # noinspection PyCallingNonCallable
                                delay_ms = delay_value(event_dict)
                            else:
                                delay_ms = delay_value

                            if delay_ms and delay_ms > 0:
                                log.info(
                                    f"Applying {delay_ms}ms delay before triggering "
                                    f"{config.saga_class.__name__} for cold start protection"
                                )
                                await asyncio.sleep(delay_ms / 1000.0)

                        # Check for conflicts if configured
                        if not config.allow_concurrent and config.conflict_key_builder:
                            # noinspection PyCallingNonCallable
                            conflict_key = config.conflict_key_builder(event_dict)

                            # Fast-track sagas skip the start lock
                            if config.fast_track:
                                log.info(f"Fast-tracking {config.saga_class.__name__} for event {event_id}")
                                context = config.context_builder(event_dict)
                                if self.projection_rebuilder and 'projection_rebuilder' not in context:
                                    context['projection_rebuilder'] = self.projection_rebuilder
                                await self._trigger_saga(
                                    config.saga_class,
                                    context,
                                    event_dict,
                                    config.description,
                                    None,
                                    0,
                                    conflict_key
                                )
                                continue

                            # Acquire saga start lock with retry
                            lock_key = f"saga:start:{conflict_key}"

                            saga_start_lock = None
                            try:
                                saga_start_lock = await retry_async(
                                    self.lock_manager.acquire_lock,
                                    lock_key,
                                    retry_config=self._lock_retry_config,
                                    context=f"saga_lock_{conflict_key}"
                                )
                            except Exception as e:
                                if "Timeout waiting for lock" in str(e):
                                    if config.auto_retry_on_conflict:
                                        log.info(
                                            f"Lock timeout for {config.saga_class.__name__}, adding to pending queue")
                                        await self._add_to_pending_queue(
                                            config,
                                            event_dict,
                                            conflict_key
                                        )
                                        continue

                                    if 'virtual' in config.saga_class.__name__.lower() or 'virtual' in str(
                                            conflict_key).lower():
                                        log.warning(f"Cannot acquire lock for virtual broker saga, skipping this event")
                                        continue

                                if not saga_start_lock:
                                    log.error(f"Could not acquire lock for {config.saga_class.__name__}: {e}")
                                    continue

                            if not saga_start_lock:
                                if config.auto_retry_on_conflict:
                                    log.info(
                                        f"Could not acquire lock for {config.saga_class.__name__}, adding to pending queue")
                                    await self._add_to_pending_queue(
                                        config,
                                        event_dict,
                                        conflict_key
                                    )
                                else:
                                    log.warning(
                                        f"Could not acquire start lock for {config.saga_class.__name__} "
                                        f"on {conflict_key} - another saga may be starting"
                                    )
                                continue

                            try:
                                # Double-check for active sagas with version awareness
                                can_start, should_queue = await self._can_start_saga_for_aggregate_smart(
                                    conflict_key,
                                    config.saga_class.__name__,
                                    event_dict,
                                    config.priority
                                )

                                if not can_start:
                                    if should_queue and config.auto_retry_on_conflict:
                                        log.info(
                                            f"Cannot start {config.saga_class.__name__} yet, "
                                            f"adding to pending queue for {conflict_key}"
                                        )
                                        await self._add_to_pending_queue(
                                            config,
                                            event_dict,
                                            conflict_key
                                        )
                                    else:
                                        log.warning(
                                            f"Skipping {config.saga_class.__name__} for event {event_id} - "
                                            f"conflicting saga already active for {conflict_key}"
                                        )
                                    continue

                                # Check deduplication
                                should_check_dedupe = True
                                if config.should_dedupe:
                                    should_check_dedupe = await config.should_dedupe(event_dict)

                                if should_check_dedupe and config.dedupe_key_builder:
                                    # noinspection PyCallingNonCallable
                                    dedupe_key = config.dedupe_key_builder(event_dict)

                                    if await self._is_saga_active(
                                            config.saga_class.__name__,
                                            dedupe_key,
                                            config.dedupe_window_seconds
                                    ):
                                        log.info(
                                            f"Skipping duplicate saga trigger for {config.saga_class.__name__} "
                                            f"with key {dedupe_key} (event: {event_id})"
                                        )
                                        continue

                                # Build context and trigger saga
                                context = config.context_builder(event_dict)
                                if self.projection_rebuilder and 'projection_rebuilder' not in context:
                                    context['projection_rebuilder'] = self.projection_rebuilder
                                await self._trigger_saga(
                                    config.saga_class,
                                    context,
                                    event_dict,
                                    config.description,
                                    config.dedupe_key_builder(event_dict) if config.dedupe_key_builder else None,
                                    config.dedupe_window_seconds,
                                    conflict_key
                                )

                            finally:
                                # Release the lock using the lock manager
                                if saga_start_lock and lock_key:
                                    try:
                                        await self.lock_manager.release_lock(saga_start_lock)
                                    except Exception as e:
                                        log.debug(f"Lock release error (may be already released): {e}")

                        else:
                            # No conflict prevention needed
                            context = config.context_builder(event_dict)
                            if self.projection_rebuilder and 'projection_rebuilder' not in context:
                                context['projection_rebuilder'] = self.projection_rebuilder
                            await self._trigger_saga(
                                config.saga_class,
                                context,
                                event_dict,
                                config.description,
                                config.dedupe_key_builder(event_dict) if config.dedupe_key_builder else None,
                                config.dedupe_window_seconds,
                                None
                            )

                    except Exception as e:
                        log.error(
                            f"Failed to trigger saga {config.saga_class.__name__} "
                            f"for event {event_type}: {e}",
                            exc_info=True
                        )

        return handle_event

    async def _should_skip_due_to_event_ordering(self, event_dict: Dict[str, Any]) -> bool:
        """
        Enhanced check for event ordering issues with version awareness.
        Tracks connection/disconnection event sequences per broker connection.
        """
        event_type = event_dict.get("event_type")
        broker_connection_id = event_dict.get("broker_connection_id") or event_dict.get("aggregate_id")
        event_version = event_dict.get("aggregate_version", 0)

        if not broker_connection_id or event_type not in ["BrokerConnectionEstablished", "BrokerDisconnected"]:
            return False

        # Get event timestamp
        event_timestamp_str = event_dict.get("timestamp")
        if not event_timestamp_str:
            return False

        from app.utils.datetime_utils import parse_timestamp_robust
        event_timestamp = parse_timestamp_robust(event_timestamp_str)
        if event_timestamp is None:
            return False

        # Track this event in the sequence with version
        event_info = {
            'event_type': event_type,
            'event_id': event_dict.get('event_id'),
            'timestamp': event_timestamp,
            'version': event_version,
            'processed_at': datetime.now(timezone.utc)
        }

        self._connection_event_sequence[str(broker_connection_id)].append(event_info)

        # Keep only recent events (last 10 or within 5 minutes)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        self._connection_event_sequence[str(broker_connection_id)] = [
            e for e in self._connection_event_sequence[str(broker_connection_id)][-10:]
            if e['processed_at'] > cutoff_time
        ]

        # Check for out-of-order events
        sequence = self._connection_event_sequence[str(broker_connection_id)]

        # Look for conflicting events
        opposite_event_type = (
            "BrokerDisconnected" if event_type == "BrokerConnectionEstablished"
            else "BrokerConnectionEstablished"
        )

        for prev_event in sequence[:-1]:  # Exclude the current event
            if prev_event['event_type'] == opposite_event_type:
                # NEW: Version-based ordering takes precedence
                if event_version < prev_event.get('version', 0):
                    log.warning(
                        f"Out-of-order event detected: {event_type} v{event_version} "
                        f"is older than already-processed {opposite_event_type} v{prev_event.get('version', 0)} "
                        f"for connection {broker_connection_id}"
                    )
                    return True
                elif event_version > prev_event.get('version', 0):
                    # Newer version should proceed
                    log.info(
                        f"Allowing newer {event_type} v{event_version} to proceed despite older "
                        f"{opposite_event_type} v{prev_event.get('version', 0)}"
                    )
                    return False

                # Same version - check timestamps
                if event_timestamp < prev_event['timestamp']:
                    log.warning(
                        f"Out-of-order event detected (same version): {event_type} (timestamp: {event_timestamp}) "
                        f"is older than already-processed {opposite_event_type} "
                        f"(timestamp: {prev_event['timestamp']}) for connection {broker_connection_id}"
                    )
                    return True

                # Check if events are too close together
                time_diff = abs((event_timestamp - prev_event['timestamp']).total_seconds())
                if time_diff < saga_config.connection_conflict_window_seconds:
                    log.warning(
                        f"Events too close together: {event_type} and {opposite_event_type} "
                        f"for connection {broker_connection_id} are only {time_diff:.2f}s apart"
                    )
                    # Allow the newer event to proceed
                    if event_timestamp < prev_event['timestamp']:
                        return True

        return False

    async def _check_for_conflicting_events(
            self,
            event_type: str,
            broker_connection_id: str,
            event_timestamp: str,
            event_version: int
    ) -> bool:
        """
        OPTIMIZED: Version-aware conflict checking with tighter window
        """
        if not broker_connection_id:
            return False

        if event_type not in ["BrokerConnectionEstablished", "BrokerDisconnected"]:
            return False

        opposite_event_type = (
            "BrokerDisconnected" if event_type == "BrokerConnectionEstablished"
            else "BrokerConnectionEstablished"
        )

        opposite_key = f"{opposite_event_type}:{broker_connection_id}"

        if opposite_key in self._saga_event_tracker:
            opposite_time = self._saga_event_tracker[opposite_key]
            time_since_opposite = (datetime.now(timezone.utc) - opposite_time).total_seconds()

            # Tighter window - 1 second max
            if time_since_opposite < 1.0:
                log.warning(
                    f"Race condition: {event_type} and {opposite_event_type} "
                    f"are only {time_since_opposite:.2f}s apart"
                )

                # NEW: Version-based resolution
                try:
                    event_dt = parse_timestamp_robust(event_timestamp)

                    if broker_connection_id in self._connection_event_sequence:
                        for tracked_event in self._connection_event_sequence[broker_connection_id]:
                            if tracked_event['event_type'] == opposite_event_type:
                                # Compare versions first
                                opposite_version = tracked_event.get('version', 0)
                                if event_version < opposite_version:
                                    log.info(f"Skipping older {event_type} v{event_version}")
                                    return True
                                elif event_version > opposite_version:
                                    log.info(f"Allowing newer {event_type} v{event_version} to proceed")
                                    return False

                                # Same version - use timestamp
                                opposite_event_dt = tracked_event['timestamp']
                                if event_dt < opposite_event_dt:
                                    log.info(f"Skipping older {event_type} (same version)")
                                    return True
                                else:
                                    log.info(f"Allowing newer {event_type} to proceed (same version)")
                                    return False
                except Exception as e:
                    log.debug(f"Error parsing timestamps: {e}")

        return False

    async def _can_start_saga_for_aggregate_smart(
            self,
            conflict_key: str,
            saga_type: str,
            event_dict: Dict[str, Any],
            priority: SagaPriority
    ) -> tuple[bool, bool]:
        """
        Enhanced check with version awareness and priority.
        Returns: (can_start, should_queue)
        """
        redis_key = f"saga_aggregate_lock:{conflict_key}"

        existing = await retry_async(
            safe_get,
            redis_key,
            retry_config=self._redis_retry_config,
            context=f"check_aggregate_lock_{conflict_key}"
        )

        if existing:
            try:
                # Parse lock data
                if isinstance(existing, str):
                    try:
                        lock_data = json.loads(existing)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        try:
                            lock_data = eval(existing)  # noqa: S307
                        except (SyntaxError, NameError, TypeError, ValueError):
                            log.error(f"Failed to parse lock data: {existing}")
                            await safe_delete(redis_key)
                            return True, False
                else:
                    lock_data = existing

                existing_saga_id = lock_data.get('saga_id')
                existing_saga_type = lock_data.get('saga_type')
                expires_at = lock_data.get('expires_at')
                locked_at = lock_data.get('locked_at')

                # Check if lock has expired
                if expires_at:
                    try:
                        expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        if datetime.now(timezone.utc) > expiry_time:
                            log.info(f"Lock for {conflict_key} has expired, cleaning up")
                            await safe_delete(redis_key)
                            return True, False
                    except Exception as e:
                        log.error(f"Error parsing expiry time: {e}")

                # NEW: Version-aware conflict resolution
                event_version = event_dict.get("aggregate_version", 0)

                # Priority-based conflict resolution
                if 'BrokerConnectionSaga' in saga_type and 'DisconnectionSaga' in existing_saga_type:
                    # Check versions
                    if event_version > 0:
                        # We have version info - use it
                        existing_version = lock_data.get('event_version', 0)
                        if event_version > existing_version:
                            log.info(
                                f"{saga_type} v{event_version} has newer version than "
                                f"{existing_saga_type} v{existing_version}, will queue for execution"
                            )
                            return False, True
                        elif event_version < existing_version:
                            log.info(
                                f"{saga_type} v{event_version} is older than "
                                f"{existing_saga_type} v{existing_version}, skipping"
                            )
                            return False, False

                    # Same version or no version - use priority
                    log.info(
                        f"{saga_type} has higher priority than {existing_saga_type}, "
                        f"will queue for execution after completion"
                    )
                    return False, True

                if 'DisconnectionSaga' in saga_type and 'BrokerConnectionSaga' in existing_saga_type:
                    # Don't override if connection saga just started
                    if locked_at:
                        try:
                            lock_time = datetime.fromisoformat(locked_at.replace('Z', '+00:00'))
                            lock_duration = (datetime.now(timezone.utc) - lock_time).total_seconds()

                            if lock_duration < saga_config.connection_conflict_window_seconds:
                                log.warning(
                                    f"Skipping {saga_type} - {existing_saga_type} just started {lock_duration:.1f}s ago"
                                )
                                return False, False
                        except Exception as e:
                            log.debug(f"Error checking lock duration: {e}")

                    # Check current connection status
                    # from app.broker_connection.queries import GetBrokerConnectionDetailsQuery

                    broker_connection_id = event_dict.get('broker_connection_id') or event_dict.get('aggregate_id')
                    if broker_connection_id:
                        try:
                            query = GetBrokerConnectionDetailsQuery(
                                broker_connection_id=uuid.UUID(broker_connection_id),
                                user_id=uuid.UUID(event_dict.get('user_id')) if event_dict.get('user_id') else None
                            )

                            query_bus = event_dict.get('query_bus', self.query_bus)
                            if query_bus:
                                connection_details = await query_bus.query(query)

                                if connection_details and connection_details.get('connected'):
                                    log.info(
                                        f"Connection is already established, skipping {saga_type}"
                                    )
                                    return False, False
                        except Exception as e:
                            log.error(f"Error checking connection status: {e}")

                # Special handling for Account Recovery sagas
                if 'AccountRecoverySaga' in saga_type:
                    # Allow recovery to override connection/disconnection sagas
                    if 'ConnectionSaga' in existing_saga_type or 'DisconnectionSaga' in existing_saga_type:
                        log.info(
                            f"Allowing {saga_type} to override {existing_saga_type} on {conflict_key}"
                        )
                        await safe_delete(redis_key)
                        if existing_saga_id and self.saga_manager:
                            try:
                                await self._cancel_conflicting_saga(uuid.UUID(existing_saga_id))
                            except Exception as e:
                                log.error(f"Error cancelling conflicting saga: {e}")
                        return True, False

                # Check if the saga is still active
                if existing_saga_id and self.saga_manager:
                    saga_status = await self.saga_manager.get_saga_status(uuid.UUID(existing_saga_id))
                    if saga_status and saga_status['status'] in ['started', 'in_progress', 'compensating']:
                        log.info(
                            f"Aggregate {conflict_key} is locked by active {existing_saga_type} "
                            f"saga {existing_saga_id} (status: {saga_status['status']})"
                        )
                        # Queue if priority is higher or equal
                        return False, priority.value >= SagaPriority.HIGH.value
                    else:
                        # Saga is not active, clean up the lock
                        log.info(f"Previous saga {existing_saga_id} for {conflict_key} is not active, cleaning up lock")
                        await safe_delete(redis_key)
                        return True, False

            except Exception as e:
                log.error(f"Error checking aggregate lock: {e}")
                # On error, allow the saga to proceed
                return True, False

        return True, False

    async def _add_to_pending_queue(
            self,
            config: SagaTriggerConfig,
            event_dict: Dict[str, Any],
            conflict_key: str
    ) -> None:
        """Add saga to pending queue"""
        if not saga_config.pending_queue_enabled:
            log.info("Pending queue disabled, skipping queueing")
            return

        context = config.context_builder(event_dict)
        if self.projection_rebuilder and 'projection_rebuilder' not in context:
            context['projection_rebuilder'] = self.projection_rebuilder

        pending_saga = PendingSaga(
            saga_class=config.saga_class,
            context=context,
            original_event=event_dict,
            description=config.description,
            dedupe_key=config.dedupe_key_builder(event_dict) if config.dedupe_key_builder else None,
            dedupe_window_seconds=config.dedupe_window_seconds,
            conflict_key=conflict_key,
            priority=config.priority,
            max_retries=config.max_retry_attempts
        )

        # Add to queue sorted by priority
        self._pending_sagas[conflict_key].append(pending_saga)
        self._pending_sagas[conflict_key].sort(key=lambda x: x.priority.value, reverse=True)

        log.info(
            f"Added {config.saga_class.__name__} to pending queue for {conflict_key} "
            f"with priority {config.priority.name}"
        )

    async def _process_pending_sagas_loop(self) -> None:
        """Background task to process pending sagas"""
        while self._running:
            try:
                await asyncio.sleep(saga_config.pending_queue_check_interval_seconds)

                # Check all aggregates with pending sagas
                for conflict_key in list(self._pending_sagas.keys()):
                    await self._process_pending_sagas_for_aggregate(conflict_key)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in pending saga processor: {e}", exc_info=True)

    async def _process_pending_sagas_for_aggregate(self, conflict_key: str) -> None:
        """
        Process pending sagas for a specific aggregate.
        DEADLOCK FIX (Nov 16, 2025): Detect and cleanup stale sagas blocking reconnection for ALL brokers.
        """
        if conflict_key not in self._pending_sagas:
            return

        pending_list = self._pending_sagas[conflict_key]
        if not pending_list:
            del self._pending_sagas[conflict_key]
            return

        # Check if aggregate is locked
        redis_key = f"saga_aggregate_lock:{conflict_key}"
        existing = await safe_get(redis_key)

        if existing:
            # Lock exists - determine if it's stale
            try:
                if isinstance(existing, str):
                    lock_data = json.loads(existing)
                else:
                    lock_data = existing

                saga_id = lock_data.get('saga_id')
                saga_type = lock_data.get('saga_type')
                locked_at = lock_data.get('locked_at')
                expires_at = lock_data.get('expires_at')

                # Check 1: Has the lock expired based on TTL?
                if expires_at:
                    expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) < expiry_time:
                        # Lock still valid by TTL

                        # Check 2: Is the saga actually still running?
                        if saga_config.stale_saga_detection_enabled and saga_id:
                            try:
                                saga_status = await self.saga_manager.get_saga_status(uuid.UUID(saga_id))

                                if saga_status:
                                    status = saga_status.get('status')

                                    # Check 3: Is saga in terminal state but lock not released?
                                    if status in ['completed', 'failed', 'compensated', 'timed_out']:
                                        log.warning(
                                            f"DEADLOCK FIX: Saga {saga_id} is {status} but lock still exists for {conflict_key}. "
                                            f"Cleaning up stale lock."
                                        )
                                        await safe_delete(redis_key)
                                        # Lock cleaned up, continue to process pending sagas below

                                    # Check 4: Has saga been locked longer than reasonable threshold?
                                    elif locked_at:
                                        locked_at_time = datetime.fromisoformat(locked_at.replace('Z', '+00:00'))
                                        lock_age = (datetime.now(timezone.utc) - locked_at_time).total_seconds()

                                        if lock_age > saga_config.stale_saga_timeout_threshold_seconds:
                                            log.error(
                                                f"DEADLOCK FIX: Saga {saga_id} ({saga_type}) has been locked for "
                                                f"{lock_age:.0f}s (threshold: {saga_config.stale_saga_timeout_threshold_seconds}s). "
                                                f"Considering it stale and cleaning up lock for {conflict_key}."
                                            )
                                            await safe_delete(redis_key)

                                            # Publish alert for monitoring
                                            await self._publish_stale_saga_alert(
                                                saga_id=saga_id,
                                                saga_type=saga_type,
                                                conflict_key=conflict_key,
                                                lock_age=lock_age
                                            )
                                            # Lock cleaned up, continue to process pending sagas below
                                        else:
                                            # Saga is still running and within threshold, keep waiting
                                            log.debug(
                                                f"Saga {saga_id} still active on {conflict_key} "
                                                f"(locked for {lock_age:.0f}s, threshold: {saga_config.stale_saga_timeout_threshold_seconds}s)"
                                            )
                                            return
                                    else:
                                        # Saga is running, keep waiting
                                        return
                                else:
                                    # Saga status not found - saga may have crashed
                                    log.warning(
                                        f"DEADLOCK FIX: Cannot find saga {saga_id} in saga manager. "
                                        f"Cleaning up orphaned lock for {conflict_key}."
                                    )
                                    await safe_delete(redis_key)
                                    # Lock cleaned up, continue to process pending sagas below
                            except Exception as e:
                                log.error(f"Error checking saga status for {saga_id}: {e}")
                                # On error checking status, keep waiting (don't prematurely release)
                                return
                        else:
                            # Stale detection disabled or no saga_id, wait for TTL expiry
                            return
            except Exception as e:
                log.error(f"Error checking lock for {conflict_key}: {e}")
                # On error, assume lock is still valid
                return

        # Lock is either released or cleaned up - process highest priority saga
        while pending_list:
            pending_saga = pending_list.pop(0)

            # Check if saga has expired
            age = (datetime.now(timezone.utc) - pending_saga.created_at).total_seconds()
            if age > saga_config.pending_saga_max_age_seconds:
                log.warning(
                    f"Pending saga {pending_saga.saga_class.__name__} expired "
                    f"after {age:.0f}s (max: {saga_config.pending_saga_max_age_seconds}s), dropping"
                )
                continue

            # Check if we've exceeded retry attempts
            if pending_saga.retry_count >= pending_saga.max_retries:
                log.warning(
                    f"Pending saga {pending_saga.saga_class.__name__} exceeded "
                    f"max retries ({pending_saga.max_retries}), dropping"
                )
                continue

            # Try to trigger the saga
            try:
                log.info(
                    f"Processing pending saga {pending_saga.saga_class.__name__} for {conflict_key} "
                    f"(attempt {pending_saga.retry_count + 1}/{pending_saga.max_retries}, "
                    f"queued for {age:.1f}s)"
                )

                # Add retry metadata to context
                pending_saga.context['retry_attempt'] = pending_saga.retry_count + 1
                pending_saga.context['was_queued'] = True
                pending_saga.context['queue_time_seconds'] = age

                saga_id = await self._trigger_saga(
                    pending_saga.saga_class,
                    pending_saga.context,
                    pending_saga.original_event,
                    pending_saga.description,
                    pending_saga.dedupe_key,
                    pending_saga.dedupe_window_seconds,
                    pending_saga.conflict_key
                )

                if saga_id:
                    log.info(
                        f"Successfully triggered pending saga {saga_id} "
                        f"after {age:.1f}s in queue"
                    )
                    # Remove from pending list if successful
                    if conflict_key in self._pending_sagas and not self._pending_sagas[conflict_key]:
                        del self._pending_sagas[conflict_key]
                    return
                else:
                    # Failed to trigger, increment retry count and re-add
                    pending_saga.retry_count += 1
                    if pending_saga.retry_count < pending_saga.max_retries:
                        # Re-add to queue with exponential backoff
                        backoff_seconds = min(2 ** pending_saga.retry_count, 30)
                        log.info(
                            f"Pending saga {pending_saga.saga_class.__name__} failed to trigger, "
                            f"retry {pending_saga.retry_count}/{pending_saga.max_retries} "
                            f"in {backoff_seconds}s"
                        )
                        await asyncio.sleep(backoff_seconds)
                        pending_list.insert(0, pending_saga)
                    else:
                        log.error(
                            f"Pending saga {pending_saga.saga_class.__name__} exceeded retries, dropping"
                        )

            except Exception as e:
                log.error(
                    f"Error processing pending saga {pending_saga.saga_class.__name__}: {e}",
                    exc_info=True
                )
                # Increment retry and re-add
                pending_saga.retry_count += 1
                if pending_saga.retry_count < pending_saga.max_retries:
                    pending_list.insert(0, pending_saga)

        # Clean up empty queue
        if conflict_key in self._pending_sagas and not self._pending_sagas[conflict_key]:
            del self._pending_sagas[conflict_key]

    async def _publish_stale_saga_alert(
        self,
        saga_id: str,
        saga_type: str,
        conflict_key: str,
        lock_age: float
    ) -> None:
        """
        Publish alert when stale saga is detected and cleaned up.
        DEADLOCK FIX (Nov 16, 2025): Alert monitoring systems of saga deadlocks.
        """
        try:
            alert_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "StaleSagaDetected",
                "saga_id": saga_id,
                "saga_type": saga_type,
                "conflict_key": conflict_key,
                "lock_age_seconds": lock_age,
                "threshold_seconds": saga_config.stale_saga_timeout_threshold_seconds,
                "action": "lock_cleaned_up",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.event_bus.publish("alerts.saga-deadlock", alert_event)

            # Increment counter for monitoring
            self._stale_sagas_cleaned_count = getattr(self, '_stale_sagas_cleaned_count', 0) + 1

            log.info(
                f"Published stale saga alert for {saga_id} "
                f"(total cleaned: {self._stale_sagas_cleaned_count})"
            )
        except Exception as e:
            log.error(f"Error publishing stale saga alert: {e}")

    async def _is_duplicate_connection_attempt(
            self,
            event_dict: Dict[str, Any],
            _config: SagaTriggerConfig
    ) -> bool:
        """Check if this is a duplicate connection attempt within threshold"""
        if "BrokerConnectionEstablished" not in event_dict.get("event_type", ""):
            return False

        connection_id = event_dict.get("broker_connection_id")
        if not connection_id:
            return False

        # Check recent attempts
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=10)

        if connection_id in self._recent_connection_attempts:
            last_attempt = self._recent_connection_attempts[connection_id]
            if last_attempt > cutoff_time:
                return True

        # Track this attempt
        self._recent_connection_attempts[connection_id] = datetime.now(timezone.utc)
        return False

    async def _cancel_conflicting_saga(self, saga_id: uuid.UUID) -> None:
        """Attempt to cancel a conflicting saga"""
        try:
            # Publish a saga cancellation event with circuit breaker
            cancellation_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "SagaCancellationRequested",
                "saga_id": str(saga_id),
                "reason": "Conflicting saga started",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": 1
            }

            await self._event_publish_circuit_breaker.execute_async(
                lambda: self.event_bus.publish("saga.control", cancellation_event)
            )
            log.info(f"Requested cancellation of conflicting saga {saga_id}")

        except Exception as e:
            log.error(f"Failed to request saga cancellation: {e}")

    async def _lock_aggregate_for_saga(
            self,
            conflict_key: str,
            saga_id: str,
            saga_type: str,
            event_version: int = 0,
            _ttl_seconds: int = 300
    ) -> bool:
        """Lock aggregate with version info"""
        redis_key = f"saga_aggregate_lock:{conflict_key}"

        # Use config for lock TTL
        is_virtual = 'virtual' in conflict_key.lower() or 'virtual' in saga_type.lower()
        ttl_seconds = saga_config.get_lock_ttl(is_virtual)

        # Shorter TTL for recovery sagas
        if 'AccountRecoverySaga' in saga_type:
            ttl_seconds = min(ttl_seconds, 600)  # Max 10 minutes for recovery

        lock_data = {
            'saga_id': saga_id,
            'saga_type': saga_type,
            'locked_at': datetime.now(timezone.utc).isoformat(),
            'conflict_key': conflict_key,
            'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(),
            'event_version': event_version  # NEW: Store version in lock
        }

        lock_json = json.dumps(lock_data)

        # Use Redis retry for setting lock
        success = await retry_async(
            safe_set,
            redis_key,
            lock_json,
            ttl_seconds=ttl_seconds,
            nx=True,
            retry_config=self._redis_retry_config,
            context=f"lock_aggregate_{conflict_key}"
        )

        if success:
            self._active_aggregate_sagas[conflict_key] = saga_id
            log.info(f"Locked aggregate {conflict_key} for saga {saga_id} with TTL {ttl_seconds}s (v{event_version})")

        return success

    async def _unlock_aggregate_for_saga(self, conflict_key: str, saga_id: str) -> None:
        """Unlock an aggregate after saga completion"""
        redis_key = f"saga_aggregate_lock:{conflict_key}"

        # Check if we own the lock
        existing = await retry_async(
            safe_get,
            redis_key,
            retry_config=self._redis_retry_config,
            context=f"get_lock_{conflict_key}"
        )

        if existing:
            try:
                # Parse lock data
                if isinstance(existing, str):
                    try:
                        lock_data = json.loads(existing)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        try:
                            lock_data = eval(existing)  # noqa: S307
                        except (SyntaxError, NameError, TypeError, ValueError):
                            log.error(f"Failed to parse lock data: {existing}")
                            await safe_delete(redis_key)
                            self._active_aggregate_sagas.pop(conflict_key, None)
                            return
                else:
                    lock_data = existing

                if lock_data.get('saga_id') == saga_id:
                    await safe_delete(redis_key)
                    self._active_aggregate_sagas.pop(conflict_key, None)
                    log.info(f"Unlocked aggregate {conflict_key} for saga {saga_id}")
                else:
                    log.warning(
                        f"Lock for {conflict_key} owned by different saga: "
                        f"{lock_data.get('saga_id')} (we are {saga_id})"
                    )
            except Exception as e:
                log.error(f"Error unlocking aggregate: {e}")
                # Force delete on error
                await safe_delete(redis_key)
                self._active_aggregate_sagas.pop(conflict_key, None)

    async def _should_skip_event(self, event_dict: Dict[str, Any]) -> bool:
        """Enhanced check if event should be skipped for saga processing"""
        event_id = event_dict.get("event_id")
        saga_id = event_dict.get("saga_id")
        event_type = event_dict.get("event_type")
        event_timestamp = event_dict.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Skip events created by sagas to prevent loops
        if saga_id:
            log.debug(f"Skipping event {event_id} created by saga {saga_id}")
            return True

        # Skip rebuild events
        if event_dict.get("_from_projection_rebuild", False):
            log.debug(f"Skipping rebuild event {event_id} for saga triggering")
            return True

        # Skip outbox events
        if event_dict.get("_from_outbox", False):
            log.debug(f"Skipping outbox event {event_id} for saga triggering")
            return True

        # Skip saga lifecycle events
        saga_event_types = {
            "SagaStarted", "SagaCompleted", "SagaFailed",
            "SagaCompensationStarted", "SagaCompensationCompleted",
            "SagaTriggered", "BrokerDisconnectionCompleted",
            "BrokerConnectionEstablishedSagaCompleted", "UserDeletionCompleted",
            "BrokerDisconnectionAbandoned",
            "AccountRecoveryCompleted", "AccountRecoveryFailed",
            "AccountRecoveryCompensationRequired", "AccountDataDiscrepancyDetected"
        }
        if event_type in saga_event_types:
            log.debug(f"Skipping saga lifecycle event {event_id}")
            return True

        # Check if we've already seen this event recently
        if event_id in self._saga_event_tracker:
            event_time = self._saga_event_tracker[event_id]
            time_since_seen = (datetime.now(timezone.utc) - event_time).total_seconds()
            if time_since_seen < 30:  # 30 second window
                log.debug(f"Skipping recently processed event {event_id} (seen {time_since_seen}s ago)")
                return True

        # Enhanced bidirectional conflict checking for connection/disconnection events
        broker_connection_id = event_dict.get("broker_connection_id") or event_dict.get("aggregate_id")
        if broker_connection_id and event_type in ["BrokerConnectionEstablished", "BrokerDisconnected"]:
            event_version = event_dict.get("aggregate_version", 0)
            # Check for conflicts
            if await self._check_for_conflicting_events(event_type, str(broker_connection_id), event_timestamp,
                                                        event_version):
                return True

            # Track this event for future conflict detection
            event_key = f"{event_type}:{broker_connection_id}"
            self._saga_event_tracker[event_key] = datetime.now(timezone.utc)

        # Track this event
        self._saga_event_tracker[event_id] = datetime.now(timezone.utc)

        return False

    async def _is_saga_active(self, saga_type: str, dedupe_key: str, _window_seconds: int) -> bool:
        """Check if a saga is already active for the given deduplication key"""
        # Check in-memory tracking
        if dedupe_key in self._active_sagas.get(saga_type, set()):
            return True

        # Check Redis for distributed deduplication
        redis_key = f"saga_dedupe:{saga_type}:{dedupe_key}"
        existing = await retry_async(
            safe_get,
            redis_key,
            retry_config=self._redis_retry_config,
            context=f"check_saga_active_{dedupe_key}"
        )

        return existing is not None

    async def _mark_saga_active(self, saga_type: str, dedupe_key: str, window_seconds: int) -> None:
        """Mark a saga as active for deduplication"""
        # Update in-memory tracking
        if saga_type not in self._active_sagas:
            self._active_sagas[saga_type] = set()
        self._active_sagas[saga_type].add(dedupe_key)

        # Update Redis for distributed deduplication
        redis_key = f"saga_dedupe:{saga_type}:{dedupe_key}"
        await retry_async(
            safe_set,
            redis_key,
            "active",
            ttl_seconds=window_seconds,
            retry_config=self._redis_retry_config,
            context=f"mark_saga_active_{dedupe_key}"
        )

    async def _trigger_saga(
            self,
            saga_class: Type[BaseSaga],
            context: Dict[str, Any],
            original_event: Dict[str, Any],
            description: str,
            dedupe_key: Optional[str] = None,
            dedupe_window_seconds: int = 300,
            conflict_key: Optional[str] = None
    ) -> Optional[uuid.UUID]:
        """Trigger a saga with all protections"""
        saga_id = None
        try:
            # Use circuit breaker for saga triggering
            async def trigger_with_manager():
                # Validate saga manager is ready
                if not self.saga_manager or not self.saga_manager.is_initialized():
                    raise RuntimeError(
                        f"Cannot trigger {saga_class.__name__} - "
                        "Saga manager not properly initialized"
                    )

                # Create saga instance
                saga = saga_class()
                nonlocal saga_id
                saga_id = saga.saga_id

                # Lock aggregate if conflict prevention is needed
                if conflict_key:
                    # Use config for lock TTL
                    is_virtual = 'virtual' in saga_class.__name__.lower() or 'virtual' in str(conflict_key).lower()
                    lock_ttl = saga_config.get_lock_ttl(is_virtual)
                    event_version = original_event.get('aggregate_version', 0)

                    # Check for conflicting sagas using smart conflict resolution
                    if 'BrokerConnectionSaga' in saga_class.__name__:
                        # Use smart check that supports queueing for reconnection scenarios
                        can_start, should_queue = await self._can_start_saga_for_aggregate_smart(
                            conflict_key,
                            saga_class.__name__,
                            original_event,
                            SagaPriority.NORMAL
                        )

                        if not can_start:
                            if should_queue and saga_config.pending_queue_enabled:
                                # Queue for later execution (e.g., after DisconnectionSaga completes)
                                log.info(
                                    f"BrokerConnectionSaga for {conflict_key} queued - "
                                    f"will execute after DisconnectionSaga completes"
                                )

                                # Add projection_rebuilder to context if needed
                                if self.projection_rebuilder and 'projection_rebuilder' not in context:
                                    context['projection_rebuilder'] = self.projection_rebuilder

                                # Create pending saga
                                pending_saga = PendingSaga(
                                    saga_class=saga_class,
                                    context=context,
                                    original_event=original_event,
                                    description=description,
                                    dedupe_key=dedupe_key,
                                    dedupe_window_seconds=dedupe_window_seconds,
                                    conflict_key=conflict_key,
                                    priority=SagaPriority.NORMAL,
                                    max_retries=saga_config.pending_saga_max_retries
                                )

                                # Add to queue sorted by priority
                                self._pending_sagas[conflict_key].append(pending_saga)
                                self._pending_sagas[conflict_key].sort(key=lambda x: x.priority.value, reverse=True)

                                log.info(
                                    f"Added {saga_class.__name__} to pending queue for {conflict_key} "
                                    f"(will retry after DisconnectionSaga completes)"
                                )
                                return None
                            else:
                                # Skip completely (either queueing disabled or shouldn't queue)
                                log.warning(
                                    f"Disconnection saga active on {conflict_key}, skipping connection saga"
                                )
                                return None

                    lock_acquired = await self._lock_aggregate_for_saga(
                        conflict_key,
                        str(saga_id),
                        saga_class.__name__,
                        event_version,
                        _ttl_seconds=lock_ttl
                    )

                    if not lock_acquired:
                        log.warning(
                            f"Failed to acquire aggregate lock for {saga_class.__name__} "
                            f"on {conflict_key} - another saga is active"
                        )
                        return None

                # Mark saga as active for deduplication
                if dedupe_key:
                    await self._mark_saga_active(saga_class.__name__, dedupe_key, dedupe_window_seconds)

                # Add metadata to context
                context['saga_service_instance'] = self.instance_id
                context['trigger_description'] = description
                context['trigger_timestamp'] = datetime.now(timezone.utc).isoformat()
                context['original_event_id'] = original_event.get('event_id')
                context['dedupe_key'] = dedupe_key
                context['conflict_key'] = conflict_key

                # Add unlock callback
                if conflict_key:
                    captured_conflict_key = conflict_key
                    captured_saga_id = str(saga_id)

                    async def unlock_aggregate():
                        await self._unlock_aggregate_for_saga(captured_conflict_key, captured_saga_id)

                    context['_unlock_aggregate'] = unlock_aggregate

                # Start saga
                await self.saga_manager.start_saga(saga, context)

                log.info(
                    f"Triggered {saga_class.__name__} (ID: {saga_id}) "
                    f"for event {original_event.get('event_type')} "
                    f"[{description}]"
                )

                # Publish saga triggered event
                await self._publish_saga_triggered_event(
                    saga_id,
                    saga_class.__name__,
                    original_event,
                    description
                )

                return saga_id

            # Execute with circuit breaker
            return await self._saga_trigger_circuit_breaker.execute_async(trigger_with_manager)

        except Exception as e:
            log.error(
                f"Error triggering {saga_class.__name__}: {e}",
                exc_info=True
            )
            # Unlock aggregate on failure
            if conflict_key and saga_id:
                await self._unlock_aggregate_for_saga(conflict_key, str(saga_id))
            return None

    async def _publish_saga_triggered_event(
            self,
            saga_id: uuid.UUID,
            saga_type: str,
            trigger_event: Dict[str, Any],
            description: str
    ) -> None:
        """Publish event when saga is triggered for monitoring"""
        try:
            from app.infra.saga.saga_events import SagaTriggered

            monitoring_event = SagaTriggered(
                event_id=str(uuid.uuid4()),
                saga_id=str(saga_id),
                saga_type=saga_type,
                trigger_event_type=trigger_event.get("event_type"),
                trigger_event_id=trigger_event.get("event_id"),
                description=description,
                instance_id=self.instance_id,
                timestamp=datetime.now(timezone.utc),
                version=1
            )

            # Publish with circuit breaker and retry
            await self._event_publish_circuit_breaker.execute_async(
                lambda: retry_async(
                    self.event_bus.publish,
                    "saga.monitoring",
                    monitoring_event.model_dump(),
                    retry_config=self._event_retry_config,
                    context="saga_triggered_event"
                )
            )

        except Exception as e:
            log.error(f"Failed to publish saga triggered event: {e}")

    @staticmethod
    async def _cleanup_stale_locks() -> None:
        """Clean up stale locks from previous runs"""
        try:
            log.info("Cleaning up stale saga locks...")
            # Stale locks will expire based on their configured TTL
            log.info("Stale locks will expire based on their configured TTL")

        except Exception as e:
            log.error(f"Error cleaning up stale locks: {e}")

    async def _cleanup_tracking_data(self) -> None:
        """Periodic cleanup of tracking data"""
        while self._running:
            try:
                await asyncio.sleep(saga_config.cleanup_interval_seconds)

                # Clean up old event tracking
                cutoff_time = datetime.now(timezone.utc) - timedelta(
                    minutes=saga_config.event_tracker_retention_minutes
                )
                old_events = [
                    event_id for event_id, timestamp in self._saga_event_tracker.items()
                    if timestamp < cutoff_time
                ]

                for event_id in old_events:
                    del self._saga_event_tracker[event_id]

                # Clean up old connection attempts
                connection_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
                old_connections = [
                    conn_id for conn_id, timestamp in self._recent_connection_attempts.items()
                    if timestamp < connection_cutoff
                ]

                for conn_id in old_connections:
                    del self._recent_connection_attempts[conn_id]

                # Clean up in-memory saga tracking
                for saga_type in list(self._active_sagas.keys()):
                    if not self._active_sagas[saga_type]:
                        del self._active_sagas[saga_type]

                # Clean up stale aggregate locks
                for conflict_key, saga_id in list(self._active_aggregate_sagas.items()):
                    # Check if saga is still active
                    if self.saga_manager:
                        try:
                            saga_status = await self.saga_manager.get_saga_status(uuid.UUID(saga_id))
                            if not saga_status or saga_status['status'] not in ['started', 'in_progress',
                                                                                'compensating']:
                                # Saga is not active, clean up lock
                                await self._unlock_aggregate_for_saga(conflict_key, saga_id)
                        except Exception as e:
                            log.error(f"Error checking saga status for cleanup: {e}")

                # Clean up expired pending sagas
                for conflict_key in list(self._pending_sagas.keys()):
                    pending_list = self._pending_sagas[conflict_key]
                    # Remove expired sagas
                    self._pending_sagas[conflict_key] = [
                        ps for ps in pending_list
                        if (datetime.now(
                            timezone.utc) - ps.created_at).total_seconds() < saga_config.pending_saga_max_age_seconds
                    ]
                    # Remove empty lists
                    if not self._pending_sagas[conflict_key]:
                        del self._pending_sagas[conflict_key]

                if old_events or old_connections:
                    log.debug(
                        f"Cleaned up {len(old_events)} old events and "
                        f"{len(old_connections)} old connection attempts"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in tracking data cleanup: {e}")

    async def trigger_saga_manually(
            self,
            saga_class: Type[BaseSaga],
            context: Dict[str, Any]
    ) -> Optional[uuid.UUID]:
        """Manually trigger a saga (for admin operations)."""
        if not self._initialized:
            raise RuntimeError("SagaService not initialized")

        # Add manual trigger metadata
        context['triggered_manually'] = True
        context['manual_trigger_time'] = datetime.now(timezone.utc).isoformat()

        # Always inject ProjectionRebuilder if available
        if self.projection_rebuilder and 'projection_rebuilder' not in context:
            context['projection_rebuilder'] = self.projection_rebuilder

        return await self._trigger_saga(
            saga_class,
            context,
            {"event_type": "ManualTrigger", "event_id": str(uuid.uuid4())},
            "Manual saga trigger"
        )

    async def get_saga_status(self, saga_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get the status of a specific saga"""
        if not self.saga_manager:
            return None

        return await self.saga_manager.get_saga_status(saga_id)

    async def retry_failed_saga(self, saga_id: uuid.UUID) -> bool:
        """Retry compensation for a failed saga"""
        if not self.saga_manager:
            return False

        return await self.saga_manager.retry_compensation(saga_id)

    def get_active_sagas_count(self) -> int:
        """Get count of currently active sagas"""
        if not self.saga_manager:
            return 0

        return self.saga_manager.get_active_sagas_count()

    async def get_saga_registry_info(self) -> Dict[str, Any]:
        """Get information about registered saga types"""
        if not self.saga_manager:
            return {"error": "Saga manager not initialized"}

        return await self.saga_manager.get_saga_registry_info()

    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the saga service"""
        status = {
            "initialized": self._initialized,
            "running": self._running,
            "instance_id": self.instance_id,
            "saga_group": self._saga_group,
            "active_consumers": len([t for t in self._consumer_tasks if not t.done()]),
            "total_consumers": len(self._consumer_tasks),
            "configured_topics": list(self._trigger_configs.keys()),
            "trigger_configurations": {},
            "duplicate_tracking": {
                "tracked_events": len(self._saga_event_tracker),
                "active_saga_types": list(self._active_sagas.keys()),
                "total_active_dedupe_keys": sum(len(keys) for keys in self._active_sagas.values())
            },
            "conflict_prevention": {
                "active_aggregate_locks": len(self._active_aggregate_sagas),
                "locked_aggregates": list(self._active_aggregate_sagas.keys())
            },
            "cold_start_protection": {
                "recent_connection_attempts": len(self._recent_connection_attempts)
            },
            "event_ordering": {
                "tracked_connections": len(self._connection_event_sequence),
                "total_events_tracked": sum(len(seq) for seq in self._connection_event_sequence.values())
            },
            "circuit_breakers": {
                "saga_trigger": self._saga_trigger_circuit_breaker.get_metrics(),
                "event_publish": self._event_publish_circuit_breaker.get_metrics()
            },
            "pending_sagas": {
                "enabled": saga_config.pending_queue_enabled,
                "total_aggregates_with_pending": len(self._pending_sagas),
                "total_pending_sagas": sum(len(ps) for ps in self._pending_sagas.values()),
                "pending_by_aggregate": {
                    k: len(v) for k, v in self._pending_sagas.items()
                }
            },
            "projection_rebuilder": {
                "available": self.projection_rebuilder is not None,
                "type": type(self.projection_rebuilder).__name__ if self.projection_rebuilder else None
            },
            "stale_saga_detection": {
                "enabled": saga_config.stale_saga_detection_enabled,
                "threshold_seconds": saga_config.stale_saga_timeout_threshold_seconds,
                "stale_sagas_cleaned": getattr(self, '_stale_sagas_cleaned_count', 0)
            },
            "config": {
                "default_timeout_seconds": saga_config.default_timeout_seconds,
                "default_retry_count": saga_config.default_retry_count,
                "virtual_broker_speed_factor": saga_config.virtual_broker_speed_factor,
                "pending_queue_enabled": saga_config.pending_queue_enabled,
                "pending_queue_check_interval_seconds": saga_config.pending_queue_check_interval_seconds,
                "cleanup_interval_seconds": saga_config.cleanup_interval_seconds,
                "connection_conflict_window_seconds": saga_config.connection_conflict_window_seconds
            }
        }

        # Add trigger configuration details
        for topic, configs in self._trigger_configs.items():
            status["trigger_configurations"][topic] = [
                {
                    "event_types": config.event_types,
                    "saga_class": config.saga_class.__name__,
                    "description": config.description,
                    "has_deduplication": config.dedupe_key_builder is not None,
                    "has_conditional_dedupe": config.should_dedupe is not None,
                    "has_conflict_prevention": config.conflict_key_builder is not None,
                    "allow_concurrent": config.allow_concurrent,
                    "fast_track": getattr(config, 'fast_track', False),
                    "has_pre_trigger_delay": config.pre_trigger_delay_ms is not None,
                    "has_state_sync_grace_period": config.state_sync_grace_period_ms is not None,
                    "has_pre_trigger_check": config.pre_trigger_check is not None,
                    "priority": config.priority.name,
                    "auto_retry_on_conflict": config.auto_retry_on_conflict,
                    "max_retry_attempts": config.max_retry_attempts
                }
                for config in configs
            ]

        # Add saga manager status if available
        if self.saga_manager:
            status["saga_manager"] = {
                "initialized": self.saga_manager.is_initialized(),
                "active_sagas": self.saga_manager.get_active_sagas_count(),
                "has_event_store": self.event_store is not None,
                "has_parent_service_reference": True
            }

            # Get registry info
            try:
                registry_info = await self.saga_manager.get_saga_registry_info()
                status["saga_registry"] = registry_info
            except Exception as e:
                status["saga_registry"] = {"error": str(e)}

        return status

    async def shutdown(self) -> None:
        """Gracefully shutdown the saga service"""
        log.info("Shutting down SagaService...")

        self._running = False

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel pending saga processor
        if self._pending_saga_processor and not self._pending_saga_processor.done():
            self._pending_saga_processor.cancel()
            try:
                await self._pending_saga_processor
            except asyncio.CancelledError:
                pass

        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            if not task.done():
                task.cancel()

        # Cancel completion listeners
        for task in self._saga_completion_listeners:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        all_tasks = self._consumer_tasks + self._saga_completion_listeners
        if all_tasks:
            results = await asyncio.gather(
                *all_tasks,
                return_exceptions=True
            )

            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    log.error(f"Consumer task {i} ended with error: {result}")

        self._consumer_tasks.clear()
        self._saga_completion_listeners.clear()
        self._initialized = False

        log.info("SagaService shutdown complete")


# Factory function for creating saga service
def create_saga_service(
        event_bus: EventBus,
        command_bus: CommandBus,
        query_bus: QueryBus,
        event_store: Optional[KurrentDBEventStore] = None,
        instance_id: Optional[str] = None,
        lock_manager: Optional[DistributedLockManager] = None,
        projection_rebuilder: Optional['ProjectionRebuilderService'] = None
) -> SagaService:
    """Factory function to create a configured saga service."""
    return SagaService(
        event_bus=event_bus,
        command_bus=command_bus,
        query_bus=query_bus,
        event_store=event_store,
        instance_id=instance_id,
        lock_manager=lock_manager,
        projection_rebuilder=projection_rebuilder
    )

# =============================================================================
# EOF
# =============================================================================