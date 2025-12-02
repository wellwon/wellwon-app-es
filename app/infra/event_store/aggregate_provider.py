# =============================================================================
# File: app/infra/event_store/aggregate_provider.py
# Description: Aggregate provider for automatic snapshot creation
# =============================================================================

from typing import Optional, Dict, Type, Any, Protocol, runtime_checkable
import uuid
import logging
from datetime import datetime, timezone

# LATE BINDING: Import function instead of dict to ensure auto-registered events are included
from app.infra.event_bus.event_registry import get_event_model

# Cache Manager for centralized caching
from app.infra.persistence.cache_manager import CacheManager

# Import aggregate types that support snapshots
# Only import what exists in your system
try:
    from app.virtual_broker.aggregate import VirtualBrokerAggregate
except ImportError:
    VirtualBrokerAggregate = None

try:
    from app.broker_account.aggregate import AccountAggregate
except ImportError:
    AccountAggregate = None

try:
    from app.broker_connection.aggregate import BrokerConnectionAggregate
except ImportError:
    BrokerConnectionAggregate = None

try:
    from app.user_account.aggregate import UserAccountAggregate
except ImportError:
    UserAccountAggregate = None

# These aggregates might not exist yet - import them conditionally
try:
    from app.order.aggregate import Order as OrderAggregate
except ImportError:
    OrderAggregate = None

try:
    from app.position.aggregate import PositionAggregate
except ImportError:
    PositionAggregate = None

try:
    from app.strategy.aggregate import StrategyAggregate
except ImportError:
    StrategyAggregate = None

try:
    from app.trade.aggregate import TradeAggregate
except ImportError:
    TradeAggregate = None

# WellWon aggregates
try:
    from app.chat.aggregate import ChatAggregate
except ImportError:
    ChatAggregate = None

try:
    from app.company.aggregate import CompanyAggregate
except ImportError:
    CompanyAggregate = None

log = logging.getLogger("wellwon.aggregate_provider")


@runtime_checkable
class AggregateSnapshotProvider(Protocol):
    """Interface for retrieving aggregates for snapshot creation"""

    async def get_aggregate_for_snapshot(
            self,
            aggregate_id: uuid.UUID,
            aggregate_type: str
    ) -> Optional[Any]:  # Return Any to avoid circular import
        """Get aggregate instance for creating snapshot"""
        ...


class DefaultAggregateProvider(AggregateSnapshotProvider):
    """
    Default implementation that creates aggregates from event store.

    This provider is responsible for loading aggregates when the snapshot
    strategy determines a snapshot should be created. It handles:
    - Loading the correct aggregate type
    - Replaying events to rebuild state
    - Caching for performance
    - Error handling and logging
    """

    def __init__(self, event_store, cache_manager: Optional[CacheManager] = None):
        """
        Initialize the aggregate provider.

        Args:
            event_store: The EventStore instance (KurrentDB or RedPanda)
            cache_manager: Optional centralized cache manager for aggregate caching
        """
        self.event_store = event_store
        self._cache_manager = cache_manager

        # Registry of aggregate types
        self._aggregate_types: Dict[str, Type[Any]] = {}

        # Register available aggregate types
        if VirtualBrokerAggregate:
            self._aggregate_types["VirtualBroker"] = VirtualBrokerAggregate
            self._aggregate_types["VirtualBrokerAccount"] = VirtualBrokerAggregate  # FIXED: Add this mapping

        if AccountAggregate:
            self._aggregate_types["BrokerAccount"] = AccountAggregate
            self._aggregate_types["Account"] = AccountAggregate  # Alias

        if BrokerConnectionAggregate:
            self._aggregate_types["BrokerConnection"] = BrokerConnectionAggregate

        if UserAccountAggregate:
            self._aggregate_types["UserAccount"] = UserAccountAggregate
            self._aggregate_types["User"] = UserAccountAggregate  # Alias

        # Register aggregates that might not exist yet
        if OrderAggregate:
            self._aggregate_types["Order"] = OrderAggregate

        if PositionAggregate:
            self._aggregate_types["Position"] = PositionAggregate

        if StrategyAggregate:
            self._aggregate_types["Strategy"] = StrategyAggregate

        if TradeAggregate:
            self._aggregate_types["Trade"] = TradeAggregate

        # WellWon aggregates
        if ChatAggregate:
            self._aggregate_types["Chat"] = ChatAggregate

        if CompanyAggregate:
            self._aggregate_types["Company"] = CompanyAggregate

        # Performance tracking
        self._load_times: Dict[str, list] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Caching - now using centralized CacheManager (or fallback to disabled)
        self._cache_enabled = bool(self._cache_manager)  # Only enable if cache_manager provided
        # TTL is now managed by cache_manager configuration (aggregate:instance = 60s)

        log.info(f"DefaultAggregateProvider initialized with {len(self._aggregate_types)} aggregate types (cache: {'enabled' if self._cache_enabled else 'disabled'})")

    async def get_aggregate_for_snapshot(
            self,
            aggregate_id: uuid.UUID,
            aggregate_type: str
    ) -> Optional[Any]:  # Return Any to avoid circular import
        """
        Get aggregate by replaying events.

        This method:
        1. Checks cache first
        2. Loads the appropriate aggregate class
        3. Fetches all events from event store
        4. Replays events to rebuild state
        5. Returns the aggregate ready for snapshot

        Args:
            aggregate_id: The aggregate ID
            aggregate_type: The aggregate type name

        Returns:
            The aggregate instance or None if not found
        """
        start_time = datetime.now(timezone.utc)

        # Check cache using CacheManager
        if self._cache_manager and self._cache_enabled:
            cache_key = self._cache_manager._make_key(
                "aggregate", "instance", aggregate_type, str(aggregate_id)
            )
            cached_value = await self._cache_manager.get(cache_key)
            if cached_value:
                self._cache_hits += 1
                log.debug(f"Cache hit for aggregate {aggregate_type}:{aggregate_id}")

                # IMPLEMENTED (2025-11-14): Deserialize cached aggregate from JSON
                try:
                    # Get aggregate class
                    aggregate_class = self._aggregate_types.get(aggregate_type)
                    if not aggregate_class:
                        log.warning(f"Unknown aggregate type in cache: {aggregate_type}")
                        self._cache_misses += 1
                    else:
                        # Deserialize aggregate state
                        import json
                        cached_data = json.loads(cached_value) if isinstance(cached_value, (str, bytes)) else cached_value

                        # Create aggregate instance
                        aggregate = aggregate_class(id=aggregate_id)

                        # Restore state (use from_dict if available, otherwise set attributes)
                        if hasattr(aggregate, 'from_dict'):
                            aggregate = aggregate_class.from_dict(cached_data)
                        else:
                            # Fallback: restore basic state
                            aggregate._version = cached_data.get('version', 0)
                            aggregate._id = aggregate_id
                            # Restore other attributes from cached_data['state'] if present
                            if 'state' in cached_data:
                                for key, value in cached_data['state'].items():
                                    if hasattr(aggregate, key):
                                        setattr(aggregate, key, value)

                        log.debug(f"Successfully deserialized aggregate {aggregate_type}:{aggregate_id} from cache")
                        return aggregate

                except Exception as e:
                    log.warning(f"Cache deserialization failed for {aggregate_type}:{aggregate_id}: {e}. Rebuilding from events.")
                    self._cache_misses += 1
            else:
                self._cache_misses += 1
        else:
            self._cache_misses += 1

        # Get aggregate class
        aggregate_class = self._aggregate_types.get(aggregate_type)
        if not aggregate_class:
            log.error(f"Unknown aggregate type: {aggregate_type}")
            return None

        try:
            # Get snapshot and events after snapshot (FIXED: use snapshot-aware loading)
            snapshot, events = await self.event_store.get_events_with_snapshot(
                aggregate_id, aggregate_type
            )

            if not events and snapshot is None:
                log.debug(f"No events or snapshot found for {aggregate_type}:{aggregate_id}")
                return None

            # Create aggregate instance
            aggregate = aggregate_class(aggregate_id)
            events_applied = 0

            # CRITICAL: Restore from snapshot first if exists
            if snapshot is not None:
                if hasattr(aggregate, 'restore_from_snapshot'):
                    aggregate.restore_from_snapshot(snapshot.state)
                    aggregate.version = snapshot.version
                    log.debug(
                        f"Restored {aggregate_type}:{aggregate_id} from snapshot at v{snapshot.version}"
                    )
                else:
                    log.warning(
                        f"Aggregate {aggregate_type} doesn't support restore_from_snapshot, "
                        f"will replay all events"
                    )

            # Replay events (only events AFTER snapshot)
            for envelope in events:
                try:
                    # Get event class from registry (late binding for auto-registered events)
                    event_class = get_event_model(envelope.event_type)
                    if not event_class:
                        log.warning(
                            f"Unknown event type '{envelope.event_type}' "
                            f"for aggregate {aggregate_id}, skipping"
                        )
                        continue

                    # Deserialize and apply event
                    domain_event = event_class(**envelope.event_data)
                    aggregate._apply(domain_event)
                    aggregate.version = envelope.aggregate_version
                    events_applied += 1

                except Exception as e:
                    log.error(
                        f"Failed to apply event {envelope.event_id} "
                        f"to aggregate {aggregate_id}: {e}"
                    )
                    # Continue with other events

            # Mark events as committed (no uncommitted events)
            if hasattr(aggregate, 'mark_events_committed'):
                aggregate.mark_events_committed()

            # Cache the aggregate using CacheManager
            # IMPLEMENTED (2025-11-14): Serialize aggregate to JSON for caching
            if self._cache_manager and self._cache_enabled:
                cache_key = self._cache_manager._make_key(
                    "aggregate", "instance", aggregate_type, str(aggregate_id)
                )
                ttl = self._cache_manager.get_cache_ttl("aggregate:instance")

                try:
                    import json
                    # Serialize aggregate (use to_dict if available)
                    if hasattr(aggregate, 'to_dict'):
                        serialized_data = json.dumps(aggregate.to_dict())
                    else:
                        # Fallback: create dict from aggregate state
                        serialized_data = json.dumps({
                            'id': str(aggregate.id),
                            'version': aggregate.version,
                            'state': {
                                key: value for key, value in vars(aggregate).items()
                                if not key.startswith('_') and key not in ['id', 'version']
                            }
                        })

                    await self._cache_manager.set(cache_key, serialized_data, ttl=ttl)
                    log.debug(f"Cached aggregate {aggregate_type}:{aggregate_id} v{aggregate.version}")

                except Exception as e:
                    log.warning(f"Failed to cache aggregate {aggregate_type}:{aggregate_id}: {e}")

            # Track performance
            load_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            if aggregate_type not in self._load_times:
                self._load_times[aggregate_type] = []
            self._load_times[aggregate_type].append(load_time)

            # Keep only last 100 measurements
            if len(self._load_times[aggregate_type]) > 100:
                self._load_times[aggregate_type] = self._load_times[aggregate_type][-100:]

            snapshot_info = f", snapshot v{snapshot.version}" if snapshot else ", no snapshot"
            log.info(
                f"Loaded aggregate {aggregate_type}:{aggregate_id} "
                f"v{aggregate.version} for snapshot "
                f"({events_applied} events{snapshot_info} in {load_time:.3f}s)"
            )

            return aggregate

        except Exception as e:
            log.error(f"Failed to load aggregate {aggregate_type}:{aggregate_id}: {e}")
            return None

    def register_aggregate_type(self, aggregate_type: str, aggregate_class: Type[Any]):
        """
        Register a new aggregate type.

        This allows you to add aggregate types at runtime as you develop them.

        Args:
            aggregate_type: The type name (e.g., "Order", "Position")
            aggregate_class: The aggregate class

        Example:
            provider.register_aggregate_type("Order", OrderAggregate)
        """
        self._aggregate_types[aggregate_type] = aggregate_class
        log.info(f"Registered aggregate type: {aggregate_type} -> {aggregate_class.__name__}")

    async def clear_cache(self):
        """Clear the aggregate cache using CacheManager"""
        if self._cache_manager and self._cache_enabled:
            # Clear all aggregate cache keys
            pattern = f"{self._cache_manager.key_prefix}:aggregate:instance:*"
            deleted = await self._cache_manager.delete_pattern(pattern)
            log.info(f"Cleared aggregate cache ({deleted} keys deleted)")
        else:
            log.debug("No cache manager, nothing to clear")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0

        return {
            "cache_enabled": self._cache_enabled,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {}

        for aggregate_type, times in self._load_times.items():
            if times:
                stats[aggregate_type] = {
                    "avg_load_time": sum(times) / len(times),
                    "min_load_time": min(times),
                    "max_load_time": max(times),
                    "samples": len(times)
                }

        return stats


class CachingAggregateProvider(DefaultAggregateProvider):
    """
    Enhanced provider with Redis caching for better performance.

    This provider adds:
    - Redis-based distributed caching
    - Automatic cache invalidation on events
    - Cache warming strategies
    """

    def __init__(self, event_store, redis_client=None, cache_ttl_seconds=300):
        """
        Initialize caching provider.

        Args:
            event_store: The event store instance
            redis_client: Optional Redis client for caching
            cache_ttl_seconds: Cache TTL in seconds (default: 5 minutes)
        """
        super().__init__(event_store)
        self.redis_client = redis_client
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_namespace = "aggregate_provider:cache"

    async def get_aggregate_for_snapshot(
            self,
            aggregate_id: uuid.UUID,
            aggregate_type: str
    ) -> Optional[Any]:
        """
        Get aggregate with Redis caching.

        First checks Redis cache, then falls back to loading from events.
        """
        if not self.redis_client:
            # No Redis, use parent implementation
            return await super().get_aggregate_for_snapshot(aggregate_id, aggregate_type)

        cache_key = f"{self._cache_namespace}:{aggregate_type}:{aggregate_id}"

        try:
            # Try Redis cache first
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                # Deserialize from cache
                aggregate_data = json.loads(cached_data)
                aggregate_class = self._aggregate_types.get(aggregate_type)
                if aggregate_class:
                    aggregate = aggregate_class(aggregate_id)
                    aggregate.restore_from_snapshot(aggregate_data['state'])
                    aggregate.version = aggregate_data['version']

                    self._cache_hits += 1
                    log.debug(f"Redis cache hit for {aggregate_type}:{aggregate_id}")
                    return aggregate

        except Exception as e:
            log.warning(f"Redis cache error: {e}")

        # Cache miss - load from events
        aggregate = await super().get_aggregate_for_snapshot(aggregate_id, aggregate_type)

        if aggregate and self.redis_client:
            try:
                # Cache in Redis
                cache_data = {
                    'state': aggregate.create_snapshot(),
                    'version': aggregate.version,
                    'cached_at': datetime.now(timezone.utc).isoformat()
                }

                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl_seconds,
                    json.dumps(cache_data)
                )

                log.debug(f"Cached aggregate {aggregate_type}:{aggregate_id} in Redis")

            except Exception as e:
                log.warning(f"Failed to cache aggregate in Redis: {e}")

        return aggregate

    async def invalidate_cache(self, aggregate_id: uuid.UUID, aggregate_type: str):
        """Invalidate cache for an aggregate (CachingAggregateProvider now delegates to parent's CacheManager)"""
        # Note: CachingAggregateProvider is deprecated in favor of using
        # DefaultAggregateProvider with CacheManager directly
        if self._cache_manager:
            cache_key = self._cache_manager._make_key(
                "aggregate", "instance", aggregate_type, str(aggregate_id)
            )
            await self._cache_manager.delete(cache_key)
            log.debug(f"Invalidated cache for {aggregate_type}:{aggregate_id}")

        # Legacy Redis cache (for backward compatibility)
        if self.redis_client:
            redis_key = f"{self._cache_namespace}:{aggregate_type}:{aggregate_id}"
            try:
                await self.redis_client.delete(redis_key)
            except Exception as e:
                log.warning(f"Failed to invalidate legacy Redis cache: {e}")


class RepositoryBasedAggregateProvider(AggregateSnapshotProvider):
    """
    Provider that uses existing aggregate repositories for loading.

    This is more efficient as it can leverage repository caching
    and snapshot loading.
    """

    def __init__(self, repositories: Dict[str, Any]):
        """
        Initialize with a map of aggregate repositories.

        Args:
            repositories: Map of aggregate_type -> repository instance
        """
        self.repositories = repositories
        log.info(f"RepositoryBasedAggregateProvider initialized with {len(repositories)} repositories")

    async def get_aggregate_for_snapshot(
            self,
            aggregate_id: uuid.UUID,
            aggregate_type: str
    ) -> Optional[Any]:
        """Get aggregate using its repository"""
        repository = self.repositories.get(aggregate_type)
        if not repository:
            log.error(f"No repository registered for aggregate type: {aggregate_type}")
            return None

        try:
            # Use repository to load aggregate
            aggregate = await repository.get_by_id(aggregate_id)
            if aggregate:
                log.debug(f"Loaded aggregate {aggregate_type}:{aggregate_id} via repository")
            return aggregate

        except Exception as e:
            log.error(f"Failed to load aggregate {aggregate_type}:{aggregate_id} via repository: {e}")
            return None


# Imports for JSON serialization if Redis caching is used
try:
    import json
except ImportError:
    json = None


# =============================================================================
# Factory Functions
# =============================================================================

def create_aggregate_provider(
        event_store,
        provider_type: str = "default",
        **kwargs
) -> AggregateSnapshotProvider:
    """
    Factory function to create aggregate providers.

    Args:
        event_store: The event store instance
        provider_type: Type of provider ("default", "caching", "repository")
        **kwargs: Additional arguments for the provider

    Returns:
        AggregateSnapshotProvider instance
    """
    if provider_type == "caching":
        return CachingAggregateProvider(event_store, **kwargs)
    elif provider_type == "repository":
        return RepositoryBasedAggregateProvider(**kwargs)
    else:
        return DefaultAggregateProvider(event_store)

# =============================================================================
# EOF
# =============================================================================