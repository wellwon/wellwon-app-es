# =============================================================================
# File: app/infra/worker_core/event_processor/domain_registry.py
# Description: Domain Registry for WellWon Platform
# Registers domain projectors for event processing
# Based on TradeCore architecture with DomainRegistration dataclass
# =============================================================================

import logging
from typing import Dict, Any, List, Optional, Callable, Type, Set
from dataclasses import dataclass, field

from app.common.base.base_model import BaseEvent
from app.infra.cqrs.projector_decorators import get_all_sync_events

log = logging.getLogger("wellwon.worker.domain_registry")

# Topic constants
USER_ACCOUNT_EVENTS_TOPIC = "transport.user-account-events"
COMPANY_EVENTS_TOPIC = "transport.company-events"
CHAT_EVENTS_TOPIC = "transport.chat-events"


# =============================================================================
# DOMAIN REGISTRATION MODEL
# =============================================================================

@dataclass
class DomainRegistration:
    """Configuration for a single domain's event processing"""
    name: str
    topics: List[str]
    projector_factory: Callable[..., Any]
    event_models: Dict[str, Optional[Type[BaseEvent]]]
    projection_config: Optional[Dict[str, Any]] = None
    enabled: bool = True
    projector_instance: Optional[Any] = None
    sync_events: Set[str] = field(default_factory=set)
    enable_sequence_tracking: bool = True

    @property
    def primary_topic(self) -> str:
        """Get the primary topic for backward compatibility"""
        return self.topics[0] if self.topics else ""

    async def initialize_projector(self, **kwargs) -> Any:
        """Initialize the projector instance using the factory"""
        if not self.enabled:
            log.info(f"Domain {self.name} is disabled, skipping initialization")
            return None

        try:
            self.projector_instance = self.projector_factory(**kwargs)
            log.info(f"Initialized projector for domain: {self.name}")
            return self.projector_instance
        except Exception as e:
            log.error(f"Failed to initialize projector for domain {self.name}: {e}")
            raise

    def has_projector(self) -> bool:
        """Check if projector instance exists"""
        return self.projector_instance is not None


# =============================================================================
# USER ACCOUNT DOMAIN CONFIGURATION
# =============================================================================

def create_user_account_domain() -> DomainRegistration:
    """Factory function for user account domain configuration"""

    # Import projector module FIRST to trigger @sync_projection decorator registration
    import app.user_account.projectors

    from app.user_account.events import (
        UserAccountCreated,
        UserAccountDeleted,
        UserEmailVerified,
        UserProfileUpdated,
        UserAuthenticationSucceeded,
        UserAuthenticationFailed,
        UserPasswordChanged,
        UserLoggedOut,
    )

    def user_projector_factory():
        from app.user_account.projectors import UserAccountProjector
        from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo
        from app.infra.persistence.cache_manager import get_cache_manager

        try:
            cache_manager = get_cache_manager()
            read_repo = UserAccountReadRepo(cache_manager=cache_manager)
        except Exception:
            read_repo = UserAccountReadRepo()

        return UserAccountProjector(read_repo)

    # NOTE: sync_events removed - now auto-discovered from @sync_projection decorators
    # Single source of truth: projector_decorators.get_all_sync_events()

    return DomainRegistration(
        name="user_account",
        topics=[USER_ACCOUNT_EVENTS_TOPIC],
        projector_factory=user_projector_factory,
        event_models={
            # Standard domain events
            "UserAccountCreated": UserAccountCreated,
            "UserAccountDeleted": UserAccountDeleted,
            "UserEmailVerified": UserEmailVerified,
            "UserProfileUpdated": UserProfileUpdated,
            "UserAuthenticationSucceeded": UserAuthenticationSucceeded,
            "UserAuthenticationFailed": UserAuthenticationFailed,
            "UserPasswordChanged": UserPasswordChanged,
            "UserLoggedOut": UserLoggedOut,
            # CES Events (Compensating Event System - External Change Detection)
            # Pattern: Greg Young's Compensating Events via PostgreSQL triggers
            # These don't have dedicated models - use None for pass-through processing
            "UserRoleChangedExternally": None,
            "UserStatusChangedExternally": None,
            "UserTypeChangedExternally": None,
            "UserEmailVerifiedExternally": None,
            "UserDeveloperStatusChangedExternally": None,
            "UserAdminFieldsChangedExternally": None,
        },
        projection_config={
            "aggregate_type": "UserAccount",
            "transport_topic": USER_ACCOUNT_EVENTS_TOPIC
        },
        enable_sequence_tracking=True
    )


# =============================================================================
# COMPANY DOMAIN CONFIGURATION
# =============================================================================

def create_company_domain() -> DomainRegistration:
    """Factory function for company domain configuration"""

    # Import projector module to trigger decorator registration
    import app.company.projectors

    from app.company.events import (
        CompanyCreated,
        CompanyUpdated,
        CompanyArchived,
        CompanyRestored,
        CompanyDeleted,
        CompanyDeleteRequested,
        UserAddedToCompany,
        UserRemovedFromCompany,
        UserCompanyRoleChanged,
        TelegramSupergroupCreated,
        TelegramSupergroupLinked,
        TelegramSupergroupUnlinked,
        TelegramSupergroupUpdated,
        TelegramSupergroupDeleted,
        CompanyBalanceUpdated,
    )

    def company_projector_factory():
        from app.company.projectors import CompanyProjector
        from app.infra.read_repos.company_read_repo import CompanyReadRepo

        # CompanyReadRepo uses static methods - no instance initialization needed
        read_repo = CompanyReadRepo()
        return CompanyProjector(read_repo)

    return DomainRegistration(
        name="company",
        topics=[COMPANY_EVENTS_TOPIC],
        projector_factory=company_projector_factory,
        event_models={
            "CompanyCreated": CompanyCreated,
            "CompanyUpdated": CompanyUpdated,
            "CompanyArchived": CompanyArchived,
            "CompanyRestored": CompanyRestored,
            "CompanyDeleted": CompanyDeleted,
            "CompanyDeleteRequested": CompanyDeleteRequested,
            "UserAddedToCompany": UserAddedToCompany,
            "UserRemovedFromCompany": UserRemovedFromCompany,
            "UserCompanyRoleChanged": UserCompanyRoleChanged,
            "TelegramSupergroupCreated": TelegramSupergroupCreated,
            "TelegramSupergroupLinked": TelegramSupergroupLinked,
            "TelegramSupergroupUnlinked": TelegramSupergroupUnlinked,
            "TelegramSupergroupUpdated": TelegramSupergroupUpdated,
            "TelegramSupergroupDeleted": TelegramSupergroupDeleted,
            "CompanyBalanceUpdated": CompanyBalanceUpdated,
        },
        projection_config={
            "aggregate_type": "Company",
            "transport_topic": COMPANY_EVENTS_TOPIC
        },
        enable_sequence_tracking=True
    )


# =============================================================================
# CHAT DOMAIN CONFIGURATION
# =============================================================================

def create_chat_domain() -> DomainRegistration:
    """Factory function for chat domain configuration"""

    # Import projector module to trigger decorator registration
    import app.chat.projectors

    from app.chat.events import (
        ChatCreated,
        ChatUpdated,
        ChatArchived,
        ChatRestored,
        ChatHardDeleted,
        ChatLinkedToCompany,
        ChatUnlinkedFromCompany,
        ParticipantAdded,
        ParticipantRemoved,
        ParticipantRoleChanged,
        ParticipantLeft,
        MessageSent,
        MessageEdited,
        MessageDeleted,
        MessageReadStatusUpdated,
        MessagesMarkedAsRead,
        TypingStarted,
        TypingStopped,
        TelegramChatLinked,
        TelegramChatUnlinked,
        TelegramMessageReceived,
    )

    def chat_projector_factory():
        """
        Create ChatProjector with Discord-style architecture.

        ScyllaDB = PRIMARY for messages (REQUIRED)
        PostgreSQL = METADATA only
        """
        from app.chat.projectors import ChatProjector
        from app.infra.read_repos.chat_read_repo import ChatReadRepo
        from app.infra.read_repos.message_scylla_repo import MessageScyllaRepo

        # PostgreSQL for metadata
        read_repo = ChatReadRepo()

        # ScyllaDB for messages (REQUIRED - Discord pattern)
        message_scylla_repo = MessageScyllaRepo()

        return ChatProjector(read_repo, message_scylla_repo)

    return DomainRegistration(
        name="chat",
        topics=[CHAT_EVENTS_TOPIC],
        projector_factory=chat_projector_factory,
        event_models={
            "ChatCreated": ChatCreated,
            "ChatUpdated": ChatUpdated,
            "ChatArchived": ChatArchived,
            "ChatRestored": ChatRestored,
            "ChatHardDeleted": ChatHardDeleted,
            "ChatLinkedToCompany": ChatLinkedToCompany,
            "ChatUnlinkedFromCompany": ChatUnlinkedFromCompany,
            "ParticipantAdded": ParticipantAdded,
            "ParticipantRemoved": ParticipantRemoved,
            "ParticipantRoleChanged": ParticipantRoleChanged,
            "ParticipantLeft": ParticipantLeft,
            "MessageSent": MessageSent,
            "MessageEdited": MessageEdited,
            "MessageDeleted": MessageDeleted,
            "MessageReadStatusUpdated": MessageReadStatusUpdated,
            "MessagesMarkedAsRead": MessagesMarkedAsRead,
            "TypingStarted": TypingStarted,
            "TypingStopped": TypingStopped,
            "TelegramChatLinked": TelegramChatLinked,
            "TelegramChatUnlinked": TelegramChatUnlinked,
            "TelegramMessageReceived": TelegramMessageReceived,
        },
        projection_config={
            "aggregate_type": "Chat",
            "transport_topic": CHAT_EVENTS_TOPIC
        },
        # Chat messages use Snowflake IDs for ordering in ScyllaDB - no sequence tracking needed
        enable_sequence_tracking=False
    )


# =============================================================================
# DOMAIN REGISTRY CLASS
# =============================================================================

class DomainRegistry:
    """Central registry for domain event processing configuration"""

    def __init__(self):
        self._domains: Dict[str, DomainRegistration] = {}
        self._topic_to_domains: Dict[str, List[DomainRegistration]] = {}
        self._initialized = False
        self.projectors: Dict[str, Any] = {}
        # NOTE: sync_events tracking removed - now uses projector_decorators.get_all_sync_events()

    def register(self, domain: DomainRegistration) -> None:
        """Register a domain configuration"""
        if domain.name in self._domains:
            raise ValueError(f"Domain {domain.name} already registered")

        self._domains[domain.name] = domain

        # Register topics
        for topic in domain.topics:
            if topic not in self._topic_to_domains:
                self._topic_to_domains[topic] = []
            self._topic_to_domains[topic].append(domain)

        # NOTE: sync_events tracking removed - single source of truth is @sync_projection decorator

        log.info(f"Registered domain: {domain.name} for topics: {domain.topics}")

    def get_projector(self, domain_name: str) -> Optional[Any]:
        """Get projector for a domain"""
        domain = self._domains.get(domain_name)
        if domain and domain.has_projector():
            return domain.projector_instance
        return self.projectors.get(domain_name)

    def get_all_projectors(self) -> List[Any]:
        """Get all registered projectors"""
        return [d.projector_instance for d in self._domains.values() if d.has_projector()]

    def get_sync_events(self) -> Set[str]:
        """Get list of all sync event types from @sync_projection decorators"""
        return get_all_sync_events()

    def get_all_sync_events(self) -> Set[str]:
        """Get list of all sync event types from @sync_projection decorators"""
        return get_all_sync_events()

    def is_sync_event(self, event_type: str) -> bool:
        """Check if an event type is configured for synchronous projection"""
        return event_type in get_all_sync_events()

    def get_enabled_domains(self) -> List[DomainRegistration]:
        """Get list of enabled domains"""
        return [d for d in self._domains.values() if d.enabled]

    def get_domains_for_topic(self, topic: str) -> List[DomainRegistration]:
        """Get domains that handle events from a topic"""
        return self._topic_to_domains.get(topic, [])

    async def initialize_all(self, event_bus=None, auth_service=None, cache_manager=None, query_bus=None, command_bus=None):
        """Initialize all domain projectors"""
        if self._initialized:
            log.warning("Domain registry already initialized")
            return True

        log.info("Initializing domain projectors...")

        for domain in self.get_enabled_domains():
            try:
                await domain.initialize_projector()
                if domain.has_projector():
                    self.projectors[domain.name] = domain.projector_instance
                    log.info(f"Domain projector ready: {domain.name}")
            except Exception as e:
                log.error(f"Failed to initialize domain {domain.name}: {e}")

        self._initialized = True
        return True


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_domain_registry = None


def create_domain_registry() -> DomainRegistry:
    """Create and populate the domain registry"""
    global _domain_registry

    if _domain_registry is None:
        registry = DomainRegistry()

        # Register WellWon domains
        registry.register(create_user_account_domain())
        registry.register(create_company_domain())
        registry.register(create_chat_domain())

        log.info(f"Domain registry created with {len(registry._domains)} domains")
        _domain_registry = registry

    return _domain_registry


def get_domain_registry() -> DomainRegistry:
    """Get or create domain registry singleton"""
    return create_domain_registry()


# =============================================================================
# EOF
# =============================================================================
