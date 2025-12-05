# app/infra/event_store/projection_rebuilder.py
# =============================================================================
# File: app/infra/event_store/projection_rebuilder.py
# Description: FIXED - Enhanced projection rebuilder with proper transport routing
# FIXED: Proper transport topic routing and rebuild event handling
# =============================================================================

import asyncio
import logging
import json
import os
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID

from app.utils.uuid_utils import generate_uuid, generate_event_id
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore
from app.infra.event_store.event_envelope import EventEnvelope
from app.infra.event_bus.event_bus import EventBus
from app.infra.persistence.redis_client import redis_client
from app.common.exceptions.exceptions import ProjectionRebuildError

log = logging.getLogger("wellwon.projection_rebuilder")


class RebuildStatus(Enum):
    """Status of a projection rebuild"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RebuildProgress:
    """Tracks progress of a projection rebuild"""
    projection_name: str
    status: RebuildStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_checkpoint: Optional[datetime] = None
    events_processed: int = 0
    events_published: int = 0  # FIXED: Track published events
    errors: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "projection_name": self.projection_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_checkpoint": self.last_checkpoint.isoformat() if self.last_checkpoint else None,
            "events_processed": self.events_processed,
            "events_published": self.events_published,  # FIXED: Include in serialization
            "errors": self.errors[-10:],  # Keep last 10 errors
            "last_error": self.last_error,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RebuildProgress':
        return cls(
            projection_name=data["projection_name"],
            status=RebuildStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            last_checkpoint=datetime.fromisoformat(data["last_checkpoint"]) if data.get("last_checkpoint") else None,
            events_processed=data.get("events_processed", 0),
            events_published=data.get("events_published", 0),  # FIXED: Load from dict
            errors=data.get("errors", []),
            last_error=data.get("last_error"),
            metadata=data.get("metadata", {})
        )


@dataclass
class ProjectionConfig:
    """FIXED: Enhanced configuration for a projection"""
    name: str
    aggregate_type: Optional[str]
    event_types: Optional[List[str]]
    transport_topic: str
    batch_size: int = 100
    checkpoint_interval: int = 1000  # Checkpoint every N events
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)  # Other projections that must be rebuilt first

    # FIXED: Enhanced configuration options
    skip_existing_events: bool = False  # Skip events already processed
    include_metadata: bool = True  # Include rebuild metadata in events
    dry_run_mode: bool = False  # Don't actually publish events
    filter_duplicates: bool = True  # Filter out duplicate events


class ProjectionRebuilder:
    """
    FIXED: Enhanced service for rebuilding projections from event store
    with proper transport routing and state management
    """

    def __init__(
            self,
            event_store: KurrentDBEventStore,
            event_bus: EventBus,
            redis_prefix: str = "projection_rebuild:",
            max_concurrent_rebuilds: int = 3,
            checkpoint_interval_seconds: int = 30
    ):
        self._event_store = event_store
        self._event_bus = event_bus
        self._redis_prefix = redis_prefix
        self._max_concurrent_rebuilds = max_concurrent_rebuilds
        self._checkpoint_interval = checkpoint_interval_seconds

        # Active rebuild tasks
        self._active_rebuilds: Dict[str, asyncio.Task] = {}

        # Projection configurations
        self._projection_configs: Dict[str, ProjectionConfig] = self._get_default_configs()

        # FIXED: Enhanced tracking
        self._event_counters: Dict[str, int] = {}
        self._duplicate_trackers: Dict[str, Set[str]] = {}  # Track processed event IDs

        # Shutdown flag
        self._shutdown = False

    def _get_default_configs(self) -> Dict[str, ProjectionConfig]:
        """Enhanced default projection configurations"""
        return {
            "users": ProjectionConfig(
                name="users",
                aggregate_type="user_account",
                event_types=["UserAccountCreated", "UserCreated", "UserPasswordChanged",
                             "UserAccountDeleted", "UserDeleted", "UserEmailVerified",
                             "UserProfileUpdated"],
                transport_topic="transport.user-account-events",
                batch_size=50  # Smaller batches for user events
            ),
        }

    def register_projection(self, config: ProjectionConfig) -> None:
        """Register a projection configuration"""
        self._projection_configs[config.name] = config
        log.info(f"Registered projection configuration: {config.name}")

    async def _acquire_rebuild_lock(self, projection_name: str, ttl_seconds: int = 3600) -> bool:
        """Acquire a distributed lock for rebuilding a projection"""
        lock_key = f"{self._redis_prefix}lock:{projection_name}"
        lock_value = f"{generate_uuid()}:{datetime.now(timezone.utc).isoformat()}"

        try:
            acquired = await redis_client.set(
                lock_key, lock_value, nx=True, ex=ttl_seconds
            )
            return bool(acquired)
        except Exception as e:
            log.error(f"Failed to acquire lock for {projection_name}: {e}")
            return False

    async def _release_rebuild_lock(self, projection_name: str) -> None:
        """Release the rebuild lock"""
        lock_key = f"{self._redis_prefix}lock:{projection_name}"
        try:
            await redis_client.delete(lock_key)
        except Exception as e:
            log.error(f"Failed to release lock for {projection_name}: {e}")

    async def _save_progress(self, progress: RebuildProgress) -> None:
        """Save rebuild progress to Redis"""
        key = f"{self._redis_prefix}progress:{progress.projection_name}"
        try:
            await redis_client.set(
                key,
                json.dumps(progress.to_dict()),
                ex=86400 * 7  # Keep for 7 days
            )
        except Exception as e:
            log.error(f"Failed to save progress for {progress.projection_name}: {e}")

    async def _load_progress(self, projection_name: str) -> Optional[RebuildProgress]:
        """Load rebuild progress from Redis"""
        key = f"{self._redis_prefix}progress:{projection_name}"
        try:
            data = await redis_client.get(key)
            if data:
                return RebuildProgress.from_dict(json.loads(data))
        except Exception as e:
            log.error(f"Failed to load progress for {projection_name}: {e}")
        return None

    async def _check_dependencies(self, projection_name: str) -> bool:
        """Check if all dependencies are rebuilt"""
        config = self._projection_configs.get(projection_name)
        if not config or not config.dependencies:
            return True

        for dep in config.dependencies:
            progress = await self._load_progress(dep)
            if not progress or progress.status != RebuildStatus.COMPLETED:
                log.warning(f"Dependency {dep} not completed for {projection_name}")
                return False

        return True

    async def rebuild_projection(
            self,
            projection_name: str,
            from_timestamp: Optional[datetime] = None,
            force: bool = False,
            dry_run: bool = False
    ) -> RebuildProgress:
        """
        FIXED: Rebuild a projection with enhanced error handling and transport routing
        """
        config = self._projection_configs.get(projection_name)
        if not config:
            raise ProjectionRebuildError(f"Unknown projection: {projection_name}")

        if not config.enabled:
            raise ProjectionRebuildError(f"Projection {projection_name} is disabled")

        # Check dependencies
        if not force and not await self._check_dependencies(projection_name):
            raise ProjectionRebuildError(
                f"Dependencies not met for {projection_name}. "
                f"Required: {config.dependencies}"
            )

        # Try to acquire lock
        if not await self._acquire_rebuild_lock(projection_name):
            # Check if already in progress
            progress = await self._load_progress(projection_name)
            if progress and progress.status == RebuildStatus.IN_PROGRESS:
                if not force:
                    raise ProjectionRebuildError(
                        f"Projection {projection_name} rebuild already in progress"
                    )
                log.warning(f"Force rebuilding {projection_name} despite active rebuild")

        # FIXED: Initialize progress with enhanced metadata
        progress = RebuildProgress(
            projection_name=projection_name,
            status=RebuildStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
            metadata={
                "from_timestamp": from_timestamp.isoformat() if from_timestamp else None,
                "dry_run": dry_run,
                "forced": force,
                "config": {
                    "aggregate_type": config.aggregate_type,
                    "event_types": config.event_types,
                    "transport_topic": config.transport_topic,
                    "batch_size": config.batch_size,
                    "dependencies": config.dependencies
                },
                "rebuild_id": str(generate_uuid())  # Unique rebuild identifier
            }
        )

        # Save initial progress
        await self._save_progress(progress)

        # Create rebuild task
        task = asyncio.create_task(
            self._rebuild_projection_task(progress, config, from_timestamp, dry_run)
        )

        self._active_rebuilds[projection_name] = task

        try:
            # Wait for completion
            await task
            return await self._load_progress(projection_name) or progress
        finally:
            # Cleanup
            await self._active_rebuilds.pop(projection_name, None)
            await self._release_rebuild_lock(projection_name)

    async def _rebuild_projection_task(
            self,
            progress: RebuildProgress,
            config: ProjectionConfig,
            from_timestamp: Optional[datetime],
            dry_run: bool
    ) -> None:
        """FIXED: Task that performs the actual rebuild with proper transport routing"""
        last_checkpoint_time = datetime.now(timezone.utc)
        events_since_checkpoint = 0
        rebuild_id = progress.metadata.get("rebuild_id", str(generate_uuid()))

        # FIXED: Initialize duplicate tracking
        if config.filter_duplicates:
            self._duplicate_trackers[progress.projection_name] = set()

        try:
            log.info(
                f"Starting rebuild of {progress.projection_name} "
                f"(from: {from_timestamp or 'beginning'}, dry_run: {dry_run}, rebuild_id: {rebuild_id})"
            )

            async def event_handler(envelope: EventEnvelope) -> None:
                nonlocal events_since_checkpoint, last_checkpoint_time

                if self._shutdown:
                    raise asyncio.CancelledError("Rebuild cancelled due to shutdown")

                # FIXED: Duplicate filtering
                if config.filter_duplicates:
                    event_key = f"{envelope.event_id}:{envelope.aggregate_version}"
                    if event_key in self._duplicate_trackers[progress.projection_name]:
                        log.debug(f"⏭Skipping duplicate event {envelope.event_id}")
                        return
                    self._duplicate_trackers[progress.projection_name].add(event_key)

                # FIXED: Process event with proper transport routing
                if not dry_run:
                    try:
                        # FIXED: Create enhanced transport event with rebuild metadata
                        transport_event = {
                            # Core event data
                            "event_id": str(envelope.event_id),
                            "event_type": envelope.event_type,
                            "aggregate_id": str(envelope.aggregate_id),
                            "aggregate_type": envelope.aggregate_type,
                            "aggregate_version": envelope.aggregate_version,
                            "event_data": envelope.event_data,
                            "event_version": envelope.event_version,

                            # Causation and correlation
                            "causation_id": str(envelope.causation_id) if envelope.causation_id else None,
                            "correlation_id": str(envelope.correlation_id) if envelope.correlation_id else None,
                            "saga_id": str(envelope.saga_id) if envelope.saga_id else None,

                            # Timing
                            "timestamp": envelope.stored_at.isoformat(),
                            "original_stored_at": envelope.stored_at.isoformat(),

                            # Sequencing
                            "sequence_number": envelope.sequence_number,

                            # FIXED: Enhanced rebuild metadata to prevent infinite loops
                            "_from_projection_rebuild": True,
                            "_rebuild_projection": progress.projection_name,
                            "_rebuild_id": rebuild_id,
                            "_rebuild_timestamp": datetime.now(timezone.utc).isoformat(),
                            "_original_event_store": True,

                            # Optional metadata
                            "metadata": envelope.metadata if config.include_metadata else None
                        }

                        # FIXED: Publish to correct transport topic with retry logic
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                await self._event_bus.publish(
                                    config.transport_topic,
                                    transport_event
                                )
                                progress.events_published += 1
                                break
                            except Exception as pub_e:
                                if attempt < max_retries - 1:
                                    log.warning(f"Retry {attempt + 1} publishing event {envelope.event_id}: {pub_e}")
                                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                                else:
                                    raise pub_e

                        log.debug(f"Published rebuilt event {envelope.event_id} to {config.transport_topic}")

                    except Exception as e:
                        error_info = {
                            "event_id": str(envelope.event_id),
                            "event_type": envelope.event_type,
                            "aggregate_id": str(envelope.aggregate_id),
                            "error": str(e),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "attempt": "publish_to_transport"
                        }
                        progress.errors.append(error_info)
                        progress.last_error = str(e)

                        log.error(
                            f"Error publishing rebuilt event {envelope.event_id} "
                            f"during {progress.projection_name} rebuild: {e}"
                        )

                # Update counters
                progress.events_processed += 1
                events_since_checkpoint += 1

                # Progress logging
                if progress.events_processed % 100 == 0:
                    log.info(
                        f"📊 Rebuild {progress.projection_name}: "
                        f"Processed {progress.events_processed} events, "
                        f"Published {progress.events_published} events"
                    )

                # Checkpoint if needed
                # CHECKPOINT ATOMICITY WARNING (2025-11-14):
                # This checkpoint save is NOT in the same transaction as the projection handler's
                # read model update. This means:
                # - If checkpoint save fails, events will be replayed on restart
                # - Projection handlers MUST be idempotent to handle replays
                # - For atomic checkpoints, projection handlers should save checkpoint in their
                #   own transaction using event_store.save_projection_checkpoint()
                now = datetime.now(timezone.utc)
                if (events_since_checkpoint >= config.checkpoint_interval or
                        (now - last_checkpoint_time).seconds >= self._checkpoint_interval):
                    progress.last_checkpoint = now
                    await self._save_progress(progress)
                    last_checkpoint_time = now
                    events_since_checkpoint = 0

                    log.debug(
                        f"Checkpoint saved for {progress.projection_name} at event {progress.events_processed}. "
                        f"Note: Not atomic with projection handler transaction (handlers must be idempotent)."
                    )

            # FIXED: Perform the replay with enhanced filtering
            log.info(f"🔄 Starting event replay for {progress.projection_name}")

            total = await self._event_store.replay_events_to_handler(
                handler=event_handler,
                aggregate_type=config.aggregate_type,
                event_types=config.event_types,
                from_timestamp=from_timestamp,
                batch_size=config.batch_size
            )

            # Mark as completed
            progress.status = RebuildStatus.COMPLETED
            progress.completed_at = datetime.now(timezone.utc)
            progress.metadata["total_events"] = total
            progress.metadata["success_rate"] = (
                progress.events_published / progress.events_processed
                if progress.events_processed > 0 else 1.0
            )

            await self._save_progress(progress)

            # FIXED: Enhanced completion logging
            duration = (progress.completed_at - progress.started_at).total_seconds()
            log.info(
                f"Completed rebuild of {progress.projection_name}. "
                f"Processed {total} events, Published {progress.events_published} events "
                f"in {duration:.2f} seconds. "
                f"Success rate: {progress.metadata['success_rate']:.2%}"
            )

            # Publish rebuild completion event
            await self._publish_rebuild_event("ProjectionRebuildCompleted", progress, config)

        except asyncio.CancelledError:
            progress.status = RebuildStatus.CANCELLED
            progress.last_error = "Rebuild cancelled"
            await self._save_progress(progress)
            log.warning(f"⏹Rebuild of {progress.projection_name} was cancelled")
            raise

        except Exception as e:
            progress.status = RebuildStatus.FAILED
            progress.last_error = str(e)
            progress.completed_at = datetime.now(timezone.utc)
            await self._save_progress(progress)

            log.error(
                f"Failed to rebuild {progress.projection_name}: {e}",
                exc_info=True
            )

            # Publish rebuild failure event
            await self._publish_rebuild_event("ProjectionRebuildFailed", progress, config)

            raise ProjectionRebuildError(f"Rebuild failed: {e}") from e

        finally:
            # Cleanup duplicate tracking
            if config.filter_duplicates:
                self._duplicate_trackers.pop(progress.projection_name, None)

    async def _publish_rebuild_event(
            self,
            event_type: str,
            progress: RebuildProgress,
            config: ProjectionConfig
    ) -> None:
        """
        Publish rebuild lifecycle events with retry logic.

        ENHANCED (2025-11-14): Added exponential backoff retry to ensure
        rebuild events are published for monitoring and observability.
        """
        rebuild_event = {
            "event_id": str(generate_uuid()),
            "event_type": event_type,
            "projection_name": progress.projection_name,
            "rebuild_id": progress.metadata.get("rebuild_id"),
            "status": progress.status.value,
            "events_processed": progress.events_processed,
            "events_published": progress.events_published,
            "errors_count": len(progress.errors),
            "duration_seconds": (
                (progress.completed_at - progress.started_at).total_seconds()
                if progress.completed_at and progress.started_at else None
            ),
            "config": {
                "aggregate_type": config.aggregate_type,
                "transport_topic": config.transport_topic,
                "batch_size": config.batch_size
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Retry logic with exponential backoff
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                await self._event_bus.publish("system.projection-rebuilds", rebuild_event)

                if attempt > 0:
                    log.info(
                        f"Successfully published rebuild event {event_type} for {progress.projection_name} "
                        f"on attempt {attempt + 1}/{max_retries}"
                    )
                else:
                    log.debug(f"Published rebuild event: {event_type} for {progress.projection_name}")

                return  # Success!

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 100ms, 200ms, 400ms
                    delay = 0.1 * (2 ** attempt)
                    log.warning(
                        f"Failed to publish rebuild event (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

        # All retries failed
        log.error(
            f"Failed to publish rebuild event {event_type} after {max_retries} attempts: {last_error}. "
            f"Event details stored in progress metadata for manual review."
        )

        # Store failed event in progress metadata for manual review
        progress.metadata["failed_rebuild_event"] = {
            "event_type": event_type,
            "event_data": rebuild_event,
            "error": str(last_error),
            "attempts": max_retries,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def rebuild_all_projections(
            self,
            force: bool = False,
            dry_run: bool = False,
            parallel: bool = False
    ) -> Dict[str, RebuildProgress]:
        """
        FIXED: Rebuild all projections respecting dependencies with enhanced error handling
        """
        results = {}

        # Sort projections by dependencies
        sorted_projections = self._topological_sort()

        if parallel:
            # Group by dependency level
            levels = self._group_by_dependency_level(sorted_projections)

            for level_idx, level in enumerate(levels):
                log.info(f"🔄 Processing dependency level {level_idx + 1}: {level}")

                # Run all projections in this level in parallel
                tasks = []
                for projection_name in level:
                    if self._projection_configs[projection_name].enabled:
                        task = asyncio.create_task(
                            self.rebuild_projection(
                                projection_name,
                                force=force,
                                dry_run=dry_run
                            )
                        )
                        tasks.append((projection_name, task))

                # Wait for all in this level to complete
                for projection_name, task in tasks:
                    try:
                        results[projection_name] = await task
                        log.info(f"Level {level_idx + 1} projection {projection_name} completed")
                    except Exception as e:
                        log.error(f"Failed to rebuild {projection_name}: {e}")
                        results[projection_name] = RebuildProgress(
                            projection_name=projection_name,
                            status=RebuildStatus.FAILED,
                            last_error=str(e)
                        )
        else:
            # Sequential rebuild
            for projection_name in sorted_projections:
                if self._projection_configs[projection_name].enabled:
                    try:
                        log.info(f"Sequential rebuild: {projection_name}")
                        results[projection_name] = await self.rebuild_projection(
                            projection_name,
                            force=force,
                            dry_run=dry_run
                        )
                        log.info(f"Sequential rebuild completed: {projection_name}")
                    except Exception as e:
                        log.error(f"Failed to rebuild {projection_name}: {e}")
                        results[projection_name] = RebuildProgress(
                            projection_name=projection_name,
                            status=RebuildStatus.FAILED,
                            last_error=str(e)
                        )

                        # Stop on failure in sequential mode
                        if not force:
                            log.error(f"Stopping sequential rebuild due to failure in {projection_name}")
                            break

        return results

    def _topological_sort(self) -> List[str]:
        """Sort projections by dependencies"""
        visited = set()
        stack = []

        def visit(name: str, path: Set[str] = None):
            if path is None:
                path = set()

            if name in path:
                raise ProjectionRebuildError(f"Circular dependency detected: {path}")

            if name not in visited:
                visited.add(name)
                path.add(name)

                config = self._projection_configs.get(name)
                if config:
                    for dep in config.dependencies:
                        if dep in self._projection_configs:
                            visit(dep, path)

                path.remove(name)
                stack.append(name)

        for name in self._projection_configs:
            if name not in visited:
                visit(name)

        return stack

    def _group_by_dependency_level(self, sorted_projections: List[str]) -> List[List[str]]:
        """Group projections by dependency level for parallel execution"""
        levels = []
        processed = set()

        while len(processed) < len(sorted_projections):
            current_level = []

            for name in sorted_projections:
                if name in processed:
                    continue

                config = self._projection_configs[name]
                # Can be processed if all dependencies are processed
                if all(dep in processed for dep in config.dependencies):
                    current_level.append(name)

            if not current_level:
                # Shouldn't happen if topological sort is correct
                raise ProjectionRebuildError("Cannot determine dependency levels")

            levels.append(current_level)
            processed.update(current_level)

        return levels

    async def get_rebuild_status(self, projection_name: str = None) -> Dict[str, Any]:
        """FIXED: Get status of rebuilds with enhanced information"""
        if projection_name:
            progress = await self._load_progress(projection_name)
            is_active = projection_name in self._active_rebuilds

            return {
                "projection": projection_name,
                "is_active": is_active,
                "progress": progress.to_dict() if progress else None,
                "locked": await redis_client.exists(f"{self._redis_prefix}lock:{projection_name}"),
                "config": self._projection_configs.get(projection_name, {}).name if self._projection_configs.get(
                    projection_name) else None
            }
        else:
            # Get all statuses
            statuses = {}

            for name in self._projection_configs:
                progress = await self._load_progress(name)
                is_active = name in self._active_rebuilds

                statuses[name] = {
                    "is_active": is_active,
                    "status": progress.status.value if progress else "never_run",
                    "events_processed": progress.events_processed if progress else 0,
                    "events_published": progress.events_published if progress else 0,
                    "last_run": progress.started_at.isoformat() if progress and progress.started_at else None,
                    "dependencies": self._projection_configs[name].dependencies,
                    "transport_topic": self._projection_configs[name].transport_topic
                }

            return {
                "projections": statuses,
                "active_rebuilds": list(self._active_rebuilds.keys()),
                "total_projections": len(self._projection_configs),
                "max_concurrent": self._max_concurrent_rebuilds
            }

    async def cancel_rebuild(self, projection_name: str) -> bool:
        """Cancel an active rebuild"""
        task = self._active_rebuilds.get(projection_name)
        if task and not task.done():
            task.cancel()
            log.info(f"⏹️ Cancelled rebuild of {projection_name}")
            return True
        return False

    async def shutdown(self) -> None:
        """Gracefully shutdown the rebuilder"""
        log.info("Shutting down projection rebuilder...")
        self._shutdown = True

        # Cancel all active rebuilds
        for name, task in list(self._active_rebuilds.items()):
            if not task.done():
                log.info(f"⏹️ Cancelling rebuild of {name}")
                task.cancel()

        # Wait for all tasks to complete
        if self._active_rebuilds:
            await asyncio.gather(
                *self._active_rebuilds.values(),
                return_exceptions=True
            )

        log.info("Projection rebuilder shutdown complete")


# FIXED: Convenience function for CLI usage
async def rebuild_projection_cli(
        projection_name: str,
        event_store: KurrentDBEventStore = None,
        event_bus: EventBus = None
) -> None:
    """CLI helper for rebuilding projections with enhanced logging"""
    if not event_store:
        from app.config.event_store_config import get_event_store_config
        from app.infra.event_store.projection_checkpoint_service import create_projection_checkpoint_service
        from app.infra.persistence import pg_client

        config = get_event_store_config()

        # REFACTORED (2025-11-14): Create checkpoint service for projection rebuilder
        # Projection rebuilder needs persistent checkpoints to track rebuild progress
        checkpoint_service = create_projection_checkpoint_service(pg_client=pg_client)

        event_store = KurrentDBEventStore(
            config=config,
            outbox_service=None,
            saga_manager=None,
            checkpoint_service=checkpoint_service  # REFACTORED: Use checkpoint service
        )
        await event_store.initialize()

    rebuilder = ProjectionRebuilder(event_store, event_bus)

    try:
        if projection_name == "all":
            results = await rebuilder.rebuild_all_projections()
            for name, progress in results.items():
                print(
                    f"{name}: {progress.status.value} - {progress.events_processed} events processed, {progress.events_published} published")
        else:
            progress = await rebuilder.rebuild_projection(projection_name)
            print(
                f"Rebuilt {projection_name}: {progress.status.value} - {progress.events_processed} events processed, {progress.events_published} published")
    finally:
        await event_store.close()
        await event_bus.close()

# =============================================================================
# EOF
# =============================================================================