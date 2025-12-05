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
    """
    Initialize Telegram Event Listener for bidirectional chat sync.

    Note: TelegramAdapter is initialized in adapters.py (Phase 1).
    This function only sets up event handlers and message routing.
    """
    logger.info("Initializing Telegram Event Listener...")

    # Check if Telegram adapter was initialized in adapters.py
    if not hasattr(app.state, 'telegram_adapter') or not app.state.telegram_adapter:
        logger.info("Telegram adapter not initialized, skipping event listener setup")
        app.state.telegram_event_listener = None
        return

    # Ensure QueryBus is available (CQRS compliance)
    if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
        logger.warning("QueryBus not available, Telegram event listener disabled")
        app.state.telegram_event_listener = None
        return

    # Get TelegramAdapter from app.state (initialized in adapters.py)
    try:
        telegram_adapter = app.state.telegram_adapter

        # Register incoming message handler for MTProto
        if telegram_adapter and hasattr(app.state, 'command_bus') and hasattr(app.state, 'query_bus'):
            from app.infra.telegram.mtproto_client import IncomingMessage
            from app.chat.commands import ProcessTelegramMessageCommand
            from app.chat.queries import GetChatByTelegramIdQuery
            from app.infra.event_store.kurrentdb_event_store import ConcurrencyError
            from app.utils.uuid_utils import generate_uuid

            async def handle_incoming_telegram_message(msg: IncomingMessage):
                """Handle incoming message from Telegram MTProto and dispatch to Chat domain"""
                import time
                t0 = time.perf_counter()
                logger.info(f"[LATENCY] T+0ms: Received Telegram message: chat_id={msg.chat_id}, topic_id={msg.topic_id}, msg_id={msg.message_id}")
                try:
                    # Secondary safeguard: skip bot messages (primary filter is in MTProto client)
                    if msg.sender_is_bot:
                        logger.info(f"[HANDLER] Skipping bot message from {msg.sender_username or msg.sender_id}")
                        return

                    # Normalize chat ID (remove -100 prefix for supergroups)
                    chat_id_str = str(msg.chat_id)
                    if chat_id_str.startswith("-100") and len(chat_id_str) > 4:
                        normalized_chat_id = int(chat_id_str[4:])
                    else:
                        normalized_chat_id = abs(msg.chat_id)

                    logger.debug(f"Normalized chat_id={normalized_chat_id}, querying for WellWon chat")

                    # Find WellWon chat by Telegram ID
                    t1 = time.perf_counter()
                    query = GetChatByTelegramIdQuery(
                        telegram_chat_id=normalized_chat_id,
                        telegram_topic_id=msg.topic_id,
                    )
                    chat_detail = await app.state.query_bus.query(query)
                    t2 = time.perf_counter()
                    logger.info(f"[LATENCY] T+{(t2-t0)*1000:.0f}ms: Chat lookup took {(t2-t1)*1000:.0f}ms")

                    if not chat_detail:
                        logger.warning(f"No chat found for telegram_chat_id={normalized_chat_id}, topic_id={msg.topic_id}")
                        return

                    logger.info(
                        f"[ROUTING] Matched message: tg_chat={normalized_chat_id}, tg_topic={msg.topic_id} "
                        f"-> wellwon_chat={chat_detail.id}, chat_topic={chat_detail.telegram_topic_id}, chat_name={chat_detail.name}"
                    )

                    # Determine message type
                    message_type = "text"
                    if msg.file_type == "voice":
                        message_type = "voice"
                    elif msg.file_type == "photo":
                        message_type = "image"
                    elif msg.file_type == "video":
                        message_type = "video"
                    elif msg.file_type == "video_note":
                        message_type = "video_note"
                    elif msg.file_type:
                        message_type = "file"

                    # Get file URL for media messages (voice, photo, etc.)
                    file_url = None
                    if msg.file_id:
                        try:
                            if msg.file_id.startswith("mtproto:"):
                                # MTProto file - download via MTProto and upload to MinIO
                                # Parse: mtproto:type:message_id:chat_id
                                parts = msg.file_id.split(":")
                                if len(parts) >= 4:
                                    mtproto_type = parts[1]
                                    tg_message_id = int(parts[2])
                                    tg_chat_id = int(parts[3])

                                    logger.info(f"[FILE] Downloading {mtproto_type} via MTProto: msg_id={tg_message_id}, chat_id={tg_chat_id}")

                                    # Download file bytes via MTProto
                                    file_bytes = await telegram_adapter.download_file_mtproto_by_message(
                                        chat_id=tg_chat_id,
                                        message_id=tg_message_id
                                    )

                                    if file_bytes:
                                        # Upload to MinIO for permanent storage
                                        from app.infra.storage.minio_provider import get_storage_provider
                                        storage = get_storage_provider()

                                        # Determine content type
                                        content_type = "audio/ogg" if mtproto_type == "voice" else "application/octet-stream"
                                        if mtproto_type == "photo":
                                            content_type = "image/jpeg"
                                        elif mtproto_type == "video":
                                            content_type = "video/mp4"

                                        result = await storage.upload_file(
                                            bucket="chat-files",
                                            file_content=file_bytes,
                                            content_type=content_type,
                                            original_filename=msg.file_name or f"{mtproto_type}_{tg_message_id}",
                                        )

                                        if result.success:
                                            file_url = result.public_url
                                            logger.info(f"[FILE] Uploaded to MinIO: {file_url[:50]}...")
                                        else:
                                            logger.warning(f"[FILE] MinIO upload failed: {result.error}")
                                    else:
                                        logger.warning(f"[FILE] MTProto download returned no bytes")
                            else:
                                # Regular Bot API file_id - get temporary CDN URL
                                file_url = await telegram_adapter.get_file_url(msg.file_id)
                                if file_url:
                                    logger.info(f"[FILE] Got temp URL for {msg.file_type}: {file_url[:50]}...")
                                else:
                                    logger.warning(f"[FILE] Could not get URL for file_id={msg.file_id}")
                        except Exception as file_err:
                            logger.warning(f"[FILE] Error getting file URL: {file_err}", exc_info=True)

                    # Dispatch ProcessTelegramMessageCommand with retry on concurrency conflicts
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            command = ProcessTelegramMessageCommand(
                                chat_id=chat_detail.id,
                                message_id=generate_uuid(),  # New UUIDv7 for each retry
                                telegram_message_id=msg.message_id,
                                telegram_chat_id=normalized_chat_id,  # For deduplication lookup
                                telegram_user_id=msg.sender_id,
                                sender_id=None,  # External Telegram user
                                content=msg.text or "",
                                message_type=message_type,
                                file_url=file_url,  # Temp Telegram CDN URL for immediate playback
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
                            t3 = time.perf_counter()
                            await app.state.command_bus.send(command)
                            t4 = time.perf_counter()
                            logger.info(f"[LATENCY] T+{(t4-t0)*1000:.0f}ms: Command dispatch took {(t4-t3)*1000:.0f}ms for chat {chat_detail.id}")
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
            # Uses TelegramIncomingHandler which properly encapsulates the business logic
            from app.infra.telegram.incoming_handler import get_incoming_handler

            incoming_handler = await get_incoming_handler(
                command_bus=app.state.command_bus,
                query_bus=app.state.query_bus,
                event_bus=app.state.event_bus,
            )

            telegram_adapter.set_read_status_handler(incoming_handler.handle_read_event)
            logger.info("MTProto read status handler registered (via TelegramIncomingHandler)")

            # NOTE: Event listener setup is deferred to after CQRS handlers are registered
            # See start_telegram_event_listener() which is called from lifespan.py Phase 11

    except ImportError as import_error:
        logger.warning(f"Telegram event listener setup failed: {import_error}")
        app.state.telegram_event_listener = None
    except Exception as listener_error:
        logger.error(f"Failed to setup Telegram event listener: {listener_error}", exc_info=True)
        logger.warning("Telegram event listener disabled - incoming messages won't be processed")
        app.state.telegram_event_listener = None


async def _setup_telegram_event_listener(app: FastAPI, telegram_adapter) -> None:
    """
    Setup Telegram Event Listener for bidirectional message sync.

    Messages are received via Telethon's event-driven system (no polling).
    The MTProto client uses run_until_disconnected() to receive real-time updates.
    """
    # Initialize Event Listener for outgoing WellWon -> Telegram events
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

async def start_telegram_event_listener(app: FastAPI) -> None:
    """
    Start Telegram Event Listener for bidirectional sync.

    Incoming messages are received via Telethon's event-driven system.
    This just sets up the listener for WellWon -> Telegram sync.
    """
    if not hasattr(app.state, 'telegram_adapter') or not app.state.telegram_adapter:
        logger.debug("Telegram adapter not available, skipping event listener setup")
        return

    await _setup_telegram_event_listener(app, app.state.telegram_adapter)


# =============================================================================
# EOF
# =============================================================================
