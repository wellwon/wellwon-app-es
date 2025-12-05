# =============================================================================
# File: app/infra/event_store/event_envelope.py
# Description: Event envelope data structures for event store
# =============================================================================

from __future__ import annotations

from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.common.base.base_model import BaseEvent
from app.infra.event_bus.event_registry import get_event_model
from app.utils.uuid_utils import generate_uuid, generate_event_id


@dataclass
class EventEnvelope:
    """Enhanced wrapper for events stored in the event store with sequence support"""
    aggregate_id: UUID
    aggregate_type: str
    aggregate_version: int
    event_id: UUID
    event_type: str
    event_data: Dict[str, Any]
    event_version: int = 1  # FIXED: Made optional with default value
    causation_id: Optional[UUID] = None  # FIXED: Made properly optional
    correlation_id: Optional[UUID] = None  # FIXED: Made properly optional
    metadata: Optional[Dict[str, Any]] = None  # FIXED: Made properly optional
    stored_at: datetime = None  # FIXED: Will be set in __post_init__ if not provided
    sequence_number: Optional[int] = None
    saga_id: Optional[UUID] = None  # Track which saga created this event
    projection_checkpoint: Optional[Dict[str, int]] = None  # Track projection progress
    commit_position: Optional[int] = None  # ADDED (2025-11-10): KurrentDB global position for read-after-write

    def __post_init__(self):
        """Set default values after initialization"""
        if self.stored_at is None:
            self.stored_at = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_event(
            cls,
            event: BaseEvent,
            aggregate_id: UUID,
            aggregate_type: str,
            aggregate_version: int,
            causation_id: Optional[UUID] = None,
            correlation_id: Optional[UUID] = None,
            metadata: Optional[Dict[str, Any]] = None,
            sequence_number: Optional[int] = None,
            saga_id: Optional[UUID] = None
    ) -> EventEnvelope:
        """Create envelope from domain event with enhanced metadata"""
        # Extract saga_id from metadata if present
        if metadata and 'saga_id' in metadata and not saga_id:
            saga_id = UUID(metadata['saga_id']) if isinstance(metadata['saga_id'], str) else metadata['saga_id']

        # Get event version from event or default to 1
        event_version = getattr(event, 'version', 1)

        return cls(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            aggregate_version=aggregate_version,
            event_id=event.event_id,
            event_type=event.event_type,
            event_data=event.model_dump(mode='json'),
            event_version=event_version,
            causation_id=causation_id,
            correlation_id=correlation_id,
            metadata=metadata or {},
            stored_at=datetime.now(timezone.utc),
            sequence_number=sequence_number,
            saga_id=saga_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "aggregate_id": str(self.aggregate_id),
            "aggregate_type": self.aggregate_type,
            "aggregate_version": self.aggregate_version,
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_data": self.event_data,
            "event_version": self.event_version,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "metadata": self.metadata,
            "stored_at": self.stored_at.isoformat(),
            "sequence_number": self.sequence_number,
            "saga_id": str(self.saga_id) if self.saga_id else None,
            "projection_checkpoint": self.projection_checkpoint,
            "commit_position": self.commit_position  # ADDED (2025-11-10)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EventEnvelope:
        """Recreate from stored dictionary"""
        return cls(
            aggregate_id=UUID(data["aggregate_id"]),
            aggregate_type=data["aggregate_type"],
            aggregate_version=data["aggregate_version"],
            event_id=UUID(data["event_id"]),
            event_type=data["event_type"],
            event_data=data["event_data"],
            event_version=data.get("event_version", 1),  # FIXED: Default to 1 if missing
            causation_id=UUID(data["causation_id"]) if data.get("causation_id") else None,
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            metadata=data.get("metadata", {}),
            stored_at=datetime.fromisoformat(data["stored_at"]),
            sequence_number=data.get("sequence_number"),
            saga_id=UUID(data["saga_id"]) if data.get("saga_id") else None,
            projection_checkpoint=data.get("projection_checkpoint"),
            commit_position=data.get("commit_position")  # ADDED (2025-11-10)
        )

    def to_event_object(self) -> Optional[BaseEvent]:
        """
        Deserialize event_data back to Pydantic event object using event registry.

        Returns:
            Pydantic event object if event type is registered, None otherwise
        """
        event_model_class = get_event_model(self.event_type)
        if event_model_class:
            try:
                # Deserialize dict to Pydantic object
                return event_model_class(**self.event_data)
            except Exception as e:
                # If deserialization fails, return None (caller can use dict instead)
                return None
        return None

    @property
    def kurrentdb_metadata(self) -> Dict[str, Any]:
        """
        Get metadata in KurrentDB format with reserved field names.

        KurrentDB uses $ prefix for reserved system fields:
        - $causationId: Direct cause of this event (previous event's ID)
        - $correlationId: Workflow/conversation ID for tracking event chains

        This enables:
        - KurrentDB system projections ($by_correlation_id, $by_causation_id)
        - Distributed tracing with OpenTelemetry
        - Event chain visualization in KurrentDB UI

        Returns:
            dict: Metadata with KurrentDB reserved field format
        """
        return {
            '$causationId': str(self.causation_id) if self.causation_id else None,
            '$correlationId': str(self.correlation_id) if self.correlation_id else None,
            'saga_id': str(self.saga_id) if self.saga_id else None,
            'aggregate_type': self.aggregate_type,
            'aggregate_id': str(self.aggregate_id),
            'aggregate_version': self.aggregate_version,
            'timestamp': self.stored_at.isoformat()
        }

    @classmethod
    def from_kurrentdb_metadata(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert KurrentDB metadata format to EventEnvelope field format.

        Converts reserved fields back to Python-friendly names:
        - $causationId → causation_id
        - $correlationId → correlation_id

        Args:
            metadata: Metadata dict from KurrentDB event

        Returns:
            dict: Field names compatible with EventEnvelope
        """
        return {
            'causation_id': metadata.get('$causationId') or metadata.get('causation_id'),  # Backward compat
            'correlation_id': metadata.get('$correlationId') or metadata.get('correlation_id'),  # Backward compat
            'saga_id': metadata.get('saga_id'),
            'aggregate_type': metadata.get('aggregate_type'),
            'aggregate_id': metadata.get('aggregate_id'),
            'aggregate_version': metadata.get('aggregate_version'),
        }

    @classmethod
    def from_partial_data(cls, data: Dict[str, Any]) -> EventEnvelope:
        """
        Create EventEnvelope from partial event data (for backward compatibility).
        This method handles events that might be missing some fields.
        """
        # Extract core fields with defaults
        event_type = data.get('event_type', 'UnknownEvent')
        event_id = data.get('event_id', generate_event_id())

        # For different event types, aggregate_id might be in different fields
        aggregate_id = (
                data.get('aggregate_id') or
                data.get('chat_id') or  # Chat domain events
                data.get('user_id') or  # User domain events
                data.get('account_id') or  # Account events
                data.get('virtual_account_id') or  # Virtual broker events
                str(generate_uuid())
        )

        # Ensure UUIDs are properly formatted - handle str, UUID objects, and ints
        if isinstance(event_id, str):
            event_id = UUID(event_id)
        elif isinstance(event_id, int):
            # Fallback: generate new UUID if int was passed (shouldn't happen)
            event_id = generate_uuid()
        # If already UUID, use as-is

        if isinstance(aggregate_id, str):
            aggregate_id = UUID(aggregate_id)
        elif isinstance(aggregate_id, int):
            # Fallback: generate new UUID if int was passed (shouldn't happen)
            aggregate_id = generate_uuid()
        # If already UUID, use as-is

        # Handle timestamp
        timestamp = None
        if 'timestamp' in data:
            try:
                timestamp = datetime.fromisoformat(data['timestamp'])
            except:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        return cls(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=data.get('aggregate_type', 'VirtualBrokerAccount'),
            aggregate_version=data.get('aggregate_version', 1),
            event_data=data,  # Store the entire dict as event_data
            event_version=data.get('event_version', data.get('version', 1)),
            stored_at=timestamp,
            sequence_number=data.get('sequence_number'),
            correlation_id=UUID(data['correlation_id']) if data.get('correlation_id') else None,
            causation_id=UUID(data['causation_id']) if data.get('causation_id') else None,
            metadata=data.get('metadata', {}),
            saga_id=UUID(data['saga_id']) if data.get('saga_id') else None
        )


@dataclass
class AggregateSnapshot:
    """Snapshot of aggregate state at a specific version"""
    aggregate_id: UUID
    aggregate_type: str
    version: int
    state: Dict[str, Any]
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    global_sequence: Optional[int] = None  # Global sequence number at snapshot time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aggregate_id": str(self.aggregate_id),
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "global_sequence": self.global_sequence
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AggregateSnapshot:
        return cls(
            aggregate_id=UUID(data["aggregate_id"]),
            aggregate_type=data["aggregate_type"],
            version=data["version"],
            state=data["state"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata"),
            global_sequence=data.get("global_sequence")
        )