"""
Data Sync Events - WellWon Platform

Generic events for data synchronization with external APIs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from app.common.base.base_model import BaseEvent


@dataclass
class DataRefreshRequested(BaseEvent):
    """
    Request to refresh data from external API.

    Use cases:
    - Refresh customs clearance status
    - Update shipment tracking
    - Sync document processing status
    """
    event_type: str = "DataRefreshRequested"

    entity_type: str
    entity_id: str
    requested_by: Optional[UUID] = None
    priority: str = "normal"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PeriodicSyncScheduled(BaseEvent):
    """
    Scheduled periodic data synchronization.

    Triggered by scheduler for routine data refresh.
    """
    event_type: str = "PeriodicSyncScheduled"

    sync_type: str
    batch_size: int = 100
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class IntegrityCheckRequested(BaseEvent):
    """
    Request for data integrity validation.

    Validates consistency between local data and external API.
    """
    event_type: str = "IntegrityCheckRequested"

    check_type: str
    entity_ids: list = None
    severity: str = "info"

    def __post_init__(self):
        if self.entity_ids is None:
            self.entity_ids = []


@dataclass
class DataSyncCompleted(BaseEvent):
    """
    Data synchronization completed successfully.
    """
    event_type: str = "DataSyncCompleted"

    entity_type: str
    entity_id: str
    records_synced: int = 0
    duration_ms: int = 0


@dataclass
class DataSyncFailed(BaseEvent):
    """
    Data synchronization failed.
    """
    event_type: str = "DataSyncFailed"

    entity_type: str
    entity_id: str
    error_message: str
    retry_count: int = 0
    will_retry: bool = False


@dataclass
class IntegrityIssueDetected(BaseEvent):
    """
    Data integrity issue detected.

    Emitted when local data doesn't match external source.
    """
    event_type: str = "IntegrityIssueDetected"

    entity_type: str
    entity_id: str
    issue_type: str
    severity: str
    details: Dict[str, Any] = None
    auto_fixed: bool = False

    def __post_init__(self):
        if self.details is None:
            self.details = {}
