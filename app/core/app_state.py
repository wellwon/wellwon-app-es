# app/core/app_state.py
# =============================================================================
# File: app/core/app_state.py
# Description: Application state definition and global state management
# UPDATED: Added DLQ Service to application state
# =============================================================================

from typing import Optional, Dict, Any
from datetime import datetime, timezone
import asyncio

# Event Bus and infrastructure types
from app.infra.event_bus.event_bus import EventBus
from app.wse.core.pubsub_bus import PubSubBus
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore

# CQRS types
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus

# Read repository types
from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
from app.infra.read_repos.broker_connection_read_repo import BrokerConnectionReadRepo
from app.infra.read_repos.broker_account_read_repo import BrokerAccountReadRepo
from app.infra.read_repos.virtual_broker_read_repo import VirtualBrokerReadRepo

# Service types
from app.services.application.broker_auth_service import BrokerAuthenticationService
from app.services.application.broker_operation_service import BrokerOperationService
from app.services.infrastructure.adapter_monitoring.adapter_monitoring_service import AdapterMonitoringService
# NOTE: BrokerStreamingService merged into BrokerOperationService
from app.services.application.user_auth_service import UserAuthenticationService
from app.services.infrastructure.saga_service import SagaService

# Virtual broker types
from app.virtual_broker.services.virtual_broker_service import VirtualBrokerService
from app.virtual_broker.services.virtual_market_data_service import VirtualBrokerMarketDataService

# Adapter types
from app.infra.broker_adapters.adapter_factory import BrokerAdapterFactory
from app.infra.broker_adapters.adapter_pool import AdapterPool
from app.infra.broker_adapters.adapter_manager import AdapterManager

# Distributed feature types
from app.infra.reliability.distributed_lock import DistributedLockManager
from app.infra.event_store.sequence_tracker import EventSequenceTracker
from app.infra.event_store.outbox_service import TransportOutboxService, OutboxPublisher
from app.infra.event_store.dlq_service import DLQService

# DLQ Service type
from app.infra.event_store.dlq_service import DLQService


# =============================================================================
# APP STATE TYPE DEFINITION
# =============================================================================
class AppState:
    """Type definition for FastAPI app.state with proper type hints"""

    def __init__(self):
        # Core infrastructure
        self.event_bus: Optional[EventBus] = None
        self.pubsub_bus: Optional[PubSubBus] = None
        self.event_store: Optional[KurrentDBEventStore] = None
        self.cache_manager = None  # Type depends on cache manager availability

        # CQRS components
        self.command_bus: Optional[CommandBus] = None
        self.query_bus: Optional[QueryBus] = None

        # Read repositories
        self.user_account_read_repo: Optional[UserAccountReadRepo] = None
        self.broker_connection_state: Optional[BrokerConnectionReadRepo] = None
        self.broker_connection_state_reader: Optional[BrokerConnectionReadRepo] = None
        self.account_state: Optional[BrokerAccountReadRepo] = None
        self.account_state_reader: Optional[BrokerAccountReadRepo] = None
        self.virtual_broker_read_repo: Optional[VirtualBrokerReadRepo] = None

        # Services - All services use AdapterManager
        self.user_auth_service: Optional[UserAuthenticationService] = None
        self.broker_auth_service: Optional[BrokerAuthenticationService] = None
        self.broker_operation_service: Optional[BrokerOperationService] = None  # Includes streaming
        self.adapter_monitoring_service: Optional[AdapterMonitoringService] = None
        # NOTE: broker_streaming_service merged into broker_operation_service

        # Virtual broker services
        self.virtual_broker_service: Optional[VirtualBrokerService] = None
        self.virtual_market_data_service: Optional[VirtualBrokerMarketDataService] = None

        # Adapter management - Unified adapter stack
        self.adapter_factory: Optional[BrokerAdapterFactory] = None
        self.adapter_pool: Optional[AdapterPool] = None
        self.adapter_manager: Optional[AdapterManager] = None

        # Configuration
        self.monitoring_config: Optional[Dict[str, Any]] = None

        # Distributed features
        self.lock_manager: Optional[DistributedLockManager] = None
        self.sequence_tracker: Optional[EventSequenceTracker] = None
        self.outbox_service: Optional[TransportOutboxService] = None
        self.dlq_service: Optional[DLQService] = None  # NEW: DLQ Service

        # Background tasks
        self.outbox_publisher: Optional[OutboxPublisher] = None
        self.outbox_cleanup_task: Optional[asyncio.Task] = None

        # Saga service
        self.saga_service: Optional[SagaService] = None

        # Data integrity monitoring
        self.data_integrity_monitor = None  # Optional service

        # Projection rebuilder service
        self.projection_rebuilder = None  # Optional service

        # CQRS registration statistics (added to track handler registration)
        self.cqrs_registration_stats: Optional[Dict[str, Any]] = None

        # Projector instances for sync projections
        self.projector_instances: Optional[Dict[str, Any]] = None


# =============================================================================
# GLOBAL STATE
# =============================================================================
_START_TIME = datetime.now(timezone.utc)


def get_start_time() -> datetime:
    """Get application start time"""
    return _START_TIME