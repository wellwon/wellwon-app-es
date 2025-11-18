# app/infra/metrics/dlq_metrics.py
"""
DLQ Service metrics collection and monitoring
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
import logging

log = logging.getLogger("wellwon.metrics.dlq")


@dataclass
class DLQMetricsSummary:
    """Summary of DLQ metrics over a time period"""
    period_start: datetime
    period_end: datetime
    total_received: int = 0
    total_processed: int = 0
    total_dropped: int = 0
    total_errors: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    average_batch_size: float = 0.0
    average_processing_time_ms: float = 0.0
    queue_high_watermark: int = 0
    emergency_persist_count: int = 0


class DLQMetricsCollector:
    """
    Centralized DLQ metrics collection with advanced analytics
    """

    def __init__(self):
        self._start_time = time.time()
        self._metrics_history: Dict[int, DLQMetricsSummary] = {}  # hour -> summary
        self._current_hour_metrics: Optional[DLQMetricsSummary] = None
        self._processing_times: list[float] = []
        self._batch_sizes: list[int] = []

        # Real-time counters
        self._total_received = 0
        self._total_processed = 0
        self._total_dropped = 0
        self._total_errors = 0
        self._by_source: Dict[str, int] = {}
        self._by_category: Dict[str, int] = {}
        self._by_reason: Dict[str, int] = {}

        # Performance metrics
        self._queue_high_watermark = 0
        self._emergency_persists = 0
        self._last_flush_time: Optional[datetime] = None
        self._kafka_forwarding_errors = 0
        self._db_persistence_errors = 0

        # Rate metrics
        self._events_per_second_history: list[float] = []
        self._last_rate_calculation = time.time()
        self._last_event_count = 0

        # Alert thresholds
        self._drop_rate_threshold = 0.05  # 5% drop rate
        self._error_rate_threshold = 0.01  # 1% error rate
        self._queue_usage_threshold = 0.8  # 80% queue usage

    def record_event_received(self, source: str, category: str) -> None:
        """Record a new event received by DLQ"""
        self._total_received += 1
        self._by_source[source] = self._by_source.get(source, 0) + 1
        self._by_category[category] = self._by_category.get(category, 0) + 1
        self._update_current_hour_metrics()

    def record_event_processed(self) -> None:
        """Record successful event processing"""
        self._total_processed += 1
        self._update_current_hour_metrics()

    def record_event_dropped(self) -> None:
        """Record dropped event"""
        self._total_dropped += 1
        self._update_current_hour_metrics()

    def record_error(self) -> None:
        """Record processing error"""
        self._total_errors += 1
        self._update_current_hour_metrics()

    def record_batch_processed(self, batch_size: int, processing_time_ms: float) -> None:
        """Record batch processing metrics"""
        self._batch_sizes.append(batch_size)
        self._processing_times.append(processing_time_ms)

        # Keep only last 1000 measurements
        if len(self._batch_sizes) > 1000:
            self._batch_sizes = self._batch_sizes[-1000:]
        if len(self._processing_times) > 1000:
            self._processing_times = self._processing_times[-1000:]

        self._last_flush_time = datetime.now(timezone.utc)

    def update_queue_high_watermark(self, queue_size: int) -> None:
        """Update queue high watermark"""
        if queue_size > self._queue_high_watermark:
            self._queue_high_watermark = queue_size

    def record_emergency_persist(self) -> None:
        """Record emergency persist event"""
        self._emergency_persists += 1

    def record_kafka_error(self) -> None:
        """Record Kafka forwarding error"""
        self._kafka_forwarding_errors += 1

    def record_db_error(self) -> None:
        """Record database persistence error"""
        self._db_persistence_errors += 1

    def _update_current_hour_metrics(self) -> None:
        """Update current hour metrics"""
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        if not self._current_hour_metrics or self._current_hour_metrics.period_start != current_hour:
            # Save previous hour metrics
            if self._current_hour_metrics:
                hour_key = int(self._current_hour_metrics.period_start.timestamp())
                self._metrics_history[hour_key] = self._current_hour_metrics

                # Keep only last 24 hours
                cutoff = time.time() - (24 * 3600)
                self._metrics_history = {
                    k: v for k, v in self._metrics_history.items()
                    if k > cutoff
                }

            # Start new hour
            self._current_hour_metrics = DLQMetricsSummary(
                period_start=current_hour,
                period_end=current_hour.replace(hour=current_hour.hour + 1)
            )

        # Update current hour metrics
        if self._current_hour_metrics:
            self._current_hour_metrics.total_received = self._total_received
            self._current_hour_metrics.total_processed = self._total_processed
            self._current_hour_metrics.total_dropped = self._total_dropped
            self._current_hour_metrics.total_errors = self._total_errors
            self._current_hour_metrics.by_source = self._by_source.copy()
            self._current_hour_metrics.by_category = self._by_category.copy()
            self._current_hour_metrics.queue_high_watermark = self._queue_high_watermark
            self._current_hour_metrics.emergency_persist_count = self._emergency_persists

            if self._batch_sizes:
                self._current_hour_metrics.average_batch_size = sum(self._batch_sizes) / len(self._batch_sizes)
            if self._processing_times:
                self._current_hour_metrics.average_processing_time_ms = sum(self._processing_times) / len(
                    self._processing_times)

    def calculate_rates(self) -> Dict[str, float]:
        """Calculate current rates"""
        current_time = time.time()
        time_diff = current_time - self._last_rate_calculation

        if time_diff > 0:
            event_diff = self._total_received - self._last_event_count
            events_per_second = event_diff / time_diff

            self._events_per_second_history.append(events_per_second)
            if len(self._events_per_second_history) > 60:  # Keep last minute
                self._events_per_second_history = self._events_per_second_history[-60:]

            self._last_rate_calculation = current_time
            self._last_event_count = self._total_received

        # Calculate rates
        drop_rate = self._total_dropped / self._total_received if self._total_received > 0 else 0
        error_rate = self._total_errors / self._total_received if self._total_received > 0 else 0
        success_rate = self._total_processed / self._total_received if self._total_received > 0 else 0

        avg_events_per_second = (
            sum(self._events_per_second_history) / len(self._events_per_second_history)
            if self._events_per_second_history else 0
        )

        return {
            "drop_rate": drop_rate,
            "error_rate": error_rate,
            "success_rate": success_rate,
            "events_per_second": avg_events_per_second,
            "events_per_minute": avg_events_per_second * 60,
            "events_per_hour": avg_events_per_second * 3600
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        rates = self.calculate_rates()
        uptime_seconds = time.time() - self._start_time

        return {
            "uptime_seconds": uptime_seconds,
            "total_received": self._total_received,
            "total_processed": self._total_processed,
            "total_dropped": self._total_dropped,
            "total_errors": self._total_errors,
            "by_source": dict(self._by_source),
            "by_category": dict(self._by_category),
            "by_reason": dict(self._by_reason),
            "rates": rates,
            "performance": {
                "average_batch_size": sum(self._batch_sizes) / len(self._batch_sizes) if self._batch_sizes else 0,
                "average_processing_time_ms": sum(self._processing_times) / len(
                    self._processing_times) if self._processing_times else 0,
                "queue_high_watermark": self._queue_high_watermark,
                "emergency_persists": self._emergency_persists,
                "last_flush_time": self._last_flush_time.isoformat() if self._last_flush_time else None
            },
            "errors": {
                "kafka_forwarding_errors": self._kafka_forwarding_errors,
                "db_persistence_errors": self._db_persistence_errors,
                "total_errors": self._total_errors
            }
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with alerts"""
        rates = self.calculate_rates()
        alerts = []

        # Check drop rate
        if rates["drop_rate"] > self._drop_rate_threshold:
            alerts.append({
                "level": "critical",
                "message": f"High drop rate: {rates['drop_rate']:.2%}",
                "threshold": f"{self._drop_rate_threshold:.2%}"
            })

        # Check error rate
        if rates["error_rate"] > self._error_rate_threshold:
            alerts.append({
                "level": "warning",
                "message": f"High error rate: {rates['error_rate']:.2%}",
                "threshold": f"{self._error_rate_threshold:.2%}"
            })

        # Check for recent errors
        if self._kafka_forwarding_errors > 10:
            alerts.append({
                "level": "warning",
                "message": f"Kafka forwarding errors: {self._kafka_forwarding_errors}",
                "threshold": "10"
            })

        if self._db_persistence_errors > 5:
            alerts.append({
                "level": "critical",
                "message": f"Database persistence errors: {self._db_persistence_errors}",
                "threshold": "5"
            })

        # Overall health
        is_healthy = len([a for a in alerts if a["level"] == "critical"]) == 0

        return {
            "healthy": is_healthy,
            "alerts": alerts,
            "metrics": self.get_metrics()
        }

    def get_hourly_summary(self, hours: int = 24) -> list[DLQMetricsSummary]:
        """Get hourly summaries for the last N hours"""
        summaries = []
        cutoff = time.time() - (hours * 3600)

        for timestamp, summary in sorted(self._metrics_history.items()):
            if timestamp > cutoff:
                summaries.append(summary)

        # Add current hour if exists
        if self._current_hour_metrics:
            summaries.append(self._current_hour_metrics)

        return summaries

    def reset_metrics(self) -> None:
        """Reset all metrics (for testing)"""
        log.warning("Resetting DLQ metrics")
        self.__init__()


# Global instance
_dlq_metrics_collector: Optional[DLQMetricsCollector] = None


def get_dlq_metrics() -> DLQMetricsCollector:
    """Get or create global DLQ metrics collector"""
    global _dlq_metrics_collector
    if _dlq_metrics_collector is None:
        _dlq_metrics_collector = DLQMetricsCollector()
    return _dlq_metrics_collector


def reset_dlq_metrics() -> None:
    """Reset global DLQ metrics (mainly for testing)"""
    global _dlq_metrics_collector
    if _dlq_metrics_collector:
        _dlq_metrics_collector.reset_metrics()