# =============================================================================
# File: app/common/base_event_model.py
# Description: Base Pydantic model for all system domain events
#              for 
# =============================================================================

from __future__ import annotations

import uuid
import time  # Keep for consistency if preferred over datetime.now() for simple ms timestamp
from datetime import datetime, timezone  # Added timezone
from typing import Final, Dict, Any  # Added Dict, Any for model_config
from pydantic import BaseModel, Field, ConfigDict

# Default schema version for events if not overridden by specific event types
_DEFAULT_DOMAIN_EVENT_VERSION: Final[int] = 1  # Using integer for event model version


class BaseEvent(BaseModel):
    """
    Base Pydantic model for all system domain events.
    Ensures common metadata fields are present in every event.
    """
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str  # To be overridden by Literal in specific event types
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # ISO UTC datetime
    # schema_version: str = Field(default=_DEFAULT_EVENT_SCHEMA_VERSION) # From original wellwon_model
    version: int = Field(default=_DEFAULT_DOMAIN_EVENT_VERSION, description="Version of this event model's schema")

    # Common Pydantic model configuration
    model_config = ConfigDict(
        frozen=True,  # Events are immutable facts (best practice 2025)
        from_attributes=True,  # Allows creating models from ORM objects or other attribute-based objects
        populate_by_name=True,  # Allows using field aliases during model initialization
        extra='allow'
        # Allows extra fields in the input data that are not defined in the model (useful for event evolution)
    )

    def to_dict_for_bus(self) -> Dict[str, Any]:
        """
        Serializes the event to a dictionary suitable for publishing to an event bus,
        converting UUID and datetime to strings.
        """
        event_dict = self.model_dump(by_alias=True)  # Use by_alias if your Pydantic models use aliases
        event_dict["event_id"] = str(self.event_id)
        event_dict["timestamp"] = self.timestamp.isoformat()  # Standard ISO format
        # Keep other fields as is, JSON serializer will handle them.
        return event_dict