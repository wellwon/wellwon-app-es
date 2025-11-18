# app/api/models/projection_rebuilder_models.py
"""
API models for projection rebuilder endpoints
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field


class RebuildPriority(str, Enum):
    """Priority levels for rebuild operations"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RebuildStatus(str, Enum):
    """Status of a projection rebuild"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectionRebuildRequest(BaseModel):
    """Request to rebuild a specific projection"""
    projection_name: str = Field(..., description="Name of the projection to rebuild")
    priority: RebuildPriority = Field(
        RebuildPriority.NORMAL,
        description="Priority level for the rebuild"
    )
    from_timestamp: Optional[datetime] = Field(
        None,
        description="Start timestamp for event replay (None = from beginning)"
    )
    to_timestamp: Optional[datetime] = Field(
        None,
        description="End timestamp for event replay (None = to latest)"
    )
    force: bool = Field(
        False,
        description="Force rebuild even if one is already in progress"
    )
    dry_run: bool = Field(
        False,
        description="Simulate rebuild without actually publishing events"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for triggering the rebuild"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "projection_name": "broker_accounts",
                "priority": "normal",
                "force": False,
                "dry_run": False,
                "reason": "Manual rebuild requested by admin"
            }
        }
    }


class AggregateRebuildRequest(BaseModel):
    """Request to rebuild projections for a specific aggregate"""
    aggregate_type: str = Field(..., description="Type of aggregate (e.g., BrokerAccount, Order)")
    aggregate_id: Optional[UUID] = Field(
        None,
        description="Specific aggregate ID (None = all aggregates of this type)"
    )
    projection_types: Optional[List[str]] = Field(
        None,
        description="Specific projections to rebuild (None = all related projections)"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for triggering the rebuild"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "aggregate_type": "BrokerAccount",
                "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
                "projection_types": ["broker_accounts"],
                "reason": "Account recovery after sync issue"
            }
        }
    }


class RebuildAllRequest(BaseModel):
    """Request to rebuild all projections"""
    priority: RebuildPriority = Field(
        RebuildPriority.LOW,
        description="Priority level for the rebuild"
    )
    force: bool = Field(
        False,
        description="Force rebuild even if projections are already being rebuilt"
    )
    parallel: bool = Field(
        False,
        description="Rebuild projections in parallel (respecting dependencies)"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for triggering the rebuild"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "priority": "low",
                "force": False,
                "parallel": True,
                "reason": "Scheduled maintenance rebuild"
            }
        }
    }


class RebuildProgress(BaseModel):
    """Progress information for a projection rebuild"""
    projection_name: str
    status: RebuildStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_checkpoint: Optional[datetime] = None
    events_processed: int = 0
    events_published: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RebuildResponse(BaseModel):
    """Response for rebuild requests"""
    success: bool
    message: str
    projection_name: Optional[str] = None
    status: Optional[str] = None
    rebuild_id: Optional[str] = None
    queue_position: Optional[int] = None
    estimated_wait_seconds: Optional[int] = None
    progress: Optional[RebuildProgress] = None
    metadata: Optional[Dict[str, Any]] = None


class AggregateRebuildResponse(BaseModel):
    """Response for aggregate rebuild requests"""
    success: bool
    message: str
    aggregate_type: str
    aggregate_id: Optional[str] = None
    projections_queued: List[Dict[str, Any]]
    status: str


class ServiceStatus(BaseModel):
    """Service status information"""
    running: bool
    queue_size: int
    active_rebuilds: int
    max_concurrent: int
    reliability_infra: bool


class ServiceMetrics(BaseModel):
    """Service metrics"""
    total_rebuilds: int
    successful_rebuilds: int
    failed_rebuilds: int
    cancelled_rebuilds: int
    total_events_processed: int
    total_events_published: int
    average_duration_seconds: float
    last_rebuild_at: Optional[datetime]
    circuit_breaker_trips: int
    retry_attempts: int
    rate_limit_hits: int


class ProjectionStatus(BaseModel):
    """Status of a single projection"""
    is_active: bool
    status: str
    events_processed: int
    events_published: int
    last_run: Optional[datetime]
    dependencies: List[str]
    transport_topic: str


class StatusResponse(BaseModel):
    """Complete status response"""
    service: ServiceStatus
    metrics: ServiceMetrics
    circuit_breakers: Dict[str, Any]
    projections: Dict[str, ProjectionStatus]
    active_requests: Dict[str, Dict[str, Any]]


class ProjectionConfig(BaseModel):
    """Configuration for a projection"""
    name: str
    aggregate_type: Optional[str]
    event_types: Optional[List[str]]
    transport_topic: str
    batch_size: int
    dependencies: List[str]
    enabled: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""
    healthy: bool
    issues: List[str]
    metrics: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Projection not found",
                "detail": "Unknown projection: invalid_projection",
                "timestamp": "2023-08-15T10:30:00Z"
            }
        }
    }