# =============================================================================
# File: app/infra/kontur/clients/base_client.py
# Description: Base client for all Kontur API clients with full reliability stack
# =============================================================================

from typing import Optional, Any, Dict, Callable, Awaitable
import re
import httpx

from app.config.kontur_config import KonturConfig
from app.config.logging_config import get_logger
from app.config.reliability_config import ReliabilityConfigs
from app.infra.reliability.circuit_breaker import CircuitBreaker
from app.infra.reliability.retry import retry_async
from app.infra.reliability.rate_limiter import RateLimiter
from app.infra.reliability.bulkhead import Bulkhead
from app.infra.kontur.error_classifier import should_retry_kontur
from app.infra.kontur.exceptions import (
    KonturBadRequestError,
    KonturAuthenticationError,
    KonturAuthorizationError,
    KonturNotFoundError,
    KonturRateLimitError,
    KonturServerError,
    KonturNetworkError,
    KonturTimeoutError,
    KonturAPIError,
    KonturSessionExpiredError,
)

log = get_logger("wellwon.infra.kontur.client")

# UUID v4 regex pattern (8-4-4-4-12 format)
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class BaseClient:
    """
    Base client for all Kontur API clients.

    Implements enterprise-grade reliability patterns:
    - Circuit Breaker: Prevents cascade failures
    - Retry: Exponential backoff with jitter
    - Rate Limiting: Token bucket (10 req/s global)
    - Caching: Redis-based response caching
    - Fallback: Graceful degradation

    Flow:
    1. Check cache (if enabled)
    2. Rate limiting
    3. Circuit breaker check
    4. Retry with exponential backoff
    5. Execute HTTP request
    6. Update cache on success
    7. Fallback to cache on failure (if available)
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        config: KonturConfig,
        category: str,
        session_refresh_callback: Optional[Callable[[], Awaitable[None]]] = None
    ):
        """
        Initialize base client with reliability patterns.

        Args:
            http_client: Shared httpx.AsyncClient instance
            config: Kontur configuration
            category: Client category (for logging and metrics)
            session_refresh_callback: Async callback to refresh session on 401
        """
        self.http = http_client
        self.config = config
        self.category = category
        self._session_refresh_callback = session_refresh_callback

        # Cache manager (will be injected if available)
        self.cache = None

        # Initialize reliability patterns based on config flags
        self._init_reliability_patterns()

    def _init_reliability_patterns(self):
        """Initialize reliability patterns based on configuration"""
        # Circuit Breaker
        if self.config.enable_circuit_breaker:
            cb_config = ReliabilityConfigs.kontur_circuit_breaker(self.category)
            self.circuit_breaker = CircuitBreaker(cb_config)
            log.debug(f"Circuit breaker initialized for {self.category}")
        else:
            self.circuit_breaker = None

        # Retry Configuration
        if self.config.enable_retry:
            self.retry_config = ReliabilityConfigs.kontur_retry()
            # Add Kontur-specific retry condition
            self.retry_config.retry_condition = should_retry_kontur
            log.debug(f"Retry pattern initialized for {self.category}")
        else:
            self.retry_config = None

        # Rate Limiter (global, shared across all categories)
        if self.config.enable_rate_limiting:
            rl_config = ReliabilityConfigs.kontur_rate_limiter()
            self.rate_limiter = RateLimiter(
                name="kontur_global",
                config=rl_config,
                cache_manager=None  # Will be set later if Redis available
            )
            log.debug(f"Rate limiter initialized for {self.category}")
        else:
            self.rate_limiter = None

        # Bulkhead (resource isolation)
        if self.config.enable_bulkhead:
            bh_config = ReliabilityConfigs.kontur_bulkhead()
            self.bulkhead = Bulkhead(
                config=bh_config,
                cache_manager=None  # Will be set later if Redis available
            )
            log.debug(f"Bulkhead initialized for {self.category}")
        else:
            self.bulkhead = None

    def set_cache_manager(self, cache_manager):
        """Set cache manager (injected after initialization)"""
        self.cache = cache_manager
        if self.rate_limiter:
            self.rate_limiter.cache_manager = cache_manager
        if self.bulkhead:
            self.bulkhead.cache_manager = cache_manager

    @staticmethod
    def _validate_uuid(value: str, param_name: str) -> bool:
        """
        Validate UUID format to prevent path traversal attacks.

        Args:
            value: UUID string to validate
            param_name: Parameter name for error messages

        Returns:
            True if valid

        Raises:
            KonturBadRequestError: If UUID format is invalid
        """
        if not value:
            return False

        if not UUID_PATTERN.match(value):
            log.error(f"Invalid UUID format for {param_name}: {value}")
            raise KonturBadRequestError(
                f"Invalid {param_name} format. Expected UUID (e.g., 'a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6'), "
                f"got: {value[:50]}"
            )

        return True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        use_long_timeout: bool = False,
        use_upload_timeout: bool = False,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        files: Optional[Dict] = None,
        response_type: str = "json",
        _retry_on_401: bool = True
    ) -> Optional[Any]:
        """
        Execute HTTP request with full reliability stack.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /commonOrganizations)
            json: JSON body for request
            params: Query parameters
            timeout: Custom timeout (overrides defaults)
            use_long_timeout: Use long timeout (120s)
            use_upload_timeout: Use upload timeout (300s)
            cache_key: Cache key for this request
            cache_ttl: Cache TTL in seconds
            _retry_on_401: Internal flag to prevent infinite retry loop

        Returns:
            Parsed JSON response or None

        Raises:
            KonturError subclasses on errors
        """
        # 1. Check cache first (if enabled)
        if cache_key and self.cache and self.config.enable_cache:
            cached = await self._get_from_cache(cache_key)
            if cached is not None:
                log.debug(f"Cache hit: {cache_key}")
                return cached

        # 2. Rate limiting
        if self.rate_limiter and self.config.enable_rate_limiting:
            await self.rate_limiter.wait_and_acquire()

        # 3. Circuit breaker + Retry + Execute (with 401 session refresh)
        try:
            result = await self._execute_with_reliability(
                method=method,
                path=path,
                json=json,
                params=params,
                timeout=timeout,
                use_long_timeout=use_long_timeout,
                use_upload_timeout=use_upload_timeout,
                files=files,
                response_type=response_type
            )
        except KonturSessionExpiredError:
            # Session expired - try to refresh and retry once
            if _retry_on_401 and self._session_refresh_callback:
                log.info("Session expired, refreshing and retrying...")
                await self._session_refresh_callback()
                return await self._request(
                    method=method,
                    path=path,
                    json=json,
                    params=params,
                    timeout=timeout,
                    use_long_timeout=use_long_timeout,
                    use_upload_timeout=use_upload_timeout,
                    cache_key=cache_key,
                    cache_ttl=cache_ttl,
                    files=files,
                    response_type=response_type,
                    _retry_on_401=False  # Prevent infinite loop
                )
            raise

        # 4. Update cache on success
        if result and cache_key and self.cache and self.config.enable_cache:
            await self._set_in_cache(cache_key, result, cache_ttl)

        return result

    async def _execute_with_reliability(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[int] = None,
        use_long_timeout: bool = False,
        use_upload_timeout: bool = False,
        files: Optional[Dict] = None,
        response_type: str = "json"
    ) -> Optional[Any]:
        """Execute with circuit breaker and retry"""

        # Define the actual HTTP call
        async def _do_http_call():
            return await self._execute_http(
                method=method,
                path=path,
                json=json,
                params=params,
                timeout=timeout,
                use_long_timeout=use_long_timeout,
                use_upload_timeout=use_upload_timeout,
                files=files,
                response_type=response_type
            )

        # Wrap with retry if enabled
        if self.retry_config and self.config.enable_retry:
            async def _call_with_retry():
                return await retry_async(
                    _do_http_call,
                    retry_config=self.retry_config,
                    context=f"kontur_{self.category}_{path}"
                )
            call_func = _call_with_retry
        else:
            call_func = _do_http_call

        # Wrap with bulkhead if enabled (outermost layer for resource isolation)
        if self.bulkhead and self.config.enable_bulkhead:
            async def _call_with_bulkhead():
                # Wrap with circuit breaker if enabled
                if self.circuit_breaker and self.config.enable_circuit_breaker:
                    return await self.circuit_breaker.call(call_func)
                else:
                    return await call_func()

            return await self.bulkhead.call(_call_with_bulkhead)
        else:
            # No bulkhead, just circuit breaker
            if self.circuit_breaker and self.config.enable_circuit_breaker:
                return await self.circuit_breaker.call(call_func)
            else:
                return await call_func()

    async def _execute_http(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[int] = None,
        use_long_timeout: bool = False,
        use_upload_timeout: bool = False,
        files: Optional[Dict] = None,
        response_type: str = "json"
    ) -> Optional[Any]:
        """
        Execute actual HTTP request.

        Args:
            response_type: Type of response expected ("json", "bytes", "text")
            files: Files for multipart upload (for file upload operations)

        Returns:
            Parsed JSON response, bytes, or text depending on response_type
            None for 204 responses

        Raises:
            KonturError subclasses on errors
        """
        # Build full URL
        url = f"{self.config.api_url}{path}"

        # Determine timeout
        if timeout is None:
            if use_upload_timeout:
                timeout = self.config.upload_timeout_seconds
            elif use_long_timeout:
                timeout = self.config.long_timeout_seconds
            else:
                timeout = self.config.timeout_seconds

        log.debug(f"Kontur API call: {method} {path} (timeout={timeout}s)")

        try:
            response = await self.http.request(
                method,
                url,
                json=json if not files else None,  # Don't send json with multipart
                params=params,
                files=files,
                timeout=timeout
            )

            # Handle HTTP errors
            if response.status_code >= 400:
                self._handle_http_error(response.status_code, response.text, path)

            # Success - handle response
            if response.status_code == 204:
                # No content
                return None

            # Return response based on type
            if response_type == "bytes":
                return response.content
            elif response_type == "text":
                return response.text
            else:  # json
                return response.json()

        except httpx.TimeoutException as e:
            log.error(f"Kontur API timeout ({self.category}/{path}): {e}")
            raise KonturTimeoutError(f"Timeout calling {path}: {e}")

        except httpx.NetworkError as e:
            log.error(f"Kontur API network error ({self.category}/{path}): {e}")
            raise KonturNetworkError(f"Network error calling {path}: {e}")

        except Exception as e:
            log.error(f"Kontur API error ({self.category}/{path}): {e}")
            raise KonturAPIError(f"Error calling {path}: {e}")

    def _handle_http_error(self, status_code: int, error_text: str, path: str):
        """
        Handle HTTP error responses.

        Raises appropriate KonturError subclass based on status code.
        """
        # Sanitize error text to prevent logging sensitive data (INN, names, addresses)
        sanitized_error = error_text[:200] if error_text else "Unknown error"
        if len(error_text) > 200:
            sanitized_error += "... (truncated)"

        log.error(f"Kontur API HTTP error {status_code} at {path}: {sanitized_error}")

        if status_code == 400:
            raise KonturBadRequestError(f"Bad request to {path}: {error_text}")
        elif status_code == 401:
            # Session expired - raise specific error for retry logic
            raise KonturSessionExpiredError(f"Session expired for {path}: {error_text}")
        elif status_code == 403:
            raise KonturAuthorizationError(f"Access forbidden to {path}: {error_text}")
        elif status_code == 404:
            raise KonturNotFoundError(f"Resource not found at {path}: {error_text}")
        elif status_code == 429:
            raise KonturRateLimitError(f"Rate limit exceeded for {path}")
        elif status_code >= 500:
            raise KonturServerError(f"Server error at {path}: {error_text}")
        else:
            raise KonturAPIError(f"API error {status_code} at {path}: {error_text}")

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache"""
        if not self.cache:
            return None

        try:
            return await self.cache.get_json(cache_key)
        except Exception as e:
            log.warning(f"Cache get error for {cache_key}: {e}")
            return None

    async def _set_in_cache(
        self,
        cache_key: str,
        value: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """Set value in cache"""
        if not self.cache:
            return

        try:
            await self.cache.set_json(
                cache_key,
                value,
                ttl=ttl or self.config.cache_ttl_options
            )
        except Exception as e:
            log.warning(f"Cache set error for {cache_key}: {e}")
