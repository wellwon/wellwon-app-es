# app/user_account/query_handlers/operational_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/operational_query_handlers.py
# Description: Query handlers for operational status & access control - CQRS COMPLIANT
# =============================================================================

import logging
from typing import TYPE_CHECKING, Any

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.cqrs_decorators import query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUserOperationalStatusQuery,
    GetUserBrokerAccessQuery,
    GetUserTradingRestrictionsQuery,
    GetUserOperationalLimitsQuery,
)
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Operational Query Handlers - CQRS Compliant
# =============================================================================

@readonly_query(GetUserOperationalStatusQuery)
class GetUserOperationalStatusQueryHandler(BaseQueryHandler[GetUserOperationalStatusQuery, dict[str, Any]]):
    """Handler for getting user operational status - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        # Only use user domain repository
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserOperationalStatusQuery) -> dict[str, Any]:
        """Get operational status for user - user domain data only"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        status = {
            'user_id': str(query.user_id),
            'is_active': profile.is_active,
            'is_operational': profile.is_active and profile.email_verified,
            'role': profile.role,
            'restrictions': []
        }

        # Check for user-level restrictions
        if not profile.is_active:
            status['restrictions'].append('account_inactive')
        if not getattr(profile, 'email_verified', False):
            status['restrictions'].append('email_not_verified')

        # Add user-specific operational info if requested
        if query.include_connection_status:
            # User domain only knows which brokers are connected
            connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)
            status['connection_status'] = {
                'total_brokers_connected': len(connected_brokers or []),
                'connected_brokers': connected_brokers or []
            }

        if query.include_account_status:
            # User domain only knows account mappings
            account_mappings = await self.user_repo.get_account_mappings(query.user_id)
            status['account_status'] = {
                'total_mappings': len(account_mappings or {}),
                'mapped_asset_types': list((account_mappings or {}).keys())
            }

        return status


@readonly_query(GetUserBrokerAccessQuery)
class GetUserBrokerAccessQueryHandler(BaseQueryHandler[GetUserBrokerAccessQuery, dict[str, Any]]):
    """Handler for checking broker access - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserBrokerAccessQuery) -> dict[str, Any]:
        """Check user's access to broker operations based on user domain data"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        access = {
            'user_id': str(query.user_id),
            'broker_id': query.broker_id,
            'operation': query.operation,
            'has_access': False,
            'reasons': []
        }

        # Basic user-level checks
        if not profile.is_active:
            access['reasons'].append('user_inactive')
            return access

        # Check if user has this broker connected
        connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)
        broker_connected = False

        for broker_data in (connected_brokers or []):
            if isinstance(broker_data, str) and broker_data.lower().startswith(query.broker_id.lower()):
                broker_connected = True
                break
            elif isinstance(broker_data, dict) and broker_data.get('broker_id', '').lower() == query.broker_id.lower():
                broker_connected = True
                break

        if not broker_connected:
            access['reasons'].append('broker_not_connected_for_user')
            return access

        # Check operation-specific access based on user role
        if query.operation == "trade":
            if profile.role in ['user', 'trader', 'admin']:
                access['has_access'] = True
            else:
                access['reasons'].append('insufficient_role_for_trading')

        elif query.operation == "data":
            # Most users can access data
            access['has_access'] = True

        elif query.operation == "account_management":
            # All active users can manage their accounts
            access['has_access'] = True

        else:
            access['reasons'].append('unknown_operation')

        return access


@readonly_query(GetUserTradingRestrictionsQuery)
class GetUserTradingRestrictionsQueryHandler(BaseQueryHandler[GetUserTradingRestrictionsQuery, dict[str, Any]]):
    """Handler for getting trading restrictions - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserTradingRestrictionsQuery) -> dict[str, Any]:
        """Get user's trading restrictions from user domain"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        restrictions = {
            'user_id': str(query.user_id),
            'global_restrictions': [],
            'broker_restrictions': {}
        }

        # Check user metadata for trading restrictions
        metadata = getattr(profile, 'metadata', {})
        trading_config = metadata.get('trading_config', {})

        # Global restrictions
        if trading_config.get('day_trading_disabled'):
            restrictions['global_restrictions'].append('day_trading_disabled')

        if trading_config.get('options_trading_disabled'):
            restrictions['global_restrictions'].append('options_trading_disabled')

        if trading_config.get('margin_trading_disabled'):
            restrictions['global_restrictions'].append('margin_trading_disabled')

        if trading_config.get('max_order_size'):
            restrictions['global_restrictions'].append({
                'type': 'max_order_size',
                'value': trading_config['max_order_size']
            })

        # Broker-specific restrictions
        if query.broker_id:
            broker_config = trading_config.get('brokers', {}).get(query.broker_id, {})
            if broker_config:
                restrictions['broker_restrictions'][query.broker_id] = broker_config
        else:
            # Return all broker restrictions
            restrictions['broker_restrictions'] = trading_config.get('brokers', {})

        return restrictions


@readonly_query(GetUserOperationalLimitsQuery)
class GetUserOperationalLimitsQueryHandler(BaseQueryHandler[GetUserOperationalLimitsQuery, dict[str, Any]]):
    """Handler for getting operational limits - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserOperationalLimitsQuery) -> dict[str, Any]:
        """Get operational limits for user"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        limits = {
            'user_id': str(query.user_id),
            'limit_type': query.limit_type,
            'limits': {},
            'current_usage': {}
        }

        # Get limits based on user role and type
        if query.limit_type == "api_calls":
            # Rate limits based on role
            if profile.role == 'admin':
                limits['limits'] = {
                    'per_minute': 1000,
                    'per_hour': 50000,
                    'per_day': 500000
                }
            elif profile.role == 'trader':
                limits['limits'] = {
                    'per_minute': 100,
                    'per_hour': 5000,
                    'per_day': 50000
                }
            else:
                limits['limits'] = {
                    'per_minute': 60,
                    'per_hour': 1000,
                    'per_day': 10000
                }

            # Get current usage from cache
            for period in ['minute', 'hour', 'day']:
                cache_key = self.cache_manager._make_key('rate_limit', str(query.user_id), 'api', period)
                usage = await self.cache_manager.get(cache_key)
                limits['current_usage'][f'per_{period}'] = int(usage) if usage else 0

        elif query.limit_type == "orders":
            # Order limits
            limits['limits'] = {
                'max_open_orders': 100,
                'max_orders_per_minute': 10,
                'max_order_value': 1000000
            }

            # Get current open orders count from cache
            cache_key = self.cache_manager._make_key('limits', 'user', str(query.user_id), 'open_orders')
            open_orders = await self.cache_manager.get(cache_key)
            limits['current_usage']['open_orders'] = int(open_orders) if open_orders else 0

        elif query.limit_type == "connections":
            # Connection limits
            limits['limits'] = {
                'max_broker_connections': 10,
                'max_accounts_per_broker': 5,
                'max_total_accounts': 25
            }

            # Get current counts from user domain
            connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)
            account_mappings = await self.user_repo.get_account_mappings(query.user_id)

            limits['current_usage'] = {
                'broker_connections': len(connected_brokers or []),
                'total_account_mappings': len(account_mappings or {})
            }

        return limits

# =============================================================================
# EOF
# =============================================================================