"""Base metrics implementation using a Prometheus client."""
import asyncio
import os
from prometheus_client import Counter, Histogram, Gauge

# Global metrics configuration
METRICS_ENABLED = bool(os.getenv("ENABLE_METRICS", "false").lower() == "true")


class MetricsFactory:
    """Factory for creating metrics with consistent naming."""

    @staticmethod
    def counter(name, description, labels=None):
        """Create a counter-metric."""
        return Counter(
            name=f"synapse_{name}",
            documentation=description,
            labelnames=labels or []
        ) if METRICS_ENABLED else DummyCounter(name, description, labels)

    @staticmethod
    def histogram(name, description, labels=None, buckets=None):
        """Create a histogram metric."""
        return Histogram(
            name=f"synapse_{name}",
            documentation=description,
            labelnames=labels or [],
            buckets=buckets or (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        ) if METRICS_ENABLED else DummyHistogram(name, description, labels)

    @staticmethod
    def gauge(name, description, labels=None):
        """Create a gauge metric."""
        return Gauge(
            name=f"synapse_{name}",
            documentation=description,
            labelnames=labels or []
        ) if METRICS_ENABLED else DummyGauge(name, description, labels)


# Fake implementations for when metrics are disabled
class DummyMetric:
    def __init__(self, name, description, labels=None):
        self.name = name
        self.description = description

    def labels(self, **kwargs):
        return self


class DummyCounter(DummyMetric):
    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass


class DummyHistogram(DummyMetric):
    def observe(self, value):
        pass

    def time(self):
        def decorator(func):
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            def sync_wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator


class DummyGauge(DummyMetric):
    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def set(self, value):
        pass