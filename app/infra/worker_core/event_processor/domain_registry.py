# =============================================================================
# File: app/infra/worker_core/event_processor/domain_registry.py
# Description: Domain Registry for WellWon Platform
# Registers domain projectors for event processing
# =============================================================================

import logging
from typing import Dict, Any, List

log = logging.getLogger("wellwon.worker.domain_registry")


class DomainRegistry:
    """
    Registry for domain projectors in WellWon Platform.

    Domains:
    - user_account: User authentication and profiles
    - (more domains to be added: company, shipment, customs, payment, document)
    """

    def __init__(self):
        self.projectors: Dict[str, Any] = {}
        self.sync_events: List[str] = []
        self._domains: Dict[str, Any] = {}
        self._topic_mappings: Dict[str, List[str]] = {
            "transport.user-account-events": ["user_account"]
        }

    def register_user_account_domain(self):
        """Register User Account domain projector"""
        try:
            from app.user_account.projectors import UserAccountProjector
            from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

            user_repo = UserAccountReadRepo()
            user_projector = UserAccountProjector(user_repo)

            self.projectors['user_account'] = user_projector
            self._domains['user_account'] = {
                'projector': user_projector,
                'enabled': True,
                'topic': 'transport.user-account-events'
            }

            # Register sync events for user_account
            self.sync_events.extend([
                "UserAccountCreated",
                "UserAccountDeleted",
                "UserEmailVerified",
                "UserProfileUpdated",
            ])

            log.info("User Account domain registered")
            return user_projector

        except Exception as e:
            log.error(f"Failed to register User Account domain: {e}")
            return None

    def register_all_domains(self):
        """Register all WellWon domains"""
        log.info("Registering WellWon domains...")

        # User Account domain
        self.register_user_account_domain()

        # TODO: Register other domains:
        # - company
        # - shipment
        # - customs
        # - payment
        # - document

        log.info(f"Domain registry initialized with {len(self.projectors)} domains")
        log.info(f"Sync events registered: {len(self.sync_events)}")

        return self.projectors

    def get_projector(self, domain_name: str):
        """Get projector for a domain"""
        return self.projectors.get(domain_name)

    def get_all_projectors(self):
        """Get all registered projectors"""
        return list(self.projectors.values())

    def get_sync_events(self):
        """Get list of all sync event types"""
        return self.sync_events

    def get_all_sync_events(self):
        """Get list of all sync event types (alias for get_sync_events)"""
        return self.sync_events

    def get_enabled_domains(self):
        """Get list of enabled domain names"""
        return [name for name, info in self._domains.items() if info.get('enabled', True)]

    def get_domains_for_topic(self, topic: str) -> List[str]:
        """Get domain names that handle events from a topic"""
        return self._topic_mappings.get(topic, [])

    async def initialize_all(self, event_bus=None, auth_service=None, cache_manager=None, query_bus=None, command_bus=None):
        """Initialize all domain projectors with dependencies"""
        log.info("Initializing domain projectors with dependencies...")
        # Projectors are already registered, this just validates they're ready
        for name, projector in self.projectors.items():
            log.info(f"Domain projector ready: {name}")
        return True


# Singleton instance
_domain_registry = None


def get_domain_registry() -> DomainRegistry:
    """Get or create domain registry singleton"""
    global _domain_registry
    if _domain_registry is None:
        _domain_registry = DomainRegistry()
        _domain_registry.register_all_domains()
    return _domain_registry


# Alias for backwards compatibility
def create_domain_registry() -> DomainRegistry:
    """Create domain registry - alias for get_domain_registry"""
    return get_domain_registry()


# =============================================================================
# EOF
# =============================================================================
