# app/core/shutdown.py
# =============================================================================
# File: app/core/shutdown.py
# Description: Graceful shutdown logic for all services
# =============================================================================

import asyncio
import logging
from typing import Any
from app.core.fastapi_types import FastAPI

from app.infra.persistence.pg_client import close_db_pool
from app.infra.persistence.redis_client import close_global_client as close_redis

logger = logging.getLogger("wellwon.shutdown")

# Import cache manager shutdown if available
try:
    from app.infra.persistence.cache_manager import shutdown_cache_manager

    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False


    async def shutdown_cache_manager():
        pass


async def shutdown_all_services(app: FastAPI) -> None:
    """Shutdown all services in the correct order"""

    # Prevent duplicate shutdowns
    if getattr(app, '_shutdown_in_progress', False):
        logger.warning("Shutdown already in progress, skipping")
        return

    app._shutdown_in_progress = True

    # Helper function for clean shutdown with timeout
    async def shutdown_service(service: Any, service_name: str, timeout: float = 10.0) -> None:
        """Safely shutdown a service if it has a shutdown method."""
        if service and hasattr(service, 'shutdown'):
            try:
                # Add timeout to prevent hanging during shutdown
                async with asyncio.timeout(timeout):
                    await service.shutdown()
                logger.info(f"{service_name} shut down")
            except TimeoutError:
                logger.error(f"{service_name} shutdown timed out after {timeout}s, continuing...")
            except Exception as shutdown_error:
                logger.error(f"Error shutting down {service_name}: {shutdown_error}")

    # Phase 1: Stop application services
    await shutdown_application_services(app)

    # Phase 2: Stop infrastructure services
    await shutdown_infrastructure_services(app)

    # Phase 3: Close database connections
    await shutdown_databases(app)

    # Phase 4: Close Redis
    await shutdown_redis()


async def shutdown_application_services(app: FastAPI) -> None:
    """Shutdown application-level services"""

    # Shutdown services in reverse order of initialization
    services_to_shutdown = [
        ("projection_rebuilder", "Projection Rebuilder"),
        ("wse_domain_publisher", "WSE Domain Publisher"),
        ("wse_snapshot_publisher", "WSE Snapshot Publisher"),
        ("saga_service", "Saga Service"),
    ]

    for attr_name, service_name in services_to_shutdown:
        service = getattr(app.state, attr_name, None)
        if service and hasattr(service, 'shutdown'):
            try:
                # Add timeout to prevent hanging
                async with asyncio.timeout(10.0):
                    await service.shutdown()
                logger.info(f"{service_name} shut down")
            except TimeoutError:
                logger.error(f"{service_name} shutdown timed out after 10s, continuing...")
            except Exception as e:
                logger.error(f"Error shutting down {service_name}: {e}")


async def shutdown_infrastructure_services(app: FastAPI) -> None:
    """Shutdown infrastructure services"""

    # Stop DLQ service
    dlq_service = getattr(app.state, 'dlq_service', None)
    if dlq_service and hasattr(dlq_service, 'stop'):
        try:
            await dlq_service.stop()
            logger.info("DLQ Service stopped")
        except Exception as dlq_error:
            logger.error(f"Error stopping DLQ service: {dlq_error}")

    # Close event store with timeout
    event_store = getattr(app.state, "event_store", None)
    if event_store and hasattr(event_store, 'close'):
        try:
            async with asyncio.timeout(10.0):
                await event_store.close()
            logger.info("Event Store shut down")
        except TimeoutError:
            logger.error("Event Store shutdown timed out after 10s")
        except Exception as es_close_error:
            logger.error(f"Error shutting down Event Store: {es_close_error}")

    # Shutdown PubSubBus with timeout
    pubsub_bus = getattr(app.state, "pubsub_bus", None)
    if pubsub_bus and hasattr(pubsub_bus, 'shutdown'):
        try:
            async with asyncio.timeout(10.0):
                await pubsub_bus.shutdown()
            logger.info("PubSubBus shut down")
        except TimeoutError:
            logger.error("PubSubBus shutdown timed out after 10s")
        except Exception as pubsub_error:
            logger.error(f"Error shutting down PubSubBus: {pubsub_error}")

    event_bus = getattr(app.state, "event_bus", None)
    if event_bus and hasattr(event_bus, 'close'):
        try:
            # EventBus uses RedpandaAdapter which can hang on consumer.stop()
            async with asyncio.timeout(10.0):
                await event_bus.close()
            logger.info("EventBus closed")
        except TimeoutError:
            logger.error("EventBus close timed out after 10s, forcing cleanup")
        except Exception as event_bus_error:
            logger.error(f"Error closing EventBus: {event_bus_error}")

    # Shutdown cache manager
    if CACHE_MANAGER_AVAILABLE and getattr(app.state, 'cache_manager', None):
        try:
            await shutdown_cache_manager()
            logger.info("Cache manager shutdown complete")
        except Exception as cache_shutdown_error:
            logger.error(f"Error shutting down cache manager: {cache_shutdown_error}")


async def shutdown_databases(app: FastAPI) -> None:
    """Close database connections"""

    # Close main database pool
    try:
        await close_db_pool()
        logger.info("Main database pool closed")
    except Exception as main_db_error:
        logger.error(f"Error closing main database pool: {main_db_error}")


async def shutdown_redis() -> None:
    """Close Redis connection"""
    try:
        await close_redis()
        logger.info("Redis connection closed")
    except Exception as redis_error:
        logger.error(f"Error closing Redis: {redis_error}")
