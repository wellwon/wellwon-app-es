# app/core/startup/cqrs.py
# =============================================================================
# File: app/core/startup/cqrs.py
# Description: CQRS initialization with automatic handler registration
# =============================================================================

import os
import logging
from typing import Dict, Any
from app.core.fastapi_types import FastAPI

from app.infra.cqrs.handler_dependencies import HandlerDependencies
from app.infra.cqrs.decorators import (
    auto_register_all_handlers,
    get_registered_handlers,
    validate_handler_registrations
)
from app.services.infrastructure.saga_service import create_saga_service

logger = logging.getLogger("wellwon.startup.cqrs")


async def initialize_cqrs_and_handlers(app: FastAPI) -> None:
    """Initialize CQRS components with automatic handler registration"""

    logger.info("Starting CQRS initialization with auto-registration")

    # Note: Buses are already initialized in lifespan.py Phase 5
    # We just need to register handlers

    # Import all handler modules to trigger decorators
    imported_stats = await _import_all_handler_modules()
    logger.info(f"Imported {imported_stats['success']} handler modules")

    # Show what was discovered
    discovered = get_registered_handlers()
    logger.info(
        f"Discovered {discovered['command_count']} commands and "
        f"{discovered['query_count']} queries via decorators"
    )

    # Create saga service (but don't initialize yet)
    await create_saga_service_instance(app)

    # Register all discovered handlers
    await register_cqrs_handlers(app)

    # Initialize saga service after handlers are registered
    await initialize_saga_service(app)


async def _import_all_handler_modules() -> Dict[str, Any]:
    """Import all handler modules to trigger decorator registration"""

    logger.info("Importing handler modules for auto-discovery...")

    modules_to_import = [
        # User domain - Command handlers
        ("app.user_account.command_handlers.auth_handlers", "user auth commands"),
        ("app.user_account.command_handlers.password_handlers", "user password commands"),
        ("app.user_account.command_handlers.profile_handlers", "user profile commands"),

        # User query handlers
        ("app.user_account.query_handlers.profile_query_handlers", "user profile queries"),
        ("app.user_account.query_handlers.auth_query_handlers", "user auth queries"),
        ("app.user_account.query_handlers.session_query_handlers", "user session queries"),
    ]

    successful_imports = 0
    failed_imports = []

    for module_name, description in modules_to_import:
        try:
            __import__(module_name)
            successful_imports += 1
            logger.debug(f"Imported {description} handlers from {module_name}")
        except ImportError as e:
            logger.warning(f"Could not import {description} handlers: {e}")
            failed_imports.append({
                'module': module_name,
                'description': description,
                'error': str(e)
            })
        except Exception as e:
            logger.error(f"Error importing {module_name}: {e}")
            failed_imports.append({
                'module': module_name,
                'description': description,
                'error': str(e)
            })

    # Log summary of failed imports if any
    if failed_imports:
        logger.warning(f"Failed to import {len(failed_imports)} modules:")
        for failed in failed_imports:
            logger.warning(f"  - {failed['module']}: {failed['error']}")

    return {
        'success': successful_imports,
        'failed': len(failed_imports),
        'failed_modules': failed_imports,
        'total': len(modules_to_import)
    }


async def create_saga_service_instance(app: FastAPI) -> None:
    """Create saga service instance (initialization happens later)"""

    enable_sagas = os.getenv("ENABLE_SAGA_MANAGER", "true").lower() == "true"

    if not enable_sagas:
        logger.info("Saga functionality disabled by configuration")
        app.state.saga_service = None
        return

    try:
        # Create saga service with projection rebuilder
        app.state.saga_service = create_saga_service(
            event_bus=app.state.event_bus,
            command_bus=app.state.command_bus,
            query_bus=app.state.query_bus,
            event_store=app.state.event_store,
            instance_id=os.getenv('INSTANCE_ID', 'default'),
            lock_manager=app.state.lock_manager,
            projection_rebuilder=app.state.projection_rebuilder if hasattr(app.state, 'projection_rebuilder') else None
        )

        logger.info("Saga Service created (not initialized yet)")

    except Exception as saga_error:
        logger.error(f"Failed to create Saga Service: {saga_error}", exc_info=True)
        logger.warning("Continuing without saga functionality")
        app.state.saga_service = None


async def register_cqrs_handlers(app: FastAPI) -> None:
    """Register all CQRS handlers using auto-registration"""

    # Create handler dependencies
    handler_deps = HandlerDependencies(
        event_bus=app.state.event_bus,
        event_store=app.state.event_store,
        command_bus=app.state.command_bus,
        query_bus=app.state.query_bus,
        user_read_repo=app.state.user_account_read_repo,
        global_config={},
        saga_manager=app.state.saga_service.saga_manager if app.state.saga_service else None,
        cache_manager=app.state.cache_manager,
        app=app
    )

    # Validate handlers before registration (optional)
    issues = validate_handler_registrations()
    if issues:
        logger.warning(f"Handler validation issues: {issues}")

    # Auto-register all handlers
    registration_stats = auto_register_all_handlers(
        command_bus=app.state.command_bus,
        query_bus=app.state.query_bus,
        dependencies=handler_deps,
        skip_missing_deps=True  # Skip if dependencies are missing
    )

    # Store stats for monitoring
    app.state.cqrs_registration_stats = registration_stats

    logger.info(
        f"CQRS handlers registered: "
        f"{registration_stats['commands']} command handlers, "
        f"{registration_stats['queries']} query handlers "
        f"(success rate: {registration_stats['success_rate']:.1f}%)"
    )

    if registration_stats['skipped']:
        logger.warning(
            f"Skipped {len(registration_stats['skipped'])} handlers: "
            f"{[h['handler'] for h in registration_stats['skipped']]}"
        )

    # Log bus info
    command_info = app.state.command_bus.get_handler_info()
    query_info = app.state.query_bus.get_handler_info()

    logger.info(f"Command bus: {command_info['total_handlers']} handlers")
    logger.info(f"Query bus: {query_info['total_handlers']} handlers")


async def initialize_saga_service(app: FastAPI) -> None:
    """Initialize saga service after handlers are registered"""

    if not app.state.saga_service:
        return

    try:
        # Initialize saga service (handles all saga registration internally)
        await app.state.saga_service.initialize()

        logger.info("Saga Service initialized and running")

    except Exception as saga_init_error:
        logger.error(f"Failed to initialize Saga Service: {saga_init_error}", exc_info=True)
        logger.warning("Disabling saga functionality due to initialization error")
        app.state.saga_service = None

# =============================================================================
# EOF
# =============================================================================
