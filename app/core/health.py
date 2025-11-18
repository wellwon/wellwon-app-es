# app/core/health.py
# =============================================================================
# File: app/core/health.py
# Description: Health check endpoints for the application
# UPDATED: Now uses new sync projection decorator system
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
        """Enhanced health check with unified adapter stack status"""
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
        "architecture": "UNIFIED ADAPTER STACK + SAGAS + EVENT STORE + STREAMING",
        "transport": "RedPanda",
        "adapter_infrastructure": {
            "adapter_factory": "enabled" if getattr(app.state, 'adapter_factory', None) else "disabled",
            "adapter_pool": "enabled" if getattr(app.state, 'adapter_pool', None) else "disabled",
            "adapter_manager": "enabled" if getattr(app.state, 'adapter_manager', None) else "disabled",
        },
        "event_store": "enabled" if getattr(app.state, 'event_store', None) else "disabled",
        "cqrs": {
            "command_bus": "enabled" if getattr(app.state, 'command_bus', None) else "disabled",
            "query_bus": "enabled" if getattr(app.state, 'query_bus', None) else "disabled",
            "handlers_registered": get_handler_count(app)
        },
        "services": {
            "authentication": bool(getattr(app.state, 'broker_auth_service', None)),
            "operation": bool(getattr(app.state, 'broker_operation_service', None)),
            "monitoring": bool(getattr(app.state, 'adapter_monitoring_service', None)),
            "streaming": bool(getattr(app.state, 'broker_streaming_service', None)),
        },
        "saga_service": {
            "enabled": bool(getattr(app.state, 'saga_service', None)),
            "status": "unknown"
        },
        "virtual_broker": {
            "enabled": bool(getattr(app.state, 'virtual_broker_service', None)),
            "status": "unknown",
            "market_data": "unknown"
        },
        "cache_manager": {
            "enabled": bool(getattr(app.state, 'cache_manager', None)),
            "status": "unknown"
        },
        "data_integrity": {
            "mode": "removed",
            "enabled": False,
            "status": "removed from codebase"
        },
        "projection_rebuilder": {
            "enabled": bool(getattr(app.state, 'projection_rebuilder', None)),
            "status": "available" if getattr(app.state, 'projection_rebuilder', None) else "not available"
        }
    }

    # Add detailed status checks
    await add_adapter_pool_stats(app, health_data)
    await add_distributed_features_status(app, health_data)
    await add_saga_service_status(app, health_data)
    await add_virtual_broker_status(app, health_data)
    await add_cache_manager_status(app, health_data)
    await add_data_integrity_status(app, health_data)
    await add_broker_streaming_status(app, health_data)
    await add_exactly_once_status(app, health_data)

    return health_data


async def add_adapter_pool_stats(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add adapter pool statistics to health data"""
    if getattr(app.state, 'adapter_manager', None):
        try:
            pool_stats = await app.state.adapter_manager.get_statistics()
            health_data["adapter_pool_stats"] = pool_stats
        except Exception as e:
            health_data["adapter_pool_stats"] = {"error": str(e)}


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
                    "decorator_system": True  # Flag to show we're using the new system
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


async def add_virtual_broker_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add virtual broker status to health data"""
    if getattr(app.state, 'virtual_broker_service', None):
        try:
            virtual_status = await app.state.virtual_broker_service.health_check()
            health_data["virtual_broker"] = {
                "enabled": True,
                "status": virtual_status.get("status", "unknown"),
                "connected_users": virtual_status.get("connected_users", 0),
                "components": virtual_status.get("components", {}),
                "market_data": "real" if getattr(app.state, 'virtual_market_data_service', None) else "simulated"
            }
        except Exception as e:
            health_data["virtual_broker"]["error"] = str(e)


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


async def add_data_integrity_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add data integrity monitor status to health data - REMOVED"""
    # DataIntegrityMonitor has been removed from the codebase
    health_data["data_integrity"] = {
        "enabled": False,
        "status": "removed from codebase"
    }


async def add_broker_streaming_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add broker streaming service status to health data"""
    if getattr(app.state, 'broker_streaming_service', None):
        try:
            streaming_status = {
                "enabled": app.state.broker_streaming_service.is_enabled(),
                "active_subscriptions": len(app.state.broker_streaming_service.active_subscriptions),
                "connected_users": len(app.state.broker_streaming_service.active_subscriptions)
            }
            health_data["broker_streaming"] = streaming_status
        except Exception as e:
            health_data["broker_streaming"] = {"error": str(e)}


async def add_exactly_once_status(app: FastAPI, health_data: Dict[str, Any]) -> None:
    """Add Exactly-Once delivery status to health data"""
    try:
        from app.infra.metrics.exactly_once_metrics import (
            broker_api_idempotent_hits_total,
            kafka_txn_commits_total,
            kafka_txn_aborts_total,
            outbox_txn_commits_total,
            outbox_txn_aborts_total,
            outbox_orphaned_events_total,
            kafka_txn_active
        )

        exactly_once_data = {
            "enabled": True,
            "implementation_date": "2025-11-13",
            "layers": {
                "kafka_transactions": {
                    "enabled": getattr(app.state, 'event_bus', None) and
                              hasattr(app.state.event_bus, '_enable_transactions') and
                              app.state.event_bus._enable_transactions,
                    "consumer_isolation": "read_committed",
                    "transactional_producers": len(getattr(getattr(app.state, 'event_bus', {}), '_transactional_producers', {}))
                },
                "broker_api_idempotency": {
                    "enabled": True,
                    "alpaca_support": "client_order_id",
                    "tradestation_support": "ClientOrderID"
                },
                "idempotent_handlers": {
                    "enabled": True,
                    "pattern": "UPSERT (ON CONFLICT DO UPDATE/NOTHING)"
                }
            },
            "reconciliation": {
                "enabled": hasattr(app.state, 'reconciliation_task'),
                "interval_hours": 6,
                "lookback_hours": 24,
                "running": hasattr(app.state, 'reconciliation_task') and
                          app.state.reconciliation_task and
                          not app.state.reconciliation_task.done()
            },
            "metrics": {
                "kafka_txn_active": kafka_txn_active._value._value if hasattr(kafka_txn_active, '_value') else 0,
            },
            "configuration": {
                "transactional_publishing": os.getenv("OUTBOX_ENABLE_TRANSACTIONAL_PUBLISHING", "false").lower() == "true",
                "transaction_timeout_ms": 60000,
                "transactional_id_prefix": "wellwon-txn"
            }
        }

        health_data["exactly_once_delivery"] = exactly_once_data

    except Exception as e:
        health_data["exactly_once_delivery"] = {
            "enabled": False,
            "error": str(e)
        }


def get_root_info(app: FastAPI) -> Dict[str, Any]:
    """Get root endpoint information"""
    return {
        "name": "WellWon API",
        "version": __version__,
        "status": "running",
        "architecture": "UNIFIED ADAPTER STACK + SAGAS + EVENT STORE + STREAMING",
        "docs": "/docs",
        "health": "/health",
        "transport": "RedPanda",
        "adapter_infrastructure": {
            "factory": "enabled" if getattr(app.state, 'adapter_factory', None) else "disabled",
            "pool": "enabled" if getattr(app.state, 'adapter_pool', None) else "disabled",
            "manager": "enabled" if getattr(app.state, 'adapter_manager', None) else "disabled",
        },
        "event_store": "enabled" if getattr(app.state, 'event_store', None) else "disabled",
        "cqrs": "enabled",
        "services": {
            "authentication": "enabled" if getattr(app.state, 'broker_auth_service', None) else "disabled",
            "operation": "enabled" if getattr(app.state, 'broker_operation_service', None) else "disabled",
            "monitoring": "enabled" if getattr(app.state, 'adapter_monitoring_service', None) else "disabled",
            "streaming": "enabled" if getattr(app.state, 'broker_streaming_service', None) else "disabled",
        },
        "saga_service": "enabled" if getattr(app.state, 'saga_service', None) else "disabled",
        "virtual_broker": "enabled" if getattr(app.state, 'virtual_broker_service', None) else "disabled",
        "cache_manager": "enabled" if getattr(app.state, 'cache_manager', None) else "disabled",
        "data_integrity": "worker_mode" if os.getenv("ENABLE_DATA_INTEGRITY_MONITOR",
                                                     "true").lower() == "true" else "disabled",
        "projection_rebuilder": "enabled" if getattr(app.state, 'projection_rebuilder', None) else "disabled",
        "features": {
            "unified_adapter_interface": True,
            "event_sourcing": bool(getattr(app.state, 'event_store', None)),
            "cqrs": True,
            "saga_orchestration": bool(getattr(app.state, 'saga_service', None)),
            "distributed_locking": bool(getattr(app.state, 'lock_manager', None)),
            "event_sequencing": bool(getattr(app.state, 'sequence_tracker', None)),
            "transactional_outbox": bool(getattr(app.state, 'outbox_service', None)),
            "exactly_once_delivery": True,  # TRUE Exactly-Once (2025-11-13)
            "kafka_transactions": os.getenv("KAFKA_ENABLE_TRANSACTIONS", "true").lower() == "true",
            "broker_api_idempotency": True,
            "reconciliation_service": True,
            "virtual_trading": bool(getattr(app.state, 'virtual_broker_service', None)),
            "real_market_data": bool(getattr(app.state, 'virtual_market_data_service', None)),
            "synchronous_projections": os.getenv("ENABLE_SYNC_PROJECTIONS", "true").lower() == "true",
            "synchronous_projections_decorator_system": True,  # NEW: Flag showing we use decorator system
            "centralized_caching": bool(
                getattr(app.state, 'cache_manager', None) and app.state.cache_manager.is_running),
            "automatic_account_recovery": bool(getattr(app.state, 'data_integrity_monitor', None)),
            "projection_rebuilding": bool(getattr(app.state, 'projection_rebuilder', None)),
            "real_time_streaming": bool(getattr(app.state, 'broker_streaming_service', None))
        }
    }