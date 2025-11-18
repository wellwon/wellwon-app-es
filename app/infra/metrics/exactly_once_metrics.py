# app/infra/event_bus/exactly_once_metrics.py
"""
Exactly-Once Delivery Metrics

Prometheus metrics for monitoring exactly-once delivery guarantees:
- Broker API idempotency
- Kafka transaction health
- Outbox reconciliation
- Duplicate detection

Created: 2025-11-13 (TRUE Exactly-Once Implementation)
"""

from prometheus_client import Counter, Histogram, Gauge

# ============================================================================
# Broker API Idempotency Metrics
# ============================================================================

broker_api_idempotent_hits_total = Counter(
    'broker_api_idempotent_hits_total',
    'Number of duplicate broker API requests prevented by idempotency keys',
    ['broker', 'operation']
)

broker_api_client_order_id_generated_total = Counter(
    'broker_api_client_order_id_generated_total',
    'Number of client_order_id values generated for broker API calls',
    ['broker']
)

broker_api_client_order_id_provided_total = Counter(
    'broker_api_client_order_id_provided_total',
    'Number of client_order_id values provided by command',
    ['broker']
)

# ============================================================================
# Kafka Transaction Metrics
# ============================================================================

kafka_txn_commits_total = Counter(
    'kafka_txn_commits_total',
    'Successful Kafka transaction commits',
    ['consumer_group', 'topic']
)

kafka_txn_aborts_total = Counter(
    'kafka_txn_aborts_total',
    'Kafka transaction aborts (failures)',
    ['consumer_group', 'topic', 'reason']
)

kafka_txn_duration_seconds = Histogram(
    'kafka_txn_duration_seconds',
    'Kafka transaction duration in seconds',
    ['consumer_group'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

kafka_txn_batch_size = Histogram(
    'kafka_txn_batch_size',
    'Number of messages processed per transaction',
    ['consumer_group'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

kafka_txn_active = Gauge(
    'kafka_txn_active',
    'Number of active Kafka transactions',
    ['consumer_group']
)

# ============================================================================
# Outbox Pattern Metrics
# ============================================================================

outbox_transactional_publish_success_total = Counter(
    'outbox_transactional_publish_success_total',
    'Successful transactional outbox publishes'
)

outbox_transactional_publish_failures_total = Counter(
    'outbox_transactional_publish_failures_total',
    'Failed transactional outbox publishes',
    ['reason']
)

outbox_transactional_publish_duration_seconds = Histogram(
    'outbox_transactional_publish_duration_seconds',
    'Duration of transactional outbox publish operations',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# ============================================================================
# Event Store Reconciliation Metrics
# ============================================================================

outbox_orphaned_events_total = Counter(
    'outbox_orphaned_events_total',
    'Orphaned events found during reconciliation (in EventStore but not in outbox)'
)

outbox_reconciliation_runs_total = Counter(
    'outbox_reconciliation_runs_total',
    'Number of reconciliation runs executed',
    ['status']  # 'success', 'failure'
)

outbox_reconciliation_duration_seconds = Histogram(
    'outbox_reconciliation_duration_seconds',
    'Duration of reconciliation operations',
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

outbox_reconciliation_events_checked = Histogram(
    'outbox_reconciliation_events_checked',
    'Number of events checked during reconciliation',
    buckets=[10, 50, 100, 500, 1000, 5000, 10000]
)

# ============================================================================
# Consumer Duplicate Detection Metrics
# ============================================================================

consumer_duplicate_messages_total = Counter(
    'consumer_duplicate_messages_total',
    'Messages re-delivered by Kafka (detected by consumer)',
    ['consumer_group', 'topic']
)

consumer_offset_commit_failures_total = Counter(
    'consumer_offset_commit_failures_total',
    'Failed offset commit attempts',
    ['consumer_group', 'topic', 'reason']
)

consumer_redelivery_latency_seconds = Histogram(
    'consumer_redelivery_latency_seconds',
    'Time between original delivery and re-delivery',
    ['consumer_group'],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300]
)

# ============================================================================
# Idempotent Handler Metrics
# ============================================================================

idempotent_handler_skips_total = Counter(
    'idempotent_handler_skips_total',
    'Number of duplicate executions prevented by idempotent handlers',
    ['handler_name', 'event_type']
)

idempotent_handler_upsert_conflicts_total = Counter(
    'idempotent_handler_upsert_conflicts_total',
    'Number of ON CONFLICT situations in projectors (duplicate detection)',
    ['projector_name', 'table_name']
)

# ============================================================================
# Transactional Producer Pool Metrics (NEW - 2025-11-14)
# ============================================================================

kafka_transactional_producer_pool_size = Gauge(
    'kafka_transactional_producer_pool_size',
    'Current number of transactional producers in pool'
)

kafka_transactional_producer_pool_max_size = Gauge(
    'kafka_transactional_producer_pool_max_size',
    'Maximum allowed transactional producers in pool'
)

kafka_transactional_producer_evictions_total = Counter(
    'kafka_transactional_producer_evictions_total',
    'Number of LRU evictions from transactional producer pool'
)

kafka_transactional_producer_creates_total = Counter(
    'kafka_transactional_producer_creates_total',
    'Number of transactional producers created'
)

kafka_transactional_producer_usage = Histogram(
    'kafka_transactional_producer_usage',
    'Usage count distribution for transactional producers',
    ['transactional_id_prefix'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

# ============================================================================
# Overall Exactly-Once Health
# ============================================================================

exactly_once_violations_total = Counter(
    'exactly_once_violations_total',
    'Detected exactly-once violations (duplicate side effects)',
    ['violation_type', 'component']
)

exactly_once_health = Gauge(
    'exactly_once_health',
    'Overall health of exactly-once delivery (1=healthy, 0=unhealthy)',
    ['component']  # 'broker_api', 'kafka_txn', 'outbox', 'reconciliation'
)

# ============================================================================
# Helper Functions
# ============================================================================

def record_broker_idempotency_hit(broker: str, operation: str = "place_order"):
    """Record a duplicate broker API request prevented by idempotency."""
    broker_api_idempotent_hits_total.labels(broker=broker, operation=operation).inc()


def record_kafka_transaction_commit(consumer_group: str, topic: str, duration: float, batch_size: int):
    """Record successful Kafka transaction commit."""
    kafka_txn_commits_total.labels(consumer_group=consumer_group, topic=topic).inc()
    kafka_txn_duration_seconds.labels(consumer_group=consumer_group).observe(duration)
    kafka_txn_batch_size.labels(consumer_group=consumer_group).observe(batch_size)


def record_kafka_transaction_abort(consumer_group: str, topic: str, reason: str):
    """Record Kafka transaction abort."""
    kafka_txn_aborts_total.labels(
        consumer_group=consumer_group,
        topic=topic,
        reason=reason
    ).inc()


def record_outbox_orphaned_event():
    """Record an orphaned event found during reconciliation."""
    outbox_orphaned_events_total.inc()


def record_idempotent_skip(handler_name: str, event_type: str):
    """Record a duplicate execution prevented by idempotent handler."""
    idempotent_handler_skips_total.labels(
        handler_name=handler_name,
        event_type=event_type
    ).inc()


def record_exactly_once_violation(violation_type: str, component: str):
    """Record exactly-once violation (duplicate side effect detected)."""
    exactly_once_violations_total.labels(
        violation_type=violation_type,
        component=component
    ).inc()

    # Mark component as unhealthy
    exactly_once_health.labels(component=component).set(0)


def mark_component_healthy(component: str):
    """Mark exactly-once component as healthy."""
    exactly_once_health.labels(component=component).set(1)


def record_transactional_producer_created():
    """Record creation of a new transactional producer."""
    kafka_transactional_producer_creates_total.inc()


def record_transactional_producer_evicted():
    """Record LRU eviction of a transactional producer."""
    kafka_transactional_producer_evictions_total.inc()


def update_transactional_producer_pool_size(current_size: int, max_size: int):
    """Update transactional producer pool size metrics."""
    kafka_transactional_producer_pool_size.set(current_size)
    kafka_transactional_producer_pool_max_size.set(max_size)


def record_transactional_producer_usage(transactional_id_prefix: str, usage_count: int):
    """Record usage count for a transactional producer."""
    kafka_transactional_producer_usage.labels(
        transactional_id_prefix=transactional_id_prefix
    ).observe(usage_count)


# Initialize health metrics
for component in ['broker_api', 'kafka_txn', 'outbox', 'reconciliation']:
    exactly_once_health.labels(component=component).set(1)
