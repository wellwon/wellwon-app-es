# app/wse/publishers/wse_domain_publisher.py
# =============================================================================
# File: app/wse/publishers/wse_domain_publisher.py
# Description: WSE Domain Publisher - Forwards domain events to WebSocket clients
# =============================================================================

"""
WSE Domain Publisher

Bridges EventBus (Redpanda domain events) → PubSubBus (WebSocket clients)

ARCHITECTURE (CQRS/ES Best Practice):
┌─────────────────────────────────────────────────────────────┐
│ CommandHandler → Event → EventStore → EventBus (Redpanda)  │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
         ┌────────────────┴──────────────────┐
         ↓                                   ↓
  Worker Projector                   WSE Domain Publisher
  (Updates PostgreSQL)               (Subscribes to EventBus)
         ↓                                   ↓
   Read Models                        PubSubBus (Redis Pub/Sub)
                                             ↓
                                      WebSocket Clients

RESPONSIBILITIES:
- Subscribe to domain events from EventBus (Redpanda)
- Transform events to frontend-friendly format
- Publish to PubSubBus for WSE clients (broadcasts to all server instances)
- Route events to correct user topics

DOMAINS SUPPORTED:
- BrokerConnection (broker_connection_update events)
- BrokerAccount (account_update events)
- Order (order_update events)
- Position (position_update events)
- User (user_update events)
- Automation (automation_update events)

NOTE: Infrastructure events (health, streaming) are handled by WSEMonitoringPublisher
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Any, Optional, Set, List, Callable, Awaitable
from uuid import UUID
from datetime import datetime, timezone

from app.infra.event_bus.event_bus import EventBus
from app.wse.core.pubsub_bus import PubSubBus
from app.wse.core.types import EventPriority
from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

log = logging.getLogger("tradecore.wse.domain_publisher")


class WSEDomainPublisher:
    """
    WSE Domain Publisher - Forwards domain events to WebSocket clients

    Subscribes to domain events from EventBus and publishes them to PubSubBus
    for real-time WebSocket updates to frontend clients.

    ARCHITECTURE COMPLIANCE:
    - ✅ Does NOT violate CQRS - projectors only update read models
    - ✅ Separate service for event forwarding (best practice)
    - ✅ Clean separation between backend EventBus and frontend PubSubBus
    """

    def __init__(
        self,
        event_bus: EventBus,
        pubsub_bus: PubSubBus,
        enable_broker_connection_events: bool = True,
        enable_account_events: bool = True,
        enable_order_events: bool = True,
        enable_position_events: bool = True,
        enable_user_events: bool = True,
        enable_automation_events: bool = True,
    ):
        """
        Initialize WSE Domain Publisher

        Args:
            event_bus: Backend event bus (Redpanda)
            pubsub_bus: Frontend event bus (Redis Pub/Sub for multi-instance WebSocket coordination)
            enable_broker_connection_events: Enable broker connection event forwarding
            enable_account_events: Enable broker account event forwarding
            enable_order_events: Enable order event forwarding
            enable_position_events: Enable position event forwarding
            enable_user_events: Enable user event forwarding
            enable_automation_events: Enable automation event forwarding
        """
        self._event_bus = event_bus
        self._pubsub_bus = pubsub_bus

        # Feature flags
        self._enable_broker_connection_events = enable_broker_connection_events
        self._enable_account_events = enable_account_events
        self._enable_order_events = enable_order_events
        self._enable_position_events = enable_position_events
        self._enable_user_events = enable_user_events
        self._enable_automation_events = enable_automation_events

        # Subscription management
        self._subscriptions: Dict[str, str] = {}  # topic -> subscription_id
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Event type mappings (from reactive_core.py)
        self._event_type_map = INTERNAL_TO_WS_EVENT_TYPE_MAP

        # Metrics
        self._events_forwarded = 0
        self._events_filtered = 0
        self._forwarding_errors = 0

        log.info(
            "WSE Domain Publisher initialized - "
            f"Accounts: {enable_account_events}, "
            f"Orders: {enable_order_events}, "
            f"Positions: {enable_position_events}, "
            f"Users: {enable_user_events}, "
            f"Automation: {enable_automation_events}"
        )

    async def start(self) -> None:
        """Start the WSE Domain Publisher - subscribe to domain events"""
        if self._running:
            log.warning("WSE Domain Publisher already running")
            return

        log.info("Starting WSE Domain Publisher...")
        self._running = True

        try:
            # CRITICAL FIX (Nov 14, 2025): Wait for _subscribe_all() to complete BEFORE returning
            # Previous bug: create_task() + sleep(3s) = race condition
            # - Logs showed: "ready" at 21:14:59, but consumers connected at 21:15:23 (24s later!)
            # - Events published between 21:14:59-21:15:23 were LOST
            # Solution: Directly await _subscribe_all() to ensure ALL consumers connected
            log.info("Starting WSE Domain Publisher subscriptions...")
            await self._subscribe_all()
            log.info(
                f"✓ WSE Domain Publisher ready - "
                f"{len(self._subscriptions)} subscriptions confirmed"
            )

        except Exception as e:
            log.error(f"Failed to start WSE Domain Publisher: {e}", exc_info=True)
            self._running = False
            raise

    async def _subscribe_all(self) -> None:
        """Subscribe to all configured domain event topics (runs in background)"""
        try:
            # Subscribe to domain event topics
            if self._enable_broker_connection_events:
                await self._subscribe_to_broker_connection_events()

            if self._enable_account_events:
                await self._subscribe_to_account_events()

            if self._enable_order_events:
                await self._subscribe_to_order_events()

            if self._enable_position_events:
                await self._subscribe_to_position_events()

            if self._enable_user_events:
                await self._subscribe_to_user_events()

            if self._enable_automation_events:
                await self._subscribe_to_automation_events()

            log.info(
                f"WSE Domain Publisher subscriptions complete - "
                f"{len(self._subscriptions)} topic subscriptions active"
            )

        except Exception as e:
            log.error(f"Failed to subscribe to event topics: {e}", exc_info=True)
            # Don't stop the service - it can retry or run without some subscriptions

    async def stop(self) -> None:
        """Stop the WSE Domain Publisher - unsubscribe from all topics"""
        if not self._running:
            return

        log.info("Stopping WSE Domain Publisher...")

        # CRITICAL FIX: Set _running = False FIRST to prevent re-subscription during shutdown
        # This was causing new consumers to start DURING shutdown, blocking Ctrl-C
        self._running = False

        # Cancel all tasks FIRST before unsubscribing (with timeout)
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

        # FIX (Nov 11, 2025): Stream subscriptions don't need explicit unsubscribe
        # subscribe_stream() creates background tasks (already cancelled above)
        # Unlike pub/sub subscriptions, there's no subscription_id to unsubscribe
        # The tasks are cancelled above, so consumers will stop automatically
        self._subscriptions.clear()
        log.debug("Cleared stream subscription tracking (tasks already cancelled)")

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

    async def _subscribe_to_broker_connection_events(self) -> None:
        """Subscribe to broker connection domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping broker connection event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.broker-connection-events"

        try:
            log.info(f"[WSEDomainPublisher] Subscribing to {topic} with group=wse-domain-publisher, consumer=wse-publisher-{os.getpid()}")
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_broker_connection_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"[WSEDomainPublisher] Successfully subscribed to {topic} for WSE forwarding (subscriptions count: {len(self._subscriptions)})")
        except Exception as e:
            log.error(f"[WSEDomainPublisher] Failed to subscribe to {topic}: {e}", exc_info=True)

    async def _subscribe_to_account_events(self) -> None:
        """Subscribe to broker account domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping account event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.broker-account-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_account_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_order_events(self) -> None:
        """Subscribe to order domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping order event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.order-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_order_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_position_events(self) -> None:
        """Subscribe to position domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping position event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.position-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_position_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_user_events(self) -> None:
        """Subscribe to user account domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping user event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.user-account-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_user_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_automation_events(self) -> None:
        """Subscribe to automation domain events"""
        # CRITICAL: Don't subscribe if service is shutting down
        if not self._running:
            log.debug("Skipping automation event subscription - service not running")
            return

        # FIXED: Use transport topic where events are actually published (not domain topic)
        topic = "transport.automation-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_automation_event,
                group="wse-domain-publisher",  # Persistent consumer group
                consumer=f"wse-publisher-{os.getpid()}",  # Unique consumer ID per process
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def _handle_broker_connection_event(self, event: Dict[str, Any]) -> None:
        """Handle broker connection domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")

            log.info(f"[WSEDomainPublisher] Received broker connection event: {event_type}, user: {user_id}, broker_connection_id: {event.get('broker_connection_id')}")

            if not event_type or not user_id:
                log.warning(f"[WSEDomainPublisher] Broker connection event missing event_type or user_id: {event}")
                return

            # CQRS COMPLIANCE (Nov 11, 2025): Removed filter - projectors no longer publish directly
            # WSEDomainPublisher now handles ALL broker connection events from EventBus
            # Previous filter (Nov 8) was workaround for CQRS violation - now fixed

            # ADDITIONAL FIX: Filter out events with connected=False to prevent frontend re-adding disconnected connections
            # EXCEPTION: Allow BrokerDisconnected through - it's an incremental update, not a snapshot
            if event.get("connected") is False and event_type != "BrokerDisconnected":
                self._events_filtered += 1
                log.debug(f"Filtered {event_type} - connection marked as disconnected (connected=False)")
                return

            # NOTE (Nov 11, 2025): Saga completion event handling
            # The BrokerConnectionEstablishedSagaCompleted event is already forwarded to frontend
            # as 'broker_connection_update'. With Fix #1 (including CONNECTING brokers in snapshots),
            # accounts will appear immediately when frontend requests snapshot.
            #
            # Future enhancement: Could add proactive snapshot broadcast here, but current
            # fix (including CONNECTING brokers) is sufficient for instant account loading.

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for event type: {event_type}")
                return

            # DEBUG: Log event structure before validation
            log.info(
                f"[WSEDomainPublisher] DEBUG: Incoming event structure - "
                f"Type: {event_type}, Keys: {list(event.keys())}, "
                f"broker_id value: {event.get('broker_id')}, "
                f"aggregate_id value: {event.get('aggregate_id')}, "
                f"broker_connection_id value: {event.get('broker_connection_id')}"
            )

            # CRITICAL FIX (2025-11-15): Validate required fields before publishing
            # This prevents malformed events from reaching the frontend
            broker_id = event.get("broker_id")
            if not broker_id or broker_id == "unknown":
                self._forwarding_errors += 1
                log.error(
                    f"[WSEDomainPublisher] REJECTING MALFORMED EVENT: Missing or invalid broker_id. "
                    f"Event type: {event_type}, Connection ID: {event.get('aggregate_id')}, "
                    f"User: {user_id}. This indicates an upstream bug in aggregate or command handler."
                )
                return

            # Transform to WebSocket format
            transformed_data = self._transform_broker_connection_event(event)

            # CRITICAL FIX (Nov 15, 2025): Promote broker_id and environment to top level
            # Frontend expects these fields at top level, not inside "data"
            # CRITICAL FIX (Nov 16, 2025): Preserve original event_type for saga completion detection
            # Problem: BrokerConnectionEstablishedSagaCompleted was transformed to broker_connection_update
            # WSEHandlers couldn't identify saga completion events to send account snapshots
            # Solution: Add original_event_type field so handlers can detect saga events
            wse_event = {
                "event_type": ws_event_type,
                "original_event_type": event_type,  # Preserve original for saga detection
                "user_id": str(user_id),
                "broker_id": transformed_data.get("broker_id"),
                "environment": transformed_data.get("environment"),
                "data": transformed_data,
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific broker connection topic
            topic = f"user:{user_id}:broker_connection_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event
            )

            self._events_forwarded += 1
            log.info(f"[WSEDomainPublisher] Forwarded {event_type} -> {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling broker connection event: {e}", exc_info=True)

    async def _handle_account_event(self, event: Dict[str, Any]) -> None:
        """Handle broker account domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")

            if not event_type or not user_id:
                log.warning(f"Account event missing event_type or user_id: {event}")
                return

            # CRITICAL FIX (Nov 16, 2025): Add diagnostic logging for BrokerAccountLinked
            if event_type == "BrokerAccountLinked":
                broker_id = event.get("broker_id")
                broker_conn_id = event.get("broker_connection_id")
                log.info(
                    f"[WSEDomainPublisher] Received BrokerAccountLinked: "
                    f"broker_id={broker_id}, broker_connection_id={broker_conn_id}, "
                    f"user_id={user_id}, account_id={event.get('account_aggregate_id')}"
                )
                # Validate broker_id for account events
                if not broker_id or broker_id == "unknown":
                    log.error(
                        f"[WSEDomainPublisher] BrokerAccountLinked has invalid broker_id: {broker_id}. "
                        f"Connection: {broker_conn_id}, User: {user_id}. "
                        f"This will cause account to not appear in WebSocket."
                    )
                    # Don't reject - try to forward anyway for debugging

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for event type: {event_type}")
                return

            # DEBUG: Log balance updates specifically (INFO level)
            if event_type == "AccountDataFromBrokerUpdated":
                log.info(
                    f"[WSE] BALANCE UPDATE RECEIVED - "
                    f"Event: {event_type}, "
                    f"User: {user_id}, "
                    f"Account: {event.get('account_aggregate_id')}, "
                    f"Balance: {event.get('balance')}, "
                    f"Equity: {event.get('equity')}, "
                    f"Buying Power: {event.get('buying_power')}"
                )

            # Transform to WebSocket format
            transformed_data = self._transform_account_event(event)

            # CRITICAL FIX (Nov 15, 2025): Promote broker_id and environment to top level
            # Frontend expects these fields at top level, not inside "data"
            # CRITICAL FIX (Nov 16, 2025): Preserve original event_type for saga completion detection
            # Problem: BrokerConnectionEstablishedSagaCompleted was transformed to broker_connection_update
            # WSEHandlers couldn't identify saga completion events to send account snapshots
            # Solution: Add original_event_type field so handlers can detect saga events
            wse_event = {
                "event_type": ws_event_type,
                "original_event_type": event_type,  # Preserve original for saga detection
                "user_id": str(user_id),
                "broker_id": transformed_data.get("broker_id"),
                "environment": transformed_data.get("environment"),
                "data": transformed_data,
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific topic
            topic = f"user:{user_id}:broker_account_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1

            # CRITICAL FIX (Nov 16, 2025): Log successful forwarding of BrokerAccountLinked
            if event_type == "BrokerAccountLinked":
                log.info(
                    f"[WSEDomainPublisher] Forwarded BrokerAccountLinked -> {ws_event_type} "
                    f"to {topic} for broker={wse_event.get('broker_id')}"
                )

            # DEBUG: Confirm successful forwarding for balance updates
            elif event_type == "AccountDataFromBrokerUpdated":
                log.info(
                    f"[WSE] BALANCE UPDATE FORWARDED - "
                    f"Topic: {topic}, "
                    f"WS Event Type: {ws_event_type}, "
                    f"Event ID: {event.get('event_id')}"
                )
            else:
                log.debug(f"Forwarded {event_type} → {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling account event: {e}", exc_info=True)

    async def _handle_order_event(self, event: Dict[str, Any]) -> None:
        """Handle order domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")

            if not event_type or not user_id:
                log.warning(f"Order event missing event_type or user_id: {event}")
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
                "data": self._transform_order_event(event),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific order events topic
            topic = f"user:{user_id}:order_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} → {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling order event: {e}", exc_info=True)

    async def _handle_position_event(self, event: Dict[str, Any]) -> None:
        """Handle position domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")

            if not event_type or not user_id:
                log.warning(f"Position event missing event_type or user_id: {event}")
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
                "data": self._transform_position_event(event),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific position events topic
            topic = f"user:{user_id}:position_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} → {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling position event: {e}", exc_info=True)

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

            # Publish to user-specific events topic (FIXED: match frontend subscription name)
            topic = f"user:{user_id}:user_account_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} → {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling user event: {e}", exc_info=True)

    async def _handle_automation_event(self, event: Dict[str, Any]) -> None:
        """Handle automation domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")

            if not event_type or not user_id:
                log.warning(f"Automation event missing event_type or user_id: {event}")
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
                "data": self._transform_automation_event(event),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific automation events topic
            topic = f"user:{user_id}:automation_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} → {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling automation event: {e}", exc_info=True)

    # =========================================================================
    # EVENT TRANSFORMERS
    # =========================================================================

    def _transform_broker_connection_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform broker connection event to WSE format"""
        # CRITICAL FIX (Nov 15, 2025): Derive connection status from event type if not explicitly set
        # Problem: Some events (BrokerConnectionEstablished, BrokerConnectionRestored) may not have
        # "connected" field, causing frontend to show DISCONNECTED status when user clicks Connect
        event_type = event.get("event_type")
        connected = event.get("connected")

        # DEBUG LOGGING (Nov 15, 2025): Track incoming event
        log.info(f"[WSE DEBUG] _transform_broker_connection_event RECEIVED event_type={event_type}, connected={connected}, full_event={event}")

        if connected is None:
            # Infer from event type
            if event_type in ["BrokerConnectionEstablished", "BrokerConnectionRestored"]:
                connected = True
                log.info(f"[WSE DEBUG] Inferred connected=True from event_type={event_type}")
            elif event_type in ["BrokerDisconnected", "BrokerConnectionAttemptFailed"]:
                connected = False
                log.info(f"[WSE DEBUG] Inferred connected=False from event_type={event_type}")
            # Otherwise keep None (will be filtered by snapshot logic)

        # CRITICAL FIX (Nov 15, 2025): Infer status from event_type for events without explicit status field
        # PROBLEM: Domain events don't have "status" field, only "connected" field
        # When user clicks Connect, 3 events arrive:
        #   1. BrokerConnectionInitiated (no status) -> should be CONNECTING
        #   2. BrokerApiCredentialsStored (no status) -> should be CONNECTING
        #   3. BrokerConnectionEstablished (no status) -> should be CONNECTED
        status = event.get("status") or event.get("last_connection_status")
        if not status:
            # Infer status from event type
            if event_type in ["BrokerConnectionEstablished", "BrokerConnectionRestored", "BrokerConnectionEstablishedSagaCompleted"]:
                status = "CONNECTED"
                log.info(f"[WSE DEBUG] Inferred status=CONNECTED from event_type={event_type}")
            elif event_type in ["BrokerConnectionInitiated", "BrokerApiCredentialsStored", "BrokerOAuthClientCredentialsStored",
                                "BrokerOAuthFlowStarted", "BrokerTokensSuccessfullyStored", "BrokerApiEndpointConfigured"]:
                status = "CONNECTING"
                log.info(f"[WSE DEBUG] Inferred status=CONNECTING from event_type={event_type}")
            elif event_type in ["BrokerDisconnected"]:
                status = "DISCONNECTED"
                log.info(f"[WSE DEBUG] Inferred status=DISCONNECTED from event_type={event_type}")
            elif event_type in ["BrokerConnectionAttemptFailed"]:
                status = "ERROR"
                log.info(f"[WSE DEBUG] Inferred status=ERROR from event_type={event_type}")

        result = {
            "broker_connection_id": event.get("aggregate_id") or event.get("broker_connection_id"),
            "broker_id": event.get("broker_id"),
            "environment": event.get("environment"),
            "connected": connected,
            "status": status,
            "status_message": event.get("status_message") or event.get("last_status_reason"),
            "api_endpoint": event.get("api_endpoint_used") or event.get("api_endpoint"),
            "last_connected_at": event.get("last_connected_at"),
            "disconnected_at": event.get("disconnected_at"),
            "error": event.get("error") or event.get("last_error"),
            "reauth_required": event.get("reauth_required"),
        }

        # DEBUG LOGGING: Track transformed result
        log.info(f"[WSE DEBUG] _transform_broker_connection_event RESULT connected={result['connected']}, result={result}")

        return result

    def _transform_account_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform account event to WSE format"""
        # DEBUG LOGGING (Nov 15, 2025): Track incoming account event
        event_type = event.get("event_type")
        broker_id = event.get("broker_id")
        environment = event.get("environment")
        log.info(f"[WSE DEBUG] _transform_account_event RECEIVED event_type={event_type}, broker_id={broker_id}, environment={environment}, full_event={event}")

        result = {
            "account_id": event.get("aggregate_id"),
            "broker_account_id": event.get("broker_account_id"),
            "broker_connection_id": event.get("broker_connection_id"),
            "account_type": event.get("account_type"),
            "balance": event.get("balance"),
            "equity": event.get("equity"),
            "buying_power": event.get("buying_power"),
            "status": event.get("status"),
            "currency": event.get("currency"),
            "broker_id": event.get("broker_id"),
            "environment": event.get("environment"),
            "metadata": event.get("metadata", {}),
        }

        # DEBUG LOGGING: Track transformed result
        log.info(f"[WSE DEBUG] _transform_account_event RESULT broker_id={result['broker_id']}, environment={result['environment']}, result={result}")

        return result

    def _transform_order_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform order event to WSE format"""
        return {
            "order_id": event.get("aggregate_id") or event.get("order_id"),
            "broker_account_id": event.get("broker_account_id"),
            "automation_id": event.get("automation_id"),
            "symbol": event.get("symbol"),
            "order_type": event.get("order_type"),
            "side": event.get("side"),
            "quantity": event.get("quantity"),
            "filled_quantity": event.get("filled_quantity"),
            "price": event.get("price"),
            "status": event.get("status"),
            "broker_order_id": event.get("broker_order_id"),
            "client_order_id": event.get("client_order_id"),
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
        }

    def _transform_position_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform position event to WSE format"""
        return {
            "position_id": event.get("aggregate_id") or event.get("position_id"),
            "broker_account_id": event.get("broker_account_id"),
            "automation_id": event.get("automation_id"),
            "symbol": event.get("symbol"),
            "asset_type": event.get("asset_type"),
            "side": event.get("side"),
            "quantity": event.get("quantity"),
            "average_entry_price": event.get("average_entry_price"),
            "current_price": event.get("current_price"),
            "stop_loss_price": event.get("stop_loss_price"),
            "take_profit_price": event.get("take_profit_price"),
            "unrealized_pnl": event.get("unrealized_pnl"),
            "unrealized_pnl_pct": event.get("unrealized_pnl_pct"),
            "realized_pnl": event.get("realized_pnl"),
            "total_pnl": event.get("total_pnl"),
            "total_pnl_pct": event.get("total_pnl_pct"),
            "pyramiding_count": event.get("pyramiding_count"),
            "status": event.get("status"),
            "opened_at": event.get("opened_at"),
            "closed_at": event.get("closed_at"),
        }

    def _transform_user_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform user event to WSE format"""
        return {
            "user_id": event.get("aggregate_id") or event.get("user_id"),
            "email": event.get("email"),
            "username": event.get("username"),
            "preferences": event.get("preferences", {}),
            "metadata": event.get("metadata", {}),
        }

    def _transform_automation_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform automation event to WSE format"""
        return {
            "automation_id": event.get("aggregate_id") or event.get("automation_id"),
            "name": event.get("name"),
            "status": event.get("status"),
            "enabled": event.get("enabled"),
            "configuration": event.get("configuration", {}),
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
                "accounts": self._enable_account_events,
                "orders": self._enable_order_events,
                "positions": self._enable_position_events,
                "users": self._enable_user_events,
                "automation": self._enable_automation_events,
            }
        }

# =============================================================================
# EOF
# =============================================================================
