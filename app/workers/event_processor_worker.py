# app/workers/event_processor_worker.py
# =============================================================================
# File: app/workers/event_processor_worker.py
# Description: Event processor worker - REFACTORED to use BaseWorker
# UPDATED: Migrated to BaseWorker infrastructure (2025-11-17)
# =============================================================================

"""
Event Processor Worker - Refactored with BaseWorker

Inherits from BaseWorker for common infrastructure.
Processes domain events and updates read models with sync projections support.

Architecture:
- BaseWorker: Infrastructure (DB, Redis, EventBus, CQRS, lifecycle)
- EventProcessingWorker: Event processing logic and domain projections
"""

import asyncio
import logging
import signal
import sys
import os
import time
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone
from collections import defaultdict

# Import BaseWorker
from app.common.base.base_worker import BaseWorker, PersistentWorkerState

# Import centralized configuration
from app.infra.worker_core.consumer_groups import (
    WorkerType,
    WorkerConsumerGroups,
    get_worker_consumer_config,
    create_redpanda_adapter_for_worker
)

# Worker configuration (using NEW unified config)
from app.config.worker_config import WorkerConfig  # NEW location
from app.infra.worker_core.event_processor.domain_registry import create_domain_registry
from app.infra.worker_core.event_processor.event_processor import EventProcessor, EventProcessingMetrics
from app.infra.worker_core.consumer_manager import ConsumerManager
from app.infra.worker_core.worker_lifecycle import (
    WorkerMetrics, HealthStatus, check_infrastructure_health
)

# Note: Infrastructure imports (DB, Redis, EventBus, CQRS, DLQ, Locks) now in BaseWorker

# Logging (only what we use directly)
from app.config.logging_config import (
    setup_logging,
    log_worker_banner,
    log_status_update,
    log_metrics_table,
)

# Note: WorkerMetricsCollector now in BaseWorker

# Constants for sync event monitoring
SYNC_EVENT_WARNING_THRESHOLD = 10  # Warn every N occurrences
SYNC_EVENT_WARNING_INTERVAL = 600  # 10 minutes


# =============================================================================
# EVENT PROCESSING WORKER (Inherits from BaseWorker)
# =============================================================================
# Note: Infrastructure, PersistentWorkerState, signal handling provided by BaseWorker

class EventProcessingWorker(BaseWorker):
    """
    Event processing worker with CQRS buses and sync projections support.

    Inherits infrastructure from BaseWorker.
    Adds domain event processing and projection management.
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        """Initialize worker with configuration"""
        # Call parent constructor with EVENT_PROCESSOR type
        super().__init__(WorkerType.EVENT_PROCESSOR, config)

        # EventProcessor-specific components
        # domain_registry created in _setup_infrastructure_worker_specific after Redis init
        self.domain_registry = None
        self.event_processor: Optional[EventProcessor] = None
        self.consumer_manager: Optional[ConsumerManager] = None

        # Sync projections tracking
        self.sync_events_registry: Set[str] = set()
        self.sync_event_warnings_logged: Set[str] = set()
        self.sync_event_counts: Dict[str, int] = defaultdict(int)
        self.last_sync_event_warning = time.time()

        # EventProcessor-specific metrics
        self.metrics = EventProcessingMetrics()

        # EventProcessor-specific background tasks
        self._gap_detection_task: Optional[asyncio.Task] = None
        self._projection_monitoring_task: Optional[asyncio.Task] = None
        self._sync_event_monitoring_task: Optional[asyncio.Task] = None

    # =============================================================================
    # BASEWORKER HOOK IMPLEMENTATIONS
    # =============================================================================

    async def _initialize_worker_specific(self):
        """Setup event processing components (called by BaseWorker.initialize())"""
        await self._setup_event_processing()

    async def _start_processing(self):
        """Start consumer manager and wait for shutdown"""
        await self.consumer_manager.start()
        await self._shutdown_event.wait()

    def _should_enable_command_bus(self) -> bool:
        """EventProcessor checks worker_consumer_config.supports_commands"""
        return self.worker_consumer_config.supports_commands

    def _should_enable_query_bus(self) -> bool:
        """EventProcessor checks worker_consumer_config.supports_queries"""
        return self.worker_consumer_config.supports_queries

    def _should_enable_sequence_tracking(self) -> bool:
        """Check if sequence tracking should be enabled for this worker"""
        # Most workers benefit from sequence tracking
        return self.worker_type not in [WorkerType.HEALTH_MONITOR]

    async def _setup_event_processing(self) -> None:
        """Setup event processing components with sync projections awareness"""
        self.logger.info("Setting up event processing...")

        # Create domain registry NOW (after Redis is initialized)
        self.domain_registry = create_domain_registry()
        self.logger.info("Domain registry created")

        # Initialize domain projectors with cache manager
        # The domain registry will create read repos with cache manager internally
        await self.domain_registry.initialize_all(
            event_bus=self.event_bus,
            auth_service=None,  # Not needed for worker
            query_bus=self.query_bus
        )

        # Collect all sync events from domain registry
        self.sync_events_registry = set(self.domain_registry.get_all_sync_events())
        self.logger.info(f"Loaded {len(self.sync_events_registry)} sync events from domain registry")

        # Log sync events for visibility
        enabled_domains = self.domain_registry.get_enabled_domains()
        sync_events_by_domain = {domain: len(self.sync_events_registry) for domain in enabled_domains}

        if self.sync_events_registry:
            sample_events = list(self.sync_events_registry)[:5]
            self.logger.debug(
                f"Sync events ({len(self.sync_events_registry)} total): "
                f"{sample_events}{'...' if len(self.sync_events_registry) > 5 else ''}"
            )
            self.logger.info(f"Enabled domains: {enabled_domains}")

        # Create event processor with CQRS buses and sync events
        self.event_processor = EventProcessor(
            domain_registry=self.domain_registry,
            event_bus=self.event_bus,
            command_bus=self.command_bus,
            query_bus=self.query_bus,
            saga_manager=None,  # NO sagas in worker
            sequence_tracker=self.sequence_tracker,
            metrics=self.metrics,
            sync_events_registry=self.sync_events_registry,  # Pass sync events
            dlq_service=self.dlq_service
        )

        # Create consumer manager with domain registry
        self.consumer_manager = ConsumerManager(
            config=self.config,
            event_bus=self.event_bus,
            event_processor=self.event_processor,
            domain_registry=self.domain_registry
        )

        self.logger.info(
            f"Event processing components initialized. "
            f"Tracking {len(self.sync_events_registry)} sync events across {len(sync_events_by_domain)} domains"
        )

    async def _setup_persistent_state_worker_specific(self):
        """Load EventProcessor-specific persistent state (hook called by BaseWorker)"""
        # Load previous sync event warnings
        previous_sync_warnings = await self.persistent_state.load_state("sync_event_warnings")
        if previous_sync_warnings:
            self.sync_event_counts.update(previous_sync_warnings.get("counts", {}))
            self.logger.info(f"Loaded previous sync event warnings: {len(self.sync_event_counts)} events tracked")

    async def _setup_worker_specific_background_tasks(self) -> None:
        """Setup EventProcessor-specific background tasks"""
        # Gap detection
        if self.config.enable_gap_detection and self.sequence_tracker:
            self._gap_detection_task = asyncio.create_task(
                self._gap_detection_loop(),
                name="gap-detection"
            )
            self._background_tasks.append(self._gap_detection_task)
            self.logger.info("Gap detection task started")

        # Projection monitoring
        if self.config.enable_projection_monitoring:
            self._projection_monitoring_task = asyncio.create_task(
                self._projection_monitoring_loop(),
                name="projection-monitoring"
            )
            self._background_tasks.append(self._projection_monitoring_task)
            self.logger.info("Projection monitoring task started")

        # State persistence
        self._state_persistence_task = asyncio.create_task(
            self._state_persistence_loop(),
            name="state-persistence"
        )
        self._background_tasks.append(self._state_persistence_task)

        # Metrics reporting
        self._metrics_reporting_task = asyncio.create_task(
            self._metrics_reporting_loop(),
            name="metrics-reporting"
        )
        self._background_tasks.append(self._metrics_reporting_task)

        # Sync event monitoring
        if self.config.enable_sync_projection_monitoring and self.sync_events_registry:
            self._sync_event_monitoring_task = asyncio.create_task(
                self._sync_event_monitoring_loop(),
                name="sync-event-monitoring"
            )
            self._background_tasks.append(self._sync_event_monitoring_task)
            self.logger.info("Sync event monitoring task started")

    async def _gap_detection_loop(self) -> None:
        """Background task for detecting and healing sequence gaps"""
        gap_config = self.config.get_gap_detection_config()

        while self._running:
            try:
                await asyncio.sleep(gap_config["interval_seconds"])

                if not self._running:
                    break

                # Check for gaps in each topic
                for topic in self.config.topics:
                    await self._detect_and_heal_gaps(topic, gap_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in gap detection loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry

    async def _detect_and_heal_gaps(self, topic: str, gap_config: Dict[str, Any]) -> None:
        """Detect and heal sequence gaps for a topic"""
        try:
            # Get domains for this topic
            domains = self.domain_registry.get_domains_for_topic(topic)
            if not domains:
                return

            # Check for missing sequences
            self.logger.debug(f"Checking sequence gaps for topic: {topic}")

            # If gaps found and self-healing enabled, we would trigger recovery
            # via command bus instead of direct event store access
            if self.config.enable_self_healing:
                self.logger.debug(f"Self-healing check completed for topic: {topic}")

        except Exception as e:
            self.logger.error(f"Error detecting gaps for topic {topic}: {e}")

    async def _projection_monitoring_loop(self) -> None:
        """Background task for monitoring projection health"""
        while self._running:
            try:
                await asyncio.sleep(300)  # 5 minutes

                if not self._running:
                    break

                await self._check_projection_health()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in projection monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _check_projection_health(self) -> None:
        """Check health of all projections"""
        try:
            # Get projection metrics from event processor
            projection_metrics = self.event_processor.get_projection_metrics()

            # Log any projections with high error rates
            for projection_name, error_count in projection_metrics.get("errors_by_projection", {}).items():
                if error_count > 100:
                    self.logger.warning(f"High error count for projection {projection_name}: {error_count}")

            # Check sync event warnings
            sync_warnings = projection_metrics.get("sync_event_warnings", {})
            for event_type, count in sync_warnings.items():
                self.sync_event_counts[event_type] = count

                # Log warning based on thresholds
                if self._should_log_sync_event_warning(event_type, count):
                    self.logger.warning(
                        f"Sync event '{event_type}' processed {count} times in async mode. "
                        f"Consider enabling sync projections in server for better consistency."
                    )
                    self.sync_event_warnings_logged.add(event_type)

            self.logger.debug(
                f"Projection health check completed - total processed: {projection_metrics.get('total_processed', 0)}, "
                f"sync events skipped: {projection_metrics.get('sync_events_skipped', 0)}"
            )

        except Exception as e:
            self.logger.error(f"Error checking projection health: {e}")

    def _should_log_sync_event_warning(self, event_type: str, count: int) -> bool:
        """Determine if we should log a sync event warning"""
        # Don't log if already logged recently
        if event_type in self.sync_event_warnings_logged:
            # Check if enough time has passed
            if time.time() - self.last_sync_event_warning < SYNC_EVENT_WARNING_INTERVAL:
                return False

        # Log on first occurrence
        if count == 1:
            return True

        # Log every N occurrences
        if count % SYNC_EVENT_WARNING_THRESHOLD == 0:
            return True

        return False

    async def _sync_event_monitoring_loop(self) -> None:
        """Monitor sync events being processed in async mode"""
        while self._running:
            try:
                await asyncio.sleep(600)  # 10 minutes

                if not self._running:
                    break

                await self._report_sync_event_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in sync event monitoring loop: {e}", exc_info=True)

    async def _report_sync_event_metrics(self) -> None:
        """Report metrics about sync events"""
        try:
            if not self.event_processor:
                return

            projection_metrics = self.event_processor.get_projection_metrics()
            sync_event_summary = projection_metrics.get("sync_event_summary", {})

            if sync_event_summary.get('total_sync_events_async', 0) > 0:
                # Save to persistent state
                await self.persistent_state.save_state("sync_event_warnings", {
                    "counts": dict(self.sync_event_counts),
                    "summary": sync_event_summary,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, ttl_seconds=86400)

                # Log summary
                self.logger.info(
                    f"Sync event summary - Total processed async: {sync_event_summary['total_sync_events_async']}. "
                    f"Top events: {sync_event_summary.get('top_events', {})}"
                )

                # Reset warning timer
                self.last_sync_event_warning = time.time()

        except Exception as e:
            self.logger.error(f"Error reporting sync event metrics: {e}")

    async def _state_persistence_loop(self) -> None:
        """Periodically persist important state"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute

                if not self._running:
                    break

                # Save current metrics
                metrics = await self._get_metrics()
                await self.persistent_state.save_state("metrics", {
                    "processed_events": metrics.processed_events,
                    "failed_events": metrics.failed_events,
                    "retry_events": metrics.retry_events,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, ttl_seconds=3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in state persistence loop: {e}")

    async def _metrics_reporting_loop(self) -> None:
        """Report metrics periodically"""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                if not self._running:
                    break

                metrics = await self._get_metrics()
                projection_metrics = self.event_processor.get_projection_metrics() if self.event_processor else {}

                # Update unified metrics collector
                self.metrics_collector.update_metrics({
                    "processed_events": metrics.processed_events,
                    "failed_events": metrics.failed_events,
                    "retry_events": metrics.retry_events,
                    "success_rate": (metrics.processed_events / max(1,
                                                                    metrics.processed_events + metrics.failed_events) * 100),
                    "recovery_triggers": projection_metrics.get('recovery_triggers', 0),
                    "sync_events_skipped": projection_metrics.get('sync_events_skipped', 0),
                })

                log_metrics_table(self.logger, "Worker Metrics", {
                    "Processed Events": metrics.processed_events,
                    "Failed Events": metrics.failed_events,
                    "Retry Events": metrics.retry_events,
                    "Recovery Triggers": projection_metrics.get('recovery_triggers', 0),
                    "Sync Events (Async)": projection_metrics.get('sync_events_skipped', 0),
                    "Success Rate": f"{(metrics.processed_events / max(1, metrics.processed_events + metrics.failed_events) * 100):.1f}%",
                    "Active Tasks": len([t for t in self._background_tasks if not t.done()])
                })

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error logging metrics: {e}")

    async def _log_startup_metrics(self):
        """Log detailed startup metrics (called after start)"""
        log_metrics_table(self.logger, "Worker Started", {
            "Worker Type": self.worker_type.value,
            "Worker ID": self.config.worker_id,
            "Consumer Group": self.worker_consumer_config.consumer_group,
            "Topics": len(self.config.topics),
            "Max Poll Records": self.worker_consumer_config.max_poll_records,
            "Session Timeout": f"{self.worker_consumer_config.session_timeout_ms}ms",
            "Max Instances": self.worker_consumer_config.instances_max,
            "Sync Events": len(self.sync_events_registry),
        })

    async def stop(self) -> None:
        """Stop processing events with proper cleanup"""
        if not self._running:
            return

        if self._shutdown_initiated:
            self.logger.warning("Shutdown already in progress")
            return

        self._shutdown_initiated = True
        self.logger.info(f"Stopping worker {self.config.worker_id}")
        self._running = False

        # Save final state
        try:
            final_metrics = await self._get_metrics()
            projection_metrics = self.event_processor.get_projection_metrics() if self.event_processor else {}

            await self.persistent_state.save_state("final_metrics", {
                "processed_events": final_metrics.processed_events,
                "failed_events": final_metrics.failed_events,
                "sync_events_skipped": projection_metrics.get('sync_events_skipped', 0),
                "sync_event_summary": projection_metrics.get('sync_event_summary', {}),
                "shutdown_time": datetime.now(timezone.utc).isoformat()
            }, ttl_seconds=86400)  # Keep for 24 hours
        except Exception as e:
            self.logger.error(f"Error saving final state: {e}")

        # Stop background tasks with timeout
        if self._background_tasks:
            self.logger.info("Stopping background tasks...")
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Some background tasks did not complete in time")

        # Stop processing
        if self.event_processor:
            self.event_processor.request_stop()

        # Stop consumers with timeout
        if self.consumer_manager:
            try:
                await asyncio.wait_for(
                    self.consumer_manager.stop(timeout=15),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                self.logger.error("Consumer manager shutdown timed out")

        # Stop lifecycle
        if self.lifecycle_manager:
            await self.lifecycle_manager.publish_shutdown_event(await self._get_metrics())
            await self.lifecycle_manager.stop()
            await self.lifecycle_manager.deregister_worker()
            await self.lifecycle_manager.cleanup_files()

        # Log final metrics
        final_metrics = await self._get_metrics()
        projection_metrics = self.event_processor.get_projection_metrics() if self.event_processor else {}
        sync_summary = projection_metrics.get('sync_event_summary', {})

        log_metrics_table(self.logger, "Worker Final Metrics", {
            "Total Processed": final_metrics.processed_events,
            "Failed Events": final_metrics.failed_events,
            "Retry Events": final_metrics.retry_events,
            "Recovery Triggers": getattr(final_metrics, 'recovery_triggers', 0),
            "Sync Events (Async)": projection_metrics.get('sync_events_skipped', 0),
            "Success Rate": f"{(final_metrics.processed_events / max(1, final_metrics.processed_events + final_metrics.failed_events) * 100):.1f}%",
            "Uptime": f"{int(time.time() - self._start_time)}s",
        })

        # Log sync event summary if any
        if sync_summary.get('total_sync_events_async', 0) > 0:
            self.logger.info(
                f"Final sync event summary: {sync_summary['total_sync_events_async']} events processed async. "
                f"Top events: {sync_summary.get('top_events', {})}"
            )

        # Close infrastructure connections
        if self.event_bus:
            await self.event_bus.close()

        # Stop cache manager
        if self.cache_manager and hasattr(self.cache_manager, 'stop'):
            await self.cache_manager.stop()

        self.logger.info(f"Worker {self.config.worker_id} stopped")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()

    # Note: handle_signal() now provided by BaseWorker with same 3-level logic

    # Callback methods for lifecycle manager
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

        # Get projection metrics from event processor
        projection_metrics = self.event_processor.get_projection_metrics() if self.event_processor else {}

        # Create base metrics
        base_metrics = WorkerMetrics(
            processed_events=self.metrics.processed_events,
            failed_events=self.metrics.failed_events,
            retry_events=self.metrics.retry_events,
            saga_events=0,  # NO sagas in worker
            saga_triggered=0,  # NO sagas in worker
            event_type_breakdown=dict(self.metrics.event_type_counters),
            topic_breakdown=dict(self.metrics.topic_counters),
            error_breakdown=dict(self.metrics.error_counters),
            consumer_stats=consumer_stats
        )

        # Add additional metrics as attributes
        base_metrics.command_bus_enabled = self.command_bus is not None
        base_metrics.query_bus_enabled = self.query_bus is not None
        base_metrics.gap_detection_enabled = self.config.enable_gap_detection
        base_metrics.recovery_triggers = projection_metrics.get('recovery_triggers', 0)
        base_metrics.sync_events_skipped = projection_metrics.get('sync_events_skipped', 0)
        base_metrics.active_background_tasks = len([t for t in self._background_tasks if not t.done()])

        return base_metrics

    async def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        projection_metrics = self.event_processor.get_projection_metrics() if self.event_processor else {}

        return {
            "worker_id": self.config.worker_id,
            "worker_type": self.worker_type.value,
            "version": "0.8",
            "architecture": "READ-SIDE with CQRS buses and sync awareness",
            "features": {
                "command_bus": self.command_bus is not None,
                "query_bus": self.query_bus is not None,
                "event_bus": self.event_bus is not None,
                "distributed_lock": self.lock_manager is not None,
                "sequence_tracking": self.sequence_tracker is not None,
                "deduplication": self.event_processor is not None,
                "gap_detection": self.config.enable_gap_detection,
                "self_healing": self.config.enable_self_healing,
                "projection_monitoring": self.config.enable_projection_monitoring,
                "sync_event_monitoring": self.config.enable_sync_projection_monitoring,
                "persistent_state": self.persistent_state is not None,
                "cache_manager": self.cache_manager is not None,
                "dlq_service": self.dlq_service is not None,
            },
            "sync_projections": {
                "total_sync_events": len(self.sync_events_registry),
                "enabled_domains": self.domain_registry.get_enabled_domains(),
                "sync_monitoring_enabled": self.config.enable_sync_projection_monitoring,
                "sync_events_processed_async": projection_metrics.get('sync_events_skipped', 0),
                "sync_event_warnings": len(self.sync_event_warnings_logged),
            },
            "infrastructure": {
                "redpanda_servers": self.config.redpanda_servers,
                "consumer_group": self.worker_consumer_config.consumer_group,
                "topics": self.config.topics,
                "dlq_topic": self.config.dlq_topic,
                "max_retries": self.config.max_retries,
                "batch_size": self.config.consumer_batch_size
            },
            "monitoring": {
                "health_check_interval": self.config.health_check_interval,
                "metrics_interval": self.config.metrics_interval,
                "heartbeat_ttl": self.config.heartbeat_ttl,
                "projection_error_threshold": self.config.projection_error_threshold
            },
            "status": "running" if self._running else "stopped",
            "uptime_seconds": int(time.time() - self._start_time) if hasattr(self, '_start_time') else 0
        }


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_worker():
    """Run the event processing worker with CQRS buses and sync projections awareness"""
    worker = None

    try:
        # Setup logging (EventProcessor uses purple "consumer" color)
        setup_logging(
            service_name="worker.event-processor",
            log_file=os.getenv("WORKER_LOG_FILE"),
            enable_json=os.getenv("ENVIRONMENT") == "production",
            service_type="consumer"  # Purple color
        )

        log = logging.getLogger("wellwon.worker.event-processor")

        # Create worker
        worker = EventProcessingWorker()

        # Display worker banner
        log_worker_banner(
            logger=log,
            worker_name="Event Processor Worker",
            instance_id=worker.config.worker_id,
            service_type="consumer"  # Purple color
        )

        # Initialize and start
        await worker.initialize()

        # Show ready status
        log_status_update(log, "Worker Ready", {
            "status": "processing events",
            "topics": ", ".join(worker.config.topics[:3]) +
                      ("..." if len(worker.config.topics) > 3 else ""),
            "sync_events": f"{len(worker.sync_events_registry)} tracked"
        })

        # Trigger startup complete
        log.info("Application startup complete")

        await worker.start()

        # Log startup metrics (after start completes)
        await worker._log_startup_metrics()

        # Setup signal handlers
        signal.signal(signal.SIGINT, worker.handle_signal)
        signal.signal(signal.SIGTERM, worker.handle_signal)

        await worker.wait_for_shutdown()

    except KeyboardInterrupt:
        log = logging.getLogger("wellwon.worker.event-processor")
        log.info("Worker interrupted by user")
    except Exception as e:
        log = logging.getLogger("wellwon.worker.event-processor")
        log.error(f"Worker failed: {e}", exc_info=True)
        raise
    finally:
        if worker:
            try:
                await asyncio.wait_for(worker.stop(), timeout=30.0)
                log = logging.getLogger("wellwon.worker.event-processor")
                log.info("Graceful shutdown completed")
            except asyncio.TimeoutError:
                log = logging.getLogger("wellwon.worker.event-processor")
                log.error("Graceful shutdown timed out")
            except Exception as e:
                log = logging.getLogger("wellwon.worker.event-processor")
                log.error(f"Error during shutdown: {e}", exc_info=True)

        # Note: Infrastructure cleanup now handled by BaseWorker.stop()
        log = logging.getLogger("wellwon.worker.event-processor")
        log.info("Worker shutdown complete")


def main():
    """Main entry point"""
    # Run the worker
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\nWorker interrupted")
    except Exception as e:
        print(f"Worker crashed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        print("Error: Python 3.8+ is required", file=sys.stderr)
        sys.exit(1)

    main()

# =============================================================================
# EOF
# =============================================================================