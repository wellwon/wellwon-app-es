# app/core/startup/adapters.py
# =============================================================================
# File: app/core/startup/adapters.py
# Description: Broker adapter infrastructure initialization
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI

from app.infra.broker_adapters.adapter_factory import BrokerAdapterFactory
from app.infra.broker_adapters.adapter_pool import AdapterPool, PoolConfig
from app.infra.broker_adapters.adapter_manager import AdapterManager

logger = logging.getLogger("wellwon.startup.adapters")


async def initialize_broker_adapters(app: FastAPI) -> None:
    """Initialize broker adapter infrastructure"""

    # Initialize adapter factory
    await initialize_adapter_factory(app)

    # Initialize adapter pool
    await initialize_adapter_pool(app)

    # Initialize adapter manager
    await initialize_adapter_manager(app)


async def initialize_adapter_factory(app: FastAPI) -> None:
    """Initialize and configure broker adapter factory"""

    factory_config = {
        "enable_auto_discovery": os.getenv("ADAPTER_AUTO_DISCOVERY", "true").lower() == "true",
        "enable_health_monitoring": os.getenv("ADAPTER_HEALTH_MONITORING", "true").lower() == "true",
    }

    adapter_factory = BrokerAdapterFactory(config=factory_config)
    app.state.adapter_factory = adapter_factory

    # Add broker alias
    adapter_factory.add_broker_alias("tcvb", "virtual")

    # Auto-discover and register adapters
    try:
        registration_results = await adapter_factory.auto_discover_and_register_all_adapters()
        registered_count = sum(1 for success in registration_results.values() if success)
        logger.info(f"Broker adapter factory initialized with {registered_count} adapters")
    except Exception as adapter_error:
        logger.error(f"Error registering broker adapters: {adapter_error}")


async def configure_adapter_factory_services(app: FastAPI) -> None:
    """Configure adapter factory with services after they are initialized"""

    if not app.state.adapter_factory:
        return

    # Configure service provider for dependency injection
    if app.state.virtual_broker_service:
        def service_provider(service_name: str):
            """Map service names to their instances for dependency injection."""
            service_map = {
                "virtual_broker_service": app.state.virtual_broker_service,
                "virtual_market_data_service": app.state.virtual_market_data_service,
            }
            return service_map.get(service_name)

        app.state.adapter_factory.set_service_provider(service_provider)
        logger.info("Configured adapter factory with virtual broker services")
    else:
        logger.info("Virtual broker service not available - virtual adapter functionality will be limited")


async def initialize_adapter_pool(app: FastAPI) -> None:
    """Initialize adapter pool for connection management"""

    pool_config = PoolConfig(
        max_adapters=int(os.getenv("ADAPTER_POOL_MAX_ADAPTERS", "100")),
        instance_id=f"instance-{os.getenv('INSTANCE_ID', 'default')}"
    )

    adapter_pool = AdapterPool(
        adapter_factory=app.state.adapter_factory,
        broker_connection_read_repo=app.state.broker_connection_state,
        monitoring_service=None,  # Will be set later by monitoring service
        config=pool_config,
        global_config={}
    )

    app.state.adapter_pool = adapter_pool
    logger.info("Adapter pool initialized")


async def initialize_adapter_manager(app: FastAPI) -> None:
    """Initialize adapter manager with unified interface"""

    adapter_manager = AdapterManager(
        adapter_pool=app.state.adapter_pool,
        adapter_factory=app.state.adapter_factory,  # Provide factory as fallback
        broker_conn_repo=app.state.broker_connection_state,  # Critical dependency
        enable_cache=True,
        cache_ttl_seconds=3600,
        max_cache_size=100
    )

    app.state.adapter_manager = adapter_manager
    logger.info("AdapterManager initialized with unified interface")