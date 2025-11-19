# app/core/routes.py
# =============================================================================
# File: app/core/routes.py
# Description: Route registration for FastAPI application
# =============================================================================

import logging
from app.core.fastapi_types import FastAPI

# Import routers from existing structure
from app.api.routers.user_account_router import router as auth_router
from app.api.routers.wse_router import router as wse_router

# Import health endpoints
from app.core.health import register_health_endpoints

logger = logging.getLogger("wellwon.routes")


def setup_routes(app: FastAPI) -> None:
    """Register all routers with the FastAPI application"""

    # Register core routers
    register_core_routers(app)

    # Register optional routers
    register_optional_routers(app)

    # Register health endpoints
    register_health_endpoints(app)


def register_core_routers(app: FastAPI) -> None:
    """Register core application routers"""

    app.include_router(auth_router, prefix="/user", tags=["User Accounts"])
    app.include_router(wse_router, tags=["WebSocket Events"])

    logger.info("Core routers registered")


def register_optional_routers(app: FastAPI) -> None:
    """Register optional routers that may not be available"""

    # Projection Rebuilder Router
    try:
        from app.api.routers.projection_rebuilder_router import router as projection_router
        app.include_router(projection_router, tags=["Admin - Projection Management"])
        logger.info("Projection rebuilder router registered")
    except ImportError:
        pass  # Not critical

    # Prometheus Metrics Router
    try:
        from app.api.routers.metrics_router import router as metrics_router
        app.include_router(metrics_router, tags=["Monitoring"])
        logger.info("Prometheus metrics router registered")
    except ImportError:
        pass  # Not critical
