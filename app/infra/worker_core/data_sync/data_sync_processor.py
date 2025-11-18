"""
Data Sync Processor - Handles broker data synchronization and integrity

Responsibilities:
1. Process background sync requests
2. Trigger sync commands via CommandBus (CQRS)
3. Monitor data integrity
4. Publish progress events

CQRS Compliance:
- Uses CommandBus to send FetchOrdersFromBrokerCommand
- Uses QueryBus for read-only checks
- Uses EventBus to publish progress
- NO direct DB access
- NO direct broker adapter calls
"""

import logging
import uuid
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus
from app.infra.event_bus.event_bus import EventBus
from app.order.commands import FetchOrdersFromBrokerCommand
from app.broker_account.commands import RefreshAccountDataFromBrokerCommand

# For tracking recovery actions
from collections import defaultdict

log = logging.getLogger("wellwon.data_sync.processor")


class DataSyncProcessor:
    """
    Processes data sync requests and monitors integrity.

    Flow:
    1. Consume BackgroundHistorySyncRequested event
    2. Send FetchOrdersFromBrokerCommand via CommandBus
    3. Monitor progress
    4. Publish completion events
    """

    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
        event_bus: EventBus,
        coordinator=None,  # Optional SyncCoordinator
        metrics=None       # Optional DataSyncMetrics
    ):
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.event_bus = event_bus
        self.coordinator = coordinator
        self.metrics = metrics

        # Internal metrics (if not provided externally)
        if not self.metrics:
            self.events_processed = 0
            self.syncs_triggered = 0
            self.errors = 0

    async def handle_event(self, event: Dict[str, Any]):
        """
        Main event handler for all data sync events.
        Routes to appropriate handler based on event_type.
        """
        event_type = event.get("event_type")

        # Track metrics
        if self.metrics:
            self.metrics.events_processed += 1
            self.metrics.event_type_counters[event_type] += 1
        else:
            self.events_processed += 1

        # Route to appropriate handler
        if event_type == "BackgroundHistorySyncRequested":
            await self.handle_sync_request(event)
        elif event_type == "IntegrityIssueDetected":
            await self.handle_integrity_issue(event)
        else:
            log.debug(f"Ignoring event type: {event_type}")

    async def handle_sync_request(self, event: Dict[str, Any]):
        """
        Handle BackgroundHistorySyncRequested event.

        Fetches historical data (orders, positions, accounts, balances) from broker.
        Supports adaptive time windows and selective data types.
        """
        start_time = time.time()

        user_id = UUID(event['user_id'])
        account_ids = event.get('account_ids', [])
        sync_window_days = event.get('sync_window_days', 30)
        tier = event.get('tier', 2)
        data_types = event.get('data_types', ['orders', 'positions', 'accounts'])
        force = event.get('force', False)

        log.info(
            f"Processing background sync for {len(account_ids)} accounts "
            f"(window: {sync_window_days} days, tier: {tier}, types: {data_types})"
        )

        # Use SyncCoordinator for batch sync with locking and rate limiting
        if self.coordinator:
            results = await self.coordinator.coordinate_sync(
                account_ids=[UUID(aid) for aid in account_ids],
                sync_function=lambda aid: self._sync_single_account(
                    user_id=user_id,
                    account_id=aid,
                    sync_window_days=sync_window_days,
                    data_types=data_types,
                    tier=tier,
                    force=force
                )
            )

            # Aggregate results
            synced_accounts = sum(1 for r in results if not r.get('error'))
            synced_orders = sum(r.get('orders_synced', 0) for r in results if not r.get('error'))
            synced_positions = sum(r.get('positions_synced', 0) for r in results if not r.get('error'))
            failed_accounts = sum(1 for r in results if r.get('error'))

        else:
            # Fallback: manual iteration if no coordinator
            synced_accounts = 0
            synced_orders = 0
            synced_positions = 0
            failed_accounts = 0

            for account_id_str in account_ids:
                try:
                    result = await self._sync_single_account(
                        user_id=user_id,
                        account_id=UUID(account_id_str),
                        sync_window_days=sync_window_days,
                        data_types=data_types,
                        tier=tier,
                        force=force
                    )

                    if not result.get('error'):
                        synced_accounts += 1
                        synced_orders += result.get('orders_synced', 0)
                        synced_positions += result.get('positions_synced', 0)
                    else:
                        failed_accounts += 1

                except Exception as e:
                    failed_accounts += 1
                    log.error(f"Sync failed for account {account_id_str}: {e}")

        # Log summary
        elapsed = time.time() - start_time
        log.info(
            f"Background sync completed - "
            f"Accounts: {synced_accounts}/{len(account_ids)}, "
            f"Orders: {synced_orders}, "
            f"Positions: {synced_positions}, "
            f"Failed: {failed_accounts}, "
            f"Time: {elapsed:.2f}s"
        )

    async def _sync_single_account(
        self,
        user_id: UUID,
        account_id: UUID,
        sync_window_days: int,
        data_types: List[str],
        tier: int,
        force: bool
    ) -> Dict[str, Any]:
        """
        Sync a single account (all data types).

        Supports: orders, positions, accounts, balances
        Returns summary of what was synced.
        """
        result = {
            'account_id': str(account_id),
            'orders_synced': 0,
            'positions_synced': 0,
            'accounts_synced': 0,
            'error': None
        }

        try:
            # Publish progress: starting
            await self._publish_progress(
                user_id=user_id,
                account_id=account_id,
                status="started",
                progress=0
            )

            # Sync orders
            if "orders" in data_types:
                await self._publish_progress(
                    user_id=user_id,
                    account_id=account_id,
                    status="syncing_orders",
                    progress=25,
                    current_step="Fetching orders from broker..."
                )

                orders_result = await self.command_bus.send(
                    FetchOrdersFromBrokerCommand(
                        user_id=user_id,
                        account_id=account_id,
                        status_filter="all" if tier >= 3 else "closed",
                        skip_terminal=False,
                        force=force,
                        metadata={
                            'source': 'background_sync',
                            'tier': tier,
                            'sync_window_days': sync_window_days
                        }
                    )
                )

                result['orders_synced'] = orders_result.get('synced', 0)

                if self.metrics:
                    self.metrics.orders_synced += result['orders_synced']

            # Sync positions
            if "positions" in data_types:
                await self._publish_progress(
                    user_id=user_id,
                    account_id=account_id,
                    status="syncing_positions",
                    progress=50,
                    current_step="Fetching positions from broker..."
                )

                positions_result = await self.command_bus.send(
                    RefreshAccountDataFromBrokerCommand(
                        account_aggregate_id=account_id,
                        user_id=user_id
                    )
                )

                result['positions_synced'] = len(positions_result.get('positions', []))

                if self.metrics:
                    self.metrics.positions_synced += result['positions_synced']

            # Sync accounts (metadata, balances)
            if "accounts" in data_types:
                await self._publish_progress(
                    user_id=user_id,
                    account_id=account_id,
                    status="syncing_accounts",
                    progress=75,
                    current_step="Refreshing account data..."
                )

                # RefreshAccountData handles balances + account metadata
                await self.command_bus.send(
                    RefreshAccountDataFromBrokerCommand(
                        account_aggregate_id=account_id,
                        user_id=user_id
                    )
                )

                result['accounts_synced'] = 1

                if self.metrics:
                    self.metrics.accounts_synced += 1

            # Complete
            await self._publish_progress(
                user_id=user_id,
                account_id=account_id,
                status="complete",
                progress=100,
                orders_synced=result['orders_synced'],
                positions_synced=result['positions_synced'],
                accounts_synced=result['accounts_synced']
            )

            # Update metrics
            if self.metrics:
                self.metrics.syncs_triggered += 1
                self.metrics.syncs_completed += 1

            log.info(
                f"Account sync complete: {account_id} - "
                f"Orders: {result['orders_synced']}, "
                f"Positions: {result['positions_synced']}"
            )

        except Exception as e:
            result['error'] = str(e)

            if self.metrics:
                self.metrics.syncs_failed += 1
                self.metrics.error_counters[type(e).__name__] += 1

            log.error(f"Account sync failed for {account_id}: {e}")

            await self._publish_progress(
                user_id=user_id,
                account_id=account_id,
                status="error",
                progress=0,
                error=str(e)
            )

        return result

    async def handle_integrity_issue(self, event: Dict[str, Any]):
        """
        Handle IntegrityIssueDetected event with automatic recovery.

        Triggers recovery actions based on issue type.
        """
        issue_type = event.get('issue_type')
        account_id = UUID(event['account_id'])
        user_id = UUID(event['user_id'])
        severity = event.get('severity', 'MEDIUM')

        log.warning(
            f"Integrity issue detected: {issue_type} for account {account_id}, "
            f"severity={severity}"
        )

        # Track metric
        if self.metrics:
            self.metrics.integrity_issues_found += 1

        # Dispatch recovery based on issue type
        try:
            if issue_type == "MISSING_ORDERS":
                # Trigger full order sync (force=True to bypass cache)
                log.info(f"Triggering order sync recovery for {account_id}")
                await self.command_bus.send(
                    FetchOrdersFromBrokerCommand(
                        user_id=user_id,
                        account_id=account_id,
                        status_filter="all",  # Fetch both open and closed
                        force=True,
                        metadata={'source': 'integrity_recovery', 'issue_type': issue_type}
                    )
                )
                if self.metrics:
                    self.metrics.recovery_actions_triggered += 1

            elif issue_type == "BALANCE_MISMATCH":
                # Trigger account data refresh
                log.info(f"Triggering account refresh for {account_id}")
                from app.broker_account.commands import RefreshAccountDataFromBrokerCommand
                await self.command_bus.send(
                    RefreshAccountDataFromBrokerCommand(
                        account_aggregate_id=account_id,
                        user_id=user_id
                    )
                )
                if self.metrics:
                    self.metrics.recovery_actions_triggered += 1

            elif issue_type == "STALE_DATA":
                # Trigger refresh of open orders only (lighter operation)
                log.info(f"Triggering order refresh for {account_id}")
                await self.command_bus.send(
                    FetchOrdersFromBrokerCommand(
                        user_id=user_id,
                        account_id=account_id,
                        status_filter="open",
                        force=True,
                        metadata={'source': 'integrity_recovery', 'issue_type': issue_type}
                    )
                )
                if self.metrics:
                    self.metrics.recovery_actions_triggered += 1

            elif issue_type == "MISSING_POSITIONS":
                # Trigger position sync via account refresh
                log.info(f"Triggering position sync for {account_id}")
                from app.broker_account.commands import RefreshAccountDataFromBrokerCommand
                await self.command_bus.send(
                    RefreshAccountDataFromBrokerCommand(
                        account_aggregate_id=account_id,
                        user_id=user_id
                    )
                )
                if self.metrics:
                    self.metrics.recovery_actions_triggered += 1

            elif issue_type == "POSITION_QUANTITY_MISMATCH":
                # Trigger full position re-sync
                log.info(f"Triggering position re-sync for {account_id}")
                from app.broker_account.commands import RefreshAccountDataFromBrokerCommand
                await self.command_bus.send(
                    RefreshAccountDataFromBrokerCommand(
                        account_aggregate_id=account_id,
                        user_id=user_id
                    )
                )
                if self.metrics:
                    self.metrics.recovery_actions_triggered += 1

            else:
                log.warning(f"Unknown integrity issue type: {issue_type}, skipping recovery")

            log.info(f"Recovery action triggered successfully for {issue_type}")

        except Exception as e:
            log.error(f"Failed to trigger recovery for {issue_type}: {e}", exc_info=True)
            if self.metrics:
                self.metrics.error_counters[f"recovery_{issue_type}"] += 1

    async def _publish_progress(
        self,
        user_id: UUID,
        account_id: UUID,
        status: str,
        progress: int,
        error: str = None,
        orders_synced: int = 0,
        current_step: str = None,
        positions_synced: int = 0,
        accounts_synced: int = 0
    ):
        """Publish sync progress event (CQRS: EventBus only)"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "BackgroundSyncProgressEvent",
            "user_id": str(user_id),
            "account_id": str(account_id),
            "status": status,  # "syncing_orders", "complete", "error"
            "progress": progress,  # 0-100
            "current_step": current_step,  # Human-readable description
            "error": error,
            "orders_synced": orders_synced,
            "positions_synced": positions_synced,
            "accounts_synced": accounts_synced,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self.event_bus.publish("worker.data-sync.sync-progress", event)
        log.debug(f"Published progress: {status} ({progress}%) for account {account_id}")
