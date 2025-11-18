# =============================================================================
# File: app/api/models/wse_api_models.py
# Description: Enhanced WebSocket event schema – 
# =============================================================================
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Literal as Lit

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_serializer

# ──────────────────────────────────────────────────────────────────────────────
# Shared ConfigDict – ONE place, ZERO warnings
# ──────────────────────────────────────────────────────────────────────────────
BASE_CFG = ConfigDict(
    populate_by_name=True,
    from_attributes=True,
    extra="ignore",
    json_encoders={
        datetime: lambda v: v.isoformat() if v else None
    }
)

DecimalStr = str  # semantic alias for pre-formatted decimals
WS_CLIENT_SCHEMA_VERSION = "0.3"
WS_PROTOCOL_VERSION = 2


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class MessagePriority(int, Enum):
    """Message priority levels matching useWSE.ts"""
    CRITICAL = 10
    HIGH = 8
    NORMAL = 5
    LOW = 3
    BACKGROUND = 1


class ConnectionHealth(str, Enum):
    """WebSocket connection health states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"
    DEGRADED = "degraded"


class ConnectionQuality(str, Enum):
    """Network connection quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


# ──────────────────────────────────────────────────────────────────────────────
# Base envelope with enhanced fields
# ──────────────────────────────────────────────────────────────────────────────
class WsBaseEvent(BaseModel):
    model_config = BASE_CFG

    # Core fields
    event_type: str = Field(..., alias="t", description="Event type identifier")
    payload: Any = Field(..., alias="p", description="Event payload")

    # Protocol fields
    version: int = Field(default=WS_PROTOCOL_VERSION, alias="v", description="Protocol version")
    sequence: Optional[int] = Field(None, alias="seq", description="Message sequence number")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="ts",
        description="ISO timestamp"
    )

    # Optional fields
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique message ID"
    )
    correlation_id: Optional[str] = Field(None, alias="cid", description="For request-response correlation")
    priority: Optional[int] = Field(None, alias="pri", description="Message priority")
    compressed: Optional[bool] = Field(None, alias="cmp", description="Whether payload is compressed")
    encrypted: Optional[bool] = Field(None, alias="enc", description="Whether payload is encrypted")

    @property
    def type(self) -> str:
        """Backward compatibility property"""
        return self.event_type


# ──────────────────────────────────────────────────────────────────────────────
# Enhanced payloads
# ──────────────────────────────────────────────────────────────────────────────
class WsMessagePayload(BaseModel):
    model_config = BASE_CFG
    message: str
    details: Optional[Dict[str, Any]] = None
    code: Optional[str] = None
    severity: Optional[str] = None


class WsEmptyPayload(BaseModel):
    model_config = BASE_CFG
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Connection & Protocol Events
# ──────────────────────────────────────────────────────────────────────────────
class WsServerReadyEvent(WsBaseEvent):
    event_type: Lit["server_ready"] = "server_ready"
    payload: WsMessagePayload


class WsClientHelloPayload(BaseModel):
    """Client hello message for protocol negotiation"""
    model_config = BASE_CFG
    client_version: str
    protocol_version: int = WS_PROTOCOL_VERSION
    features: Dict[str, bool] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)


class WsClientHelloEvent(WsBaseEvent):
    event_type: Lit["client_hello"] = "client_hello"
    payload: WsClientHelloPayload


class WsPingPayload(BaseModel):
    model_config = BASE_CFG
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    sequence: Optional[int] = None


class WsPingEvent(WsBaseEvent):
    event_type: Lit["ping"] = "ping"
    payload: WsPingPayload


class WsPongEvent(WsBaseEvent):
    event_type: Lit["PONG"] = "PONG"
    payload: WsEmptyPayload = Field(default_factory=WsEmptyPayload)
    client_ping_timestamp: Optional[int] = Field(None)
    server_timestamp: Optional[int] = Field(
        default_factory=lambda: int(datetime.now().timestamp() * 1000)
    )


class WsHeartbeatEvent(WsBaseEvent):
    event_type: Lit["heartbeat"] = "heartbeat"
    payload: WsEmptyPayload = Field(default_factory=WsEmptyPayload)


# ──────────────────────────────────────────────────────────────────────────────
# Enhanced Subscription Management
# ──────────────────────────────────────────────────────────────────────────────
class WsSubscriptionPayload(BaseModel):
    model_config = BASE_CFG
    action: Optional[Lit["subscribe", "unsubscribe"]] = None
    topics: List[str] = Field(default_factory=list)
    pending_subscriptions: Optional[List[str]] = None
    failed_subscriptions: Optional[List[str]] = None
    message: Optional[str] = None
    success: bool = True
    active_subscriptions: Optional[List[str]] = None
    subscription_limits: Optional[Dict[str, int]] = None


class WsSubscriptionEvent(WsBaseEvent):
    event_type: Lit["subscription_update"] = "subscription_update"
    payload: WsSubscriptionPayload


# ──────────────────────────────────────────────────────────────────────────────
# Sync & Snapshot Events
# ──────────────────────────────────────────────────────────────────────────────
class WsSyncRequestPayload(BaseModel):
    model_config = BASE_CFG
    topics: List[str]
    last_sequence: int = 0
    include_snapshots: bool = True
    snapshot_types: Optional[List[str]] = None


class WsSyncRequestEvent(WsBaseEvent):
    event_type: Lit["sync_request"] = "sync_request"
    payload: WsSyncRequestPayload


class WsSnapshotCompleteEvent(WsBaseEvent):
    event_type: Lit["snapshot_complete"] = "snapshot_complete"
    payload: WsMessagePayload


# ──────────────────────────────────────────────────────────────────────────────
# Connection Metrics & Diagnostics
# ──────────────────────────────────────────────────────────────────────────────
class WsConnectionMetrics(BaseModel):
    """Detailed connection metrics"""
    model_config = BASE_CFG

    # Message metrics
    messages_received: int = 0
    messages_sent: int = 0
    messages_queued: int = 0
    messages_dropped: int = 0

    # Compression metrics
    compression_ratio: float = 1.0
    compression_hits: int = 0

    # Connection metrics
    reconnect_count: int = 0
    connection_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0

    # Latency metrics
    last_latency: Optional[float] = None
    avg_latency: Optional[float] = None
    min_latency: Optional[float] = None
    max_latency: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None

    # Network metrics
    bytes_received: int = 0
    bytes_sent: int = 0
    bandwidth: float = 0.0  # bytes per second
    message_rate: float = 0.0  # messages per second

    # Timestamps
    connected_since: Optional[str] = None
    last_message_received: Optional[str] = None
    last_message_sent: Optional[str] = None
    last_health_check: Optional[str] = None

    # Error tracking
    last_error_code: Optional[int] = None
    last_error_message: Optional[str] = None
    auth_failures: int = 0
    protocol_errors: int = 0


class WsNetworkDiagnostics(BaseModel):
    """Network quality diagnostics"""
    model_config = BASE_CFG

    connection_quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    stability: float = Field(100.0, ge=0, le=100)
    network_jitter: float = Field(0.0, ge=0)
    packet_loss: float = Field(0.0, ge=0, le=100)
    round_trip_time: float = Field(0.0, ge=0)
    suggestions: List[str] = Field(default_factory=list)
    last_analysis: Optional[str] = None


class WsCircuitBreakerInfo(BaseModel):
    """Circuit breaker status"""
    model_config = BASE_CFG

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failures: int = 0
    last_failure_time: Optional[str] = None
    success_count: int = 0
    next_retry_time: Optional[str] = None
    threshold: int = 5
    timeout: int = 60000  # ms


class WsQueueStats(BaseModel):
    """Message queue statistics"""
    model_config = BASE_CFG

    size: int = 0
    capacity: int = 10000
    utilization_percent: float = 0.0
    oldest_message_age: Optional[float] = None
    priority_distribution: Dict[int, int] = Field(default_factory=dict)
    processing_rate: float = 0.0
    backpressure: bool = False


class WsSecurityInfo(BaseModel):
    """Security configuration info"""
    model_config = BASE_CFG

    encryption_enabled: bool = False
    encryption_algorithm: Optional[str] = None
    message_signing_enabled: bool = False
    session_key_rotation: Optional[int] = None
    last_key_rotation: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Health Check & Monitoring Events
# ──────────────────────────────────────────────────────────────────────────────
class WsHealthCheckPayload(BaseModel):
    model_config = BASE_CFG
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    server_time: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    diagnostics: Optional[WsNetworkDiagnostics] = None
    circuit_breaker: Optional[WsCircuitBreakerInfo] = None
    metrics: Optional[WsConnectionMetrics] = None


class WsHealthCheckEvent(WsBaseEvent):
    event_type: Lit["health_check"] = "health_check"
    payload: WsHealthCheckPayload


class WsHealthCheckRequestEvent(WsBaseEvent):
    event_type: Lit["health_check_request"] = "health_check_request"
    payload: WsEmptyPayload = Field(default_factory=WsEmptyPayload)


class WsHealthCheckResponsePayload(BaseModel):
    model_config = BASE_CFG
    timestamp: str
    server_time: int
    diagnostics: WsNetworkDiagnostics
    circuit_breaker: WsCircuitBreakerInfo
    client_version: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class WsHealthCheckResponseEvent(WsBaseEvent):
    event_type: Lit["health_check_response"] = "health_check_response"
    payload: WsHealthCheckResponsePayload


# ──────────────────────────────────────────────────────────────────────────────
# Metrics Events
# ──────────────────────────────────────────────────────────────────────────────
class WsMetricsRequestEvent(WsBaseEvent):
    event_type: Lit["metrics_request"] = "metrics_request"
    payload: WsEmptyPayload = Field(default_factory=WsEmptyPayload)


class WsMetricsResponsePayload(BaseModel):
    model_config = BASE_CFG
    connection_stats: WsConnectionMetrics
    subscriptions: List[str]
    event_bus_stats: Optional[Dict[str, Any]] = None
    server_time: str
    queue_stats: WsQueueStats
    circuit_breaker: WsCircuitBreakerInfo
    diagnostics: WsNetworkDiagnostics
    security: Optional[WsSecurityInfo] = None


class WsMetricsResponseEvent(WsBaseEvent):
    event_type: Lit["metrics_response"] = "metrics_response"
    payload: WsMetricsResponsePayload


# ──────────────────────────────────────────────────────────────────────────────
# Connection Quality & Optimization
# ──────────────────────────────────────────────────────────────────────────────
class WsConnectionQualityPayload(BaseModel):
    model_config = BASE_CFG
    quality: ConnectionQuality
    message: str
    suggestions: List[str] = Field(default_factory=list)
    metrics: Optional[WsConnectionMetrics] = None
    recommended_settings: Optional[Dict[str, Any]] = None


class WsConnectionQualityEvent(WsBaseEvent):
    event_type: Lit["connection_quality"] = "connection_quality"
    payload: WsConnectionQualityPayload


# ──────────────────────────────────────────────────────────────────────────────
# Rate Limiting
# ──────────────────────────────────────────────────────────────────────────────
class WsRateLimitWarningPayload(BaseModel):
    model_config = BASE_CFG
    message: str
    limit: int
    window: float  # seconds
    retry_after: float  # seconds
    current_usage: Optional[int] = None


class WsRateLimitWarningEvent(WsBaseEvent):
    event_type: Lit["rate_limit_warning"] = "rate_limit_warning"
    payload: WsRateLimitWarningPayload


# ──────────────────────────────────────────────────────────────────────────────
# Configuration Updates
# ──────────────────────────────────────────────────────────────────────────────
class WsConfigUpdatePayload(BaseModel):
    model_config = BASE_CFG
    compression_enabled: Optional[bool] = None
    encryption_enabled: Optional[bool] = None
    batching_enabled: Optional[bool] = None
    max_queue_size: Optional[int] = None
    heartbeat_interval: Optional[int] = None
    idle_timeout: Optional[int] = None


class WsConfigUpdateEvent(WsBaseEvent):
    event_type: Lit["config_update"] = "config_update"
    payload: WsConfigUpdatePayload


# ──────────────────────────────────────────────────────────────────────────────
# Priority Messages
# ──────────────────────────────────────────────────────────────────────────────
class WsPriorityMessagePayload(BaseModel):
    model_config = BASE_CFG
    content: Any
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: Optional[int] = None  # time to live in seconds


class WsPriorityMessageEvent(WsBaseEvent):
    event_type: Lit["priority_message"] = "priority_message"
    payload: WsPriorityMessagePayload
    priority: int = Field(default=MessagePriority.NORMAL.value)


# ──────────────────────────────────────────────────────────────────────────────
# Enhanced Connection Statistics
# ──────────────────────────────────────────────────────────────────────────────
class WsConnectionStatsPayload(BaseModel):
    model_config = BASE_CFG
    connected_since: Optional[int] = None  # Unix timestamp in milliseconds
    messages_sent: int = 0
    messages_received: int = 0
    last_latency_ms: Optional[int] = None
    avg_latency_ms: Optional[float] = None
    min_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None
    client_ip: Optional[str] = None
    server_id: Optional[str] = None
    reconnect_count: int = 0
    subscriptions_count: int = 0
    bandwidth_bytes_sent: Optional[int] = None
    bandwidth_bytes_received: Optional[int] = None
    compression_ratio: Optional[float] = None
    queue_utilization: Optional[float] = None
    circuit_breaker_state: Optional[str] = None


class WsConnectionStatsEvent(WsBaseEvent):
    event_type: Lit["connection_stats"] = "connection_stats"
    payload: WsConnectionStatsPayload


# ──────────────────────────────────────────────────────────────────────────────
# Reconnection Support
# ──────────────────────────────────────────────────────────────────────────────
class WsReconnectPayload(BaseModel):
    model_config = BASE_CFG
    reason: str
    reconnect_delay_ms: int = 1000
    reconnect_attempt_max: int = -1  # -1 for infinite
    last_message_id: Optional[str] = None
    last_sequence: Optional[int] = None
    suggested_endpoint: Optional[str] = None


class WsReconnectInfoEvent(WsBaseEvent):
    event_type: Lit["reconnect_info"] = "reconnect_info"
    payload: WsReconnectPayload


# ──────────────────────────────────────────────────────────────────────────────
# Error handling with severity levels
# ──────────────────────────────────────────────────────────────────────────────
class WsErrorPayload(BaseModel):
    model_config = BASE_CFG
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    severity: Lit["warning", "error", "critical"] = "error"
    recoverable: bool = True
    retry_after: Optional[int] = None  # seconds
    suggested_action: Optional[str] = None


class WsErrorEvent(WsBaseEvent):
    event_type: Lit["error"] = "error"
    payload: WsErrorPayload


# ──────────────────────────────────────────────────────────────────────────────
# Broker Connection Events (keeping existing)
# ──────────────────────────────────────────────────────────────────────────────
from app.infra.broker_adapters.common.adapter_enums import BrokerConnectionStatusEnum, MarketStatusEnum
# from app.broker_connection.read_models import BrokerConnectionReadModel


class WsBrokerModuleInfo(BaseModel):
    """Information about a specific module in a modular adapter"""
    model_config = BASE_CFG

    module_id: str
    module_type: str
    is_healthy: bool
    status: str = "unknown"
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    last_checked: Optional[str] = None  # Changed from datetime to str

    @field_serializer('last_checked')
    def serialize_last_checked(self, dt: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime to ISO format string"""
        return dt.isoformat() if dt else None


class WsBrokerConnectionInfo(BaseModel):
    model_config = BASE_CFG

    broker_connection_id: str
    broker_id: str
    environment: Lit["paper", "live"]
    status: BrokerConnectionStatusEnum
    market_status: Optional[MarketStatusEnum] = None
    reauth_required: bool = False
    message: Optional[str] = None
    last_connected_at: Optional[str] = None  # Changed from datetime to str
    last_heartbeat_at: Optional[str] = None  # Changed from datetime to str
    api_endpoint: Optional[str] = None
    connection_instance_id: Optional[str] = None
    adapter_type: Optional[str] = None
    modules: Optional[Dict[str, WsBrokerModuleInfo]] = None
    supported_assets: Optional[List[str]] = None
    adapter_version: Optional[str] = None

    @classmethod
    def from_read_model(cls, rm: BrokerConnectionReadModel,
                        module_health: Optional[Dict[str, Dict[str, Any]]] = None) -> "WsBrokerConnectionInfo":
        modules = None
        if module_health:
            modules = {
                module_id: WsBrokerModuleInfo(
                    module_id=module_id,
                    module_type=health_info.get("type", "unknown"),
                    is_healthy=health_info.get("is_healthy", False),
                    status=health_info.get("status", "unknown"),
                    message=health_info.get("message"),
                    details=health_info.get("details"),
                    capabilities=health_info.get("capabilities"),
                    last_checked=health_info.get("last_checked").isoformat() if isinstance(health_info.get("last_checked"), datetime) else health_info.get("last_checked")
                )
                for module_id, health_info in module_health.items()
            }

        # Convert datetime fields to ISO strings
        last_connected = None
        if hasattr(rm, 'last_connected_at') and rm.last_connected_at:
            last_connected = rm.last_connected_at.isoformat() if isinstance(rm.last_connected_at, datetime) else str(rm.last_connected_at)

        last_heartbeat = None
        if hasattr(rm, 'last_heartbeat_at') and rm.last_heartbeat_at:
            last_heartbeat = rm.last_heartbeat_at.isoformat() if isinstance(rm.last_heartbeat_at, datetime) else str(rm.last_heartbeat_at)

        return cls(
            broker_connection_id=str(rm.id),
            broker_id=rm.broker_id,
            environment=rm.environment.value if isinstance(rm.environment, Enum) else str(rm.environment).lower(),
            status=rm.last_connection_status,
            reauth_required=rm.reauth_required,
            message=rm.last_status_reason,
            last_connected_at=last_connected,
            last_heartbeat_at=last_heartbeat,
            api_endpoint=rm.api_endpoint,
            connection_instance_id=str(rm.connection_instance_id) if rm.connection_instance_id else None,
            modules=modules
        )

    @model_validator(mode="after")
    def _validate_env(self) -> "WsBrokerConnectionInfo":
        if self.environment not in {"paper", "live"}:
            raise ValueError("environment must be 'paper' or 'live'")
        return self


class WsBrokerStatusSnapshotPayload(BaseModel):
    model_config = BASE_CFG
    connections: List[WsBrokerConnectionInfo]
    trim_archived: bool = False
    include_module_details: bool = False


class WsBrokerStatusSnapshotEvent(WsBaseEvent):
    event_type: Lit["broker_connection_snapshot"] = "broker_connection_snapshot"
    payload: WsBrokerStatusSnapshotPayload


class WsBrokerStatusUpdateEvent(WsBaseEvent):
    event_type: Lit["broker_status_update"] = "broker_status_update"
    payload: WsBrokerConnectionInfo


class WsBrokerRemoveEvent(WsBaseEvent):
    event_type: Lit["broker_status_remove"] = "broker_status_remove"
    payload: WsBrokerConnectionInfo


class WsBrokerModuleHealthUpdatePayload(BaseModel):
    model_config = BASE_CFG
    broker_connection_id: str
    module_updates: Dict[str, WsBrokerModuleInfo]


class WsBrokerModuleHealthUpdateEvent(WsBaseEvent):
    event_type: Lit["broker_module_health_update"] = "broker_module_health_update"
    payload: WsBrokerModuleHealthUpdatePayload


# ──────────────────────────────────────────────────────────────────────────────
# Account Events (keeping existing)
# ──────────────────────────────────────────────────────────────────────────────
# from app.broker_account.read_models import BrokerAccountReadModel
from app.infra.broker_adapters.common.adapter_enums import AssetTypeEnum


class WsPositionInfo(BaseModel):
    """Real-time position information"""
    model_config = BASE_CFG

    symbol: str
    quantity: DecimalStr
    side: str
    market_value: Optional[DecimalStr] = None
    avg_cost: Optional[DecimalStr] = None
    unrealized_pnl: Optional[DecimalStr] = None
    unrealized_pnl_percent: Optional[DecimalStr] = None
    asset_class: Optional[str] = None


class WsAccountInfo(BaseModel):
    """
    WebSocket account information model.
    Note: 'id' field represents the internal account UUID.
    Frontend expects this as 'accountId' in camelCase.
    """
    model_config = BASE_CFG

    id: str  # Internal account UUID (maps to 'accountId' in frontend)
    broker_connection_id: Optional[str] = None
    broker_id: str
    environment: Lit["paper", "live"]
    asset_type: AssetTypeEnum
    broker_account_id: str  # External broker account ID (maps to 'brokerAccountId' in frontend)
    account_name: Optional[str] = None
    balance: DecimalStr
    currency: str
    equity: Optional[DecimalStr] = None
    buying_power: Optional[DecimalStr] = None
    status: Optional[str] = None
    account_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    deleted: bool = False
    archived: Optional[bool] = False
    last_synced_at: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    positions: Optional[List[WsPositionInfo]] = None
    open_orders_count: Optional[int] = None
    daily_pnl: Optional[DecimalStr] = None
    daily_pnl_percent: Optional[DecimalStr] = None

    @classmethod
    def from_read_model(cls, rm: BrokerAccountReadModel,
                        positions: Optional[List[Dict[str, Any]]] = None) -> "WsAccountInfo":
        position_list = None
        if positions:
            position_list = [
                WsPositionInfo(
                    symbol=pos.get("symbol", ""),
                    quantity=str(pos.get("quantity", 0)),
                    side=pos.get("side", "long"),
                    market_value=str(pos.get("market_value", 0)) if pos.get("market_value") else None,
                    avg_cost=str(pos.get("avg_cost", 0)) if pos.get("avg_cost") else None,
                    unrealized_pnl=str(pos.get("unrealized_pnl", 0)) if pos.get("unrealized_pnl") else None,
                    unrealized_pnl_percent=str(pos.get("unrealized_pnl_percent", 0)) if pos.get(
                        "unrealized_pnl_percent") else None,
                    asset_class=pos.get("asset_class")
                )
                for pos in positions
            ]

        # Convert datetime fields to ISO strings
        created = rm.created_at.isoformat() if isinstance(rm.created_at, datetime) else str(rm.created_at)
        updated = None
        if rm.updated_at:
            updated = rm.updated_at.isoformat() if isinstance(rm.updated_at, datetime) else str(rm.updated_at)
        last_synced = None
        if hasattr(rm, 'last_synced_at') and rm.last_synced_at:
            last_synced = rm.last_synced_at.isoformat() if isinstance(rm.last_synced_at, datetime) else str(rm.last_synced_at)

        return cls(
            id=str(rm.id),  # Internal UUID
            broker_connection_id=str(rm.broker_connection_id) if rm.broker_connection_id else None,
            broker_id=rm.broker_id,
            environment=rm.environment.value if isinstance(rm.environment, Enum) else str(rm.environment).lower(),
            asset_type=rm.asset_type,
            broker_account_id=rm.broker_account_id,  # External broker account ID (FIXED: was rm.account_id)
            account_name=rm.account_name,
            balance=f"{rm.balance:.2f}",
            currency=rm.currency,
            equity=f"{rm.equity:.2f}" if rm.equity is not None else None,
            buying_power=f"{rm.buying_power:.2f}" if rm.buying_power is not None else None,
            status=rm.status,
            account_type=rm.account_type,
            metadata=rm.metadata,
            deleted=rm.deleted,
            archived=bool(rm.archived),
            last_synced_at=last_synced,
            created_at=created,
            updated_at=updated,
            positions=position_list
        )


class WsAccountSnapshotPayload(BaseModel):
    model_config = BASE_CFG
    accounts: List[WsAccountInfo]
    include_positions: bool = False
    count: Optional[int] = Field(None, description="Number of accounts in snapshot")

    @model_validator(mode="after")
    def set_count(self) -> "WsAccountSnapshotPayload":
        """Automatically set count based on accounts list"""
        if self.count is None and self.accounts:
            self.count = len(self.accounts)
        return self


class WsAccountSnapshotEvent(WsBaseEvent):
    event_type: Lit["broker_account_snapshot"] = "broker_account_snapshot"
    payload: WsAccountSnapshotPayload


class WsAccountUpdateEvent(WsBaseEvent):
    event_type: Lit["account_update"] = "account_update"
    payload: WsAccountInfo


# ──────────────────────────────────────────────────────────────────────────────
# Market Data Events
# ──────────────────────────────────────────────────────────────────────────────
class WsQuoteData(BaseModel):
    model_config = BASE_CFG

    symbol: str
    bid: Optional[DecimalStr] = None
    ask: Optional[DecimalStr] = None
    last: Optional[DecimalStr] = None
    volume: Optional[int] = None
    timestamp: Optional[int] = None
    exchange: Optional[str] = None


class WsMarketDataUpdatePayload(BaseModel):
    model_config = BASE_CFG
    quotes: List[WsQuoteData]
    source: Optional[str] = None


class WsMarketDataUpdateEvent(WsBaseEvent):
    event_type: Lit["market_data_update"] = "market_data_update"
    payload: WsMarketDataUpdatePayload


# ──────────────────────────────────────────────────────────────────────────────
# Trading Events
# ──────────────────────────────────────────────────────────────────────────────
class WsOrderUpdate(BaseModel):
    model_config = BASE_CFG

    order_id: str
    client_order_id: Optional[str] = None
    account_id: str
    symbol: str
    side: str
    quantity: DecimalStr
    order_type: str
    status: str
    filled_quantity: Optional[DecimalStr] = None
    avg_fill_price: Optional[DecimalStr] = None
    limit_price: Optional[DecimalStr] = None
    stop_price: Optional[DecimalStr] = None
    time_in_force: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime to ISO format string"""
        if dt is None:
            return None
        return dt.isoformat() if isinstance(dt, datetime) else str(dt)


class WsOrderUpdateEvent(WsBaseEvent):
    event_type: Lit["order_update"] = "order_update"
    payload: WsOrderUpdate


class WsPositionUpdateEvent(WsBaseEvent):
    event_type: Lit["position_update"] = "position_update"
    payload: WsPositionInfo


# ──────────────────────────────────────────────────────────────────────────────
# System Status
# ──────────────────────────────────────────────────────────────────────────────
class WsSystemStatusPayload(BaseModel):
    model_config = BASE_CFG
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    api_status: Optional[str] = None
    datafeed_status: Optional[str] = None
    active_connections: Optional[int] = None
    event_queue_size: Optional[int] = None
    adapter_statuses: Optional[Dict[str, str]] = None
    module_statuses: Optional[Dict[str, Dict[str, str]]] = None
    event_bus_health: Optional[Dict[str, Any]] = None
    circuit_breakers: Optional[Dict[str, str]] = None


class WsSystemStatusEvent(WsBaseEvent):
    event_type: Lit["system_status"] = "system_status"
    payload: WsSystemStatusPayload


# ──────────────────────────────────────────────────────────────────────────────
# OAuth Flow Events
# ──────────────────────────────────────────────────────────────────────────────
class WsOAuthStatusPayload(BaseModel):
    model_config = BASE_CFG
    broker_id: str
    status: str
    message: Optional[str] = None
    authorization_url: Optional[str] = None
    expires_at: Optional[str] = None

    @field_serializer('expires_at')
    def serialize_expires_at(self, dt: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime to ISO format string"""
        return dt.isoformat() if dt else None


class WsOAuthStatusEvent(WsBaseEvent):
    event_type: Lit["oauth_status"] = "oauth_status"
    payload: WsOAuthStatusPayload


# ──────────────────────────────────────────────────────────────────────────────
# Enhanced Event Registry
# ──────────────────────────────────────────────────────────────────────────────
WS_EVENT_TYPE_TO_MODEL: Dict[str, Type[WsBaseEvent]] = {
    # Core events
    "server_ready": WsServerReadyEvent,
    "client_hello": WsClientHelloEvent,
    "ping": WsPingEvent,
    "PONG": WsPongEvent,
    "heartbeat": WsHeartbeatEvent,

    # Sync & snapshots
    "sync_request": WsSyncRequestEvent,
    "snapshot_complete": WsSnapshotCompleteEvent,

    # Connection management
    "subscription_update": WsSubscriptionEvent,
    "reconnect_info": WsReconnectInfoEvent,
    "error": WsErrorEvent,

    # Monitoring
    "health_check": WsHealthCheckEvent,
    "health_check_request": WsHealthCheckRequestEvent,
    "health_check_response": WsHealthCheckResponseEvent,
    "metrics_request": WsMetricsRequestEvent,
    "metrics_response": WsMetricsResponseEvent,
    "connection_quality": WsConnectionQualityEvent,
    "connection_stats": WsConnectionStatsEvent,

    # Configuration
    "config_update": WsConfigUpdateEvent,
    "rate_limit_warning": WsRateLimitWarningEvent,
    "priority_message": WsPriorityMessageEvent,

    # Broker events
    "broker_connection_snapshot": WsBrokerStatusSnapshotEvent,
    "broker_status_update": WsBrokerStatusUpdateEvent,
    "broker_connection_update": WsBrokerStatusUpdateEvent,  # Alias
    "broker_status_remove": WsBrokerRemoveEvent,
    "broker_module_health_update": WsBrokerModuleHealthUpdateEvent,

    # Account events
    "broker_account_snapshot": WsAccountSnapshotEvent,
    "account_update": WsAccountUpdateEvent,

    # Market data
    "market_data_update": WsMarketDataUpdateEvent,

    # Trading
    "order_update": WsOrderUpdateEvent,
    "position_update": WsPositionUpdateEvent,

    # System
    "system_status": WsSystemStatusEvent,

    # OAuth
    "oauth_status": WsOAuthStatusEvent,
}


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def create_ws_event(
        event_type: str,
        payload: Any,
        priority: Optional[int] = None,
        compressed: Optional[bool] = None,
        encrypted: Optional[bool] = None,
        correlation_id: Optional[str] = None,
        sequence: Optional[int] = None,
        **kwargs
) -> WsBaseEvent:
    """Create a WebSocket event with proper type handling"""
    event_class = WS_EVENT_TYPE_TO_MODEL.get(event_type)
    if not event_class:
        raise ValueError(f"Unknown event type: {event_type}")

    # Build the event data
    event_data = {
        "event_type": event_type,
        "payload": payload,
    }

    # Add optional fields if provided
    if priority is not None:
        event_data["priority"] = priority
    if compressed is not None:
        event_data["compressed"] = compressed
    if encrypted is not None:
        event_data["encrypted"] = encrypted
    if correlation_id is not None:
        event_data["correlation_id"] = correlation_id
    if sequence is not None:
        event_data["sequence"] = sequence

    # Add any additional kwargs
    event_data.update(kwargs)

    return event_class(**event_data)


async def transform_event_for_ws(event: Dict[str, Any]) -> Dict[str, Any]:
    """Transform internal events to WebSocket format"""
    # Ensure event_type is present
    if 'type' in event and 'event_type' not in event:
        event['event_type'] = event['type']

    # Convert to short format
    transformed = {
        't': event.get('event_type', event.get('type')),
        'p': event.get('payload', event),
        'v': event.get('version', WS_PROTOCOL_VERSION),
        'ts': event.get('timestamp', datetime.now(timezone.utc).isoformat()),
    }

    # Add optional fields
    if 'id' in event:
        transformed['id'] = event['id']
    if 'sequence' in event:
        transformed['seq'] = event['sequence']
    if 'priority' in event:
        transformed['pri'] = event['priority']
    if 'correlation_id' in event:
        transformed['cid'] = event['correlation_id']

    return transformed


def parse_ws_message(message: Dict[str, Any]) -> WsBaseEvent:
    """Parse a WebSocket message into the appropriate event model"""
    # Handle both long and short format
    event_type = message.get('t', message.get('type', message.get('event_type')))
    payload = message.get('p', message.get('payload', {}))

    # Get the appropriate model
    event_class = WS_EVENT_TYPE_TO_MODEL.get(event_type, WsBaseEvent)

    # Create the event
    return event_class(
        event_type=event_type,
        payload=payload,
        version=message.get('v', message.get('version', WS_PROTOCOL_VERSION)),
        sequence=message.get('seq', message.get('sequence')),
        timestamp=message.get('ts', message.get('timestamp', datetime.now(timezone.utc).isoformat())),
        id=message.get('id'),
        correlation_id=message.get('cid', message.get('correlation_id')),
        priority=message.get('pri', message.get('priority')),
        compressed=message.get('cmp', message.get('compressed')),
        encrypted=message.get('enc', message.get('encrypted')),
    )


# Force model rebuilding to resolve forward references
for model in WS_EVENT_TYPE_TO_MODEL.values():
    if hasattr(model, "model_rebuild"):
        model.model_rebuild(force=True)

# ──────────────────────────────────────────────────────────────────────────────
# Re-exports
# ──────────────────────────────────────────────────────────────────────────────
__all__ = [
    # Base
    "WsBaseEvent",

    # Enums
    "MessagePriority",
    "ConnectionHealth",
    "ConnectionQuality",
    "CircuitBreakerState",

    # Core Events
    "WsServerReadyEvent",
    "WsClientHelloEvent",
    "WsPingEvent",
    "WsPongEvent",
    "WsHeartbeatEvent",

    # Sync & Subscription
    "WsSyncRequestEvent",
    "WsSnapshotCompleteEvent",
    "WsSubscriptionEvent",

    # Monitoring & Metrics
    "WsHealthCheckEvent",
    "WsHealthCheckRequestEvent",
    "WsHealthCheckResponseEvent",
    "WsMetricsRequestEvent",
    "WsMetricsResponseEvent",
    "WsConnectionQualityEvent",
    "WsConnectionStatsEvent",

    # Configuration & Control
    "WsConfigUpdateEvent",
    "WsRateLimitWarningEvent",
    "WsPriorityMessageEvent",

    # Connection Management
    "WsReconnectInfoEvent",
    "WsErrorEvent",

    # Broker Events
    "WsBrokerStatusSnapshotEvent",
    "WsBrokerStatusUpdateEvent",
    "WsBrokerRemoveEvent",
    "WsBrokerModuleHealthUpdateEvent",

    # Account Events
    "WsAccountSnapshotEvent",
    "WsAccountUpdateEvent",

    # Trading Events
    "WsOrderUpdateEvent",
    "WsPositionUpdateEvent",

    # Market Data
    "WsMarketDataUpdateEvent",

    # System
    "WsSystemStatusEvent",

    # OAuth
    "WsOAuthStatusEvent",

    # Models
    "WsConnectionMetrics",
    "WsNetworkDiagnostics",
    "WsCircuitBreakerInfo",
    "WsQueueStats",
    "WsSecurityInfo",
    "WsBrokerModuleInfo",
    "WsBrokerConnectionInfo",
    "WsPositionInfo",
    "WsAccountInfo",
    "WsQuoteData",
    "WsOrderUpdate",

    # Payloads
    "WsAccountSnapshotPayload",
    "WsBrokerStatusSnapshotPayload",

    # Helpers
    "WS_EVENT_TYPE_TO_MODEL",
    "create_ws_event",
    "transform_event_for_ws",
    "parse_ws_message",

    # Constants
    "WS_PROTOCOL_VERSION",
    "WS_CLIENT_SCHEMA_VERSION",
]