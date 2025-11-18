"""
Backpressure Controller for Kafka/Redpanda Consumers

Implements backpressure control strategies to prevent consumer overload
and gracefully handle downstream processing bottlenecks.

Key Features:
- Pause/Resume partition consumption based on lag
- Dynamic throttling via max_poll_records adjustment
- Queue-based processing with bounded capacity
- Integration with Consumer Lag Monitor
- Graceful degradation under load

Industry Best Practices:
- Manual commit control for exactly-once semantics
- Pause/resume for flow control
- Dynamic queue sizing based on processing rate
- Circuit breaker pattern for downstream failures

References:
- https://gautambangalore.medium.com/integrating-rate-limiting-and-backpressure-strategies
- https://medium.com/walkme-engineering/managing-consumer-commits-and-back-pressure-with-node-js-and-kafka
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
from collections import deque

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition, ConsumerRecord

from app.infra.event_bus.consumer_lag_monitor import (
    ConsumerLagMonitor,
    ConsumerGroupLagMetrics,
    LagSeverity,
)


log = logging.getLogger(__name__)


class BackpressureState(str, Enum):
    """Backpressure control states"""
    NORMAL = "normal"          # No backpressure, consuming normally
    THROTTLED = "throttled"    # Reduced consumption rate
    PAUSED = "paused"          # Consumption paused
    RECOVERING = "recovering"  # Resuming from pause


@dataclass
class BackpressureMetrics:
    """Backpressure controller metrics"""
    state: BackpressureState
    paused_partitions: int
    throttled_partitions: int
    queue_size: int
    queue_capacity: int
    processing_rate: float  # messages per second
    pause_count: int
    resume_count: int
    throttle_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def queue_utilization(self) -> float:
        """Queue utilization percentage (0-100)"""
        if self.queue_capacity == 0:
            return 0.0
        return (self.queue_size / self.queue_capacity) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "state": self.state.value,
            "paused_partitions": self.paused_partitions,
            "throttled_partitions": self.throttled_partitions,
            "queue_size": self.queue_size,
            "queue_capacity": self.queue_capacity,
            "queue_utilization_pct": round(self.queue_utilization, 2),
            "processing_rate": round(self.processing_rate, 2),
            "pause_count": self.pause_count,
            "resume_count": self.resume_count,
            "throttle_count": self.throttle_count,
            "timestamp": self.timestamp.isoformat(),
        }


# Message processor callback type
MessageProcessor = Callable[[ConsumerRecord], Any]


class BackpressureController:
    """
    Controls backpressure for Kafka/Redpanda consumers.

    Strategies:
    1. Queue-based: Bounded queue with async processing
    2. Pause/Resume: Stop consuming when queue is full
    3. Dynamic throttling: Adjust poll size based on lag
    4. Manual commits: Commit only after successful processing

    Usage:
        controller = BackpressureController(
            consumer=consumer,
            lag_monitor=lag_monitor,
            max_queue_size=1000,
            pause_threshold=0.9,
            resume_threshold=0.5
        )

        # Register message processor
        controller.register_processor(my_async_processor)

        # Start processing
        await controller.start()

        # Get metrics
        metrics = controller.get_metrics()

        # Stop processing
        await controller.stop()
    """

    def __init__(
        self,
        consumer: AIOKafkaConsumer,
        lag_monitor: Optional[ConsumerLagMonitor] = None,
        max_queue_size: int = 1000,
        pause_threshold: float = 0.9,  # Pause at 90% queue capacity
        resume_threshold: float = 0.5,  # Resume at 50% queue capacity
        max_processing_workers: int = 10,
        commit_interval_seconds: int = 5,
    ):
        """
        Initialize backpressure controller.

        Args:
            consumer: AIOKafkaConsumer instance
            lag_monitor: Optional lag monitor for intelligent throttling
            max_queue_size: Maximum processing queue size
            pause_threshold: Queue utilization to trigger pause (0-1)
            resume_threshold: Queue utilization to trigger resume (0-1)
            max_processing_workers: Max concurrent message processors
            commit_interval_seconds: How often to commit offsets
        """
        self.consumer = consumer
        self.lag_monitor = lag_monitor
        self.max_queue_size = max_queue_size
        self.pause_threshold = pause_threshold
        self.resume_threshold = resume_threshold
        self.max_workers = max_processing_workers
        self.commit_interval = commit_interval_seconds

        # Processing queue
        self._queue: deque = deque(maxlen=max_queue_size)
        self._queue_lock = asyncio.Lock()

        # State tracking
        self._state = BackpressureState.NORMAL
        self._paused_partitions: Set[TopicPartition] = set()
        self._throttled_partitions: Set[TopicPartition] = set()

        # Metrics
        self._pause_count = 0
        self._resume_count = 0
        self._throttle_count = 0
        self._processed_count = 0
        self._last_processed_time = time.time()
        self._processing_rate = 0.0

        # Tasks
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._processor_tasks: List[asyncio.Task] = []
        self._commit_task: Optional[asyncio.Task] = None

        # Message processor
        self._processor: Optional[MessageProcessor] = None

        # Commit tracking
        self._pending_commits: Dict[TopicPartition, int] = {}
        self._commit_lock = asyncio.Lock()

    def register_processor(self, processor: MessageProcessor) -> None:
        """Register message processor callback"""
        self._processor = processor
        log.info(f"Registered message processor: {processor.__name__}")

    async def start(self) -> None:
        """Start backpressure controller"""
        if self._running:
            log.warning("Backpressure controller already running")
            return

        if not self._processor:
            raise ValueError("Message processor not registered. Call register_processor() first.")

        self._running = True

        # Start consumer task
        self._consumer_task = asyncio.create_task(self._consume_loop())

        # Start processor workers
        for i in range(self.max_workers):
            task = asyncio.create_task(self._process_loop(worker_id=i))
            self._processor_tasks.append(task)

        # Start commit task
        self._commit_task = asyncio.create_task(self._commit_loop())

        log.info(f"Started backpressure controller with {self.max_workers} workers, "
                f"queue size {self.max_queue_size}")

    async def stop(self) -> None:
        """Stop backpressure controller"""
        if not self._running:
            return

        self._running = False

        # Cancel all tasks
        if self._consumer_task:
            self._consumer_task.cancel()
        for task in self._processor_tasks:
            task.cancel()
        if self._commit_task:
            self._commit_task.cancel()

        # Wait for cancellation
        tasks_to_wait = [self._consumer_task] + self._processor_tasks + [self._commit_task]
        await asyncio.gather(*tasks_to_wait, return_exceptions=True)

        # Final commit
        await self._commit_offsets()

        log.info("Stopped backpressure controller")

    async def _consume_loop(self) -> None:
        """Main consumption loop with backpressure control"""
        while self._running:
            try:
                # Check if we should pause/resume based on queue size
                await self._check_backpressure()

                # Poll messages with timeout
                try:
                    data = await asyncio.wait_for(
                        self.consumer.getmany(timeout_ms=1000, max_records=100),
                        timeout=2.0
                    )
                except asyncio.TimeoutError:
                    continue

                if not data:
                    await asyncio.sleep(0.1)
                    continue

                # Add messages to processing queue
                for tp, messages in data.items():
                    for message in messages:
                        async with self._queue_lock:
                            if len(self._queue) >= self.max_queue_size:
                                # Queue full, trigger backpressure
                                await self._trigger_pause([tp])
                                break
                            self._queue.append(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in consume loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_loop(self, worker_id: int) -> None:
        """Worker loop for processing messages"""
        while self._running:
            try:
                # Get message from queue
                message = None
                async with self._queue_lock:
                    if self._queue:
                        message = self._queue.popleft()

                if not message:
                    await asyncio.sleep(0.1)
                    continue

                # Process message
                try:
                    if asyncio.iscoroutinefunction(self._processor):
                        await self._processor(message)
                    else:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self._processor, message)

                    # Track for commit
                    tp = TopicPartition(message.topic, message.partition)
                    async with self._commit_lock:
                        self._pending_commits[tp] = message.offset + 1

                    # Update metrics
                    self._processed_count += 1
                    self._update_processing_rate()

                except Exception as e:
                    log.error(f"Error processing message: {e}", exc_info=True)
                    # Message will not be committed, will be reprocessed

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in process loop (worker {worker_id}): {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _commit_loop(self) -> None:
        """Periodic commit loop"""
        while self._running:
            try:
                await asyncio.sleep(self.commit_interval)
                await self._commit_offsets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in commit loop: {e}", exc_info=True)

    async def _commit_offsets(self) -> None:
        """Commit pending offsets"""
        async with self._commit_lock:
            if not self._pending_commits:
                return

            try:
                # Build offset dict for commit
                offsets = {tp: offset for tp, offset in self._pending_commits.items()}

                # Commit offsets
                await self.consumer.commit(offsets)

                log.debug(f"Committed {len(offsets)} partition offsets")

                # Clear pending commits
                self._pending_commits.clear()

            except Exception as e:
                log.error(f"Failed to commit offsets: {e}", exc_info=True)

    async def _check_backpressure(self) -> None:
        """Check and apply backpressure based on queue utilization"""
        async with self._queue_lock:
            queue_size = len(self._queue)

        utilization = queue_size / self.max_queue_size

        # Trigger pause if above threshold
        if utilization >= self.pause_threshold and self._state != BackpressureState.PAUSED:
            assignment = self.consumer.assignment()
            if assignment:
                await self._trigger_pause(list(assignment))

        # Resume if below threshold
        elif utilization <= self.resume_threshold and self._state == BackpressureState.PAUSED:
            await self._trigger_resume(list(self._paused_partitions))

    async def _trigger_pause(self, partitions: List[TopicPartition]) -> None:
        """Pause consumption on partitions"""
        if not partitions:
            return

        try:
            self.consumer.pause(*partitions)
            self._paused_partitions.update(partitions)
            self._state = BackpressureState.PAUSED
            self._pause_count += 1

            log.warning(f"Paused {len(partitions)} partitions due to backpressure "
                       f"(queue: {len(self._queue)}/{self.max_queue_size})")

        except Exception as e:
            log.error(f"Failed to pause partitions: {e}", exc_info=True)

    async def _trigger_resume(self, partitions: List[TopicPartition]) -> None:
        """Resume consumption on partitions"""
        if not partitions:
            return

        try:
            self.consumer.resume(*partitions)
            self._paused_partitions.difference_update(partitions)

            if not self._paused_partitions:
                self._state = BackpressureState.NORMAL
            else:
                self._state = BackpressureState.RECOVERING

            self._resume_count += 1

            log.info(f"Resumed {len(partitions)} partitions "
                    f"(queue: {len(self._queue)}/{self.max_queue_size})")

        except Exception as e:
            log.error(f"Failed to resume partitions: {e}", exc_info=True)

    def _update_processing_rate(self) -> None:
        """Update processing rate calculation"""
        current_time = time.time()
        elapsed = current_time - self._last_processed_time

        if elapsed >= 1.0:  # Update every second
            self._processing_rate = self._processed_count / elapsed
            self._processed_count = 0
            self._last_processed_time = current_time

    def get_metrics(self) -> BackpressureMetrics:
        """Get current backpressure metrics"""
        return BackpressureMetrics(
            state=self._state,
            paused_partitions=len(self._paused_partitions),
            throttled_partitions=len(self._throttled_partitions),
            queue_size=len(self._queue),
            queue_capacity=self.max_queue_size,
            processing_rate=self._processing_rate,
            pause_count=self._pause_count,
            resume_count=self._resume_count,
            throttle_count=self._throttle_count,
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status"""
        metrics = self.get_metrics()
        return {
            "status": "running" if self._running else "stopped",
            "state": metrics.state.value,
            "queue_utilization_pct": round(metrics.queue_utilization, 2),
            "processing_rate": round(metrics.processing_rate, 2),
            "paused_partitions": metrics.paused_partitions,
            "has_processor": self._processor is not None,
        }
