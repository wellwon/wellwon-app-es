# app/common/events/data_sync_events.py
"""
Data Integrity Monitor Event Definitions - ENHANCED VERSION

These events are used by the DataIntegrityMonitor service and other components
to track integrity checking operations, issues, and metrics.

FIXED: Added all events that the monitor publishes
ENHANCED: Proper event structure matching the system
"""

from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone

# Import your existing BaseEvent which is already Pydantic v2 compatible
from app.common.base.base_model import BaseEvent


# ========================================================================
# CORE INTEGRITY EVENTS
# ========================================================================

class IntegrityCheckStarted(BaseEvent):
    """
    Emitted when an integrity check starts.

    Attributes:
        check_id: Unique identifier for this check
        connection_id: UUID of the broker connection being checked (as string)
        user_id: UUID of the user who owns the connection
        broker_id: Broker identifier (e.g., 'alpaca', 'ibkr')
        triggered_by: What triggered this check ("startup", "continuous", "manual", "connection_established")
        check_type: Level of check being performed ("basic", "standard", "deep")
        correlation_id: ID to correlate related events
    """
    check_id: str
    connection_id: str
    user_id: str
    broker_id: str
    triggered_by: str
    check_type: str  # "basic", "standard", "deep"
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityCheckStarted"] = "IntegrityCheckStarted"


class IntegrityCheckCompleted(BaseEvent):
    """
    Emitted when an integrity check completes.

    Attributes:
        check_id: Unique identifier for this check
        connection_id: UUID of the broker connection that was checked (as string)
        user_id: UUID of the user who owns the connection
        broker_id: Broker identifier
        status: Final status (HEALTHY, DEGRADED, CRITICAL, RECOVERING, PENDING_DISCOVERY, UNKNOWN)
        missing_accounts: Number of accounts found in broker but not in local database
        balance_discrepancies: Number of accounts with balance mismatches
        status_mismatches: Number of accounts with status mismatches
        duration_ms: How long the check took in milliseconds
        recovery_triggered: Whether automatic recovery was triggered
        discovery_triggered: Whether account discovery was triggered
        correlation_id: ID to correlate related events
    """
    check_id: str
    connection_id: str
    user_id: str
    broker_id: str
    status: str
    missing_accounts: int = 0
    balance_discrepancies: int = 0
    status_mismatches: int = 0
    duration_ms: int
    recovery_triggered: bool = False
    discovery_triggered: bool = False
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityCheckCompleted"] = "IntegrityCheckCompleted"


class IntegrityMetricsUpdate(BaseEvent):
    """
    Emitted periodically with integrity monitoring metrics.

    Attributes:
        metrics: Dictionary containing all current metrics including:
            - Total checks performed
            - Health status counts
            - Error counts
            - Recovery statistics
            - Performance metrics (latencies)
            - Circuit breaker states
    """
    metrics: Dict[str, Any]
    event_type: Literal["IntegrityMetricsUpdate"] = "IntegrityMetricsUpdate"


# ========================================================================
# ISSUE AND ALERT EVENTS
# ========================================================================

class IntegrityIssueDetected(BaseEvent):
    """
    Emitted when a specific integrity issue is detected.

    Attributes:
        issue_id: Unique identifier for this issue
        connection_id: UUID of the broker connection (optional, for connection-level issues)
        account_id: UUID of the specific account (for account-level issues)
        user_id: UUID of the user
        broker_id: Broker identifier
        issue_type: Type of issue (MISSING_ACCOUNTS, BALANCE_MISMATCH, etc.)
        severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
        description: Human-readable description
        details: Additional details about the issue
        auto_recoverable: Whether this issue can be auto-recovered
        check_id: ID of the check that found this issue
        correlation_id: ID to correlate related events
    """
    issue_id: str
    user_id: str
    broker_id: str
    issue_type: str
    severity: str
    description: str
    connection_id: Optional[str] = None  # Optional - for connection-level issues
    account_id: Optional[str] = None     # Optional - for account-level issues
    details: Dict[str, Any] = {}
    auto_recoverable: bool = True
    check_id: Optional[str] = None
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityIssueDetected"] = "IntegrityIssueDetected"


class IntegrityAlert(BaseEvent):
    """
    Emitted when a critical integrity issue requires immediate attention.

    Attributes:
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        alert_type: Type of alert (MISSING_ACCOUNTS, BALANCE_DISCREPANCY, etc.)
        severity: Severity level (CRITICAL, HIGH, etc.)
        message: Alert message
        details: Additional details
        check_id: ID of the check that triggered this alert
        correlation_id: ID to correlate related events
    """
    connection_id: str
    user_id: str
    broker_id: str
    alert_type: str
    severity: str
    message: str
    details: Dict[str, Any] = {}
    check_id: Optional[str] = None
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityAlert"] = "IntegrityAlert"


# ========================================================================
# RECOVERY EVENTS
# ========================================================================

class IntegrityRecoveryTriggered(BaseEvent):
    """
    Emitted when automatic recovery is triggered.

    Attributes:
        recovery_id: Unique identifier for this recovery operation
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        missing_accounts_count: Number of missing accounts to recover
        triggered_by: What triggered the recovery
        correlation_id: ID to correlate related events
    """
    recovery_id: str
    connection_id: str
    user_id: str
    broker_id: str
    missing_accounts_count: int
    triggered_by: str
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityRecoveryTriggered"] = "IntegrityRecoveryTriggered"


class IntegrityRecoveryCompleted(BaseEvent):
    """
    Emitted when recovery operation completes successfully.

    Attributes:
        recovery_id: Unique identifier for this recovery operation
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        accounts_recovered: Number of accounts recovered
        duration_ms: How long the recovery took
        correlation_id: ID to correlate related events
    """
    recovery_id: str
    connection_id: str
    user_id: str
    broker_id: str
    accounts_recovered: int
    duration_ms: int
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityRecoveryCompleted"] = "IntegrityRecoveryCompleted"


class IntegrityRecoveryFailed(BaseEvent):
    """
    Emitted when recovery operation fails.

    Attributes:
        recovery_id: Unique identifier for this recovery operation
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        error: Error message
        correlation_id: ID to correlate related events
    """
    recovery_id: str
    connection_id: str
    user_id: str
    broker_id: str
    error: str
    correlation_id: Optional[str] = None
    event_type: Literal["IntegrityRecoveryFailed"] = "IntegrityRecoveryFailed"


# ========================================================================
# DISCOVERY EVENTS
# ========================================================================

class IntegrityDiscoveryTriggered(BaseEvent):
    """
    Emitted when account discovery is triggered by integrity monitor.

    Attributes:
        discovery_id: Unique identifier for this discovery operation
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        reason: Why discovery was triggered
    """
    discovery_id: str
    connection_id: str
    user_id: str
    broker_id: str
    reason: str  # "missing_accounts_detected", "new_oauth_connection", etc.
    event_type: Literal["IntegrityDiscoveryTriggered"] = "IntegrityDiscoveryTriggered"


class IntegrityDiscoveryCompleted(BaseEvent):
    """
    Emitted when account discovery completes.

    Attributes:
        discovery_id: Unique identifier for this discovery operation
        connection_id: UUID of the broker connection
        user_id: UUID of the user
        broker_id: Broker identifier
        accounts_discovered: Number of accounts discovered
        accounts_linked: Number of accounts linked
        success: Whether discovery was successful
    """
    discovery_id: str
    connection_id: str
    user_id: str
    broker_id: str
    accounts_discovered: int
    accounts_linked: int
    success: bool = True
    event_type: Literal["IntegrityDiscoveryCompleted"] = "IntegrityDiscoveryCompleted"


# ========================================================================
# SYSTEM EVENTS
# ========================================================================

class IntegrityMonitorStarted(BaseEvent):
    """
    Emitted when the integrity monitor service starts.

    Attributes:
        config: Configuration the monitor started with
    """
    config: Dict[str, Any]
    event_type: Literal["IntegrityMonitorStarted"] = "IntegrityMonitorStarted"


class BackgroundHistorySyncRequested(BaseEvent):
    """
    Request background sync of historical data for accounts.

    Published by: Server (on connect, user action, scheduler)
    Consumed by: DataSyncWorker

    Supports:
    - Multi-account batch sync
    - Adaptive time windows (7/30/365 days)
    - Selective data types (orders, positions, accounts)
    - Tiered priority (1=realtime, 2=background, 3=historical)
    """
    event_type: Literal["BackgroundHistorySyncRequested"] = "BackgroundHistorySyncRequested"
    user_id: str
    account_ids: List[str]
    sync_window_days: int = 30  # Default: 30 days
    tier: int = 2  # 1=realtime, 2=background, 3=historical
    data_types: List[str] = ["orders", "positions", "accounts"]  # What to sync
    force: bool = False  # Force refresh even if recently synced
    triggered_by: str = "manual"  # "manual", "scheduler", "connection_established"


class BackgroundSyncProgressEvent(BaseEvent):
    """
    Progress update for background sync operation.

    Published by: DataSyncWorker
    Consumed by: WebSocket clients (via WSE), monitoring

    Tracks progress of multi-step sync operation.
    """
    event_type: Literal["BackgroundSyncProgressEvent"] = "BackgroundSyncProgressEvent"
    user_id: str
    account_id: str
    status: str  # "started", "syncing_orders", "syncing_positions", "syncing_accounts", "complete", "error"
    progress: int  # 0-100
    current_step: Optional[str] = None  # "Fetching orders...", "Syncing positions..."

    # Data synced counters
    orders_synced: int = 0
    positions_synced: int = 0
    accounts_synced: int = 0
    fills_synced: int = 0

    # Error info
    error: Optional[str] = None

    # Timing
    estimated_completion_ms: Optional[int] = None
    elapsed_ms: Optional[int] = None


class IntegrityMonitorStopped(BaseEvent):
    """
    Emitted when the integrity monitor service stops.

    Attributes:
        metrics: Final metrics at shutdown
        reason: Why the monitor stopped
    """
    metrics: Dict[str, Any]
    reason: str = "shutdown"
    event_type: Literal["IntegrityMonitorStopped"] = "IntegrityMonitorStopped"


# ========================================================================
# DEPRECATED BUT KEPT FOR COMPATIBILITY
# ========================================================================

class IntegrityRecoveryStarted(BaseEvent):
    """
    DEPRECATED: Use IntegrityRecoveryTriggered instead.
    Kept for backward compatibility.
    """
    connection_id: str
    saga_id: str
    missing_accounts_count: int
    triggered_by: str
    discrepancy_summary: Dict[str, int]
    event_type: Literal["IntegrityRecoveryStarted"] = "IntegrityRecoveryStarted"


class IntegrityAlertRaised(BaseEvent):
    """
    DEPRECATED: Use IntegrityAlert instead.
    Kept for backward compatibility.
    """
    connection_id: str
    alert_type: str
    severity: str
    details: Dict[str, Any]
    recommended_action: str
    event_type: Literal["IntegrityAlertRaised"] = "IntegrityAlertRaised"


class AccountDiscoveryInitiated(BaseEvent):
    """
    DEPRECATED: Use IntegrityDiscoveryTriggered instead.
    Kept for backward compatibility.
    """
    connection_id: str
    broker_id: str
    user_id: str
    reason: str
    missing_count: int
    event_type: Literal["AccountDiscoveryInitiated"] = "AccountDiscoveryInitiated"


# ========================================================================
# EVENT HELPERS
# ========================================================================

def create_integrity_check_started_event(
        check_id: str,
        connection_id: str,
        user_id: str,
        broker_id: str,
        triggered_by: str,
        check_type: str,
        correlation_id: Optional[str] = None
) -> IntegrityCheckStarted:
    """Helper to create IntegrityCheckStarted event"""
    return IntegrityCheckStarted(
        check_id=check_id,
        connection_id=connection_id,
        user_id=user_id,
        broker_id=broker_id,
        triggered_by=triggered_by,
        check_type=check_type,
        correlation_id=correlation_id
    )


def create_integrity_check_completed_event(
        check_id: str,
        connection_id: str,
        user_id: str,
        broker_id: str,
        status: str,
        duration_ms: int,
        missing_accounts: int = 0,
        balance_discrepancies: int = 0,
        status_mismatches: int = 0,
        recovery_triggered: bool = False,
        discovery_triggered: bool = False,
        correlation_id: Optional[str] = None
) -> IntegrityCheckCompleted:
    """Helper to create IntegrityCheckCompleted event"""
    return IntegrityCheckCompleted(
        check_id=check_id,
        connection_id=connection_id,
        user_id=user_id,
        broker_id=broker_id,
        status=status,
        duration_ms=duration_ms,
        missing_accounts=missing_accounts,
        balance_discrepancies=balance_discrepancies,
        status_mismatches=status_mismatches,
        recovery_triggered=recovery_triggered,
        discovery_triggered=discovery_triggered,
        correlation_id=correlation_id
    )


def create_integrity_alert(
        connection_id: str,
        user_id: str,
        broker_id: str,
        alert_type: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
        check_id: Optional[str] = None,
        correlation_id: Optional[str] = None
) -> IntegrityAlert:
    """Helper to create IntegrityAlert event"""
    return IntegrityAlert(
        connection_id=connection_id,
        user_id=user_id,
        broker_id=broker_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        details=details,
        check_id=check_id,
        correlation_id=correlation_id
    )


# ========================================================================
# TOPIC MAPPINGS
# ========================================================================

# Define which topics each event type should be published to
INTEGRITY_EVENT_TOPICS = {
    "IntegrityCheckStarted": "system.data-integrity-events",
    "IntegrityCheckCompleted": "system.data-integrity-events",
    "IntegrityMetricsUpdate": "system.data-integrity-metrics",
    "IntegrityIssueDetected": "system.data-integrity-events",
    "IntegrityAlert": "alerts.data-integrity",
    "IntegrityRecoveryTriggered": "integrity.recovery_triggered",
    "IntegrityRecoveryCompleted": "integrity.recovery_completed",
    "IntegrityRecoveryFailed": "integrity.recovery_failed",
    "IntegrityDiscoveryTriggered": "integrity.discovery_triggered",
    "IntegrityDiscoveryCompleted": "integrity.discovery_completed",
    "IntegrityMonitorStarted": "system.worker-events",
    "IntegrityMonitorStopped": "system.worker-events",
}


def get_topic_for_event(event_type: str) -> str:
    """Get the correct Kafka topic for an integrity event type"""
    return INTEGRITY_EVENT_TOPICS.get(event_type, "system.data-integrity-events")