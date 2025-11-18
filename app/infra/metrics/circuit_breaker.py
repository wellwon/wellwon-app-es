# app/infra/metrics/circuit_breaker.py
"""Circuit Breaker metrics."""

from prometheus_client import Gauge, Counter, Histogram

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Current state (0=closed, 1=open, 2=half_open)',
    ['name']
)

circuit_breaker_failures = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['name']
)

circuit_breaker_trips = Counter(
    'circuit_breaker_trips_total',
    'Number of times circuit breaker opened',
    ['name']
)

circuit_breaker_call_duration = Histogram(
    'circuit_breaker_call_duration_seconds',
    'Duration of calls through circuit breaker',
    ['name', 'result'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# app/infra/metrics/rate_limiter.py
"""Rate Limiter metrics."""

from prometheus_client import Counter, Gauge, Histogram

rate_limit_violations = Counter(
    'rate_limit_violations_total',
    'Total rate limit violations',
    ['name']
)

rate_limit_tokens = Gauge(
    'rate_limit_tokens_available',
    'Current available tokens',
    ['name']
)

rate_limit_wait_time = Histogram(
    'rate_limit_wait_time_seconds',
    'Time spent waiting for rate limit',
    ['name'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

rate_limit_requests = Counter(
    'rate_limit_requests_total',
    'Total rate limit checks',
    ['name', 'result']  # result: allowed/denied
)

# app/infra/metrics/retry.py
"""Retry mechanism metrics."""

from prometheus_client import Counter, Histogram

retry_attempts = Counter(
    'retry_attempts_total',
    'Total retry attempts',
    ['name', 'success']
)

retry_exhausted = Counter(
    'retry_exhausted_total',
    'Total retries exhausted',
    ['name']
)

retry_delay = Histogram(
    'retry_delay_seconds',
    'Retry delay distribution',
    ['name', 'attempt'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

retry_total_duration = Histogram(
    'retry_total_duration_seconds',
    'Total time spent in retry loops',
    ['name'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
)