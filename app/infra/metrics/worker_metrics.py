# app/infra/metrics/worker_metrics.py
# =============================================================================
# File: app/infra/metrics/worker_metrics.py
# Description: Unified metrics interface for all workers
# Author: TradeCore Platform Team
# Version: 0.8
# =============================================================================

"""
Unified Worker Metrics Collector

Provides a consistent metrics interface for all worker types with
Prometheus export support and Redis persistence.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# Prometheus metrics
from prometheus_client import Counter, Gauge, Histogram, Summary, Info

# Redis for distributed metrics
from app.infra.persistence.redis_client import get_global_client as get_redis_instance

# Worker types
from app.infra.worker_core.consumer_groups import WorkerType


# =============================================================================
# METRIC TYPES
# =============================================================================

class MetricType(Enum):
    """Types of metrics collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"


@dataclass
class MetricDefinition:
    """Definition of a metric"""
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms
    objectives: Optional[Dict[float, float]] = None  # For summaries


# =============================================================================
# STANDARD METRICS DEFINITIONS
# =============================================================================

STANDARD_WORKER_METRICS = {
    # Event processing metrics
    "events_processed_total": MetricDefinition(
        name="worker_events_processed_total",
        metric_type=MetricType.COUNTER,
        description="Total number of events processed",
        labels=["worker_type", "event_type", "status"]
    ),
    "events_processing_duration": MetricDefinition(
        name="worker_events_processing_duration_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Time spent processing events",
        labels=["worker_type", "event_type"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    ),
    "events_in_flight": MetricDefinition(
        name="worker_events_in_flight",
        metric_type=MetricType.GAUGE,
        description="Number of events currently being processed",
        labels=["worker_type"]
    ),

    # Error metrics
    "errors_total": MetricDefinition(
        name="worker_errors_total",
        metric_type=MetricType.COUNTER,
        description="Total number of errors",
        labels=["worker_type", "error_type"]
    ),
    "error_rate": MetricDefinition(
        name="worker_error_rate",
        metric_type=MetricType.GAUGE,
        description="Current error rate percentage",
        labels=["worker_type"]
    ),

    # Recovery metrics (for data integrity and connection recovery workers)
    "recoveries_triggered_total": MetricDefinition(
        name="worker_recoveries_triggered_total",
        metric_type=MetricType.COUNTER,
        description="Total number of recoveries triggered",
        labels=["worker_type", "recovery_type", "result"]
    ),
    "recovery_duration": MetricDefinition(
        name="worker_recovery_duration_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Time spent on recovery operations",
        labels=["worker_type", "recovery_type"],
        buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
    ),
    "active_recoveries": MetricDefinition(
        name="worker_active_recoveries",
        metric_type=MetricType.GAUGE,
        description="Number of active recovery operations",
        labels=["worker_type"]
    ),

    # Resource metrics
    "memory_usage": MetricDefinition(
        name="worker_memory_usage_bytes",
        metric_type=MetricType.GAUGE,
        description="Current memory usage in bytes",
        labels=["worker_type"]
    ),
    "cpu_usage": MetricDefinition(
        name="worker_cpu_usage_percent",
        metric_type=MetricType.GAUGE,
        description="Current CPU usage percentage",
        labels=["worker_type"]
    ),

    # Kafka consumer metrics
    "consumer_lag": MetricDefinition(
        name="worker_consumer_lag",
        metric_type=MetricType.GAUGE,
        description="Current consumer lag",
        labels=["worker_type", "topic", "partition"]
    ),
    "consumer_offset": MetricDefinition(
        name="worker_consumer_offset",
        metric_type=MetricType.GAUGE,
        description="Current consumer offset",
        labels=["worker_type", "topic", "partition"]
    ),

    # Worker lifecycle metrics
    "worker_info": MetricDefinition(
        name="worker_info",
        metric_type=MetricType.INFO,
        description="Worker information",
        labels=["worker_type", "instance_id", "version", "consumer_group"]
    ),
    "worker_uptime": MetricDefinition(
        name="worker_uptime_seconds",
        metric_type=MetricType.GAUGE,
        description="Worker uptime in seconds",
        labels=["worker_type", "instance_id"]
    ),
    "worker_restarts": MetricDefinition(
        name="worker_restarts_total",
        metric_type=MetricType.COUNTER,
        description="Total number of worker restarts",
        labels=["worker_type", "instance_id"]
    ),
}


# =============================================================================
# UNIFIED METRICS COLLECTOR
# =============================================================================

class WorkerMetricsCollector:
    """
    Unified metrics collector for all worker types.

    Provides:
    - Consistent metric collection across all workers
    - Prometheus export support
    - Redis persistence for distributed metrics
    - Automatic metric aggregation
    """

    def __init__(self, worker_type: WorkerType, instance_id: Optional[str] = None):
        self.worker_type = worker_type
        self.instance_id = instance_id or f"{worker_type.value}-default"
        self.logger = logging.getLogger(f"tradecore.metrics.{worker_type.value}")

        # Initialize Prometheus metrics
        self._metrics: Dict[str, Any] = {}
        self._initialize_prometheus_metrics()

        # Local metric storage for aggregation
        self._local_metrics: Dict[str, Any] = defaultdict(float)
        self._metric_history: Dict[str, List[tuple]] = defaultdict(list)

        # Start time for uptime calculation
        self._start_time = time.time()

        # Redis client for distributed metrics
        self._redis_client = None
        self._redis_namespace = f"worker_metrics:{worker_type.value}:{instance_id}"

    def _initialize_prometheus_metrics(self):
        """Initialize Prometheus metrics based on definitions"""
        for metric_name, definition in STANDARD_WORKER_METRICS.items():
            if definition.metric_type == MetricType.COUNTER:
                self._metrics[metric_name] = Counter(
                    definition.name,
                    definition.description,
                    definition.labels
                )
            elif definition.metric_type == MetricType.GAUGE:
                self._metrics[metric_name] = Gauge(
                    definition.name,
                    definition.description,
                    definition.labels
                )
            elif definition.metric_type == MetricType.HISTOGRAM:
                self._metrics[metric_name] = Histogram(
                    definition.name,
                    definition.description,
                    definition.labels,
                    buckets=definition.buckets or Histogram.DEFAULT_BUCKETS
                )
            elif definition.metric_type == MetricType.SUMMARY:
                self._metrics[metric_name] = Summary(
                    definition.name,
                    definition.description,
                    definition.labels
                )
            elif definition.metric_type == MetricType.INFO:
                self._metrics[metric_name] = Info(
                    definition.name,
                    definition.description
                )

    async def initialize(self):
        """Initialize Redis connection for distributed metrics"""
        try:
            self._redis_client = get_redis_instance()

            # Set worker info
            if "worker_info" in self._metrics:
                self._metrics["worker_info"].info({
                    "worker_type": self.worker_type.value,
                    "instance_id": self.instance_id,
                    "version": "0.8",
                    "consumer_group": f"{self.worker_type.value}-workers"
                })

            # Increment restart counter
            await self._increment_restart_counter()

        except Exception as e:
            self.logger.error(f"Failed to initialize metrics collector: {e}")

    async def _increment_restart_counter(self):
        """Increment the restart counter in Redis"""
        if not self._redis_client:
            return

        try:
            restart_key = f"{self._redis_namespace}:restarts"
            await self._redis_client.incr(restart_key)

            # Update Prometheus metric
            if "worker_restarts" in self._metrics:
                restarts = int(await self._redis_client.get(restart_key) or 0)
                self._metrics["worker_restarts"].labels(
                    worker_type=self.worker_type.value,
                    instance_id=self.instance_id
                ).inc()

        except Exception as e:
            self.logger.error(f"Failed to increment restart counter: {e}")

    def increment_events_processed(self, event_type: str, status: str = "success"):
        """Increment events processed counter"""
        if "events_processed_total" in self._metrics:
            self._metrics["events_processed_total"].labels(
                worker_type=self.worker_type.value,
                event_type=event_type,
                status=status
            ).inc()

        # Update local metrics
        self._local_metrics[f"events_processed_{status}"] += 1

    def record_event_duration(self, event_type: str, duration_seconds: float):
        """Record event processing duration"""
        if "events_processing_duration" in self._metrics:
            self._metrics["events_processing_duration"].labels(
                worker_type=self.worker_type.value,
                event_type=event_type
            ).observe(duration_seconds)

        # Store in history for percentile calculations
        self._metric_history["event_durations"].append((time.time(), duration_seconds))

    def set_events_in_flight(self, count: int):
        """Set number of events currently being processed"""
        if "events_in_flight" in self._metrics:
            self._metrics["events_in_flight"].labels(
                worker_type=self.worker_type.value
            ).set(count)

    def increment_errors(self, error_type: str):
        """Increment error counter"""
        if "errors_total" in self._metrics:
            self._metrics["errors_total"].labels(
                worker_type=self.worker_type.value,
                error_type=error_type
            ).inc()

        self._local_metrics["errors_total"] += 1

    def update_error_rate(self):
        """Calculate and update error rate"""
        total_processed = self._local_metrics.get("events_processed_success", 0)
        total_errors = self._local_metrics.get("errors_total", 0)

        if total_processed + total_errors > 0:
            error_rate = (total_errors / (total_processed + total_errors)) * 100

            if "error_rate" in self._metrics:
                self._metrics["error_rate"].labels(
                    worker_type=self.worker_type.value
                ).set(error_rate)

    def increment_recoveries(self, recovery_type: str, result: str):
        """Increment recovery counter"""
        if "recoveries_triggered_total" in self._metrics:
            self._metrics["recoveries_triggered_total"].labels(
                worker_type=self.worker_type.value,
                recovery_type=recovery_type,
                result=result
            ).inc()

    def record_recovery_duration(self, recovery_type: str, duration_seconds: float):
        """Record recovery operation duration"""
        if "recovery_duration" in self._metrics:
            self._metrics["recovery_duration"].labels(
                worker_type=self.worker_type.value,
                recovery_type=recovery_type
            ).observe(duration_seconds)

    def set_active_recoveries(self, count: int):
        """Set number of active recovery operations"""
        if "active_recoveries" in self._metrics:
            self._metrics["active_recoveries"].labels(
                worker_type=self.worker_type.value
            ).set(count)

    def update_consumer_metrics(self, topic: str, partition: int, lag: int, offset: int):
        """Update Kafka consumer metrics"""
        if "consumer_lag" in self._metrics:
            self._metrics["consumer_lag"].labels(
                worker_type=self.worker_type.value,
                topic=topic,
                partition=str(partition)
            ).set(lag)

        if "consumer_offset" in self._metrics:
            self._metrics["consumer_offset"].labels(
                worker_type=self.worker_type.value,
                topic=topic,
                partition=str(partition)
            ).set(offset)

    def update_resource_metrics(self, memory_bytes: int, cpu_percent: float):
        """Update resource usage metrics"""
        if "memory_usage" in self._metrics:
            self._metrics["memory_usage"].labels(
                worker_type=self.worker_type.value
            ).set(memory_bytes)

        if "cpu_usage" in self._metrics:
            self._metrics["cpu_usage"].labels(
                worker_type=self.worker_type.value
            ).set(cpu_percent)

    def update_uptime(self):
        """Update worker uptime metric"""
        uptime_seconds = time.time() - self._start_time

        if "worker_uptime" in self._metrics:
            self._metrics["worker_uptime"].labels(
                worker_type=self.worker_type.value,
                instance_id=self.instance_id
            ).set(uptime_seconds)

    def update_metrics(self, metrics_dict: Dict[str, Any]):
        """Update multiple metrics at once"""
        for key, value in metrics_dict.items():
            if key == "processed_events":
                self._local_metrics["events_processed_success"] = value
            elif key == "failed_events":
                self._local_metrics["events_processed_failed"] = value
            elif key == "errors":
                self._local_metrics["errors_total"] = value
            elif key == "active_recoveries" and "active_recoveries" in self._metrics:
                self.set_active_recoveries(value)

        # Update derived metrics
        self.update_error_rate()
        self.update_uptime()

    async def persist_metrics(self):
        """Persist current metrics to Redis"""
        if not self._redis_client:
            return

        try:
            # Create metrics snapshot
            snapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "worker_type": self.worker_type.value,
                "instance_id": self.instance_id,
                "uptime_seconds": time.time() - self._start_time,
                "metrics": dict(self._local_metrics)
            }

            # Store in Redis with TTL
            import json
            snapshot_key = f"{self._redis_namespace}:snapshot"
            await self._redis_client.setex(
                snapshot_key,
                3600,  # 1 hour TTL
                json.dumps(snapshot)
            )

            # Store in time series for historical analysis
            ts_key = f"{self._redis_namespace}:timeseries:{int(time.time())}"
            await self._redis_client.setex(
                ts_key,
                86400,  # 24 hour TTL
                json.dumps(snapshot)
            )

        except Exception as e:
            self.logger.error(f"Failed to persist metrics: {e}")

    async def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all instances of this worker type"""
        if not self._redis_client:
            return {}

        try:
            # Get all worker instances
            pattern = f"worker_metrics:{self.worker_type.value}:*:snapshot"
            keys = []

            # Redis SCAN to find all snapshots
            cursor = 0
            while True:
                cursor, batch_keys = await self._redis_client.scan(
                    cursor, match=pattern, count=100
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break

            # Aggregate metrics from all instances
            aggregated = {
                "total_instances": len(keys),
                "total_events_processed": 0,
                "total_errors": 0,
                "total_recoveries": 0,
                "average_uptime": 0,
                "instances": []
            }

            total_uptime = 0

            for key in keys:
                try:
                    import json
                    snapshot_data = await self._redis_client.get(key)
                    if snapshot_data:
                        snapshot = json.loads(snapshot_data)
                        metrics = snapshot.get("metrics", {})

                        aggregated["total_events_processed"] += metrics.get("events_processed_success", 0)
                        aggregated["total_errors"] += metrics.get("errors_total", 0)
                        aggregated["total_recoveries"] += metrics.get("recoveries_triggered", 0)
                        total_uptime += snapshot.get("uptime_seconds", 0)

                        aggregated["instances"].append({
                            "instance_id": snapshot.get("instance_id"),
                            "uptime": snapshot.get("uptime_seconds", 0),
                            "last_update": snapshot.get("timestamp")
                        })

                except Exception as e:
                    self.logger.warning(f"Failed to parse snapshot from {key}: {e}")

            if aggregated["total_instances"] > 0:
                aggregated["average_uptime"] = total_uptime / aggregated["total_instances"]

            return aggregated

        except Exception as e:
            self.logger.error(f"Failed to get aggregated metrics: {e}")
            return {}

    def get_local_metrics(self) -> Dict[str, Any]:
        """Get local metrics for this instance"""
        return {
            "worker_type": self.worker_type.value,
            "instance_id": self.instance_id,
            "uptime_seconds": time.time() - self._start_time,
            "events_processed": self._local_metrics.get("events_processed_success", 0),
            "events_failed": self._local_metrics.get("events_processed_failed", 0),
            "errors_total": self._local_metrics.get("errors_total", 0),
            "error_rate": self._calculate_error_rate(),
            "recoveries_triggered": self._local_metrics.get("recoveries_triggered", 0),
            "last_update": datetime.now(timezone.utc).isoformat()
        }

    def _calculate_error_rate(self) -> float:
        """Calculate current error rate"""
        total_processed = self._local_metrics.get("events_processed_success", 0)
        total_errors = self._local_metrics.get("errors_total", 0)

        if total_processed + total_errors > 0:
            return (total_errors / (total_processed + total_errors)) * 100
        return 0.0

    def cleanup_old_metrics(self, max_age_seconds: int = 86400):
        """Clean up old metrics from history"""
        cutoff_time = time.time() - max_age_seconds

        for metric_name, history in self._metric_history.items():
            self._metric_history[metric_name] = [
                (timestamp, value) for timestamp, value in history
                if timestamp > cutoff_time
            ]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def create_metrics_collector(worker_type: WorkerType,
                                   instance_id: Optional[str] = None) -> WorkerMetricsCollector:
    """Create and initialize a metrics collector"""
    collector = WorkerMetricsCollector(worker_type, instance_id)
    await collector.initialize()
    return collector


def get_worker_metrics_labels(worker_type: WorkerType) -> Dict[str, str]:
    """Get standard labels for worker metrics"""
    return {
        "worker_type": worker_type.value,
        "service": "tradecore",
        "component": "worker"
    }


# Export commonly used items
__all__ = [
    'WorkerMetricsCollector',
    'MetricType',
    'MetricDefinition',
    'STANDARD_WORKER_METRICS',
    'create_metrics_collector',
    'get_worker_metrics_labels',
]