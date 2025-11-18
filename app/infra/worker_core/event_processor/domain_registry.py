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

    def register_user_account_domain(self):
        """Register User Account domain projector"""
        try:
            from app.user_account.projectors import UserAccountProjector
            from app.infra.read_repos.user_account_read_repo import UserAccountReadRepo

            user_repo = UserAccountReadRepo()
            user_projector = UserAccountProjector(user_repo)

            self.projectors['user_account'] = user_projector

            # Register sync events for user_account
            self.sync_events.extend([
                "UserAccountCreated",
                "UserAccountDeleted",
                "UserEmailVerified",
                "UserProfileUpdated",
            ])

            log.info("✅ User Account domain registered")
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


# Singleton instance
_domain_registry = None


def get_domain_registry() -> DomainRegistry:
    """Get or create domain registry singleton"""
    global _domain_registry
    if _domain_registry is None:
        _domain_registry = DomainRegistry()
        _domain_registry.register_all_domains()
    return _domain_registry


# =============================================================================
# EOF
# =============================================================================
