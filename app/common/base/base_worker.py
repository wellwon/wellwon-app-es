# app/common/base/base_worker.py
"""
Base Worker - Complete Shared Infrastructure for All Worker Types

Provides EVERYTHING common between all worker types:
- PersistentWorkerState (Redis-backed)
- Full infrastructure initialization (DB, Redis, EventBus, CQRS)
- Beautiful logging (add_startup_info, log_worker_banner, etc.)
- Signal handling with multi-signal support (graceful → expedite → force)
- Health monitoring (30s loop)
- Metrics publishing (5min loop)
- Background tasks management
- DLQ service
- Sequence tracker
- Distributed locks
- Graceful shutdown with timeouts
- WorkerConfig integration

Usage:
    class MyWorker(BaseWorker):
        def __init__(self, config: Optional[WorkerConfig] = None):
            super().__init__(WorkerType.MY_WORKER, config)

        async def _initialize_worker_specific(self):
            # Custom initialization
            self.my_processor = MyProcessor(...)
            self.consumer_manager = ConsumerManager(...)

        async def _process_events_loop(self):
            # Main event processing
            await self.consumer_manager.start()
            await self._shutdown_event.wait()
            await self.consumer_manager.stop()

        async def _get_health_status(self) -> HealthStatus:
            # Return HealthStatus object
            return await check_infrastructure_health(...)

        async def _get_metrics(self) -> WorkerMetrics:
            # Return WorkerMetrics object
            return WorkerMetrics(...)
"""

import asyncio
import logging
import signal
import sys
import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# Persistence
from app.infra.persistence.pg_client import init_db_pool, close_db_pool, db as pg_db_proxy
from app.infra.persistence.redis_client import (
    init_global_client as init_redis,
    close_global_client as close_redis,
    get_global_client as get_redis_instance
)
from app.infra.persistence.cache_manager import initialize_cache_manager, get_cache_manager

# Event Bus
from app.infra.event_bus.event_bus import EventBus

# CQRS
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus

# Worker infrastructure
from app.infra.worker_core.worker_lifecycle import (
    WorkerLifecycleManager, WorkerMetrics, HealthStatus, check_infrastructure_health
)
from app.infra.worker_core.consumer_groups import (
    WorkerType, get_worker_consumer_config, create_redpanda_adapter_for_worker
)
from app.config.worker_config import WorkerConfig, create_worker_config  # NEW unified config

# Components
from app.infra.event_store.sequence_tracker import EventSequenceTracker
from app.infra.reliability.distributed_lock import DistributedLockManager
from app.infra.event_store.dlq_service import DLQService

# Logging with beautiful formatting
from app.config.logging_config import (
    setup_logging,
    log_worker_banner,
    log_status_update,
    log_metrics_table,
    log_error_box,
    add_startup_info,
)

# Unified metrics interface
from app.infra.metrics.worker_metrics import WorkerMetricsCollector

log = logging.getLogger(__name__)


# =============================================================================
# PERSISTENT STATE MANAGEMENT
# =============================================================================

class PersistentWorkerState:
    """
    Persistent state storage for workers using Redis.

    Provides durable state that survives worker restarts.
    Used for tracking processed events, last sync timestamps, metrics, etc.
    """

    def __init__(self, worker_type: WorkerType, instance_id: str):
        self.worker_type = worker_type
        self.instance_id = instance_id
        self.namespace = f"worker_state:{worker_type.value}:{instance_id}"
        self.redis_client = None
        self.logger = logging.getLogger(f"wellwon.worker.{worker_type.value}.state")

    async def initialize(self):
        """Initialize connection to Redis"""
        self.redis_client = get_redis_instance()
        self.logger.info(f"Persistent state initialized (namespace: {self.namespace})")

    async def save_state(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Save state with TTL"""
        if not self.redis_client:
            return

        try:
            import json
            full_key = f"{self.namespace}:{key}"
            await self.redis_client.setex(
                full_key,
                ttl_seconds,
                json.dumps(value, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to save state for {key}: {e}")

    async def load_state(self, key: str) -> Optional[Any]:
        """Load state from Redis"""
        if not self.redis_client:
            return None

        try:
            import json
            full_key = f"{self.namespace}:{key}"
            value = await self.redis_client.get(full_key)
            if value:
                return json.loads(value)
        except Exception as e:
            self.logger.error(f"Failed to load state for {key}: {e}")
        return None

    async def delete_state(self, key: str):
        """Delete state"""
        if not self.redis_client:
            return

        try:
            full_key = f"{self.namespace}:{key}"
            await self.redis_client.delete(full_key)
        except Exception as e:
            self.logger.error(f"Failed to delete state for {key}: {e}")


# =============================================================================
# BASE WORKER - COMPLETE IMPLEMENTATION
# =============================================================================

class BaseWorker(ABC):
    """
    Abstract base class for all worker types with COMPLETE infrastructure.

    Provides everything common between all worker types.
    Subclasses only implement worker-specific logic.
    """

    def __init__(self, worker_type: WorkerType, config: Optional[WorkerConfig] = None):
        self.worker_type = worker_type
        self.worker_consumer_config = get_worker_consumer_config(worker_type)

        if not self.worker_consumer_config:
            raise ValueError(f"No configuration found for worker type: {worker_type}")

        if not self.worker_consumer_config.enabled:
            raise ValueError(f"Worker type {worker_type} is not enabled")

        # Create or use provided config
        if config:
            self.config = config
        else:
            instance_id = os.getenv("WORKER_INSTANCE_ID") or self.worker_consumer_config.get_client_id()
            self.config = create_worker_config(
                worker_id=instance_id,
                consumer_group_prefix=self.worker_consumer_config.consumer_group,
                topics=self.worker_consumer_config.topics,
                consumer_batch_size=self.worker_consumer_config.max_poll_records,
                max_retries=self.worker_consumer_config.max_retries,
                retry_delay_base_s=self.worker_consumer_config.retry_backoff_ms / 1000.0,
                dlq_topic=self.worker_consumer_config.get_dead_letter_topic(),
            )

        # Set instance ID
        self.instance_id = self.config.worker_id

        # Infrastructure connections (initialized in initialize())
        self.event_bus: Optional[EventBus] = None
        self.redpanda_adapter = None
        self.cache_manager = None
        self.dlq_service: Optional[DLQService] = None

        # CQRS buses
        self.command_bus: Optional[CommandBus] = None
        self.query_bus: Optional[QueryBus] = None

        # Worker components
        self.lifecycle_manager: Optional[WorkerLifecycleManager] = None
        self.sequence_tracker: Optional[EventSequenceTracker] = None
        self.lock_manager: Optional[DistributedLockManager] = None

        # State management
        self.persistent_state: Optional[PersistentWorkerState] = None
        self._running = False
        self._initialized = False
        self._shutdown_event = asyncio.Event()
        self._start_time = time.time()
        self._shutdown_initiated = False
        self._signal_count = 0

        # Metrics
        self.metrics_collector = WorkerMetricsCollector(self.worker_type)

        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._state_persistence_task: Optional[asyncio.Task] = None
        self._metrics_reporting_task: Optional[asyncio.Task] = None

        # Logger
        self.logger = logging.getLogger(f"wellwon.worker.{self.worker_type.value}")

    async def initialize(self) -> None:
        """Initialize common infrastructure for all workers"""
        if self._initialized:
            self.logger.warning("Worker already initialized")
            return

        self.logger.info(f"Worker ({self.config.worker_id}) initializing as {self.worker_type.value}")

        try:
            # 1. Connect to infrastructure
            await self._connect_infrastructure()

            # 2. Worker-specific initialization (BEFORE lifecycle)
            # This allows workers to set up components needed by lifecycle callbacks
            self.logger.info("Running worker-specific initialization...")
            await self._initialize_worker_specific()
            self.logger.info("Worker-specific initialization complete")

            # 3. Setup lifecycle management (AFTER worker components ready)
            await self._setup_lifecycle()

            # 4. Initialize persistent state
            await self._setup_persistent_state()

            # 5. Setup background tasks (AFTER all components ready)
            await self._setup_background_tasks()

            self._initialized = True
            self.logger.info(f"Worker ({self.config.worker_id}) initialized successfully")

            # Log detailed initialization status
            log_status_update(self.logger, "Worker Initialized", {
                "worker_id": self.config.worker_id,
                "worker_type": self.worker_type.value,
                "consumer_group": self.worker_consumer_config.consumer_group,
                "topics": len(self.config.topics),
                "max_instances": self.worker_consumer_config.instances_max,
                "batch_size": self.worker_consumer_config.max_poll_records,
                "command_bus": "enabled" if self.command_bus else "disabled",
                "query_bus": "enabled" if self.query_bus else "disabled",
            })

        except Exception as e:
            self.logger.error(f"Failed to initialize worker: {e}", exc_info=True)
            raise

    async def _connect_infrastructure(self) -> None:
        """Connect to existing infrastructure (DB, Redis, EventBus, CQRS)"""
        self.logger.info("Connecting to infrastructure...")

        # Temporarily reduce logging for setup (quiet initialization)
        import logging as log_module
        redpanda_logger = log_module.getLogger("wellwon.redpanda_adapter")
        event_bus_logger = log_module.getLogger("wellwon.event_bus")
        original_redpanda_level = redpanda_logger.level
        original_event_bus_level = event_bus_logger.level
        redpanda_logger.setLevel(log_module.WARNING)
        event_bus_logger.setLevel(log_module.WARNING)

        try:
            # Connect to databases
            add_startup_info("PostgreSQL", "[green]✓[/green] Initializing", "database")
            await init_db_pool()
            await pg_db_proxy.execute("SELECT 1")
            add_startup_info("PostgreSQL", "[green]✓[/green] Ready", "database")

            add_startup_info("Redis", "[green]✓[/green] Initializing", "database")
            await init_redis()
            add_startup_info("Redis", "[green]✓[/green] Ready", "database")

            # Initialize cache manager
            add_startup_info("Cache Manager", "[green]✓[/green] Initializing", "features")
            self.cache_manager = await initialize_cache_manager()
            add_startup_info("Cache Manager", "[green]✓[/green] Ready", "features")

            # Create RedPanda adapter using centralized config
            add_startup_info("RedPanda Adapter", "[green]✓[/green] Initializing", "messaging")
            self.redpanda_adapter = create_redpanda_adapter_for_worker(
                self.worker_type,
                instance_id=self.config.worker_id
            )
            add_startup_info("RedPanda Adapter", "[green]✓[/green] Ready", "messaging")

            add_startup_info("Event Bus", "[green]✓[/green] Initializing", "messaging")
            self.event_bus = EventBus(self.redpanda_adapter, validate_on_publish=False)
            add_startup_info("Event Bus", "[green]✓[/green] Ready", "messaging")

            # Initialize DLQ service
            if self.config.dlq_enabled:
                try:
                    add_startup_info("DLQ Service", "[green]✓[/green] Initializing", "features")
                    self.dlq_service = DLQService()
                    await self.dlq_service.initialize()
                    add_startup_info("DLQ Service", "[green]✓[/green] Ready", "features")
                except Exception as e:
                    self.logger.warning(f"Failed to initialize DLQ service: {e}")
                    self.dlq_service = None

            # Setup sequence tracker for exactly-once processing
            if self.config.enable_sequence_tracking:
                add_startup_info("Sequence Tracker", "[green]✓[/green] Initializing", "features")
                self.sequence_tracker = EventSequenceTracker(
                    namespace=f"worker_sequence_{self.worker_type.value}",
                    ttl_seconds=86400
                )
                add_startup_info("Sequence Tracker", "[green]✓[/green] Ready", "features")

            # Initialize distributed lock manager
            add_startup_info("Distributed Lock", "[green]✓[/green] Initializing", "features")
            self.lock_manager = DistributedLockManager(
                namespace=f"worker_lock_{self.config.worker_id}",
                default_ttl_ms=self.worker_consumer_config.session_timeout_ms,
                max_wait_ms=5000
            )
            add_startup_info("Distributed Lock", "[green]✓[/green] Ready", "features")

            # Initialize CQRS buses (using overrideable logic)
            if self._should_enable_command_bus():
                add_startup_info("Command Bus", "[green]✓[/green] Initializing", "features")
                self.command_bus = CommandBus()
                add_startup_info("Command Bus", "[green]✓[/green] Ready", "features")
            else:
                self.logger.info("Command Bus: disabled")

            if self._should_enable_query_bus():
                add_startup_info("Query Bus", "[green]✓[/green] Initializing", "features")
                self.query_bus = QueryBus()
                add_startup_info("Query Bus", "[green]✓[/green] Ready", "features")
            else:
                self.logger.info("Query Bus: disabled")

            self.logger.info("Infrastructure connections established")

        finally:
            # Restore logging levels
            redpanda_logger.setLevel(original_redpanda_level)
            event_bus_logger.setLevel(original_event_bus_level)

    async def _setup_lifecycle(self) -> None:
        """Setup lifecycle management"""
        self.lifecycle_manager = WorkerLifecycleManager(
            config=self.config,
            event_bus=self.event_bus,
            get_health_status=self._get_health_status,
            get_metrics=self._get_metrics
        )

        await self.lifecycle_manager.create_readiness_file()
        await self.lifecycle_manager.register_worker()
        await self.lifecycle_manager.publish_startup_event()

        self.logger.info("Lifecycle management initialized")

    async def _setup_persistent_state(self) -> None:
        """Setup persistent state storage"""
        self.persistent_state = PersistentWorkerState(self.worker_type, self.instance_id)
        await self.persistent_state.initialize()

        # Load any previous state
        previous_metrics = await self.persistent_state.load_state("metrics")
        if previous_metrics:
            self.logger.info(f"Loaded previous metrics: {previous_metrics}")

        # Hook for worker-specific persistent state loading
        if hasattr(self, '_setup_persistent_state_worker_specific'):
            await self._setup_persistent_state_worker_specific()

    async def _setup_background_tasks(self) -> None:
        """Setup background monitoring and maintenance tasks"""
        # Common tasks (all workers)
        self._state_persistence_task = asyncio.create_task(
            self._state_persistence_loop(),
            name="state-persistence"
        )
        self._background_tasks.append(self._state_persistence_task)

        # Metrics reporting
        self._metrics_reporting_task = asyncio.create_task(
            self._metrics_reporting_loop(),
            name="metrics-reporting"
        )
        self._background_tasks.append(self._metrics_reporting_task)

        # Worker-specific tasks (gap detection, projection monitoring, etc.)
        await self._setup_worker_specific_background_tasks()

    async def _state_persistence_loop(self) -> None:
        """Periodically persist important state"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute

                if not self._running:
                    break

                # Save current metrics
                metrics = await self._get_metrics()
                await self.persistent_state.save_state("metrics", {
                    "processed_events": getattr(metrics, 'processed_events', 0),
                    "failed_events": getattr(metrics, 'failed_events', 0),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, ttl_seconds=3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in state persistence loop: {e}")

    async def _metrics_reporting_loop(self) -> None:
        """Report metrics periodically"""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                if not self._running:
                    break

                # Get and log metrics
                await self._log_periodic_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error logging metrics: {e}")

    async def _log_periodic_metrics(self):
        """Log periodic metrics (override in subclass for custom logging)"""
        metrics = await self._get_metrics()
        self.logger.info(f"Metrics: {metrics}")

    @abstractmethod
    async def _initialize_worker_specific(self):
        """
        Worker-specific initialization.

        Override to set up worker-specific components:
        - Domain registry (EventProcessor)
        - Event processor (EventProcessor)
        - Consumer manager
        - Saga processor
        - etc.
        """
        pass

    async def _setup_worker_specific_background_tasks(self):
        """
        Setup worker-specific background tasks.

        Override to add custom background tasks (gap detection, projection monitoring, etc.)
        Default implementation does nothing.
        """
        pass

    async def _start_processing(self):
        """
        Start worker-specific processing logic.

        Override to implement custom processing logic.
        Typically starts consumer manager and waits for shutdown.

        Default implementation just waits for shutdown signal.
        """
        await self._shutdown_event.wait()

    @abstractmethod
    async def _get_health_status(self) -> HealthStatus:
        """
        Get worker-specific health status.

        Must return HealthStatus object from worker_lifecycle.
        """
        pass

    @abstractmethod
    async def _get_metrics(self) -> WorkerMetrics:
        """
        Get worker-specific operational metrics.

        Must return WorkerMetrics object from worker_lifecycle.
        """
        pass

    def _should_enable_command_bus(self) -> bool:
        """
        Determine if command bus should be enabled.
        Override to customize logic (e.g., check worker_consumer_config.supports_commands).
        """
        return self.config.enable_command_bus

    def _should_enable_query_bus(self) -> bool:
        """
        Determine if query bus should be enabled.
        Override to customize logic (e.g., check worker_consumer_config.supports_queries).
        """
        return self.config.enable_query_bus

    async def start(self) -> None:
        """Start processing events"""
        if not self._initialized:
            raise RuntimeError("Worker must be initialized before starting")

        if self._running:
            self.logger.warning("Worker already running")
            return

        self.logger.info(f"Starting {self.worker_type.value} worker {self.config.worker_id}")
        self._running = True

        try:
            # Start lifecycle monitoring
            await self.lifecycle_manager.start()

            # Start worker-specific processing
            await self._start_processing()

        except Exception as e:
            self.logger.error(f"Failed to start worker: {e}", exc_info=True)
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop processing events with proper cleanup"""
        if not self._running:
            return

        if self._shutdown_initiated:
            self.logger.warning("Shutdown already in progress")
            return

        self._shutdown_initiated = True
        self.logger.info(f"Stopping worker {self.config.worker_id}")
        self._running = False

        # Save final state
        try:
            final_metrics = await self._get_metrics()
            await self.persistent_state.save_state("final_metrics", {
                "processed_events": getattr(final_metrics, 'processed_events', 0),
                "failed_events": getattr(final_metrics, 'failed_events', 0),
                "shutdown_time": datetime.now(timezone.utc).isoformat()
            }, ttl_seconds=86400)
        except Exception as e:
            self.logger.error(f"Error saving final state: {e}")

        # Stop background tasks with timeout
        if self._background_tasks:
            self.logger.info("Stopping background tasks...")
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Some background tasks did not complete in time")

        # Stop lifecycle
        if self.lifecycle_manager:
            await self.lifecycle_manager.publish_shutdown_event(await self._get_metrics())
            await self.lifecycle_manager.stop()
            await self.lifecycle_manager.deregister_worker()
            await self.lifecycle_manager.cleanup_files()

        # Log final metrics
        await self._log_final_metrics()

        # Close infrastructure connections
        if self.event_bus:
            await self.event_bus.close()

        if self.cache_manager and hasattr(self.cache_manager, 'stop'):
            await self.cache_manager.stop()

        self.logger.info(f"Worker {self.config.worker_id} stopped")

    async def _log_final_metrics(self):
        """Log final metrics (override in subclass for custom logging)"""
        final_metrics = await self._get_metrics()
        uptime = int(time.time() - self._start_time)
        self.logger.info(f"Final metrics - Uptime: {uptime}s, Metrics: {final_metrics}")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()

    def handle_signal(self, sig, frame):
        """
        Handle system signals with multi-level support.

        1st signal: Graceful shutdown
        2nd signal: Expedite shutdown
        3rd+ signal: Force exit
        """
        self._signal_count += 1
        signal_name = signal.Signals(sig).name

        self.logger.warning(f"Received signal {signal_name} (count: {self._signal_count})")

        if self._signal_count == 1:
            # First signal - graceful shutdown
            self.logger.warning("Initiating graceful shutdown...")
            self._shutdown_event.set()
        elif self._signal_count == 2:
            # Second signal - expedite shutdown
            self.logger.warning("Second signal received - expediting shutdown")
            self._shutdown_event.set()
        else:
            # Third+ signal - force exit
            self.logger.error("Multiple signals received - forcing immediate exit")
            os._exit(1)

    async def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        return {
            "worker_id": self.config.worker_id,
            "worker_type": self.worker_type.value,
            "version": "0.8",
            "features": {
                "command_bus": self.command_bus is not None,
                "query_bus": self.query_bus is not None,
                "event_bus": self.event_bus is not None,
                "distributed_lock": self.lock_manager is not None,
                "sequence_tracking": self.sequence_tracker is not None,
                "persistent_state": self.persistent_state is not None,
                "cache_manager": self.cache_manager is not None,
                "dlq_service": self.dlq_service is not None,
            },
            "infrastructure": {
                "redpanda_servers": self.config.redpanda_servers,
                "consumer_group": self.worker_consumer_config.consumer_group,
                "topics": self.config.topics,
                "dlq_topic": self.config.dlq_topic,
                "max_retries": self.config.max_retries,
                "batch_size": self.config.consumer_batch_size
            },
            "monitoring": {
                "health_check_interval": self.config.health_check_interval,
                "metrics_interval": self.config.metrics_interval,
                "heartbeat_ttl": self.config.heartbeat_ttl,
            },
            "status": "running" if self._running else "stopped",
            "uptime_seconds": int(time.time() - self._start_time)
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BaseWorker',
    'PersistentWorkerState',
]
