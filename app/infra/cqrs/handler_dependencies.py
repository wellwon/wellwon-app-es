"""
Handler Dependencies - WellWon Platform

Common dependencies container for all command and query handlers.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from app.infra.event_bus.event_bus import EventBus
from app.infra.event_store.kurrentdb_event_store import KurrentDBEventStore

if TYPE_CHECKING:
    from app.infra.cqrs.command_bus import CommandBus
    from app.infra.cqrs.query_bus import QueryBus
    from app.services.application.user_auth_service import UserAuthenticationService
    from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
    from app.infra.read_repos.company_read_repo import CompanyReadRepo
    from app.infra.read_repos.chat_read_repo import ChatReadRepo
    from app.infra.persistence.cache_manager import CacheManager
    from app.infra.saga.saga_manager import SagaManager


@dataclass
class HandlerDependencies:
    """
    Container for all handler dependencies.

    Dependencies are injected from application startup.
    Only includes WellWon-relevant services and repositories.
    """

    event_bus: EventBus
    event_store: Optional[KurrentDBEventStore] = None

    command_bus: Optional['CommandBus'] = None
    query_bus: Optional['QueryBus'] = None

    user_auth_service: Optional['UserAuthenticationService'] = None

    saga_manager: Optional['SagaManager'] = None

    user_read_repo: Optional['UserAccountReadRepo'] = None
    company_read_repo: Optional['CompanyReadRepo'] = None
    chat_read_repo: Optional['ChatReadRepo'] = None

    cache_manager: Optional['CacheManager'] = None

    global_config: Dict[str, Any] = field(default_factory=dict)

    app: Optional[Any] = None
