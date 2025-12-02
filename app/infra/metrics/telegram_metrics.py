# =============================================================================
# File: app/infra/metrics/telegram_metrics.py
# Description: Prometheus metrics for Telegram integration monitoring
# =============================================================================
# Metrics for:
#   - Webhook processing (requests, latency, errors)
#   - Message sending (success, failures, rate limits)
#   - MTProto client (connections, reconnections, flood waits)
#   - Message deduplication (hits, misses)
#   - Security events (IP blocks, invalid secrets)
# =============================================================================

from prometheus_client import Counter, Histogram, Gauge

# =============================================================================
# Webhook Metrics
# =============================================================================

telegram_webhook_requests_total = Counter(
    'telegram_webhook_requests_total',
    'Total webhook requests received',
    ['status']  # success, duplicate, invalid_secret, invalid_ip, error
)

telegram_webhook_latency_seconds = Histogram(
    'telegram_webhook_latency_seconds',
    'Webhook request processing time',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

telegram_webhook_messages_total = Counter(
    'telegram_webhook_messages_total',
    'Total messages received via webhook',
    ['message_type']  # text, photo, document, voice, video, topic_created
)

# =============================================================================
# Message Sending Metrics (Bot API)
# =============================================================================

telegram_messages_sent_total = Counter(
    'telegram_messages_sent_total',
    'Total messages sent to Telegram',
    ['message_type', 'status']  # text/photo/document/voice, success/error/rate_limited
)

telegram_send_latency_seconds = Histogram(
    'telegram_send_latency_seconds',
    'Time to send message to Telegram',
    ['message_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

telegram_rate_limit_hits_total = Counter(
    'telegram_rate_limit_hits_total',
    'Total rate limit (429) responses from Telegram',
    ['endpoint']  # send_message, send_photo, etc.
)

telegram_rate_limit_wait_seconds = Histogram(
    'telegram_rate_limit_wait_seconds',
    'Time waited due to rate limiting',
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

# =============================================================================
# MTProto Client Metrics
# =============================================================================

telegram_mtproto_connected = Gauge(
    'telegram_mtproto_connected',
    'MTProto client connection status (1=connected, 0=disconnected)'
)

telegram_mtproto_reconnects_total = Counter(
    'telegram_mtproto_reconnects_total',
    'Total reconnection attempts',
    ['status']  # success, failure
)

telegram_mtproto_flood_waits_total = Counter(
    'telegram_mtproto_flood_waits_total',
    'Total FloodWaitError occurrences',
    ['operation']  # send_message, create_group, etc.
)

telegram_mtproto_flood_wait_seconds = Histogram(
    'telegram_mtproto_flood_wait_seconds',
    'Flood wait duration',
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

telegram_mtproto_entity_cache_hits = Counter(
    'telegram_mtproto_entity_cache_hits_total',
    'Entity cache hits (avoided API calls)'
)

telegram_mtproto_entity_cache_misses = Counter(
    'telegram_mtproto_entity_cache_misses_total',
    'Entity cache misses (required API calls)'
)

# =============================================================================
# Group/Topic Operations Metrics
# =============================================================================

telegram_group_operations_total = Counter(
    'telegram_group_operations_total',
    'Total group/topic operations',
    ['operation', 'status']  # create_group/create_topic/delete_topic, success/error
)

telegram_group_operation_latency_seconds = Histogram(
    'telegram_group_operation_latency_seconds',
    'Group/topic operation latency',
    ['operation'],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# =============================================================================
# Deduplication Metrics
# =============================================================================

telegram_dedup_checks_total = Counter(
    'telegram_dedup_checks_total',
    'Total deduplication checks',
    ['result']  # new, duplicate
)

telegram_dedup_cache_size = Gauge(
    'telegram_dedup_cache_size',
    'Current size of deduplication cache'
)

# =============================================================================
# Security Metrics
# =============================================================================

telegram_security_blocked_total = Counter(
    'telegram_security_blocked_total',
    'Total requests blocked by security checks',
    ['reason']  # invalid_ip, invalid_secret, rate_limited
)

telegram_security_ip_checks_total = Counter(
    'telegram_security_ip_checks_total',
    'Total IP address verification checks',
    ['result']  # allowed, blocked, skipped_local
)

# =============================================================================
# Message Queue Metrics (Outgoing)
# =============================================================================

telegram_outgoing_queue_size = Gauge(
    'telegram_outgoing_queue_size',
    'Number of messages in outgoing queue'
)

telegram_outgoing_queue_latency_seconds = Histogram(
    'telegram_outgoing_queue_latency_seconds',
    'Time messages spend in outgoing queue',
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
)

telegram_outgoing_dlq_total = Counter(
    'telegram_outgoing_dlq_total',
    'Messages moved to dead letter queue',
    ['reason']  # max_retries, permanent_error
)

# =============================================================================
# Health Metrics
# =============================================================================

telegram_health_status = Gauge(
    'telegram_health_status',
    'Telegram integration health (1=healthy, 0=unhealthy)'
)

telegram_bot_api_available = Gauge(
    'telegram_bot_api_available',
    'Bot API availability (1=available, 0=unavailable)'
)

telegram_mtproto_available = Gauge(
    'telegram_mtproto_available',
    'MTProto client availability (1=available, 0=unavailable)'
)


# =============================================================================
# Helper Functions
# =============================================================================

def record_webhook_request(status: str) -> None:
    """Record a webhook request with status."""
    telegram_webhook_requests_total.labels(status=status).inc()


def record_message_sent(message_type: str, success: bool) -> None:
    """Record a sent message."""
    status = "success" if success else "error"
    telegram_messages_sent_total.labels(message_type=message_type, status=status).inc()


def record_rate_limit(endpoint: str, wait_seconds: float) -> None:
    """Record a rate limit hit."""
    telegram_rate_limit_hits_total.labels(endpoint=endpoint).inc()
    telegram_rate_limit_wait_seconds.observe(wait_seconds)


def record_flood_wait(operation: str, wait_seconds: float) -> None:
    """Record a FloodWaitError."""
    telegram_mtproto_flood_waits_total.labels(operation=operation).inc()
    telegram_mtproto_flood_wait_seconds.observe(wait_seconds)


def record_dedup_check(is_duplicate: bool) -> None:
    """Record a deduplication check result."""
    result = "duplicate" if is_duplicate else "new"
    telegram_dedup_checks_total.labels(result=result).inc()


def record_security_block(reason: str) -> None:
    """Record a security block."""
    telegram_security_blocked_total.labels(reason=reason).inc()


def set_health_status(healthy: bool, bot_api: bool, mtproto: bool) -> None:
    """Set health status gauges."""
    telegram_health_status.set(1 if healthy else 0)
    telegram_bot_api_available.set(1 if bot_api else 0)
    telegram_mtproto_available.set(1 if mtproto else 0)
