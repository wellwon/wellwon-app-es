# app/infra/cqrs/query_bus.py
# =============================================================================
# File: app/infra/cqrs/query_bus.py
# Description: Production-ready Query Bus with string-based routing
# UPDATED: Using Pydantic v2 for all queries
# FIXED: Cache key generation now handles nested dictionaries properly
# =============================================================================

import logging
import json
import hashlib
from typing import Dict, Type, Any, Callable, Awaitable, Union, List, Optional, TypeVar
from abc import ABC, abstractmethod
import uuid

from pydantic import BaseModel

log = logging.getLogger("wellwon.cqrs.query")

# Type vars
TQuery = TypeVar('TQuery', bound='Query')
TResult = TypeVar('TResult')


# =============================================================================
# Base Classes
# =============================================================================

class Query(BaseModel):
    """Base class for all queries using Pydantic v2"""
    saga_id: Optional[uuid.UUID] = None


class IQueryHandler(ABC):
    """Base class for all query handlers"""

    @abstractmethod
    async def handle(self, query: Query) -> Any:
        """
        Handle the query and return result.
        Subclasses must implement this method.
        """
        pass


# =============================================================================
# Middleware Support (Query-specific)
# =============================================================================

class QueryMiddleware(ABC):
    """Base middleware class for queries"""

    @abstractmethod
    async def process(
            self,
            query: Any,
            next_handler: Callable[[Any], Awaitable[Any]]
    ) -> Any:
        """Process query and call next handler"""
        pass


class QueryLoggingMiddleware(QueryMiddleware):
    """Logs all queries with context"""

    async def process(self, query: Any, next_handler: Callable) -> Any:
        query_type = type(query).__name__
        saga_id = getattr(query, 'saga_id', None)

        if saga_id:
            log.info(f"Processing query {query_type} [saga: {saga_id}]")
        else:
            log.info(f"Processing query {query_type}")

        try:
            result = await next_handler(query)
            log.debug(f"Query {query_type} completed successfully")
            return result
        except Exception as e:
            log.error(f"Query {query_type} failed: {e}")
            raise


class QueryCachingMiddleware(QueryMiddleware):
    """Optional caching middleware for queries with TTL support"""

    # Queries that should not be cached
    SKIP_CACHE_QUERIES = {
        'CreateUserSessionQuery',  # Contains device_info dict that changes
        'GetUserActiveSessionsQuery',
        'GetActiveSessionCountQuery',
        'CheckConcurrentSessionsQuery',
        'GetUserByUsernameQuery',
        'GetUserProfileQuery',
    }

    def __init__(self, cache_ttl: int = 60):
        # Cache now stores tuples of (result, expiry_timestamp)
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._cache_ttl = cache_ttl

    async def process(self, query: Any, next_handler: Callable) -> Any:
        # Skip caching for certain queries
        query_type_name = type(query).__name__
        if query_type_name in self.SKIP_CACHE_QUERIES:
            log.debug(f"Skipping cache for query {query_type_name}")
            return await next_handler(query)

        # Generate cache key
        try:
            cache_key = self._generate_cache_key(query)
        except Exception as e:
            log.warning(f"Failed to generate cache key for {query_type_name}: {e}. Skipping cache.")
            return await next_handler(query)

        # Check cache with TTL validation
        if cache_key in self._cache:
            cached_result, expiry_time = self._cache[cache_key]
            import time
            current_time = time.time()

            # Check if cache entry is still valid
            if current_time < expiry_time:
                log.debug(f"Cache hit for query {query_type_name} (expires in {expiry_time - current_time:.1f}s)")
                return cached_result
            else:
                # Cache expired, remove it
                log.debug(f"Cache expired for query {query_type_name}")
                del self._cache[cache_key]

        result = await next_handler(query)

        # Cache the result with expiry timestamp
        import time
        expiry_time = time.time() + self._cache_ttl
        self._cache[cache_key] = (result, expiry_time)
        log.debug(f"Cached query {query_type_name} for {self._cache_ttl}s")
        return result

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.
        Returns number of entries invalidated.
        """
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            log.info(f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}")

        return len(keys_to_delete)

    def clear_all(self) -> int:
        """Clear all cache entries. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        if count > 0:
            log.info(f"Cleared all {count} cache entries")
        return count

    def _generate_cache_key(self, query: Any) -> str:
        """Generate a cache key from query - handles nested dicts properly"""
        query_type_name = type(query).__name__

        try:
            if isinstance(query, BaseModel):
                # For Pydantic models, use model_dump with json serialization
                query_dict = query.model_dump(exclude={'saga_id'})
                # Convert to JSON to handle nested structures
                query_json = json.dumps(query_dict, sort_keys=True, default=str)
            else:
                # For non-Pydantic objects
                query_dict = query.__dict__ if hasattr(query, '__dict__') else {}
                # Exclude saga_id from cache key
                query_dict = {k: v for k, v in query_dict.items() if k != 'saga_id'}
                # Convert to JSON to handle nested structures
                query_json = json.dumps(query_dict, sort_keys=True, default=str)

            # Use SHA256 for consistent hashing
            hash_digest = hashlib.sha256(query_json.encode()).hexdigest()[:16]
            return f"{query_type_name}:{hash_digest}"

        except Exception as e:
            # If we can't serialize, fall back to object id
            log.debug(f"Could not serialize query {query_type_name} for caching: {e}")
            return f"{query_type_name}:{id(query)}"


class QueryMetricsMiddleware(QueryMiddleware):
    """Tracks query execution metrics"""

    def __init__(self):
        self.query_counts: Dict[str, int] = {}
        self.query_errors: Dict[str, int] = {}

    async def process(self, query: Any, next_handler: Callable) -> Any:
        query_name = type(query).__name__

        # Increment query count
        self.query_counts[query_name] = self.query_counts.get(query_name, 0) + 1

        try:
            result = await next_handler(query)
            return result
        except Exception as e:
            # Increment error count
            self.query_errors[query_name] = self.query_errors.get(query_name, 0) + 1
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get query execution metrics"""
        return {
            "query_counts": self.query_counts.copy(),
            "query_errors": self.query_errors.copy(),
            "total_queries": sum(self.query_counts.values()),
            "total_errors": sum(self.query_errors.values())
        }


# =============================================================================
# Query Bus Implementation
# =============================================================================

class QueryBus:
    """
    Query Bus for read operations.
    Supports both type-based and string-based routing for flexibility.
    """

    def __init__(self, enable_caching: bool = False):
        # Type-based handlers
        self._handlers: Dict[Type[Query], IQueryHandler] = {}
        self._handler_factories: Dict[Type[Query], Callable[[], IQueryHandler]] = {}

        # String-based handlers
        self._string_handlers: Dict[str, IQueryHandler] = {}
        self._string_handler_factories: Dict[str, Callable[[], IQueryHandler]] = {}

        self._middleware: List[QueryMiddleware] = []

        # Metrics middleware
        self._metrics_middleware = QueryMetricsMiddleware()

        # Add default middleware
        self.use(QueryLoggingMiddleware())
        self.use(self._metrics_middleware)

        # Add caching if enabled
        if enable_caching:
            self.use(QueryCachingMiddleware())

    def use(self, middleware: QueryMiddleware) -> 'QueryBus':
        """Add middleware to the pipeline"""
        self._middleware.append(middleware)
        return self

    def register_handler(
            self,
            query_type: Union[Type[Query], str],
            handler_factory: Callable[[], IQueryHandler]
    ) -> None:
        """
        Register a handler factory for a query type.
        Can accept either a type or a string name.
        """
        if isinstance(query_type, str):
            self._string_handler_factories[query_type] = handler_factory
            log.debug(f"Registered query handler for name '{query_type}'")
        else:
            self._handler_factories[query_type] = handler_factory
            # Also register by string name
            query_name = query_type.__name__
            self._string_handler_factories[query_name] = handler_factory
            log.debug(f"Registered query handler for {query_name}")

    def register_handlers(self, registry: Dict[Union[Type[Query], str], Callable]) -> None:
        """Bulk register handlers"""
        for query_type, factory in registry.items():
            self.register_handler(query_type, factory)

    async def query(self, query: TQuery) -> TResult:
        """Execute a query through the middleware pipeline"""
        # Build the handler chain
        handler = self._build_handler_chain(query)

        # Execute
        return await handler(query)

    def _build_handler_chain(self, query: Query) -> Callable:
        """Build the middleware chain for queries"""
        query_type = type(query)
        query_name = query_type.__name__

        # Try string-based lookup first
        if query_name not in self._string_handlers:
            factory = self._string_handler_factories.get(query_name)

            # Fallback to type-based
            if not factory:
                factory = self._handler_factories.get(query_type)

            if not factory:
                # Provide helpful error message
                registered_types = [t.__name__ for t in self._handler_factories.keys()]
                registered_strings = list(self._string_handler_factories.keys())
                all_registered = sorted(set(registered_types + registered_strings))

                raise ValueError(
                    f"No handler registered for query {query_name}. "
                    f"Registered handlers: {all_registered}"
                )

            handler_instance = factory()
            self._string_handlers[query_name] = handler_instance
            if query_type in self._handler_factories:
                self._handlers[query_type] = handler_instance

        final_handler = self._string_handlers.get(query_name) or self._handlers.get(query_type)

        # Build the chain
        async def handler_wrapper(q):
            return await final_handler.handle(q)

        chain = handler_wrapper

        # Wrap with middleware
        for middleware in reversed(self._middleware):
            current_chain = chain

            async def wrapped(q, mw=middleware, next_h=current_chain):
                return await mw.process(q, lambda query: next_h(query))

            chain = wrapped

        return chain

    def get_metrics(self) -> Dict[str, Any]:
        """Get query execution metrics"""
        return self._metrics_middleware.get_metrics()

    def get_handler_info(self) -> Dict[str, Any]:
        """Get information about registered handlers"""
        return {
            "type_handlers": [h.__name__ for h in self._handler_factories.keys()],
            "string_handlers": list(self._string_handler_factories.keys()),
            "total_handlers": len(self._handler_factories) + len(
                set(self._string_handler_factories.keys()) - {h.__name__ for h in self._handler_factories.keys()}),
            "middleware_count": len(self._middleware)
        }

# =============================================================================
# EOF
# =============================================================================