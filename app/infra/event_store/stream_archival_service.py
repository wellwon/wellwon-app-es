# app/infra/event_store/stream_archival_service.py
# =============================================================================
# Stream Archival Service
#
# Server-side subscription that archives EventStore streams when entities are deleted.
# Follows CQRS/ES best practice: "Implement archival through event subscriptions"
#
# Architecture:
#   Command Handler → emits deletion event → EventStore
#                                               ↓
#                         Archival Subscription (this service)
#                                               ↓
#                              archive_stream() - soft deletes stream
# =============================================================================

import logging
import uuid
from typing import Optional, Dict, Any

log = logging.getLogger("wellwon.services.stream_archival")


class StreamArchivalService:
    """
    Server-side service that subscribes to deletion events and archives
    corresponding EventStore streams.

    This keeps PostgreSQL (read model) and EventStore (write model) in sync.
    When an entity is deleted from the read model, the stream is soft-deleted
    to prevent stale events from being replayed.

    Best Practice: Archival is decoupled from command handlers via subscriptions.
    """

    def __init__(self, event_bus, event_store):
        """
        Initialize stream archival service.

        Args:
            event_bus: EventBus to subscribe for deletion events
            event_store: KurrentDB EventStore for stream archival
        """
        self._event_bus = event_bus
        self._event_store = event_store
        self._subscriptions = []

        # Map deletion event types to aggregate types
        # WellWon domains only
        self._deletion_event_mapping = {
            "UserAccountDeleted": "user_account",
            # Future domains:
            # "CompanyDeleted": "company",
            # "ShipmentDeleted": "shipment",
        }

        log.info("StreamArchivalService initialized")

    async def start(self) -> None:
        """
        Start subscribing to deletion events.
        Call this during server startup after EventBus and EventStore are ready.
        """
        if not self._event_bus or not self._event_store:
            log.warning("EventBus or EventStore not available, stream archival disabled")
            return

        # Subscribe to transport topics for domain events
        # WellWon domains only
        topics = [
            "transport.user-account-events",
            # Future domains:
            # "transport.company-events",
            # "transport.shipment-events",
        ]

        for topic in topics:
            try:
                await self._event_bus.subscribe(
                    channel=topic,
                    handler=self._handle_event,
                    group="stream-archival-service",
                    consumer="archival-subscriber"
                )
                self._subscriptions.append(topic)
                log.info(f"Subscribed to {topic} for stream archival")
            except Exception as e:
                log.error(f"Failed to subscribe to {topic}: {e}")

        log.info(f"StreamArchivalService started with {len(self._subscriptions)} subscriptions")

    async def stop(self) -> None:
        """Stop the service and unsubscribe from events."""
        log.info("StreamArchivalService stopping")
        # Unsubscribe logic would go here if needed
        self._subscriptions.clear()

    async def _handle_event(self, event_dict: Dict[str, Any]) -> None:
        """
        Handle incoming events and archive streams for deletion events.

        Args:
            event_dict: The event data
        """
        event_type = event_dict.get("event_type", "")

        # Check if this is a deletion event
        aggregate_type = self._deletion_event_mapping.get(event_type)
        if not aggregate_type:
            return  # Not a deletion event, ignore

        # Get aggregate_id from event
        aggregate_id_str = (
            event_dict.get("aggregate_id") or
            event_dict.get("user_id")
            # Future domains:
            # event_dict.get("company_id") or
            # event_dict.get("shipment_id")
        )

        if not aggregate_id_str:
            log.warning(f"Cannot archive stream for {event_type}: missing aggregate_id")
            return

        try:
            aggregate_id = uuid.UUID(str(aggregate_id_str))

            # Archive the stream
            archived = await self._event_store.archive_stream(
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type,
                reason=f"Entity deleted via {event_type}"
            )

            if archived:
                log.info(
                    f"Archived EventStore stream {aggregate_type}-{aggregate_id} "
                    f"after {event_type}"
                )

        except Exception as e:
            # Log but don't fail - archival is best-effort
            log.warning(f"Failed to archive stream for {event_type}: {e}")


# =============================================================================
# Factory function
# =============================================================================

_archival_service_instance: Optional[StreamArchivalService] = None


async def create_and_start_archival_service(event_bus, event_store) -> StreamArchivalService:
    """
    Create and start the stream archival service.

    Args:
        event_bus: EventBus instance
        event_store: EventStore instance

    Returns:
        Started StreamArchivalService instance
    """
    global _archival_service_instance

    service = StreamArchivalService(event_bus, event_store)
    await service.start()

    _archival_service_instance = service
    return service


def get_archival_service() -> Optional[StreamArchivalService]:
    """Get the global archival service instance."""
    return _archival_service_instance
