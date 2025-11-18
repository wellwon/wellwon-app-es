# =============================================================================
# File: app/exceptions.py
# Description: Common Exceptions for
# - Centralized error handling for services, domains, and API layers.
# FIXED: Added ProjectionRebuildError to __all__ list
# =============================================================================

from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel

__all__ = [
    # Base Exceptions
    "TradeCoreBaseError",

    # Original Broker Exceptions
    "BrokerAuthError",
    "BrokerRequestError",
    "BrokerResponseError",
    "BrokerNotFoundError",
    "AdapterNotInitializedError",
    "ConfigurationError",
    "DataValidationError",
    "InvalidOperationError",
    "ResourceNotFoundError",
    "PermissionError",

    # New Asset/Trading Specific Exceptions
    "AssetNotSupportedError",
    "InsufficientFundsError",
    "OrderValidationError",
    "SymbolNotFoundError",
    "RateLimitExceededError",
    "MarketClosedError",
    "OperationTimeoutError",
    "ApiVersionMismatchError",
    "CircuitBreakerOpenError",

    # Adapter-specific exceptions
    "AdapterAuthError",
    "AdapterConnectionError",
    "AdapterInvalidRequestError",
    "AdapterNotFoundError",
    "AdapterRateLimitError",
    "AdapterServerError",

    # Broker interaction exceptions
    "AdapterInitializationError",
    "BrokerOperationError",
    "BrokerConnectionError",
    "UserNotFoundError",
    "OrderNotFoundError",
    "ModuleNotFoundError",
    "ModuleOperationError",

    # FIXED: Event Store and Projection exceptions
    "ProjectionRebuildError",

    # Model classes
    "EmergencyExitResult"
]


class TradeCoreBaseError(Exception):
    """Base exception for all custom errors in the TradeCore application."""

    def __init__(
            self,
            message: str,
            status_code: Optional[int] = None,
            detail: Optional[Any] = None,
            error_code: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code

    def __str__(self) -> str:
        return self.message


class BrokerAuthError(TradeCoreBaseError):
    """Authentication or authorization failure for broker-level operations."""

    def __init__(
            self,
            message: str = "Broker authorization failed.",
            status_code: Optional[int] = None,  # Add this parameter
            detail: Optional[Any] = None
    ):
        super().__init__(message, status_code=status_code or 401, detail=detail, error_code="BROKER_AUTH_FAILURE")


class BrokerRequestError(TradeCoreBaseError):
    """Generic wrapper for broker REST / WebSocket request errors."""

    def __init__(
            self,
            message: str = "Broker request failed.",
            status_code: Optional[int] = None,  # Add this line
            status_code_from_broker: Optional[int] = None,
            payload_sent: Optional[Dict[str, Any]] = None,
            broker_response_preview: Optional[str] = None,
            detail: Optional[Any] = None
    ) -> None:
        self.status_code_from_broker = status_code_from_broker
        self.payload_sent = payload_sent
        self.broker_response_preview = broker_response_preview
        full_message = message
        if status_code_from_broker is not None:
            full_message += f" [Broker HTTP {status_code_from_broker}]"
        super().__init__(full_message, status_code=status_code, detail=detail, error_code="BROKER_REQUEST_ERROR")


class BrokerResponseError(TradeCoreBaseError):
    """Error for invalid, unexpected, or unparsable broker responses."""

    def __init__(
            self,
            message: str = "Broker response error.",
            response_preview: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        self.response_preview = response_preview
        super().__init__(message, status_code=502, detail=detail, error_code="BROKER_RESPONSE_INVALID")


class BrokerNotFoundError(TradeCoreBaseError):
    """Raised when a specific broker configuration or adapter class is not found or registered."""

    def __init__(
            self,
            message: str = "Broker not found or not supported.",
            broker_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"Broker '{broker_id}' not found or not supported." if broker_id else message
        super().__init__(final_message, status_code=404, detail=detail, error_code="BROKER_NOT_FOUND")


class AdapterNotInitializedError(TradeCoreBaseError):
    """Raised when an operation is attempted on an adapter that hasn't been properly initialized."""

    def __init__(
            self,
            message: str = "Broker adapter session not initialized.",
            broker_id: Optional[str] = None,
            user_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if broker_id and user_id:
            final_message = f"Adapter session for broker '{broker_id}', user '{user_id}' not initialized."
        super().__init__(final_message, status_code=409, detail=detail, error_code="ADAPTER_NOT_INITIALIZED")


class ConfigurationError(TradeCoreBaseError):
    """Raised for application configuration issues (e.g., missing environment variables)."""

    def __init__(
            self,
            message: str = "Application configuration error.",
            missing_key: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"Configuration error: {missing_key} is not set." if missing_key else message
        super().__init__(final_message, status_code=500, detail=detail, error_code="APP_CONFIG_ERROR")


class DataValidationError(TradeCoreBaseError):
    """Rose for Pydantic or other data validation errors."""

    def __init__(
            self,
            message: str = "Data validation error.",
            errors: Optional[Any] = None,
            detail: Optional[Any] = None
    ):
        self.errors = errors
        final_detail = {"errors": errors} if errors else {}
        if isinstance(detail, dict):
            final_detail.update(detail)
        elif detail:
            final_detail["additional_info"] = detail
        super().__init__(message, status_code=422, detail=final_detail, error_code="DATA_VALIDATION_ERROR")


class InvalidOperationError(TradeCoreBaseError):
    """Raised when an operation is attempted that is invalid in the current domain state or context."""

    def __init__(
            self,
            message: str = "Invalid operation attempted.",
            reason: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"{message}{f': {reason}' if reason else ''}"
        super().__init__(final_message, status_code=400, detail=detail, error_code="INVALID_OPERATION")


class ResourceNotFoundError(TradeCoreBaseError):
    """Generic error for when a requested resource is not found."""

    def __init__(
            self,
            resource_type: str = "Resource",
            resource_id: Optional[Any] = None,
            message: Optional[str] = None,
            status_code: Optional[int] = None,  # Add this line
            detail: Optional[Any] = None
    ):
        final_message = message or (
            f"{resource_type} '{resource_id}' not found." if resource_id else f"{resource_type} not found.")
        super().__init__(final_message, status_code=status_code or 404, detail=detail, error_code="RESOURCE_NOT_FOUND")


class PermissionError(TradeCoreBaseError):  # Custom version of Python's standard exception
    """Raised when a user is not authorized to perform an operation."""

    def __init__(
            self,
            message: str = "Permission denied.",
            detail: Optional[Any] = None
    ):
        super().__init__(message, status_code=403, detail=detail, error_code="PERMISSION_DENIED")


# --- New exceptions to support comprehensive adapter operations ---

class AssetNotSupportedError(TradeCoreBaseError):
    """Raised when an operation is attempted with an asset type not supported by the broker adapter."""

    def __init__(
            self,
            asset_type: Optional[str] = None,
            broker_id: Optional[str] = None,
            supported_assets: Optional[List[str]] = None,
            detail: Optional[Any] = None
    ):
        asset_info = f"Asset type '{asset_type}'" if asset_type else "This asset type"
        broker_info = f" for broker '{broker_id}'" if broker_id else ""
        supported_info = f" (Supported: {', '.join(supported_assets)})" if supported_assets else ""

        message = f"{asset_info} is not supported{broker_info}.{supported_info}"
        super().__init__(message, status_code=400, detail=detail, error_code="ASSET_NOT_SUPPORTED")


class InsufficientFundsError(TradeCoreBaseError):
    """Raised when an operation requires more funds than available in the account."""

    def __init__(
            self,
            message: str = "Insufficient funds for this operation.",
            required_amount: Optional[Union[float, str]] = None,
            available_amount: Optional[Union[float, str]] = None,
            currency: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if required_amount and available_amount:
            currency_str = f" {currency}" if currency else ""
            final_message = f"Insufficient funds: required {required_amount}{currency_str}, available {available_amount}{currency_str}"

        final_detail = {
            "required_amount": required_amount,
            "available_amount": available_amount,
            "currency": currency
        } if required_amount or available_amount else detail

        super().__init__(final_message, status_code=400, detail=final_detail, error_code="INSUFFICIENT_FUNDS")


class OrderValidationError(TradeCoreBaseError):
    """Raised when an order fails validation before submission to the broker."""

    def __init__(
            self,
            message: str = "Order validation failed.",
            validation_errors: Optional[List[str]] = None,
            order_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if order_id:
            final_message = f"Order '{order_id}' validation failed"
            if validation_errors and len(validation_errors) == 1:
                final_message += f": {validation_errors[0]}"

        final_detail = {"validation_errors": validation_errors} if validation_errors else {}
        if isinstance(detail, dict):
            final_detail.update(detail)
        elif detail:
            final_detail["additional_info"] = detail

        super().__init__(final_message, status_code=400, detail=final_detail, error_code="ORDER_VALIDATION_ERROR")


class SymbolNotFoundError(ResourceNotFoundError):
    """Raised when a trading symbol is not found or is invalid."""

    def __init__(
            self,
            symbol: Optional[str] = None,
            asset_class: Optional[str] = None,
            exchange: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        symbol_str = f"'{symbol}'" if symbol else ""
        asset_str = f" ({asset_class})" if asset_class else ""
        exchange_str = f" on {exchange}" if exchange else ""

        message = f"Symbol {symbol_str}{asset_str}{exchange_str} not found or invalid."

        super().__init__(
            resource_type="Symbol",
            resource_id=symbol,
            message=message,
            detail=detail
        )
        self.error_code = "SYMBOL_NOT_FOUND"


class RateLimitExceededError(TradeCoreBaseError):
    """Raised when an API rate limit is exceeded."""

    def __init__(
            self,
            message: str = "Rate limit exceeded.",
            status_code: Optional[int] = None,
            retry_after_seconds: Optional[int] = None,
            limit_type: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if retry_after_seconds:
            final_message = f"Rate limit exceeded. Retry after {retry_after_seconds} seconds."
        elif limit_type:
            final_message = f"{limit_type} rate limit exceeded."

        final_detail = {
            "retry_after_seconds": retry_after_seconds,
            "limit_type": limit_type
        } if retry_after_seconds or limit_type else detail

        super().__init__(final_message, status_code=status_code or 429, detail=final_detail,
                         error_code="RATE_LIMIT_EXCEEDED")


class MarketClosedError(TradeCoreBaseError):
    """Raised when an operation requires the market to be open."""

    def __init__(
            self,
            message: str = "Market is closed for this operation.",
            market: Optional[str] = None,
            next_open_time: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if market:
            final_message = f"{market} market is closed"
            if next_open_time:
                final_message += f". Next open time: {next_open_time}"

        final_detail = {
            "market": market,
            "next_open_time": next_open_time
        } if market or next_open_time else detail

        super().__init__(final_message, status_code=400, detail=final_detail, error_code="MARKET_CLOSED")


class OperationTimeoutError(TradeCoreBaseError):
    """Raised when an operation times out."""

    def __init__(
            self,
            message: str = "Operation timed out.",
            operation: Optional[str] = None,
            timeout_seconds: Optional[int] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if operation:
            final_message = f"{operation} operation timed out"
            if timeout_seconds:
                final_message += f" after {timeout_seconds} seconds"

        super().__init__(final_message, status_code=408, detail=detail, error_code="OPERATION_TIMEOUT")


class ApiVersionMismatchError(TradeCoreBaseError):
    """Raised when there's an API version mismatch between client and broker."""

    def __init__(
            self,
            message: str = "API version mismatch.",
            expected_version: Optional[str] = None,
            actual_version: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if expected_version and actual_version:
            final_message = f"API version mismatch: expected {expected_version}, got {actual_version}"

        final_detail = {
            "expected_version": expected_version,
            "actual_version": actual_version
        } if expected_version or actual_version else detail

        super().__init__(final_message, status_code=400, detail=final_detail, error_code="API_VERSION_MISMATCH")


# Add the new exception class right before the "Adapter-specific exceptions" section:
class CircuitBreakerOpenError(TradeCoreBaseError):
    """Raised when the circuit breaker pattern is active and blocking requests."""

    def __init__(
            self,
            message: str = "Circuit breaker is open.",
            retry_after_seconds: Optional[int] = None,
            service_name: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if service_name:
            final_message = f"Circuit breaker is open for {service_name}"
            if retry_after_seconds:
                final_message += f". Try again after {retry_after_seconds} seconds"

        final_detail = {
            "retry_after_seconds": retry_after_seconds,
            "service_name": service_name
        } if retry_after_seconds or service_name else detail

        super().__init__(final_message, status_code=503, detail=final_detail, error_code="CIRCUIT_BREAKER_OPEN")


# --- Adapter-specific exceptions (matching app.common.exceptions) ---

class AdapterAuthError(TradeCoreBaseError):
    """Authentication or authorization failure for adapter operations."""

    def __init__(
            self,
            message: str = "Adapter authorization failed.",
            adapter_name: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"{adapter_name} authorization failed" if adapter_name else message
        super().__init__(final_message, status_code=401, detail=detail, error_code="ADAPTER_AUTH_ERROR")


class AdapterConnectionError(TradeCoreBaseError):
    """Raised when a connection to an external service via an adapter fails."""

    def __init__(
            self,
            message: str = "Failed to connect to external service.",
            adapter_name: Optional[str] = None,
            service_name: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if adapter_name and service_name:
            final_message = f"Failed to connect to {service_name} via {adapter_name} adapter"
        elif adapter_name:
            final_message = f"Connection error in {adapter_name} adapter"

        super().__init__(final_message, status_code=503, detail=detail, error_code="ADAPTER_CONNECTION_ERROR")


class AdapterInvalidRequestError(TradeCoreBaseError):
    """Raised when an adapter rejects a request due to invalid parameters or format."""

    def __init__(
            self,
            message: str = "Invalid request to adapter.",
            adapter_name: Optional[str] = None,
            invalid_params: Optional[List[str]] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if adapter_name:
            final_message = f"Invalid request to {adapter_name} adapter"
            if invalid_params:
                if len(invalid_params) == 1:
                    final_message += f": Invalid parameter '{invalid_params[0]}'"
                else:
                    final_message += f": Invalid parameters {', '.join([f"'{p}'" for p in invalid_params])}"

        final_detail = {"invalid_params": invalid_params} if invalid_params else detail

        super().__init__(final_message, status_code=400, detail=final_detail, error_code="ADAPTER_INVALID_REQUEST")


class AdapterNotFoundError(TradeCoreBaseError):
    """Raised when a requested adapter is not registered or available."""

    def __init__(
            self,
            message: str = "Adapter not found.",
            adapter_name: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"Adapter '{adapter_name}' not found" if adapter_name else message
        super().__init__(final_message, status_code=404, detail=detail, error_code="ADAPTER_NOT_FOUND")


class AdapterRateLimitError(TradeCoreBaseError):
    """Raised when an adapter hits rate limits of an external service."""

    def __init__(
            self,
            message: str = "Adapter rate limit exceeded.",
            adapter_name: Optional[str] = None,
            retry_after_seconds: Optional[int] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if adapter_name:
            final_message = f"{adapter_name} adapter rate limit exceeded"
            if retry_after_seconds:
                final_message += f". Retry after {retry_after_seconds} seconds"

        final_detail = {"retry_after_seconds": retry_after_seconds} if retry_after_seconds else detail

        super().__init__(final_message, status_code=429, detail=final_detail, error_code="ADAPTER_RATE_LIMIT")


class AdapterServerError(TradeCoreBaseError):
    """Raised when an external service accessed via adapter returns a server error."""

    def __init__(
            self,
            message: str = "External service error.",
            adapter_name: Optional[str] = None,
            service_name: Optional[str] = None,
            status_code: Optional[int] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if service_name and adapter_name:
            final_message = f"{service_name} server error via {adapter_name} adapter"
            if status_code:
                final_message += f" (HTTP {status_code})"
        elif adapter_name:
            final_message = f"Server error in {adapter_name} adapter"

        final_detail = {
            "adapter_name": adapter_name,
            "service_name": service_name,
            "status_code": status_code
        } if adapter_name or service_name or status_code else detail

        super().__init__(final_message, status_code=502, detail=final_detail, error_code="ADAPTER_SERVER_ERROR")


# --- Additional broker interaction exceptions ---

class AdapterInitializationError(TradeCoreBaseError):
    """Raised when an adapter cannot be properly initialized."""

    def __init__(
            self,
            message: str = "Failed to initialize adapter.",
            adapter_name: Optional[str] = None,
            user_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if adapter_name:
            final_message = f"Failed to initialize {adapter_name} adapter"
            if user_id:
                final_message += f" for user '{user_id}'"

        super().__init__(final_message, status_code=500, detail=detail, error_code="ADAPTER_INIT_ERROR")


class BrokerOperationError(TradeCoreBaseError):
    """Raised when a broker operation fails."""

    def __init__(
            self,
            message: str = "Broker operation failed.",
            operation: Optional[str] = None,
            broker_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if operation and broker_id:
            final_message = f"{operation} operation failed for broker '{broker_id}'"
        elif operation:
            final_message = f"{operation} operation failed"

        super().__init__(final_message, status_code=400, detail=detail, error_code="BROKER_OPERATION_ERROR")


class BrokerConnectionError(TradeCoreBaseError):
    """Raised when connection to a broker fails."""

    def __init__(
            self,
            message: str = "Failed to connect to broker.",
            broker_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"Failed to connect to broker '{broker_id}'" if broker_id else message
        super().__init__(final_message, status_code=503, detail=detail, error_code="BROKER_CONNECTION_ERROR")


class UserNotFoundError(TradeCoreBaseError):
    """Raised when a user is not found."""

    def __init__(
            self,
            message: str = "User not found.",
            user_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = f"User '{user_id}' not found" if user_id else message
        super().__init__(final_message, status_code=404, detail=detail, error_code="USER_NOT_FOUND")


class OrderNotFoundError(TradeCoreBaseError):
    """Raised when an order is not found."""

    def __init__(
            self,
            message: str = "Order not found.",
            order_id: Optional[str] = None,
            user_id: Optional[str] = None,
            broker_id: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if order_id:
            final_message = f"Order '{order_id}' not found"
            if user_id:
                final_message += f" for user '{user_id}'"
            if broker_id:
                final_message += f" with broker '{broker_id}'"

        super().__init__(final_message, status_code=404, detail=detail, error_code="ORDER_NOT_FOUND")


class ModuleNotFoundError(TradeCoreBaseError):
    """Raised when a module is not found in a modular adapter."""

    def __init__(
            self,
            message: str = "Module not found.",
            module_name: Optional[str] = None,
            adapter_name: Optional[str] = None,
            available_modules: Optional[List[str]] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if module_name:
            final_message = f"Module '{module_name}' not found"
            if adapter_name:
                final_message += f" in {adapter_name} adapter"
            if available_modules:
                final_message += f". Available modules: {', '.join(available_modules)}"

        super().__init__(final_message, status_code=404, detail=detail, error_code="MODULE_NOT_FOUND")


class ModuleOperationError(TradeCoreBaseError):
    """Raised when a module operation fails."""

    def __init__(
            self,
            message: str = "Module operation failed.",
            module_name: Optional[str] = None,
            operation: Optional[str] = None,
            detail: Optional[Any] = None
    ):
        final_message = message
        if module_name and operation:
            final_message = f"{operation} operation failed in '{module_name}' module"
        elif module_name:
            final_message = f"Operation failed in '{module_name}' module"
        elif operation:
            final_message = f"{operation} operation failed in module"

        super().__init__(final_message, status_code=400, detail=detail, error_code="MODULE_OPERATION_ERROR")


# FIXED: Event Store and Projection Exceptions
class ProjectionRebuildError(Exception):
    """
    Raised when there's an error rebuilding projections from the event store.

    This exception is used to indicate failures during:
    - Projection rebuild initialization
    - Event replay from event store
    - Projection state reconstruction
    - Dependency resolution for projections
    """

    def __init__(
            self,
            message: str,
            projection_name: Optional[str] = None,
            event_count: Optional[int] = None,
            last_event_id: Optional[str] = None,
            original_error: Optional[Exception] = None
    ):
        """
        Initialize ProjectionRebuildError.

        Args:
            message: Error description
            projection_name: Name of the projection that failed
            event_count: Number of events processed before failure
            last_event_id: ID of the last event processed before failure
            original_error: The underlying exception that caused this error
        """
        self.projection_name = projection_name
        self.event_count = event_count
        self.last_event_id = last_event_id
        self.original_error = original_error

        # Build detailed error message
        parts = [message]
        if projection_name:
            parts.append(f"Projection: {projection_name}")
        if event_count is not None:
            parts.append(f"Events processed: {event_count}")
        if last_event_id:
            parts.append(f"Last event ID: {last_event_id}")
        if original_error:
            parts.append(f"Caused by: {type(original_error).__name__}: {str(original_error)}")

        self.message = " | ".join(parts)
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "projection_name": self.projection_name,
            "event_count": self.event_count,
            "last_event_id": self.last_event_id,
            "original_error": str(self.original_error) if self.original_error else None,
            "original_error_type": type(self.original_error).__name__ if self.original_error else None
        }


# Model classes
class EmergencyExitResult(BaseModel):
    """
    Result of an emergency exit operation.

    Contains information about canceled orders, closed positions,
    success status, any errors that occurred, and a timestamp.
    """
    success: bool
    errors: List[str]
    cancelled_orders: List[Any]  # Replace Any with Order model if available
    closed_positions: List[Any]  # Replace Any with Position model if available
    timestamp: str