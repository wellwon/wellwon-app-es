# app/infra/cqrs/handler_dependencies.py
# =============================================================================
# File: app/infra/cqrs/handler_dependencies.py
# Description: Common dependencies container for all handlers
# =============================================================================

from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

# Import core infrastructure
from app.infra.event_bus.event_bus import EventBus
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from app.infra.cqrs.command_bus import CommandBus
    from app.infra.cqrs.query_bus import QueryBus
    from app.services.application.broker_operation_service import BrokerOperationService
    from app.services.infrastructure.market_data_service import MarketDataService
    from app.services.infrastructure.adapter_monitoring.adapter_monitoring_service import AdapterMonitoringService
    from app.services.application.broker_auth_service import BrokerAuthenticationService
    from app.services.application.user_auth_service import UserAuthenticationService
    from app.virtual_broker.services.virtual_broker_service import VirtualBrokerService
    from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
    from app.infra.read_repos.broker_connection_read_repo import BrokerConnectionReadRepo
    from app.infra.read_repos.broker_account_read_repo import BrokerAccountReadRepo
    from app.infra.read_repos.virtual_broker_read_repo import VirtualBrokerReadRepo
    from app.infra.read_repos.order_read_repo import OrderReadRepository
    from app.infra.read_repos.position_read_repo import PositionReadRepository
    from app.infra.read_repos.portfolio_read_repo import PortfolioReadRepository
    from app.infra.read_repos.automation_read_repo import AutomationReadRepository
    from app.infra.persistence.cache_manager import CacheManager
    from app.infra.saga.saga_manager import SagaManager


@dataclass
class HandlerDependencies:
    """Container for all handler dependencies - injected from outside."""
    # Core infrastructure
    event_bus: EventBus
    event_store: Optional[KurrentDBEventStore] = None

    # CQRS buses (for handlers that need to send other commands/queries)
    command_bus: Optional['CommandBus'] = None
    query_bus: Optional['QueryBus'] = None

    # Services (all injected from outside)
    operation_service: Optional['BrokerOperationService'] = None
    market_data_service: Optional['MarketDataService'] = None
    monitoring_service: Optional['AdapterMonitoringService'] = None
    auth_service: Optional['BrokerAuthenticationService'] = None
    user_auth_service: Optional['UserAuthenticationService'] = None

    # Saga manager
    saga_manager: Optional['SagaManager'] = None

    # Virtual broker service
    virtual_broker_service: Optional['VirtualBrokerService'] = None

    # Repositories (all injected from outside) - RENAMED for consistency
    user_read_repo: Optional['UserAccountReadRepo'] = None
    broker_connection_read_repo: Optional['BrokerConnectionReadRepo'] = None  # Was: broker_conn_read_repo
    broker_account_read_repo: Optional['BrokerAccountReadRepo'] = None  # Was: account_read_repo
    virtual_broker_read_repo: Optional['VirtualBrokerReadRepo'] = None
    order_read_repo: Optional['OrderReadRepository'] = None
    position_read_repo: Optional['PositionReadRepository'] = None
    portfolio_read_repo: Optional['PortfolioReadRepository'] = None
    automation_read_repo: Optional['AutomationReadRepository'] = None

    # Infrastructure
    cache_manager: Optional['CacheManager'] = None

    # Configuration
    global_config: Dict[str, Any] = field(default_factory=dict)

    # Application state (for special cases)
    app: Optional[Any] = None