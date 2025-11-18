# app/api/routers/projection_rebuilder_router.py
"""
FastAPI router for projection rebuilder service.
Compatible with Python 3.13 and latest FastAPI.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Request
)
from fastapi.responses import JSONResponse

from app.api.models.projection_rebuilder_models import (
    ProjectionRebuildRequest,
    AggregateRebuildRequest,
    RebuildAllRequest,
    RebuildResponse,
    AggregateRebuildResponse,
    StatusResponse,
    ProjectionConfig,
    HealthCheckResponse,
    ErrorResponse,
    RebuildPriority,
    RebuildStatus,
    ServiceStatus,
    ServiceMetrics,
    ProjectionStatus,
    RebuildProgress
)
from app.security.jwt_auth import get_current_user
from app.services.infrastructure.projection_rebuilder_service import ProjectionRebuilderService
from app.common.exceptions.exceptions import ProjectionRebuildError

logger = logging.getLogger("wellwon.api.projection_rebuilder")

# Create router
router = APIRouter(
    prefix="/projection-rebuilder",
    tags=["projection-rebuilder"],
    responses={
        404: {"model": ErrorResponse, "description": "Projection not found"},
        409: {"model": ErrorResponse, "description": "Conflict - Rebuild already in progress"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


async def get_projection_rebuilder_service(request: Request) -> ProjectionRebuilderService:
    """
    Dependency to get projection rebuilder service from app state.
    """
    if hasattr(request.app.state, 'projection_rebuilder'):
        return request.app.state.projection_rebuilder

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Projection rebuilder service not available"
    )


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild_projection(
        request: ProjectionRebuildRequest,
        current_user: Annotated[dict, Depends(get_current_user)],
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> RebuildResponse:
    """
    Rebuild a specific projection.

    Requires authentication. The rebuild will be queued based on the specified priority.
    High priority rebuilds will wait for completion before returning.
    """
    try:
        logger.info(
            f"User {current_user.get('email', 'unknown')} requested rebuild of {request.projection_name} "
            f"with priority {request.priority}"
        )

        # Call service method
        progress = await service.rebuild_projection(
            projection_name=request.projection_name,
            from_timestamp=request.from_timestamp,
            to_timestamp=request.to_timestamp,
            priority=request.priority,
            requested_by=f"user:{current_user.get('email', 'unknown')}",
            reason=request.reason,
            force=request.force,
            dry_run=request.dry_run
        )

        # Build response based on status
        if progress.status == RebuildStatus.PENDING:
            return RebuildResponse(
                success=True,
                message=f"Rebuild queued for {request.projection_name}",
                projection_name=request.projection_name,
                status=progress.status.value,
                queue_position=progress.metadata.get("queue_size", 0)
            )
        else:
            return RebuildResponse(
                success=True,
                message=f"Rebuild completed for {request.projection_name}",
                projection_name=request.projection_name,
                status=progress.status.value,
                progress=RebuildProgress(
                    projection_name=progress.projection_name,
                    status=progress.status,
                    started_at=progress.started_at,
                    completed_at=progress.completed_at,
                    last_checkpoint=progress.last_checkpoint,
                    events_processed=progress.events_processed,
                    events_published=progress.events_published,
                    errors_count=len(progress.errors) if hasattr(progress, 'errors') else 0,
                    last_error=progress.last_error if hasattr(progress, 'last_error') else None,
                    metadata=progress.metadata if hasattr(progress, 'metadata') else {}
                )
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ProjectionRebuildError as e:
        if "already being rebuilt" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to rebuild projection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild projection: {str(e)}"
        )


@router.post("/rebuild-aggregate", response_model=AggregateRebuildResponse)
async def rebuild_aggregate_projections(
        request: AggregateRebuildRequest,
        current_user: Annotated[dict, Depends(get_current_user)],
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> AggregateRebuildResponse:
    """
    Rebuild projections for a specific aggregate type.

    This is useful for rebuilding projections after recovering or modifying
    specific aggregates. All related projections will be rebuilt.
    """
    try:
        logger.info(
            f"User {current_user.get('email', 'unknown')} requested aggregate rebuild for {request.aggregate_type}"
        )

        result = await service.rebuild_aggregate_projections(
            aggregate_type=request.aggregate_type,
            aggregate_id=request.aggregate_id,
            projection_types=request.projection_types,
            requested_by=f"user:{current_user.get('email', 'unknown')}",
            reason=request.reason
        )

        return AggregateRebuildResponse(
            success=True,
            message=f"Queued rebuild for {request.aggregate_type} projections",
            aggregate_type=request.aggregate_type,
            aggregate_id=str(request.aggregate_id) if request.aggregate_id else None,
            projections_queued=result.get("projections_queued", []),
            status=result.get("status", "queued")
        )

    except Exception as e:
        logger.error(f"Failed to rebuild aggregate projections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild aggregate projections: {str(e)}"
        )


@router.post("/rebuild-all", response_model=RebuildResponse)
async def rebuild_all_projections(
        request: RebuildAllRequest,
        current_user: Annotated[dict, Depends(get_current_user)],
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> RebuildResponse:
    """
    Rebuild all projections.

    This operation rebuilds all registered projections, respecting their dependencies.
    Use with caution as this can be a resource-intensive operation.
    """
    try:
        # Check if user is admin (adjust based on your auth system)
        if not current_user.get('is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can rebuild all projections"
            )

        logger.warning(
            f"Admin {current_user.get('email', 'unknown')} initiated full projection rebuild"
        )

        result = await service.rebuild_all_projections(
            priority=request.priority,
            requested_by=f"admin:{current_user.get('email', 'unknown')}",
            reason=request.reason or "Full rebuild requested by admin",
            force=request.force,
            parallel=request.parallel
        )

        if result.get("status") == "completed":
            return RebuildResponse(
                success=True,
                message=f"Completed rebuild of all projections in {result.get('mode', 'unknown')} mode",
                status="completed",
                metadata=result.get("results", {})
            )
        else:
            return RebuildResponse(
                success=True,
                message=f"Queued rebuild of {len(result.get('projections_queued', []))} projections",
                status="queued",
                queue_position=result.get("queue_size", 0)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rebuild all projections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild all projections: {str(e)}"
        )


@router.get("/status", response_model=StatusResponse)
async def get_service_status(
        projection_name: Annotated[Optional[str], Query(description="Get status for specific projection")] = None,
        current_user: Annotated[dict, Depends(get_current_user)] = None,
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)] = None
) -> StatusResponse:
    """
    Get comprehensive status of the projection rebuilder service.

    Returns service status, metrics, and information about all projections.
    If projection_name is provided, returns detailed status for that projection.
    """
    try:
        status_data = await service.get_status()

        # Convert to response model
        return StatusResponse(
            service=ServiceStatus(
                running=status_data["service"]["running"],
                queue_size=status_data["service"]["queue_size"],
                active_rebuilds=status_data["service"]["active_rebuilds"],
                max_concurrent=status_data["service"]["max_concurrent"],
                reliability_infra=status_data["service"]["reliability_infra"]
            ),
            metrics=ServiceMetrics(**status_data["metrics"]),
            circuit_breakers=status_data.get("circuit_breakers", {}),
            projections={
                name: ProjectionStatus(**proj_status)
                for name, proj_status in status_data.get("projections", {}).items()
            },
            active_requests=status_data.get("active_requests", {})
        )

    except Exception as e:
        logger.error(f"Failed to get service status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {str(e)}"
        )


@router.get("/projection/{projection_name}/config", response_model=ProjectionConfig)
async def get_projection_config(
        projection_name: str,
        current_user: Annotated[dict, Depends(get_current_user)],
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> ProjectionConfig:
    """
    Get configuration for a specific projection.

    Returns the projection's configuration including dependencies and event types.
    """
    try:
        config = await service.get_projection_config(projection_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Projection '{projection_name}' not found"
            )

        return ProjectionConfig(**config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get projection config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get projection config: {str(e)}"
        )


@router.delete("/projection/{projection_name}/cancel")
async def cancel_rebuild(
        projection_name: str,
        current_user: Annotated[dict, Depends(get_current_user)],
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> Dict[str, Any]:
    """
    Cancel an active rebuild for a projection.

    This will attempt to cancel the rebuild if it's currently in progress.
    """
    try:
        logger.info(
            f"User {current_user.get('email', 'unknown')} requested cancellation of {projection_name} rebuild"
        )

        cancelled = await service.cancel_rebuild(projection_name)

        if cancelled:
            return {
                "success": True,
                "message": f"Rebuild of {projection_name} has been cancelled"
            }
        else:
            return {
                "success": False,
                "message": f"No active rebuild found for {projection_name}"
            }

    except Exception as e:
        logger.error(f"Failed to cancel rebuild: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel rebuild: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
        service: Annotated[ProjectionRebuilderService, Depends(get_projection_rebuilder_service)]
) -> HealthCheckResponse:
    """
    Health check endpoint for the projection rebuilder service.

    Returns health status and any issues detected.
    """
    try:
        health = await service.health_check()

        return HealthCheckResponse(
            healthy=health["healthy"],
            issues=health.get("issues", []),
            metrics=health.get("metrics", {})
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return HealthCheckResponse(
            healthy=False,
            issues=[f"Health check failed: {str(e)}"],
            metrics={}
        )


@router.websocket("/ws/progress/{projection_name}")
async def rebuild_progress_websocket(
        websocket: WebSocket,
        projection_name: str
):
    """
    WebSocket endpoint for real-time rebuild progress updates.

    Connect to this endpoint to receive live updates about a projection rebuild.
    """
    await websocket.accept()

    try:
        # Get service from app state via WebSocket
        service = None
        if hasattr(websocket, 'app') and hasattr(websocket.app.state, 'projection_rebuilder'):
            service = websocket.app.state.projection_rebuilder
        else:
            await websocket.send_json({
                "error": "Projection rebuilder service not available"
            })
            await websocket.close()
            return

        # Send updates every second while rebuild is active
        while True:
            status_data = await service.get_status()

            # Check if projection is being rebuilt
            if projection_name in status_data.get("active_requests", {}):
                await websocket.send_json({
                    "projection": projection_name,
                    "status": "in_progress",
                    "details": status_data["active_requests"][projection_name]
                })
            else:
                # Check if completed
                projection_status = status_data.get("projections", {}).get(projection_name)
                if projection_status:
                    await websocket.send_json({
                        "projection": projection_name,
                        "status": "completed",
                        "details": projection_status
                    })
                    break
                else:
                    await websocket.send_json({
                        "projection": projection_name,
                        "status": "not_found"
                    })
                    break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for projection {projection_name}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass


def get_projection_rebuilder_router(
        service: Optional[ProjectionRebuilderService] = None
) -> APIRouter:
    """
    Factory function to create the router with an optional service instance.

    This is useful for testing or when you want to inject a specific service instance.
    """
    if service:
        # Override the dependency
        async def override_get_service():
            return service

        router.dependency_overrides[get_projection_rebuilder_service] = override_get_service

    return router