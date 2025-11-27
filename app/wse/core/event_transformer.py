# =============================================================================
# File: app/wse/core/event_transformer.py
# Description: Event Transformation Between Internal and WebSocket Formats
# =============================================================================

"""
EventTransformer for WSE

Transforms internal domain events to WebSocket-compatible format.

Architecture:
    Internal Domain Event -> EventTransformer -> WebSocket Event (v2)

WebSocket Event Format (v2):
    {
        "v": 2,                          # Protocol version
        "id": "evt_123",                 # Event ID
        "t": "user_profile_updated",     # Event type (mapped from internal)
        "ts": "2025-01-13T...",          # Timestamp (ISO 8601)
        "seq": 1234,                     # Sequence number
        "p": {...},                      # Payload (transformed)
        "cid": "cor_123",                # Correlation ID (optional)
        "pri": 5,                        # Priority (optional)
        "event_version": 1,              # Schema version (optional)
        "trace_id": "trace_123",         # Distributed tracing (optional)
        "latency_ms": 15                 # Processing latency (optional)
    }

Transformation Pipeline:
    1. Decode bytes to strings (safe multi-encoding)
    2. Map internal event type -> WebSocket event type
    3. Transform payload (domain-specific)
    4. Calculate latency for monitoring
    5. Add metadata (correlation, tracing, priority)

Supported Event Types:
    - user_account_update
    - user_profile_updated
    - system_announcement

Performance:
    - Latency tracking (warn >1s, info >100ms)
    - Safe string decoding with fallback encodings
    - Deep serialization (UUIDs, datetimes, enums)
"""

import logging
import uuid as uuid_module
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, Union

from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

log = logging.getLogger("wellwon.wse.transformer")


class EventTransformer:
    """Transform events between internal and WebSocket formats"""

    @staticmethod
    def safe_decode_bytes(value: Union[bytes, str, Any]) -> str:
        """Safely decode bytes to string with multiple fallback encodings"""
        if isinstance(value, bytes):
            # Try different encodings in order of likelihood
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii']:
                try:
                    return value.decode(encoding)
                except (UnicodeDecodeError, AttributeError):
                    continue
            # Final fallback: hex representation
            return value.hex()
        elif isinstance(value, str):
            return value
        else:
            return str(value)

    @staticmethod
    def transform_for_ws(event: Dict[str, Any], sequence: int = 0) -> Dict[str, Any]:
        """Transform internal event to WebSocket format"""

        # Check if already transformed
        if all(key in event for key in ['v', 't', 'p', 'id', 'ts']):
            # Already in WebSocket format, just update sequence if needed
            if 'seq' not in event:
                event['seq'] = sequence
            return event

        # Ensure all string fields are properly decoded if they're bytes
        def ensure_str(value):
            if isinstance(value, bytes):
                return EventTransformer.safe_decode_bytes(value)
            elif isinstance(value, uuid_module.UUID):
                return str(value)
            elif isinstance(value, (datetime, date)):
                return value.isoformat()
            elif isinstance(value, Enum):
                return value.value
            return value

        # Deep convert any non-serializable types to strings
        def convert_to_serializable(obj):
            if isinstance(obj, bytes):
                return EventTransformer.safe_decode_bytes(obj)
            elif isinstance(obj, uuid_module.UUID):
                return str(obj)
            elif isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return convert_to_serializable(obj.__dict__)
            return obj

        # Get the event type and ensure it's a string
        event_type = ensure_str(event.get('event_type') or event.get('type') or 'unknown')

        # Map internal event type to WebSocket event type
        ws_event_type = INTERNAL_TO_WS_EVENT_TYPE_MAP.get(event_type, event_type.lower())

        # Extract metadata
        metadata = event.get('_metadata') or {}

        # Calculate event processing latency for observability
        event_timestamp_str = metadata.get('timestamp') or event.get('timestamp')
        event_latency_ms = None
        if event_timestamp_str:
            try:
                # Parse event timestamp (robust handling for PostgreSQL hour 24 edge case)
                from app.utils.datetime_utils import parse_timestamp_robust
                event_timestamp = parse_timestamp_robust(event_timestamp_str)

                # Calculate latency from event creation to now
                if event_timestamp:
                    latency_delta = datetime.now(timezone.utc) - event_timestamp.replace(tzinfo=timezone.utc)
                    event_latency_ms = int(latency_delta.total_seconds() * 1000)

                    # Log latency for monitoring (info level only for high latency)
                    if event_latency_ms > 1000:  # > 1 second
                        log.warning(
                            f"High event latency detected: {event_latency_ms}ms for event type {event_type}"
                        )
                    elif event_latency_ms > 100:  # > 100ms
                        log.info(
                            f"Event latency: {event_latency_ms}ms for event type {event_type}"
                        )
                    else:
                        log.debug(
                            f"Event latency: {event_latency_ms}ms for event type {event_type}"
                        )
            except Exception as e:
                log.debug(f"Could not calculate event latency: {e}")

        # Build WebSocket-compatible event
        ws_event = {
            'v': 2,  # Protocol version
            'id': ensure_str(metadata.get('event_id') or event.get('event_id') or str(uuid_module.uuid4())),
            't': ws_event_type,
            'ts': ensure_str(
                metadata.get('timestamp') or event.get('timestamp') or datetime.now(timezone.utc).isoformat()),
            'seq': sequence,
            'p': convert_to_serializable(EventTransformer._transform_payload(ws_event_type, event)),
        }

        # Preserve original event type for specific handlers
        if event_type != ws_event_type:
            ws_event['original_event_type'] = event_type

        # Add latency metadata for monitoring
        if event_latency_ms is not None:
            ws_event['latency_ms'] = event_latency_ms

        # Add optional fields if present
        if 'correlation_id' in metadata or 'correlation_id' in event:
            ws_event['cid'] = ensure_str(metadata.get('correlation_id') or event.get('correlation_id'))

        if 'priority' in metadata or 'pri' in event:
            ws_event['pri'] = metadata.get('priority') or event.get('pri')

        # Add event version for schema evolution support
        event_version = event.get('version') or metadata.get('version', 1)
        if event_version:
            ws_event['event_version'] = int(event_version)

        # Add trace_id for distributed tracing support
        trace_id = metadata.get('trace_id') or event.get('trace_id')
        if trace_id:
            ws_event['trace_id'] = ensure_str(trace_id)
            # Log with trace_id for traceability
            log.debug(f"Event {event_type} with trace_id: {trace_id}")

        return ws_event

    @staticmethod
    def _transform_payload(ws_event_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform event payload to WebSocket format"""
        # Call the appropriate transformation method
        if ws_event_type == 'user_account_update' or ws_event_type == 'user_profile_updated':
            return EventTransformer._transform_user_account(event)
        elif ws_event_type == 'system_announcement':
            return EventTransformer._transform_system_announcement(event)
        else:
            # Default transformation - extract payload
            return EventTransformer._extract_payload(event)

    @staticmethod
    def _transform_user_account(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform user account event"""
        return {
            'user_id': str(event.get('user_id', event.get('aggregate_id', ''))),
            'email': event.get('email'),
            'first_name': event.get('first_name'),
            'last_name': event.get('last_name'),
            'company_name': event.get('company_name'),
            'role': event.get('role'),
            'phone': event.get('phone'),
            'avatar_url': event.get('avatar_url'),
            'timezone': event.get('timezone'),
            'language': event.get('language'),
            'is_active': event.get('is_active', True),
            'email_verified': event.get('email_verified', False),
            'created_at': event.get('created_at'),
            'updated_at': event.get('updated_at'),
            'metadata': event.get('metadata'),
        }

    @staticmethod
    def _transform_system_announcement(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform system announcement event"""
        return {
            'id': event.get('id') or str(uuid_module.uuid4()),
            'type': event.get('type', 'info'),
            'title': event.get('title'),
            'message': event.get('message'),
            'timestamp': event.get('timestamp') or datetime.now(timezone.utc).isoformat(),
            'priority': event.get('priority', 'normal'),
            'dismissible': event.get('dismissible', True),
            'action': event.get('action'),
            'expires_at': event.get('expires_at'),
        }

    @staticmethod
    def _extract_payload(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format payload from a domain event"""
        # Remove metadata and extract actual payload
        payload = event.get('payload', event)
        if '_metadata' in payload:
            payload = {k: v for k, v in payload.items() if k != '_metadata'}

        # Ensure event_type is set if type is provided
        if 'type' in payload and 'event_type' not in payload:
            payload['event_type'] = payload['type']

        return payload


# =============================================================================
# EOF
# =============================================================================
