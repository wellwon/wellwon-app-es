# app/core/background_tasks.py
# =============================================================================
# File: app/core/background_tasks.py
# Description: Background task management
# =============================================================================

import asyncio
import logging
from app.core.fastapi_types import FastAPI

logger = logging.getLogger("wellwon.background")

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

    # Stop outbox publisher
    if hasattr(app.state, 'outbox_publisher') and app.state.outbox_publisher:
        try:
            await app.state.outbox_publisher.stop()
            logger.info("Outbox publisher stopped")
        except Exception as e:
            logger.error(f"Error stopping outbox publisher: {e}")
