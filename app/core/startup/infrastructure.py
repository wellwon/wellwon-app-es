# app/core/startup/infrastructure.py
# =============================================================================
# File: app/core/startup/infrastructure.py
# Description: Core infrastructure initialization (DB, Redis, ScyllaDB, EventBus, Cache)
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI

from app.infra.persistence.pg_client import (
    init_db_pool, run_schema
)
from app.infra.persistence.redis_client import (
    init_global_client as init_redis,
    get_global_client as get_redis_instance
)
from app.infra.event_bus.event_bus import init_event_bus, EventBus
from app.infra.event_bus.redpanda_adapter import RedpandaTransportAdapter
from app.wse.core.pubsub_bus import PubSubBus

logger = logging.getLogger("wellwon.startup.infrastructure")

# ScyllaDB imports with error handling
try:
    from app.infra.persistence.scylladb import (
        init_global_scylla_client,
        get_scylla_client,
        close_global_scylla_client,
    )
    from app.config.scylla_config import ScyllaConfig, load_scylla_config_from_env

    SCYLLA_AVAILABLE = True
except ImportError as scylla_import_error:
    logger.warning(f"ScyllaDB client not available: {scylla_import_error}")
    SCYLLA_AVAILABLE = False

    async def init_global_scylla_client(config=None):
        return None

    def get_scylla_client():
        return None

    async def close_global_scylla_client():
        pass

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


async def initialize_databases(app: FastAPI) -> None:
    """
    Initialize PostgreSQL and ScyllaDB databases
    """
    # Main PostgreSQL Database
    await init_db_pool()
    logger.info("PostgreSQL pool initialized.")

    # ScyllaDB (for high-volume message storage)
    if SCYLLA_AVAILABLE and os.getenv("SCYLLA_ENABLED", "false").lower() == "true":
        try:
            scylla_config = ScyllaConfig(
                contact_points=os.getenv("SCYLLA_CONTACT_POINTS", "localhost"),
                port=int(os.getenv("SCYLLA_PORT", "9042")),
                keyspace=os.getenv("SCYLLA_KEYSPACE", "wellwon_scylla"),
                username=os.getenv("SCYLLA_USERNAME"),
                password=os.getenv("SCYLLA_PASSWORD"),
            )
            scylla_client = await init_global_scylla_client(scylla_config)
            app.state.scylla_client = scylla_client
            logger.info(f"ScyllaDB client initialized (keyspace: {scylla_config.keyspace})")
        except Exception as scylla_error:
            logger.error(f"Failed to initialize ScyllaDB: {scylla_error}")
            logger.warning("Continuing without ScyllaDB - message storage will use PostgreSQL only")
            app.state.scylla_client = None
    else:
        if not SCYLLA_AVAILABLE:
            logger.info("ScyllaDB client not available (cassandra-driver not installed)")
        else:
            logger.info("ScyllaDB disabled (SCYLLA_ENABLED != true)")
        app.state.scylla_client = None


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
            bootstrap_servers=os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:29092"),
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
        critical_channels = os.getenv("CRITICAL_CHANNELS", "user_accounts,payments,sagas")
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


async def run_database_schemas() -> None:
    """Run database schemas for main database"""
    # Main database schema
    schema_file_path = "database/wellwon.sql"
    try:
        await run_schema(schema_file_path)
        logger.info(f"Main database schema checked/applied.")
    except FileNotFoundError:
        logger.warning(f"Main schema file not found, skipping schema run.")
    except Exception as schema_error:
        logger.error(f"Error running main schema: {schema_error}")
