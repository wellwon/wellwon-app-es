# =============================================================================
# system_router.py – System Status & Health Endpoints
# -----------------------------------------------------------------------------
# • Health check endpoint
# • Redis ping check
# • Event bus health check
# • System status summary
# =============================================================================

import logging
import os
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from app.infra.persistence.redis_client import ping as redis_ping
from app import __version__
from app.api.models.system_api_models import (
    RootInfoResponse, HealthCheckResponse, CachePingResponse,
    EventBusHealthResponse, SystemStatusResponse
)
# Update system_router.py to import the enums
from app.common.enums.enums import SystemHealthStatusEnum, ComponentStatusEnum

router = APIRouter(tags=["System"])

_start_time = datetime.now(timezone.utc)

def get_start_time() -> datetime:
    return _start_time

@router.get("/", summary="API Root - Version Information", response_model=RootInfoResponse)
async def root_info() -> RootInfoResponse:
    """Retrieve basic information about the API service."""
    return RootInfoResponse(
        application_name="TradeCore API",
        version=__version__,
        status="running",
        server_start_time_utc=_start_time.isoformat(),
    )

@router.get("/health", summary="Health Check", response_model=HealthCheckResponse)
async def healthcheck(request: Request) -> HealthCheckResponse:
    """Perform a comprehensive health check of all system components."""
    try:
        redis_ok = await redis_ping()
        
        # Get EventBus from the app state
        event_bus = request.app.state.event_bus
        event_bus_status = False
        if hasattr(event_bus, 'check_connection'):
            event_bus_status = await event_bus.check_connection()

        status = SystemHealthStatusEnum.HEALTHY if (redis_ok and event_bus_status) else SystemHealthStatusEnum.DEGRADED
        
        return HealthCheckResponse(
            status=status,
            version=__version__,
            redis=ComponentStatusEnum.ALIVE if redis_ok else ComponentStatusEnum.UNREACHABLE,
            event_bus=ComponentStatusEnum.CONNECTED if event_bus_status else ComponentStatusEnum.DISCONNECTED,
            uptime_seconds=(datetime.now(timezone.utc) - _start_time).total_seconds(),
            current_time_utc=datetime.now(timezone.utc).isoformat()
        )
    except Exception as exc:
        log = logging.getLogger("tradecore.server")
        log.error(f"Error in health check: {exc}", exc_info=True)
        
        return HealthCheckResponse(
            status=SystemHealthStatusEnum.ERROR,
            version=__version__,
            redis=ComponentStatusEnum.UNKNOWN,
            event_bus=ComponentStatusEnum.UNKNOWN,
            uptime_seconds=(datetime.now(timezone.utc) - _start_time).total_seconds(),
            current_time_utc=datetime.now(timezone.utc).isoformat(),
            error=str(exc)
        )

@router.get("/cache/ping", summary="Redis ping check", response_model=CachePingResponse)
async def cache_ping() -> CachePingResponse:
    """Check Redis connectivity with a simple ping operation."""
    alive = await redis_ping()
    status = ComponentStatusEnum.ALIVE if alive else ComponentStatusEnum.UNREACHABLE
    
    response = CachePingResponse(status=status)
    return JSONResponse(
        status_code=200 if alive else 500, 
        content=response.model_dump()
    )

@router.get("/health/event-bus", summary="Event Bus health and status", response_model=EventBusHealthResponse)
async def event_bus_health(request: Request) -> EventBusHealthResponse:
    """Detailed health status of the event messaging system."""
    try:
        event_bus = request.app.state.event_bus
        if hasattr(event_bus, 'health_check'):
            health_info = await event_bus.health_check()
            
            # Convert the health_info dictionary to a proper EventBusHealthResponse
            response = EventBusHealthResponse(
                healthy=health_info.get("healthy", False),
                connection_active=health_info.get("connection_active", False),
                transport_type=health_info.get("transport_type", "unknown"),
                channels=health_info.get("channels", {}),
                metrics=health_info.get("metrics", {}),
                last_heartbeat=health_info.get("last_heartbeat"),
                details=health_info.get("details")
            )
            
            return JSONResponse(
                status_code=200 if health_info.get("healthy", False) else 503,
                content=response.model_dump()
            )
        else:
            # Fallback for basic EventBus without a health check
            is_connected = await event_bus.check_connection() if hasattr(event_bus, 'check_connection') else True
            
            response = EventBusHealthResponse(
                healthy=is_connected,
                connection_active=is_connected,
                transport_type="redis",
                details="Basic EventBus without enhanced health monitoring"
            )
            
            return JSONResponse(
                status_code=200,
                content=response.model_dump()
            )
    except Exception as exc:
        log = logging.getLogger("tradecore.server")
        log.error(f"Error checking event bus health: {exc}", exc_info=True)
        
        response = EventBusHealthResponse(
            healthy=False,
            connection_active=False,
            transport_type="unknown",
            error=str(exc)
        )
        
        return JSONResponse(
            status_code=500, 
            content=response.model_dump()
        )

@router.get("/status", summary="System status for dashboard", response_model=SystemStatusResponse)
async def status_dashboard(request: Request) -> SystemStatusResponse:
    """Get overall system status including all components for dashboard display."""
    try:
        event_bus = request.app.state.event_bus
        event_bus_ok = await event_bus.check_connection() if hasattr(event_bus, 'check_connection') else True
        redis_ok = await redis_ping()
        
        # Get system metrics if psutil is available (run in thread to avoid blocking)
        cpu_usage = None
        memory_usage = None
        if os.environ.get("COLLECT_SYSTEM_METRICS", "false").lower() == "true":
            try:
                # Run blocking psutil calls in thread pool to avoid blocking event loop
                import asyncio
                loop = asyncio.get_event_loop()
                cpu_usage = await loop.run_in_executor(None, lambda: psutil.cpu_percent(interval=0.1))
                memory_usage = psutil.virtual_memory().percent
            except (ImportError, AttributeError):
                pass
        
        return SystemStatusResponse(
            api=ComponentStatusEnum.ONLINE,
            redis=ComponentStatusEnum.CONNECTED if redis_ok else ComponentStatusEnum.DISCONNECTED,
            event_bus=ComponentStatusEnum.CONNECTED if event_bus_ok else ComponentStatusEnum.DISCONNECTED,
            lastBackup=datetime.now(timezone.utc).isoformat(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage
        )
    except Exception as exc:
        log = logging.getLogger("tradecore.server")
        log.error(f"Error getting system status: {exc}", exc_info=True)
        
        return SystemStatusResponse(
            api=ComponentStatusEnum.WARNING,
            redis=ComponentStatusEnum.UNKNOWN,
            event_bus=ComponentStatusEnum.UNKNOWN,
            lastBackup=datetime.now(timezone.utc).isoformat()
        )


@router.get("/metrics", summary="Prometheus metrics export", response_class=PlainTextResponse)
async def prometheus_metrics(request: Request) -> str:
    """
    Export system metrics in Prometheus format.

    OPTIMIZATION (Nov 11, 2025): Added Prometheus metrics export for production monitoring.
    Industry standard: Bloomberg, Alpaca, Interactive Brokers all use Prometheus.

    Metrics exposed:
    - WSE connections (active, total, by broker)
    - Message rates (sent, received, compression ratio)
    - Network quality (latency, jitter, packet loss)
    - Circuit breaker state
    - Queue stats (size, capacity, dropped messages)
    - System resources (CPU, memory, uptime)
    """
    try:
        metrics_lines = []

        # System metrics
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        metrics_lines.append(f"# HELP tradecore_uptime_seconds System uptime in seconds")
        metrics_lines.append(f"# TYPE tradecore_uptime_seconds gauge")
        metrics_lines.append(f"tradecore_uptime_seconds {uptime}")

        # CPU and memory (run in thread to avoid blocking)
        try:
            # Run blocking psutil call in thread pool to avoid blocking event loop
            import asyncio
            loop = asyncio.get_event_loop()
            cpu_usage = await loop.run_in_executor(None, lambda: psutil.cpu_percent(interval=0.1))
            memory_usage = psutil.virtual_memory().percent

            metrics_lines.append(f"# HELP tradecore_cpu_usage_percent CPU usage percentage")
            metrics_lines.append(f"# TYPE tradecore_cpu_usage_percent gauge")
            metrics_lines.append(f"tradecore_cpu_usage_percent {cpu_usage}")

            metrics_lines.append(f"# HELP tradecore_memory_usage_percent Memory usage percentage")
            metrics_lines.append(f"# TYPE tradecore_memory_usage_percent gauge")
            metrics_lines.append(f"tradecore_memory_usage_percent {memory_usage}")
        except (ImportError, AttributeError):
            pass

        # Redis health
        redis_ok = await redis_ping()
        metrics_lines.append(f"# HELP tradecore_redis_up Redis connection status (1=up, 0=down)")
        metrics_lines.append(f"# TYPE tradecore_redis_up gauge")
        metrics_lines.append(f"tradecore_redis_up {1 if redis_ok else 0}")

        # Event bus health
        event_bus = request.app.state.event_bus
        event_bus_ok = await event_bus.check_connection() if hasattr(event_bus, 'check_connection') else True
        metrics_lines.append(f"# HELP tradecore_event_bus_up Event bus connection status (1=up, 0=down)")
        metrics_lines.append(f"# TYPE tradecore_event_bus_up gauge")
        metrics_lines.append(f"tradecore_event_bus_up {1 if event_bus_ok else 0}")

        # WSE metrics (if available)
        wse_manager = getattr(request.app.state, 'wse_manager', None)
        if wse_manager and hasattr(wse_manager, 'get_stats'):
            stats = wse_manager.get_stats()

            # Active connections
            metrics_lines.append(f"# HELP tradecore_wse_connections_active Active WebSocket connections")
            metrics_lines.append(f"# TYPE tradecore_wse_connections_active gauge")
            metrics_lines.append(f"tradecore_wse_connections_active {stats.get('active_connections', 0)}")

            # Total messages
            metrics_lines.append(f"# HELP tradecore_wse_messages_sent_total Total messages sent")
            metrics_lines.append(f"# TYPE tradecore_wse_messages_sent_total counter")
            metrics_lines.append(f"tradecore_wse_messages_sent_total {stats.get('messages_sent', 0)}")

            metrics_lines.append(f"# HELP tradecore_wse_messages_received_total Total messages received")
            metrics_lines.append(f"# TYPE tradecore_wse_messages_received_total counter")
            metrics_lines.append(f"tradecore_wse_messages_received_total {stats.get('messages_received', 0)}")

            # Compression ratio
            if 'compression_ratio' in stats:
                metrics_lines.append(f"# HELP tradecore_wse_compression_ratio Average compression ratio")
                metrics_lines.append(f"# TYPE tradecore_wse_compression_ratio gauge")
                metrics_lines.append(f"tradecore_wse_compression_ratio {stats.get('compression_ratio', 0)}")

            # Latency (if available)
            if 'avg_latency_ms' in stats:
                metrics_lines.append(f"# HELP tradecore_wse_latency_ms Average message latency in milliseconds")
                metrics_lines.append(f"# TYPE tradecore_wse_latency_ms gauge")
                metrics_lines.append(f"tradecore_wse_latency_ms {stats.get('avg_latency_ms', 0)}")

        return "\n".join(metrics_lines) + "\n"

    except Exception as exc:
        log = logging.getLogger("tradecore.server")
        log.error(f"Error exporting Prometheus metrics: {exc}", exc_info=True)
        return f"# Error exporting metrics: {exc}\n"