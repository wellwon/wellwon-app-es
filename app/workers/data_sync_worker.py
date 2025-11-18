# app/workers/data_sync_worker_v2.py
"""
Data Sync Worker - REFACTORED to use BaseWorker

Architecture:
- Inherits BaseWorker for all infrastructure (DB, Redis, EventBus, CQRS, lifecycle)
- DataSyncProcessor for sync logic and event handling
- SyncCoordinator for batch operations and rate limiting
- IntegrityChecker for data validation (NEW!)
- Beautiful logging matching EventProcessorWorker style

Topics consumed:
- transport.background-sync-events (background sync requests)
- alerts.data-integrity (integrity issues)

Responsibilities:
1. Tier 2/3: Background historical sync (30 days, 1 year)
2. Emergency: Integrity checks + automatic recovery
3. Progress tracking and reporting

Matches EventProcessorWorker architecture 100%.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from collections import defaultdict

# Import BaseWorker
from app.common.base.base_worker import BaseWorker

# Import centralized configuration
from app.infra.worker_core.consumer_groups import (
    WorkerType,
    get_worker_consumer_config
)

# Worker configuration
from app.config.worker_config import WorkerConfig

# Worker infrastructure
from app.infra.worker_core.consumer_manager import ConsumerManager
from app.infra.worker_core.worker_lifecycle import (
    WorkerMetrics, HealthStatus, check_infrastructure_health
)

# Data sync components
from app.infra.worker_core.data_sync.data_sync_processor import DataSyncProcessor
from app.infra.worker_core.data_sync.sync_coordinator import SyncCoordinator
from app.infra.worker_core.data_sync.integrity_checker import (
    IntegrityChecker,
    IntegrityCheckResult,
    CheckLevel,
    IntegrityStatus
)

# Queries for integrity checks
from app.broker_connection.queries import GetAllActiveConnectionsQuery

# Import query handlers to register them (decorator auto-registers on import)
import app.broker_connection.query_handlers.connection_query_handlers  # noqa: F401

# Events
from app.infra.worker_core.data_sync.data_sync_events import IntegrityIssueDetected

# Logging with beautiful formatting
from app.config.logging_config import (
    setup_logging,
    log_worker_banner,
    log_status_update,
    log_metrics_table,
)

log = logging.getLogger(__name__)


# =============================================================================
# DATA SYNC METRICS (Worker-Specific)
# =============================================================================

class DataSyncMetrics:
    """Metrics tracking for data sync operations"""

    def __init__(self):
        # Event processing
        self.events_processed = 0
        self.event_type_counters = defaultdict(int)

        # Sync operations
        self.syncs_triggered = 0
        self.syncs_completed = 0
        self.syncs_failed = 0

        # Data synced
        self.accounts_synced = 0
        self.orders_synced = 0
        self.positions_synced = 0

        # Integrity monitoring
        self.integrity_checks_run = 0
        self.integrity_issues_found = 0
        self.recovery_actions_triggered = 0

        # Error tracking
        self.error_counters = defaultdict(int)

        # Timing
        self.total_sync_time_ms = 0
        self.avg_sync_time_ms = 0


# =============================================================================
# DATA SYNC WORKER (Inherits from BaseWorker)
# =============================================================================

class DataSyncWorker(BaseWorker):
    """
    Data Sync Worker with full production features.

    Inherits infrastructure from BaseWorker (DB, Redis, EventBus, CQRS, lifecycle).
    Adds data sync processing and integrity monitoring.

    Responsibilities:
    - Background historical sync (Tier 2/3)
    - Data integrity monitoring and recovery (Emergency)
    - Progress tracking and reporting
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        """Initialize worker with configuration"""
        # Call parent constructor with DATA_SYNC type
        super().__init__(WorkerType.DATA_SYNC, config)

        # DataSync-specific components (CQRS compliant - NO service injection!)
        self.sync_coordinator: Optional[SyncCoordinator] = None
        self.sync_processor: Optional[DataSyncProcessor] = None
        self.consumer_manager: Optional[ConsumerManager] = None
        self.integrity_checker: Optional[IntegrityChecker] = None

        # DataSync-specific metrics
        self.metrics = DataSyncMetrics()

        # DataSync-specific background tasks
        self._integrity_monitoring_task: Optional[asyncio.Task] = None

    # =============================================================================
    # BASEWORKER HOOK IMPLEMENTATIONS
    # =============================================================================

    async def _initialize_worker_specific(self):
        """
        Setup data sync components (called by BaseWorker.initialize()).

        CQRS Compliant: Uses ONLY CommandBus, QueryBus, EventBus.
        NO direct service injection!
        """
        self.logger.info("Setting up data sync processing...")

        # Import and register query handlers (force registration before use)
        from app.broker_connection.query_handlers import connection_query_handlers
        from app.broker_account.query_handlers import account_query_handlers

        # Import and register command handlers (force registration before use)
        # IMPORTANT: Import full module paths to trigger @command_handler decorators
        import app.order.command_handlers.broker_sync_handlers  # FetchOrdersFromBrokerCommand
        import app.broker_account.command_handlers.balance_handlers  # RefreshAccountDataFromBrokerCommand

        # NOW: Actually register the handlers with the worker's buses!
        from app.infra.cqrs.decorators import auto_register_all_handlers
        from app.infra.cqrs.handler_dependencies import HandlerDependencies

        # Create dependencies for handlers (minimal set for worker)
        # CQRS: Worker has EventBus, CommandBus, QueryBus + read repos
        # NOTE: operation_service=None (workers don't call broker APIs directly)
        from app.infra.read_repos.broker_connection_read_repo import BrokerConnectionReadRepo
        from app.infra.read_repos.broker_account_read_repo import BrokerAccountReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        cache_manager = get_cache_manager()

        deps = HandlerDependencies(
            event_bus=self.event_bus,  # Required
            command_bus=self.command_bus,  # For sending commands
            query_bus=self.query_bus,  # For reading data
            broker_connection_read_repo=BrokerConnectionReadRepo(cache_manager=cache_manager),
            broker_account_read_repo=BrokerAccountReadRepo(cache_manager=cache_manager)
            # operation_service=None - workers don't call broker APIs
            # Handlers needing it will be skipped (skip_missing_deps=True)
        )

        # Auto-register ALL decorated handlers with this worker's buses
        stats = auto_register_all_handlers(
            command_bus=self.command_bus,
            query_bus=self.query_bus,
            dependencies=deps,
            skip_missing_deps=True  # Some handlers may need dependencies we don't have
        )

        self.logger.info(
            f"Handlers registered: {stats['commands']} commands, "
            f"{stats['queries']} queries, {stats.get('skipped', [])} skipped"
        )

        # Create sync coordinator (handles locking, rate limiting)
        self.sync_coordinator = SyncCoordinator()

        # Create integrity checker (CQRS compliant - uses buses only!)
        self.integrity_checker = IntegrityChecker(
            query_bus=self.query_bus,
            command_bus=self.command_bus  # Fetches broker data via commands
        )

        # Create data sync processor
        self.sync_processor = DataSyncProcessor(
            command_bus=self.command_bus,
            query_bus=self.query_bus,
            event_bus=self.event_bus,
            coordinator=self.sync_coordinator,
            metrics=self.metrics
        )

        # Create consumer manager
        self.consumer_manager = ConsumerManager(
            config=self.config,
            event_bus=self.event_bus,
            event_processor=None,  # We handle events directly via sync_processor
            domain_registry=None   # Not needed for data sync
        )

        # Hook up processor to consumer
        self.consumer_manager._process_event = self.sync_processor.handle_event

        self.logger.info("Data sync processing initialized (CQRS compliant)")

    async def _start_processing(self):
        """Start consumer manager and wait for shutdown"""
        await self.consumer_manager.start()

        self.logger.info("Consumers started, waiting for shutdown signal")

        await self._shutdown_event.wait()

        self.logger.info("Shutdown signal received, stopping consumers")

        await self.consumer_manager.stop(timeout=15)

    def _should_enable_command_bus(self) -> bool:
        """DataSync checks worker_consumer_config.supports_commands"""
        return self.worker_consumer_config.supports_commands

    def _should_enable_query_bus(self) -> bool:
        """DataSync checks worker_consumer_config.supports_queries"""
        return self.worker_consumer_config.supports_queries

    async def _setup_worker_specific_background_tasks(self) -> None:
        """Setup DataSync-specific background tasks"""

        # Integrity monitoring (NEW!)
        if self.config.enable_gap_detection:
            self._integrity_monitoring_task = asyncio.create_task(
                self._integrity_monitoring_loop(),
                name="integrity-monitoring"
            )
            self._background_tasks.append(self._integrity_monitoring_task)
            self.logger.info("Integrity monitoring task started")

    async def _get_health_status(self) -> HealthStatus:
        """Get health status - infrastructure only"""
        consumer_healthy = self.consumer_manager.is_healthy() if self.consumer_manager else False

        return await check_infrastructure_health(
            event_bus=self.event_bus,
            consumer_manager_healthy=consumer_healthy
        )

    async def _get_metrics(self) -> WorkerMetrics:
        """Get worker metrics"""
        consumer_stats = (
            await self.consumer_manager.get_consumer_stats()
            if self.consumer_manager else {}
        )

        # Create base metrics
        base_metrics = WorkerMetrics(
            processed_events=self.metrics.events_processed,
            failed_events=self.metrics.syncs_failed,
            retry_events=0,  # TODO: Track retries
            saga_events=0,  # No sagas in data sync worker
            saga_triggered=0,
            event_type_breakdown=dict(self.metrics.event_type_counters),
            topic_breakdown={},
            error_breakdown=dict(self.metrics.error_counters),
            consumer_stats=consumer_stats
        )

        # Add data sync specific metrics
        base_metrics.syncs_triggered = self.metrics.syncs_triggered
        base_metrics.syncs_completed = self.metrics.syncs_completed
        base_metrics.accounts_synced = self.metrics.accounts_synced
        base_metrics.orders_synced = self.metrics.orders_synced
        base_metrics.positions_synced = self.metrics.positions_synced
        base_metrics.integrity_checks_run = self.metrics.integrity_checks_run
        base_metrics.integrity_issues_found = self.metrics.integrity_issues_found
        base_metrics.recovery_actions_triggered = self.metrics.recovery_actions_triggered
        base_metrics.active_background_tasks = len([t for t in self._background_tasks if not t.done()])

        return base_metrics

    # =============================================================================
    # WORKER-SPECIFIC BACKGROUND TASKS
    # =============================================================================

    async def _integrity_monitoring_loop(self) -> None:
        """
        Periodic integrity checks (Emergency Recovery).

        Runs every 10 minutes, checks all active connections for issues.
        """
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes (more reactive!)

                if not self._running:
                    break

                self.logger.info("Running periodic integrity checks...")

                # Get all active connections
                connections = await self.query_bus.query(GetAllActiveConnectionsQuery())

                checked_accounts = 0
                issues_found = 0

                for conn in connections:
                    try:
                        # Run integrity check for each account in connection
                        # (connections can have multiple accounts)
                        if not hasattr(conn, 'accounts') or not conn.accounts:
                            continue

                        for account in conn.accounts:
                            # Run check using IntegrityChecker
                            result = await self.integrity_checker.check_account_integrity(
                                user_id=conn.user_id,
                                account_id=account.id,
                                broker_id=conn.broker_id,
                                level=CheckLevel.STANDARD
                            )

                            checked_accounts += 1
                            self.metrics.integrity_checks_run += 1

                            # If issues found, publish IntegrityIssueDetected event
                            if result.issues:
                                issues_found += len(result.issues)
                                self.metrics.integrity_issues_found += len(result.issues)

                                for issue in result.issues:
                                    event = IntegrityIssueDetected(
                                        issue_id=issue.issue_id,
                                        user_id=str(conn.user_id),
                                        account_id=str(account.id),
                                        broker_id=conn.broker_id,
                                        issue_type=issue.type.value,
                                        severity=issue.severity.value,
                                        description=issue.description,
                                        details=issue.details,
                                        auto_recoverable=issue.auto_recoverable
                                    )

                                    # Publish to alerts.data-integrity topic
                                    await self.event_bus.publish(
                                        "alerts.data-integrity",
                                        event.model_dump()
                                    )

                                    self.logger.warning(
                                        f"Integrity issue detected: {issue.type.value} "
                                        f"for account {account.id}, severity={issue.severity.value}"
                                    )

                    except Exception as e:
                        self.logger.error(f"Error checking integrity for connection {conn.id}: {e}")

                self.logger.info(
                    f"Integrity check cycle complete: "
                    f"checked={checked_accounts} accounts, "
                    f"issues={issues_found}"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in integrity monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_worker():
    """Run the data sync worker with beautiful logging (like EventProcessorWorker)"""
    import os
    import sys

    worker = None

    try:
        # Setup logging with yellow color for data sync (data_integrity service type)
        setup_logging(
            service_name=f"worker.{WorkerType.DATA_SYNC.value}",
            log_file=os.getenv("WORKER_LOG_FILE"),
            enable_json=os.getenv("ENVIRONMENT") == "production",
            service_type="data_integrity"  # Yellow color
        )

        log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")

        # Create worker
        worker = DataSyncWorker()

        # Display worker banner (beautiful startup like EventProcessorWorker)
        log_worker_banner(
            logger=log,
            worker_name="Data Sync Worker",
            instance_id=worker.instance_id,
            service_type="data_integrity"
        )

        # Initialize (BaseWorker handles all infrastructure + calls _initialize_worker_specific)
        await worker.initialize()

        # Show ready status
        log_status_update(log, "Worker Ready", {
            "status": "processing sync events",
            "topics": ", ".join(worker.config.topics[:3]) +
                      ("..." if len(worker.config.topics) > 3 else ""),
        })

        # Trigger startup complete
        log.info("Application startup complete")

        # Start processing (BaseWorker calls _start_processing)
        await worker.start()

        # BaseWorker handles signal setup, wait for shutdown
        await worker.wait_for_shutdown()

    except KeyboardInterrupt:
        log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")
        log.info("Worker interrupted by user")
    except Exception as e:
        log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")
        log.error(f"Worker failed: {e}", exc_info=True)
        raise
    finally:
        if worker:
            try:
                # BaseWorker handles graceful shutdown
                await asyncio.wait_for(worker.stop(), timeout=30.0)
                log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")
                log.info("Graceful shutdown completed")
            except asyncio.TimeoutError:
                log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")
                log.error("Graceful shutdown timed out")
            except Exception as e:
                log = logging.getLogger(f"tradecore.worker.{WorkerType.DATA_SYNC.value}")
                log.error(f"Error during shutdown: {e}", exc_info=True)


def main():
    """Main entry point"""
    import sys

    # Run the worker
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\nWorker interrupted")
    except Exception as e:
        print(f"Worker crashed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import sys
    if sys.version_info < (3, 8):
        print("Error: Python 3.8+ is required", file=sys.stderr)
        sys.exit(1)

    main()
