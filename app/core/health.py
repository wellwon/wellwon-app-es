# app/core/health.py
# =============================================================================
# File: app/core/health.py
# Description: Health check endpoints for the application
# =============================================================================

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from app.core.fastapi_types import FastAPI

from app.core import __version__

logger = logging.getLogger("wellwon.health")


def get_handler_count(app: FastAPI) -> int:
    """Get the total number of registered handlers"""
    try:
        if hasattr(app.state, 'command_bus') and app.state.command_bus:
            command_info = app.state.command_bus.get_handler_info()
            return command_info.get('total_handlers', 0)
    except Exception:
        pass
    return 0


def register_health_endpoints(app: FastAPI) -> None:
    """Register health check endpoints directly on the app"""

    @app.get("/health", tags=["System"])
    async def health_check() -> Dict[str, Any]:
        """Enhanced health check with system status"""
        return await get_health_status(app)

    @app.get("/", tags=["System"])
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information"""
        return get_root_info(app)


async def get_health_status(app: FastAPI) -> Dict[str, Any]:
    """Get comprehensive health status of the application"""

    health_data = {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "architecture": "EVENT SOURCING + CQRS + DDD",
        "transport": "RedPanda",
        "event_store": "enabled" if getattr(app.state, 'event_store', None) else "disabled",
        "cqrs": {
            "command_bus": "enabled" if getattr(app.state, 'command_bus', None) else "disabled",
            "query_bus": "enabled" if getattr(app.state, 'query_bus', None) else "disabled",
            "handlers_registered": get_handler_count(app)
        },
        "services": {
            "user_authentication": bool(getattr(app.state, 'user_auth_service', None)),
        },
        "saga_service": {
            "enabled": bool(getattr(app.state, 'saga_service', None)),
            "status": "unknown"
        },
        "cache_manager": {
            "enabled": bool(getattr(app.state, 'cache_manager', None)),
            "status": "unknown"
        },
        "projection_rebuilder": {
            "enabled": bool(getattr(app.state, 'projection_rebuilder', None)),
            "status": "available" if getattr(app.state, 'projection_rebuilder', None) else "not available"
        }
    }

    # Add detailed status checks
    await add_distributed_features_status(app, health_data)
    await add_saga_service_status(app, health_data)
    await add_cache_manager_status(app, health_data)

    return health_data


async def add_distributed_features_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add distributed features status to health data"""
    if getattr(app.state, 'event_store', None):
        health_data["distributed_features"] = {
            "locking": "enabled" if getattr(app.state, 'lock_manager', None) else "disabled",
            "sequencing": "enabled" if getattr(app.state, 'sequence_tracker', None) else "disabled",
            "outbox": "enabled" if getattr(app.state, 'outbox_service', None) else "disabled",
            "sync_projections": "enabled" if os.getenv("ENABLE_SYNC_PROJECTIONS",
                                                       "true").lower() == "true" else "disabled"
        }

        # Add sync projection details using new decorator system
        if os.getenv("ENABLE_SYNC_PROJECTIONS", "true").lower() == "true":
            try:
                from app.infra.event_store.sync_decorators import get_sync_projection_metrics, get_projector_info

                metrics = get_sync_projection_metrics()
                info = get_projector_info()

                health_data["distributed_features"]["sync_projection_events"] = metrics.get('total_sync_events', 0)
                health_data["sync_projections"] = {
                    "metrics": metrics,
                    "projector_info": info,
                    "status": "enabled",
                    "decorator_system": True
                }
            except Exception as e:
                health_data["sync_projections"] = {"error": str(e)}

        # Add outbox stats
        if getattr(app.state, 'outbox_service', None):
            try:
                outbox_stats = await app.state.outbox_service.get_outbox_stats()
                health_data["outbox_stats"] = {
                    "pending": outbox_stats.get("pending", 0),
                    "published": outbox_stats.get("published", 0),
                    "failed": outbox_stats.get("failed", 0),
                    "dead_letter": outbox_stats.get("dead_letter", 0)
                }
            except Exception as e:
                health_data["outbox_stats"] = {"error": str(e)}


async def add_saga_service_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add saga service status to health data"""
    if getattr(app.state, 'saga_service', None):
        try:
            saga_status = await app.state.saga_service.get_service_status()
            health_data["saga_service"] = {
                "enabled": True,
                "initialized": saga_status.get("initialized", False),
                "running": saga_status.get("running", False),
                "active_sagas": saga_status.get("saga_manager", {}).get("active_sagas", 0),
                "active_consumers": saga_status.get("active_consumers", 0),
                "configured_topics": saga_status.get("configured_topics", [])
            }
        except Exception as e:
            health_data["saga_service"]["error"] = str(e)


async def add_cache_manager_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add cache manager status to health data"""
    if getattr(app.state, 'cache_manager', None):
        try:
            cache_health = await app.state.cache_manager.health_check()
            health_data["cache_manager"] = {
                "enabled": True,
                "healthy": cache_health.get("healthy", False),
                "running": app.state.cache_manager.is_running,
                "metrics": cache_health.get("metrics"),
                "config": cache_health.get("config"),
                "redis": cache_health.get("redis")
            }
        except Exception as e:
            health_data["cache_manager"]["error"] = str(e)


def get_root_info(app: FastAPI) -> Dict[str, Any]:
    """Get root endpoint information"""
    return {
        "name": "WellWon API",
        "version": __version__,
        "status": "running",
        "architecture": "EVENT SOURCING + CQRS + DDD",
        "docs": "/docs",
        "health": "/health",
        "transport": "RedPanda",
        "event_store": "enabled" if getattr(app.state, 'event_store', None) else "disabled",
        "cqrs": "enabled",
        "services": {
            "user_authentication": "enabled" if getattr(app.state, 'user_auth_service', None) else "disabled",
        },
        "saga_service": "enabled" if getattr(app.state, 'saga_service', None) else "disabled",
        "cache_manager": "enabled" if getattr(app.state, 'cache_manager', None) else "disabled",
        "projection_rebuilder": "enabled" if getattr(app.state, 'projection_rebuilder', None) else "disabled",
        "features": {
            "event_sourcing": bool(getattr(app.state, 'event_store', None)),
            "cqrs": True,
            "saga_orchestration": bool(getattr(app.state, 'saga_service', None)),
            "distributed_locking": bool(getattr(app.state, 'lock_manager', None)),
            "event_sequencing": bool(getattr(app.state, 'sequence_tracker', None)),
            "transactional_outbox": bool(getattr(app.state, 'outbox_service', None)),
            "synchronous_projections": os.getenv("ENABLE_SYNC_PROJECTIONS", "true").lower() == "true",
            "centralized_caching": bool(
                getattr(app.state, 'cache_manager', None) and app.state.cache_manager.is_running),
            "projection_rebuilding": bool(getattr(app.state, 'projection_rebuilder', None)),
        }
    }
