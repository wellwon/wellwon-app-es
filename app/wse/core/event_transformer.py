# =============================================================================
# File: app/wse/core/event_transformer.py
# Description: Event Transformation Between Internal and WebSocket Formats
# =============================================================================

"""
EventTransformer for WSE

Transforms internal domain events to WebSocket-compatible format.

Architecture:
    Internal Domain Event -> EventTransformer -> WebSocket Event (v2)

WebSocket Message Format (Protocol v2):

    Wire format: {category}{json}
    Example: U{"t":"user_profile_updated","p":{...},"id":"evt_123",...,"v":2}

    JSON structure:
    {
        "t": "user_profile_updated",     # Event type (mapped from internal)
        "p": {...},                      # Payload (transformed)
        "id": "evt_123",                 # Event ID
        "ts": "2025-01-13T...",          # Timestamp (ISO 8601)
        "seq": 1234,                     # Sequence number
        "cid": "cor_123",                # Correlation ID (optional)
        "pri": 5,                        # Priority (optional)
        "event_version": 1,              # Schema version (optional)
        "trace_id": "trace_123",         # Distributed tracing (optional)
        "latency_ms": 15,                # Processing latency (optional)
        "v": 2                           # Protocol version (always last)
    }

    Note: "_msg_cat" is used internally and extracted as prefix during serialization.

Message Categories (prefix):
    S (Snapshot): Full state dump for initial sync or reconnect
    U (Update): Incremental delta updates (default)
    WSE (System): Protocol/system messages (ping, pong, errors, etc.)

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
from app.wse.core.types import MessageCategory, WSE_SYSTEM_EVENT_TYPES

log = logging.getLogger("wellwon.wse.transformer")


class EventTransformer:
    """Transform events between internal and WebSocket formats"""

    @staticmethod
    def determine_message_category(event_type: str) -> str:
        """
        Determine message category based on event type.

        Categories (Protocol v2):
            S (Snapshot): Full state dump for initial sync
            U (Update): Incremental delta updates (default)
            WSE (System): Protocol/system messages

        Args:
            event_type: The WebSocket event type

        Returns:
            Category string: "S", "U", or "WSE"
        """
        event_type_lower = event_type.lower()

        # Snapshot - full state dump
        if 'snapshot' in event_type_lower:
            return MessageCategory.SNAPSHOT.value

        # System - WSE protocol messages
        if event_type in WSE_SYSTEM_EVENT_TYPES or event_type_lower in WSE_SYSTEM_EVENT_TYPES:
            return MessageCategory.SYSTEM.value

        # Default - incremental update
        return MessageCategory.UPDATE.value

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

                    # Log latency for monitoring (warning only for very high latency)
                    if event_latency_ms > 3000:  # > 3 seconds (warning)
                        log.warning(
                            f"High event latency detected: {event_latency_ms}ms for event type {event_type}"
                        )
                    elif event_latency_ms > 500:  # > 500ms (info)
                        log.info(
                            f"Event latency: {event_latency_ms}ms for event type {event_type}"
                        )
                    else:
                        log.debug(
                            f"Event latency: {event_latency_ms}ms for event type {event_type}"
                        )
            except Exception as e:
                log.debug(f"Could not calculate event latency: {e}")

        # Build WebSocket-compatible event (Protocol v2 order: t, p, id, ts, seq, _msg_cat, ..., v)
        ws_event = {
            't': ws_event_type,
            'p': convert_to_serializable(EventTransformer._transform_payload(ws_event_type, event)),
            'id': ensure_str(metadata.get('event_id') or event.get('event_id') or str(uuid_module.uuid4())),
            'ts': ensure_str(
                metadata.get('timestamp') or event.get('timestamp') or datetime.now(timezone.utc).isoformat()),
            'seq': sequence,
            '_msg_cat': EventTransformer.determine_message_category(ws_event_type),
        }

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
            log.debug(f"Event {event_type} with trace_id: {trace_id}")

        # Add latency metadata for monitoring
        if event_latency_ms is not None:
            ws_event['latency_ms'] = event_latency_ms

        # Protocol version at the end (v2)
        ws_event['v'] = 2

        return ws_event

    @staticmethod
    def _transform_payload(ws_event_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform event payload to WebSocket format"""
        # User domain events
        if ws_event_type in ('user_account_update', 'user_profile_updated', 'user_admin_status_updated'):
            return EventTransformer._transform_user_account(event)

        # Company domain events
        if ws_event_type.startswith('company_'):
            return EventTransformer._transform_company_event(event)

        # Chat domain events
        if ws_event_type in ('chat_created', 'chat_updated', 'chat_archived', 'chat_deleted'):
            return EventTransformer._transform_chat_event(event)

        # Message events
        if ws_event_type in ('message_created', 'message_updated', 'message_deleted'):
            return EventTransformer._transform_message_event(event)

        # Participant events
        if ws_event_type in ('participant_joined', 'participant_left', 'participant_role_changed'):
            return EventTransformer._transform_participant_event(event)

        # System events
        if ws_event_type == 'system_announcement':
            return EventTransformer._transform_system_announcement(event)

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
            'is_active': event.get('is_active'),
            'is_developer': event.get('is_developer'),
            'user_type': event.get('user_type'),
            'admin_user_id': str(event.get('admin_user_id')) if event.get('admin_user_id') else None,
            'email_verified': event.get('email_verified'),
            # BaseEvent uses 'timestamp', not 'created_at'
            'created_at': event.get('created_at') or event.get('timestamp'),
            'updated_at': event.get('updated_at') or event.get('timestamp'),
            'metadata': event.get('metadata'),
        }

    @staticmethod
    def _transform_company_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform company domain event for WSE/frontend optimistic updates"""
        return {
            'company_id': str(event.get('company_id', event.get('aggregate_id', ''))),
            'id': str(event.get('company_id', event.get('aggregate_id', ''))),  # alias for frontend
            'name': event.get('name'),
            'company_name': event.get('name'),  # alias for frontend
            'client_type': event.get('client_type', 'company'),
            'description': event.get('description'),
            'owner_id': str(event.get('owner_id', '')) if event.get('owner_id') else None,
            'created_by': str(event.get('created_by', '')) if event.get('created_by') else None,
            'telegram_chat_id': event.get('telegram_chat_id'),
            'telegram_group_id': event.get('telegram_group_id'),
            'telegram_topic_id': event.get('telegram_topic_id'),
            'telegram_invite_link': event.get('telegram_invite_link'),
            'logo_url': event.get('logo_url'),
            'is_active': event.get('is_active', True),
            'balance': event.get('balance'),
            'currency': event.get('currency'),
            'user_id': str(event.get('user_id', '')) if event.get('user_id') else None,
            'role': event.get('role'),
            # BaseEvent uses 'timestamp', not 'created_at'
            'created_at': event.get('created_at') or event.get('timestamp'),
            'updated_at': event.get('updated_at') or event.get('timestamp'),
        }

    @staticmethod
    def _transform_chat_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform chat domain event for WSE/frontend optimistic updates"""
        # telegram_supergroup_id may be in event or legacy telegram_chat_id
        telegram_supergroup_id = event.get('telegram_supergroup_id') or event.get('telegram_chat_id')
        chat_id = str(event.get('chat_id', event.get('aggregate_id', '')))

        return {
            'chat_id': chat_id,
            'id': chat_id,  # alias for frontend
            'name': event.get('name'),
            'chat_name': event.get('name'),  # alias for frontend
            'chat_type': event.get('chat_type'),
            'company_id': str(event.get('company_id', '')) if event.get('company_id') else None,
            'created_by': str(event.get('created_by', '')) if event.get('created_by') else None,
            'participant_count': event.get('participant_count', 1),
            'is_active': event.get('is_active', True),
            # Include both fields for compatibility
            'telegram_chat_id': event.get('telegram_chat_id'),
            'telegram_supergroup_id': telegram_supergroup_id,
            'telegram_topic_id': event.get('telegram_topic_id'),
            'last_message_at': event.get('last_message_at'),
            # BaseEvent uses 'timestamp', not 'created_at'
            'created_at': event.get('created_at') or event.get('timestamp'),
            'updated_at': event.get('updated_at') or event.get('timestamp'),
        }

    @staticmethod
    def _transform_message_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform message event with full Telegram support"""
        # Extract telegram_user_data for external senders
        telegram_user_data = event.get('telegram_user_data') or {}

        # Build sender display name
        sender_id = event.get('sender_id')
        if sender_id:
            # WellWon user - use sender_name from event or lookup
            sender_name = event.get('sender_name')
        else:
            # External Telegram user - build name from telegram_user_data
            first = telegram_user_data.get('first_name', '')
            last = telegram_user_data.get('last_name', '')
            username = telegram_user_data.get('username', '')
            sender_name = f"{first} {last}".strip() or f"@{username}" if username else "Telegram User"

        return {
            'message_id': str(event.get('message_id', event.get('aggregate_id', ''))),
            'chat_id': str(event.get('chat_id', '')) if event.get('chat_id') else None,
            'sender_id': str(sender_id) if sender_id else None,
            'sender_name': sender_name,
            'content': event.get('content'),
            'message_type': event.get('message_type', 'text'),
            'reply_to_id': str(event.get('reply_to_id', '')) if event.get('reply_to_id') else None,
            'file_url': event.get('file_url'),
            'file_name': event.get('file_name'),
            'file_size': event.get('file_size'),
            'file_type': event.get('file_type'),
            'voice_duration': event.get('voice_duration'),
            'source': event.get('source', 'web'),
            # Telegram-specific fields
            'telegram_message_id': event.get('telegram_message_id'),
            'telegram_user_id': event.get('telegram_user_id'),
            'telegram_user_data': telegram_user_data if telegram_user_data else None,
            'is_edited': event.get('is_edited', False),
            'is_deleted': event.get('is_deleted', False),
            # BaseEvent uses 'timestamp', not 'created_at'
            'created_at': event.get('created_at') or event.get('timestamp'),
            'updated_at': event.get('updated_at') or event.get('timestamp'),
        }

    @staticmethod
    def _transform_participant_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform participant event"""
        return {
            'chat_id': str(event.get('chat_id', '')) if event.get('chat_id') else None,
            'user_id': str(event.get('user_id', '')) if event.get('user_id') else None,
            'user_name': event.get('user_name'),
            'role': event.get('role', 'member'),
            'is_active': event.get('is_active', True),
            # BaseEvent uses 'timestamp', not 'joined_at'
            'joined_at': event.get('joined_at') or event.get('timestamp'),
            'left_at': event.get('left_at'),
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
