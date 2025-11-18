# =============================================================================
# File: app/wse/core/event_transformer.py
# Description: Event Transformation Between Internal and WebSocket Formats
# =============================================================================

"""
EventTransformer for WSE

Transforms internal domain events to WebSocket-compatible format.

Architecture:
    Internal Domain Event → EventTransformer → WebSocket Event (v2)

WebSocket Event Format (v2):
    {
        "v": 2,                          # Protocol version
        "id": "evt_123",                 # Event ID
        "t": "order_update",             # Event type (mapped from internal)
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
    2. Map internal event type → WebSocket event type
    3. Transform payload (domain-specific)
    4. Calculate latency for monitoring
    5. Add metadata (correlation, tracing, priority)

Supported Event Types:
    - broker_connection_update
    - broker_module_health_update
    - account_update, account_remove
    - position_update
    - order_update
    - strategy_update
    - system_announcement
    - broker_status_remove

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
                # Parse event timestamp
                if isinstance(event_timestamp_str, str):
                    event_timestamp = datetime.fromisoformat(event_timestamp_str.replace('Z', '+00:00'))
                elif isinstance(event_timestamp_str, datetime):
                    event_timestamp = event_timestamp_str
                else:
                    event_timestamp = None

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

        # CRITICAL FIX (Nov 16, 2025): Preserve original event type for specific handlers
        # Problem: Handler at wse_handlers.py:1253 needs to detect saga completion events
        # Solution: When event_type is transformed (e.g., BrokerConnectionEstablishedSagaCompleted → broker_connection_update),
        # preserve the original type so handlers can identify specific events
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
        if ws_event_type == 'broker_connection_update' or ws_event_type == 'broker_status_update':
            return EventTransformer._transform_broker_connection(event)
        elif ws_event_type == 'broker_module_health_update':
            return EventTransformer._transform_module_health(event)
        elif ws_event_type == 'account_update':
            return EventTransformer._transform_account(event)
        elif ws_event_type == 'position_update':
            return EventTransformer._transform_position(event)
        elif ws_event_type == 'order_update':
            return EventTransformer._transform_order(event)
        elif ws_event_type == 'strategy_update':
            return EventTransformer._transform_strategy(event)
        elif ws_event_type == 'system_announcement':
            return EventTransformer._transform_system_announcement(event)
        elif ws_event_type == 'broker_status_remove':
            return EventTransformer._transform_broker_remove(event)
        elif ws_event_type == 'account_remove':
            return EventTransformer._transform_account_remove(event)
        else:
            # Default transformation - extract payload
            return EventTransformer._extract_payload(event)

    @staticmethod
    def _transform_broker_connection(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform broker connection event to WsBrokerConnectionInfo format"""

        # Log the incoming event for debugging
        log.info(f"[TRANSFORMER DEBUG] _transform_broker_connection RECEIVED event: {event}")
        log.debug(f"=== TRANSFORMING BROKER CONNECTION EVENT ===")
        log.debug(f"Event type: {event.get('event_type', event.get('type', 'unknown'))}")
        log.debug(f"Connected: {event.get('connected')}, Is Healthy: {event.get('is_healthy')}")
        log.debug(f"Status: {event.get('new_status', event.get('status', 'unknown'))}")

        # Ensure we have the event type
        event_type = event.get('event_type', event.get('type', ''))

        # CRITICAL FIX (Nov 15, 2025): Extract data first to check nested fields
        # Domain publisher wraps transformed data in 'data' field, so status is inside data!
        data = event.get('data', {})

        # Map internal status to frontend-expected status
        # Check data object first (where domain_publisher puts it), then fall back to top level
        status = data.get('status', event.get('new_status', event.get('status', 'UNKNOWN')))

        # Handle different status formats (Enums, strings, etc.)
        if hasattr(status, 'value'):
            status = status.value
        status = str(status)  # Ensure it's a string

        # FIXED: Handle environment properly
        environment = event.get('environment', 'paper')

        # Handle enum values
        if hasattr(environment, 'value'):
            environment = environment.value
        elif isinstance(environment, str):
            # Handle string representations like "EnvironmentType.LIVE"
            if environment.startswith('EnvironmentType.'):
                # Extract the actual value from string representation
                environment = environment.split('.')[-1].lower()
            elif environment.upper() in ['LIVE', 'SIM', 'PAPER']:
                # Normalize to lowercase
                environment = environment.lower()

        # Ensure environment is valid
        if environment not in ['live', 'sim', 'paper']:
            log.warning(f"Invalid environment value: {environment}, defaulting to 'paper'")
            environment = 'paper'

        # Determine final status based on event type and available data
        final_status = 'DISCONNECTED'  # Default

        # CRITICAL FIX (Nov 15, 2025): Infer status from event type for events without 'connected'/'status' fields
        # PROBLEM: When user clicks Connect, aggregate emits 3 events:
        #   1. BrokerConnectionInitiated (no fields) -> was defaulting to DISCONNECTED
        #   2. BrokerApiCredentialsStored (no fields) -> was defaulting to DISCONNECTED
        #   3. BrokerConnectionEstablished (connected=True) -> CONNECTED
        # This caused "3 disconnect updates" to appear on Connect button click

        # Event type to status inference map (for events without explicit status fields)
        event_type_status_map = {
            # Connection lifecycle events
            'BrokerConnectionInitiated': 'CONNECTING',
            'BrokerApiCredentialsStored': 'CONNECTING',
            'BrokerOAuthClientCredentialsStored': 'CONNECTING',
            'BrokerOAuthFlowStarted': 'CONNECTING',
            'BrokerTokensSuccessfullyStored': 'CONNECTING',
            'BrokerApiEndpointConfigured': 'CONNECTING',
            'BrokerConnectionEstablished': 'CONNECTED',
            'BrokerConnectionRestored': 'CONNECTED',
            'BrokerConnectionEstablishedSagaCompleted': 'CONNECTED',

            # Token refresh (don't change connection status)
            'BrokerTokensSuccessfullyRefreshed': None,  # Don't update connection status

            # Disconnection events
            'BrokerConnectionAttemptFailed': 'ERROR',
            'BrokerDisconnected': 'DISCONNECTED',
        }

        # Step 1: Check if event type has explicit status mapping
        inferred_status = event_type_status_map.get(event_type)
        if inferred_status is not None:
            final_status = inferred_status
            log.debug(f"[FIX] {event_type} inferred status from event type: {final_status}")
        # Step 2: Check for explicit 'connected' field (overrides event type inference)
        elif event_type in ['BrokerConnectionEstablished', 'BrokerConnectionRestored']:
            # Check both data object and top level for connected field
            connected = data.get('connected', event.get('connected'))
            if connected is not None:
                final_status = 'CONNECTED' if connected else 'DISCONNECTED'
                log.debug(f"[FIX] {event_type} using 'connected' field: {connected} -> {final_status}")
            else:
                # These events should ALWAYS have connected=True by definition
                final_status = 'CONNECTED'
                log.warning(f"[FIX] {event_type} missing 'connected' field, defaulting to CONNECTED")
        elif event_type == 'BrokerConnectionHealthChecked':
            # Priority order for determining status:
            # 1. Explicit 'connected' field
            # 2. 'is_healthy' field
            # 3. 'health_status' string analysis

            # Check both data object and top level for connected field
            connected = data.get('connected', event.get('connected'))
            is_healthy = data.get('is_healthy', event.get('is_healthy'))

            if connected is not None:
                final_status = 'CONNECTED' if connected else 'DISCONNECTED'
                log.debug(f"Using 'connected' field: {connected} -> {final_status}")
            elif is_healthy is not None:
                if is_healthy:
                    final_status = 'CONNECTED'
                else:
                    # Check if it's an auth issue
                    health_status_str = str(data.get('health_status', event.get('health_status', ''))).lower()
                    if any(auth_word in health_status_str for auth_word in
                           ['auth', 'reauth', 'authentication', 'unauthorized']):
                        final_status = 'NEEDS_REAUTHENTICATION'
                    else:
                        final_status = 'DISCONNECTED'
                log.debug(f"Using 'is_healthy' field: {is_healthy} -> {final_status}")
            else:
                # Fallback to analyzing health_status string
                health_status_str = str(data.get('health_status', event.get('health_status', ''))).lower()
                if any(connected_word in health_status_str for connected_word in ['healthy', 'connected', 'active']):
                    final_status = 'CONNECTED'
                elif any(auth_word in health_status_str for auth_word in ['auth', 'reauth', 'authentication']):
                    final_status = 'NEEDS_REAUTHENTICATION'
                else:
                    final_status = 'DISCONNECTED'
                log.debug(f"Using health_status string analysis: '{health_status_str}' -> {final_status}")
        else:
            # For other event types, use status mapping
            status_upper = status.upper()
            status_map = {
                'CONNECTED': 'CONNECTED',
                'CONNECTING': 'CONNECTING',
                'DISCONNECTED': 'DISCONNECTED',
                'ERROR': 'ERROR',
                'PENDING': 'PENDING',
                'CONNECTION_LOST': 'DISCONNECTED',
                'REAUTH_REQUIRED': 'NEEDS_REAUTHENTICATION',
                'NEEDS_REAUTHENTICATION': 'NEEDS_REAUTHENTICATION',
                'UNKNOWN': 'DISCONNECTED',
            }
            final_status = status_map.get(status_upper, 'DISCONNECTED')
            log.debug(f"Using status mapping: {status_upper} -> {final_status}")

        # CRITICAL FIX (2025-11-15): Extract broker_id from correct location
        # Domain events come directly with broker_id, but domain_publisher wraps in "data" field
        # Check both locations for compatibility (data already extracted above)
        broker_id = event.get('broker_id') or data.get('broker_id')
        broker_connection_id = event.get('broker_connection_id') or data.get('broker_connection_id')

        # DEBUG: Log event structure to diagnose broker_id extraction (temporary)
        if event.get('event_type') == 'broker_connection_update':
            log.info(
                f"[EventTransformer] DEBUG Event structure for broker_connection_update:\n"
                f"  Top-level broker_id: {event.get('broker_id')}\n"
                f"  Nested data.broker_id: {data.get('broker_id')}\n"
                f"  Top-level keys: {list(event.keys())}\n"
                f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}\n"
                f"  Final broker_id: {broker_id}"
            )

        if not broker_id:
            log.error(
                f"[EventTransformer] CRITICAL: Missing broker_id in event. "
                f"Event type: {event.get('event_type')}, "
                f"Connection ID: {broker_connection_id}. "
                f"This should have been filtered by domain_publisher!"
            )
            # No fallback - let it fail if broker_id is truly missing
            # This forces proper validation upstream

        if not broker_connection_id:
            log.error(
                f"[EventTransformer] CRITICAL: Missing broker_connection_id in event. "
                f"Event type: {event.get('event_type')}, "
                f"Broker ID: {broker_id}. "
                f"This should have been filtered by domain_publisher!"
            )

        # Build the transformed event - NO FALLBACKS!
        # If broker_id is None, we pass it through and let downstream validation catch it
        transformed = {
            'broker_connection_id': str(broker_connection_id) if broker_connection_id else '',
            'broker_id': broker_id,  # No fallback - pass actual value (even if None)
            'environment': environment,  # FIXED: Use properly serialized environment
            'status': final_status,
            'reauth_required': bool(event.get('reauth_required', False) or final_status == 'NEEDS_REAUTHENTICATION'),
            'message': (
                    event.get('message') or
                    event.get('reason') or
                    event.get('status_message') or
                    event.get('health_status') or
                    f"Status: {final_status}"
            ),
            'last_connected_at': event.get('last_connected_at'),
            'last_heartbeat_at': event.get('last_heartbeat_at') or event.get('checked_at'),
            'api_endpoint': event.get('api_endpoint') or event.get('api_endpoint_used'),
            'adapter_type': event.get('adapter_type', 'modular'),
            'modules': event.get('module_health'),
            'response_time_ms': event.get('response_time_ms'),
            'is_healthy': bool(data.get('is_healthy', event.get('is_healthy', final_status == 'CONNECTED'))),
            'connected': bool(data.get('connected', event.get('connected', final_status == 'CONNECTED')))
        }

        # Ensure consistency between fields
        if transformed['status'] == 'CONNECTED':
            transformed['is_healthy'] = True
            transformed['connected'] = True
        elif transformed['status'] == 'DISCONNECTED' or transformed['status'] == 'ERROR':
            transformed['is_healthy'] = False
            transformed['connected'] = False

        # Log the transformation result
        log.debug(f"=== TRANSFORMATION RESULT ===")
        log.debug(f"Final status: {final_status}")
        log.debug(f"Environment: {transformed['environment']}")
        log.debug(f"Is healthy: {transformed['is_healthy']}")
        log.debug(f"Connected: {transformed['connected']}")

        return transformed

    @staticmethod
    def _transform_module_health(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform module health event"""
        # Log incoming event for debugging
        log.debug(f"Transforming module health event: {event.get('event_type', 'unknown')}")

        # Get broker_connection_id with validation
        broker_connection_id = event.get('broker_connection_id', '')
        if not broker_connection_id:
            log.warning("Module health event missing broker_connection_id")

        broker_connection_id = str(broker_connection_id)

        # Check if this is already a bundled update
        if 'module_updates' in event:
            # Already bundled, ensure all values are serializable
            module_updates = {}
            for module_name, module_data in event['module_updates'].items():
                if isinstance(module_data, dict):
                    # Ensure all timestamps are strings
                    if 'last_checked' in module_data and hasattr(module_data['last_checked'], 'isoformat'):
                        module_data['last_checked'] = module_data['last_checked'].isoformat()
                    module_updates[module_name] = module_data
                else:
                    # Handle unexpected format
                    log.warning(f"Unexpected module data format for {module_name}: {type(module_data)}")
                    module_updates[module_name] = {
                        'module_id': module_name,
                        'module_type': module_name,
                        'is_healthy': False,
                        'status': 'unknown',
                        'message': f"Invalid module data format: {type(module_data)}",
                        'last_checked': datetime.now(timezone.utc).isoformat(),
                    }

            result = {
                'broker_connection_id': broker_connection_id,
                'module_updates': module_updates
            }
        else:
            # Single module update (legacy format)
            module_name = event.get('module_name', 'unknown')

            result = {
                'broker_connection_id': broker_connection_id,
                'module_updates': {
                    module_name: {
                        'module_id': module_name,
                        'module_type': module_name,
                        'is_healthy': bool(event.get('is_healthy', False)),
                        'status': 'healthy' if event.get('is_healthy') else 'unhealthy',
                        'message': event.get('message', ''),
                        'details': event.get('error_details'),
                        'last_checked': datetime.now(timezone.utc).isoformat(),
                    }
                }
            }

        log.debug(f"Transformed module health result: {result}")
        return result

    @staticmethod
    def _transform_account(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform account event"""
        # DEBUG LOGGING (Nov 15, 2025): Track account event transformation
        log.info(f"[TRANSFORMER DEBUG] _transform_account RECEIVED event: {event}")

        broker_id = event.get('broker_id')
        if not broker_id:
            log.warning(
                f"[EventTransformer] Account event missing broker_id. "
                f"Account ID: {event.get('account_id')}, "
                f"Connection ID: {event.get('broker_connection_id')}, "
                f"FULL EVENT: {event}"
            )

        return {
            'id': str(event.get('account_id', event.get('id', ''))),
            'broker_connection_id': str(event.get('broker_connection_id', '')) if event.get(
                'broker_connection_id') else None,
            'broker_id': broker_id,  # No fallback - pass actual value
            'environment': event.get('environment', 'paper'),
            'asset_type': event.get('asset_type', 'UNKNOWN'),
            'broker_account_id': event.get('broker_account_id', ''),
            'account_name': event.get('account_name'),
            'balance': str(event.get('balance', 0)),
            'currency': event.get('currency', 'USD'),
            'equity': str(event.get('equity')) if event.get('equity') is not None else None,
            'buying_power': str(event.get('buying_power')) if event.get('buying_power') is not None else None,
            'status': event.get('status'),
            'account_type': event.get('account_type'),
            'metadata': event.get('metadata'),
            'deleted': event.get('deleted', False),
            'archived': event.get('archived', False),
            'last_synced_at': event.get('last_synced_at'),
            'created_at': event.get('created_at', datetime.now(timezone.utc).isoformat()),
            'updated_at': event.get('updated_at'),
            'positions': event.get('positions'),
            'open_orders_count': event.get('open_orders_count'),
            'daily_pnl': str(event.get('daily_pnl')) if event.get('daily_pnl') is not None else None,
            'daily_pnl_percent': str(event.get('daily_pnl_percent')) if event.get(
                'daily_pnl_percent') is not None else None,
        }

    @staticmethod
    def _transform_position(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform position event"""
        return {
            'symbol': event.get('symbol', ''),
            'quantity': str(event.get('quantity', 0)),
            'side': event.get('side', 'long'),
            'market_value': str(event.get('market_value', 0)) if event.get('market_value') else None,
            'avg_cost': str(event.get('avg_cost', 0)) if event.get('avg_cost') else None,
            'unrealized_pnl': str(event.get('unrealized_pnl', 0)) if event.get('unrealized_pnl') else None,
            'unrealized_pnl_percent': str(event.get('unrealized_pnl_percent', 0)) if event.get(
                'unrealized_pnl_percent') else None,
            'asset_class': event.get('asset_class'),
        }

    @staticmethod
    def _transform_order(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform order event"""
        return {
            'order_id': str(event.get('order_id', '')),
            'client_order_id': event.get('client_order_id'),
            'account_id': str(event.get('account_id', '')),
            'symbol': event.get('symbol', ''),
            'side': event.get('side', ''),
            'quantity': str(event.get('quantity', 0)),
            'order_type': event.get('order_type', ''),
            'status': event.get('status', ''),
            'filled_quantity': str(event.get('filled_quantity')) if event.get('filled_quantity') else None,
            'avg_fill_price': str(event.get('avg_fill_price')) if event.get('avg_fill_price') else None,
            'limit_price': str(event.get('limit_price')) if event.get('limit_price') else None,
            'stop_price': str(event.get('stop_price')) if event.get('stop_price') else None,
            'time_in_force': event.get('time_in_force'),
            'created_at': event.get('created_at', datetime.now(timezone.utc).isoformat()),
            'updated_at': event.get('updated_at'),
        }

    @staticmethod
    def _transform_strategy(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform strategy event"""
        return {
            'strategy_id': str(event.get('strategy_id', '')),
            'name': event.get('name'),
            'account_id': str(event.get('account_id', '')),
            'broker_id': event.get('broker_id'),
            'environment': event.get('environment'),
            'asset_type': event.get('asset_type'),
            'settings': event.get('settings') or event.get('parameters') or {},
            'active': event.get('active', False),
            'webhook_generated': event.get('webhook_generated', False),
            'status': event.get('status'),
            'last_execution': event.get('last_execution'),
            'next_execution': event.get('next_execution'),
            'error_message': event.get('error_message'),
            'created_at': event.get('created_at'),
            'updated_at': event.get('updated_at'),
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
    def _transform_broker_remove(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform broker remove event"""
        return {
            'broker_connection_id': str(event.get('broker_connection_id', '')),
            'broker_id': event.get('broker_id'),
            'environment': event.get('environment'),
            'reason': event.get('reason', 'Connection purged'),
        }

    @staticmethod
    def _transform_account_remove(event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform account remove event with enhanced metadata"""
        # Extract account identifiers
        account_id = str(event.get('account_id') or event.get('account_aggregate_id') or event.get('id', ''))
        broker_connection_id = event.get('broker_connection_id')

        # Determine deletion type and cascade flag
        event_type = event.get('event_type', '')
        deletion_type = event.get('deletion_type', 'hard')  # 'hard' or 'soft'
        is_cascade = 'Batch' in event_type or 'bulk' in event_type.lower()

        # Build transformed payload
        transformed = {
            'id': account_id,
            'account_id': account_id,
            'broker_id': event.get('broker_id'),
            'broker_account_id': event.get('broker_account_id'),  # External broker account ID
            'environment': event.get('environment'),
            'reason': event.get('reason', 'Account deleted'),
            'deletion_type': deletion_type,
            'cascade': is_cascade,  # True if deleted as part of broker disconnect
        }

        # Add broker_connection_id if present
        if broker_connection_id:
            transformed['broker_connection_id'] = str(broker_connection_id)

        # Add deletion timestamp if present
        if 'deleted_at' in event:
            transformed['deleted_at'] = event['deleted_at']

        return transformed

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
