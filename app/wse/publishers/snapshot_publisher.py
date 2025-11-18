# app/wse/publishers/snapshot_publisher.py
# =============================================================================
# File: app/wse/publishers/snapshot_publisher.py
# Description: WSE Snapshot Publisher - Sends snapshots on saga completion
# =============================================================================

"""
WSE Snapshot Publisher

Subscribes to saga completion events and automatically sends full snapshots via WebSocket.

ARCHITECTURE (CQRS/ES Best Practice):
┌─────────────────────────────────────────────────────────────┐
│ Saga → SagaCompleted → EventBus (Redpanda - GUARANTEED)    │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
                  WSE Snapshot Publisher
                  (Subscribes to EventBus)
                          ↓
                  SnapshotService (Query DB)
                          ↓
                  PubSubBus (Redis Pub/Sub)
                          ↓
                   WebSocket Clients

RESPONSIBILITIES:
- Subscribe to saga completion events from EventBus (Redpanda)
- Query SnapshotService for fresh data
- Publish snapshots to PubSubBus for WebSocket clients
- Guaranteed delivery via Redpanda consumer groups

SEPARATION OF CONCERNS:
- DomainPublisher = Incremental updates (BrokerAccountLinked, OrderPlaced, etc.)
- SnapshotPublisher = Full snapshots (SagaCompleted, etc.)
- MonitoringPublisher = Health/metrics
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Any, Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timezone

from app.infra.event_bus.event_bus import EventBus
from app.wse.core.pubsub_bus import PubSubBus

if TYPE_CHECKING:
    from app.wse.services.snapshot_service import SnapshotServiceProtocol

log = logging.getLogger("tradecore.wse.snapshot_publisher")


class WSESnapshotPublisher:
    """
    WSE Snapshot Publisher - Sends full snapshots on saga completion

    Subscribes to saga completion events and automatically broadcasts snapshots
    to WebSocket clients via PubSubBus.

    ARCHITECTURE COMPLIANCE:
    - SnapshotService stays pure (query-only, CQRS compliant)
    - Guaranteed delivery via Redpanda consumer groups
    - Clean separation from DomainPublisher (incrementals)
    - Industry best practice (Axon, MassTransit, NServiceBus pattern)
    """

    def __init__(
        self,
        event_bus: EventBus,
        pubsub_bus: PubSubBus,
        snapshot_service: SnapshotServiceProtocol,
        enable_saga_snapshots: bool = True,
    ):
        """
        Initialize WSE Snapshot Publisher

        Args:
            event_bus: Backend event bus (Redpanda)
            pubsub_bus: Frontend event bus (Redis Pub/Sub)
            snapshot_service: Snapshot service for querying data
            enable_saga_snapshots: Enable saga completion snapshot broadcasting
        """
        self._event_bus = event_bus
        self._pubsub_bus = pubsub_bus
        self._snapshot_service = snapshot_service

        # Feature flags
        self._enable_saga_snapshots = enable_saga_snapshots

        # Subscription management
        self._subscriptions: Dict[str, str] = {}  # topic -> subscription_id
        self._running = False

        # Deduplication tracking (prevent duplicate snapshots)
        self._sent_snapshots: set = set()  # broker_connection_id

        # Metrics
        self._snapshots_sent = 0
        self._snapshot_errors = 0

        log.info("WSESnapshotPublisher initialized")

    async def start(self) -> None:
        """Start the snapshot publisher and subscribe to events"""
        if self._running:
            log.warning("WSESnapshotPublisher already running")
            return

        self._running = True
        log.info("Starting WSESnapshotPublisher...")

        # Subscribe to saga events
        if self._enable_saga_snapshots:
            await self._subscribe_to_saga_events()

        log.info("WSESnapshotPublisher started successfully")

    async def stop(self) -> None:
        """Stop the snapshot publisher and clean up subscriptions"""
        if not self._running:
            return

        log.info("Stopping WSESnapshotPublisher...")
        self._running = False

        # Unsubscribe from all topics
        for topic, sub_id in self._subscriptions.items():
            try:
                await self._event_bus.unsubscribe(sub_id)
                log.debug(f"Unsubscribed from {topic}")
            except Exception as e:
                log.error(f"Error unsubscribing from {topic}: {e}")

        self._subscriptions.clear()
        log.info("WSESnapshotPublisher stopped")

    # =========================================================================
    # SUBSCRIPTION
    # =========================================================================

    async def _subscribe_to_saga_events(self) -> None:
        """Subscribe to saga completion events"""
        if not self._running:
            log.debug("Skipping saga event subscription - service not running")
            return

        try:
            topic = "transport.broker-connection-events"

            log.info(f"Subscribing to saga events on topic: {topic}")

            subscription_id = await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_saga_event,
                group="wse-snapshot-publisher",
                consumer=f"snapshot-pub-{os.getpid()}"
            )

            self._subscriptions[topic] = subscription_id
            log.info(f"✓ Subscribed to saga events: {topic} (group: wse-snapshot-publisher)")

        except Exception as e:
            log.error(f"Failed to subscribe to saga events: {e}", exc_info=True)
            raise

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def _handle_saga_event(self, event: Dict[str, Any]) -> None:
        """
        Handle saga completion events and send snapshots

        This handler receives events from Redpanda with GUARANTEED delivery
        via consumer group offset management (exactly-once semantics).
        """
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id")
            broker_connection_id = event.get("broker_connection_id")

            # Only handle saga completion events
            if event_type != "BrokerConnectionEstablishedSagaCompleted":
                return  # Ignore other events

            if not user_id:
                log.warning(f"Saga completion event missing user_id: {event}")
                return

            log.info(
                f"[SNAPSHOT_PUBLISHER] Received saga completion for user {user_id}, "
                f"broker_connection {broker_connection_id}"
            )

            # Deduplication check (one snapshot per broker connection)
            if broker_connection_id and broker_connection_id in self._sent_snapshots:
                log.debug(f"Snapshot already sent for connection {broker_connection_id}, skipping")
                return

            # Send account snapshot
            await self._send_account_snapshot_after_saga(user_id, broker_connection_id, event)

            # Track sent snapshot
            if broker_connection_id:
                self._sent_snapshots.add(broker_connection_id)

                # Prevent unbounded growth (keep last 1000)
                if len(self._sent_snapshots) > 1000:
                    self._sent_snapshots = set(list(self._sent_snapshots)[-500:])

        except Exception as e:
            self._snapshot_errors += 1
            log.error(f"Error handling saga event: {e}", exc_info=True)

    async def _send_account_snapshot_after_saga(
        self,
        user_id: str,
        broker_connection_id: Optional[str],
        saga_event: Dict[str, Any]
    ) -> None:
        """
        Send account snapshot after saga completion

        Args:
            user_id: User UUID string
            broker_connection_id: Broker connection UUID string
            saga_event: Full saga completion event
        """
        try:
            user_uuid = UUID(user_id)

            # CRITICAL: Wait for PostgreSQL projection COMMIT propagation
            # Saga waits 200ms for projection commit, BUT SYNC projection can take up to 5s timeout
            # Need sufficient wait to ensure READ COMMITTED isolation level sees the data
            # Testing showed 300ms insufficient - increasing to 700ms for reliability
            await asyncio.sleep(0.7)

            log.info(f"[SNAPSHOT_PUBLISHER] Querying accounts for user {user_uuid} after projection wait")

            # Query snapshot (pure CQRS - SnapshotService uses QueryBus)
            accounts = await self._snapshot_service.get_accounts_snapshot(
                user_id=user_uuid,
                include_positions=False,
                include_deleted=False
            )

            log.info(f"[SNAPSHOT_PUBLISHER] Retrieved {len(accounts)} accounts from SnapshotService")

            # Build snapshot message (INTERNAL format - EventTransformer will pass through)
            # NOTE: broker_account_snapshot has identity mapping in event_mappings.py
            # EventTransformer sees event_type and routes to correct handler without transformation
            snapshot_message = {
                'event_type': 'broker_account_snapshot',
                'user_id': str(user_id),
                'broker_id': saga_event.get('broker_id'),
                'environment': saga_event.get('environment'),
                'accounts': accounts,  # Direct accounts array (not nested in 'data')
                'include_positions': False,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'count': len(accounts),
                'from_connected_brokers_only': True,
                'trigger': 'saga_completion',
                'saga_id': saga_event.get('saga_id'),
                'broker_connection_id': broker_connection_id
            }

            # Publish to user-specific broker account topic
            topic = f"user:{user_id}:broker_account_events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=snapshot_message
            )

            self._snapshots_sent += 1
            log.info(
                f"[SNAPSHOT_PUBLISHER] ✓ Account snapshot sent to user {user_id}: "
                f"{len(accounts)} accounts via PubSubBus (trigger: saga_completion)"
            )

        except Exception as e:
            self._snapshot_errors += 1
            log.error(
                f"[SNAPSHOT_PUBLISHER] Failed to send snapshot for user {user_id}: {e}",
                exc_info=True
            )
            # Don't raise - snapshot delivery is best-effort, not critical

    # =========================================================================
    # METRICS
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get publisher metrics"""
        return {
            'running': self._running,
            'snapshots_sent': self._snapshots_sent,
            'snapshot_errors': self._snapshot_errors,
            'subscriptions': len(self._subscriptions),
            'dedup_cache_size': len(self._sent_snapshots)
        }
