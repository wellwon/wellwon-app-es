# app/wse/dependencies.py
# =============================================================================
# File: app/wse/dependencies.py
# Description: WSE Dependency Injection for FastAPI
# REFACTORED: Moved to WSE bounded context (DDD best practice)
# =============================================================================

from typing import Optional
from fastapi import WebSocket

from app.wse.services.snapshot_service import WSESnapshotService, SnapshotServiceProtocol, create_wse_snapshot_service

# Cache the service instances
_snapshot_service: Optional[WSESnapshotService] = None


def get_snapshot_service(websocket: WebSocket) -> SnapshotServiceProtocol:
    """
    Get snapshot service with QueryBus dependency injection for WebSocket endpoints.

    REFACTORED: Now uses FastAPI WebSocket to get query_bus from app.state (CQRS compliant).
    FIXED: Proper FastAPI dependency injection for WebSocket connections.

    Args:
        websocket: FastAPI WebSocket object (injected by FastAPI, provides access to app.state)

    Returns:
        SnapshotServiceProtocol instance with QueryBus injected

    Raises:
        ValueError: If query_bus is not available in app.state
    """
    global _snapshot_service

    if _snapshot_service is None:
        # Get app from WebSocket scope
        app = websocket.scope.get("app")

        if not app:
            # Try alternative method
            request = websocket.scope.get("request")
            if request and hasattr(request, 'app'):
                app = request.app

        if not app:
            raise ValueError("Cannot access app from WebSocket scope. Ensure FastAPI app is properly configured.")

        # Get query_bus from app state
        if not hasattr(app.state, 'query_bus') or not app.state.query_bus:
            raise ValueError("query_bus not available in app.state. Ensure CQRS is initialized.")

        # Create service with proper QueryBus injection
        _snapshot_service = create_wse_snapshot_service(
            query_bus=app.state.query_bus,
            include_integrity_fields=True
        )

    return _snapshot_service


def reset_snapshot_service() -> None:
    """Reset the snapshot service instance (useful for testing)"""
    global _snapshot_service
    _snapshot_service = None