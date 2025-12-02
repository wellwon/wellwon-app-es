# app/core/startup/services.py
# =============================================================================
# File: app/core/startup/services.py
# Description: Service initialization during startup
# =============================================================================

import os
import logging
import asyncio
from app.core.fastapi_types import FastAPI

# Read repositories
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
from app.infra.read_repos.chat_read_repo import ChatReadRepo
from app.infra.read_repos.company_read_repo import CompanyReadRepo
from app.infra.read_repos.message_scylla_repo import MessageScyllaRepo

# Services
from app.services.application.user_auth_service import UserAuthenticationService

logger = logging.getLogger("wellwon.startup.services")


async def initialize_read_repositories(app: FastAPI) -> None:
    """Initialize read repositories"""

    app.state.user_account_read_repo = UserAccountReadRepo()
    app.state.chat_read_repo = ChatReadRepo()
    app.state.company_read_repo = CompanyReadRepo()
    app.state.message_scylla_repo = MessageScyllaRepo()

    logger.info("Read repositories initialized.")


async def initialize_storage(app: FastAPI) -> None:
    """Initialize MinIO storage and ensure buckets exist."""
    logger.info("Initializing MinIO storage...")

    try:
        from app.infra.storage.minio_provider import get_storage_provider

        storage = get_storage_provider()

        # Ensure main bucket exists
        bucket_ok = await storage.ensure_bucket_exists()
        if bucket_ok:
            logger.info("MinIO storage initialized - bucket ready")
        else:
            logger.warning("MinIO storage initialization failed - uploads may not work")

        app.state.storage_provider = storage

    except Exception as e:
        logger.error(f"Failed to initialize MinIO storage: {e}", exc_info=True)
        logger.warning("Continuing without MinIO storage - file uploads will fail")
        app.state.storage_provider = None


async def initialize_services(app: FastAPI) -> None:
    """Initialize all application services"""
    logger.info("Starting service initialization...")

    # Ensure CQRS buses are available
    if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
        raise RuntimeError("Query Bus must be initialized before services")

    if not hasattr(app.state, 'command_bus'):
        logger.warning("Command Bus not initialized - some features may be limited")

    # Initialize MinIO storage
    await initialize_storage(app)

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
    """Initialize Telegram Event Listener and Adapter for bidirectional chat sync"""
    logger.info("Initializing Telegram Event Listener and Adapter...")

    enable_telegram = os.getenv("ENABLE_TELEGRAM_SYNC", "true").lower() == "true"

    if not enable_telegram:
        logger.info("Telegram disabled by configuration")
        app.state.telegram_event_listener = None
        app.state.telegram_adapter = None
        return

    # Ensure QueryBus is available (CQRS compliance)
    if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
        logger.warning("QueryBus not available, Telegram disabled")
        app.state.telegram_event_listener = None
        app.state.telegram_adapter = None
        return

    # Initialize TelegramAdapter first (singleton for API calls)
    try:
        from app.infra.telegram.adapter import get_telegram_adapter

        telegram_adapter = await get_telegram_adapter()
        app.state.telegram_adapter = telegram_adapter
        logger.info("TelegramAdapter initialized - outgoing Telegram API calls enabled")

        # Register incoming message handler for MTProto
        if telegram_adapter and hasattr(app.state, 'command_bus') and hasattr(app.state, 'query_bus'):
            from app.infra.telegram.mtproto_client import IncomingMessage
            from app.chat.commands import ProcessTelegramMessageCommand
            from app.chat.queries import GetChatByTelegramIdQuery
            from app.infra.event_store.kurrentdb_event_store import ConcurrencyError
            import uuid

            async def handle_incoming_telegram_message(msg: IncomingMessage):
                """Handle incoming message from Telegram MTProto and dispatch to Chat domain"""
                logger.info(f"Received Telegram message: chat_id={msg.chat_id}, topic_id={msg.topic_id}")
                try:
                    # Normalize chat ID (remove -100 prefix for supergroups)
                    chat_id_str = str(msg.chat_id)
                    if chat_id_str.startswith("-100") and len(chat_id_str) > 4:
                        normalized_chat_id = int(chat_id_str[4:])
                    else:
                        normalized_chat_id = abs(msg.chat_id)

                    logger.debug(f"Normalized chat_id={normalized_chat_id}, querying for WellWon chat")

                    # Find WellWon chat by Telegram ID
                    query = GetChatByTelegramIdQuery(
                        telegram_chat_id=normalized_chat_id,
                        telegram_topic_id=msg.topic_id,
                    )
                    chat_detail = await app.state.query_bus.query(query)

                    if not chat_detail:
                        logger.warning(f"No chat found for telegram_chat_id={normalized_chat_id}, topic_id={msg.topic_id}")
                        return

                    logger.info(f"Found chat id={chat_detail.id}, dispatching command")

                    # Determine message type
                    message_type = "text"
                    if msg.file_type == "voice":
                        message_type = "voice"
                    elif msg.file_type == "photo":
                        message_type = "image"
                    elif msg.file_type:
                        message_type = "file"

                    # Dispatch ProcessTelegramMessageCommand with retry on concurrency conflicts
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            command = ProcessTelegramMessageCommand(
                                chat_id=chat_detail.id,
                                message_id=uuid.uuid4(),  # New UUID for each retry
                                telegram_message_id=msg.message_id,
                                telegram_user_id=msg.sender_id,
                                sender_id=None,  # External Telegram user
                                content=msg.text or "",
                                message_type=message_type,
                                file_url=None,  # TODO: Download file if needed
                                file_name=msg.file_name,
                                file_size=msg.file_size,
                                file_type=msg.file_type,
                                voice_duration=msg.voice_duration,
                                telegram_topic_id=msg.topic_id,
                                telegram_user_data={
                                    "first_name": msg.sender_first_name,
                                    "last_name": msg.sender_last_name,
                                    "username": msg.sender_username,
                                    "is_bot": msg.sender_is_bot,
                                },
                            )
                            await app.state.command_bus.send(command)
                            logger.info(f"Command dispatched for chat {chat_detail.id}")
                            break  # Success - exit retry loop

                        except ConcurrencyError as ce:
                            if attempt < max_retries - 1:
                                logger.warning(f"Concurrency conflict for chat {chat_detail.id}, retry {attempt + 1}/{max_retries}")
                                await asyncio.sleep(0.05 * (2 ** attempt))  # Exponential backoff
                            else:
                                logger.error(f"Failed to process Telegram message after {max_retries} retries: {ce}")

                except Exception as e:
                    logger.error(f"Error handling Telegram message: {e}", exc_info=True)

            telegram_adapter.set_incoming_message_handler(handle_incoming_telegram_message)
            logger.info("MTProto incoming message handler registered")

            # Register read status handler for syncing Telegram read status to WellWon
            from app.infra.telegram.mtproto_client import ReadEventInfo
            from app.chat.commands import MarkMessagesAsReadCommand

            async def handle_telegram_read_event(read_info: ReadEventInfo):
                """Handle read event from Telegram and sync to WellWon"""
                logger.info(
                    f"Received Telegram read event: chat_id={read_info.chat_id}, "
                    f"max_id={read_info.max_id}, is_outbox={read_info.is_outbox}"
                )
                try:
                    # Only process outbox events (when someone else reads our messages)
                    # inbox events mean WE read messages, which shouldn't trigger a sync back
                    if not read_info.is_outbox:
                        logger.debug("Ignoring inbox read event (we read their messages)")
                        return

                    # Find WellWon chat by Telegram chat ID
                    from app.chat.queries import GetChatByTelegramIdQuery
                    query = GetChatByTelegramIdQuery(
                        telegram_chat_id=read_info.chat_id,
                        telegram_topic_id=None,  # Will match any topic in this group
                    )
                    chat_detail = await app.state.query_bus.query(query)

                    if not chat_detail:
                        logger.debug(f"No chat found for telegram_chat_id={read_info.chat_id}")
                        return

                    logger.info(
                        f"Syncing Telegram read status to WellWon chat {chat_detail.id}: "
                        f"telegram_max_id={read_info.max_id}"
                    )

                    # TODO: Map telegram_message_id to WellWon message_id
                    # For now, just log the event
                    # The full implementation would:
                    # 1. Query messages with telegram_message_id <= max_id
                    # 2. Mark those messages as read for the chat participants

                except Exception as e:
                    logger.error(f"Error handling Telegram read event: {e}", exc_info=True)

            telegram_adapter.set_read_status_handler(handle_telegram_read_event)
            logger.info("MTProto read status handler registered")

            # NOTE: Polling setup is deferred to after CQRS handlers are registered
            # See start_telegram_polling() which is called from lifespan.py Phase 10

    except ImportError as import_error:
        logger.warning(f"TelegramAdapter not available: {import_error}")
        app.state.telegram_adapter = None
    except Exception as adapter_error:
        logger.error(f"Failed to initialize TelegramAdapter: {adapter_error}", exc_info=True)
        logger.warning("TelegramAdapter disabled - chat topics will not be created in Telegram")
        app.state.telegram_adapter = None


async def _setup_telegram_polling(app: FastAPI, telegram_adapter) -> None:
    """
    Setup Telegram polling by loading all linked chats and starting the polling task.

    This is necessary because Telethon's event-based system doesn't work reliably
    when the same session is used on multiple devices (phone, desktop, etc.).
    Polling ensures we always receive messages regardless of session conflicts.
    """
    try:
        # Get the MTProto client from the adapter
        mtproto_client = telegram_adapter._mtproto_client
        if not mtproto_client:
            logger.warning("MTProto client not available, polling disabled")
            return

        # Query all chats that have a linked Telegram supergroup via CQRS
        from app.chat.queries import GetLinkedTelegramChatsQuery

        linked_chats = await app.state.query_bus.query(GetLinkedTelegramChatsQuery())
        logger.info(f"Found {len(linked_chats)} linked Telegram chats in database")

        # Only add linked chats from database - no hardcoded defaults
        if not linked_chats:
            logger.info("No linked Telegram chats found in database")
        else:
            # Add all linked chats to the polling monitor
            for chat in linked_chats:
                if chat.telegram_supergroup_id:
                    mtproto_client.add_monitored_chat(
                        chat.telegram_supergroup_id,
                        last_message_id=chat.last_telegram_message_id
                    )
                    logger.info(
                        f"Added chat '{chat.name}' (supergroup={chat.telegram_supergroup_id}, "
                        f"topic={chat.telegram_topic_id}) to polling monitor"
                    )
            logger.info(f"Added {len(linked_chats)} linked chats to polling monitor")

        # Start the polling task
        await mtproto_client.start_polling()
        logger.info("Telegram message polling started")

    except Exception as e:
        logger.error(f"Failed to setup Telegram polling: {e}", exc_info=True)

    # Initialize Event Listener for incoming events
    try:
        from app.infra.telegram.listener import create_telegram_event_listener

        telegram_listener = await create_telegram_event_listener(
            event_bus=app.state.event_bus,
            query_bus=app.state.query_bus
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
            "enable_company_events": os.getenv("WSE_ENABLE_COMPANY_EVENTS", "true").lower() == "true",
            "enable_chat_events": os.getenv("WSE_ENABLE_CHAT_EVENTS", "true").lower() == "true",
        }

        # Get chat_read_repo from app.state (initialized earlier by initialize_read_repositories)
        chat_read_repo = getattr(app.state, 'chat_read_repo', None)
        if not chat_read_repo:
            logger.warning("ChatReadRepo not available - message broadcast to participants will be disabled")

        wse_domain_publisher = WSEDomainPublisher(
            event_bus=app.state.event_bus,
            pubsub_bus=app.state.pubsub_bus,
            enable_user_events=wse_domain_config["enable_user_events"],
            enable_company_events=wse_domain_config["enable_company_events"],
            enable_chat_events=wse_domain_config["enable_chat_events"],
            chat_read_repo=chat_read_repo,
        )

        await wse_domain_publisher.start()
        app.state.wse_domain_publisher = wse_domain_publisher

        logger.info(
            f"WSE Domain Publisher started - "
            f"Users: {wse_domain_config['enable_user_events']}, "
            f"Companies: {wse_domain_config['enable_company_events']}, "
            f"Chats: {wse_domain_config['enable_chat_events']}, "
            f"ChatReadRepo: {'enabled' if chat_read_repo else 'disabled'}"
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

async def start_telegram_polling(app: FastAPI) -> None:
    """
    Start Telegram polling after CQRS handlers are registered.

    This must be called AFTER initialize_cqrs_and_handlers() because
    _setup_telegram_polling uses GetLinkedTelegramChatsQuery which requires
    the query handler to be registered.
    """
    if not hasattr(app.state, 'telegram_adapter') or not app.state.telegram_adapter:
        logger.debug("Telegram adapter not available, skipping polling setup")
        return

    await _setup_telegram_polling(app, app.state.telegram_adapter)


# =============================================================================
# EOF
# =============================================================================
