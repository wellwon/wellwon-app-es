# =============================================================================
# File: app/api/websocket/ws_event_sequencer.py
# Description: Event sequencing and deduplication for WebSocket connections
# =============================================================================

import asyncio
from typing import Set, Dict, Optional, Deque, Any, List
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

log = logging.getLogger("tradecore.wse_event_sequencer")


@dataclass
class SequencedEvent:
    """Event with sequence information"""
    event_id: str
    sequence: int
    timestamp: datetime
    topic: str
    payload: Dict[str, Any]


class EventSequencer:
    """Enhanced event sequencer with frontend compatibility"""

    def __init__(self, window_size: int = 10000, max_out_of_order: int = 100):
        self.sequence = 0
        self.seen_ids: Set[str] = set()
        self.seen_ids_queue: Deque[str] = deque(maxlen=window_size)
        self.window_size = window_size
        self.max_out_of_order = max_out_of_order

        # For handling out-of-order events
        self.expected_sequences: Dict[str, int] = {}  # topic -> expected seq
        self.buffered_events: Dict[str, Dict[int, SequencedEvent]] = {}  # topic -> {seq: event}

        # Stats tracking (for frontend compatibility)
        self.duplicate_count = 0
        self.out_of_order_count = 0
        self.dropped_count = 0

        self._lock = asyncio.Lock()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def get_next_sequence(self) -> int:
        """Get the next sequence number"""
        async with self._lock:
            self.sequence += 1
            return self.sequence

    def get_current_sequence(self) -> int:
        """Get the current sequence number without incrementing"""
        return self.sequence

    async def is_duplicate(self, event_id: str) -> bool:
        """Check if an event is duplicate within the window"""
        async with self._lock:
            if event_id in self.seen_ids:
                self.duplicate_count += 1
                return True

            self.seen_ids.add(event_id)
            self.seen_ids_queue.append(event_id)

            # Clean up old IDs when the queue is full
            if len(self.seen_ids_queue) >= self.window_size:
                # Remove the oldest ID from a set
                old_id = self.seen_ids_queue[0]
                self.seen_ids.discard(old_id)

            return False

    async def process_sequenced_event(
            self,
            topic: str,
            sequence: int,
            event: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process an event with a sequence number.
        Returns a list of events that can be delivered (maintaining order).
        """
        async with self._lock:
            # Initialize topic tracking if needed
            if topic not in self.expected_sequences:
                self.expected_sequences[topic] = sequence
                self.buffered_events[topic] = {}
                return [event]

            expected = self.expected_sequences[topic]

            # If this is the expected sequence, deliver it and any buffered
            if sequence == expected:
                events_to_deliver = [event]
                self.expected_sequences[topic] = sequence + 1

                # Check if we can deliver buffered events
                while self.expected_sequences[topic] in self.buffered_events[topic]:
                    next_seq = self.expected_sequences[topic]
                    buffered_event = self.buffered_events[topic].pop(next_seq)
                    events_to_deliver.append(buffered_event.payload)
                    self.expected_sequences[topic] = next_seq + 1

                return events_to_deliver

            # If this is a future event, buffer it
            elif sequence > expected:
                self.out_of_order_count += 1

                # Check if too far ahead
                if sequence - expected > self.max_out_of_order:
                    log.warning(
                        f"Event sequence {sequence} too far ahead of expected {expected} "
                        f"for topic {topic}, dropping intermediate events"
                    )
                    self.dropped_count += (sequence - expected - 1)

                    # Reset an expected sequence to this event
                    self.expected_sequences[topic] = sequence + 1
                    self.buffered_events[topic].clear()
                    return [event]

                # Buffer the event
                self.buffered_events[topic][sequence] = SequencedEvent(
                    event_id=event.get('id', ''),
                    sequence=sequence,
                    timestamp=datetime.now(timezone.utc),
                    topic=topic,
                    payload=event
                )

                log.debug(f"Buffered out-of-order event seq={sequence}, expected={expected}")
                return None

            # If this is an old event, skip it
            else:
                log.debug(f"Skipping old event with sequence {sequence}, expected {expected}")
                self.dropped_count += 1
                return None

    async def reset_sequence(self, topic: Optional[str] = None) -> None:
        """Reset sequence for a specific topic or all topics"""
        async with self._lock:
            if topic:
                if topic in self.expected_sequences:
                    del self.expected_sequences[topic]
                if topic in self.buffered_events:
                    del self.buffered_events[topic]
            else:
                self.expected_sequences.clear()
                self.buffered_events.clear()

    async def get_sequence_stats(self) -> Dict[str, Any]:
        """Get detailed sequence statistics"""
        async with self._lock:
            topic_stats = {}
            total_buffered = 0

            for topic, expected in self.expected_sequences.items():
                buffered = self.buffered_events.get(topic, {})
                total_buffered += len(buffered)

                gaps = []
                if buffered:
                    sequences = sorted(buffered.keys())
                    last = expected
                    for seq in sequences:
                        if seq - last > 1:
                            gaps.append({
                                'start': last + 1,
                                'end': seq - 1,
                                'size': seq - last - 1
                            })
                        last = seq

                topic_stats[topic] = {
                    'expected': expected,
                    'buffered': len(buffered),
                    'gaps': gaps,
                    'buffered_sequences': sorted(buffered.keys()) if buffered else []
                }

            return {
                'current_sequence': self.sequence,
                'duplicate_count': self.duplicate_count,
                'out_of_order_count': self.out_of_order_count,
                'dropped_count': self.dropped_count,
                'topics': topic_stats,
                'total_topics': len(self.expected_sequences),
                'total_buffered': total_buffered,
                'seen_ids_count': len(self.seen_ids)
            }

    async def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about buffered events (frontend compatible)"""
        async with self._lock:
            stats = {
                'total_topics': len(self.expected_sequences),
                'total_buffered': sum(len(events) for events in self.buffered_events.values()),
                'topics': {}
            }

            for topic, expected in self.expected_sequences.items():
                buffered = self.buffered_events.get(topic, {})
                if buffered:
                    sequences = sorted(buffered.keys())
                    stats['topics'][topic] = {
                        'expected_sequence': expected,
                        'buffered_count': len(buffered),
                        'buffered_sequences': sequences,
                        'gap_size': sequences[0] - expected if sequences else 0,
                        'oldest_buffered_age': (
                                datetime.now(timezone.utc) - min(
                            e.timestamp for e in buffered.values()
                        ).replace(tzinfo=timezone.utc)
                        ).total_seconds() if buffered else 0
                    }

            return stats

    async def cleanup(self) -> None:
        """Manually trigger cleanup"""
        async with self._lock:
            await self._cleanup_internal()

    async def _cleanup_internal(self) -> None:
        """Internal cleanup logic"""
        now = datetime.now(timezone.utc)

        # Cleanly buffered events older than 5 minutes
        for topic, events in list(self.buffered_events.items()):
            to_remove = []
            for seq, event in events.items():
                age = (now - event.timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                if age > 300:  # 5 minutes
                    to_remove.append(seq)

            for seq in to_remove:
                del events[seq]
                self.dropped_count += 1

            # Remove a topic if no buffered events
            if not events and topic in self.buffered_events:
                del self.buffered_events[topic]
                del self.expected_sequences[topic]

        # Clean up old-seen IDs
        if len(self.seen_ids) > self.window_size * 1.5:
            # Keep only the most recent window_size IDs
            recent_ids = list(self.seen_ids_queue)[-self.window_size:]
            self.seen_ids = set(recent_ids)
            self.seen_ids_queue = deque(recent_ids, maxlen=self.window_size)

    async def _cleanup_loop(self):
        """Periodically clean up old buffered events"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                async with self._lock:
                    await self._cleanup_internal()

                    # Log stats if we have buffered events
                    total_buffered = sum(len(events) for events in self.buffered_events.values())
                    if total_buffered > 0:
                        log.info(
                            f"EventSequencer: {total_buffered} events buffered across {len(self.buffered_events)} topics"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in sequencer cleanup: {e}")

    async def shutdown(self):
        """Shutdown the sequencer"""
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass

        log.info(f"EventSequencer shutdown - Stats: duplicates={self.duplicate_count}, "
                 f"out_of_order={self.out_of_order_count}, dropped={self.dropped_count}")