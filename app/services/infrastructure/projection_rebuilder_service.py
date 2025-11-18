# app/services/projection_rebuilder_service.py
"""
Projection Rebuilder Service - Using Existing Infrastructure

This version uses the existing reliability infrastructure from the codebase
instead of implementing custom circuit breakers and retry logic.
FIXED: Updated imports to match the actual reliability infrastructure used in saga_service.py
UPDATED: Using 'logger' instead of 'log' for consistency with codebase
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field

# Import existing reliability infrastructure - matching saga_service imports
try:
    from app.infra.reliability.circuit_breaker import (
        CircuitBreakerConfig, get_circuit_breaker
    )
    from app.infra.reliability.retry import retry_async, RetryConfig
    from app.config.reliability_config import ReliabilityConfigs

    # Try to import rate limiter if available
    try:
        from app.infra.reliability.rate_limiter import RateLimiter
    except ImportError:
        RateLimiter = None

    RELIABILITY_AVAILABLE = True
except ImportError as e:
    RELIABILITY_AVAILABLE = False
    # Don't log here since logger isn't defined yet
    # Fallback imports if reliability infra doesn't exist
    CircuitBreakerConfig = None
    get_circuit_breaker = None
    retry_async = None
    RetryConfig = None
    ReliabilityConfigs = None
    RateLimiter = None

from app.infra.event_store.projection_rebuilder import (
    ProjectionRebuilder,
    RebuildProgress,
    RebuildStatus,
    ProjectionConfig
)
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore
from app.infra.event_bus.event_bus import EventBus
from app.common.exceptions.exceptions import ProjectionRebuildError

logger = logging.getLogger("wellwon.projection_rebuilder_service")


class RebuildPriority(Enum):
    """Priority levels for rebuild operations"""
    LOW = "low"  # Scheduled maintenance
    NORMAL = "normal"  # Manual rebuilds
    HIGH = "high"  # Saga-initiated rebuilds
    CRITICAL = "critical"  # Emergency recovery


@dataclass
class RebuildRequest:
    """Request for projection rebuild with metadata"""
    projection_name: str
    priority: RebuildPriority
    requested_by: str  # "saga:AccountRecovery", "user:admin", "system:maintenance"
    requested_at: datetime
    reason: Optional[str] = None
    aggregate_filter: Optional[Dict[str, Any]] = None  # For targeted rebuilds
    dry_run: bool = False
    force: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceMetrics:
    """Metrics for monitoring service health"""
    total_rebuilds: int = 0
    successful_rebuilds: int = 0
    failed_rebuilds: int = 0
    cancelled_rebuilds: int = 0
    active_rebuilds: int = 0
    total_events_processed: int = 0
    total_events_published: int = 0
    average_rebuild_duration_seconds: float = 0.0
    last_rebuild_at: Optional[datetime] = None
    circuit_breaker_trips: int = 0
    retry_attempts: int = 0
    rate_limit_hits: int = 0


class ProjectionRebuilderService:
    """
    Production-ready Projection Rebuilder Service using existing infrastructure.

    Features:
    - Uses existing CircuitBreaker from infra/reliability
    - Uses existing RetryPolicy for resilient operations
    - Uses existing RateLimiter for resource protection (if available)
    - Priority-based rebuild queue
    - Comprehensive metrics and monitoring
    - Saga integration for automated recovery
    """

    def __init__(
            self,
            event_store: KurrentDBEventStore,
            event_bus: EventBus,
            command_bus=None,
            query_bus=None,
            config: Optional[Dict[str, Any]] = None
    ):
        self._event_store = event_store
        self._event_bus = event_bus
        self._command_bus = command_bus
        self._query_bus = query_bus

        # Configuration
        self._config = config or {}
        self._max_concurrent_rebuilds = self._config.get("max_concurrent_rebuilds", 3)

        # Core rebuilder
        self._rebuilder = ProjectionRebuilder(
            event_store=event_store,
            event_bus=event_bus,
            redis_prefix="projection_rebuild:",
            max_concurrent_rebuilds=self._max_concurrent_rebuilds,
            checkpoint_interval_seconds=self._config.get("checkpoint_interval", 30)
        )

        # Request queue (priority-based)
        self._request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_rebuilds: Dict[str, RebuildRequest] = {}

        # Initialize reliability components if available
        self._circuit_breakers: Dict[str, Any] = {}
        self._retry_configs: Dict[str, Any] = {}
        self._rate_limiter = None

        if RELIABILITY_AVAILABLE:
            self._init_reliability_components()
        else:
            logger.warning(
                "Reliability infrastructure not available - service will run without circuit breakers and retry policies")

        # Metrics
        self._metrics = ServiceMetrics()

        # Service state
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None

        # Register custom projections
        self._register_custom_projections()

        logger.info(
            f"ProjectionRebuilderService initialized with "
            f"max_concurrent={self._max_concurrent_rebuilds}, "
            f"reliability_infra={RELIABILITY_AVAILABLE}"
        )

    def _init_reliability_components(self):
        """Initialize reliability components from existing infrastructure"""
        # Create rate limiter for overall service if available
        if RateLimiter:
            self._rate_limiter = RateLimiter(
                max_requests=self._config.get("rate_limit_max_requests", 100),
                time_window=self._config.get("rate_limit_window_seconds", 60)
            )

        # Get retry configurations from ReliabilityConfigs if available
        if ReliabilityConfigs:
            # Use pre-configured settings
            self._default_retry_config = ReliabilityConfigs.redis_retry()
        elif RetryConfig:
            # Fallback to manual configuration
            self._default_retry_config = RetryConfig(
                max_attempts=self._config.get("retry_max_attempts", 3),
                initial_delay_ms=self._config.get("retry_initial_delay_ms", 1000),
                max_delay_ms=self._config.get("retry_max_delay_ms", 60000),
                backoff_factor=self._config.get("retry_backoff_factor", 2.0),
                jitter=self._config.get("retry_jitter", True)
            )

    def _get_circuit_breaker(self, projection_name: str):
        """Get or create circuit breaker for projection using existing infrastructure"""
        if not RELIABILITY_AVAILABLE or not get_circuit_breaker:
            return None

        if projection_name not in self._circuit_breakers:
            # Create circuit breaker config
            config = CircuitBreakerConfig(
                name=f"projection_rebuild_{projection_name}",
                failure_threshold=self._config.get("circuit_breaker_threshold", 5),
                reset_timeout_seconds=self._config.get("circuit_breaker_timeout_seconds", 300),
                half_open_max_calls=self._config.get("circuit_breaker_half_open_calls", 3),
                success_threshold=self._config.get("circuit_breaker_success_threshold", 2)
            )

            self._circuit_breakers[projection_name] = get_circuit_breaker(
                f"projection_rebuild_{projection_name}",
                config
            )

        return self._circuit_breakers[projection_name]

    async def _execute_with_circuit_breaker(self, projection_name: str, operation):
        """Execute operation with circuit breaker protection"""
        breaker = self._get_circuit_breaker(projection_name)
        if not breaker:
            # No circuit breaker available, execute directly
            return await operation()

        try:
            return await breaker.execute_async(operation)
        except Exception as e:
            self._metrics.circuit_breaker_trips += 1
            if "Circuit breaker is OPEN" in str(e):
                raise ProjectionRebuildError(f"Circuit breaker open for {projection_name}: {e}")
            raise

    async def _execute_with_retry(self, operation, context: str):
        """Execute operation with retry policy"""
        if not RELIABILITY_AVAILABLE or not retry_async:
            # No retry available, execute directly
            return await operation()

        self._metrics.retry_attempts += 1

        return await retry_async(
            operation,
            retry_config=self._default_retry_config,
            context=context
        )

    async def _check_rate_limit(self):
        """Check rate limit before processing"""
        if self._rate_limiter:
            allowed = await self._rate_limiter.allow_request()
            if not allowed:
                self._metrics.rate_limit_hits += 1
                raise ProjectionRebuildError("Rate limit exceeded for projection rebuilds")

    def _register_custom_projections(self) -> None:
        """Register any custom projection configurations"""
        custom_configs = self._config.get("custom_projections", {})
        for name, config_data in custom_configs.items():
            config = ProjectionConfig(**config_data)
            self._rebuilder.register_projection(config)
            logger.info(f"Registered custom projection: {name}")

    async def start(self) -> None:
        """Start the service worker"""
        if self._running:
            logger.warning("Service already running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("ProjectionRebuilderService started")

    async def stop(self) -> None:
        """Stop the service gracefully"""
        if not self._running:
            return

        logger.info("Stopping ProjectionRebuilderService...")
        self._running = False
        self._shutdown_event.set()

        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Wait for active rebuilds to complete
        if self._active_rebuilds:
            logger.info(f"Waiting for {len(self._active_rebuilds)} active rebuilds to complete...")
            await self._rebuilder.shutdown()

        logger.info("ProjectionRebuilderService stopped")

    async def _worker_loop(self) -> None:
        """Main worker loop processing rebuild requests"""
        logger.info("Rebuild worker started")

        while self._running:
            try:
                # Wait for request with timeout
                priority_value, request = await asyncio.wait_for(
                    self._request_queue.get(),
                    timeout=1.0
                )

                # Check rate limit
                try:
                    await self._check_rate_limit()
                except ProjectionRebuildError as e:
                    # Re-queue the request and wait
                    await self._request_queue.put((priority_value, request))
                    await asyncio.sleep(1.0)
                    continue

                # Check if we can process
                if len(self._active_rebuilds) >= self._max_concurrent_rebuilds:
                    # Re-queue the request
                    await self._request_queue.put((priority_value, request))
                    await asyncio.sleep(0.1)
                    continue

                # Process the request
                asyncio.create_task(self._process_rebuild_request(request))

            except asyncio.TimeoutError:
                # Check for shutdown
                if self._shutdown_event.is_set():
                    break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)

        logger.info("Rebuild worker stopped")

    async def _process_rebuild_request(self, request: RebuildRequest) -> None:
        """Process a single rebuild request with reliability features"""
        projection_name = request.projection_name

        try:
            # Track active rebuild
            self._active_rebuilds[projection_name] = request
            self._metrics.active_rebuilds = len(self._active_rebuilds)

            # Log start
            logger.info(
                f"Starting {request.priority.value} priority rebuild of {projection_name} "
                f"requested by {request.requested_by} (reason: {request.reason})"
            )

            start_time = datetime.now(timezone.utc)

            # Define the rebuild operation
            async def rebuild_operation():
                # Simple wrapper for projection_rebuilder since it already has from_timestamp parameter
                if hasattr(self._rebuilder, 'rebuild_projection'):
                    return await self._rebuilder.rebuild_projection(
                        projection_name=projection_name,
                        force=request.force,
                        dry_run=request.dry_run
                    )
                else:
                    # Fallback if method signature is different
                    raise ProjectionRebuildError(f"Rebuild method not available for {projection_name}")

            # Execute with reliability wrappers
            if request.force:
                # Force mode bypasses circuit breaker but still uses retry
                if RELIABILITY_AVAILABLE:
                    progress = await self._execute_with_retry(
                        rebuild_operation,
                        f"rebuild_{projection_name}"
                    )
                else:
                    progress = await rebuild_operation()
            else:
                # Normal mode uses circuit breaker and retry
                if RELIABILITY_AVAILABLE:
                    async def protected_operation():
                        return await self._execute_with_retry(
                            rebuild_operation,
                            f"rebuild_{projection_name}"
                        )

                    progress = await self._execute_with_circuit_breaker(projection_name, protected_operation)
                else:
                    progress = await rebuild_operation()

            # Update metrics
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._update_metrics_on_success(progress, duration)

            # Publish completion event
            await self._publish_rebuild_event(
                "ProjectionRebuildCompleted",
                request,
                progress,
                {"duration_seconds": duration}
            )

            logger.info(
                f"Completed rebuild of {projection_name} in {duration:.2f}s "
                f"(processed: {progress.events_processed}, published: {progress.events_published})"
            )

        except Exception as e:
            # Update metrics
            self._metrics.failed_rebuilds += 1

            # Publish failure event
            await self._publish_rebuild_event(
                "ProjectionRebuildFailed",
                request,
                None,
                {"error": str(e)}
            )

            logger.error(
                f"Failed to rebuild {projection_name} requested by {request.requested_by}: {e}",
                exc_info=True
            )

        finally:
            # Clean up
            self._active_rebuilds.pop(projection_name, None)
            self._metrics.active_rebuilds = len(self._active_rebuilds)

    def _update_metrics_on_success(self, progress: RebuildProgress, duration: float) -> None:
        """Update metrics after successful rebuild"""
        self._metrics.total_rebuilds += 1
        self._metrics.successful_rebuilds += 1
        self._metrics.total_events_processed += progress.events_processed
        self._metrics.total_events_published += progress.events_published
        self._metrics.last_rebuild_at = datetime.now(timezone.utc)

        # Update average duration
        if self._metrics.average_rebuild_duration_seconds == 0:
            self._metrics.average_rebuild_duration_seconds = duration
        else:
            # Running average
            self._metrics.average_rebuild_duration_seconds = (
                    (self._metrics.average_rebuild_duration_seconds * (
                            self._metrics.successful_rebuilds - 1) + duration)
                    / self._metrics.successful_rebuilds
            )

    async def _publish_rebuild_event(
            self,
            event_type: str,
            request: RebuildRequest,
            progress: Optional[RebuildProgress],
            extra_data: Dict[str, Any]
    ) -> None:
        """Publish rebuild lifecycle events"""
        try:
            event_data = {
                "event_type": event_type,
                "projection_name": request.projection_name,
                "priority": request.priority.value,
                "requested_by": request.requested_by,
                "reason": request.reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **extra_data
            }

            if progress:
                event_data.update({
                    "events_processed": progress.events_processed,
                    "events_published": progress.events_published,
                    "status": progress.status.value
                })

            # Mark as critical event if priority is high or critical
            if request.priority in [RebuildPriority.HIGH, RebuildPriority.CRITICAL]:
                if hasattr(self._event_bus, 'mark_channel_as_critical'):
                    self._event_bus.mark_channel_as_critical("system.projection-rebuilds")

            await self._event_bus.publish("system.projection-rebuilds", event_data)

        except Exception as e:
            logger.error(f"Failed to publish rebuild event: {e}")

    # =====================================================================
    # PUBLIC API
    # =====================================================================

    async def rebuild_aggregate_projections(
            self,
            aggregate_type: str,
            aggregate_id: Optional[UUID] = None,
            projection_types: Optional[List[str]] = None,
            requested_by: str = "saga:unknown",
            reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rebuild projections for a specific aggregate.
        This is the primary method used by sagas during recovery.
        """
        # Map aggregate types to projections
        projection_mapping = {
            "BrokerConnection": ["broker_connections"],
            "BrokerAccount": ["broker_accounts"],
            "Account": ["broker_accounts"],
            "UserAccount": ["users"],
            "User": ["users"],
            "Order": ["orders"],
            "Position": ["positions", "broker_accounts"],  # Positions affect account balances
        }

        projection_names = projection_mapping.get(aggregate_type, [])
        if not projection_names:
            logger.warning(f"No projection mapping for aggregate type: {aggregate_type}")
            return {
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id) if aggregate_id else None,
                "projections_rebuilt": [],
                "status": "no_projections"
            }

        # Filter by requested types if specified
        if projection_types:
            projection_names = [p for p in projection_names if p in projection_types]

        results = []

        for projection_name in projection_names:
            # Create high-priority request
            request = RebuildRequest(
                projection_name=projection_name,
                priority=RebuildPriority.HIGH,
                requested_by=requested_by,
                requested_at=datetime.now(timezone.utc),
                reason=reason or f"Aggregate recovery for {aggregate_type}:{aggregate_id}",
                aggregate_filter={
                    "aggregate_type": aggregate_type,
                    "aggregate_id": str(aggregate_id) if aggregate_id else None
                },
                force=True  # Always force for recovery
            )

            # Queue the request - fixed to use tuple
            await self._request_queue.put((request.priority.value, request))

            results.append({
                "projection": projection_name,
                "queued": True,
                "priority": request.priority.value
            })

        return {
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id) if aggregate_id else None,
            "projections_queued": results,
            "status": "queued"
        }

    async def rebuild_projection(
            self,
            projection_name: str,
            from_timestamp: Optional[datetime] = None,
            to_timestamp: Optional[datetime] = None,
            priority: RebuildPriority = RebuildPriority.NORMAL,
            requested_by: str = "user:unknown",
            reason: Optional[str] = None,
            force: bool = False,
            dry_run: bool = False
    ) -> RebuildProgress:
        """
        Queue a projection rebuild request and wait for completion.
        This method is used by sagas for direct projection rebuilds.
        """
        # If service is not running, execute directly
        if not self._running:
            logger.warning("Service not running, executing rebuild directly")
            return await self._rebuilder.rebuild_projection(
                projection_name=projection_name,
                from_timestamp=from_timestamp,
                force=force,
                dry_run=dry_run
            )

        # Validate projection exists
        if not hasattr(self._rebuilder, '_projection_configs'):
            # Fallback - assume projection is valid
            logger.warning(f"Cannot validate projection {projection_name}, proceeding anyway")
        elif projection_name not in self._rebuilder._projection_configs:
            raise ValueError(f"Unknown projection: {projection_name}")

        # Check if already rebuilding
        if projection_name in self._active_rebuilds:
            active = self._active_rebuilds[projection_name]

            # If force is true and it's the same request, wait for completion
            if force:
                logger.info(f"Force rebuild requested, waiting for active rebuild to complete")
                # Wait up to 5 minutes for active rebuild
                max_wait = 300
                start_wait = datetime.now(timezone.utc)

                while projection_name in self._active_rebuilds:
                    if (datetime.now(timezone.utc) - start_wait).total_seconds() > max_wait:
                        raise ProjectionRebuildError(f"Timeout waiting for active rebuild of {projection_name}")
                    await asyncio.sleep(1)

                # Now queue our rebuild
            else:
                # Return existing rebuild info
                existing_progress = await self._rebuilder.get_rebuild_status(projection_name)
                if existing_progress:
                    return existing_progress['progress']

                raise ProjectionRebuildError(
                    f"Projection {projection_name} is already being rebuilt by {active.requested_by}"
                )

        # Create request
        request = RebuildRequest(
            projection_name=projection_name,
            priority=priority,
            requested_by=requested_by,
            requested_at=datetime.now(timezone.utc),
            reason=reason,
            force=force,
            dry_run=dry_run,
            metadata={
                "from_timestamp": from_timestamp.isoformat() if from_timestamp else None,
                "to_timestamp": to_timestamp.isoformat() if to_timestamp else None
            }
        )

        # Queue the request
        await self._request_queue.put((request.priority.value, request))

        # For high priority requests (like sagas), wait for completion
        if priority in [RebuildPriority.HIGH, RebuildPriority.CRITICAL]:
            logger.info(f"High priority rebuild requested, waiting for completion")

            # Wait for rebuild to start
            max_wait_start = 30
            start_wait = datetime.now(timezone.utc)

            while projection_name not in self._active_rebuilds:
                if (datetime.now(timezone.utc) - start_wait).total_seconds() > max_wait_start:
                    raise ProjectionRebuildError(f"Timeout waiting for rebuild of {projection_name} to start")
                await asyncio.sleep(0.1)

            # Wait for rebuild to complete
            max_wait_complete = 600  # 10 minutes
            start_wait = datetime.now(timezone.utc)

            while projection_name in self._active_rebuilds:
                if (datetime.now(timezone.utc) - start_wait).total_seconds() > max_wait_complete:
                    raise ProjectionRebuildError(f"Timeout waiting for rebuild of {projection_name} to complete")
                await asyncio.sleep(1)

            # Load and return the progress
            if hasattr(self._rebuilder, '_load_progress'):
                progress = await self._rebuilder._load_progress(projection_name)
                if progress:
                    return progress

            # Fallback - create a basic progress object
            return RebuildProgress(
                projection_name=projection_name,
                status=RebuildStatus.COMPLETED,
                events_processed=0,
                events_published=0
            )
        else:
            # For normal priority, return immediately with queued status
            return RebuildProgress(
                projection_name=projection_name,
                status=RebuildStatus.PENDING,
                events_processed=0,
                events_published=0,
                metadata={"queued": True, "queue_size": self._request_queue.qsize()}
            )

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        rebuilder_status = await self._rebuilder.get_rebuild_status()

        circuit_breaker_status = {}
        if RELIABILITY_AVAILABLE and self._circuit_breakers:
            for name, breaker in self._circuit_breakers.items():
                if hasattr(breaker, 'get_metrics'):
                    circuit_breaker_status[name] = breaker.get_metrics()
                else:
                    # Fallback for basic status
                    circuit_breaker_status[name] = {
                        "state": "unknown",
                        "can_execute": True
                    }

        return {
            "service": {
                "running": self._running,
                "queue_size": self._request_queue.qsize(),
                "active_rebuilds": len(self._active_rebuilds),
                "max_concurrent": self._max_concurrent_rebuilds,
                "reliability_infra": RELIABILITY_AVAILABLE
            },
            "metrics": {
                "total_rebuilds": self._metrics.total_rebuilds,
                "successful_rebuilds": self._metrics.successful_rebuilds,
                "failed_rebuilds": self._metrics.failed_rebuilds,
                "cancelled_rebuilds": self._metrics.cancelled_rebuilds,
                "total_events_processed": self._metrics.total_events_processed,
                "total_events_published": self._metrics.total_events_published,
                "average_duration_seconds": round(self._metrics.average_rebuild_duration_seconds, 2),
                "last_rebuild_at": self._metrics.last_rebuild_at.isoformat() if self._metrics.last_rebuild_at else None,
                "circuit_breaker_trips": self._metrics.circuit_breaker_trips,
                "retry_attempts": self._metrics.retry_attempts,
                "rate_limit_hits": self._metrics.rate_limit_hits
            },
            "circuit_breakers": circuit_breaker_status,
            "projections": rebuilder_status["projections"] if isinstance(rebuilder_status, dict) else {},
            "active_requests": {
                name: {
                    "priority": req.priority.value,
                    "requested_by": req.requested_by,
                    "reason": req.reason,
                    "started_at": req.requested_at.isoformat()
                }
                for name, req in self._active_rebuilds.items()
            }
        }

    async def cancel_rebuild(self, projection_name: str) -> bool:
        """Cancel an active rebuild"""
        return await self._rebuilder.cancel_rebuild(projection_name)

    async def rebuild_all_projections(
            self,
            priority: RebuildPriority = RebuildPriority.LOW,
            requested_by: str = "system:maintenance",
            reason: Optional[str] = None,
            force: bool = False,
            parallel: bool = False
    ) -> Dict[str, Any]:
        """Queue rebuild of all projections"""
        if parallel and hasattr(self._rebuilder, 'rebuild_all_projections'):
            # Use the rebuilder's parallel capability directly
            results = await self._rebuilder.rebuild_all_projections(
                force=force,
                parallel=True
            )

            return {
                "status": "completed",
                "mode": "parallel",
                "results": {
                    name: {
                        "status": progress.status.value,
                        "events_processed": progress.events_processed,
                        "events_published": progress.events_published
                    }
                    for name, progress in results.items()
                }
            }
        else:
            # Queue individual requests respecting dependencies
            if hasattr(self._rebuilder, '_topological_sort'):
                sorted_projections = self._rebuilder._topological_sort()
            else:
                # Fallback - use all known projections
                sorted_projections = list(self._rebuilder._projection_configs.keys()) if hasattr(self._rebuilder,
                                                                                                 '_projection_configs') else []

            queued = []

            for projection_name in sorted_projections:
                request = RebuildRequest(
                    projection_name=projection_name,
                    priority=priority,
                    requested_by=requested_by,
                    requested_at=datetime.now(timezone.utc),
                    reason=reason or "Full rebuild requested",
                    force=force
                )

                await self._request_queue.put((request.priority.value, request))
                queued.append(projection_name)

            return {
                "status": "queued",
                "mode": "sequential",
                "projections_queued": queued,
                "queue_size": self._request_queue.qsize()
            }

    async def get_projection_config(self, projection_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific projection"""
        if not hasattr(self._rebuilder, '_projection_configs'):
            return None

        config = self._rebuilder._projection_configs.get(projection_name)
        if not config:
            return None

        return {
            "name": config.name,
            "aggregate_type": config.aggregate_type,
            "event_types": config.event_types,
            "transport_topic": config.transport_topic,
            "batch_size": config.batch_size,
            "dependencies": config.dependencies,
            "enabled": config.enabled
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for monitoring"""
        healthy = True
        issues = []

        # Check if service is running
        if not self._running:
            healthy = False
            issues.append("Service not running")

        # Check for stuck rebuilds
        for name, request in self._active_rebuilds.items():
            age = (datetime.now(timezone.utc) - request.requested_at).total_seconds()
            if age > 3600:  # 1 hour
                issues.append(f"Rebuild {name} running for {age:.0f} seconds")

        # Check circuit breakers if available
        if RELIABILITY_AVAILABLE and self._circuit_breakers:
            for name, breaker in self._circuit_breakers.items():
                if hasattr(breaker, 'is_open') and breaker.is_open():
                    issues.append(f"Circuit breaker open for {name}")

        return {
            "healthy": healthy and len(issues) == 0,
            "issues": issues,
            "metrics": {
                "queue_size": self._request_queue.qsize(),
                "active_rebuilds": len(self._active_rebuilds),
                "reliability_enabled": RELIABILITY_AVAILABLE
            }
        }


def create_projection_rebuilder_service(
        event_store: KurrentDBEventStore,
        event_bus: EventBus,
        command_bus=None,
        query_bus=None,
        config: Optional[Dict[str, Any]] = None
) -> ProjectionRebuilderService:
    """
    Factory function to create ProjectionRebuilderService.

    Configuration options:
    - max_concurrent_rebuilds: Maximum concurrent rebuild operations (default: 3)
    - checkpoint_interval: Checkpoint interval in seconds (default: 30)
    - circuit_breaker_threshold: Failure threshold before opening (default: 5)
    - circuit_breaker_timeout_seconds: Recovery timeout (default: 300)
    - circuit_breaker_success_threshold: Successes needed to close (default: 2)
    - retry_max_attempts: Maximum retry attempts (default: 3)
    - retry_initial_delay_ms: Initial retry delay in milliseconds (default: 1000)
    - retry_max_delay_ms: Maximum retry delay in milliseconds (default: 60000)
    - retry_backoff_factor: Exponential backoff factor (default: 2.0)
    - retry_jitter: Add jitter to retry delays (default: True)
    - rate_limit_max_requests: Max requests per window (default: 100)
    - rate_limit_window_seconds: Rate limit window (default: 60)
    - custom_projections: Dict of custom projection configurations
    """
    service = ProjectionRebuilderService(
        event_store=event_store,
        event_bus=event_bus,
        command_bus=command_bus,
        query_bus=query_bus,
        config=config or {}
    )

    logger.info(
        f"Created ProjectionRebuilderService "
        f"(reliability_infra={'available' if RELIABILITY_AVAILABLE else 'not available'})"
    )

    return service