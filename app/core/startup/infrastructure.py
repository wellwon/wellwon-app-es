# app/core/startup/infrastructure.py
# =============================================================================
# File: app/core/startup/infrastructure.py
# Description: Core infrastructure initialization (DB, Redis, EventBus, Cache)
# UPDATED: Changed ENABLE_VB_DATABASE default to true
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI

from app.infra.persistence.pg_client import (
    init_db_pool, init_vb, run_schema, run_vb_schema
)
from app.infra.persistence.redis_client import (
    init_global_client as init_redis,
    get_global_client as get_redis_instance
)
from app.infra.event_bus.event_bus import init_event_bus, EventBus
from app.infra.event_bus.redpanda_adapter import RedpandaTransportAdapter
from app.wse.core.pubsub_bus import PubSubBus

logger = logging.getLogger("wellwon.startup.infrastructure")

# Cache manager imports with error handling
try:
    from app.infra.persistence.cache_manager import (
        initialize_cache_manager, shutdown_cache_manager
    )

    CACHE_MANAGER_AVAILABLE = True
except ImportError as cache_import_error:
    logger.warning(f"Cache manager not available: {cache_import_error}")
    CACHE_MANAGER_AVAILABLE = False


    # Create dummy functions
    async def initialize_cache_manager(redis_client):
        return None


    async def shutdown_cache_manager():
        pass


async def initialize_databases(app: FastAPI) -> bool:
    """
    Initialize PostgreSQL databases (main and virtual broker)
    Returns: bool indicating if VB database was initialized
    """
    # Main PostgreSQL Database
    await init_db_pool()
    logger.info("PostgreSQL pool initialized.")

    # Virtual Broker Database (optional)
    # CHANGED: Default to true for production use
    enable_vb_database = os.getenv("ENABLE_VB_DATABASE", "true").lower() == "true"
    vb_database_initialized = False

    if enable_vb_database:
        try:
            await init_vb()
            vb_database_initialized = True
            logger.info("Virtual Broker PostgreSQL pool initialized.")
        except Exception as vb_db_error:
            logger.error(f"Failed to initialize VB database: {vb_db_error}")
            logger.warning("Continuing without VB database - VB operations will use main database")
            vb_database_initialized = False

    return vb_database_initialized


async def initialize_cache(app: FastAPI) -> None:
    """Initialize Redis and Cache Manager"""
    # Initialize Redis
    await init_redis()
    logger.info("Global Redis client initialized.")

    # Initialize Cache Manager
    if CACHE_MANAGER_AVAILABLE:
        try:
            redis_client = get_redis_instance()
            cache_manager = await initialize_cache_manager(redis_client)
            app.state.cache_manager = cache_manager
            logger.info("Cache manager initialized and started with background tasks")

            # Log cache configuration
            try:
                bg_tasks = cache_manager.background_task_count
            except AttributeError:
                bg_tasks = "N/A"

            cache_config_info = {
                "enabled": cache_manager.enabled,
                "key_prefix": cache_manager.key_prefix,
                "cleanup_on_startup": cache_manager.cleanup_on_startup,
                "cleanup_interval_hours": cache_manager.cleanup_interval_hours,
                "aggressive_cleanup": cache_manager.broker_aggressive_cleanup,
                "is_running": cache_manager.is_running,
                "background_tasks": bg_tasks
            }
            logger.info(f"Cache configuration: {cache_config_info}")

        except Exception as cache_init_error:
            logger.error(f"Failed to initialize cache manager: {cache_init_error}", exc_info=True)
            logger.warning("Continuing without cache manager - caching will be disabled")
            app.state.cache_manager = None
    else:
        logger.warning("Cache manager module not available - caching will be disabled")
        app.state.cache_manager = None


async def initialize_event_infrastructure(app: FastAPI) -> None:
    """Initialize EventBus and Reactive EventBus"""
    # Initialize EventBus with RedPanda transport
    try:
        redpanda_adapter = RedpandaTransportAdapter(
            bootstrap_servers=os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092"),
            client_id=f"wellwon-api-{os.getenv('INSTANCE_ID', 'default')}",
            producer_config={
                'acks': 'all',
                'compression_type': 'snappy',
                'linger_ms': 10,
                'enable_idempotence': True,
            },
            consumer_config={
                'session_timeout_ms': 30000,
                'heartbeat_interval_ms': 3000,
                'max_poll_records': 500,
            }
        )

        initialized_event_bus: EventBus = init_event_bus(
            adapter=redpanda_adapter,
            validate_on_publish=True
        )

        # Mark critical channels for enhanced reliability
        critical_channels = os.getenv("CRITICAL_CHANNELS", "orders,payments,accounts,broker_connections,sagas")
        for channel in critical_channels.split(","):
            if channel.strip():
                initialized_event_bus.mark_channel_as_critical(channel.strip())

        app.state.event_bus = initialized_event_bus
        logger.info("Enhanced EventBus initialized with RedPanda transport.")

    except Exception as transport_error:
        logger.error(f"Failed to initialize EventBus: {transport_error}", exc_info=True)
        raise RuntimeError(f"EventBus initialization failed: {transport_error}")

    # Initialize PubSubBus (Redis Pub/Sub for WebSocket coordination)
    # Uses global Redis client and connection pool (redis-py official pattern)
    redis_client = get_redis_instance()
    pubsub_bus = PubSubBus(redis_client=redis_client)
    await pubsub_bus.initialize()
    app.state.pubsub_bus = pubsub_bus
    logger.info("PubSubBus initialized - using global Redis connection pool")


async def run_database_schemas(vb_database_initialized: bool) -> None:
    """Run database schemas for main and VB databases"""
    # Main database schema
    schema_file_path = "database/wellwon.sql"
    try:
        await run_schema(schema_file_path)
        logger.info(f"Main database schema checked/applied.")
    except FileNotFoundError:
        logger.warning(f"Main schema file not found, skipping schema run.")
    except Exception as schema_error:
        logger.error(f"Error running main schema: {schema_error}")

    # Virtual Broker schema
    if vb_database_initialized:
        vb_schema_path = os.getenv("VB_SCHEMA_PATH", "database/wellwon_vb.sql")
        if os.getenv("VB_RUN_SCHEMA", "true").lower() == "true":
            try:
                await run_vb_schema(vb_schema_path)
                logger.info("Virtual Broker schema checked/applied.")
            except FileNotFoundError:
                logger.warning(f"VB schema file not found at {vb_schema_path}, skipping.")
            except Exception as vb_schema_error:
                logger.error(f"Error running VB schema: {vb_schema_error}")
                # Continue anyway - schema might already exist