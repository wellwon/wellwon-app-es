# app/user_account/query_handlers/monitoring_query_handlers.py
# =============================================================================
# File: app/user_account/query_handlers/monitoring_query_handlers.py
# Description: Query handlers for monitoring, analytics & compliance - CQRS COMPLIANT
# =============================================================================

import logging
from typing import TYPE_CHECKING, Any
from datetime import datetime, timezone, timedelta

from app.infra.cqrs.query_bus import IQueryHandler
from app.infra.cqrs.decorators import query_handler, readonly_query, cached_query_handler, readonly_query
from app.common.base.base_query_handler import BaseQueryHandler
from app.user_account.queries import (
    GetUsersWithActiveMonitoringQuery,
    GetUserMonitoringStatusQuery,
    GetUserSystemHealthQuery,
    GetUsersRequiringAttentionQuery,
    GetUserActivityMetricsQuery,
    GetUserComplianceStatusQuery,
    BatchGetUserStatusQuery,
    GetInactiveUsersQuery,
    GetUserAuditTrailQuery,
    UserMonitoringStatus,
    UserSystemHealth,
    UserActivityMetrics,
    UserComplianceStatus,
    UserAuditEntry,
    GetUserProfileQuery,
    GetUserActiveSessionsQuery,
)
from app.common.exceptions.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies


# =============================================================================
# Monitoring Query Handlers - CQRS Compliant
# =============================================================================

@readonly_query(GetUsersWithActiveMonitoringQuery)
class GetUsersWithActiveMonitoringQueryHandler(BaseQueryHandler[GetUsersWithActiveMonitoringQuery, list[UserMonitoringStatus]]):
    """Handler for getting users with active monitoring - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUsersWithActiveMonitoringQuery) -> list[UserMonitoringStatus]:
        """Get users that have active monitoring from cache"""
        results = []

        # This would need a more efficient implementation in production
        # For now, return empty list as we can't scan all users efficiently
        self.log.info(f"GetUsersWithActiveMonitoringQuery: Would need dedicated index for efficiency")

        return results


@cached_query_handler(GetUserMonitoringStatusQuery, ttl=60)
class GetUserMonitoringStatusQueryHandler(BaseQueryHandler[GetUserMonitoringStatusQuery, UserMonitoringStatus]):
    """Handler for getting user monitoring status - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserMonitoringStatusQuery) -> UserMonitoringStatus:
        """Get monitoring status for user - user domain data only"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        # Get user domain data
        connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)
        account_mappings = await self.user_repo.get_account_mappings(query.user_id)

        # Determine health status based on user domain data
        health_status = "healthy"
        issues = []

        # Check if user is active
        if not profile.is_active:
            health_status = "error"
            issues.append({
                'type': 'user_inactive',
                'severity': 'critical',
                'description': 'User account is inactive'
            })

        # Check if email is verified
        if not getattr(profile, 'email_verified', False):
            health_status = "warning" if health_status == "healthy" else health_status
            issues.append({
                'type': 'email_not_verified',
                'severity': 'warning',
                'description': 'Email not verified'
            })

        # Check monitoring metadata from cache
        monitoring_metadata = {}
        cache_key = self.cache_manager._make_key('monitoring', 'user', str(query.user_id))
        monitoring_data = await self.cache_manager.get_json(cache_key)
        if monitoring_data:
            monitoring_metadata = monitoring_data

        status = UserMonitoringStatus(
            user_id=query.user_id,
            is_monitored=len(connected_brokers or []) > 0,
            monitoring_level="standard",  # Could be determined by user subscription
            total_connections=len(connected_brokers or []),
            active_connections=0,  # User domain doesn't track connection state
            total_accounts=len(account_mappings or {}),
            health_status=health_status,
            last_activity=profile.last_login,
            issues=issues,
            monitoring_metadata=monitoring_metadata
        )

        return status


@readonly_query(GetUserSystemHealthQuery)
class GetUserSystemHealthQueryHandler(BaseQueryHandler[GetUserSystemHealthQuery, UserSystemHealth]):
    """Handler for getting user system health - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.query_bus = deps.query_bus

    async def handle(self, query: GetUserSystemHealthQuery) -> UserSystemHealth:
        """Get overall system health for user"""
        now = datetime.now(timezone.utc)

        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        # Initialize health data
        broker_health = {}
        account_health = {}
        session_health = {}
        recommendations = []

        # Check broker health (user domain perspective)
        if query.include_broker_health:
            connected_brokers = await self.user_repo.get_connected_brokers(query.user_id)

            broker_health = {
                'total_brokers_connected': len(connected_brokers or []),
                'brokers': connected_brokers or [],
                'health_status': 'healthy' if connected_brokers else 'warning'
            }

            if not connected_brokers:
                recommendations.append("Connect to at least one broker")

        # Check account health (user domain perspective)
        if query.include_account_health:
            account_mappings = await self.user_repo.get_account_mappings(query.user_id)

            account_health = {
                'total_mappings': len(account_mappings or {}),
                'mapped_asset_types': list((account_mappings or {}).keys()),
                'health_status': 'healthy' if account_mappings else 'warning'
            }

            if not account_mappings:
                recommendations.append("Map at least one account to an asset type")

        # Check session health
        if query.include_session_health:
            # Use query bus for sessions
            sessions = await self.query_bus.query(
                GetUserActiveSessionsQuery(user_id=query.user_id, include_expired=False)
            )

            active_sessions = len(sessions)
            expiring_soon = 0

            for session in sessions:
                if (session.expires_at - now).total_seconds() < 3600:  # 1 hour
                    expiring_soon += 1

            session_health = {
                'active_sessions': active_sessions,
                'expiring_soon': expiring_soon,
                'session_health': 'healthy' if active_sessions > 0 else 'warning'
            }

            if expiring_soon > 0:
                recommendations.append(f"{expiring_soon} sessions expiring soon")

        # Determine overall status
        overall_status = "healthy"

        if not profile.is_active:
            overall_status = "critical"
        elif broker_health.get('health_status') == 'warning':
            overall_status = "degraded"
        elif session_health.get('active_sessions', 0) == 0:
            overall_status = "degraded"

        return UserSystemHealth(
            user_id=query.user_id,
            overall_status=overall_status,
            last_check_time=now,
            broker_health=broker_health,
            account_health=account_health,
            session_health=session_health,
            recommendations=recommendations
        )


@readonly_query(GetUsersRequiringAttentionQuery)
class GetUsersRequiringAttentionQueryHandler(BaseQueryHandler[GetUsersRequiringAttentionQuery, list[dict[str, Any]]]):
    """Handler for finding users with issues - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUsersRequiringAttentionQuery) -> list[dict[str, Any]]:
        """Get users with issues requiring attention"""
        results = []

        # This would need a more efficient implementation in production
        # Would require dedicated indexes or monitoring tables
        self.log.info(f"GetUsersRequiringAttentionQuery: Would need dedicated monitoring infrastructure")

        return results


@cached_query_handler(GetUserActivityMetricsQuery, ttl=300)
class GetUserActivityMetricsQueryHandler(BaseQueryHandler[GetUserActivityMetricsQuery, UserActivityMetrics]):
    """Handler for getting user activity metrics - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserActivityMetricsQuery) -> UserActivityMetrics:
        """Get activity metrics for monitoring"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        # Default metrics
        metrics = UserActivityMetrics(
            user_id=query.user_id,
            period_days=query.period_days,
            total_logins=0,
            unique_login_days=0,
            average_session_duration_minutes=0.0,
            total_trades=0,
            total_volume=0.0,
            most_active_broker=None,
            activity_trend="stable",
            last_activity_time=profile.last_login
        )

        # Get metrics from cache if available
        cache_key = self.cache_manager._make_key('metrics', 'user', 'activity', str(query.user_id))
        cached_metrics = await self.cache_manager.get_json(cache_key)

        if cached_metrics:
            metrics.total_logins = cached_metrics.get('total_logins', 0)
            metrics.unique_login_days = cached_metrics.get('unique_login_days', 0)
            metrics.average_session_duration_minutes = cached_metrics.get('average_session_duration_minutes', 0.0)

            if query.include_trading_activity:
                metrics.total_trades = cached_metrics.get('total_trades', 0)
                metrics.total_volume = cached_metrics.get('total_volume', 0.0)
                metrics.most_active_broker = cached_metrics.get('most_active_broker')

            # Determine activity trend
            previous_period_logins = cached_metrics.get('previous_period_logins', 0)
            if previous_period_logins > 0:
                change_percent = ((metrics.total_logins - previous_period_logins) / previous_period_logins) * 100
                if change_percent > 20:
                    metrics.activity_trend = "increasing"
                elif change_percent < -20:
                    metrics.activity_trend = "decreasing"

        return metrics


@readonly_query(GetUserComplianceStatusQuery)
class GetUserComplianceStatusQueryHandler(BaseQueryHandler[GetUserComplianceStatusQuery, UserComplianceStatus]):
    """Handler for getting user compliance status - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.user_repo = deps.user_read_repo

    async def handle(self, query: GetUserComplianceStatusQuery) -> UserComplianceStatus:
        """Get compliance status for monitoring"""
        # Get user profile
        profile = await self.user_repo.get_user_profile_by_user_id(query.user_id)

        profile = self.handle_not_found(
            resource=profile,
            resource_type="User",
            resource_id=query.user_id
        )

        # Get compliance data from profile metadata
        metadata = getattr(profile, 'metadata', {})
        compliance_data = metadata.get('compliance', {})

        # Default status
        status = UserComplianceStatus(
            user_id=query.user_id,
            is_compliant=True,
            kyc_status="not_started",
            agreements_signed=False,
            trading_restrictions=[],
            compliance_issues=[],
            last_review_date=None,
            next_review_date=None
        )

        # Check KYC
        if query.check_kyc:
            status.kyc_status = compliance_data.get('kyc_status', 'not_started')
            if status.kyc_status not in ['verified', 'pending']:
                status.is_compliant = False
                status.compliance_issues.append({
                    'type': 'kyc_incomplete',
                    'severity': 'high',
                    'description': 'KYC verification not completed'
                })

        # Check agreements
        if query.check_agreements:
            status.agreements_signed = compliance_data.get('agreements_signed', False)
            if not status.agreements_signed:
                status.is_compliant = False
                status.compliance_issues.append({
                    'type': 'agreements_missing',
                    'severity': 'medium',
                    'description': 'Required agreements not signed'
                })

        # Check restrictions
        if query.check_restrictions:
            status.trading_restrictions = compliance_data.get('trading_restrictions', [])

        # Set review dates
        if compliance_data.get('last_review_date'):
            status.last_review_date = datetime.fromisoformat(compliance_data['last_review_date'])
        if compliance_data.get('next_review_date'):
            status.next_review_date = datetime.fromisoformat(compliance_data['next_review_date'])

        return status


@readonly_query(BatchGetUserStatusQuery)
class BatchGetUserStatusQueryHandler(BaseQueryHandler[BatchGetUserStatusQuery, dict[str, dict[str, Any]]]):
    """Handler for batch user status retrieval - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.query_bus = deps.query_bus

    async def handle(self, query: BatchGetUserStatusQuery) -> dict[str, dict[str, Any]]:
        """Batch get status for multiple users using query bus"""
        results = {}

        for user_id in query.user_ids:
            try:
                # Use query bus to get user profile
                profile = await self.query_bus.query(
                    GetUserProfileQuery(user_id=user_id)
                )

                if not profile:
                    continue

                user_status = {
                    'user_id': str(user_id),
                    'username': profile.username,
                    'is_active': profile.is_active,
                    'last_login': profile.last_login.isoformat() if profile.last_login else None
                }

                # Note: For true CQRS compliance, we'd need separate queries
                # for connections and accounts rather than including them here

                results[str(user_id)] = user_status

            except Exception as e:
                self.log.error(f"Failed to get status for user {user_id}: {e}")

        return results


@readonly_query(GetInactiveUsersQuery)
class GetInactiveUsersQueryHandler(BaseQueryHandler[GetInactiveUsersQuery, list[dict[str, Any]]]):
    """Handler for finding inactive users - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()

    async def handle(self, query: GetInactiveUsersQuery) -> list[dict[str, Any]]:
        """Get users with no recent activity"""
        results = []

        # This would need implementation at the repository or database level
        # Cannot efficiently scan all users from handler
        self.log.info(f"GetInactiveUsersQuery: Would need dedicated database query")

        return results


@readonly_query(GetUserAuditTrailQuery)
class GetUserAuditTrailQueryHandler(BaseQueryHandler[GetUserAuditTrailQuery, list[UserAuditEntry]]):
    """Handler for getting user audit trail - CQRS COMPLIANT"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.cache_manager = deps.cache_manager

    async def handle(self, query: GetUserAuditTrailQuery) -> list[UserAuditEntry]:
        """Get audit trail from cache"""
        entries = []

        # Get recent audit events from cache
        cache_pattern = self.cache_manager._make_key('audit', 'user', str(query.user_id), '*')

        # This would need a proper audit log implementation
        self.log.info(f"GetUserAuditTrailQuery: Would need dedicated audit infrastructure")

        return entries

# =============================================================================
# EOF
# =============================================================================