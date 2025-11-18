# File: app/infra/event_store/sequence_tracker.py
# =============================================================================
# File: app/infra/event_store/sequence_tracker.py
# Description: Tracks event sequences for ensuring ordered processing
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, Optional, List, Set, Any
from datetime import datetime, timezone
import uuid

from app.infra.persistence.redis_client import (
    safe_get, safe_set, safe_delete, hincrby, hgetall, pipeline
)
from app.infra.persistence.cache_manager import CacheManager

log = logging.getLogger("tradecore.sequence_tracker")


class EventSequenceError(Exception):
    """Base exception for sequence-related errors"""
    pass


class OutOfOrderEventError(EventSequenceError):
    """Event received out of sequence"""
    pass


class DuplicateEventError(EventSequenceError):
    """Event already processed"""
    pass


class EventSequenceTracker:
    """
    Tracks event processing sequences to ensure ordered and exactly-once processing.
    Uses Redis for distributed state management.
    """

    def __init__(
            self,
            namespace: str = "event_sequence",
            ttl_seconds: int = 86400,  # 24 hours default
            cache_manager: Optional[CacheManager] = None  # Centralized cache manager
    ):
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self._cache_manager = cache_manager

        # Caching - now using centralized CacheManager (or fallback to disabled)
        self._cache_enabled = bool(cache_manager)
        # TTL is now managed by cache_manager configuration (sequence:tracking = 60s)

    def _get_sequence_key(self, aggregate_id: uuid.UUID, projection_name: str) -> str:
        """Get Redis key for sequence tracking"""
        return f"{self.namespace}:{projection_name}:{aggregate_id}"

    async def get_last_sequence(
            self,
            aggregate_id: uuid.UUID,
            projection_name: str
    ) -> int:
        """Get the last processed sequence number for an aggregate"""
        # Check cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "sequence", "tracking", projection_name, str(aggregate_id)
            )
            cached_value = await self._cache_manager.get(cache_key)
            if cached_value is not None:
                return int(cached_value)

        # Check Redis directly (fallback)
        key = self._get_sequence_key(aggregate_id, projection_name)
        value = await safe_get(key)

        sequence = int(value) if value else 0

        # Update cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "sequence", "tracking", projection_name, str(aggregate_id)
            )
            ttl = self._cache_manager.get_cache_ttl("sequence:tracking")
            await self._cache_manager.set(cache_key, str(sequence), ttl=ttl)

        return sequence

    async def check_and_update_sequence(
            self,
            aggregate_id: uuid.UUID,
            projection_name: str,
            event_sequence: int,
            event_id: uuid.UUID,
            allow_replay: bool = False
    ) -> bool:
        """
        Check if event should be processed and update sequence.

        Args:
            aggregate_id: The aggregate ID
            projection_name: Name of the projection
            event_sequence: Sequence number of the event
            event_id: Event ID for idempotency
            allow_replay: Whether to allow replaying already processed events

        Returns:
            True if event should be processed, False if should skip

        Raises:
            OutOfOrderEventError: If event is out of order
            DuplicateEventError: If event already processed (and not allowing replay)
        """
        last_sequence = await self.get_last_sequence(aggregate_id, projection_name)

        # Check for duplicate
        if event_sequence <= last_sequence:
            if allow_replay:
                log.debug(
                    f"Replaying event {event_id} with sequence {event_sequence} "
                    f"(last: {last_sequence})"
                )
                return True
            else:
                raise DuplicateEventError(
                    f"Event {event_id} already processed. "
                    f"Sequence: {event_sequence}, Last: {last_sequence}"
                )

        # Check for out of order
        if event_sequence > last_sequence + 1:
            raise OutOfOrderEventError(
                f"Event {event_id} out of order. "
                f"Expected: {last_sequence + 1}, Got: {event_sequence}"
            )

        # Update sequence in Redis
        key = self._get_sequence_key(aggregate_id, projection_name)
        await safe_set(key, str(event_sequence), ttl_seconds=self.ttl_seconds)

        # Update cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "sequence", "tracking", projection_name, str(aggregate_id)
            )
            ttl = self._cache_manager.get_cache_ttl("sequence:tracking")
            await self._cache_manager.set(cache_key, str(event_sequence), ttl=ttl)

        return True

    async def get_missing_sequences(
            self,
            aggregate_id: uuid.UUID,
            projection_name: str,
            up_to_sequence: int
    ) -> List[int]:
        """
        Get list of missing sequence numbers.

        Args:
            aggregate_id: The aggregate ID
            projection_name: Name of the projection
            up_to_sequence: Check up to this sequence number

        Returns:
            List of missing sequence numbers
        """
        last_processed = await self.get_last_sequence(aggregate_id, projection_name)

        if last_processed >= up_to_sequence:
            return []

        # Return range of missing sequences
        return list(range(last_processed + 1, up_to_sequence + 1))

    async def mark_sequences_processed(
            self,
            aggregate_id: uuid.UUID,
            projection_name: str,
            sequences: List[int]
    ) -> None:
        """Mark multiple sequences as processed (for batch operations)"""
        if not sequences:
            return

        # Update to highest sequence in Redis
        max_sequence = max(sequences)
        key = self._get_sequence_key(aggregate_id, projection_name)
        await safe_set(key, str(max_sequence), ttl_seconds=self.ttl_seconds)

        # Update cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "sequence", "tracking", projection_name, str(aggregate_id)
            )
            ttl = self._cache_manager.get_cache_ttl("sequence:tracking")
            await self._cache_manager.set(cache_key, str(max_sequence), ttl=ttl)

    async def reset_sequence(
            self,
            aggregate_id: uuid.UUID,
            projection_name: str
    ) -> bool:
        """Reset sequence tracking for an aggregate (for rebuilds)"""
        key = self._get_sequence_key(aggregate_id, projection_name)
        deleted = await safe_delete(key)

        # Clear from cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "sequence", "tracking", projection_name, str(aggregate_id)
            )
            await self._cache_manager.delete(cache_key)

        return deleted > 0

    async def get_projection_stats(self, projection_name: str) -> Dict[str, Any]:
        """Get statistics for a projection"""
        pattern = f"{self.namespace}:{projection_name}:*"

        # Return basic stats
        return {
            "projection": projection_name,
            "cache_enabled": self._cache_enabled,
            "cache_manager": "CacheManager" if self._cache_manager else "disabled"
        }


class SequenceAwareProjector:
    """
    Base class for projectors that handle event ordering.
    """

    def __init__(
            self,
            projection_name: str,
            sequence_tracker: Optional[EventSequenceTracker] = None
    ):
        self.projection_name = projection_name
        self.sequence_tracker = sequence_tracker or EventSequenceTracker()
        self.pending_events: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    async def handle_event_with_ordering(
            self,
            event_dict: Dict[str, Any]
    ) -> None:
        """
        Handle event with sequence ordering checks.
        """
        event_id = uuid.UUID(event_dict.get("event_id"))
        aggregate_id = uuid.UUID(event_dict.get("aggregate_id"))
        sequence = event_dict.get("sequence_number")

        if sequence is None:
            # No sequence number - process immediately (legacy support)
            await self._process_event(event_dict)
            return

        try:
            # Check sequence
            should_process = await self.sequence_tracker.check_and_update_sequence(
                aggregate_id=aggregate_id,
                projection_name=self.projection_name,
                event_sequence=sequence,
                event_id=event_id,
                allow_replay=False
            )

            if should_process:
                await self._process_event(event_dict)

                # Check if we have pending events to process
                await self._process_pending_events(aggregate_id)

        except OutOfOrderEventError as e:
            log.warning(f"Out of order event: {e}")

            # Store for later processing
            if aggregate_id not in self.pending_events:
                self.pending_events[aggregate_id] = []

            self.pending_events[aggregate_id].append(event_dict)

            # Try to fill the gap
            await self._try_fill_sequence_gap(aggregate_id, sequence)

        except DuplicateEventError:
            log.debug(f"Skipping duplicate event {event_id}")

    async def _process_event(self, event_dict: Dict[str, Any]) -> None:
        """Override this to implement actual projection logic"""
        raise NotImplementedError

    async def _process_pending_events(self, aggregate_id: uuid.UUID) -> None:
        """Process any pending events that are now in sequence"""
        if aggregate_id not in self.pending_events:
            return

        pending = self.pending_events[aggregate_id]
        if not pending:
            return

        # Sort by sequence
        pending.sort(key=lambda e: e.get("sequence_number", 0))

        processed = []
        for event in pending:
            sequence = event.get("sequence_number")
            event_id = uuid.UUID(event.get("event_id"))

            try:
                should_process = await self.sequence_tracker.check_and_update_sequence(
                    aggregate_id=aggregate_id,
                    projection_name=self.projection_name,
                    event_sequence=sequence,
                    event_id=event_id,
                    allow_replay=False
                )

                if should_process:
                    await self._process_event(event)
                    processed.append(event)
                else:
                    # Still out of order, stop processing
                    break

            except (OutOfOrderEventError, DuplicateEventError):
                # Still can't process this one
                break

        # Remove processed events
        for event in processed:
            pending.remove(event)

        if not pending:
            del self.pending_events[aggregate_id]

    async def _try_fill_sequence_gap(
            self,
            aggregate_id: uuid.UUID,
            up_to_sequence: int
    ) -> None:
        """
        Try to fill sequence gaps by fetching missing events.
        Override this to implement gap filling logic.
        """
        missing = await self.sequence_tracker.get_missing_sequences(
            aggregate_id,
            self.projection_name,
            up_to_sequence
        )

        if missing:
            log.warning(
                f"Missing sequences for aggregate {aggregate_id}: {missing}. "
                f"Implement gap filling logic."
            )