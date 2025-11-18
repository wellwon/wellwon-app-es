# app/user_account/query_handlers/mapping_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/mapping_query_handlers.py
# Description: Query handlers for user broker/account mappings - CQRS COMPLIANT
# =============================================================================

import logging
from typing import TYPE_CHECKING, Any
from datetime import datetime, timezone

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.decorators import query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUserConnectedBrokersQuery,
    GetUserAccountMappingsQuery,
    GetUserOAuthStateQuery,
    GetUserCredentialsSummaryQuery,
    ConnectedBroker,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Mapping Query Handlers - CQRS Compliant
# =============================================================================

@query_handler(GetUserConnectedBrokersQuery)
class GetUserConnectedBrokersQueryHandler(BaseQueryHandler[GetUserConnectedBrokersQuery, list[ConnectedBroker]]):
    """Handler for getting user's connected brokers - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Only use user domain repository
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserConnectedBrokersQuery) -> list[ConnectedBroker]:
        """Get list of brokers connected by this user"""
        # Get connected brokers from user repository (user domain data)
        connected_brokers_data = await self.user_repo.get_connected_brokers(query.user_id)

        brokers = []

        # Transform user's broker data
        if connected_brokers_data and isinstance(connected_brokers_data, list):
            for broker_data in connected_brokers_data:
                if isinstance(broker_data, dict):
                    # Handle dictionary format
                    brokers.append(ConnectedBroker(
                        broker_id=broker_data.get('broker_id'),
                        broker_name=broker_data.get('broker_name', broker_data.get('broker_id', '').title()),
                        environments=[],  # User domain doesn't track environments
                        total_accounts=broker_data.get('account_count', 0),
                        connection_ids=[]  # User domain doesn't track connection IDs
                    ))
                elif isinstance(broker_data, str):
                    # Handle simple string format (broker:environment)
                    parts = broker_data.split(':')
                    broker_id = parts[0]
                    environment = parts[1] if len(parts) > 1 else 'unknown'

                    # Check if we already have this broker
                    existing = next((b for b in brokers if b.broker_id == broker_id), None)
                    if existing:
                        existing.environments.append({'environment': environment})
                    else:
                        brokers.append(ConnectedBroker(
                            broker_id=broker_id,
                            broker_name=broker_id.title(),
                            environments=[{'environment': environment}],
                            total_accounts=0,
                            connection_ids=[]
                        ))

        return brokers


@readonly_query(GetUserAccountMappingsQuery)
class GetUserAccountMappingsQueryHandler(BaseQueryHandler[GetUserAccountMappingsQuery, dict[str, list[str]]]):
    """Handler for getting user's broker account mappings - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserAccountMappingsQuery) -> dict[str, list[str]]:
        """Get broker account mappings from user domain"""
        mappings = {}

        # Get mappings from user repository or cache
        # Get all asset types we know about
        asset_types = ['stocks', 'options', 'crypto', 'forex', 'futures', 'multi']

        for asset_type in asset_types:
            # Use the repository method if available, otherwise check cache
            try:
                mapping = await self.user_repo.get_account_mapping(query.user_id, asset_type)
                if mapping:
                    mappings[asset_type] = [mapping]
            except AttributeError:
                # Fallback to cache if repository method doesn't exist
                key = self.cache_manager._make_key('user', str(query.user_id), 'account_mapping', asset_type)
                account_id = await self.cache_manager.get(key)
                if account_id:
                    mappings[asset_type] = [account_id]

        # If broker_id filter is specified, we can't filter here as user domain
        # doesn't know which account belongs to which broker
        if query.broker_id:
            self.log.info(f"Broker filtering requested but not available in user domain")

        return mappings


@query_handler(GetUserOAuthStateQuery)
class GetUserOAuthStateQueryHandler(BaseQueryHandler[GetUserOAuthStateQuery, dict[str, Any]]):
    """Handler for getting user OAuth states - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # User domain only knows which brokers are connected, not OAuth details
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserOAuthStateQuery) -> dict[str, Any]:
        """Get OAuth states for user's brokers"""
        # Get connected brokers from user domain
        connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)

        oauth_states = {}

        # User domain doesn't store OAuth details, just broker connections
        for broker_data in (connected_brokers or []):
            if isinstance(broker_data, str):
                parts = broker_data.split(':')
                broker_id = parts[0]
                environment = parts[1] if len(parts) > 1 else 'unknown'

                if query.broker_id and broker_id.lower() != query.broker_id.lower():
                    continue

                if broker_id not in oauth_states:
                    oauth_states[broker_id] = []

                oauth_states[broker_id].append({
                    'environment': environment,
                    'has_oauth': None,  # User domain doesn't know
                    'token_expires_at': None,  # User domain doesn't know
                    'reauth_required': None,  # User domain doesn't know
                    'is_expired': None  # User domain doesn't know
                })

        return {
            'user_id': str(query.user_id),
            'oauth_states': oauth_states,
            'total_connections': len(connected_brokers or []),
            'connections_with_oauth': 0  # User domain doesn't track this
        }


@query_handler(GetUserCredentialsSummaryQuery)
class GetUserCredentialsSummaryQueryHandler(BaseQueryHandler[GetUserCredentialsSummaryQuery, dict[str, Any]]):
    """Handler for getting credentials summary - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserCredentialsSummaryQuery) -> dict[str, Any]:
        """Get summary of user's stored credentials"""
        # Get connected brokers from user domain
        connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)

        summary = {
            'user_id': str(query.user_id),
            'total_connections': len(connected_brokers or []),
            'credentials_by_type': {
                'oauth': 0,  # User domain doesn't track credential types
                'api_key': 0,
                'both': 0,
                'none': 0
            },
            'brokers': {}
        }

        # Parse connected brokers
        for broker_data in (connected_brokers or []):
            if isinstance(broker_data, str):
                parts = broker_data.split(':')
                broker_id = parts[0]
                environment = parts[1] if len(parts) > 1 else 'unknown'

                if broker_id not in summary['brokers']:
                    summary['brokers'][broker_id] = {
                        'connections': 0,
                        'environments': set(),
                        'has_expired_tokens': False,  # User domain doesn't know
                        'needs_reauth': False  # User domain doesn't know
                    }

                broker_info = summary['brokers'][broker_id]
                broker_info['connections'] += 1
                broker_info['environments'].add(environment)

        # Convert sets to lists for JSON serialization
        for broker_id in summary['brokers']:
            summary['brokers'][broker_id]['environments'] = list(
                summary['brokers'][broker_id]['environments']
            )

        return summary

# =============================================================================
# EOF
# =============================================================================