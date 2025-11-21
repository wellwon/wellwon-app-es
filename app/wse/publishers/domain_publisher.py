# =============================================================================
# File: app/wse/publishers/domain_publisher.py
# Description: WSE Domain Publisher - Forwards domain events to WebSocket clients
# =============================================================================

"""
WSE Domain Publisher

Bridges EventBus (Redpanda domain events) -> PubSubBus (WebSocket clients)

ARCHITECTURE (CQRS/ES Best Practice):
+-------------------------------------------------------------+
| CommandHandler -> Event -> EventStore -> EventBus (Redpanda) |
+---------------------------+---------------------------------+
                            |
             +--------------+--------------+
             |                             |
      Worker Projector              WSE Domain Publisher
      (Updates PostgreSQL)          (Subscribes to EventBus)
             |                             |
       Read Models                  PubSubBus (Redis Pub/Sub)
                                           |
                                    WebSocket Clients

RESPONSIBILITIES:
- Subscribe to domain events from EventBus (Redpanda)
- Transform events to frontend-friendly format
- Publish to PubSubBus for WSE clients (broadcasts to all server instances)
- Route events to correct user topics

DOMAINS SUPPORTED:
- User (user_update events)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.infra.event_bus.event_bus import EventBus
from app.wse.core.pubsub_bus import PubSubBus
from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

log = logging.getLogger("wellwon.wse.domain_publisher")


class WSEDomainPublisher:
    """
    WSE Domain Publisher - Forwards domain events to WebSocket clients

    Subscribes to domain events from EventBus and publishes them to PubSubBus
    for real-time WebSocket updates to frontend clients.
    """

    def __init__(
        self,
        event_bus: EventBus,
        pubsub_bus: PubSubBus,
        enable_user_events: bool = True,
    ):
        """
        Initialize WSE Domain Publisher

        Args:
            event_bus: Backend event bus (Redpanda)
            pubsub_bus: Frontend event bus (Redis Pub/Sub for multi-instance WebSocket coordination)
            enable_user_events: Enable user event forwarding
        """
        self._event_bus = event_bus
        self._pubsub_bus = pubsub_bus

        # Feature flags
        self._enable_user_events = enable_user_events

        # Subscription management
        self._subscriptions: Dict[str, str] = {}  # topic -> subscription_id
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Event type mappings
        self._event_type_map = INTERNAL_TO_WS_EVENT_TYPE_MAP

        # Metrics
        self._events_forwarded = 0
        self._events_filtered = 0
        self._forwarding_errors = 0

        log.info(
            "WSE Domain Publisher initialized - "
            f"Users: {enable_user_events}"
        )

    async def start(self) -> None:
        """Start the WSE Domain Publisher - subscribe to domain events"""
        if self._running:
            log.warning("WSE Domain Publisher already running")
            return

        log.info("Starting WSE Domain Publisher...")
        self._running = True

        try:
            log.info("Starting WSE Domain Publisher subscriptions...")
            await self._subscribe_all()
            log.info(
                f"WSE Domain Publisher ready - "
                f"{len(self._subscriptions)} subscriptions confirmed"
            )

        except Exception as e:
            log.error(f"Failed to start WSE Domain Publisher: {e}", exc_info=True)
            self._running = False
            raise

    async def _subscribe_all(self) -> None:
        """Subscribe to all configured domain event topics"""
        try:
            if self._enable_user_events:
                await self._subscribe_to_user_events()

            log.info(
                f"WSE Domain Publisher subscriptions complete - "
                f"{len(self._subscriptions)} topic subscriptions active"
            )

        except Exception as e:
            log.error(f"Failed to subscribe to event topics: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop the WSE Domain Publisher - unsubscribe from all topics"""
        if not self._running:
            return

        log.info("Stopping WSE Domain Publisher...")

        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                log.warning("WSE task cancellation timed out after 5s")

        self._tasks.clear()
        self._subscriptions.clear()

        log.info(
            f"WSE Domain Publisher stopped - "
            f"Forwarded: {self._events_forwarded}, "
            f"Filtered: {self._events_filtered}, "
            f"Errors: {self._forwarding_errors}"
        )

    async def shutdown(self) -> None:
        """Shutdown the WSE Domain Publisher (alias for stop)"""
        await self.stop()

    # =========================================================================
    # TOPIC SUBSCRIPTIONS
    # =========================================================================

    async def _subscribe_to_user_events(self) -> None:
        """Subscribe to user account domain events"""
        if not self._running:
            log.debug("Skipping user event subscription - service not running")
            return

        topic = "transport.user-account-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_user_event,
                group="wse-domain-publisher",
                consumer=f"wse-publisher-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def _handle_user_event(self, event: Dict[str, Any]) -> None:
        """Handle user account domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id") or event.get("aggregate_id")

            if not event_type or not user_id:
                log.warning(f"User event missing event_type or user_id: {event}")
                return

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for event type: {event_type}")
                return

            # Transform to WebSocket format
            wse_event = {
                "event_type": ws_event_type,
                "user_id": str(user_id),
                "data": self._transform_user_event(event),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific events topic
            topic = f"user:{user_id}:events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} -> {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling user event: {e}", exc_info=True)

    # =========================================================================
    # EVENT TRANSFORMERS
    # =========================================================================

    def _transform_user_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform user event to WSE format"""
        return {
            "user_id": event.get("aggregate_id") or event.get("user_id"),
            "email": event.get("email"),
            "first_name": event.get("first_name"),
            "last_name": event.get("last_name"),
            "company_name": event.get("company_name"),
            "role": event.get("role"),
            "phone": event.get("phone"),
            "avatar_url": event.get("avatar_url"),
            "bio": event.get("bio"),
            "user_type": event.get("user_type"),
            "is_developer": event.get("is_developer"),
            "timezone": event.get("timezone"),
            "language": event.get("language"),
            "is_active": event.get("is_active", True),
            "email_verified": event.get("email_verified", False),
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
            "metadata": event.get("metadata", {}),
        }

    # =========================================================================
    # METRICS & STATUS
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return {
            "running": self._running,
            "subscriptions": len(self._subscriptions),
            "events_forwarded": self._events_forwarded,
            "events_filtered": self._events_filtered,
            "forwarding_errors": self._forwarding_errors,
            "enabled_domains": {
                "users": self._enable_user_events,
            }
        }


# =============================================================================
# EOF
# =============================================================================
