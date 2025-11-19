# =============================================================================
# File: app/wse/websocket/wse_handlers.py
# Description: Message handlers for WebSocket protocol
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
from app.wse.core.types import EventPriority

log = logging.getLogger("wellwon.wse_handlers")


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

    def __init__(self, connection):
        """
        Initialize handler with WebSocket connection

        Args:
            connection: WebSocketConnection instance
        """
        self.connection = connection

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
                'message': 'Welcome to WellWon WebSocket Events'
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
                    normalized_topic = self._normalize_topic(topic)

                    log.info(f"=== SUBSCRIBING TO TOPIC ===")
                    log.info(f"Original topic: {topic}")
                    log.info(f"Normalized topic: {normalized_topic}")
                    log.info(f"User ID: {self.connection.user_id}")

                    subscription_id = await self.connection.event_bus.subscribe(
                        pattern=normalized_topic,
                        handler=self._create_event_handler()
                    )

                    self.connection.subscription_ids[topic] = subscription_id
                    self.connection.subscriptions.add(topic)
                    self.connection.pending_subscriptions.discard(topic)
                    self.connection.failed_subscriptions.discard(topic)
                    success_topics.append(topic)

                    log.info(f"Subscribed {self.connection.conn_id} to {topic} (normalized: {normalized_topic})")

                except Exception as e:
                    log.error(f"Failed to subscribe to {topic}: {e}", exc_info=True)
                    self.connection.failed_subscriptions.add(topic)
                    self.connection.pending_subscriptions.discard(topic)
                    failed_topics.append({'topic': topic, 'error': str(e)})

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

    async def handle_sync_request(self, message_data: Dict[str, Any]) -> None:
        """Handle sync request for initial data"""
        payload = message_data.get('p', {})
        topics = payload.get('topics', [])
        last_sequence = payload.get('last_sequence', 0)

        log.info("=== SYNC REQUEST RECEIVED ===")
        log.info(f"User: {self.connection.user_id}")
        log.info(f"Topics: {topics}")

        # Send a sync complete message
        await self.connection.send_message({
            't': 'snapshot_complete',
            'p': {
                'message': 'Initial sync complete',
                'success': True,
                'snapshots_sent': [],
                'details': {
                    'sequence': self.connection.sequence_number,
                    'topics': topics,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'last_sequence_processed': last_sequence,
                    'connection_id': self.connection.conn_id
                }
            }
        })

        # Mark initial sync as complete
        if hasattr(self.connection, 'mark_initial_sync_complete'):
            await self.connection.mark_initial_sync_complete()

        log.info(f"Sync request completed successfully")

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
        system_status = {
            'api': 'healthy',
            'api_status': 'operational',
            'redis': 'healthy',
            'event_bus': 'healthy',
            'cpu_usage': 15.2,
            'memory_usage': 45.8,
            'active_connections': 1,
            'event_queue_size': 0,
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
            # USER DOMAIN EVENTS
            'user_account_events': f"user:{self.connection.user_id}:events",

            # SYSTEM EVENTS
            'system_events': "system:announcements",
            'monitoring_events': f"user:{self.connection.user_id}:monitoring",
        }

        normalized = topic_map.get(topic, topic)
        log.info(f"Normalized topic '{topic}' to '{normalized}' for user {self.connection.user_id}")

        return normalized

    def _create_event_handler(self):
        """Create an event handler that sends to WebSocket"""

        # Track event IDs to prevent duplicates
        processed_event_ids = set()

        async def handler(event: Dict[str, Any]) -> None:
            """Handle events from the reactive bus and send to WebSocket"""
            try:
                # Extract event details
                event_type = event.get('event_type', event.get('type', 'unknown'))
                event_id = event.get('event_id', event.get('_metadata', {}).get('event_id'))

                log.info(f"[HANDLER_START] Processing event: {event_type}, id: {event_id}")

                # Check if we've already processed this event ID
                if event_id and event_id in processed_event_ids:
                    log.debug(f"Skipping already processed event {event_id}")
                    return

                # Add to processed set (with size limit)
                if event_id:
                    processed_event_ids.add(event_id)
                    # Prevent unbounded growth
                    if len(processed_event_ids) > 10000:
                        processed_event_ids.clear()
                        processed_event_ids.update(list(processed_event_ids)[-5000:])

                # Check if this is already a transformed WebSocket event
                if all(key in event for key in ['v', 't', 'p', 'id', 'ts']):
                    ws_type = event.get('t')
                    log.info(f"Event already in WebSocket format, type: {ws_type}")
                    log.info(f"[HANDLER_SENDING] About to send to WebSocket: {ws_type}")
                    await self.connection.send_message(event)
                    log.info(f"[HANDLER_SENT] Successfully sent: {ws_type}")
                else:
                    # This is a raw event that needs transformation
                    from app.wse.core.event_transformer import EventTransformer
                    seq = self.connection.get_next_sequence()
                    transformed = EventTransformer.transform_for_ws(event, seq)

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
