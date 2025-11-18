# =============================================================================
# File: app/wse/websocket/wse_handlers.py
# Description: Message handlers for WebSocket protocol
# UPDATED: Added Order snapshot support for trading_events topic
# UPDATED: Filter disconnected broker events from being sent to frontend
# =============================================================================
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import UUID
from enum import Enum

from app.api.models.wse_api_models import MessagePriority
from app.wse.services.snapshot_service import SnapshotServiceProtocol
from app.wse.core.types import EventPriority

log = logging.getLogger("tradecore.wse_handlers")

# Module-level tracking for broker monitoring tasks
_monitoring_tasks: Dict[str, asyncio.Task] = {}  # user_id -> Task


class ConnectionState(Enum):
    """WebSocket connection states matching frontend"""
    PENDING = "pending"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEGRADED = "degraded"


class WSEHandler:
    """Handles incoming WebSocket messages with full frontend compatibility"""

    def __init__(self, connection, snapshot_service: SnapshotServiceProtocol):
        """
        Initialize handler with WebSocket connection and snapshot service

        Args:
            connection: WebSocketConnection instance
            snapshot_service: Snapshot service for fetching data
        """
        self.connection = connection
        self.snapshot_service = snapshot_service

        # Message type handlers - comprehensive list matching frontend
        self.handlers = {
            # Ping/Pong handlers
            'ping': self.handle_ping,
            'PING': self.handle_ping,
            'pong': self.handle_pong,
            'PONG': self.handle_pong,

            # Connection management
            'client_hello': self.handle_client_hello,
            'connection_state_request': self.handle_connection_state_request,

            # Subscription management
            'subscription': self.handle_subscription,
            'subscription_update': self.handle_subscription,

            # Data synchronization
            'sync_request': self.handle_sync_request,
            'request_broker_snapshot': self.handle_broker_snapshot_request,
            'request_account_snapshot': self.handle_account_snapshot_request,
            'request_order_snapshot': self.handle_order_snapshot_request,

            # Health and metrics
            'health_check': self.handle_health_check,
            'health_check_request': self.handle_health_check,
            'health_check_response': self.handle_health_check_response,
            'metrics_request': self.handle_metrics_request,
            'metrics_response': self.handle_metrics_response,

            # Configuration
            'config_update': self.handle_config_update,
            'config_request': self.handle_config_request,

            # Message handling
            'priority_message': self.handle_priority_message,
            'batch_message': self.handle_batch_message,

            # Debug and diagnostics
            'debug_handlers': self.handle_debug_request,
            'debug_request': self.handle_debug_request,
            'sequence_stats_request': self.handle_sequence_stats_request,

            # Security
            'encryption_request': self.handle_encryption_request,
            'key_rotation_request': self.handle_key_rotation_request,

            # System status handlers
            'system_status_request': self.handle_system_status_request,

            # Broker-specific message types (from upstream broker WebSocket)
            'broker_action': self.handle_broker_action,  # Alpaca broker action messages
        }

    async def handle_message(self, message_data: Dict[str, Any]) -> None:
        """Route message to appropriate handler with enhanced error handling"""
        if not message_data:
            return

        # Normalize message format
        message_data = self._normalize_message_format(message_data)

        # Check for duplicate messages
        msg_id = message_data.get('id')
        if msg_id and self.connection.is_duplicate_message(msg_id):
            self.connection.metrics.messages_dropped += 1
            log.debug(f"Dropped duplicate message: {msg_id}")
            return

        # Get message type
        msg_type = message_data.get('t') or message_data.get('type')

        # Log message handling
        log.debug(f"Handling message type: {msg_type}")

        # Route to handler
        handler = self.handlers.get(msg_type)
        if handler:
            try:
                await handler(message_data)
            except Exception as e:
                log.error(f"Error handling {msg_type}: {e}", exc_info=True)
                await self._send_error(
                    f"Error processing {msg_type}: {str(e)}",
                    "HANDLER_ERROR",
                    recoverable=True
                )
        else:
            # Unknown message type - publish to event bus for custom handling
            log.warning(f"Unknown message type: {msg_type}")
            await self._publish_client_message(msg_type, message_data)

    def _normalize_message_format(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message format to use 't' and 'p' consistently"""
        # Convert 'type' to 't'
        if 'type' in message_data and 't' not in message_data:
            message_data['t'] = message_data.pop('type')

        # Convert 'payload' to 'p'
        if 'payload' in message_data and 'p' not in message_data:
            message_data['p'] = message_data.pop('payload')

        # Ensure 'p' exists
        if 'p' not in message_data:
            message_data['p'] = {}

        return message_data

    async def handle_ping(self, message_data: Any) -> None:
        """Handle ping message with enhanced latency tracking"""
        # Extract timestamp
        timestamp = None

        if isinstance(message_data, str):
            # Plain text PING
            if ':' in message_data:
                try:
                    timestamp = int(message_data.split(':', 1)[1])
                except Exception:
                    timestamp = int(datetime.now().timestamp() * 1000)
        elif isinstance(message_data, dict):
            # JSON ping
            payload = message_data.get('p', {})
            timestamp = payload.get('timestamp') or payload.get('ts')

        if timestamp is None:
            timestamp = int(datetime.now().timestamp() * 1000)

        # Send pong with detailed timing
        await self.connection.send_message({
            't': 'PONG',
            'p': {
                'client_timestamp': timestamp,
                'server_timestamp': int(datetime.now().timestamp() * 1000),
                'connection_id': self.connection.conn_id
            }
        }, priority=MessagePriority.CRITICAL)

        # Calculate and record latency
        latency = datetime.now().timestamp() * 1000 - timestamp
        self.connection.metrics.record_latency(latency)
        self.connection.network_analyzer.record_latency(latency)

    async def handle_pong(self, message_data: Dict[str, Any]) -> None:
        """Handle pong response from client"""
        payload = message_data.get('p', {})
        if 'server_timestamp' in payload:
            latency = datetime.now().timestamp() * 1000 - payload['server_timestamp']
            self.connection.metrics.record_latency(latency)

    async def handle_client_hello(self, message_data: Dict[str, Any]) -> None:
        """Handle client hello message for protocol negotiation"""
        payload = message_data.get('p', {})

        # Extract client information
        client_version = payload.get('client_version', 'unknown')
        protocol_version = payload.get('protocol_version', 2)
        features = payload.get('features', {})
        capabilities = payload.get('capabilities', [])

        # Update connection with client information
        self.connection.client_version = client_version
        self.connection.protocol_version = protocol_version
        self.connection.client_features = features
        self.connection.client_capabilities = capabilities

        # Log client information
        log.info(f"Client hello received - Version: {client_version}, Protocol: {protocol_version}")
        log.debug(f"Client features: {features}")
        log.debug(f"Client capabilities: {capabilities}")

        # Send server hello response
        from app import __version__
        await self.connection.send_message({
            't': 'server_hello',
            'p': {
                'server_version': f'{__version__}',
                'protocol_version': self.connection.protocol_version,
                'supported_features': {
                    'compression': self.connection.compression_enabled,
                    'encryption': self.connection.encryption_enabled,
                    'batching': True,
                    'priority_queue': True,
                    'circuit_breaker': True,
                    'message_signing': self.connection.security_manager.message_signing_enabled,
                    'health_check': True,
                    'metrics': True
                },
                'server_time': datetime.now(timezone.utc).isoformat(),
                'connection_id': self.connection.conn_id,
                'message': 'Welcome to TradeCore WebSocket Events'
            }
        }, priority=MessagePriority.HIGH.value)

    async def handle_connection_state_request(self, message_data: Dict[str, Any]) -> None:
        """Handle connection state request"""
        state = getattr(self.connection, 'connection_state', ConnectionState.CONNECTED)

        await self.connection.send_message({
            't': 'connection_state_response',
            'p': {
                'state': state.value if isinstance(state, Enum) else str(state),
                'connection_id': self.connection.conn_id,
                'connected_since': self.connection.metrics.connected_since.isoformat() if self.connection.metrics.connected_since else None,
                'metrics': {
                    'messages_sent': self.connection.metrics.messages_sent,
                    'messages_received': self.connection.metrics.messages_received,
                    'compression_ratio': self.connection.metrics.compression_ratio,
                    'avg_latency': self.connection.metrics.avg_latency
                }
            }
        }, priority=MessagePriority.HIGH.value)

    async def handle_subscription(self, message_data: Dict[str, Any]) -> None:
        """Handle subscription management with enhanced feedback"""
        payload = message_data.get('p', {})
        action = payload.get('action')
        topics = payload.get('topics', [])

        # For broker/account events, we need current state, not historical events
        # Set start_from_latest appropriately
        include_history = payload.get('include_history', False)
        start_from_latest = not include_history  # If not including history, start from latest

        if not topics:
            await self._send_error("No topics specified", "INVALID_SUBSCRIPTION")
            return

        success_topics = []
        failed_topics = []
        already_subscribed = []

        if action == 'subscribe':
            for topic in topics:
                if topic in self.connection.subscriptions:
                    already_subscribed.append(topic)
                    success_topics.append(topic)
                    continue

                self.connection.pending_subscriptions.add(topic)

                try:
                    # For broker events, we want the current state AND future updates
                    is_state_topic = any(t in topic for t in ['broker', 'account'])

                    normalized_topic = self._normalize_topic(topic)

                    log.info(f"=== SUBSCRIBING TO TOPIC ===")
                    log.info(f"Original topic: {topic}")
                    log.info(f"Normalized topic: {normalized_topic}")
                    log.info(f"Is state topic: {is_state_topic}")
                    log.info(f"User ID: {self.connection.user_id}")

                    # Note: Redis Pub/Sub doesn't support filters/transforms at subscribe time.
                    # Filtering (duplicates, disconnected events) happens in handler itself.
                    # Redis Pub/Sub delivers new messages only (from subscription time forward).
                    subscription_id = await self.connection.event_bus.subscribe(
                        pattern=normalized_topic,
                        handler=self._create_event_handler()
                    )

                    self.connection.subscription_ids[topic] = subscription_id
                    self.connection.subscriptions.add(topic)
                    self.connection.pending_subscriptions.discard(topic)
                    self.connection.failed_subscriptions.discard(topic)
                    success_topics.append(topic)

                    log.info(f"✓ Subscribed {self.connection.conn_id} to {topic} (normalized: {normalized_topic})")

                except Exception as e:
                    log.error(f"Failed to subscribe to {topic}: {e}", exc_info=True)
                    self.connection.failed_subscriptions.add(topic)
                    self.connection.pending_subscriptions.discard(topic)
                    failed_topics.append({'topic': topic, 'error': str(e)})

            # CRITICAL FIX: Prevent duplicate broker monitoring
            if 'broker_connection_events' in success_topics and self.connection.adapter_monitoring_service:
                user_id = self.connection.user_id

                # FIXED: Use a more specific key that includes connection instance
                monitoring_key = f"{user_id}_{self.connection.conn_id}"

                # Check if monitoring task already exists for this specific connection
                existing_task = _monitoring_tasks.get(monitoring_key)

                if existing_task and not existing_task.done():
                    log.info(
                        f"Broker monitoring already running for user {user_id} on connection {self.connection.conn_id}, skipping duplicate start")
                else:
                    log.info(f"Initiating broker monitoring for user {user_id} on connection {self.connection.conn_id}")

                    async def delayed_monitoring_start():
                        try:
                            # Wait before starting monitoring to avoid initial flood
                            await asyncio.sleep(2)  # 2 second delay

                            log.info(f"Starting delayed broker monitoring for user {user_id}")

                            # Verify broker monitoring service state
                            if not self.connection.adapter_monitoring_service:
                                log.error("Broker monitoring service is None!")
                                return

                            # Check reactive event bus availability via WSEMonitoringPublisher
                            has_reactive_bus = False
                            if hasattr(self.connection.adapter_monitoring_service, '_wse_publisher'):
                                wse_publisher = self.connection.adapter_monitoring_service._wse_publisher
                                log.info(
                                    f"[WSE_HANDLERS] Checking PubSubBus - "
                                    f"wse_publisher exists: {wse_publisher is not None}"
                                )
                                if wse_publisher and hasattr(wse_publisher, '_pubsub_bus'):
                                    has_reactive_bus = wse_publisher._pubsub_bus is not None
                                    log.info(
                                        f"[WSE_HANDLERS] WSE Publisher reactive bus check - "
                                        f"has_reactive_bus: {has_reactive_bus}, "
                                        f"_pubsub_bus type: {type(wse_publisher._pubsub_bus).__name__ if wse_publisher._pubsub_bus else 'None'}"
                                    )

                            if not has_reactive_bus:
                                log.error(
                                    f"[WSE_HANDLERS] Broker monitoring service has no reactive event bus! "
                                    f"Attempting injection from connection.event_bus..."
                                )

                                # Try to inject it from connection's event_bus
                                if (hasattr(self.connection.adapter_monitoring_service, '_wse_publisher') and
                                    hasattr(self.connection, 'event_bus') and
                                    hasattr(self.connection.event_bus, '_pubsub_bus')):

                                    wse_publisher = self.connection.adapter_monitoring_service._wse_publisher
                                    if wse_publisher:
                                        wse_publisher._pubsub_bus = self.connection.event_bus._pubsub_bus
                                        log.info(
                                            f"[WSE_HANDLERS] Injected reactive event bus - "
                                            f"Type: {type(wse_publisher._pubsub_bus).__name__ if wse_publisher._pubsub_bus else 'None'}"
                                        )
                                        has_reactive_bus = True

                            if has_reactive_bus:
                                # Start monitoring all broker connections for this user
                                # Convert user_id to UUID if it's a string, otherwise use as-is
                                user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
                                log.info(
                                    f"[WSE_HANDLERS] Starting user monitoring - "
                                    f"user_id: {user_id_uuid}, has_reactive_bus: True"
                                )
                                monitor_ids = await self.connection.adapter_monitoring_service.start_user_monitoring(
                                    user_id_uuid
                                )

                                if monitor_ids:
                                    log.info(
                                        f"[WSE_HANDLERS] Started {len(monitor_ids)} broker monitors for user {user_id} - "
                                        f"Incremental updates ENABLED"
                                    )
                                    log.info("✓ Reactive event bus is available - real-time updates enabled")
                                else:
                                    log.warning(f"[WSE_HANDLERS] No broker connections found to monitor for user {user_id}")
                            else:
                                log.error(
                                    f"[WSE_HANDLERS] Cannot start monitoring - reactive event bus not available! "
                                    f"Incremental updates DISABLED"
                                )

                        except Exception as e:
                            log.error(f"Failed to start broker monitoring: {e}", exc_info=True)
                        finally:
                            # Remove from tracking when done
                            if monitoring_key in _monitoring_tasks:
                                del _monitoring_tasks[monitoring_key]

                    # Create and track the task with connection-specific key
                    task = asyncio.create_task(delayed_monitoring_start())

                    # Add done callback to log errors
                    def _log_task_exception(t):
                        if t.cancelled():
                            log.debug(f"Monitoring task cancelled for user {user_id}")
                        elif t.exception():
                            log.error(f"Monitoring task failed for user {user_id}: {t.exception()}", exc_info=t.exception())

                    task.add_done_callback(_log_task_exception)
                    _monitoring_tasks[monitoring_key] = task
                    log.info(f"Created monitoring task for user {user_id} on connection {self.connection.conn_id}")

            # Send streaming status snapshot if newly subscribed (async to not block)
            log.info(f"Checking broker_streaming snapshot condition: in_success={('broker_streaming' in success_topics)}, not_already_subscribed={('broker_streaming' not in already_subscribed)}, success_topics={success_topics}, already_subscribed={already_subscribed}")
            if 'broker_streaming' in success_topics and 'broker_streaming' not in already_subscribed:
                log.info("✓ Condition MET - Creating task to send streaming status snapshot")
                async def send_streaming_snapshot():
                    try:
                        user_id = UUID(self.connection.user_id)
                        await asyncio.sleep(0.1)  # Small delay to not block subscription response
                        log.info(f"Sending streaming status snapshot for newly subscribed user {user_id}")
                        await self._send_streaming_status_snapshot(user_id)
                    except Exception as e:
                        log.error(f"Failed to send streaming status snapshot: {e}", exc_info=True)

                asyncio.create_task(send_streaming_snapshot())
            else:
                log.info("✗ Condition NOT MET - Snapshot will not be sent")

        elif action == 'unsubscribe':
            for topic in topics:
                if topic not in self.connection.subscriptions:
                    success_topics.append(topic)
                    continue

                if topic in self.connection.subscription_ids:
                    try:
                        await self.connection.event_bus.unsubscribe(
                            self.connection.subscription_ids[topic]
                        )
                        del self.connection.subscription_ids[topic]
                        success_topics.append(topic)
                    except Exception as e:
                        log.error(f"Failed to unsubscribe from {topic}: {e}")
                        failed_topics.append({'topic': topic, 'error': str(e)})

                self.connection.subscriptions.discard(topic)
                self.connection.failed_subscriptions.discard(topic)

            # Stop broker monitoring if unsubscribing from broker events
            if 'broker_connection_events' in success_topics and self.connection.adapter_monitoring_service:
                try:
                    user_id = self.connection.user_id
                    monitoring_key = f"{user_id}_{self.connection.conn_id}"

                    log.info(f"Stopping broker monitoring for user {user_id}")

                    # Cancel monitoring task if exists
                    if monitoring_key in _monitoring_tasks:
                        task = _monitoring_tasks[monitoring_key]
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                        del _monitoring_tasks[monitoring_key]

                    # Stop monitoring for this user
                    stopped_count = await self.connection.adapter_monitoring_service.stop_user_monitoring(
                        UUID(user_id)
                    )

                    if stopped_count > 0:
                        log.info(f"✓ Stopped {stopped_count} broker monitors for user {user_id}")

                except Exception as e:
                    log.error(f"Failed to stop broker monitoring: {e}", exc_info=True)
                    # Don't fail the unsubscription, just log the error

        else:
            await self._send_error(f"Invalid subscription action: {action}", "INVALID_ACTION")
            return

        # Send detailed subscription update
        await self.connection.send_message({
            't': 'subscription_update',
            'p': {
                'action': action,
                'success': len(failed_topics) == 0,
                'message': f"Successfully {action}d {len(success_topics)} topics",
                'topics': list(self.connection.subscriptions),
                'success_topics': success_topics,
                'failed_topics': failed_topics,
                'already_subscribed': already_subscribed,
                'pending_subscriptions': list(self.connection.pending_subscriptions),
                'failed_subscriptions': list(self.connection.failed_subscriptions),
                'active_subscriptions': list(self.connection.subscriptions),
                'subscription_limits': {
                    'max_topics': 100,
                    'current_topics': len(self.connection.subscriptions)
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }, priority=MessagePriority.NORMAL.value)

        # CRITICAL FIX (Nov 12, 2025): Auto-send snapshots ONLY for broker connections
        # Account snapshots are sent when BrokerAccountLinked event arrives (after projection completes)
        # This prevents race condition where snapshot is sent before SYNC projection writes to DB
        if action == 'subscribe' and len(success_topics) > 0:
            try:
                user_id = UUID(self.connection.user_id)

                # Auto-send broker snapshot if subscribed to broker events
                if 'broker_connection_events' in success_topics:
                    log.info(f"✓ Auto-sending broker snapshot after subscription")
                    await self._send_broker_snapshot(user_id, include_module_details=False)

                # REMOVED (Nov 17, 2025): Auto-send account snapshot on subscription
                # REPLACED WITH: WSESnapshotPublisher service (clean architecture)
                # Account snapshots now sent automatically by SnapshotPublisher when saga completes
                # This provides guaranteed delivery via Redpanda consumer groups (no Redis Pub/Sub timing race)

            except Exception as e:
                log.error(f"Failed to auto-send snapshots after subscription: {e}", exc_info=True)

    async def handle_sync_request(self, message_data: Dict[str, Any]) -> None:
        """Handle sync request for initial data with enhanced options"""
        payload = message_data.get('p', {})
        topics = payload.get('topics', [])
        last_sequence = payload.get('last_sequence', 0)
        include_snapshots = payload.get('include_snapshots', True)
        include_positions = payload.get('include_positions', False)
        include_module_details = payload.get('include_module_details', False)
        include_history = payload.get('include_history', False)

        log.info("=== SYNC REQUEST RECEIVED ===")
        log.info(f"User: {self.connection.user_id}")
        log.info(f"Topics: {topics}")
        log.info(f"Include snapshots: {include_snapshots}")
        log.info(f"Include history: {include_history}")

        # FIXED: Add sync request tracking to prevent duplicates
        sync_key = f"sync_{self.connection.user_id}_{self.connection.conn_id}"
        current_time = datetime.now(timezone.utc)

        # Check if we recently sent snapshots to this connection
        if hasattr(self.connection, '_last_sync_time'):
            time_since_last_sync = (current_time - self.connection._last_sync_time).total_seconds()
            if time_since_last_sync < 5.0:  # 5 seconds cooldown
                log.warning(f"Sync request too soon after previous sync ({time_since_last_sync:.1f}s ago), ignoring")
                await self.connection.send_message({
                    't': 'snapshot_complete',
                    'p': {
                        'message': 'Sync already completed recently',
                        'success': True,
                        'snapshots_sent': [],
                        'details': {
                            'sequence': self.connection.sequence_number,
                            'topics': topics,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'skipped': True,
                            'reason': 'recent_sync'
                        }
                    }
                })
                return

        # Update sync time
        self.connection._last_sync_time = current_time

        snapshots_sent = []

        # FIXED: Track what we've already sent to prevent duplicates
        sent_broker_snapshot = False
        sent_account_snapshot = False
        sent_automation_snapshot = False
        sent_order_snapshot = False
        sent_position_snapshot = False

        if include_snapshots:
            try:
                user_id = UUID(self.connection.user_id)

                # Send broker connection snapshot (current state only)
                if not sent_broker_snapshot and any('broker' in topic.lower() for topic in topics):
                    log.info("Sending broker connection snapshot...")
                    await self._send_broker_snapshot(user_id, include_module_details)
                    snapshots_sent.append('broker_connections')
                    sent_broker_snapshot = True
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

                # Send account snapshot (current state only)
                if not sent_account_snapshot and any('account' in topic.lower() for topic in topics):
                    log.info("Sending account snapshot...")
                    await self._send_account_snapshot(user_id, include_positions)
                    snapshots_sent.append('accounts')
                    sent_account_snapshot = True
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

                # Send automation snapshot if requested
                if not sent_automation_snapshot and any('automation' in topic.lower() or 'strategy' in topic.lower() for topic in topics):
                    log.info("Sending automation snapshot...")
                    await self._send_automation_snapshot(user_id)
                    snapshots_sent.append('automations')
                    sent_automation_snapshot = True
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

                # Send order snapshot if requested
                if not sent_order_snapshot and any('trading' in topic.lower() or 'order' in topic.lower() for topic in topics):
                    log.info("Sending order snapshot...")
                    await self._send_order_snapshot(user_id, active_only=True)
                    snapshots_sent.append('orders')
                    sent_order_snapshot = True
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

                # Send position snapshot if requested
                if not sent_position_snapshot and any('trading' in topic.lower() or 'position' in topic.lower() for topic in topics):
                    log.info("Sending position snapshot...")
                    await self._send_position_snapshot(user_id, open_only=True)
                    snapshots_sent.append('positions')
                    sent_position_snapshot = True
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

                # Send streaming status snapshot if requested
                if 'broker_streaming' in topics:
                    log.info("Sending streaming status snapshot...")
                    await self._send_streaming_status_snapshot(user_id)
                    snapshots_sent.append('broker_streaming')
                    # Add small delay to prevent flooding
                    await asyncio.sleep(0.1)

            except Exception as e:
                log.error(f"Error during sync request: {e}", exc_info=True)
                await self._send_error(
                    "Failed to process sync request",
                    "SYNC_ERROR",
                    details=str(e),
                    recoverable=True
                )
                return

        # Send a snapshot complete with summary
        await self.connection.send_message({
            't': 'snapshot_complete',
            'p': {
                'message': 'Initial sync complete',
                'success': True,
                'snapshots_sent': snapshots_sent,
                'details': {
                    'sequence': self.connection.sequence_number,
                    'topics': topics,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'last_sequence_processed': last_sequence,
                    'include_history': include_history,
                    'connection_id': self.connection.conn_id
                }
            }
        })

        # Mark initial sync as complete
        if hasattr(self.connection, 'mark_initial_sync_complete'):
            await self.connection.mark_initial_sync_complete()

        log.info(f"Sync request completed successfully with {len(snapshots_sent)} snapshots")

    async def handle_broker_snapshot_request(self, message_data: Dict[str, Any]) -> None:
        """Handle explicit broker snapshot request"""
        payload = message_data.get('p', {})
        include_module_details = payload.get('include_module_details', False)

        try:
            user_id = UUID(self.connection.user_id)
            await self._send_broker_snapshot(user_id, include_module_details)
        except Exception as e:
            log.error(f"Error sending broker snapshot: {e}")
            await self._send_error(
                "Failed to fetch broker snapshot",
                "SNAPSHOT_ERROR",
                details=str(e)
            )

    async def handle_account_snapshot_request(self, message_data: Dict[str, Any]) -> None:
        """Handle explicit account snapshot request"""
        payload = message_data.get('p', {})
        include_positions = payload.get('include_positions', False)

        try:
            user_id = UUID(self.connection.user_id)
            await self._send_account_snapshot(user_id, include_positions)
        except Exception as e:
            log.error(f"Error sending account snapshot: {e}")
            await self._send_error(
                "Failed to fetch account snapshot",
                "SNAPSHOT_ERROR",
                details=str(e)
            )

    async def handle_order_snapshot_request(self, message_data: Dict[str, Any]) -> None:
        """Handle explicit order snapshot request"""
        payload = message_data.get('p', {})
        active_only = payload.get('active_only', True)
        account_id = payload.get('account_id')

        try:
            user_id = UUID(self.connection.user_id)

            # If account_id specified, get orders for specific account
            if account_id:
                log.info(f"Fetching orders for specific account: {account_id}")
                order_infos = await self.snapshot_service.get_orders_snapshot(
                    user_id=user_id,
                    account_id=UUID(account_id),
                    active_only=active_only
                )

                # Send filtered snapshot
                await self.connection.send_message({
                    't': 'order_snapshot',
                    'p': {
                        'orders': order_infos,
                        'account_id': account_id,
                        'active_only': active_only,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'count': len(order_infos)
                    }
                })

                log.info(f"✓ Order snapshot sent for account {account_id} with {len(order_infos)} orders")
            else:
                # Send all user orders
                await self._send_order_snapshot(user_id, active_only)

        except Exception as e:
            log.error(f"Error sending order snapshot: {e}")
            await self._send_error(
                "Failed to fetch order snapshot",
                "SNAPSHOT_ERROR",
                details=str(e)
            )

    async def handle_batch_message(self, message_data: Dict[str, Any]) -> None:
        """Handle batch of messages from client"""
        payload = message_data.get('p', {})
        messages = payload.get('messages', [])

        results = []
        for idx, msg in enumerate(messages):
            try:
                # Normalize each message in the batch
                msg = self._normalize_message_format(msg)
                await self.handle_message(msg)
                results.append({'index': idx, 'success': True})
            except Exception as e:
                log.error(f"Error processing batch message {idx}: {e}")
                results.append({
                    'index': idx,
                    'success': False,
                    'error': str(e)
                })

        # Send batch processing result
        await self.connection.send_message({
            't': 'batch_message_result',
            'p': {
                'total': len(messages),
                'successful': sum(1 for r in results if r['success']),
                'failed': sum(1 for r in results if not r['success']),
                'results': results
            }
        }, priority=MessagePriority.NORMAL.value)

    async def handle_health_check(self, message_data: Dict[str, Any]) -> None:
        """Handle health check request with comprehensive diagnostics"""
        # Get network diagnostics
        diagnostics = self.connection.network_analyzer.analyze()

        # Get circuit breaker state
        cb_metrics = self.connection.circuit_breaker.get_metrics()

        # Get sequence stats
        sequence_stats = await self.connection.event_sequencer.get_buffer_stats()

        await self.connection.send_message({
            't': 'health_check_response',
            'p': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'server_time': int(datetime.now().timestamp() * 1000),
                'connection_id': self.connection.conn_id,
                'status': 'healthy',
                'diagnostics': {
                    'connection_quality': diagnostics['quality'],
                    'network_jitter': diagnostics['jitter'],
                    'packet_loss': diagnostics['packet_loss'],
                    'avg_latency': self.connection.metrics.avg_latency,
                    'suggestions': diagnostics['suggestions']
                },
                'circuit_breaker': {
                    'state': cb_metrics['state'],
                    'failures': cb_metrics['failure_count'],
                    'success_count': cb_metrics.get('success_count', 0),
                    'last_failure_time': cb_metrics.get('last_failure_time')
                },
                'queue_stats': self.connection.message_queue.get_stats(),
                'sequence_stats': sequence_stats,
                'subscriptions': {
                    'active': len(self.connection.subscriptions),
                    'pending': len(self.connection.pending_subscriptions),
                    'failed': len(self.connection.failed_subscriptions)
                },
                'client_info': {
                    'version': self.connection.client_version,
                    'protocol': self.connection.protocol_version,
                    'features': self.connection.client_features
                }
            }
        }, priority=MessagePriority.HIGH.value)

        self.connection.metrics.last_health_check = datetime.now(timezone.utc)

    async def handle_health_check_response(self, message_data: Dict[str, Any]) -> None:
        """Process health check response from client with quality assessment"""
        payload = message_data.get('p', {})

        # Log client metrics
        if 'stats' in payload:
            log.info(f"Client stats for {self.connection.conn_id}: {payload['stats']}")

        if 'diagnostics' in payload:
            diagnostics = payload['diagnostics']
            quality = diagnostics.get('connectionQuality', diagnostics.get('quality'))

            # If client reports poor quality, send optimization suggestions
            if quality in ['poor', 'fair']:
                recommendations = self._get_quality_recommendations(quality, diagnostics)

                await self.connection.send_message({
                    't': 'connection_quality',
                    'p': {
                        'quality': quality,
                        'message': 'Connection quality could be improved',
                        'suggestions': recommendations['suggestions'],
                        'recommended_settings': recommendations['settings'],
                        'diagnostics': diagnostics
                    }
                }, priority=MessagePriority.HIGH.value)

    def _get_quality_recommendations(self, quality: str, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quality improvement recommendations"""
        suggestions = []
        settings = {
            'compression': True,
            'batch_size': 20,
            'batch_timeout': 200
        }

        jitter = diagnostics.get('jitter', 0)
        packet_loss = diagnostics.get('packetLoss', 0)
        latency = diagnostics.get('avgLatency', 0)

        if jitter > 50:
            suggestions.append("High jitter detected. Consider using a wired connection.")
            settings['batch_size'] = 30
            settings['batch_timeout'] = 300

        if packet_loss > 1:
            suggestions.append("Packet loss detected. Check network congestion.")
            settings['compression'] = True

        if latency > 200:
            suggestions.append("High latency detected. Consider connecting to a closer server.")
            settings['batch_size'] = 50

        if not suggestions:
            suggestions.append("Consider closing bandwidth-intensive applications.")

        return {
            'suggestions': suggestions,
            'settings': settings
        }

    async def handle_metrics_request(self, message_data: Dict[str, Any]) -> None:
        """Handle metrics request with comprehensive stats"""
        # Get event bus stats
        event_bus_stats = await self.connection.event_bus.get_stats()

        # Get sequence stats
        sequence_stats = await self.connection.event_sequencer.get_buffer_stats()

        await self.connection.send_message({
            't': 'metrics_response',
            'p': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'connection_id': self.connection.conn_id,
                'connection_stats': self.connection.metrics.to_dict(),
                'subscriptions': {
                    'active': list(self.connection.subscriptions),
                    'pending': list(self.connection.pending_subscriptions),
                    'failed': list(self.connection.failed_subscriptions),
                    'count': len(self.connection.subscriptions)
                },
                'event_bus_stats': event_bus_stats,
                'queue_stats': self.connection.message_queue.get_stats(),
                'circuit_breaker': self.connection.circuit_breaker.get_metrics(),
                'diagnostics': self.connection.network_analyzer.analyze(),
                'sequence_stats': sequence_stats,
                'compression_stats': self.connection.compression_manager.get_stats(),
                'security': self.connection.security_manager.get_security_info(),
                'uptime': (datetime.now(
                    timezone.utc) - self.connection.metrics.connected_since).total_seconds() if self.connection.metrics.connected_since else 0
            }
        })

    async def handle_metrics_response(self, message_data: Dict[str, Any]) -> None:
        """Handle metrics response from client"""
        payload = message_data.get('p', {})

        # Log interesting client metrics
        if 'queue_stats' in payload:
            queue_stats = payload['queue_stats']
            if queue_stats.get('backpressure'):
                log.warning(f"Client {self.connection.conn_id} experiencing backpressure")

        if 'offline_queue' in payload:
            offline = payload['offline_queue']
            if offline.get('size', 0) > 0:
                log.info(f"Client {self.connection.conn_id} has {offline['size']} offline messages")

    async def handle_config_request(self, message_data: Dict[str, Any]) -> None:
        """Handle configuration request"""
        await self.connection.send_message({
            't': 'config_response',
            'p': {
                'compression_enabled': self.connection.compression_enabled,
                'compression_threshold': self.connection.compression_threshold,
                'encryption_enabled': self.connection.encryption_enabled,
                'batch_size': self.connection.batch_size,
                'batch_timeout': self.connection.batch_timeout,
                'max_queue_size': self.connection.message_queue.max_size,
                'protocol_version': self.connection.protocol_version,
                'heartbeat_interval': 15000,  # ms
                'idle_timeout': 40000,  # ms
                'rate_limits': {
                    'capacity': self.connection.rate_limiter.capacity,
                    'refill_rate': self.connection.rate_limiter.refill_rate,
                    'refill_interval': self.connection.rate_limiter.refill_interval
                }
            }
        }, priority=MessagePriority.HIGH.value)

    async def handle_config_update(self, message_data: Dict[str, Any]) -> None:
        """Handle configuration update request with validation"""
        payload = message_data.get('p', {})
        updated_settings = {}

        # Update compression
        if 'compression_enabled' in payload:
            self.connection.compression_enabled = payload['compression_enabled']
            updated_settings['compression_enabled'] = self.connection.compression_enabled

        if 'compression_threshold' in payload:
            threshold = payload['compression_threshold']
            if 512 <= threshold <= 10240:  # Reasonable limits
                self.connection.compression_threshold = threshold
                updated_settings['compression_threshold'] = threshold

        # Update batching
        if 'batching_enabled' in payload:
            if payload['batching_enabled']:
                self.connection.batch_size = payload.get('batch_size', 10)
                self.connection.batch_timeout = payload.get('batch_timeout', 0.1)
            else:
                self.connection.batch_size = 1
            updated_settings['batch_size'] = self.connection.batch_size
            updated_settings['batch_timeout'] = self.connection.batch_timeout

        # Update queue size
        if 'max_queue_size' in payload:
            max_size = payload['max_queue_size']
            if 100 <= max_size <= 100000:  # Reasonable limits
                self.connection.message_queue.max_size = max_size
                updated_settings['max_queue_size'] = max_size

        log.info(f"Configuration updated for {self.connection.conn_id}: {updated_settings}")

        # Send confirmation
        await self.connection.send_message({
            't': 'config_update_response',
            'p': {
                'success': True,
                'updated_settings': updated_settings,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }, priority=MessagePriority.HIGH.value)

    async def handle_priority_message(self, message_data: Dict[str, Any]) -> None:
        """Handle priority message from client"""
        payload = message_data.get('p', {})
        priority = message_data.get('pri', message_data.get('priority', MessagePriority.NORMAL.value))

        # Validate priority
        valid_priorities = [1, 3, 5, 8, 10]
        if priority not in valid_priorities:
            priority = min(valid_priorities, key=lambda x: abs(x - priority))

        # Forward to event bus with priority
        await self.connection.event_bus.publish(
            f"priority:{self.connection.user_id}:messages",
            {
                'content': payload.get('content', payload),
                'priority': priority,
                'ttl': payload.get('ttl'),
                'user_id': self.connection.user_id,
                'conn_id': self.connection.conn_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'correlation_id': message_data.get('cid')
            },
            priority=EventPriority(priority)
        )

    async def handle_debug_request(self, message_data: Dict[str, Any]) -> None:
        """Handle debug information request with comprehensive details"""
        debug_info = {
            'connection_id': self.connection.conn_id,
            'user_id': self.connection.user_id,
            'registered_handlers': list(self.handlers.keys()),
            'subscriptions': {
                'active': list(self.connection.subscriptions),
                'pending': list(self.connection.pending_subscriptions),
                'failed': list(self.connection.failed_subscriptions),
                'subscription_ids': list(self.connection.subscription_ids.keys())
            },
            'connection_state': getattr(self.connection, 'connection_state',
                                        ConnectionState.CONNECTED).value if hasattr(self.connection,
                                                                                    'connection_state') else 'connected',
            'metrics': self.connection.metrics.to_dict(),
            'circuit_breaker': self.connection.circuit_breaker.get_metrics(),
            'compression': {
                'enabled': self.connection.compression_enabled,
                'threshold': self.connection.compression_threshold,
                'stats': self.connection.compression_manager.get_stats()
            },
            'encryption': {
                'enabled': self.connection.encryption_enabled,
                'info': self.connection.security_manager.get_security_info()
            },
            'sequence': {
                'current': self.connection.sequence_number,
                'seen_messages': len(self.connection.seen_message_ids)
            },
            'protocol_version': self.connection.protocol_version,
            'client_version': self.connection.client_version,
            'client_features': self.connection.client_features,
            'queue_stats': self.connection.message_queue.get_stats(),
            'rate_limiter': {
                'tokens': self.connection.rate_limiter.tokens,
                'capacity': self.connection.rate_limiter.capacity,
                'retry_after': self.connection.rate_limiter.get_retry_after()
            }
        }

        await self.connection.send_message({
            't': 'debug_response',
            'p': debug_info
        }, priority=MessagePriority.HIGH.value)

    async def handle_sequence_stats_request(self, message_data: Dict[str, Any]) -> None:
        """Handle sequence statistics request"""
        stats = await self.connection.event_sequencer.get_buffer_stats()

        await self.connection.send_message({
            't': 'sequence_stats_response',
            'p': stats
        }, priority=MessagePriority.HIGH.value)

    async def handle_encryption_request(self, message_data: Dict[str, Any]) -> None:
        """Handle encryption setup request"""
        payload = message_data.get('p', {})
        action = payload.get('action', 'status')

        if action == 'enable':
            if not self.connection.encryption_enabled:
                await self.connection.security_manager.initialize({
                    'encryption_enabled': True,
                    'message_signing_enabled': payload.get('signing', False)
                })
                self.connection.encryption_enabled = True

            # Exchange keys if needed
            public_key = payload.get('public_key')
            if public_key:
                await self.connection.security_manager.set_server_public_key(public_key)

            # Get server public key
            server_key = await self.connection.security_manager.get_public_key()

            await self.connection.send_message({
                't': 'encryption_response',
                'p': {
                    'enabled': True,
                    'public_key': server_key,
                    'algorithms': {
                        'encryption': 'AES-GCM-256',
                        'signing': 'HMAC-SHA256',
                        'key_exchange': 'ECDH-P256'
                    }
                }
            }, priority=MessagePriority.HIGH.value)

        elif action == 'disable':
            self.connection.encryption_enabled = False
            await self.connection.send_message({
                't': 'encryption_response',
                'p': {'enabled': False}
            }, priority=MessagePriority.HIGH.value)

        else:  # status
            info = self.connection.security_manager.get_security_info()
            await self.connection.send_message({
                't': 'encryption_response',
                'p': info
            }, priority=MessagePriority.HIGH.value)

    async def handle_key_rotation_request(self, message_data: Dict[str, Any]) -> None:
        """Handle key rotation request"""
        if self.connection.encryption_enabled:
            await self.connection.security_manager.rotate_keys()

            # Get a new public key if using key exchange
            new_key = await self.connection.security_manager.get_public_key()

            await self.connection.send_message({
                't': 'key_rotation_response',
                'p': {
                    'success': True,
                    'new_public_key': new_key,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }, priority=MessagePriority.HIGH.value)
        else:
            await self._send_error("Encryption not enabled", "ENCRYPTION_REQUIRED")

    async def handle_system_status_request(self, message_data: Dict[str, Any]) -> None:
        """Handle system status request"""
        # Check if we have access to system status through services
        system_status = {
            'api': 'healthy',
            'api_status': 'operational',
            'datafeed_status': 'operational',
            'redis': 'healthy',
            'event_bus': 'healthy',
            'cpu_usage': 15.2,  # These would come from actual monitoring
            'memory_usage': 45.8,
            'active_connections': 1,
            'event_queue_size': 0,
            'adapter_statuses': {},
            'module_statuses': {},
            'circuit_breakers': {},
            'uptime': 3600,
        }

        await self.connection.send_message({
            't': 'system_status',
            'p': system_status
        }, priority=MessagePriority.HIGH.value)

    # Helper methods
    def _normalize_topic(self, topic: str) -> str:
        """Normalize topic name for event bus"""
        # Map WebSocket topics to event bus topics (domain-based separation)
        topic_map = {
            # DOMAIN EVENTS (lifecycle - what happened)
            'broker_connection_events': f"user:{self.connection.user_id}:broker_connection_events",
            'broker_account_events': f"user:{self.connection.user_id}:broker_account_events",
            'user_account_events': f"user:{self.connection.user_id}:events",
            'automation_events': f"user:{self.connection.user_id}:automation_events",
            'order_events': f"user:{self.connection.user_id}:order_events",  # Order domain
            'position_events': f"user:{self.connection.user_id}:position_events",  # Position domain
            'portfolio_events': f"user:{self.connection.user_id}:portfolio_events",  # Portfolio domain

            # MONITORING STATE (runtime - current state) - UPDATED Nov 13, 2025
            'broker_health': f"user:{self.connection.user_id}:broker_health",  # NEW: REST API health
            'broker_streaming': f"user:{self.connection.user_id}:broker_streaming",  # RENAMED: WebSocket health

            # REAL-TIME DATA (market data streams)
            'market_data': f"user:{self.connection.user_id}:market_data",

            # SYSTEM EVENTS
            'system_events': "system:announcements",
            'monitoring_events': f"user:{self.connection.user_id}:monitoring",
        }

        normalized = topic_map.get(topic, topic)
        log.info(f"Normalized topic '{topic}' to '{normalized}' for user {self.connection.user_id}")

        return normalized

    def _create_event_handler(self):
        """Create an event handler that sends to WebSocket"""

        # Track last sent events to prevent duplicates
        last_sent_events = {}  # broker_connection_id -> (event_id, timestamp, health_status, response_time)

        # Track events by message ID to prevent duplicates from different buses
        processed_event_ids = set()  # Track event IDs we've already processed

        async def handler(event: Dict[str, Any]) -> None:
            """Handle events from the reactive bus and send to WebSocket"""
            try:
                # Extract event details
                event_type = event.get('event_type', event.get('type', 'unknown'))
                event_id = event.get('event_id', event.get('_metadata', {}).get('event_id'))

                log.info(f"[HANDLER_START] Processing event: {event_type}, id: {event_id}")

                # CRITICAL FIX (Nov 17, 2025): Send account snapshot ONLY on SagaCompleted
                # ROOT CAUSE: BrokerAccountLinked arrives via Redis Pub/Sub (fast ~10ms) BEFORE PostgreSQL projection commits
                # SOLUTION: Saga already waits for projection commit, so SagaCompleted guarantees data is in DB
                # REMOVED: Early snapshot trigger on BrokerAccountLinked (race condition with projection)
                original_event_type = event.get('original_event_type', event_type)

                # Track sent snapshots to avoid duplicates (one snapshot per broker connection)
                if not hasattr(self, '_snapshot_sent_for_connection'):
                    self._snapshot_sent_for_connection = set()

                # Log BrokerAccountLinked but don't send snapshot yet (wait for SagaCompleted)
                if original_event_type == "BrokerAccountLinked":
                    broker_connection_id = event.get('broker_connection_id')
                    log.debug(f"[ACCOUNT_LINKED] BrokerAccountLinked received for connection {broker_connection_id}, snapshot will be sent on SagaCompleted")

                # REMOVED (Nov 17, 2025): Snapshot trigger on SagaCompleted moved to WSESnapshotPublisher
                # REASON: WSEHandler receives via Redis Pub/Sub (ephemeral, unreliable)
                # SnapshotPublisher receives via Redpanda (durable, guaranteed delivery)
                # Having TWO sources causes race conditions and conflicting snapshots
                # CLEAN ARCHITECTURE: SnapshotPublisher handles ALL saga completion snapshots

                broker_connection_id = (
                        event.get('broker_connection_id') or
                        event.get('payload', {}).get('broker_connection_id') or
                        event.get('p', {}).get('broker_connection_id')
                )

                # CRITICAL: Check if we've already processed this event ID
                if event_id and event_id in processed_event_ids:
                    log.debug(f"Skipping already processed event {event_id}")
                    return

                # Add to processed set (with size limit)
                if event_id:
                    processed_event_ids.add(event_id)
                    # Prevent unbounded growth
                    if len(processed_event_ids) > 10000:
                        # Remove oldest entries (convert to list, slice, convert back)
                        processed_event_ids.clear()
                        processed_event_ids.update(list(processed_event_ids)[-5000:])

                # FIXED: Enhanced deduplication for broker connection events
                if event_type in ['BrokerConnectionHealthChecked',
                                  'BrokerConnectionHealthUpdated'] and broker_connection_id:
                    current_time = datetime.now(timezone.utc)

                    # Check if we've sent a similar event recently
                    if broker_connection_id in last_sent_events:
                        last_event_id, last_timestamp, last_health, last_response_time = last_sent_events[
                            broker_connection_id]

                        if isinstance(last_timestamp, datetime):
                            time_diff = (current_time - last_timestamp).total_seconds()

                            # Get current event details
                            is_healthy = event.get('is_healthy', event.get('connected', True))
                            response_time = event.get('response_time_ms')

                            # Skip if:
                            # 1. Same health status within 1 second
                            # 2. Second event with null response_time following one with a value
                            if time_diff < 1:
                                if is_healthy == last_health:
                                    if last_response_time is not None and response_time is None:
                                        log.debug(
                                            f"Skipping duplicate broker event (null response_time) for {broker_connection_id}")
                                        return
                                    elif last_response_time == response_time:
                                        log.debug(
                                            f"Skipping duplicate broker event (same response_time) for {broker_connection_id}")
                                        return

                    # Update tracking
                    is_healthy = event.get('is_healthy', event.get('connected', True))
                    response_time = event.get('response_time_ms')
                    last_sent_events[broker_connection_id] = (event_id, current_time, is_healthy, response_time)

                    # Clean old entries
                    keys_to_remove = []
                    for key, (_, timestamp, _, _) in list(last_sent_events.items()):
                        if isinstance(timestamp, datetime) and (current_time - timestamp).total_seconds() > 60:
                            keys_to_remove.append(key)
                    for key in keys_to_remove:
                        del last_sent_events[key]

                # CRITICAL FIX: Filter out disconnected/unhealthy broker events
                if event_type in ['BrokerConnectionHealthChecked', 'BrokerConnectionHealthUpdated',
                                  'BrokerDisconnected']:
                    # Check if this is a disconnected event
                    is_healthy = event.get('is_healthy', event.get('connected', True))
                    status = event.get('status', event.get('new_status', ''))

                    # Convert status to string if it's an enum
                    if hasattr(status, 'value'):
                        status = status.value
                    status = str(status).upper()

                    # Only filter DISCONNECTED status, allow unhealthy to pass through
                    if status in ['DISCONNECTED']:
                        log.debug(f"Filtering out disconnected broker event: {event_type}, status: {status}")
                        return

                    # Log unhealthy events but don't filter them
                    if not is_healthy:
                        log.info(f"Forwarding unhealthy broker event: {event_type}, status: {status}")

                # Check if this is already a transformed WebSocket event
                if all(key in event for key in ['v', 't', 'p', 'id', 'ts']):
                    # FIXED (2025-11-15): Removed disconnect filter - disconnect is a valid incremental update!
                    # Previous filter was blocking broker_connection_update events with connected=False
                    # This prevented frontend from receiving disconnect notifications
                    ws_type = event.get('t')

                    # This is already in WebSocket format, send as-is
                    log.info(f"Event already in WebSocket format, type: {ws_type}")
                    log.info(f"[HANDLER_SENDING] About to send to WebSocket: {ws_type}")
                    await self.connection.send_message(event)
                    log.info(f"[HANDLER_SENT] Successfully sent: {ws_type}")
                else:
                    # This is a raw event that needs transformation
                    from app.wse.core.event_transformer import EventTransformer
                    seq = self.connection.get_next_sequence()
                    transformed = EventTransformer.transform_for_ws(event, seq)

                    # FIXED (2025-11-15): Removed disconnect filter for incremental updates
                    # Disconnect events are valid incremental updates that frontend needs to receive
                    # Note: Snapshots still filter disconnected brokers in snapshot_service.py

                    log.info(f"Transformed event {event_type} to WebSocket type {transformed.get('t')}")
                    log.info(f"[HANDLER_SENDING] About to send to WebSocket: {transformed.get('t')}")
                    await self.connection.send_message(transformed)
                    log.info(f"[HANDLER_SENT] Successfully sent: {transformed.get('t')}")

                log.info(
                    f"[HANDLER_COMPLETE] Sent event type {event.get('t', event.get('event_type'))} to WebSocket {self.connection.conn_id}"
                )

            except Exception as e:
                log.error(f"Error handling event for {self.connection.conn_id}: {e}", exc_info=True)

        return handler

    async def _send_broker_snapshot(self, user_id: UUID, include_module_details: bool = False) -> None:
        """Send a broker connection snapshot using the snapshot service"""
        try:
            log.info("=== FETCHING BROKER CONNECTIONS via Snapshot Service ===")
            log.info(f"User ID: {user_id}, Include modules: {include_module_details}")

            # UPDATED: Snapshot service now filters disconnected brokers by default
            connection_infos = await self.snapshot_service.get_broker_connections_snapshot(
                user_id=user_id,
                include_archived=False,  # Never include disconnected brokers for WebSocket
                include_module_details=include_module_details
            )

            # Build the snapshot message
            snapshot_message = {
                't': 'broker_connection_snapshot',
                'p': {
                    'connections': connection_infos,
                    'trim_archived': True,
                    'include_module_details': include_module_details,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'count': len(connection_infos),
                    'only_connected': True  # Signal to frontend that this only includes connected brokers
                }
            }

            # Log what we're sending
            log.info("=== SENDING BROKER SNAPSHOT ===")
            log.info(f"Connections count: {len(connection_infos)}")
            log.info(f"Message size: {len(json.dumps(snapshot_message))} bytes")

            # Send the message
            await self.connection.send_message(snapshot_message)

            log.info(f"✓ Broker snapshot sent successfully with {len(connection_infos)} connections")

        except Exception as e:
            log.error(f"Error sending broker snapshot: {e}", exc_info=True)
            await self._send_error(
                "Failed to fetch broker connections",
                "SNAPSHOT_ERROR",
                details=str(e),
                recoverable=True
            )

    async def _send_account_snapshot(self, user_id: UUID, include_positions: bool = False) -> None:
        """Send account snapshot using the snapshot service"""
        try:
            log.info("=== FETCHING ACCOUNTS via Snapshot Service ===")
            log.info(f"User ID: {user_id}, Include positions: {include_positions}")

            # UPDATED: Snapshot service now filters accounts from disconnected brokers
            account_infos = await self.snapshot_service.get_accounts_snapshot(
                user_id=user_id,
                include_positions=include_positions,
                include_deleted=False  # Don't include accounts from disconnected brokers
            )

            # Build the snapshot message
            snapshot_message = {
                't': 'broker_account_snapshot',
                'p': {
                    'accounts': account_infos,
                    'include_positions': include_positions,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'count': len(account_infos),
                    'from_connected_brokers_only': True  # Signal that these are only from connected brokers
                }
            }

            # Log what we're sending
            log.info("=== SENDING ACCOUNT SNAPSHOT ===")
            log.info(f"Accounts count: {len(account_infos)}")
            log.info(f"Message size: {len(json.dumps(snapshot_message))} bytes")

            # CRITICAL DEBUG: Log actual account IDs being sent
            account_ids = [acc.get('accountId', acc.get('brokerAccountId', 'unknown')) for acc in account_infos]
            log.info(f"Account IDs in snapshot: {account_ids}")
            log.info(f"Full snapshot message type: {snapshot_message.get('t')}")
            log.info(f"Snapshot payload keys: {list(snapshot_message.get('p', {}).keys())}")
            log.info(f"Accounts array length in payload: {len(snapshot_message.get('p', {}).get('accounts', []))}")

            # Send the message
            await self.connection.send_message(snapshot_message)

            log.info(f"✓ Account snapshot sent successfully with {len(account_infos)} accounts")

        except Exception as e:
            log.error(f"Error sending account snapshot: {e}", exc_info=True)
            await self._send_error(
                "Failed to fetch accounts",
                "SNAPSHOT_ERROR",
                details=str(e),
                recoverable=True
            )

    async def _send_automation_snapshot(self, user_id: UUID) -> None:
        """Send an automation snapshot if snapshot service supports it"""
        try:
            # Check if snapshot service has automation support
            if hasattr(self.snapshot_service, 'get_automations_snapshot'):
                automations = await self.snapshot_service.get_automations_snapshot(user_id)

                await self.connection.send_message({
                    't': 'automation_snapshot',
                    'p': {
                        'automations': automations,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'count': len(automations)
                    }
                })

                log.info(f"✓ Automation snapshot sent with {len(automations)} automations")
            else:
                log.info("Automation snapshot not supported by snapshot service")

        except Exception as e:
            log.error(f"Error sending automation snapshot: {e}", exc_info=True)

    async def _send_order_snapshot(self, user_id: UUID, active_only: bool = True) -> None:
        """Send active orders snapshot using the snapshot service"""
        try:
            log.info("=== FETCHING ORDERS via Snapshot Service ===")
            log.info(f"User ID: {user_id}, Active only: {active_only}")

            # Get orders from snapshot service
            order_infos = await self.snapshot_service.get_orders_snapshot(
                user_id=user_id,
                active_only=active_only
            )

            # Build the snapshot message
            snapshot_message = {
                't': 'order_snapshot',
                'p': {
                    'orders': order_infos,
                    'active_only': active_only,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'count': len(order_infos)
                }
            }

            # Log what we're sending
            log.info("=== SENDING ORDER SNAPSHOT ===")
            log.info(f"Orders count: {len(order_infos)}")
            log.info(f"Message size: {len(json.dumps(snapshot_message))} bytes")

            # Send the message
            await self.connection.send_message(snapshot_message)

            log.info(f"✓ Order snapshot sent successfully with {len(order_infos)} orders")

        except Exception as e:
            log.error(f"Error sending order snapshot: {e}", exc_info=True)
            await self._send_error(
                "Failed to fetch orders",
                "SNAPSHOT_ERROR",
                details=str(e),
                recoverable=True
            )

    async def _send_position_snapshot(self, user_id: UUID, open_only: bool = True) -> None:
        """Send positions snapshot using the snapshot service"""
        try:
            log.info("=== FETCHING POSITIONS via Snapshot Service ===")
            log.info(f"User ID: {user_id}, Open only: {open_only}")

            # Get positions from snapshot service
            position_infos = await self.snapshot_service.get_positions_snapshot(
                user_id=user_id,
                open_only=open_only
            )

            # Build the snapshot message
            snapshot_message = {
                't': 'position_snapshot',
                'p': {
                    'positions': position_infos,
                    'open_only': open_only,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'count': len(position_infos)
                }
            }

            # Log what we're sending
            log.info("=== SENDING POSITION SNAPSHOT ===")
            log.info(f"Positions count: {len(position_infos)}")
            log.info(f"Message size: {len(json.dumps(snapshot_message))} bytes")

            # Send the message
            await self.connection.send_message(snapshot_message)

            log.info(f"✓ Position snapshot sent successfully with {len(position_infos)} positions")

        except Exception as e:
            log.error(f"Error sending position snapshot: {e}", exc_info=True)
            await self._send_error(
                "Failed to fetch positions",
                "SNAPSHOT_ERROR",
                details=str(e),
                recoverable=True
            )

    async def _send_streaming_status_snapshot(self, user_id: UUID) -> None:
        """Send streaming status snapshot using the snapshot service"""
        try:
            log.debug("=== STREAMING STATUS SNAPSHOT METHOD CALLED ===")
            log.debug(f"User ID: {user_id}")
            log.debug(f"Snapshot service type: {type(self.snapshot_service)}")

            # Get streaming status from snapshot service
            streaming_status = await self.snapshot_service.get_streaming_status_snapshot(
                user_id=user_id
            )

            log.debug(f"=== SNAPSHOT SERVICE RETURNED ===")
            log.debug(f"Result type: {type(streaming_status)}")
            log.debug(f"Result length: {len(streaming_status)}")
            if streaming_status:
                log.debug(f"First item: {streaming_status[0]}")

            # Build the snapshot message
            snapshot_message = {
                't': 'broker_streaming_snapshot',
                'p': {
                    'streaming_status': streaming_status,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'count': len(streaming_status)
                }
            }

            # Log what we're sending
            log.debug("=== SENDING BROKER STREAMING SNAPSHOT TO CLIENT ===")
            log.debug(f"Broker streaming count: {len(streaming_status)}")
            log.debug(f"Message type: broker_streaming_snapshot")
            log.debug(f"Message size estimate: {len(str(snapshot_message))} bytes")

            # Send the message
            await self.connection.send_message(snapshot_message)

            log.info(f"Broker streaming snapshot sent successfully with {len(streaming_status)} statuses")

        except Exception as e:
            log.error(f"Error sending streaming status snapshot: {e}", exc_info=True)
            await self._send_error(
                "Failed to fetch streaming status",
                "SNAPSHOT_ERROR",
                details=str(e),
                recoverable=True
            )

    async def _send_error(self, message: str, code: str, details: Optional[str] = None,
                          recoverable: bool = True) -> None:
        """Send an error message to client with standard format"""
        error_message = {
            't': 'error',
            'p': {
                'message': message,
                'code': code,
                'details': details,
                'recoverable': recoverable,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'connection_id': self.connection.conn_id,
                'severity': 'error' if not recoverable else 'warning'
            }
        }

        # Log the error
        log.error(f"Sending error to client: {code} - {message}")

        await self.connection.send_message(error_message, priority=MessagePriority.HIGH.value)

    async def handle_broker_action(self, message_data: Dict[str, Any]) -> None:
        """
        Handle broker_action messages from upstream broker WebSocket (e.g., Alpaca).
        These are informational messages about broker actions like halt/resume trading.
        """
        payload = message_data.get('p', message_data)

        # Log the broker action for monitoring
        log.info(f"Broker action received: {payload}")

        # Publish to event bus for any subscribers who want to handle broker actions
        await self.connection.event_bus.publish(
            f"broker_actions:{self.connection.user_id}",
            {
                'type': 'broker_action',
                'action': payload.get('action', 'unknown'),
                'message': payload.get('message'),
                'symbol': payload.get('symbol'),
                'reason': payload.get('reason'),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': self.connection.user_id,
                'raw_data': payload
            },
            priority=EventPriority.NORMAL
        )

    async def _publish_client_message(self, msg_type: str, message_data: Dict[str, Any]) -> None:
        """Publish unknown message types to event bus for custom handling"""
        await self.connection.event_bus.publish(
            f"client:{self.connection.user_id}:messages",
            {
                'type': msg_type,
                'payload': message_data.get('p', {}),
                'user_id': self.connection.user_id,
                'conn_id': self.connection.conn_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'raw_message': message_data,
                'client_version': self.connection.client_version,
                'protocol_version': self.connection.protocol_version
            },
            priority=EventPriority(message_data.get('pri', message_data.get('priority', EventPriority.NORMAL.value)))
        )