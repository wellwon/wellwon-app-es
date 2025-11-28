# app/core/startup/services.py
# =============================================================================
# File: app/core/startup/services.py
# Description: Service initialization during startup
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI

# Read repositories
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
from app.infra.read_repos.chat_read_repo import ChatReadRepo

# Services
from app.services.application.user_auth_service import UserAuthenticationService

logger = logging.getLogger("wellwon.startup.services")


async def initialize_read_repositories(app: FastAPI) -> None:
    """Initialize read repositories"""

    app.state.user_account_read_repo = UserAccountReadRepo()
    app.state.chat_read_repo = ChatReadRepo()

    logger.info("Read repositories initialized.")


async def initialize_services(app: FastAPI) -> None:
    """Initialize all application services"""
    logger.info("Starting service initialization...")

    # Ensure CQRS buses are available
    if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
        raise RuntimeError("Query Bus must be initialized before services")

    if not hasattr(app.state, 'command_bus'):
        logger.warning("Command Bus not initialized - some features may be limited")

    # User authentication service
    app.state.user_auth_service = UserAuthenticationService()

    # Initialize WSE Publishers
    try:
        await initialize_wse_domain_publisher(app)
        logger.info("WSE Domain Publisher initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_wse_domain_publisher: {e}", exc_info=True)

    # Initialize Telegram Event Listener
    try:
        await initialize_telegram_event_listener(app)
        logger.info("Telegram Event Listener initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_telegram_event_listener: {e}", exc_info=True)

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

    # Initialize WSE Snapshot Publisher
    try:
        await initialize_wse_snapshot_publisher(app)
        logger.info("WSE Snapshot Publisher initialized")
    except Exception as e:
        logger.error(f"FAILED initialize_wse_snapshot_publisher: {e}", exc_info=True)

    logger.info("All services initialized successfully")


async def initialize_telegram_event_listener(app: FastAPI) -> None:
    """Initialize Telegram Event Listener for bidirectional chat sync"""
    logger.info("Initializing Telegram Event Listener...")

    enable_telegram = os.getenv("ENABLE_TELEGRAM_SYNC", "true").lower() == "true"

    if not enable_telegram:
        logger.info("Telegram Event Listener disabled by configuration")
        app.state.telegram_event_listener = None
        return

    try:
        from app.infra.telegram.listener import create_telegram_event_listener

        telegram_listener = await create_telegram_event_listener(
            event_bus=app.state.event_bus,
            chat_repository=None  # Will be set when Chat domain read repo is available
        )

        app.state.telegram_event_listener = telegram_listener

        logger.info("Telegram Event Listener started - bidirectional chat sync enabled")

    except ImportError as import_error:
        logger.warning(f"Telegram Event Listener not available: {import_error}")
        app.state.telegram_event_listener = None
    except Exception as telegram_error:
        logger.error(f"Failed to initialize Telegram Event Listener: {telegram_error}", exc_info=True)
        logger.warning("Continuing without Telegram sync - WellWon messages will not be forwarded to Telegram")
        app.state.telegram_event_listener = None


async def initialize_wse_domain_publisher(app: FastAPI) -> None:
    """Initialize WSE Domain Publisher for real-time WebSocket event forwarding"""
    logger.info("Initializing WSE Domain Publisher...")

    enable_wse_domain = os.getenv("ENABLE_WSE_NOTIFIER", "true").lower() == "true"

    if not enable_wse_domain:
        logger.info("WSE Domain Publisher disabled by configuration")
        app.state.wse_domain_publisher = None
        return

    try:
        from app.wse.publishers.domain_publisher import WSEDomainPublisher

        wse_domain_config = {
            "enable_user_events": os.getenv("WSE_ENABLE_USER_EVENTS", "true").lower() == "true",
        }

        wse_domain_publisher = WSEDomainPublisher(
            event_bus=app.state.event_bus,
            pubsub_bus=app.state.pubsub_bus,
            enable_user_events=wse_domain_config["enable_user_events"]
        )

        await wse_domain_publisher.start()
        app.state.wse_domain_publisher = wse_domain_publisher

        logger.info(
            f"WSE Domain Publisher started - "
            f"Users: {wse_domain_config['enable_user_events']}"
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
    logger.info("Initializing WSE Snapshot Publisher...")

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


async def initialize_optional_services(app: FastAPI) -> None:
    """Initialize optional services like data integrity monitor"""

    # Initialize Projection Rebuilder Service
    await initialize_projection_rebuilder(app)


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

# =============================================================================
# EOF
# =============================================================================
