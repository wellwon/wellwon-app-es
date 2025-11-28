# =============================================================================
# File: app/infra/saga/saga_events.py
# Description: Saga-related event models
#              Consolidated saga lifecycle, monitoring, and integration events
# =============================================================================

from typing import Optional, Dict, Any, List, Literal

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_decorators import saga_event
from pydantic import Field


# =============================================================================
# Core Saga Lifecycle Events
# =============================================================================

@saga_event()
class SagaStarted(BaseEvent):
    """Raised when a saga is started"""
    event_type: Literal["SagaStarted"] = "SagaStarted"
    saga_id: str
    saga_type: str
    initial_context: Dict[str, Any]
    timeout_minutes: int
    timestamp: str


@saga_event()
class SagaStepStarted(BaseEvent):
    """Raised when a saga step begins execution"""
    event_type: Literal["SagaStepStarted"] = "SagaStepStarted"
    saga_id: str
    saga_type: str
    step_name: str
    step_number: int
    total_steps: int
    timestamp: str


@saga_event()
class SagaStepCompleted(BaseEvent):
    """Raised when a saga step completes successfully"""
    event_type: Literal["SagaStepCompleted"] = "SagaStepCompleted"
    saga_id: str
    saga_type: str
    step_name: str
    step_number: int
    step_result: Optional[Dict[str, Any]] = None
    duration_ms: int
    timestamp: str


@saga_event()
class SagaStepFailed(BaseEvent):
    """Raised when a saga step fails"""
    event_type: Literal["SagaStepFailed"] = "SagaStepFailed"
    saga_id: str
    saga_type: str
    step_name: str
    step_number: int
    error_type: str
    error_message: str
    retry_count: int
    will_retry: bool
    timestamp: str


@saga_event()
class SagaCompleted(BaseEvent):
    """Raised when a saga completes all steps successfully"""
    event_type: Literal["SagaCompleted"] = "SagaCompleted"
    saga_id: str
    saga_type: str
    final_context: Dict[str, Any]
    total_duration_ms: int
    steps_executed: int
    timestamp: str


@saga_event()
class SagaCompensationStarted(BaseEvent):
    """Raised when saga compensation begins"""
    event_type: Literal["SagaCompensationStarted"] = "SagaCompensationStarted"
    saga_id: str
    saga_type: str
    failed_step: str
    compensation_reason: str
    timestamp: str


@saga_event()
class SagaCompensationCompleted(BaseEvent):
    """Raised when saga compensation completes"""
    event_type: Literal["SagaCompensationCompleted"] = "SagaCompensationCompleted"
    saga_id: str
    saga_type: str
    compensated_steps: List[str]
    compensation_duration_ms: int
    timestamp: str


@saga_event()
class SagaFailed(BaseEvent):
    """Raised when a saga fails and cannot be compensated"""
    event_type: Literal["SagaFailed"] = "SagaFailed"
    saga_id: str
    saga_type: str
    failure_reason: str
    failed_step: Optional[str] = None
    requires_manual_intervention: bool
    timestamp: str


@saga_event()
class SagaTimedOut(BaseEvent):
    """Raised when a saga exceeds its timeout"""
    event_type: Literal["SagaTimedOut"] = "SagaTimedOut"
    saga_id: str
    saga_type: str
    timeout_minutes: int
    last_completed_step: Optional[str] = None
    timestamp: str


@saga_event()
class SagaRetrying(BaseEvent):
    """Raised when a saga step is being retried"""
    event_type: Literal["SagaRetrying"] = "SagaRetrying"
    saga_id: str
    saga_type: str
    step_name: str
    retry_attempt: int
    max_retries: int
    retry_delay_seconds: int
    timestamp: str


# =============================================================================
# Saga Monitoring Events
# =============================================================================

@saga_event()
class SagaTriggered(BaseEvent):
    """Published when a saga is triggered by an event"""
    event_type: Literal["SagaTriggered"] = "SagaTriggered"
    saga_id: str = Field(..., description="Unique identifier for the saga instance")
    saga_type: str = Field(..., description="Type/class name of the saga")
    trigger_event_type: str = Field(..., description="Event type that triggered the saga")
    trigger_event_id: str = Field(..., description="ID of the event that triggered the saga")
    description: str = Field(..., description="Human-readable description of the saga trigger")
    instance_id: str = Field(..., description="Saga service instance ID")
    version: int = Field(default=1, description="Event schema version")


@saga_event()
class SagaMetricsUpdated(BaseEvent):
    """Raised periodically with saga execution metrics"""
    event_type: Literal["SagaMetricsUpdated"] = "SagaMetricsUpdated"
    total_active_sagas: int
    sagas_by_type: Dict[str, int]
    success_rate: float
    average_duration_ms: float
    failed_sagas_count: int
    timestamp: str


@saga_event()
class SagaHealthCheck(BaseEvent):
    """Raised for saga manager health checks"""
    event_type: Literal["SagaHealthCheck"] = "SagaHealthCheck"
    manager_instance: str
    is_healthy: bool
    active_saga_count: int
    pending_saga_count: int
    error_count: int
    timestamp: str


# =============================================================================
# Specific Saga Completion Events
# =============================================================================

@saga_event()
class UserDeletionCompleted(BaseEvent):
    """Raised when user deletion saga completes"""
    event_type: Literal["UserDeletionCompleted"] = "UserDeletionCompleted"
    saga_id: str
    user_id: str
    deletion_summary: Dict[str, Any]
    timestamp: str


@saga_event()
class BrokerDisconnectionCompleted(BaseEvent):
    """Raised when broker disconnection saga completes"""
    event_type: Literal["BrokerDisconnectionCompleted"] = "BrokerDisconnectionCompleted"
    saga_id: str
    broker_connection_id: str
    user_id: str
    disconnection_summary: Dict[str, Any]
    timestamp: str


@saga_event()
class BrokerConnectionEstablishedSagaCompleted(BaseEvent):
    """Raised when broker connection establishment saga completes"""
    event_type: Literal["BrokerConnectionEstablishedSagaCompleted"] = "BrokerConnectionEstablishedSagaCompleted"
    saga_id: str
    broker_connection_id: str
    user_id: str
    connection_summary: Dict[str, Any]
    timestamp: str


@saga_event()
class AccountRefreshCompleted(BaseEvent):
    """Raised when account refresh saga completes"""
    event_type: Literal["AccountRefreshCompleted"] = "AccountRefreshCompleted"
    saga_id: str
    account_id: str
    user_id: str
    refresh_summary: Dict[str, Any]
    timestamp: str


@saga_event()
class OrderFulfillmentCompleted(BaseEvent):
    """Raised when order fulfillment saga completes"""
    event_type: Literal["OrderFulfillmentCompleted"] = "OrderFulfillmentCompleted"
    saga_id: str
    order_id: str
    user_id: str
    fulfillment_summary: Dict[str, Any]
    timestamp: str


@saga_event()
class CompanyCreationSagaCompleted(BaseEvent):
    """Raised when company creation saga completes successfully"""
    event_type: Literal["CompanyCreationSagaCompleted"] = "CompanyCreationSagaCompleted"
    saga_id: str
    company_id: str
    company_name: str
    telegram_group_id: Optional[int] = None
    telegram_invite_link: Optional[str] = None
    chat_id: Optional[str] = None
    chat_linked: bool = False  # True if existing chat was linked, False if new chat created
    created_by: str
    timestamp: str


@saga_event()
class CompanyCreationSagaFailed(BaseEvent):
    """Raised when company creation saga fails"""
    event_type: Literal["CompanyCreationSagaFailed"] = "CompanyCreationSagaFailed"
    saga_id: str
    company_id: str
    failure_reason: str
    failed_step: str
    requires_manual_intervention: bool = False
    timestamp: str


# =============================================================================
# Saga Compensation Events
# =============================================================================

@saga_event()
class SagaCompensationStepStarted(BaseEvent):
    """Raised when a specific compensation step starts"""
    event_type: Literal["SagaCompensationStepStarted"] = "SagaCompensationStepStarted"
    saga_id: str
    saga_type: str
    step_name: str
    compensation_reason: str
    timestamp: str


@saga_event()
class SagaCompensationStepCompleted(BaseEvent):
    """Raised when a specific compensation step completes"""
    event_type: Literal["SagaCompensationStepCompleted"] = "SagaCompensationStepCompleted"
    saga_id: str
    saga_type: str
    step_name: str
    compensation_result: Optional[Dict[str, Any]] = None
    timestamp: str


@saga_event()
class SagaCompensationStepFailed(BaseEvent):
    """Raised when a compensation step fails"""
    event_type: Literal["SagaCompensationStepFailed"] = "SagaCompensationStepFailed"
    saga_id: str
    saga_type: str
    step_name: str
    error_message: str
    requires_manual_intervention: bool
    timestamp: str


@saga_event()
class SagaManualInterventionRequired(BaseEvent):
    """Raised when saga requires manual intervention"""
    event_type: Literal["SagaManualInterventionRequired"] = "SagaManualInterventionRequired"
    saga_id: str
    saga_type: str
    intervention_reason: str
    failed_step: Optional[str] = None
    suggested_actions: List[str]
    timestamp: str


# =============================================================================
# Account Operation Events
# =============================================================================

@saga_event()
class AccountDiscoveryFailed(BaseEvent):
    """Raised when account discovery fails"""
    event_type: Literal["AccountDiscoveryFailed"] = "AccountDiscoveryFailed"
    saga_id: Optional[str] = None
    broker_connection_id: str
    error_message: str
    timestamp: str


# =============================================================================
# Broker Connection Events
# =============================================================================

@saga_event()
class BrokerConnectionReady(BaseEvent):
    """Raised when broker connection is fully ready"""
    event_type: Literal["BrokerConnectionReady"] = "BrokerConnectionReady"
    saga_id: Optional[str] = None
    broker_connection_id: str
    user_id: str
    connection_details: Dict[str, Any]
    timestamp: str


@saga_event()
class BrokerConnectionHealthCheckCompleted(BaseEvent):
    """Raised when connection health check completes"""
    event_type: Literal["BrokerConnectionHealthCheckCompleted"] = "BrokerConnectionHealthCheckCompleted"
    saga_id: Optional[str] = None
    broker_connection_id: str
    is_healthy: bool
    health_details: Dict[str, Any]
    timestamp: str


@saga_event()
class BrokerConnectionEstablishmentCompleted(BaseEvent):
    """Raised when connection establishment completes"""
    event_type: Literal["BrokerConnectionEstablishmentCompleted"] = "BrokerConnectionEstablishmentCompleted"
    saga_id: Optional[str] = None
    broker_connection_id: str
    success: bool
    details: Dict[str, Any]
    timestamp: str


@saga_event()
class BrokerConnectionValidationCompleted(BaseEvent):
    """Raised when connection validation completes"""
    event_type: Literal["BrokerConnectionValidationCompleted"] = "BrokerConnectionValidationCompleted"
    saga_id: Optional[str] = None
    broker_connection_id: str
    is_valid: bool
    validation_details: Dict[str, Any]
    timestamp: str


# =============================================================================
# Saga Compensation Required Events
# =============================================================================

@saga_event()
class BrokerDisconnectionCompensationRequired(BaseEvent):
    """Raised when broker disconnection needs compensation"""
    event_type: Literal["BrokerDisconnectionCompensationRequired"] = "BrokerDisconnectionCompensationRequired"
    saga_id: str
    broker_connection_id: str
    user_id: str
    step: str
    timestamp: str


@saga_event()
class UserDeletionCompensationRequired(BaseEvent):
    """Raised when user deletion needs compensation"""
    event_type: Literal["UserDeletionCompensationRequired"] = "UserDeletionCompensationRequired"
    saga_id: str
    user_id: str
    step: str
    reason: str
    timestamp: str


@saga_event()
class AccountRefreshCompensationRequired(BaseEvent):
    """Raised when account refresh needs compensation"""
    event_type: Literal["AccountRefreshCompensationRequired"] = "AccountRefreshCompensationRequired"
    saga_id: str
    account_id: str
    reason: str
    timestamp: str


@saga_event()
class BrokerAccountDiscoveryFailed(BaseEvent):
    """Raised when account discovery fails and needs compensation"""
    event_type: Literal["BrokerAccountDiscoveryFailed"] = "BrokerAccountDiscoveryFailed"
    saga_id: str
    broker_connection_id: str
    requires_manual_review: bool
    timestamp: str


# =============================================================================
# Broker Operation Events
# =============================================================================

@saga_event()
class BrokerTokenRefreshCompleted(BaseEvent):
    """Raised when broker token refresh completes"""
    event_type: Literal["BrokerTokenRefreshCompleted"] = "BrokerTokenRefreshCompleted"
    saga_id: Optional[str] = None
    broker_connection_id: str
    success: bool
    timestamp: str


@saga_event()
class BrokerOAuthFlowCompleted(BaseEvent):
    """Raised when broker OAuth flow completes"""
    event_type: Literal["BrokerOAuthFlowCompleted"] = "BrokerOAuthFlowCompleted"
    saga_id: Optional[str] = None
    broker_connection_id: str
    success: bool
    timestamp: str


# =============================================================================
# Batch Operation Events
# =============================================================================

@saga_event()
class BatchAccountDeletionCompleted(BaseEvent):
    """Raised when batch account deletion completes"""
    event_type: Literal["BatchAccountDeletionCompleted"] = "BatchAccountDeletionCompleted"
    saga_id: Optional[str] = None
    user_id: str
    deleted_count: int
    failed_count: int
    details: Dict[str, Any]
    timestamp: str


@saga_event()
class BatchConnectionPurgeCompleted(BaseEvent):
    """Raised when batch connection purge completes"""
    event_type: Literal["BatchConnectionPurgeCompleted"] = "BatchConnectionPurgeCompleted"
    saga_id: Optional[str] = None
    user_id: str
    purged_count: int
    failed_count: int
    details: Dict[str, Any]
    timestamp: str


@saga_event()
class BatchOperationProgress(BaseEvent):
    """Raised to report batch operation progress"""
    event_type: Literal["BatchOperationProgress"] = "BatchOperationProgress"
    saga_id: Optional[str] = None
    operation_type: str
    total_items: int
    processed_items: int
    failed_items: int
    percent_complete: float
    timestamp: str


# =============================================================================
# System Integration Events
# =============================================================================

@saga_event()
class CrossDomainOperationCompleted(BaseEvent):
    """Raised when a cross-domain operation completes"""
    event_type: Literal["CrossDomainOperationCompleted"] = "CrossDomainOperationCompleted"
    saga_id: Optional[str] = None
    operation_type: str
    domains_involved: List[str]
    success: bool
    details: Dict[str, Any]
    timestamp: str


@saga_event()
class SystemResourcesReconciled(BaseEvent):
    """Raised when system resources are reconciled"""
    event_type: Literal["SystemResourcesReconciled"] = "SystemResourcesReconciled"
    saga_id: Optional[str] = None
    resource_type: str
    reconciliation_details: Dict[str, Any]
    timestamp: str


@saga_event()
class IntegrationHealthCheck(BaseEvent):
    """Raised for integration health checks"""
    event_type: Literal["IntegrationHealthCheck"] = "IntegrationHealthCheck"
    integration_name: str
    is_healthy: bool
    health_details: Dict[str, Any]
    timestamp: str


# =============================================================================
# Notification Events
# =============================================================================

@saga_event()
class UserNotificationRequired(BaseEvent):
    """Raised when user notification is required"""
    event_type: Literal["UserNotificationRequired"] = "UserNotificationRequired"
    user_id: str
    notification_type: str
    title: str
    message: str
    priority: str  # "low", "medium", "high", "urgent"
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


@saga_event()
class SystemAlertGenerated(BaseEvent):
    """Raised when system alert is generated"""
    event_type: Literal["SystemAlertGenerated"] = "SystemAlertGenerated"
    alert_type: str
    severity: str  # "info", "warning", "error", "critical"
    message: str
    source: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


# =============================================================================
# Data Synchronization Events
# =============================================================================

@saga_event()
class DataSynchronizationCompleted(BaseEvent):
    """Raised when data synchronization completes"""
    event_type: Literal["DataSynchronizationCompleted"] = "DataSynchronizationCompleted"
    sync_type: str
    source: str
    destination: str
    records_synced: int
    success: bool
    details: Dict[str, Any]
    timestamp: str


@saga_event()
class ProjectionRebuildCompleted(BaseEvent):
    """Raised when projection rebuild completes"""
    event_type: Literal["ProjectionRebuildCompleted"] = "ProjectionRebuildCompleted"
    projection_name: str
    events_processed: int
    success: bool
    duration_ms: int
    details: Dict[str, Any]
    timestamp: str


# =============================================================================
# Export all event types
# =============================================================================

__all__ = [
    # Core saga lifecycle
    "SagaStarted", "SagaStepStarted", "SagaStepCompleted", "SagaStepFailed",
    "SagaCompleted", "SagaCompensationStarted", "SagaCompensationCompleted",
    "SagaFailed", "SagaTimedOut", "SagaRetrying",

    # Monitoring events
    "SagaTriggered", "SagaMetricsUpdated", "SagaHealthCheck",

    # Specific saga completions
    "UserDeletionCompleted", "BrokerDisconnectionCompleted",
    "BrokerConnectionEstablishedSagaCompleted", "AccountRefreshCompleted",
    "OrderFulfillmentCompleted", "CompanyCreationSagaCompleted", "CompanyCreationSagaFailed",

    # Compensation events
    "SagaCompensationStepStarted", "SagaCompensationStepCompleted",
    "SagaCompensationStepFailed", "SagaManualInterventionRequired",

    # Account operation events
    "AccountDiscoveryFailed",

    # Broker connection events
    "BrokerConnectionReady", "BrokerConnectionHealthCheckCompleted",
    "BrokerConnectionEstablishmentCompleted", "BrokerConnectionValidationCompleted",

    # Saga compensation required events
    "BrokerDisconnectionCompensationRequired", "UserDeletionCompensationRequired",
    "AccountRefreshCompensationRequired", "BrokerAccountDiscoveryFailed",

    # Broker operation events
    "BrokerTokenRefreshCompleted", "BrokerOAuthFlowCompleted",

    # Batch operation events
    "BatchAccountDeletionCompleted", "BatchConnectionPurgeCompleted",
    "BatchOperationProgress",

    # System integration events
    "CrossDomainOperationCompleted", "SystemResourcesReconciled",
    "IntegrationHealthCheck",

    # Notification events
    "UserNotificationRequired", "SystemAlertGenerated",

    # Data synchronization events
    "DataSynchronizationCompleted", "ProjectionRebuildCompleted",
]

# =============================================================================
# EOF
# =============================================================================
