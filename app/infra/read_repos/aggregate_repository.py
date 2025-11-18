# File: app/infra/read_repos/aggregate_repository.py
# =============================================================================
# File: app/infra/repositories/aggregate_repository.py
# Description: Enhanced Generic Aggregate Repository for Event Sourcing
#              with Distributed Locking, Event Sequencing, and Saga Support
# =============================================================================

from __future__ import annotations

import logging
import asyncio
from typing import Type, TypeVar, Optional, List, Dict, Any, Protocol, runtime_checkable, Callable, Awaitable
from abc import abstractmethod
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from app.infra.event_store.kurrentdb_event_store import (
    KurrentDBEventStore, ConcurrencyError, AggregateNotFoundError
)
from app.infra.event_store.event_envelope import EventEnvelope

from app.infra.event_bus.event_registry import EVENT_TYPE_TO_PYDANTIC_MODEL
from app.common.base.base_model import BaseEvent

# Import our new components
from app.infra.reliability.distributed_lock import (
    DistributedLockManager, LockAcquisitionError, LockInfo
)
from app.infra.event_store.sequence_tracker import EventSequenceTracker
from app.infra.saga.saga_manager import SagaManager, BaseSaga

log = logging.getLogger("wellwon.aggregate_repository")

# Type variable for aggregate types
T = TypeVar('T', bound='EventSourcedAggregate')


@runtime_checkable
class EventSourcedAggregate(Protocol):
    """Protocol defining the interface for event-sourced aggregates"""

    @property
    def id(self) -> uuid.UUID:
        """Aggregate ID"""
        ...

    @property
    def version(self) -> int:
        """Current version number"""
        ...

    @version.setter
    def version(self, value: int) -> None:
        """Set version number"""
        ...

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Get list of uncommitted events"""
        ...

    def mark_events_committed(self) -> None:
        """Mark all uncommitted events as committed"""
        ...

    def _apply(self, event: BaseEvent) -> None:
        """Apply an event to update aggregate state"""
        ...

    @abstractmethod
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current state"""
        ...

    @abstractmethod
    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore aggregate from snapshot data"""
        ...


class AggregateRepository:
    """
    Enhanced generic repository for loading and saving event-sourced aggregates.
    Features:
    - Distributed locking for concurrent access control
    - Event sequencing with proper ordering guarantees
    - Saga integration for distributed transactions
    - Optimistic concurrency control
    - Snapshot optimization
    - Automatic retry with exponential backoff
    """

    def __init__(
            self,
            event_store: KurrentDBEventStore,
            aggregate_class: Type[T],
            aggregate_type: str,
            snapshot_frequency: int = 100,  # Create snapshot every N events
            enable_snapshots: bool = True,
            # New parameters for enhanced features
            lock_manager: Optional[DistributedLockManager] = None,
            sequence_tracker: Optional[EventSequenceTracker] = None,
            saga_manager: Optional[SagaManager] = None,
            enable_locking: bool = True,
            enable_sequencing: bool = True,
            lock_timeout_ms: int = 30000,  # 30 seconds default
            max_retry_attempts: int = 3,
            retry_delay_ms: int = 100
    ):
        """
        Initialize enhanced aggregate repository.

        Args:
            event_store: RedPanda event store instance
            aggregate_class: Class of the aggregate (must implement EventSourcedAggregate)
            aggregate_type: Type name for the aggregate (e.g., "User", "BrokerConnection")
            snapshot_frequency: Create a snapshot every N events
            enable_snapshots: Whether to use snapshots
            lock_manager: Distributed lock manager (creates default if None)
            sequence_tracker: Event sequence tracker (creates default if None)
            saga_manager: Saga manager for distributed transactions
            enable_locking: Whether to use distributed locking
            enable_sequencing: Whether to enforce event sequencing
            lock_timeout_ms: Timeout for distributed locks
            max_retry_attempts: Maximum retry attempts for operations
            retry_delay_ms: Initial delay between retries
        """
        self.event_store = event_store
        self.aggregate_class = aggregate_class
        self.aggregate_type = aggregate_type
        self.snapshot_frequency = snapshot_frequency
        self.enable_snapshots = enable_snapshots

        # Enhanced features
        self.lock_manager = lock_manager or (DistributedLockManager() if enable_locking else None)
        self.sequence_tracker = sequence_tracker or (EventSequenceTracker() if enable_sequencing else None)
        self.saga_manager = saga_manager

        self.enable_locking = enable_locking
        self.enable_sequencing = enable_sequencing
        self.lock_timeout_ms = lock_timeout_ms
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_ms = retry_delay_ms

        # Validate that aggregate_class implements required interface
        if not issubclass(aggregate_class, EventSourcedAggregate):
            raise TypeError(
                f"{aggregate_class.__name__} must implement EventSourcedAggregate protocol"
            )

        log.info(
            f"AggregateRepository initialized for {aggregate_type} "
            f"(snapshots: {enable_snapshots}, frequency: {snapshot_frequency}, "
            f"locking: {enable_locking}, sequencing: {enable_sequencing})"
        )

    async def get_by_id(
            self,
            aggregate_id: uuid.UUID,
            acquire_lock: bool = False,
            lock_timeout_ms: Optional[int] = None
    ) -> Optional[T]:
        """
        Load an aggregate from the event store.

        Args:
            aggregate_id: UUID of the aggregate to load
            acquire_lock: Whether to acquire a distributed lock while loading
            lock_timeout_ms: Override default lock timeout

        Returns:
            The aggregate instance or None if not found

        Raises:
            LockAcquisitionError: If lock cannot be acquired
            Exception: If there's an error loading the aggregate
        """
        if acquire_lock and self.enable_locking:
            # Load with distributed lock
            timeout = lock_timeout_ms or self.lock_timeout_ms
            async with self.lock_manager.lock_aggregate(aggregate_id, ttl_ms=timeout):
                return await self._load_aggregate_internal(aggregate_id)
        else:
            # Load without lock
            return await self._load_aggregate_internal(aggregate_id)

    async def _load_aggregate_internal(self, aggregate_id: uuid.UUID) -> Optional[T]:
        """Internal method to load aggregate"""
        try:
            log.debug(f"Loading aggregate {aggregate_id} of type {self.aggregate_type}")

            # Start with a new aggregate instance
            aggregate = self.aggregate_class(aggregate_id)
            start_version = 0
            events_applied = 0

            # Try to load from snapshot if enabled
            if self.enable_snapshots:
                try:
                    snapshot = await self.event_store.get_latest_snapshot(
                        aggregate_id, self.aggregate_type
                    )

                    if snapshot:
                        log.debug(
                            f"Found snapshot for {aggregate_id} at version {snapshot.version}"
                        )
                        aggregate.restore_from_snapshot(snapshot.state)
                        aggregate.version = snapshot.version
                        start_version = snapshot.version
                except Exception as e:
                    log.warning(
                        f"Failed to load snapshot for {aggregate_id}, "
                        f"will replay all events: {e}"
                    )

            # Load and apply events after snapshot (or from beginning)
            events = await self.event_store.get_events(
                aggregate_id,
                self.aggregate_type,
                from_version=start_version + 1
            )

            if not events and start_version == 0:
                # No events found and no snapshot - aggregate doesn't exist
                log.debug(f"No events found for aggregate {aggregate_id}")
                return None

            # Apply events to aggregate
            for envelope in events:
                try:
                    # Get the event class from registry
                    event_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(envelope.event_type)
                    if not event_class:
                        log.error(
                            f"Unknown event type '{envelope.event_type}' "
                            f"for aggregate {aggregate_id}"
                        )
                        continue

                    # Deserialize and apply the event
                    domain_event = event_class(**envelope.event_data)
                    aggregate._apply(domain_event)
                    aggregate.version = envelope.aggregate_version
                    events_applied += 1

                except Exception as e:
                    log.error(
                        f"Failed to apply event {envelope.event_id} "
                        f"to aggregate {aggregate_id}: {e}",
                        exc_info=True
                    )
                    raise

            # Clear uncommitted events (we just loaded from store)
            aggregate.mark_events_committed()

            log.info(
                f"Loaded aggregate {aggregate_id} at version {aggregate.version} "
                f"(snapshot: v{start_version}, events applied: {events_applied})"
            )

            return aggregate

        except Exception as e:
            log.error(
                f"Error loading aggregate {aggregate_id} of type {self.aggregate_type}: {e}",
                exc_info=True
            )
            raise

    @asynccontextmanager
    async def load_for_update(
            self,
            aggregate_id: uuid.UUID,
            timeout_ms: Optional[int] = None,
            saga_id: Optional[uuid.UUID] = None,  # ✅ ADD saga_id parameter
            causation_id: Optional[uuid.UUID] = None,  # ✅ ADD for completeness
            metadata: Optional[Dict[str, Any]] = None  # ✅ ADD for completeness
    ):
        """
        Context manager for load-update-save pattern with automatic locking.

        Usage:
            async with repository.load_for_update(aggregate_id, saga_id=saga_id) as aggregate:
                aggregate.do_something()
                # Automatically saved on exit with saga context
        """
        if not self.enable_locking:
            raise RuntimeError("load_for_update requires locking to be enabled")

        lock_info = None
        aggregate = None
        timeout = timeout_ms or self.lock_timeout_ms

        try:
            # Acquire lock first
            lock_info = await self.lock_manager.acquire_lock(
                aggregate_id,
                ttl_ms=timeout,
                wait=True
            )

            # Load aggregate
            aggregate = await self._load_aggregate_internal(aggregate_id)

            if not aggregate:
                raise AggregateNotFoundError(f"Aggregate {aggregate_id} not found")

            # Track initial version for optimistic concurrency
            initial_version = aggregate.version
            initial_event_count = len(aggregate.get_uncommitted_events())

            yield aggregate

            # Save if there are new events
            if len(aggregate.get_uncommitted_events()) > initial_event_count:
                await self._save_internal(
                    aggregate,
                    expected_version=initial_version,
                    lock_info=lock_info,
                    saga_id=saga_id,
                    causation_id=causation_id,
                    metadata=metadata
                )

        finally:
            # Always release lock
            if lock_info and self.lock_manager:
                try:
                    await self.lock_manager.release_lock(lock_info)
                except Exception as e:
                    log.error(f"Error releasing lock for aggregate {aggregate_id}: {e}")

    async def save(
            self,
            aggregate: T,
            causation_id: Optional[uuid.UUID] = None,
            correlation_id: Optional[uuid.UUID] = None,
            metadata: Optional[Dict[str, Any]] = None,
            expected_version: Optional[int] = None,
            saga_id: Optional[uuid.UUID] = None,
            use_lock: bool = True
    ) -> int:
        """
        Save aggregate events to the event store with enhanced features.

        Args:
            aggregate: The aggregate to save
            causation_id: ID of the command that caused these events
            correlation_id: ID for correlating related events across aggregates
            metadata: Additional metadata to store with events
            expected_version: Expected version for optimistic concurrency control
            saga_id: ID of the saga orchestrating this change
            use_lock: Whether to use distributed locking

        Returns:
            The new version number after saving

        Raises:
            LockAcquisitionError: If can't acquire lock
            ConcurrencyError: If expected version doesn't match
            Exception: If save fails
        """
        # Add saga_id to metadata if provided
        if saga_id and metadata is None:
            metadata = {}
        if saga_id:
            metadata['saga_id'] = str(saga_id)

        if use_lock and self.enable_locking:
            # Save with distributed lock
            return await self._save_with_lock(
                aggregate, causation_id, correlation_id,
                metadata, expected_version, saga_id
            )
        else:
            # Save without lock
            return await self._save_internal(
                aggregate, causation_id, correlation_id,
                saga_id,
                metadata, expected_version
            )

    async def _save_with_lock(
            self,
            aggregate: T,
            causation_id: Optional[uuid.UUID],
            correlation_id: Optional[uuid.UUID],
            metadata: Optional[Dict[str, Any]],
            expected_version: Optional[int],
            saga_id: Optional[uuid.UUID] = None
    ) -> int:
        """Save with distributed locking and retry logic"""
        last_error = None

        for attempt in range(self.max_retry_attempts):
            try:
                # Acquire lock
                async with self.lock_manager.lock_aggregate(
                        aggregate.id,
                        ttl_ms=self.lock_timeout_ms
                ) as lock_info:

                    log.debug(
                        f"Acquired lock for aggregate {aggregate.id} "
                        f"(attempt {attempt + 1}/{self.max_retry_attempts})"
                    )

                    # Save with lock held
                    return await self._save_internal(
                        aggregate, causation_id, correlation_id,
                        saga_id,
                        metadata, expected_version, lock_info
                    )

            except LockAcquisitionError as e:
                last_error = e
                log.warning(
                    f"Failed to acquire lock for aggregate {aggregate.id} "
                    f"(attempt {attempt + 1}/{self.max_retry_attempts}): {e}"
                )

                if attempt < self.max_retry_attempts - 1:
                    # Exponential backoff
                    await asyncio.sleep(self.retry_delay_ms * (2 ** attempt) / 1000)

            except ConcurrencyError as e:
                # Don't retry on version conflicts
                raise

            except Exception as e:
                last_error = e
                log.error(
                    f"Error saving aggregate {aggregate.id} "
                    f"(attempt {attempt + 1}/{self.max_retry_attempts}): {e}"
                )

                if attempt < self.max_retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay_ms * (2 ** attempt) / 1000)

        # All retries failed
        raise last_error or Exception("Failed to save aggregate after all retries")

    async def _save_internal(
            self,
            aggregate: T,
            causation_id: Optional[uuid.UUID] = None,
            correlation_id: Optional[uuid.UUID] = None,
            saga_id: Optional[uuid.UUID] = None,  # ADD THIS
            metadata: Optional[Dict[str, Any]] = None,
            expected_version: Optional[int] = None,
            lock_info: Optional[LockInfo] = None
    ) -> int:
        """Internal save method"""
        events = aggregate.get_uncommitted_events()

        if not events:
            log.debug(f"No uncommitted events for aggregate {aggregate.id}")
            return aggregate.version

        # Calculate expected version if not provided
        if expected_version is None:
            expected_version = aggregate.version - len(events)

        try:
            # Double-check version if we have a lock
            if lock_info:
                current_version = await self.event_store.get_aggregate_version(
                    aggregate.id, self.aggregate_type
                )

                if current_version != expected_version:
                    raise ConcurrencyError(
                        f"Version changed while holding lock. "
                        f"Expected: {expected_version}, Current: {current_version}"
                    )

            log.info(
                f"Saving {len(events)} events for aggregate {aggregate.id} "
                f"(expected version: {expected_version})"
            )

            # Prepare events with sequence numbers if sequencing is enabled
            if self.enable_sequencing:
                events_with_sequence = []
                current_seq = expected_version

                for event in events:
                    current_seq += 1
                    # Add sequence number to event data
                    event_dict = event.model_dump()
                    event_dict['sequence_number'] = current_seq

                    # Recreate event with sequence number
                    event_class = type(event)
                    enhanced_event = event_class(**event_dict)
                    events_with_sequence.append(enhanced_event)

                events = events_with_sequence

            # Append events to event store
            new_version = await self.event_store.append_events(
                aggregate_id=aggregate.id,
                aggregate_type=self.aggregate_type,
                events=events,
                expected_version=expected_version,
                causation_id=causation_id,
                correlation_id=correlation_id,
                saga_id=saga_id,  # ADD THIS
                metadata=metadata
            )

            # Update aggregate version
            aggregate.version = new_version

            # Mark events as committed
            aggregate.mark_events_committed()

            # Check if we should create a snapshot
            if self.enable_snapshots and new_version % self.snapshot_frequency == 0:
                await self._create_snapshot(aggregate, new_version)

            log.info(
                f"Successfully saved aggregate {aggregate.id} "
                f"at version {new_version}" +
                (f" (saga: {saga_id})" if saga_id else "")  # ADD THIS for better logging
            )

            return new_version

        except ConcurrencyError as e:
            log.warning(
                f"Concurrency conflict saving aggregate {aggregate.id}: {e}"
            )
            raise
        except Exception as e:
            log.error(
                f"Error saving aggregate {aggregate.id}: {e}",
                exc_info=True
            )
            raise

    async def _create_snapshot(self, aggregate: T, version: int) -> None:
        """
        Create a snapshot of the aggregate.

        Args:
            aggregate: The aggregate to snapshot
            version: Version number for the snapshot
        """
        try:
            log.debug(f"Creating snapshot for aggregate {aggregate.id} at version {version}")

            # Get snapshot data from aggregate
            snapshot_data = aggregate.create_snapshot()

            # Add metadata
            snapshot_metadata = {
                "created_by": "AggregateRepository",
                "aggregate_class": self.aggregate_class.__name__,
                "snapshot_time": datetime.now(timezone.utc).isoformat()
            }

            # Save snapshot to event store
            await self.event_store.save_snapshot(
                aggregate_id=aggregate.id,
                aggregate_type=self.aggregate_type,
                version=version,
                state=snapshot_data,
                metadata=snapshot_metadata
            )

            log.info(
                f"Created snapshot for aggregate {aggregate.id} at version {version}"
            )

        except Exception as e:
            # Don't fail the save operation if snapshot fails
            log.error(
                f"Failed to create snapshot for aggregate {aggregate.id}: {e}",
                exc_info=True
            )

    async def execute_with_saga(
            self,
            aggregate_id: uuid.UUID,
            saga: BaseSaga,
            operation: Callable[[T], Awaitable[None]],
            initial_context: Optional[Dict[str, Any]] = None
    ) -> uuid.UUID:
        """
        Execute an operation on an aggregate within a saga.

        Args:
            aggregate_id: ID of the aggregate to modify
            saga: The saga instance to execute
            operation: Async function that modifies the aggregate
            initial_context: Initial context for the saga

        Returns:
            The saga ID

        Raises:
            Exception: If operation fails
        """
        if not self.saga_manager:
            raise RuntimeError("Saga manager not configured")

        # Start the saga
        saga_id = await self.saga_manager.start_saga(saga, initial_context)

        try:
            # Load and modify aggregate within saga context
            async with self.load_for_update(aggregate_id) as aggregate:
                # Execute the operation
                await operation(aggregate)

                # Save will happen automatically with saga_id in metadata
                # when the context manager exits

        except Exception as e:
            log.error(f"Operation failed within saga {saga_id}: {e}")
            # Saga manager will handle compensation
            raise

        return saga_id

    # Helper methods for common operations

    async def exists(self, aggregate_id: uuid.UUID) -> bool:
        """
        Check if an aggregate exists in the event store.

        Args:
            aggregate_id: ID of the aggregate to check

        Returns:
            True if the aggregate exists, False otherwise
        """
        try:
            version = await self.event_store.get_aggregate_version(
                aggregate_id, self.aggregate_type
            )
            return version > 0
        except Exception as e:
            log.error(f"Error checking if aggregate {aggregate_id} exists: {e}")
            return False

    async def get_version(self, aggregate_id: uuid.UUID) -> int:
        """
        Get the current version of an aggregate.

        Args:
            aggregate_id: ID of the aggregate

        Returns:
            Current version number (0 if doesn't exist)
        """
        try:
            return await self.event_store.get_aggregate_version(
                aggregate_id, self.aggregate_type
            )
        except Exception as e:
            log.error(f"Error getting version for aggregate {aggregate_id}: {e}")
            return 0

    async def get_events(
            self,
            aggregate_id: uuid.UUID,
            from_version: int = 0,
            to_version: Optional[int] = None
    ) -> List[EventEnvelope]:
        """
        Get raw events for an aggregate.

        Args:
            aggregate_id: ID of the aggregate
            from_version: Start version (inclusive)
            to_version: End version (inclusive), None for all

        Returns:
            List of event envelopes
        """
        return await self.event_store.get_events(
            aggregate_id,
            self.aggregate_type,
            from_version,
            to_version
        )

    async def load_at_version(
            self,
            aggregate_id: uuid.UUID,
            version: int
    ) -> Optional[T]:
        """
        Load an aggregate at a specific version.

        Args:
            aggregate_id: ID of the aggregate
            version: Version to load up to

        Returns:
            Aggregate at the specified version or None
        """
        try:
            log.debug(
                f"Loading aggregate {aggregate_id} at version {version}"
            )

            # Create new aggregate
            aggregate = self.aggregate_class(aggregate_id)

            # Load events up to specified version
            events = await self.event_store.get_events(
                aggregate_id,
                self.aggregate_type,
                from_version=1,
                to_version=version
            )

            if not events:
                return None

            # Apply events
            for envelope in events:
                event_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(envelope.event_type)
                if event_class:
                    domain_event = event_class(**envelope.event_data)
                    aggregate._apply(domain_event)
                    aggregate.version = envelope.aggregate_version

            aggregate.mark_events_committed()

            return aggregate

        except Exception as e:
            log.error(
                f"Error loading aggregate {aggregate_id} at version {version}: {e}",
                exc_info=True
            )
            raise

    async def get_aggregate_history(
            self,
            aggregate_id: uuid.UUID,
            include_snapshots: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete history of an aggregate.

        Args:
            aggregate_id: ID of the aggregate
            include_snapshots: Whether to include snapshot information

        Returns:
            Dictionary with aggregate history
        """
        try:
            # Get all events
            events = await self.get_events(aggregate_id)

            # Get current version
            current_version = await self.get_version(aggregate_id)

            history = {
                "aggregate_id": str(aggregate_id),
                "aggregate_type": self.aggregate_type,
                "current_version": current_version,
                "total_events": len(events),
                "events": [
                    {
                        "version": e.aggregate_version,
                        "event_type": e.event_type,
                        "event_id": str(e.event_id),
                        "stored_at": e.stored_at.isoformat(),
                        "causation_id": str(e.causation_id) if e.causation_id else None,
                        "correlation_id": str(e.correlation_id) if e.correlation_id else None
                    }
                    for e in events
                ]
            }

            if include_snapshots:
                snapshot = await self.event_store.get_latest_snapshot(
                    aggregate_id, self.aggregate_type
                )
                if snapshot:
                    history["latest_snapshot"] = {
                        "version": snapshot.version,
                        "created_at": snapshot.created_at.isoformat(),
                        "metadata": snapshot.metadata
                    }

            return history

        except Exception as e:
            log.error(
                f"Error getting history for aggregate {aggregate_id}: {e}",
                exc_info=True
            )
            raise

    def get_lock_manager(self) -> Optional[DistributedLockManager]:
        """Get the lock manager instance"""
        return self.lock_manager

    def get_sequence_tracker(self) -> Optional[EventSequenceTracker]:
        """Get the sequence tracker instance"""
        return self.sequence_tracker

    def get_saga_manager(self) -> Optional[SagaManager]:
        """Get the saga manager instance"""
        return self.saga_manager


# Convenience function to create typed repositories
def create_repository(
        event_store: KurrentDBEventStore,
        aggregate_class: Type[T],
        aggregate_type: str,
        enable_enhanced_features: bool = True,
        saga_manager: Optional[SagaManager] = None,
        **kwargs
) -> AggregateRepository[T]:
    """
    Create a typed aggregate repository with enhanced features.

    Args:
        event_store: The event store instance
        aggregate_class: The aggregate class
        aggregate_type: Type name for the aggregate
        enable_enhanced_features: Enable locking and sequencing
        saga_manager: Optional saga manager for distributed transactions
        **kwargs: Additional configuration options

    Example:
        user_repo = create_repository(
            event_store,
            UserAggregate,
            "User",
            enable_enhanced_features=True,
            saga_manager=saga_manager
        )
    """
    return AggregateRepository(
        event_store=event_store,
        aggregate_class=aggregate_class,
        aggregate_type=aggregate_type,
        enable_locking=enable_enhanced_features,
        enable_sequencing=enable_enhanced_features,
        saga_manager=saga_manager,
        **kwargs
    )

# =============================================================================
# EOF
# =============================================================================