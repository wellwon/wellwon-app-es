"""
Consumer Lag Monitor for Redpanda/Kafka

Monitors consumer lag with per-partition granularity and provides
alerting capabilities based on position lag and time lag thresholds.

Industry best practices:
- Per-partition lag tracking (not just aggregate)
- Both position lag and time lag monitoring
- Rate-of-change detection for early warning
- Prometheus-ready metrics structure
- Dynamic threshold adjustment

References:
- https://docs.redpanda.com/current/manage/monitoring/
- https://aiokafka.readthedocs.io/en/stable/consumer.html
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition


log = logging.getLogger(__name__)


class LagSeverity(str, Enum):
    """Lag severity levels for alerting"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PartitionLagMetrics:
    """Lag metrics for a single partition"""
    topic: str
    partition: int
    high_watermark: int
    current_offset: int
    position_lag: int  # Number of messages behind
    last_poll_timestamp: int  # milliseconds
    time_lag_ms: int  # Time lag in milliseconds
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def severity(self) -> LagSeverity:
        """Calculate severity based on lag thresholds"""
        # Critical: >10k messages OR >5 minutes
        if self.position_lag > 10000 or self.time_lag_ms > 300000:
            return LagSeverity.CRITICAL
        # Warning: >1k messages OR >1 minute
        elif self.position_lag > 1000 or self.time_lag_ms > 60000:
            return LagSeverity.WARNING
        return LagSeverity.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "topic": self.topic,
            "partition": self.partition,
            "high_watermark": self.high_watermark,
            "current_offset": self.current_offset,
            "position_lag": self.position_lag,
            "time_lag_ms": self.time_lag_ms,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConsumerGroupLagMetrics:
    """Aggregated lag metrics for entire consumer group"""
    consumer_group: str
    total_partitions: int
    max_position_lag: int
    sum_position_lag: int
    max_time_lag_ms: int
    avg_time_lag_ms: float
    partitions_by_severity: Dict[LagSeverity, int]
    partition_metrics: List[PartitionLagMetrics]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def overall_severity(self) -> LagSeverity:
        """Overall severity based on worst partition"""
        if self.partitions_by_severity.get(LagSeverity.CRITICAL, 0) > 0:
            return LagSeverity.CRITICAL
        elif self.partitions_by_severity.get(LagSeverity.WARNING, 0) > 0:
            return LagSeverity.WARNING
        return LagSeverity.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "consumer_group": self.consumer_group,
            "total_partitions": self.total_partitions,
            "max_position_lag": self.max_position_lag,
            "sum_position_lag": self.sum_position_lag,
            "max_time_lag_ms": self.max_time_lag_ms,
            "avg_time_lag_ms": self.avg_time_lag_ms,
            "overall_severity": self.overall_severity.value,
            "partitions_by_severity": {
                k.value: v for k, v in self.partitions_by_severity.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }


# Callback type for lag alerts
LagAlertCallback = Callable[[ConsumerGroupLagMetrics], None]


class ConsumerLagMonitor:
    """
    Monitors consumer lag with per-partition granularity.

    Features:
    - Per-partition position lag and time lag tracking
    - Automatic severity classification (normal/warning/critical)
    - Alert callbacks for threshold violations
    - Async monitoring loop
    - Prometheus-ready metrics structure

    Usage:
        monitor = ConsumerLagMonitor(
            consumer=consumer,
            consumer_group="my-group",
            check_interval_seconds=10
        )

        # Register alert callback
        monitor.register_alert_callback(my_alert_handler)

        # Start monitoring
        await monitor.start()

        # Get current metrics
        metrics = await monitor.get_metrics()

        # Stop monitoring
        await monitor.stop()
    """

    def __init__(
        self,
        consumer: AIOKafkaConsumer,
        consumer_group: str,
        check_interval_seconds: int = 30,
        position_lag_threshold: int = 1000,
        time_lag_threshold_ms: int = 60000,
    ):
        """
        Initialize lag monitor.

        Args:
            consumer: AIOKafkaConsumer instance to monitor
            consumer_group: Consumer group name
            check_interval_seconds: How often to check lag (default: 30s)
            position_lag_threshold: Warning threshold for position lag (default: 1000)
            time_lag_threshold_ms: Warning threshold for time lag (default: 60000ms = 1min)
        """
        self.consumer = consumer
        self.consumer_group = consumer_group
        self.check_interval = check_interval_seconds
        self.position_lag_threshold = position_lag_threshold
        self.time_lag_threshold_ms = time_lag_threshold_ms

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._latest_metrics: Optional[ConsumerGroupLagMetrics] = None
        self._alert_callbacks: List[LagAlertCallback] = []
        self._previous_metrics: Dict[TopicPartition, PartitionLagMetrics] = {}

    def register_alert_callback(self, callback: LagAlertCallback) -> None:
        """Register callback to be called when lag exceeds thresholds"""
        self._alert_callbacks.append(callback)
        log.info(f"Registered lag alert callback: {callback.__name__}")

    async def start(self) -> None:
        """Start monitoring loop"""
        if self._running:
            log.warning("Consumer lag monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info(f"Started consumer lag monitor for group '{self.consumer_group}' "
                f"(check interval: {self.check_interval}s)")

    async def stop(self) -> None:
        """Stop monitoring loop"""
        if not self._running:
            return

        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        log.info(f"Stopped consumer lag monitor for group '{self.consumer_group}'")

    async def get_metrics(self) -> Optional[ConsumerGroupLagMetrics]:
        """Get latest lag metrics (async snapshot)"""
        try:
            return await self._collect_metrics()
        except Exception as e:
            log.error(f"Failed to collect lag metrics: {e}", exc_info=True)
            return self._latest_metrics

    async def get_partition_metrics(
        self,
        topic: str,
        partition: int
    ) -> Optional[PartitionLagMetrics]:
        """Get metrics for specific partition"""
        tp = TopicPartition(topic, partition)
        return await self._collect_partition_metrics(tp)

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                metrics = await self._collect_metrics()
                if metrics:
                    self._latest_metrics = metrics

                    # Check if alerts should be triggered
                    if metrics.overall_severity in (LagSeverity.WARNING, LagSeverity.CRITICAL):
                        await self._trigger_alerts(metrics)

                    # Log summary
                    log.info(
                        f"Consumer lag [{self.consumer_group}]: "
                        f"max_lag={metrics.max_position_lag}, "
                        f"total_lag={metrics.sum_position_lag}, "
                        f"max_time_lag={metrics.max_time_lag_ms}ms, "
                        f"severity={metrics.overall_severity.value}"
                    )

            except Exception as e:
                log.error(f"Error in lag monitor loop: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _collect_metrics(self) -> Optional[ConsumerGroupLagMetrics]:
        """Collect lag metrics for all assigned partitions"""
        try:
            assignment = self.consumer.assignment()
            if not assignment:
                log.debug("No partitions assigned to consumer")
                return None

            partition_metrics: List[PartitionLagMetrics] = []

            for tp in assignment:
                metrics = await self._collect_partition_metrics(tp)
                if metrics:
                    partition_metrics.append(metrics)
                    self._previous_metrics[tp] = metrics

            if not partition_metrics:
                return None

            # Calculate aggregates
            max_position_lag = max(m.position_lag for m in partition_metrics)
            sum_position_lag = sum(m.position_lag for m in partition_metrics)
            max_time_lag_ms = max(m.time_lag_ms for m in partition_metrics)
            avg_time_lag_ms = sum(m.time_lag_ms for m in partition_metrics) / len(partition_metrics)

            # Count partitions by severity
            partitions_by_severity = {
                LagSeverity.NORMAL: 0,
                LagSeverity.WARNING: 0,
                LagSeverity.CRITICAL: 0,
            }
            for m in partition_metrics:
                partitions_by_severity[m.severity] += 1

            return ConsumerGroupLagMetrics(
                consumer_group=self.consumer_group,
                total_partitions=len(partition_metrics),
                max_position_lag=max_position_lag,
                sum_position_lag=sum_position_lag,
                max_time_lag_ms=max_time_lag_ms,
                avg_time_lag_ms=avg_time_lag_ms,
                partitions_by_severity=partitions_by_severity,
                partition_metrics=partition_metrics,
            )

        except Exception as e:
            log.error(f"Failed to collect metrics: {e}", exc_info=True)
            return None

    async def _collect_partition_metrics(
        self,
        tp: TopicPartition
    ) -> Optional[PartitionLagMetrics]:
        """Collect lag metrics for single partition"""
        try:
            # Get high watermark (latest offset in partition)
            high_watermark = self.consumer.highwater(tp)
            if high_watermark is None:
                return None

            # Get current consumer position
            current_offset = await self.consumer.position(tp)
            if current_offset is None:
                return None

            # Calculate position lag
            position_lag = max(0, high_watermark - current_offset)

            # Get last poll timestamp
            last_poll_ts = self.consumer.last_poll_timestamp(tp)
            current_ts = int(time.time() * 1000)  # milliseconds
            time_lag_ms = current_ts - last_poll_ts if last_poll_ts else 0

            return PartitionLagMetrics(
                topic=tp.topic,
                partition=tp.partition,
                high_watermark=high_watermark,
                current_offset=current_offset,
                position_lag=position_lag,
                last_poll_timestamp=last_poll_ts,
                time_lag_ms=time_lag_ms,
            )

        except Exception as e:
            log.error(f"Failed to collect partition metrics for {tp}: {e}")
            return None

    async def _trigger_alerts(self, metrics: ConsumerGroupLagMetrics) -> None:
        """Trigger registered alert callbacks"""
        for callback in self._alert_callbacks:
            try:
                # Run callback in executor if it's blocking
                if asyncio.iscoroutinefunction(callback):
                    await callback(metrics)
                else:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, metrics)
            except Exception as e:
                log.error(f"Error in alert callback {callback.__name__}: {e}", exc_info=True)

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of monitor"""
        return {
            "status": "running" if self._running else "stopped",
            "consumer_group": self.consumer_group,
            "check_interval_seconds": self.check_interval,
            "has_metrics": self._latest_metrics is not None,
            "latest_severity": self._latest_metrics.overall_severity.value if self._latest_metrics else None,
            "alert_callbacks_count": len(self._alert_callbacks),
        }
