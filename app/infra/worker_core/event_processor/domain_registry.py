# app/infra/consumers/domain_registry.py
# =============================================================================
# File: app/infra/consumers/domain_registry.py
# Description: Domain registry with saga event handling and sync projections
# FIXED: Added enable_sequence_tracking attribute to DomainRegistration
# =============================================================================

"""
Domain Registry Module - READ-SIDE ONLY with Multi-Topic and Sync Projections Support

ARCHITECTURE:
- Allows domains to listen to multiple topics for cross-domain events
- Maintains CQRS separation (read-side only)
- Enables proper cascade operations (e.g., account deletion on broker disconnect)
- FIXED: Handles saga completion events appropriately
- ADDED: Virtual broker domain for virtual trading accounts
- ADDED: Sync projections support
- UPDATED: All read repositories now use CacheManager
- FIXED: Ensure projector instances are properly initialized for all domains
- FIXED: Handle missing dependencies gracefully in worker context
- FIXED: Added enable_sequence_tracking attribute
"""

from typing import Dict, Type, Callable, Optional, Any, List, Set
from dataclasses import dataclass, field
import logging

from app.common.base.base_model import BaseEvent
from app.infra.worker_core.worker_config import (
    USER_ACCOUNT_EVENTS_TOPIC,
    BROKER_ACCOUNT_EVENTS_TOPIC,
    BROKER_CONNECTION_EVENTS_TOPIC,
    AUTOMATION_EVENTS_TOPIC,
    POSITION_EVENTS_TOPIC,
    ORDER_EVENTS_TOPIC
)
from app.virtual_broker.events import VirtualAccountsDeleted
from app.infra.event_store.sync_decorators import get_all_sync_events as get_decorator_sync_events
# Import saga events to register them
from app.infra.saga import saga_events

# Add virtual broker topic
VIRTUAL_BROKER_EVENTS_TOPIC = "transport.virtual-broker-events"

log = logging.getLogger("tradecore.worker.domain_registry")


# =============================================================================
# DOMAIN REGISTRATION MODEL - Enhanced with Multi-Topic and Sync Support
# =============================================================================

@dataclass
class DomainRegistration:
    """
    Configuration for a single domain's event processing - READ-SIDE ONLY.

    ENHANCED: Now supports multiple topics and sync events.
    FIXED: Added enable_sequence_tracking attribute
    """
    name: str
    topics: List[str]  # CHANGED: Now a list instead of single topic
    projector_factory: Callable[..., Any]
    event_models: Dict[str, Type[BaseEvent]]
    projection_config: Optional[Dict[str, Any]] = None
    enabled: bool = True
    projector_instance: Optional[Any] = None
    sync_events: Set[str] = field(default_factory=set)  # NEW: Sync events for this domain
    sync_event_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # NEW: Config for sync events
    enable_sequence_tracking: bool = True  # FIXED: Added this attribute

    @property
    def primary_topic(self) -> str:
        """Get the primary topic (first in list) for backward compatibility"""
        return self.topics[0] if self.topics else ""

    async def initialize_projector(self, **kwargs) -> Any:
        """Initialize the projector instance using the factory"""
        if not self.enabled:
            log.info(f"Domain {self.name} is disabled, skipping initialization")
            return None

        try:
            self.projector_instance = self.projector_factory(**kwargs)
            log.info(f"Initialized projector for domain: {self.name} (with {len(self.sync_events)} sync events)")
            return self.projector_instance
        except Exception as e:
            log.error(f"Failed to initialize projector for domain {self.name}: {e}")
            raise

    def has_projector(self) -> bool:
        """Check if projector instance exists"""
        return self.projector_instance is not None


# =============================================================================
# SYNC EVENTS LOADING
# =============================================================================

def load_domain_sync_events(domain_name: str) -> tuple[Set[str], Dict[str, Dict[str, Any]]]:
    """
    Load sync events for a domain from its sync_events.py file
    Returns (sync_events_set, event_config_dict)
    """
    sync_events: Set[str] = set()
    event_config: Dict[str, Dict[str, Any]] = {}

    try:
        # Import sync_events module for the domain
        if domain_name == "user_account":
            from app.user_account.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "broker_account":
            from app.broker_account.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "broker_connection":
            from app.broker_connection.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "virtual_broker":
            from app.virtual_broker.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "order":
            from app.order.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "automation":
            from app.automation.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "position":
            from app.position.sync_events import SYNC_EVENTS, EVENT_CONFIG  # type: ignore[misc]
            sync_events = SYNC_EVENTS  # type: ignore[possibly-undefined]
            event_config = EVENT_CONFIG  # type: ignore[possibly-undefined]
        elif domain_name == "portfolio":
            # Portfolio has no sync events (read-only domain, projection-based)
            sync_events = set()
            event_config = {}
    except ImportError as e:
        log.debug(f"No sync_events module for domain {domain_name}: {e}")
        sync_events = set()
        event_config = {}
    except Exception as e:
        log.error(f"Error loading sync events for domain {domain_name}: {e}")
        sync_events = set()
        event_config = {}

    return sync_events, event_config


# =============================================================================
# USER DOMAIN CONFIGURATION
# =============================================================================

def create_user_domain() -> DomainRegistration:
    """Factory function for user domain configuration"""

    from app.user_account.events import (
        UserAccountCreated, UserPasswordChanged, UserAccountDeleted,
        UserPasswordResetViaSecret, UserEmailVerified, UserBrokerAccountMappingSet,
        UserConnectedBrokerAdded, UserConnectedBrokerRemoved,
        UserAuthenticationSucceeded, UserAuthenticationFailed, UserLoggedOut
    )

    def user_projector_factory():
        from app.user_account.projectors import UserAccountProjector
        from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        # Create read repo with cache manager
        cache_manager = get_cache_manager()
        read_repo = UserAccountReadRepo(cache_manager=cache_manager)

        return UserAccountProjector(read_repo)

    # Load sync events
    sync_events, sync_event_config = load_domain_sync_events("user_account")

    return DomainRegistration(
        name="user_account",
        topics=[USER_ACCOUNT_EVENTS_TOPIC],  # Only needs its own topic
        projector_factory=user_projector_factory,
        event_models={
            "UserAccountCreated": UserAccountCreated,
            "UserCreated": UserAccountCreated,
            "UserPasswordChanged": UserPasswordChanged,
            "UserAccountDeleted": UserAccountDeleted,
            "UserDeleted": UserAccountDeleted,
            "UserPasswordResetViaSecret": UserPasswordResetViaSecret,
            "UserEmailVerified": UserEmailVerified,
            "UserBrokerAccountMappingSet": UserBrokerAccountMappingSet,
            "UserAccountMappingSet": UserBrokerAccountMappingSet,
            "UserConnectedBrokerAdded": UserConnectedBrokerAdded,
            "UserConnectedBrokerRemoved": UserConnectedBrokerRemoved,
            "UserAuthenticationSucceeded": UserAuthenticationSucceeded,
            "UserAuthenticationFailed": UserAuthenticationFailed,
            "UserLoggedOut": UserLoggedOut,  # FIX (Nov 11, 2025): Acknowledge logout event
        },
        projection_config={
            "aggregate_type": "User",
            "transport_topic": USER_ACCOUNT_EVENTS_TOPIC
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True  # Enable sequence tracking for user domain
    )


# =============================================================================
# BROKER ACCOUNT DOMAIN CONFIGURATION - FIXED with Multi-Topic Support
# =============================================================================

def create_broker_account_domain() -> DomainRegistration:
    """
    Factory function for broker account domain configuration.
    FIXED: Now listens to BOTH account events AND connection events for proper cascade deletion.
    UPDATED: Read repository uses CacheManager
    """

    from app.broker_account.events import (
        BrokerAccountLinked, AccountDataFromBrokerUpdated,
        UserSetAccountDetailsChanged, UserAccountMarkedDeleted,
        UserAccountArchivedStatusChanged, BrokerAccountDeleted
    )
    # Import user events for cascade deletion
    from app.user_account.events import UserAccountDeleted

    def account_projector_factory(event_bus=None):
        from app.broker_account.projectors import BrokerAccountProjector
        from app.infra.read_repos.broker_account_read_repo import BrokerAccountReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        # Create read repo with cache manager
        cache_manager = get_cache_manager()
        read_repo = BrokerAccountReadRepo(cache_manager=cache_manager)

        # CQRS COMPLIANCE (Nov 11, 2025): Removed reactive_event_bus from projector
        # WSEDomainPublisher handles all domain event forwarding to WebSocket

        return BrokerAccountProjector(
            broker_account_read_repo=read_repo,
            event_bus=event_bus,
            cache_manager=cache_manager  # Redis fast path (2025-11-10)
        )

    # Load sync events
    sync_events, sync_event_config = load_domain_sync_events("broker_account")

    return DomainRegistration(
        name="broker_account",
        topics=[
            BROKER_ACCOUNT_EVENTS_TOPIC,  # Primary topic
            BROKER_CONNECTION_EVENTS_TOPIC,  # For BrokerConnectionPurged safety net
            USER_ACCOUNT_EVENTS_TOPIC,  # For UserDeleted events
        ],
        projector_factory=account_projector_factory,
        event_models={
            # Account events
            "BrokerAccountLinked": BrokerAccountLinked,
            "AccountDataFromBrokerUpdated": AccountDataFromBrokerUpdated,
            "UserSetAccountDetailsChanged": UserSetAccountDetailsChanged,
            "UserAccountMarkedDeleted": UserAccountMarkedDeleted,
            "UserAccountArchivedStatusChanged": UserAccountArchivedStatusChanged,

            # Connection events (safety net only)
            "BrokerConnectionPurged": None,  # Safety net to ensure accounts are deleted

            # User events for cascade deletion
            "UserDeleted": UserAccountDeleted,
            "UserAccountDeleted": UserAccountDeleted,

            # Saga orchestration events - handled directly, not requiring specific event models
            "BrokerAccountsCleanupOrchestrated": None,  # Handled directly
            "BrokerAccountDeleted": BrokerAccountDeleted,  # FIXED: Now has sync projection for hard delete

            # FIXED: Add saga completion events that this domain should acknowledge
            "AccountDiscoveryCompleted": None,  # Saga completion - just log
            "BrokerAccountsDeleted": None,  # Notification event - just log
            "AllAccountsRefreshCompleted": None,  # Saga completion - just log
            "BulkArchiveCompleted": None,  # Saga completion - just log
            "BrokerDisconnectionAbandoned": None,  # FIXED: Race condition event - just acknowledge
            "BrokerDisconnectionCompleted": None,  # ADDED: Saga completion event
        },
        projection_config={
            "aggregate_type": "Account",
            "primary_topic": BROKER_ACCOUNT_EVENTS_TOPIC,
            "cross_topic_events": ["BrokerConnectionPurged", "UserDeleted"],
            # NOTE: BrokerDisconnected removed - deletion now handled via saga commands
            "dependencies": ["broker_connections", "users"]
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True  # Enable sequence tracking for broker account domain
    )


# =============================================================================
# BROKER CONNECTION DOMAIN CONFIGURATION - FIXED with Saga Events
# =============================================================================

def create_broker_connection_domain() -> DomainRegistration:
    """
    Factory function for broker connection domain configuration
    UPDATED: Read repository uses CacheManager
    FIXED: Handle missing query_bus gracefully in worker context
    FIXED: Properly handle BrokerConnectionStatusReset event
    """

    from app.broker_connection.events import (
        BrokerConnectionInitiated, BrokerApiCredentialsStored,
        BrokerOAuthClientCredentialsStored, BrokerOAuthFlowStarted,
        BrokerTokensSuccessfullyStored, BrokerConnectionEstablished,
        BrokerConnectionAttemptFailed, BrokerConnectionHealthUpdated,
        BrokerTokensSuccessfullyRefreshed, BrokerDisconnected,
        BrokerApiEndpointConfigured, BrokerConnectionPurged,
        BrokerConnectionHealthChecked, BrokerConnectionMetricsUpdated,
        BrokerConnectionModuleHealthChanged, BrokerConnectionReauthRequired,
        BrokerConnectionRateLimited, BrokerConnectionCredentialsCleared,
        BrokerConnectionStatusReset  # ADDED: Import the event class
    )

    def connection_projector_factory(query_bus_instance=None):
        from app.broker_connection.projectors import BrokerConnectionProjector
        from app.infra.read_repos.broker_connection_read_repo import BrokerConnectionReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        # Create read repo with cache manager
        cache_manager = get_cache_manager()
        read_repo = BrokerConnectionReadRepo(cache_manager=cache_manager)

        # Create projector - handle missing dependencies gracefully
        return BrokerConnectionProjector(
            read_repo=read_repo,
            query_bus=query_bus_instance
        )

    # Load sync events
    sync_events, sync_event_config = load_domain_sync_events("broker_connection")

    return DomainRegistration(
        name="broker_connection",
        topics=[BROKER_CONNECTION_EVENTS_TOPIC],
        projector_factory=connection_projector_factory,
        event_models={
            "BrokerConnectionInitiated": BrokerConnectionInitiated,
            "BrokerApiCredentialsStored": BrokerApiCredentialsStored,
            "BrokerOAuthClientCredentialsStored": BrokerOAuthClientCredentialsStored,
            "BrokerOAuthFlowStarted": BrokerOAuthFlowStarted,
            "BrokerTokensSuccessfullyStored": BrokerTokensSuccessfullyStored,
            "BrokerConnectionEstablished": BrokerConnectionEstablished,
            "BrokerConnectionAttemptFailed": BrokerConnectionAttemptFailed,
            "BrokerConnectionHealthUpdated": BrokerConnectionHealthUpdated,
            "BrokerTokensSuccessfullyRefreshed": BrokerTokensSuccessfullyRefreshed,
            "BrokerDisconnected": BrokerDisconnected,
            "BrokerApiEndpointConfigured": BrokerApiEndpointConfigured,
            "BrokerConnectionPurged": BrokerConnectionPurged,
            "BrokerConnectionHealthChecked": BrokerConnectionHealthChecked,
            "BrokerConnectionMetricsUpdated": BrokerConnectionMetricsUpdated,
            "BrokerConnectionModuleHealthChanged": BrokerConnectionModuleHealthChanged,
            "BrokerConnectionReauthRequired": BrokerConnectionReauthRequired,
            "BrokerConnectionRateLimited": BrokerConnectionRateLimited,
            "BrokerConnectionCredentialsCleared": BrokerConnectionCredentialsCleared,

            # FIXED: Map to actual event class instead of None
            "BrokerConnectionStatusReset": BrokerConnectionStatusReset,

            # These can remain as None if they're just notifications
            "VirtualBrokerReadyForDiscovery": None,
            "VirtualBrokerUserConnected": None,

            # Saga completion events
            "BrokerConnectionSetupCompleted": None,
            "BrokerDisconnectionCompleted": None,
            "BrokerConnectionEstablishedSagaCompleted": None,
            "AllConnectionsHealthCheckCompleted": None,
            "AllBrokersDisconnectCompleted": None,
            "BrokerReconnectionAttempted": None,
            "BrokerReconnectionFailed": None,
        },
        projection_config={
            "aggregate_type": "BrokerConnection",
            "transport_topic": BROKER_CONNECTION_EVENTS_TOPIC
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True
    )


# =============================================================================
# VIRTUAL BROKER DOMAIN CONFIGURATION - FIXED
# =============================================================================

def create_virtual_broker_domain() -> DomainRegistration:
    """
    Factory function for virtual broker domain configuration
    FIXED: Removed use_vb_database parameter
    UPDATED: Read repository uses CacheManager
    """

    from app.virtual_broker.events import (
        VirtualAccountCreated,
        VirtualAccountBalanceUpdated,
        VirtualAccountEquityUpdated,
        VirtualAccountBuyingPowerUpdated,
        VirtualAccountMarginUpdated,
        VirtualAccountReset,
        VirtualOrderPlaced,
        VirtualOrderExecuted,
        VirtualOrderPartiallyFilled,
        VirtualOrderCancelled,
        VirtualOrderRejected,
        VirtualOrderModified,
        VirtualOrderExpired,
        VirtualPositionOpened,
        VirtualPositionUpdated,
        VirtualPositionClosed,
        VirtualPositionMarketValueUpdated,
        VirtualPositionTransferred,
        VirtualRiskLimitExceeded,
        VirtualMarginCallTriggered,
        VirtualRiskLimitUpdated,
        VirtualMarketDataReceived,
        VirtualMarketDataError,
        VirtualDividendReceived,
        VirtualStockSplitProcessed,
        VirtualCorporateActionAnnounced,
        VirtualPerformanceCalculated,
        VirtualReportGenerated,
        VirtualSystemMaintenanceScheduled,
        VirtualDataSyncCompleted
    )

    # Import broker events for handling disconnection
    from app.broker_connection.events import BrokerDisconnected, BrokerConnectionPurged

    def virtual_broker_projector_factory(app=None):
        """FIXED: Handle optional app parameter gracefully"""
        from app.virtual_broker.projectors import VirtualBrokerProjectorService
        from app.infra.read_repos.virtual_broker_read_repo import VirtualBrokerReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        # Create read repo with cache manager
        cache_manager = get_cache_manager()
        read_repo = VirtualBrokerReadRepo(cache_manager=cache_manager)

        # Create projector - app can be None in worker context
        return VirtualBrokerProjectorService(
            app=app,
            read_repo=read_repo,
            cache_manager=cache_manager  # ADDED (2025-11-10): Redis fast path
        )

    # Load sync events
    sync_events, sync_event_config = load_domain_sync_events("virtual_broker")

    return DomainRegistration(
        name="virtual_broker",
        topics=[
            VIRTUAL_BROKER_EVENTS_TOPIC,  # Primary topic
            BROKER_CONNECTION_EVENTS_TOPIC  # Also listen to broker connection events for cleanup
        ],
        projector_factory=virtual_broker_projector_factory,
        event_models={
            # Account events
            "VirtualAccountCreated": VirtualAccountCreated,
            "VirtualAccountBalanceUpdated": VirtualAccountBalanceUpdated,
            "VirtualAccountEquityUpdated": VirtualAccountEquityUpdated,
            "VirtualAccountBuyingPowerUpdated": VirtualAccountBuyingPowerUpdated,
            "VirtualAccountMarginUpdated": VirtualAccountMarginUpdated,
            "VirtualAccountReset": VirtualAccountReset,
            "VirtualAccountsDeleted": VirtualAccountsDeleted,  # ADDED: Handle deletion event

            # Order events
            "VirtualOrderPlaced": VirtualOrderPlaced,
            "VirtualOrderExecuted": VirtualOrderExecuted,
            "VirtualOrderPartiallyFilled": VirtualOrderPartiallyFilled,
            "VirtualOrderCancelled": VirtualOrderCancelled,
            "VirtualOrderRejected": VirtualOrderRejected,
            "VirtualOrderModified": VirtualOrderModified,
            "VirtualOrderExpired": VirtualOrderExpired,

            # Position events
            "VirtualPositionOpened": VirtualPositionOpened,
            "VirtualPositionUpdated": VirtualPositionUpdated,
            "VirtualPositionClosed": VirtualPositionClosed,
            "VirtualPositionMarketValueUpdated": VirtualPositionMarketValueUpdated,
            "VirtualPositionTransferred": VirtualPositionTransferred,

            # Risk events
            "VirtualRiskLimitExceeded": VirtualRiskLimitExceeded,
            "VirtualMarginCallTriggered": VirtualMarginCallTriggered,
            "VirtualRiskLimitUpdated": VirtualRiskLimitUpdated,

            # Market data events
            "VirtualMarketDataReceived": VirtualMarketDataReceived,
            "VirtualMarketDataError": VirtualMarketDataError,

            # Corporate action events
            "VirtualDividendReceived": VirtualDividendReceived,
            "VirtualStockSplitProcessed": VirtualStockSplitProcessed,
            "VirtualCorporateActionAnnounced": VirtualCorporateActionAnnounced,

            # Performance and reporting events
            "VirtualPerformanceCalculated": VirtualPerformanceCalculated,
            "VirtualReportGenerated": VirtualReportGenerated,

            # System events
            "VirtualSystemMaintenanceScheduled": VirtualSystemMaintenanceScheduled,
            "VirtualDataSyncCompleted": VirtualDataSyncCompleted,

            # ADD THESE VIRTUAL BROKER SPECIFIC EVENTS:
            "VirtualBrokerUserConnected": None,  # Handle in projector if needed
            "VirtualBrokerUserDisconnected": None,  # Handle in projector if needed
            "VirtualBrokerReadyForDiscovery": None,  # Handle in projector if needed
            "VirtualBrokerCacheCleared": None,  # Handle in projector
            "VirtualBrokerCleanupCompleted": None,  # Handle in projector

            # CRITICAL: Add broker connection events for cleanup
            "BrokerDisconnected": BrokerDisconnected,  # Handle disconnection
            "BrokerConnectionPurged": BrokerConnectionPurged,  # Handle final purge
            "BrokerDisconnectionCompleted": None,  # Saga completion
        },
        projection_config={
            "aggregate_type": "VirtualBrokerAccount",
            "transport_topic": VIRTUAL_BROKER_EVENTS_TOPIC,
            "is_virtual": True,
            "cross_topic_events": ["BrokerDisconnected", "BrokerConnectionPurged"]
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True  # Enable sequence tracking for virtual broker domain
    )


# =============================================================================
# ORDER DOMAIN CONFIGURATION
# =============================================================================

def create_order_domain() -> DomainRegistration:
    """
    Factory function for order domain configuration
    """

    from app.order.events import (
        OrderPlacedEvent,
        OrderSubmittedEvent,
        OrderAcceptedEvent,
        OrderFilledEvent,
        OrderCompletedEvent,
        OrderCancelledEvent,
        OrderRejectedEvent,
        OrderExpiredEvent,
        OrderModifiedEvent,
        BracketOrderPlacedEvent,
        OrderMetadataUpdatedEvent,
        OrderSyncedFromBrokerEvent,
        OrderStatusUpdatedEvent
    )

    def order_projector_factory():
        # Import the full module to register standalone @sync_projection functions
        import app.order.projectors
        from app.order.projectors import OrderProjector
        from app.infra.read_repos.order_read_repo import OrderReadRepository
        from app.infra.persistence.cache_manager import get_cache_manager

        # Create read repo with cache manager
        cache_manager = get_cache_manager()
        read_repo = OrderReadRepository(cache_manager=cache_manager)

        # Create and return OrderProjector instance
        return OrderProjector(read_repo=read_repo)

    # Load sync events from sync_events.py
    sync_events, sync_event_config = load_domain_sync_events("order")

    # Order domain uses ORDER_EVENTS_TOPIC
    from app.infra.worker_core.worker_config import ORDER_EVENTS_TOPIC

    return DomainRegistration(
        name="order",
        topics=[ORDER_EVENTS_TOPIC],
        projector_factory=order_projector_factory,
        event_models={
            "OrderPlacedEvent": OrderPlacedEvent,
            "OrderSubmittedEvent": OrderSubmittedEvent,
            "OrderAcceptedEvent": OrderAcceptedEvent,
            "OrderFilledEvent": OrderFilledEvent,
            "OrderCompletedEvent": OrderCompletedEvent,
            "OrderCancelledEvent": OrderCancelledEvent,
            "OrderRejectedEvent": OrderRejectedEvent,
            "OrderExpiredEvent": OrderExpiredEvent,
            "OrderModifiedEvent": OrderModifiedEvent,
            "BracketOrderPlacedEvent": BracketOrderPlacedEvent,
            "OrderMetadataUpdatedEvent": OrderMetadataUpdatedEvent,
            "OrderSyncedFromBrokerEvent": OrderSyncedFromBrokerEvent,
            "OrderStatusUpdatedEvent": OrderStatusUpdatedEvent,
        },
        projection_config={
            "aggregate_type": "Order",
            "transport_topic": ORDER_EVENTS_TOPIC
        },
        sync_events=sync_events,  # FIXED: Load from sync_events.py
        sync_event_config=sync_event_config,  # FIXED: Load config from sync_events.py
        enable_sequence_tracking=True
    )


# =============================================================================
# AUTOMATION DOMAIN CONFIGURATION
# =============================================================================

def create_automation_domain() -> DomainRegistration:
    """
    Factory function for automation domain configuration
    Trading automations with TradersPost webhook support and derivatives
    UPDATED: Now listens to broker account events for cross-domain automation unbinding
    """

    from app.automation.events import (
        AutomationCreatedEvent,
        AutomationUpdatedEvent,
        PyramidingConfigUpdatedEvent,
        AutomationActivatedEvent,
        AutomationDeactivatedEvent,
        AutomationSuspendedEvent,
        AutomationDeletedEvent,
        WebhookSignalReceivedEvent,
        SignalProcessedEvent,
        SignalRejectedEvent,
        PositionSizeCalculatedEvent,
        RiskLimitExceededEvent,
        WebhookTokenRotatedEvent
    )

    # Import broker account events for cross-domain projections
    from app.broker_account.events import (
        BrokerAccountDeleted,
        BrokerAccountsBatchDeleted
    )

    def automation_projector_factory():
        from app.automation.projectors import AUTOMATION_PROJECTORS
        from app.infra.persistence.pg_client import db

        # Create projector container
        class AutomationProjector:
            def __init__(self, pg_client):
                self.pg_client = pg_client
                self.projectors = AUTOMATION_PROJECTORS

            async def handle_event(self, event_dict: dict) -> None:
                """Route event to appropriate projector"""
                event_type = event_dict.get("event_type")

                if event_type in self.projectors:
                    projector_func = self.projectors[event_type]

                    # Reconstruct Pydantic event from dict
                    from app.infra.event_bus.event_registry import EVENT_TYPE_TO_PYDANTIC_MODEL
                    event_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(event_type)

                    if event_class:
                        event_obj = event_class(**event_dict)
                        await projector_func(event_obj, self.pg_client)
                    else:
                        log.error(f"No Pydantic model found for event type: {event_type}")
                else:
                    log.debug(f"No projector for automation event: {event_type}")

        return AutomationProjector(db)

    # Load sync events from sync_events.py
    sync_events, sync_event_config = load_domain_sync_events("automation")

    return DomainRegistration(
        name="automation",
        topics=[
            AUTOMATION_EVENTS_TOPIC,  # Primary topic
            BROKER_ACCOUNT_EVENTS_TOPIC  # Cross-domain: Listen for account deletions
        ],
        projector_factory=automation_projector_factory,
        event_models={
            # Automation domain events
            "AutomationCreatedEvent": AutomationCreatedEvent,
            "AutomationUpdatedEvent": AutomationUpdatedEvent,
            "PyramidingConfigUpdatedEvent": PyramidingConfigUpdatedEvent,
            "AutomationActivatedEvent": AutomationActivatedEvent,
            "AutomationDeactivatedEvent": AutomationDeactivatedEvent,
            "AutomationSuspendedEvent": AutomationSuspendedEvent,
            "AutomationDeletedEvent": AutomationDeletedEvent,
            "WebhookSignalReceivedEvent": WebhookSignalReceivedEvent,
            "SignalProcessedEvent": SignalProcessedEvent,
            "SignalRejectedEvent": SignalRejectedEvent,
            "PositionSizeCalculatedEvent": PositionSizeCalculatedEvent,
            "RiskLimitExceededEvent": RiskLimitExceededEvent,
            "WebhookTokenRotatedEvent": WebhookTokenRotatedEvent,

            # Cross-domain: Broker account deletion events
            "BrokerAccountDeleted": BrokerAccountDeleted,
            "BrokerAccountsBatchDeleted": BrokerAccountsBatchDeleted,
        },
        projection_config={
            "aggregate_type": "Automation",
            "transport_topic": AUTOMATION_EVENTS_TOPIC,
            "cross_topic_events": ["BrokerAccountDeleted", "BrokerAccountsBatchDeleted"]
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True
    )


# =============================================================================
# POSITION DOMAIN CONFIGURATION
# =============================================================================

def create_position_domain() -> DomainRegistration:
    """
    Factory function for position domain configuration
    Position management with pyramiding (position scaling) support
    """

    from app.position.events import (
        PositionOpenedEvent,
        PositionIncreasedEvent,
        PositionReducedEvent,
        PositionClosedEvent,
        PositionPnLUpdatedEvent,
        StopLossUpdatedEvent,
        TakeProfitUpdatedEvent,
        StopLossTriggeredEvent,
        TakeProfitTriggeredEvent,
        PyramidValidationFailedEvent,
        PositionReconciledEvent,
        PositionStateChangedEvent
    )

    def position_projector_factory():
        from app.position.projectors import PositionProjector

        # PositionProjector uses sync decorators and doesn't need read_repo parameter
        # Create and return PositionProjector instance
        return PositionProjector()

    # Load sync events from sync_events.py
    sync_events, sync_event_config = load_domain_sync_events("position")

    return DomainRegistration(
        name="position",
        topics=[POSITION_EVENTS_TOPIC],
        projector_factory=position_projector_factory,
        event_models={
            "PositionOpenedEvent": PositionOpenedEvent,
            "PositionIncreasedEvent": PositionIncreasedEvent,
            "PositionReducedEvent": PositionReducedEvent,
            "PositionClosedEvent": PositionClosedEvent,
            "PositionPnLUpdatedEvent": PositionPnLUpdatedEvent,
            "StopLossUpdatedEvent": StopLossUpdatedEvent,
            "TakeProfitUpdatedEvent": TakeProfitUpdatedEvent,
            "StopLossTriggeredEvent": StopLossTriggeredEvent,
            "TakeProfitTriggeredEvent": TakeProfitTriggeredEvent,
            "PyramidValidationFailedEvent": PyramidValidationFailedEvent,
            "PositionReconciledEvent": PositionReconciledEvent,
            "PositionStateChangedEvent": PositionStateChangedEvent,
        },
        projection_config={
            "aggregate_type": "Position",
            "transport_topic": POSITION_EVENTS_TOPIC
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=True
    )


# =============================================================================
# PORTFOLIO DOMAIN CONFIGURATION
# =============================================================================

def create_portfolio_domain() -> DomainRegistration:
    """
    Factory function for portfolio domain configuration.

    READ-ONLY domain that projects events from other domains:
    - OrderFilledEvent → account_activities
    - PositionClosedEvent → account_activities + portfolio_performance_stats
    - AccountDataFromBrokerUpdated → portfolio_snapshots

    No commands, no aggregate - pure projection-based read models.
    """

    # Import events from other domains that Portfolio listens to
    from app.order.events import OrderFilledEvent
    from app.position.events import PositionClosedEvent
    from app.broker_account.events import AccountDataFromBrokerUpdated

    def portfolio_projector_factory():
        from app.portfolio.projectors import PortfolioProjector

        # Portfolio projector uses pg_db_proxy and cache_manager directly
        # No read repository needed since it's projection-only
        return PortfolioProjector()

    # Portfolio has no sync events (empty sync_events.py)
    sync_events, sync_event_config = load_domain_sync_events("portfolio")

    return DomainRegistration(
        name="portfolio",
        topics=[
            ORDER_EVENTS_TOPIC,  # For OrderFilledEvent
            POSITION_EVENTS_TOPIC,  # For PositionClosedEvent
            BROKER_ACCOUNT_EVENTS_TOPIC,  # For AccountDataFromBrokerUpdated
        ],
        projector_factory=portfolio_projector_factory,
        event_models={
            # Order events
            "OrderFilledEvent": OrderFilledEvent,

            # Position events
            "PositionClosedEvent": PositionClosedEvent,

            # Broker account events
            "AccountDataFromBrokerUpdated": AccountDataFromBrokerUpdated,
        },
        projection_config={
            "aggregate_type": "Portfolio",  # Read-only, no actual aggregate
            "is_read_only": True,
            "cross_topic_events": [
                "OrderFilledEvent",
                "PositionClosedEvent",
                "AccountDataFromBrokerUpdated"
            ],
            "dependencies": ["order", "position", "broker_account"]
        },
        sync_events=sync_events,
        sync_event_config=sync_event_config,
        enable_sequence_tracking=False  # Portfolio doesn't need sequence tracking (read-only)
    )


# =============================================================================
# SAGA NOTIFICATION DOMAIN - FIXED: Handle saga completion events
# =============================================================================

def create_saga_notification_domain() -> DomainRegistration:
    """
    FIXED: Factory function for saga notification domain configuration.
    This domain handles saga completion events that don't need projection updates
    but should be acknowledged to prevent them from going to DLQ.
    """

    # Import saga event classes (consolidated in infra/saga)
    from app.infra.saga.saga_events import (
        BrokerDisconnectionCompleted,
        BrokerConnectionEstablishedSagaCompleted,
        UserDeletionCompleted,
        # Saga lifecycle events
        SagaStarted,
        SagaCompleted,
        SagaFailed,
        SagaCompensationStarted,
        SagaCompensationCompleted,
        # Additional saga events
        SagaStepCompleted,
        SagaStepFailed,
        SagaTimedOut,
        SagaManualInterventionRequired,
        # Monitoring events
        SagaTriggered
    )

    # Import broker account domain events (NOT saga events)
    from app.broker_account.events import (
        AccountDiscoveryCompleted,
        AllAccountsRefreshCompleted,
        BulkArchiveCompleted,
        BrokerAccountsDeleted
    )

    # FIXED: Import virtual broker events
    from app.virtual_broker.events import VirtualBrokerCleanupCompleted

    def saga_notification_projector_factory(event_bus_instance=None):
        """Create a simple projector that just logs saga completion events"""

        class SagaNotificationProjector:
            def __init__(self, event_bus_param=None):
                self.event_bus = event_bus_param

            async def handle_event(self, event_dict: Dict[str, Any]) -> None:
                """Handle saga notification events by logging them"""
                event_type = event_dict.get("event_type")
                event_id = event_dict.get("event_id")
                saga_id = event_dict.get("saga_id")

                log.info(f"Saga notification: {event_type} (event: {event_id}, saga: {saga_id})")

                # Special handling for specific event types
                if event_type == "BrokerConnectionEstablished":
                    connection_id = event_dict.get("aggregate_id", "unknown")
                    log.debug(f"Broker connection established (handled by server sync): {connection_id}")

                elif event_type == "BrokerConnectionStatusReset":
                    connection_id = event_dict.get("connection_id", "unknown")
                    log.info(f"Broker connection status reset for: {connection_id}")

                elif event_type == "VirtualBrokerReadyForDiscovery":
                    connection_id = event_dict.get("connection_id", "unknown")
                    log.info(f"Virtual broker ready for discovery: {connection_id}")

                elif event_type == "VirtualBrokerUserConnected":
                    user_id = event_dict.get("user_id", "unknown")
                    connection_id = event_dict.get("connection_id", "unknown")
                    log.info(f"Virtual broker user connected: {user_id}, connection: {connection_id}")

                elif event_type == "VirtualBrokerUserDisconnected":
                    user_id = event_dict.get("user_id", "unknown")
                    connection_id = event_dict.get("connection_id", "unknown")
                    log.info(f"Virtual broker user disconnected: {user_id}, connection: {connection_id}")

                elif event_type == "VirtualBrokerCleanupCompleted":  # ADDED
                    user_id = event_dict.get("user_id", "unknown")
                    account_count = event_dict.get("accounts_deleted", 0)
                    log.info(f"Virtual broker cleanup completed for user {user_id}: {account_count} accounts deleted")

                elif event_type == "BrokerConnectionEstablishedSagaCompleted":  # FIXED: Use correct event name
                    connection_summary = event_dict.get("connection_summary", {})  # FIXED: Use correct field
                    account_count = connection_summary.get("account_count", 0)
                    log.info(f"Broker connection established saga completed with {account_count} accounts discovered")

                elif event_type == "BrokerDisconnectionCompleted":  # FIXED: Use correct event name
                    disconnection_summary = event_dict.get("disconnection_summary", {})  # FIXED: Use correct field
                    accounts_deleted = disconnection_summary.get("accounts_deleted", 0)
                    broker_id = disconnection_summary.get("broker_id", "unknown")
                    log.info(f"Broker disconnection completed for {broker_id} with {accounts_deleted} accounts deleted")

                elif event_type == "BrokerDisconnectionAbandoned":  # FIXED: Handle race condition
                    broker_connection_id = event_dict.get("broker_connection_id", "unknown")
                    reason = event_dict.get("reason", "unknown")
                    log.warning(
                        f"Broker disconnection abandoned for {broker_connection_id} - "
                        f"reason: {reason} (likely reconnected during disconnection)"
                    )

                elif event_type == "AccountDiscoveryCompleted":
                    discovered_count = event_dict.get("discovered_count", 0)
                    linked_count = event_dict.get("linked_count", 0)
                    log.info(f"Account discovery completed: {discovered_count} discovered, {linked_count} linked")

                # OrderStreamingUpdate removed - now handled directly in BrokerOperationService via CommandBus

                elif event_type == "BrokerAccountsDeleted":
                    deleted_count = event_dict.get("deleted_count", 0)
                    deletion_type = event_dict.get("deletion_type", "unknown")
                    reason = event_dict.get("deletion_reason", "unknown")
                    log.info(
                        f"Broker accounts deleted: {deleted_count} accounts ({deletion_type} delete, reason: {reason})")

                elif event_type == "BrokerAccountDeleted":  # ADDED
                    account_id = event_dict.get("account_id", "unknown")
                    broker_connection_id = event_dict.get("broker_connection_id", "unknown")
                    log.info(f"Broker account {account_id} deleted for connection {broker_connection_id}")

                elif event_type == "UserDeletionCompleted":
                    deletion_summary = event_dict.get("deletion_summary", {})
                    brokers_disconnected = deletion_summary.get("brokers_disconnected", 0)
                    log.info(f"User deletion completed with {brokers_disconnected} brokers disconnected")

        return SagaNotificationProjector(event_bus_instance)

    return DomainRegistration(
        name="saga_notifications",
        topics=[
            BROKER_CONNECTION_EVENTS_TOPIC,  # For connection saga events
            BROKER_ACCOUNT_EVENTS_TOPIC,  # For account saga events
            USER_ACCOUNT_EVENTS_TOPIC,  # For user saga events
            VIRTUAL_BROKER_EVENTS_TOPIC,  # Add virtual broker events
            # ORDER_EVENTS_TOPIC removed - order updates now via CommandBus directly
        ],
        projector_factory=saga_notification_projector_factory,
        event_models={
            # Sync-only events that workers should acknowledge but not process
            "BrokerOAuthFlowStarted": None,  # Sync-only event handled by server
            "BrokerTokensSuccessfullyStored": None,  # Sync-only event handled by server
            "BrokerApiEndpointConfigured": None,  # Sync-only event handled by server
            "BrokerConnectionEstablished": None,  # FIXED: Sync-only event handled by server

            # Connection events that don't need projection updates
            "BrokerConnectionStatusReset": None,
            "VirtualBrokerReadyForDiscovery": None,
            "VirtualBrokerUserConnected": None,
            "VirtualBrokerUserDisconnected": None,  # ADDED

            # FIXED: Import and use actual event classes instead of None
            "VirtualBrokerCleanupCompleted": VirtualBrokerCleanupCompleted,
            "BrokerConnectionEstablishedSagaCompleted": BrokerConnectionEstablishedSagaCompleted,
            "BrokerDisconnectionCompleted": BrokerDisconnectionCompleted,
            "BrokerDisconnectionAbandoned": None,  # FIXED: Handle disconnection race condition
            "AccountDiscoveryCompleted": AccountDiscoveryCompleted,
            "BrokerAccountsDeleted": BrokerAccountsDeleted,
            "BrokerAccountDeleted": None,  # ADDED: Individual account deletion
            "AllAccountsRefreshCompleted": AllAccountsRefreshCompleted,
            "BulkArchiveCompleted": BulkArchiveCompleted,
            "UserDeletionCompleted": UserDeletionCompleted,

            # Saga lifecycle events
            "SagaStarted": SagaStarted,
            "SagaCompleted": SagaCompleted,
            "SagaFailed": SagaFailed,
            "SagaCompensationStarted": SagaCompensationStarted,
            "SagaCompensationCompleted": SagaCompensationCompleted,

            # Additional saga events
            "SagaTriggered": SagaTriggered,  # FIXED: Use actual event class
            "SagaStepCompleted": SagaStepCompleted,
            "SagaStepFailed": SagaStepFailed,
            "SagaTimedOut": SagaTimedOut,
            "SagaManualInterventionRequired": SagaManualInterventionRequired,
        },
        projection_config={
            "aggregate_type": "SagaNotification",
            "purpose": "acknowledgment_only",
            "skip_projection": True
        },
        sync_events=set(),  # No sync events for saga notifications
        sync_event_config={},
        enable_sequence_tracking=False  # Saga notifications don't need sequence tracking
    )


# =============================================================================
# DOMAIN REGISTRY - Enhanced with Multi-Topic and Sync Support
# =============================================================================

class DomainRegistry:
    """
    Central registry for domain EVENT PROCESSING configuration.
    ENHANCED: Now supports domains listening to multiple topics and sync projections.
    UPDATED: Properly initializes read repositories with CacheManager
    FIXED: Better error handling for missing projector instances
    """

    def __init__(self):
        self._domains: Dict[str, DomainRegistration] = {}
        self._topic_to_domains: Dict[str, List[DomainRegistration]] = {}  # CHANGED: Now list of domains
        self._all_sync_events: Set[str] = set()  # NEW: All sync events across domains
        self._sync_event_to_domains: Dict[str, List[str]] = {}  # NEW: Which domains handle each sync event
        self._initialized = False

    def register(self, domain: DomainRegistration) -> None:
        """Register a domain configuration for event processing"""
        if domain.name in self._domains:
            raise ValueError(f"Domain {domain.name} already registered")

        self._domains[domain.name] = domain

        # Register all topics this domain listens to
        for topic in domain.topics:
            if topic not in self._topic_to_domains:
                self._topic_to_domains[topic] = []
            self._topic_to_domains[topic].append(domain)

        # Register sync events
        self._all_sync_events.update(domain.sync_events)
        for sync_event in domain.sync_events:
            if sync_event not in self._sync_event_to_domains:
                self._sync_event_to_domains[sync_event] = []
            self._sync_event_to_domains[sync_event].append(domain.name)

        log.info(
            f"Registered domain: {domain.name} for topics: {domain.topics} "
            f"with {len(domain.event_models)} event types and {len(domain.sync_events)} sync events"
        )

    def get_by_name(self, name: str) -> Optional[DomainRegistration]:
        """Get domain by name"""
        return self._domains.get(name)

    def get_domains_for_topic(self, topic: str) -> List[DomainRegistration]:
        """Get all domains that listen to a specific topic"""
        return self._topic_to_domains.get(topic, [])

    def get_all_topics(self) -> List[str]:
        """Get all registered topics"""
        return list(self._topic_to_domains.keys())

    def get_enabled_domains(self) -> List[DomainRegistration]:
        """Get all enabled domains"""
        return [d for d in self._domains.values() if d.enabled]

    def get_all_domains(self) -> Dict[str, DomainRegistration]:
        """Get all registered domains (enabled and disabled)"""
        return self._domains.copy()

    def get_all_sync_events(self) -> Set[str]:
        """
        Get all sync events across all domains.
        Now sources from @sync_projection decorators (single source of truth).
        """
        return get_decorator_sync_events()

    def get_domains_for_sync_event(self, event_type: str) -> List[str]:
        """Get domains that handle a specific sync event"""
        return self._sync_event_to_domains.get(event_type, [])

    def is_sync_event(self, event_type: str) -> bool:
        """
        Check if an event type is marked for sync projection.
        Now sources from @sync_projection decorators (single source of truth).
        """
        return event_type in get_decorator_sync_events()

    async def initialize_all(self, event_bus=None, auth_service=None, query_bus=None, **kwargs) -> None:
        """
        Initialize all enabled domain projectors
        UPDATED: Properly handles CacheManager for all read repositories
        FIXED: Better error handling and logging
        FIXED: Pass all optional dependencies gracefully
        """
        if self._initialized:
            log.warning("Domain registry already initialized")
            return

        successful_initializations = 0
        failed_initializations = []

        for domain in self.get_enabled_domains():
            try:
                # Pass appropriate parameters based on domain requirements
                init_kwargs = {}

                if domain.name == "broker_account" and event_bus:
                    init_kwargs['event_bus'] = event_bus
                elif domain.name == "broker_connection":
                    # Pass optional dependencies - can be None in worker context
                    init_kwargs['query_bus_instance'] = query_bus
                    # auth_service is no longer needed by the projector
                elif domain.name == "saga_notifications":
                    init_kwargs['event_bus_instance'] = event_bus
                elif domain.name == "virtual_broker":
                    # Virtual broker projector handles optional app parameter
                    init_kwargs['app'] = kwargs.get('app')
                else:
                    # User domain and others don't need extra parameters
                    pass

                await domain.initialize_projector(**init_kwargs)

                if domain.has_projector():
                    log.info(f"Successfully initialized projector for domain: {domain.name}")
                    successful_initializations += 1
                else:
                    log.warning(f"Domain {domain.name} has no projector instance after initialization")
                    failed_initializations.append(domain.name)

            except Exception as e:
                log.error(f"Failed to initialize projector for domain {domain.name}: {e}", exc_info=True)
                failed_initializations.append(domain.name)
                # Continue with other domains instead of failing completely
                continue

        self._initialized = True

        # Log sync events summary
        sync_events_by_domain = {}
        for domain in self.get_enabled_domains():
            if domain.sync_events:
                sync_events_by_domain[domain.name] = len(domain.sync_events)

        log.info(
            f"Initialized {successful_initializations}/{len(self.get_enabled_domains())} domain projectors. "
            f"Failed: {failed_initializations}. "
            f"Total sync events: {len(self._all_sync_events)}. "
            f"Sync events by domain: {sync_events_by_domain}"
        )

        if failed_initializations:
            log.warning(f"Failed to initialize domains: {failed_initializations}")

    def get_event_model(self, topic: str, event_type: str) -> Optional[Type[BaseEvent]]:
        """Get the event model class for a given topic and event type"""
        # Check all domains that listen to this topic
        domains = self.get_domains_for_topic(topic)
        for domain in domains:
            model = domain.event_models.get(event_type)
            if model:
                return model
        return None

    def get_all_event_types(self) -> Dict[str, List[str]]:
        """Get all registered event types grouped by domain"""
        all_events = {}
        for domain_name, domain in self._domains.items():
            all_events[domain_name] = list(domain.event_models.keys())
        return all_events

    def get_projector_for_domain(self, domain_name: str) -> Optional[Any]:
        """Get projector instance for a domain"""
        domain = self.get_by_name(domain_name)
        if domain and domain.has_projector():
            return domain.projector_instance
        return None

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry"""
        stats = {
            "total_domains": len(self._domains),
            "enabled_domains": len(self.get_enabled_domains()),
            "initialized_domains": sum(1 for d in self._domains.values() if d.has_projector()),
            "total_topics": len(self._topic_to_domains),
            "total_event_types": sum(len(d.event_models) for d in self._domains.values()),
            "total_sync_events": len(self._all_sync_events),
            "cross_topic_domains": [],
            "domains": {}
        }

        for domain_name, domain in self._domains.items():
            is_cross_topic = len(domain.topics) > 1
            if is_cross_topic:
                stats["cross_topic_domains"].append(domain_name)

            domain_stats = {
                "enabled": domain.enabled,
                "has_projector": domain.has_projector(),
                "event_types": len(domain.event_models),
                "sync_events": len(domain.sync_events),
                "topics": domain.topics,
                "is_cross_topic": is_cross_topic,
                "enable_sequence_tracking": domain.enable_sequence_tracking  # Include the new attribute
            }
            stats["domains"][domain_name] = domain_stats

        return stats

    def get_sync_event_config(self, event_type: str) -> Dict[str, Any]:
        """Get configuration for a sync event"""
        for domain in self._domains.values():
            if event_type in domain.sync_event_config:
                return domain.sync_event_config[event_type]
        return {}


# =============================================================================
# CREATE AND POPULATE REGISTRY - FIXED with Saga Domain
# =============================================================================

def create_domain_registry() -> DomainRegistry:
    """
    Create and populate the domain registry with all configured domains.
    ENHANCED: Now with multi-topic support for cross-domain event handling.
    FIXED: Includes saga notification domain to handle completion events.
    ADDED: Virtual broker domain for virtual trading accounts.
    ADDED: Sync projections support.
    UPDATED: All read repositories use CacheManager
    """
    registry = DomainRegistry()

    # Register all domains
    registry.register(create_user_domain())
    registry.register(create_broker_account_domain())
    registry.register(create_broker_connection_domain())
    registry.register(create_saga_notification_domain())  # FIXED: Add saga domain
    registry.register(create_virtual_broker_domain())  # ADDED: Virtual broker domain
    registry.register(create_order_domain())  # ADDED: Order domain
    registry.register(create_automation_domain())  # ADDED: Automation domain
    registry.register(create_position_domain())  # ADDED: Position domain with pyramiding
    registry.register(create_portfolio_domain())  # ADDED: Portfolio domain (read-only, projection-based)

    log.info(
        "Domain registry created with multi-topic support, saga event handling, virtual broker support, "
        "order domain, automation domain, position domain, portfolio domain (read-only), sync projections, "
        "and CacheManager integration"
    )

    # Log registry statistics
    stats = registry.get_registry_stats()
    log.info(
        f"Registry initialized with {stats['total_domains']} domains, "
        f"{stats['total_topics']} topics, {stats['total_event_types']} event types, "
        f"{stats['total_sync_events']} sync events"
    )

    if stats["cross_topic_domains"]:
        log.info(f"Cross-topic domains: {stats['cross_topic_domains']}")

    return registry


# Global registry instance
DOMAIN_REGISTRY = create_domain_registry()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_domain_registry() -> Dict[str, Any]:
    """Validate the domain registry for completeness"""
    registry = DOMAIN_REGISTRY
    validation_report = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": registry.get_registry_stats()
    }

    # Check for duplicate event types across domains
    all_events = {}
    for domain_name, domain in registry.get_all_domains().items():
        for event_type in domain.event_models.keys():
            if event_type not in all_events:
                all_events[event_type] = []
            all_events[event_type].append(domain_name)

    duplicates = {event: domains for event, domains in all_events.items() if len(domains) > 1}
    if duplicates:
        # This is now expected for cross-domain events and saga notifications
        validation_report["info"] = f"Cross-domain events: {duplicates}"

    # Check for missing critical events
    critical_events = [
        "BrokerConnectionEstablished", "BrokerDisconnected",
        "BrokerAccountLinked", "UserAccountCreated", "UserDeleted"
    ]

    missing_critical = []
    for event in critical_events:
        if event not in all_events:
            missing_critical.append(event)

    if missing_critical:
        validation_report["errors"].append(f"Missing critical events: {missing_critical}")
        validation_report["valid"] = False

    # Verify cross-domain setup
    # NOTE: BrokerDisconnected is no longer handled directly by broker_account domain.
    # The saga pattern now handles deletions via DeleteBrokerAccountCommand, which
    # emits BrokerAccountDeleted events. This maintains CQRS/ES compliance.

    # Verify saga notification domain
    saga_domain = registry.get_by_name("saga_notifications")
    if not saga_domain:
        validation_report["warnings"].append("No saga notification domain configured")
    elif "BrokerConnectionEstablishedSagaCompleted" not in saga_domain.event_models:
        validation_report["warnings"].append("Saga domain missing completion events")

    # Verify virtual broker domain
    virtual_domain = registry.get_by_name("virtual_broker")
    if not virtual_domain:
        validation_report["warnings"].append("No virtual broker domain configured")
    elif "VirtualAccountCreated" not in virtual_domain.event_models:
        validation_report["errors"].append("Virtual broker domain missing VirtualAccountCreated event")
        validation_report["valid"] = False

    # Verify sync events
    for domain_name, domain in registry.get_all_domains().items():
        for event_type in domain.sync_events:
            if event_type not in domain.event_models:
                validation_report["warnings"].append(
                    f"Domain {domain_name} has sync event {event_type} but no event model"
                )

    # Check for uninitialized projectors
    for domain_name, domain in registry.get_all_domains().items():
        if domain.enabled and not domain.has_projector():
            validation_report["warnings"].append(
                f"Domain {domain_name} is enabled but has no projector instance"
            )

    return validation_report


def get_all_domains_for_event(event_type: str) -> List[str]:
    """Get all domains that handle a specific event type"""
    domains = []
    for domain_name, domain in DOMAIN_REGISTRY.get_all_domains().items():
        if event_type in domain.event_models:
            domains.append(domain_name)
    return domains

# =============================================================================
# EOF
# =============================================================================