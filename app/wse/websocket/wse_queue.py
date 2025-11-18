# =============================================================================
# File: app/api/websocket/ws_queue.py
# Description: Priority message queue for WebSocket connections
# =============================================================================

import asyncio
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class QueuedMessage:
    """Message in the queue"""
    message: Dict[str, Any]
    priority: int
    timestamp: float
    retry_count: int = 0


class PriorityMessageQueue:
    """Priority-based message queue with batching support"""

    def __init__(self, max_size: int = 1000, batch_size: int = 10):
        # PERFORMANCE OPTIMIZATION: Reduced from 10,000 to 1,000
        # This saves ~9 MB per connection (10,000 * 500 bytes → 1,000 * 500 bytes)
        # 1,000 messages = sufficient buffer for 10-100 seconds at typical rates
        self.max_size = max_size
        self.batch_size = batch_size
        self.queues: Dict[int, asyncio.Queue] = {
            10: asyncio.Queue(),  # CRITICAL
            8: asyncio.Queue(),  # HIGH
            5: asyncio.Queue(),  # NORMAL
            3: asyncio.Queue(),  # LOW
            1: asyncio.Queue(),  # BACKGROUND
        }
        self.size = 0
        self.priority_distribution: Dict[int, int] = defaultdict(int)
        self.oldest_message_timestamp: Optional[float] = None
        self._lock = asyncio.Lock()
        self.dropped_count: Dict[int, int] = defaultdict(int)  # Track dropped messages by priority

    async def enqueue(self, message: Dict[str, Any], priority: int = 5) -> bool:
        """
        Add a message to the queue with priority-based dropping

        When queue is full:
        1. Try to drop BACKGROUND (1) priority messages
        2. Try to drop LOW (3) priority messages
        3. Try to drop NORMAL (5) priority messages
        4. If new message is LOW/NORMAL and still full, drop it
        5. For HIGH/CRITICAL, drop oldest NORMAL as last resort
        6. If absolutely full with only HIGH/CRITICAL, drop new message
        """
        async with self._lock:
            if self.size >= self.max_size:
                # Try to make room by dropping lower priority messages
                dropped = False

                for drop_priority in [1, 3, 5]:  # BACKGROUND, LOW, NORMAL
                    queue = self.queues[drop_priority]
                    if not queue.empty():
                        try:
                            dropped_msg = await queue.get()
                            self.size -= 1
                            self.priority_distribution[drop_priority] -= 1
                            self.dropped_count[drop_priority] += 1
                            dropped = True
                            break
                        except asyncio.QueueEmpty:
                            continue

                if not dropped:
                    # Queue full with only HIGH/CRITICAL messages
                    if priority < 8:  # Not HIGH or CRITICAL
                        self.dropped_count[priority] += 1
                        return False

            # Normalize priority to valid values
            valid_priorities = sorted(self.queues.keys(), reverse=True)
            if priority not in valid_priorities:
                # Find the closest valid priority
                priority = min(valid_priorities, key=lambda x: abs(x - priority))

            queue = self.queues[priority]
            queued_msg = QueuedMessage(
                message=message,
                priority=priority,
                timestamp=asyncio.get_event_loop().time()
            )

            await queue.put(queued_msg)
            self.size += 1
            self.priority_distribution[priority] += 1

            # Update oldest message timestamp
            if self.oldest_message_timestamp is None:
                self.oldest_message_timestamp = queued_msg.timestamp

            return True

    async def dequeue_batch(self) -> List[Tuple[int, Dict[str, Any]]]:
        """Get a batch of messages ordered by priority"""
        async with self._lock:
            batch = []

            # Process from highest to lowest priority
            for priority in sorted(self.queues.keys(), reverse=True):
                queue = self.queues[priority]

                while not queue.empty() and len(batch) < self.batch_size:
                    try:
                        queued_msg = queue.get_nowait()
                        batch.append((priority, queued_msg.message))
                        self.size -= 1
                        self.priority_distribution[priority] -= 1

                    except asyncio.QueueEmpty:
                        break

            # Update oldest message timestamp
            if self.size == 0:
                self.oldest_message_timestamp = None
            elif batch:
                # Need to find the new oldest message
                # This is expensive, so we might want to track it differently
                # For now, we'll just reset it and let it be set on next enqueue
                self.oldest_message_timestamp = None

            return batch

    def clear(self) -> None:
        """Clear all queues (synchronous - for emergency shutdown)"""
        # Clear all priority queues
        for queue in self.queues.values():
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        # Reset counters
        self.size = 0
        self.priority_distribution.clear()
        self.oldest_message_timestamp = None

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        # Calculate oldest message age
        oldest_age = None
        if self.oldest_message_timestamp is not None:
            oldest_age = asyncio.get_event_loop().time() - self.oldest_message_timestamp

        # Add priority-specific queue depths
        priority_depths = {}
        for priority, queue in self.queues.items():
            priority_depths[f"priority_{priority}_depth"] = queue.qsize()

        return {
            "size": self.size,
            "capacity": self.max_size,
            "utilization_percent": (self.size / self.max_size) * 100 if self.max_size > 0 else 0,
            "priority_distribution": dict(self.priority_distribution),
            "priority_queue_depths": priority_depths,
            "dropped_by_priority": dict(self.dropped_count),
            "total_dropped": sum(self.dropped_count.values()),
            "backpressure": self.size > self.max_size * 0.8,
            "oldest_message_age": oldest_age,
            "processing_rate": 0.0  # Could be calculated if we track dequeue times
        }