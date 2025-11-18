# app/core/background_tasks.py
# =============================================================================
# File: app/core/background_tasks.py
# Description: Background task management
# =============================================================================

import asyncio
import logging
from app.core.fastapi_types import FastAPI

logger = logging.getLogger("tradecore.background")

# Global flag for background tasks (exported for backward compatibility)
_stop_requested = False


async def cleanup_outbox_periodically(app_instance: FastAPI) -> None:
    """Enhanced outbox cleanup with better error handling"""
    global _stop_requested

    while not _stop_requested:
        try:
            if hasattr(app_instance.state, 'outbox_service') and app_instance.state.outbox_service:
                # Clean up old published events (keep for 7 days)
                cleaned = await app_instance.state.outbox_service.cleanup_published_events(days_to_keep=7)
                if cleaned > 0:
                    logger.info(f"Cleaned {cleaned} old events from outbox")

                # Move stuck/failed events to dead letter queue
                dlq_count = await app_instance.state.outbox_service.move_to_dead_letter()
                if dlq_count > 0:
                    logger.warning(f"Moved {dlq_count} events to dead letter queue")

                # Log outbox stats
                stats = await app_instance.state.outbox_service.get_outbox_stats()
                pending_count = stats.get('pending', 0)

                if pending_count > 100:  # Alert if too many pending
                    logger.warning(f"High number of pending outbox events: {pending_count}")
                elif pending_count > 0:
                    logger.debug(f"Outbox stats: {pending_count} pending, {stats.get('published', 0)} published")

        except Exception as cleanup_error:
            logger.error(f"Error in outbox cleanup task: {cleanup_error}", exc_info=True)

        # Wait for next cleanup cycle (1 hour)
        await asyncio.sleep(3600)


async def reconciliation_task(app_instance: FastAPI) -> None:
    """
    Background task for EventStore reconciliation (Exactly-Once Delivery).

    Runs periodically to detect and fix orphaned events:
    - Events in KurrentDB (EventStore) but NOT in outbox table
    - Old pending events stuck in outbox

    Part of TRUE Exactly-Once Implementation (2025-11-13).
    Runs every 6 hours, checks last 24 hours of events.
    """
    global _stop_requested

    from datetime import datetime, timezone, timedelta
    from app.infra.event_store.reconciliation_service import EventStoreReconciliationService

    # Configuration
    interval_hours = 6
    lookback_hours = 24

    # Create reconciliation service
    event_store = getattr(app_instance.state, 'event_store', None)
    reconciliation_service = EventStoreReconciliationService(event_store=event_store)

    logger.info(
        f"Starting reconciliation task: interval={interval_hours}h, lookback={lookback_hours}h"
    )

    while not _stop_requested:
        try:
            # Wait for interval
            await asyncio.sleep(interval_hours * 3600)

            # Run reconciliation
            since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            count = await reconciliation_service.reconcile_orphaned_events(since)

            if count > 0:
                logger.warning(f"Reconciliation found and fixed {count} orphaned events")
            else:
                logger.debug("Reconciliation completed: no orphaned events found")

        except asyncio.CancelledError:
            logger.info("Reconciliation task cancelled")
            break

        except Exception as e:
            logger.error(f"Reconciliation task error: {e}", exc_info=True)
            # Continue running despite errors
            await asyncio.sleep(300)  # 5 min backoff on error


async def _streaming_restoration_task(adapter_monitoring_service, query_bus) -> None:
    """
    Background task for streaming restoration after server restart.

    Restores broker streaming for ALL connected brokers to ensure data integrity.
    This prevents race conditions and ensures order fills are never missed.

    PROTOCOL-AGNOSTIC: Works with all broker protocols:
    - Alpaca: WebSocket streaming
    - TradeStation: HTTP Chunks (Server-Sent Events)
    - Virtual: Simulated streaming

    Critical for:
    - Order fill tracking (real-time via broker streaming)
    - Position tracking and pyramiding
    - Risk management
    - P&L calculations

    Runs AFTER server startup complete (not during startup phase).

    REFACTORED (Phase 2): Now uses AdapterMonitoringService.restore_streaming_for_user()
    which delegates to StreamingLifecycleManager for proper separation of concerns.
    """
    try:
        # CRITICAL FIX: Wait longer for all services to be ready
        # This prevents race conditions with WSE connections from frontend
        # that also try to create adapters on user login
        await asyncio.sleep(3.0)

        logger.info("Starting streaming restoration for all connected brokers...")

        # Query for ALL connected brokers (regardless of automations or login status)
        from app.broker_connection.queries import GetAllConnectionsQuery

        query = GetAllConnectionsQuery(
            only_active=True,  # Only get connected brokers
            include_disconnected=False  # Exclude disconnected brokers
        )
        all_connections = await query_bus.query(query)

        if not all_connections:
            logger.info("No connected brokers found, skipping streaming restoration")
            return

        # Extract unique user IDs
        unique_users = {}
        for conn in all_connections:
            # Skip Virtual Broker - doesn't use real streaming (Redis-based simulation)
            if conn.broker_id == "virtual":
                continue

            user_id = conn.user_id
            if user_id not in unique_users:
                unique_users[user_id] = []
            unique_users[user_id].append({
                'broker_id': conn.broker_id,
                'environment': conn.environment,
                'connection_id': conn.id
            })

        logger.info(
            f"Found {len(all_connections)} connected broker(s) across {len(unique_users)} user(s)"
        )

        # Restore streaming for each user (REFACTORED: Now uses AdapterMonitoringService)
        total_restored = 0
        total_monitors_started = 0
        for user_id, connections in unique_users.items():
            try:
                # Restore streaming connections (market data + trading data)
                await adapter_monitoring_service.restore_streaming_for_user(user_id)

                # CRITICAL: Also start continuous monitoring (health checks)
                # This ensures broker_health_update and broker_streaming_update are published every 30s
                # Best practice: Startup initialization pattern (not event-driven)
                monitor_ids = await adapter_monitoring_service.start_user_monitoring(user_id)
                total_monitors_started += len(monitor_ids)

                logger.info(
                    f"Started {len(monitor_ids)} continuous monitors for user {user_id} "
                    f"(REST API + Streaming health checks)"
                )

                # Log each restored connection
                for conn_info in connections:
                    logger.info(
                        f"Restored streaming for user {user_id}: "
                        f"{conn_info['broker_id']} ({conn_info['environment']}) - "
                        f"connection: {conn_info['connection_id']}"
                    )

                total_restored += len(connections)

            except Exception as e:
                # CRITICAL FIX: Gracefully handle errors during restoration
                # This prevents one failed adapter from crashing the entire restoration
                # Common errors: lock contention, missing credentials, network issues
                error_msg = str(e)

                # Credentials not loaded yet - this is EXPECTED after restart
                # They will be loaded when user logs in
                if "No authentication credentials" in error_msg or "credentials" in error_msg.lower():
                    logger.info(
                        f"Skipped streaming restoration for user {user_id} "
                        f"({len(connections)} connection(s)) - credentials not yet loaded. "
                        f"Streaming will be established when user logs in."
                    )
                else:
                    # Other errors (network, lock contention, etc.) - log as warning
                    logger.warning(
                        f"Skipped streaming restoration for user {user_id} "
                        f"({len(connections)} connection(s)): {e}"
                    )
                    logger.debug(f"Restoration error details for user {user_id}", exc_info=True)

        logger.info(
            f"Streaming restoration complete: restored streaming for "
            f"{total_restored} connection(s) across {len(unique_users)} user(s)"
        )

    except Exception as e:
        logger.error(f"Error during streaming restoration: {e}", exc_info=True)


async def start_background_tasks(app: FastAPI) -> None:
    """Start all background tasks"""
    global _stop_requested
    _stop_requested = False

    # Start outbox cleanup task if outbox service is available
    if hasattr(app.state, 'outbox_service') and app.state.outbox_service:
        app.state.outbox_cleanup_task = asyncio.create_task(
            cleanup_outbox_periodically(app)
        )
        logger.info("Outbox cleanup task started")

    # Start reconciliation task (Exactly-Once Delivery)
    app.state.reconciliation_task = asyncio.create_task(
        reconciliation_task(app)
    )
    logger.info("EventStore reconciliation task started (interval=6h, lookback=24h)")

    # Start streaming restoration task for ALL connected brokers (REFACTORED: Phase 2)
    if (hasattr(app.state, 'adapter_monitoring_service') and app.state.adapter_monitoring_service and
        hasattr(app.state, 'query_bus') and app.state.query_bus):
        app.state.streaming_restoration_task = asyncio.create_task(
            _streaming_restoration_task(
                adapter_monitoring_service=app.state.adapter_monitoring_service,
                query_bus=app.state.query_bus
            )
        )
        logger.info("Streaming restoration task started for all connected brokers (using AdapterMonitoringService)")

    # Add other background tasks here as needed
    # Example:
    # if hasattr(app.state, 'monitoring_service') and app.state.monitoring_service:
    #     app.state.monitoring_task = asyncio.create_task(
    #         monitor_system_health(app)
    #     )


async def stop_background_tasks(app: FastAPI) -> None:
    """Stop all background tasks gracefully"""
    global _stop_requested
    _stop_requested = True

    # Cancel outbox cleanup task
    if hasattr(app.state, 'outbox_cleanup_task') and app.state.outbox_cleanup_task:
        app.state.outbox_cleanup_task.cancel()
        try:
            await app.state.outbox_cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Outbox cleanup task stopped")

    # Cancel reconciliation task
    if hasattr(app.state, 'reconciliation_task') and app.state.reconciliation_task:
        app.state.reconciliation_task.cancel()
        try:
            await app.state.reconciliation_task
        except asyncio.CancelledError:
            pass
        logger.info("Reconciliation task stopped")

    # Cancel streaming restoration task (if still running)
    if hasattr(app.state, 'streaming_restoration_task') and app.state.streaming_restoration_task:
        if not app.state.streaming_restoration_task.done():
            app.state.streaming_restoration_task.cancel()
            try:
                await app.state.streaming_restoration_task
            except asyncio.CancelledError:
                pass
            logger.info("Streaming restoration task stopped")

    # Stop outbox publisher
    if hasattr(app.state, 'outbox_publisher') and app.state.outbox_publisher:
        try:
            await app.state.outbox_publisher.stop()
            logger.info("Outbox publisher stopped")
        except Exception as e:
            logger.error(f"Error stopping outbox publisher: {e}")

    # Cancel other background tasks here
    # Add similar cleanup for any other background tasks