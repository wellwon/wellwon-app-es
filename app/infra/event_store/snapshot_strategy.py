# =============================================================================
# File: app/infra/event_store/snapshot_strategy.py
# Description: Intelligent snapshot strategy for event store optimization
#
# This module implements automatic snapshot creation based on:
# - Event count thresholds
# - Time intervals
# - Storage size limits
# - Aggregate-specific rules
#
# Following best practices from EventStore DB, Axon Framework, and
# production systems at Stripe, Square, and PayPal.
# =============================================================================

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import hashlib

from app.config.snapshot_config import SnapshotConfig
from app.infra.persistence.redis_client import (
    safe_get, safe_set, hincrby, hgetall, pipeline
)

# Cache Manager for centralized caching
from app.infra.persistence.cache_manager import CacheManager

log = logging.getLogger("wellwon.event_store.snapshot_strategy")


class SnapshotTriggerReason(Enum):
    """Reasons why a snapshot was triggered"""
    EVENT_INTERVAL = auto()
    TIME_INTERVAL = auto()
    SIZE_THRESHOLD = auto()
    MANUAL_REQUEST = auto()
    STARTUP_RECOVERY = auto()
    NO_PREVIOUS_SNAPSHOT = auto()
    AGGREGATE_SPECIFIC_RULE = auto()


@dataclass
class SnapshotMetadata:
    """
    Metadata about snapshots for decision making.

    ENHANCED (2025-11-14): Added verification tracking to detect snapshot failures.
    """
    aggregate_id: str
    aggregate_type: str
    last_snapshot_version: int = 0
    last_snapshot_time: Optional[datetime] = None
    last_snapshot_size_bytes: int = 0
    total_snapshots_created: int = 0
    average_snapshot_duration_ms: float = 0.0
    last_snapshot_reason: Optional[str] = None
    last_snapshot_verification_failed: bool = False  # NEW: Track verification failures


@dataclass
class SnapshotDecision:
    """Result of snapshot decision logic"""
    should_create: bool
    reason: SnapshotTriggerReason
    details: str
    priority: int = 0  # 0 = normal, higher = more urgent
    metadata: Dict[str, Any] = field(default_factory=dict)


class SnapshotStrategy:
    """
    Intelligent strategy for determining when to create snapshots.

    Features:
    - Multiple trigger conditions (events, time, size)
    - Per-aggregate customization
    - Performance tracking
    - Redis-backed metadata storage
    - Concurrent snapshot limiting
    """

    def __init__(
            self,
            config: Optional[SnapshotConfig] = None,
            redis_namespace: str = "event_store:snapshots",
            cache_manager: Optional[CacheManager] = None
    ):
        self.config = config or SnapshotConfig()
        self.redis_namespace = redis_namespace
        self._cache_manager = cache_manager

        # Caching - now using centralized CacheManager (or fallback to disabled)
        self._cache_enabled = bool(cache_manager)
        # TTL is now managed by cache_manager configuration (event_store:metadata = 300s)

        # Concurrent snapshot limiting
        self._active_snapshots: Set[str] = set()
        self._snapshot_semaphore = asyncio.Semaphore(
            self.config.snapshot_batch_size
        )

        # Special rules for specific aggregates
        self._aggregate_rules: Dict[str, Any] = self._init_aggregate_rules()

        log.info(
            f"SnapshotStrategy initialized - "
            f"default_interval={self.config.default_event_interval}, "
            f"time_interval={self.config.default_time_interval_hours}h, "
            f"size_threshold={self.config.default_size_threshold_mb}MB"
        )

    def _init_aggregate_rules(self) -> Dict[str, Any]:
        """Initialize aggregate-specific rules"""
        return {
            "VirtualBroker": {
                "high_activity_threshold": 50,  # More frequent during high trading
                "quiet_hours_interval": 200,  # Less frequent during quiet hours
                "check_trading_hours": True
            },
            "BrokerAccount": {
                "balance_change_threshold": 0.01,  # Snapshot on significant balance changes
                "force_daily_snapshot": True  # Always snapshot at least daily
            },
            "Order": {
                "completed_orders_threshold": 20,  # Snapshot after N completed orders
                "include_open_orders": False  # Don't count open orders
            }
        }

    async def should_snapshot(
            self,
            aggregate_id: str,
            aggregate_type: str,
            current_version: int,
            last_snapshot_version: Optional[int] = None,
            last_snapshot_time: Optional[datetime] = None,
            events_size_bytes: Optional[int] = None,
            force: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if a snapshot should be created.

        Returns:
            Tuple of (should_create: bool, reason: str)
        """
        # Quick check for forced snapshot
        if force:
            return True, "Manual snapshot requested"

        # Check if already creating snapshot for this aggregate
        snapshot_key = f"{aggregate_type}:{aggregate_id}"
        if snapshot_key in self._active_snapshots:
            log.debug(f"Snapshot already in progress for {snapshot_key}")
            return False, "Snapshot already in progress"

        # Get metadata
        metadata = await self._get_snapshot_metadata(aggregate_id, aggregate_type)

        # Update with provided values
        if last_snapshot_version is not None:
            metadata.last_snapshot_version = last_snapshot_version
        if last_snapshot_time is not None:
            metadata.last_snapshot_time = last_snapshot_time

        # Run decision logic
        decision = await self._make_snapshot_decision(
            metadata, current_version, events_size_bytes
        )

        if decision.should_create:
            # Check if we can acquire semaphore (non-blocking)
            if not self._snapshot_semaphore.locked():
                return True, decision.details
            else:
                log.debug(f"Snapshot delayed for {snapshot_key} - too many concurrent snapshots")
                return False, "Too many concurrent snapshots"

        return False, decision.details

    async def _make_snapshot_decision(
            self,
            metadata: SnapshotMetadata,
            current_version: int,
            events_size_bytes: Optional[int] = None
    ) -> SnapshotDecision:
        """Core decision logic for snapshot creation"""

        # Check 1: No previous snapshot
        if metadata.last_snapshot_version == 0 or metadata.last_snapshot_time is None:
            return SnapshotDecision(
                should_create=True,
                reason=SnapshotTriggerReason.NO_PREVIOUS_SNAPSHOT,
                details="No previous snapshot exists",
                priority=10  # High priority
            )

        # Check 2: Event interval
        events_since_snapshot = current_version - metadata.last_snapshot_version
        event_interval = self._get_event_interval(metadata.aggregate_type)

        if events_since_snapshot >= event_interval:
            return SnapshotDecision(
                should_create=True,
                reason=SnapshotTriggerReason.EVENT_INTERVAL,
                details=f"Event interval reached: {events_since_snapshot} events (threshold: {event_interval})",
                priority=5,
                metadata={"events_since_snapshot": events_since_snapshot}
            )

        # Check 3: Time interval
        if metadata.last_snapshot_time:
            time_since_snapshot = datetime.now(timezone.utc) - metadata.last_snapshot_time
            hours_elapsed = time_since_snapshot.total_seconds() / 3600
            time_interval = self._get_time_interval(metadata.aggregate_type)

            if hours_elapsed >= time_interval:
                return SnapshotDecision(
                    should_create=True,
                    reason=SnapshotTriggerReason.TIME_INTERVAL,
                    details=f"Time interval reached: {hours_elapsed:.1f} hours (threshold: {time_interval}h)",
                    priority=3,
                    metadata={"hours_elapsed": hours_elapsed}
                )

        # Check 4: Size threshold
        if events_size_bytes:
            size_mb = events_size_bytes / (1024 * 1024)
            if size_mb >= self.config.default_size_threshold_mb:
                return SnapshotDecision(
                    should_create=True,
                    reason=SnapshotTriggerReason.SIZE_THRESHOLD,
                    details=f"Size threshold reached: {size_mb:.1f}MB (threshold: {self.config.default_size_threshold_mb}MB)",
                    priority=7,
                    metadata={"size_mb": size_mb}
                )

        # Check 5: Aggregate-specific rules
        aggregate_decision = await self._check_aggregate_specific_rules(
            metadata, current_version
        )
        if aggregate_decision and aggregate_decision.should_create:
            return aggregate_decision

        # No snapshot needed
        return SnapshotDecision(
            should_create=False,
            reason=SnapshotTriggerReason.EVENT_INTERVAL,  # Default reason
            details=f"No snapshot needed: {events_since_snapshot}/{event_interval} events, {hours_elapsed:.1f}/{time_interval}h elapsed"
        )

    async def _check_aggregate_specific_rules(
            self,
            metadata: SnapshotMetadata,
            current_version: int
    ) -> Optional[SnapshotDecision]:
        """Check aggregate-specific snapshot rules"""

        rules = self._aggregate_rules.get(metadata.aggregate_type, {})
        if not rules:
            return None

        # Example: VirtualBroker trading hours check
        if metadata.aggregate_type == "VirtualBroker" and rules.get("check_trading_hours"):
            if self._is_trading_hours():
                # More frequent snapshots during trading
                threshold = rules.get("high_activity_threshold", 50)
                events_since = current_version - metadata.last_snapshot_version
                if events_since >= threshold:
                    return SnapshotDecision(
                        should_create=True,
                        reason=SnapshotTriggerReason.AGGREGATE_SPECIFIC_RULE,
                        details=f"High trading activity: {events_since} events",
                        priority=6
                    )

        # Example: BrokerAccount daily snapshot
        if metadata.aggregate_type == "BrokerAccount" and rules.get("force_daily_snapshot"):
            if metadata.last_snapshot_time:
                hours_elapsed = (datetime.now(timezone.utc) - metadata.last_snapshot_time).total_seconds() / 3600
                if hours_elapsed >= 24:
                    return SnapshotDecision(
                        should_create=True,
                        reason=SnapshotTriggerReason.AGGREGATE_SPECIFIC_RULE,
                        details="Daily snapshot required for financial data",
                        priority=8
                    )

        return None

    def _get_event_interval(self, aggregate_type: str) -> int:
        """Get event interval for aggregate type"""
        return self.config.aggregate_snapshot_intervals.get(
            aggregate_type,
            self.config.default_event_interval
        )

    def _get_time_interval(self, aggregate_type: str) -> int:
        """Get time interval in hours for aggregate type"""
        # Could be customized per aggregate type
        time_intervals = {
            "BrokerAccount": 12,  # More frequent for financial data
            "UserAccount": 48,  # Less frequent for user data
        }
        return time_intervals.get(
            aggregate_type,
            self.config.default_time_interval_hours
        )

    def _is_trading_hours(self) -> bool:
        """Check if current time is during trading hours"""
        now = datetime.now(timezone.utc)
        # Simple check - would be more sophisticated in production
        weekday = now.weekday()
        hour = now.hour

        # Monday-Friday, 9:30 AM - 4:00 PM ET (14:30-21:00 UTC)
        if weekday < 5 and 14 <= hour < 21:
            return True
        return False

    async def record_snapshot(
            self,
            aggregate_id: str,
            aggregate_type: str,
            version: int,
            size_bytes: Optional[int] = None,
            duration_ms: Optional[float] = None,
            reason: Optional[str] = None,
            verify: bool = False
    ) -> bool:
        """
        Record that a snapshot was created.

        ENHANCED (2025-11-14): Added optional verification to ensure
        snapshot was actually saved to KurrentDB.

        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Aggregate type
            version: Snapshot version
            size_bytes: Snapshot size in bytes
            duration_ms: Snapshot creation duration
            reason: Reason for snapshot creation
            verify: If True, verify snapshot exists in KurrentDB (adds latency)

        Returns:
            bool: True if snapshot verified (or verification skipped), False if verification failed
        """
        snapshot_key = f"{aggregate_type}:{aggregate_id}"

        try:
            # Update metadata
            metadata = await self._get_snapshot_metadata(aggregate_id, aggregate_type)
            metadata.last_snapshot_version = version
            metadata.last_snapshot_time = datetime.now(timezone.utc)
            metadata.total_snapshots_created += 1

            if size_bytes:
                metadata.last_snapshot_size_bytes = size_bytes

            if duration_ms and metadata.average_snapshot_duration_ms > 0:
                # Running average
                metadata.average_snapshot_duration_ms = (
                        metadata.average_snapshot_duration_ms * 0.9 + duration_ms * 0.1
                )
            else:
                metadata.average_snapshot_duration_ms = duration_ms or 0

            if reason:
                metadata.last_snapshot_reason = reason

            # OPTIONAL VERIFICATION (2025-11-14): Verify snapshot exists in KurrentDB
            if verify and self._event_store:
                try:
                    verified_snapshot = await self._event_store.load_snapshot(
                        aggregate_id, aggregate_type
                    )

                    if not verified_snapshot:
                        log.error(
                            f"Snapshot verification FAILED: No snapshot found for {aggregate_type}:{aggregate_id} v{version}"
                        )
                        metadata.last_snapshot_verification_failed = True
                        await self._save_snapshot_metadata(metadata)
                        self._active_snapshots.discard(snapshot_key)
                        return False

                    if verified_snapshot.version != version:
                        log.error(
                            f"Snapshot verification FAILED: Expected version {version} but found {verified_snapshot.version} "
                            f"for {aggregate_type}:{aggregate_id}"
                        )
                        metadata.last_snapshot_verification_failed = True
                        await self._save_snapshot_metadata(metadata)
                        self._active_snapshots.discard(snapshot_key)
                        return False

                    log.debug(f"Snapshot verification PASSED for {aggregate_type}:{aggregate_id} v{version}")
                    metadata.last_snapshot_verification_failed = False

                except Exception as verify_error:
                    log.error(f"Snapshot verification error for {aggregate_type}:{aggregate_id}: {verify_error}")
                    metadata.last_snapshot_verification_failed = True
                    # Continue - don't fail the operation
            else:
                # Verification skipped
                metadata.last_snapshot_verification_failed = False

            # Save to Redis (via CacheManager)
            await self._save_snapshot_metadata(metadata)

            # Remove from active snapshots
            self._active_snapshots.discard(snapshot_key)

            log.info(
                f"Recorded snapshot for {aggregate_type}:{aggregate_id} "
                f"v{version} ({size_bytes} bytes, {duration_ms:.1f}ms){' [VERIFIED]' if verify else ''}"
            )

            return True

        except Exception as e:
            log.error(f"Failed to record snapshot metadata: {e}")
            # Don't fail the operation
            self._active_snapshots.discard(snapshot_key)
            return False

    async def mark_snapshot_started(self, aggregate_id: str, aggregate_type: str) -> bool:
        """Mark that snapshot creation has started"""
        snapshot_key = f"{aggregate_type}:{aggregate_id}"

        if snapshot_key in self._active_snapshots:
            return False  # Already in progress

        self._active_snapshots.add(snapshot_key)
        return True

    async def mark_snapshot_failed(self, aggregate_id: str, aggregate_type: str) -> None:
        """Mark that snapshot creation failed"""
        snapshot_key = f"{aggregate_type}:{aggregate_id}"
        self._active_snapshots.discard(snapshot_key)

    async def _get_snapshot_metadata(
            self,
            aggregate_id: str,
            aggregate_type: str
    ) -> SnapshotMetadata:
        """Get snapshot metadata from CacheManager or Redis"""
        snapshot_key = f"{aggregate_type}:{aggregate_id}"

        # Check cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "event_store", "metadata", aggregate_type, str(aggregate_id)
            )
            cached_value = await self._cache_manager.get(cache_key)
            if cached_value:
                try:
                    metadata_dict = json.loads(cached_value)
                    return SnapshotMetadata(
                        aggregate_id=aggregate_id,
                        aggregate_type=aggregate_type,
                        last_snapshot_version=metadata_dict.get("last_snapshot_version", 0),
                        last_snapshot_time=datetime.fromisoformat(metadata_dict["last_snapshot_time"])
                        if metadata_dict.get("last_snapshot_time") else None,
                        last_snapshot_size_bytes=metadata_dict.get("last_snapshot_size_bytes", 0),
                        total_snapshots_created=metadata_dict.get("total_snapshots_created", 0),
                        average_snapshot_duration_ms=metadata_dict.get("average_snapshot_duration_ms", 0.0),
                        last_snapshot_reason=metadata_dict.get("last_snapshot_reason")
                    )
                except Exception as e:
                    log.warning(f"Failed to parse cached metadata: {e}")

        # Load from Redis (fallback)
        redis_key = f"{self.redis_namespace}:metadata:{snapshot_key}"
        data = await safe_get(redis_key)

        if data:
            try:
                metadata_dict = json.loads(data)
                metadata = SnapshotMetadata(
                    aggregate_id=aggregate_id,
                    aggregate_type=aggregate_type,
                    last_snapshot_version=metadata_dict.get("last_snapshot_version", 0),
                    last_snapshot_time=datetime.fromisoformat(metadata_dict["last_snapshot_time"])
                    if metadata_dict.get("last_snapshot_time") else None,
                    last_snapshot_size_bytes=metadata_dict.get("last_snapshot_size_bytes", 0),
                    total_snapshots_created=metadata_dict.get("total_snapshots_created", 0),
                    average_snapshot_duration_ms=metadata_dict.get("average_snapshot_duration_ms", 0.0),
                    last_snapshot_reason=metadata_dict.get("last_snapshot_reason")
                )

                # Update cache using CacheManager
                if self._cache_manager and self._cache_enabled:
                    cache_key = self._cache_manager._make_key(
                        "event_store", "metadata", aggregate_type, str(aggregate_id)
                    )
                    ttl = self._cache_manager.get_cache_ttl("event_store:metadata")
                    await self._cache_manager.set(cache_key, data, ttl=ttl)

                return metadata

            except Exception as e:
                log.error(f"Failed to parse snapshot metadata: {e}")

        # Return default metadata
        return SnapshotMetadata(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type
        )

    async def _save_snapshot_metadata(self, metadata: SnapshotMetadata) -> None:
        """Save snapshot metadata to Redis"""
        snapshot_key = f"{metadata.aggregate_type}:{metadata.aggregate_id}"
        redis_key = f"{self.redis_namespace}:metadata:{snapshot_key}"

        metadata_dict = {
            "aggregate_id": metadata.aggregate_id,
            "aggregate_type": metadata.aggregate_type,
            "last_snapshot_version": metadata.last_snapshot_version,
            "last_snapshot_time": metadata.last_snapshot_time.isoformat()
            if metadata.last_snapshot_time else None,
            "last_snapshot_size_bytes": metadata.last_snapshot_size_bytes,
            "total_snapshots_created": metadata.total_snapshots_created,
            "average_snapshot_duration_ms": metadata.average_snapshot_duration_ms,
            "last_snapshot_reason": metadata.last_snapshot_reason
        }

        await safe_set(
            redis_key,
            json.dumps(metadata_dict),
            ttl_seconds=86400 * 30  # 30 days
        )

    async def get_snapshot_stats(self) -> Dict[str, Any]:
        """Get statistics about snapshot creation"""
        # This would aggregate data from Redis
        # For now, return local stats
        return {
            "active_snapshots": len(self._active_snapshots),
            "cache_enabled": self._cache_enabled,
            "semaphore_available": self._snapshot_semaphore._value,
            "config": {
                "default_event_interval": self.config.default_event_interval,
                "default_time_interval_hours": self.config.default_time_interval_hours,
                "default_size_threshold_mb": self.config.default_size_threshold_mb,
                "batch_size": self.config.snapshot_batch_size
            }
        }

    async def cleanup_old_metadata(self, days_to_keep: int = 90) -> int:
        """Clean up old snapshot metadata"""
        # Implementation would scan Redis and remove old entries
        # This is a placeholder
        return 0

    def should_use_async(self, aggregate_type: str) -> bool:
        """Determine if snapshot should be created asynchronously"""
        # Could have per-aggregate rules
        async_aggregates = {
            "VirtualBroker": True,  # Large aggregates
            "Order": True,  # High volume
            "Position": True,  # High volume
        }

        return async_aggregates.get(
            aggregate_type,
            self.config.enable_async_snapshots
        )

    async def wait_for_semaphore(self) -> None:
        """Wait to acquire snapshot semaphore"""
        await self._snapshot_semaphore.acquire()

    def release_semaphore(self) -> None:
        """Release snapshot semaphore"""
        self._snapshot_semaphore.release()

    def get_snapshot_key(self, aggregate_id: str, aggregate_type: str) -> str:
        """Get unique key for snapshot tracking"""
        return f"{aggregate_type}:{aggregate_id}"

    def calculate_snapshot_hash(self, snapshot_data: Dict[str, Any]) -> str:
        """Calculate hash of snapshot for integrity verification"""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(snapshot_data, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()


# =============================================================================
# Utility Functions
# =============================================================================

def create_snapshot_strategy(config: Optional[SnapshotConfig] = None) -> SnapshotStrategy:
    """Factory function to create snapshot strategy"""
    return SnapshotStrategy(config=config)


async def analyze_snapshot_patterns(
        strategy: SnapshotStrategy,
        days: int = 7
) -> Dict[str, Any]:
    """Analyze snapshot creation patterns for optimization"""
    # This would query Redis for historical data
    # Placeholder for now
    return {
        "average_interval_hours": 24,
        "peak_snapshot_hour": 14,  # 2 PM UTC
        "aggregates_needing_adjustment": []
    }

# =============================================================================
# EOF
# =============================================================================