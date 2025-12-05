# app/infra/consumers/worker_lifecycle.py
# =============================================================================
# File: app/infra/consumers/worker_lifecycle.py
# Description: Manages worker lifecycle with sync projections metrics
# =============================================================================

"""
Worker Lifecycle Manager

Handles all lifecycle-related concerns for a worker:
- Worker registration/deregistration in Redis
- Heartbeat updates
- Health check monitoring and file management
- Metrics collection and publishing (including sync projections)
- Background task management for monitoring

This is pure infrastructure management - no business logic.
"""

import asyncio
import json
import logging
import os
import socket
import time
from uuid import UUID
from datetime import datetime, timezone
from pathlib import Path

from app.utils.uuid_utils import generate_event_id
from typing import Optional, Dict, Any, Callable, Awaitable, List
from dataclasses import dataclass, field

from app.infra.worker_core.worker_config import WorkerConfig
from app.infra.event_bus.event_bus import EventBus
from app.infra.persistence.redis_client import (
    safe_set, safe_delete, hincrby,
    get_global_circuit_breaker as get_redis_circuit_breaker
)
from app.infra.persistence.pg_client import (
    get_global_circuit_breaker as get_pg_circuit_breaker
)

log = logging.getLogger("wellwon.worker.lifecycle")


@dataclass
class HealthStatus:
    """Infrastructure health status"""
    redis_healthy: bool
    postgres_healthy: bool
    event_bus_healthy: bool
    consumer_manager_healthy: bool
    overall_healthy: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerMetrics:
    """Worker processing metrics with sync projections tracking"""
    processed_events: int = 0
    failed_events: int = 0
    retry_events: int = 0
    saga_events: int = 0
    saga_triggered: int = 0
    sync_events_skipped: int = 0  # NEW: Sync events processed async
    event_type_breakdown: Dict[str, int] = field(default_factory=dict)
    topic_breakdown: Dict[str, int] = field(default_factory=dict)
    error_breakdown: Dict[str, int] = field(default_factory=dict)
    consumer_stats: Dict[str, Any] = field(default_factory=dict)
    sync_event_breakdown: Dict[str, int] = field(default_factory=dict)  # NEW: Breakdown by event type


class WorkerLifecycleManager:
    """
    Manages worker lifecycle including registration, health checks, and monitoring.

    Pure infrastructure management - no business logic.
    Enhanced with sync projections metrics.
    """

    def __init__(
            self,
            config: WorkerConfig,
            event_bus: EventBus,
            get_health_status: Callable[[], Awaitable[HealthStatus]],
            get_metrics: Callable[[], Awaitable[WorkerMetrics]]
    ):
        """
        Initialize the lifecycle manager.

        Args:
            config: Worker configuration
            event_bus: Event bus for publishing events
            get_health_status: Callback to get current health status
            get_metrics: Callback to get current metrics
        """
        self.config = config
        self.event_bus = event_bus
        self._get_health_status = get_health_status
        self._get_metrics = get_metrics

        # State
        self._start_time = time.time()
        self._running = False
        self._stop_requested = False

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None

        # Resource monitoring (initialized once to avoid repeated imports)
        self._process = None
        try:
            import psutil
            self._process = psutil.Process()
            # Prime the CPU measurement cache (first call initializes, returns 0.0)
            self._process.cpu_percent(interval=None)
        except ImportError:
            pass

        # Startup info for logging
        self._startup_info = self._build_startup_info()

    def _build_startup_info(self) -> Dict[str, Any]:
        """Build startup information for logging"""
        return {
            "instance_id": self.config.worker_id,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "version": "0.6.0",
            "transport": "RedPanda",
            "consumer_group_prefix": self.config.consumer_group_prefix,
            "topics": self.config.topics,
            "features": {
                "cqrs_buses": self.config.enable_command_bus and self.config.enable_query_bus,
                "sequence_tracking": self.config.enable_sequence_tracking,
                "gap_detection": self.config.enable_gap_detection,
                "self_healing": self.config.enable_self_healing,
                "projection_monitoring": self.config.enable_projection_monitoring,
                "sync_projection_monitoring": self.config.enable_sync_projection_monitoring,
                "virtual_broker": self.config.enable_virtual_broker,
                "saga_processing": self.config.enable_saga_processing,
                "admin_endpoints": self.config.enable_admin_endpoints
            }
        }

    def print_startup_banner(self) -> None:
        """Print the startup banner with configuration details"""
        log.info("=" * 80)
        log.info(f" Worker Starting")
        log.info(f"Instance ID: {self.config.worker_id}")
        log.info(f"Transport: RedPanda")
        log.info("=" * 80)
        log.info("Configuration:")
        log.info(f"  Consumer Group: {self.config.consumer_group_prefix}")
        log.info(f"  Topics: {', '.join(self.config.topics)}")
        log.info(f"  DLQ Topic: {self.config.dlq_topic}")
        log.info(f"  Max Retries: {self.config.max_retries}")
        log.info(f"  Batch Size: {self.config.consumer_batch_size}")
        log.info("=" * 80)
        log.info("Features:")
        log.info(
            f"  CQRS Buses: {'enabled' if (self.config.enable_command_bus and self.config.enable_query_bus) else 'disabled'}")
        log.info(f"  Sequence Tracking: {'enabled' if self.config.enable_sequence_tracking else 'disabled'}")
        log.info(f"  Gap Detection: {'enabled' if self.config.enable_gap_detection else 'disabled'}")
        log.info(f"  Self Healing: {'enabled' if self.config.enable_self_healing else 'disabled'}")
        log.info(f"  Projection Monitoring: {'enabled' if self.config.enable_projection_monitoring else 'disabled'}")
        log.info(
            f"  Sync Projection Monitoring: {'enabled' if self.config.enable_sync_projection_monitoring else 'disabled'}")
        log.info(f"  Virtual Broker: {'enabled' if self.config.enable_virtual_broker else 'disabled'}")
        log.info(f"  Saga Processing: {'enabled' if self.config.enable_saga_processing else 'disabled'}")
        log.info(f"  Admin Endpoints: {'enabled' if self.config.enable_admin_endpoints else 'disabled'}")
        log.info("=" * 80)
        log.info("Monitoring:")
        log.info(f"  Health Check Interval: {self.config.health_check_interval}s")
        log.info(f"  Metrics Publish Interval: {self.config.metrics_interval}s")
        log.info(f"  Heartbeat TTL: {self.config.heartbeat_ttl}s")
        log.info("=" * 80)

    async def register_worker(self) -> None:
        """Register worker instance in Redis"""
        worker_info = {
            **self._startup_info,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "topics": self.config.topics
        }

        key = f"{self.config.worker_registry_key}:{self.config.worker_id}"
        await safe_set(key, json.dumps(worker_info), ttl_seconds=self.config.heartbeat_ttl)
        await hincrby(self.config.worker_metrics_key, "total_workers", 1)

        log.info(f"Registered worker instance: {self.config.worker_id}")

    async def deregister_worker(self) -> None:
        """Remove worker from registry"""
        key = f"{self.config.worker_registry_key}:{self.config.worker_id}"
        await safe_delete(key)
        await hincrby(self.config.worker_metrics_key, "total_workers", -1)

        log.info(f"Deregistered worker instance: {self.config.worker_id}")

    async def create_readiness_file(self) -> None:
        """Create readiness file to indicate worker is ready"""
        self.config.readiness_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.readiness_file_path.touch(exist_ok=True)
        log.debug(f"Created readiness file: {self.config.readiness_file_path}")

    async def cleanup_files(self) -> None:
        """Remove readiness and health check files"""
        try:
            self.config.readiness_file_path.unlink(missing_ok=True)
            self.config.health_check_file_path.unlink(missing_ok=True)
            log.debug("Cleaned up lifecycle files")
        except OSError as e:
            log.warning(f"Error cleaning up files: {e}")

    async def start(self) -> None:
        """Start all lifecycle management tasks"""
        if self._running:
            log.warning("Lifecycle manager already running")
            return

        log.info("Starting worker lifecycle management")
        self._running = True
        self._stop_requested = False

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name="heartbeat-loop"
        )
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(),
            name="health-check-loop"
        )
        self._metrics_task = asyncio.create_task(
            self._metrics_loop(),
            name="metrics-loop"
        )

        log.info("Worker lifecycle management started")

    async def stop(self) -> None:
        """Stop all lifecycle management tasks"""
        log.info("Stopping worker lifecycle management")
        self._stop_requested = True
        self._running = False

        # Cancel background tasks
        tasks = [
            self._heartbeat_task,
            self._health_check_task,
            self._metrics_task
        ]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        log.info("Worker lifecycle management stopped")

    async def publish_startup_event(self) -> None:
        """Publish worker startup event"""
        await self._publish_worker_event("worker_startup", {
            "message": "Worker started successfully",
            **self._startup_info
        })

    async def publish_shutdown_event(self, metrics: WorkerMetrics) -> None:
        """Publish worker shutdown event with enhanced metrics"""
        await self._publish_worker_event("worker_shutdown", {
            "message": "Worker shutting down",
            "uptime_seconds": int(time.time() - self._start_time),
            "metrics": {
                "processed_events": metrics.processed_events,
                "failed_events": metrics.failed_events,
                "saga_events": metrics.saga_events,
                "saga_triggered": metrics.saga_triggered,
                "sync_events_skipped": metrics.sync_events_skipped
            }
        })

    async def _heartbeat_loop(self) -> None:
        """Update worker heartbeat and status - infrastructure metrics only"""
        while not self._stop_requested:
            try:
                # Get resource usage (non-blocking)
                memory_mb = 0
                cpu_percent = 0

                if self._process:
                    try:
                        memory_mb = self._process.memory_info().rss / 1024 / 1024
                        # Use interval=None for instant non-blocking measurement
                        # This uses cached value from previous call, avoiding 100ms block
                        cpu_percent = self._process.cpu_percent(interval=None)
                    except Exception:
                        # Process may have been terminated or monitoring failed
                        pass

                # Get current metrics
                metrics = await self._get_metrics()

                # Build status with infrastructure info only
                worker_status = {
                    "instance_id": self.config.worker_id,
                    "hostname": socket.gethostname(),
                    "pid": os.getpid(),
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": int(time.time() - self._start_time),
                    "status": "running",
                    "metrics": {
                        "processed_events": metrics.processed_events,
                        "failed_events": metrics.failed_events,
                        "saga_events": metrics.saga_events,
                        "saga_triggered": metrics.saga_triggered,
                        "sync_events_skipped": metrics.sync_events_skipped
                    },
                    "resources": {
                        "memory_mb": round(memory_mb, 2),
                        "cpu_percent": round(cpu_percent, 2)
                    },
                    "features": {
                        "sync_projection_monitoring": self.config.enable_sync_projection_monitoring
                    }
                }

                key = f"{self.config.worker_registry_key}:{self.config.worker_id}"
                await safe_set(key, json.dumps(worker_status), ttl_seconds=self.config.heartbeat_ttl)

                await asyncio.sleep(self.config.heartbeat_ttl // 2)

            except Exception as e:
                log.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _health_check_loop(self) -> None:
        """Periodic health check - infrastructure components only"""
        while not self._stop_requested:
            try:
                # Get infrastructure health status
                health = await self._get_health_status()

                # Build health data - infrastructure only
                health_data = {
                    "timestamp": health.timestamp.isoformat(),
                    "worker_id": self.config.worker_id,
                    "uptime_seconds": round(time.time() - self._start_time),
                    "infrastructure": {
                        "redis": {
                            "healthy": health.redis_healthy,
                            "circuit_breaker": "open" if not health.redis_healthy else "closed"
                        },
                        "postgres": {
                            "healthy": health.postgres_healthy,
                            "circuit_breaker": "open" if not health.postgres_healthy else "closed"
                        },
                        "event_bus": {
                            "healthy": health.event_bus_healthy
                        },
                        "consumer_manager": {
                            "healthy": health.consumer_manager_healthy
                        }
                    },
                    "overall_healthy": health.overall_healthy,
                    "details": health.details,
                    "monitoring": {
                        "sync_projections": self.config.enable_sync_projection_monitoring
                    }
                }

                # Write health file
                self.config.health_check_file_path.parent.mkdir(parents=True, exist_ok=True)
                self.config.health_check_file_path.write_text(json.dumps(health_data, indent=2))

                # Publish health event
                await self._publish_worker_event("worker_health_check", health_data)

                log.info(
                    f"Infrastructure health - "
                    f"Redis: {health.redis_healthy}, "
                    f"PG: {health.postgres_healthy}, "
                    f"EventBus: {health.event_bus_healthy}, "
                    f"Consumers: {health.consumer_manager_healthy}, "
                    f"Overall: {health.overall_healthy}"
                )

                await asyncio.sleep(self.config.health_check_interval)

            except Exception as e:
                log.error(f"Health check error: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _metrics_loop(self) -> None:
        """Publish processing metrics periodically with sync projections data"""
        while not self._stop_requested:
            try:
                await asyncio.sleep(self.config.metrics_interval)

                # Get current metrics
                metrics = await self._get_metrics()

                # Build metrics data - pure processing metrics
                metrics_data = {
                    "period_seconds": self.config.metrics_interval,
                    "events": {
                        "processed": metrics.processed_events,
                        "failed": metrics.failed_events,
                        "retried": metrics.retry_events,
                        "saga_events": metrics.saga_events,
                        "saga_triggered": metrics.saga_triggered,
                        "sync_events_skipped": metrics.sync_events_skipped
                    },
                    "breakdown": {
                        "by_event_type": dict(metrics.event_type_breakdown),
                        "by_topic": dict(metrics.topic_breakdown),
                        "by_error": dict(metrics.error_breakdown),
                        "by_sync_event": dict(metrics.sync_event_breakdown) if hasattr(metrics,
                                                                                       'sync_event_breakdown') else {}
                    },
                    "consumer_stats": metrics.consumer_stats,
                    "sync_projections": {
                        "monitoring_enabled": self.config.enable_sync_projection_monitoring,
                        "events_processed_async": metrics.sync_events_skipped
                    }
                }

                await self._publish_worker_event("worker_metrics", metrics_data)

                # Enhanced logging for sync events
                if metrics.sync_events_skipped > 0:
                    log.info(
                        f"Published metrics - "
                        f"Processed: {metrics.processed_events}, "
                        f"Failed: {metrics.failed_events}, "
                        f"Sagas: {metrics.saga_triggered}, "
                        f"Sync Events (Async): {metrics.sync_events_skipped}"
                    )
                else:
                    log.info(
                        f"Published metrics - "
                        f"Processed: {metrics.processed_events}, "
                        f"Failed: {metrics.failed_events}, "
                        f"Sagas: {metrics.saga_triggered}"
                    )

                # Save sync projection metrics to Redis if significant
                if self.config.enable_sync_projection_monitoring and metrics.sync_events_skipped > 0:
                    await self._save_sync_projection_metrics(metrics)

            except Exception as e:
                log.error(f"Metrics error: {e}")

    async def _save_sync_projection_metrics(self, metrics: WorkerMetrics) -> None:
        """Save sync projection metrics to Redis for monitoring"""
        try:
            from app.infra.persistence.redis_client import safe_set

            key = f"{self.config.sync_projection_metrics_prefix}:{self.config.worker_id}"

            sync_metrics = {
                "worker_id": self.config.worker_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sync_events_skipped": metrics.sync_events_skipped,
                "sync_event_breakdown": dict(getattr(metrics, 'sync_event_breakdown', {})),
                "total_processed": metrics.processed_events
            }

            await safe_set(key, json.dumps(sync_metrics), ttl_seconds=3600)  # Keep for 1 hour

        except Exception as e:
            log.warning(f"Failed to save sync projection metrics: {e}")

    async def _publish_worker_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish worker monitoring events"""
        if not self.event_bus:
            return

        try:
            event_data = {
                "event_id": generate_event_id(),
                "event_type": event_type,
                "worker_id": self.config.worker_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                **data
            }

            await self.event_bus.publish(self.config.worker_events_topic, event_data)

        except Exception as e:
            log.error(f"Failed to publish worker event: {e}")

    def get_uptime_seconds(self) -> int:
        """Get worker uptime in seconds"""
        return int(time.time() - self._start_time)

    def is_running(self) -> bool:
        """Check if lifecycle manager is running"""
        return self._running


# Helper function for infrastructure health checks
async def check_infrastructure_health(
        event_bus: EventBus,
        consumer_manager_healthy: bool
) -> HealthStatus:
    """
    Check health of infrastructure components only.
    No business logic checks, no Event Store checks.
    """
    # Get circuit breaker states
    redis_cb = get_redis_circuit_breaker()
    pg_cb = get_pg_circuit_breaker()

    redis_healthy = redis_cb.can_execute() if redis_cb else False
    pg_healthy = pg_cb.can_execute() if pg_cb else False
    event_bus_healthy = event_bus is not None

    # Overall health is based on infrastructure only
    overall_healthy = all([
        redis_healthy,
        pg_healthy,
        event_bus_healthy,
        consumer_manager_healthy
    ])

    # Get circuit breaker states asynchronously if they're async methods
    redis_state = "unknown"
    pg_state = "unknown"

    try:
        if redis_cb:
            # Check if get_state is async
            state_result = redis_cb.get_state()
            if asyncio.iscoroutine(state_result):
                state = await state_result
                redis_state = state.name if hasattr(state, 'name') else str(state)
            else:
                redis_state = state_result.name if hasattr(state_result, 'name') else str(state_result)
    except Exception as e:
        log.warning(f"Failed to get Redis circuit breaker state: {e}")

    try:
        if pg_cb:
            # Check if get_state is async
            state_result = pg_cb.get_state()
            if asyncio.iscoroutine(state_result):
                state = await state_result
                pg_state = state.name if hasattr(state, 'name') else str(state)
            else:
                pg_state = state_result.name if hasattr(state_result, 'name') else str(state_result)
    except Exception as e:
        log.warning(f"Failed to get PostgreSQL circuit breaker state: {e}")

    # Infrastructure details - Use getattr with defaults for safety
    details = {
        "circuit_breakers": {
            "redis": {
                "state": redis_state,
                "failures": getattr(redis_cb, 'failure_count', 0) if redis_cb else 0,
                "last_failure": getattr(redis_cb, 'last_failure_time', None) if redis_cb else None
            },
            "postgres": {
                "state": pg_state,
                "failures": getattr(pg_cb, 'failure_count', 0) if pg_cb else 0,
                "last_failure": getattr(pg_cb, 'last_failure_time', None) if pg_cb else None
            }
        },
        "sync_projections": {
            "monitoring_enabled": os.getenv("WORKER_ENABLE_SYNC_PROJECTION_MONITORING", "true").lower() == "true"
        }
    }

    return HealthStatus(
        redis_healthy=redis_healthy,
        postgres_healthy=pg_healthy,
        event_bus_healthy=event_bus_healthy,
        consumer_manager_healthy=consumer_manager_healthy,
        overall_healthy=overall_healthy,
        details=details
    )

# =============================================================================
# EOF
# =============================================================================