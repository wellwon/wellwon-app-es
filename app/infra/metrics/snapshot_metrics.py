# =============================================================================
# File: app/infra/event_store/snapshot_metrics.py
# Description: Metrics collection for event store snapshot operations
# =============================================================================
import uuid

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
import logging
from functools import wraps
from contextlib import contextmanager
from typing import Dict, Any, Optional
from datetime import datetime, timezone

log = logging.getLogger("tradecore.snapshot_metrics")


class SnapshotMetrics:
    """
    Comprehensive metrics for snapshot operations.

    Tracks:
    - Snapshot creation count and rate
    - Creation duration and size
    - Failures and errors
    - Active operations
    - Aggregate-specific metrics
    """

    def __init__(self, namespace: str = "event_store", subsystem: str = "snapshots"):
        """
        Initialize snapshot metrics.

        Args:
            namespace: Prometheus namespace
            subsystem: Prometheus subsystem
        """
        # Counters
        self.snapshots_created = Counter(
            f'{namespace}_{subsystem}_created_total',
            'Total number of snapshots created',
            ['aggregate_type', 'reason']
        )

        self.snapshot_failures = Counter(
            f'{namespace}_{subsystem}_failures_total',
            'Total number of snapshot creation failures',
            ['aggregate_type', 'error_type']
        )

        self.snapshots_loaded = Counter(
            f'{namespace}_{subsystem}_loaded_total',
            'Total number of snapshots loaded',
            ['aggregate_type']
        )

        self.snapshots_cleaned = Counter(
            f'{namespace}_{subsystem}_cleaned_total',
            'Total number of old snapshots cleaned up',
            ['aggregate_type']
        )

        # Histograms
        self.snapshot_creation_duration = Histogram(
            f'{namespace}_{subsystem}_creation_duration_seconds',
            'Time to create a snapshot',
            ['aggregate_type'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )

        self.snapshot_size_bytes = Histogram(
            f'{namespace}_{subsystem}_size_bytes',
            'Size of snapshot in bytes',
            ['aggregate_type'],
            buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600)  # 1KB to 100MB
        )

        self.events_since_snapshot = Histogram(
            f'{namespace}_{subsystem}_events_since_last',
            'Number of events since last snapshot',
            ['aggregate_type'],
            buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
        )

        # Gauges
        self.active_snapshot_tasks = Gauge(
            f'{namespace}_{subsystem}_active_tasks',
            'Number of active snapshot creation tasks'
        )

        self.last_snapshot_version = Gauge(
            f'{namespace}_{subsystem}_last_version',
            'Version of last snapshot created',
            ['aggregate_type', 'aggregate_id']
        )

        self.snapshot_lag_seconds = Gauge(
            f'{namespace}_{subsystem}_lag_seconds',
            'Time since last snapshot was created',
            ['aggregate_type']
        )

        # Summary for percentiles
        self.snapshot_compression_ratio = Summary(
            f'{namespace}_{subsystem}_compression_ratio',
            'Compression ratio of snapshots (compressed/uncompressed)',
            ['aggregate_type']
        )

        # Internal tracking
        self._last_snapshot_time: Dict[str, datetime] = {}
        self._snapshot_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, Dict[str, int]] = {}

        log.info(f"SnapshotMetrics initialized with namespace={namespace}, subsystem={subsystem}")

    def record_snapshot_created(
            self,
            aggregate_type: str,
            aggregate_id: str,
            version: int,
            reason: str,
            size_bytes: Optional[int] = None,
            duration_seconds: Optional[float] = None,
            events_since_last: Optional[int] = None
    ):
        """
        Record that a snapshot was created.

        Args:
            aggregate_type: Type of aggregate
            aggregate_id: ID of aggregate
            version: Version of snapshot
            reason: Reason for creation (e.g., "event_interval", "time_interval")
            size_bytes: Size of snapshot
            duration_seconds: Time taken to create
            events_since_last: Number of events since last snapshot
        """
        # Update counters
        self.snapshots_created.labels(
            aggregate_type=aggregate_type,
            reason=reason
        ).inc()

        # Update version gauge
        self.last_snapshot_version.labels(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id
        ).set(version)

        # Record size if provided
        if size_bytes is not None:
            self.snapshot_size_bytes.labels(
                aggregate_type=aggregate_type
            ).observe(size_bytes)

        # Record duration if provided
        if duration_seconds is not None:
            self.snapshot_creation_duration.labels(
                aggregate_type=aggregate_type
            ).observe(duration_seconds)

        # Record events since last snapshot
        if events_since_last is not None:
            self.events_since_snapshot.labels(
                aggregate_type=aggregate_type
            ).observe(events_since_last)

        # Update internal tracking
        self._last_snapshot_time[aggregate_type] = datetime.now(timezone.utc)
        self._snapshot_counts[aggregate_type] = self._snapshot_counts.get(aggregate_type, 0) + 1

        # Update lag gauge
        self.snapshot_lag_seconds.labels(aggregate_type=aggregate_type).set(0)

        log.debug(
            f"Recorded snapshot: {aggregate_type}:{aggregate_id} v{version} "
            f"(reason={reason}, size={size_bytes}, duration={duration_seconds}s)"
        )

    def record_snapshot_failure(
            self,
            aggregate_type: str,
            error_type: str,
            error_message: Optional[str] = None
    ):
        """
        Record a snapshot creation failure.

        Args:
            aggregate_type: Type of aggregate
            error_type: Type of error (e.g., "timeout", "serialization", "storage")
            error_message: Optional error message
        """
        self.snapshot_failures.labels(
            aggregate_type=aggregate_type,
            error_type=error_type
        ).inc()

        # Track error counts
        if aggregate_type not in self._error_counts:
            self._error_counts[aggregate_type] = {}
        self._error_counts[aggregate_type][error_type] = \
            self._error_counts[aggregate_type].get(error_type, 0) + 1

        log.error(
            f"Snapshot failure: {aggregate_type} - {error_type}"
            + (f": {error_message}" if error_message else "")
        )

    def record_snapshot_loaded(self, aggregate_type: str):
        """Record that a snapshot was loaded"""
        self.snapshots_loaded.labels(aggregate_type=aggregate_type).inc()

    def record_snapshots_cleaned(self, aggregate_type: str, count: int):
        """Record snapshot cleanup"""
        self.snapshots_cleaned.labels(aggregate_type=aggregate_type).inc(count)

    def record_compression_ratio(self, aggregate_type: str, ratio: float):
        """Record snapshot compression ratio"""
        self.snapshot_compression_ratio.labels(aggregate_type=aggregate_type).observe(ratio)

    @contextmanager
    def track_snapshot_duration(self, aggregate_type: str):
        """
        Context manager to track snapshot creation duration.

        Usage:
            with metrics.track_snapshot_duration("Order"):
                # Create snapshot
        """
        start_time = time.time()
        self.active_snapshot_tasks.inc()

        try:
            yield
        finally:
            duration = time.time() - start_time
            self.snapshot_creation_duration.labels(
                aggregate_type=aggregate_type
            ).observe(duration)
            self.active_snapshot_tasks.dec()

    def track_active_task(self):
        """
        Decorator to track active snapshot tasks.

        Usage:
            @metrics.track_active_task()
            async def create_snapshot(...):
                ...
        """

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                self.active_snapshot_tasks.inc()
                try:
                    return await func(*args, **kwargs)
                finally:
                    self.active_snapshot_tasks.dec()

            return wrapper

        return decorator

    def update_lag_metrics(self):
        """Update snapshot lag metrics for all aggregate types"""
        current_time = datetime.now(timezone.utc)

        for aggregate_type, last_time in self._last_snapshot_time.items():
            lag_seconds = (current_time - last_time).total_seconds()
            self.snapshot_lag_seconds.labels(aggregate_type=aggregate_type).set(lag_seconds)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics.

        Returns:
            Dictionary with current metrics
        """
        self.update_lag_metrics()

        stats = {
            "total_snapshots": sum(self._snapshot_counts.values()),
            "snapshots_by_type": dict(self._snapshot_counts),
            "errors_by_type": dict(self._error_counts),
            "active_tasks": self.active_snapshot_tasks._value._value,
            "aggregate_types": list(self._snapshot_counts.keys()),
        }

        # Add lag information
        current_time = datetime.now(timezone.utc)
        lags = {}
        for agg_type, last_time in self._last_snapshot_time.items():
            lags[agg_type] = {
                "last_snapshot": last_time.isoformat(),
                "lag_seconds": (current_time - last_time).total_seconds()
            }
        stats["snapshot_lags"] = lags

        return stats

    def reset(self):
        """Reset internal counters (for testing)"""
        self._last_snapshot_time.clear()
        self._snapshot_counts.clear()
        self._error_counts.clear()
        log.info("Snapshot metrics reset")


class SnapshotMetricsCollector:
    """
    Collector that integrates with the snapshot system to automatically
    record metrics.
    """

    def __init__(self, metrics: SnapshotMetrics):
        self.metrics = metrics

    async def on_snapshot_created(
            self,
            aggregate_type: str,
            aggregate_id: uuid.UUID,
            version: int,
            reason: str,
            snapshot_data: Dict[str, Any],
            duration_seconds: float,
            events_since_last: Optional[int] = None
    ):
        """Hook called when snapshot is created"""
        # Calculate size
        import json
        size_bytes = len(json.dumps(snapshot_data).encode('utf-8'))

        # Record metrics
        self.metrics.record_snapshot_created(
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            version=version,
            reason=reason,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            events_since_last=events_since_last
        )

    async def on_snapshot_failed(
            self,
            aggregate_type: str,
            aggregate_id: uuid.UUID,
            error: Exception
    ):
        """Hook called when snapshot creation fails"""
        # Classify error
        error_type = "unknown"
        if "timeout" in str(error).lower():
            error_type = "timeout"
        elif "serialization" in str(error).lower():
            error_type = "serialization"
        elif any(storage in str(error).lower() for storage in ["kafka", "redis", "s3"]):
            error_type = "storage"
        else:
            error_type = type(error).__name__

        self.metrics.record_snapshot_failure(
            aggregate_type=aggregate_type,
            error_type=error_type,
            error_message=str(error)
        )


# =============================================================================
# Grafana Dashboard Queries
# =============================================================================

GRAFANA_QUERIES = {
    "snapshot_creation_rate": {
        "query": 'rate(event_store_snapshots_created_total[5m])',
        "legend": "{{aggregate_type}} - {{reason}}",
        "title": "Snapshot Creation Rate"
    },

    "snapshot_creation_latency_p95": {
        "query": 'histogram_quantile(0.95, event_store_snapshots_creation_duration_seconds)',
        "legend": "{{aggregate_type}}",
        "title": "Snapshot Creation Latency (95th percentile)"
    },

    "snapshot_failures": {
        "query": 'rate(event_store_snapshots_failures_total[5m])',
        "legend": "{{aggregate_type}} - {{error_type}}",
        "title": "Snapshot Failure Rate"
    },

    "active_snapshot_tasks": {
        "query": 'event_store_snapshots_active_tasks',
        "legend": "Active Tasks",
        "title": "Active Snapshot Tasks"
    },

    "snapshot_sizes_p95": {
        "query": 'histogram_quantile(0.95, event_store_snapshots_size_bytes)',
        "legend": "{{aggregate_type}}",
        "title": "Snapshot Sizes (95th percentile)"
    },

    "snapshot_lag": {
        "query": 'event_store_snapshots_lag_seconds',
        "legend": "{{aggregate_type}}",
        "title": "Time Since Last Snapshot"
    },

    "events_between_snapshots": {
        "query": 'histogram_quantile(0.95, event_store_snapshots_events_since_last)',
        "legend": "{{aggregate_type}}",
        "title": "Events Between Snapshots (95th percentile)"
    }
}

# =============================================================================
# Singleton Instance
# =============================================================================

# Global metrics instance
_metrics_instance: Optional[SnapshotMetrics] = None


def get_snapshot_metrics() -> SnapshotMetrics:
    """Get or create the global snapshot metrics instance"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = SnapshotMetrics()
    return _metrics_instance


# =============================================================================
# Integration Helpers
# =============================================================================

def integrate_with_event_store(event_store, metrics: Optional[SnapshotMetrics] = None):
    """
    Integrate metrics with an event store instance.

    Args:
        event_store: The RedPandaEventStore instance
        metrics: Optional metrics instance (uses global if not provided)
    """
    metrics = metrics or get_snapshot_metrics()

    # Monkey-patch the event store to record metrics
    original_save_snapshot = event_store.save_snapshot

    async def save_snapshot_with_metrics(
            aggregate_id,
            aggregate_type,
            version,
            state,
            metadata=None
    ):
        start_time = time.time()

        try:
            # Call original method
            await original_save_snapshot(
                aggregate_id,
                aggregate_type,
                version,
                state,
                metadata
            )

            # Record success metrics
            duration = time.time() - start_time
            reason = metadata.get("reason", "unknown") if metadata else "unknown"

            import json
            size_bytes = len(json.dumps(state).encode('utf-8'))

            metrics.record_snapshot_created(
                aggregate_type=aggregate_type,
                aggregate_id=str(aggregate_id),
                version=version,
                reason=reason,
                size_bytes=size_bytes,
                duration_seconds=duration
            )

        except Exception as e:
            # Record failure
            metrics.record_snapshot_failure(
                aggregate_type=aggregate_type,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise

    # Replace method
    event_store.save_snapshot = save_snapshot_with_metrics

    log.info("Integrated snapshot metrics with event store")

# =============================================================================
# EOF
# =============================================================================