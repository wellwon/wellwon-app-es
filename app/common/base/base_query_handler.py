# app/common/base/base_query_handler.py
"""
Base Query Handler

Provides common infrastructure for all query handlers in WellWon.

Unlike BaseCommandHandler (which handles event publishing and sagas),
BaseQueryHandler is LIGHTWEIGHT and provides:
- Logging infrastructure
- Authorization helpers
- Error handling wrappers
- Performance tracking (optional)
- Abstract handle() method

Key Principles:
1. Queries are READ-ONLY operations (no events, no state changes)
2. Handlers are OPTIONAL to inherit from this base (lightweight)
3. No saga/outbox/versioning needed (queries don't write)
4. Focus on utilities, not enforcement
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Generic, TypeVar
from uuid import UUID
from datetime import datetime, timezone

from app.common.exceptions.exceptions import PermissionError, ResourceNotFoundError

# Type variables for generic query and result types
TQuery = TypeVar('TQuery')
TResult = TypeVar('TResult')


class BaseQueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Base class for all query handlers in WellWon.

    Provides:
    - Common logging infrastructure
    - Authorization validation helpers
    - Error handling patterns
    - Performance tracking hooks
    - Abstract handle() method

    Usage:
        @query_handler(GetOrderQuery)
        class GetOrderQueryHandler(BaseQueryHandler[GetOrderQuery, OrderReadModel]):
            def __init__(self, deps: HandlerDependencies):
                super().__init__()
                self.order_repo = deps.order_read_repo

            async def handle(self, query: GetOrderQuery) -> Optional[OrderReadModel]:
                # Validate authorization
                self.validate_resource_ownership(
                    resource_user_id=order.user_id,
                    requesting_user_id=query.user_id,
                    resource_type="order"
                )

                # Execute query
                return await self.order_repo.get_by_id(
                    order_id=query.order_id,
                    user_id=query.user_id
                )

    Note: Inheriting from this base class is OPTIONAL.
    Simple query handlers can work without it.
    """

    def __init__(self):
        """
        Initialize base query handler.

        Sets up logging infrastructure for query handler.
        """
        # Instance logger (better than module-level for base class)
        self.log = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        # Performance tracking (optional)
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """
        Handle the query and return result.

        Must be implemented by subclasses.

        Args:
            query: Query object containing parameters

        Returns:
            Query result (read model, DTO, or primitive type)

        Raises:
            ResourceNotFoundError: If resource not found
            PermissionError: If user not authorized
            ValueError: If query parameters invalid
        """
        pass

    # =========================================================================
    # Authorization Helpers
    # =========================================================================

    def validate_resource_ownership(
        self,
        resource_user_id: UUID,
        requesting_user_id: UUID,
        resource_type: str = "resource",
        resource_id: Optional[UUID] = None
    ) -> None:
        """
        Validate that the requesting user owns the resource.

        Common pattern for authorization in queries.

        Args:
            resource_user_id: User ID who owns the resource
            requesting_user_id: User ID making the request
            resource_type: Type of resource (for error message)
            resource_id: Optional resource ID (for error message)

        Raises:
            PermissionError: If user doesn't own resource

        Example:
            self.validate_resource_ownership(
                resource_user_id=order.user_id,
                requesting_user_id=query.user_id,
                resource_type="order",
                resource_id=query.order_id
            )
        """
        if resource_user_id != requesting_user_id:
            resource_str = f"{resource_type} {resource_id}" if resource_id else resource_type
            self.log.warning(
                f"Authorization failed - User {requesting_user_id} "
                f"attempted to access {resource_str} owned by {resource_user_id}"
            )
            raise PermissionError(
                f"Unauthorized access to {resource_str}"
            )

    def validate_optional_resource_ownership(
        self,
        resource_user_id: Optional[UUID],
        requesting_user_id: Optional[UUID],
        resource_type: str = "resource"
    ) -> bool:
        """
        Validate ownership when user_id is optional (e.g., admin queries).

        Args:
            resource_user_id: User ID who owns the resource (may be None)
            requesting_user_id: User ID making the request (may be None)
            resource_type: Type of resource (for logging)

        Returns:
            True if authorized, False otherwise

        Example:
            # Admin query (no user_id filter)
            if query.user_id is None:
                # Admin access - no ownership check
                pass
            else:
                # User access - validate ownership
                if not self.validate_optional_resource_ownership(
                    resource_user_id=conn.user_id,
                    requesting_user_id=query.user_id,
                    resource_type="connection"
                ):
                    return None  # Not authorized
        """
        # If no requesting user specified, assume admin/system access
        if requesting_user_id is None:
            return True

        # If resource has no owner, allow access
        if resource_user_id is None:
            return True

        # Check ownership
        if resource_user_id != requesting_user_id:
            self.log.debug(
                f"Ownership check failed for {resource_type} - "
                f"Resource owner: {resource_user_id}, Requester: {requesting_user_id}"
            )
            return False

        return True

    # =========================================================================
    # Error Handling Helpers
    # =========================================================================

    def handle_not_found(
        self,
        resource: Any,
        resource_type: str,
        resource_id: Any,
        raise_exception: bool = True
    ) -> Optional[Any]:
        """
        Handle resource not found scenario.

        Args:
            resource: Resource object (or None if not found)
            resource_type: Type of resource (for error message)
            resource_id: ID of resource
            raise_exception: If True, raise exception. If False, return None.

        Returns:
            Resource if found, None if not found and raise_exception=False

        Raises:
            ResourceNotFoundError: If resource not found and raise_exception=True

        Example:
            order = await self.order_repo.get_by_id(query.order_id)

            # Option 1: Raise exception
            order = self.handle_not_found(
                resource=order,
                resource_type="Order",
                resource_id=query.order_id
            )

            # Option 2: Return None
            order = self.handle_not_found(
                resource=order,
                resource_type="Order",
                resource_id=query.order_id,
                raise_exception=False
            )
        """
        if resource is None:
            error_msg = f"{resource_type} {resource_id} not found"

            if raise_exception:
                self.log.warning(error_msg)
                raise ResourceNotFoundError(error_msg)
            else:
                self.log.debug(error_msg)
                return None

        return resource

    def safe_getattr(
        self,
        obj: Any,
        attr: str,
        default: Any = None,
        transform: Optional[callable] = None
    ) -> Any:
        """
        Safely get attribute with optional transformation.

        Common pattern for converting enums to strings.

        Args:
            obj: Object to get attribute from
            attr: Attribute name
            default: Default value if attribute doesn't exist
            transform: Optional transformation function (e.g., lambda x: x.value)

        Returns:
            Attribute value (optionally transformed)

        Example:
            # Get enum as string value
            status = self.safe_getattr(
                obj=conn.last_connection_status,
                attr='value',
                default='unknown'
            )

            # Or with transform
            environment = self.safe_getattr(
                obj=conn,
                attr='environment',
                default='paper',
                transform=lambda x: x.value if hasattr(x, 'value') else x
            )
        """
        value = getattr(obj, attr, default)

        if transform and value is not None:
            try:
                return transform(value)
            except Exception as e:
                self.log.debug(f"Transform failed for {attr}: {e}")
                return value

        return value

    # =========================================================================
    # Performance Tracking (Optional)
    # =========================================================================

    def start_tracking(self) -> None:
        """
        Start tracking query execution time.

        Optional - handlers can call this to track performance.

        Example:
            async def handle(self, query: GetOrderQuery):
                self.start_tracking()
                result = await self.order_repo.get_by_id(query.order_id)
                self.end_tracking()
                return result
        """
        self._start_time = datetime.now(timezone.utc)

    def end_tracking(self, log_duration: bool = True) -> Optional[float]:
        """
        End tracking and optionally log duration.

        Args:
            log_duration: If True, log the duration at DEBUG level

        Returns:
            Duration in milliseconds, or None if tracking not started

        Example:
            self.start_tracking()
            result = await self.execute_complex_query()
            duration_ms = self.end_tracking()

            if duration_ms > 1000:
                self.log.warning(f"Slow query: {duration_ms}ms")
        """
        if self._start_time is None:
            return None

        self._end_time = datetime.now(timezone.utc)
        duration_ms = (self._end_time - self._start_time).total_seconds() * 1000

        if log_duration:
            self.log.debug(
                f"Query {self.__class__.__name__} executed in {duration_ms:.2f}ms"
            )

        return duration_ms

    def get_execution_time(self) -> Optional[float]:
        """
        Get query execution time without ending tracking.

        Returns:
            Duration in milliseconds, or None if tracking not started
        """
        if self._start_time is None:
            return None

        now = datetime.now(timezone.utc)
        return (now - self._start_time).total_seconds() * 1000

    # =========================================================================
    # Logging Helpers
    # =========================================================================

    def log_query_start(self, query: TQuery) -> None:
        """
        Log query start at DEBUG level.

        Args:
            query: Query object

        Example:
            async def handle(self, query: GetOrderQuery):
                self.log_query_start(query)
                return await self.order_repo.get_by_id(query.order_id)
        """
        self.log.debug(
            f"Handling query {self.__class__.__name__}: {query}"
        )

    def log_query_result(
        self,
        query: TQuery,
        result: TResult,
        duration_ms: Optional[float] = None
    ) -> None:
        """
        Log query result at DEBUG level.

        Args:
            query: Query object
            result: Query result
            duration_ms: Optional execution duration

        Example:
            async def handle(self, query: GetOrderQuery):
                self.start_tracking()
                result = await self.order_repo.get_by_id(query.order_id)
                self.log_query_result(query, result, self.end_tracking(log_duration=False))
                return result
        """
        duration_str = f" in {duration_ms:.2f}ms" if duration_ms else ""
        result_summary = self._summarize_result(result)

        self.log.debug(
            f"Query {self.__class__.__name__} completed{duration_str}: {result_summary}"
        )

    def _summarize_result(self, result: Any) -> str:
        """
        Create a summary string for query result.

        Args:
            result: Query result

        Returns:
            Summary string
        """
        if result is None:
            return "None"
        elif isinstance(result, list):
            return f"List[{len(result)} items]"
        elif hasattr(result, 'id'):
            return f"{result.__class__.__name__}(id={result.id})"
        else:
            return f"{result.__class__.__name__}"


# =============================================================================
# Convenience Interfaces (Optional)
# =============================================================================

class IQueryHandler(ABC):
    """
    Simple interface for query handlers that don't need BaseQueryHandler utilities.

    This is the minimal interface - handlers can implement this directly
    without inheriting from BaseQueryHandler.

    Example:
        @query_handler(GetOrderQuery)
        class GetOrderQueryHandler(IQueryHandler):
            def __init__(self, deps: HandlerDependencies):
                self.order_repo = deps.order_read_repo

            async def handle(self, query: GetOrderQuery) -> OrderReadModel:
                return await self.order_repo.get_by_id(query.order_id)
    """

    @abstractmethod
    async def handle(self, query: Any) -> Any:
        """Handle the query"""
        pass
