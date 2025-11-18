# =============================================================================
# File: app/infra/consumers/worker_manager.py
# Description: Manages multiple workers - scaling, health monitoring, coordination
# =============================================================================

import asyncio
import logging
import os
import signal
import uuid
import json
import socket
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from app.infra.event_bus.event_bus import EventBus
from app.infra.event_bus.redpanda_adapter import RedpandaTransportAdapter
from app.infra.persistence.redis_client import (
    safe_set, safe_get, safe_delete, hincrby,
    init_global_client as init_redis,
    close_global_client as close_redis
)
from app.infra.persistence.pg_client import (
    init_db_pool, close_db_pool
)

log = logging.getLogger("wellwon.worker_manager")


class ManagerState(Enum):
    """Manager lifecycle states"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    SCALING = "scaling"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ScalingDecision(Enum):
    """Scaling decisions"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


class ManagerEventType(Enum):
    """Manager event types"""
    STARTED = "manager_started"
    STOPPED = "manager_stopped"
    WORKER_SPAWNED = "worker_spawned"
    WORKER_TERMINATED = "worker_terminated"
    SCALING_EVENT = "scaling_event"
    HEALTH_CHECK = "manager_health_check"
    ERROR = "manager_error"


@dataclass
class ManagedWorkerInfo:
    """Information about a managed worker"""
    worker_id: str
    process: asyncio.subprocess.Process
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: str = "starting"
    restart_count: int = 0
    last_health_check: Optional[datetime] = None
    health_status: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagerConfig:
    """Configuration for the worker manager"""
    manager_id: str = field(
        default_factory=lambda: f"manager-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    min_workers: int = 1
    max_workers: int = 10
    initial_workers: int = 2

    # Scaling configuration
    enable_auto_scaling: bool = True
    scale_up_threshold: float = 0.8  # 80% load
    scale_down_threshold: float = 0.2  # 20% load
    scale_cooldown_seconds: int = 300  # 5 minutes

    # Health and monitoring
    health_check_interval: int = 60
    metrics_interval: int = 300
    worker_restart_delay: int = 10
    max_restart_attempts: int = 3
    worker_startup_timeout: int = 60
    worker_shutdown_timeout: int = 30

    # Redis keys
    manager_registry_key: str = "wellwon:managers:registry"
    worker_registry_key: str = "wellwon:workers:registry"

    # Topics
    manager_events_topic: str = "system.manager-events"

    # Worker configuration
    worker_module: str = "app.infra.worker_core.worker"
    worker_env_vars: Dict[str, str] = field(default_factory=dict)

    # Resource limits
    worker_memory_limit_mb: Optional[int] = None
    worker_cpu_limit: Optional[float] = None


class WorkerManager:
    """
    Manages multiple worker processes with scaling, health monitoring,
    and fault tolerance capabilities.
    """

    def __init__(self, config: Optional[ManagerConfig] = None):
        self.config = config or ManagerConfig()

        # State
        self._state = ManagerState.INITIALIZING
        self._workers: Dict[str, ManagedWorkerInfo] = {}
        self._worker_lock = asyncio.Lock()
        self._stop_requested = False
        self._start_time = datetime.now(timezone.utc)

        # Scaling state
        self._last_scaling_decision: Optional[datetime] = None
        self._scaling_metrics_history: List[Dict[str, Any]] = []

        # Infrastructure
        self._event_bus: Optional[EventBus] = None

        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._scaling_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Callbacks
        self._event_callbacks: Dict[ManagerEventType, List[Callable]] = {}

        log.info(f"WorkerManager created: {self.config.manager_id}")

    async def initialize(self) -> None:
        """Initialize manager infrastructure"""
        try:
            log.info("Initializing WorkerManager infrastructure")

            # Initialize Redis
            await init_redis()
            log.info("Redis initialized")

            # Initialize PostgreSQL
            await init_db_pool()
            log.info("PostgreSQL initialized")

            # Initialize event bus
            redpanda_adapter = RedpandaTransportAdapter(
                bootstrap_servers=os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092"),
                client_id=f"manager-{self.config.manager_id}",
                producer_config={
                    'acks': 'all',
                    'compression_type': 'snappy',
                    'enable_idempotence': True,
                }
            )

            self._event_bus = EventBus(redpanda_adapter, validate_on_publish=True)
            log.info("Event bus initialized")

            # Register manager
            await self._register_manager()

            # Publish startup event
            await self._publish_event(ManagerEventType.STARTED, {
                "config": {
                    "min_workers": self.config.min_workers,
                    "max_workers": self.config.max_workers,
                    "auto_scaling": self.config.enable_auto_scaling
                }
            })

            self._state = ManagerState.READY
            log.info("WorkerManager initialized successfully")

        except Exception as e:
            log.error(f"Failed to initialize WorkerManager: {e}", exc_info=True)
            self._state = ManagerState.ERROR
            raise

    async def start(self) -> None:
        """Start the manager and spawn initial workers"""
        if self._state != ManagerState.READY:
            raise RuntimeError(f"Cannot start manager in state {self._state}")

        log.info(f"Starting WorkerManager with {self.config.initial_workers} initial workers")
        self._state = ManagerState.RUNNING
        self._stop_requested = False

        # Spawn initial workers
        for i in range(self.config.initial_workers):
            await self._spawn_worker()

        # Start background tasks
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._metrics_task = asyncio.create_task(self._metrics_loop())

        if self.config.enable_auto_scaling:
            self._scaling_task = asyncio.create_task(self._scaling_loop())

        log.info(f"WorkerManager started with {len(self._workers)} workers")

    async def stop(self) -> None:
        """Stop all workers and shutdown manager"""
        log.info("Stopping WorkerManager")
        self._stop_requested = True
        self._state = ManagerState.STOPPING

        # Stop all workers
        await self._stop_all_workers()

        # Cancel background tasks
        tasks = [
            self._monitor_task,
            self._scaling_task,
            self._metrics_task,
            self._heartbeat_task
        ]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cleanup infrastructure
        await self._cleanup()

        # Deregister
        await self._deregister_manager()

        # Publish shutdown event
        await self._publish_event(ManagerEventType.STOPPED, {
            "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
            "workers_managed": len(self._workers)
        })

        self._state = ManagerState.STOPPED
        log.info("WorkerManager stopped")

    async def _spawn_worker(self) -> Optional[str]:
        """Spawn a new worker process"""
        async with self._worker_lock:
            if len(self._workers) >= self.config.max_workers:
                log.warning(f"Cannot spawn worker: max workers ({self.config.max_workers}) reached")
                return None

            worker_id = f"worker-{self.config.manager_id}-{len(self._workers)}-{uuid.uuid4().hex[:8]}"

            # Prepare environment variables
            env = os.environ.copy()
            env.update({
                "WORKER_INSTANCE_ID": worker_id,
                "WORKER_GROUP_PREFIX": f"synapse_worker_{self.config.manager_id}",
                "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
                **self.config.worker_env_vars
            })

            # Spawn worker process
            try:
                cmd = [
                    "python", "-m", self.config.worker_module
                ]

                # Add resource limits if configured
                if self.config.worker_memory_limit_mb:
                    # This would require platform-specific implementation
                    pass

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                worker_info = ManagedWorkerInfo(
                    worker_id=worker_id,
                    process=process,
                    state="starting"
                )

                self._workers[worker_id] = worker_info

                # Monitor worker startup
                asyncio.create_task(self._monitor_worker_startup(worker_id))

                await self._publish_event(ManagerEventType.WORKER_SPAWNED, {
                    "worker_id": worker_id,
                    "total_workers": len(self._workers)
                })

                log.info(f"Spawned worker {worker_id} (PID: {process.pid})")
                return worker_id

            except Exception as e:
                log.error(f"Failed to spawn worker: {e}", exc_info=True)
                return None

    async def _monitor_worker_startup(self, worker_id: str) -> None:
        """Monitor worker startup and verify it's healthy"""
        worker = self._workers.get(worker_id)
        if not worker:
            return

        start_time = datetime.now(timezone.utc)
        timeout = timedelta(seconds=self.config.worker_startup_timeout)

        while (datetime.now(timezone.utc) - start_time) < timeout:
            # Check if process is still alive
            if worker.process.returncode is not None:
                log.error(f"Worker {worker_id} died during startup (exit code: {worker.process.returncode})")
                worker.state = "failed"
                await self._handle_worker_failure(worker_id)
                return

            # Check if worker registered in Redis
            worker_key = f"{self.config.worker_registry_key}:{worker_id}"
            worker_data = await safe_get(worker_key)

            if worker_data:
                worker.state = "running"
                log.info(f"Worker {worker_id} started successfully")
                return

            await asyncio.sleep(1)

        # Timeout reached
        log.error(f"Worker {worker_id} failed to start within timeout")
        worker.state = "timeout"
        await self._terminate_worker(worker_id)

    async def _terminate_worker(self, worker_id: str) -> None:
        """Terminate a specific worker"""
        worker = self._workers.get(worker_id)
        if not worker:
            return

        log.info(f"Terminating worker {worker_id}")

        try:
            # Send SIGTERM
            worker.process.terminate()

            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(
                    worker.process.wait(),
                    timeout=self.config.worker_shutdown_timeout
                )
            except asyncio.TimeoutError:
                # Force kill if not responsive
                log.warning(f"Worker {worker_id} not responding to SIGTERM, sending SIGKILL")
                worker.process.kill()
                await worker.process.wait()

            # Remove from tracking
            async with self._worker_lock:
                del self._workers[worker_id]

            await self._publish_event(ManagerEventType.WORKER_TERMINATED, {
                "worker_id": worker_id,
                "reason": "terminated"
            })

        except Exception as e:
            log.error(f"Error terminating worker {worker_id}: {e}")

    async def _stop_all_workers(self) -> None:
        """Stop all managed workers"""
        log.info(f"Stopping {len(self._workers)} workers")

        # Send SIGTERM to all workers
        for worker_id, worker in self._workers.items():
            if worker.process.returncode is None:
                worker.process.terminate()

        # Wait for graceful shutdown
        shutdown_tasks = []
        for worker_id, worker in self._workers.items():
            shutdown_tasks.append(
                asyncio.create_task(
                    asyncio.wait_for(
                        worker.process.wait(),
                        timeout=self.config.worker_shutdown_timeout
                    )
                )
            )

        if shutdown_tasks:
            results = await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            # Force kill any remaining
            for i, (worker_id, worker) in enumerate(self._workers.items()):
                if isinstance(results[i], asyncio.TimeoutError):
                    log.warning(f"Force killing worker {worker_id}")
                    worker.process.kill()
                    await worker.process.wait()

        self._workers.clear()

    async def _monitor_loop(self) -> None:
        """Monitor worker health and restart failed workers"""
        while not self._stop_requested:
            try:
                async with self._worker_lock:
                    for worker_id, worker in list(self._workers.items()):
                        # Check if process is alive
                        if worker.process.returncode is not None:
                            log.error(f"Worker {worker_id} died (exit code: {worker.process.returncode})")
                            await self._handle_worker_failure(worker_id)
                            continue

                        # Health check
                        worker_key = f"{self.config.worker_registry_key}:{worker_id}"
                        worker_data = await safe_get(worker_key)

                        if worker_data:
                            try:
                                data = json.loads(worker_data)
                                worker.last_health_check = datetime.now(timezone.utc)
                                worker.health_status = data
                                worker.metrics = data.get("metrics", {})

                                # Check if worker is healthy
                                last_heartbeat = datetime.fromisoformat(
                                    data["last_heartbeat"].replace('Z', '+00:00')
                                )
                                age = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()

                                if age > self.config.health_check_interval * 2:
                                    log.warning(f"Worker {worker_id} heartbeat too old ({age}s)")
                                    await self._handle_worker_failure(worker_id)

                            except Exception as e:
                                log.error(f"Error parsing worker data: {e}")
                        else:
                            # No heartbeat data
                            if worker.state == "running":
                                log.warning(f"No heartbeat from worker {worker_id}")
                                await self._handle_worker_failure(worker_id)

                await asyncio.sleep(self.config.health_check_interval)

            except Exception as e:
                log.error(f"Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(self.config.health_check_interval)

    async def _handle_worker_failure(self, worker_id: str) -> None:
        """Handle worker failure with restart logic"""
        worker = self._workers.get(worker_id)
        if not worker:
            return

        # Remove failed worker
        async with self._worker_lock:
            if worker_id in self._workers:
                del self._workers[worker_id]

        # Check restart attempts
        if worker.restart_count >= self.config.max_restart_attempts:
            log.error(f"Worker {worker_id} exceeded max restart attempts")
            await self._publish_event(ManagerEventType.ERROR, {
                "worker_id": worker_id,
                "error": "max_restarts_exceeded"
            })

            # Spawn new worker if below minimum
            if len(self._workers) < self.config.min_workers:
                await self._spawn_worker()
            return

        # Restart after delay
        log.info(f"Restarting worker {worker_id} after {self.config.worker_restart_delay}s")
        await asyncio.sleep(self.config.worker_restart_delay)

        # Spawn replacement
        new_worker_id = await self._spawn_worker()
        if new_worker_id and new_worker_id in self._workers:
            self._workers[new_worker_id].restart_count = worker.restart_count + 1

    async def _scaling_loop(self) -> None:
        """Auto-scaling loop based on worker metrics"""
        while not self._stop_requested:
            try:
                # Check cooldown
                if self._last_scaling_decision:
                    cooldown_elapsed = (datetime.now(timezone.utc) - self._last_scaling_decision).total_seconds()
                    if cooldown_elapsed < self.config.scale_cooldown_seconds:
                        await asyncio.sleep(60)
                        continue

                # Calculate load metrics
                load_metrics = await self._calculate_load_metrics()

                # Make scaling decision
                decision = self._make_scaling_decision(load_metrics)

                if decision == ScalingDecision.SCALE_UP:
                    await self._scale_up()
                elif decision == ScalingDecision.SCALE_DOWN:
                    await self._scale_down()

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                log.error(f"Scaling loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _calculate_load_metrics(self) -> Dict[str, float]:
        """Calculate aggregate load metrics from all workers"""
        total_events = 0
        total_queue_depth = 0
        total_errors = 0
        worker_count = 0

        async with self._worker_lock:
            for worker in self._workers.values():
                if worker.state == "running" and worker.metrics:
                    total_events += worker.metrics.get("processed_events", 0)
                    total_queue_depth += worker.metrics.get("queue_depth", 0)
                    total_errors += worker.metrics.get("failed_events", 0)
                    worker_count += 1

        if worker_count == 0:
            return {"load_factor": 0.0}

        # Calculate load factor (0.0 to 1.0+)
        # This is a simplified calculation - adjust based on your needs
        avg_queue_depth = total_queue_depth / worker_count
        error_rate = total_errors / max(total_events, 1)

        # Queue depth normalized (assuming 1000 as high load)
        queue_load = min(avg_queue_depth / 1000.0, 1.0)

        # Combined load factor
        load_factor = queue_load * (1 + error_rate)

        metrics = {
            "load_factor": load_factor,
            "avg_queue_depth": avg_queue_depth,
            "error_rate": error_rate,
            "total_events": total_events,
            "worker_count": worker_count
        }

        # Store for history
        self._scaling_metrics_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metrics
        })

        # Keep only last hour
        if len(self._scaling_metrics_history) > 60:
            self._scaling_metrics_history = self._scaling_metrics_history[-60:]

        return metrics

    def _make_scaling_decision(self, metrics: Dict[str, float]) -> ScalingDecision:
        """Make scaling decision based on metrics"""
        load_factor = metrics.get("load_factor", 0.0)
        current_workers = len(self._workers)

        if load_factor > self.config.scale_up_threshold:
            if current_workers < self.config.max_workers:
                return ScalingDecision.SCALE_UP
        elif load_factor < self.config.scale_down_threshold:
            if current_workers > self.config.min_workers:
                return ScalingDecision.SCALE_DOWN

        return ScalingDecision.NO_CHANGE

    async def _scale_up(self) -> None:
        """Scale up by adding a worker"""
        current_count = len(self._workers)

        log.info(f"Scaling up from {current_count} to {current_count + 1} workers")

        await self._publish_event(ManagerEventType.SCALING_EVENT, {
            "direction": "up",
            "from_count": current_count,
            "to_count": current_count + 1
        })

        worker_id = await self._spawn_worker()
        if worker_id:
            self._last_scaling_decision = datetime.now(timezone.utc)

    async def _scale_down(self) -> None:
        """Scale down by removing the least loaded worker"""
        if len(self._workers) <= self.config.min_workers:
            return

        # Find least loaded worker
        least_loaded_id = None
        min_events = float('inf')

        async with self._worker_lock:
            for worker_id, worker in self._workers.items():
                if worker.state == "running" and worker.metrics:
                    events = worker.metrics.get("processed_events", 0)
                    if events < min_events:
                        min_events = events
                        least_loaded_id = worker_id

        if least_loaded_id:
            current_count = len(self._workers)
            log.info(f"Scaling down from {current_count} to {current_count - 1} workers")

            await self._publish_event(ManagerEventType.SCALING_EVENT, {
                "direction": "down",
                "from_count": current_count,
                "to_count": current_count - 1,
                "removed_worker": least_loaded_id
            })

            await self._terminate_worker(least_loaded_id)
            self._last_scaling_decision = datetime.now(timezone.utc)

    async def _metrics_loop(self) -> None:
        """Publish aggregated metrics periodically"""
        while not self._stop_requested:
            try:
                await asyncio.sleep(self.config.metrics_interval)

                # Aggregate metrics
                total_events = 0
                total_errors = 0
                total_queue_depth = 0
                worker_metrics = {}

                async with self._worker_lock:
                    for worker_id, worker in self._workers.items():
                        if worker.metrics:
                            total_events += worker.metrics.get("processed_events", 0)
                            total_errors += worker.metrics.get("failed_events", 0)
                            total_queue_depth += worker.metrics.get("queue_depth", 0)
                            worker_metrics[worker_id] = worker.metrics

                metrics_data = {
                    "worker_count": len(self._workers),
                    "total_events_processed": total_events,
                    "total_errors": total_errors,
                    "total_queue_depth": total_queue_depth,
                    "success_rate": (total_events / (total_events + total_errors) * 100) if (
                                                                                                        total_events + total_errors) > 0 else 0,
                    "scaling_metrics": self._scaling_metrics_history[-10:] if self._scaling_metrics_history else [],
                    "per_worker_metrics": worker_metrics
                }

                await self._publish_event(ManagerEventType.HEALTH_CHECK, metrics_data)

            except Exception as e:
                log.error(f"Metrics loop error: {e}", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """Update manager status in Redis"""
        while not self._stop_requested:
            try:
                status = {
                    "manager_id": self.config.manager_id,
                    "state": self._state.value,
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
                    "worker_count": len(self._workers),
                    "worker_states": {
                        worker_id: {
                            "state": worker.state,
                            "pid": worker.process.pid if worker.process else None,
                            "restart_count": worker.restart_count
                        }
                        for worker_id, worker in self._workers.items()
                    }
                }

                key = f"{self.config.manager_registry_key}:{self.config.manager_id}"
                await safe_set(key, json.dumps(status), ttl_seconds=60)

                await asyncio.sleep(30)

            except Exception as e:
                log.error(f"Heartbeat error: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def _register_manager(self) -> None:
        """Register manager in Redis"""
        info = {
            "manager_id": self.config.manager_id,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "started_at": self._start_time.isoformat(),
            "config": {
                "min_workers": self.config.min_workers,
                "max_workers": self.config.max_workers,
                "auto_scaling": self.config.enable_auto_scaling
            }
        }

        key = f"{self.config.manager_registry_key}:{self.config.manager_id}"
        await safe_set(key, json.dumps(info), ttl_seconds=3600)

        await hincrby(f"{self.config.manager_registry_key}:metrics", "total_managers", 1)

    async def _deregister_manager(self) -> None:
        """Remove manager from Redis"""
        key = f"{self.config.manager_registry_key}:{self.config.manager_id}"
        await safe_delete(key)

        await hincrby(f"{self.config.manager_registry_key}:metrics", "total_managers", -1)

    async def _publish_event(self, event_type: ManagerEventType, data: Dict[str, Any]) -> None:
        """Publish manager event"""
        if self._event_bus:
            event_data = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type.value,
                "manager_id": self.config.manager_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **data
            }

            try:
                await self._event_bus.publish(
                    self.config.manager_events_topic,
                    event_data
                )
            except Exception as e:
                log.error(f"Failed to publish event: {e}")

        # Call registered callbacks
        for callback in self._event_callbacks.get(event_type, []):
            try:
                asyncio.create_task(callback(event_type, data))
            except Exception as e:
                log.error(f"Callback error: {e}")

    async def _cleanup(self) -> None:
        """Cleanup infrastructure connections"""
        if self._event_bus and hasattr(self._event_bus, 'close'):
            await self._event_bus.close()

        await close_redis()
        await close_db_pool()

    def register_event_callback(self, event_type: ManagerEventType, callback: Callable) -> None:
        """Register callback for manager events"""
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)

    async def get_status(self) -> Dict[str, Any]:
        """Get manager status and metrics"""
        async with self._worker_lock:
            workers_info = {
                worker_id: {
                    "state": worker.state,
                    "pid": worker.process.pid if worker.process else None,
                    "started_at": worker.started_at.isoformat(),
                    "restart_count": worker.restart_count,
                    "last_health_check": worker.last_health_check.isoformat() if worker.last_health_check else None,
                    "metrics": worker.metrics
                }
                for worker_id, worker in self._workers.items()
            }

        return {
            "manager_id": self.config.manager_id,
            "state": self._state.value,
            "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
            "worker_count": len(self._workers),
            "config": {
                "min_workers": self.config.min_workers,
                "max_workers": self.config.max_workers,
                "auto_scaling": self.config.enable_auto_scaling
            },
            "workers": workers_info,
            "scaling_history": self._scaling_metrics_history[-10:] if self._scaling_metrics_history else []
        }

    @asynccontextmanager
    async def graceful_shutdown(self):
        """Context manager for graceful shutdown on signals"""
        shutdown_event = asyncio.Event()

        def signal_handler(sig):
            log.info(f"Received signal {sig}, initiating graceful shutdown")
            shutdown_event.set()

        # Register signal handlers
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, lambda s, f: signal_handler(s))

        try:
            yield shutdown_event
        finally:
            # Cleanup will happen in stop()
            pass


# CLI entry point for running the manager
async def run_manager(config: Optional[ManagerConfig] = None):
    """Run the worker manager"""
    manager = WorkerManager(config)

    try:
        await manager.initialize()
        await manager.start()

        # Wait for shutdown signal
        async with manager.graceful_shutdown() as shutdown_event:
            await shutdown_event.wait()

    except Exception as e:
        log.error(f"Manager failed: {e}", exc_info=True)
    finally:
        await manager.stop()


def main():
    """Main entry point"""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Create config from environment
    config = ManagerConfig(
        min_workers=int(os.getenv("MANAGER_MIN_WORKERS", "1")),
        max_workers=int(os.getenv("MANAGER_MAX_WORKERS", "10")),
        initial_workers=int(os.getenv("MANAGER_INITIAL_WORKERS", "2")),
        enable_auto_scaling=os.getenv("MANAGER_AUTO_SCALING", "true").lower() == "true"
    )

    # Run
    try:
        asyncio.run(run_manager(config))
    except KeyboardInterrupt:
        print("\nManager stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Manager error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()