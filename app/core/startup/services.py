# app/core/startup/services.py
# =============================================================================
# File: app/core/startup/services.py
# Description: Service initialization during startup
# UPDATED: Fixed VirtualBrokerService initialization for pure CQRS
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI

from app.common.enums.enums import CacheTTL

# Read repositories
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
from app.infra.read_repos.broker_connection_read_repo import BrokerConnectionReadRepo
from app.infra.read_repos.broker_account_read_repo import BrokerAccountReadRepo
from app.infra.read_repos.virtual_broker_read_repo import VirtualBrokerReadRepo
from app.infra.read_repos.order_read_repo import OrderReadRepository
from app.infra.read_repos.position_read_repo import PositionReadRepository
from app.infra.read_repos.portfolio_read_repo import PortfolioReadRepository
from app.infra.read_repos.automation_read_repo import AutomationReadRepository

# Services
from app.services.application.user_auth_service import UserAuthenticationService
from app.services.application.broker_auth_service import BrokerAuthenticationService
from app.services.application.broker_operation_service import BrokerOperationService
from app.services.infrastructure.market_data_service import MarketDataService
from app.services.infrastructure.adapter_monitoring.adapter_monitoring_service import AdapterMonitoringService
# NOTE: BrokerStreamingService merged into BrokerOperationService

# Virtual broker services
from app.virtual_broker.services.virtual_broker_service import VirtualBrokerService
from app.virtual_broker.services.virtual_market_data_service import VirtualBrokerMarketDataService
from app.infra.market_data.base_provider import MarketDataProviderType

logger = logging.getLogger("tradecore.startup.services")


async def initialize_read_repositories(app: FastAPI, vb_database_initialized: bool) -> None:
    """Initialize read repositories"""

    app.state.user_account_read_repo = UserAccountReadRepo()
    app.state.broker_connection_state = BrokerConnectionReadRepo()
    app.state.broker_connection_state_reader = app.state.broker_connection_state
    app.state.account_state = BrokerAccountReadRepo()
    app.state.account_state_reader = app.state.account_state

    # Initialize virtual broker read repository with VB database support
    app.state.virtual_broker_read_repo = VirtualBrokerReadRepo()

    # Initialize order read repository
    app.state.order_read_repo = OrderReadRepository(
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )

    # Initialize position read repository
    app.state.position_read_repo = PositionReadRepository(
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )

    # Initialize portfolio read repository (read-only domain)
    app.state.portfolio_read_repo = PortfolioReadRepository(
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )

    # Initialize automation read repository
    app.state.automation_read_repo = AutomationReadRepository()

    logger.info(
        f"Read repositories initialized (VB using {'VB database' if vb_database_initialized else 'main database'})."
    )


async def initialize_services(app: FastAPI, vb_database_initialized: bool) -> None:
    """Initialize all application services"""
    logger.info("Starting service initialization...")

    # Ensure CQRS buses are available
    if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
        raise RuntimeError("Query Bus must be initialized before services")

    if not hasattr(app.state, 'command_bus'):
        logger.warning("Command Bus not initialized - some features may be limited")

    # User authentication service
    app.state.user_auth_service = UserAuthenticationService()

    # Broker authentication service - UPDATED: Now uses Query Bus (CQRS-compliant)
    auth_service = BrokerAuthenticationService()
    await auth_service.initialize(
        adapter_manager=app.state.adapter_manager,
        query_bus=app.state.query_bus,  # ADDED: Query Bus for CQRS compliance
        broker_conn_repo=app.state.broker_connection_state  # DEPRECATED: Kept for backward compatibility
    )
    app.state.broker_auth_service = auth_service

    # Market data service initialization (REST API for on-demand queries)
    market_data_service = MarketDataService(
        adapter_manager=app.state.adapter_manager,
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )
    app.state.market_data_service_rest = market_data_service  # REST API queries

    logger.info("MarketDataService initialized (REST API for on-demand queries)")

    # Broker operation service initialization (REFACTORED: streaming moved to AdapterMonitoringService)
    broker_operation_service = BrokerOperationService(
        adapter_manager=app.state.adapter_manager,
        query_bus=app.state.query_bus,
        command_bus=app.state.command_bus if hasattr(app.state, 'command_bus') else None
    )
    app.state.broker_operation_service = broker_operation_service

    logger.info("BrokerOperationService initialized (streaming lifecycle managed by AdapterMonitoringService)")

    # Trading data handler initialization (Real-time trading events)
    from app.services.application.broker_streaming.trading_data_handler import TradingDataHandler

    trading_data_handler = TradingDataHandler(
        command_bus=app.state.command_bus,
        query_bus=app.state.query_bus,
        adapter_manager=app.state.adapter_manager
    )
    app.state.trading_data_service = trading_data_handler  # Keep old name for backward compat
    app.state.trading_data_handler = trading_data_handler
    await trading_data_handler.start()

    logger.info("TradingDataHandler initialized (CQRS + ES + DDD)")

    # Connect TradingDataHandler to StreamingLifecycleManager (if available)
    # NOTE: This must happen AFTER AdapterMonitoringService initialization
    # Will be connected in initialize_monitoring_service after adapter_monitoring_service is created

    # Initialize monitoring service
    await initialize_monitoring_service(app)

    # Initialize virtual broker services
    await initialize_virtual_broker_services(app, vb_database_initialized)

    # NOTE: BrokerStreamingService merged into BrokerOperationService
    # Streaming functionality now handled by BrokerOperationService

    # Initialize WSE Publishers (order matters!)
    try:
        await initialize_wse_domain_publisher(app)
        logger.info("WSE Domain Publisher initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_wse_domain_publisher: {e}", exc_info=True)

    # Create SnapshotService in app.state (needed by SnapshotPublisher)
    try:
        from app.wse.services.snapshot_service import create_wse_snapshot_service

        app.state.snapshot_service = create_wse_snapshot_service(
            query_bus=app.state.query_bus,
            include_integrity_fields=True
        )
        logger.info("SnapshotService created in app.state")
    except Exception as e:
        logger.error(f"Failed to create SnapshotService: {e}", exc_info=True)
        app.state.snapshot_service = None

    # CRITICAL FIX (Nov 17, 2025): Initialize WSE Snapshot Publisher
    # Sends automatic snapshots when saga completes (guaranteed delivery via Redpanda)
    try:
        await initialize_wse_snapshot_publisher(app)
        logger.info("WSE Snapshot Publisher initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_wse_snapshot_publisher: {e}", exc_info=True)

    try:
        await initialize_wse_market_data_publisher(app)
        logger.info("WSE Market Data Publisher initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_wse_market_data_publisher: {e}", exc_info=True)

    # Initialize Platform Market Data Handler (depends on WSE Market Data Publisher)
    try:
        await initialize_market_data_service(app)
        logger.info("MarketDataHandler initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_market_data_service: {e}", exc_info=True)

    logger.info("All services initialized successfully")


async def initialize_monitoring_service(app: FastAPI) -> None:
    """Initialize broker monitoring service - REFACTORED to use CQRS only"""

    monitoring_config = {
        "cache_ttl_seconds": int(os.getenv("BROKER_HEALTH_CACHE_TTL", str(CacheTTL.BROKER_HEALTH_CACHE))),
        "enable_integrity_monitoring": os.getenv("ENABLE_INTEGRITY_MONITORING", "true").lower() == "true",
        "enable_wse_updates": os.getenv("ENABLE_WSE_UPDATES", "true").lower() == "true",
        "enable_pool_monitoring": os.getenv("ENABLE_POOL_MONITORING", "true").lower() == "true",
        "enable_distributed_caching": os.getenv("ENABLE_DISTRIBUTED_CACHING", "true").lower() == "true",
        "deep_check_interval_seconds": int(os.getenv("BROKER_DEEP_CHECK_INTERVAL", "300")),
        "integrity_check_interval_seconds": int(os.getenv("BROKER_INTEGRITY_CHECK_INTERVAL", "300")),
        "max_consecutive_failures": int(os.getenv("BROKER_MAX_CONSECUTIVE_FAILURES", "3"))
    }

    # REFACTORED: No more direct repository access - only CQRS
    # EventBus, CommandBus, QueryBus are now REQUIRED for proper CQRS compliance
    adapter_monitoring_service = AdapterMonitoringService(
        adapter_manager=app.state.adapter_manager,
        event_bus=app.state.event_bus,
        command_bus=app.state.command_bus,
        query_bus=app.state.query_bus,
        pubsub_bus=app.state.pubsub_bus,
        cache_ttl_seconds=monitoring_config["cache_ttl_seconds"],
        deep_check_interval_seconds=monitoring_config["deep_check_interval_seconds"],
        integrity_check_interval_seconds=monitoring_config["integrity_check_interval_seconds"],
        max_consecutive_failures=monitoring_config["max_consecutive_failures"],
        enable_wse_updates=monitoring_config["enable_wse_updates"],
        enable_pool_monitoring=monitoring_config["enable_pool_monitoring"],
        enable_distributed_caching=monitoring_config["enable_distributed_caching"],
        enable_integrity_monitoring=monitoring_config["enable_integrity_monitoring"]
    )

    app.state.adapter_monitoring_service = adapter_monitoring_service
    app.state.monitoring_config = monitoring_config

    # Update adapter pool's monitoring service reference
    if hasattr(app.state, 'adapter_pool') and app.state.adapter_pool:
        app.state.adapter_pool._monitoring_service = adapter_monitoring_service

    # NOTE: setup_event_listeners() is now called AFTER MarketDataService initialization
    # to prevent race condition where events trigger before service injection

    # Connect TradingDataHandler to StreamingLifecycleManager (if available)
    trading_data_handler = getattr(app.state, 'trading_data_handler', None)
    if trading_data_handler and hasattr(adapter_monitoring_service, 'streaming_lifecycle_manager'):
        streaming_manager = adapter_monitoring_service.streaming_lifecycle_manager
        if streaming_manager:
            streaming_manager.set_trading_data_handler(trading_data_handler)
            logger.info("TradingDataHandler connected to StreamingLifecycleManager")

    logger.info("AdapterMonitoringService initialized with CQRS pattern (event listeners deferred)")


async def initialize_virtual_broker_services(app: FastAPI, vb_database_initialized: bool) -> None:
    """Initialize virtual broker services with CQRS support"""

    enable_virtual_broker = os.getenv("ENABLE_VIRTUAL_BROKER", "true").lower() == "true"

    if not enable_virtual_broker:
        logger.info("Virtual broker disabled by configuration")
        return

    try:
        # Get virtual broker configuration
        virtual_broker_config = {
            "virtual_broker": {
                "enabled": True,
                "default_initial_balance": os.getenv("VIRTUAL_BROKER_INITIAL_BALANCE", "100000.00"),
                "enable_real_market_data": os.getenv("VIRTUAL_BROKER_REAL_DATA", "false").lower() == "true",
                "yahoo_data": os.getenv("VIRTUAL_BROKER_YAHOO_DATA", "false").lower() == "true",
                "use_vb_database": vb_database_initialized
            }
        }

        # FIXED: Create Virtual Broker Service with only required parameters
        virtual_broker_service = VirtualBrokerService(
            config=virtual_broker_config,
            command_bus=app.state.command_bus,
            query_bus=app.state.query_bus
        )
        await virtual_broker_service.initialize()
        app.state.virtual_broker_service = virtual_broker_service

        logger.info(
            f"Virtual Broker Service initialized as pure CQRS facade "
            f"(using {'VB database' if vb_database_initialized else 'main database'})."
        )

        # Optionally initialize Virtual Market Data Service
        if virtual_broker_config["virtual_broker"]["enable_real_market_data"]:
            await initialize_virtual_market_data_service(app)
        else:
            app.state.virtual_market_data_service = None
            logger.info("Virtual Broker configured with simulated market data.")

    except Exception as virtual_broker_error:
        logger.error(f"Failed to initialize Virtual Broker Service: {virtual_broker_error}", exc_info=True)
        logger.warning("Continuing without virtual broker functionality.")
        app.state.virtual_broker_service = None
        app.state.virtual_market_data_service = None


async def initialize_virtual_market_data_service(app: FastAPI) -> None:
    """Initialize virtual market data service"""

    try:
        market_data_config = {
            "rate_limit": int(os.getenv("MARKET_DATA_RATE_LIMIT", "2000")),
            "cache_ttl": int(os.getenv("MARKET_DATA_CACHE_TTL", "60")),
        }

        virtual_market_data_service = VirtualBrokerMarketDataService(
            event_bus=app.state.event_bus,
            default_provider=MarketDataProviderType.YAHOO,
            provider_config=market_data_config
        )
        await virtual_market_data_service.initialize()
        app.state.virtual_market_data_service = virtual_market_data_service

        logger.info("Virtual Market Data Service initialized with real data support.")

    except Exception as market_data_error:
        logger.warning(f"Failed to initialize Virtual Market Data Service: {market_data_error}")
        logger.info("Virtual Broker will use simulated market data.")
        app.state.virtual_market_data_service = None


# NOTE: initialize_streaming_service() REMOVED
# BrokerStreamingService functionality merged into BrokerOperationService
# Streaming is now configured via BrokerOperationService initialization parameters


async def initialize_wse_domain_publisher(app: FastAPI) -> None:
    """Initialize WSE Domain Publisher for real-time WebSocket event forwarding"""
    logger.info("→ Initializing WSE Domain Publisher...")

    enable_wse_domain = os.getenv("ENABLE_WSE_NOTIFIER", "true").lower() == "true"

    if not enable_wse_domain:
        logger.info("WSE Domain Publisher disabled by configuration")
        app.state.wse_domain_publisher = None
        return

    try:
        from app.wse.publishers.domain_publisher import WSEDomainPublisher

        wse_domain_config = {
            "enable_broker_connection_events": os.getenv("WSE_ENABLE_BROKER_CONNECTION_EVENTS", "true").lower() == "true",
            "enable_account_events": os.getenv("WSE_ENABLE_ACCOUNT_EVENTS", "true").lower() == "true",
            "enable_order_events": os.getenv("WSE_ENABLE_ORDER_EVENTS", "true").lower() == "true",
            "enable_user_events": os.getenv("WSE_ENABLE_USER_EVENTS", "true").lower() == "true",
            "enable_automation_events": os.getenv("WSE_ENABLE_AUTOMATION_EVENTS", "true").lower() == "true",
        }

        wse_domain_publisher = WSEDomainPublisher(
            event_bus=app.state.event_bus,
            pubsub_bus=app.state.pubsub_bus,
            enable_broker_connection_events=wse_domain_config["enable_broker_connection_events"],
            enable_account_events=wse_domain_config["enable_account_events"],
            enable_order_events=wse_domain_config["enable_order_events"],
            enable_user_events=wse_domain_config["enable_user_events"],
            enable_automation_events=wse_domain_config["enable_automation_events"]
        )

        await wse_domain_publisher.start()
        app.state.wse_domain_publisher = wse_domain_publisher

        logger.info(
            f"WSE Domain Publisher started - "
            f"BrokerConnections: {wse_domain_config['enable_broker_connection_events']}, "
            f"Accounts: {wse_domain_config['enable_account_events']}, "
            f"Orders: {wse_domain_config['enable_order_events']}, "
            f"Users: {wse_domain_config['enable_user_events']}, "
            f"Automation: {wse_domain_config['enable_automation_events']}"
        )

    except ImportError as import_error:
        logger.warning(f"WSE Domain Publisher not available: {import_error}")
        app.state.wse_domain_publisher = None
    except Exception as wse_error:
        logger.error(f"Failed to initialize WSE Domain Publisher: {wse_error}", exc_info=True)
        logger.warning("Continuing without WSE Domain Publisher - real-time domain events will not reach WebSocket clients")
        app.state.wse_domain_publisher = None


async def initialize_wse_snapshot_publisher(app: FastAPI) -> None:
    """Initialize WSE Snapshot Publisher for automatic snapshot delivery on saga completion"""
    logger.info("→ Initializing WSE Snapshot Publisher...")

    enable_wse_snapshots = os.getenv("ENABLE_WSE_SNAPSHOT_PUBLISHER", "true").lower() == "true"

    if not enable_wse_snapshots:
        logger.info("WSE Snapshot Publisher disabled by configuration")
        app.state.wse_snapshot_publisher = None
        return

    try:
        from app.wse.publishers.snapshot_publisher import WSESnapshotPublisher

        # Get SnapshotService from app.state
        snapshot_service = app.state.snapshot_service
        if not snapshot_service:
            raise RuntimeError("SnapshotService not available in app.state")

        wse_snapshot_publisher = WSESnapshotPublisher(
            event_bus=app.state.event_bus,
            pubsub_bus=app.state.pubsub_bus,
            snapshot_service=snapshot_service,
            enable_saga_snapshots=True
        )

        await wse_snapshot_publisher.start()
        app.state.wse_snapshot_publisher = wse_snapshot_publisher

        logger.info("WSE Snapshot Publisher started - automatic snapshots on saga completion enabled")

    except ImportError as import_error:
        logger.warning(f"WSE Snapshot Publisher not available: {import_error}")
        app.state.wse_snapshot_publisher = None
    except Exception as snapshot_error:
        logger.error(f"Failed to initialize WSE Snapshot Publisher: {snapshot_error}", exc_info=True)
        logger.warning("Continuing without WSE Snapshot Publisher - saga completion snapshots will not be sent automatically")
        app.state.wse_snapshot_publisher = None


async def initialize_wse_market_data_publisher(app: FastAPI) -> None:
    """Initialize WSE Market Data Publisher for real-time market data to WebSocket clients"""
    logger.info("→ Initializing WSE Market Data Publisher...")

    enable_wse_market_data = os.getenv("ENABLE_WSE_MARKET_DATA", "true").lower() == "true"

    if not enable_wse_market_data:
        logger.info("WSE Market Data Publisher disabled by configuration")
        app.state.wse_market_data_publisher = None
        return

    try:
        from app.wse.publishers.market_data_publisher import WSEMarketDataPublisher

        wse_market_data_publisher = WSEMarketDataPublisher(
            pubsub_bus=app.state.pubsub_bus
        )

        # No start() method needed - publisher is ready immediately after construction
        app.state.wse_market_data_publisher = wse_market_data_publisher

        logger.info("WSE Market Data Publisher initialized - real-time quotes will reach frontend")

    except ImportError as import_error:
        logger.warning(f"WSE Market Data Publisher not available: {import_error}")
        app.state.wse_market_data_publisher = None
    except Exception as wse_error:
        logger.error(f"Failed to initialize WSE Market Data Publisher: {wse_error}", exc_info=True)
        logger.warning("Continuing without WSE Market Data Publisher - real-time market data will not reach frontend")
        app.state.wse_market_data_publisher = None


async def initialize_market_data_service(app: FastAPI) -> None:
    """Initialize Platform Market Data Handler - coordinates all market data"""
    logger.info("Initializing Platform Market Data Handler...")

    try:
        from app.services.application.broker_streaming.market_data_handler import MarketDataHandler

        # Get dependencies
        wse_market_data_publisher = getattr(app.state, 'wse_market_data_publisher', None)
        command_bus = getattr(app.state, 'command_bus', None)
        adapter_manager = getattr(app.state, 'adapter_manager', None)
        cache_manager = getattr(app.state, 'cache_manager', None)

        if not wse_market_data_publisher:
            logger.warning(
                "WSE Market Data Publisher not available - MarketDataHandler will not publish to frontend"
            )

        # Create handler
        market_data_handler = MarketDataHandler(
            wse_market_data_publisher=wse_market_data_publisher,
            command_bus=command_bus,
            adapter_manager=adapter_manager,
            cache_manager=cache_manager,
        )

        await market_data_handler.initialize()
        app.state.market_data_service = market_data_handler  # Keep old name for backward compat
        app.state.market_data_handler = market_data_handler

        # Connect to StreamingLifecycleManager (if available)
        adapter_monitoring_service = getattr(app.state, 'adapter_monitoring_service', None)
        if adapter_monitoring_service and hasattr(adapter_monitoring_service, 'streaming_lifecycle_manager'):
            streaming_manager = adapter_monitoring_service.streaming_lifecycle_manager
            if streaming_manager:
                streaming_manager.set_market_data_handler(market_data_handler)
                logger.info("MarketDataHandler connected to StreamingLifecycleManager")

        logger.info("Platform Market Data Handler initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize Market Data Handler: {e}", exc_info=True)
        logger.warning("Continuing without Market Data Handler - market data will not reach frontend")
        app.state.market_data_service = None
        app.state.market_data_handler = None

    finally:
        # Setup event listeners AFTER MarketDataService injection attempt (prevents race condition)
        # Event listeners handle ORDER/ACCOUNT updates even if MarketDataService failed
        adapter_monitoring_service = getattr(app.state, 'adapter_monitoring_service', None)
        if adapter_monitoring_service:
            await adapter_monitoring_service.setup_event_listeners()
            logger.info("Streaming lifecycle event listeners activated")


async def initialize_optional_services(app: FastAPI) -> None:
    """Initialize optional services like data integrity monitor"""

    # Initialize Projection Rebuilder Service
    await initialize_projection_rebuilder(app)

    # Initialize Data Integrity Monitor
    await initialize_data_integrity_monitor(app)


async def initialize_projection_rebuilder(app: FastAPI) -> None:
    """Initialize projection rebuilder service"""

    if not (app.state.event_store and os.getenv("ENABLE_EVENT_STORE", "true").lower() == "true"):
        return

    try:
        from app.services.infrastructure.projection_rebuilder_service import create_projection_rebuilder_service

        # Configuration for the rebuilder service
        rebuilder_config = {
            "max_concurrent_rebuilds": int(os.getenv("PROJECTION_MAX_CONCURRENT_REBUILDS", "3")),
            "enable_circuit_breaker": os.getenv("PROJECTION_ENABLE_CIRCUIT_BREAKER", "true").lower() == "true",
            "enable_metrics": os.getenv("PROJECTION_ENABLE_METRICS", "true").lower() == "true",
            "circuit_breaker_threshold": int(os.getenv("PROJECTION_CIRCUIT_BREAKER_THRESHOLD", "5")),
            "circuit_breaker_timeout_seconds": int(os.getenv("PROJECTION_CIRCUIT_BREAKER_TIMEOUT", "300")),
            "checkpoint_interval": int(os.getenv("PROJECTION_CHECKPOINT_INTERVAL", "30"))
        }

        projection_rebuilder = create_projection_rebuilder_service(
            event_store=app.state.event_store,
            event_bus=app.state.event_bus,
            command_bus=app.state.command_bus,
            query_bus=app.state.query_bus,
            config=rebuilder_config
        )

        app.state.projection_rebuilder = projection_rebuilder

        # Start the service worker
        await projection_rebuilder.start()

        logger.info("ProjectionRebuilderService created and started successfully")

    except ImportError as import_error:
        logger.warning(f"ProjectionRebuilderService not available: {import_error}")
        logger.warning("Projection rebuild will not work in sagas")
    except Exception as rebuilder_error:
        logger.error(f"Failed to create ProjectionRebuilderService: {rebuilder_error}", exc_info=True)
        logger.warning("Continuing without projection rebuild functionality")


async def initialize_data_integrity_monitor(app: FastAPI) -> None:
    """Initialize data integrity monitor - REMOVED"""
    # DataIntegrityMonitor has been removed from the codebase
    app.state.data_integrity_monitor = None
    logger.info("Data Integrity Monitor removed - functionality deprecated")

# =============================================================================
# EOF
# =============================================================================