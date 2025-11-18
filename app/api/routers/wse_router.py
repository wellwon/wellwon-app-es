# app/api/routers/wse_router.py
# =============================================================================
# File: app/api/routers/wse_router.py
# Description: WebSocket Events router for 
# =============================================================================

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, Header, Cookie, Request
from starlette import status
from starlette.websockets import WebSocketState

from app.wse.websocket.wse_connection import WSEConnection
from app.wse.websocket.wse_handlers import WSEHandler
from app.wse.dependencies import get_snapshot_service
from app.wse.services.snapshot_service import SnapshotServiceProtocol
from app.security.jwt_auth import JwtTokenManager

log = logging.getLogger("wellwon.wse_router")
router = APIRouter()

# Constants
PROTOCOL_VERSION = 2
DEFAULT_TOPICS = [
    'broker_connection_events',
    'broker_account_events',
    'user_account_events',
    'system_events',
    'monitoring_events'
]

# Module-level tracking for sync requests
_sync_request_tracking: Dict[str, datetime] = {}
_sync_tracking_lock = asyncio.Lock()
_cleanup_task: Optional[asyncio.Task] = None


async def _cleanup_sync_tracking():
    """Periodically clean up old sync tracking entries"""
    global _sync_request_tracking

    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes

            async with _sync_tracking_lock:
                current_time = datetime.now(timezone.utc)
                cutoff_time = current_time - timedelta(minutes=5)

                # Remove entries older than 5 minutes
                old_count = len(_sync_request_tracking)
                _sync_request_tracking = {
                    k: v for k, v in _sync_request_tracking.items()
                    if v > cutoff_time
                }
                removed_count = old_count - len(_sync_request_tracking)

                if removed_count > 0:
                    log.info(f"Cleaned up {removed_count} old sync tracking entries")

        except asyncio.CancelledError:
            log.info("Sync tracking cleanup task cancelled")
            break
        except Exception as e:
            log.error(f"Error in sync tracking cleanup: {e}")


def _ensure_cleanup_task():
    """Ensure the cleanup task is running"""
    global _cleanup_task

    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_cleanup_sync_tracking())
        log.debug("Started sync tracking cleanup task")


@router.on_event("startup")
async def startup_event():
    """Initialize router resources on startup"""
    _ensure_cleanup_task()


@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup router resources on shutdown"""
    global _cleanup_task

    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        log.info("Sync tracking cleanup task stopped")


@router.websocket("/wse")
async def websocket_endpoint(
        websocket: WebSocket,
        token: Optional[str] = Query(None, description="JWT token"),
        authorization: Optional[str] = Header(None),
        access_token: Optional[str] = Cookie(None),  # Cookie-based auth support
        client_version: Optional[str] = Query("unknown", description="Client version"),
        protocol_version: Optional[int] = Query(2, description="Protocol version"),
        topics: Optional[str] = Query(None, description="Initial topics to subscribe"),
        compression: Optional[bool] = Query(True, description="Enable compression"),
        encryption: Optional[bool] = Query(False, description="Enable encryption"),
        message_signing: Optional[bool] = Query(False, description="Selective signing for critical operations (Binance/Coinbase pattern)"),
        snapshot_service: SnapshotServiceProtocol = Depends(get_snapshot_service)
) -> None:
    """
    Enhanced WebSocket endpoint with full useWSE.ts compatibility

    Query Parameters:
        token: JWT authentication token
        client_version: Client application version
        protocol_version: WebSocket protocol version (default: 2)
        topics: Comma-separated list of initial topics to subscribe
        compression: Enable message compression (default: true)
        encryption: Enable message encryption (default: false)
    """

    # Declare global variables that will be accessed
    global _sync_request_tracking

    # Ensure cleanup task is running
    _ensure_cleanup_task()

    # Accept the connection first to send proper error messages
    await websocket.accept()

    # Enhanced logging for debugging
    client_ip = websocket.client.host if websocket.client else "unknown"
    log.info(
        f"WebSocket connection attempt - "
        f"Client: {client_version}, "
        f"Protocol: {protocol_version}, "
        f"IP: {client_ip}"
    )

    # Extract token with multiple fallbacks
    token_to_validate = None
    token_source = None

    # 1. Try query parameter
    if token and token not in ['undefined', 'null', '', 'bearer']:
        token_to_validate = token
        token_source = "query"
        log.debug("Token found in query parameter")

    # 2. Try Authorization header
    elif authorization and authorization not in ['undefined', 'null', '']:
        if authorization.startswith("Bearer "):
            token_to_validate = authorization[7:]
            token_source = "bearer"
            log.debug("Token extracted from Bearer header")
        elif authorization.startswith("Token "):
            token_to_validate = authorization[6:]
            token_source = "token_header"
            log.debug("Token extracted from Token header")
        elif len(authorization.split('.')) == 3:  # Looks like a JWT
            token_to_validate = authorization
            token_source = "raw_header"
            log.debug("Raw token found in Authorization header")

    # 3. Try cookie
    elif access_token and access_token not in ['undefined', 'null', '']:
        token_to_validate = access_token
        token_source = "cookie"
        log.debug("Token extracted from cookie")

    # 4. Try WebSocket scope cookies
    if not token_to_validate:
        cookies = websocket.scope.get("cookies", {})
        for cookie_name in ['access_token', 'jwt', 'token', 'auth_token']:
            if cookie_name in cookies:
                token_to_validate = cookies[cookie_name]
                if token_to_validate and token_to_validate not in ['undefined', 'null', '']:
                    token_source = f"scope_cookie_{cookie_name}"
                    log.debug(f"Token extracted from scope cookie: {cookie_name}")
                    break
                else:
                    token_to_validate = None

    # Validate token
    user_id = None
    auth_error = None
    auth_details = {}

    if token_to_validate:
        log.info(
            f"Validating token - "
            f"Source: {token_source}, "
            f"Length: {len(token_to_validate)}, "
            f"Prefix: {token_to_validate[:20]}..."
        )

        try:
            # Use JWT manager with better error handling
            token_manager = JwtTokenManager()

            # First check if token is valid format
            try:
                # Decode without verification first to check structure
                import jwt as pyjwt
                unverified_payload = pyjwt.decode(
                    token_to_validate,
                    options={"verify_signature": False}
                )

                log.debug(f"Token structure valid, claims: {list(unverified_payload.keys())}")

                # Now verify the token properly
                payload = token_manager.decode_token_payload(token_to_validate)

                if payload:
                    user_id_str = payload.get("sub") or payload.get("user_id")
                    if user_id_str:
                        user_id = UUID(user_id_str)
                        log.info(f"Token validated successfully for user: {user_id}")
                        auth_details = {
                            "user_id": str(user_id),
                            "token_source": token_source,
                            "exp": payload.get("exp"),
                            "iat": payload.get("iat")
                        }
                    else:
                        auth_error = "Token missing user identification"
                        auth_details = {"missing_fields": ["sub", "user_id"]}
                else:
                    auth_error = "Token validation failed"
                    auth_details = {"validation_error": "decode_returned_none"}

            except pyjwt.ExpiredSignatureError:
                auth_error = "Token has expired"
                auth_details = {"error_type": "expired"}
            except pyjwt.InvalidTokenError as e:
                auth_error = f"Invalid token: {str(e)}"
                auth_details = {"error_type": "invalid_token", "detail": str(e)}
            except Exception as e:
                log.error(f"Token decode error: {e}", exc_info=True)
                auth_error = f"Token validation failed: {str(e)}"
                auth_details = {"error_type": "decode_error", "detail": str(e)}

        except Exception as e:
            auth_error = f"Authentication error: {str(e)}"
            auth_details = {"error_type": "auth_error", "detail": str(e)}
            log.error(auth_error, exc_info=True)
    else:
        auth_error = "No authentication token provided"
        auth_details = {
            "searched_locations": ["query", "header", "cookie", "scope"],
            "hint": "Please provide token via query parameter 'token' or Authorization header"
        }

    # Handle authentication failure gracefully
    if not user_id:
        log.warning(
            f"WebSocket authentication failed - "
            f"Error: {auth_error}, "
            f"Details: {auth_details}"
        )

        # Send informative error message
        error_message = {
            't': 'error',
            'p': {
                'message': auth_error or "Authentication failed",
                'code': 'AUTH_FAILED',
                'recoverable': False,
                'details': {
                    **auth_details,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'hint': 'Please ensure you are logged in and try again',
                    'protocol_version': protocol_version,
                    'client_version': client_version
                }
            }
        }

        try:
            await websocket.send_json(error_message)
            log.debug("Auth error message sent to client")
        except Exception as e:
            log.error(f"Failed to send auth error: {e}")

        # Close with appropriate code
        await websocket.close(code=4401, reason="Authentication required")
        return

    # Generate connection ID
    conn_id = f"ws_{user_id.hex[:8]}_{uuid.uuid4().hex[:8]}"

    log.info(
        f"WebSocket v{protocol_version} connection authenticated - "
        f"User: {user_id}, "
        f"ConnID: {conn_id}, "
        f"Client: {client_version}, "
        f"Compression: {compression}, "
        f"Encryption: {encryption}"
    )

    # Get services from app state
    app = websocket.scope.get("app")
    if not app:
        # Try alternative ways to get app
        request = websocket.scope.get("request")
        if request and hasattr(request, 'app'):
            app = request.app
        else:
            log.error("Cannot access app state from WebSocket scope")
            try:
                await websocket.send_json({
                    't': 'error',
                    'p': {
                        'message': 'Server configuration error - app state not available',
                        'code': 'SERVER_ERROR',
                        'recoverable': False,
                        'details': {
                            'error_type': 'app_state_missing',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    }
                })
            except Exception:
                pass
            await websocket.close(code=1011, reason="Server configuration error")
            return

    # Get PubSubBus from app.state
    try:
        event_bus = getattr(app.state, 'pubsub_bus', None)
        if not event_bus:
            raise RuntimeError("PubSubBus not available in app.state")
        log.debug("PubSubBus obtained successfully")

        # PubSubBus is ephemeral - no cleanup needed!
        # Messages are broadcast in real-time and not stored
        log.debug(f"PubSubBus ready for user {user_id}")

    except Exception as e:
        log.error(f"Failed to get event bus: {e}", exc_info=True)
        try:
            await websocket.send_json({
                't': 'error',
                'p': {
                    'message': f'Failed to initialize event bus: {str(e)}',
                    'code': 'INIT_ERROR',
                    'recoverable': False,
                    'details': {
                        'error_type': 'event_bus_init',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                }
            })
        except Exception:
            pass
        await websocket.close(code=1011, reason="Event bus initialization failed")
        return

    # Get optional services
    broker_interaction_service = None
    adapter_monitoring_service = None

    if hasattr(app, 'state'):
        broker_interaction_service = getattr(app.state, "broker_interaction_service", None)
        adapter_monitoring_service = getattr(app.state, "adapter_monitoring_service", None)
        # Inject query_bus into snapshot service if not already set
        if hasattr(snapshot_service, 'query_bus') and snapshot_service.query_bus is None:
            query_bus = getattr(app.state, 'query_bus', None)
            if query_bus:
                snapshot_service.query_bus = query_bus
        # Inject streaming_health_monitor for real streaming status (FACADE, not lifecycle manager!)
        if hasattr(snapshot_service, 'streaming_health_monitor') and snapshot_service.streaming_health_monitor is None:
            if adapter_monitoring_service and hasattr(adapter_monitoring_service, 'streaming_health_monitor'):
                snapshot_service.streaming_health_monitor = adapter_monitoring_service.streaming_health_monitor

    connection = WSEConnection(
        conn_id=conn_id,
        user_id=str(user_id),
        ws=websocket,
        event_bus=event_bus,
        protocol_version=protocol_version,
        compression_enabled=compression,
        encryption_enabled=encryption,
        message_signing_enabled=message_signing,  # Industry standard: selective signing (Binance/Coinbase pattern)
        broker_interaction_service=broker_interaction_service,
        adapter_monitoring_service=adapter_monitoring_service
    )

    # Create message handler with snapshot service
    message_handler = WSEHandler(connection, snapshot_service=snapshot_service)

    try:
        # Initialize connection
        await connection.initialize()
        log.debug(f"Connection {conn_id} initialized")

        # Send ready event with detailed info
        await connection.send_message({
            't': 'server_ready',
            'p': {
                'message': 'Connection established',
                'details': {
                    'version': protocol_version,
                    'client_version': client_version,
                    'features': {
                        'compression': compression,
                        'encryption': encryption,
                        'batching': True,
                        'priority_queue': True,
                        'circuit_breaker': True,
                        'offline_queue': False,
                        'message_signing': connection.security_manager.message_signing_enabled,
                        'health_check': True,
                        'metrics': True
                    },
                    'connection_id': conn_id,
                    'server_time': datetime.now(timezone.utc).isoformat(),
                    'user_id': str(user_id),
                    'auth_source': token_source,
                    'endpoints': {
                        'primary': f"ws://{websocket.client.host}/ws/events" if websocket.client else None,
                        'health_check_interval': 30000,
                        'heartbeat_interval': 15000
                    }
                }
            }
        }, priority=10)

        # FIXED: Track sync requests to prevent duplicates using datetime
        async with _sync_tracking_lock:
            sync_key = f"{user_id}_last_sync"
            last_sync_time = _sync_request_tracking.get(sync_key)
            current_time = datetime.now(timezone.utc)

            # If a sync was done in the last 5 seconds, skip initial sync
            should_skip_initial_sync = False
            if last_sync_time:
                time_since_last_sync = (current_time - last_sync_time).total_seconds()
                should_skip_initial_sync = time_since_last_sync < 5

            if should_skip_initial_sync:
                log.info(f"Skipping initial sync for user {user_id} - sync done {time_since_last_sync:.1f}s ago")
                initial_topics = []  # Don't auto-subscribe if recently synced
            else:
                # Handle initial topic subscriptions normally
                initial_topics = []
                if topics:
                    initial_topics = [t.strip() for t in topics.split(',') if t.strip()]

                if not initial_topics:
                    initial_topics = DEFAULT_TOPICS

                # Update sync tracking
                _sync_request_tracking[sync_key] = current_time

            # Clean old entries periodically
            if len(_sync_request_tracking) > 1000:
                # Remove entries older than 1 minute
                cutoff_time = current_time - timedelta(minutes=1)
                _sync_request_tracking = {
                    k: v for k, v in _sync_request_tracking.items()
                    if v > cutoff_time
                }

        if initial_topics:
            log.info(f"Initial subscription topics: {initial_topics}")

            # Subscribe to initial topics
            await message_handler.handle_subscription({
                't': 'subscription',
                'p': {
                    'action': 'subscribe',
                    'topics': initial_topics
                }
            })
        else:
            log.info("No initial topic subscriptions due to recent sync")

        log.info(f"WebSocket {conn_id} connected and initialized successfully")

        # Main message loop
        while connection._running:
            try:
                # Receive messages with timeout
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=1.0  # 1 second timeout for checking connection state
                )

                if message['type'] == 'websocket.receive':
                    if 'text' in message:
                        data = message['text']
                        parsed = await connection.handle_incoming(data)

                        if parsed:
                            await message_handler.handle_message(parsed)

                    elif 'bytes' in message:
                        data = message['bytes']
                        parsed = await connection.handle_incoming(data)

                        if parsed:
                            await message_handler.handle_message(parsed)

                elif message['type'] == 'websocket.disconnect':
                    log.info(f"WebSocket {conn_id} disconnect message received")
                    break

            except asyncio.TimeoutError:
                # Timeout is normal - continue to check connection state
                continue

            except WebSocketDisconnect:
                log.info(f"WebSocket {conn_id} disconnected")
                break

            except Exception as e:
                log.error(f"WebSocket {conn_id} error: {e}", exc_info=True)
                connection.circuit_breaker.record_failure()

                # Check if circuit breaker is open (use get_state_sync() method)
                if connection.circuit_breaker.get_state_sync() == "OPEN":
                    log.warning(f"Circuit breaker OPEN for {conn_id}, closing connection")

                    # Send error before closing
                    try:
                        await connection.send_message({
                            't': 'error',
                            'p': {
                                'message': 'Server error - circuit breaker activated',
                                'code': 'CIRCUIT_BREAKER_OPEN',
                                'recoverable': False,
                                'details': {
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                            }
                        }, priority=10)
                    except Exception:
                        pass

                    await websocket.close(code=1011, reason="Server error")
                    break

    except Exception as e:
        log.error(f"WebSocket {conn_id} initialization error: {e}", exc_info=True)

        # Try to send detailed error message
        try:
            await websocket.send_json({
                't': 'error',
                'p': {
                    'message': f'Initialization failed: {str(e)}',
                    'code': 'INIT_ERROR',
                    'recoverable': False,
                    'details': {
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                }
            })
        except Exception:
            pass

    finally:
        # Clean up connection
        try:
            await connection.cleanup()
        except Exception as e:
            log.error(f"Error during connection cleanup: {e}")

        # Close WebSocket if still open
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=1000, reason="Normal closure")
            except Exception:
                pass

        # Log final metrics
        try:
            metrics = connection.metrics.to_dict()
            duration = (datetime.now(timezone.utc) - connection.metrics.connected_since).total_seconds()
            log.info(
                f"WebSocket {conn_id} closed - "
                f"Duration: {duration:.1f}s, "
                f"Messages: {metrics['messages_sent']}/{metrics['messages_received']}, "
                f"Compression ratio: {metrics['compression_ratio']:.2f}"
            )
        except Exception as e:
            log.error(f"Error logging final metrics: {e}")


@router.get("/ws/health")
async def websocket_health_check(request: Request):
    """Health check endpoint for WebSocket service"""
    try:
        # Get PubSubBus from app.state
        pubsub_bus = getattr(request.app.state, 'pubsub_bus', None)
        if not pubsub_bus:
            return {
                "status": "unhealthy",
                "websocket_service": "error",
                "error": "PubSubBus not available",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        metrics = pubsub_bus.get_metrics()
        is_healthy = metrics.get('running', False)

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "websocket_service": "active",
            "pubsub_bus": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "websocket_service": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/ws/compression-test")
async def compression_test():
    """Test compression functionality"""
    from app.wse.websocket.wse_compression import CompressionManager

    cm = CompressionManager()

    # Test data of various sizes
    test_cases = [
        {"size": 500, "data": "x" * 500},  # Below threshold
        {"size": 1500, "data": "x" * 1500},  # Above threshold, repetitive
        {"size": 2000, "data": ''.join(str(i % 10) for i in range(2000))},  # Less repetitive
        {"size": 5000, "data": json.dumps({"test": "data" * 100, "array": list(range(1000))})}  # JSON data
    ]

    results = []

    for case in test_cases:
        data = case["data"].encode('utf-8')
        original_size = len(data)

        try:
            # Test compression
            compressed = cm.compress(data)
            compressed_size = len(compressed)
            ratio = compressed_size / original_size

            # Test decompression
            decompressed = cm.decompress(compressed)
            decompression_success = decompressed == data

            results.append({
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": round(ratio, 3),
                "saved_bytes": original_size - compressed_size,
                "saved_percentage": round((1 - ratio) * 100, 1),
                "decompression_success": decompression_success,
                "should_compress": cm.should_compress(data),
                "beneficial": ratio < 0.9  # 10% reduction threshold
            })

        except Exception as e:
            results.append({
                "original_size": original_size,
                "error": str(e)
            })

    return {
        "compression_threshold": cm.COMPRESSION_THRESHOLD,
        "compression_level": cm.COMPRESSION_LEVEL,
        "test_results": results,
        "stats": cm.get_stats(),
        "recommendation": "Compression is most effective for repetitive or structured data > 1KB"
    }


@router.get("/ws/debug")
async def websocket_debug_info(request: Request):
    """Debug endpoint to check WebSocket service status"""
    # Declare global variable
    global _sync_request_tracking

    try:
        # Get PubSubBus from app.state
        pubsub_bus = getattr(request.app.state, 'pubsub_bus', None)
        pubsub_metrics = pubsub_bus.get_metrics() if pubsub_bus else None

        # Get sync tracking info
        async with _sync_tracking_lock:
            current_time = datetime.now(timezone.utc)
            sync_info = {
                "active_users": len(_sync_request_tracking),
                "recent_syncs": [
                    {
                        "user_id": user_id,
                        "last_sync": last_sync.isoformat(),
                        "seconds_ago": (current_time - last_sync).total_seconds()
                    }
                    for user_id, last_sync in _sync_request_tracking.items()
                    if (current_time - last_sync).total_seconds() < 60  # Last minute
                ]
            }

        return {
            "status": "active",
            "pubsub_bus": pubsub_metrics,
            "sync_tracking": sync_info,
            "protocol_version": PROTOCOL_VERSION,
            "default_topics": DEFAULT_TOPICS,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cleanup_task_running": _cleanup_task is not None and not _cleanup_task.done()
        }
    except Exception as e:
        log.error(f"Debug endpoint error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }