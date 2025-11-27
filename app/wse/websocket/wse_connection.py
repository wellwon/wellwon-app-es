# =============================================================================
# File: app/wse/websocket/wse_connection.py (SIMPLIFIED WITH DIRECT RELIABILITY USAGE)
# Description: WebSocket connection using reliability infrastructure directly
# =============================================================================

import asyncio
import json
import uuid
import time
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, Set, Union, List
from dataclasses import dataclass, field
from collections import deque
from decimal import Decimal
from enum import Enum

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.infra.reliability.circuit_breaker import CircuitBreaker
from app.infra.reliability.rate_limiter import RateLimiter
from app.config.reliability_config import CircuitBreakerConfig, RateLimiterConfig, ReliabilityConfigs
from app.wse.core.pubsub_bus import PubSubBus
from app.infra.metrics.wse_metrics import (
    ConnectionMetrics, NetworkQualityAnalyzer,
    ws_connections_active, ws_connections_total, ws_disconnections_total,
    ws_messages_sent_total, ws_messages_received_total,
    ws_message_send_latency_seconds, ws_bytes_sent_total, ws_bytes_received_total,
    ws_queue_size, ws_queue_dropped_total, ws_queue_backpressure
)
from app.wse.websocket.wse_compression import CompressionManager
from app.wse.websocket.wse_security import SecurityManager
from app.wse.websocket.wse_queue import PriorityMessageQueue
from app.wse.websocket.wse_event_sequencer import EventSequencer

log = logging.getLogger("wellwon.wse_connection")

# Check if Prometheus metrics are available
try:
    from prometheus_client import Counter
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    log.warning("prometheus_client not available - WSE metrics will not be exported")

# Constants matching frontend
HEARTBEAT_INTERVAL = 15  # seconds
IDLE_TIMEOUT = 40  # seconds
HEALTH_CHECK_INTERVAL = 30  # seconds
METRICS_INTERVAL = 60  # seconds
COMPRESSION_THRESHOLD = 1024  # bytes


class ConnectionState(Enum):
    """WebSocket connection states matching frontend"""
    PENDING = "pending"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEGRADED = "degraded"


class DateTimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles datetime objects and other types.

    CRITICAL FIX (Nov 11, 2025): Added circular reference protection.
    Problem: hasattr(obj, '__dict__') can return objects with circular refs
    Solution: Use check_circular=True and skip non-serializable objects
    """

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, '__dict__'):
            # CRITICAL FIX: Filter out circular references and non-serializable objects
            try:
                # Try to convert __dict__ to plain dict, filtering out complex objects
                obj_dict = {}
                for key, value in obj.__dict__.items():
                    # Skip private attributes and complex objects that might have circular refs
                    if key.startswith('_'):
                        continue
                    # Only serialize simple types
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        obj_dict[key] = value
                    elif isinstance(value, (datetime, date, Decimal, uuid.UUID, Enum)):
                        obj_dict[key] = self.default(value)
                return obj_dict
            except (TypeError, ValueError):
                # If serialization fails, return string representation
                return str(obj)
        return super().default(obj)


# Selective message signing (Industry standard: sign only critical operations)
# Based on Binance/Coinbase best practices - sign orders/trades, not market data/status
SIGNED_MESSAGE_TYPES = frozenset({
    # Critical trading operations (must be signed for integrity)
    'order_placed', 'order_filled', 'order_cancelled', 'order_update', 'order_rejected',
    'trade_executed', 'position_opened', 'position_closed', 'position_update',
    # Account operations
    'account_withdrawal', 'account_transfer', 'account_funding',
    # Automation operations
    'automation_enabled', 'automation_disabled', 'automation_config_change'
})


@dataclass
class WSEConnection:
    """Manages a single WebSocket connection with all features and frontend compatibility"""

    conn_id: str
    user_id: str
    ws: WebSocket
    event_bus: PubSubBus

    # Configuration
    protocol_version: int = 2
    compression_enabled: bool = True
    encryption_enabled: bool = False
    message_signing_enabled: bool = False  # Industry standard: connection-level auth only (Binance/Coinbase pattern)
    batch_size: int = 10
    batch_timeout: float = 0.1
    compression_threshold: int = COMPRESSION_THRESHOLD

    # Optional services
    broker_interaction_service: Optional[Any] = None
    adapter_monitoring_service: Optional[Any] = None

    # Connection state
    connection_state: ConnectionState = field(default=ConnectionState.PENDING)

    # Components (initialized in __post_init__)
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    circuit_breaker: CircuitBreaker = field(init=False)
    rate_limiter: RateLimiter = field(init=False)
    message_queue: PriorityMessageQueue = field(default_factory=lambda: PriorityMessageQueue(batch_size=10))
    compression_manager: CompressionManager = field(default_factory=CompressionManager)
    security_manager: SecurityManager = field(default_factory=SecurityManager)
    network_analyzer: NetworkQualityAnalyzer = field(default_factory=NetworkQualityAnalyzer)
    event_sequencer: EventSequencer = field(default_factory=EventSequencer)

    # State
    subscriptions: Set[str] = field(default_factory=set)
    subscription_ids: Dict[str, str] = field(default_factory=dict)
    pending_subscriptions: Set[str] = field(default_factory=set)
    failed_subscriptions: Set[str] = field(default_factory=set)

    # Client information
    client_features: Dict[str, bool] = field(default_factory=dict)
    client_version: str = "unknown"
    client_capabilities: List[str] = field(default_factory=list)

    # Sequencing
    sequence_number: int = 0
    # PERFORMANCE OPTIMIZATION: Reduced from 10,000 to 1,000 to save memory
    # 10 MB per connection → 2 MB per connection (5x improvement)
    # 1,000 messages = 10-100 seconds buffer at typical event rates
    seen_message_ids: deque = field(default_factory=lambda: deque(maxlen=1000))

    # Control
    _running: bool = True
    _tasks: Set[asyncio.Task] = field(default_factory=set)
    _last_activity: float = field(default_factory=time.time)
    _idle_timer: Optional[asyncio.Task] = None

    # Debug mode
    debug_mode: bool = field(default=False)
    event_count: Dict[str, int] = field(default_factory=dict)  # Track events by type

    # Add these fields for startup filtering
    initial_sync_complete: bool = field(default=False)
    startup_grace_period: float = field(default=10.0)  # seconds
    connection_start_time: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize components that need configuration"""
        # Create circuit breaker with WSE-specific config
        cb_config = CircuitBreakerConfig(
            name=f"wse_{self.conn_id}",
            failure_threshold=10,
            success_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=5,
            window_size=50,
            failure_rate_threshold=0.3
        )
        self.circuit_breaker = CircuitBreaker(cb_config)

        # Create rate limiter with WSE-specific config
        rl_config = RateLimiterConfig(
            algorithm="token_bucket",
            capacity=1000,
            refill_rate=100.0,
            distributed=False
        )
        self.rate_limiter = RateLimiter(
            name=f"wse_{self.conn_id}",
            config=rl_config
        )

    async def initialize(self) -> None:
        """Initialize the connection with state management"""
        await self.set_state(ConnectionState.CONNECTING)

        self.metrics.connected_since = datetime.now(timezone.utc)
        self.metrics.connection_attempts += 1
        self.metrics.successful_connections += 1

        # Prometheus metrics
        if METRICS_AVAILABLE:
            ws_connections_total.labels(user_id=self.user_id).inc()
            ws_connections_active.inc()

        # Initialize security if enabled
        # OPTIMIZATION (Nov 11, 2025): Enable message signing independently of encryption
        # Message signing provides integrity verification without performance overhead of encryption
        if self.encryption_enabled or self.message_signing_enabled:
            await self.security_manager.initialize({
                'encryption_enabled': self.encryption_enabled,
                'message_signing_enabled': self.message_signing_enabled
            })

        # Start background tasks
        self._start_background_tasks()

        # Reset idle timer
        self._reset_idle_timer()

        # Set connected state
        await self.set_state(ConnectionState.CONNECTED)

        # Enable debug mode in development
        if log.isEnabledFor(logging.DEBUG):
            self.debug_mode = True

        log.info(f"WebSocket connection {self.conn_id} initialized for user {self.user_id}")

    async def set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify client"""
        old_state = self.connection_state
        self.connection_state = state

        if old_state != state:
            log.info(f"Connection {self.conn_id} state changed: {old_state.value} -> {state.value}")

            # Skip sending state change notifications during initial connection sequence
            # to avoid flooding the client with messages before handlers are ready
            initial_states = [ConnectionState.PENDING, ConnectionState.CONNECTING]
            if old_state in initial_states and state == ConnectionState.CONNECTED:
                # This is the initial connection - don't send intermediate state changes
                log.debug("Skipping state change notification during initial connection")
                return

            # Send state change notification for other transitions
            await self.send_message({
                't': 'connection_state_change',
                'p': {
                    'old_state': old_state.value,
                    'new_state': state.value,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'connection_id': self.conn_id
                }
            }, priority=10)  # High priority

    async def mark_initial_sync_complete(self) -> None:
        """Mark that initial sync is complete to stop filtering old events"""
        self.initial_sync_complete = True
        log.info(f"Initial sync marked complete for connection {self.conn_id}")

    def _start_background_tasks(self) -> None:
        """Start all background tasks"""
        tasks = [
            self._sender_loop(),
            self._heartbeat_loop(),
            self._health_check_loop(),
            self._metrics_collection_loop(),
            self._sequence_cleanup_loop()
        ]

        # Add debug task if enabled
        if self.debug_mode:
            tasks.append(self._debug_stats_loop())

        for task_coro in tasks:
            task = asyncio.create_task(task_coro)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    def get_next_sequence(self) -> int:
        """Get the next sequence number"""
        self.sequence_number += 1
        return self.sequence_number

    def is_duplicate_message(self, message_id: str) -> bool:
        """Check if a message is duplicate"""
        if message_id in self.seen_message_ids:
            return True
        self.seen_message_ids.append(message_id)
        return False

    async def send_message(self, message: Dict[str, Any], priority: int = 5) -> bool:
        """Queue a message for sending with format normalization"""
        if not self._running:
            return False

        # Track when message enters WSE for processing time metrics
        message['_wse_received_at'] = time.time()

        # ENHANCED DEBUG LOGGING - Phase 6: Track message entry
        message_type = message.get('t') or message.get('type', 'unknown')
        message_id = message.get('id', 'unknown')
        log.debug(f"[WSE_QUEUE] Event: {message_type}, ID: {message_id}, Priority: {priority}")

        # Enhanced startup filtering
        if not self.initial_sync_complete:
            startup_grace_period = 30.0  # 30 seconds

            if time.time() - self.connection_start_time < startup_grace_period:
                event_type = message.get('t', '')

                # Never filter critical system messages
                never_filter = [
                    'broker_connection_snapshot',
                    'broker_account_snapshot',
                    'server_ready',
                    'subscription_update',
                    'error',
                    'connection_state_change',
                    'server_hello',
                    'health_check_response',
                    'heartbeat',
                    'PONG',
                    'snapshot_complete',
                ]

                if event_type not in never_filter:
                    # Check if this is a flood of old broker updates
                    if event_type in ['broker_connection_update', 'broker_status_update']:
                        # For broker updates during startup, only send if very recent
                        event_ts = message.get('ts', message.get('p', {}).get('timestamp'))
                        if event_ts:
                            try:
                                if isinstance(event_ts, str):
                                    event_dt = datetime.fromisoformat(event_ts.replace('Z', '+00:00'))
                                else:
                                    event_dt = event_ts

                                age = (datetime.now(timezone.utc) - event_dt).total_seconds()

                                # During startup, only send broker updates from last 10 seconds
                                if age > 10:
                                    log.debug(f"Filtering old {event_type} during startup: {age:.0f}s old")
                                    return True  # Pretend we sent it
                            except Exception:
                                pass
                else:
                    log.debug(f"Not filtering critical event: {event_type}")

        # Normalize message format for frontend compatibility
        if 'type' in message and 't' not in message:
            message['t'] = message.pop('type')

        if 'payload' in message and 'p' not in message:
            message['p'] = message.pop('payload')

        # Check rate limit
        if not await self.rate_limiter.acquire():
            self.metrics.messages_dropped += 1
            await self._send_rate_limit_warning()
            return False

        # Add message ID if not present
        if 'id' not in message:
            message['id'] = str(uuid.uuid4())

        # Add sequence number
        if 'seq' not in message:
            message['seq'] = self.get_next_sequence()

        # Add protocol version
        message.setdefault('v', self.protocol_version)

        # Add timestamp
        message.setdefault('ts', datetime.now(timezone.utc).isoformat())

        # Track event types in debug mode
        if self.debug_mode:
            event_type = message.get('t', 'unknown')
            self.event_count[event_type] = self.event_count.get(event_type, 0) + 1

        return await self.message_queue.enqueue(message, priority)

    async def handle_incoming(self, data: Union[str, bytes]) -> Optional[Dict[str, Any]]:
        """Handle incoming WebSocket message and return parsed data"""
        self._last_activity = time.time()
        self._reset_idle_timer()

        self.metrics.messages_received += 1
        self.metrics.last_message_received = datetime.now(timezone.utc)

        # Fixed: Don't increment packets for every message, only for actual network packets
        # This is handled by the ping/pong mechanism

        if isinstance(data, bytes):
            byte_count = len(data)
            self.metrics.bytes_received += byte_count
            self.network_analyzer.record_bytes(byte_count)

            # Prometheus metrics
            if METRICS_AVAILABLE:
                ws_messages_received_total.labels(message_type='binary').inc()
                ws_bytes_received_total.inc(byte_count)

            return await self._parse_binary_message(data)
        else:
            byte_count = len(data.encode('utf-8'))
            self.metrics.bytes_received += byte_count
            self.network_analyzer.record_bytes(byte_count)

            # Prometheus metrics
            if METRICS_AVAILABLE:
                ws_messages_received_total.labels(message_type='text').inc()
                ws_bytes_received_total.inc(byte_count)

            return self._parse_text_message(data)

    def _parse_text_message(self, data: str) -> Optional[Dict[str, Any]]:
        """Parse text message with special handling"""
        # Handle PING as special case
        if data.upper().startswith('PING'):
            # Record packet sent by client
            self.network_analyzer.record_packet_received()
            return {'type': 'ping', 'raw': data}

        # Handle PONG response
        if data.startswith('PONG:'):
            try:
                # Record packet received
                self.network_analyzer.record_packet_received()

                timestamp = int(data.split(':', 1)[1])
                latency = int(datetime.now().timestamp() * 1000) - timestamp
                self.metrics.record_latency(latency)
                self.network_analyzer.record_latency(latency)
                log.debug(f"PONG received, latency: {latency}ms")
            except:
                pass
            return None  # Don't process PONG as a regular message

        try:
            parsed = json.loads(data)
            # Normalize format
            if 'type' in parsed and 't' not in parsed:
                parsed['t'] = parsed.pop('type')
            if 'payload' in parsed and 'p' not in parsed:
                parsed['p'] = parsed.pop('payload')
            return parsed
        except json.JSONDecodeError:
            self.metrics.protocol_errors += 1
            log.warning(f"Invalid JSON received: {data[:100]}")
            return None

    async def _parse_binary_message(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse binary message with compression and encryption support"""
        try:
            # Log the first few bytes for debugging
            log.debug(f"Parsing binary message: {len(data)} bytes, first 10: {data[:10].hex()}")

            # Check for compression header 'C':
            if data.startswith(b'C:'):
                decompressed = self.compression_manager.decompress(data[2:])
                self.metrics.compression_hits += 1
                parsed = json.loads(decompressed.decode('utf-8'))
                log.debug(
                    f"Decompressed C: prefixed: {len(data)} -> {len(decompressed)} bytes, type: {parsed.get('t')}")
                return self._normalize_message_format(parsed)

            # Check for msgpack header 'M':
            elif data.startswith(b'M:'):
                parsed = self.compression_manager.unpack_msgpack(data[2:])
                return self._normalize_message_format(parsed)

            # Check for encryption header 'E':
            elif data.startswith(b'E:') and self.encryption_enabled:
                decrypted = await self.security_manager.decrypt_message(data[2:])
                if decrypted:
                    parsed = json.loads(decrypted) if isinstance(decrypted, str) else json.loads(
                        decrypted.decode('utf-8'))
                    return self._normalize_message_format(parsed)
                else:
                    self.metrics.protocol_errors += 1
                    return None

            # Try as raw JSON
            else:
                parsed = json.loads(data.decode('utf-8'))
                return self._normalize_message_format(parsed)

        except Exception as e:
            self.metrics.protocol_errors += 1
            log.error(f"Failed to parse binary message: {e}")
            return None

    def _normalize_message_format(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message format for consistency"""
        if 'type' in message and 't' not in message:
            message['t'] = message.pop('type')
        if 'payload' in message and 'p' not in message:
            message['p'] = message.pop('payload')
        return message

    async def _send_raw_message(self, message: Dict[str, Any]) -> None:
        """Send a message through the WebSocket with proper formatting"""
        send_start_time = time.time()  # Track send latency
        message_type = message.get('t', 'unknown')
        priority = message.get('priority', 5)

        try:
            # Check if connection is still running and WebSocket is connected
            if not self._running or self.ws.client_state != WebSocketState.CONNECTED:
                return

            # Calculate WSE processing time for observability
            wse_received_at = message.pop('_wse_received_at', None)
            if wse_received_at:
                wse_processing_ms = int((time.time() - wse_received_at) * 1000)
                message['wse_processing_ms'] = wse_processing_ms

                # Log high WSE processing times for monitoring
                if wse_processing_ms > 100:  # > 100ms
                    log.warning(f"High WSE processing time: {wse_processing_ms}ms for event type {message.get('t')}")
                elif wse_processing_ms > 50:  # > 50ms
                    log.info(f"Elevated WSE processing time: {wse_processing_ms}ms for event type {message.get('t')}")

            # Ensure message has all required fields
            message.setdefault('v', self.protocol_version)
            message.setdefault('ts', datetime.now(timezone.utc).isoformat())

            # Selective message signing (Industry standard: Binance/Coinbase pattern)
            # ONLY sign critical operations (orders, trades, positions) - NOT market data/status updates
            # CRITICAL FIX (Nov 11, 2025): sign_message() now returns string directly
            # Previously returned dict with 'signature' key, now returns JWT token string
            message_type = message.get('t', '')

            should_sign = (
                self.message_signing_enabled or  # Global override for all messages
                message_type in SIGNED_MESSAGE_TYPES  # Selective signing for critical ops
            )

            if should_sign:
                signature = await self.security_manager.sign_message(message)
                if signature:
                    message['sig'] = signature  # signature is already a string (JWT token)
                    log.debug(f"Signed message type: {message_type} (sig length: {len(signature)})")
                else:
                    log.warning(f"Failed to sign message type: {message_type}")

            # Serialize to JSON with message category prefix (Protocol v2)
            # Format: {category}{json} e.g., U{"t":"user_update",...}
            msg_cat = message.pop('_msg_cat', 'U')  # Extract and remove from message
            json_data = json.dumps(message, cls=DateTimeEncoder)
            data = f"{msg_cat}{json_data}"
            data_bytes = data.encode('utf-8')

            # ENHANCED DEBUG LOGGING - Phase 6: Pre-send info
            log.debug(
                f"[WSE_SENDING] Event: {message_type}, "
                f"Size: {len(data_bytes)}B, "
                f"Compress: {self.compression_enabled and len(data_bytes) > self.compression_threshold}"
            )

            # Check compression threshold correctly
            should_compress = (
                    self.compression_enabled and
                    len(data_bytes) > self.compression_threshold and
                    not message.get('encrypted', False)
            )

            # Encrypt if enabled (takes precedence)
            if self.encryption_enabled and message.get('encrypted', False):
                encrypted = await self.security_manager.encrypt_message(data)
                if encrypted:
                    byte_count = len(encrypted) + 2
                    await self.ws.send_bytes(b'E:' + encrypted)
                    self.metrics.bytes_sent += byte_count

                    # Prometheus metrics
                    if METRICS_AVAILABLE:
                        ws_bytes_sent_total.inc(byte_count)

                    log.debug(f"Sent encrypted message: {len(data_bytes)} -> {byte_count} bytes")
                else:
                    # Fallback to plain text
                    await self.ws.send_text(data)
                    self.metrics.bytes_sent += len(data_bytes)

                    # Prometheus metrics
                    if METRICS_AVAILABLE:
                        ws_bytes_sent_total.inc(len(data_bytes))

                    log.warning("Encryption failed, sent as plain text")

            # Use compression if beneficial
            elif should_compress:
                compressed = self.compression_manager.compress(data_bytes)

                # Always send with C: prefix regardless of compression ratio
                byte_count = len(compressed) + 2
                await self.ws.send_bytes(b'C:' + compressed)
                self.metrics.compression_hits += 1
                self.metrics.bytes_sent += byte_count

                # Prometheus metrics
                if METRICS_AVAILABLE:
                    ws_bytes_sent_total.inc(byte_count)

                compression_ratio = len(compressed) / len(data_bytes)
                self.metrics.compression_ratio = compression_ratio

                log.debug(
                    f"Sent compressed message with C: prefix - "
                    f"Type: {message.get('t')}, "
                    f"Original: {len(data_bytes)} bytes, "
                    f"Compressed: {len(compressed)} bytes, "
                    f"Ratio: {compression_ratio:.2f}"
                )
            else:
                # No compression needed
                await self.ws.send_text(data)
                self.metrics.bytes_sent += len(data_bytes)

                # Prometheus metrics
                if METRICS_AVAILABLE:
                    ws_bytes_sent_total.inc(len(data_bytes))

                log.debug(f"Sent plain text message: {len(data_bytes)} bytes")

            self.metrics.messages_sent += 1
            self.metrics.last_message_sent = datetime.now(timezone.utc)

            # Calculate total send latency
            total_send_latency_ms = (time.time() - send_start_time) * 1000

            # ENHANCED DEBUG LOGGING - Phase 6: Send success with timing
            log.debug(
                f"[WSE_SENT] Event: {message_type}, "
                f"Bytes: {self.metrics.bytes_sent}, "
                f"Latency: {total_send_latency_ms:.2f}ms, "
                f"Total: {self.metrics.messages_sent}"
            )

            # Don't count every message as a packet
            # Packets are counted by ping/pong mechanism

            # Prometheus metrics
            if METRICS_AVAILABLE:
                # Track message send
                priority_str = str(priority) if isinstance(priority, int) else 'unknown'
                ws_messages_sent_total.labels(message_type=message_type, priority=priority_str).inc()

                # Track send latency
                send_latency = time.time() - send_start_time
                ws_message_send_latency_seconds.labels(priority=priority_str).observe(send_latency)

                # Track bytes sent (already tracked in self.metrics.bytes_sent above)
                # ws_bytes_sent_total is already incremented in the send logic above

            self.circuit_breaker.record_success()

        except Exception as e:
            log.error(f"Send error: {e}")
            self.circuit_breaker.record_failure()
            self.metrics.last_error_message = str(e)
            await self.set_state(ConnectionState.ERROR)
            raise

    async def _sender_loop(self) -> None:
        """Send queued messages with batch support"""
        while self._running:
            try:
                # Get batch of messages
                batch = await self.message_queue.dequeue_batch()

                if batch:
                    # Send individually or as batch based on client capability
                    if self.client_features.get('batch_messages', False) and len(batch) > 1:
                        # Send as batch message
                        batch_message = {
                            't': 'batch',
                            'p': {
                                'messages': [msg for _, msg in batch],
                                'count': len(batch)
                            }
                        }
                        await self._send_raw_message(batch_message)
                    else:
                        # Send individually
                        for priority, message in batch:
                            await self._send_raw_message(message)

                    # Small delay between batches
                    await asyncio.sleep(0.001)
                else:
                    # No messages, wait
                    await asyncio.sleep(self.batch_timeout)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Sender loop error: {e}")
                self.circuit_breaker.record_failure()
                await asyncio.sleep(1)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats"""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                # Send heartbeat
                await self.send_message({
                    't': 'heartbeat',
                    'p': {
                        'timestamp': int(datetime.now().timestamp() * 1000),
                        'sequence': self.sequence_number
                    }
                }, priority=10)

                # Also send PING for latency measurement
                if self.ws and self.ws.client_state == WebSocketState.CONNECTED:
                    try:
                        # Record packet sent
                        self.network_analyzer.record_packet_sent()
                        await self.ws.send_text(f"PING:{int(datetime.now().timestamp() * 1000)}")
                        self.metrics.messages_sent += 1
                    except Exception as e:
                        log.error(f"Failed to send ping: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Heartbeat error: {e}")

    async def _health_check_loop(self) -> None:
        """Perform periodic health checks"""
        while self._running:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

                # Update network diagnostics
                diagnostics = self.network_analyzer.analyze()

                # Check circuit breaker state
                cb_state = await self.circuit_breaker.get_state()
                if cb_state["state"] == "OPEN":
                    await self.set_state(ConnectionState.DEGRADED)
                    if self.circuit_breaker.can_execute():
                        log.info(f"Circuit breaker for {self.conn_id} transitioning to HALF_OPEN")
                elif cb_state["state"] == "CLOSED" and self.connection_state == ConnectionState.DEGRADED:
                    await self.set_state(ConnectionState.CONNECTED)

                # Send health status if poor
                if diagnostics['quality'] in ['poor', 'fair']:
                    await self.send_message({
                        't': 'connection_quality',
                        'p': {
                            'quality': diagnostics['quality'],
                            'suggestions': diagnostics['suggestions'],
                            'metrics': self.metrics.to_dict(),
                            'jitter': diagnostics['jitter'],
                            'packet_loss': diagnostics['packet_loss']
                        }
                    }, priority=8)

                # Log health check
                if self.debug_mode:
                    log.debug(f"Health check - Quality: {diagnostics['quality']}, "
                              f"Jitter: {diagnostics['jitter']}ms, "
                              f"Packet loss: {diagnostics['packet_loss']}%")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Health check error: {e}")

    async def _metrics_collection_loop(self) -> None:
        """Collect and calculate metrics"""
        last_message_count = 0
        last_byte_count = 0

        while self._running:
            try:
                await asyncio.sleep(METRICS_INTERVAL)

                # Calculate message rate
                current_messages = self.metrics.messages_received + self.metrics.messages_sent
                self.metrics.message_rate = (current_messages - last_message_count) / METRICS_INTERVAL
                last_message_count = current_messages

                # Calculate bandwidth
                current_bytes = self.metrics.bytes_received + self.metrics.bytes_sent
                self.metrics.bandwidth = (current_bytes - last_byte_count) / METRICS_INTERVAL
                last_byte_count = current_bytes

                # Update compression ratio
                if self.metrics.compression_hits > 0:
                    total_original = self.metrics.bytes_sent / (self.metrics.compression_ratio or 1)
                    self.metrics.compression_ratio = self.metrics.bytes_sent / total_original if total_original > 0 else 1

                # Prometheus queue metrics
                if METRICS_AVAILABLE:
                    queue_stats = self.message_queue.get_stats()
                    ws_queue_size.labels(connection_id=self.conn_id, priority='total').set(queue_stats['size'])
                    ws_queue_backpressure.labels(connection_id=self.conn_id).set(1 if queue_stats['backpressure'] else 0)

                    # Track dropped messages by priority
                    for priority, dropped in queue_stats.get('dropped_by_priority', {}).items():
                        ws_queue_dropped_total.labels(connection_id=self.conn_id, priority=str(priority)).inc(dropped)

                # Log metrics periodically
                log.info(f"Connection {self.conn_id} metrics - "
                         f"Rate: {self.metrics.message_rate:.2f} msg/s, "
                         f"Bandwidth: {self.metrics.bandwidth:.2f} B/s, "
                         f"Compression: {self.metrics.compression_ratio:.2f}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Metrics collection error: {e}")

    async def _sequence_cleanup_loop(self) -> None:
        """Periodically clean up sequence tracking"""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Clean up old seen message IDs
                if len(self.seen_message_ids) > 5000:
                    # Keep only the last 5000
                    new_deque = deque(list(self.seen_message_ids)[-5000:], maxlen=10000)
                    self.seen_message_ids = new_deque

                # Clean up sequencer
                await self.event_sequencer.cleanup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Sequence cleanup error: {e}")

    async def _debug_stats_loop(self) -> None:
        """Periodically log debug statistics"""
        while self._running and self.debug_mode:
            try:
                await asyncio.sleep(60)  # Every minute

                log.info(f"=== Connection {self.conn_id} Debug Stats ===")
                log.info(f"Messages sent: {self.metrics.messages_sent}")
                log.info(f"Messages received: {self.metrics.messages_received}")
                log.info(f"Active subscriptions: {list(self.subscriptions)}")
                log.info(f"Queue size: {self.message_queue.size}")
                log.info(f"Event types sent: {dict(self.event_count)}")

                # Reset event count
                self.event_count.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Debug stats error: {e}")

    def _reset_idle_timer(self) -> None:
        """Reset idle timeout timer"""
        if self._idle_timer:
            self._idle_timer.cancel()

        async def idle_timeout():
            await asyncio.sleep(IDLE_TIMEOUT)
            if self._running:
                log.warning(f"Connection {self.conn_id} idle timeout")
                # Stop sender loop FIRST to prevent send-after-close errors
                self._running = False
                # Clear message queue to prevent pending sends
                self.message_queue.clear()
                # Now set state and close
                await self.set_state(ConnectionState.DISCONNECTED)
                await self.ws.close(code=1000, reason="Idle timeout")

        self._idle_timer = asyncio.create_task(idle_timeout())

    async def _send_rate_limit_warning(self) -> None:
        """Send rate limit warning to client with proper format"""
        rl_status = self.rate_limiter.get_status()

        await self.send_message({
            't': 'rate_limit_warning',
            'p': {
                'message': 'Rate limit exceeded. Please slow down your requests.',
                'code': 'RATE_LIMIT_EXCEEDED',
                'limit': rl_status.get('capacity', 1000),
                'window': 1.0,  # 1 second window
                'retry_after': 1.0,
                'current_usage': rl_status.get('capacity', 1000) - rl_status.get('available_tokens', 0),
                'stats': {
                    'tokens_remaining': rl_status.get('available_tokens', 0),
                    'refill_rate': rl_status.get('refill_rate', 100),
                    'capacity': rl_status.get('capacity', 1000)
                }
            }
        }, priority=10)

    async def cleanup(self) -> None:
        """Clean up connection resources"""
        self._running = False

        # Set disconnected state
        await self.set_state(ConnectionState.DISCONNECTED)

        # Prometheus metrics
        if METRICS_AVAILABLE:
            ws_connections_active.dec()
            ws_disconnections_total.labels(reason='normal').inc()

        # Cancel idle timer
        if self._idle_timer:
            self._idle_timer.cancel()

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Unsubscribe from all topics
        for sub_id in self.subscription_ids.values():
            try:
                await self.event_bus.unsubscribe(sub_id)
            except Exception as e:
                log.error(f"Error unsubscribing {sub_id}: {e}")

        # Cleanup components
        await self.event_sequencer.shutdown()

        # Log final metrics
        log.info(
            f"Connection {self.conn_id} closed - "
            f"Messages: {self.metrics.messages_sent}/{self.metrics.messages_received}, "
            f"Bytes: {self.metrics.bytes_sent}/{self.metrics.bytes_received}, "
            f"Compression hits: {self.metrics.compression_hits}, "
            f"Compression ratio: {self.metrics.compression_ratio:.2f}"
        )

        if self.debug_mode:
            log.info(f"Final event count: {dict(self.event_count)}")