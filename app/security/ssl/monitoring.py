# =============================================================================
# File: app/security/ssl/monitoring.py
# Description: Simple SSL metrics collection module for WellWon
# =============================================================================

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

log = logging.getLogger("wellwon.ssl.monitoring")


class MetricsCollector:
    """Simple metrics collector for monitoring."""

    def __init__(self):
        self.metrics = {}

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a gauge metric."""
        key = self._make_key(name, labels)
        self.metrics[key] = {
            "type": "gauge",
            "name": name,
            "value": value,
            "labels": labels or {},
            "timestamp": datetime.now(timezone.utc)
        }
        log.debug(f"Gauge {name}: {value}, labels: {labels}")

    def counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        if key not in self.metrics:
            self.metrics[key] = {
                "type": "counter",
                "name": name,
                "value": 0,
                "labels": labels or {},
                "timestamp": datetime.now(timezone.utc)
            }
        self.metrics[key]["value"] += value
        log.debug(f"Counter {name}: +{value}, labels: {labels}")

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram metric."""
        key = self._make_key(name, labels)
        if key not in self.metrics:
            self.metrics[key] = {
                "type": "histogram",
                "name": name,
                "values": [],
                "labels": labels or {},
                "timestamp": datetime.now(timezone.utc)
            }
        self.metrics[key]["values"].append(value)
        log.debug(f"Histogram {name}: {value}, labels: {labels}")

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return self.metrics.copy()


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector