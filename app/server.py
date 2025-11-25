# app/server.py
# =============================================================================
# File: app/server.py
# Project: 
# Description: Main FastAPI application entry point (refactored for modularity)
# =============================================================================

from __future__ import annotations

import os
import logging
from app.core.fastapi_types import FastAPI

from app.core import __version__
from app.core.lifespan import lifespan
from app.core.middleware import setup_middleware
from app.core.routes import setup_routes
from app.core.exceptions import setup_exception_handlers
from app.config.logging_config import setup_logging

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
setup_logging(
    service_name="api",
    log_file=os.getenv("LOG_FILE") if os.getenv("LOG_FILE") else None,
    enable_json=os.getenv("ENVIRONMENT") == "production",
    service_type="api"  # Green border for main API
)

# Get logger for this module
logger = logging.getLogger("wellwon.server")

# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(
    title=f"WellWon API v{__version__}",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# =============================================================================
# SETUP COMPONENTS
# =============================================================================
setup_middleware(app)
setup_routes(app)
setup_exception_handlers(app)

# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================
# Export commonly used functions for backward compatibility
from app.core.app_state import get_start_time
from app.core.background_tasks import _stop_requested

__all__ = ["app", "get_start_time", "__version__", "_stop_requested"]

# =============================================================================
# Development entry point
# =============================================================================
if __name__ == "__main__":
    import subprocess
    import sys

    port = os.getenv("PORT", "5001")
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "true").lower() == "true"

    logger.info(f"Starting WellWon API on {host}:{port} (reload={reload})")

    # Build granian command
    cmd = [
        "granian",
        "--interface", "asgi",
        "app.server:app",
        "--host", host,
        "--port", str(port),
        "--http", "2"
    ]

    if reload:
        cmd.extend([
            "--reload",
            "--reload-paths", "app/",  # Watch ONLY app/ directory - ignores everything else
            "--reload-tick", "100",
        ])

    # Run granian
    subprocess.run(cmd)