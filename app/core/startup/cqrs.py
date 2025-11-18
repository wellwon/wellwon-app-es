# app/core/startup/cqrs.py
# =============================================================================
# File: app/core/startup/cqrs.py
# Description: CQRS initialization with automatic handler registration
# UPDATED: Using decorator-based auto-registration (NO MORE REGISTRIES!)
# UPDATED: Fixed imports for new broker_connection structure with separate files
# UPDATED: Added new broker_account modular structure with separate handler files
# UPDATED: Added split user_account query handlers
# UPDATED: Added new virtual_broker modular structure with separate handler files
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

logger = logging.getLogger("tradecore.startup.cqrs")


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
        # User domain - Command handlers remain in single file
        ("app.user_account.handlers", "user command"),

        # User query handlers are now split into separate files
        ("app.user_account.query_handlers.profile_query_handlers", "user profile queries"),
        ("app.user_account.query_handlers.auth_query_handlers", "user auth queries"),
        ("app.user_account.query_handlers.session_query_handlers", "user session queries"),
        ("app.user_account.query_handlers.mapping_query_handlers", "user mapping queries"),
        ("app.user_account.query_handlers.preference_query_handlers", "user preference queries"),
        ("app.user_account.query_handlers.operational_query_handlers", "user operational queries"),
        ("app.user_account.query_handlers.monitoring_query_handlers", "user monitoring queries"),

        # Broker connection domain - UPDATED FOR NEW STRUCTURE
        # Command handlers are now in separate files
        ("app.broker_connection.command_handlers.connection_handlers", "broker connection"),
        ("app.broker_connection.command_handlers.oauth_handlers", "broker OAuth"),
        ("app.broker_connection.command_handlers.disconnect_handlers", "broker disconnect"),
        ("app.broker_connection.command_handlers.batch_handlers", "broker batch operations"),

        # Query handlers are also in separate files
        ("app.broker_connection.query_handlers.connection_query_handlers", "broker connection queries"),
        ("app.broker_connection.query_handlers.oauth_query_handlers", "broker OAuth queries"),
        ("app.broker_connection.query_handlers.auth_query_handlers", "broker auth queries"),
        ("app.broker_connection.query_handlers.monitoring_query_handlers", "broker monitoring queries"),
        ("app.broker_connection.query_handlers.service_query_handlers", "broker service operations"),

        # Broker account domain - UPDATED FOR NEW STRUCTURE
        # Command handlers are now in separate files
        ("app.broker_account.command_handlers.account_management_handlers", "account management"),
        ("app.broker_account.command_handlers.balance_handlers", "account balance"),
        ("app.broker_account.command_handlers.account_discovery_handlers", "account discovery"),
        ("app.broker_account.command_handlers.account_recovery_handlers", "account recovery"),
        ("app.broker_account.command_handlers.batch_handlers", "account batch operations"),

        # Query handlers are also in separate files
        ("app.broker_account.query_handlers.account_query_handlers", "account queries"),
        ("app.broker_account.query_handlers.balance_query_handlers", "balance queries"),
        ("app.broker_account.query_handlers.monitoring_query_handlers", "account monitoring"),
        ("app.broker_account.query_handlers.service_query_handlers", "account service operations"),

        # Virtual broker domain - UPDATED FOR NEW MODULAR STRUCTURE
        # Command handlers are now in separate files
        ("app.virtual_broker.command_handlers.account_management_handlers", "virtual account management"),
        ("app.virtual_broker.command_handlers.balance_handlers", "virtual balance operations"),
        ("app.virtual_broker.command_handlers.order_handlers", "virtual order management"),
        ("app.virtual_broker.command_handlers.position_handlers", "virtual position management"),
        ("app.virtual_broker.command_handlers.corporate_action_handlers", "virtual corporate actions"),
        ("app.virtual_broker.command_handlers.risk_handlers", "virtual risk management"),
        ("app.virtual_broker.command_handlers.reporting_handlers", "virtual reporting"),
        ("app.virtual_broker.command_handlers.batch_handlers", "virtual batch operations"),
        ("app.virtual_broker.command_handlers.cache_handlers", "virtual cache management"),

        # Query handlers are also in separate files
        ("app.virtual_broker.query_handlers.account_query_handlers", "virtual account queries"),
        ("app.virtual_broker.query_handlers.position_query_handlers", "virtual position/order queries"),
        ("app.virtual_broker.query_handlers.performance_query_handlers", "virtual performance queries"),
        ("app.virtual_broker.query_handlers.cache_query_handlers", "virtual cache queries"),
        ("app.virtual_broker.query_handlers.batch_query_handlers", "virtual batch queries"),
        ("app.virtual_broker.query_handlers.monitoring_query_handlers", "virtual monitoring queries"),
        ("app.virtual_broker.query_handlers.service_query_handlers", "virtual service queries"),

        # Order domain - Command handlers in separate files
        ("app.order.command_handlers.order_lifecycle_handlers", "order lifecycle"),
        ("app.order.command_handlers.broker_sync_handlers", "order broker sync"),
        ("app.order.command_handlers.bracket_order_handlers", "bracket orders"),
        ("app.order.command_handlers.order_modification_handlers", "order modifications"),
        ("app.order.command_handlers.broker_submission_handlers", "broker order submission"),

        # Order query handlers
        ("app.order.query_handlers.order_query_handlers", "order queries"),

        # Position domain - Command handlers in separate files
        ("app.position.command_handlers.position_lifecycle_handlers", "position lifecycle"),
        ("app.position.command_handlers.pyramiding_handlers", "position pyramiding"),
        ("app.position.command_handlers.price_update_handlers", "position price updates"),
        ("app.position.command_handlers.risk_management_handlers", "position risk management"),
        ("app.position.command_handlers.reconciliation_handlers", "position reconciliation"),
        ("app.position.command_handlers.trade_correction_handlers", "position trade corrections"),

        # Position query handlers
        ("app.position.query_handlers.position_query_handlers", "position queries"),

        # Portfolio query handlers (read-only domain)
        ("app.portfolio.query_handlers.portfolio_query_handlers", "portfolio queries"),

        # Automation domain - Command handlers
        ("app.automation.command_handlers.lifecycle_handlers", "automation lifecycle"),
        ("app.automation.command_handlers.signal_handlers", "automation signal processing"),
        ("app.automation.command_handlers.pyramiding_handlers", "automation pyramiding"),

        # Automation query handlers
        ("app.automation.query_handlers.automation_query_handlers", "automation queries"),
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
            projection_rebuilder=app.state.projection_rebuilder
        )

        # Set service provider for saga context injection
        if app.state.virtual_broker_service:
            def saga_service_provider(service_name: str):
                """Provide services to saga context"""
                if service_name == 'virtual_broker_service':
                    return app.state.virtual_broker_service
                return None

            if hasattr(app.state.saga_service, 'set_service_provider'):
                app.state.saga_service.set_service_provider(saga_service_provider)

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
        operation_service=app.state.broker_operation_service,
        market_data_service=app.state.market_data_service_rest if hasattr(app.state, 'market_data_service_rest') else None,
        monitoring_service=app.state.adapter_monitoring_service,
        auth_service=app.state.broker_auth_service,
        user_auth_service=app.state.user_auth_service,
        virtual_broker_service=app.state.virtual_broker_service,
        user_read_repo=app.state.user_account_read_repo,
        broker_connection_read_repo=app.state.broker_connection_state,
        broker_account_read_repo=app.state.account_state,
        virtual_broker_read_repo=app.state.virtual_broker_read_repo,
        order_read_repo=app.state.order_read_repo if hasattr(app.state, 'order_read_repo') else None,
        position_read_repo=app.state.position_read_repo if hasattr(app.state, 'position_read_repo') else None,
        portfolio_read_repo=app.state.portfolio_read_repo if hasattr(app.state, 'portfolio_read_repo') else None,
        automation_read_repo=app.state.automation_read_repo if hasattr(app.state, 'automation_read_repo') else None,
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