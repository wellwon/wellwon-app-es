# =============================================================================
# File: app/models/system_api_models.py
# Description: API models for system health and status endpoints
# =============================================================================

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from enum import Enum

# Update system_api_models.py to import from enums.py
from app.common.enums.enums import SystemHealthStatusEnum, ComponentStatusEnum

# Schema version for system API responses
SYSTEM_API_SCHEMA_VERSION = "1.0.0"

# =============================================================================
# System API Models
# =============================================================================

# Then replace the local enum classes with the imported ones
# Replace 'SystemHealthStatus' with 'SystemHealthStatusEnum'
# Replace 'ComponentStatus' with 'ComponentStatusEnum'
class SystemHealthStatus(str, Enum):
    """Health status values for system components"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    ERROR = "error"
    UNKNOWN = "unknown"

class ComponentStatus(str, Enum):
    """Status values for individual components"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ALIVE = "alive"
    UNREACHABLE = "unreachable"
    ERROR = "error"
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"

class BaseSystemResponse(BaseModel):
    """Base model for all system API responses"""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {}}
    )
    
    schema_version: str = Field(
        default=SYSTEM_API_SCHEMA_VERSION,
        description="Schema version of the response"
    )
    
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when response was generated"
    )

# =============================================================================
# Root Info Models
# =============================================================================

class RootInfoResponse(BaseSystemResponse):
    """Response model for the API root endpoint"""
    application_name: str = Field(
        description="Name of the application"
    )
    version: str = Field(
        description="Version of the application"
    )
    status: str = Field(
        default="running",
        description="Current running status of the application"
    )
    server_start_time_utc: str = Field(
        description="Server start time in ISO format"
    )

# =============================================================================
# Health Check Models
# =============================================================================

class HealthCheckResponse(BaseSystemResponse):
    """Response model for the health check endpoint"""
    status: SystemHealthStatusEnum = Field(
        description="Overall health status of the system"
    )
    version: str = Field(
        description="Version of the application"
    )
    redis: ComponentStatusEnum = Field(
        description="Status of Redis connection"
    )
    event_bus: ComponentStatusEnum = Field(
        description="Status of the Event Bus"
    )
    uptime_seconds: float = Field(
        description="Server uptime in seconds"
    )
    current_time_utc: str = Field(
        description="Current time in ISO format"
    )
    error: Optional[str] = Field(
        default=None, 
        description="Error message if health check failed"
    )

# =============================================================================
# Cache Ping Models
# =============================================================================

class CachePingResponse(BaseSystemResponse):
    """Response model for the cache ping endpoint"""
    status: ComponentStatusEnum = Field(
        description="Status of Redis connection"
    )

# =============================================================================
# Event Bus Health Models
# =============================================================================

class CircuitBreakerStatus(BaseModel):
    """Status information for circuit breakers"""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {}}
    )
    
    state: str = Field(
        description="Current state of the circuit breaker (closed/open/half-open)"
    )
    failure_count: int = Field(
        description="Current failure count"
    )
    last_failure_time: Optional[str] = Field(
        default=None,
        description="Timestamp of the last failure"
    )
    reset_timeout: float = Field(
        description="Time in seconds until the circuit resets"
    )

class ChannelHealth(BaseModel):
    """Health information for individual channels"""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {}}
    )
    
    is_critical: bool = Field(
        description="Whether this channel is marked as critical"
    )
    messages_published: int = Field(
        description="Number of messages published to this channel"
    )
    messages_consumed: int = Field(
        description="Number of messages consumed from this channel"
    )
    circuit_breaker: Optional[CircuitBreakerStatus] = Field(
        default=None,
        description="Circuit breaker status if enabled"
    )

class EventBusHealthResponse(BaseSystemResponse):
    """Response model for the event bus health endpoint"""
    healthy: bool = Field(
        description="Overall health status of the event bus"
    )
    connection_active: bool = Field(
        description="Whether the connection to the transport is active"
    )
    transport_type: str = Field(
        description="Type of transport used by the event bus"
    )
    channels: Dict[str, ChannelHealth] = Field(
        default_factory=dict,
        description="Health information for individual channels"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Performance metrics for the event bus"
    )
    last_heartbeat: Optional[str] = Field(
        default=None,
        description="Timestamp of the last transport heartbeat"
    )
    details: Optional[str] = Field(
        default=None,
        description="Additional details about event bus health"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if health check failed"
    )

# =============================================================================
# System Status Models
# =============================================================================

class SystemStatusResponse(BaseSystemResponse):
    """Response model for the system status endpoint"""
    api: ComponentStatusEnum = Field(
        description="Status of the API service"
    )
    redis: ComponentStatusEnum = Field(
        description="Status of Redis connection"
    )
    event_bus: ComponentStatusEnum = Field(
        description="Status of the Event Bus"
    )
    lastBackup: str = Field(
        description="Timestamp of the last system backup"
    )
    cpu_usage: Optional[float] = Field(
        default=None,
        description="Current CPU usage percentage"
    )
    memory_usage: Optional[float] = Field(
        default=None,
        description="Current memory usage percentage"
    )

# =============================================================================
# Export model registry
# =============================================================================

SYSTEM_API_RESPONSE_MODELS = {
    "RootInfo": RootInfoResponse,
    "HealthCheck": HealthCheckResponse,
    "CachePing": CachePingResponse,
    "EventBusHealth": EventBusHealthResponse,
    "SystemStatus": SystemStatusResponse
}