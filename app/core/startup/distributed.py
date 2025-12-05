# app/core/startup/distributed.py
# =============================================================================
# File: app/core/startup/distributed.py
# Description: Initialize distributed features (Event Store, locks, outbox, DLQ)
# =============================================================================

import asyncio
import logging
from app.core.fastapi_types import FastAPI

from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore
from app.config.event_store_config import EventStoreConfig
from app.infra.reliability.distributed_lock import DistributedLockManager
from app.infra.event_store.sequence_tracker import EventSequenceTracker
from app.infra.event_store.outbox_service import create_transport_outbox, OutboxPublisher
from app.infra.event_store.dlq_service import create_dlq_service
from app.infra.event_store.stream_archival_service import create_and_start_archival_service

# Import decorator-based sync projection system
from app.infra.cqrs.projector_decorators import auto_register_sync_projections

logger = logging.getLogger("wellwon.startup.distributed")


async def initialize_distributed_features(app: FastAPI) -> None:
    """Initialize Event Store and distributed features"""

    try:
        # Initialize distributed lock manager
        await initialize_lock_manager(app)

        # Initialize sequence tracker
        await initialize_sequence_tracker(app)

        # Initialize DLQ service (before outbox!)
        await initialize_dlq_service(app)

        # Initialize outbox service
        await initialize_outbox_service(app)

        # Initialize event store
        await initialize_event_store(app)

        # NOTE: Sync projections are registered later in the startup sequence
        # after all projector instances are created

    except Exception as es_error:
        logger.error(f"Failed to initialize distributed features: {es_error}", exc_info=True)
        raise  # Critical error - don't continue


async def initialize_lock_manager(app: FastAPI) -> None:
    """Initialize distributed lock manager"""

    app.state.lock_manager = DistributedLockManager(
        namespace="wellwon_lock",
        default_ttl_ms=30000,  # 30 seconds
        max_wait_ms=5000  # 5 seconds
    )
    logger.info("Distributed Lock Manager initialized.")


async def initialize_sequence_tracker(app: FastAPI) -> None:
    """Initialize event sequence tracker"""

    app.state.sequence_tracker = EventSequenceTracker(
        namespace="wellwon_sequence",
        ttl_seconds=86400,  # 24 hours
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )
    logger.info("Event Sequence Tracker initialized.")


async def initialize_dlq_service(app: FastAPI) -> None:
    """Initialize Dead Letter Queue service"""

    try:
        # Always use production profile
        dlq_profile = "production"

        # Create DLQ service
        dlq_service = create_dlq_service(
            profile=dlq_profile,
            event_bus=app.state.event_bus if hasattr(app.state, 'event_bus') else None
        )

        # Store in app state
        app.state.dlq_service = dlq_service

        # Start the service (always enabled in production profile)
        await dlq_service.start()
        logger.info(f"DLQ Service started with profile: {dlq_profile}")

    except Exception as dlq_error:
        logger.error(f"Failed to initialize DLQ Service: {dlq_error}", exc_info=True)
        raise  # DLQ is critical


async def initialize_outbox_service(app: FastAPI) -> None:
    """Initialize transactional outbox pattern"""

    # Define custom event-to-topic mappings for WellWon domains
    custom_mappings = {
        # User account events
        "UserAccountCreated": "transport.user-account-events",
        "UserDeleted": "transport.user-account-events",
        "UserProfileUpdated": "transport.user-account-events",
        "UserAccountDeleted": "transport.user-account-events",
        "UserHardDeleted": "transport.user-account-events",
        "UserAdminStatusUpdated": "transport.user-account-events",
        "UserRoleChangedExternally": "transport.user-account-events",
        "UserStatusChangedExternally": "transport.user-account-events",
        # Company domain events
        "CompanyCreated": "transport.company-events",
        "CompanyUpdated": "transport.company-events",
        "CompanyArchived": "transport.company-events",
        "CompanyRestored": "transport.company-events",
        "CompanyDeleted": "transport.company-events",
        "CompanyDeleteRequested": "transport.company-events",
        "UserAddedToCompany": "transport.company-events",
        "UserRemovedFromCompany": "transport.company-events",
        "UserCompanyRoleChanged": "transport.company-events",
        "TelegramSupergroupCreated": "transport.company-events",
        "TelegramSupergroupLinked": "transport.company-events",
        "TelegramSupergroupUnlinked": "transport.company-events",
        "TelegramSupergroupUpdated": "transport.company-events",
        "TelegramSupergroupDeleted": "transport.company-events",
        "CompanyBalanceUpdated": "transport.company-events",
        # Saga events
        "SagaStarted": "saga.events",
        "SagaCompleted": "saga.events",
        "SagaFailed": "saga.events",
        # Chat domain events (for WSE real-time updates)
        "ChatCreated": "transport.chat-events",
        "ChatUpdated": "transport.chat-events",
        "ChatArchived": "transport.chat-events",
        "ChatRestored": "transport.chat-events",
        "ChatHardDeleted": "transport.chat-events",
        "ChatLinkedToCompany": "transport.chat-events",
        "ChatUnlinkedFromCompany": "transport.chat-events",
        "MessageSent": "transport.chat-events",
        "MessageEdited": "transport.chat-events",
        "MessageDeleted": "transport.chat-events",
        "ParticipantAdded": "transport.chat-events",
        "ParticipantRemoved": "transport.chat-events",
        "ParticipantLeft": "transport.chat-events",
        "ParticipantRoleChanged": "transport.chat-events",
        "MessagesMarkedAsRead": "transport.chat-events",
        "MessageReadStatusUpdated": "transport.chat-events",
        "TelegramChatLinked": "transport.chat-events",
        "TelegramChatUnlinked": "transport.chat-events",
        "TelegramMessageReceived": "transport.chat-events",
    }

    # Create outbox service with DLQ support
    app.state.outbox_service = create_transport_outbox(
        event_bus=app.state.event_bus,
        custom_mappings=custom_mappings,
        dlq_service=app.state.dlq_service if hasattr(app.state, 'dlq_service') else None
    )

    logger.info("Transport Outbox Service initialized.")

    # Start outbox publisher
    await start_outbox_publisher(app)


async def start_outbox_publisher(app: FastAPI) -> None:
    """Start the outbox publisher for exactly-once delivery"""

    # Import to get registered sync events
    from app.infra.cqrs.projector_decorators import get_all_sync_events
    sync_event_types = get_all_sync_events()

    # Create and start the outbox publisher
    # Uses PostgreSQL LISTEN/NOTIFY for near-zero latency
    outbox_publisher = OutboxPublisher(
        outbox_service=app.state.outbox_service,
        poll_interval_seconds=0.1,  # 100ms fallback polling
        batch_size=50,
        synchronous_mode=True,  # Always enabled
        synchronous_event_types=sync_event_types,
        use_listen_notify=True  # Instant processing via PostgreSQL NOTIFY
    )

    # Start publisher as background task
    asyncio.create_task(outbox_publisher.start())
    app.state.outbox_publisher = outbox_publisher

    logger.info(
        f"Outbox publisher started: sync_mode=True, "
        f"listen_notify=ENABLED (near-zero latency)"
    )


async def initialize_event_store(app: FastAPI) -> None:
    """Initialize KurrentDB event store with all distributed features"""
    from app.infra.event_store.projection_checkpoint_service import create_projection_checkpoint_service
    from app.infra.persistence import pg_client

    # Load KurrentDB configuration from environment
    esdb_config = EventStoreConfig.from_env()

    # Create checkpoint service
    checkpoint_service = create_projection_checkpoint_service(pg_client=pg_client)

    # Create KurrentDB event store with config object
    event_store = KurrentDBEventStore(
        config=esdb_config,
        outbox_service=app.state.outbox_service,
        saga_manager=None,  # Will be set by saga service
        sequence_tracker=app.state.sequence_tracker,
        dlq_service=app.state.dlq_service if hasattr(app.state, 'dlq_service') else None,
        checkpoint_service=checkpoint_service,
        cache_manager=app.state.cache_manager if hasattr(app.state, 'cache_manager') else None
    )

    # Initialize KurrentDB connection
    await event_store.initialize()
    app.state.event_store = event_store

    logger.info(f"KurrentDB Event Store initialized (connection: {esdb_config.connection_string})")

    # Log snapshot configuration
    if esdb_config.enable_snapshots:
        snapshot_details = []

        # Add auto-snapshot status
        if esdb_config.enable_auto_snapshots:
            snapshot_details.append("auto: enabled")
        else:
            snapshot_details.append("auto: disabled")

        # Add storage backend
        snapshot_details.append("backend: KurrentDB")

        # Add default intervals
        snapshot_details.append(f"interval: {esdb_config.snapshot_interval}")

        logger.info(f"Snapshots enabled ({', '.join(snapshot_details)})")

        # Log automatic snapshot processor status separately
        if esdb_config.enable_auto_snapshots:
            logger.info("Automatic snapshot processor started")
    else:
        logger.info("Snapshots disabled")

    # Initialize Stream Archival Service
    # Archives EventStore streams when entities are deleted from read model
    await initialize_archival_service(app)


async def initialize_archival_service(app: FastAPI) -> None:
    """
    Initialize Stream Archival Service.

    Archives EventStore streams when entities are deleted from read model,
    keeping PostgreSQL and EventStore in sync.
    """
    if not hasattr(app.state, 'event_bus') or not app.state.event_bus:
        logger.warning("EventBus not available, stream archival service disabled")
        return

    if not hasattr(app.state, 'event_store') or not app.state.event_store:
        logger.warning("EventStore not available, stream archival service disabled")
        return

    try:
        archival_service = await create_and_start_archival_service(
            event_bus=app.state.event_bus,
            event_store=app.state.event_store
        )
        app.state.archival_service = archival_service
        logger.info("Stream Archival Service initialized and started")
    except Exception as e:
        logger.warning(f"Failed to start Stream Archival Service: {e}")
        # Non-critical, don't raise


async def register_sync_projections_phase(app: FastAPI) -> None:
    """
    Register synchronous projections using decorator system.
    This is called after all services and projectors are initialized.
    """

    if not app.state.event_store:
        logger.info("Event store not available for sync projections")
        return

    logger.info("Registering synchronous projections...")

    # Import projector modules to register @sync_projection decorators
    # MessageSent projection needs to be SYNC for immediate ScyllaDB writes
    modules_to_import = [
        "app.user_account.projectors",
        "app.company.projectors",
        "app.chat.projectors",  # CRITICAL: MessageSent sync projection for ScyllaDB
    ]

    for module in modules_to_import:
        try:
            __import__(module)
            logger.debug(f"Imported {module} for sync projection registration")
        except ImportError as e:
            logger.warning(f"Could not import {module}: {e}")

    # Create projector instances - ONLY for domains that need SYNC projections
    projector_instances = {}

    # User Account Projector - SYNC (needed for immediate login after registration)
    if hasattr(app.state, 'user_account_read_repo'):
        from app.user_account.projectors import UserAccountProjector
        projector_instances["user_account"] = UserAccountProjector(
            app.state.user_account_read_repo
        )

    # Company Projector - SYNC (UserAddedToCompany needs immediate consistency)
    from app.company.projectors import CompanyProjector
    from app.infra.read_repos.company_read_repo import CompanyReadRepo
    projector_instances["company"] = CompanyProjector(CompanyReadRepo())

    # Chat Projector - SYNC (ScyllaDB = PRIMARY for messages)
    from app.chat.projectors import ChatProjector
    from app.infra.read_repos.chat_read_repo import ChatReadRepo
    from app.infra.read_repos.message_scylla_repo import MessageScyllaRepo
    projector_instances["chat"] = ChatProjector(ChatReadRepo(), MessageScyllaRepo())

    # Store projector instances in app state for debugging
    app.state.projector_instances = projector_instances

    # Auto-register all sync projections with event store
    stats = await auto_register_sync_projections(
        app.state.event_store,
        projector_instances
    )

    logger.info(
        f"Sync projections registered: "
        f"{stats['sync_events']} events, "
        f"{stats['handlers_registered']} handlers, "
        f"domains: {stats['domains']}"
    )

    # Log async projections info
    from app.infra.cqrs.projector_decorators import get_all_async_events
    async_events = get_all_async_events()
    logger.info(f"Async projections available: {len(async_events)} events")

    # Log validation issues if any
    validation = stats.get('validation', {})
    if validation.get('missing_handlers'):
        logger.warning(f"Events without handlers: {validation['missing_handlers']}")
    if validation.get('missing_events'):
        logger.warning(f"Handlers without sync events: {validation['missing_events']}")

# =============================================================================
# EOF
# =============================================================================
