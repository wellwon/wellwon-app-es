# app/core/routes.py
# =============================================================================
# File: app/core/routes.py
# Description: Route registration for FastAPI application
# =============================================================================

import logging
from app.core.fastapi_types import FastAPI

# Import routers from existing structure
from app.api.routers.user_account_router import router as auth_router
from app.api.routers.oauth_router import router as oauth_router
from app.api.routers.broker_connection_router import router as broker_router
from app.api.routers.broker_account_router import router as account_router
from app.api.routers.order_router import router as order_router
from app.api.routers.position_router import router as position_router
from app.api.routers.portfolio_router import router as portfolio_router
from app.api.routers.automation_router import router as automation_router
from app.api.routers.wse_router import router as wse_router
from app.api.routers.system_router import router as system_router
from app.api.routers.adapter_pool_router import router as pool_router
from app.api.routers.debug_router import router as debug_router
# REMOVED: streaming_router (deprecated - streaming works through adapters directly)

# Import health endpoints
from app.core.health import register_health_endpoints

logger = logging.getLogger("tradecore.routes")


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
    app.include_router(oauth_router, prefix="/oauth", tags=["OAuth"])
    app.include_router(broker_router, prefix="/broker", tags=["Broker Connections"])
    app.include_router(account_router, prefix="/account", tags=["Broker Accounts"])
    app.include_router(order_router, prefix="/orders", tags=["Orders"])
    app.include_router(position_router, prefix="/positions", tags=["Positions"])
    app.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
    app.include_router(automation_router, prefix="/automations", tags=["Automations"])
    app.include_router(wse_router, tags=["WebSocket Events"])
    app.include_router(system_router, tags=["System"])
    # REMOVED: streaming_router (deprecated - streaming works through adapters directly)

    logger.info("Core routers registered")


def register_optional_routers(app: FastAPI) -> None:
    """Register optional routers that may not be available"""

    # Debug Router (development only)
    try:
        app.include_router(debug_router, tags=["Debug"])
        logger.info("Debug router registered")
    except Exception as e:
        logger.warning(f"Debug router not available: {e}")

    # Data Integrity Router
    try:
        from app.api.routers.data_integrity_router import router as data_integrity_router
        app.include_router(data_integrity_router, tags=["Admin - Data Integrity"])
        logger.info("Data integrity router registered")
    except ImportError:
        logger.warning("Data integrity router not available")

    # Pool Management Router
    try:
        app.include_router(pool_router, prefix="/admin/pool", tags=["Admin - Pool Management"])
        logger.info("Pool management router registered")
    except Exception as pool_router_error:
        logger.warning(f"Pool management router not available: {pool_router_error}")

    # Projection Rebuilder Router
    try:
        from app.api.routers.projection_rebuilder_router import router as projection_router
        app.include_router(projection_router, tags=["Admin - Projection Management"])
        logger.info("Projection rebuilder router registered")
    except ImportError:
        logger.warning("Projection rebuilder router not available")

    # Prometheus Metrics Router
    try:
        from app.api.routers.metrics_router import router as metrics_router
        app.include_router(metrics_router, tags=["Monitoring"])
        logger.info("Prometheus metrics router registered")
    except ImportError as e:
        logger.warning(f"Prometheus metrics router not available: {e}")