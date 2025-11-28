# =============================================================================
# File: app/common/base/base_handler.py
# Description: Base command handler for 
#              Provides consistent event publishing to both event store and transport.
#              All domain command handlers should inherit from this base class.
#              FIXED: Removed duplicate transport publishing when using Event Store with Outbox
#              UPDATED: Added saga_id support for distributed transaction tracking
#              FIXED: Proper version handling for new aggregates
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional, Any, Protocol, runtime_checkable, List, Dict
from abc import ABC, abstractmethod
import uuid

from app.infra.event_bus.event_bus import EventBus
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore
from app.common.base.base_model import BaseEvent

log = logging.getLogger("wellwon.base_handler")


@runtime_checkable
class AggregateProtocol(Protocol):
    """Protocol defining the interface that aggregates must implement."""
    id: uuid.UUID
    version: int

    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Get list of uncommitted events."""
        ...

    def mark_events_committed(self) -> None:
        """Mark all uncommitted events as committed."""
        ...


class BaseCommandHandler(ABC):
    """
    Base class for all command handlers in WellWon.

    Provides:
    - Consistent event publishing to both event store and transport
    - Proper event serialization for both Redis and RedPanda
    - Version tracking for optimistic concurrency
    - Error handling and logging
    - Exactly-once delivery via Outbox pattern when Event Store is enabled
    - Saga tracking for distributed transactions
    - Proper version handling for new aggregates
    """

    def __init__(
            self,
            event_bus: EventBus,
            transport_topic: str,
            event_store: Optional[KurrentDBEventStore] = None
    ):
        """
        Initialize the base command handler.

        Args:
            event_bus: EventBus instance for publishing to transport streams
            transport_topic: Topic name for transport (e.g., "transport.entity-events")
            event_store: Optional event store for permanent event storage
        """
        self.event_bus = event_bus
        self.transport_topic = transport_topic
        self.event_store = event_store

    async def publish_and_commit_events(
            self,
            aggregate: AggregateProtocol,
            aggregate_type: str,
            expected_version: Optional[int] = None,
            causation_id: Optional[uuid.UUID] = None,
            correlation_id: Optional[uuid.UUID] = None,
            saga_id: Optional[uuid.UUID] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Publish events to both event store (if configured) and transport, then mark as committed.

        When Event Store is configured with Outbox pattern:
        - Events are stored in Event Store
        - Events are saved to Outbox table in same transaction
        - OutboxPublisher handles publishing to transport (exactly-once)

        When Event Store is not configured:
        - Events are published directly to transport (at-least-once)

        Args:
            aggregate: The aggregate containing uncommitted events
            aggregate_type: Type of aggregate (e.g., "BrokerConnection", "User", "Account")
            expected_version: Expected version for optimistic concurrency:
                             - None = new aggregate (will be passed as-is to event store)
                             - 0 or greater = existing aggregate at specific version
            causation_id: ID of the command that caused these events
            correlation_id: ID for correlating related events across aggregates
            saga_id: ID of the saga orchestrating these events (for distributed transactions)
            metadata: Additional metadata to store with events

        Returns:
            The new version number after publishing

        Raises:
            Exception: If event store publishing fails (transport failures are logged but don't fail)
        """
        # Get uncommitted events from aggregate
        events = aggregate.get_uncommitted_events()

        if not events:
            log.debug(f"No uncommitted events for {aggregate_type}:{aggregate.id}")
            return aggregate.version

        # Log the expected version for debugging
        version_str = "None (new aggregate)" if expected_version is None else str(expected_version)
        log.info(
            f"Publishing {len(events)} events for {aggregate_type}:{aggregate.id} "
            f"(expected version: {version_str})" +
            (f" [saga: {saga_id}]" if saga_id else "")
        )

        # Initialize new_version - will be updated by event store if used
        new_version = aggregate.version

        # Check if Event Store is configured and has outbox enabled
        event_store_has_outbox = (
                self.event_store and
                hasattr(self.event_store, '_enable_outbox') and
                self.event_store._enable_outbox and
                hasattr(self.event_store, '_outbox_service') and
                self.event_store._outbox_service
        )

        # 1. Store in event store (permanent storage) if configured
        if self.event_store:
            try:
                # Pass expected_version as-is to event store
                # The event store will handle None as -1 for new aggregates
                new_version = await self.event_store.append_events(
                    aggregate_id=aggregate.id,
                    aggregate_type=aggregate_type,
                    events=events,
                    expected_version=expected_version,
                    causation_id=causation_id,
                    correlation_id=correlation_id,
                    saga_id=saga_id,
                    metadata=metadata,
                    publish_to_transport=True  # Tell event store to save to outbox
                )

                # Update aggregate version to match event store
                aggregate.version = new_version

                if event_store_has_outbox:
                    log.info(
                        f"Stored {len(events)} events in event store with outbox for "
                        f"{aggregate_type}:{aggregate.id} (new version: {new_version}). "
                        f"OutboxPublisher will handle transport delivery."
                    )
                else:
                    log.info(
                        f"Stored {len(events)} events in event store for "
                        f"{aggregate_type}:{aggregate.id} (new version: {new_version})"
                    )
            except Exception as e:
                log.error(
                    f"Failed to store events in event store for "
                    f"{aggregate_type}:{aggregate.id}: {e}",
                    exc_info=True
                )
                # Re-raise to fail the command - event store is source of truth
                raise

        # 2. Only publish directly to transport if:
        #    - No event store configured OR
        #    - Event store doesn't have outbox enabled
        if not self.event_store or not event_store_has_outbox:
            log.debug(
                f"Publishing events directly to transport "
                f"(event_store={bool(self.event_store)}, outbox={event_store_has_outbox})"
            )

            # This is best-effort - failures are logged but don't fail the command
            transport_failures = 0
            for event in events:
                try:
                    # Use mode='json' to ensure proper serialization of UUIDs, datetimes, etc.
                    event_dict = event.model_dump(mode='json', by_alias=True)

                    # Add saga_id to event metadata if present
                    if saga_id:
                        event_dict['saga_id'] = str(saga_id)

                    await self.event_bus.publish(self.transport_topic, event_dict)

                    log.debug(
                        f"Published {event.event_type} (ID: {event.event_id}) "
                        f"to transport topic {self.transport_topic}" +
                        (f" [saga: {saga_id}]" if saga_id else "")
                    )
                except Exception as e:
                    transport_failures += 1
                    log.error(
                        f"Failed to publish event {event.event_id} to transport "
                        f"topic {self.transport_topic}: {e}",
                        exc_info=True
                    )
                    # Continue with other events even if one fails

            if transport_failures > 0:
                log.warning(
                    f"Failed to publish {transport_failures}/{len(events)} events "
                    f"to transport for {aggregate_type}:{aggregate.id}. "
                    f"Projections may be delayed or need to be rebuilt."
                )

        # 3. Mark events as committed on the aggregate
        aggregate.mark_events_committed()

        log.info(
            f"Successfully processed {len(events)} events for "
            f"{aggregate_type}:{aggregate.id} (final version: {new_version})" +
            (f" [saga: {saga_id}]" if saga_id else "")
        )

        return new_version

    async def publish_events(
            self,
            aggregate: AggregateProtocol,
            aggregate_id: uuid.UUID,
            command: Any,
            aggregate_type: Optional[str] = None,
    ) -> int:
        """
        Convenience method for publishing events with simpler signature.

        This wraps publish_and_commit_events for handlers that use the
        simplified (aggregate, aggregate_id, command) pattern.

        Args:
            aggregate: The aggregate containing uncommitted events
            aggregate_id: ID of the aggregate (for logging/tracking)
            command: The command that caused these events (for correlation)
            aggregate_type: Type of aggregate. If not provided, derived from aggregate class name.

        Returns:
            The new version number after publishing
        """
        # Derive aggregate type from aggregate class name if not provided
        if aggregate_type is None:
            class_name = aggregate.__class__.__name__
            # Remove 'Aggregate' suffix if present (e.g., ChatAggregate -> Chat)
            aggregate_type = class_name.replace('Aggregate', '') if class_name.endswith('Aggregate') else class_name

        # Extract correlation/causation from command if available
        causation_id = getattr(command, 'command_id', None) or getattr(command, 'causation_id', None)
        correlation_id = getattr(command, 'correlation_id', None)
        saga_id = getattr(command, 'saga_id', None)

        # Determine expected version - None for new aggregates, current version for existing
        expected_version = None if aggregate.version == 0 else aggregate.version

        return await self.publish_and_commit_events(
            aggregate=aggregate,
            aggregate_type=aggregate_type,
            expected_version=expected_version,
            causation_id=causation_id,
            correlation_id=correlation_id,
            saga_id=saga_id,
        )

    @abstractmethod
    async def handle(self, command: Any) -> Any:
        """
        Handle the command. Must be implemented by subclasses.

        Args:
            command: The command to handle

        Returns:
            Command-specific return value (often aggregate ID)
        """
        pass


# =============================================================================
# Utility functions for handlers that don't inherit from base
# =============================================================================

async def publish_events_standalone(
        events: List[BaseEvent],
        aggregate_id: uuid.UUID,
        aggregate_type: str,
        transport_topic: str,
        event_bus: EventBus,
        event_store: Optional[KurrentDBEventStore] = None,
        expected_version: Optional[int] = None,
        causation_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        saga_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Standalone function for publishing events when not using BaseCommandHandler.

    Use this for one-off cases or during migration.

    Args:
        events: List of events to publish
        aggregate_id: ID of the aggregate
        aggregate_type: Type of aggregate
        transport_topic: Topic for transport publishing
        event_bus: EventBus instance
        event_store: Optional event store instance
        expected_version: Expected version for optimistic concurrency:
                         - None = new aggregate
                         - 0 or greater = existing aggregate
        causation_id: ID of the command that caused these events
        correlation_id: ID for correlating related events
        saga_id: ID of the saga orchestrating these events
        metadata: Additional metadata to store with events

    Returns:
        New version number after publishing
    """
    if not events:
        return expected_version if expected_version is not None else 0

    new_version = expected_version if expected_version is not None else 0

    # Check if Event Store has outbox enabled
    event_store_has_outbox = (
            event_store and
            hasattr(event_store, '_enable_outbox') and
            event_store._enable_outbox and
            hasattr(event_store, '_outbox_service') and
            event_store._outbox_service
    )

    # Store in event store if available
    if event_store:
        new_version = await event_store.append_events(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            events=events,
            expected_version=expected_version,
            causation_id=causation_id,
            correlation_id=correlation_id,
            saga_id=saga_id,
            metadata=metadata,
            publish_to_transport=True  # Save to outbox if enabled
        )

    # Only publish to transport if no event store or no outbox
    if not event_store or not event_store_has_outbox:
        for event in events:
            try:
                event_dict = event.model_dump(mode='json', by_alias=True)

                # Add saga_id to event metadata if present
                if saga_id:
                    event_dict['saga_id'] = str(saga_id)

                await event_bus.publish(transport_topic, event_dict)
            except Exception as e:
                log.error(f"Failed to publish event to transport: {e}", exc_info=True)

    return new_version

# =============================================================================
# EOF
# =============================================================================