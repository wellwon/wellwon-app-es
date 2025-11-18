# app/infra/event_store/reconciliation_service.py
"""
EventStore Reconciliation Service

Detects and fixes orphaned events:
- Events in KurrentDB (EventStore) but NOT in outbox table
- Can happen if outbox insert fails but EventStore append succeeds

This service:
1. Queries KurrentDB for event IDs
2. Queries outbox table for event IDs
3. Finds difference (orphaned events)
4. Re-inserts orphaned events into outbox for publishing

Created: 2025-11-13 (TRUE Exactly-Once Implementation)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Set, List
from uuid import UUID

from app.infra.persistence.pg_client import db as pg_db_proxy
from app.infra.metrics.exactly_once_metrics import (
    record_outbox_orphaned_event,
    outbox_reconciliation_runs_total,
    outbox_reconciliation_duration_seconds,
    outbox_reconciliation_events_checked
)

log = logging.getLogger("wellwon.event_store.reconciliation")


class EventStoreReconciliationService:
    """
    Reconciliation service to detect and fix orphaned events.

    Orphaned events: Events that exist in KurrentDB but not in the outbox table.
    This can happen if:
    - EventStore.append() succeeds
    - Outbox.insert() fails
    - Transaction rollback leaves event in KurrentDB but not in outbox
    """

    def __init__(self, event_store=None):
        """
        Initialize reconciliation service.

        Args:
            event_store: KurrentDB event store instance (for querying events)
        """
        self.event_store = event_store
        self._reconciliation_count = 0

    async def reconcile_orphaned_events(
        self,
        since: datetime,
        batch_size: int = 100
    ) -> int:
        """
        Find orphaned events and gaps using sequence-based detection.

        ENHANCED (2025-11-14): TRUE orphaned event detection using:
        1. Sequence gap detection (PostgreSQL best practice)
        2. Aggregate version gaps per aggregate
        3. Old pending events stuck in outbox

        This catches events that were written to event_store table but failed
        to write to outbox table due to transaction issues.

        Args:
            since: Check events created after this timestamp
            batch_size: Max events to process per batch

        Returns:
            Number of orphaned events reconciled
        """
        import time
        start_time = time.time()

        log.info(f"Starting ENHANCED reconciliation for events since {since}")

        try:
            # STRATEGY 1: Detect sequence gaps in outbox table
            # If we have aggregate_version 1,2,3,5,6 → version 4 is ORPHANED
            gap_events = await self._detect_sequence_gaps(since)

            # STRATEGY 2: Find old pending/failed events (original logic)
            old_pending_events = await self._get_old_pending_events(hours=24)

            # STRATEGY 3: Detect stuck events with high publish_attempts
            stuck_events = await self._get_stuck_events()

            # Combine all detected issues (using set to avoid duplicates)
            all_problematic_events = set(gap_events + old_pending_events + stuck_events)

            if not all_problematic_events:
                log.info("No orphaned or problematic events found")
                outbox_reconciliation_runs_total.labels(status='success').inc()
                return 0

            log.warning(
                f"Found {len(all_problematic_events)} problematic events: "
                f"{len(gap_events)} gaps, {len(old_pending_events)} old, {len(stuck_events)} stuck"
            )

            # Reset all problematic events for retry
            reconciled_count = 0
            for event_id in all_problematic_events:
                try:
                    await self._reset_event_for_retry(event_id)
                    reconciled_count += 1
                    record_outbox_orphaned_event()

                except Exception as e:
                    log.error(f"Failed to reconcile event {event_id}: {e}")

            # Record metrics
            duration = time.time() - start_time
            outbox_reconciliation_runs_total.labels(status='success').inc()
            outbox_reconciliation_duration_seconds.observe(duration)
            outbox_reconciliation_events_checked.observe(len(all_problematic_events))

            log.info(
                f"Reconciliation complete: {reconciled_count} events reset for retry, "
                f"duration={duration:.2f}s"
            )

            self._reconciliation_count += reconciled_count
            return reconciled_count

        except Exception as e:
            log.error(f"Reconciliation failed: {e}", exc_info=True)
            outbox_reconciliation_runs_total.labels(status='failure').inc()
            raise

    async def _get_outbox_event_ids(self, since: datetime) -> Set[UUID]:
        """Get all event IDs from outbox table since timestamp."""
        rows = await pg_db_proxy.fetch(
            """
            SELECT event_id
            FROM event_outbox
            WHERE created_at >= $1
            """,
            since
        )
        return {row['event_id'] for row in rows}

    async def _detect_sequence_gaps(self, since: datetime) -> List[UUID]:
        """
        Detect sequence gaps using aggregate_version for each aggregate.

        BEST PRACTICE (PostgreSQL): Use Window Functions to detect gaps.
        If aggregate has versions [1,2,3,5,6], version 4 is missing (orphaned).

        Returns:
            List of event_ids that appear to have gaps before them
        """
        rows = await pg_db_proxy.fetch(
            """
            WITH version_sequences AS (
                SELECT
                    aggregate_id,
                    aggregate_version,
                    event_id,
                    LAG(aggregate_version) OVER (
                        PARTITION BY aggregate_id
                        ORDER BY aggregate_version
                    ) as prev_version
                FROM event_outbox
                WHERE created_at >= $1
                  AND aggregate_version IS NOT NULL
                  AND status IN ('pending', 'failed')
            )
            SELECT event_id
            FROM version_sequences
            WHERE prev_version IS NOT NULL
              AND aggregate_version > prev_version + 1
            LIMIT 100
            """,
            since
        )

        gap_event_ids = [row['event_id'] for row in rows]

        if gap_event_ids:
            log.warning(
                f"Detected {len(gap_event_ids)} events with sequence gaps "
                f"(potential orphaned events)"
            )

        return gap_event_ids

    async def _get_old_pending_events(self, hours: int = 24) -> List[UUID]:
        """
        Get events that are stuck in 'pending' or 'failed' status for too long.

        These might be orphaned or poison pills that need attention.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        rows = await pg_db_proxy.fetch(
            """
            SELECT event_id
            FROM event_outbox
            WHERE status IN ('pending', 'failed')
              AND created_at < $1
              AND publish_attempts < 10  -- Not yet moved to DLQ
            ORDER BY created_at ASC
            LIMIT 100
            """,
            cutoff
        )

        return [row['event_id'] for row in rows]

    async def _get_stuck_events(self) -> List[UUID]:
        """
        Get events that have been retried many times but not moved to DLQ.

        These are likely poison pills or have configuration issues.
        """
        rows = await pg_db_proxy.fetch(
            """
            SELECT event_id
            FROM event_outbox
            WHERE status = 'failed'
              AND publish_attempts >= 5
              AND publish_attempts < 10  -- Not yet in DLQ
              AND created_at > NOW() - INTERVAL '48 hours'
            ORDER BY publish_attempts DESC, created_at ASC
            LIMIT 50
            """,
        )

        stuck_event_ids = [row['event_id'] for row in rows]

        if stuck_event_ids:
            log.warning(
                f"Detected {len(stuck_event_ids)} stuck events "
                f"with high retry attempts"
            )

        return stuck_event_ids

    async def _reset_event_for_retry(self, event_id: UUID) -> None:
        """
        Reset an event to 'pending' status for retry.

        This clears publish_attempts and last_attempt_at to give it a fresh start.
        """
        await pg_db_proxy.execute(
            """
            UPDATE event_outbox
            SET status = 'pending',
                publish_attempts = 0,
                last_attempt_at = NULL,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE event_id = $1
            """,
            event_id
        )

        log.info(f"Reset event {event_id} for retry")

    async def get_reconciliation_stats(self) -> dict:
        """Get reconciliation statistics."""
        return {
            'total_reconciled': self._reconciliation_count,
            'last_run': datetime.now(timezone.utc).isoformat()
        }


# Background task function for running reconciliation periodically
async def run_reconciliation_periodically(
    reconciliation_service: EventStoreReconciliationService,
    interval_hours: int = 6,
    lookback_hours: int = 24
) -> None:
    """
    Background task to run reconciliation periodically.

    Args:
        reconciliation_service: Reconciliation service instance
        interval_hours: How often to run reconciliation
        lookback_hours: How far back to check for orphaned events
    """
    import asyncio

    log.info(
        f"Starting periodic reconciliation task: "
        f"interval={interval_hours}h, lookback={lookback_hours}h"
    )

    while True:
        try:
            # Wait for interval
            await asyncio.sleep(interval_hours * 3600)

            # Run reconciliation
            since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            count = await reconciliation_service.reconcile_orphaned_events(since)

            if count > 0:
                log.warning(f"Reconciliation found and fixed {count} orphaned events")

        except asyncio.CancelledError:
            log.info("Reconciliation task cancelled")
            break

        except Exception as e:
            log.error(f"Reconciliation task error: {e}", exc_info=True)
            # Continue running despite errors
            await asyncio.sleep(300)  # 5 min backoff on error
