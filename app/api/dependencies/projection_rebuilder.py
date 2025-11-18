# app/api/dependencies/projection_rebuilder.py
"""
Simplified dependency injection for projection rebuilder service.
Add this to your dependencies module.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request

from app.services.infrastructure.projection_rebuilder_service import ProjectionRebuilderService

# Global reference to the service (set during app startup)
_projection_rebuilder_service: Optional[ProjectionRebuilderService] = None


def set_projection_rebuilder_service(service: ProjectionRebuilderService) -> None:
    """
    Set the global projection rebuilder service instance.
    This should be called during app startup.
    """
    global _projection_rebuilder_service
    _projection_rebuilder_service = service


def get_projection_rebuilder_service(request: Request) -> ProjectionRebuilderService:
    """
    Dependency to get projection rebuilder service.
    First tries to get from request.app.state, then falls back to global.
    """
    # Try to get from app state first
    if hasattr(request.app.state, 'projection_rebuilder') and request.app.state.projection_rebuilder:
        return request.app.state.projection_rebuilder

    # Fall back to global reference
    if _projection_rebuilder_service:
        return _projection_rebuilder_service

    # Service not available
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Projection rebuilder service not available"
    )


# Then update the router to use this simpler dependency:
# In projection_rebuilder_router.py, replace the import and usage:

"""
from app.api.dependencies.projection_rebuilder import get_projection_rebuilder_service

# Remove the complex get_projection_rebuilder_service function from the router
# The dependency is now imported from the dependencies module
"""