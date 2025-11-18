# app/infra/metrics/wse_metrics.py
"""
WSE Metrics - Internal tracking and Prometheus export

Provides:
1. Internal metrics classes (ConnectionMetrics, NetworkQualityAnalyzer)
2. Prometheus metrics export for monitoring
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import deque
from prometheus_client import Counter, Histogram, Gauge


# ============================================================================
# Internal Metrics Classes (used by WSEConnection)
# ============================================================================

@dataclass
class ConnectionMetrics:
    """Internal metrics for a WebSocket connection"""

    # Connection lifecycle
    connected_since: Optional[datetime] = None
    connection_attempts: int = 0
    successful_connections: int = 0

    # Message counters
    messages_sent: int = 0
    messages_received: int = 0
    messages_dropped: int = 0

    # Byte counters
    bytes_sent: int = 0
    bytes_received: int = 0

    # Timestamps
    last_message_sent: Optional[datetime] = None
    last_message_received: Optional[datetime] = None

    # Compression
    compression_hits: int = 0
    compression_ratio: float = 1.0

    # Errors
    protocol_errors: int = 0
    last_error_message: str = ""

    # Performance
    message_rate: float = 0.0  # messages per second
    bandwidth: float = 0.0  # bytes per second
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))

    def record_latency(self, latency_ms: int) -> None:
        """Record a latency measurement"""
        self.latencies.append(latency_ms)

    def get_avg_latency(self) -> float:
        """Get average latency in ms"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "connected_since": self.connected_since.isoformat() if self.connected_since else None,
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "messages_dropped": self.messages_dropped,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "last_message_sent": self.last_message_sent.isoformat() if self.last_message_sent else None,
            "last_message_received": self.last_message_received.isoformat() if self.last_message_received else None,
            "compression_hits": self.compression_hits,
            "compression_ratio": self.compression_ratio,
            "protocol_errors": self.protocol_errors,
            "last_error_message": self.last_error_message,
            "message_rate": self.message_rate,
            "bandwidth": self.bandwidth,
            "avg_latency_ms": self.get_avg_latency()
        }


@dataclass
class NetworkQualityAnalyzer:
    """Analyzes network quality for a WebSocket connection"""

    # Packet tracking
    packets_sent: int = 0
    packets_received: int = 0
    expected_packets: int = 0

    # Byte tracking
    bytes_tracked: int = 0
    last_byte_time: float = field(default_factory=time.time)

    # Latency tracking
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))

    # Quality thresholds (ms)
    EXCELLENT_LATENCY = 50
    GOOD_LATENCY = 100
    FAIR_LATENCY = 200

    def record_packet_sent(self) -> None:
        """Record a packet sent"""
        self.packets_sent += 1
        self.expected_packets += 1

    def record_packet_received(self) -> None:
        """Record a packet received"""
        self.packets_received += 1

    def record_bytes(self, size: int) -> None:
        """Record bytes transferred"""
        self.bytes_tracked += size
        self.last_byte_time = time.time()

    def record_latency(self, latency_ms: int) -> None:
        """Record a latency measurement"""
        self.latencies.append(latency_ms)

    def calculate_jitter(self) -> float:
        """Calculate jitter (variance in latency) in ms"""
        if len(self.latencies) < 2:
            return 0.0

        latencies_list = list(self.latencies)
        avg = sum(latencies_list) / len(latencies_list)
        variance = sum((x - avg) ** 2 for x in latencies_list) / len(latencies_list)
        return variance ** 0.5  # Standard deviation

    def calculate_packet_loss(self) -> float:
        """Calculate packet loss percentage"""
        if self.expected_packets == 0:
            return 0.0

        lost = self.expected_packets - self.packets_received
        return (lost / self.expected_packets) * 100 if lost > 0 else 0.0

    def get_avg_latency(self) -> float:
        """Get average latency in ms"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def analyze(self) -> Dict[str, Any]:
        """Analyze network quality and return diagnostics"""
        avg_latency = self.get_avg_latency()
        jitter = self.calculate_jitter()
        packet_loss = self.calculate_packet_loss()

        # Determine quality level
        if avg_latency < self.EXCELLENT_LATENCY and packet_loss < 1 and jitter < 10:
            quality = "excellent"
            suggestions = []
        elif avg_latency < self.GOOD_LATENCY and packet_loss < 3 and jitter < 25:
            quality = "good"
            suggestions = []
        elif avg_latency < self.FAIR_LATENCY and packet_loss < 5 and jitter < 50:
            quality = "fair"
            suggestions = ["Consider reducing message frequency", "Check network conditions"]
        else:
            quality = "poor"
            suggestions = [
                "High latency detected - check network connection",
                "Consider reducing message size or frequency",
                "Packet loss detected - network may be unstable"
            ]

        return {
            "quality": quality,
            "avg_latency_ms": avg_latency,
            "jitter": jitter,
            "packet_loss": packet_loss,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "suggestions": suggestions
        }


# ============================================================================
# Prometheus Metrics (External Export)
# ============================================================================

# ============================================================================
# Pub/Sub Metrics
# ============================================================================

pubsub_published_total = Counter(
    'wse_pubsub_published_total',
    'Total messages published to Redis Pub/Sub',
    ['topic', 'priority']
)

pubsub_received_total = Counter(
    'wse_pubsub_received_total',
    'Total messages received from Redis Pub/Sub',
    ['pattern']
)

pubsub_publish_latency_seconds = Histogram(
    'wse_pubsub_publish_latency_seconds',
    'Time to publish message to Redis',
    ['topic'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

pubsub_batch_size = Histogram(
    'wse_pubsub_batch_size',
    'Number of messages in Redis pipeline batch',
    buckets=[1, 10, 25, 50, 100, 250, 500]
)

pubsub_handler_errors_total = Counter(
    'wse_pubsub_handler_errors_total',
    'Total handler errors',
    ['pattern', 'error_type']
)

pubsub_listener_errors_total = Counter(
    'wse_pubsub_listener_errors_total',
    'Total listener errors (circuit breaker)',
    ['error_type']
)

pubsub_circuit_breaker_state = Gauge(
    'wse_pubsub_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)'
)

# ============================================================================
# WebSocket Connection Metrics
# ============================================================================

ws_connections_active = Gauge(
    'wse_connections_active',
    'Number of active WebSocket connections'
)

ws_connections_total = Counter(
    'wse_connections_total',
    'Total WebSocket connections established',
    ['user_id']
)

ws_disconnections_total = Counter(
    'wse_disconnections_total',
    'Total WebSocket disconnections',
    ['reason']
)

ws_messages_sent_total = Counter(
    'wse_messages_sent_total',
    'Total messages sent to WebSocket clients',
    ['message_type', 'priority']
)

ws_messages_received_total = Counter(
    'wse_messages_received_total',
    'Total messages received from WebSocket clients',
    ['message_type']
)

ws_message_send_latency_seconds = Histogram(
    'wse_message_send_latency_seconds',
    'Time to send message to WebSocket client',
    ['priority'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0]
)

ws_bytes_sent_total = Counter(
    'wse_bytes_sent_total',
    'Total bytes sent to WebSocket clients'
)

ws_bytes_received_total = Counter(
    'wse_bytes_received_total',
    'Total bytes received from WebSocket clients'
)

# ============================================================================
# Queue Metrics
# ============================================================================

ws_queue_size = Gauge(
    'wse_queue_size',
    'Size of send queue',
    ['connection_id', 'priority']
)

ws_queue_utilization = Gauge(
    'wse_queue_utilization',
    'Queue utilization percentage',
    ['connection_id']
)

ws_queue_dropped_total = Counter(
    'wse_queue_dropped_total',
    'Messages dropped due to full queue',
    ['connection_id', 'priority']
)

ws_queue_backpressure = Gauge(
    'wse_queue_backpressure',
    'Queue backpressure indicator (1=backpressure, 0=normal)',
    ['connection_id']
)

ws_queue_oldest_message_age_seconds = Gauge(
    'wse_queue_oldest_message_age_seconds',
    'Age of oldest message in queue',
    ['connection_id']
)

# ============================================================================
# Dead Letter Queue Metrics
# ============================================================================

dlq_messages_total = Counter(
    'wse_dlq_messages_total',
    'Total messages sent to Dead Letter Queue',
    ['channel', 'error_type']
)

dlq_size = Gauge(
    'wse_dlq_size',
    'Number of messages in DLQ',
    ['channel']
)

dlq_replayed_total = Counter(
    'wse_dlq_replayed_total',
    'Total messages replayed from DLQ',
    ['channel']
)

# ============================================================================
# Compression Metrics
# ============================================================================

ws_compression_ratio = Histogram(
    'wse_compression_ratio',
    'Compression ratio achieved',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
)

ws_compression_hits_total = Counter(
    'wse_compression_hits_total',
    'Total messages compressed'
)

# ============================================================================
# Rate Limiting Metrics
# ============================================================================

ws_rate_limited_total = Counter(
    'wse_rate_limited_total',
    'Total messages dropped due to rate limiting',
    ['connection_id']
)

# ============================================================================
# Health Metrics
# ============================================================================

ws_health_status = Gauge(
    'wse_health_status',
    'WSE health status (1=healthy, 0=unhealthy)'
)

ws_heartbeat_latency_seconds = Histogram(
    'wse_heartbeat_latency_seconds',
    'WebSocket heartbeat latency',
    ['connection_id'],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)
