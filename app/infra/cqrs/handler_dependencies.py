"""
Handler Dependencies - WellWon Platform

Common dependencies container for all command and query handlers.

Architecture: Ports & Adapters (Hexagonal Architecture)
- Ports are defined in domain: app/{domain}/ports/
- Adapters implement ports: app/infra/{service}/adapter.py
- Dependencies inject port types, not concrete adapters
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
    from app.infra.read_repos.message_scylla_repo import MessageScyllaRepo
    from app.infra.persistence.cache_manager import CacheManager
    from app.infra.saga.saga_manager import SagaManager

    # Port types (interface definitions from domains)
    from app.customs.ports.kontur_declarant_port import KonturDeclarantPort
    from app.chat.ports.telegram_messaging_port import TelegramMessagingPort
    from app.company.ports.telegram_groups_port import TelegramGroupsPort
    from app.company.ports.company_enrichment_port import CompanyEnrichmentPort

    # Concrete adapter types (for backward compatibility)
    from app.infra.telegram.adapter import TelegramAdapter
    from app.infra.kontur.adapter import KonturAdapter


@dataclass
class HandlerDependencies:
    """
    Container for all handler dependencies.

    Dependencies are injected from application startup.

    Architecture Pattern: Ports & Adapters
    =======================================
    Handlers should use PORT types (interfaces) not concrete adapters:
    - self._kontur = deps.kontur_adapter  # Implements KonturDeclarantPort
    - self._telegram = deps.telegram_adapter  # Implements TelegramMessagingPort

    This allows:
    - Testing with Fake adapters
    - Swapping implementations without changing handlers
    - Clean separation between domain and infrastructure
    """

    # =========================================================================
    # Core Infrastructure
    # =========================================================================

    event_bus: EventBus
    event_store: Optional[KurrentDBEventStore] = None

    command_bus: Optional['CommandBus'] = None
    query_bus: Optional['QueryBus'] = None

    # =========================================================================
    # Application Services
    # =========================================================================

    user_auth_service: Optional['UserAuthenticationService'] = None
    saga_manager: Optional['SagaManager'] = None

    # =========================================================================
    # Read Repositories
    # =========================================================================

    user_read_repo: Optional['UserAccountReadRepo'] = None
    company_read_repo: Optional['CompanyReadRepo'] = None
    chat_read_repo: Optional['ChatReadRepo'] = None
    message_scylla_repo: Optional['MessageScyllaRepo'] = None

    # =========================================================================
    # Infrastructure
    # =========================================================================

    cache_manager: Optional['CacheManager'] = None

    # =========================================================================
    # Adapters (implement domain ports)
    #
    # These are concrete adapters that implement domain port interfaces.
    # Handlers should type-hint with port types for better abstraction:
    #
    #   self._kontur: 'KonturDeclarantPort' = deps.kontur_adapter
    #   self._telegram: 'TelegramMessagingPort' = deps.telegram_adapter
    #
    # Port interfaces defined in:
    #   - app/customs/ports/kontur_declarant_port.py
    #   - app/chat/ports/telegram_messaging_port.py
    #   - app/company/ports/telegram_groups_port.py
    #   - app/company/ports/company_enrichment_port.py
    # =========================================================================

    # Kontur Declarant API - implements KonturDeclarantPort
    # Used by: Customs domain (declarations, organizations, forms)
    kontur_adapter: Optional['KonturAdapter'] = None

    # Telegram API - implements TelegramMessagingPort + TelegramGroupsPort
    # Used by: Chat domain (messaging), Company domain (group management)
    telegram_adapter: Optional['TelegramAdapter'] = None

    # DaData API - implements CompanyEnrichmentPort
    # Used by: Company domain (company lookup, autocomplete)
    # Note: Currently accessed via get_dadata_adapter() singleton
    # TODO: Add dadata_adapter field when Company domain is fully implemented

    # =========================================================================
    # Configuration
    # =========================================================================

    global_config: Dict[str, Any] = field(default_factory=dict)
    app: Optional[Any] = None
