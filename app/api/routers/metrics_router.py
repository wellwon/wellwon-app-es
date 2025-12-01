# app/api/routers/metrics_router.py
"""
Prometheus metrics endpoint for WSE and application monitoring
"""

from fastapi import APIRouter, Response
import logging

log = logging.getLogger("wellwon.metrics")

router = APIRouter(tags=["monitoring"])

# Try to import prometheus_client
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    log.warning("prometheus_client not installed - /metrics endpoint will return empty response")


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint

    Exposes metrics in Prometheus text format for scraping:
    - WSE Pub/Sub metrics (publish/receive, latency, errors)
    - WebSocket connection metrics
    - Queue metrics (size, dropped, backpressure)
    - Dead Letter Queue metrics
    - Circuit breaker states

    Usage:
        curl http://localhost:5001/metrics

    Prometheus scrape configuration:
        scrape_configs:
          - job_name: 'wellwon-wse'
            scrape_interval: 15s
            static_configs:
              - targets: ['localhost:5001']
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain"
        )

    try:
        # Import metrics to ensure they're registered
        from app.infra.metrics.wse_metrics import (
            pubsub_published_total,
            pubsub_received_total,
            ws_connections_active,
            dlq_messages_total
        )

        # Import Telegram metrics
        from app.infra.metrics.telegram_metrics import (
            telegram_webhook_requests_total,
            telegram_messages_sent_total,
            telegram_health_status,
        )

        # Generate Prometheus metrics in text format
        metrics_output = generate_latest()

        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST
        )

    except Exception as e:
        log.error(f"Failed to generate metrics: {e}", exc_info=True)
        return Response(
            content=f"# Error generating metrics: {str(e)}\n",
            media_type="text/plain",
            status_code=500
        )


@router.get("/health/metrics")
async def metrics_health():
    """
    Health check for metrics system

    Returns:
        status: healthy/degraded
        prometheus_available: true/false
        message: description
    """
    return {
        "status": "healthy" if PROMETHEUS_AVAILABLE else "degraded",
        "prometheus_available": PROMETHEUS_AVAILABLE,
        "message": "Metrics system operational" if PROMETHEUS_AVAILABLE else "prometheus_client not installed"
    }
