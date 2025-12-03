# app/core/lifespan.py
# =============================================================================
# File: app/core/lifespan.py
# Description: Application lifespan management (startup/shutdown)
# =============================================================================

import asyncio
import logging
from contextlib import asynccontextmanager
from app.core.fastapi_types import FastAPI

from app.core import __version__
from app.core.app_state import AppState
from app.core.background_tasks import start_background_tasks, stop_background_tasks
from app.core.startup.infrastructure import (
   initialize_databases,
   initialize_cache,
   initialize_event_infrastructure,
   run_database_schemas
)
from app.core.startup.services import (
   initialize_read_repositories,
   initialize_services,
   initialize_optional_services,
   start_telegram_polling
)
from app.core.startup.distributed import initialize_distributed_features, register_sync_projections_phase
from app.core.startup.cqrs import initialize_cqrs_and_handlers
from app.core.startup.adapters import initialize_adapters
from app.core.shutdown import shutdown_all_services

logger = logging.getLogger("wellwon.lifespan")


# =============================================================================
# LIFESPAN (Startup/Shutdown)
# =============================================================================
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
   """Application lifespan manager with structured initialization"""

   logger.info(f"{__version__} API starting up...")

   # Initialize app state
   app_instance.state = AppState()

   try:
       # Phase 1: Core Infrastructure
       logger.info("Phase 1: Initializing core infrastructure...")
       await initialize_databases(app_instance)
       await initialize_cache(app_instance)
       await initialize_event_infrastructure(app_instance)

       # Phase 2: Read Repositories
       logger.info("Phase 2: Initializing read repositories...")
       await initialize_read_repositories(app_instance)

       # Phase 3: Distributed Features (Event Store, Locks, etc.)
       logger.info("Phase 3: Initializing distributed features...")
       await initialize_distributed_features(app_instance)

       # Phase 4: CQRS Infrastructure
       logger.info("Phase 4: Initializing CQRS...")
       from app.infra.cqrs.command_bus import CommandBus
       from app.infra.cqrs.query_bus import QueryBus

       # Create command bus
       command_bus = CommandBus()

       app_instance.state.command_bus = command_bus
       app_instance.state.query_bus = QueryBus(enable_caching=True)
       logger.info("CQRS buses initialized")

       # Phase 5: External Adapters
       logger.info("Phase 5: Initializing external adapters...")
       await initialize_adapters(app_instance)

       # Phase 6: Core Services
       logger.info("Phase 6: Initializing core services...")
       await initialize_services(app_instance)

       # Phase 7: CQRS Handlers and Saga Service
       logger.info("Phase 7: Initializing CQRS handlers and saga service...")
       await initialize_cqrs_and_handlers(app_instance)

       # Phase 8: Optional Services (Projection Rebuilder)
       logger.info("Phase 8: Initializing optional services...")
       await initialize_optional_services(app_instance)

       # Phase 9: Register Synchronous Projections
       logger.info("Phase 9: Registering synchronous projections...")
       await register_sync_projections_phase(app_instance)

       # Phase 10: Database Schemas
       logger.info("Phase 10: Running database schemas...")
       await run_database_schemas()

       # Phase 11: Telegram Polling (after CQRS handlers are registered)
       logger.info("Phase 11: Starting Telegram polling...")
       await start_telegram_polling(app_instance)

       # Phase 12: Background Tasks
       logger.info("Phase 12: Starting background tasks...")
       await start_background_tasks(app_instance)

       # Startup complete
       logger.info("=" * 60)
       logger.info("Application startup complete - all systems operational")
       logger.info(f"WellWon v{__version__} ready to serve requests")
       logger.info("=" * 60)

       await asyncio.sleep(0.1)  # Small delay to ensure all async initialization is complete

       yield

   except Exception as startup_error:
       logger.error(f"Critical error during startup: {startup_error}", exc_info=True)
       raise

   finally:
       # Graceful shutdown with timeout to prevent hanging
       logger.info(f"WellWon v{__version__} API shutting down...")
       try:
           # Use timeout to prevent hanging during shutdown
           async with asyncio.timeout(30.0):
               await stop_background_tasks(app_instance)
               await shutdown_all_services(app_instance)
           logger.info(f"WellWon v{__version__} API stopped gracefully")
       except TimeoutError:
           logger.error("Shutdown timed out after 30s, forcing exit")
           logger.error("This usually indicates a blocking operation in shutdown handlers")
       except Exception as e:
           logger.error(f"Error during shutdown: {e}", exc_info=True)

# =============================================================================
# EOF
# =============================================================================
