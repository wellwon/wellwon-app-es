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

log = logging.getLogger("wellwon.worker.domain_registry")

# Topic constants
USER_ACCOUNT_EVENTS_TOPIC = "transport.user-account-events"


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

    from app.user_account.events import (
        UserAccountCreated,
        UserAccountDeleted,
        UserEmailVerified,
        UserProfileUpdated,
        UserAuthenticationSucceeded,
        UserPasswordChanged,
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

    sync_events = {
        "UserAccountCreated",
        "UserAccountDeleted",
        "UserEmailVerified",
        "UserProfileUpdated",
    }

    return DomainRegistration(
        name="user_account",
        topics=[USER_ACCOUNT_EVENTS_TOPIC],
        projector_factory=user_projector_factory,
        event_models={
            "UserAccountCreated": UserAccountCreated,
            "UserAccountDeleted": UserAccountDeleted,
            "UserEmailVerified": UserEmailVerified,
            "UserProfileUpdated": UserProfileUpdated,
            "UserAuthenticationSucceeded": UserAuthenticationSucceeded,
            "UserPasswordChanged": UserPasswordChanged,
        },
        projection_config={
            "aggregate_type": "UserAccount",
            "transport_topic": USER_ACCOUNT_EVENTS_TOPIC
        },
        sync_events=sync_events,
        enable_sequence_tracking=True
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
        self.sync_events: List[str] = []

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

        # Track sync events
        self.sync_events.extend(domain.sync_events)

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

    def get_sync_events(self) -> List[str]:
        """Get list of all sync event types"""
        return self.sync_events

    def get_all_sync_events(self) -> List[str]:
        """Get list of all sync event types"""
        return self.sync_events

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

        # TODO: Add more domains as they're created
        # registry.register(create_company_domain())
        # registry.register(create_shipment_domain())

        log.info(f"Domain registry created with {len(registry._domains)} domains")
        _domain_registry = registry

    return _domain_registry


def get_domain_registry() -> DomainRegistry:
    """Get or create domain registry singleton"""
    return create_domain_registry()


# =============================================================================
# EOF
# =============================================================================
